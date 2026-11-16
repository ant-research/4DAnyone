"""A viewer-only, antialiased ground reference in calibrated world coordinates."""

import math

import numpy as np
import torch

from .camera import world_up


class GroundGrid:
    def __init__(self, normal, origin, extent):
        self.normal = np.asarray(normal, dtype=np.float64)
        self.normal /= np.linalg.norm(self.normal)
        self.origin = np.asarray(origin, dtype=np.float64)
        axis = np.eye(3)[np.argmin(np.abs(self.normal))]
        u = axis - np.dot(axis, self.normal) * self.normal
        u /= np.linalg.norm(u)
        self.basis = np.stack((u, np.cross(self.normal, u), self.normal))
        self.extent = max(float(extent), 1e-3)
        self.spacing = self.extent / 8
        self.key = self.cached = None

    @classmethod
    @torch.inference_mode()
    def from_model(cls, model, cameras, space_scale):
        up = world_up(cameras)
        # Bound startup work; low-opacity strays should not set the floor.
        stride = max(1, math.ceil(len(model) / 100_000))
        xyz = model.xyz[::stride]
        visible = model.opacity[::stride, 0].sigmoid() > 0.1
        points = xyz[visible].cpu().numpy() * space_scale
        if len(points) < 8:
            points = xyz.cpu().numpy() * space_scale
        heights = points @ up
        low, high = np.quantile(heights, (0.005, 0.995))
        extent = max(float(high - low), 1e-3)
        center = np.median(points, axis=0)
        level = low - 0.02 * extent
        origin = center + (level - np.dot(center, up)) * up
        return cls(up, origin, extent)

    def projection(self, camera):
        """Small frame-specific uniforms; no grid image crosses the network."""
        view, intrinsic = (np.asarray(camera[name], dtype=np.float64) for name in ("w2c", "K"))
        rotation = view[:3, :3]
        center = -rotation.T @ view[:3, 3]
        offset = self.basis @ (center - self.origin)
        coefficients = self.basis @ rotation.T @ np.linalg.inv(intrinsic)
        return dict(
            coefficients=coefficients.tolist(), offset=offset.tolist(), extent=self.extent, spacing=self.spacing
        )

    @torch.inference_mode()
    def background(self, camera, value, device):
        key = (repr(camera), value, str(device))
        if key == self.key:
            return self.cached
        self.key, self.cached = None, None
        projection = self.projection(camera)
        u0, v0, height = projection["offset"]
        base = torch.full((3, 1, 1), value, device=device, dtype=torch.float32)
        # Both sides are visible. At the plane itself the intersection is degenerate.
        if abs(height) <= self.extent * 1e-5:
            self.key, self.cached = key, base
            return base
        coeff = torch.as_tensor(projection["coefficients"], device=device, dtype=torch.float32)
        x = torch.arange(camera["width"], device=device, dtype=torch.float32)[None, :] + 0.5
        y = torch.arange(camera["height"], device=device, dtype=torch.float32)[:, None] + 0.5
        rays = [row[0] * x + row[1] * y + row[2] for row in coeff]
        ru, rv, denominator = rays
        side = 1 if height > 0 else -1
        valid = denominator * side < -1e-5
        denominator = side * (denominator * side).clamp(max=-1e-5)
        distance = -height / denominator
        u, v = (u0 + distance * ru) / self.spacing, (v0 + distance * rv) / self.spacing
        # Analytic pixel derivatives avoid finite-difference seams and horizon aliasing.
        widths = []
        for row, ray in ((coeff[0], ru), (coeff[1], rv)):
            derivative = sum((row[i] * denominator - ray * coeff[2, i]).abs() for i in (0, 1))
            widths.append((abs(height) * derivative / denominator.square() / self.spacing).clamp_min(1e-6))

        def lines(coordinate, footprint):
            nearest = ((coordinate + 0.5).remainder(1) - 0.5).abs()
            coverage = (1 - nearest / footprint).clamp(0, 1)
            # Fade unresolved cells rather than producing a moire pattern at the horizon.
            return coverage * ((0.5 - footprint) / 0.35).clamp(0, 1)

        minor = torch.maximum(lines(u, widths[0]), lines(v, widths[1]))
        major = torch.maximum(lines(u / 5, widths[0] / 5), lines(v / 5, widths[1] / 5))
        squared_range = (distance * ru).square() + (distance * rv).square() + height**2
        fade = torch.exp(-squared_range / (self.extent * 20) ** 2) * valid
        strength = torch.maximum(minor * 0.16, major * 0.28) * fade
        gray = (value + strength * (1 if value < 0.5 else -1)).clamp(0, 1)
        self.cached = gray[None].expand(3, -1, -1)
        self.key = key
        return self.cached
