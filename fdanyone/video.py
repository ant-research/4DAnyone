"""PTS-aware canonical video decoding and encoding."""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from fdanyone.config import INFERENCE
from fdanyone.errors import VideoContractError

AUTO_DOWNSAMPLE_FPS = tuple(
    Fraction(numerator, denominator) for numerator, denominator in INFERENCE.auto_downsample_fps
)
SAMPLING_POLICY = INFERENCE.temporal_sampling_policy
INTEGER_RATIO_TOLERANCE = 1e-3


def validate_required_video_codecs() -> None:
    missing = []
    for codec in ("libx264", "libx264rgb"):
        try:
            av.codec.Codec(codec, "w")
        except (ValueError, av.FFmpegError):
            missing.append(codec)
    if missing:
        raise VideoContractError(
            f"The installed FFmpeg/PyAV build lacks required video encoders: {missing}. "
            "Install a PyAV build with libx264 and libx264rgb support."
        )


def choose_canonical_fps(input_rate: Fraction) -> Fraction:
    """Keep the source rate unless it supports clean integer downsampling.

    High-frame-rate sources may be reduced to an exact 24/25/30-family
    divisor (48 -> 24, 50 -> 25, 60 -> 30, 120 -> 30). Rates without such a
    divisor, including 40 FPS, are preserved exactly.
    """

    if input_rate <= 0:
        raise VideoContractError(f"Input frame rate must be positive, got {input_rate}.")

    divisible: list[tuple[Fraction, int]] = []
    for candidate in AUTO_DOWNSAMPLE_FPS:
        ratio = float(input_rate / candidate)
        multiple = round(ratio)
        if multiple >= 2 and abs(ratio - multiple) <= INTEGER_RATIO_TOLERANCE:
            divisible.append((candidate, multiple))
    if divisible:
        _, multiple = max(divisible, key=lambda match: float(match[0]))
        return input_rate / multiple

    return input_rate


def _stream_rate(stream: av.video.stream.VideoStream) -> Fraction:
    for value in (stream.average_rate, stream.guessed_rate, stream.base_rate):
        if value is not None and value > 0:
            return Fraction(value.numerator, value.denominator)
    raise VideoContractError("The input video does not declare a usable frame rate.")


def _normalize_rotation_degrees(raw: object) -> int:
    """Normalize a display-matrix rotation to a supported CCW quarter turn."""

    try:
        rotation = int(round(float(raw))) % 360
    except (TypeError, ValueError):
        rotation = 0
    if rotation not in (0, 90, 180, 270):
        raise VideoContractError(f"Unsupported video rotation metadata: {raw!r} degrees.")
    return rotation


def _rotation_degrees(stream: av.video.stream.VideoStream) -> int:
    return _normalize_rotation_degrees(stream.metadata.get("rotate", "0"))


def _frame_rotation_degrees(frame: av.VideoFrame, metadata_rotation: int) -> int:
    """Prefer FFmpeg display-matrix side data over the legacy rotate tag."""

    frame_rotation = getattr(frame, "rotation", 0)
    if frame_rotation is None or float(frame_rotation) == 0.0:
        return metadata_rotation
    return _normalize_rotation_degrees(frame_rotation)


def _frame_timestamp(frame: av.VideoFrame, stream: av.video.stream.VideoStream, index: int) -> Fraction:
    if frame.pts is not None and frame.time_base is not None:
        return Fraction(frame.pts * frame.time_base)
    rate = _stream_rate(stream)
    return Fraction(index, 1) / rate


def _frame_to_rgb(frame: av.VideoFrame, rotation_degrees: int) -> np.ndarray:
    rgb = frame.to_ndarray(format="rgb24")
    if rotation_degrees == 90:
        rgb = np.rot90(rgb, k=1)
    elif rotation_degrees == 180:
        rgb = np.rot90(rgb, k=2)
    elif rotation_degrees == 270:
        rgb = np.rot90(rgb, k=3)
    return np.ascontiguousarray(rgb)


