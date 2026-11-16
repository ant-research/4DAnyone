"""Chunked all-view visual-hull intersection."""

from pathlib import Path

import cv2
import numpy as np
import torch

from .data import camera_tensors, staging_directory, write_json


@torch.no_grad()
def carve_points(masks, projections, bounds, voxel_size, chunk_size):
    device = projections.device
    axes = [torch.arange(a, b, voxel_size, device=device) for a, b in zip(*bounds, strict=True)]
    nx, ny, nz = [len(axis) for axis in axes]
    _, height, width = masks.shape
    points = []
    for start in range(0, nx * ny * nz, chunk_size):
        idx = torch.arange(start, min(start + chunk_size, nx * ny * nz), device=device)
        xyz = torch.stack((axes[0][idx // (ny * nz)], axes[1][(idx // nz) % ny], axes[2][idx % nz]), -1)
        xyz = xyz.to(projections.dtype)
        pixel = (projections @ torch.cat((xyz, torch.ones_like(xyz[:, :1])), -1).T).transpose(1, 2)
        z = pixel[..., 2]
        uv = torch.round(pixel[..., :2] / z[..., None].clamp_min(1e-8)).long()
        u, v = uv.unbind(-1)
        valid = (z > 0) & (u >= 0) & (u < width) & (v >= 0) & (v < height)
        inside = (
            masks[torch.arange(len(masks), device=device)[:, None], v.clamp(0, height - 1), u.clamp(0, width - 1)]
            & valid
        )
        points.append(xyz[inside.all(0)].float().cpu())
    return torch.cat(points).numpy()


def carve(training_data, output, device="cuda", *, bounds, carve_chunk, voxel_size):
    output = Path(output).resolve()
    projections = []
    for camera in training_data.cameras:
        k, view, _, _ = camera_tensors(camera, device)
        projections.append(k @ view[:3])
    projections = torch.stack(projections)
    records = []
    with staging_directory(output) as staging:
        for frame in training_data.frames:
            masks = [
                cv2.imread(str(training_data.root / "fmasks" / c["name"] / (frame + ".png")), cv2.IMREAD_GRAYSCALE)
                for c in training_data.cameras
            ]
            if any(mask is None for mask in masks):
                raise ValueError(f"Missing mask for frame {frame}")
            masks = torch.from_numpy(np.stack(masks)).to(device) > 127
            xyz = carve_points(masks, projections, bounds, voxel_size, carve_chunk)
            if len(xyz) < 4:
                raise ValueError(f"Insufficient hull at frame {frame}; inspect masks, cameras and bounds")
            np.save(staging / (frame + ".npy"), xyz, allow_pickle=False)
            records.append(dict(frame=frame, points=len(xyz)))
            print(f"carve {frame}: {len(xyz)} points", flush=True)
        write_json(
            staging / "metadata.json",
            dict(scene=training_data.fingerprint(), bounds=bounds, voxel_size=voxel_size, frames=records),
        )
