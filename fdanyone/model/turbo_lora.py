"""Apply the pinned Wan2.2 Turbo difference-LoRA to a resident DiT."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from fdanyone.errors import AssetError

if TYPE_CHECKING:
    from torch import Tensor, nn

_PREFIX = "diffusion_model."
_DOWN = ".lora_down.weight"
_UP = ".lora_up.weight"
_BIAS_DIFF = ".diff_b"
_TENSOR_DIFF = ".diff"
_FUSED_METADATA_KEYS = (
    "4danyone.lora_sha256",
    "4danyone.turbo_lora_sha256",
    "4danyone.turbo_lora",
)


def _stem(key: str, suffix: str) -> str:
    stem = key[: -len(suffix)]
    if not stem.startswith(_PREFIX):
        raise ValueError(f"Turbo tensor lacks the {_PREFIX!r} prefix: {key}")
    return stem.removeprefix(_PREFIX)


def _direct_target(state_dict: Mapping[str, Tensor], stem: str) -> str:
    candidates = tuple(key for key in (stem, f"{stem}.weight") if key in state_dict)
    if len(candidates) != 1:
        raise ValueError(f"Turbo tensor {stem!r} must resolve to one base tensor, got {candidates}.")
    return candidates[0]


def validate_turbo_base_metadata(base_metadata: Mapping[str, str] | None) -> None:
    """Reject checkpoints that explicitly identify an earlier Turbo fusion."""

    fused_markers = sorted(set(base_metadata or {}).intersection(_FUSED_METADATA_KEYS))
    if fused_markers:
        raise AssetError(f"Refusing to apply Turbo to an already-fused checkpoint: {fused_markers}.")


def _fuse_low_rank_delta(state_dict: Mapping[str, Tensor], adapter: Mapping[str, Tensor], down_key: str) -> None:
    import torch

    up_key = f"{down_key[: -len(_DOWN)]}{_UP}"
    if up_key not in adapter:
        raise ValueError(f"Turbo LoRA-down tensor has no paired LoRA-up tensor: {down_key}")

    target = f"{_stem(down_key, _DOWN)}.weight"
    if target not in state_dict:
        raise ValueError(f"Turbo tensor {down_key} targets missing base tensor {target}.")

    base = state_dict[target]
    down = adapter[down_key]
    up = adapter[up_key]
    if (
        base.ndim != 2
        or down.ndim != 2
        or up.ndim != 2
        or up.shape[1] != down.shape[0]
        or tuple(base.shape) != (up.shape[0], down.shape[1])
    ):
        raise ValueError(
            f"Turbo matrix shapes do not reconstruct {target}: "
            f"base={tuple(base.shape)}, up={tuple(up.shape)}, down={tuple(down.shape)}."
        )

    merged = base.detach().to(dtype=torch.float32, copy=True)
    merged.addmm_(up.float(), down.float())
    base.copy_(merged)


def _fuse_direct_delta(state_dict: Mapping[str, Tensor], adapter: Mapping[str, Tensor], key: str) -> None:
    import torch

    if key.endswith(_BIAS_DIFF):
        target = f"{_stem(key, _BIAS_DIFF)}.bias"
    elif key.endswith(_TENSOR_DIFF):
        target = _direct_target(state_dict, _stem(key, _TENSOR_DIFF))
    else:
        raise ValueError(f"Unrecognized Turbo tensor suffix: {key}")

    if target not in state_dict:
        raise ValueError(f"Turbo tensor {key} targets missing base tensor {target}.")
    base = state_dict[target]
    delta = adapter[key]
    if tuple(base.shape) != tuple(delta.shape):
        raise ValueError(
            f"Turbo tensor shape mismatch for {target}: base={tuple(base.shape)}, delta={tuple(delta.shape)}."
        )

    merged = base.detach().to(dtype=torch.float32, copy=True)
    merged.add_(delta.float())
    base.copy_(merged)


def fuse_turbo_lora(model: nn.Module, adapter_path: str | Path) -> None:
    """Fuse the fixed-strength Wan2.2 5B Turbo LoRA into one resident DiT.

    The complete adapter remains in its serialized FP16 dtype on the target
    device.  Each target uses one temporary FP32 base tensor, converts only its
    current adapter components to FP32, and copies the merged result back into
    the original base storage and dtype.
    """

    state_dict = model.state_dict(keep_vars=True)

    path = Path(adapter_path).expanduser().resolve()
    if not path.is_file():
        raise AssetError(f"Turbo LoRA does not exist: {path}")
    if not state_dict:
        raise AssetError("Cannot apply Turbo LoRA to an empty state dict.")

    try:
        import torch
        from safetensors.torch import load_file

        devices = {tensor.device for tensor in state_dict.values()}
        if len(devices) != 1:
            raise ValueError(f"Turbo base tensors must share one device, got {sorted(map(str, devices))}.")
        device = devices.pop()
        adapter = load_file(str(path), device=str(device))
        adapter_dtypes = {tensor.dtype for tensor in adapter.values()}
        if adapter_dtypes != {torch.float16}:
            raise ValueError(
                f"Turbo LoRA tensors must all be serialized as FP16, got {sorted(map(str, adapter_dtypes))}."
            )
        with torch.no_grad():
            for key in sorted(adapter):
                if key.endswith(_UP):
                    down_key = f"{key[: -len(_UP)]}{_DOWN}"
                    if down_key not in adapter:
                        raise ValueError(f"Turbo LoRA-up tensor has no paired LoRA-down tensor: {key}")
                    continue
                if key.endswith(_DOWN):
                    _fuse_low_rank_delta(state_dict, adapter, key)
                else:
                    _fuse_direct_delta(state_dict, adapter, key)
    except ImportError as exc:
        raise AssetError("PyTorch and safetensors are required to load the Turbo LoRA.") from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise AssetError(f"Turbo LoRA is incompatible with this 4DAnyone checkpoint: {exc}") from exc
