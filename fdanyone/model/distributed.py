"""Single-node distributed target denoising.

The public pipeline keeps preprocessing, RCP, and result publication in the
primary process.  This module gives each CUDA worker one DiT replica and uses
NCCL collectives to evaluate independent camera groups in parallel.  Every
TCR step is fully gathered before the next routing step begins.
"""

from __future__ import annotations

import json
import logging
import math
import os
import socket
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from fdanyone.errors import FourDAnyoneError

if TYPE_CHECKING:
    from torch import Tensor

    from fdanyone.config import DenoisingProfile
    from fdanyone.model.conditioning import PoseFeatureBank
    from fdanyone.model.loader import Denoiser

LOGGER = logging.getLogger("fdanyone")

CameraGroup = tuple[int, ...]
StepGroups = tuple[CameraGroup, ...]
Routes = tuple[StepGroups, ...]


class WorkerReport(TypedDict):
    """Per-rank measurements published by a distributed denoising worker."""

    rank: int
    device: str
    device_name: str
    attention_backend: str
    model_load_seconds: float
    denoise_seconds: float
    peak_vram_allocated_bytes: int
    peak_vram_reserved_bytes: int


@dataclass(frozen=True)
class DistributedDenoiseRequest:
    checkpoint_path: str
    turbo_lora_path: str | None
    denoising_profile: DenoisingProfile
    routes: Routes
    devices: tuple[str, ...]
    work_dir: str
    pose_feature_shape: tuple[int, ...]
    init_method: str


def worker_count_for_groups(num_groups: int, max_workers: int) -> int:
    """Use fewer workers when that balances groups without adding waves."""

    if num_groups <= 0 or max_workers <= 0:
        raise ValueError(f"num_groups and max_workers must be positive, got {num_groups} and {max_workers}.")
    workers = min(num_groups, max_workers)
    waves = math.ceil(num_groups / workers)
    for candidate in range(workers, 0, -1):
        if num_groups % candidate == 0 and num_groups // candidate == waves:
            return candidate
    return workers


def select_worker_devices(devices: Sequence[str], num_groups: int) -> tuple[str, ...]:
    """Choose the largest balanced GPU prefix that does not add a wave."""

    if not devices:
        raise ValueError("At least one candidate GPU is required.")
    return tuple(devices[: worker_count_for_groups(num_groups, len(devices))])


def group_waves(groups: Sequence[CameraGroup], num_workers: int) -> tuple[StepGroups, ...]:
    """Split one routing step into waves that fit the available workers."""

    if num_workers <= 0:
        raise ValueError(f"num_workers must be positive, got {num_workers}.")
    return tuple(tuple(groups[start : start + num_workers]) for start in range(0, len(groups), num_workers))


def validate_routes(routes: Routes, num_views: int) -> None:
    """Require every routing step to be a disjoint canonical camera partition."""

    expected = list(range(num_views))
    if not routes:
        raise ValueError("Distributed denoising requires at least one routing step.")
    if not routes[0] or not routes[0][0]:
        raise ValueError("Distributed denoising requires non-empty camera groups.")
    num_groups = len(routes[0])
    group_size = len(routes[0][0])
    for step_index, groups in enumerate(routes):
        if len(groups) != num_groups:
            raise ValueError(f"Routing step {step_index} has {len(groups)} groups; every step must have {num_groups}.")
        if any(len(group) != group_size for group in groups):
            raise ValueError(f"Routing step {step_index} contains camera groups with inconsistent sizes.")
        flattened = sorted(camera for group in groups for camera in group)
        if flattened != expected:
            raise ValueError(
                f"Routing step {step_index} is not a disjoint partition of cameras 0..{num_views - 1}: {groups}."
            )


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _resolve_empty_workspace(path: str | Path) -> Path:
    """Validate the caller-owned transient directory used by spawned ranks."""

    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Distributed work_dir must be an existing directory: {root}")
    if any(root.iterdir()):
        raise ValueError(f"Distributed work_dir must be empty: {root}")
    return root


def _write_pose_feature_file(pose_features: PoseFeatureBank, path: Path) -> tuple[int, ...]:
    """Write precomputed target pose features to a worker-shared BF16 tensor."""

    import torch

    features = pose_features.features
    if features.ndim != 5 or features.shape[0] <= 0:
        raise FourDAnyoneError("Distributed target denoising requires at least one pose feature.")
    shape = tuple(features.shape)
    numel = math.prod(shape)
    with path.open("xb") as handle:
        handle.truncate(numel * features.element_size())
    mapped = torch.from_file(str(path), shared=True, size=numel, dtype=torch.bfloat16).view(shape)
    mapped.copy_(features)
    del mapped
    return shape


