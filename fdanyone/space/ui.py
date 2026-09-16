"""Single-task page: render controls, submit work and collect independent previews."""

from __future__ import annotations

import html
from concurrent.futures import CancelledError
from dataclasses import dataclass
from pathlib import Path

import gradio as gr

from fdanyone.errors import FourDAnyoneError
from fdanyone.space.display import DISPLAY_HTML, DISPLAY_JS
from fdanyone.space.form import InferenceForm
from fdanyone.space.help import HELP_JS, option_label
from fdanyone.space.jobs import FINISHED, JobManager
from fdanyone.space.monitor import MONITOR_HTML, MONITOR_JS, preparing_monitor
from fdanyone.space.previews import motion_available, prepare_preview
from fdanyone.space.task import path_label
from fdanyone.space.viewer import export_layout_update, scene_info
from fdanyone.space.web_assets import display_payload, prepare_web_assets

ERRORS = (FourDAnyoneError, OSError, ValueError, TypeError, KeyError)
ASSETS = Path(__file__).with_name("assets")


@dataclass
class Session:
    """One tab's observation and pending preview; inference belongs to JobManager."""

    signature: list | None = None
    preview: str | None = None
    scene: dict | None = None
    motion_requested: bool = False
    submitting: bool = False
    console: str | None = None


