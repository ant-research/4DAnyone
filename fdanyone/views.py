"""Resolve the reader-facing target-view layout and inference grouping."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fdanyone.config import CAMERA
from fdanyone.errors import ConfigurationError

VALID_VIEWS_PER_GROUP = (4, 6)
MIN_PITCH = -15
MAX_PITCH = 45

# RCP uses the canonical proposal cameras seen during training. The resolved
# group size selects a prefix; at most the first four become target references.
RCP_CAMERA_ORDER = (4, 9, 14, 19, 0, 12)


@dataclass(frozen=True)
class TargetView:
    """One requested camera in the layer-major public view order."""

    camera_id: int
    layer_index: int
    pitch: int
    yaw: float


@dataclass(frozen=True)
class ViewPlan:
    """Validated target cameras and method components for one run."""

    views_per_layer: int
    layer_pitches: tuple[int, ...]
    start_yaw: int
    yaw_span: int
    views_per_group: int
    enable_rcp: bool
    enable_tcr: bool

    @property
    def num_layers(self) -> int:
        return len(self.layer_pitches)

    @property
    def num_target_views(self) -> int:
        return self.views_per_layer * self.num_layers

    @property
    def num_groups(self) -> int:
        return self.num_target_views // self.views_per_group

    @property
    def target_views(self) -> tuple[TargetView, ...]:
        step = self.yaw_span / self.views_per_layer
        return tuple(
            TargetView(
                camera_id=layer_index * self.views_per_layer + view_index,
                layer_index=layer_index,
                pitch=pitch,
                yaw=self.start_yaw + view_index * step,
            )
            for layer_index, pitch in enumerate(self.layer_pitches)
            for view_index in range(self.views_per_layer)
        )

    @property
    def front_camera_ids(self) -> tuple[int, ...]:
        return tuple(view.camera_id for view in self.target_views if abs(view.yaw % 360.0) < 1e-8)

    @property
    def rcp_camera_ids(self) -> tuple[int, ...]:
        return RCP_CAMERA_ORDER[: self.views_per_group] if self.enable_rcp else ()

    @property
    def is_canonical_target_ring(self) -> bool:
        return (
            self.views_per_layer == CAMERA.count
            and self.layer_pitches == (int(CAMERA.pitch_degrees),)
            and self.start_yaw == 0
            and self.yaw_span == 360
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "views_per_layer": self.views_per_layer,
            "layer_pitches": list(self.layer_pitches),
            "start_yaw": self.start_yaw,
            "yaw_span": self.yaw_span,
            "views_per_group": self.views_per_group,
            "enable_rcp": self.enable_rcp,
            "enable_tcr": self.enable_tcr,
        }

    @classmethod
    def from_dict(cls, value: object) -> ViewPlan:
        if not isinstance(value, dict):
            raise ConfigurationError("View plan must be a JSON object.")
        try:
            return resolve_view_plan(
                views_per_layer=value["views_per_layer"],
                layer_pitches=value["layer_pitches"],
                start_yaw=value["start_yaw"],
                yaw_span=value["yaw_span"],
                views_per_group=value["views_per_group"],
                enable_rcp=value["enable_rcp"],
                enable_tcr=value["enable_tcr"],
            )
        except KeyError as exc:
            raise ConfigurationError(f"View plan is missing {exc.args[0]!r}.") from None


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{name} must be an integer, got {value!r}.")
    return value


def _layer_pitches(value: object) -> tuple[int, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise ConfigurationError("layer_pitches must be a non-empty list of integer degrees.")
    pitches = tuple(_integer("Each layer pitch", pitch) for pitch in value)
    if len(set(pitches)) != len(pitches):
        raise ConfigurationError(f"layer_pitches must not contain duplicates, got {list(pitches)}.")
    invalid = [pitch for pitch in pitches if not MIN_PITCH <= pitch <= MAX_PITCH]
    if invalid:
        raise ConfigurationError(
            f"Each layer pitch must be between {MIN_PITCH} and {MAX_PITCH} degrees, got {invalid}."
        )
    return pitches


def _group_size(value: int | str, views_per_layer: int) -> int:
    if isinstance(value, str):
        if value.lower() == "auto":
            divisors = tuple(size for size in VALID_VIEWS_PER_GROUP if views_per_layer % size == 0)
            if not divisors:
                raise ConfigurationError(f"views_per_layer ({views_per_layer}) must be divisible by 4 or 6.")
            return max(divisors)
        try:
            value = int(value)
        except ValueError:
            raise ConfigurationError(
                f"views_per_group must be 'auto' or one of {VALID_VIEWS_PER_GROUP}, got {value!r}."
            ) from None
    value = _integer("views_per_group", value)
    if value not in VALID_VIEWS_PER_GROUP:
        raise ConfigurationError(f"views_per_group must be one of {VALID_VIEWS_PER_GROUP}, got {value!r}.")
    if views_per_layer % value:
        raise ConfigurationError(f"views_per_layer ({views_per_layer}) must be divisible by views_per_group ({value}).")
    return value


def resolve_view_plan(
    *,
    views_per_layer: int = 24,
    layer_pitches: Sequence[int] = (15,),
    start_yaw: int = 0,
    yaw_span: int = 360,
    views_per_group: int | str = "auto",
    enable_rcp: bool = True,
    enable_tcr: bool = True,
) -> ViewPlan:
    """Validate the compact CLI settings before expensive work starts."""

    views_per_layer = _integer("views_per_layer", views_per_layer)
    if views_per_layer <= 0:
        raise ConfigurationError(f"views_per_layer must be positive, got {views_per_layer}.")
    pitches = _layer_pitches(layer_pitches)
    start_yaw = _integer("start_yaw", start_yaw)
    start_yaw = (start_yaw + 180) % 360 - 180
    yaw_span = _integer("yaw_span", yaw_span)
    if not 0 < yaw_span <= 360:
        raise ConfigurationError(f"yaw_span must be between 1 and 360 degrees, got {yaw_span}.")
    resolved_group_size = _group_size(views_per_group, views_per_layer)
    if not isinstance(enable_rcp, bool):
        raise ConfigurationError(f"enable_rcp must be True or False, got {enable_rcp!r}.")
    if not isinstance(enable_tcr, bool):
        raise ConfigurationError(f"enable_tcr must be True or False, got {enable_tcr!r}.")

    # Up to six requested targets are cheaper and clearer to generate directly.
    rcp_active = enable_rcp and views_per_layer * len(pitches) > 6
    return ViewPlan(
        views_per_layer=views_per_layer,
        layer_pitches=pitches,
        start_yaw=start_yaw,
        yaw_span=yaw_span,
        views_per_group=resolved_group_size,
        enable_rcp=rcp_active,
        enable_tcr=enable_tcr,
    )
