"""Hydra/Lightning-free multi-view generation.

RCP and final target generation share one source encoding and prompt embedding.
Target groups execute sequentially on one GPU or concurrently across multiple
GPUs; TCR optionally shifts their membership between denoising steps.
"""

from __future__ import annotations

import gc
import logging
import math
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, TypedDict

import numpy as np
from PIL import Image

from fdanyone.assets import BaseAssets
from fdanyone.config import INFERENCE
from fdanyone.errors import FourDAnyoneError
from fdanyone.model.conditioning import PoseFeatureBank, PoseFeatureCache, build_pose_feature_cache, load_prompt_context
from fdanyone.model.denoise import denoise_group
from fdanyone.model.distributed import Routes, WorkerReport, denoise_targets_distributed, select_worker_devices
from fdanyone.model.loader import Denoiser, load_denoiser, load_vae
from fdanyone.model.metrics import GenerationMetrics
from fdanyone.model.routing import routing_steps
from fdanyone.skeleton.pipeline import Conditioning
from fdanyone.video import CanonicalClip, write_video
from fdanyone.views import ViewPlan

if TYPE_CHECKING:
    from torch import Tensor, nn

    from fdanyone.vendor.diffsynth.models.wan_video_vae import WanVideoVAE38

LOGGER = logging.getLogger("fdanyone")


class ParallelismReport(TypedDict):
    """The target-denoising topology and measurements written to metadata."""

    backend: str
    candidate_devices: list[str]
    used_devices: list[str]
    groups_per_step: int
    waves_per_step: int
    workers: list[WorkerReport]


@dataclass(frozen=True)
class GeneratedViews:
    """Paths and measurements produced by one resolved view plan."""

    rcp_videos: tuple[Path, ...]
    target_videos: tuple[Path, ...]
    view_plan: ViewPlan
    seed: int
    device: str
    elapsed_seconds: dict[str, float]
    stage_peak_vram_bytes: dict[str, dict[str, int]]
    peak_vram_allocated_bytes: int
    peak_vram_reserved_bytes: int
    parallelism: ParallelismReport | None = None


@dataclass(frozen=True)
class _GenerationPlan:
    view_plan: ViewPlan
    device: str
    device_index: int
    worker_devices: tuple[str, ...]

    @property
    def distributed(self) -> bool:
        return len(self.worker_devices) > 1

    @property
    def needs_primary_denoiser(self) -> bool:
        return self.view_plan.enable_rcp or not self.distributed


def _empty_cuda_cache() -> None:
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


@contextmanager
def _model_on_device(model: nn.Module, device: str) -> Iterator[nn.Module]:
    """Keep one model resident for exactly one exception-safe stage."""

    model.to(device)
    _empty_cuda_cache()
    try:
        yield model
    finally:
        model.to("cpu")
        _empty_cuda_cache()


def _tiler_kwargs() -> dict[str, bool | tuple[int, int]]:
    return {
        "tiled": INFERENCE.tiled_vae,
        "tile_size": INFERENCE.vae_tile_size,
        "tile_stride": INFERENCE.vae_tile_stride,
    }


def _bf16_autocast():
    """Match Lightning's ``bf16-mixed`` inference context without Lightning."""

    import torch

    return torch.autocast(device_type="cuda", dtype=torch.bfloat16)


def _channels_last_source_layout(video):
    """Preserve the frozen source tensor's VFHWC-backed VCFHW layout."""

    import torch

    if video.ndim != 5:
        raise FourDAnyoneError(f"Expected a 5D video tensor, got shape {tuple(video.shape)}.")
    return video.contiguous(memory_format=torch.channels_last_3d)


def _encode_videos(vae: WanVideoVAE38, videos: Tensor, device: str) -> Tensor:
    import torch

    videos = videos.to(dtype=torch.bfloat16, device=device)
    with torch.inference_mode(), _bf16_autocast():
        latents = vae.encode(videos, device=device, **_tiler_kwargs())
    return latents.detach().to("cpu")


def _noise(vae: WanVideoVAE38, num_views: int, num_frames: int, seed: int, device: str) -> Tensor:
    import torch

    shape = (
        num_views,
        vae.model.z_dim,
        (num_frames - 1) // 4 + 1,
        INFERENCE.height // vae.upsampling_factor,
        INFERENCE.width // vae.upsampling_factor,
    )
    generator = torch.Generator("cpu").manual_seed(seed)
    return torch.randn(shape, generator=generator, device="cpu", dtype=torch.float32).to(
        dtype=torch.bfloat16, device=device
    )


