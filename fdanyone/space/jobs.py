"""Queue local inference and own the complete lifetime of its subprocesses."""

from __future__ import annotations

import concurrent.futures
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field, replace
from pathlib import Path

from fdanyone.errors import ConfigurationError, FourDAnyoneError
from fdanyone.io import lock_output, remove_tree, resolve_output_path, sha256_file
from fdanyone.output_directory import OutputDirectory
from fdanyone.run_request import REQUEST_FILE, read_run_request, save_run_request
from fdanyone.space.monitor import RunMonitor
from fdanyone.space.previews import PreviewLoader
from fdanyone.space.settings import complete_options
from fdanyone.space.source import probe_input
from fdanyone.space.task import SavedTask, SpaceConfig, ensure_new_output, read_task, saved_request, source_matches

FINISHED = {"complete", "failed", "cancelled"}
REPOSITORY = Path(__file__).resolve().parents[2]


@dataclass
class Job:
    token: str
    directory: Path
    output_dir: Path
    options: dict
    state: str = "queued"
    message: str = "Preparing Inference"
    started: float = field(default_factory=time.monotonic)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    future: concurrent.futures.Future | None = None
    finished: float | None = None
    monitor: RunMonitor = field(default_factory=RunMonitor)

    def check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise concurrent.futures.CancelledError


def stop_process_group(process: subprocess.Popen, grace_seconds: float = 3.0) -> None:
    """Terminate this job's workers, including grandchildren, on POSIX hosts."""

    if os.name != "posix":
        process.kill()
        process.wait()
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            process.wait()
            return
        time.sleep(0.05)
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


