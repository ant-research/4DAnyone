"""Per-view VAE execution and publication for generation stages."""

from __future__ import annotations

import gc
import logging
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import BoundedSemaphore, Event
from typing import TYPE_CHECKING, TypeVar

import numpy as np
from PIL import Image

from fdanyone.config import INFERENCE
from fdanyone.errors import FourDAnyoneError
from fdanyone.video import CanonicalClip, write_video

if TYPE_CHECKING:
    from torch import Tensor

    from fdanyone.vendor.diffsynth.models.wan_video_vae import WanVideoVAE38

LOGGER = logging.getLogger("fdanyone")

Output = TypeVar("Output")


@dataclass(frozen=True)
class PublishedRcp:
    """Canonical RCP frame directories and videos."""

    frame_directories: tuple[Path, ...]
    videos: tuple[Path, ...]


@dataclass(frozen=True)
class _DecodedView:
    """Host-owned values consumed by publication sinks."""

    video: Tensor | None
    rgb_frames: tuple[np.ndarray, ...]


def _bf16_autocast():
    import torch

    return torch.autocast(device_type="cuda", dtype=torch.bfloat16)


def _rgb_frames(video: Tensor) -> tuple[np.ndarray, ...]:
    """Freeze the released CUDA scaling boundary before CPU publication."""

    scaled = video.detach().float().add_(1.0).mul_(127.5).clamp_(0.0, 255.0).to(device="cpu")
    return tuple(
        scaled[:, frame_index].permute(1, 2, 0).numpy().astype(np.uint8) for frame_index in range(scaled.shape[1])
    )


def _save_jpegs(video: Tensor, camera_id: int, root: Path) -> Path:
    import torchvision.transforms.functional as transform

    frame_dir = root / f"{camera_id:06d}"
    frame_dir.mkdir(parents=True, exist_ok=False)
    for frame_index in range(video.shape[1]):
        normalized = video[:, frame_index].float().mul_(0.5).add_(0.5).clamp_(0.0, 1.0)
        image = transform.to_pil_image(normalized)
        image.save(frame_dir / f"{frame_index:06d}.jpg", quality=INFERENCE.rcp_jpeg_quality)
    return frame_dir


def load_reference_videos(frame_dirs: Iterable[Path], num_frames: int) -> Tensor:
    """Load the frozen JPEG reference boundary as ``[V,C,F,H,W]``."""

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
    frame_first = torch.stack(videos, dim=0).mul_(2.0).sub_(1.0)
    return frame_first.permute(0, 2, 1, 3, 4)