def _denoise_rcp(
    denoiser: Denoiser,
    vae: WanVideoVAE38,
    src_latents: Tensor,
    context: Tensor,
    camera_ids: tuple[int, ...],
    pose_features: PoseFeatureBank,
    device: str,
    seed: int,
) -> Tensor:
    import torch
    from tqdm.auto import tqdm

    if pose_features.num_features != len(camera_ids):
        raise FourDAnyoneError(f"RCP requires {len(camera_ids)} pose features, got {pose_features.num_features}.")
    denoiser.scheduler.set_timesteps(
        INFERENCE.num_inference_steps,
        denoising_strength=INFERENCE.denoising_strength,
        shift=INFERENCE.scheduler_shift,
    )
    latents = _noise(vae, len(camera_ids), INFERENCE.num_frames, seed, device)
    source = src_latents.to(dtype=denoiser.dtype, device=device)
    context = context.to(dtype=denoiser.dtype, device=device)
    pose_feature_batch = pose_features.allocate_group(len(camera_ids), device)
    pose_features.copy_group(tuple(range(len(camera_ids))), pose_feature_batch)
    null_pose_feature = pose_features.null_on(device)

    with torch.inference_mode(), _bf16_autocast():
        for step_index, _ in enumerate(tqdm(denoiser.scheduler.timesteps, desc=f"RCP 1-to-{len(camera_ids)}")):
            latents = denoise_group(
                denoiser,
                latents,
                source,
                context,
                pose_feature_batch,
                null_pose_feature,
                step_index,
            )
    return latents.detach().to("cpu")


def _tensor_frames(video) -> Iterable[np.ndarray]:
    """Match DiffSynth's float-to-uint8 truncation exactly."""

    frames = video.detach().float().add_(1.0).mul_(127.5).clamp_(0.0, 255.0).to("cpu")
    for frame_index in range(frames.shape[1]):
        yield frames[:, frame_index].permute(1, 2, 0).numpy().astype(np.uint8)


def _save_rcp_jpegs(video, camera_id: int, root: Path) -> Path:
    import torchvision.transforms.functional as transform

    frame_dir = root / f"{camera_id:06d}"
    frame_dir.mkdir(parents=True, exist_ok=False)
    normalized = video.detach().float().mul(0.5).add_(0.5).clamp_(0.0, 1.0).to("cpu")
    for frame_index in range(normalized.shape[1]):
        image = transform.to_pil_image(normalized[:, frame_index])
        image.save(frame_dir / f"{frame_index:06d}.jpg", quality=INFERENCE.rcp_jpeg_quality)
    return frame_dir


def _rcp_reference_video_layout(frame_first_video):
    """Match ``prepare_batch`` for JPEG-backed ``[V,F,C,H,W]`` data."""

    if frame_first_video.ndim != 5:
        raise FourDAnyoneError(f"Expected a 5D frame-first video tensor, got shape {tuple(frame_first_video.shape)}.")
    return frame_first_video.permute(0, 2, 1, 3, 4)


def _load_rcp_reference_videos(frame_dirs: Iterable[Path], num_frames: int):
    """Decode RCP references exactly like the frozen JPEG-backed input path."""

    import torch
    import torchvision.transforms.functional as transform

    videos = []
    for frame_dir in frame_dirs:
        frames = []
        for frame_index in range(num_frames):
            path = frame_dir / f"{frame_index:06d}.jpg"
            with Image.open(path) as image:
                frames.append(transform.to_tensor(image.convert("RGB")))
        videos.append(torch.stack(frames, dim=0))
    frame_first_video = torch.stack(videos, dim=0).mul_(2.0).sub_(1.0)
    return _rcp_reference_video_layout(frame_first_video)