class JobManager:
    """One output and its inference lifetime, shared by all browser sessions."""

    def __init__(self, config: SpaceConfig):
        if config.video_path is None:
            source = Path(saved_request(config.output_dir)["options"]["video_path"])
            config = replace(config, video_path=source)
        self.config = config
        self.revision = 0
        self.job: Job | None = None
        self.lock = threading.RLock()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="inference")
        self.closed = False
        self.previews = PreviewLoader()

    def current_job(self) -> Job | None:
        with self.lock:
            return self.job

    def record(self) -> SavedTask | None:
        with self.lock:
            directory = self.config.output_dir
            if not (directory / REQUEST_FILE).exists():
                return None
            return read_task(directory, self.config.cache_dir)

    def signature(self) -> list:
        with self.lock:
            return [self.revision, self.job.state if self.job else None]

    def deletion_key(self) -> list:
        with self.lock:
            return [self.revision, sha256_file(self.config.output_dir / REQUEST_FILE)]

    def delete_output(self, expected: list) -> None:
        """Delete only the confirmed, inactive task while holding the CLI's lock."""
        with self.lock:
            if self.closed or self.job and self.job.state not in FINISHED:
                raise ConfigurationError("Wait for inference to stop before deleting its output.")
            output = resolve_output_path(self.config.output_dir)
            if output != self.config.output_dir or output.is_symlink() or not output.is_dir():
                raise ConfigurationError("The output directory changed. Reload the Space before deleting it.")
            with lock_output(output):
                if expected != self.deletion_key():
                    raise ConfigurationError("The task changed. Review its current state before deleting output.")
                record = self.record()
                if record is None or record.complete:
                    raise ConfigurationError("Only unfinished task output can be deleted in the Space.")
                protected = [
                    REPOSITORY,
                    self.config.video_path,
                    self.config.cache_dir,
                    self.config.model_dir,
                    self.config.gvhmr_root,
                    *(
                        Path(record.options[key])
                        for key in ("video_path", "model_dir", "gvhmr_root", "checkpoint_path", "mhr70_regressor_path")
                        if record.options.get(key)
                    ),
                ]
                if any(path.resolve().is_relative_to(output) for path in protected):
                    raise ConfigurationError("Cannot delete an output folder containing source, models, code or cache.")
                self.previews.discard_all(wait=True)
                remove_tree(output)
                self.job = None
                self.revision += 1

    def resume(self) -> Job:
        with self.lock:
            record = self.record()
            if record and record.complete:
                raise ConfigurationError("This result is complete.")
            if not record or not record.resumable:
                raise ConfigurationError("Cannot resume: the saved settings or original source video are unavailable.")
            return self.submit(record.options, resume=True)

    def submit(self, options: dict, *, resume: bool = False) -> Job:
        from fdanyone.assets import SMPLX_MODEL

        options = complete_options(
            {
                "model_dir": str(self.config.model_dir),
                "gvhmr_root": str(self.config.gvhmr_root),
                "gpu_ids": self.config.gpu_ids,
                "attention_backend": self.config.attention_backend,
                **options,
            }
        )
        model_dir = Path(options["model_dir"]).expanduser().resolve()
        gvhmr_root = Path(options["gvhmr_root"]).expanduser().resolve()
        if not (model_dir / SMPLX_MODEL).is_file():
            raise ConfigurationError(
                "SMPL-X is not installed. Run python scripts/download_smplx.py "
                "in the terminal with the same model directory, then try again."
            )
        source = Path(options["video_path"]).resolve()
        probe_input(source, options["start_time"], options["target_fps"])
        with self.lock:
            if self.closed:
                raise ConfigurationError("The Space is shutting down.")
            current = self.current_job()
            if current and current.state not in FINISHED:
                raise ConfigurationError("This task already has an active inference run.")
            output_dir = resolve_output_path(self.config.output_dir)
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            with lock_output(output_dir):
                if not resume:
                    ensure_new_output(output_dir)
                else:
                    OutputDirectory(output_dir).validate_available()
                previous = read_run_request(output_dir)
                if previous and not source_matches(source, previous["source"], self.config.cache_dir):
                    raise ConfigurationError("The source video differs from the saved request.")
                token = uuid.uuid4().hex
                directory = self.config.cache_dir / "jobs" / token
                directory.mkdir(parents=True)
                gpu_ids = options["gpu_ids"]
                payload = {
                    **options,
                    "video_path": str(source),
                    "output_dir": str(output_dir),
                    "model_dir": str(model_dir),
                    "gvhmr_root": str(gvhmr_root),
                    "gpu_ids": list(gpu_ids) if gpu_ids is not None else None,
                }
                save_run_request(output_dir, payload, space_job=str(directory))
                # Write before queueing so reloads can recover the request/log
                # even if the process stops before the worker starts.
                (directory / "request.json").write_text(json.dumps(payload) + "\n")
            job = Job(token, directory, output_dir, payload)
            self.job = job
            self.revision += 1
            job.future = self.executor.submit(self._run, job)
            return job

    def get(self, token: str) -> Job:
        with self.lock:
            if self.job is None or self.job.token != token:
                raise ConfigurationError("This run is no longer available. Start a new run.")
            return self.job

    def cancel(self, token: str | None) -> str:
        if not token:
            return "No active run."
        with self.lock:
            job = self.get(token)
            if job.state in FINISHED:
                return job.message
            job.cancel_event.set()
            if job.future is not None and job.future.cancel():
                job.state, job.message = "cancelled", "Stopped. Resume inference or delete the saved output."
                job.finished = time.monotonic()
            else:
                job.message = "Stopping the inference workers…"
            return job.message

    def snapshot(self, token: str) -> dict:
        with self.lock:
            job = self.get(token)
            elapsed = (job.finished or time.monotonic()) - job.started
            return {
                "state": job.state,
                "message": job.message,
                "elapsed": elapsed,
                "output_dir": job.output_dir,
                "monitor": job.monitor.payload(
                    token=token,
                    name=job.output_dir.name,
                    state=job.state,
                    message=job.message,
                    elapsed=elapsed,
                    log_path=job.directory / "inference.log",
                    stopping=job.cancel_event.is_set(),
                ),
            }

    def monitor(self, record: SavedTask | None) -> dict | None:
        """Recover this task's current run or the directly indexed saved log."""

        with self.lock:
            job = self.current_job()
            if job is not None:
                return self.snapshot(job.token)["monitor"]
        if not record or record.log_dir is None:
            return None
        directory = record.log_dir.resolve()
        if not directory.is_relative_to((self.config.cache_dir / "jobs").resolve()):
            return None
        try:
            request = json.loads((directory / "request.json").read_text())
            if Path(request["output_dir"]).resolve() != record.directory.resolve():
                return None
            if not (directory / "inference.log").is_file():
                return None
            status = json.loads((directory / "status.json").read_text())
        except (OSError, ValueError, KeyError):
            return None
        monitor = RunMonitor()
        monitor.status(status)
        state = "complete" if record.complete else "failed" if status.get("error") else "cancelled"
        return monitor.payload(
            token=directory.name,
            name=record.directory.name,
            state=state,
            message=status.get("message", ""),
            elapsed=status.get("summary", {}).get("total_pipeline_elapsed_seconds"),
            log_path=directory / "inference.log",
        )

    def _update(self, job: Job, **fields) -> None:
        with self.lock:
            for name, value in fields.items():
                setattr(job, name, value)
            if fields.get("state") in FINISHED and job.finished is None:
                job.finished = time.monotonic()

    def _status(self, job: Job, status: dict) -> None:
        with self.lock:
            job.message = status["message"]
            job.monitor.status(status)

    def _command(self, request: Path) -> list[str]:
        return [sys.executable, "-u", "-m", "fdanyone.space.worker", str(request)]

    def _run(self, job: Job) -> None:
        process = None
        try:
            job.check_cancelled()
            request = job.directory / "request.json"
            self._update(job, state="running", message="Starting inference")
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(REPOSITORY)
            environment.pop("PYTHONHOME", None)
            # Avoid oversubscribing a shared workstation during video preparation.
            environment.setdefault("OMP_NUM_THREADS", "8")
            with (job.directory / "inference.log").open("w") as log:
                process = subprocess.Popen(
                    self._command(request),
                    cwd=REPOSITORY,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                while process.poll() is None:
                    job.check_cancelled()
                    try:
                        status = json.loads((job.directory / "status.json").read_text())
                    except (OSError, ValueError):
                        pass
                    else:
                        self._status(job, status)
                    job.cancel_event.wait(0.3)
            job.check_cancelled()
            if process.returncode:
                # A crashed parent may leave a model worker in its process group.
                stop_process_group(process)
                try:
                    status = json.loads((job.directory / "status.json").read_text())
                except (OSError, ValueError, KeyError):
                    status = {}
                if status.get("error") and status.get("message"):
                    message = status["message"]
                else:
                    message = f"Inference exited with code {process.returncode}. See the run log."
                    if status.get("message"):
                        message += f" Last stage: {status['message']}."
                raise FourDAnyoneError(message)
            from fdanyone.space.viewer import read_result

            # Inference completes when its published result is valid. Scene
            # preparation belongs to PreviewLoader and cannot fail the run.
            read_result(job.output_dir)
            job.check_cancelled()
            self._update(job, state="complete", message="Complete")
        except concurrent.futures.CancelledError:
            if process is not None:
                stop_process_group(process)
            self._update(job, state="cancelled", message="Stopped. Resume inference or delete the saved output.")
        except Exception as exc:
            if process is not None and process.poll() is None:
                stop_process_group(process)
            self._update(job, state="failed", message=f"Failed: {exc}")

    def close(self) -> None:
        with self.lock:
            self.closed = True
            if self.job:
                self.cancel(self.job.token)
        self.previews.close()
        self.executor.shutdown(wait=True, cancel_futures=True)
