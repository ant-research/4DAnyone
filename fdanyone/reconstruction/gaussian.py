"""Flat native 4D Gaussians and their conditional 3D distributions."""

import torch
from torch import nn
from torch.nn import functional as F

C0 = 0.28209479177387814


def rotation4(left, right):
    a, b, c, d = F.normalize(left, dim=-1).unbind(-1)
    p, q, r, s = F.normalize(right, dim=-1).unbind(-1)
    lmat = torch.stack((a, -b, -c, -d, b, a, -d, c, c, d, a, -b, d, -c, b, a), -1).reshape(-1, 4, 4)
    rmat = torch.stack((p, q, r, s, -q, p, -s, r, -r, s, p, -q, -s, -r, q, p), -1).reshape(-1, 4, 4)
    return lmat @ rmat


def covariance4(log_scale, log_time_scale, left, right, packed=False):
    scale = torch.cat((log_scale, log_time_scale), -1).exp()
    if scale.is_cuda and scale.dtype == torch.float32:
        from .kernels import Covariance

        spatial, velocity, temporal = Covariance.apply(scale, left, right)
        if not packed:
            spatial = spatial[:, [0, 1, 2, 1, 3, 4, 2, 4, 5]].reshape(-1, 3, 3)
        return spatial, velocity, temporal
    factor = rotation4(left, right) * scale[:, None, :]
    full = factor @ factor.transpose(-1, -2)
    temporal = full[:, 3, 3:]
    cross = full[:, :3, 3]
    velocity = cross / temporal
    spatial = full[:, :3, :3] - cross[:, :, None] * velocity[:, None, :]
    if packed:
        spatial = spatial[:, [0, 0, 0, 1, 1, 2], [0, 1, 2, 1, 2, 2]]
    return spatial, velocity, temporal


def sh_color(coefficients, direction, degree):
    x, y, z = direction.unbind(-1)
    basis = [torch.ones_like(x) * C0]
    if degree > 0:
        basis += [-0.4886025119029199 * y, 0.4886025119029199 * z, -0.4886025119029199 * x]
    if degree > 1:
        basis += [
            1.0925484305920792 * x * y,
            -1.0925484305920792 * y * z,
            0.31539156525252005 * (2 * z * z - x * x - y * y),
            -1.0925484305920792 * x * z,
            0.5462742152960396 * (x * x - y * y),
        ]
    if degree > 2:
        basis += [
            -0.5900435899266435 * y * (3 * x * x - y * y),
            2.890611442640554 * x * y * z,
            -0.4570457994644658 * y * (4 * z * z - x * x - y * y),
            0.3731763325901154 * z * (2 * z * z - 3 * x * x - 3 * y * y),
            -0.4570457994644658 * x * (4 * z * z - x * x - y * y),
            1.445305721320277 * z * (x * x - y * y),
            -0.5900435899266435 * x * (x * x - 3 * y * y),
        ]
    return ((coefficients[:, : len(basis)] * torch.stack(basis, -1)[..., None]).sum(1) + 0.5).clamp(0, 1)


class Gaussians(nn.Module):
    names = ("xyz", "time", "scale", "time_scale", "left", "right", "opacity", "dc", "sh")

    def __init__(self, tensors, degree=0):
        super().__init__()
        for name in self.names:
            self.register_parameter(name, nn.Parameter(tensors[name].float().contiguous()))
        self.degree = degree
        self.reset_statistics()

    def __len__(self):
        return len(self.xyz)

    def covariance(self, packed=False):
        return covariance4(self.scale, self.time_scale, self.left, self.right, packed)

    def tensors(self):
        return {name: getattr(self, name).detach() for name in self.names}

    def reset_statistics(self):
        for name in ("gradient_sum", "observations", "radius"):
            value = self.xyz.new_zeros(len(self))
            if name in self._buffers:
                setattr(self, name, value)
            else:
                self.register_buffer(name, value)

    def evaluate(self, time, camera_center, threshold, visibility=None, packed=False):
        return evaluate_conditional(self, self.covariance(packed), time, camera_center, threshold, visibility)


def evaluate_conditional(model, conditional, time, camera_center, threshold, visibility=None, indices=None):
    """Shared training/playback evaluation; optional indices are exact temporal survivors."""
    covariance, velocity, variance = conditional
    if indices is None:
        dt = time - model.time
        marginal = torch.exp(-0.5 * dt.square() / variance)
        indices = torch.where(marginal[:, 0].detach() > threshold)[0]
        xyz = (model.xyz + velocity * dt)[indices]
        opacity = (model.opacity.sigmoid() * marginal)[indices, 0]
    else:
        dt = time - model.time[indices]
        marginal = torch.exp(-0.5 * dt.square() / variance[indices])
        xyz = model.xyz[indices] + velocity[indices] * dt
        opacity = (model.opacity[indices].sigmoid() * marginal)[:, 0]
    if visibility is not None:
        visible = visibility(xyz.detach())
        xyz, indices, opacity = xyz[visible], indices[visible], opacity[visible]
    direction = F.normalize(xyz - camera_center, dim=-1)
    # Inactive SH must be absent from autograd, so Adam does not advance its step.
    coefficients = torch.cat((model.dc[indices], model.sh[indices]), 1) if model.degree else model.dc[indices]
    rgb = sh_color(coefficients, direction, model.degree)
    return xyz, covariance[indices], rgb, opacity, indices
