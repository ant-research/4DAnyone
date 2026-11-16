"""One gsplat backend shared by training and offline rendering."""

import math

import torch

from .data import camera_tensors


class Camera:
    """Static camera tensors in training units; prepare once and reuse across frames."""

    def __init__(self, camera, device, *, far, image_scale, near, space_scale):
        self.k, self.view, self.height, self.width = camera_tensors(camera, device, space_scale, image_scale)
        self.near, self.far = near / space_scale, far / space_scale
        self.center = -self.view[:3, :3].T @ self.view[:3, 3]
        k, height, width, near, far = self.k, self.height, self.width, self.near, self.far
        projection = k.new_zeros(4, 4)
        projection[0, 0] = 2 * k[0, 0] / width
        projection[0, 1] = 2 * k[0, 1] / width
        projection[0, 2] = -1 + 2 * k[0, 2] / width
        projection[1, 1] = 2 * k[1, 1] / height
        projection[1, 2] = -1 + 2 * k[1, 2] / height
        projection[2, 2] = (far + near) / (far - near)
        projection[2, 3] = -2 * far * near / (far - near)
        projection[3, 2] = k[2, 2]
        self.clip = projection @ self.view

    @torch.no_grad()
    def visible(self, xyz):
        hom = torch.cat((xyz, torch.ones_like(xyz[:, :1])), -1) @ self.clip.T
        ndc = hom[:, :3] / (hom[:, 3:] + 1e-7)
        return (ndc[:, :2].abs() < 1.2).all(-1) & (ndc[:, 2].abs() < 1.01)


def render(model, camera: Camera, time, *, marginal_threshold):
    from gsplat.cuda._wrapper import fully_fused_projection, isect_offset_encode, isect_tiles, rasterize_to_pixels

    height, width = camera.height, camera.width
    xyz, packed_cov, rgb, opacity, indices = model.evaluate(
        time,
        camera.center,
        marginal_threshold,
        visibility=camera.visible,
        packed=True,
    )
    if not len(xyz):
        zero = model.xyz.sum() * 0
        return (zero.expand(3, height, width), zero.expand(1, height, width), None)
    radii, means, depths, conics, _ = fully_fused_projection(
        xyz,
        packed_cov,
        None,
        None,
        camera.view[None],
        camera.k[None],
        width,
        height,
        packed=False,
        near_plane=camera.near,
        far_plane=camera.far,
    )
    tile_width, tile_height = math.ceil(width / 16), math.ceil(height / 16)
    _, intersections, flatten = isect_tiles(means, radii, depths, 16, tile_width, tile_height, packed=False, n_images=1)
    offsets = isect_offset_encode(intersections, 1, tile_width, tile_height)
    image, alpha = rasterize_to_pixels(
        means, conics, rgb[None], opacity[None], width, height, 16, offsets, flatten, packed=False, absgrad=False
    )
    if means.requires_grad:
        means.retain_grad()
    return (
        image[0].permute(2, 0, 1),
        alpha[0].permute(2, 0, 1),
        (indices, means, radii[0].amax(-1) / max(height, width), (width, height)),
    )


@torch.no_grad()
def accumulate_statistics(model, metadata):
    for record in metadata:
        if record is None:
            continue
        indices, means, radii, size = record
        if means.grad is None:
            raise RuntimeError("Missing screen-space gradients")
        model.gradient_sum[indices] += (means.grad[0] * means.new_tensor(size) * 0.5).norm(dim=-1)
        model.observations[indices] += (radii != 0).float()
        model.radius[indices] = torch.maximum(model.radius[indices], radii)
        model.radius[indices] = torch.maximum(model.radius[indices], (radii == -1).float())
