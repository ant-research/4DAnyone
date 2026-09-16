"""Serve the pinned Web Viewer API with the runtime already in gradio-rerun."""

from __future__ import annotations

import base64
import hashlib
import importlib.metadata
import re
import tempfile
import threading
import uuid
from pathlib import Path
from urllib.parse import quote

from fdanyone.errors import FourDAnyoneError

VERSION = "0.37.1"
WASM_SHA256 = "a5119572793205c35f682546b30882152fd3e2869b24c82226f852dfa6db7fe3"
ASSETS = Path(__file__).with_name("assets")
_LOCK = threading.Lock()


def file_url(path: Path | str, *, revision: str | None = None) -> str:
    """Relative to the mounted Space, including deployments behind a path prefix."""
    url = "./gradio_api/file=" + quote(str(Path(path).resolve()), safe="/")
    return url + "?v=" + quote(revision, safe="") if revision else url


def _cache_modules(directory: Path) -> Path:
    # Version the whole import graph: a query on scene.js would leave its relative
    # imports cached at their old URLs, mixing code from different Space versions.
    files = {path.relative_to(ASSETS): path.read_bytes() for path in sorted(ASSETS.rglob("*.js"))}
    digest = hashlib.sha256()
    for path, data in files.items():
        digest.update(path.as_posix().encode() + b"\0" + hashlib.sha256(data).digest())
    modules = directory / "modules" / digest.hexdigest()[:16]
    if not modules.is_dir():
        modules.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=modules.parent) as temporary:
            staged = Path(temporary) / "assets"
            for path, data in files.items():
                target = staged / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            try:
                staged.rename(modules)
            except OSError:
                if not modules.is_dir():
                    raise
    return modules


def prepare_web_assets(cache_dir: Path) -> dict:
    import gradio as gr
    import gradio_rerun

    version = importlib.metadata.version("gradio-rerun")
    if version != VERSION:
        raise FourDAnyoneError(f"The Space viewer needs gradio-rerun=={VERSION}; found {version}.")
    directory = cache_dir / "web-viewer" / VERSION
    destination = directory / "re_viewer_bg.wasm"
    with _LOCK:
        if not destination.is_file():
            directory.mkdir(parents=True, exist_ok=True)
            package = Path(gradio_rerun.__file__).parent / "templates/component/index.js"
            match = re.search(r"data:application/wasm;base64,([A-Za-z0-9+/=]+)", package.read_text())
            if match is None:
                raise FourDAnyoneError(
                    "Cannot locate the installed Rerun viewer runtime. Reinstall requirements-gui.txt."
                )
            data = base64.b64decode(match[1], validate=True)
            if hashlib.sha256(data).hexdigest() != WASM_SHA256:
                raise FourDAnyoneError("The installed Rerun viewer runtime does not match this Space version.")
            temporary = directory / f".{uuid.uuid4().hex}.wasm"
            try:
                temporary.write_bytes(data)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
        modules = _cache_modules(directory)
    gr.set_static_paths(paths=[ASSETS.resolve(), directory.resolve()])
    return {
        "scene": file_url(modules / "scene.js"),
        "media": file_url(modules / "media.js"),
        "wasm": file_url(destination),
    }


def display_payload(recording: Path, info: dict, *, layout_only: bool = False) -> dict:
    """Convert only exported cache files into browser media URLs."""
    revision = info["recording_id"]
    payload = {
        "recording": file_url(recording, revision=revision),
        "recording_id": revision,
        "layout_only": layout_only,
        "camera_count": info["camera_count"],
    }
    if layout_only:
        return payload
    media = info["media"]
    source, overlay = media["source"], media["overlay"]
    if overlay:
        overlay = {
            **overlay,
            **{key: file_url(overlay[key]) for key in ("vertices", "faces", "keypoints")},
        }
    return {
        **payload,
        "fps": info["fps"],
        "frames": info["frames"],
        "source": {**source, "url": file_url(source["path"])} if source else None,
        "overlay": overlay,
        "targets": [{**target, "url": file_url(target["path"])} for target in media["targets"]],
        "notes": info["notes"],
    }
