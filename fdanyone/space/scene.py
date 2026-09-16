"""Rerun scene geometry and native-video logging; no task or cache ownership."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np

from fdanyone.errors import FourDAnyoneError
from fdanyone.skeleton.keypoints import BLUE, LINKS, VISIBLE_KEYPOINT_IDS, keypoint_color

CAMERA_PLANE_DISTANCE = 0.36


def log_video(recording, entity: str, video: Path, fps, frames: int) -> None:
    import rerun as rr

    asset = rr.AssetVideo(path=video)
    timestamps = asset.read_frame_timestamps_nanos()
    if len(timestamps) != frames:
        raise FourDAnyoneError(f"Video preview has {len(timestamps)} frames, expected {frames}.")
    recording.log(entity, asset, static=True)
    recording.send_columns(
        entity,
        indexes=[rr.TimeColumn("time", duration=np.arange(frames) / float(fps))],
        columns=rr.VideoFrameReference.columns_nanos(timestamps),
    )


def log_cameras(recording, cameras, *, videos=(), fps=None, frames=121) -> None:
    """An editable empty rig, or the fixed calibrated cameras of a result."""
    import rerun as rr

    if videos:
        for camera, video in zip(cameras, videos, strict=True):
            entity = f"world/cameras/{camera['camera_id']:02d}"
            transform = np.asarray(camera["camera_to_world"])
            recording.log(entity, rr.TransformAxes3D(0, show_frame=False), static=True)
            recording.log(entity, rr.Transform3D(mat3x3=transform[:3, :3], translation=transform[:3, 3]), static=True)
            recording.log(
                entity,
                rr.Pinhole(
                    image_from_camera=np.asarray(camera["K"]),
                    resolution=[camera["image_width"], camera["image_height"]],
                    camera_xyz=rr.ViewCoordinates.RDF,
                    image_plane_distance=CAMERA_PLANE_DISTANCE,
                    color=BLUE,
                    line_width=0,
                ),
                static=True,
            )
            log_video(recording, f"{entity}/image", video, fps, frames)
    _log_camera_frames(
        recording,
        [(camera, (camera["image_width"], camera["image_height"]), bool(videos)) for camera in cameras],
    )
    recording.log(
        "world/labels",
        rr.Points3D(
            [np.asarray(camera["camera_to_world"])[:3, 3] for camera in cameras],
            colors=BLUE,
            radii=0.018,
            labels=[f"{camera['camera_id']:02d}" for camera in cameras],
            show_labels=True,
        ),
        static=True,
    )


def blueprint(context: dict, count: int):
    import rerun.blueprint as rrb

    center = np.asarray(context["center"]) + [0, context["target_height"], 0]
    scene = rrb.Spatial3DView(
        origin="world",
        name="Scene",
        contents=[
            "world/body/**",
            "world/cameras/**",
            "world/camera_frames/**",
            "world/labels/**",
            "world/stage/**",
            "world/reference/**",
        ],
        eye_controls=rrb.EyeControls3D(
            position=center + np.array([0.85, 0.55, 1.1]) * context["radius"] * (1.25 if count >= 12 else 1),
            look_target=center,
            eye_up=[0, 1, 0],
        ),
    )
    return rrb.Blueprint(
        scene,
        rrb.TimePanel(timeline="time", play_state="playing", loop_mode="all", state="hidden"),
        rrb.BlueprintPanel(state="hidden"),
        rrb.SelectionPanel(state="hidden"),
    )


def _log_camera_frames(recording, frames: list) -> None:
    """Batch static rig geometry so repaint cost does not grow by entity per camera."""
    import rerun as rr

    entity = "world/camera_frames"
    # Only display geometry lives here, so clearing it never masks video frames.
    recording.log(entity, rr.Clear(recursive=True), static=True)
    lines, fills, bezels = [], [], []
    for camera, size, has_video in frames:
        width, height = size
        outline, bezel, faces = _rounded_frame(width, height, min(size) * 0.075, min(size) * 0.02)
        transform = np.asarray(camera["camera_to_world"])
        origin = transform[:3, 3]
        projection = np.linalg.inv(camera["K"]).T @ transform[:3, :3].T * CAMERA_PLANE_DISTANCE
        plane = np.column_stack([outline + [width / 2, height / 2], np.ones(len(outline))]) @ projection + origin
        corners = plane[np.arange(4) * (len(outline) // 4) + len(outline) // 8]
        lines.extend([np.vstack([plane, plane[0]]), *[np.stack([origin, corner]) for corner in corners]])
        if has_video:
            vertices = np.column_stack([bezel + [width / 2, height / 2], np.ones(len(bezel))]) @ projection + origin
            for direction in (-1, 1):
                bezels.append((vertices + transform[:3, 2] * (direction * 0.0005), faces))
        else:
            count = len(plane)
            fills.append(
                (
                    np.vstack([plane.mean(axis=0), plane]),
                    np.column_stack([np.zeros(count), np.arange(count) + 1, (np.arange(count) + 1) % count + 1]),
                )
            )
    recording.log(
        f"{entity}/lines",
        rr.LineStrips3D(lines, colors=BLUE, radii=rr.Radius.ui_points(0.75)),
        static=True,
    )
    for name, meshes, color in [("fill", fills, [*BLUE, 65]), ("bezel", bezels, BLUE)]:
        if not meshes:
            continue
        vertices, faces, offset = [], [], 0
        for points, triangles in meshes:
            vertices.append(points)
            faces.append(triangles + offset)
            offset += len(points)
        recording.log(
            f"{entity}/{name}",
            rr.Mesh3D(
                vertex_positions=np.concatenate(vertices),
                triangle_indices=np.concatenate(faces).astype(np.uint32),
                albedo_factor=color,
            ),
            static=True,
        )


def log_stage(recording, context: dict) -> None:
    """A thin disk matching the camera ring, just below the original ground grid."""
    import rerun as rr

    count = 128
    angles = np.arange(count) * (2 * np.pi / count)
    center = np.asarray(context["center"], dtype=np.float64) - [0, 0.005, 0]
    radius = context["radius"]
    rim = center + np.column_stack([np.cos(angles), np.zeros(count), np.sin(angles)]) * radius
    indices = np.arange(count)
    next_indices = (indices + 1) % count
    recording.log(
        "world/stage/top",
        rr.Mesh3D(
            vertex_positions=np.vstack([center, rim]),
            triangle_indices=np.column_stack([np.zeros(count), next_indices + 1, indices + 1]).astype(np.uint32),
            vertex_normals=np.tile([0, 1, 0], (count + 1, 1)),
            albedo_factor=[32, 34, 39],
        ),
        static=True,
    )
    recording.log(
        "world/stage/edge",
        rr.Mesh3D(
            vertex_positions=np.vstack([rim, rim - [0, 0.005, 0]]),
            triangle_indices=np.vstack(
                [
                    np.column_stack([indices, next_indices, next_indices + count]),
                    np.column_stack([indices, next_indices + count, indices + count]),
                ]
            ),
            albedo_factor=[22, 24, 28],
        ),
        static=True,
    )
    recording.log(
        "world/stage/rim",
        rr.LineStrips3D([np.vstack([rim, rim[0]])], radii=rr.Radius.ui_points(0.6), colors=[68, 72, 80]),
        static=True,
    )


def _rounded_outline(width: float, height: float, radius: float) -> np.ndarray:
    centers = [(width / 2 - radius, height / 2 - radius), (-width / 2 + radius, height / 2 - radius)]
    centers += [(-width / 2 + radius, -height / 2 + radius), (width / 2 - radius, -height / 2 + radius)]
    angles = np.linspace(0, np.pi / 2, 13)[None, :] + np.arange(4)[:, None] * (np.pi / 2)
    arcs = np.stack([np.cos(angles), np.sin(angles)], axis=-1)
    return (np.asarray(centers)[:, None, :] + radius * arcs).reshape(-1, 2)


def _rounded_frame(width: float, height: float, radius: float, border: float):
    inner = _rounded_outline(width, height, radius)
    # A tighter outer curve keeps the video's square corners under even a thin bezel.
    outer = _rounded_outline(width + border * 2, height + border * 2, min(radius + border, border * 3))
    count = len(inner)
    indices, next_indices = np.arange(count), (np.arange(count) + 1) % count
    faces = np.vstack(
        [
            np.column_stack([indices, next_indices, next_indices + count]),
            np.column_stack([indices, next_indices + count, indices + count]),
        ]
    )
    return outer, np.vstack([outer, inner]), faces


def log_source_card(recording, context: dict, video: Path, source_info: dict) -> None:
    """A rounded video screen: full brightness toward +Z and dimmed on the back."""
    import rerun as rr

    width, height = source_info["width"], source_info["height"]
    card_height = 2 * context["target_height"]
    card_width = card_height * width / height
    radius, border = min(card_width, card_height) * np.array([0.06, 0.012])
    center = np.asarray(context["center"]) + [0, card_height / 2 + border, 0]
    outer, bezel, faces = _rounded_frame(card_width, card_height, radius, border)
    count = len(outer)
    indices, next_indices = np.arange(count), (np.arange(count) + 1) % count
    frame = np.column_stack([bezel, np.zeros(count * 2)]) + center
    # One double-sided video needs one decoder. A back-facing translucent mesh
    # dims its reverse side; the bezels mask the rectangular video corners.
    recording.log(
        "world/reference/back_tint",
        rr.Mesh3D(
            vertex_positions=np.vstack([center, np.column_stack([outer, np.zeros(count)]) + center]) - [0, 0, 0.001],
            triangle_indices=np.column_stack([np.zeros(count), indices + 1, next_indices + 1]).astype(np.uint32),
            albedo_factor=[12, 14, 18, 178],
            face_rendering=rr.components.MeshFaceRendering.Back,
        ),
        static=True,
    )
    for side, direction in [("front", 1), ("back", -1)]:
        recording.log(
            f"world/reference/{side}_bezel",
            rr.Mesh3D(
                vertex_positions=frame + [0, 0, direction * 0.002], triangle_indices=faces, albedo_factor=[30, 33, 39]
            ),
            static=True,
        )
    entity = "world/reference/screen"
    recording.log(entity, rr.TransformAxes3D(0, show_frame=False), static=True)
    recording.log(
        entity,
        rr.Transform3D(mat3x3=np.diag([1, -1, -1]), translation=center + [0, 0, card_height]),
        static=True,
    )
    recording.log(
        entity,
        rr.Pinhole(
            focal_length=height,
            resolution=[width, height],
            camera_xyz=rr.ViewCoordinates.RDF,
            image_plane_distance=card_height,
            line_width=0,
        ),
        static=True,
    )
    log_video(recording, f"{entity}/video", video, Fraction(source_info["fps"]), source_info["frames"])


def log_body(recording, body: dict, fps, check_cancelled) -> None:
    import rerun as rr

    point_ids = sorted(VISIBLE_KEYPOINT_IDS)
    recording.log(
        "world/body/mesh",
        rr.Mesh3D.from_fields(triangle_indices=body["faces"], albedo_factor=[180, 180, 180, 75]),
        static=True,
    )
    recording.log(
        "world/body/skeleton",
        rr.LineStrips3D.from_fields(radii=0.008, colors=[color for _, _, _, color, _ in LINKS]),
        static=True,
    )
    recording.log(
        "world/body/joints",
        rr.Points3D.from_fields(radii=0.012, colors=[keypoint_color(i) for i in point_ids]),
        static=True,
    )
    for index, vertices in enumerate(body["vertices"]):
        check_cancelled()
        recording.set_time("time", duration=index / float(fps))
        keypoints = body["keypoints"][index]
        recording.log("world/body/mesh", rr.Mesh3D.from_fields(vertex_positions=vertices))
        recording.log(
            "world/body/skeleton", rr.LineStrips3D.from_fields(strips=[keypoints[[a, b]] for _, a, b, _, _ in LINKS])
        )
        recording.log("world/body/joints", rr.Points3D.from_fields(positions=keypoints[point_ids]))
