"""CUDA device selection shared by pipeline and isolated workers."""

from __future__ import annotations

import os
import subprocess
from collections.abc import MutableMapping, Sequence

from fdanyone.errors import ConfigurationError

CUDA_ALLOCATOR_CONF = "PYTORCH_CUDA_ALLOC_CONF"
CUDA_MAX_SPLIT_SIZE_MB = 4096
CUDA_EXPANDABLE_SEGMENT_MAX_MEMORY_BYTES = 24 * 1024**3


def _visible_gpu_identifiers(environment: MutableMapping[str, str]) -> tuple[str, ...] | None:
    """Return CUDA-visible NVIDIA identifiers without initializing CUDA."""

    raw = environment.get("CUDA_VISIBLE_DEVICES")
    if raw is None:
        raw = environment.get("NVIDIA_VISIBLE_DEVICES")
    if raw is None or raw.strip().lower() == "all":
        return None
    if raw.strip().lower() in {"", "-1", "none", "void"}:
        return ()
    return tuple(identifier.strip() for identifier in raw.split(",") if identifier.strip())


def _selected_gpu_identifiers(
    gpu_ids: Sequence[int] | None,
    environment: MutableMapping[str, str],
) -> tuple[str, ...] | None:
    """Map CUDA-visible indices to identifiers accepted by ``nvidia-smi``."""

    visible = _visible_gpu_identifiers(environment)
    if gpu_ids is None:
        return visible
    if (
        isinstance(gpu_ids, (str, bytes))
        or not isinstance(gpu_ids, Sequence)
        or not gpu_ids
        or any(isinstance(gpu_id, bool) or not isinstance(gpu_id, int) or gpu_id < 0 for gpu_id in gpu_ids)
    ):
        return ()
    if visible is None:
        return tuple(str(gpu_id) for gpu_id in gpu_ids)
    if any(gpu_id >= len(visible) for gpu_id in gpu_ids):
        return ()
    return tuple(visible[gpu_id] for gpu_id in gpu_ids)


def _query_total_memory_bytes(identifiers: tuple[str, ...] | None) -> tuple[int, ...]:
    """Query selected GPU capacities through the driver utility, before PyTorch."""

    if identifiers == ():
        return ()
    command = ["nvidia-smi"]
    if identifiers is not None:
        command.append(f"--id={','.join(identifiers)}")
    command.extend(("--query-gpu=memory.total", "--format=csv,noheader,nounits"))
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=5)
        totals_mib = tuple(int(line.strip()) for line in completed.stdout.splitlines() if line.strip())
    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        return ()
    return tuple(total_mib * 1024**2 for total_mib in totals_mib)


def selected_gpus_need_expandable_segments(
    gpu_ids: Sequence[int] | None,
    environment: MutableMapping[str, str] | None = None,
) -> bool:
    """Return whether any selected GPU has at most 24 GiB of device memory."""

    environment = os.environ if environment is None else environment
    identifiers = _selected_gpu_identifiers(gpu_ids, environment)
    totals = _query_total_memory_bytes(identifiers)
    return bool(totals) and any(total <= CUDA_EXPANDABLE_SEGMENT_MAX_MEMORY_BYTES for total in totals)


def configure_inference_cuda_allocator(
    environment: MutableMapping[str, str] | None = None,
    *,
    use_expandable_segments: bool = False,
) -> None:
    """Configure the long-lived DiT allocator before the first PyTorch import."""

    environment = os.environ if environment is None else environment
    current = environment.get(CUDA_ALLOCATOR_CONF, "").strip()
    options = tuple(option.strip() for option in current.split(",") if option.strip())
    keys = {option.partition(":")[0] for option in options}
    backend = next((option.partition(":")[2] for option in options if option.partition(":")[0] == "backend"), None)
    if backend not in {None, "native"}:
        return
    additions: list[str] = []
    if use_expandable_segments and "expandable_segments" not in keys:
        additions.append("expandable_segments:True")
    if "max_split_size_mb" not in keys:
        additions.append(f"max_split_size_mb:{CUDA_MAX_SPLIT_SIZE_MB}")
    if additions:
        environment[CUDA_ALLOCATOR_CONF] = ",".join((*options, *additions))


def select_cuda_device(device: str) -> tuple[str, int]:
    """Validate, select, and normalize one CUDA device."""

    import torch

    try:
        requested = torch.device(device)
    except (RuntimeError, TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid CUDA device {device!r}.") from exc
    if requested.type != "cuda" or not torch.cuda.is_available():
        raise ConfigurationError(f"4DAnyone requires an available CUDA device, got {device!r}.")
    index = torch.cuda.current_device() if requested.index is None else requested.index
    if index < 0 or index >= torch.cuda.device_count():
        raise ConfigurationError(
            f"CUDA device index {index} is unavailable; visible device count is {torch.cuda.device_count()}."
        )
    torch.cuda.set_device(index)
    return f"cuda:{index}", index


def select_cuda_devices(gpu_ids: Sequence[int] | None = None) -> tuple[str, ...]:
    """Select an ordered set of CUDA-visible devices for one inference run."""

    import torch

    if not torch.cuda.is_available() or torch.cuda.device_count() <= 0:
        raise ConfigurationError("4DAnyone requires at least one available CUDA device.")

    if gpu_ids is None:
        selected = tuple(range(torch.cuda.device_count()))
    else:
        if isinstance(gpu_ids, (str, bytes)) or not isinstance(gpu_ids, Sequence) or not gpu_ids:
            raise ConfigurationError("gpu_ids must be a non-empty list of CUDA-visible device IDs.")
        selected = tuple(gpu_ids)
        invalid = [gpu_id for gpu_id in selected if isinstance(gpu_id, bool) or not isinstance(gpu_id, int)]
        if invalid:
            raise ConfigurationError(f"gpu_ids must contain only integers, got {invalid!r}.")
        if len(set(selected)) != len(selected):
            raise ConfigurationError(f"gpu_ids must not contain duplicates, got {list(selected)!r}.")

    available = torch.cuda.device_count()
    unavailable = [gpu_id for gpu_id in selected if gpu_id < 0 or gpu_id >= available]
    if unavailable:
        raise ConfigurationError(
            f"gpu_ids contains unavailable CUDA-visible device IDs {unavailable}; visible device count is {available}."
        )
    torch.cuda.set_device(selected[0])
    return tuple(f"cuda:{gpu_id}" for gpu_id in selected)