def _decode_rcp(
    vae: WanVideoVAE38,
    latents: Tensor,
    camera_ids: tuple[int, ...],
    output_dir: Path,
    clip: CanonicalClip,
    device: str,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    import torch

    if latents.shape[0] != len(camera_ids):
        raise FourDAnyoneError(f"RCP decode expected {len(camera_ids)} latent views, got {latents.shape[0]}.")
    frame_root = output_dir / "frames"
    video_root = output_dir / "videos"
    frame_root.mkdir(parents=True, exist_ok=False)
    video_root.mkdir(parents=True, exist_ok=False)
    frame_outputs: list[Path] = []
    video_outputs: list[Path] = []
    with torch.inference_mode(), _bf16_autocast():
        for latent_index, camera_id in enumerate(camera_ids):
            LOGGER.info("Decoding RCP camera %02d", camera_id)
            video = vae.decode(
                latents[latent_index : latent_index + 1].to(dtype=torch.bfloat16, device=device),
                device=device,
                **_tiler_kwargs(),
            )[0]
            frame_outputs.append(_save_rcp_jpegs(video, camera_id, frame_root))
            video_outputs.append(
                write_video(
                    _tensor_frames(video),
                    video_root / f"{camera_id:02d}.mp4",
                    clip.fps,
                    crf=INFERENCE.target_h264_crf,
                    preset=INFERENCE.h264_preset,
                )
            )
            del video
            torch.cuda.empty_cache()
    return tuple(frame_outputs), tuple(video_outputs)


def _denoise_targets_single(
    denoiser: Denoiser,
    src_latents: Tensor,
    context: Tensor,
    pose_features: PoseFeatureBank,
    initial_latents: Tensor,
    routes: Routes,
    device: str,
) -> Tensor:
    import torch
    from tqdm.auto import tqdm

    num_views = initial_latents.shape[0]
    if pose_features.num_features != num_views:
        raise FourDAnyoneError(
            f"Target generation requires {num_views} pose features, got {pose_features.num_features}."
        )
    denoiser.scheduler.set_timesteps(
        INFERENCE.num_inference_steps,
        denoising_strength=INFERENCE.denoising_strength,
        shift=INFERENCE.scheduler_shift,
    )
    latents = initial_latents
    source = src_latents.to(dtype=denoiser.dtype, device=device)
    context = context.to(dtype=denoiser.dtype, device=device)
    null_pose_feature = pose_features.null_on(device)
    group_size = len(routes[0][0])
    pose_feature_batch = pose_features.allocate_group(group_size, device)

    with torch.inference_mode(), _bf16_autocast():
        for step_index, groups in enumerate(tqdm(routes, desc=f"Generate {num_views} target views")):
            for view_indices in groups:
                index = torch.tensor(view_indices, dtype=torch.long, device=device)
                local_latents = torch.index_select(latents, 0, index)
                pose_features.copy_group(view_indices, pose_feature_batch)
                local_latents = denoise_group(
                    denoiser,
                    local_latents,
                    source,
                    context,
                    pose_feature_batch,
                    null_pose_feature,
                    step_index,
                )
                latents.index_copy_(0, index, local_latents)
                del local_latents
    return latents.detach().to("cpu")


def _decode_targets(
    vae: WanVideoVAE38,
    latents: Tensor,
    output_dir: Path,
    clip: CanonicalClip,
    device: str,
) -> tuple[Path, ...]:
    import torch

    video_root = output_dir / "videos"
    video_root.mkdir(parents=True, exist_ok=False)
    outputs: list[Path] = []
    with torch.inference_mode(), _bf16_autocast():
        for camera_id in range(latents.shape[0]):
            LOGGER.info("Decoding target camera %02d", camera_id)
            video = vae.decode(
                latents[camera_id : camera_id + 1].to(dtype=torch.bfloat16, device=device),
                device=device,
                **_tiler_kwargs(),
            )[0]
            path = write_video(
                _tensor_frames(video),
                video_root / f"{camera_id:02d}.mp4",
                clip.fps,
                crf=INFERENCE.target_h264_crf,
                preset=INFERENCE.h264_preset,
            )
            outputs.append(path)
            del video
            torch.cuda.empty_cache()
    return tuple(outputs)


def _resolve_generation_plan(
    clip: CanonicalClip,
    conditioning: Conditioning,
    devices: tuple[str, ...],
    seed: int,
) -> _GenerationPlan:
    import torch

    if conditioning.num_frames != INFERENCE.num_frames or len(clip.frames) != INFERENCE.num_frames:
        raise FourDAnyoneError("Generation requires the frozen 121-frame contract.")
    if seed < 0:
        raise FourDAnyoneError(f"seed must be non-negative, got {seed}.")
    if not devices:
        raise FourDAnyoneError("Generation requires at least one CUDA device.")

    view_plan = conditioning.view_plan
    if len(conditioning.target_skeletons) != view_plan.num_target_views:
        raise FourDAnyoneError("Target skeleton count does not match the resolved view plan.")
    if len(conditioning.rcp_skeletons) != len(view_plan.rcp_camera_ids):
        raise FourDAnyoneError("RCP skeleton count does not match the resolved view plan.")

    device = devices[0]
    device_index = int(device.removeprefix("cuda:"))
    worker_devices = select_worker_devices(devices, view_plan.num_groups)
    LOGGER.info("Using %s (%s)", device, torch.cuda.get_device_name(device_index))
    if len(worker_devices) < len(devices):
        LOGGER.info(
            "Using %d of %d candidate GPUs for %d target groups",
            len(worker_devices),
            len(devices),
            view_plan.num_groups,
        )
    return _GenerationPlan(
        view_plan=view_plan,
        device=device,
        device_index=device_index,
        worker_devices=worker_devices,
    )


def _generate_rcp_and_references(
    *,
    denoiser: Denoiser,
    vae: WanVideoVAE38,
    source_latents: Tensor,
    context: Tensor,
    pose_cache: PoseFeatureCache,
    plan: _GenerationPlan,
    root: Path,
    clip: CanonicalClip,
    seed: int,
    metrics: GenerationMetrics,
) -> tuple[Tensor, tuple[Path, ...]]:
    import torch

    rcp_pose_features = pose_cache.rcp
    if rcp_pose_features is None:
        raise FourDAnyoneError("RCP was enabled without precomputed proposal pose features.")
    with metrics.stage("rcp_denoise"), _model_on_device(denoiser.model, plan.device):
        rcp_latents = _denoise_rcp(
            denoiser,
            vae,
            source_latents,
            context,
            plan.view_plan.rcp_camera_ids,
            rcp_pose_features,
            plan.device,
            seed,
        )

    with metrics.stage("rcp_decode_and_reference_encode"), _model_on_device(vae, plan.device):
        rcp_root = root / "rcp"
        rcp_root.mkdir()
        frame_dirs, rcp_videos = _decode_rcp(
            vae,
            rcp_latents,
            plan.view_plan.rcp_camera_ids,
            rcp_root,
            clip,
            plan.device,
        )
        # The released model consumes four JPEG-decoded proposal views. Keep
        # that numerical boundary even though the decoded tensors are local.
        reference_videos = _load_rcp_reference_videos(frame_dirs[:4], INFERENCE.num_frames)
        reference_latents = _encode_videos(vae, reference_videos, plan.device)
        target_sources = torch.cat([source_latents, reference_latents], dim=0)
    return target_sources, rcp_videos


def _target_routes(view_plan: ViewPlan) -> Routes:
    return routing_steps(
        views_per_layer=view_plan.views_per_layer,
        num_layers=view_plan.num_layers,
        group_size=view_plan.views_per_group,
        num_steps=INFERENCE.num_inference_steps,
        enable_tcr=view_plan.enable_tcr,
    )


def _denoise_targets_multi_gpu(
    *,
    target_sources: Tensor,
    context: Tensor,
    initial_latents: Tensor,
    pose_features: PoseFeatureBank,
    routes: Routes,
    checkpoint_path: str | Path,
    root: Path,
    devices: tuple[str, ...],
    candidate_devices: tuple[str, ...],
    num_groups: int,
) -> tuple[Tensor, ParallelismReport]:
    with TemporaryDirectory(prefix=".distributed-", dir=root) as work_dir:
        target_latents, workers = denoise_targets_distributed(
            src_latents=target_sources,
            context=context,
            initial_latents=initial_latents,
            pose_features=pose_features,
            routes=routes,
            checkpoint_path=checkpoint_path,
            work_dir=work_dir,
            devices=devices,
            denoising_strength=INFERENCE.denoising_strength,
            scheduler_shift=INFERENCE.scheduler_shift,
        )
    return target_latents, {
        "backend": "nccl",
        "candidate_devices": list(candidate_devices),
        "used_devices": list(devices),
        "groups_per_step": num_groups,
        "waves_per_step": math.ceil(num_groups / len(devices)),
        "workers": workers,
    }


def generate_views(
    *,
    clip: CanonicalClip,
    conditioning: Conditioning,
    checkpoint_path: str | Path,
    assets: BaseAssets,
    output_dir: str | Path,
    devices: tuple[str, ...],
    seed: int,
) -> GeneratedViews:
    """Generate the proposal (when enabled) and the requested target views."""

    plan = _resolve_generation_plan(clip, conditioning, devices, seed)
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=False)
    metrics = GenerationMetrics(plan.device_index)

    with metrics.stage("prompt"):
        context = load_prompt_context(assets.prompt_context)

    with metrics.stage("pose_conditioning"):
        pose_cache = build_pose_feature_cache(
            conditioning=conditioning,
            checkpoint_path=checkpoint_path,
            device=plan.device,
        )

    with metrics.stage("model_load"):
        denoiser = load_denoiser(checkpoint_path=checkpoint_path) if plan.needs_primary_denoiser else None
        vae = load_vae(assets.vae)

    with metrics.stage("source_encode"), _model_on_device(vae, plan.device):
        source_video = _channels_last_source_layout(conditioning.load_source_tensor())
        source_latents = _encode_videos(vae, source_video, plan.device)
        del source_video

    rcp_videos: tuple[Path, ...] = ()
    target_sources = source_latents
    if plan.view_plan.enable_rcp:
        if denoiser is None:
            raise RuntimeError("RCP requires a primary-process denoiser.")
        target_sources, rcp_videos = _generate_rcp_and_references(
            denoiser=denoiser,
            vae=vae,
            source_latents=source_latents,
            context=context,
            pose_cache=pose_cache,
            plan=plan,
            root=root,
            clip=clip,
            seed=seed,
            metrics=metrics,
        )

    parallelism = None
    with metrics.stage("target_denoise"):
        routes = _target_routes(plan.view_plan)
        initial_latents = _noise(
            vae,
            plan.view_plan.num_target_views,
            INFERENCE.num_frames,
            seed,
            plan.device,
        )
        if plan.distributed:
            if denoiser is not None:
                del denoiser
            initial_latents = initial_latents.to("cpu")
            _empty_cuda_cache()
            target_latents, parallelism = _denoise_targets_multi_gpu(
                target_sources=target_sources,
                context=context,
                initial_latents=initial_latents,
                pose_features=pose_cache.target,
                routes=routes,
                checkpoint_path=checkpoint_path,
                root=root,
                devices=plan.worker_devices,
                candidate_devices=devices,
                num_groups=plan.view_plan.num_groups,
            )
        else:
            if denoiser is None:
                raise RuntimeError("Single-GPU target generation requires a primary-process denoiser.")
            with _model_on_device(denoiser.model, plan.device):
                target_latents = _denoise_targets_single(
                    denoiser,
                    target_sources,
                    context,
                    pose_cache.target,
                    initial_latents,
                    routes,
                    plan.device,
                )
            del denoiser
        del initial_latents

    if parallelism is not None:
        workers = parallelism["workers"]
        metrics.merge_cuda_peak(
            "target_denoise",
            allocated_bytes=max(int(worker["peak_vram_allocated_bytes"]) for worker in workers),
            reserved_bytes=max(int(worker["peak_vram_reserved_bytes"]) for worker in workers),
        )

    with metrics.stage("target_decode"):
        target_root = root / "target"
        target_root.mkdir()
        with _model_on_device(vae, plan.device):
            target_videos = _decode_targets(vae, target_latents, target_root, clip, plan.device)

    del target_latents, target_sources, source_latents, context, pose_cache, vae
    _empty_cuda_cache()
    return GeneratedViews(
        rcp_videos=rcp_videos,
        target_videos=target_videos,
        view_plan=plan.view_plan,
        seed=seed,
        device=plan.device,
        elapsed_seconds=metrics.elapsed_seconds,
        stage_peak_vram_bytes=metrics.stage_peak_vram_bytes,
        peak_vram_allocated_bytes=metrics.peak_vram_allocated_bytes,
        peak_vram_reserved_bytes=metrics.peak_vram_reserved_bytes,
        parallelism=parallelism,
    )
