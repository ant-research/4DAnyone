"""Shared widget templates, view counts and CUDA labels."""

from __future__ import annotations

import re
from pathlib import Path

from fdanyone.errors import ConfigurationError

PITCH_PRESETS = ((15,), (15, 0), (30, 15, 0), (30, 15, 0, -15), (45, 30, 15, 0, -15))
MAX_LAYERS = len(PITCH_PRESETS)
VIEWS_PER_GROUP = 6
_ASSETS = Path(__file__).with_name("assets")
SLIDER_HTML = (_ASSETS / "slider.html").read_text()
SLIDER_JS = (_ASSETS / "slider.js").read_text()
PITCHES_HTML = (_ASSETS / "pitches.html").read_text()
PITCHES_JS = (_ASSETS / "pitches.js").read_text()


def view_counts(num_layers: int) -> tuple[int, ...]:
    return (6, 8, 12, 16, 24, 36, 48) if num_layers == 3 else (6, 12, 18, 24, 36, 48)


def validate_view_count(views, num_layers):
    if not 1 <= num_layers <= MAX_LAYERS:
        raise ConfigurationError(f"No. Layers must be between 1 and {MAX_LAYERS}.")
    counts = view_counts(num_layers)
    if views not in counts:
        raise ConfigurationError(f"With {num_layers} layers, choose {', '.join(map(str, counts))} views per layer.")


def gpu_model(name: str) -> str:
    """Shorten a driver-provided model name for the GPU heading."""
    name = re.sub(r"\b(NVIDIA|GeForce|Tesla|Quadro)\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\bRTX\s+(?=A\d)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"-(?:SXM\d*|PCIE)-", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+HBM\w*\b", "", name, flags=re.IGNORECASE)
    return name.strip()


def describe_gpus(models: dict[int, str]) -> str:
    """Keep common models concise and mixed-device assignments unambiguous."""
    groups = {}
    for index, name in models.items():
        groups.setdefault(name, []).append(str(index))
    if not groups:
        return "No CUDA GPUs Available"
    if len(groups) == 1:
        return next(iter(groups))
    return "\n".join(f"{', '.join(indices)} · {name}" for name, indices in groups.items())
