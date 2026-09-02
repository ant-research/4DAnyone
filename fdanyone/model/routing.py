"""Target-context routing across view groups."""

from __future__ import annotations


def _validate_grouping(num_views: int, group_size: int) -> int:
    if num_views <= 0 or group_size <= 0 or num_views % group_size:
        raise ValueError(f"num_views={num_views} must be divisible by positive group_size={group_size}.")
    return num_views // group_size


def view_groups(
    num_views: int,
    group_size: int,
    offset: int = 0,
) -> tuple[tuple[int, ...], ...]:
    """Partition one camera layer into cyclically shifted groups."""

    num_groups = _validate_grouping(num_views, group_size)
    return tuple(
        tuple((group_index * group_size + offset + local_index) % num_views for local_index in range(group_size))
        for group_index in range(num_groups)
    )


def routing_steps(
    *,
    views_per_layer: int,
    num_layers: int,
    group_size: int,
    num_steps: int,
    enable_tcr: bool,
    tcr_stride: int = 1,
    freeze_after_one_cycle: bool = False,
) -> tuple[tuple[tuple[int, ...], ...], ...]:
    """Return layer-local target groups for every denoising step."""

    if num_steps <= 0:
        raise ValueError(f"num_steps must be positive, got {num_steps}.")
    if num_layers <= 0:
        raise ValueError(f"num_layers must be positive, got {num_layers}.")
    if tcr_stride <= 0:
        raise ValueError(f"tcr_stride must be positive, got {tcr_stride}.")
    _validate_grouping(views_per_layer, group_size)

    def step_offset(step_index: int) -> int:
        if not enable_tcr:
            return 0
        offset = step_index * tcr_stride
        if freeze_after_one_cycle and offset >= group_size:
            return 0
        return offset

    return tuple(
        tuple(
            tuple(layer_index * views_per_layer + view_index for view_index in group)
            for layer_index in range(num_layers)
            for group in view_groups(
                views_per_layer,
                group_size,
                step_offset(step_index),
            )
        )
        for step_index in range(num_steps)
    )
