"""The ordered source and synchronized appearance-reference input contract."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fdanyone.errors import ConfigurationError


def normalize_reference_paths(values: Sequence[str | Path] | None, *, base_dir: Path | None = None) -> tuple[Path, ...]:
    """Resolve optional input paths and reject duplicate references."""
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ConfigurationError("reference_video_paths must be a list of up to 4 video paths.")
    if len(values) > 4:
        raise ConfigurationError("Provide at most 4 reference videos.")
    if any(not isinstance(value, (str, Path)) or not str(value).strip() for value in values):
        raise ConfigurationError("Each reference video must have a non-empty file path.")
    paths = tuple(Path(value).expanduser() for value in values)
    paths = tuple(((base_dir / path) if base_dir is not None else path).resolve() for path in paths)
    if len(set(paths)) != len(paths):
        raise ConfigurationError("Reference videos must be distinct.")
    return paths


def validate_input_files(source: str | Path, references: tuple[Path, ...]) -> None:
    source = Path(source).expanduser().resolve()
    if source in references:
        raise ConfigurationError("Do not include the source in reference_video_paths.")
    for path in (source, *references):
        if not path.is_file():
            raise ConfigurationError(f"Input video does not exist: {path}")
