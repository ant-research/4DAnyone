"""Export the recovered mesh in the source camera for a lightweight WebGL overlay."""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np

from fdanyone.skeleton.keypoints import BLUE, LINKS, VISIBLE_KEYPOINT_IDS, keypoint_color


def camera_points(points: np.ndarray, transforms: np.ndarray) -> np.ndarray:
    """Invert per-frame OpenCV camera-to-world poses without changing geometry."""
    return np.einsum("fvi,fij->fvj", points - transforms[:, None, :3, 3], transforms[:, :3, :3]).astype("<f4")


def export_overlay(body: dict, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in ("vertices", "faces", "keypoints"):
        destination = directory / f"{name}.bin"
        if not destination.is_file():
            array = (
                np.asarray(body[name], dtype="<u4")
                if name == "faces"
                else camera_points(body[name], body["source_camera_to_world"])
            )
            temporary = directory / f".{name}-{uuid.uuid4().hex}.bin"
            try:
                array.tofile(temporary)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
        paths[name] = str(destination)
    return {
        **paths,
        "vertex_count": int(body["vertices"].shape[1]),
        "keypoint_count": int(body["keypoints"].shape[1]),
        "frames": int(body["vertices"].shape[0]),
        "source_size": np.asarray(body["source_size"]).tolist(),
        "intrinsics": np.asarray(body["intrinsics"]).tolist(),
        "color": list(BLUE),
        "links": [[a, b, list(color), major] for _, a, b, color, major in LINKS],
        "joints": [[index, list(keypoint_color(index))] for index in sorted(VISIBLE_KEYPOINT_IDS)],
    }