@dataclass(frozen=True)
class CanonicalFrame:
    rgb: np.ndarray
    source_index: int
    source_pts: int | None
    source_timestamp: Fraction
    canonical_timestamp: Fraction


@dataclass(frozen=True)
class ClipInfo:
    """Input provenance and raster information without decoded pixel storage."""

    source_path: Path
    fps: Fraction
    start_time: Fraction
    num_frames: int
    height: int
    width: int

    @property
    def fps_num(self) -> int:
        return self.fps.numerator

    @property
    def fps_den(self) -> int:
        return self.fps.denominator


@dataclass(frozen=True)
class CanonicalClip:
    source_path: Path
    source_size_bytes: int
    source_mtime_ns: int
    fps: Fraction
    input_rate: Fraction
    source_time_base: Fraction
    start_time: Fraction
    frames: tuple[CanonicalFrame, ...]
    rotation_degrees: int

    @property
    def info(self) -> ClipInfo:
        return ClipInfo(
            source_path=self.source_path,
            fps=self.fps,
            start_time=self.start_time,
            num_frames=len(self.frames),
            height=self.height,
            width=self.width,
        )

    @property
    def height(self) -> int:
        return int(self.frames[0].rgb.shape[0])

    @property
    def width(self) -> int:
        return int(self.frames[0].rgb.shape[1])

    @property
    def fps_num(self) -> int:
        return self.fps.numerator

    @property
    def fps_den(self) -> int:
        return self.fps.denominator

    @property
    def rgb_frames(self) -> tuple[np.ndarray, ...]:
        return tuple(frame.rgb for frame in self.frames)

    def metadata(self) -> dict:
        return {
            # The subprocess boundary only needs source identity, not a
            # machine-specific absolute path. Keep the file-protocol payload
            # safe to share by storing the basename.
            "source_path": self.source_path.name,
            "source_size_bytes": self.source_size_bytes,
            "source_mtime_ns": self.source_mtime_ns,
            "fps_num": self.fps_num,
            "fps_den": self.fps_den,
            "input_rate_num": self.input_rate.numerator,
            "input_rate_den": self.input_rate.denominator,
            "source_time_base_num": self.source_time_base.numerator,
            "source_time_base_den": self.source_time_base.denominator,
            "start_time_num": self.start_time.numerator,
            "start_time_den": self.start_time.denominator,
            "sampling_policy": SAMPLING_POLICY,
            "num_frames": len(self.frames),
            "height": self.height,
            "width": self.width,
            "rotation_degrees_applied": self.rotation_degrees,
            "frames": [
                {
                    "canonical_index": index,
                    "canonical_timestamp_sec": float(frame.canonical_timestamp),
                    "source_index": frame.source_index,
                    "source_pts": frame.source_pts,
                    "source_timestamp_sec": float(frame.source_timestamp),
                }
                for index, frame in enumerate(self.frames)
            ],
        }

    def write_metadata(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.metadata(), indent=2, sort_keys=True) + "\n")


@dataclass(frozen=True)
class _DecodedFrame:
    rgb: np.ndarray
    index: int
    pts: int | None
    timestamp: Fraction
    time_base: Fraction
    rotation_degrees: int


def _decode_frames(
    container: av.container.InputContainer,
    stream: av.video.stream.VideoStream,
    rotation: int,
) -> Iterator[_DecodedFrame]:
    observed_rotation = None
    for index, frame in enumerate(container.decode(stream)):
        frame_rotation = _frame_rotation_degrees(frame, rotation)
        if observed_rotation is None:
            observed_rotation = frame_rotation
        elif frame_rotation != observed_rotation:
            raise VideoContractError(
                f"Video display rotation changes at frame {index}: {observed_rotation} -> {frame_rotation}."
            )
        yield _DecodedFrame(
            rgb=_frame_to_rgb(frame, frame_rotation),
            index=index,
            pts=frame.pts,
            timestamp=_frame_timestamp(frame, stream, index),
            time_base=(
                Fraction(frame.time_base)
                if frame.time_base is not None
                else Fraction(stream.time_base)
                if stream.time_base is not None
                else Fraction(1, 1) / _stream_rate(stream)
            ),
            rotation_degrees=frame_rotation,
        )


