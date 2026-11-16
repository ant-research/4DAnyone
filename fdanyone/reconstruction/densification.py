"""Point updates over flat tensors, including Adam state migration."""

import math

import torch

from .gaussian import rotation4


class Topology:
    def __init__(
        self,
        spatial_scale,
        duration,
        interval,
        *,
        densify_every,
        densify_from,
        densify_until,
        discard_opacity,
        gradient_threshold,
        lr_steps,
        marginal_threshold,
        max_scene_scale,
        min_gradient,
        min_opacity,
        min_screen_radius,
        opacity_reset_every,
        opacity_reset_radius,
        prune_until,
        sh_degree,
        sh_every,
        sh_gradient_threshold,
        size_threshold,
        view_dependent_ratio,
        xyz_lr,
        xyz_lr_final,
    ):
        self.densify_every = densify_every
        self.densify_from = densify_from
        self.densify_until = densify_until
        self.discard_opacity = discard_opacity
        self.gradient_threshold = gradient_threshold
        self.lr_steps = lr_steps
        self.marginal_threshold = marginal_threshold
        self.max_scene_scale = max_scene_scale
        self.min_gradient = min_gradient
        self.min_opacity = min_opacity
        self.min_screen_radius = min_screen_radius
        self.opacity_reset_every = opacity_reset_every
        self.opacity_reset_radius = opacity_reset_radius
        self.prune_until = prune_until
        self.sh_degree = sh_degree
        self.sh_every = sh_every
        self.sh_gradient_threshold = sh_gradient_threshold
        self.size_threshold = size_threshold
        self.view_dependent_ratio = view_dependent_ratio
        self.xyz_lr = xyz_lr
        self.xyz_lr_final = xyz_lr_final
        self.spatial_scale, self.duration, self.interval = spatial_scale, duration, interval
        self.sh_threshold = self.sh_gradient_threshold

    @torch.no_grad()
    def clip_sh(self, model):
        if model.degree and model.sh.grad is not None:
            enabled = model.sh[:, :1, :1] != 0
            activate = model.sh.grad[:, :1, :1].abs() > self.sh_threshold
            count = (model.degree + 1) ** 2 - 1
            model.sh.grad[:, :count] *= enabled | activate

    @torch.no_grad()
    def refresh_sh_threshold(self, model):
        ratio = (model.sh[:, 0, 0] != 0).float().mean().item() if model.sh.shape[1] else 0
        self.sh_threshold = math.inf if ratio > self.view_dependent_ratio else self.sh_gradient_threshold

    @torch.no_grad()
    def prune(self, model, optimizer):
        _, _, variance = model.covariance()
        previous = ((model.time / self.interval).long() * self.interval).clamp_min(0)
        following = ((model.time / self.interval + 1).long() * self.interval).clamp_max(self.duration - self.interval)
        before = torch.exp(-0.5 * (previous - model.time).square() / variance)
        after = torch.exp(-0.5 * (following - model.time).square() / variance)
        opacity = model.opacity.sigmoid()
        time_bad = ((before < self.marginal_threshold) & (after < self.marginal_threshold)) | (
            (before * opacity < self.discard_opacity) & (after * opacity < self.discard_opacity)
        )
        radius = (-2 * math.log(self.marginal_threshold) * variance[:, 0]).sqrt()
        required = torch.where(radius <= 0.5, 2.0, 1.0)
        required = torch.where(radius <= 0.1, 3.0, required)
        avg = (model.gradient_sum / model.observations).nan_to_num(nan=0)
        no_gradient = (avg <= self.min_gradient) & (model.observations >= required)
        too_large = (
            torch.cat((model.scale, model.time_scale), -1).exp().amax(-1) > self.spatial_scale * self.max_scene_scale
        )
        remove = (
            time_bad[:, 0]
            | (opacity[:, 0] < self.min_opacity)
            | no_gradient
            | too_large
            | (model.radius <= self.min_screen_radius)
        )
        # The reference records max-screen counts but does not remove those points.
        if remove.all():
            raise RuntimeError("Pruning would remove every Gaussian; inspect initialization and masks")
        count = int(remove.sum())
        if count:
            optimizer.resize(model, ~remove)
        return count

    @torch.no_grad()
    def densify(self, model, optimizer):
        avg = (model.gradient_sum / model.observations).nan_to_num(nan=0)
        small = model.scale.exp().amax(-1) <= self.size_threshold * self.spatial_scale
        selected = small & (avg >= self.gradient_threshold)
        count_clone = int(selected.sum())
        if count_clone:
            additions = {name: getattr(model, name)[selected].clone() for name in model.names}
            if math.isinf(self.sh_threshold) or not model.degree:
                additions["sh"].zero_()
            optimizer.resize(model, torch.ones(len(model), dtype=torch.bool, device=model.xyz.device), additions)
        avg = (model.gradient_sum / model.observations).nan_to_num(nan=0)
        selected = (model.scale.exp().amax(-1) > self.size_threshold * self.spatial_scale) & (
            avg >= self.gradient_threshold
        )
        count_split = int(selected.sum())
        if count_split:
            additions = {
                name: getattr(model, name)[selected].repeat((2,) + (1,) * (getattr(model, name).ndim - 1))
                for name in model.names
            }
            std = torch.cat((additions["scale"], additions["time_scale"]), -1).exp()
            samples = std * torch.randn_like(std)
            position = (rotation4(additions["left"], additions["right"]) @ samples[..., None])[..., 0]
            position += torch.cat((additions["xyz"], additions["time"]), -1)
            additions["xyz"], additions["time"] = position[:, :3], position[:, 3:]
            logs = (std / 1.6).clamp(1e-6, 1e6).log()
            additions["scale"], additions["time_scale"] = logs[:, :3], logs[:, 3:]
            if math.isinf(self.sh_threshold) or not model.degree:
                additions["sh"].zero_()
            optimizer.resize(model, ~selected, additions)
        return count_clone, count_split

    @torch.no_grad()
    def update(self, model, optimizer, step):
        self.clip_sh(model)
        # The original first pre-optimizer hook has no updated points yet.
        if step > 0 and step % self.densify_every == 0:
            fraction = min(step / self.lr_steps, 1)
            lr = (
                math.exp(math.log(self.xyz_lr) * (1 - fraction) + math.log(self.xyz_lr_final) * fraction)
                * self.spatial_scale
            )
            for group in optimizer.param_groups:
                if group["name"] == "xyz":
                    group["lr"] = lr
            if model.degree:
                self.refresh_sh_threshold(model)
        if 0 < step < self.densify_until and step % self.sh_every == 0:
            model.degree = min(model.degree + 1, self.sh_degree)
        changed = False
        counts = dict(pruned=0, cloned=0, split=0)
        if (
            self.densify_from < step <= self.densify_until
            and step % self.opacity_reset_every
            and step % self.densify_every == 0
        ):
            counts["pruned"] = self.prune(model, optimizer)
            counts["cloned"], counts["split"] = self.densify(model, optimizer)
            changed = True
        elif self.densify_until < step < self.prune_until and step % self.densify_every == 0:
            counts["pruned"] = self.prune(model, optimizer)
            changed = True
        if changed:
            model.reset_statistics()
            optimizer.replace(model, "time", model.time.clamp(-self.interval, self.duration + self.interval))
        if self.densify_from < step < self.densify_until and step % self.opacity_reset_every == 0:
            _, _, variance = model.covariance()
            long = (-2 * math.log(self.marginal_threshold) * variance).sqrt() > self.opacity_reset_radius
            reset = math.log(2 * self.min_opacity / (1 - 2 * self.min_opacity))
            optimizer.replace(model, "opacity", torch.where(long, reset, model.opacity))
            changed = True
        return changed, counts
