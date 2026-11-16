"""Periodic calibrated camera paths, sampled only at trained scene times."""

import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


def orbit(cameras, times, *, anchor=0, half=False):
    """Blend an ordered camera ring periodically, including across its seam."""
    count = len(cameras)
    if count < 4 or not 0 <= anchor < count:
        raise ValueError("Orbit requires at least four ordered cameras and a valid anchor")
    if half and (count < 8 or count % 4):
        raise ValueError("180-degree orbit needs at least eight ring cameras, divisible by four")
    poses = np.array([np.linalg.inv(c["w2c"]) for c in cameras])
    rotations = Rotation.from_matrix(poses[:, :3, :3]).as_quat()
    start, span = (anchor - count / 4, count / 2) if half else (anchor, count)
    records = []
    for u, time in zip(np.linspace(0, 1, len(times)), times, strict=True):
        value = start + u * span
        i, t = int(np.floor(value)) % count, value % 1
        weights = ((1 - t) ** 3 / 6, (3 * t**3 - 6 * t * t + 4) / 6, (-3 * t**3 + 3 * t * t + 3 * t + 1) / 6, t**3 / 6)
        q, center = np.zeros(4), np.zeros(3)
        for index, weight in zip((i - 1, i, i + 1, i + 2), weights, strict=True):
            index %= count
            part = rotations[index]
            q += weight * (part if np.dot(rotations[i], part) >= 0 else -part)
            center += weight * poses[index, :3, 3]
        pose = np.eye(4)
        pose[:3, :3], pose[:3, 3] = Rotation.from_quat(q).as_matrix(), center
        k = (1 - t) * np.array(cameras[i]["K"]) + t * np.array(cameras[(i + 1) % count]["K"])
        camera = dict(cameras[anchor], K=k.tolist(), w2c=np.linalg.inv(pose).tolist())
        records.append(dict(camera=camera, time=float(time)))
    return records


def trajectory(cameras, times, kind, fixed_time=None, anchor=0):
    times = np.asarray(times, dtype=np.float64)
    if times.ndim != 1 or not len(times) or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError("Training timestamps must be finite, increasing and nonempty")

    def nearest(value):
        if not np.isfinite(value) or not times[0] <= value <= times[-1]:
            raise ValueError("Trajectory sample time is outside the trained timeline")
        return float(times[np.abs(times - value).argmin()])

    if fixed_time is not None and kind not in ("orbit360", "orbit180"):
        raise ValueError("--time is supported only for orbit trajectories")
    if kind == "dataset":
        return [dict(camera=camera, time=float(t)) for camera in cameras for t in times]
    if kind not in ("orbit360", "orbit180"):
        records = json.loads(Path(kind).read_text())
        if not isinstance(records, list) or not records:
            raise ValueError("Trajectory must be a nonempty list of camera/time records")
        return [dict(record, time=nearest(record["time"])) for record in records]
    if not 0 <= anchor < len(cameras):
        raise ValueError("Invalid anchor camera index")
    centers = np.array([np.linalg.inv(c["w2c"])[:3, 3] for c in cameras])
    ring = np.flatnonzero(np.isclose(centers[:, 1], centers[anchor, 1], atol=1e-3))
    position = int(np.flatnonzero(ring == anchor)[0])
    sample_times = times if fixed_time is None else np.full(len(times), nearest(fixed_time))
    return orbit([cameras[i] for i in ring], sample_times, anchor=position, half=kind == "orbit180")
