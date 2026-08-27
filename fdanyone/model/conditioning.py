"""Frozen, timestep-independent conditioning used by the denoiser."""

from __future__ import annotations

import gc
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fdanyone.config import INFERENCE
from fdanyone.errors import AssetError, FourDAnyoneError

if TYPE_CHECKING:
    from torch import Tensor

    from fdanyone.skeleton.pipeline import Conditioning, SkeletonVideo

LOGGER = logging.getLogger("fdanyone")

PROMPT_CONTEXT_FORMAT = "fdanyone.prompt_context"
PROMPT_CONTEXT_VERSION = "2"
PROMPT_CONTEXT_KEY = "context"
PROMPT_CONTEXT_SHAPE = (1, 512, 4096)
PROMPT_CONTEXT_SOURCE_REPO = "Wan-AI/Wan2.1-T2V-1.3B"
PROMPT_CONTEXT_SOURCE_REVISION = "3f40b6dc4ca5c02dd23c9db74d9d2ccb82903b86"
POSE_FEATURE_SHAPE = (3072, 31, 40, 22)
POSE_ENCODER_BATCH_LIMIT = 6


def load_prompt_context(path: str | Path):
    """Load and validate the frozen UMT5 output consumed by the DiT."""

    import torch

    try:
        from safetensors import safe_open
    except ImportError as exc:
        raise AssetError("safetensors is required to load prompt conditioning.") from exc

    resolved = Path(path).expanduser().resolve()
    try:
        with safe_open(str(resolved), framework="pt", device="cpu") as tensors:
            keys = tuple(tensors.keys())
            metadata = tensors.metadata() or {}
            if keys != (PROMPT_CONTEXT_KEY,):
                raise AssetError(f"Prompt conditioning must contain only {PROMPT_CONTEXT_KEY!r}, got {keys}.")
            context = tensors.get_tensor(PROMPT_CONTEXT_KEY)
    except AssetError:
        raise
    except Exception as exc:
        raise AssetError(f"Could not load prompt conditioning from {resolved}: {exc}") from exc

    expected_metadata = {
        "format": PROMPT_CONTEXT_FORMAT,
        "version": PROMPT_CONTEXT_VERSION,
        "prompt": INFERENCE.prompt,
        "source_repo": PROMPT_CONTEXT_SOURCE_REPO,
        "source_revision": PROMPT_CONTEXT_SOURCE_REVISION,
    }
    mismatched = {
        key: (metadata.get(key), expected)
        for key, expected in expected_metadata.items()
        if metadata.get(key) != expected
    }
    if mismatched:
        raise AssetError(f"Prompt conditioning metadata does not match the released method: {mismatched}.")
    for key in ("text_encoder_sha256", "tokenizer_manifest_sha256"):
        value = metadata.get(key, "")
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise AssetError(f"Prompt conditioning metadata has no valid {key} provenance hash.")
    if tuple(context.shape) != PROMPT_CONTEXT_SHAPE or context.dtype != torch.bfloat16:
        raise AssetError(
            "Prompt conditioning must be BF16 with shape "
            f"{PROMPT_CONTEXT_SHAPE}, got dtype={context.dtype}, shape={tuple(context.shape)}."
        )
    return context.contiguous()


@dataclass(frozen=True)
class PoseEncodingPlan:
    """Fixed-shape PoseEncoder batches for one ordered camera layout."""

    batch_size: int
    packed_views: int
    feature_groups: tuple[tuple[int, ...], ...]


def plan_pose_encoding(*, num_features: int, group_size: int, packed_views: int) -> PoseEncodingPlan:
    """Partition camera indices while reserving packed-view null inputs.

    Every PoseEncoder call uses the same batch shape.  This preserves the
    released CUDA convolution path while bounding full-resolution inputs to six
    videos.  Camera indices remain the only identity used after decoding.
    """

    if num_features <= 0:
        raise FourDAnyoneError(f"Pose conditioning requires at least one camera, got {num_features}.")
    if group_size <= 0 or num_features % group_size:
        raise FourDAnyoneError(
            f"Pose camera count {num_features} must be divisible by positive group size {group_size}."
        )
    if packed_views <= 0:
        raise FourDAnyoneError(f"Pose conditioning requires packed views, got {packed_views}.")

    batch_size = min(POSE_ENCODER_BATCH_LIMIT, group_size + packed_views)
    feature_capacity = batch_size - packed_views
    if feature_capacity <= 0:
        raise FourDAnyoneError(f"Pose batch limit {POSE_ENCODER_BATCH_LIMIT} cannot hold {packed_views} packed views.")
    groups = tuple(
        tuple(range(start, min(start + feature_capacity, num_features)))
        for start in range(0, num_features, feature_capacity)
    )
    return PoseEncodingPlan(batch_size=batch_size, packed_views=packed_views, feature_groups=groups)


