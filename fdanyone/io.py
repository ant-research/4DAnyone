"""Filesystem helpers for crash-safe result publication."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import shutil
import time
import uuid
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

from fdanyone.errors import FourDAnyoneError

_RETRYABLE_TREE_ERRORS = {errno.EBUSY, errno.ENOTEMPTY, errno.ESTALE}


def resolve_output_path(path: str | Path) -> Path:
    """Normalize an output path without following a possibly dangling leaf symlink."""

    expanded = Path(path).expanduser()
    return expanded.parent.resolve() / expanded.name


@contextmanager
def lock_output(path: Path):
    """Reserve an output through a stable, writable sidecar file.

    Keep the empty lock file outside the output directory and never unlink it: replacing
    its inode could let concurrent writers acquire different locks. The OS
    releases the lock on process exit, including SIGKILL.
    """

    lock_path = path.with_name(f".{path.name}.lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o666)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise FourDAnyoneError(f"Another inference run is using {path}.") from exc
        yield
    finally:
        os.close(descriptor)


def sha256_file(path: str | Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    """Hash a file without materializing it in memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: str | Path, value: object, *, sort_keys: bool = True) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=sort_keys) + "\n")
    os.replace(temporary, target)


def remove_tree(
    path: str | Path,
    *,
    attempts: int = 8,
    initial_delay_seconds: float = 0.1,
    ignore_errors: bool = False,
) -> None:
    """Remove a tree, tolerating short directory-entry lag on network filesystems."""

    target = Path(path)
    if attempts <= 0:
        raise ValueError(f"attempts must be positive, got {attempts}.")
    for attempt in range(attempts):
        try:
            shutil.rmtree(target)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            retryable = exc.errno in _RETRYABLE_TREE_ERRORS and attempt + 1 < attempts
            if not retryable:
                if ignore_errors:
                    return
                raise
            time.sleep(initial_delay_seconds * (2**attempt))


class AtomicResultDirectory(AbstractContextManager[Path]):
    """Build beside the destination and rename only after all validation passes."""

    def __init__(self, destination: str | Path):
        self.destination = resolve_output_path(destination)
        self.working = self.destination.with_name(f".{self.destination.name}.work-{uuid.uuid4().hex[:10]}")
        self._committed = False

    def _destination_exists(self) -> bool:
        return os.path.lexists(self.destination)

    def __enter__(self) -> Path:
        if self._destination_exists():
            raise FourDAnyoneError(
                f"Output directory already exists: {self.destination}. Choose a new directory to avoid mixed runs."
            )
        self.working.mkdir(parents=True)
        return self.working

    def commit(self) -> Path:
        if self._committed:
            return self.destination
        if self._destination_exists():
            raise FourDAnyoneError(
                f"Output directory appeared during inference: {self.destination}. Refusing to overwrite it."
            )
        os.replace(self.working, self.destination)
        self._committed = True
        return self.destination

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if exc_type is None:
            try:
                self.commit()
            except BaseException:
                remove_tree(self.working, ignore_errors=True)
                raise
        else:
            remove_tree(self.working, ignore_errors=True)
        return False
