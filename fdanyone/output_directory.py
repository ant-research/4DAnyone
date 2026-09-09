"""Output staging, reusable motion, and a single forward-only completion protocol."""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fdanyone.errors import ConfigurationError, FourDAnyoneError
from fdanyone.io import lock_output, remove_tree, resolve_output_path

if TYPE_CHECKING:
    from fdanyone.motion.result import MotionResult

LOGGER = logging.getLogger("fdanyone")
_GENERATED = ("cameras.json", "skeletons", "videos", "metadata.json")
_DIRECTORIES = {"gvhmr", "skeletons", "videos", ".inference"}


def read_output_metadata(directory: str | Path) -> dict:
    """Require the final commit marker before any reader consumes the output."""

    path = Path(directory) / "metadata.json"
    try:
        metadata = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise FourDAnyoneError(f"Output is incomplete or has invalid metadata: {path}.") from exc
    if not isinstance(metadata, dict):
        raise FourDAnyoneError(f"Output metadata must contain a JSON object: {path}.")
    return metadata


class OutputDirectory:
    """Stage output under an OS lock, retaining motion and unfinished work on failure.

    The private workspace records ownership and the start of publication, not
    process liveness. A retry holding the directory lock can discard that run's
    partial generated artifacts. Publication only moves forward, with metadata
    last. Nothing removes published artifacts after that commit point.
    """

    def __init__(self, destination: str | Path):
        self.destination = resolve_output_path(destination)
        self.motion_dir = self.destination / "gvhmr"
        self.working = self.destination / ".inference"
        self._owner = self.working / ".4danyone"
        self._publishing = self.working / ".publishing"

    def validate_available(self) -> None:
        """Protect completed results and unrelated files before preparing a retry."""

        if not os.path.lexists(self.destination):
            return
        if self.destination.is_symlink() or not self.destination.is_dir():
            raise ConfigurationError(f"Output path already exists: {self.destination}. Choose a new --output_dir.")
        if os.path.lexists(self.destination / "metadata.json"):
            raise ConfigurationError(f"4DAnyone output already exists: {self.destination}. Choose a new --output_dir.")
        allowed = {"gvhmr", ".inference"}
        if self._owner.is_file() and self._publishing.is_file():
            allowed.update(_GENERATED[:-1])
        self._check_entries(self.destination, allowed)
        if self.working.exists():
            self._check_entries(self.working, {*_GENERATED, "gvhmr", ".4danyone", ".publishing"})
            if any(self.working.iterdir()) and not self._owner.is_file():
                raise ConfigurationError(f"Unrecognized staging directory: {self.working}. Choose a new --output_dir.")

    @staticmethod
    def _check_entries(directory: Path, allowed: set[str]) -> None:
        for path in directory.iterdir():
            expected_type = path.is_dir() if path.name in _DIRECTORIES else path.is_file()
            if path.name not in allowed or path.is_symlink() or not expected_type:
                raise ConfigurationError(f"Unrecognized output entry: {path}. Choose a new --output_dir.")

    def _prepare(self) -> None:
        # Only a marked, interrupted publication owns artifacts outside staging.
        if self._publishing.is_file():
            for name in _GENERATED[:-1]:
                path = self.destination / name
                if name in _DIRECTORIES:
                    remove_tree(path)
                else:
                    path.unlink(missing_ok=True)
        self.working.mkdir(exist_ok=True)
        self._owner.touch(exist_ok=True)
        # Ownership survives an interruption in cleanup itself.
        for path in self.working.iterdir():
            if path == self._owner:
                continue
            if path.is_dir():
                remove_tree(path)
            else:
                path.unlink()

    def save_motion(self, motion: MotionResult) -> None:
        """Publish the complete motion pair once, independently of generation."""

        if os.path.lexists(self.motion_dir):
            raise ConfigurationError(f"Motion output already exists: {self.motion_dir}.")
        staged = motion.save(self.working / "gvhmr")
        staged.rename(self.motion_dir)

    def _publish(self) -> None:
        self._check_entries(self.working, {*_GENERATED, ".4danyone"})
        if {path.name for path in self.working.iterdir()} != {*_GENERATED, ".4danyone"}:
            raise ConfigurationError("Output is incomplete. Refusing to publish partial results.")
        read_output_metadata(self.working)
        for name in _GENERATED:
            if os.path.lexists(self.destination / name):
                raise ConfigurationError(f"Output appeared during inference: {self.destination / name}.")
        self._publishing.touch(exist_ok=False)
        for name in _GENERATED:
            (self.working / name).rename(self.destination / name)

    @contextmanager
    def stage(self):
        self.validate_available()
        self.destination.mkdir(parents=True, exist_ok=True)
        with lock_output(self.destination):
            self.validate_available()
            self._prepare()
            yield self.working
            self._publish()
            try:
                remove_tree(self.working)
            except OSError as exc:
                LOGGER.warning("Output is complete, but staging cleanup failed at %s: %s", self.working, exc)
