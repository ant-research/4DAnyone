"""Canonical target-video paths shared by publication and result consumers."""

from __future__ import annotations

from pathlib import Path

from fdanyone.errors import FourDAnyoneError


def target_video_path(camera_id: int) -> Path:
    """Return the relative publication path for a target camera."""

    return Path("videos") / f"{camera_id:02d}.mp4"


def read_target_videos(root: Path, cameras: list[dict]) -> tuple[Path, ...]:
    """Read the canonical camera-indexed videos, contained within the result."""

    if not cameras or [camera.get("camera_id") for camera in cameras] != list(range(len(cameras))):
        raise FourDAnyoneError("Target cameras must be ordered by camera ID.")
    layout = tuple(target_video_path(index) for index in range(len(cameras)))
    if tuple(camera.get("video") for camera in cameras) != tuple(str(path) for path in layout):
        raise FourDAnyoneError("Camera video paths must use the videos/<camera_id>.mp4 layout.")

    root = root.resolve()
    paths = tuple(root / relative for relative in layout)
    for path in paths:
        if not path.is_file() or not path.resolve().is_relative_to(root):
            raise FourDAnyoneError(f"Missing or external result file: {path.relative_to(root)}")
    return paths
