"""Dataset replay and explicit camera/time trajectories from a standalone model."""

from fractions import Fraction
from pathlib import Path

import cv2
import torch

from .checkpoint import load_render_model, render_config
from .data import staging_directory, write_json
from .losses import composite
from .rasterizer import Camera, render
from .trajectory import trajectory


@torch.no_grad()
def render_video(
    model_path, output, kind="orbit360", device="cuda", fixed_time=None, anchor=0, *, background="black", fps=None
):
    import av

    if background not in ("black", "white", "gray"):
        raise ValueError("Background must be black, white or gray")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Render output exists: {output}")
    payload, model = load_render_model(model_path, device)
    config = render_config(payload["config"])
    model.eval()
    records = trajectory(payload["cameras"], payload["times"], kind, fixed_time, anchor)
    rate = Fraction(str(fps)) if fps is not None else Fraction(payload["fps"])
    if rate <= 0:
        raise ValueError("Playback FPS must be positive")
    color = torch.full((3, 1, 1), {"black": 0.0, "white": 1.0, "gray": 0.5}[background], device=device)
    destination = output
    with staging_directory(destination) as output:
        write_json(output / "trajectory.json", records)
        first = records[0]["camera"]
        width, height = int(first["width"] * config["image_scale"]), int(first["height"] * config["image_scale"])
        with av.open(str(output / "rgb.mp4"), "w") as container:
            stream = container.add_stream("libx264", rate=rate)
            stream.width, stream.height = width, height
            stream.pix_fmt = "yuv420p" if width % 2 == 0 and height % 2 == 0 else "yuv444p"
            stream.options = {"crf": "18"}
            (output / "alpha").mkdir()
            for i, record in enumerate(records):
                rgb, alpha, _ = render(
                    model,
                    Camera(
                        record["camera"],
                        device,
                        far=config["far"],
                        image_scale=config["image_scale"],
                        near=config["near"],
                        space_scale=config["space_scale"],
                    ),
                    record["time"],
                    marginal_threshold=config["marginal_threshold"],
                )
                image = composite(rgb, alpha, color).clamp(0, 1).mul(255).round().byte().permute(1, 2, 0).cpu().numpy()
                if image.shape[:2] != (height, width):
                    raise ValueError("Video trajectory must use a fixed output raster")
                for packet in stream.encode(av.VideoFrame.from_ndarray(image, format="rgb24")):
                    container.mux(packet)
                if not cv2.imwrite(
                    str(output / "alpha" / f"{i:06d}.png"), alpha[0].clamp(0, 1).mul(255).round().byte().cpu().numpy()
                ):
                    raise OSError(f"Could not write alpha frame {i}")
            for packet in stream.encode():
                container.mux(packet)
        write_json(
            output / "render.json",
            dict(
                frames=len(records),
                fps=str(rate),
                training_fps=payload["fps"],
                time_sampling="nearest",
                background=background,
                step=payload["step"],
                model_size=Path(model_path).stat().st_size,
                model_mtime_ns=Path(model_path).stat().st_mtime_ns,
                points=len(model),
            ),
        )
