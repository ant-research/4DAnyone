"""Short option descriptions shared by editable controls and saved arguments."""

import html
from pathlib import Path

DESCRIPTIONS = {
    "Source": "The input video for this task. It must contain at least 121 usable frames after Clip Start.",
    "Output": "The folder for this task's saved settings, recovered motion and generated videos.",
    "Clip Start": (
        "Where to start in the source video, in seconds. Inference uses the next 121 frames; "
        "the slider leaves enough video for a full clip."
    ),
    "No. Layers": (
        "Use one to five camera rings around the person. Each layer has its own pitch and the same number of views."
    ),
    "Pitches": (
        "Each layer's camera elevation, in degrees. Positive angles look down from above; negative angles look up. "
        "Use distinct integers from −15° to 45°."
    ),
    "Views Per Layer": (
        "Evenly spaced cameras on each layer. More views give more angles and take longer to generate. "
        "Available values keep the total view count divisible by six."
    ),
    "Start Yaw": (
        "The first camera's horizontal angle on every layer. 0° faces the person; change this to rotate the whole rig."
    ),
    "Yaw Span": (
        "How far each layer wraps around the person. 360° makes a full ring; smaller spans cover an arc. "
        "The end angle is excluded to avoid duplicate views."
    ),
    "Attention": "Auto selects a suitable attention backend for your GPUs.",
    "Turbo Model": "Use 4DAnyone-Turbo for faster generation. Turn this off to use the Base model.",
    "RCP": "Use shared reference views to improve appearance consistency across generated views.",
    "TCR": "Share context between view groups to improve structural consistency across generated views.",
    "GPUs": (
        "Select one or more CUDA GPUs for inference. All available GPUs are selected by default. "
        "Numbers follow CUDA_VISIBLE_DEVICES when it is set."
    ),
}
HELP_JS = Path(__file__).with_name("assets").joinpath("help.js").read_text()


def option_label(label: str, *, context: str = "edit") -> str:
    """Native popovers keep click-away, Escape and keyboard focus in the browser."""
    identifier = f"help-{context}-{label.lower().replace(' ', '-').replace('.', '')}"
    text = html.escape(label)
    return (
        '<span class="option-label">'
        f'<button type="button" class="help-button" popovertarget="{identifier}" '
        f'aria-label="About {text}">{text}</button>'
        f'<span id="{identifier}" class="option-help" popover="auto" role="note" '
        f'aria-labelledby="{identifier}-title">'
        f'<span class="help-heading"><strong id="{identifier}-title">{text}</strong>'
        f'<button type="button" popovertarget="{identifier}" popovertargetaction="hide" '
        'aria-label="Close Description">×</button></span>'
        f'<span class="help-description">{html.escape(DESCRIPTIONS[label])}</span></span></span>'
    )
