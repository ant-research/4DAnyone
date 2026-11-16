"""One resumable workflow from generated views to a rendered 4DGS scene."""

import hashlib
import json
import os
from pathlib import Path

from fdanyone.download import ensure_foreground_model, ensure_perceptual_vgg19
from fdanyone.io import lock_output, remove_tree, sha256_file
from fdanyone.output_directory import read_output_metadata
from fdanyone.result_videos import read_target_videos

from .data import TrainingData, staging_directory, write_json
from .settings import check_settings, training_identity, training_settings


def source_identity(result, masks=None):
    result = Path(result).resolve()
    read_output_metadata(result)
    records = json.loads((result / "cameras.json").read_text())["cameras"]
    videos = read_target_videos(result, records)
    digest = hashlib.sha256()
    for path in (result / "metadata.json", result / "cameras.json", *videos):
        digest.update(str(path.relative_to(result)).encode())
        digest.update(sha256_file(path).encode())
    if masks is not None:
        masks = Path(masks).resolve()
        for path in sorted(masks.glob("*/*.png")):
            digest.update(str(path.relative_to(masks)).encode())
            digest.update(sha256_file(path).encode())
    else:
        from fdanyone.assets import BIREFNET_REVISION

        digest.update(BIREFNET_REVISION.encode())
    return digest.hexdigest()


def check_runtime(settings, device):
    import torch
    from gsplat.cuda._backend import _C

    from .kernels import extension

    if torch.device(device).type != "cuda" or not torch.cuda.is_available():
        raise ValueError("4DGS training requires a CUDA GPU")
    if _C is None:
        raise RuntimeError("gsplat CUDA backend is unavailable")
    with torch.cuda.device(device):
        extension()
    if settings["perceptual_weight"]:
        from fdanyone.nerfstudio.perceptual import VGG19PerceptualLoss

        VGG19PerceptualLoss(
            settings["perceptual_weights"],
            settings["perceptual_compute_dtype"],
            include_rgb=settings["perceptual_include_rgb"],
        )


# Only these products belong to the reconstruction workflow; user files stay intact.
PRODUCTS = (
    "run.json",
    "config.json",
    "train.jsonl",
    "data",
    "scene",  # Owned by older runs; explicit restart removes it.
    "initialization",
    "checkpoints",
    "input_cache",
    "render",
    "config.json.tmp",
    "run.json.tmp",
    "train.tmp",
    ".restart.json.tmp",
)


def clear_products(output):
    for name in PRODUCTS:
        path = output / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.exists():
            remove_tree(path)


def protect_inputs(output, paths):
    roots = [output / name for name in PRODUCTS]
    for path in paths:
        path = Path(path).resolve()
        if any(path == root or root in path.parents for root in roots):
            raise ValueError(
                f"Restart would remove an input: {path}. Move it outside the reconstruction products first."
            )


def completed_checkpoint(output, steps):
    rendered = output / "render"
    if not rendered.exists():
        return None
    record = json.loads((rendered / "render.json").read_text())
    checkpoint = output / "checkpoints/latest.pt"
    if not checkpoint.is_file():
        raise ValueError("Completed render has no checkpoint; use --resume False to start over")
    model_path = checkpoint.with_suffix(".npz")
    if not model_path.is_file():
        raise ValueError("Missing render model latest.npz; use a new output or --resume False")
    stat = model_path.stat()
    expected = (stat.st_size, stat.st_mtime_ns, steps)
    actual = tuple(record.get(key) for key in ("model_size", "model_mtime_ns", "step"))
    if actual != expected:
        raise ValueError(
            "Existing render belongs to a different render model or training budget; use --resume False to start over"
        )
    if not (rendered / "rgb.mp4").is_file():
        raise ValueError("Completed render is missing rgb.mp4; use --resume False to start over")
    return checkpoint


