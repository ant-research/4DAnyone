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
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TypeVar

from fdanyone.errors import FourDAnyoneError

LOGGER = logging.getLogger("fdanyone")

CameraGroup = tuple[int, ...]
StepGroups = tuple[CameraGroup, ...]
Routes = tuple[StepGroups, ...]
ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class DistributedDenoiseRequest:
    checkpoint_path: str
    work_dir: str
    devices: tuple[str, ...]
    routes: Routes
    denoising_strength: float
    scheduler_shift: float
    skeleton_shape: tuple[int, ...]
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


def run_group_schedule(
    routes: Routes,
    num_workers: int,
    *,
    execute_wave: Callable[[int, StepGroups], Sequence[ResultT]],
    apply_result: Callable[[CameraGroup, ResultT], None],
    finish_step: Callable[[int], None],
) -> None:
    """Execute group waves in route order and finish each step with a barrier."""

    for step_index, groups in enumerate(routes):
        for wave in group_waves(groups, num_workers):
            results = tuple(execute_wave(step_index, wave))
            if len(results) != len(wave):
                raise RuntimeError(f"Distributed wave returned {len(results)} results for {len(wave)} camera groups.")
            for group, result in zip(wave, results, strict=True):
                apply_result(group, result)
        finish_step(step_index)


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_skeleton_tensor_file(conditioning, skeletons: Iterable, path: Path) -> tuple[int, ...]:
    """Decode target skeletons once into a file-backed BF16 tensor."""

    import torch

    items = tuple(skeletons)
    if not items:
        raise FourDAnyoneError("Distributed target denoising requires at least one skeleton video.")

    LOGGER.info("Preparing shared target skeleton 1/%d from %s", len(items), items[0].path.name)
    first = conditioning.load_skeleton_tensor([items[0]]).to(dtype=torch.bfloat16, device="cpu").contiguous()
    if first.ndim != 5 or first.shape[0] != 1:
        raise FourDAnyoneError(f"Expected one 5D skeleton tensor, got shape {tuple(first.shape)}.")
    shape = (len(items), *tuple(first.shape[1:]))
    numel = math.prod(shape)
    with path.open("xb") as handle:
        handle.truncate(numel * first.element_size())
    mapped = torch.from_file(str(path), shared=True, size=numel, dtype=torch.bfloat16).view(shape)
    mapped[0].copy_(first[0])
    del first
    for camera_id, skeleton in enumerate(items[1:], start=1):
        LOGGER.info(
            "Preparing shared target skeleton %d/%d from %s",
            camera_id + 1,
            len(items),
            skeleton.path.name,
        )
        tensor = conditioning.load_skeleton_tensor([skeleton]).to(dtype=torch.bfloat16, device="cpu").contiguous()
        if tuple(tensor.shape[1:]) != shape[1:] or tensor.shape[0] != 1:
            raise FourDAnyoneError(
                f"Skeleton camera {camera_id} has shape {tuple(tensor.shape)}, expected {(1, *shape[1:])}."
            )
        mapped[camera_id].copy_(tensor[0])
        del tensor
    del mapped
    return shape


