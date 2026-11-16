"""Training views, masks, camera calibration and frame timing."""

import hashlib
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np
import torch


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, path)


@contextmanager
def staging_directory(destination):
    """Publish a complete stage; an exception leaves its destination untouched."""
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f"Output exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="." + destination.name + "-", dir=destination.parent))
    try:
        yield staging
        os.rename(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def read_cameras(path):
    payload = json.loads(Path(path).read_text())
    if payload.get("camera_model") != "OPENCV":
        raise ValueError("Expected OpenCV cameras")
    records = sorted(payload["cameras"], key=lambda c: c["camera_id"])
    names = [f"{c['camera_id']:02d}" for c in records]
    if not names or len(set(names)) != len(names):
        raise ValueError("Camera IDs must be nonempty and unique")
    cameras = []
    for name, record in zip(names, records, strict=True):
        k = np.asarray(record["K"], dtype=np.float64)
        pose = np.asarray(record["camera_to_world"], dtype=np.float64)
        if k.shape != (3, 3) or pose.shape != (4, 4) or not np.isfinite(k).all() or not np.isfinite(pose).all():
            raise ValueError(f"Invalid camera: {name}")
        r = pose[:3, :3]
        if (
            not np.allclose(pose[3], [0, 0, 0, 1])
            or not np.allclose(r.T @ r, np.eye(3), atol=1e-5)
            or not np.isclose(np.linalg.det(r), 1)
        ):
            raise ValueError(f"Invalid camera pose: {name}")
        cameras.append(
            dict(
                name=name,
                K=k.tolist(),
                w2c=np.linalg.inv(pose).tolist(),
                height=int(record["image_height"]),
                width=int(record["image_width"]),
            )
        )
    return cameras


def camera_tensors(camera, device, space_scale=1.0, image_scale=1.0):
    k = torch.tensor(camera["K"], dtype=torch.float32, device=device)
    view = torch.tensor(camera["w2c"], dtype=torch.float32, device=device)
    height, width = int(camera["height"] * image_scale), int(camera["width"] * image_scale)
    k[0] *= width / camera["width"]
    k[1] *= height / camera["height"]
    view[:3, 3] /= space_scale
    return k, view, height, width


def premultiplied_pixels(image, mask, size, encoding="straight"):
    """BGR + coverage to RGB/alpha bytes; filter premultiplied color, never straight RGB."""
    rgb = image[..., ::-1].astype(np.float32) / 255
    alpha = mask.astype(np.float32) / 255
    if encoding == "straight":
        rgb *= alpha[..., None]
    elif encoding != "premultiplied":
        raise ValueError("rgb_encoding must be straight or premultiplied")
    if (image.shape[1], image.shape[0]) != size:
        rgb = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)
        alpha = cv2.resize(mask, size, interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    pixels = np.concatenate((rgb, alpha[..., None]), -1)
    return np.rint(pixels * 255).clip(0, 255).astype(np.uint8).transpose(2, 0, 1).copy()


class TrainingData:
    metadata_file = "metadata.json"
    image_suffix = ".jpg"
    metadata_fields = {"fps", "frames", "source_identity"}

    def __init__(self, root, *, image_scale=1.0, cameras=None, camera_files=None):
        self.root = Path(root).resolve()
        self.meta = json.loads((self.root / self.metadata_file).read_text())
        unknown = self.meta.keys() - self.metadata_fields
        if unknown:
            raise ValueError(f"Unsupported training-data metadata: {sorted(unknown)}")
        self.fps = Fraction(str(self.meta["fps"]))
        if self.fps <= 0:
            raise ValueError("FPS must be positive")
        self.cameras = read_cameras(self.root / "cameras.json") if cameras is None else cameras
        self.camera_files = [self.root / "cameras.json"] if camera_files is None else camera_files
        self.frames = self.meta["frames"]
        if not self.frames or not all(isinstance(f, str) and f.isdigit() for f in self.frames):
            raise ValueError("frames must be nonempty numeric filename stems")
        ids = list(map(int, self.frames))
        if ids != list(range(ids[0], ids[0] + len(ids))):
            raise ValueError("v1 requires contiguous frame IDs in increasing order")
        self.times = np.arange(len(ids)) / float(self.fps)
        self.duration = len(ids) / float(self.fps)
        self.image_scale = image_scale
        names = {c["name"] for c in self.cameras}
        for subdir, suffix in [("images", self.image_suffix), ("fmasks", ".png")]:
            if {p.name for p in (self.root / subdir).iterdir() if p.is_dir()} != names:
                raise ValueError(f"{subdir}: camera inventory differs")
            for camera in self.cameras:
                folder = self.root / subdir / camera["name"]
                if {p.name for p in folder.iterdir()} != {f + suffix for f in self.frames}:
                    raise ValueError(f"{folder}: frame inventory differs")
                p = folder / (self.frames[0] + suffix)
                image = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
                if image is None or list(image.shape[:2]) != [camera["height"], camera["width"]]:
                    raise ValueError(f"Invalid raster: {p}")

    def __len__(self):
        return len(self.frames) * len(self.cameras)

    def fingerprint(self):
        digest = hashlib.sha256()
        paths = list(self.camera_files)
        for directory in ("images", "fmasks"):
            paths.extend(sorted(p for p in (self.root / directory).rglob("*") if p.is_file()))
        for path in paths:
            digest.update(str(path.relative_to(self.root)).encode())
            digest.update(path.read_bytes())
        digest.update((self.root / self.metadata_file).read_bytes())
        return digest.hexdigest()

    def pixels(self, index):
        camera_idx, frame_idx = divmod(index, len(self.frames))
        camera, frame = self.cameras[camera_idx], self.frames[frame_idx]
        image = cv2.imread(str(self.root / "images" / camera["name"] / (frame + self.image_suffix)))
        mask = cv2.imread(str(self.root / "fmasks" / camera["name"] / (frame + ".png")), cv2.IMREAD_GRAYSCALE)
        if image is None or mask is None or image.shape[:2] != mask.shape:
            raise ValueError(f"Invalid image/mask at {camera['name']}/{frame}")
        scale = self.image_scale
        size = (int(camera["width"] * scale), int(camera["height"] * scale))
        return self.process_pixels(image, mask, size)

    def process_pixels(self, image, mask, size):
        return premultiplied_pixels(image, mask, size)
