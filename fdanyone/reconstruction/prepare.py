"""Decode generated views and optionally infer foreground masks."""

import json
import shutil
from contextlib import closing
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from fdanyone.output_directory import read_output_metadata
from fdanyone.result_videos import read_target_videos

from .data import staging_directory, write_json


def make_masks(images, output, model_path, device):
    from PIL import Image

    from fdanyone.foreground import iter_foreground_masks

    paths = sorted(images.glob("*/*.jpg"))

    def frames():
        for path in paths:
            with Image.open(path) as image:
                frame = np.asarray(image.convert("RGB"))
            yield frame

    with closing(iter_foreground_masks(frames(), model_path, device)) as masks:
        for index, (path, mask) in enumerate(zip(paths, masks, strict=True), 1):
            target = output / path.relative_to(images).with_suffix(".png")
            target.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(mask).save(target)
            if index % 100 == 0 or index == len(paths):
                print(f"masks {index}/{len(paths)}", flush=True)


def prepare(result, output, masks=None, model_dir="models", device="cuda", *, source_id=None):
    import av

    result, output = Path(result).resolve(), Path(output).resolve()
    if output.exists() or result == output or result in output.parents:
        raise ValueError("Use a new output directory outside the source result")
    metadata = read_output_metadata(result)["output"]
    rig = json.loads((result / "cameras.json").read_text())
    if rig["camera_model"] != "OPENCV":
        raise ValueError("Expected OpenCV cameras")
    records = sorted(rig["cameras"], key=lambda c: c["camera_id"])
    fps, count = Fraction(metadata["fps"]), int(metadata["frames_per_video"])
    if len(records) != metadata["target_views"] or len({c["camera_id"] for c in records}) != len(records):
        raise ValueError("Target-camera inventory differs from metadata")
    if masks is None:
        from fdanyone.download import ensure_foreground_model

        model_path = ensure_foreground_model(model_dir)
    videos = read_target_videos(result, records)
    with staging_directory(output) as staging:
        shutil.copyfile(result / "cameras.json", staging / "cameras.json")
        for camera, video in zip(records, videos, strict=True):
            folder = staging / "images" / f"{camera['camera_id']:02d}"
            folder.mkdir(parents=True)
            decoded = 0
            with av.open(str(video)) as container:
                stream = container.streams.video[0]
                if stream.average_rate != fps:
                    raise ValueError(f"FPS mismatch: {video}")
                for index, frame in enumerate(container.decode(stream)):
                    image = frame.to_ndarray(format="bgr24")
                    if image.shape[:2] != (camera["image_height"], camera["image_width"]):
                        raise ValueError(f"Raster mismatch: {video}")
                    if frame.pts is None or Fraction(frame.pts) * frame.time_base != Fraction(index) / fps:
                        raise ValueError(f"PTS mismatch: {video}, frame {index}")
                    if not cv2.imwrite(str(folder / f"{index:06d}.jpg"), image, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                        raise OSError(f"Could not write decoded frame {index} from {video}")
                    decoded += 1
            if decoded != count:
                raise ValueError(f"Frame count mismatch: {video}")
        if masks is not None:
            shutil.copytree(masks, staging / "fmasks")
        else:
            make_masks(staging / "images", staging / "fmasks", model_path, device)
        write_json(
            staging / "metadata.json",
            dict(fps=str(fps), frames=[f"{i:06d}" for i in range(count)], source_identity=source_id),
        )
        from .data import TrainingData

        TrainingData(staging)
