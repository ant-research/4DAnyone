"""Persist the original inference request independently of output publication."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fdanyone.errors import ConfigurationError
from fdanyone.io import sha256_file, write_json

REQUEST_FILE = ".4danyone-request.json"
REQUEST_VERSION = 2


def read_run_request(directory: str | Path) -> dict | None:
    """Read a request in the current format without changing its arguments."""

    path = Path(directory) / REQUEST_FILE
    if not path.exists() and not path.is_symlink():
        return None
    try:
        if path.is_symlink():
            raise ValueError("The request must be a regular file")
        value = json.loads(path.read_text())
        if value["version"] != REQUEST_VERSION or not isinstance(value["options"], dict):
            raise ValueError("Unsupported request format")
        if not isinstance(value["options"]["video_path"], str) or not isinstance(value["source"], dict):
            raise ValueError("Invalid source identity")
        return value
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigurationError(f"Cannot read saved inference settings: {path}.") from exc


def save_run_request(directory: str | Path, options: dict, **fields) -> dict:
    """Call while reserving the output; never place orchestration files in staging."""

    directory = Path(directory)
    previous = read_run_request(directory) or {}
    source = Path(options["video_path"]).resolve()
    stat = source.stat()
    identity = {"path": str(source), "filename": source.name, "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    old_source = previous.get("source", {})
    identity["sha256"] = (
        old_source["sha256"]
        if old_source.get("sha256") and all(old_source.get(key) == value for key, value in identity.items())
        else sha256_file(source)
    )
    options = dict(options)
    for key in ("model_dir", "gvhmr_root", "checkpoint_path", "mhr70_regressor_path"):
        if options.get(key):
            options[key] = str(Path(options[key]).expanduser().resolve())
    value = {
        **previous,
        "version": REQUEST_VERSION,
        "created_at": previous.get("created_at", datetime.now(timezone.utc).isoformat()),
        "options": {**options, "video_path": str(source), "output_dir": str(directory.resolve())},
        "source": identity,
        **fields,
    }
    write_json(directory / REQUEST_FILE, value)
    return value
