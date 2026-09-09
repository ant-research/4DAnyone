"""Build source-aware Goliath40 conditioning for multi-view generation."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from fdanyone.assets import BIREFNET_REPO_ID, BIREFNET_REVISION
from fdanyone.config import CAMERA, CROP, FOREGROUND, INFERENCE, SKELETON, CameraConfig
from fdanyone.errors import AssetError, FourDAnyoneError
from fdanyone.foreground import predict_foreground_masks
from fdanyone.geometry.cameras import (
    CAMERA_FRAME,
    WORLD_FRAME,
    Camera,
    camera_grid,
    camera_ring,
    project_points,
    reference_intrinsics,
)
from fdanyone.geometry.crop import Crop, center_crop, crop_from_bounds, mask_bounds, transform_intrinsics
from fdanyone.geometry.framing import analyze_input_framing, solve_clip_framing
from fdanyone.io import write_json
from fdanyone.motion.gvhmr import gvhmr_imports, validate_gvhmr
from fdanyone.motion.result import MotionResult
from fdanyone.skeleton.keypoints import KEYPOINT_NAMES
from fdanyone.skeleton.renderer import estimate_body_height, projected_body_scales, render_goliath40
from fdanyone.vendor.pytorch3d_compat import install_if_needed as install_pytorch3d_compat
from fdanyone.video import CanonicalClip, iter_rgb_video, write_lossless_video, write_video
from fdanyone.views import ViewPlan

LOGGER = logging.getLogger("fdanyone")


@dataclass(frozen=True)
class SkeletonVideo:
    path: Path
    crop: Crop


@dataclass(frozen=True)
class Conditioning:
    root: Path
    source_video: Path
    source_crop: Crop
    target_skeletons: tuple[SkeletonVideo, ...]
    rcp_skeletons: tuple[SkeletonVideo, ...]
    view_plan: ViewPlan
    fps_num: int
    fps_den: int
    num_frames: int

    def load_source_tensor(self):
        return _video_tensor(self.source_video, self.num_frames, crop=self.source_crop)

    def load_skeleton_tensor(self, skeletons: Iterable[SkeletonVideo]):
        import torch

        videos = [_video_tensor(item.path, self.num_frames, crop=item.crop) for item in skeletons]
        return torch.cat(videos, dim=0)

    @classmethod
    def load(cls, directory: str | Path) -> Conditioning:
        root = Path(directory).expanduser().resolve()
        camera_payload = json.loads((root / "cameras.json").read_text())
        metadata = json.loads((root / "metadata.json").read_text())
        try:
            view_plan = ViewPlan.from_dict(metadata["view_plan"])
        except (KeyError, TypeError) as exc:
            raise FourDAnyoneError("Conditioning artifacts have no valid view plan.") from exc
        records = camera_payload["cameras"]
        if [int(record["camera_id"]) for record in records] != list(range(view_plan.num_target_views)):
            raise FourDAnyoneError("Target conditioning cameras are not in canonical order.")
        for record, view in zip(records, view_plan.target_views, strict=True):
            if (
                int(record.get("layer_index", -1)) != view.layer_index
                or int(record.get("pitch_degrees", 1000)) != view.pitch
                or abs(float(record.get("yaw_degrees", 1000.0)) - view.yaw) > 1e-8
            ):
                raise FourDAnyoneError("Target conditioning cameras do not match the resolved view layout.")
        if camera_payload.get("front_camera_ids") != list(view_plan.front_camera_ids):
            raise FourDAnyoneError("Target conditioning has the wrong frontal-camera IDs.")
        rcp_records = camera_payload.get("rcp_cameras", [])
        if [int(record["camera_id"]) for record in rcp_records] != list(view_plan.rcp_camera_ids):
            raise FourDAnyoneError("RCP conditioning cameras do not match the resolved view plan.")

        def skeletons(camera_records: list[dict]) -> tuple[SkeletonVideo, ...]:
            return tuple(
                SkeletonVideo(root / record["skeleton_video"], Crop(**record["crop"])) for record in camera_records
            )

        target_skeletons = skeletons(records)
        rcp_skeletons = skeletons(rcp_records)
        required = (
            root / metadata["source_video"],
            *(item.path for item in (*target_skeletons, *rcp_skeletons)),
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FourDAnyoneError(f"Conditioning artifacts are incomplete: {missing}.")
        return cls(
            root=root,
            source_video=root / metadata["source_video"],
            source_crop=Crop(**metadata["source_crop"]),
            target_skeletons=target_skeletons,
            rcp_skeletons=rcp_skeletons,
            view_plan=view_plan,
            fps_num=int(metadata["fps_num"]),
            fps_den=int(metadata["fps_den"]),
            num_frames=int(metadata["num_frames"]),
        )


@dataclass(frozen=True)
class _BodyGeometry:
    vertices_world: np.ndarray
    joints_world: np.ndarray
    keypoints_world: np.ndarray
    keypoints_incam: np.ndarray
    motion_world_to_canonical_world: np.ndarray
    regressor_metadata: dict[str, int | str]


def _video_tensor(path: Path, num_frames: int, *, crop: Crop | None = None):
    import torch
    import torchvision.transforms.functional as transform
    from torchvision.transforms import InterpolationMode

    output_frames = []
    for frame in iter_rgb_video(path):
        tensor = torch.from_numpy(frame).permute(2, 0, 1).float().div_(255.0)
        if crop is not None:
            height, width = tensor.shape[-2:]
            scaled = _scale_crop(
                crop,
                scale_y=height / crop.original_height,
                scale_x=width / crop.original_width,
            )
            tensor = transform.crop(tensor, scaled.top, scaled.left, scaled.height, scaled.width)
            if tensor.shape[-2:] != (crop.output_height, crop.output_width):
                tensor = transform.resize(
                    tensor,
                    (crop.output_height, crop.output_width),
                    interpolation=InterpolationMode.BICUBIC,
                    antialias=True,
                )
            tensor = tensor.clamp_(0.0, 1.0)
        output_frames.append(tensor.mul_(2.0).sub_(1.0))
    if len(output_frames) != num_frames:
        raise FourDAnyoneError(f"Video {path} has {len(output_frames)} decoded frames, expected {num_frames}.")
    return torch.stack(output_frames, dim=1).unsqueeze(0).contiguous()


def _safe_regressor_metadata(support_shape: tuple[int, ...]) -> dict[str, int | str]:
    return {
        "format": "sparse_vertex_regressor",
        "num_keypoints": int(support_shape[0]),
        "support_vertices_per_keypoint": int(support_shape[1]),
    }


def _load_regressor(path: Path, device):
    import torch

    data = torch.load(path, map_location="cpu", weights_only=True)
    support = data["support_vertex_ids"].detach().long().to(device)
    weights = data["weights"].detach().float().to(device)
    names = tuple(str(value) for value in data["keypoint_names"])
    if support.shape != weights.shape or support.shape[0] != 70:
        raise AssetError(f"Unexpected MHR70 regressor shapes: support={support.shape}, weights={weights.shape}.")
    if names != KEYPOINT_NAMES:
        raise AssetError("MHR70 regressor keypoint order does not match the frozen Goliath70 schema.")
    return support, weights, _safe_regressor_metadata(tuple(support.shape))


@contextmanager
def _gvhmr_geometry_context(gvhmr_root: Path):
    install_pytorch3d_compat()
    with gvhmr_imports(gvhmr_root):
        yield


def _body_geometry(
    motion: MotionResult,
    regressor_path: Path,
    gvhmr_root: Path,
    device: str,
) -> _BodyGeometry:
    import torch

    body_model = gvhmr_root / "inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz"
    if not body_model.is_file():
        raise AssetError(
            "The licensed SMPL-X body model is missing. Run `python scripts/download_smplx.py`; "
            f"expected the GVHMR compatibility link at {body_model}."
        )
    utility_root = gvhmr_root / "hmr4d/utils/body_model"
    smplx_to_smpl_path = utility_root / "smplx2smpl_sparse.pt"
    joint_regressor_path = utility_root / "smpl_neutral_J_regressor.pt"
    for path in (smplx_to_smpl_path, joint_regressor_path):
        if not path.is_file():
            raise AssetError(f"GVHMR body-model utility is missing: {path}")

    torch_device = torch.device(device)
    support, weights, regressor_metadata = _load_regressor(regressor_path, torch_device)
    with _gvhmr_geometry_context(gvhmr_root):
        from hmr4d.utils.geo_transform import apply_T_on_points, compute_T_ayfz2ay
        from hmr4d.utils.smplx_utils import make_smplx

        smplx = make_smplx("supermotion").to(torch_device).eval()
        global_parameters = {name: value.to(torch_device) for name, value in motion.smpl_params_global.items()}
        incam_parameters = {name: value.to(torch_device) for name, value in motion.smpl_params_incam.items()}
        with torch.inference_mode():
            vertices_global = smplx(**global_parameters).vertices.detach()
            vertices_incam = smplx(**incam_parameters).vertices.detach()
        if tuple(vertices_global.shape[1:]) != (10475, 3) or vertices_incam.shape != vertices_global.shape:
            raise FourDAnyoneError(
                "Expected matching global/incam SMPL-X vertices [frames,10475,3], got "
                f"{tuple(vertices_global.shape)} and {tuple(vertices_incam.shape)}."
            )
        keypoints_global = (vertices_global[:, support] * weights[None, :, :, None]).sum(dim=2)
        keypoints_incam = (vertices_incam[:, support] * weights[None, :, :, None]).sum(dim=2)
        smplx_to_smpl = torch.load(smplx_to_smpl_path, map_location=torch_device, weights_only=True)
        joint_regressor = torch.load(joint_regressor_path, map_location=torch_device, weights_only=True)
        vertices_smpl = torch.stack([torch.matmul(smplx_to_smpl, frame) for frame in vertices_global])
        offset = torch.einsum("jv,vi->ji", joint_regressor, vertices_smpl[0])[0]
        offset = offset.clone()
        offset[1] = vertices_smpl[..., 1].min()
        vertices_offset = vertices_smpl - offset
        first_joints = torch.einsum("jv,lvi->lji", joint_regressor, vertices_offset[[0]])
        transform = compute_T_ayfz2ay(first_joints, inverse=True)
        vertices_world = apply_T_on_points(vertices_offset, transform)
        keypoints_world = apply_T_on_points(keypoints_global - offset, transform)
        joints_world = torch.einsum("jv,lvi->lji", joint_regressor, vertices_world)

    world_transform = transform[0].detach().clone()
    world_transform[:3, 3] -= world_transform[:3, :3] @ offset
    result = _BodyGeometry(
        vertices_world.detach().cpu().numpy().astype(np.float32),
        joints_world.detach().cpu().numpy().astype(np.float32),
        keypoints_world.detach().cpu().numpy().astype(np.float32),
        keypoints_incam.detach().cpu().numpy().astype(np.float32),
        world_transform.detach().cpu().numpy().astype(np.float64),
        regressor_metadata,
    )
    del smplx, vertices_global, vertices_incam, vertices_smpl, vertices_world, keypoints_global, keypoints_world
    torch.cuda.empty_cache()
    return result


def _front_direction(joints: np.ndarray) -> np.ndarray:
    first = joints[0]
    left = first[1, [0, 2]] - first[2, [0, 2]] + first[16, [0, 2]] - first[17, [0, 2]]
    norm = float(np.linalg.norm(left))
    if norm <= 1e-8:
        return np.array([0.0, 0.0, -1.0], dtype=np.float64)
    left /= norm
    return np.array([left[1], 0.0, -left[0]], dtype=np.float64)


def _projection_shape(height: int, width: int, max_render_height: int = 1280) -> tuple[int, int]:
    divisor = 2
    while height / divisor > max_render_height:
        divisor += 1
    return height // divisor, width // divisor


def _output_skeleton_shape(height: int, width: int) -> tuple[int, int]:
    while max(height, width) > INFERENCE.skeleton_max_dimension:
        height //= 2
        width //= 2
    return max(2, height - height % 2), max(2, width - width % 2)


def _scale_crop(crop: Crop, *, scale_y: float, scale_x: float) -> Crop:
    original_height = max(1, int(round(crop.original_height * scale_y)))
    original_width = max(1, int(round(crop.original_width * scale_x)))
    top = min(max(0, int(round(crop.top * scale_y))), original_height - 1)
    left = min(max(0, int(round(crop.left * scale_x))), original_width - 1)
    height = min(max(1, int(round(crop.height * scale_y))), original_height - top)
    width = min(max(1, int(round(crop.width * scale_x))), original_width - left)
    return Crop(
        top,
        left,
        height,
        width,
        original_height,
        original_width,
        crop.output_height,
        crop.output_width,
    )


def _cropped_camera(camera: Camera, crop: Crop) -> Camera:
    intrinsic = transform_intrinsics(np.asarray(camera.K), crop)
    return replace(
        camera,
        K=tuple(tuple(float(value) for value in row) for row in intrinsic),
        image_width=crop.output_width,
        image_height=crop.output_height,
    )


def _resized_camera(camera: Camera, image_height: int, image_width: int) -> Camera:
    intrinsic = np.asarray(camera.K, dtype=np.float64).copy()
    intrinsic[0] *= image_width / camera.image_width
    intrinsic[1] *= image_height / camera.image_height
    intrinsic[2, 2] = 1.0
    return replace(
        camera,
        K=tuple(tuple(float(value) for value in row) for row in intrinsic),
        image_width=image_width,
        image_height=image_height,
    )


def build_skeleton_conditioning(
    *,
    motion: MotionResult,
    clip: CanonicalClip,
    regressor_path: str | Path,
    foreground_model_path: str | Path,
    gvhmr_root: str | Path,
    output_dir: str | Path,
    device: str,
    view_plan: ViewPlan,
) -> Conditioning:
    """Build source, RCP, and target conditioning on one camera grid."""

    gvhmr_root, _ = validate_gvhmr(gvhmr_root)
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Estimating source foreground masks with BiRefNet")
    masks = predict_foreground_masks(clip.rgb_frames, foreground_model_path, device)
    geometry = _body_geometry(motion, Path(regressor_path), gvhmr_root, device)
    input_framing = analyze_input_framing(
        geometry.keypoints_incam,
        KEYPOINT_NAMES,
        motion.K_fullimg.detach().cpu().numpy(),
        motion.observed_keypoints_2d.detach().cpu().numpy(),
        masks,
    )

    targets = geometry.vertices_world.mean(axis=1)
    targets[:, 1] = 0.0
    center = targets.mean(axis=0)
    front_direction = _front_direction(geometry.joints_world)
    reference_K = reference_intrinsics(clip.height, clip.width)
    framing_pitches = tuple(dict.fromkeys((*view_plan.layer_pitches, int(CAMERA.pitch_degrees))))

    def camera_factory(radius: float, target_height: float) -> tuple[Camera, ...]:
        # A full safety ring at every requested pitch keeps framing independent
        # of view density while covering all target and canonical RCP cameras.
        candidate_center = center.copy()
        candidate_center[1] = target_height
        return tuple(
            camera
            for layer_index, pitch in enumerate(framing_pitches)
            for camera in camera_ring(
                center=candidate_center,
                front_direction=front_direction,
                K=reference_K,
                image_height=clip.height,
                image_width=clip.width,
                radius=radius,
                target_height=target_height,
                spec=CameraConfig(count=CAMERA.count, pitch_degrees=float(pitch)),
                layer_index=layer_index,
                camera_id_offset=layer_index * CAMERA.count,
            )
        )

    projection_height, projection_width = _projection_shape(clip.height, clip.width)
    framing = solve_clip_framing(
        geometry.keypoints_world,
        KEYPOINT_NAMES,
        input_framing,
        camera_factory,
        projection_width / projection_height,
    )
    LOGGER.info(
        "Adaptive framing: input=%s confidence=%.3f radius=%.3f target_height=%.3f f/H=%.3f",
        input_framing.label,
        input_framing.confidence,
        framing.radius,
        framing.target_height,
        framing.focal_normalized,
    )
    center[1] = framing.target_height
    raw_intrinsic = reference_intrinsics(
        clip.height,
        clip.width,
        focal_normalized=framing.focal_normalized,
    )
    raw_target_cameras = camera_grid(
        center=center,
        front_direction=front_direction,
        K=raw_intrinsic,
        image_height=clip.height,
        image_width=clip.width,
        radius=framing.radius,
        target_height=framing.target_height,
        views_per_layer=view_plan.views_per_layer,
        layer_pitches=view_plan.layer_pitches,
        start_yaw=view_plan.start_yaw,
        yaw_span=view_plan.yaw_span,
    )

    source_crop = crop_from_bounds(
        bounds=mask_bounds(masks, CROP.mask_threshold),
        image_height=clip.height,
        image_width=clip.width,
        output_height=INFERENCE.height,
        output_width=INFERENCE.width,
        margins=CROP.margins,
        allow_upscale=CROP.allow_upscale,
    )
    target_crop = center_crop(clip.height, clip.width, INFERENCE.height, INFERENCE.width)
    source_video = write_lossless_video(clip, root / "source.mkv")
    skeleton_root = root / "goliath40"
    skeleton_root.mkdir()
    skeleton_height, skeleton_width = _output_skeleton_shape(clip.height, clip.width)
    body_height = estimate_body_height(geometry.keypoints_world, KEYPOINT_NAMES)
    np.save(root / "keypoints_3d.npy", geometry.keypoints_world)

    def render_skeleton(camera: Camera, path: Path) -> Path:
        projected, depths = [], []
        for frame_points in geometry.keypoints_world:
            xy, depth, _ = project_points(frame_points, camera)
            projected.append(xy)
            depths.append(depth)
        keypoints_2d = np.stack(projected)
        keypoint_depths = np.stack(depths)
        body_scales = projected_body_scales(
            keypoint_depths,
            KEYPOINT_NAMES,
            body_height,
            float(np.sqrt(raw_intrinsic[0, 0] * raw_intrinsic[1, 1])),
        )

        def rendered_frames(
            points=keypoints_2d,
            point_depths=keypoint_depths,
            scales=body_scales,
        ):
            scores = np.ones(len(KEYPOINT_NAMES), dtype=np.float32)
            for frame_index in range(motion.num_frames):
                yield render_goliath40(
                    points[frame_index],
                    point_depths[frame_index],
                    scores,
                    canvas_height=clip.height,
                    canvas_width=clip.width,
                    output_height=skeleton_height,
                    output_width=skeleton_width,
                    body_scale_px=float(scales[frame_index]),
                )

        return write_video(
            rendered_frames(),
            path,
            clip.fps,
            crf=INFERENCE.skeleton_h264_crf,
            preset=INFERENCE.h264_preset,
        )

    target_paths = tuple(
        render_skeleton(camera, skeleton_root / f"{camera.camera_id:02d}.mp4") for camera in raw_target_cameras
    )
    cropped_target_cameras = tuple(_cropped_camera(camera, target_crop) for camera in raw_target_cameras)

    if not view_plan.enable_rcp:
        raw_rcp_cameras: tuple[Camera, ...] = ()
        rcp_paths: tuple[Path, ...] = ()
        cropped_rcp_cameras: tuple[Camera, ...] = ()
    elif view_plan.is_canonical_target_ring:
        raw_rcp_cameras = tuple(raw_target_cameras[camera_id] for camera_id in view_plan.rcp_camera_ids)
        rcp_paths = tuple(target_paths[camera_id] for camera_id in view_plan.rcp_camera_ids)
        cropped_rcp_cameras = tuple(cropped_target_cameras[camera_id] for camera_id in view_plan.rcp_camera_ids)
    else:
        canonical_cameras = camera_ring(
            center=center,
            front_direction=front_direction,
            K=raw_intrinsic,
            image_height=clip.height,
            image_width=clip.width,
            radius=framing.radius,
            target_height=framing.target_height,
            layer_index=-1,
        )
        raw_rcp_cameras = tuple(canonical_cameras[camera_id] for camera_id in view_plan.rcp_camera_ids)
        rcp_root = root / "rcp_goliath40"
        rcp_root.mkdir()
        rcp_paths = tuple(
            render_skeleton(camera, rcp_root / f"{camera.camera_id:02d}.mp4") for camera in raw_rcp_cameras
        )
        cropped_rcp_cameras = tuple(_cropped_camera(camera, target_crop) for camera in raw_rcp_cameras)

    def camera_records(
        raw_cameras: tuple[Camera, ...],
        cropped_cameras: tuple[Camera, ...],
        paths: tuple[Path, ...],
    ) -> list[dict]:
        return [
            {
                **camera.to_dict(),
                "crop": asdict(target_crop),
                "raw_camera": raw.to_dict(),
                "skeleton_camera": _resized_camera(raw, skeleton_height, skeleton_width).to_dict(),
                "skeleton_video": path.relative_to(root).as_posix(),
            }
            for raw, camera, path in zip(raw_cameras, cropped_cameras, paths, strict=True)
        ]

    framing_payload = framing.to_dict()
    camera_payload = {
        "camera_model": "OPENCV",
        "world_frame": WORLD_FRAME,
        "camera_frame": CAMERA_FRAME,
        "front_camera_ids": list(view_plan.front_camera_ids),
        "motion_world": motion.motion_world,
        "motion_world_to_canonical_world": geometry.motion_world_to_canonical_world.tolist(),
        "ring_center": center.tolist(),
        "framing": framing_payload,
        "cameras": camera_records(raw_target_cameras, cropped_target_cameras, target_paths),
        "rcp_cameras": camera_records(raw_rcp_cameras, cropped_rcp_cameras, rcp_paths),
    }
    write_json(root / "cameras.json", camera_payload)
    write_json(
        root / "metadata.json",
        {
            "view_plan": view_plan.to_dict(),
            "num_frames": motion.num_frames,
            "fps_num": clip.fps_num,
            "fps_den": clip.fps_den,
            "source_video": source_video.name,
            "source_crop": asdict(source_crop),
            "source_crop_policy": {
                "subject": "fmask",
                "threshold": CROP.mask_threshold,
                "margins": CROP.margins,
                "allow_upscale": CROP.allow_upscale,
            },
            "foreground_model": {
                "repo_id": BIREFNET_REPO_ID,
                "revision": BIREFNET_REVISION,
                "image_size": FOREGROUND.image_size,
                "batch_size": FOREGROUND.batch_size,
            },
            "framing": framing_payload,
            "regressor_metadata": geometry.regressor_metadata,
            "keypoint_names": KEYPOINT_NAMES,
            "visible_keypoint_set": "goliath40",
            "skeleton_codec_boundary": f"libx264_crf{INFERENCE.skeleton_h264_crf}",
            "skeleton_canvas": {"height": skeleton_height, "width": skeleton_width},
            "skeleton_draw_scale": {
                "mode": "kp3d",
                "body_height_3d": body_height,
                "body_reference_px": SKELETON.draw_body_reference_px,
            },
        },
    )
    return Conditioning(
        root=root,
        source_video=source_video,
        source_crop=source_crop,
        target_skeletons=tuple(SkeletonVideo(path, target_crop) for path in target_paths),
        rcp_skeletons=tuple(SkeletonVideo(path, target_crop) for path in rcp_paths),
        view_plan=view_plan,
        fps_num=clip.fps_num,
        fps_den=clip.fps_den,
        num_frames=motion.num_frames,
    )
