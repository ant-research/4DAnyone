"""Direct, registry-free loading of the frozen Wan/SpaTem inference stack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fdanyone.errors import AssetError, ConfigurationError

if TYPE_CHECKING:
    import torch
    from torch import nn

    from fdanyone.vendor.diffsynth.schedulers.flow_match import FlowMatchScheduler

POSE_ENCODER_PREFIX = "pose_encoder."


@dataclass(frozen=True)
class Denoiser:
    """The exact DiT, scheduler, and dtype used by one denoising process."""

    model: nn.Module
    scheduler: FlowMatchScheduler
    dtype: torch.dtype


def _load_checkpoint(
    path: Path,
    *,
    include_prefix: str | None = None,
    exclude_prefixes: tuple[str, ...] = (),
):
    try:
        from safetensors import safe_open
    except ImportError as exc:
        raise AssetError("safetensors is required to load the 4DAnyone checkpoint.") from exc
    with safe_open(str(path), framework="pt", device="cpu") as checkpoint:
        checkpoint_keys = checkpoint.keys()
        keys = (
            key
            for key in checkpoint_keys
            if (include_prefix is None or key.startswith(include_prefix))
            and not any(key.startswith(prefix) for prefix in exclude_prefixes)
        )
        return {key: checkpoint.get_tensor(key) for key in keys}


def _strict_assign(module, state_dict: dict, label: str) -> None:
    """Load into a meta-initialized module without a second parameter copy."""

    try:
        incompatible = module.load_state_dict(state_dict, strict=True, assign=True)
    except TypeError as exc:
        raise ConfigurationError("4DAnyone requires PyTorch >=2.8 for assign-based model loading.") from exc
    except RuntimeError as exc:
        raise AssetError(f"{label} is incompatible with the released architecture: {exc}") from exc
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise AssetError(
            f"{label} strict load failed; missing={incompatible.missing_keys}, "
            f"unexpected={incompatible.unexpected_keys}"
        )


def _load_dit(checkpoint_path: Path):
    import torch

    from fdanyone.vendor.diffsynth.models.wan_video_dit import (
        MODEL_DIM,
        NUM_HEADS,
        FourDAnyoneDiT,
        precompute_freqs_cis_3d,
    )

    with torch.device("meta"):
        dit = FourDAnyoneDiT()
    state_dict = _load_checkpoint(checkpoint_path, exclude_prefixes=(POSE_ENCODER_PREFIX,))
    _strict_assign(dit, state_dict, "4DAnyone DiT checkpoint")
    del state_dict
    # ``freqs`` is a derived, non-persistent tensor and therefore is not in the
    # state dict populated above.
    dit.freqs = precompute_freqs_cis_3d(MODEL_DIM // NUM_HEADS)
    return dit.eval().requires_grad_(False)


def load_pose_encoder(checkpoint_path: str | Path, device: str):
    """Load only the small pose encoder partition from the DiT checkpoint."""

    import torch

    from fdanyone.vendor.diffsynth.models.wan_video_dit import MODEL_DIM
    from fdanyone.vendor.diffsynth.models.wan_video_pose_encoder import PoseEncoder

    state_dict = {
        key.removeprefix(POSE_ENCODER_PREFIX): value
        for key, value in _load_checkpoint(Path(checkpoint_path), include_prefix=POSE_ENCODER_PREFIX).items()
    }
    with torch.device("meta"):
        pose_encoder = PoseEncoder(out_dim=MODEL_DIM, in_channels=3)
    _strict_assign(pose_encoder, state_dict, "4DAnyone pose encoder checkpoint")
    del state_dict
    return pose_encoder.to(device=device, dtype=torch.bfloat16).eval().requires_grad_(False)


def _load_vae(path: Path, dtype):
    import torch

    from fdanyone.vendor.diffsynth.models.wan_video_vae import WanVideoVAE38

    state_dict = torch.load(path, map_location="cpu", weights_only=True)
    state_dict = WanVideoVAE38.state_dict_converter().from_civitai(state_dict)
    with torch.device("meta"):
        vae = WanVideoVAE38()
    _strict_assign(vae, state_dict, "Wan2.2 VAE")
    del state_dict
    # These tensors are derived attributes, not checkpoint entries. Recreate
    # them after strict assignment because construction happened on ``meta``.
    vae.materialize_normalization(device="cpu")
    return vae.to(dtype=dtype).eval().requires_grad_(False)


def load_vae(path: str | Path):
    """Load the frozen Wan VAE as an independent generation stage."""

    import torch

    return _load_vae(Path(path), torch.bfloat16)


def load_denoiser(*, checkpoint_path: str | Path) -> Denoiser:
    """Load the DiT and scheduler required by one distributed worker."""

    import torch

    from fdanyone.vendor.diffsynth.schedulers.flow_match import FlowMatchScheduler

    dtype = torch.bfloat16
    return Denoiser(
        model=_load_dit(Path(checkpoint_path)),
        scheduler=FlowMatchScheduler(shift=5, sigma_min=0.0, extra_one_step=True),
        dtype=dtype,
    )
