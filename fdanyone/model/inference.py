"""Hydra/Lightning-free multi-view generation.

RCP and final target generation share one source encoding and prompt embedding.
Target groups execute sequentially on one GPU or concurrently across multiple
GPUs; TCR optionally shifts their membership between denoising steps.
"""

from __future__ import annotations

import gc
import logging
import math
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, TypedDict

from fdanyone.assets import BaseAssets
from fdanyone.config import INFERENCE, DenoisingProfile
from fdanyone.errors import FourDAnyoneError
from fdanyone.model.conditioning import (
    PoseFeatureBank,
    PoseFeatureCache,
    build_pose_feature_cache,
    load_prompt_context,
)
from fdanyone.model.denoise import denoise_group
from fdanyone.model.distributed import (
    WorkerReport,
    denoise_targets_distributed,
    select_worker_devices,
)
from fdanyone.model.loader import Denoiser, load_denoiser
from fdanyone.model.metrics import GenerationMetrics
from fdanyone.model.routing import Routes, routing_steps, validate_routes
from fdanyone.model.vae import VaeExecutor, load_reference_videos
from fdanyone.skeleton.pipeline import Conditioning
from fdanyone.video import CanonicalClip
from fdanyone.views import ViewPlan

if TYPE_CHECKING:
    from torch import Tensor

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
    denoising_profile: DenoisingProfile
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
    candidate_devices: tuple[str, ...]
    primary_device: str
    dit_devices: tuple[str, ...]

    @property
    def primary_device_index(self) -> int:
        return int(self.primary_device.removeprefix("cuda:"))

    @property
    def distributed(self) -> bool:
        return len(self.dit_devices) > 1

    @property
    def needs_primary_denoiser(self) -> bool:
        return self.view_plan.enable_rcp or not self.distributed


def _empty_cuda_cache() -> None:
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


@contextmanager
def _denoiser_on_device(denoiser: Denoiser, device: str) -> Iterator[None]:
    """Keep one denoiser resident and Turbo-fused for one safe stage."""

    try:
        denoiser.prepare_on_device(device)
        _empty_cuda_cache()
        yield
    finally:
        denoiser.model.to("cpu")
        _empty_cuda_cache()


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


def _noise(
    *,
    vae: VaeExecutor,
    num_views: int,
    num_frames: int,
    seed: int,
    device: str,
) -> Tensor:
    import torch

    shape = (
        num_views,
        vae.latent_channels,
        (num_frames - 1) // 4 + 1,
        INFERENCE.height // vae.upsampling_factor,
        INFERENCE.width // vae.upsampling_factor,
    )
    generator = torch.Generator("cpu").manual_seed(seed)
    return torch.randn(shape, generator=generator, device="cpu", dtype=torch.float32).to(
        dtype=torch.bfloat16, device=device
    )


def _denoise_rcp(
    *,
    denoiser: Denoiser,
    vae: VaeExecutor,
    src_latents: Tensor,
    context: Tensor,
    camera_ids: tuple[int, ...],
    pose_features: PoseFeatureBank,
    seed: int,
    device: str,
) -> Tensor:
    import torch
    from tqdm.auto import tqdm

    if pose_features.num_features != len(camera_ids):
        raise FourDAnyoneError(f"RCP requires {len(camera_ids)} pose features, got {pose_features.num_features}.")
    latents = _noise(
        vae=vae,
        num_views=len(camera_ids),
        num_frames=INFERENCE.num_frames,
        seed=seed,
        device=device,
    )
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


