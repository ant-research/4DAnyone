"""Use the project page's black surfaces, fine borders and quiet pill buttons."""

import base64
from pathlib import Path

import gradio as gr

from fdanyone.skeleton.keypoints import RED

COLORS = {
    "body_background_fill": "#000000",
    "body_text_color": "#F5F5F7",
    "body_text_color_subdued": "#8E8E93",
    "background_fill_primary": "#121214",
    "background_fill_secondary": "#1D1D1F",
    "block_background_fill": "#121214",
    "block_border_color": "#424245",
    "block_label_background_fill": "transparent",
    "block_label_text_color": "#8E8E93",
    "block_title_text_color": "#F5F5F7",
    "block_info_text_color": "#8E8E93",
    "panel_background_fill": "#121214",
    "panel_border_color": "#424245",
    "border_color_primary": "#424245",
    "border_color_accent": "#55555A",
    "border_color_accent_subdued": "#424245",
    "color_accent_soft": "#1D1D1F",
    "input_background_fill": "#1D1D1F",
    "input_background_fill_focus": "#1D1D1F",
    "input_background_fill_hover": "#2A2A2D",
    "input_border_color": "#424245",
    "input_border_color_focus": "#3274D8",
    "input_border_color_hover": "#55555A",
    "input_placeholder_color": "#76767B",
    "checkbox_background_color": "#1D1D1F",
    "checkbox_background_color_selected": "#3274D8",
    "checkbox_border_color": "#55555A",
    "checkbox_border_color_selected": "#3274D8",
    "checkbox_label_background_fill": "#1D1D1F",
    "checkbox_label_background_fill_hover": "#2A2A2D",
    "checkbox_label_background_fill_selected": "#2A2A2D",
    "checkbox_label_border_color": "#424245",
    "checkbox_label_border_color_selected": "#3274D8",
    "checkbox_label_text_color": "#F5F5F7",
    "checkbox_label_text_color_selected": "#F5F5F7",
    "link_text_color": "#3274D8",
    "link_text_color_hover": "#4685E3",
    "slider_color": "#3274D8",
    "loader_color": "#3274D8",
    "accordion_text_color": "#F5F5F7",
    "error_background_fill": "#1D1D1F",
    "error_text_color": "#F5F5F7",
    "error_border_color": "#55555A",
}
for variant in ("primary", "secondary", "cancel"):
    COLORS.update(
        {
            f"button_{variant}_background_fill": "#1D1D1F",
            f"button_{variant}_background_fill_hover": "#2A2A2D",
            f"button_{variant}_border_color": "#424245",
            f"button_{variant}_border_color_hover": "#55555A",
            f"button_{variant}_text_color": "#F5F5F7",
            f"button_{variant}_text_color_hover": "#F5F5F7",
            f"button_{variant}_shadow": "none",
            f"button_{variant}_shadow_hover": "none",
            f"button_{variant}_shadow_active": "none",
        }
    )

THEME = gr.themes.Base(font=["Lato", "system-ui", "sans-serif"]).set(
    **COLORS,
    **{f"{key}_dark": value for key, value in COLORS.items()},
    color_accent="#3274D8",
    block_shadow="none",
    block_shadow_dark="none",
    input_shadow="none",
    input_shadow_dark="none",
    block_radius="12px",
    input_radius="8px",
    button_border_width="1px",
    button_border_width_dark="1px",
    checkbox_label_border_width="1px",
    checkbox_label_border_width_dark="1px",
    button_large_radius="999px",
    button_medium_radius="999px",
    button_small_radius="999px",
    button_large_text_weight="400",
    button_medium_text_weight="400",
    button_small_text_weight="400",
    button_transform_hover="none",
    button_transform_active="none",
    block_title_text_weight="400",
    layout_gap="16px",
)

# Embed the project's small font files so localhost use needs no font CDN or extra route.
_assets = Path(__file__).with_name("assets")
_fonts = (_assets / "fonts.css").read_text()
for _path in _assets.glob("*.woff2"):
    _encoded = base64.b64encode(_path.read_bytes()).decode("ascii")
    _fonts = _fonts.replace(f"../fonts/{_path.name}", f"data:font/woff2;base64,{_encoded}")
CSS = (
    _fonts
    + f".gradio-container {{ --space-red: rgb{RED}; }}\n"
    + "".join((_assets / name).read_text() for name in ("workbench.css", "display.css", "monitor.css"))
)
