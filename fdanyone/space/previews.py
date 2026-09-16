"""Prepare scenes independently of inference and discard obsolete preview requests."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import CancelledError, ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from pathlib import Path

from fdanyone.space.viewer import export_input, export_recording, read_result


def motion_available(output: Path) -> bool:
    """The CLI atomically publishes these two files as one motion directory."""
    return all((output / "gvhmr" / name).is_file() for name in ("motion.json", "motion.safetensors"))


def prepare_preview(config, task, layout, start_time, has_motion, *, check_cancelled):
    """Build the current task's input, recovered body or completed result preview."""
    source = task.source if task else config.video_path
    options = (
        task.options if task else {"model_dir": config.model_dir, "gvhmr_root": config.gvhmr_root, "target_fps": "auto"}
    )
    directories = {key: Path(options[key]) for key in ("model_dir", "gvhmr_root")}
    if task and task.complete:
        return export_recording(
            read_result(config.output_dir),
            config.cache_dir / "viewer",
            source=source,
            **directories,
            check_cancelled=check_cancelled,
        )
    return export_input(
        source,
        config.cache_dir / "viewer",
        layout,
        start_time=start_time,
        target_fps=options["target_fps"],
        motion_dir=config.output_dir / "gvhmr" if has_motion else None,
        **directories,
        check_cancelled=check_cancelled,
    )


class PreviewLoader:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="space-preview")
        self.pending = {}
        self.futures = set()
        self.lock = threading.RLock()

    def submit(self, previous, function, *args, **kwargs):
        with self.lock:
            self.discard(previous)
            # A closed/reloaded tab may never collect its last preview.
            while len(self.pending) >= 32:
                self.discard(next(iter(self.pending)))
            token = uuid.uuid4().hex
            cancelled = threading.Event()

            def check_cancelled():
                if cancelled.is_set():
                    raise CancelledError

            future = self.executor.submit(function, *args, check_cancelled=check_cancelled, **kwargs)
            self.futures.add(future)
            future.add_done_callback(self._finished)
            self.pending[token] = (future, cancelled)
            return token

    def _finished(self, future):
        with self.lock:
            self.futures.discard(future)

    def take(self, token):
        with self.lock:
            if not token or token not in self.pending:
                return None
            future, _ = self.pending[token]
            if not future.done():
                return None
            del self.pending[token]
        return future.result()

    def discard(self, token):
        with self.lock:
            pending = self.pending.pop(token, None)
            if pending:
                future, cancelled = pending
                cancelled.set()
                future.cancel()

    def discard_all(self, *, wait=False):
        with self.lock:
            futures = list(self.futures)
            for token in list(self.pending):
                self.discard(token)
        if wait:
            wait_futures(futures)

    def close(self):
        self.discard_all()
        self.executor.shutdown(wait=True, cancel_futures=True)