def validate_clip_options(
    *,
    start_time: float,
    fps: str | int | float | Fraction | None,
) -> Fraction | None:
    """Validate clip options without video I/O and normalize the requested FPS."""

    if not math.isfinite(start_time) or start_time < 0:
        raise VideoContractError(f"start_time must be non-negative, got {start_time}.")
    if fps is None:
        return None
    try:
        rate = Fraction(str(fps))
    except (ValueError, ZeroDivisionError) as exc:
        raise VideoContractError(f"Cannot parse target fps {fps!r} as a rational frame rate.") from exc
    if rate <= 0:
        raise VideoContractError(f"Target fps must be positive, got {rate}.")
    return rate


def decode_canonical_clip(
    video_path: str | Path,
    *,
    num_frames: int = 121,
    start_time: float = 0.0,
    fps: str | int | float | Fraction | None = None,
) -> CanonicalClip:
    """Decode one canonical clip, selecting frames by source presentation time."""

    path = Path(video_path).expanduser().resolve()
    if not path.is_file():
        raise VideoContractError(f"Input video does not exist: {path}")
    if num_frames <= 0:
        raise VideoContractError(f"num_frames must be positive, got {num_frames}.")
    fps = validate_clip_options(start_time=start_time, fps=fps)

    source_stat = path.stat()

    with av.open(str(path), mode="r") as container:
        if not container.streams.video:
            raise VideoContractError(f"Input has no video stream: {path}")
        stream = container.streams.video[0]
        input_rate = _stream_rate(stream)
        output_rate = choose_canonical_fps(input_rate) if fps is None else fps
        metadata_rotation = _rotation_degrees(stream)
        decoded = _decode_frames(container, stream, metadata_rotation)
        try:
            previous = next(decoded)
        except StopIteration as exc:
            raise VideoContractError(f"Input video contains no decodable frames: {path}") from exc

        origin = previous.timestamp
        start_offset = Fraction(str(start_time))
        start = origin + start_offset
        targets = [start + Fraction(index, 1) / output_rate for index in range(num_frames)]
        selected: list[_DecodedFrame] = []
        target_index = 0
        current = previous

        for current in decoded:
            if current.timestamp < previous.timestamp:
                raise VideoContractError(
                    f"Input presentation timestamps are not monotonic at source frame {current.index}: "
                    f"{float(current.timestamp):.6f}s < {float(previous.timestamp):.6f}s."
                )
            while target_index < num_frames and targets[target_index] <= current.timestamp:
                target = targets[target_index]
                candidate = previous if abs(previous.timestamp - target) <= abs(current.timestamp - target) else current
                if selected and candidate.index < selected[-1].index:
                    raise VideoContractError("Temporal sampling produced non-monotonic source-frame order.")
                selected.append(candidate)
                target_index += 1
            if target_index >= num_frames:
                break
            previous = current

        max_error = Fraction(3, 4) / output_rate
        if target_index < num_frames:
            # A faster canonical clock can legitimately select the final source
            # frame more than once, just as it may reuse frames in the middle of
            # the clip. Stop once the nearest-frame error exceeds the same gap
            # bound enforced below; that remains a short-input failure rather
            # than temporal padding.
            while target_index < num_frames and abs(current.timestamp - targets[target_index]) <= max_error:
                if selected and current.index < selected[-1].index:
                    raise VideoContractError("Temporal sampling produced non-monotonic source-frame order.")
                selected.append(current)
                target_index += 1

        if len(selected) != num_frames:
            duration = float(current.timestamp - origin)
            required = float(Fraction(num_frames - 1, 1) / output_rate + start_offset)
            raise VideoContractError(
                f"Input is too short for {num_frames} frames at {float(output_rate):.6f} FPS from "
                f"start_time={start_time}: decoded duration={duration:.3f}s, required={required:.3f}s."
            )

        errors = [abs(frame.timestamp - target) for frame, target in zip(selected, targets, strict=True)]
        if max(errors) > max_error:
            raise VideoContractError(
                "Input timestamps contain a gap too large for stable sampling: "
                f"max error={float(max(errors)):.6f}s, limit={float(max_error):.6f}s."
            )
        expected_shape = selected[0].rgb.shape
        if any(frame.rgb.shape != expected_shape for frame in selected[1:]):
            raise VideoContractError("Input frame dimensions change inside the selected canonical clip.")
        source_time_base = selected[0].time_base
        if any(frame.time_base != source_time_base for frame in selected[1:]):
            raise VideoContractError("Input frame time base changes inside the selected canonical clip.")

        canonical_frames = tuple(
            CanonicalFrame(
                rgb=frame.rgb,
                source_index=frame.index,
                source_pts=frame.pts,
                source_timestamp=frame.timestamp,
                canonical_timestamp=Fraction(index, 1) / output_rate,
            )
            for index, frame in enumerate(selected)
        )

    final_stat = path.stat()
    if (final_stat.st_size, final_stat.st_mtime_ns) != (source_stat.st_size, source_stat.st_mtime_ns):
        raise VideoContractError(f"Input video changed while it was being decoded: {path}")
    return CanonicalClip(
        source_path=path,
        source_size_bytes=source_stat.st_size,
        source_mtime_ns=source_stat.st_mtime_ns,
        fps=output_rate,
        input_rate=input_rate,
        source_time_base=source_time_base,
        start_time=start_offset,
        frames=canonical_frames,
        rotation_degrees=selected[0].rotation_degrees,
    )


