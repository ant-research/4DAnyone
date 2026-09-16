"""Read clip timing and prepare native-resolution synchronized source previews."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import av

from fdanyone.config import INFERENCE
from fdanyone.errors import ConfigurationError, FourDAnyoneError
from fdanyone.video import _decode_frames, _rotation_degrees, _stream_rate, choose_canonical_fps, validate_clip_options


def _remux_source(source, destination, *, fps, indices, start_time, check_cancelled):
    """Keep the compressed frames when the entire input already matches the clip."""

    if start_time or (indices is not None and list(indices) != list(range(INFERENCE.num_frames))):
        return None
    with av.open(str(source)) as container:
        video = container.streams.video[0]
        rate = Fraction(fps or choose_canonical_fps(_stream_rate(video)))
        codec = video.codec_context
        if (
            codec.name != "h264"
            or codec.format is None
            or codec.format.name != "yuv420p"
            or video.frames != INFERENCE.num_frames
            or _stream_rate(video) != rate
            or _rotation_degrees(video)
            or video.width % 2
            or video.height % 2
        ):
            return None
        timestamps = []
        with av.open(str(destination), "w", options={"movflags": "+faststart"}) as output:
            stream = output.add_stream_from_template(video)
            for packet in container.demux(video):
                check_cancelled()
                if not packet.size:
                    continue
                if (
                    packet.pts is None
                    or packet.dts is None
                    or (not timestamps and not packet.is_keyframe)
                    or packet.duration * packet.time_base != 1 / rate
                ):
                    return None
                timestamps.append(packet.pts * packet.time_base)
                if len(timestamps) > INFERENCE.num_frames:
                    return None
                packet.stream = stream
                output.mux(packet)
        if sorted(timestamps) != [index / rate for index in range(INFERENCE.num_frames)]:
            return None
        return {
            "width": video.width,
            "height": video.height,
            "frames": INFERENCE.num_frames,
            "fps": str(rate),
            "source_indices": list(range(INFERENCE.num_frames)),
        }


def prepare_source(
    source: Path, cache_dir: Path, *, fps=None, indices=None, start_time=0.0, check_cancelled=lambda: None
):
    """Share source media across input, motion and result previews with the same timeline."""

    check_cancelled()
    source = source.resolve()
    if fps is None:
        with av.open(str(source)) as container:
            fps = choose_canonical_fps(_stream_rate(container.streams.video[0]))
    fps = Fraction(fps)
    stat = source.stat()
    identity = [1, str(source), stat.st_size, stat.st_mtime_ns, float(start_time), str(fps)]
    key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
    destination = cache_dir / "sources" / key / "source.mp4"
    if indices is not None:
        indices = [int(index) for index in indices]
    info_path = destination.with_suffix(".json")
    if destination.is_file() and info_path.is_file():
        info = json.loads(info_path.read_text())
        if indices is None or info["source_indices"] == indices:
            return {**info, "path": str(destination)}
    if indices is not None:
        # A saved motion can use a different sampling timeline. Keep both files
        # immutable so an open input preview continues to use its own frames.
        timeline = hashlib.sha256(json.dumps(indices).encode()).hexdigest()[:24]
        destination = destination.with_name(f"{timeline}.mp4")
    info = encode_source(
        source, destination, fps=fps, indices=indices, start_time=start_time, check_cancelled=check_cancelled
    )
    return {**info, "path": str(destination)}


def encode_source(
    source: Path,
    destination: Path,
    *,
    fps=None,
    indices=None,
    start_time=0.0,
    check_cancelled=lambda: None,
) -> dict:
    """Reuse matching compressed frames or resample with two decoded frames in memory."""

    info_path = destination.with_suffix(".json")
    if destination.is_file() and info_path.is_file():
        return json.loads(info_path.read_text())
    temporary = destination.with_name(f".{uuid.uuid4().hex}.mp4")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        info = _remux_source(
            source, temporary, fps=fps, indices=indices, start_time=start_time, check_cancelled=check_cancelled
        )
        if info is not None:
            temporary.replace(destination)
            info_path.write_text(json.dumps(info) + "\n")
            return info
        with (
            av.open(str(source)) as container,
            av.open(str(temporary), "w", options={"movflags": "+faststart"}) as output,
        ):
            video = container.streams.video[0]
            fps = fps or choose_canonical_fps(_stream_rate(video))
            frames = iter(_decode_frames(container, video, _rotation_degrees(video)))
            previous = next(frames)
            height, width = previous.rgb.shape[:2]
            size = max(2, round(width / 2) * 2), max(2, round(height / 2) * 2)
            stream = output.add_stream("libx264", rate=fps)
            stream.width, stream.height = size
            stream.pix_fmt = "yuv420p"
            stream.codec_context.max_b_frames = 0
            stream.codec_context.gop_size = max(1, round(fps))
            stream.options = {"crf": "18", "preset": "veryfast"}
            count = 0
            source_indices = []

            def write(frame):
                nonlocal count
                check_cancelled()
                resized = av.VideoFrame.from_ndarray(frame.rgb, format="rgb24").reformat(
                    width=size[0], height=size[1], format="yuv420p"
                )
                resized.pts = count
                resized.time_base = 1 / fps
                for packet in stream.encode(resized):
                    output.mux(packet)
                source_indices.append(frame.index)
                count += 1

            if indices is not None:
                indices = list(indices)
                current = previous
                while count < len(indices):
                    check_cancelled()
                    if current.index == indices[count]:
                        write(current)
                    elif current.index < indices[count]:
                        current = next(frames)
                    else:
                        raise FourDAnyoneError("The source video does not match the saved motion timeline.")
            else:
                origin = float(previous.timestamp) + start_time
                current = previous
                for current in frames:
                    check_cancelled()
                    while count < INFERENCE.num_frames and origin + count / float(fps) <= float(current.timestamp):
                        target = origin + count / float(fps)
                        write(
                            previous
                            if abs(float(previous.timestamp) - target) <= abs(float(current.timestamp) - target)
                            else current
                        )
                    if count == INFERENCE.num_frames:
                        break
                    previous = current
                if count < INFERENCE.num_frames and abs(
                    float(current.timestamp) - (origin + count / float(fps))
                ) <= 0.75 / float(fps):
                    write(current)
            if not count:
                raise FourDAnyoneError("No source frames are available after Clip Start.")
            for packet in stream.encode():
                output.mux(packet)
        info = {
            "width": size[0],
            "height": size[1],
            "frames": count,
            "fps": str(fps),
            "source_indices": source_indices,
        }
        temporary.replace(destination)
        info_path.write_text(json.dumps(info) + "\n")
        return info
    except (StopIteration, IndexError) as exc:
        raise FourDAnyoneError("The original source clip is missing required frames.") from exc
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class ClipTiming:
    source_fps: Fraction
    duration: Fraction | None

    @classmethod
    def read(cls, path: Path | None):
        """Read the selected video's header once, without decoding its frames."""
        if path is None:
            return None
        try:
            with av.open(str(path)) as container:
                stream = container.streams.video[0]
                rate = stream.average_rate or stream.guessed_rate or stream.base_rate
                if rate is None or rate <= 0:
                    return None
                duration = stream.duration * stream.time_base if stream.duration is not None else None
                if duration is None and stream.frames:
                    duration = Fraction(stream.frames) / rate
                if duration is None and container.duration is not None:
                    duration = Fraction(container.duration, av.time_base)
                return cls(Fraction(rate), Fraction(duration) if duration is not None else None)
        except (OSError, ValueError, IndexError):
            return None

    def start_max(self, target_fps) -> float:
        rate = validate_clip_options(
            start_time=0, fps=None if str(target_fps).strip().lower() == "auto" else target_fps
        ) or choose_canonical_fps(self.source_fps)
        if self.duration is None:
            return 0.0
        # The last frame's timestamp precedes the container's end by one source
        # frame. Round down so the slider endpoint still contains all 121 frames.
        last = self.duration - 1 / self.source_fps
        maximum = max(Fraction(0), last - Fraction(INFERENCE.num_frames - 1) / rate)
        return float(maximum * 100 // 1) / 100


def probe_input(video: Path, start_time: float, target_fps="auto") -> None:
    """Reject unreadable or short clips before queuing GPU work."""
    rate = validate_clip_options(
        start_time=start_time,
        fps=None if str(target_fps).lower() == "auto" else target_fps,
    )
    timing = ClipTiming.read(video)
    if timing is None:
        raise ConfigurationError("Cannot read the source video's frame rate.")
    needed = (INFERENCE.num_frames - 1) / float(rate or choose_canonical_fps(timing.source_fps))
    if timing.duration is not None and float(timing.duration) - start_time <= needed:
        raise ConfigurationError(
            f"Need 121 frames after the selected start, about {needed:.2f} seconds. "
            "Choose an earlier start or a longer video."
        )
