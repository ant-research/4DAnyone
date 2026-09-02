"""Top-level inference orchestration."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from fdanyone.assets import (
    CHECKPOINT,
    HF_REPO_ID,
    HF_REVISION,
    TURBO_LORA,
    TURBO_LORA_NAME,
    TURBO_LORA_SHA256,
    resolve_base_assets,
    resolve_checkpoint,
    resolve_foreground_model,
    resolve_regressor,
    resolve_turbo_lora,
)
from fdanyone.config import BASE24, INFERENCE, RANK64_DELTA4
from fdanyone.device import CUDA_ALLOCATOR_CONF, select_cuda_devices
from fdanyone.download import ensure_example_video, ensure_models, ensure_smplx
from fdanyone.errors import ConfigurationError
from fdanyone.io import AtomicResultDirectory, remove_tree, write_json
from fdanyone.motion.gvhmr import validate_gvhmr
from fdanyone.motion.result import MotionResult
from fdanyone.video import (
    decode_canonical_clip,
    validate_required_video_codecs,
    verify_lossless_video,
    write_gvhmr_video,
)
from fdanyone.views import ViewPlan, resolve_view_plan

LOGGER = logging.getLogger("fdanyone")


def _data_paths(data_dir: str, video_path: str) -> tuple[Path, Path, Path]:
    data_root = Path(data_dir).expanduser().resolve()
    run_name = Path(video_path).stem
    return (
        data_root,
        data_root / "gvhmr" / "results" / run_name,
        data_root / "fdanyone" / run_name,
    )


def _discard_scratch(path: Path) -> None:
    """Best-effort cleanup that can never invalidate a published result.

    Some network filesystems keep an open, hidden tombstone after a file is
    unlinked.  Such a tombstone may remain ``EBUSY`` until this process exits,
    so cleanup must not be part of the atomic publication transaction.
    """

    try:
        remove_tree(path)
    except OSError as exc:
        LOGGER.warning(
            "Could not remove temporary files at %s (%s). "
            "The result is unaffected; the hidden scratch directory can be removed after this process exits.",
            path,
            exc,
        )


def _worker_environment() -> dict[str, str]:
    """Give the short-lived GVHMR workers this checkout and stable CUDA flags."""

    environment = os.environ.copy()
    environment.update(
        {
            "TORCH_CUDNN_V8_API_DISABLED": "1",
            "CUDNN_FRONTEND_DISABLE": "1",
            "CUDNN_LOGINFO_DBG": "0",
            "CUDNN_LOGDEST_DBG": "stderr",
            "CUDA_DEVICE_MAX_CONNECTIONS": "1",
            "NVIDIA_TF32_OVERRIDE": "0",
        }
    )
    environment.pop("PYTHONHOME", None)
    # The 4 GiB split policy is specific to the long-lived DiT process. These
    # short-lived preprocessing workers use unrelated allocation shapes.
    environment.pop(CUDA_ALLOCATOR_CONF, None)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
    return environment


def _run_motion(
    *,
    working_video: Path,
    output_dir: Path,
    gvhmr_root: Path,
    device: str,
    worker_python: str,
    clip_metadata: Path,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    request_path = output_dir / ".motion-worker-request.json"
    result_dir = output_dir / "result"
    write_json(
        request_path,
        {
            "gvhmr_root": str(gvhmr_root),
            "working_video": str(working_video),
            "clip_metadata": str(clip_metadata),
            "output_dir": str(output_dir / "runtime"),
            "result_dir": str(result_dir),
            "device": device,
        },
    )
    try:
        subprocess.run(
            [worker_python, "-m", "fdanyone.motion.worker", str(request_path)],
            check=True,
            env=_worker_environment(),
        )
    finally:
        request_path.unlink(missing_ok=True)
    return MotionResult.load(result_dir)


def _build_conditioning(
    *,
    regressor: Path,
    foreground_model: Path,
    gvhmr_root: Path,
    output_dir: Path,
    device: str,
    worker_python: str,
    working_video: Path,
    clip_metadata: Path,
    motion_result_dir: Path,
    view_plan: ViewPlan,
):
    from fdanyone.skeleton.pipeline import Conditioning

    request_path = output_dir.parent / ".skeleton-worker-request.json"
    write_json(
        request_path,
        {
            "working_video": str(working_video),
            "clip_metadata": str(clip_metadata),
            "motion_result_dir": str(motion_result_dir),
            "regressor_path": str(regressor),
            "foreground_model_path": str(foreground_model),
            "gvhmr_root": str(gvhmr_root),
            "output_dir": str(output_dir),
            "device": device,
            "view_plan": view_plan.to_dict(),
        },
    )
    try:
        subprocess.run(
            [
                worker_python,
                "-m",
                "fdanyone.skeleton.worker",
                str(request_path),
            ],
            check=True,
            env=_worker_environment(),
        )
    finally:
        request_path.unlink(missing_ok=True)
    return Conditioning.load(output_dir)


def run_pipeline(
    *,
    video_path: str,
    data_dir: str,
    model_dir: str,
    checkpoint_path: str | None,
    enable_turbo: bool,
    mhr70_regressor_path: str | None,
    gvhmr_root: str,
    gpu_ids: list[int] | None,
    start_time: float,
    target_fps: str | int | float,
    seed: int,
    views_per_layer: int,
    layer_pitches: list[int],
    start_yaw: int,
    yaw_span: int,
    views_per_group: int | str,
    enable_rcp: bool,
    enable_tcr: bool,
) -> dict:
    """Execute inference and publish reusable GVHMR plus 4DAnyone results."""

    pipeline_started = time.monotonic()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    if seed < 0:
        raise ConfigurationError(f"seed must be non-negative, got {seed}.")
    if not isinstance(enable_turbo, bool):
        raise ConfigurationError(f"enable_turbo must be True or False, got {enable_turbo!r}.")
    denoising_profile = RANK64_DELTA4 if enable_turbo else BASE24
    view_plan = resolve_view_plan(
        views_per_layer=views_per_layer,
        layer_pitches=layer_pitches,
        start_yaw=start_yaw,
        yaw_span=yaw_span,
        views_per_group=views_per_group,
        enable_rcp=enable_rcp,
        enable_tcr=enable_tcr,
    )
    data_root, motion_dir, result_dir = _data_paths(data_dir, video_path)
    run_name = Path(video_path).stem
    atomic = AtomicResultDirectory(result_dir)
    # Fail before asset resolution or video decode; the context manager
    # checks again later in case another process creates the path.
    if os.path.lexists(atomic.destination):
        raise ConfigurationError(
            f"4DAnyone result already exists: {atomic.destination}. Choose a new --data_dir or input filename."
        )
    validate_required_video_codecs()
    devices = select_cuda_devices(gpu_ids)
    device = devices[0]

    ensure_example_video(video_path)
    # Resolve the licensed body model before starting the much larger public
    # model download. Interactive use continues automatically after setup;
    # background jobs receive an actionable error instead of hanging.
    ensure_smplx(model_dir, gvhmr_root)
    ensure_models(model_dir, gvhmr_root)
    turbo_lora = resolve_turbo_lora(model_dir) if enable_turbo else None
    gvhmr_root, gvhmr_revision = validate_gvhmr(gvhmr_root)
    worker_python = os.path.abspath(sys.executable)

    regressor = resolve_regressor(mhr70_regressor_path, model_dir=model_dir)
    foreground_model = resolve_foreground_model(model_dir)
    canonical_fps = None if str(target_fps).lower() == "auto" else target_fps
    clip = decode_canonical_clip(
        video_path,
        num_frames=INFERENCE.num_frames,
        start_time=start_time,
        fps=canonical_fps,
    )
    data_root.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=f".{run_name}.scratch-", dir=data_root))
    try:
        clip_metadata = scratch / "canonical_clip.json"
        clip.write_metadata(clip_metadata)
        working_video = write_gvhmr_video(clip, scratch / "canonical_clip.mp4")

        if os.path.lexists(motion_dir):
            if motion_dir.is_symlink() or not motion_dir.is_dir():
                raise ConfigurationError(f"GVHMR result path is not a regular directory: {motion_dir}")
            motion = MotionResult.load(motion_dir)
            if motion.gvhmr_revision != gvhmr_revision:
                raise ConfigurationError(
                    f"Existing GVHMR result at {motion_dir} was produced by "
                    f"GVHMR@{motion.gvhmr_revision}, not GVHMR@{gvhmr_revision}."
                )
            motion.validate_against_clip(clip)
            LOGGER.info("Reusing validated GVHMR result at %s", motion_dir)
        else:
            with AtomicResultDirectory(motion_dir) as motion_work:
                motion = _run_motion(
                    working_video=working_video,
                    output_dir=scratch / "gvhmr",
                    gvhmr_root=gvhmr_root,
                    device=device,
                    worker_python=worker_python,
                    clip_metadata=clip_metadata,
                )
                motion.validate_against_clip(clip)
                motion.save(motion_work)

        checkpoint = resolve_checkpoint(checkpoint_path, model_dir=model_dir)
        base_assets = resolve_base_assets(model_dir)
        # Record the published identity only for the published checkpoint; an
        # explicit override must not claim the frozen Hugging Face coordinates.
        if checkpoint_path is None:
            model_identity = {"checkpoint": CHECKPOINT, "repo_id": HF_REPO_ID, "revision": HF_REVISION}
        else:
            model_identity = {"checkpoint": checkpoint.name, "source": "local_override"}
        if turbo_lora is not None:
            model_identity["turbo_lora"] = {
                "name": TURBO_LORA_NAME,
                "file": TURBO_LORA,
                "sha256": TURBO_LORA_SHA256,
            }

        with atomic as work:
            # Heavy rendering and generation are imported only after the motion
            # contract has been materialized, keeping CLI/help and CPU tests light.
            from fdanyone.model.inference import generate_views
            from fdanyone.output import export_result

            conditioning = _build_conditioning(
                regressor=regressor,
                foreground_model=foreground_model,
                gvhmr_root=gvhmr_root,
                output_dir=scratch / "conditioning",
                device=device,
                worker_python=worker_python,
                working_video=working_video,
                clip_metadata=clip_metadata,
                motion_result_dir=motion_dir,
                view_plan=view_plan,
            )
            if conditioning.num_frames != len(clip.frames) or (
                conditioning.fps_num,
                conditioning.fps_den,
            ) != (
                clip.fps_num,
                clip.fps_den,
            ):
                raise ConfigurationError("Skeleton conditioning does not match the canonical clip timeline.")
            # Re-decode the worker-produced source before it becomes a model tensor.
            verify_lossless_video(clip, conditioning.source_video)
            generated = generate_views(
                clip=clip,
                conditioning=conditioning,
                checkpoint_path=checkpoint,
                turbo_lora_path=turbo_lora,
                denoising_profile=denoising_profile,
                assets=base_assets,
                output_dir=scratch / "generation",
                devices=devices,
                seed=seed,
            )
            summary = export_result(
                clip=clip,
                conditioning=conditioning,
                generated=generated,
                destination=work,
                motion=motion,
                model_identity=model_identity,
                pipeline_started=pipeline_started,
            )
    finally:
        _discard_scratch(scratch)
    summary["result_dir"] = str(result_dir)
    summary["motion_dir"] = str(motion_dir)
    return summary