def write_lossless_video(clip: CanonicalClip, path: str | Path) -> Path:
    """Write an FFV1 working video. A subsequent decode must be RGB-identical."""

    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(output_path), mode="w", format="matroska") as container:
        stream = container.add_stream("ffv1", rate=clip.fps)
        stream.width = clip.width
        stream.height = clip.height
        # FFV1 does not expose 8-bit GBR planar. BGR0 is an exact 8-bit RGB
        # representation (the fourth byte is padding) and round-trips to rgb24.
        stream.pix_fmt = "bgr0"
        for index, canonical_frame in enumerate(clip.frames):
            frame = av.VideoFrame.from_ndarray(canonical_frame.rgb, format="rgb24")
            frame.pts = index
            frame.time_base = Fraction(1, 1) / clip.fps
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    verify_lossless_video(clip, output_path)
    return output_path


def write_gvhmr_video(clip: CanonicalClip, path: str | Path) -> Path:
    """Write the frame-counted, RGB-lossless MP4 consumed by GVHMR.

    GVHMR's imageio metadata probe cannot determine the frame count of an
    FFV1 Matroska stream. ``libx264rgb`` in lossless mode preserves every RGB
    byte while placing an exact frame count in the MP4 index.
    """

    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(output_path), mode="w") as container:
        stream = container.add_stream("libx264rgb", rate=clip.fps)
        stream.width = clip.width
        stream.height = clip.height
        stream.pix_fmt = "rgb24"
        stream.options = {"crf": "0", "preset": "medium"}
        for index, canonical_frame in enumerate(clip.frames):
            frame = av.VideoFrame.from_ndarray(canonical_frame.rgb, format="rgb24")
            frame.pts = index
            frame.time_base = Fraction(1, 1) / clip.fps
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    verify_lossless_video(clip, output_path)
    with av.open(str(output_path), mode="r") as container:
        declared_frames = int(container.streams.video[0].frames)
    if declared_frames != len(clip.frames):
        raise VideoContractError(
            f"Backend MP4 declares {declared_frames} frames, expected {len(clip.frames)}: {output_path}."
        )
    return output_path


def verify_lossless_video(clip: CanonicalClip, path: str | Path) -> None:
    decoded = iter_rgb_video(path)
    sentinel = object()
    for index, (actual, expected) in enumerate(itertools.zip_longest(decoded, clip.rgb_frames, fillvalue=sentinel)):
        if actual is sentinel or expected is sentinel or not np.array_equal(actual, expected):
            raise VideoContractError(f"Lossless working-video verification failed at frame {index}.")


