"""World-unit OpenCV cameras for a browser orbit controller."""

import math

import numpy as np


def vector(value):
    value = np.asarray(value, dtype=np.float64)
    if value.shape != (3,) or not np.isfinite(value).all() or np.abs(value).max() > 1e6:
        raise ValueError("Invalid camera vector")
    return value


def normalize(value):
    length = np.linalg.norm(value)
    if length < 1e-8:
        raise ValueError("Degenerate camera")
    return value / length


def orbit_camera(pose, width, height):
    position, target, up = (vector(pose[key]) for key in ("position", "target", "up"))
    forward = normalize(target - position)
    right = normalize(np.cross(forward, normalize(up)))
    down = np.cross(forward, right)
    rotation = np.stack((right, down, forward))
    view = np.eye(4)
    view[:3, :3], view[:3, 3] = rotation, -rotation @ position
    fov = float(pose["fov"])
    if not math.isfinite(fov) or not 10 <= fov <= 100:
        raise ValueError("Field of view must be between 10 and 100 degrees")
    focal = height / (2 * math.tan(math.radians(fov) / 2))
    return dict(
        K=[[focal, 0, width / 2], [0, focal, height / 2], [0, 0, 1]],
        w2c=view.tolist(),
        width=width,
        height=height,
    )


def world_up(cameras):
    """Gravity up for a calibrated rig: the mean image-up of its cameras.

    Rig cameras share an elevation around the subject, so their pitch cancels;
    a single camera's image-up leans toward its viewing direction.
    """
    poses = np.linalg.inv(np.asarray([camera["w2c"] for camera in cameras]))
    up = -poses[:, :3, 1].mean(0)
    if np.linalg.norm(up) < 1e-6:
        up = -poses[0, :3, 1]
    return normalize(up)


def initial_pose(cameras):
    poses = np.linalg.inv(np.asarray([camera["w2c"] for camera in cameras]))
    positions, directions = poses[:, :3, 3], poses[:, :3, 2]
    # Least-squares intersection of the calibrated optical axes, in world units.
    projections = np.eye(3)[None] - directions[:, :, None] * directions[:, None, :]
    target = np.linalg.lstsq(projections.sum(0), (projections @ positions[..., None]).sum(0)[:, 0], rcond=None)[0]
    first = cameras[0]
    # Preserve camera 0's optical axis exactly; the fit only estimates orbit distance.
    distance = float(np.dot(target - positions[0], directions[0]))
    if not np.isfinite(distance) or distance < 1e-5:
        distance = max(float(np.median(np.linalg.norm(positions - target, axis=1))), 1.0)
    target = positions[0] + directions[0] * distance
    # Orbit about gravity so dragging keeps the ground level. A camera looking
    # (almost) straight along it would be degenerate; keep its own image-up.
    up = world_up(cameras)
    if abs(np.dot(directions[0], up)) > 0.995:
        up = normalize(-poses[0, :3, 1])
    fov = np.clip(math.degrees(2 * math.atan(first["height"] / (2 * first["K"][1][1]))), 10, 100)
    return dict(position=positions[0].tolist(), target=target.tolist(), up=up.tolist(), fov=float(fov))
