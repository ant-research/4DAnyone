"""Shared denoising math for RCP, single-GPU, and multi-GPU execution."""

from __future__ import annotations


def denoise_group(pipe, latents, source, context, skeletons, step_index: int):
    """Advance one camera group by one scheduler step."""

    import torch

    timestep = pipe.scheduler.timesteps[step_index]
    batched_timestep = timestep.unsqueeze(0).to(dtype=pipe.torch_dtype, device=latents.device)
    batched_timestep = torch.cat([batched_timestep] * latents.shape[0], dim=0)
    prediction = pipe.dit(
        x=latents,
        x_src=source,
        timestep=batched_timestep,
        skeletons=skeletons,
        context=context,
        **pipe.prepare_extra_input(latents),
    )
    return pipe.scheduler.step(prediction, timestep, latents)