@dataclass(frozen=True)
class PoseFeatureBank:
    """Owned CPU BF16 features in canonical camera-index order."""

    features: Tensor
    null_features: Tensor

    def __post_init__(self) -> None:
        import torch

        feature_shape = tuple(self.features.shape)
        null_shape = tuple(self.null_features.shape)
        if self.features.ndim != 5 or feature_shape[1:] != POSE_FEATURE_SHAPE:
            raise FourDAnyoneError(f"Pose features must have shape [views, {POSE_FEATURE_SHAPE}], got {feature_shape}.")
        if self.null_features.ndim != 5 or null_shape[1:] != POSE_FEATURE_SHAPE or null_shape[0] <= 0:
            raise FourDAnyoneError(
                f"Null pose features must have shape [packed_views, {POSE_FEATURE_SHAPE}], got {null_shape}."
            )
        if self.features.dtype != torch.bfloat16 or self.null_features.dtype != torch.bfloat16:
            raise FourDAnyoneError("Pose and null features must use BF16.")
        if self.features.device.type != "cpu" or self.null_features.device.type != "cpu":
            raise FourDAnyoneError("Pose feature banks must remain CPU-resident between denoising calls.")
        for label, tensor in (("pose", self.features), ("null pose", self.null_features)):
            exact_storage_bytes = tensor.numel() * tensor.element_size()
            if (
                not tensor.is_contiguous()
                or tensor.storage_offset() != 0
                or tensor.untyped_storage().nbytes() != exact_storage_bytes
            ):
                raise FourDAnyoneError(f"The {label} feature tensor must own one exact contiguous storage.")

    @property
    def num_features(self) -> int:
        return int(self.features.shape[0])

    @property
    def num_packed_views(self) -> int:
        return int(self.null_features.shape[0])

    def allocate_group(self, size: int, device: str) -> Tensor:
        """Allocate one reusable GPU group buffer."""

        import torch

        if size <= 0:
            raise FourDAnyoneError(f"A pose feature group must be non-empty, got {size}.")
        return torch.empty((size, *POSE_FEATURE_SHAPE), dtype=self.features.dtype, device=device)

    def copy_group(self, indices: tuple[int, ...], destination: Tensor) -> None:
        """Copy canonical camera features into a reusable device buffer."""

        if not indices:
            raise FourDAnyoneError("A pose feature group cannot be empty.")
        expected = (len(indices), *POSE_FEATURE_SHAPE)
        if tuple(destination.shape) != expected or destination.dtype != self.features.dtype:
            raise FourDAnyoneError(
                f"Pose destination must have dtype={self.features.dtype}, shape={expected}; "
                f"got dtype={destination.dtype}, shape={tuple(destination.shape)}."
            )
        invalid = tuple(index for index in indices if index < 0 or index >= self.num_features)
        if invalid:
            raise FourDAnyoneError(
                f"Pose feature indices {invalid} are outside camera range 0..{self.num_features - 1}."
            )
        for output_index, feature_index in enumerate(indices):
            destination[output_index].copy_(self.features[feature_index])

    def null_on(self, device: str) -> Tensor:
        return self.null_features.to(device=device)


@dataclass(frozen=True)
class PoseFeatureCache:
    """Pose features grouped by the RCP and target denoising layouts."""

    rcp: PoseFeatureBank | None
    target: PoseFeatureBank


def _encode_pose_batch(pose_encoder, videos):
    """Encode one bounded batch and return its CPU-resident BF16 features."""

    import torch

    with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        encoded = pose_encoder(videos)
    expected = (videos.shape[0], *POSE_FEATURE_SHAPE)
    if tuple(encoded.shape) != expected or encoded.dtype != torch.bfloat16:
        raise FourDAnyoneError(
            f"PoseEncoder returned dtype={encoded.dtype}, shape={tuple(encoded.shape)}; expected BF16 {expected}."
        )
    return encoded.detach().to(device="cpu").contiguous()


