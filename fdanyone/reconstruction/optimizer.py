"""Elementwise Adam with the training recipe's zero-gradient semantics."""

import math

import torch


class GaussianAdam(torch.optim.Optimizer):
    def __init__(self, model, *, dc_lr, opacity_lr, rotation_lr, scale_lr, sh_lr, time_lr, xyz_lr):
        rates = dict(
            xyz=xyz_lr,
            time=time_lr,
            scale=scale_lr,
            time_scale=scale_lr,
            left=rotation_lr,
            right=rotation_lr,
            opacity=opacity_lr,
            dc=dc_lr,
            sh=sh_lr,
        )
        super().__init__([dict(params=[getattr(model, n)], name=n, lr=rates[n]) for n in model.names], {})

    @torch.no_grad()
    def step(self, closure=None):
        if closure is not None:
            raise ValueError("GaussianAdam does not use closures")
        for group in self.param_groups:
            p = group["params"][0]
            if p.grad is None:
                continue
            state = self.state[p]
            if not state:
                state.update(step=0, exp_avg=torch.zeros_like(p), exp_avg_sq=torch.zeros_like(p))
            state["step"] += 1
            grad, first, second = p.grad, state["exp_avg"], state["exp_avg_sq"]
            if p.is_cuda and p.dtype == torch.float32:
                from .kernels import extension

                extension().adam(p, grad.contiguous(), first, second, state["step"], group["lr"])
                continue
            active = grad != 0
            # Unlike ordinary Adam, exactly-zero gradients freeze both moments and values.
            first.copy_(torch.where(active, first * 0.9 + grad * 0.1, first))
            second.copy_(torch.where(active, second * 0.999 + grad.square() * 0.001, second))
            correction1 = 1 - 0.9 ** state["step"]
            correction2 = math.sqrt(1 - 0.999 ** state["step"])
            update = first / (second.sqrt() / correction2 + 1e-15) * (group["lr"] / correction1)
            p.sub_(torch.where(active, update, 0))

    @torch.no_grad()
    def resize(self, model, keep, additions=None):
        """Preserve surviving gradients/moments; newly created points start at zero."""
        additions = additions or {}
        for group in self.param_groups:
            name, old = group["name"], group["params"][0]
            extra = additions.get(name, old[:0])
            new = torch.nn.Parameter(torch.cat((old[keep], extra)).detach())
            if old.grad is not None:
                new.grad = torch.cat((old.grad[keep], torch.zeros_like(extra)))
            state = self.state.pop(old, None)
            if state:
                self.state[new] = dict(
                    step=state["step"],
                    **{
                        key: torch.cat((state[key][keep], torch.zeros_like(extra))) for key in ("exp_avg", "exp_avg_sq")
                    },
                )
            group["params"] = [new]
            setattr(model, name, new)
        count = len(next(iter(additions.values()))) if additions else 0
        for name in ("gradient_sum", "observations", "radius"):
            old = getattr(model, name)
            setattr(model, name, torch.cat((old[keep], old.new_zeros(count))))

    @torch.no_grad()
    def replace(self, model, name, value):
        p = getattr(model, name)
        p.copy_(value)
        if p.grad is not None:
            p.grad.zero_()
        if self.state[p]:
            self.state[p]["exp_avg"].zero_()
            self.state[p]["exp_avg_sq"].zero_()
