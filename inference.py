"""Run 4DAnyone inference from a monocular video."""

from __future__ import annotations

import sys

from fdanyone.device import configure_inference_cuda_allocator
from fdanyone.errors import FourDAnyoneError


def inference(
    video_path: str,
    views_per_layer: int = 24,
    layer_pitches: list[int] = [15],  # noqa: B006 - normalized without mutation
    start_yaw: int = 0,
    yaw_span: int = 360,
    views_per_group: int | str = "auto",
    enable_rcp: bool = True,
    enable_tcr: bool = True,
    data_dir: str = "data",
    model_dir: str = "models",
    checkpoint_path: str | None = None,
    mhr70_regressor_path: str | None = None,
    gvhmr_root: str = "third_party/GVHMR",
    gpu_ids: list[int] | None = None,
    target_fps: str | int | float = "auto",
    start_time: float = 0.0,
    seed: int = 42,
) -> dict:
    """Generate synchronized target-view videos from one monocular video.

    Args:
        video_path: Input video; it must contain at least 121 usable frames.
        views_per_layer: Number of evenly spaced yaw views at each pitch. It
            must be divisible by 4 or 6.
        layer_pitches: Camera pitch for each layer in degrees, for example
            [-10,15,35]. Positive values place the camera above the subject;
            each value must be between -15 and 45.
        start_yaw: First yaw in every layer, in degrees; 0 faces the person.
        yaw_span: Angular range sampled by each layer, from 1 to 360 degrees.
            The end angle is excluded so a full ring never duplicates a view.
        views_per_group: Maximum target views generated together. auto chooses
            6 when possible and otherwise 4; a manual value must be 4 or 6 and
            divide views_per_layer.
        enable_rcp: Use proposal views before generating more than six targets.
            The proposal count follows views_per_group.
        enable_tcr: Shift view groups cyclically between denoising steps.
        data_dir: Root for reusable GVHMR motion and final 4DAnyone outputs.
        model_dir: Model root; missing public checkpoints download here.
        checkpoint_path: Local 4DAnyone checkpoint override.
        mhr70_regressor_path: Local SMPL-X-to-MHR70 regressor override.
        gvhmr_root: Path to the GVHMR source checkout.
        gpu_ids: GPU IDs used for parallel pose/VAE view stages and target
            denoising. Omit to use all visible GPUs.
        target_fps: auto preserves the input clock unless it divides evenly
            to 24, 25, or 30 FPS; a positive number requests an explicit FPS.
        start_time: Clip start time on the input timeline, in seconds.
        seed: Random seed shared by proposal and target generation.
    """

    # This must run before the first model/PyTorch import. It protects the
    # reusable 5--6 GiB DiT FFN allocation from allocator fragmentation.
    configure_inference_cuda_allocator()
    # Keep model imports out of module scope so ``--help`` stays lightweight.
    from fdanyone.pipeline import run_pipeline

    return run_pipeline(
        video_path=video_path,
        views_per_layer=views_per_layer,
        layer_pitches=layer_pitches,
        start_yaw=start_yaw,
        yaw_span=yaw_span,
        views_per_group=views_per_group,
        enable_rcp=enable_rcp,
        enable_tcr=enable_tcr,
        data_dir=data_dir,
        model_dir=model_dir,
        checkpoint_path=checkpoint_path,
        mhr70_regressor_path=mhr70_regressor_path,
        gvhmr_root=gvhmr_root,
        gpu_ids=gpu_ids,
        target_fps=target_fps,
        start_time=start_time,
        seed=seed,
    )


def main() -> None:
    """Bootstrap the CLI without importing Fire or PyTorch at module import."""

    configure_inference_cuda_allocator()
    from fire import Fire

    try:
        Fire(inference)
    except FourDAnyoneError as exc:
        message = " ".join(line.strip() for line in str(exc).splitlines())
        print(f"error: {message}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