def _denoise_targets_single(
    *,
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
    validate_routes(routes, num_views)
    num_timesteps = len(denoiser.scheduler.timesteps)
    if len(routes) != num_timesteps:
        raise FourDAnyoneError(
            f"Denoising requires one route per scheduler timestep; got "
            f"{len(routes)} routes for {num_timesteps} timesteps."
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


def _resolve_generation_plan(
    *,
    clip: CanonicalClip,
    conditioning: Conditioning,
    devices: tuple[str, ...],
) -> _GenerationPlan:
    import torch

    if conditioning.num_frames != INFERENCE.num_frames or len(clip.frames) != INFERENCE.num_frames:
        raise FourDAnyoneError("Generation requires the frozen 121-frame contract.")
    if not devices:
        raise FourDAnyoneError("Generation requires at least one CUDA device.")

    view_plan = conditioning.view_plan
    if len(conditioning.target_skeletons) != view_plan.num_target_views:
        raise FourDAnyoneError("Target skeleton count does not match the resolved view plan.")
    if len(conditioning.rcp_skeletons) != len(view_plan.rcp_camera_ids):
        raise FourDAnyoneError("RCP skeleton count does not match the resolved view plan.")

    primary_device = devices[0]
    primary_device_index = int(primary_device.removeprefix("cuda:"))
    dit_devices = select_worker_devices(devices, view_plan.num_groups)
    LOGGER.info(
        "Using %s (%s)",
        primary_device,
        torch.cuda.get_device_name(primary_device_index),
    )
    if len(dit_devices) < len(devices):
        LOGGER.info(
            "Using %d of %d candidate GPUs for DiT and all %d for independent view stages",
            len(dit_devices),
            len(devices),
            len(devices),
        )
    return _GenerationPlan(
        view_plan=view_plan,
        candidate_devices=devices,
        primary_device=primary_device,
        dit_devices=dit_devices,
    )


def _generate_rcp_and_references(
    *,
    denoiser: Denoiser,
    vae: VaeExecutor,
    clip: CanonicalClip,
    plan: _GenerationPlan,
    seed: int,
    source_latents: Tensor,
    context: Tensor,
    pose_cache: PoseFeatureCache,
    root: Path,
    metrics: GenerationMetrics,
) -> tuple[Tensor, tuple[Path, ...]]:
    import torch

    rcp_pose_features = pose_cache.rcp
    if rcp_pose_features is None:
        raise FourDAnyoneError("RCP was enabled without precomputed proposal pose features.")
    with (
        metrics.stage("rcp_denoise"),
        _denoiser_on_device(denoiser, plan.primary_device),
    ):
        rcp_latents = _denoise_rcp(
            denoiser=denoiser,
            vae=vae,
            src_latents=source_latents,
            context=context,
            camera_ids=plan.view_plan.rcp_camera_ids,
            pose_features=rcp_pose_features,
            seed=seed,
            device=plan.primary_device,
        )

    with metrics.stage("rcp_decode_and_publish"):
        rcp_root = root / "rcp"
        rcp_root.mkdir()
        published = vae.publish_rcp(
            rcp_latents,
            plan.view_plan.rcp_camera_ids,
            rcp_root,
            clip,
        )
    _merge_view_stage_peak(metrics, "rcp_decode_and_publish", vae)

    with metrics.stage("rcp_reference_load"):
        # The released model consumes four JPEG-decoded proposal views. Keep
        # that numerical boundary even though the decoded tensors are local.
        reference_videos = load_reference_videos(published.frame_directories[:4], INFERENCE.num_frames)

    with metrics.stage("reference_encode"):
        reference_latents = vae.encode(reference_videos)
        target_sources = torch.cat([source_latents, reference_latents], dim=0)
    _merge_view_stage_peak(metrics, "reference_encode", vae)
    return target_sources, published.videos


def _merge_view_stage_peak(metrics: GenerationMetrics, stage: str, vae: VaeExecutor) -> None:
    if not vae.last_peak_vram_bytes:
        return
    metrics.merge_cuda_peak(
        stage,
        allocated_bytes=max(peak["allocated"] for peak in vae.last_peak_vram_bytes.values()),
        reserved_bytes=max(peak["reserved"] for peak in vae.last_peak_vram_bytes.values()),
    )


def _target_routes(*, view_plan: ViewPlan, profile: DenoisingProfile) -> Routes:
    return routing_steps(
        view_plan=view_plan,
        num_steps=profile.num_inference_steps,
        tcr_stride=profile.tcr_stride,
        freeze_after_one_cycle=profile.freeze_tcr_after_one_cycle,
    )


def _denoise_targets_multi_gpu(
    *,
    checkpoint_path: str | Path,
    turbo_lora_path: str | Path | None,
    denoising_profile: DenoisingProfile,
    plan: _GenerationPlan,
    target_sources: Tensor,
    context: Tensor,
    initial_latents: Tensor,
    pose_features: PoseFeatureBank,
    routes: Routes,
    root: Path,
) -> tuple[Tensor, ParallelismReport]:
    with TemporaryDirectory(prefix=".distributed-", dir=root) as work_dir:
        target_latents, workers = denoise_targets_distributed(
            checkpoint_path=checkpoint_path,
            turbo_lora_path=turbo_lora_path,
            denoising_profile=denoising_profile,
            src_latents=target_sources,
            context=context,
            initial_latents=initial_latents,
            pose_features=pose_features,
            routes=routes,
            work_dir=work_dir,
            devices=plan.dit_devices,
        )
    return target_latents, {
        "backend": "nccl",
        "candidate_devices": list(plan.candidate_devices),
        "used_devices": list(plan.dit_devices),
        "groups_per_step": plan.view_plan.num_groups,
        "waves_per_step": math.ceil(plan.view_plan.num_groups / len(plan.dit_devices)),
        "workers": workers,
    }


def generate_views(
    *,
    clip: CanonicalClip,
    conditioning: Conditioning,
    checkpoint_path: str | Path,
    turbo_lora_path: str | Path | None,
    denoising_profile: DenoisingProfile,
    assets: BaseAssets,
    output_dir: str | Path,
    devices: tuple[str, ...],
    seed: int,
) -> GeneratedViews:
    """Generate the proposal (when enabled) and the requested target views."""

    if seed < 0:
        raise FourDAnyoneError(f"seed must be non-negative, got {seed}.")
    plan = _resolve_generation_plan(
        clip=clip,
        conditioning=conditioning,
        devices=devices,
    )
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=False)
    metrics = GenerationMetrics(plan.primary_device_index)

    with metrics.stage("prompt"):
        context = load_prompt_context(assets.prompt_context)

    with metrics.stage("pose_conditioning"):
        pose_cache = build_pose_feature_cache(
            conditioning=conditioning,
            checkpoint_path=checkpoint_path,
            devices=plan.candidate_devices,
        )

    with metrics.stage("model_load"):
        denoiser = (
            load_denoiser(
                checkpoint_path=checkpoint_path,
                turbo_lora_path=turbo_lora_path,
                profile=denoising_profile,
            )
            if plan.needs_primary_denoiser
            else None
        )
        vae = VaeExecutor.load(assets.vae, plan.candidate_devices)

    try:
        with metrics.stage("source_encode"):
            source_video = _channels_last_source_layout(conditioning.load_source_tensor())
            source_latents = vae.encode(source_video)
            del source_video
        _merge_view_stage_peak(metrics, "source_encode", vae)

        rcp_videos: tuple[Path, ...] = ()
        target_sources = source_latents
        if plan.view_plan.enable_rcp:
            if denoiser is None:
                raise RuntimeError("RCP requires a primary-process denoiser.")
            target_sources, rcp_videos = _generate_rcp_and_references(
                denoiser=denoiser,
                vae=vae,
                clip=clip,
                plan=plan,
                seed=seed,
                source_latents=source_latents,
                context=context,
                pose_cache=pose_cache,
                root=root,
                metrics=metrics,
            )
        del source_latents
        # Parallel VAE replicas are stage-local. Retaining only the prototype
        # bounds parent host memory while distributed DiT workers load.
        vae.release_replicas()
        target_pose_features = pose_cache.target
        del pose_cache

        parallelism = None
        with metrics.stage("target_denoise"):
            routes = _target_routes(view_plan=plan.view_plan, profile=denoising_profile)
            initial_latents = _noise(
                vae=vae,
                num_views=plan.view_plan.num_target_views,
                num_frames=INFERENCE.num_frames,
                seed=seed,
                device=plan.primary_device,
            )
            if plan.distributed:
                denoiser = None
                initial_latents = initial_latents.to("cpu")
                _empty_cuda_cache()
                target_latents, parallelism = _denoise_targets_multi_gpu(
                    checkpoint_path=checkpoint_path,
                    turbo_lora_path=turbo_lora_path,
                    denoising_profile=denoising_profile,
                    plan=plan,
                    target_sources=target_sources,
                    context=context,
                    initial_latents=initial_latents,
                    pose_features=target_pose_features,
                    routes=routes,
                    root=root,
                )
            else:
                if denoiser is None:
                    raise RuntimeError("Single-GPU target generation requires a primary-process denoiser.")
                with _denoiser_on_device(denoiser, plan.primary_device):
                    target_latents = _denoise_targets_single(
                        denoiser=denoiser,
                        src_latents=target_sources,
                        context=context,
                        pose_features=target_pose_features,
                        initial_latents=initial_latents,
                        routes=routes,
                        device=plan.primary_device,
                    )
                denoiser = None
            del initial_latents

        if parallelism is not None:
            workers = parallelism["workers"]
            metrics.merge_cuda_peak(
                "target_denoise",
                allocated_bytes=max(int(worker["peak_vram_allocated_bytes"]) for worker in workers),
                reserved_bytes=max(int(worker["peak_vram_reserved_bytes"]) for worker in workers),
            )
        del target_pose_features, target_sources, context

        with metrics.stage("target_decode_and_publish"):
            target_root = root / "target"
            target_root.mkdir()
            target_videos = vae.publish_targets(target_latents, target_root, clip)
        _merge_view_stage_peak(metrics, "target_decode_and_publish", vae)

        result = GeneratedViews(
            rcp_videos=rcp_videos,
            target_videos=target_videos,
            view_plan=plan.view_plan,
            denoising_profile=denoising_profile,
            seed=seed,
            device=plan.primary_device,
            elapsed_seconds=metrics.elapsed_seconds,
            stage_peak_vram_bytes=metrics.stage_peak_vram_bytes,
            peak_vram_allocated_bytes=metrics.peak_vram_allocated_bytes,
            peak_vram_reserved_bytes=metrics.peak_vram_reserved_bytes,
            parallelism=parallelism,
        )
    finally:
        vae.close()
        _empty_cuda_cache()

    return result
