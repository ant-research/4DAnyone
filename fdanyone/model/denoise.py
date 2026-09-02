"""Request-scoped denoising for RCP, single-GPU, and distributed execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType

    from torch import Tensor

    from fdanyone.model.loader import Denoiser
    from fdanyone.vendor.diffsynth.models.wan_video_dit import DiTRequestContext


CameraGroup = tuple[int, ...]


class DenoisingRequest:
    """Own all DiT state reusable within one denoising stage."""

    def __init__(
        self,
        denoiser: Denoiser,
        *,
        source: Tensor,
        context: Tensor,
        null_pose_feature: Tensor,
        target_views: int,
        stage: str,
    ) -> None:
        if not stage:
            raise ValueError("A denoising request requires a stage name.")
        self._denoiser = denoiser
        self._stage = stage
        self._model_context: DiTRequestContext | None = denoiser.model.prepare_request(
            x_src=source,
            context=context,
            null_pose_feature=null_pose_feature,
            target_views=target_views,
        )
        self._step_calls = 0
        self._model_calls = 0

    @property
    def retained_bytes(self) -> int:
        return self._require_context().retained_bytes

    def _require_context(self) -> DiTRequestContext:
        if self._model_context is None:
            raise RuntimeError("The denoising request is closed.")
        return self._model_context

    def step(
        self,
        latents: Tensor,
        pose_features: Tensor,
        step_index: int,
        group: CameraGroup,
    ) -> Tensor:
        """Advance one ordered camera group by one scheduler step."""

        if len(group) != latents.shape[0]:
            raise ValueError(f"Camera group has {len(group)} views, but the latent batch has {latents.shape[0]}.")
        timestep = self._denoiser.scheduler.timesteps[step_index]
        batched_timestep = (
            timestep.reshape(1)
            .to(dtype=self._denoiser.dtype, device=latents.device)
            .expand(latents.shape[0])
            .contiguous()
        )

        prediction = self._denoiser.model(
            x=latents,
            timestep=batched_timestep,
            pose_features=pose_features,
            request=self._require_context(),
        )
        self._model_calls += 1
        updated = self._denoiser.scheduler.step(prediction, timestep, latents)
        self._step_calls += 1
        return updated

    def report(self) -> dict[str, object]:
        context = self._require_context()
        return {
            "stage": self._stage,
            "policy": "exact-eager",
            "exact": {
                "request_context": True,
                "request_preparations": 1,
                "step_calls": self._step_calls,
                "model_calls": self._model_calls,
                "cross_kv_blocks": len(context.cross_attention),
                "cross_kv_projections": len(context.cross_attention),
                "cross_kv_uses": self._model_calls * len(context.cross_attention),
                "cross_kv_reuses": max(self._model_calls - 1, 0) * len(context.cross_attention),
                "target_views": context.target_views,
                "packed_views": context.packed_views,
                "grid_size": list(context.grid_size),
                "retained_bytes": context.retained_bytes,
            },
        }

    def close(self) -> None:
        """Release request-owned device tensors before the model can move."""

        self._model_context = None

    def __enter__(self) -> DenoisingRequest:
        self._require_context()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
