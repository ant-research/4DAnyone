"""Frozen, timestep-independent conditioning used by the denoiser."""

from __future__ import annotations

import gc
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import Event
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


@dataclass(frozen=True)
class _PoseEncodingJob:
    """One complete fixed-shape PoseEncoder call."""

    feature_indices: tuple[int, ...]
    skeletons: tuple[SkeletonVideo, ...]
    batch_size: int
    packed_views: int
    channels_last: bool
    builder: _PoseFeatureBuilder


@dataclass
class _PoseFeatureBuilder:
    """Gather independently computed batches into canonical camera order."""

    features: Tensor
    null_features: Tensor

    @classmethod
    def create(cls, num_features: int, packed_views: int) -> _PoseFeatureBuilder:
        import torch

        return cls(
            features=torch.empty((num_features, *POSE_FEATURE_SHAPE), dtype=torch.bfloat16, device="cpu"),
            null_features=torch.empty((packed_views, *POSE_FEATURE_SHAPE), dtype=torch.bfloat16, device="cpu"),
        )

    def store(self, job: _PoseEncodingJob, encoded: Tensor) -> None:
        for batch_index, feature_index in enumerate(job.feature_indices):
            self.features[feature_index].copy_(encoded[batch_index])
        if job.feature_indices[0] == 0:
            null_start = len(job.feature_indices)
            self.null_features.copy_(encoded[null_start : null_start + job.packed_views])

    def build(self) -> PoseFeatureBank:
        return PoseFeatureBank(features=self.features, null_features=self.null_features)


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


def _pose_jobs(
    *,
    skeletons: tuple[SkeletonVideo, ...],
    group_size: int,
    packed_views: int,
    channels_last: bool,
) -> tuple[tuple[_PoseEncodingJob, ...], _PoseFeatureBuilder]:
    """Plan complete fixed-shape calls and their canonical output owner."""

    plan = plan_pose_encoding(
        num_features=len(skeletons),
        group_size=group_size,
        packed_views=packed_views,
    )
    builder = _PoseFeatureBuilder.create(len(skeletons), packed_views)
    jobs = tuple(
        _PoseEncodingJob(
            feature_indices=indices,
            skeletons=tuple(skeletons[index] for index in indices),
            batch_size=plan.batch_size,
            packed_views=packed_views,
            channels_last=channels_last,
            builder=builder,
        )
        for indices in plan.feature_groups
    )
    return jobs, builder


def _execute_pose_job(
    *,
    job: _PoseEncodingJob,
    pose_encoder,
    conditioning: Conditioning,
    device: str,
) -> None:
    """Decode, encode, and gather one bounded pose batch."""

    import torch

    video_shape = None
    batch = None
    memory_format = torch.channels_last_3d if job.channels_last else torch.contiguous_format
    for batch_index, skeleton in enumerate(job.skeletons):
        LOGGER.info("Loading skeleton conditioning from %s", skeleton.path.name)
        decoded = conditioning.load_skeleton_tensor([skeleton]).to(dtype=torch.bfloat16, device="cpu").contiguous()
        if decoded.ndim != 5 or decoded.shape[0] != 1:
            raise FourDAnyoneError(f"Expected one 5D skeleton tensor, got shape {tuple(decoded.shape)}.")
        current_shape = tuple(decoded.shape[1:])
        if video_shape is None:
            video_shape = current_shape
            batch = torch.empty(
                (job.batch_size, *video_shape),
                dtype=torch.bfloat16,
                device=device,
                memory_format=memory_format,
            ).fill_(-1)
        elif current_shape != video_shape:
            raise FourDAnyoneError(
                f"Skeleton {skeleton.path} has shape {tuple(decoded.shape)}, expected {(1, *video_shape)}."
            )
        batch[batch_index].copy_(decoded[0])
        del decoded

    encoded = _encode_pose_batch(pose_encoder, batch)
    job.builder.store(job, encoded)
    del batch, encoded


def build_pose_feature_cache(
    *,
    conditioning: Conditioning,
    checkpoint_path: str | Path,
    devices: tuple[str, ...],
) -> PoseFeatureCache:
    """Encode all fixed-shape pose jobs on an ordered CUDA device pool.

    One worker owns one PoseEncoder and one full-resolution batch at a time.
    This bounds host/device memory while independent jobs execute concurrently;
    builders restore canonical camera order regardless of completion order.
    """

    import torch

    from fdanyone.model.loader import load_pose_encoder

    view_plan = conditioning.view_plan
    if not conditioning.target_skeletons:
        raise FourDAnyoneError("Pose conditioning requires at least one skeleton video.")
    if not devices:
        raise FourDAnyoneError("Pose conditioning requires at least one CUDA device.")

    rcp_jobs: tuple[_PoseEncodingJob, ...] = ()
    rcp_builder = None
    if view_plan.enable_rcp:
        rcp_jobs, rcp_builder = _pose_jobs(
            skeletons=conditioning.rcp_skeletons,
            group_size=view_plan.views_per_group,
            packed_views=1,
            channels_last=True,
        )
    target_jobs, target_builder = _pose_jobs(
        skeletons=conditioning.target_skeletons,
        group_size=view_plan.views_per_group,
        packed_views=2 if view_plan.enable_rcp else 1,
        channels_last=False,
    )
    jobs = (*rcp_jobs, *target_jobs)
    worker_count = min(len(jobs), len(devices))
    stopped = Event()
    prototype = load_pose_encoder(checkpoint_path, "cpu")
    pose_encoders = [prototype]
    pose_encoders.extend(deepcopy(prototype) for _ in range(worker_count - 1))

    def run(worker_index: int) -> None:
        device = devices[worker_index]
        device_index = int(device.removeprefix("cuda:"))
        torch.cuda.set_device(device_index)
        pose_encoder = pose_encoders[worker_index]
        try:
            pose_encoder.to(device)
            for job in jobs[worker_index::worker_count]:
                if stopped.is_set():
                    return
                _execute_pose_job(
                    job=job,
                    pose_encoder=pose_encoder,
                    conditioning=conditioning,
                    device=device,
                )
        except BaseException:
            stopped.set()
            raise
        finally:
            pose_encoder.to("cpu")
            torch.cuda.empty_cache()

    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="pose") as pool:
        futures = [pool.submit(run, worker_index) for worker_index in range(worker_count)]
        try:
            for future in as_completed(futures):
                future.result()
        except BaseException:
            stopped.set()
            for future in futures:
                future.cancel()
            raise

    pose_encoders.clear()
    gc.collect()
    return PoseFeatureCache(
        rcp=None if rcp_builder is None else rcp_builder.build(),
        target=target_builder.build(),
    )
