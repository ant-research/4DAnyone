"""CUDA device selection shared by pipeline and isolated workers."""

from __future__ import annotations

from collections.abc import Sequence

from fdanyone.errors import ConfigurationError


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