@dataclass
class _WorkerState:
    """CUDA tensors and collectives owned by one spawned NCCL rank."""

    rank: int
    request: DistributedDenoiseRequest
    denoiser: Denoiser
    device: str
    device_index: int
    source: Tensor
    context: Tensor
    null_pose_feature: Tensor
    pose_features: Tensor
    latents: Tensor | None
    pose_feature_batch: Tensor
    latent_tail: tuple[int, ...]

    @property
    def is_primary(self) -> bool:
        return self.rank == 0

    @property
    def world_size(self) -> int:
        return len(self.request.devices)

    def _scatter_latents(self, wave: StepGroups) -> Tensor:
        import torch
        import torch.distributed as dist

        local_input = torch.empty(
            (self.pose_feature_batch.shape[0], *self.latent_tail),
            dtype=self.denoiser.dtype,
            device=self.device,
        )
        scatter_list = None
        if self.is_primary:
            if self.latents is None:
                raise RuntimeError("The primary distributed rank does not own canonical latents.")
            scatter_list = [torch.zeros_like(local_input) for _ in range(self.world_size)]
            for worker_index, group in enumerate(wave):
                index = torch.tensor(group, dtype=torch.long, device=self.device)
                scatter_list[worker_index].copy_(torch.index_select(self.latents, 0, index))
        dist.scatter(local_input, scatter_list=scatter_list, src=0)
        return local_input

    def _denoise_local_group(self, local_input: Tensor, wave: StepGroups, step_index: int) -> Tensor:
        import torch

        if self.rank >= len(wave):
            return torch.zeros_like(local_input)

        from fdanyone.model.denoise import denoise_group

        group = wave[self.rank]
        for output_index, camera_id in enumerate(group):
            self.pose_feature_batch[output_index].copy_(self.pose_features[camera_id])
        with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            return denoise_group(
                self.denoiser,
                local_input,
                self.source,
                self.context,
                self.pose_feature_batch,
                self.null_pose_feature,
                step_index,
            )

    def _gather_and_commit(self, local_result: Tensor, wave: StepGroups) -> None:
        import torch
        import torch.distributed as dist

        gathered = [torch.empty_like(local_result) for _ in range(self.world_size)] if self.is_primary else None
        dist.gather(local_result, gather_list=gathered, dst=0)
        if not self.is_primary:
            return
        if self.latents is None or gathered is None:
            raise RuntimeError("The primary distributed rank cannot commit gathered latents.")
        for group, result in zip(wave, gathered[: len(wave)], strict=True):
            index = torch.tensor(group, dtype=torch.long, device=self.device)
            self.latents.index_copy_(0, index, result)

    def denoise(self) -> None:
        """Run every route step, committing a complete step before TCR moves on."""

        import torch.distributed as dist

        for step_index, groups in enumerate(self.request.routes):
            for wave in group_waves(groups, self.world_size):
                local_input = self._scatter_latents(wave)
                local_result = self._denoise_local_group(local_input, wave, step_index)
                self._gather_and_commit(local_result, wave)
                del local_input, local_result
            dist.barrier(device_ids=[self.device_index])
            if self.is_primary:
                LOGGER.info("Completed target denoising step %d/%d", step_index + 1, len(self.request.routes))


def _load_worker_state(rank: int, request: DistributedDenoiseRequest, denoiser: Denoiser) -> _WorkerState:
    import torch

    device = request.devices[rank]
    payload = torch.load(
        Path(request.work_dir) / "inputs.pt",
        map_location="cpu",
        weights_only=True,
        mmap=True,
    )
    group_size = len(request.routes[0][0])
    pose_features = torch.from_file(
        str(Path(request.work_dir) / "pose_features.bf16"),
        shared=False,
        size=math.prod(request.pose_feature_shape),
        dtype=torch.bfloat16,
    ).view(request.pose_feature_shape)
    return _WorkerState(
        rank=rank,
        request=request,
        denoiser=denoiser,
        device=device,
        device_index=int(device.removeprefix("cuda:")),
        source=payload["source"].to(dtype=denoiser.dtype, device=device),
        context=payload["context"].to(dtype=denoiser.dtype, device=device),
        null_pose_feature=payload["null_pose_feature"].to(dtype=denoiser.dtype, device=device),
        pose_features=pose_features,
        latents=payload["initial_latents"].to(dtype=denoiser.dtype, device=device) if rank == 0 else None,
        pose_feature_batch=torch.empty(
            (group_size, *request.pose_feature_shape[1:]),
            dtype=denoiser.dtype,
            device=device,
        ),
        latent_tail=tuple(payload["initial_latents"].shape[1:]),
    )


