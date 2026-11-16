"""Read-only Gaussian playback on one CUDA worker, with bounded temporal caches."""

import time
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path

import cv2
import torch

from ..checkpoint import load_render_model, render_config
from ..gaussian import evaluate_conditional
from ..losses import composite
from ..rasterizer import Camera, render
from .camera import initial_pose
from .grid import GroundGrid


class PlaybackModel:
    def __init__(self, model, threshold, cache_bytes=64 * 1024**2):
        self.model = model
        self.xyz = model.xyz
        self.conditional = model.covariance(packed=True)
        self.threshold, self.cache_bytes = threshold, cache_bytes
        self.indices = OrderedDict()
        self.used_bytes = 0

    def evaluate(self, time, camera_center, threshold, visibility=None, packed=False):
        if not packed or threshold != self.threshold:
            raise ValueError("Playback requires packed covariance and the saved temporal threshold")
        indices = self.indices.pop(time, None)
        if indices is None:
            marginal = torch.exp(-0.5 * (time - self.model.time).square() / self.conditional[2])
            indices = torch.where(marginal[:, 0] > threshold)[0]
            size = indices.numel() * indices.element_size()
            while self.indices and self.used_bytes + size > self.cache_bytes:
                _, old = self.indices.popitem(last=False)
                self.used_bytes -= old.numel() * old.element_size()
            if size <= self.cache_bytes:
                self.used_bytes += size
                self.indices[time] = indices
        else:
            self.indices[time] = indices
        return evaluate_conditional(self.model, self.conditional, time, camera_center, threshold, visibility, indices)


class Renderer:
    def __init__(self, model_path, device="cuda", title=None, *, ground_grid=True):
        if not str(device).startswith("cuda"):
            raise ValueError("The interactive renderer requires CUDA")
        device = torch.device(device)
        if device.index is None:
            device = torch.device("cuda", torch.cuda.current_device())
        torch.cuda.set_device(device)
        torch.set_num_threads(4)
        self.device = device
        self.started = time.perf_counter()
        payload, model = load_render_model(model_path, device)
        self.config = render_config(payload["config"])
        self.cameras, self.times = payload["cameras"], payload["times"]
        self.fps, self.step = float(Fraction(payload["fps"])), payload["step"]
        if not self.times or self.fps <= 0:
            raise ValueError("Checkpoint timeline is empty or invalid")
        self.title = title or Path(model_path).stem
        del payload
        model.eval().requires_grad_(False)
        with torch.inference_mode():
            self.model = PlaybackModel(model, self.config["marginal_threshold"])
        self.pose = initial_pose(self.cameras)
        self.grid = GroundGrid.from_model(model, self.cameras, self.config["space_scale"]) if ground_grid else None
        self.last_camera = None
        self.camera_key = None
        self.metadata = dict(
            title=self.title,
            frames=len(self.times),
            fps=self.fps,
            times=self.times,
            width=self.cameras[0]["width"],
            height=self.cameras[0]["height"],
            points=len(model),
            step=self.step,
            camera=self.pose,
        )

    @torch.inference_mode()
    def tensors(self, camera, frame):
        key = repr(camera)
        if key != self.camera_key:
            self.last_camera = Camera(
                camera,
                self.device,
                image_scale=1.0,
                space_scale=self.config["space_scale"],
                near=self.config["near"],
                far=self.config["far"],
            )
            self.camera_key = key
        rgb, alpha, _ = render(
            self.model, self.last_camera, self.times[frame], marginal_threshold=self.config["marginal_threshold"]
        )
        return rgb, alpha

    @torch.inference_mode()
    def image(self, request):
        started = time.perf_counter()
        rgb, alpha = self.tensors(request["camera"], request["frame"])
        value = {"black": 0.0, "gray": 0.5, "white": 1.0}[request["background"]]
        if request.get("layers", False):
            # RGB is already opacity-weighted; transmit alpha separately without
            # unpremultiplication, gamma conversion or a baked background.
            pixels = torch.cat((rgb, alpha), 0).clamp(0, 1).mul(255).round().byte()
            pixels = pixels.permute(1, 2, 0).contiguous().cpu().numpy()
            projection = self.grid.projection(request["camera"]) if self.grid is not None else None
            return pixels, dict(
                render_ms=(time.perf_counter() - started) * 1000,
                active_cache_bytes=self.model.used_bytes,
                grid=projection,
                background=value,
            )
        color = (
            self.grid.background(request["camera"], value, self.device)
            if self.grid is not None and request.get("grid", True)
            else rgb.new_full((3, 1, 1), value)
        )
        pixels = (
            composite(rgb, alpha, color).clamp(0, 1).mul(255).round().byte().permute(1, 2, 0).contiguous().cpu().numpy()
        )
        elapsed = (time.perf_counter() - started) * 1000
        return pixels, dict(render_ms=elapsed, active_cache_bytes=self.model.used_bytes)


def encode_image(pixels, quality):
    started = time.perf_counter()
    extension = ".png" if quality == "lossless" else ".jpg"
    options = [] if extension == ".png" else [cv2.IMWRITE_JPEG_QUALITY, 95]
    conversion = cv2.COLOR_RGBA2BGR if pixels.shape[2] == 4 else cv2.COLOR_RGB2BGR
    success, encoded = cv2.imencode(extension, cv2.cvtColor(pixels, conversion), options)
    if not success:
        raise RuntimeError("Could not encode the rendered image")
    return encoded.tobytes(), (time.perf_counter() - started) * 1000


def encode_frame(pixels, quality):
    started = time.perf_counter()
    if pixels.shape[2] == 3:
        color, _ = encode_image(pixels, quality)
        return color, (time.perf_counter() - started) * 1000, {}
    alpha = cv2.extractChannel(pixels, 3)
    x, y, width, height = cv2.boundingRect(alpha)
    if width and height:
        # Omit only transparent margins, never resample the subject. Align JPEG
        # blocks with the original frame and keep padding around the silhouette.
        right = min(pixels.shape[1], ((x + width + 23) // 16) * 16)
        bottom = min(pixels.shape[0], ((y + height + 23) // 16) * 16)
        x, y = max(0, ((x - 8) // 16) * 16), max(0, ((y - 8) // 16) * 16)
        width, height = right - x, bottom - y
    else:
        x, y, width, height = 0, 0, 1, 1
    color, _ = encode_image(pixels[y : y + height, x : x + width].copy(), quality)
    success, alpha = cv2.imencode(".png", alpha[y : y + height, x : x + width], [cv2.IMWRITE_PNG_COMPRESSION, 1])
    if not success:
        raise RuntimeError("Could not encode the opacity image")
    alpha = alpha.tobytes()
    descriptor = dict(
        transport="rgb-alpha-v1", color_bytes=len(color), alpha_bytes=len(alpha), crop=[x, y, width, height]
    )
    return color + alpha, (time.perf_counter() - started) * 1000, descriptor