def write_video(
    frames: Iterator[np.ndarray] | tuple[np.ndarray, ...],
    path: str | Path,
    fps: Fraction,
    *,
    crf: int = 18,
    preset: str = "medium",
) -> Path:
    """Encode RGB frames as a broadly playable H.264 MP4."""

    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    iterator = iter(frames)
    try:
        first = next(iterator)
    except StopIteration as exc:
        raise VideoContractError("Cannot encode an empty video.") from exc
    height, width = first.shape[:2]
    with av.open(str(output_path), mode="w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width = width
        stream.height = height
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": str(crf), "preset": preset}
        for index, rgb in enumerate(itertools.chain((first,), iterator)):
            if rgb.shape != first.shape:
                raise VideoContractError(f"Frame {index} has shape {rgb.shape}, expected {first.shape}.")
            frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(rgb), format="rgb24")
            frame.pts = index
            frame.time_base = Fraction(1, 1) / fps
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return output_path


def iter_rgb_video(path: str | Path) -> Iterator[np.ndarray]:
    """Stream RGB frames without interpreting or resampling timestamps."""

    video_path = Path(path).expanduser().resolve()
    with av.open(str(video_path), mode="r") as container:
        if not container.streams.video:
            raise VideoContractError(f"Video has no stream: {video_path}")
        for frame in container.decode(container.streams.video[0]):
            yield np.ascontiguousarray(frame.to_ndarray(format="rgb24"))


def read_rgb_video(path: str | Path, *, expected_frames: int | None = None) -> tuple[np.ndarray, ...]:
    """Decode an RGB video without interpreting or resampling its timestamps."""

    frames = tuple(iter_rgb_video(path))
    if expected_frames is not None and len(frames) != expected_frames:
        raise VideoContractError(
            f"{Path(path).expanduser().resolve()} has {len(frames)} frames, expected {expected_frames}."
        )
    return frames


def load_canonical_working_clip(video_path: str | Path, metadata_path: str | Path) -> CanonicalClip:
    """Rehydrate the canonical clip inside a short-lived worker."""

    video_path = Path(video_path).expanduser().resolve()
    metadata = json.loads(Path(metadata_path).read_text())
    if metadata.get("sampling_policy") != SAMPLING_POLICY:
        raise VideoContractError(f"Unsupported canonical sampling policy: {metadata.get('sampling_policy')!r}.")
    records = metadata["frames"]
    decoded = read_rgb_video(video_path, expected_frames=int(metadata["num_frames"]))
    if len(records) != len(decoded):
        raise VideoContractError(
            f"Canonical metadata has {len(records)} frame records, but {video_path} has {len(decoded)} frames."
        )
    frames = []
    for canonical_index, (rgb, record) in enumerate(zip(decoded, records, strict=True)):
        if int(record["canonical_index"]) != canonical_index:
            raise VideoContractError("Canonical subprocess metadata is not in frame-index order.")
        frames.append(
            CanonicalFrame(
                rgb=rgb,
                source_index=int(record["source_index"]),
                source_pts=None if record["source_pts"] is None else int(record["source_pts"]),
                source_timestamp=Fraction(str(record["source_timestamp_sec"])),
                canonical_timestamp=Fraction(canonical_index, 1)
                / Fraction(int(metadata["fps_num"]), int(metadata["fps_den"])),
            )
        )
    return CanonicalClip(
        source_path=Path(metadata["source_path"]),
        source_size_bytes=int(metadata["source_size_bytes"]),
        source_mtime_ns=int(metadata["source_mtime_ns"]),
        fps=Fraction(int(metadata["fps_num"]), int(metadata["fps_den"])),
        input_rate=Fraction(int(metadata["input_rate_num"]), int(metadata["input_rate_den"])),
        source_time_base=Fraction(int(metadata["source_time_base_num"]), int(metadata["source_time_base_den"])),
        start_time=Fraction(int(metadata["start_time_num"]), int(metadata["start_time_den"])),
        frames=tuple(frames),
        rotation_degrees=int(metadata["rotation_degrees_applied"]),
    )
