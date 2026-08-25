"""Hydra/Lightning-free multi-view generation.

RCP and final target generation share one source encoding and prompt embedding.
Target groups execute sequentially on one GPU; TCR optionally shifts their
membership between denoising steps.
"""

from __future__ import annotations

import gc
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from fdanyone.assets import BaseAssets
from fdanyone.config import INFERENCE
from fdanyone.errors import FourDAnyoneError
from fdanyone.model.loader import load_pipeline
from fdanyone.model.routing import routing_steps
from fdanyone.skeleton.pipeline import Conditioning, SkeletonVideo
from fdanyone.video import CanonicalClip, write_video
from fdanyone.views import ViewPlan

LOGGER = logging.getLogger("fdanyone")


@dataclass(frozen=True)
class GeneratedViews:
    """Paths and measurements produced by one resolved view plan."""

    rcp_videos: tuple[Path, ...]
    target_videos: tuple[Path, ...]
    view_plan: ViewPlan
    seed: int
    device: str
    elapsed_seconds: dict[str, float]
    peak_vram_allocated_bytes: int
    peak_vram_reserved_bytes: int


def _empty_cuda_cache() -> None:
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _move_model(model, device: str) -> None:
    model.to(device)
    _empty_cuda_cache()


def _offload_model(model) -> None:
    model.to("cpu")
    _empty_cuda_cache()


def _tiler_kwargs() -> dict:
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


def _encode_prompt(pipe, device: str) -> dict[str, object]:
    import torch

    _move_model(pipe.text_encoder, device)
    with torch.inference_mode(), _bf16_autocast():
        context = pipe.prompter.encode_prompt(INFERENCE.prompt, positive=True, device=device)
    prompt = {"context": context.detach().to("cpu")}
    _offload_model(pipe.text_encoder)
    return prompt


def _encode_videos(pipe, videos, device: str):
    import torch

    videos = videos.to(dtype=pipe.torch_dtype, device=device)
    with torch.inference_mode(), _bf16_autocast():
        latents = pipe.encode_video(videos, **_tiler_kwargs())
    return latents.detach().to("cpu")


def _noise(pipe, num_views: int, num_frames: int, seed: int, device: str):
    import torch

    shape = (
        num_views,
        pipe.vae.model.z_dim,
        (num_frames - 1) // 4 + 1,
        INFERENCE.height // pipe.vae.upsampling_factor,
        INFERENCE.width // pipe.vae.upsampling_factor,
    )
    generator = torch.Generator("cpu").manual_seed(seed)
    return torch.randn(shape, generator=generator, device="cpu", dtype=torch.float32).to(
        dtype=pipe.torch_dtype, device=device
    )


def _load_skeleton_cache(
    conditioning: Conditioning,
    skeletons: Iterable[SkeletonVideo],
    cache: dict[SkeletonVideo, object],
) -> None:
    import torch

    for skeleton in skeletons:
        if skeleton in cache:
            continue
        LOGGER.info("Loading skeleton conditioning from %s", skeleton.path.name)
        tensor = conditioning.load_skeleton_tensor([skeleton]).to(dtype=torch.bfloat16, device="cpu")
        cache[skeleton] = tensor.contiguous()


def _skeleton_group(
    cache: dict[SkeletonVideo, object],
    skeletons: Iterable[SkeletonVideo],
    device: str,
    *,
    channels_last: bool = False,
):
    import torch

    items = tuple(skeletons)
    first = cache[items[0]]
    memory_format = torch.channels_last_3d if channels_last else torch.contiguous_format
    group = torch.empty(
        (len(items), *first.shape[1:]),
        dtype=first.dtype,
        device=device,
        memory_format=memory_format,
    )
    for output_index, skeleton in enumerate(items):
        group[output_index].copy_(cache[skeleton][0])
    return group


