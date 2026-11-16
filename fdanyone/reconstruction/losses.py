"""Image, silhouette and optional frozen perceptual reconstruction losses."""

import torch
from torch.nn import functional as F


def composite(rgb, alpha, background):
    """RGB is already opacity-weighted. Background must retain the alpha gradient."""
    return rgb + (1 - alpha) * background


def ssim(x, y):
    coordinates = torch.arange(11, dtype=x.dtype, device=x.device) - 5
    kernel = torch.exp(-coordinates.square() / (2 * 1.5**2))
    kernel = (kernel / kernel.sum()).reshape(1, 1, 1, 11).expand(x.shape[1], 1, 1, 11)

    def blur(value):
        value = F.conv2d(value, kernel.transpose(-1, -2), padding=(5, 0), groups=x.shape[1])
        return F.conv2d(value, kernel, padding=(0, 5), groups=x.shape[1])

    mx, my = blur(x), blur(y)
    vx, vy, cov = blur(x * x) - mx * mx, blur(y * y) - my * my, blur(x * y) - mx * my
    return (
        ((2 * mx * my + 0.01**2) / (mx * mx + my * my + 0.01**2)) * ((2 * cov + 0.03**2) / (vx + vy + 0.03**2))
    ).mean()


class Objective:
    def __init__(
        self,
        device,
        *,
        background_color,
        l1_weight,
        mask_weight,
        perceptual_compute_dtype,
        perceptual_include_rgb,
        perceptual_start_step,
        perceptual_weight,
        perceptual_weights,
        seed,
        ssim_weight,
    ):
        self.l1_weight = l1_weight
        self.mask_weight = mask_weight
        self.perceptual_start_step = perceptual_start_step
        self.perceptual_weight = perceptual_weight
        self.ssim_weight = ssim_weight
        self.background_generator = (
            torch.Generator(device=device).manual_seed(seed) if background_color == "random" else None
        )
        self.perceptual = None
        if self.perceptual_weight:
            from fdanyone.nerfstudio.perceptual import VGG19PerceptualLoss

            self.perceptual = VGG19PerceptualLoss(
                perceptual_weights, perceptual_compute_dtype, include_rgb=perceptual_include_rgb
            ).to(device)

    def __call__(self, image, alpha, target, mask, step=0):
        if image.ndim == 3:
            image, alpha, target, mask = (t[None] for t in (image, alpha, target, mask))
        if self.background_generator is not None:
            background = torch.rand((len(image), 3, 1, 1), device=image.device, generator=self.background_generator)
            image, target = composite(image, alpha, background), composite(target, mask, background)
        terms = {"l1": (image - target).abs().mean(), "mask": (alpha - mask).square().mean()}
        terms["ssim"] = 1 - ssim(image, target)
        terms["perceptual"] = (
            self.perceptual(image, target)
            if self.perceptual and step >= self.perceptual_start_step
            else image.sum() * 0
        )
        loss = (
            terms["l1"] * self.l1_weight
            + terms["ssim"] * self.ssim_weight
            + terms["mask"] * self.mask_weight
            + terms["perceptual"] * self.perceptual_weight
        )
        return loss, terms
