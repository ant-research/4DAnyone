"""A Splatfacto method using the reconstruction perceptual objective."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from nerfstudio.models.splatfacto import SplatfactoModel, SplatfactoModelConfig
from nerfstudio.plugins.types import MethodSpecification

from fdanyone.assets import PERCEPTUAL_VGG19
from fdanyone.download import ensure_perceptual_vgg19
from fdanyone.nerfstudio.perceptual import VGG19PerceptualLoss


@dataclass
class PerceptualSplatfactoModelConfig(SplatfactoModelConfig):
    """Splatfacto configuration with the custom VGG-19 perceptual loss."""

    _target: type = field(default_factory=lambda: PerceptualSplatfactoModel)
    perceptual_loss_weight: float = 0.5
    """Perceptual-loss multiplier used by the reconstruction recipe."""
    perceptual_weights_path: Path = Path("models") / PERCEPTUAL_VGG19
    """Safetensors converted from the official MatConvNet VGG-19 model."""
    perceptual_compute_dtype: str = "float32"
    """VGG convolution dtype: float32 or bfloat16 with FP32 fallback on unsupported GPUs."""


class PerceptualSplatfactoModel(SplatfactoModel):
    """Nerfstudio Splatfacto with the custom pixel-plus-feature loss."""

    config: PerceptualSplatfactoModelConfig

    def populate_modules(self) -> None:
        super().populate_modules()
        if self.config.perceptual_loss_weight < 0:
            raise ValueError("perceptual_loss_weight must be non-negative.")
        weights_path = Path(self.config.perceptual_weights_path).expanduser()
        if self.config.perceptual_loss_weight > 0 and weights_path == Path("models") / PERCEPTUAL_VGG19:
            weights_path = ensure_perceptual_vgg19()
        self.perceptual_loss = (
            VGG19PerceptualLoss(
                weights_path,
                compute_dtype=self.config.perceptual_compute_dtype,
            )
            if self.config.perceptual_loss_weight > 0
            else None
        )

    def get_loss_dict(self, outputs, batch, metrics_dict=None):
        loss_dict = super().get_loss_dict(outputs, batch, metrics_dict)
        if not self.training or self.perceptual_loss is None:
            return loss_dict

        target = self.composite_with_background(self.get_gt_img(batch["image"]), outputs["background"])
        prediction = outputs["rgb"]
        if "mask" in batch:
            mask = self._downscale_if_required(batch["mask"]).to(self.device)
            target = target * mask
            prediction = prediction * mask
        target = target.permute(2, 0, 1).unsqueeze(0)
        prediction = prediction.permute(2, 0, 1).unsqueeze(0)
        loss_dict["perceptual_loss"] = self.config.perceptual_loss_weight * self.perceptual_loss(
            prediction,
            target,
        )
        return loss_dict


def splatfacto_perceptual_method() -> MethodSpecification:
    """Register the custom method without patching the Nerfstudio checkout."""

    # Start from the installed Nerfstudio version's own Splatfacto recipe so
    # optimizer defaults remain aligned with that installation.
    from nerfstudio.configs.method_configs import method_configs

    config = deepcopy(method_configs["splatfacto"])
    config.method_name = "splatfacto-perceptual"
    config.pipeline.model = PerceptualSplatfactoModelConfig()
    return MethodSpecification(
        config=config,
        description="Splatfacto with the custom VGG-19 perceptual reconstruction loss.",
    )