def _encode_pose_feature_set(
    *,
    pose_encoder,
    conditioning: Conditioning,
    skeletons: tuple[SkeletonVideo, ...],
    group_size: int,
    packed_views: int,
    device: str,
    channels_last: bool,
) -> PoseFeatureBank:
    """Encode poses in fixed-shape batches capped below the denoising group."""

    import torch

    plan = plan_pose_encoding(
        num_features=len(skeletons),
        group_size=group_size,
        packed_views=packed_views,
    )
    features = torch.empty(
        (len(skeletons), *POSE_FEATURE_SHAPE),
        dtype=torch.bfloat16,
        device="cpu",
    )
    null_features = torch.empty(
        (packed_views, *POSE_FEATURE_SHAPE),
        dtype=torch.bfloat16,
        device="cpu",
    )
    video_shape = None
    memory_format = torch.channels_last_3d if channels_last else torch.contiguous_format
    for group_index, feature_indices in enumerate(plan.feature_groups):
        batch = None
        for batch_index, feature_index in enumerate(feature_indices):
            skeleton = skeletons[feature_index]
            LOGGER.info("Loading skeleton conditioning from %s", skeleton.path.name)
            decoded = conditioning.load_skeleton_tensor([skeleton]).to(dtype=torch.bfloat16, device="cpu").contiguous()
            if decoded.ndim != 5 or decoded.shape[0] != 1:
                raise FourDAnyoneError(f"Expected one 5D skeleton tensor, got shape {tuple(decoded.shape)}.")
            current_shape = tuple(decoded.shape[1:])
            if video_shape is None:
                video_shape = current_shape
            elif current_shape != video_shape:
                raise FourDAnyoneError(
                    f"Skeleton {skeleton.path} has shape {tuple(decoded.shape)}, expected {(1, *video_shape)}."
                )
            if batch is None:
                batch = torch.empty(
                    (plan.batch_size, *video_shape),
                    dtype=torch.bfloat16,
                    device=device,
                    memory_format=memory_format,
                ).fill_(-1)
            batch[batch_index].copy_(decoded[0])
            del decoded

        encoded = _encode_pose_batch(pose_encoder, batch)
        for batch_index, feature_index in enumerate(feature_indices):
            features[feature_index].copy_(encoded[batch_index])
        if group_index == 0:
            null_start = len(feature_indices)
            null_features.copy_(encoded[null_start : null_start + packed_views])
        del batch, encoded

    return PoseFeatureBank(features=features, null_features=null_features)


def build_pose_feature_cache(
    *,
    conditioning: Conditioning,
    checkpoint_path: str | Path,
    device: str,
) -> PoseFeatureCache:
    """Encode every skeleton once before the full DiT is loaded.

    PoseEncoder has no cross-view operations.  Inputs are therefore split into
    fixed-shape batches of at most six videos, keeping the full-resolution peak
    bounded while preserving a stable CUDA convolution path.  Only compact
    output features are retained.
    """

    import torch

    from fdanyone.model.loader import load_pose_encoder

    view_plan = conditioning.view_plan
    if not conditioning.target_skeletons:
        raise FourDAnyoneError("Pose conditioning requires at least one skeleton video.")

    pose_encoder = load_pose_encoder(checkpoint_path, device)
    try:
        rcp = None
        if view_plan.enable_rcp:
            rcp = _encode_pose_feature_set(
                pose_encoder=pose_encoder,
                conditioning=conditioning,
                skeletons=conditioning.rcp_skeletons,
                group_size=view_plan.views_per_group,
                packed_views=1,
                device=device,
                channels_last=True,
            )
        target = _encode_pose_feature_set(
            pose_encoder=pose_encoder,
            conditioning=conditioning,
            skeletons=conditioning.target_skeletons,
            group_size=view_plan.views_per_group,
            packed_views=2 if view_plan.enable_rcp else 1,
            device=device,
            channels_last=False,
        )
    finally:
        del pose_encoder
        gc.collect()
        torch.cuda.empty_cache()

    return PoseFeatureCache(rcp=rcp, target=target)
