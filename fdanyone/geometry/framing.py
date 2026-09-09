"""Source-aware static-camera framing for the canonical camera ring."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

import cv2
import numpy as np

from fdanyone.config import FRAMING, FramingConfig
from fdanyone.geometry.cameras import Camera

FULL_BODY_BOTTOM = 0.82
CLOSE_UP_BOTTOM = 0.35
HALF_BODY_BOTTOM = 0.42
_ANATOMY_COORDS = (0.0, 0.18, 0.45, 0.72, 0.94, 1.0)
_FINGER_TOKENS = ("thumb", "index", "middle", "ring", "pinky")


@dataclass(frozen=True)
class InputFraming:
    label: str
    visible_body_bottom: float
    visible_body_bottom_p50: float
    visible_body_bottom_p80: float
    visible_height_ratio: float
    wrist_out_ratio_x: float
    wrist_out_ratio_y: float
    valid_frame_ratio: float
    torso_valid_ratio: float
    projection_alignment_error_ratio: float | None
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "fmask_used": True}


@dataclass(frozen=True)
class AdaptiveThresholds:
    closeup_strength: float
    height_target_ratio: float
    height_percentile: float
    width_target_ratio: float
    width_percentile: float


@dataclass(frozen=True)
class RadiusSolve:
    radius: float
    height_ratio: float
    width_ratio: float
    bound: str | None
    limiting_constraint: str


@dataclass(frozen=True)
class FocalSolve:
    focal_normalized: float
    height_ratio: float
    width_ratio: float
    bound: str | None
    limiting_constraint: str


@dataclass(frozen=True)
class ClipFraming:
    radius: float
    target_height: float
    focal_normalized: float
    input: InputFraming
    input_applied: bool
    radius_solve: RadiusSolve
    adaptive_thresholds: AdaptiveThresholds | None = None
    focal_solve: FocalSolve | None = None
    cutoff_ratio: float | None = None
    target_bound: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "method": "sequence_input_profile_static_radius_target_focal",
            "radius": self.radius,
            "target_height": self.target_height,
            "focal_normalized": self.focal_normalized,
            "input_framing_applied": self.input_applied,
            "input_framing": self.input.to_dict(),
            "adaptive_thresholds": (None if self.adaptive_thresholds is None else asdict(self.adaptive_thresholds)),
            "radius_solver": asdict(self.radius_solve),
            "focal_solver": None if self.focal_solve is None else asdict(self.focal_solve),
            "cutoff_ratio": self.cutoff_ratio,
            "target_bound": self.target_bound,
        }


def _name_index(names: Sequence[str]) -> dict[str, int]:
    normalized = [str(name).strip().lower().replace("_", "-") for name in names]
    mapping = dict(zip(normalized, range(len(normalized)), strict=True))
    if len(mapping) != len(normalized):
        raise ValueError("Keypoint names must be unique after normalization.")
    return mapping


def _required_indices(names: Sequence[str]) -> dict[str, int]:
    required = ["nose", "left-eye", "right-eye", "left-ear", "right-ear", "neck"]
    for side in ("left", "right"):
        required.extend(
            f"{side}-{part}"
            for part in (
                "shoulder",
                "hip",
                "knee",
                "ankle",
                "big-toe-tip",
                "small-toe-tip",
                "heel",
            )
        )
    mapping = _name_index(names)
    missing = [name for name in required if name not in mapping]
    if missing:
        raise ValueError(f"Missing framing keypoints: {missing}.")
    return {name: mapping[name] for name in required}


def _sample_path(anchors: Sequence[np.ndarray], samples_per_segment: int) -> tuple[np.ndarray, np.ndarray]:
    point_chunks: list[np.ndarray] = []
    coordinate_chunks: list[np.ndarray] = []
    for index, (start, end) in enumerate(zip(anchors, anchors[1:], strict=False)):
        endpoint = index == len(anchors) - 2
        weights = np.linspace(
            0.0,
            1.0,
            samples_per_segment + int(endpoint),
            endpoint=endpoint,
            dtype=np.float64,
        )
        point_chunks.append(start[:, None] * (1.0 - weights[None, :, None]) + end[:, None] * weights[None, :, None])
        coordinate_chunks.append(_ANATOMY_COORDS[index] * (1.0 - weights) + _ANATOMY_COORDS[index + 1] * weights)
    return np.concatenate(point_chunks, axis=1), np.concatenate(coordinate_chunks)


def anatomy_samples(
    keypoints: np.ndarray,
    names: Sequence[str],
    samples_per_segment: int = 8,
) -> tuple[np.ndarray, np.ndarray]:
    points = np.asarray(keypoints, dtype=np.float64)
    if points.ndim != 3 or points.shape[1:] != (len(names), 3) or not np.isfinite(points).all():
        raise ValueError(f"Expected finite keypoints [frames,{len(names)},3], got {points.shape}.")
    if samples_per_segment < 2:
        raise ValueError("samples_per_segment must be at least two.")
    ids = _required_indices(names)
    face = np.mean(
        points[:, [ids[name] for name in ("nose", "left-eye", "right-eye", "left-ear", "right-ear")]], axis=1
    )
    head_top = face + 0.65 * (face - points[:, ids["neck"]])
    paths: list[np.ndarray] = []
    coordinates: list[np.ndarray] = []
    for side in ("left", "right"):
        foot = np.mean(
            points[:, [ids[f"{side}-{part}"] for part in ("big-toe-tip", "small-toe-tip", "heel")]],
            axis=1,
        )
        path, path_coordinates = _sample_path(
            [
                head_top,
                points[:, ids[f"{side}-shoulder"]],
                points[:, ids[f"{side}-hip"]],
                points[:, ids[f"{side}-knee"]],
                points[:, ids[f"{side}-ankle"]],
                foot,
            ],
            samples_per_segment,
        )
        paths.append(path)
        coordinates.append(path_coordinates)
    return np.concatenate(paths, axis=1), np.concatenate(coordinates)


def project_incam(points: np.ndarray, intrinsics: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    points = np.asarray(points, dtype=np.float64)
    cameras = np.asarray(intrinsics, dtype=np.float64)
    if points.ndim != 3 or points.shape[-1] != 3:
        raise ValueError(f"Expected points [frames,keypoints,3], got {points.shape}.")
    if cameras.shape == (3, 3):
        cameras = np.broadcast_to(cameras, (points.shape[0], 3, 3))
    if cameras.shape == (1, 3, 3):
        cameras = np.broadcast_to(cameras, (points.shape[0], 3, 3))
    if cameras.shape != (points.shape[0], 3, 3):
        raise ValueError(f"Expected intrinsics [{points.shape[0]},3,3], got {cameras.shape}.")
    if not np.isfinite(points).all() or not np.isfinite(cameras).all():
        raise ValueError("Projection inputs must be finite.")
    homogeneous = np.einsum("fij,fkj->fki", cameras, points)
    depths = points[..., 2]
    xy = homogeneous[..., :2] / np.maximum(homogeneous[..., 2:3], 1e-8)
    return xy, depths


def _inside(xy: np.ndarray, depths: np.ndarray, width: int, height: int) -> np.ndarray:
    return (depths > 1e-6) & (xy[..., 0] >= 0) & (xy[..., 0] < width) & (xy[..., 1] >= 0) & (xy[..., 1] < height)


def _mask_support(xy: np.ndarray, inside: np.ndarray, masks: np.ndarray) -> np.ndarray:
    masks = np.asarray(masks)
    if masks.ndim != 3 or masks.shape[0] != xy.shape[0]:
        raise ValueError(f"Expected masks [frames,height,width], got {masks.shape}.")
    height, width = masks.shape[1:]
    patch_radius = max(3, int(round(min(width, height) * 0.005)))
    kernel = np.ones((2 * patch_radius + 1,) * 2, dtype=np.uint8)
    support = np.zeros_like(inside)
    for frame_index, mask in enumerate(masks):
        dilated = cv2.dilate((mask >= 64).astype(np.uint8), kernel)
        candidates = np.flatnonzero(inside[frame_index])
        if candidates.size:
            pixels = np.rint(xy[frame_index, candidates]).astype(np.int64)
            pixels[:, 0] = np.clip(pixels[:, 0], 0, width - 1)
            pixels[:, 1] = np.clip(pixels[:, 1], 0, height - 1)
            support[frame_index, candidates] = dilated[pixels[:, 1], pixels[:, 0]] > 0
    return support


def _torso_valid(vitpose: np.ndarray, width: int, height: int) -> np.ndarray:
    detector = np.asarray(vitpose, dtype=np.float64)
    if detector.ndim != 3 or detector.shape[1:] != (17, 3):
        raise ValueError(f"Expected VitPose [frames,17,3], got {detector.shape}.")
    valid = (
        (detector[..., 2] >= 0.3)
        & (detector[..., 0] >= 0)
        & (detector[..., 0] < width)
        & (detector[..., 1] >= 0)
        & (detector[..., 1] < height)
    )
    shoulders = valid[:, 5] & valid[:, 6]
    torso = shoulders & (valid[:, 11] | valid[:, 12])
    return shoulders if float(torso.mean()) < 0.5 else torso


def _alignment_error(
    projected: np.ndarray,
    names: Sequence[str],
    vitpose: np.ndarray,
    width: int,
    height: int,
) -> float | None:
    coco_names = (
        "nose",
        "left-eye",
        "right-eye",
        "left-ear",
        "right-ear",
        "left-shoulder",
        "right-shoulder",
        "left-elbow",
        "right-elbow",
        "left-wrist",
        "right-wrist",
        "left-hip",
        "right-hip",
        "left-knee",
        "right-knee",
        "left-ankle",
        "right-ankle",
    )
    mapping = _name_index(names)
    if any(name not in mapping for name in coco_names):
        return None
    detector = np.asarray(vitpose, dtype=np.float64)
    valid = (
        (detector[..., 2] >= 0.3)
        & (detector[..., 0] >= 0)
        & (detector[..., 0] < width)
        & (detector[..., 1] >= 0)
        & (detector[..., 1] < height)
    )
    if not valid.any():
        return None
    errors = np.linalg.norm(projected[:, [mapping[name] for name in coco_names]] - detector[..., :2], axis=-1)
    return float(np.median(errors[valid]) / height)


def analyze_input_framing(
    incam_keypoints: np.ndarray,
    names: Sequence[str],
    intrinsics: np.ndarray,
    vitpose: np.ndarray,
    masks: np.ndarray,
) -> InputFraming:
    masks = np.asarray(masks)
    if masks.ndim != 3:
        raise ValueError(f"Expected masks [frames,height,width], got {masks.shape}.")
    frame_count, height, width = masks.shape
    if np.asarray(incam_keypoints).shape[0] != frame_count or np.asarray(vitpose).shape[0] != frame_count:
        raise ValueError("Input-framing arrays do not share one frame count.")

    anatomy, coordinates = anatomy_samples(incam_keypoints, names)
    anatomy_xy, anatomy_depth = project_incam(anatomy, intrinsics)
    support = _mask_support(anatomy_xy, _inside(anatomy_xy, anatomy_depth, width, height), masks)
    torso_valid = _torso_valid(vitpose, width, height)
    bottoms = np.full(frame_count, np.nan)
    visible_heights = np.full(frame_count, np.nan)
    for frame_index in range(frame_count):
        valid = np.flatnonzero(support[frame_index])
        if valid.size and torso_valid[frame_index]:
            bottoms[frame_index] = float(coordinates[valid].max())
            y = anatomy_xy[frame_index, valid, 1]
            visible_heights[frame_index] = float(np.clip((y.max() - y.min()) / height, 0.0, 1.0))
    valid_frames = np.isfinite(bottoms)
    if not valid_frames.any():
        raise ValueError("No valid frames for input framing analysis.")

    projected, depths = project_incam(incam_keypoints, intrinsics)
    mapping = _name_index(names)
    wrists = [mapping[name] for name in ("left-wrist", "right-wrist")]
    wrist_xy = projected[:, wrists]
    wrist_depth = depths[:, wrists]
    wrist_out_x = (wrist_depth <= 1e-6) | (wrist_xy[..., 0] < 0) | (wrist_xy[..., 0] >= width)
    wrist_out_y = (wrist_depth <= 1e-6) | (wrist_xy[..., 1] < 0) | (wrist_xy[..., 1] >= height)
    alignment = _alignment_error(projected, names, vitpose, width, height)
    valid_ratio = float(valid_frames.mean())
    torso_ratio = float(torso_valid.mean())
    alignment_score = 0.6 if alignment is None else float(np.clip(1.0 - alignment / 0.15, 0.0, 1.0))
    confidence = float(np.clip(0.45 * valid_ratio + 0.35 * torso_ratio + 0.20 * alignment_score, 0.0, 1.0))
    bottom = float(np.percentile(bottoms[valid_frames], 20.0))
    if bottom >= FULL_BODY_BOTTOM:
        label = "full_body"
    elif bottom >= HALF_BODY_BOTTOM:
        label = "half_body"
    else:
        label = "close_up"
    finite_heights = visible_heights[np.isfinite(visible_heights)]
    return InputFraming(
        label=label,
        visible_body_bottom=round(bottom, 6),
        visible_body_bottom_p50=round(float(np.percentile(bottoms[valid_frames], 50.0)), 6),
        visible_body_bottom_p80=round(float(np.percentile(bottoms[valid_frames], 80.0)), 6),
        visible_height_ratio=round(float(np.percentile(finite_heights, 50.0)) if finite_heights.size else 0.0, 6),
        wrist_out_ratio_x=round(float(np.any(wrist_out_x, axis=1).mean()), 6),
        wrist_out_ratio_y=round(float(np.any(wrist_out_y, axis=1).mean()), 6),
        valid_frame_ratio=round(valid_ratio, 6),
        torso_valid_ratio=round(torso_ratio, 6),
        projection_alignment_error_ratio=None if alignment is None else round(alignment, 6),
        confidence=round(confidence, 6),
    )


def _camera_coordinates(points: np.ndarray, cameras: Sequence[Camera]) -> np.ndarray:
    world = np.asarray(points, dtype=np.float64)
    points_h = np.concatenate([world, np.ones((*world.shape[:-1], 1), dtype=np.float64)], axis=-1)
    w2c = np.asarray([camera.world_to_camera for camera in cameras], dtype=np.float64)
    return np.einsum("cij,fkj->cfki", w2c[:, :3], points_h)


def projected_axis_ratios(
    points: np.ndarray,
    cameras: Sequence[Camera],
    focal_normalized: float,
    *,
    axis: int,
    axis_scale: float = 1.0,
) -> np.ndarray:
    camera_points = _camera_coordinates(points, cameras)
    depths = camera_points[..., 2]
    coordinates = focal_normalized * camera_points[..., axis] / np.maximum(depths, 1e-6) / axis_scale
    ratios = coordinates.max(axis=2) - coordinates.min(axis=2)
    ratios[np.any(depths <= 1e-6, axis=2)] = np.inf
    return ratios.max(axis=0)


def _selected(points: np.ndarray, names: Sequence[str], *, exclude_hands: bool, exclude_fingers: bool) -> np.ndarray:
    excluded = _FINGER_TOKENS
    if exclude_hands:
        excluded = ("wrist", *_FINGER_TOKENS)
    elif not exclude_fingers:
        excluded = ()
    ids = [index for index, name in enumerate(names) if not any(token in name.lower() for token in excluded)]
    return np.asarray(points)[:, ids]


def solve_radius(
    points: np.ndarray,
    names: Sequence[str],
    camera_factory: Callable[[float, float], Sequence[Camera]],
    aspect_ratio: float,
    spec: FramingConfig = FRAMING,
) -> RadiusSolve:
    height_points = _selected(points, names, exclude_hands=True, exclude_fingers=True)
    width_points = _selected(points, names, exclude_hands=False, exclude_fingers=True)

    def evaluate(radius: float) -> tuple[float, float, float]:
        cameras = camera_factory(radius, spec.reference_target_height)
        heights = projected_axis_ratios(height_points, cameras, spec.reference_focal_normalized, axis=1)
        widths = projected_axis_ratios(
            width_points, cameras, spec.reference_focal_normalized, axis=0, axis_scale=aspect_ratio
        )
        height = float(np.percentile(heights, spec.height_percentile))
        width = float(np.percentile(widths, spec.width_percentile))
        return max(height / spec.height_target_ratio, width / spec.width_target_ratio), height, width

    def result(radius: float, values: tuple[float, float, float], bound: str | None) -> RadiusSolve:
        _, height, width = values
        limiting = "width" if width / spec.width_target_ratio > height / spec.height_target_ratio else "height"
        return RadiusSolve(radius, height, width, bound, limiting)

    lower_values = evaluate(spec.min_radius)
    if lower_values[0] <= 1.0:
        return result(spec.min_radius, lower_values, "min")
    upper_values = evaluate(spec.max_radius)
    if upper_values[0] > 1.0:
        return result(spec.max_radius, upper_values, "max")
    lower, upper, best = spec.min_radius, spec.max_radius, upper_values
    for _ in range(24):
        midpoint = (lower + upper) / 2
        values = evaluate(midpoint)
        if values[0] > 1.0:
            lower = midpoint
        else:
            upper, best = midpoint, values
        if values[0] <= 1.0 and abs(values[0] - 1.0) <= 1e-4:
            break
    return result(upper, best, None)


def adaptive_thresholds(profile: InputFraming) -> AdaptiveThresholds:
    strength = float(
        np.clip((FULL_BODY_BOTTOM - profile.visible_body_bottom) / (FULL_BODY_BOTTOM - CLOSE_UP_BOTTOM), 0.0, 1.0)
    )
    return AdaptiveThresholds(strength, 0.80 + 0.12 * strength, 95.0, 0.90 + 0.20 * strength, 80.0 - 30.0 * strength)


def _cutoff_points(points: np.ndarray, coordinates: np.ndarray, cutoff: float) -> np.ndarray:
    path_length = points.shape[1] // 2
    output = []
    for offset in (0, path_length):
        local_coordinates = coordinates[offset : offset + path_length]
        local_points = points[:, offset : offset + path_length]
        after = int(np.searchsorted(local_coordinates, cutoff, side="right"))
        if after == 0:
            output.append(local_points[:, 0])
        elif after >= len(local_coordinates):
            output.append(local_points[:, -1])
        else:
            before = after - 1
            weight = (cutoff - local_coordinates[before]) / (local_coordinates[after] - local_coordinates[before])
            output.append(local_points[:, before] * (1.0 - weight) + local_points[:, after] * weight)
    return np.stack(output, axis=1)


def _visible_anatomy(
    points: np.ndarray,
    names: Sequence[str],
    bottom: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    samples, coordinates = anatomy_samples(points, names)
    core = samples[:, coordinates <= bottom + 1e-8]
    cutoff = _cutoff_points(samples, coordinates, bottom)
    if not np.any(np.isclose(coordinates, bottom, atol=1e-8)):
        core = np.concatenate([core, cutoff], axis=1)
    mapping = _name_index(names)
    arm_tokens = ("shoulder", "acromion", "elbow", "olecranon", "cubital-fossa", "wrist")
    arms = np.asarray(points)[
        :, [index for name, index in mapping.items() if any(token in name for token in arm_tokens)]
    ]
    return (
        np.asarray(core, dtype=np.float32),
        np.asarray(np.concatenate([core, arms], axis=1), dtype=np.float32),
        np.asarray(cutoff, dtype=np.float32),
    )


def _solve_focal(
    core: np.ndarray,
    width_points: np.ndarray,
    cameras: Sequence[Camera],
    thresholds: AdaptiveThresholds,
    aspect_ratio: float,
    spec: FramingConfig,
) -> tuple[FocalSolve, np.ndarray]:
    unit_heights = projected_axis_ratios(core, cameras, 1.0, axis=1)
    unit_widths = projected_axis_ratios(width_points, cameras, 1.0, axis=0, axis_scale=aspect_ratio)
    unit_height = float(np.percentile(unit_heights, thresholds.height_percentile))
    unit_width = float(np.percentile(unit_widths, thresholds.width_percentile))
    height_focal = thresholds.height_target_ratio / unit_height
    width_focal = thresholds.width_target_ratio / unit_width if unit_width > 0 else np.inf
    unconstrained = min(height_focal, width_focal)
    focal = float(np.clip(unconstrained, spec.reference_focal_normalized, spec.max_focal_normalized))
    bound = (
        "min"
        if unconstrained < spec.reference_focal_normalized
        else "max"
        if unconstrained > spec.max_focal_normalized
        else None
    )
    return (
        FocalSolve(
            focal,
            float(np.percentile(unit_heights * focal, thresholds.height_percentile)),
            float(np.percentile(unit_widths * focal, thresholds.width_percentile)),
            bound,
            "width" if width_focal < height_focal else "height",
        ),
        unit_heights,
    )


def _cutoff_ratio(points: np.ndarray, cameras: Sequence[Camera], focal: float, percentile: float) -> float:
    camera_points = _camera_coordinates(points, cameras)
    positions = 0.5 + focal * camera_points[..., 1] / np.maximum(camera_points[..., 2], 1e-6)
    positions[camera_points[..., 2] <= 1e-6] = np.nan
    return float(np.percentile(positions[np.isfinite(positions)], percentile))


def solve_clip_framing(
    keypoints: np.ndarray,
    names: Sequence[str],
    profile: InputFraming,
    camera_factory: Callable[[float, float], Sequence[Camera]],
    aspect_ratio: float,
    spec: FramingConfig = FRAMING,
) -> ClipFraming:
    radius_result = solve_radius(keypoints, names, camera_factory, aspect_ratio, spec)
    applied = profile.confidence >= spec.input_min_confidence
    thresholds = adaptive_thresholds(profile) if applied else None
    if not applied or thresholds is None or thresholds.closeup_strength <= 0:
        return ClipFraming(
            radius_result.radius,
            spec.reference_target_height,
            spec.reference_focal_normalized,
            profile,
            applied,
            radius_result,
            thresholds,
        )

    core, width_points, cutoff = _visible_anatomy(keypoints, names, profile.visible_body_bottom)
    centers = (core[..., 1].min(axis=1) + core[..., 1].max(axis=1)) / 2
    anatomical_target = float(np.median(centers))
    alignment = min(1.0, 2.0 * thresholds.closeup_strength)
    initial_target = spec.reference_target_height * (1.0 - alignment) + anatomical_target * alignment

    def evaluate(target_height: float) -> tuple[FocalSolve, float]:
        cameras = camera_factory(radius_result.radius, target_height)
        focal, _ = _solve_focal(core, width_points, cameras, thresholds, aspect_ratio, spec)
        return focal, _cutoff_ratio(cutoff, cameras, focal.focal_normalized, spec.cutoff_percentile)

    lower, upper = initial_target - 0.5, initial_target + 0.5
    lower_value, upper_value = evaluate(lower), evaluate(upper)
    increasing = upper_value[1] > lower_value[1]
    if not min(lower_value[1], upper_value[1]) <= spec.cutoff_target_ratio <= max(lower_value[1], upper_value[1]):
        if abs(lower_value[1] - spec.cutoff_target_ratio) <= abs(upper_value[1] - spec.cutoff_target_ratio):
            target, value, target_bound = lower, lower_value, "min"
        else:
            target, value, target_bound = upper, upper_value, "max"
    else:
        target, value, target_bound = lower, lower_value, None
        for _ in range(20):
            midpoint = (lower + upper) / 2
            candidate = evaluate(midpoint)
            error = candidate[1] - spec.cutoff_target_ratio
            if abs(error) < abs(value[1] - spec.cutoff_target_ratio):
                target, value = midpoint, candidate
            if abs(error) <= 1e-4:
                break
            if (error < 0) == increasing:
                lower = midpoint
            else:
                upper = midpoint

    return ClipFraming(
        radius_result.radius,
        target,
        value[0].focal_normalized,
        profile,
        True,
        radius_result,
        thresholds,
        value[0],
        value[1],
        target_bound,
    )