def run(data_dir, output_dir, options=None, *, model_dir=None, masks=None, device="cuda", resume=True, stop_after=None):
    from .carve import carve
    from .checkpoint import perceptual_identity
    from .initialization import InitialPoints
    from .prepare import prepare
    from .render import render_video
    from .train import train

    if type(resume) is not bool:
        raise ValueError("resume must be True or False")
    options = {} if options is None else dict(options)
    result = Path(data_dir).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    if output == result or result in output.parents or output in result.parents:
        raise ValueError("Use separate source and reconstruction directories")
    masks = Path(masks).expanduser().resolve() if masks is not None else None
    model_dir = Path(model_dir).expanduser().resolve() if model_dir is not None else None
    output.parent.mkdir(parents=True, exist_ok=True)
    with lock_output(output):
        if os.path.lexists(output) and not output.is_dir():
            raise ValueError("Reconstruction output must be a directory")
        record_path, pending_path = output / "run.json", output / ".restart.json"
        pending = json.loads(pending_path.read_text()) if pending_path.exists() else None
        previous = None
        if pending is not None:
            previous = pending["run"]
            if resume:
                saved = check_settings(pending["settings"])
        elif record_path.is_file():
            previous = json.loads(record_path.read_text())
            if resume:
                try:
                    saved = check_settings(json.loads((output / "config.json").read_text()))
                except (OSError, ValueError) as exc:
                    raise ValueError(f"Cannot resume saved settings: {exc}. Use --resume False to start over.") from exc
        elif output.exists() and any(output.iterdir()):
            raise ValueError("No native run.json found; choose a new output or use development tools for old runs")
        if (pending is not None or record_path.is_file()) and (
            not isinstance(previous, dict)
            or set(previous) != {"source", "recipe", "weights"}
            or not isinstance(previous["source"], str)
            or len(previous["source"]) != 64
            or not isinstance(previous["recipe"], dict)
        ):
            raise ValueError("Unrecognized run.json; choose a new reconstruction output")
        continuing = resume and previous is not None
        settings = check_settings({**saved, **options}) if continuing else training_settings(options)
        restarting = pending is not None or (not resume and previous is not None)
        mask_files = [] if masks is None else sorted(masks.glob("*/*.png"))
        if masks is not None and (not masks.is_dir() or not mask_files):
            raise ValueError("masks must be a directory containing camera/frame PNGs")
        if restarting:
            protect_inputs(
                output,
                [
                    result,
                    result / "metadata.json",
                    result / "cameras.json",
                    model_dir or "models",
                    *([masks] if masks is not None else []),
                    *mask_files,
                ],
            )
        identity = source_identity(result, masks)
        if settings["perceptual_weight"] and (model_dir is not None or not settings["perceptual_weights"]):
            settings["perceptual_weights"] = str(ensure_perceptual_vgg19(model_dir or "models"))
        if restarting and settings["perceptual_weight"]:
            protect_inputs(output, [settings["perceptual_weights"]])
        record = dict(
            source=identity,
            recipe=training_identity(settings),
            weights=perceptual_identity(settings["perceptual_weights"] if settings["perceptual_weight"] else None),
        )
        if continuing and previous != record:
            changed = sorted(
                key
                for key in record["recipe"].keys() | previous["recipe"].keys()
                if record["recipe"].get(key) != previous["recipe"].get(key)
            )
            changed.extend(key for key in ("source", "weights") if previous[key] != record[key])
            action = "Pending restart" if pending is not None else "Resume"
            raise ValueError(
                f"{action} requires the same source, training recipe and perceptual weights; "
                f"changed: {changed}. Use --resume False to start over; supply the original --masks if used."
            )
        if continuing and not restarting:
            if (output / "scene").exists() or (
                (output / "checkpoints/latest.pt").exists() and not (output / "checkpoints/latest.npz").is_file()
            ):
                raise ValueError("Old or incomplete output layout; use a new output directory or --resume False")
            checkpoint = completed_checkpoint(output, settings["steps"])
            if checkpoint is not None:
                return checkpoint
        check_runtime(settings, device)
        training_data_path = output / "data"
        if (restarting or not training_data_path.exists()) and masks is None:
            ensure_foreground_model(model_dir or "models")
        if restarting:
            # Persist the *new* recipe before removing any old product. A retry uses it.
            write_json(pending_path, dict(settings=settings, run=record))
            clear_products(output)
            write_json(output / "config.json", settings)
            write_json(record_path, record)
            pending_path.unlink()
        elif previous is not None:
            write_json(output / "config.json", settings)
        else:
            # An empty user-created directory is also a new destination.
            if output.exists():
                output.rmdir()
            with staging_directory(output) as staging:
                write_json(staging / "config.json", settings)
                write_json(staging / "run.json", record)
        if not training_data_path.exists():
            prepare(
                result,
                training_data_path,
                masks=masks,
                model_dir=model_dir or "models",
                device=device,
                source_id=identity,
            )
        training_data = TrainingData(training_data_path, image_scale=settings["image_scale"])
        if training_data.meta.get("source_identity") != identity:
            raise ValueError("Prepared training data belongs to a different source")
        initialization = output / "initialization"
        if not initialization.exists():
            carve(
                training_data,
                initialization,
                device,
                bounds=settings["bounds"],
                voxel_size=settings["voxel_size"],
                carve_chunk=settings["carve_chunk"],
            )
        points = InitialPoints(initialization)
        checkpoint = train(
            training_data,
            points,
            output,
            settings,
            device,
            resume=(output / "checkpoints/latest.pt").exists(),
            stop_after=stop_after,
        )
        if stop_after is not None:
            return checkpoint
        render_video(checkpoint.with_suffix(".npz"), output / "render", device=device)
        return checkpoint
