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
from fdanyone.io import remove_tree, resolve_output_path, write_json
from fdanyone.motion.gvhmr import validate_gvhmr
from fdanyone.motion.result import MotionResult
from fdanyone.output_directory import OutputDirectory
from fdanyone.run_request import save_run_request
from fdanyone.video import (
    decode_canonical_clip,
    validate_clip_options,
    validate_required_video_codecs,
    verify_lossless_video,
    write_gvhmr_video,
)
from fdanyone.views import ViewPlan, resolve_view_plan

LOGGER = logging.getLogger("fdanyone")
PROGRESS = logging.getLogger("fdanyone.progress")
PROGRESS.addHandler(logging.NullHandler())
PROGRESS.propagate = False


def _resolve_output_dir(output_dir: str | None, video_path: str) -> Path:
    """Resolve the output directory without following its final path component."""

    target = Path("data/fdanyone") / Path(video_path).stem if output_dir is None else Path(output_dir)
    return resolve_output_path(target)


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
    working_video: Path,
    clip_metadata: Path,
    motion_result_dir: Path,
    view_plan: ViewPlan,
    output_dir: Path,
    regressor: Path,
    foreground_model: Path,
    gvhmr_root: Path,
    device: str,
    worker_python: str,
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
    output_dir: str | None,
    model_dir: str,
    checkpoint_path: str | None,
    mhr70_regressor_path: str | None,
    gvhmr_root: str,
    gpu_ids: list[int] | None,
    attention_backend: str,
    start_time: float,
    target_fps: str | int | float,
    seed: int,
    views_per_layer: int,
    layer_pitches: list[int],
    start_yaw: int,
    yaw_span: int,
    enable_rcp: bool,
    enable_tcr: bool,
    enable_turbo: bool,
) -> dict:
    """Execute inference for one clip, retaining reusable motion."""

    request_options = locals().copy()
    pipeline_started = time.monotonic()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    PROGRESS.info("Checking input and settings", extra={"fraction": 0.02})
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
        enable_rcp=enable_rcp,
        enable_tcr=enable_tcr,
    )
    canonical_fps = validate_clip_options(
        start_time=start_time,
        fps=None if str(target_fps).lower() == "auto" else target_fps,
    )
    checkpoint = resolve_checkpoint(checkpoint_path, model_dir=model_dir) if checkpoint_path is not None else None
    destination = _resolve_output_dir(output_dir, video_path)
    clip_name = Path(video_path).stem
    output = OutputDirectory(destination)
    # Check before downloads and decoding, then again when locking the output.
    output.validate_available()
    validate_required_video_codecs()
    devices = select_cuda_devices(gpu_ids)
    device = devices[0]

    from fdanyone.vendor.diffsynth.models.wan_video_dit import get_attention_backend

    # Resolve once, before downloading assets or preparing conditioning. Every
    # DiT, including spawned replicas, receives this concrete backend.
    attention_backend = get_attention_backend(attention_backend)
    LOGGER.info("Using attention backend: %s", attention_backend)

    PROGRESS.info("Preparing model assets", extra={"fraction": 0.05})
    ensure_example_video(video_path)
    # Resolve the licensed body model before starting the much larger public
    # model download. Interactive use continues automatically after setup;
    # background jobs receive an actionable error instead of hanging.
    ensure_smplx(model_dir, gvhmr_root)
    ensure_models(model_dir, gvhmr_root)
    turbo_lora = resolve_turbo_lora(model_dir) if enable_turbo else None
    gvhmr_root, gvhmr_revision = validate_gvhmr(gvhmr_root)
    worker_python = os.path.abspath(sys.executable)

    if checkpoint is None:
        checkpoint = resolve_checkpoint(model_dir=model_dir)
    base_assets = resolve_base_assets(model_dir)
    regressor = resolve_regressor(mhr70_regressor_path, model_dir=model_dir)
    foreground_model = resolve_foreground_model(model_dir)
    PROGRESS.info("Preparing the 121-frame clip", extra={"fraction": 0.10})
    clip = decode_canonical_clip(
        video_path,
        num_frames=INFERENCE.num_frames,
        start_time=start_time,
        fps=canonical_fps,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=f".{clip_name}.scratch-", dir=destination.parent))
    try:
        clip_metadata = scratch / "canonical_clip.json"
        clip.write_metadata(clip_metadata)
        working_video = write_gvhmr_video(clip, scratch / "canonical_clip.mp4")

        with output.stage() as work:
            PROGRESS.info("Recovering human motion with GVHMR", extra={"fraction": 0.15})
            if output.motion_dir.exists():
                LOGGER.info("Reusing GVHMR motion from %s", output.motion_dir)
                motion = MotionResult.load(output.motion_dir)
            else:
                save_run_request(destination, request_options)
                motion = _run_motion(
                    working_video=working_video,
                    output_dir=scratch / "gvhmr",
                    gvhmr_root=gvhmr_root,
                    device=device,
                    worker_python=worker_python,
                    clip_metadata=clip_metadata,
                )
            if motion.gvhmr_revision != gvhmr_revision:
                raise ConfigurationError(
                    f"GVHMR motion has revision {motion.gvhmr_revision}, expected {gvhmr_revision}. "
                    "Choose a new --output_dir to recover motion with the current GVHMR version."
                )
            motion.validate_against_clip(clip)
            if output.motion_dir.exists():
                save_run_request(destination, request_options)
            else:
                output.save_motion(motion)

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

            # Heavy rendering and generation are imported only after the motion
            # contract has been materialized, keeping CLI/help and CPU tests light.
            from fdanyone.model.inference import generate_views
            from fdanyone.output_writer import write_output

            PROGRESS.info("Building foreground masks and skeletons", extra={"fraction": 0.30})
            conditioning = _build_conditioning(
                working_video=working_video,
                clip_metadata=clip_metadata,
                motion_result_dir=output.motion_dir,
                view_plan=view_plan,
                output_dir=scratch / "conditioning",
                regressor=regressor,
                foreground_model=foreground_model,
                gvhmr_root=gvhmr_root,
                device=device,
                worker_python=worker_python,
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
            PROGRESS.info("Generating target-view videos", extra={"fraction": 0.45})
            generated = generate_views(
                clip=clip,
                conditioning=conditioning,
                checkpoint_path=checkpoint,
                turbo_lora_path=turbo_lora,
                denoising_profile=denoising_profile,
                attention_backend=attention_backend,
                assets=base_assets,
                output_dir=scratch / "generation",
                devices=devices,
                seed=seed,
            )
            PROGRESS.info("Saving and validating generated videos", extra={"fraction": 0.92})
            summary = write_output(
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
    summary["output_dir"] = str(destination)
    PROGRESS.info("Inference complete", extra={"fraction": 1.0})
    return summary
