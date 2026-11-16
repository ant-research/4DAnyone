"""VGG-19 perceptual loss for Nerfstudio reconstruction."""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from functools import cache
from pathlib import Path

import torch
import torch.nn.functional as F
from safetensors.torch import load_file
from torch import nn

from fdanyone.errors import AssetError

# The reference objective reads these layers from the MatConvNet VGG-19
# checkpoint and returns features after conv{1,2,3,4,5}_2. The final two VGG
# convolutions and classifier are not evaluated by its forward pass.
VGG19_CONV_CHANNELS = (
    (3, 64),
    (64, 64),
    (64, 128),
    (128, 128),
    (128, 256),
    (256, 256),
    (256, 256),
    (256, 256),
    (256, 512),
    (512, 512),
    (512, 512),
    (512, 512),
    (512, 512),
    (512, 512),
)
VGG19_FEATURE_LAYERS = (2, 4, 6, 10, 14)
VGG19_POOL_AFTER = frozenset((2, 4, 8, 12))
PERCEPTUAL_FEATURE_DIVISORS = (2.6, 4.8, 3.7, 5.6, 0.15)
PERCEPTUAL_COMPUTE_DTYPES = ("float32", "bfloat16")


@cache
def _supports_bfloat16(device_index: int) -> bool:
    # Check the tensor's GPU, and do not mistake BF16 emulation for native support.
    with torch.cuda.device(device_index):
        supported = torch.cuda.is_bf16_supported(including_emulation=False)
    if not supported:
        warnings.warn(
            f"CUDA device {device_index} does not support native bfloat16; "
            "falling back to float32 for the perceptual loss.",
            RuntimeWarning,
            stacklevel=2,
        )
    return supported


def _autocast_context(compute_dtype: str, device: torch.device) -> AbstractContextManager:
    if compute_dtype not in PERCEPTUAL_COMPUTE_DTYPES:
        choices = ", ".join(PERCEPTUAL_COMPUTE_DTYPES)
        raise ValueError(f"perceptual compute dtype must be one of: {choices}.")
    if compute_dtype == "float32":
        return nullcontext()
    if device.type != "cuda":
        raise RuntimeError("bfloat16 perceptual computation currently requires CUDA.")
    device_index = device.index if device.index is not None else torch.cuda.current_device()
    if not _supports_bfloat16(device_index):
        # Override any surrounding mixed-precision context as well.
        return torch.autocast(device_type="cuda", enabled=False)
    return torch.autocast(device_type="cuda", dtype=torch.bfloat16)


def _validated_weights(path: Path) -> Mapping[str, torch.Tensor]:
    try:
        state = load_file(str(path), device="cpu")
    except (OSError, ValueError) as exc:
        raise AssetError(f"Cannot load perceptual VGG-19 weights at {path}: {exc}") from exc

    expected = set()
    for index, (in_channels, out_channels) in enumerate(VGG19_CONV_CHANNELS, start=1):
        weight_name = f"conv{index}.weight"
        bias_name = f"conv{index}.bias"
        expected.update((weight_name, bias_name))
        weight = state.get(weight_name)
        bias = state.get(bias_name)
        expected_weight_shape = (out_channels, in_channels, 3, 3)
        if weight is None or tuple(weight.shape) != expected_weight_shape:
            shape = None if weight is None else tuple(weight.shape)
            raise AssetError(
                f"Perceptual VGG-19 tensor {weight_name} has shape {shape}; expected {expected_weight_shape}."
            )
        if bias is None or tuple(bias.shape) != (out_channels,):
            shape = None if bias is None else tuple(bias.shape)
            raise AssetError(f"Perceptual VGG-19 tensor {bias_name} has shape {shape}; expected {(out_channels,)}.")
    unexpected = set(state) - expected
    if unexpected:
        raise AssetError(f"Perceptual VGG-19 weights contain unexpected tensors: {sorted(unexpected)}")
    return state


