"""Write generated videos, cameras, and run metadata into output staging."""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from fdanyone.config import INFERENCE
from fdanyone.device import CUDA_ALLOCATOR_CONF
from fdanyone.errors import FourDAnyoneError
from fdanyone.result_videos import target_video_path

if TYPE_CHECKING:
    from fdanyone.model.inference import GeneratedViews
    from fdanyone.motion.result import MotionResult
    from fdanyone.skeleton.pipeline import Conditioning
    from fdanyone.video import ClipInfo


def _runtime_metadata(device: str) -> dict:
    import torch

    cuda = {
        "available": torch.cuda.is_available(),
        "torch_cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "allocator_config": os.environ.get(CUDA_ALLOCATOR_CONF),
    }
    if torch.cuda.is_available():
        torch_device = torch.device(device)
        properties = torch.cuda.get_device_properties(torch_device)
        cuda.update(
            {
                "device": device,
                "device_name": torch.cuda.get_device_name(torch_device),
                "device_capability": list(torch.cuda.get_device_capability(torch_device)),
                "device_total_memory_bytes": properties.total_memory,
            }
        )
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda": cuda,
    }


def _camera_rig_payload(payload: dict, cameras: list[dict]) -> dict:
    """Keep the final OpenCV camera rig needed by downstream tools."""

    records = []
    for camera in cameras:
        camera_id = int(camera["camera_id"])
        records.append(
            {
                "camera_id": camera_id,
                "layer_index": int(camera["layer_index"]),
                "pitch": int(camera["pitch_degrees"]),
                "yaw": float(camera["yaw_degrees"]),
                "K": camera["K"],
                "camera_to_world": camera["camera_to_world"],
                "image_width": int(camera["image_width"]),
                "image_height": int(camera["image_height"]),
                "video": str(target_video_path(camera_id)),
                "skeleton_video": f"skeletons/{camera_id:02d}.mp4",
            }
        )
    return {
        "camera_model": "OPENCV",
        "world_frame": payload["world_frame"],
        "camera_frame": payload["camera_frame"],
        "front_camera_ids": payload["front_camera_ids"],
        "framing": payload["framing"],
        "cameras": records,
    }


def _target_cameras(payload: object, expected_count: int) -> list[dict]:
    """Read the camera records produced by the conditioning stage."""

    if not isinstance(payload, dict) or payload.get("camera_model") != "OPENCV":
        raise FourDAnyoneError("Conditioning did not produce an OpenCV camera rig.")
    cameras = payload.get("cameras")
    if not isinstance(cameras, list) or len(cameras) != expected_count:
        raise FourDAnyoneError(f"Conditioning must contain {expected_count} target cameras.")
    if [camera.get("camera_id") for camera in cameras if isinstance(camera, dict)] != list(range(expected_count)):
        raise FourDAnyoneError("Target cameras are not in canonical order.")
    return cameras


def write_output(
    *,
    clip: ClipInfo,
    conditioning: Conditioning,
    generated: GeneratedViews,
    destination: str | Path,
    motion: MotionResult,
    model_identity: dict,
    pipeline_started: float,
) -> dict:
    """Write target, skeleton, camera, and metadata artifacts into staging."""

    root = Path(destination).expanduser().resolve()
    attention_backend = generated.attention_backend
    view_plan = generated.view_plan
    if conditioning.view_plan != view_plan:
        raise FourDAnyoneError("Conditioning and generation resolved different view plans.")
    if len(generated.target_videos) != view_plan.num_target_views:
        raise FourDAnyoneError(
            f"Generation returned {len(generated.target_videos)} target videos, expected {view_plan.num_target_views}."
        )
    if len(conditioning.target_skeletons) != view_plan.num_target_views:
        raise FourDAnyoneError(
            f"Conditioning returned {len(conditioning.target_skeletons)} target skeletons, "
            f"expected {view_plan.num_target_views}."
        )

    videos_root = root / "videos"
    skeletons_root = root / "skeletons"
    videos_root.mkdir(parents=True, exist_ok=False)
    skeletons_root.mkdir(exist_ok=False)
    for camera_id, source in enumerate(generated.target_videos):
        shutil.copy2(source, root / target_video_path(camera_id))
    for camera_id, skeleton in enumerate(conditioning.target_skeletons):
        shutil.copy2(skeleton.path, skeletons_root / f"{camera_id:02d}.mp4")

    camera_payload = json.loads((conditioning.root / "cameras.json").read_text())
    conditioning_metadata = json.loads((conditioning.root / "metadata.json").read_text())
    camera_records = _target_cameras(camera_payload, view_plan.num_target_views)
    total_elapsed = time.monotonic() - pipeline_started
    generation_metadata = {
        "seed": generated.seed,
        "view_plan": {
            **view_plan.to_dict(),
            "num_layers": view_plan.num_layers,
            "num_target_views": view_plan.num_target_views,
            "num_groups": view_plan.num_groups,
        },
        "attention_backend": attention_backend,
        "inference_steps": generated.denoising_profile.num_inference_steps,
        "denoising_profile": generated.denoising_profile.to_dict(),
        "elapsed_seconds": generated.elapsed_seconds,
        "stage_peak_vram_bytes": generated.stage_peak_vram_bytes,
        "total_elapsed_seconds": total_elapsed,
        "peak_vram_allocated_bytes": generated.peak_vram_allocated_bytes,
        "peak_vram_reserved_bytes": generated.peak_vram_reserved_bytes,
    }
    if generated.parallelism is not None:
        generation_metadata["parallelism"] = generated.parallelism

    metadata = {
        "input": {
            "filename": clip.source_path.name,
            "fps": f"{clip.fps_num}/{clip.fps_den}",
            "start_time_seconds": float(clip.start_time),
            "num_frames": clip.num_frames,
            "width": clip.width,
            "height": clip.height,
        },
        "motion": {
            "method": "GVHMR",
            "revision": motion.gvhmr_revision,
        },
        "preprocessing": {
            "source_crop_policy": conditioning_metadata["source_crop_policy"],
            "foreground_model": conditioning_metadata["foreground_model"],
            "framing": conditioning_metadata["framing"],
            "skeleton_draw_scale": conditioning_metadata["skeleton_draw_scale"],
        },
        "model": dict(model_identity),
        "generation": generation_metadata,
        "output": {
            "target_views": view_plan.num_target_views,
            "frames_per_video": INFERENCE.num_frames,
            "width": INFERENCE.width,
            "height": INFERENCE.height,
            "fps": f"{clip.fps_num}/{clip.fps_den}",
        },
        "runtime": _runtime_metadata(generated.device),
    }
    # Staging is private. Output publication, not each JSON write, owns the
    # commit boundary and interruption recovery.
    for name, payload in (
        ("cameras.json", _camera_rig_payload(camera_payload, camera_records)),
        ("metadata.json", metadata),
    ):
        (root / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return {
        "attention_backend": attention_backend,
        "num_target_videos": view_plan.num_target_views,
        "fps": f"{clip.fps_num}/{clip.fps_den}",
        "peak_vram_allocated_bytes": generated.peak_vram_allocated_bytes,
        "peak_vram_reserved_bytes": generated.peak_vram_reserved_bytes,
        "total_pipeline_elapsed_seconds": total_elapsed,
    }
