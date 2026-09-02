"""Map canonical target cameras onto cyclic denoising groups."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fdanyone.views import ViewPlan

CameraOrder = tuple[int, ...]
CameraGroup = tuple[int, ...]
StepGroups = tuple[CameraGroup, ...]
Routes = tuple[StepGroups, ...]


def denoising_camera_order(view_plan: ViewPlan) -> CameraOrder:
    """Return one deterministic cycle over the plan's canonical camera IDs.

    A single layer keeps its public yaw order. Multiple layers form a
    Hamiltonian cycle in the open pitch-by-yaw grid, so partial yaw layouts do
    not need a false edge between their horizontal endpoints.
    """

    views_per_layer = view_plan.views_per_layer
    num_layers = view_plan.num_layers
    if views_per_layer <= 0 or num_layers <= 0:
        raise ValueError("A denoising camera order requires a non-empty resolved view plan.")
    if len(set(view_plan.layer_pitches)) != num_layers:
        raise ValueError("A denoising camera order requires distinct pitch layers.")
    if num_layers == 1:
        return tuple(range(views_per_layer))
    if views_per_layer % 2:
        raise ValueError("A multi-layer camera ring requires an even number of views per layer.")

    # Public IDs follow input layer order. Physical vertical neighbors follow
    # pitch order, so this mapping changes traversal without changing identity.
    layers_by_pitch = tuple(sorted(range(num_layers), key=view_plan.layer_pitches.__getitem__))

    def camera_id(pitch_rank: int, yaw_index: int) -> int:
        return layers_by_pitch[pitch_rank] * views_per_layer + yaw_index

    # Reserve the lowest-pitch row as the return lane: descend the first yaw
    # column, snake through the remaining rows, then traverse that row backward.
    order = [camera_id(pitch_rank, 0) for pitch_rank in range(num_layers)]
    for yaw_index in range(1, views_per_layer):
        pitch_ranks = range(num_layers - 1, 0, -1) if yaw_index % 2 else range(1, num_layers)
        order.extend(camera_id(pitch_rank, yaw_index) for pitch_rank in pitch_ranks)
    order.extend(camera_id(0, yaw_index) for yaw_index in range(views_per_layer - 1, 0, -1))

    return tuple(order)


def cyclic_groups(
    camera_order: Sequence[int],
    group_size: int,
    offset: int = 0,
) -> StepGroups:
    """Partition a cyclic camera order into equally sized consecutive groups."""

    order = tuple(camera_order)
    num_views = len(order)
    if num_views <= 0 or group_size <= 0 or num_views % group_size:
        raise ValueError(f"{num_views} cameras must be divisible by positive group_size={group_size}.")
    return tuple(
        tuple(order[(group_start + offset + local_index) % num_views] for local_index in range(group_size))
        for group_start in range(0, num_views, group_size)
    )


def routing_steps(
    *,
    view_plan: ViewPlan,
    num_steps: int,
    tcr_stride: int = 1,
    freeze_after_one_cycle: bool = False,
) -> Routes:
    """Return fixed or TCR-shifted partitions of one global camera ring."""

    if num_steps <= 0:
        raise ValueError(f"num_steps must be positive, got {num_steps}.")
    if tcr_stride <= 0:
        raise ValueError(f"tcr_stride must be positive, got {tcr_stride}.")
    camera_order = denoising_camera_order(view_plan)

    def step_offset(step_index: int) -> int:
        if not view_plan.enable_tcr:
            return 0
        offset = step_index * tcr_stride
        if freeze_after_one_cycle and offset >= view_plan.views_per_group:
            return 0
        return offset

    return tuple(
        cyclic_groups(
            camera_order,
            view_plan.views_per_group,
            step_offset(step_index),
        )
        for step_index in range(num_steps)
    )


def validate_routes(routes: Routes, num_views: int) -> None:
    """Require every routing step to be an equal partition of canonical IDs."""

    if num_views <= 0:
        raise ValueError(f"Target denoising requires a positive camera count, got {num_views}.")
    if not routes:
        raise ValueError("Target denoising requires at least one routing step.")
    if not routes[0] or not routes[0][0]:
        raise ValueError("Target denoising requires non-empty camera groups.")

    num_groups = len(routes[0])
    group_size = len(routes[0][0])
    expected_ids = list(range(num_views))
    for step_index, groups in enumerate(routes):
        if len(groups) != num_groups:
            raise ValueError(f"Routing step {step_index} has {len(groups)} groups; every step must have {num_groups}.")
        if any(len(group) != group_size for group in groups):
            raise ValueError(f"Routing step {step_index} contains camera groups with inconsistent sizes.")
        camera_ids = sorted(camera_id for group in groups for camera_id in group)
        if camera_ids != expected_ids:
            raise ValueError(
                f"Routing step {step_index} is not a disjoint partition of cameras 0..{num_views - 1}: {groups}."
            )
