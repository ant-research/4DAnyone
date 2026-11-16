"""Training settings at the workflow/checkpoint boundary; components take explicit arguments."""

import math

# Fixed algorithm settings. User-facing defaults are declared below in DEFAULTS.
FIXED = {
    "checkpoint_steps": [],
    "carve_chunk": 1000000,
    "space_scale": 0.1,
    "point_fraction": 0.333333333,
    "initial_opacity": 0.1,
    "initial_scale": 0.3,
    "initial_span": 3.0,
    "sh_degree": 3,
    "marginal_threshold": 0.05,
    "near": 0.2,
    "far": 20.0,
    "densify_from": 500,
    "densify_until": None,
    "prune_until": None,
    "densify_every": 100,
    "opacity_reset_every": 15000,
    "opacity_reset_radius": 1.5,
    "sh_every": 1000,
    "sh_gradient_threshold": 1e-06,
    "view_dependent_ratio": 0.15,
    "gradient_threshold": 0.0002,
    "size_threshold": 0.01,
    "min_opacity": 0.005,
    "discard_opacity": 0.0001,
    "min_gradient": 0.0,
    "max_scene_scale": 10000.0,
    "min_screen_radius": -1e-06,
    "xyz_lr": 0.00016,
    "xyz_lr_final": 1.6e-05,
    "lr_steps": 150000,
    "time_lr": 0.00016,
    "scale_lr": 0.005,
    "rotation_lr": 0.001,
    "opacity_lr": 0.05,
    "dc_lr": 0.0025,
    "sh_lr": 0.000125,
    "perceptual_include_rgb": False,
    "perceptual_weights": "",
}
DEFAULTS = {
    "steps": 100000,
    "batch_size": 4,
    "image_scale": 1.0,
    "voxel_size": 0.025,
    "bounds": ((-3.0, -3.0, -3.0), (3.0, 3.0, 3.0)),
    "seed": 42,
    "l1_weight": 0.8,
    "ssim_weight": 0.2,
    "mask_weight": 0.4,
    "background_color": "random",
    "perceptual_weight": 0.5,
    "perceptual_start_step": 75000,
    "perceptual_compute_dtype": "bfloat16",
    "loader_workers": 4,
    "save_every": 5000,
    "log_every": 100,
}
PUBLIC = frozenset(DEFAULTS)
FIELDS = FIXED.keys() | PUBLIC
EXECUTION = frozenset(
    ("loader_workers", "save_every", "log_every", "carve_chunk", "checkpoint_steps", "perceptual_weights")
)


def training_settings(options):
    """Combine user options with algorithm settings and resolve the schedule."""
    return check_settings({**FIXED, **DEFAULTS, **options})


def check_settings(values):
    """Validate and normalize a complete recipe, including when restoring it."""
    missing, extra = FIELDS - values.keys(), values.keys() - FIELDS
    if missing or extra:
        raise ValueError(f"Saved recipe fields differ: missing={sorted(missing)}, extra={sorted(extra)}")
    values = dict(values)
    if type(values["steps"]) is not int or values["steps"] <= 0:
        raise ValueError("steps must be a positive integer")
    for name, default in (("densify_until", values["steps"] // 2), ("prune_until", values["steps"])):
        if values[name] is None:
            values[name] = default
    for name in [
        "steps",
        "batch_size",
        "seed",
        "loader_workers",
        "save_every",
        "log_every",
        "carve_chunk",
        "sh_degree",
        "densify_from",
        "densify_every",
        "opacity_reset_every",
        "sh_every",
        "lr_steps",
        "perceptual_start_step",
        "densify_until",
        "prune_until",
    ]:
        if type(values[name]) is not int or values[name] < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    for name in [
        "image_scale",
        "voxel_size",
        "space_scale",
        "point_fraction",
        "initial_opacity",
        "initial_scale",
        "initial_span",
        "marginal_threshold",
        "near",
        "far",
        "opacity_reset_radius",
        "sh_gradient_threshold",
        "view_dependent_ratio",
        "gradient_threshold",
        "size_threshold",
        "min_opacity",
        "discard_opacity",
        "min_gradient",
        "max_scene_scale",
        "min_screen_radius",
        "xyz_lr",
        "xyz_lr_final",
        "time_lr",
        "scale_lr",
        "rotation_lr",
        "opacity_lr",
        "dc_lr",
        "sh_lr",
        "l1_weight",
        "ssim_weight",
        "perceptual_weight",
        "mask_weight",
    ]:
        value = values[name]
        if type(value) not in (int, float) or not math.isfinite(value) or (value < 0 and name != "min_screen_radius"):
            raise ValueError(f"{name} must be a finite nonnegative number")
        values[name] = float(value)
    for name in (
        "steps",
        "batch_size",
        "save_every",
        "log_every",
        "carve_chunk",
        "densify_every",
        "opacity_reset_every",
        "sh_every",
        "lr_steps",
        "space_scale",
        "voxel_size",
    ):
        if values[name] <= 0:
            raise ValueError(f"{name} must be positive")
    if not 0 < values["point_fraction"] <= 1 or not 0 < values["image_scale"] <= 1:
        raise ValueError("point_fraction and image_scale must lie in (0, 1]")
    if not 0 < values["marginal_threshold"] < 1 or not 0 < values["initial_opacity"] < 1:
        raise ValueError("Invalid Gaussian opacity/temporal threshold")
    if values["sh_degree"] not in range(4) or values["far"] <= values["near"]:
        raise ValueError("Supported SH degrees are 0..3; far must exceed near")
    if values["perceptual_compute_dtype"] not in ("float32", "bfloat16"):
        raise ValueError("perceptual_compute_dtype must be float32 or bfloat16")
    if type(values["perceptual_include_rgb"]) is not bool:
        raise ValueError("perceptual_include_rgb must be a boolean")
    if any(type(step) is not int or not 0 < step <= values["steps"] for step in values["checkpoint_steps"]):
        raise ValueError("checkpoint_steps must contain positive steps within the training budget")
    values["checkpoint_steps"] = list(values["checkpoint_steps"])
    if values["background_color"] not in ("black", "random"):
        raise ValueError("background_color must be black or random")
    bounds = values["bounds"]
    if len(bounds) != 2 or any(len(row) != 3 for row in bounds):
        raise ValueError("bounds must be two xyz corners")
    if any(type(x) not in (int, float) or not math.isfinite(x) for row in bounds for x in row):
        raise ValueError("bounds must be finite")
    if any(a >= b for a, b in zip(*bounds, strict=True)):
        raise ValueError("bounds must have positive extent")
    values["bounds"] = [list(row) for row in bounds]
    return values


def training_identity(settings):
    """Numerical settings, excluding execution-only options and the weight path."""
    return {key: value for key, value in settings.items() if key not in EXECUTION}