class MatConvNetVGG19Features(nn.Module):
    """Frozen MatConvNet VGG-19 features used by the perceptual objective.

    The weights are non-persistent buffers: they move with the Nerfstudio model
    but remain in the separately downloaded asset instead of being duplicated
    into every Splatfacto checkpoint.
    """

    def __init__(self, weights_path: str | Path) -> None:
        super().__init__()
        path = Path(weights_path).expanduser().resolve()
        if not path.is_file():
            raise AssetError(
                f"Perceptual VGG-19 weights do not exist: {path}. "
                "Run `python scripts/download_model.py` to install them."
            )
        state = _validated_weights(path)
        for index in range(1, len(VGG19_CONV_CHANNELS) + 1):
            self.register_buffer(
                f"conv{index}_weight",
                state[f"conv{index}.weight"].float().contiguous(),
                persistent=False,
            )
            self.register_buffer(
                f"conv{index}_bias",
                state[f"conv{index}.bias"].float().contiguous(),
                persistent=False,
            )

    def forward(self, image: torch.Tensor) -> tuple[torch.Tensor, ...]:
        features = []
        value = image.float().contiguous()
        for index in range(1, len(VGG19_CONV_CHANNELS) + 1):
            weight = getattr(self, f"conv{index}_weight")
            bias = getattr(self, f"conv{index}_bias")
            value = F.relu(F.conv2d(value, weight, bias, padding=1), inplace=False)
            if index in VGG19_FEATURE_LAYERS:
                features.append(value)
            if index in VGG19_POOL_AFTER:
                value = F.avg_pool2d(value, kernel_size=2, stride=2)
        return tuple(features)


def perceptual_distance(
    prediction: torch.Tensor,
    target: torch.Tensor,
    prediction_features: tuple[torch.Tensor, ...],
    target_features: tuple[torch.Tensor, ...],
    *,
    include_rgb: bool = True,
) -> torch.Tensor:
    """Apply the reference pixel/feature weighting to scaled images."""

    if len(prediction_features) != 5 or len(target_features) != 5:
        raise ValueError("The perceptual loss requires exactly five VGG feature tensors.")
    terms = [torch.mean(torch.abs(target - prediction))] if include_rgb else []
    terms.extend(
        torch.mean(torch.abs(target_features[index] - prediction_features[index])) / divisor
        for index, divisor in enumerate(PERCEPTUAL_FEATURE_DIVISORS)
    )
    # Removing the FP32 RGB term must not turn the feature sum into a BF16 reduction.
    return torch.stack(terms).to(prediction.dtype).sum() / 255.0


class VGG19PerceptualLoss(nn.Module):
    """The reconstruction objective's VGG-19 loss, not standard LPIPS."""

    def __init__(self, weights_path: str | Path, compute_dtype: str = "float32", *, include_rgb: bool = True) -> None:
        super().__init__()
        if compute_dtype not in PERCEPTUAL_COMPUTE_DTYPES:
            choices = ", ".join(PERCEPTUAL_COMPUTE_DTYPES)
            raise ValueError(f"perceptual compute dtype must be one of: {choices}.")
        self.compute_dtype = compute_dtype
        self.include_rgb = include_rgb
        self.features = MatConvNetVGG19Features(weights_path)
        self.register_buffer(
            "imagenet_mean",
            torch.tensor((123.6800, 116.7790, 103.9390), dtype=torch.float32).reshape(1, 3, 1, 1),
            persistent=False,
        )

    def forward(self, prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        if prediction.shape != target.shape or prediction.ndim != 4 or prediction.shape[1] != 3:
            raise ValueError("VGG-19 perceptual loss expects prediction and target with matching [B, 3, H, W] shapes.")
        prediction_scaled = prediction.float() * 255.0 - self.imagenet_mean
        target_scaled = target.float() * 255.0 - self.imagenet_mean
        with _autocast_context(self.compute_dtype, prediction.device):
            with torch.no_grad():
                target_features = self.features(target_scaled)
            prediction_features = self.features(prediction_scaled)
        return perceptual_distance(
            prediction_scaled,
            target_scaled,
            prediction_features,
            target_features,
            include_rgb=self.include_rgb,
        )