def build_space(manager: JobManager) -> gr.Blocks:
    config = manager.config
    form = InferenceForm(config)
    assets = prepare_web_assets(config.cache_dir)
    with gr.Blocks(title="4DAnyone Space", analytics_enabled=False) as space:
        session = gr.State(Session())
        timer = gr.Timer(1)
        with gr.Row(elem_id="space-workspace"):
            viewer = gr.HTML(
                value=None,
                assets=assets,
                html_template=DISPLAY_HTML,
                js_on_load=DISPLAY_JS,
                apply_default_css=False,
                elem_id="space-viewer",
            )
            with gr.Column(min_width=0, elem_id="space-sidebar"):
                gr.Markdown("# 4DAnyone Space", elem_id="space-heading")
                with gr.Column(min_width=0, elem_id="task-panel"):
                    gr.Markdown("### Data", elem_id="data-heading")
                    task_info = gr.HTML("", js_on_load=HELP_JS, elem_id="task-info")
                    form.clip_control()
                with (
                    gr.Column(min_width=0, elem_id="space-controls"),
                    gr.Column(min_width=0, elem_id="parameters-scroll"),
                ):
                    form.parameters()
                with gr.Column(min_width=0, elem_id="execution-area"):
                    scene_status = gr.Markdown("", elem_id="scene-status")
                    status = gr.Markdown("", elem_id="run-status")
                    run_monitor = gr.HTML(
                        value=None,
                        html_template=MONITOR_HTML,
                        js_on_load=MONITOR_JS,
                        apply_default_css=False,
                        elem_id="run-monitor",
                    )
                    with gr.Row(elem_id="run-actions"):
                        run = gr.Button(
                            "Run Inference",
                            variant="primary",
                            interactive=False,
                            min_width=0,
                            elem_id="run-inference",
                        )
                        stop = gr.Button(
                            "Stop",
                            interactive=False,
                            visible=False,
                            elem_id="stop-inference",
                            min_width=60,
                            scale=0,
                        )
                        delete = gr.HTML(
                            value=None,
                            html_template=(ASSETS / "delete.html").read_text(),
                            js_on_load=(ASSETS / "delete.js").read_text(),
                            apply_default_css=False,
                            visible=False,
                            min_width=0,
                            scale=0,
                            elem_id="delete-output",
                        )
                    log_download = gr.DownloadButton("Run Log", visible=False, size="sm", min_width=0)

        outputs = [
            session,
            timer,
            task_info,
            run,
            stop,
            delete,
            status,
            run_monitor,
            log_download,
            scene_status,
            viewer,
            *form.outputs,
        ]

        def skip():
            return {component: gr.skip() for component in outputs}

        def controls(record, values):
            job = manager.current_job()
            active = job is not None and job.state not in FINISHED
            action = "Inference Running" if active else "Run Inference"
            if not active and record:
                action = "Completed" if record.complete else "Resume Inference"
            source = record.options["video_path"] if record else config.video_path
            summary = (
                '<dl class="task-paths">'
                + "".join(
                    f'<div class="task-path"><dt>{option_label(label)}</dt><dd>'
                    f'<code tabindex="0" aria-label="{label} Path" '
                    f'title="{html.escape(str(path), quote=True)}">'
                    f"{html.escape(path_label(path))}</code></dd></div>"
                    for label, path in [("Source", source), ("Output", config.output_dir)]
                )
                + "</dl>"
            )
            return {
                **form.update(record, values),
                task_info: summary,
                run: gr.update(
                    value=action, interactive=not active and bool(record.resumable if record else source.is_file())
                ),
                stop: gr.update(value="Stop", interactive=active, visible=active),
                delete: gr.update(
                    value={"key": manager.deletion_key(), "output": path_label(config.output_dir)}
                    if record and not record.complete and not active
                    else None,
                    visible=bool(record and not record.complete and not active),
                ),
            }

        def show_recording(tab, path):
            tab.scene = info = scene_info(path)
            return {
                session: tab,
                viewer: display_payload(path, info),
                scene_status: "",
                timer: gr.update(active=not info["target_count"]),
            }

        def show_monitor(tab, payload):
            if payload is None:
                tab.console = None
                return {session: tab, run_monitor: None}
            previous, tab.console = tab.console, payload["log"]
            if tab.console == previous:
                payload = {key: value for key, value in payload.items() if key != "log"}
            return {session: tab, run_monitor: payload}

        def request_preview(tab, record, values):
            tab.motion_requested = record is not None and motion_available(config.output_dir)
            tab.preview = manager.previews.submit(
                tab.preview,
                prepare_preview,
                config,
                record,
                form.layout(values, editable=record is None),
                values["start_time"],
                tab.motion_requested,
            )
            return {
                session: tab,
                scene_status: "Preparing Preview…",
                timer: gr.update(active=True),
            }

        def initialize(tab):
            record = manager.record()
            values = form.values(record)
            tab.signature = manager.signature()
            return {
                **controls(record, values),
                **show_monitor(tab, manager.monitor(record)),
                **request_preview(tab, record, values),
            }

        def reset_task(tab):
            tab.scene = None
            return {
                **initialize(tab),
                viewer: None,
                status: "",
                log_download: gr.update(value=None, visible=False),
            }

        def delete_run(confirmation, tab, *raw_values):
            try:
                manager.delete_output(confirmation["key"])
                return reset_task(tab)
            except ERRORS as exc:
                record = manager.record()
                return {
                    **controls(record, form.values(record) if record else form.decode(raw_values)),
                    status: f"Cannot Delete Output: {html.escape(str(exc))}",
                }

        def start_run(tab, *raw_values):
            values = form.decode(raw_values)
            tab.submitting = True
            try:
                yield {
                    **form.field_updates(values, interactive=False),
                    run: gr.update(value="Starting Inference", interactive=False),
                    delete: gr.update(value=None, visible=False),
                    **show_monitor(tab, preparing_monitor()),
                    status: "",
                }
                # Every tab resumes the saved request; editable browser values
                # can only create the first request for this output directory.
                record = manager.record()
                job = manager.resume() if record else manager.submit(form.options(values))
                record = manager.record()
                tab.signature = None
                updates = {
                    **controls(record, form.values(record)),
                    **show_monitor(tab, manager.snapshot(job.token)["monitor"]),
                    status: "",
                    log_download: gr.update(visible=False),
                }
            except (*ERRORS, ImportError) as exc:
                record = manager.record()
                updates = {
                    **controls(record, form.values(record) if record else values),
                    **show_monitor(tab, manager.monitor(record)),
                    status: f"Cannot Start: {html.escape(str(exc))}",
                }
            finally:
                tab.submitting = False
            yield updates

        def change_layout(tab, *raw_values):
            if manager.record():
                return skip()
            values = form.decode(raw_values)
            try:
                layout = form.layout(values, editable=True)
                if tab.scene is None or tab.preview:
                    return request_preview(tab, None, values)
                path, tab.scene = export_layout_update(tab.scene, config.cache_dir / "viewer", layout)
                return {session: tab, viewer: display_payload(path, tab.scene, layout_only=True), scene_status: ""}
            except ERRORS as exc:
                return {scene_status: f"Camera Layout: {html.escape(str(exc))}"}

        def change_start(tab, *raw_values):
            if manager.record():
                return skip()
            values = form.decode(raw_values)
            try:
                selected = float(values["start_time"])
                values["start_time"] = min(max(0, selected), form.start_max)
                updates = request_preview(tab, None, values)
                # Valid slider values already live in the browser. Echoing a
                # delayed callback could replace a newer selection.
                if selected != values["start_time"]:
                    field = form.fields["start_time"]
                    updates[field] = form.field_updates(values, interactive=True)[field]
                return updates
            except ERRORS as exc:
                return {scene_status: f"Clip Start: {html.escape(str(exc))}"}

        def follow_task(tab, *raw_values):
            with manager.lock:
                if tab.submitting:
                    return skip()
                updates = {session: tab}
                job = manager.current_job()
                signature = manager.signature()
                if job is None and tab.signature != signature:
                    return reset_task(tab)
                if job and (job.state not in FINISHED or signature != tab.signature):
                    snapshot = manager.snapshot(job.token)
                    updates.update(show_monitor(tab, snapshot["monitor"]))
                    if signature != tab.signature:
                        record = manager.record()
                        updates.update(controls(record, form.values(record) if record else form.decode(raw_values)))
                        tab.signature = signature
                        if snapshot["state"] in FINISHED:
                            updates[status] = ""
                            if snapshot["state"] == "failed" and (job.directory / "inference.log").is_file():
                                updates[log_download] = gr.update(
                                    value=str(job.directory / "inference.log"), visible=True
                                )
                            manager.previews.discard(tab.preview)
                            tab.preview = None
                            if record:
                                updates.update(request_preview(tab, record, form.values(record)))
                    if (
                        snapshot["state"] == "running"
                        and not tab.motion_requested
                        and motion_available(config.output_dir)
                    ):
                        record = manager.record()
                        updates.update(request_preview(tab, record, form.values(record)))
                try:
                    ready = manager.previews.take(tab.preview)
                    if ready:
                        updates.update(show_recording(tab, ready))
                        tab.preview = None
                except CancelledError:
                    tab.preview = None
                except Exception as exc:
                    tab.preview = None
                    updates[scene_status] = f"Preview Unavailable: {html.escape(str(exc))}"
                return updates

        def cancel_run():
            job = manager.current_job()
            message = manager.cancel(job.token if job else None)
            return {status: message, stop: gr.update(value="Stopping…", interactive=False)}

        events = dict(outputs=outputs, concurrency_id="space-controls", concurrency_limit=1, show_progress="hidden")
        space.load(initialize, session, **events)
        gr.on(
            [form.fields[name].input for name in ("views_per_layer", "layer_pitches", "start_yaw", "yaw_span")],
            change_layout,
            [session, *form.inputs],
            trigger_mode="always_last",
            **events,
        )
        form.fields["start_time"].input(
            change_start,
            [session, *form.inputs],
            trigger_mode="always_last",
            **events,
        )
        run.click(start_run, [session, *form.inputs], api_name="run", **events)
        stop.click(cancel_run, outputs=outputs, queue=False, api_name="stop")
        delete.click(delete_run, [delete, session, *form.inputs], api_name=False, **events)
        timer.tick(
            follow_task,
            [session, *form.inputs],
            outputs=outputs,
            queue=False,
            show_progress="hidden",
            api_name=False,
        )
    return space