def _worker(rank: int, request: DistributedDenoiseRequest) -> None:
    """Run one NCCL rank. Rank zero owns and publishes the canonical latents."""

    import torch
    import torch.distributed as dist

    from fdanyone.model.denoise import denoise_group
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
    pipe = load_denoiser(checkpoint_path=request.checkpoint_path, device=device)
    pipe.dit.to(device)
    model_load_seconds = time.monotonic() - model_started

    dist.init_process_group(
        backend="nccl",
        init_method=request.init_method,
        rank=rank,
        world_size=len(request.devices),
        timeout=timedelta(minutes=30),
    )
    try:
        payload = torch.load(
            Path(request.work_dir) / "inputs.pt",
            map_location="cpu",
            weights_only=True,
            mmap=True,
        )
        source = payload["source"].to(dtype=pipe.torch_dtype, device=device)
        context = payload["context"].to(dtype=pipe.torch_dtype, device=device)
        skeletons = torch.from_file(
            str(Path(request.work_dir) / "skeletons.bf16"),
            shared=False,
            size=math.prod(request.skeleton_shape),
            dtype=torch.bfloat16,
        ).view(request.skeleton_shape)
        routes = request.routes
        group_size = len(routes[0][0])
        latent_shape = tuple(payload["initial_latents"].shape)
        latent_tail = latent_shape[1:]
        latents = payload["initial_latents"].to(dtype=pipe.torch_dtype, device=device) if rank == 0 else None

        pipe.scheduler.set_timesteps(
            len(routes),
            denoising_strength=request.denoising_strength,
            shift=request.scheduler_shift,
        )
        dist.barrier(device_ids=[device_index])
        denoise_started = time.monotonic()

        def execute_wave(step_index: int, wave: StepGroups):
            local_input = torch.empty((group_size, *latent_tail), dtype=pipe.torch_dtype, device=device)
            if rank == 0:
                scatter_list = []
                for worker_index in range(len(request.devices)):
                    padded = torch.zeros_like(local_input)
                    if worker_index < len(wave):
                        group = wave[worker_index]
                        index = torch.tensor(group, dtype=torch.long, device=device)
                        padded[: len(group)].copy_(torch.index_select(latents, 0, index))
                    scatter_list.append(padded)
            else:
                scatter_list = None
            dist.scatter(local_input, scatter_list=scatter_list, src=0)
            if scatter_list is not None:
                del scatter_list

            local_result = torch.zeros_like(local_input)
            if rank < len(wave):
                group = wave[rank]
                valid = len(group)
                local_latents = local_input[:valid]
                cpu_index = torch.tensor(group, dtype=torch.long, device="cpu")
                local_skeletons = torch.index_select(skeletons, 0, cpu_index).to(device=device)
                with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                    updated = denoise_group(
                        pipe,
                        local_latents,
                        source,
                        context,
                        local_skeletons,
                        step_index,
                    )
                local_result[:valid].copy_(updated)
                del local_latents, local_skeletons, updated

            gather_list = [torch.empty_like(local_result) for _ in request.devices] if rank == 0 else None
            dist.gather(local_result, gather_list=gather_list, dst=0)
            del local_input, local_result
            if rank == 0:
                return tuple(gather_list[: len(wave)])
            return (None,) * len(wave)

        def apply_result(group: CameraGroup, result) -> None:
            if rank != 0:
                return
            index = torch.tensor(group, dtype=torch.long, device=device)
            latents.index_copy_(0, index, result[: len(group)])

        def finish_step(step_index: int) -> None:
            dist.barrier(device_ids=[device_index])
            if rank == 0:
                LOGGER.info("Completed target denoising step %d/%d", step_index + 1, len(routes))

        run_group_schedule(
            routes,
            len(request.devices),
            execute_wave=execute_wave,
            apply_result=apply_result,
            finish_step=finish_step,
        )
        torch.cuda.synchronize(device_index)
        denoise_seconds = time.monotonic() - denoise_started

        if rank == 0:
            temporary = Path(request.work_dir) / ".target_latents.pt.tmp"
            torch.save(latents.detach().to("cpu"), temporary)
            os.replace(temporary, Path(request.work_dir) / "target_latents.pt")

        report = {
            "rank": rank,
            "device": device,
            "device_name": torch.cuda.get_device_name(device_index),
            "attention_backend": resolved_backend,
            "model_load_seconds": model_load_seconds,
            "denoise_seconds": denoise_seconds,
            "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated(device_index)),
            "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved(device_index)),
        }
        report_path = Path(request.work_dir) / f"rank-{rank}.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        dist.barrier(device_ids=[device_index])
    finally:
        if dist.is_initialized():
            dist.destroy_process_group()


def denoise_targets_distributed(
    *,
    src_latents,
    context,
    initial_latents,
    conditioning,
    routes: Routes,
    checkpoint_path: str | Path,
    work_dir: str | Path,
    devices: Sequence[str],
    denoising_strength: float,
    scheduler_shift: float,
) -> tuple[object, list[dict[str, object]]]:
    """Prepare shared inputs, launch NCCL workers, and return canonical latents."""

    import torch
    import torch.multiprocessing as mp

    devices = tuple(devices)
    if len(devices) < 2:
        raise ValueError("Distributed denoising requires at least two GPUs.")
    if not torch.distributed.is_available() or not torch.distributed.is_nccl_available():
        raise FourDAnyoneError("Multi-GPU inference requires a PyTorch build with NCCL support.")
    validate_routes(routes, int(initial_latents.shape[0]))
    num_groups = len(routes[0])

    root = Path(work_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=False)
    torch.save(
        {
            "source": src_latents.detach().to("cpu").contiguous(),
            "context": context.detach().to("cpu").contiguous(),
            "initial_latents": initial_latents.detach().to("cpu").contiguous(),
        },
        root / "inputs.pt",
    )
    skeleton_shape = _write_skeleton_tensor_file(
        conditioning,
        conditioning.target_skeletons,
        root / "skeletons.bf16",
    )
    request = DistributedDenoiseRequest(
        checkpoint_path=str(Path(checkpoint_path).expanduser().resolve()),
        work_dir=str(root),
        devices=devices,
        routes=routes,
        denoising_strength=denoising_strength,
        scheduler_shift=scheduler_shift,
        skeleton_shape=skeleton_shape,
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
    reports = []
    for rank in range(len(devices)):
        report_path = root / f"rank-{rank}.json"
        if not report_path.is_file():
            raise FourDAnyoneError(f"Multi-GPU worker {rank} did not publish its runtime report.")
        reports.append(json.loads(report_path.read_text()))
    return latents, reports