def _publish_worker_result(state: _WorkerState, report: WorkerReport) -> None:
    import torch

    root = Path(state.request.work_dir)
    if state.is_primary:
        if state.latents is None:
            raise RuntimeError("The primary distributed rank has no target latents to publish.")
        temporary = root / ".target_latents.pt.tmp"
        torch.save(state.latents.detach().to("cpu"), temporary)
        os.replace(temporary, root / "target_latents.pt")
    (root / f"rank-{state.rank}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def _worker(rank: int, request: DistributedDenoiseRequest) -> None:
    """Run one NCCL rank. Rank zero owns and publishes the canonical latents."""

    import torch
    import torch.distributed as dist

    from fdanyone.model.loader import load_denoiser
    from fdanyone.vendor.diffsynth.models.wan_video_dit import get_attention_backend

    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s | %(levelname)s | GPU rank {rank} | %(message)s",
    )
    os.environ.setdefault("TORCH_NCCL_ASYNC_ERROR_HANDLING", "1")
    os.environ.setdefault("CUDA_DEVICE_MAX_CONNECTIONS", "1")

    device = request.devices[rank]
    device_index = int(device.removeprefix("cuda:"))
    torch.cuda.set_device(device_index)
    torch.cuda.reset_peak_memory_stats(device_index)
    resolved_backend = get_attention_backend()

    model_started = time.monotonic()
    denoiser = load_denoiser(
        checkpoint_path=request.checkpoint_path,
        turbo_lora_path=request.turbo_lora_path,
        profile=request.denoising_profile,
    )
    denoiser.prepare_on_device(device)
    torch.cuda.synchronize(device_index)
    model_load_seconds = time.monotonic() - model_started

    dist.init_process_group(
        backend="nccl",
        init_method=request.init_method,
        rank=rank,
        world_size=len(request.devices),
        timeout=timedelta(minutes=30),
    )
    try:
        state = _load_worker_state(rank, request, denoiser)
        dist.barrier(device_ids=[device_index])
        denoise_started = time.monotonic()
        state.denoise()
        torch.cuda.synchronize(device_index)
        denoise_seconds = time.monotonic() - denoise_started

        report: WorkerReport = {
            "rank": rank,
            "device": device,
            "device_name": torch.cuda.get_device_name(device_index),
            "attention_backend": resolved_backend,
            "model_load_seconds": model_load_seconds,
            "denoise_seconds": denoise_seconds,
            "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated(device_index)),
            "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved(device_index)),
        }
        _publish_worker_result(state, report)
        dist.barrier(device_ids=[device_index])
    finally:
        if dist.is_initialized():
            dist.destroy_process_group()


def denoise_targets_distributed(
    *,
    checkpoint_path: str | Path,
    turbo_lora_path: str | Path | None,
    denoising_profile: DenoisingProfile,
    routes: Routes,
    src_latents: Tensor,
    context: Tensor,
    initial_latents: Tensor,
    pose_features: PoseFeatureBank,
    work_dir: str | Path,
    devices: Sequence[str],
) -> tuple[Tensor, list[WorkerReport]]:
    """Prepare shared inputs, launch NCCL workers, and return canonical latents."""

    import torch
    import torch.multiprocessing as mp

    devices = tuple(devices)
    if len(devices) < 2:
        raise ValueError("Distributed denoising requires at least two GPUs.")
    if not torch.distributed.is_available() or not torch.distributed.is_nccl_available():
        raise FourDAnyoneError("Multi-GPU inference requires a PyTorch build with NCCL support.")
    validate_routes(routes, int(initial_latents.shape[0]))
    if len(routes) != denoising_profile.num_inference_steps:
        raise ValueError(
            f"Denoising profile {denoising_profile.name!r} requires "
            f"{denoising_profile.num_inference_steps} routing steps, got {len(routes)}."
        )
    num_groups = len(routes[0])

    root = _resolve_empty_workspace(work_dir)
    torch.save(
        {
            "source": src_latents.detach().to("cpu").contiguous(),
            "context": context.detach().to("cpu").contiguous(),
            "null_pose_feature": pose_features.null_features,
            "initial_latents": initial_latents.detach().to("cpu").contiguous(),
        },
        root / "inputs.pt",
    )
    pose_feature_shape = _write_pose_feature_file(
        pose_features,
        root / "pose_features.bf16",
    )
    request = DistributedDenoiseRequest(
        checkpoint_path=str(Path(checkpoint_path).expanduser().resolve()),
        turbo_lora_path=(None if turbo_lora_path is None else str(Path(turbo_lora_path).expanduser().resolve())),
        denoising_profile=denoising_profile,
        routes=routes,
        devices=devices,
        work_dir=str(root),
        pose_feature_shape=pose_feature_shape,
        init_method=f"tcp://127.0.0.1:{_free_local_port()}",
    )
    LOGGER.info(
        "Starting distributed target denoising on %d GPUs (%d groups, up to %d waves per step)",
        len(devices),
        num_groups,
        math.ceil(num_groups / len(devices)),
    )
    try:
        mp.spawn(_worker, args=(request,), nprocs=len(devices), join=True)
    except Exception as exc:
        raise FourDAnyoneError(f"Multi-GPU target denoising failed: {exc}") from exc

    output_path = root / "target_latents.pt"
    if not output_path.is_file():
        raise FourDAnyoneError("Multi-GPU target denoising finished without publishing target latents.")
    latents = torch.load(output_path, map_location="cpu", weights_only=True)
    reports: list[WorkerReport] = []
    for rank in range(len(devices)):
        report_path = root / f"rank-{rank}.json"
        if not report_path.is_file():
            raise FourDAnyoneError(f"Multi-GPU worker {rank} did not publish its runtime report.")
        reports.append(json.loads(report_path.read_text()))
    return latents, reports
