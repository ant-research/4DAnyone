"""Persist the original inference request independently of output publication."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fdanyone.errors import ConfigurationError
from fdanyone.inputs import normalize_reference_paths, validate_input_files
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
        references = value["options"].get("reference_video_paths")
        if references is None:
            references = []
        if not isinstance(references, list) or len(references) > 4:
            raise ValueError("Invalid saved reference paths")
        identities = value.get("references", [])
        if not isinstance(identities, list) or len(identities) != len(references):
            raise ValueError("Invalid reference identities")
        if any(
            not isinstance(path, str) or not path.strip() or not isinstance(item, dict) or item.get("path") != path
            for path, item in zip(references, identities, strict=True)
        ):
            raise ValueError("Reference identities do not match the saved input order")
        return value
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigurationError(f"Cannot read saved inference settings: {path}.") from exc


def save_run_request(directory: str | Path, options: dict, **fields) -> dict:
    """Call while reserving the output; never place orchestration files in staging."""

    directory = Path(directory)
    previous = read_run_request(directory) or {}
    source = Path(options["video_path"]).expanduser().resolve()
    references = normalize_reference_paths(options.get("reference_video_paths"))
    validate_input_files(source, references)
    identity = _file_identity(source, previous.get("source", {}))
    previous_references = {item["path"]: item for item in previous.get("references", [])}
    reference_identities = [_file_identity(path, previous_references.get(str(path), {})) for path in references]
    options = dict(options)
    for key in ("model_dir", "gvhmr_root", "checkpoint_path", "mhr70_regressor_path"):
        if options.get(key):
            options[key] = str(Path(options[key]).expanduser().resolve())
    options["reference_video_paths"] = [str(path) for path in references] or None
    value = {
        **previous,
        "version": REQUEST_VERSION,
        "created_at": previous.get("created_at", datetime.now(timezone.utc).isoformat()),
        "options": {**options, "video_path": str(source), "output_dir": str(directory.resolve())},
        "source": identity,
        "references": reference_identities,
        **fields,
    }
    write_json(directory / REQUEST_FILE, value)
    return value


def _file_identity(path: Path, previous: dict) -> dict:
    stat = path.stat()
    identity = {"path": str(path), "filename": path.name, "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    identity["sha256"] = (
        previous["sha256"]
        if previous.get("sha256") and all(previous.get(key) == value for key, value in identity.items())
        else sha256_file(path)
    )
    return identity
