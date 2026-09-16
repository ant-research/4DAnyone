"""A synchronized body, source overlay and complete target-video scene."""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import CancelledError, ThreadPoolExecutor
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from fdanyone.config import FRAMING
from fdanyone.errors import FourDAnyoneError
from fdanyone.geometry.cameras import camera_grid, reference_intrinsics
from fdanyone.output_directory import read_output_metadata
from fdanyone.space import scene

_EXPORT_LOCK = threading.Lock()
RECORDING_VERSION = 17


@dataclass(frozen=True)
class Result:
    directory: Path
    metadata: dict
    cameras: tuple[dict, ...]
    videos: tuple[Path, ...]
    fps: Fraction
    frames: int


def _contained_file(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise FourDAnyoneError(f"Missing or external result file: {relative}")
    return path


def read_result(directory: str | Path) -> Result:
    root = Path(directory).expanduser().resolve()
    _contained_file(root, "metadata.json")
    metadata = read_output_metadata(root)
    try:
        rig = json.loads(_contained_file(root, "cameras.json").read_text())
        cameras = rig["cameras"]
        if rig.get("camera_model") != "OPENCV" or not isinstance(cameras, list) or not cameras:
            raise ValueError("Expected a nonempty OPENCV camera rig")
        if rig["world_frame"]["name"] != "canonical_human_world" or rig["camera_frame"]["name"] != "opencv_camera":
            raise ValueError("Unsupported camera coordinate system")
        if [camera["camera_id"] for camera in cameras] != list(range(len(cameras))):
            raise ValueError("Cameras must be ordered by camera ID")
        fps = Fraction(metadata["output"]["fps"])
        frames = int(metadata["output"]["frames_per_video"])
        if fps <= 0 or frames != 121 or metadata["output"]["target_views"] != len(cameras):
            raise ValueError("Output does not describe synchronized 121-frame videos")
        videos = []
        for camera in cameras:
            camera_id = camera["camera_id"]
            relative = f"videos/dense/{camera_id:02d}.mp4"
            if camera["video"] != relative:
                raise ValueError(f"Unexpected video path for camera {camera_id}")
            intrinsic = np.asarray(camera["K"], dtype=np.float64)
            transform = np.asarray(camera["camera_to_world"], dtype=np.float64)
            if (
                intrinsic.shape != (3, 3)
                or transform.shape != (4, 4)
                or not np.isfinite(intrinsic).all()
                or not np.isfinite(transform).all()
                or not np.allclose(transform[3], [0, 0, 0, 1])
            ):
                raise ValueError(f"Invalid calibration for camera {camera_id}")
            if min(camera["image_width"], camera["image_height"]) <= 0:
                raise ValueError("Invalid camera image dimensions")
            videos.append(_contained_file(root, relative))
    except (OSError, ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        raise FourDAnyoneError(f"Cannot open this 4DAnyone output: {exc}") from exc
    return Result(root, metadata, tuple(cameras), tuple(videos), fps, frames)


def _target_video(result: Result, camera_id: int, destination: Path, check_cancelled: Callable) -> tuple[int, int]:
    """Keep the generated H.264 bytes, including their native resolution and quality."""

    camera = result.cameras[camera_id]
    size = camera["image_width"], camera["image_height"]
    if destination.exists():
        return size
    temporary = destination.with_name(f".{destination.stem}-{uuid.uuid4().hex}.mp4")
    count = 0
    try:
        with av.open(str(result.videos[camera_id])) as source:
            source.streams.video[0].codec_context.thread_count = 2
            if source.streams.video[0].average_rate != result.fps:
                raise FourDAnyoneError(f"Camera {camera_id} video FPS does not match its metadata.")
            for count, frame in enumerate(source.decode(video=0), start=1):
                check_cancelled()
                if count > result.frames:
                    raise FourDAnyoneError(f"Camera {camera_id} has more than {result.frames} frames.")
                if (frame.width, frame.height) != (camera["image_width"], camera["image_height"]):
                    raise FourDAnyoneError(f"Camera {camera_id} video dimensions do not match its calibration.")
        if count != result.frames:
            raise FourDAnyoneError(f"Camera {camera_id} has {count} frames; expected {result.frames}.")
        check_cancelled()
        shutil.copyfile(result.videos[camera_id], temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return size


def _prepare_targets(result: Result, media: Path, check_cancelled: Callable) -> dict:
    stopped = threading.Event()

    def check():
        check_cancelled()
        if stopped.is_set():
            raise CancelledError

    def prepare(index):
        check()
        return _target_video(result, index, media / f"{index:02d}.mp4", check)

    with ThreadPoolExecutor(max_workers=min(4, len(result.videos)), thread_name_prefix="space-video") as pool:
        futures = [pool.submit(prepare, index) for index in range(len(result.videos))]
        try:
            return {index: future.result() for index, future in enumerate(futures)}
        finally:
            stopped.set()
            for future in futures:
                future.cancel()


def scene_info(recording: Path) -> dict:
    return json.loads(recording.with_suffix(".json").read_text())


def _identity(path: Path | None):
    if path is None or not path.is_file():
        return None
    stat = path.stat()
    return str(path.resolve()), stat.st_size, stat.st_mtime_ns


def _cache_key(identity) -> str:
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]


def _body_identity(motion_dir, model_dir, gvhmr_root):
    from fdanyone.assets import MHR70_REGRESSOR, SMPLX_MODEL

    if motion_dir is None:
        return None
    return [
        [_identity(motion_dir / name) for name in ("motion.json", "motion.safetensors")],
        [_identity(model_dir / name) for name in (MHR70_REGRESSOR, SMPLX_MODEL)] if model_dir else None,
        str(gvhmr_root.resolve()) if gvhmr_root else None,
    ]


def _cached_recording(destination: Path, *, require_body: bool) -> bool:
    try:
        # Failed body preparation must remain retryable, including after a
        # transient failure that did not change any of the input files.
        if not destination.is_file():
            return False
        info = scene_info(destination)
        return not require_body or info["body_frames"] > 0
    except (OSError, ValueError, KeyError):
        return False


def _result_context(result: Result) -> dict:
    framing = result.metadata.get("preprocessing", {}).get("framing", {})
    radius = framing.get("radius", FRAMING.reference_radius)
    height = framing.get("target_height", FRAMING.reference_target_height)
    first = result.cameras[0]
    transform = np.asarray(first["camera_to_world"])
    center = transform[:3, 3] + transform[:3, 2] * radius / np.linalg.norm(transform[[0, 2], 2])
    center[1] = 0
    return {
        "center": center.tolist(),
        "radius": radius,
        "target_height": height,
        "K": first["K"],
        "image_width": first["image_width"],
        "image_height": first["image_height"],
    }


def layout_cameras(context: dict, layout: dict) -> list[dict]:
    cameras = camera_grid(
        center=np.asarray(context["center"]),
        front_direction=np.array([0, 0, -1]),
        K=np.asarray(context["K"]),
        image_height=context["image_height"],
        image_width=context["image_width"],
        radius=context["radius"],
        target_height=context["target_height"],
        **layout,
    )
    return [
        {
            "camera_id": c.camera_id,
            "K": c.K,
            "camera_to_world": c.camera_to_world,
            "image_width": c.image_width,
            "image_height": c.image_height,
            "yaw": c.yaw_degrees,
            "pitch": c.pitch_degrees,
        }
        for c in cameras
    ]


def _save_recording(destination: Path, info: dict, log_scene) -> Path:
    import rerun as rr

    temporary = destination.with_name(f".{uuid.uuid4().hex}.rrd")
    recording = rr.RecordingStream(info["application_id"], recording_id=info["recording_id"])
    try:
        recording.save(str(temporary), default_blueprint=scene.blueprint(info["context"], info["target_count"]))
        recording.log("world", rr.ViewCoordinates.RIGHT_HAND_Y_UP, static=True)
        scene.log_stage(recording, info["context"])
        log_scene(recording)
        recording.flush()
        recording.disconnect()
        temporary.replace(destination)
        destination.with_suffix(".json").write_text(json.dumps(info) + "\n")
    finally:
        recording.disconnect()
        temporary.unlink(missing_ok=True)
    return destination


def _prepare_body(motion_dir, model_dir, gvhmr_root, cache_dir, check_cancelled):
    from fdanyone.space.body import load_body

    if motion_dir is None:
        return None, []
    if model_dir is None or gvhmr_root is None:
        return None, ["Set the model and GVHMR directories to show the recovered body."]
    try:
        return load_body(motion_dir, model_dir, gvhmr_root, cache_dir, check_cancelled), []
    except (FourDAnyoneError, OSError, ValueError) as exc:
        return None, [str(exc)]


def export_recording(
    result: Result,
    cache_dir: Path,
    *,
    source: Path | None = None,
    model_dir: Path | None = None,
    gvhmr_root: Path | None = None,
    check_cancelled: Callable = lambda: None,
) -> Path:
    from fdanyone.space.overlay import export_overlay
    from fdanyone.space.source import prepare_source

    body_identity = _body_identity(result.directory / "gvhmr", model_dir, gvhmr_root)
    identity = [
        RECORDING_VERSION,
        str(result.directory),
        result.metadata,
        result.cameras,
        [_identity(p) for p in result.videos],
        _identity(source),
        body_identity,
    ]
    key = _cache_key(identity)
    recording_id = uuid.uuid4().hex
    destination = cache_dir / f"{key}.rrd"
    with _EXPORT_LOCK:
        check_cancelled()
        if _cached_recording(destination, require_body=bool(model_dir and gvhmr_root)):
            return destination
        media = cache_dir / key
        media.mkdir(parents=True, exist_ok=True)
        sizes = _prepare_targets(result, media, check_cancelled)
        body, notes = _prepare_body(result.directory / "gvhmr", model_dir, gvhmr_root, cache_dir, check_cancelled)
        source_info = None
        if source is not None:
            indices = body["source_indices"] if body is not None else None
            source_info = prepare_source(
                source,
                cache_dir,
                fps=result.fps,
                indices=indices,
                start_time=result.metadata["input"].get("start_time_seconds", 0),
                check_cancelled=check_cancelled,
            )
        else:
            notes.append("Original Source Video Unavailable. Restore the source at its saved path.")
        info = {
            "application_id": f"4danyone_space_{recording_id}",
            "recording_id": recording_id,
            "context": _result_context(result),
            "target_count": len(result.cameras),
            "camera_count": len(result.cameras),
            "notes": notes,
            "source": str(source) if source else None,
            "body_frames": len(body["vertices"]) if body is not None else 0,
            "fps": float(result.fps),
            "frames": result.frames,
            "media": {
                "source": source_info,
                "targets": [
                    {"id": index, "path": str(media / f"{index:02d}.mp4"), "width": size[0], "height": size[1]}
                    for index, size in sizes.items()
                ],
                "overlay": export_overlay(body, cache_dir / "overlays" / _cache_key([1, body_identity]))
                if body is not None
                else None,
            },
        }

        def log_scene(recording):
            scene.log_cameras(
                recording,
                result.cameras,
                videos=[media / f"{index:02d}.mp4" for index in sizes],
                fps=result.fps,
                frames=result.frames,
            )
            if body is not None:
                scene.log_body(recording, body, result.fps, check_cancelled)
            check_cancelled()

        return _save_recording(destination, info, log_scene)


def export_input(
    source: Path | None,
    cache_dir: Path,
    layout: dict,
    *,
    start_time=0.0,
    target_fps="auto",
    motion_dir: Path | None = None,
    model_dir: Path | None = None,
    gvhmr_root: Path | None = None,
    check_cancelled: Callable = lambda: None,
) -> Path:
    from fdanyone.space.overlay import export_overlay
    from fdanyone.space.source import prepare_source
    from fdanyone.video import validate_clip_options

    rate = validate_clip_options(start_time=start_time, fps=None if str(target_fps).lower() == "auto" else target_fps)
    body_identity = _body_identity(motion_dir, model_dir, gvhmr_root)
    key = _cache_key(
        [RECORDING_VERSION, "input", _identity(source), float(start_time), str(rate), layout, body_identity]
    )
    destination = cache_dir / f"input-{key}.rrd"

    with _EXPORT_LOCK:
        check_cancelled()
        if _cached_recording(destination, require_body=bool(motion_dir and model_dir and gvhmr_root)):
            return destination
        cache_dir.mkdir(parents=True, exist_ok=True)
        body, notes = _prepare_body(motion_dir, model_dir, gvhmr_root, cache_dir, check_cancelled)
        source_info = (
            prepare_source(
                source,
                cache_dir,
                start_time=start_time,
                fps=rate,
                check_cancelled=check_cancelled,
                indices=body["source_indices"] if body is not None else None,
            )
            if source
            else None
        )
        width, height = (source_info["width"], source_info["height"]) if source_info else (360, 640)
        context = {
            "center": [0, 0, 0],
            "radius": FRAMING.reference_radius,
            "target_height": FRAMING.reference_target_height,
            "image_width": width,
            "image_height": height,
            "K": reference_intrinsics(height, width).tolist(),
        }
        cameras = layout_cameras(context, layout)
        recording_id = uuid.uuid4().hex
        info = {
            "application_id": f"4danyone_space_{recording_id}",
            "recording_id": recording_id,
            "context": context,
            "target_count": 0,
            "camera_count": len(cameras),
            "notes": notes,
            "body_frames": len(body["vertices"]) if body is not None else 0,
            "source": str(source) if source else None,
            "fps": float(Fraction(source_info["fps"])) if source_info else 25.0,
            "frames": source_info["frames"] if source_info else 0,
            "media": {
                "source": source_info,
                "targets": [],
                "overlay": export_overlay(body, cache_dir / "overlays" / _cache_key([1, body_identity]))
                if body is not None
                else None,
            },
        }

        def log_scene(recording):
            scene.log_cameras(recording, cameras)
            if source_info and body is None:
                scene.log_source_card(recording, context, Path(source_info["path"]), source_info)
            if body is not None:
                scene.log_body(recording, body, info["fps"], check_cancelled)

        return _save_recording(destination, info, log_scene)


def export_layout_update(info: dict, cache_dir: Path, layout: dict) -> tuple[Path, dict]:
    """Append a small camera update to the active store without reloading its videos."""

    import rerun as rr

    if info["target_count"]:
        raise FourDAnyoneError("Saved result cameras are read-only.")
    cameras = layout_cameras(info["context"], layout)
    destination = cache_dir / f"layout-{uuid.uuid4().hex}.rrd"
    cache_dir.mkdir(parents=True, exist_ok=True)
    recording = rr.RecordingStream(info["application_id"], recording_id=info["recording_id"])
    try:
        recording.save(str(destination))
        scene.log_cameras(recording, cameras)
        recording.flush()
    finally:
        recording.disconnect()
    return destination, {**info, "camera_count": len(cameras)}