def _denoise_rcp(
    pipe,
    src_latents,
    prompt,
    camera_ids: tuple[int, ...],
    skeletons: tuple[SkeletonVideo, ...],
    skeleton_cache: dict[SkeletonVideo, object],
    device: str,
    seed: int,
):
    import torch
    from tqdm.auto import tqdm

    if len(skeletons) != len(camera_ids):
        raise FourDAnyoneError(f"RCP requires {len(camera_ids)} skeleton views, got {len(skeletons)}.")
    pipe.scheduler.set_timesteps(
        INFERENCE.num_inference_steps,
        denoising_strength=INFERENCE.denoising_strength,
        shift=INFERENCE.scheduler_shift,
    )
    latents = _noise(pipe, len(skeletons), INFERENCE.num_frames, seed, device)
    source = src_latents.to(dtype=pipe.torch_dtype, device=device)
    context = {name: value.to(dtype=pipe.torch_dtype, device=device) for name, value in prompt.items()}
    # Preserve the reviewed RCP tensor layout: it changes CUDA kernel selection.
    # Target generation below materializes each sequential group contiguously.
    skeleton_tensor = _skeleton_group(skeleton_cache, skeletons, device, channels_last=True)

    with torch.inference_mode(), _bf16_autocast():
        for timestep in tqdm(pipe.scheduler.timesteps, desc=f"RCP 1-to-{len(camera_ids)}"):
            batched_timestep = timestep.unsqueeze(0).to(dtype=pipe.torch_dtype, device=device)
            batched_timestep = torch.cat([batched_timestep] * len(skeletons), dim=0)
            prediction = pipe.dit(
                x=latents,
                x_src=source,
                timestep=batched_timestep,
                skeletons=skeleton_tensor,
                **context,
                **pipe.prepare_extra_input(latents),
            )
            latents = pipe.scheduler.step(prediction, timestep, latents)
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
    pipe,
    latents,
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
            video = pipe.decode_video(
                latents[latent_index : latent_index + 1].to(dtype=pipe.torch_dtype, device=device),
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


def _denoise_targets(
    pipe,
    src_latents,
    prompt,
    skeletons: tuple[SkeletonVideo, ...],
    skeleton_cache: dict[SkeletonVideo, object],
    view_plan: ViewPlan,
    device: str,
    seed: int,
):
    import torch
    from tqdm.auto import tqdm

    num_views = len(skeletons)
    if num_views != view_plan.num_target_views:
        raise FourDAnyoneError(
            f"Target generation requires {view_plan.num_target_views} skeleton views, got {num_views}."
        )
    pipe.scheduler.set_timesteps(
        INFERENCE.num_inference_steps,
        denoising_strength=INFERENCE.denoising_strength,
        shift=INFERENCE.scheduler_shift,
    )
    latents = _noise(pipe, num_views, INFERENCE.num_frames, seed, device)
    source = src_latents.to(dtype=pipe.torch_dtype, device=device)
    context = {name: value.to(dtype=pipe.torch_dtype, device=device) for name, value in prompt.items()}
    routes = routing_steps(
        views_per_layer=view_plan.views_per_layer,
        num_layers=view_plan.num_layers,
        group_size=view_plan.views_per_group,
        num_steps=INFERENCE.num_inference_steps,
        enable_tcr=view_plan.enable_tcr,
    )

    with torch.inference_mode(), _bf16_autocast():
        for step_index, groups in enumerate(tqdm(routes, desc=f"Generate {num_views} target views")):
            for view_indices in groups:
                index = torch.tensor(view_indices, dtype=torch.long, device=device)
                local_latents = torch.index_select(latents, 0, index)
                local_skeletons = _skeleton_group(
                    skeleton_cache,
                    (skeletons[view_index] for view_index in view_indices),
                    device,
                )
                timestep = pipe.scheduler.timesteps[step_index]
                batched_timestep = timestep.unsqueeze(0).to(dtype=pipe.torch_dtype, device=device)
                batched_timestep = torch.cat([batched_timestep] * len(view_indices), dim=0)
                prediction = pipe.dit(
                    x=local_latents,
                    x_src=source,
                    timestep=batched_timestep,
                    skeletons=local_skeletons,
                    **context,
                    **pipe.prepare_extra_input(local_latents),
                )
                local_latents = pipe.scheduler.step(prediction, timestep, local_latents)
                latents.index_copy_(0, index, local_latents)
                del local_latents, local_skeletons, prediction
    return latents.detach().to("cpu")


def _decode_targets(pipe, latents, output_dir: Path, clip: CanonicalClip, device: str) -> tuple[Path, ...]:
    import torch

    video_root = output_dir / "videos"
    video_root.mkdir(parents=True, exist_ok=False)
    outputs: list[Path] = []
    with torch.inference_mode(), _bf16_autocast():
        for camera_id in range(latents.shape[0]):
            LOGGER.info("Decoding target camera %02d", camera_id)
            video = pipe.decode_video(
                latents[camera_id : camera_id + 1].to(dtype=pipe.torch_dtype, device=device),
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


def generate_views(
    *,
    clip: CanonicalClip,
    conditioning: Conditioning,
    checkpoint_path: str | Path,
    assets: BaseAssets,
    output_dir: str | Path,
    device: str,
    seed: int,
) -> GeneratedViews:
    """Generate the proposal (when enabled) and the requested target views."""

    import torch

    if conditioning.num_frames != INFERENCE.num_frames or len(clip.frames) != INFERENCE.num_frames:
        raise FourDAnyoneError("Generation requires the frozen 121-frame contract.")
    if seed < 0:
        raise FourDAnyoneError(f"seed must be non-negative, got {seed}.")
    device_index = int(device.removeprefix("cuda:"))
    LOGGER.info("Using %s (%s)", device, torch.cuda.get_device_name(device_index))

    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=False)
    view_plan = conditioning.view_plan
    if len(conditioning.target_skeletons) != view_plan.num_target_views:
        raise FourDAnyoneError("Target skeleton count does not match the resolved view plan.")
    if len(conditioning.rcp_skeletons) != len(view_plan.rcp_camera_ids):
        raise FourDAnyoneError("RCP skeleton count does not match the resolved view plan.")
    loaded = load_pipeline(checkpoint_path=checkpoint_path, assets=assets, device=device)
    pipe = loaded.pipe
    timings: dict[str, float] = {}
    skeleton_cache: dict[SkeletonVideo, object] = {}
    torch.cuda.reset_peak_memory_stats(device_index)

    started = time.monotonic()
    prompt = _encode_prompt(pipe, device)
    loaded.release_text_encoder()
    timings["prompt"] = time.monotonic() - started

    started = time.monotonic()
    _move_model(pipe.vae, device)
    source_video = _channels_last_source_layout(conditioning.load_source_tensor())
    source_latents = _encode_videos(pipe, source_video, device)
    del source_video
    _offload_model(pipe.vae)
    timings["source_encode"] = time.monotonic() - started

    rcp_videos: tuple[Path, ...] = ()
    target_sources = source_latents
    if view_plan.enable_rcp:
        started = time.monotonic()
        _load_skeleton_cache(conditioning, conditioning.rcp_skeletons, skeleton_cache)
        _move_model(pipe.dit, device)
        rcp_latents = _denoise_rcp(
            pipe,
            source_latents,
            prompt,
            view_plan.rcp_camera_ids,
            conditioning.rcp_skeletons,
            skeleton_cache,
            device,
            seed,
        )
        _offload_model(pipe.dit)
        timings["rcp_denoise"] = time.monotonic() - started

        started = time.monotonic()
        rcp_root = root / "rcp"
        rcp_root.mkdir()
        _move_model(pipe.vae, device)
        frame_dirs, rcp_videos = _decode_rcp(
            pipe,
            rcp_latents,
            view_plan.rcp_camera_ids,
            rcp_root,
            clip,
            device,
        )
        # Match the reference JPEG-backed RCP boundary before the second VAE
        # encode; backing layout changes can otherwise select different BF16
        # CUDA kernels even when tensor values are identical.
        rcp_reference_videos = _load_rcp_reference_videos(frame_dirs[:4], INFERENCE.num_frames)
        rcp_reference_latents = _encode_videos(pipe, rcp_reference_videos, device)
        # VAE38 encodes batch elements independently, so the existing source
        # encoding is identical to re-encoding source plus the RCP references.
        target_sources = torch.cat([source_latents, rcp_reference_latents], dim=0)
        del rcp_latents, rcp_reference_videos, rcp_reference_latents
        _offload_model(pipe.vae)
        timings["rcp_decode_and_reference_encode"] = time.monotonic() - started

    started = time.monotonic()
    _load_skeleton_cache(conditioning, conditioning.target_skeletons, skeleton_cache)
    _move_model(pipe.dit, device)
    target_latents = _denoise_targets(
        pipe,
        target_sources,
        prompt,
        conditioning.target_skeletons,
        skeleton_cache,
        view_plan,
        device,
        seed,
    )
    _offload_model(pipe.dit)
    timings["target_denoise"] = time.monotonic() - started

    started = time.monotonic()
    target_root = root / "target"
    target_root.mkdir()
    _move_model(pipe.vae, device)
    target_videos = _decode_targets(pipe, target_latents, target_root, clip, device)
    _offload_model(pipe.vae)
    timings["target_decode"] = time.monotonic() - started
    peak_vram_allocated = int(torch.cuda.max_memory_allocated(device_index))
    peak_vram_reserved = int(torch.cuda.max_memory_reserved(device_index))

    del target_latents, target_sources, source_latents, prompt, skeleton_cache, loaded, pipe
    _empty_cuda_cache()
    return GeneratedViews(
        rcp_videos=rcp_videos,
        target_videos=target_videos,
        view_plan=view_plan,
        seed=seed,
        device=device,
        elapsed_seconds=timings,
        peak_vram_allocated_bytes=peak_vram_allocated,
        peak_vram_reserved_bytes=peak_vram_reserved,
    )
