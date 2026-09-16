"""Named inference controls and a read-only rendering of the saved CLI arguments."""

from __future__ import annotations

import html

import gradio as gr

from fdanyone.device import validate_gpu_ids
from fdanyone.space.controls import (
    MAX_LAYERS,
    PITCH_PRESETS,
    PITCHES_HTML,
    PITCHES_JS,
    SLIDER_HTML,
    SLIDER_JS,
    VIEWS_PER_GROUP,
    describe_gpus,
    gpu_model,
    validate_view_count,
    view_counts,
)
from fdanyone.space.gpus import available_gpus
from fdanyone.space.help import option_label
from fdanyone.space.settings import complete_options, layout_options, make_options, validate_options
from fdanyone.space.source import ClipTiming
from fdanyone.space.task import SavedTask, SpaceConfig
from fdanyone.views import MAX_PITCH, MIN_PITCH

ATTENTION_LABELS = {
    "auto": "Auto",
    "sdpa": "SDPA",
    "flash_attn_3": "Flash Attention 3",
    "sageattention": "SageAttention",
}


class InferenceForm:
    def __init__(self, config: SpaceConfig):
        self.config = config
        models = available_gpus()
        self.gpus = list(range(len(models)))
        self.gpu_description = describe_gpus({index: gpu_model(name) for index, name in enumerate(models)})
        timing = ClipTiming.read(config.video_path)
        self.start_max = timing.start_max("auto") if timing else 0
        self.defaults = complete_options(
            dict(views_per_layer=6, gpu_ids=config.gpu_ids, attention_backend=config.attention_backend)
        )
        self.fields = {}

    def slider(self, name, label, elem_id, **props):
        self.fields[name] = gr.HTML(
            value=self.defaults[name],
            label=label,
            label_html=option_label(label),
            input_id=f"{elem_id}-input",
            interactive=True,
            html_template=SLIDER_HTML,
            js_on_load=SLIDER_JS,
            apply_default_css=False,
            elem_id=elem_id,
            **props,
        )
        return self.fields[name]

    def clip_control(self):
        self.slider(
            "start_time",
            "Clip Start",
            "clip-start",
            minimum=0,
            maximum=self.start_max,
            step=0.01,
            precision=2,
            minimum_decimals=1,
            suffix=" s",
            commit_on_change=True,
        )
        self.saved_clip = gr.HTML("", visible=False, elem_id="saved-clip-start")

    def parameters(self):
        self.note = gr.Markdown("", elem_id="parameter-note")
        self.saved = gr.HTML("", visible=False, elem_id="saved-parameters")
        with gr.Column(min_width=0, elem_id="settings-grid") as self.panel:
            with gr.Column(min_width=0, elem_classes="settings-section"):
                gr.HTML(
                    '<div class="section-heading"><h3>Camera Layout</h3>'
                    '<output class="camera-view-count" aria-live="polite">6 views in total</output></div>',
                    elem_id="camera-heading",
                )
                self.fields["layer_pitches"] = gr.HTML(
                    value=self.defaults["layer_pitches"],
                    views=6,
                    min_pitch=MIN_PITCH,
                    max_pitch=MAX_PITCH,
                    max_layers=MAX_LAYERS,
                    pitch_presets=[list(pitches) for pitches in PITCH_PRESETS],
                    view_counts={str(count): list(view_counts(count)) for count in range(1, MAX_LAYERS + 1)},
                    interactive=True,
                    html_template=PITCHES_HTML.replace("{{layers_label}}", option_label("No. Layers")).replace(
                        "{{pitches_label}}", option_label("Pitches")
                    ),
                    js_on_load=PITCHES_JS,
                    apply_default_css=False,
                    elem_id="camera-pitches",
                )
                self.slider("views_per_layer", "Views Per Layer", "camera-views", counts=list(view_counts(1)))
                self.slider("start_yaw", "Start Yaw", "camera-yaw", minimum=-180, maximum=180, step=1, suffix="°")
                self.slider("yaw_span", "Yaw Span", "camera-span", minimum=1, maximum=360, step=1, suffix="°")
            with gr.Column(min_width=0, elem_classes="settings-section"):
                gr.Markdown("### Model")
                with gr.Row(elem_classes="option-row"):
                    gr.HTML(option_label("Attention"), min_width=0)
                    self.fields["attention_backend"] = gr.Dropdown(
                        [(label, value) for value, label in ATTENTION_LABELS.items()],
                        value=self.config.attention_backend,
                        label="Attention",
                        show_label=False,
                        min_width=0,
                        elem_id="attention-backend",
                    )
                for name, label in [("turbo", "Turbo Model"), ("rcp", "RCP"), ("tcr", "TCR")]:
                    with gr.Row(elem_classes="option-row"):
                        gr.HTML(option_label(label), min_width=0)
                        self.fields[f"enable_{name}"] = gr.Checkbox(
                            value=self.defaults[f"enable_{name}"],
                            label=label,
                            show_label=False,
                            min_width=0,
                            elem_id=f"enable-{name}",
                            elem_classes="model-toggle",
                        )
            with gr.Column(min_width=0, elem_classes="settings-section"):
                gr.HTML(
                    '<div class="section-heading"><h3>'
                    + option_label("GPUs")
                    + '</h3><span class="gpu-description">'
                    + html.escape(self.gpu_description)
                    + "</span></div>",
                    elem_id="gpu-heading",
                )
                self.fields["gpu_ids"] = gr.CheckboxGroup(
                    choices=[(str(index), index) for index in self.gpus],
                    value=self.gpus if self.config.gpu_ids is None else list(self.config.gpu_ids),
                    label="GPUs",
                    show_label=False,
                    elem_id="gpu-selection",
                )

    @property
    def inputs(self):
        return list(self.fields.values())

    @property
    def outputs(self):
        return [self.saved_clip, self.note, self.saved, self.panel, *self.inputs]

    def decode(self, values) -> dict:
        return dict(zip(self.fields, values, strict=True))

    def values(self, task: SavedTask | None) -> dict:
        options = task.options if task else self.defaults
        return {
            **{name: options[name] for name in self.fields},
            "gpu_ids": list(self.gpus if options["gpu_ids"] is None else options["gpu_ids"]),
        }

    @staticmethod
    def layout(values, *, editable=False) -> dict:
        layout = layout_options(
            *(values[name] for name in ("views_per_layer", "layer_pitches", "start_yaw", "yaw_span"))
        )
        if editable:
            validate_view_count(layout["views_per_layer"], len(layout["layer_pitches"]))
            layout["layer_pitches"] = sorted(layout["layer_pitches"], reverse=True)
        return layout

    def options(self, values) -> dict:
        layout = self.layout(values, editable=True)
        validate_gpu_ids(values["gpu_ids"], len(self.gpus))
        options = make_options(
            str(self.config.video_path),
            layout["views_per_layer"],
            layout["layer_pitches"],
            layout["start_yaw"],
            layout["yaw_span"],
            values["enable_turbo"],
            min(values["start_time"], self.start_max),
        )
        options.update(
            gpu_ids=None if values["gpu_ids"] == self.gpus else values["gpu_ids"],
            target_fps="auto",
            views_per_group=VIEWS_PER_GROUP,
            **{name: values[name] for name in ("enable_rcp", "enable_tcr", "attention_backend")},
            model_dir=str(self.config.model_dir),
            gvhmr_root=str(self.config.gvhmr_root),
        )
        validate_options(options)
        return options

    def update(self, task: SavedTask | None, values: dict) -> dict:
        locked = task is not None
        detail = task.error if task else ""
        if task and not task.complete and task.source is None:
            detail = "Original Source Video Unavailable Or Changed"
        updates = {
            self.note: gr.update(value=html.escape(detail), visible=bool(detail)),
            self.panel: gr.update(visible=not locked),
            self.saved: gr.update(value=self.summary(task) if task else "", visible=locked),
            self.saved_clip: gr.update(
                value='<dl class="clip-summary">'
                + saved_row("Clip Start", f"{float(values['start_time'])} s")
                + "</dl>",
                visible=locked,
            ),
            **self.field_updates(values, interactive=not locked),
        }
        updates[self.fields["start_time"]]["visible"] = not locked
        return updates

    def field_updates(self, values: dict, *, interactive: bool) -> dict:
        """Send complete HTML props so controls survive hiding and remounting."""
        props = {
            name: {
                **(component.props if isinstance(component, gr.HTML) else {}),
                "value": values[name],
                "interactive": interactive,
            }
            for name, component in self.fields.items()
        }
        props["start_time"].update(
            maximum=max(self.start_max, values["start_time"]),
            interactive=interactive and self.start_max > 0,
        )
        props["layer_pitches"]["views"] = values["views_per_layer"]
        props["views_per_layer"]["counts"] = list(view_counts(len(values["layer_pitches"])))
        choices = sorted(set(self.gpus) | set(values["gpu_ids"])) if not interactive else self.gpus
        props["gpu_ids"]["choices"] = [(str(index), index) for index in choices]
        return {component: gr.update(**props[name]) for name, component in self.fields.items()}

    def summary(self, task: SavedTask) -> str:
        options = task.options
        pitches = options["layer_pitches"]
        gpu_ids = options["gpu_ids"]
        gpu_names = ", ".join(map(str, self.gpus if gpu_ids is None else gpu_ids))
        if gpu_ids is None:
            gpu_names = f"All Available · {gpu_names}"
        camera = [
            ("No. Layers", len(pitches)),
            ("Pitches", ", ".join(f"{pitch}°" for pitch in pitches)),
            ("Views Per Layer", options["views_per_layer"]),
            ("Start Yaw", f"{options['start_yaw']}°"),
            ("Yaw Span", f"{options['yaw_span']}°"),
        ]
        model = [
            ("Attention", ATTENTION_LABELS[options["attention_backend"]]),
            ("Turbo Model", "On" if options["enable_turbo"] else "Off"),
            ("RCP", "On" if options["enable_rcp"] else "Off"),
            ("TCR", "On" if options["enable_tcr"] else "Off"),
        ]
        total = options["views_per_layer"] * len(pitches)
        return (
            '<section class="saved-section"><div class="section-heading"><h3>Camera Layout</h3>'
            f'<span class="camera-view-count">{total} views in total</span></div><dl>'
            + "".join(saved_row(*row) for row in camera)
            + '</dl></section><section class="saved-section"><div class="section-heading"><h3>Model</h3></div><dl>'
            + "".join(saved_row(*row) for row in model)
            + '</dl></section><section class="saved-section"><div class="section-heading"><h3>'
            + option_label("GPUs", context="saved")
            + "</h3>"
            + '<span class="gpu-description">'
            + html.escape(self.gpu_description)
            + '</span></div><div class="saved-gpus" data-parameter="GPUs">'
            + html.escape(gpu_names or "Unavailable")
            + "</div></section>"
        )


def saved_row(label, value):
    return (
        f'<div class="saved-option" data-parameter="{label}"><dt>'
        + option_label(label, context="saved")
        + f"</dt><dd>{html.escape(str(value))}</dd></div>"
    )
