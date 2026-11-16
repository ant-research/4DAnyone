"""Full training checkpoints and independent, pickle-free rendering models."""

import json
import os
from pathlib import Path

import numpy as np
import torch

from fdanyone.io import sha256_file

from .gaussian import Gaussians

# Preserve positions and sensitive temporal parameters; compact appearance/shape.
RENDER_DTYPES = {name: np.float32 if name in ("xyz", "time", "time_scale") else np.float16 for name in Gaussians.names}


def perceptual_identity(weights):
    if weights is None:
        return None
    return sha256_file(weights)


def save_checkpoint(
    path,
    model,
    optimizer,
    topology,
    sampler,
    training_data,
    settings,
    step,
    fingerprint,
    background_rng=None,
    weights_identity=None,
):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(
        format=1,
        weights_identity=weights_identity,
        step=step,
        model={k: v.cpu() for k, v in model.tensors().items()},
        degree=model.degree,
        config=settings,
        cameras=training_data.cameras,
        times=training_data.times.tolist(),
        fps=str(training_data.fps),
        scene_fingerprint=fingerprint,
        optimizer=optimizer.state_dict(),
        statistics={name: getattr(model, name).cpu() for name in ("gradient_sum", "observations", "radius")},
        sh_threshold=topology.sh_threshold,
        sampler=sampler.state_dict(),
        rng=torch.get_rng_state(),
        cuda_rng=torch.cuda.get_rng_state(model.xyz.device),
        background_rng=background_rng,
    )
    # Publish the render model first; the PT replacement commits the saved step.
    save_render_model(path.with_suffix(".npz"), payload)
    temporary = path.with_name(path.name + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def load_checkpoint(path, device="cuda"):
    payload = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
    if payload.get("format") != 1:
        raise ValueError("Unsupported reconstruction checkpoint")
    model = Gaussians({k: v.to(device) for k, v in payload["model"].items()}, payload["degree"])
    if not len(model) or not all(torch.isfinite(p).all() for p in model.parameters()):
        raise ValueError("Checkpoint has empty/nonfinite Gaussians")
    return payload, model


def render_config(saved):
    """The only training settings needed by standalone rendering."""
    fields = ("image_scale", "space_scale", "near", "far", "marginal_threshold")
    missing = set(fields) - saved.keys()
    if missing:
        raise ValueError(f"Checkpoint lacks rendering settings: {sorted(missing)}")
    return {key: saved[key] for key in fields}


def save_render_model(path, payload):
    """Compress render parameters without changing the FP32 training payload."""
    path = Path(path)
    if path.suffix != ".npz":
        raise ValueError("Render models use .npz")
    metadata = {key: payload[key] for key in ("step", "degree", "cameras", "times", "fps")}
    metadata.update(format="4dgs-render/1", config=render_config(payload["config"]))
    encoded = np.frombuffer(json.dumps(metadata, allow_nan=False).encode("utf-8"), dtype=np.uint8)
    arrays = {}
    for name, dtype in RENDER_DTYPES.items():
        with np.errstate(over="ignore", invalid="ignore"):
            array = payload["model"][name].detach().numpy().astype(dtype, copy=False)
        if not np.isfinite(array).all():
            raise ValueError(f"Nonfinite render parameter after storage conversion: {name}")
        arrays[name] = array
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, metadata=encoded, **arrays)
    os.replace(temporary, path)


def load_render_model(path, device="cuda"):
    """Load the standalone NPZ model; training checkpoints are a separate format."""
    if Path(path).suffix != ".npz":
        raise ValueError("Rendering requires a .npz model, not a training .pt checkpoint")
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != {*Gaussians.names, "metadata"}:
            raise ValueError("Render model has unexpected or missing arrays")
        encoded = archive["metadata"]
        if encoded.dtype != np.uint8 or encoded.ndim != 1:
            raise ValueError("Render metadata must be UTF-8 JSON bytes")
        metadata = json.loads(encoded.tobytes().decode("utf-8"))
        if metadata.get("format") != "4dgs-render/1":
            raise ValueError("Unsupported render model format")
        if set(metadata) != {"format", "step", "degree", "cameras", "times", "fps", "config"}:
            raise ValueError("Render model has unexpected or missing metadata")
        degree = metadata["degree"]
        if type(degree) is not int or not 0 <= degree <= 3:
            raise ValueError("Invalid spherical-harmonic degree")
        tensors = {}
        xyz = archive["xyz"]
        count = xyz.shape[0] if xyz.ndim == 2 else 0
        shapes = dict(xyz=(3,), time=(1,), scale=(3,), time_scale=(1,), left=(4,), right=(4,), opacity=(1,), dc=(1, 3))
        for name in Gaussians.names:
            array = xyz if name == "xyz" else archive[name]
            shape = shapes.get(name)
            valid = (
                array.shape == (count, *shape)
                if shape
                else (
                    array.ndim == 3
                    and array.shape[0] == count
                    and array.shape[1] >= (degree + 1) ** 2 - 1
                    and array.shape[2] == 3
                )
            )
            if (
                not count
                or array.dtype not in (np.float32, RENDER_DTYPES[name])
                or not valid
                or not np.isfinite(array).all()
            ):
                raise ValueError(f"Invalid render model array: {name}")
            tensors[name] = torch.from_numpy(array).to(device)
    render_config(metadata["config"])
    return metadata, Gaussians(tensors, degree)
