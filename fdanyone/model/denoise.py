"""Shared denoising math for RCP, single-GPU, and multi-GPU execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from torch import Tensor

    from fdanyone.model.loader import Denoiser


def denoise_group(
    denoiser: Denoiser,
    latents: Tensor,
    source: Tensor,
    context: Tensor,
    pose_features: Tensor,
    null_pose_feature: Tensor,
    step_index: int,
) -> Tensor:
    """Advance one camera group by one scheduler step."""

    import torch

    timestep = denoiser.scheduler.timesteps[step_index]
    batched_timestep = timestep.unsqueeze(0).to(dtype=denoiser.dtype, device=latents.device)
    batched_timestep = torch.cat([batched_timestep] * latents.shape[0], dim=0)
    prediction = denoiser.model(
        x=latents,
        x_src=source,
        timestep=batched_timestep,
        pose_features=pose_features,
        null_pose_feature=null_pose_feature,
        context=context,
    )
    return denoiser.scheduler.step(prediction, timestep, latents)
