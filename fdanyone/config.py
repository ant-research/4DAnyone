"""Fixed model and preprocessing settings used by the released method.

Only reader-useful choices live in the CLI. These values describe the trained
model and therefore stay together here instead of being exposed as knobs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InferenceConfig:
    num_frames: int = 121
    height: int = 1280
    width: int = 704
    prompt: str = "视频中的人在做动作"
    auto_downsample_fps: tuple[tuple[int, int], ...] = (
        (24, 1),
        (24000, 1001),
        (25, 1),
        (30, 1),
        (30000, 1001),
    )
    temporal_sampling_policy: str = "nearest_source_pts_on_zero_based_cfr_clock"
    rcp_jpeg_quality: int = 85
    skeleton_h264_crf: int = 17
    target_h264_crf: int = 18
    h264_preset: str = "medium"
    skeleton_max_dimension: int = 2048
    num_inference_steps: int = 24
    denoising_strength: float = 1.0
    scheduler_shift: float = 5.0
    tiled_vae: bool = False
    vae_tile_size: tuple[int, int] = (52, 30)
    vae_tile_stride: tuple[int, int] = (26, 15)


@dataclass(frozen=True)
class CameraConfig:
    count: int = 24
    pitch_degrees: float = 15.0

    def __post_init__(self) -> None:
        if self.count <= 0:
            raise ValueError("Camera count must be positive.")


@dataclass(frozen=True)
class ForegroundConfig:
    """Pinned standard BiRefNet inference contract."""

    image_size: tuple[int, int] = (1024, 1024)
    batch_size: int = 4


@dataclass(frozen=True)
class FramingConfig:
    """Sequence-level camera solve matching the current GVHMR demo."""

    reference_radius: float = 3.0
    reference_target_height: float = 1.0
    reference_focal_normalized: float = 1664.0 / 1280.0
    height_target_ratio: float = 0.80
    height_percentile: float = 95.0
    width_target_ratio: float = 0.90
    width_percentile: float = 80.0
    min_radius: float = 1.5
    max_radius: float = 8.0
    input_min_confidence: float = 0.55
    max_focal_normalized: float = 4.0
    cutoff_target_ratio: float = 0.99
    cutoff_percentile: float = 80.0


@dataclass(frozen=True)
class CropConfig:
    """Source-mask crop; generated cameras use a plain center aspect crop."""

    margin_top: float = 0.04
    margin_right: float = 0.04
    margin_bottom: float = 0.04
    margin_left: float = 0.04
    allow_upscale: bool = True
    mask_threshold: float = 0.05

    @property
    def margins(self) -> tuple[float, float, float, float]:
        return (self.margin_top, self.margin_right, self.margin_bottom, self.margin_left)


@dataclass(frozen=True)
class SkeletonConfig:
    draw_body_reference_px: float = 640.0


INFERENCE = InferenceConfig()
CAMERA = CameraConfig()
FOREGROUND = ForegroundConfig()
FRAMING = FramingConfig()
CROP = CropConfig()
SKELETON = SkeletonConfig()
