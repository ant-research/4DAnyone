"""Direct, registry-free loading of the frozen Wan/SpaTem inference stack."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fdanyone.config import DenoisingProfile
from fdanyone.errors import AssetError, ConfigurationError

if TYPE_CHECKING:
    import torch
    from torch import nn

    from fdanyone.vendor.diffsynth.schedulers.flow_match import FlowMatchScheduler

POSE_ENCODER_PREFIX = "pose_encoder."


@dataclass
class Denoiser:
    """A loaded DiT, its configured scheduler, and optional Turbo fusion."""

    model: nn.Module
    scheduler: FlowMatchScheduler
    dtype: torch.dtype
    turbo_lora_path: Path | None = None
    turbo_lora_applied: bool = field(default=False, init=False)

    def prepare_on_device(self, device: str | torch.device) -> None:
        """Move the DiT to a device and apply its configured Turbo delta once."""

        self.model.to(device=device, dtype=self.dtype)
        if self.turbo_lora_path is not None and not self.turbo_lora_applied:
            from fdanyone.model.turbo_lora import fuse_turbo_lora

            fuse_turbo_lora(self.model, self.turbo_lora_path)
            self.turbo_lora_applied = True


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
        return (
            {key: checkpoint.get_tensor(key) for key in keys},
            dict(checkpoint.metadata() or {}),
        )


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
    state_dict, metadata = _load_checkpoint(checkpoint_path, exclude_prefixes=(POSE_ENCODER_PREFIX,))
    _strict_assign(dit, state_dict, "4DAnyone DiT checkpoint")
    del state_dict
    # ``freqs`` is a derived, non-persistent tensor and therefore is not in the
    # state dict populated above.
    dit.freqs = precompute_freqs_cis_3d(MODEL_DIM // NUM_HEADS)
    return dit.eval().requires_grad_(False), metadata


def load_pose_encoder(checkpoint_path: str | Path, device: str):
    """Load only the small pose encoder partition from the DiT checkpoint."""

    import torch

    from fdanyone.vendor.diffsynth.models.wan_video_dit import MODEL_DIM
    from fdanyone.vendor.diffsynth.models.wan_video_pose_encoder import PoseEncoder

    checkpoint, _ = _load_checkpoint(Path(checkpoint_path), include_prefix=POSE_ENCODER_PREFIX)
    state_dict = {key.removeprefix(POSE_ENCODER_PREFIX): value for key, value in checkpoint.items()}
    del checkpoint
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


def load_denoiser(
    *,
    checkpoint_path: str | Path,
    turbo_lora_path: str | Path | None,
    profile: DenoisingProfile,
) -> Denoiser:
    """Load one DiT and configure its denoising trajectory."""

    import torch

    from fdanyone.vendor.diffsynth.schedulers.flow_match import FlowMatchScheduler

    dtype = torch.bfloat16
    checkpoint = Path(checkpoint_path).expanduser().resolve()
    if not checkpoint.is_file():
        raise AssetError(f"4DAnyone checkpoint does not exist: {checkpoint}")
    turbo_path = None if turbo_lora_path is None else Path(turbo_lora_path).expanduser().resolve()
    if turbo_path is not None and not turbo_path.is_file():
        raise AssetError(f"Turbo LoRA does not exist: {turbo_path}")
    model, metadata = _load_dit(checkpoint)
    if turbo_path is not None:
        from fdanyone.model.turbo_lora import validate_turbo_base_metadata

        validate_turbo_base_metadata(metadata)
    # ``step`` only reads the trajectory, so RCP and target generation can
    # safely share one scheduler configured when this denoiser is loaded.
    scheduler = FlowMatchScheduler(shift=profile.scheduler_shift, sigma_min=0.0, extra_one_step=True)
    scheduler.set_timesteps(
        profile.num_inference_steps,
        denoising_strength=profile.denoising_strength,
    )
    return Denoiser(
        model=model,
        scheduler=scheduler,
        dtype=dtype,
        turbo_lora_path=turbo_path,
    )
