"""Per-frame hull initialization and nearest-neighbor motion estimates."""

import json
import math
from pathlib import Path

import numpy as np
import torch
from scipy.spatial import cKDTree
from torch.nn import functional as F

from .gaussian import C0, Gaussians, covariance4


class InitialPoints:
    """Ordered initialization clouds and the inputs that produced them."""

    def __init__(self, path):
        self.path = Path(path)
        self.metadata = json.loads((self.path / "metadata.json").read_text())

    def cloud(self, frame):
        xyz = np.load(self.path / (frame + ".npy"), allow_pickle=False)
        if xyz.dtype != np.float32 or xyz.ndim != 2 or xyz.shape[1] != 3 or len(xyz) < 4 or not np.isfinite(xyz).all():
            raise ValueError(f"Invalid initialization cloud: {frame}")
        return xyz, np.ones_like(xyz)


def decompose4(covariance):
    _, singular, vh = torch.linalg.svd(covariance)
    scales, rotation = singular.sqrt(), vh.mT
    swap = torch.linalg.det(rotation) < 0
    scales[swap] = scales[swap][:, [1, 0, 2, 3]]
    rotation[swap] = rotation[swap][:, :, [1, 0, 2, 3]]
    r = rotation
    p = (r[:, 0, 0] + r[:, 1, 1] + r[:, 2, 2] + r[:, 3, 3]) / 4
    q = -(r[:, 1, 0] - r[:, 0, 1] - r[:, 3, 2] + r[:, 2, 3]) / 4
    u = -(r[:, 2, 0] + r[:, 3, 1] - r[:, 0, 2] - r[:, 1, 3]) / 4
    v = -(r[:, 3, 0] - r[:, 2, 1] + r[:, 1, 2] - r[:, 0, 3]) / 4
    b = (r[:, 1, 0] - r[:, 0, 1] + r[:, 3, 2] - r[:, 2, 3]) / 4
    c = (r[:, 2, 0] - r[:, 3, 1] - r[:, 0, 2] + r[:, 1, 3]) / 4
    d = (r[:, 3, 0] + r[:, 2, 1] - r[:, 1, 2] - r[:, 0, 3]) / 4
    left = F.normalize(torch.stack((torch.ones_like(p), b / p, c / p, d / p), -1), dim=-1)
    right = F.normalize(torch.stack((p, q, u, v), -1), dim=-1)
    return scales, left, right


def nearest_indices(query, reference):
    """Exact KD-tree nearest neighbors with first-index tie breaking in float32."""
    tree = cKDTree(reference)
    distances, indices = tree.query(query, k=2, workers=-1)
    selected = indices[:, 0].copy()
    tied = np.flatnonzero(np.isclose(distances[:, 0], distances[:, 1], rtol=2e-6, atol=1e-7))
    for i in tied:
        candidates = np.array(sorted(tree.query_ball_point(query[i], distances[i, 0] * (1 + 2e-6) + 1e-7)))
        squared = ((reference[candidates] - query[i]) ** 2).sum(-1, dtype=np.float32)
        selected[i] = candidates[squared.argmin()]
    return selected


@torch.no_grad()
def initialize_frame(
    xyz,
    rgb,
    next_cloud,
    time,
    interval,
    device,
    *,
    initial_opacity,
    initial_scale,
    initial_span,
    marginal_threshold,
    sh_degree,
    space_scale,
):
    xyz = np.asarray(xyz, np.float32) / space_scale
    # The CUDA initializer uses the mean squared distance to the nearest three
    # other points. A KD tree avoids a quadratic distance matrix.
    distances = cKDTree(xyz).query(xyz, k=4, workers=-1)[0][:, 1:]
    dist = np.sqrt(np.maximum((distances**2).mean(-1), 1e-7)).astype(np.float32)
    dist = np.minimum(dist, dist.mean() * 5) * initial_scale
    xyz_t = torch.as_tensor(xyz, device=device)
    scales = torch.as_tensor(np.log(np.clip(dist, 1e-6, 1e6)), device=device)[:, None].repeat(1, 3)
    temporal = interval * initial_span / math.sqrt(-2 * math.log(marginal_threshold))
    time_scale = torch.full_like(scales[:, :1], math.log(temporal))
    left = torch.zeros((len(xyz), 4), device=device)
    left[:, 0] = 1
    right = left.clone()
    if next_cloud is not None:
        next_xyz, next_rgb = next_cloud
        next_xyz = next_xyz / space_scale
        nearest = nearest_indices(np.c_[xyz, rgb], np.c_[next_xyz, next_rgb])
        velocity = torch.as_tensor((next_xyz[nearest] - xyz) / interval, device=device)
        spatial, _, variance = covariance4(scales, time_scale, left, right)
        cross = velocity * variance
        full = xyz_t.new_zeros((len(xyz), 4, 4))
        full[:, :3, :3] = spatial + cross[:, :, None] * velocity[:, None, :]
        full[:, :3, 3], full[:, 3, :3], full[:, 3, 3:] = cross, cross, variance
        values, ql, qr = decompose4(full)
        logs = values.clamp(1e-6, 1e6).log()
        _, _, actual = covariance4(logs[:, :3], logs[:, 3:], ql, qr)
        bad = ((actual - variance).abs()[:, 0] > 1e-4) | ~torch.isfinite(actual[:, 0])
        scales = torch.where(bad[:, None], scales, logs[:, :3])
        time_scale = torch.where(bad[:, None], time_scale, logs[:, 3:])
        left, right = torch.where(bad[:, None], left, ql), torch.where(bad[:, None], right, qr)
    data = dict(
        xyz=xyz_t,
        time=torch.full_like(time_scale, time),
        scale=scales,
        time_scale=time_scale,
        left=left,
        right=right,
        opacity=torch.full_like(time_scale, math.log(initial_opacity / (1 - initial_opacity))),
        dc=(torch.as_tensor(rgb, device=device)[:, None, :] - 0.5) / C0,
        sh=torch.zeros((len(xyz), (sh_degree + 1) ** 2 - 1, 3), device=device),
    )
    return data


@torch.no_grad()
def initialize(
    training_data,
    points,
    device,
    *,
    point_fraction,
    initial_opacity,
    initial_scale,
    initial_span,
    marginal_threshold,
    sh_degree,
    space_scale,
):
    all_frames = {name: [] for name in Gaussians.names}
    current = points.cloud(training_data.frames[0])
    for index, frame in enumerate(training_data.frames):
        xyz, rgb = current
        next_cloud = points.cloud(training_data.frames[index + 1]) if index + 1 < len(training_data.frames) else None
        data = initialize_frame(
            xyz,
            rgb,
            next_cloud,
            float(training_data.times[index]),
            1 / float(training_data.fps),
            device,
            initial_opacity=initial_opacity,
            initial_scale=initial_scale,
            initial_span=initial_span,
            marginal_threshold=marginal_threshold,
            sh_degree=sh_degree,
            space_scale=space_scale,
        )
        count = max(1, int(len(xyz) * point_fraction))
        selection = torch.randperm(len(xyz))[:count].to(device)
        for name in all_frames:
            all_frames[name].append(data[name][selection].cpu())
        print(f"initialize {frame}: {count} Gaussians", flush=True)
        current = next_cloud
    return Gaussians({name: torch.cat(values).to(device) for name, values in all_frames.items()})