class VaeExecutor:
    """Run independent views on an ordered CUDA device pool.

    Each worker owns one model replica and processes a deterministic strided
    subset of camera indices. Models return to CPU between stages so the same
    replicas can be reused without competing with the DiT for device memory.
    """

    def __init__(self, model: WanVideoVAE38, devices: tuple[str, ...]) -> None:
        if not devices:
            raise FourDAnyoneError("VAE execution requires at least one CUDA device.")
        self.devices = devices
        self._models = [model]
        self.last_peak_vram_bytes: dict[str, dict[str, int]] = {}

    @classmethod
    def load(cls, path: str | Path, devices: tuple[str, ...]) -> VaeExecutor:
        from fdanyone.model.loader import load_vae

        return cls(load_vae(path), devices)

    @property
    def latent_channels(self) -> int:
        return int(self._models[0].model.z_dim)

    @property
    def upsampling_factor(self) -> int:
        return int(self._models[0].upsampling_factor)

    def _ensure_models(self, count: int) -> None:
        while len(self._models) < count:
            self._models.append(deepcopy(self._models[0]))

    @staticmethod
    def _worker_count(num_views: int, num_devices: int) -> int:
        if num_views <= 0:
            raise FourDAnyoneError("VAE execution requires at least one view.")
        return min(num_views, num_devices)

    @staticmethod
    def _worker_indices(num_views: int, worker_index: int, worker_count: int) -> tuple[int, ...]:
        return tuple(range(worker_index, num_views, worker_count))

    def _run_workers(
        self,
        *,
        num_views: int,
        operation: Callable[[WanVideoVAE38, str, tuple[int, ...], Event], None],
        stopped: Event | None = None,
    ) -> None:
        import torch

        worker_count = self._worker_count(num_views, len(self.devices))
        self._ensure_models(worker_count)
        stopped = Event() if stopped is None else stopped
        peaks: dict[str, dict[str, int]] = {}

        def run(worker_index: int) -> None:
            device = self.devices[worker_index]
            device_index = int(device.removeprefix("cuda:"))
            model = self._models[worker_index]
            indices = self._worker_indices(num_views, worker_index, worker_count)
            torch.cuda.set_device(device_index)
            torch.cuda.reset_peak_memory_stats(device_index)
            try:
                model.to(device)
                operation(model, device, indices, stopped)
                torch.cuda.synchronize(device_index)
                peaks[device] = {
                    "allocated": int(torch.cuda.max_memory_allocated(device_index)),
                    "reserved": int(torch.cuda.max_memory_reserved(device_index)),
                }
            except BaseException:
                stopped.set()
                raise
            finally:
                model.to("cpu")

        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="vae") as pool:
            futures = [pool.submit(run, worker_index) for worker_index in range(worker_count)]
            try:
                for future in as_completed(futures):
                    future.result()
            except BaseException:
                stopped.set()
                for future in futures:
                    future.cancel()
                raise
        # Do not let a completed worker release cached mappings while a peer is
        # still executing.  This raced with expandable segments in low-memory
        # multi-GPU inference.  Join every worker before serial cache cleanup.
        for worker_index in range(worker_count):
            torch.cuda.set_device(int(self.devices[worker_index].removeprefix("cuda:")))
            torch.cuda.empty_cache()
        self.last_peak_vram_bytes = peaks

    @staticmethod
    def _encode_view(model: WanVideoVAE38, video: Tensor, device: str) -> Tensor:
        import torch

        if INFERENCE.tiled_vae:
            tile_size = tuple(size * model.upsampling_factor for size in INFERENCE.vae_tile_size)
            tile_stride = tuple(stride * model.upsampling_factor for stride in INFERENCE.vae_tile_stride)
            batched = video.unsqueeze(0).to(dtype=torch.bfloat16, device="cpu")
            return model.tiled_encode(batched, device, tile_size, tile_stride)
        batched = video.unsqueeze(0).to(dtype=torch.bfloat16, device=device)
        return model.encode_view(batched)

    @staticmethod
    def _decode_view(model: WanVideoVAE38, latent: Tensor, device: str) -> Tensor:
        import torch

        if INFERENCE.tiled_vae:
            batched = latent.unsqueeze(0).to(dtype=torch.bfloat16, device="cpu")
            return model.tiled_decode(
                batched,
                device,
                INFERENCE.vae_tile_size,
                INFERENCE.vae_tile_stride,
            )
        batched = latent.unsqueeze(0).to(dtype=torch.bfloat16, device=device)
        return model.decode_view(batched)

    def encode(self, videos: Tensor) -> Tensor:
        """Encode CPU-resident views and gather latents by input index."""

        import torch

        if videos.ndim != 5 or videos.device.type != "cpu":
            raise FourDAnyoneError(f"VAE input must be CPU [V,C,F,H,W], got {tuple(videos.shape)} on {videos.device}.")
        outputs: list[Tensor | None] = [None] * videos.shape[0]

        def operation(model: WanVideoVAE38, device: str, indices: tuple[int, ...], stopped: Event) -> None:
            with torch.inference_mode(), _bf16_autocast():
                for index in indices:
                    if stopped.is_set():
                        return
                    encoded = self._encode_view(model, videos[index], device)
                    outputs[index] = encoded[0].detach().to(device="cpu").contiguous()
                    del encoded

        self._run_workers(num_views=videos.shape[0], operation=operation)
        if any(output is None for output in outputs):
            raise RuntimeError("VAE encode completed without every canonical view.")
        return torch.stack(outputs)  # type: ignore[arg-type]

    def _decode_and_publish(
        self,
        latents: Tensor,
        sink: Callable[[int, _DecodedView], Output],
        *,
        retain_video: bool,
    ) -> tuple[Output, ...]:
        import torch

        if latents.ndim != 5 or latents.device.type != "cpu":
            raise FourDAnyoneError(
                f"VAE latents must be CPU [V,C,F,H,W], got {tuple(latents.shape)} on {latents.device}."
            )
        num_views = int(latents.shape[0])
        worker_count = self._worker_count(num_views, len(self.devices))
        slots = BoundedSemaphore(worker_count)
        sink_futures: list[Future[Output] | None] = [None] * num_views
        stopped = Event()

        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="video-codec") as codec_pool:

            def release_slot(future: Future[Output]) -> None:
                if future.exception() is not None:
                    stopped.set()
                slots.release()

            def operation(
                model: WanVideoVAE38,
                device: str,
                indices: tuple[int, ...],
                worker_stop: Event,
            ) -> None:
                with torch.inference_mode(), _bf16_autocast():
                    for index in indices:
                        if worker_stop.is_set():
                            return
                        slots.acquire()
                        try:
                            decoded = self._decode_view(model, latents[index], device)
                            device_video = decoded[0].detach()
                            rgb_frames = _rgb_frames(device_video)
                            video = device_video.to(device="cpu").contiguous() if retain_video else None
                            del decoded, device_video
                            future = codec_pool.submit(
                                sink,
                                index,
                                _DecodedView(video=video, rgb_frames=rgb_frames),
                            )
                            future.add_done_callback(release_slot)
                            sink_futures[index] = future
                        except BaseException:
                            slots.release()
                            stopped.set()
                            raise

            self._run_workers(num_views=num_views, operation=operation, stopped=stopped)
            for future in sink_futures:
                if future is not None and future.done() and future.exception() is not None:
                    future.result()
            if any(future is None for future in sink_futures):
                raise RuntimeError("VAE decode completed without every canonical view.")
            return tuple(future.result() for future in sink_futures if future is not None)

    def publish_rcp(
        self,
        latents: Tensor,
        camera_ids: tuple[int, ...],
        output_dir: Path,
        clip: CanonicalClip,
    ) -> PublishedRcp:
        if latents.shape[0] != len(camera_ids):
            raise FourDAnyoneError(f"RCP decode expected {len(camera_ids)} latent views, got {latents.shape[0]}.")
        frame_root = output_dir / "frames"
        video_root = output_dir / "videos"
        frame_root.mkdir(parents=True, exist_ok=False)
        video_root.mkdir(parents=True, exist_ok=False)

        def publish(index: int, decoded: _DecodedView) -> tuple[Path, Path]:
            camera_id = camera_ids[index]
            LOGGER.info("Publishing RCP camera %02d", camera_id)
            if decoded.video is None:
                raise RuntimeError("RCP publication requires the decoded BF16 video.")
            frame_dir = _save_jpegs(decoded.video, camera_id, frame_root)
            video_path = write_video(
                iter(decoded.rgb_frames),
                video_root / f"{camera_id:02d}.mp4",
                clip.fps,
                crf=INFERENCE.target_h264_crf,
                preset=INFERENCE.h264_preset,
            )
            return frame_dir, video_path

        published = self._decode_and_publish(latents, publish, retain_video=True)
        return PublishedRcp(
            frame_directories=tuple(item[0] for item in published),
            videos=tuple(item[1] for item in published),
        )

    def publish_targets(self, latents: Tensor, output_dir: Path, clip: CanonicalClip) -> tuple[Path, ...]:
        video_root = output_dir / "videos"
        video_root.mkdir(parents=True, exist_ok=False)

        def publish(camera_id: int, decoded: _DecodedView) -> Path:
            LOGGER.info("Publishing target camera %02d", camera_id)
            return write_video(
                iter(decoded.rgb_frames),
                video_root / f"{camera_id:02d}.mp4",
                clip.fps,
                crf=INFERENCE.target_h264_crf,
                preset=INFERENCE.h264_preset,
            )

        return self._decode_and_publish(latents, publish, retain_video=False)

    def release_replicas(self) -> None:
        """Keep one CPU model while releasing stage-local parallel replicas."""

        del self._models[1:]
        gc.collect()

    def close(self) -> None:
        """Release all CPU replicas after the final VAE stage."""

        self._models.clear()
        gc.collect()
