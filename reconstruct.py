"""Reconstruct and render a dynamic Gaussian scene from a 4DAnyone result."""

import inspect
import sys

from fire import Fire

from fdanyone.cli import check_arguments
from fdanyone.errors import ConfigurationError
from fdanyone.reconstruction.settings import DEFAULTS
from fdanyone.reconstruction.viewer.shared import view


def reconstruct(data_dir, output_dir, *, resume=True, model_dir=None, masks=None, device="cuda", **training):
    """Carve, train and render a 4DAnyone result. See also: render and view.

    Omitted training options reuse saved settings; conflicting overrides fail.

    Args:
        data_dir: Generated 4DAnyone result.
        output_dir: Reconstruction directory.
        resume: Continue existing work; False replaces reconstruction products and starts over.
        model_dir: Model root (defaults to models).
        masks: Optional existing camera/frame PNG masks.
        steps: Training budget; densification ends halfway through.
        perceptual_start_step: First step with VGG loss (independent of steps).
        perceptual_weight: VGG feature loss weight; 0 disables it.
        perceptual_compute_dtype: bfloat16 or float32; unsupported GPUs use float32.
        background_color: random or black, shared by prediction and target.
    """
    if type(resume) is not bool:
        raise ValueError("resume must be True or False")
    if unknown := training.keys() - DEFAULTS.keys():
        raise TypeError(f"Unknown training options: {sorted(unknown)}")
    from fdanyone.reconstruction.pipeline import run

    return run(str(data_dir), str(output_dir), training, resume=resume, model_dir=model_dir, masks=masks, device=device)


# Fire/Python help show defaults, while **training retains only explicitly supplied options.
_signature = inspect.signature(reconstruct)
reconstruct.__signature__ = _signature.replace(
    parameters=[
        *(p for p in _signature.parameters.values() if p.kind != p.VAR_KEYWORD),
        *(inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=value) for name, value in DEFAULTS.items()),
    ]
)


def render(model, output, *, trajectory="orbit360", time=None, anchor=0, background="black", fps=None, device="cuda"):
    """Render a standalone .npz model. Trajectory: orbit360, orbit180, dataset or a JSON path."""
    from fdanyone.reconstruction.render import render_video

    render_video(str(model), str(output), trajectory, device, time, anchor, background=background, fps=fps)


def main():
    commands = {"render": render, "view": view}
    args = sys.argv[1:]
    function = commands[args.pop(0)] if args and args[0] in commands else reconstruct
    if any(arg in ("--help", "-h") for arg in args):
        args = ["--help"]  # Fire otherwise runs a complete command before showing trailing help.
    else:
        if any(arg in ("-", "--") for arg in args):
            raise SystemExit("Command chaining is not supported. See --help.")
        check_arguments(function, args)
    Fire(
        function, command=args, name="reconstruct.py" + (" " + function.__name__ if function is not reconstruct else "")
    )


if __name__ == "__main__":
    try:
        main()
    except ConfigurationError as exc:
        raise SystemExit(f"error: {exc}") from None
