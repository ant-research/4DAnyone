"""Single-GPU training and resumable tensor checkpoints."""

import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from .checkpoint import load_checkpoint, perceptual_identity, save_checkpoint
from .data import write_json
from .densification import Topology
from .initialization import initialize
from .loader import Sampler, batches
from .losses import Objective
from .optimizer import GaussianAdam
from .rasterizer import Camera, accumulate_statistics, render
from .settings import check_settings, training_identity


def make_camera(camera, settings, device):
    return Camera(
        camera,
        device,
        far=settings["far"],
        image_scale=settings["image_scale"],
        near=settings["near"],
        space_scale=settings["space_scale"],
    )


def make_optimizer(model, settings):
    return GaussianAdam(
        model,
        dc_lr=settings["dc_lr"],
        opacity_lr=settings["opacity_lr"],
        rotation_lr=settings["rotation_lr"],
        scale_lr=settings["scale_lr"],
        sh_lr=settings["sh_lr"],
        time_lr=settings["time_lr"],
        xyz_lr=settings["xyz_lr"],
    )


def make_topology(settings, spatial_scale, duration, interval):
    return Topology(
        spatial_scale,
        duration,
        interval,
        densify_every=settings["densify_every"],
        densify_from=settings["densify_from"],
        densify_until=settings["densify_until"],
        discard_opacity=settings["discard_opacity"],
        gradient_threshold=settings["gradient_threshold"],
        lr_steps=settings["lr_steps"],
        marginal_threshold=settings["marginal_threshold"],
        max_scene_scale=settings["max_scene_scale"],
        min_gradient=settings["min_gradient"],
        min_opacity=settings["min_opacity"],
        min_screen_radius=settings["min_screen_radius"],
        opacity_reset_every=settings["opacity_reset_every"],
        opacity_reset_radius=settings["opacity_reset_radius"],
        prune_until=settings["prune_until"],
        sh_degree=settings["sh_degree"],
        sh_every=settings["sh_every"],
        sh_gradient_threshold=settings["sh_gradient_threshold"],
        size_threshold=settings["size_threshold"],
        view_dependent_ratio=settings["view_dependent_ratio"],
        xyz_lr=settings["xyz_lr"],
        xyz_lr_final=settings["xyz_lr_final"],
    )


def make_objective(settings, device):
    return Objective(
        device,
        background_color=settings["background_color"],
        l1_weight=settings["l1_weight"],
        mask_weight=settings["mask_weight"],
        perceptual_compute_dtype=settings["perceptual_compute_dtype"],
        perceptual_include_rgb=settings["perceptual_include_rgb"],
        perceptual_start_step=settings["perceptual_start_step"],
        perceptual_weight=settings["perceptual_weight"],
        perceptual_weights=settings["perceptual_weights"],
        seed=settings["seed"],
        ssim_weight=settings["ssim_weight"],
    )


def initialize_model(training_data, points, settings, device):
    return initialize(
        training_data,
        points,
        device,
        point_fraction=settings["point_fraction"],
        initial_opacity=settings["initial_opacity"],
        initial_scale=settings["initial_scale"],
        initial_span=settings["initial_span"],
        marginal_threshold=settings["marginal_threshold"],
        sh_degree=settings["sh_degree"],
        space_scale=settings["space_scale"],
    )


def train(
    training_data, points, output, settings, device="cuda", resume=False, stop_after=None, *, restore=check_settings
):
    settings = restore(settings)
    if training_data.image_scale != settings["image_scale"]:
        raise ValueError("Training data and configured image_scale differ")
    if stop_after is not None and stop_after <= 0:
        raise ValueError("--stop-after must be positive")
    if torch.device(device).type != "cuda":
        raise ValueError("Training requires a CUDA GPU")
    output = Path(output)
    sizes = {
        (int(c["height"] * settings["image_scale"]), int(c["width"] * settings["image_scale"]))
        for c in training_data.cameras
    }
    if len(sizes) != 1:
        raise ValueError("Batched training requires equal camera image sizes")
    # Four VGG pooling stages require a minimum spatial extent of 16 pixels.
    if (
        settings["perceptual_weight"]
        and settings["perceptual_start_step"] < settings["steps"]
        and min(next(iter(sizes))) < 16
    ):
        raise ValueError("VGG loss requires training images at least 16 pixels high and wide; increase image_scale")
    fingerprint = training_data.fingerprint()
    carve_record = points.metadata
    if carve_record["scene"] != fingerprint:
        raise ValueError("Carved points do not match the training data inputs")
    if (
        not np.allclose(carve_record["bounds"], settings["bounds"])
        or carve_record["voxel_size"] != settings["voxel_size"]
    ):
        raise ValueError("Carve settings differ from the training configuration")
    checkpoint = output / "checkpoints/latest.pt"
    if checkpoint.exists() and not resume:
        raise FileExistsError("A checkpoint exists; use --resume or a new output")
    if resume and not checkpoint.exists():
        raise FileNotFoundError("No checkpoint to resume")
    torch.manual_seed(settings["seed"])
    torch.cuda.manual_seed(settings["seed"])
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    torch.set_num_threads(min(torch.get_num_threads(), 8))
    spatial_scale = float(
        np.min(np.subtract(settings["bounds"][1], settings["bounds"][0])) / settings["space_scale"] / 2
    )
    topology = make_topology(settings, spatial_scale, training_data.duration, 1 / float(training_data.fps))
    sampler = Sampler(len(training_data), settings["seed"])
    weights_identity = perceptual_identity(settings["perceptual_weights"] if settings["perceptual_weight"] else None)
    objective = make_objective(settings, device)
    start_step = 0
    if resume:
        payload, model = load_checkpoint(checkpoint, device)
        previous = restore(payload["config"])
        if payload["scene_fingerprint"] != fingerprint or training_identity(previous) != training_identity(settings):
            raise ValueError("Resume requires identical training data and configuration")
        if payload.get("weights_identity") is not None:
            same_weights = payload["weights_identity"] == weights_identity
        else:
            same_weights = (
                not settings["perceptual_weight"] or previous["perceptual_weights"] == settings["perceptual_weights"]
            )
        if not same_weights:
            raise ValueError("Resume requires the same perceptual weights")
        optimizer = make_optimizer(model, settings)
        optimizer.load_state_dict(payload["optimizer"])
        for name, value in payload["statistics"].items():
            setattr(model, name, value.to(device))
        topology.sh_threshold = payload["sh_threshold"]
        sampler.restore(payload["sampler"])
        torch.set_rng_state(payload["rng"].cpu())
        torch.cuda.set_rng_state(payload["cuda_rng"].cpu(), device)
        start_step = payload["step"]
        if objective.background_generator is not None:
            state = payload.get("background_rng")
            if state is None and start_step:
                raise ValueError("Random-background resume requires the saved background RNG state")
            if state is not None:
                objective.background_generator.set_state(state.cpu())
        del payload  # Parameters and Adam state now live on the training device.
    else:
        model = initialize_model(training_data, points, settings, device)
        optimizer = make_optimizer(model, settings)
    # A crash can leave log lines newer than the last atomic checkpoint.
    log_path = output / "train.jsonl"
    if log_path.exists():
        lines = []
        for line in log_path.read_text().splitlines():
            try:
                if json.loads(line)["step"] <= start_step:
                    lines.append(line)
            except (ValueError, KeyError):
                break
        temporary = log_path.with_suffix(".tmp")
        temporary.write_text("".join(line + "\n" for line in lines))
        temporary.replace(log_path)
    write_json(output / "config.json", settings)
    torch.cuda.reset_peak_memory_stats(device)
    started = time.monotonic()
    end_step = settings["steps"] if stop_after is None else min(settings["steps"], start_step + stop_after)
    if end_step <= start_step:
        return checkpoint
    cameras = [make_camera(camera, settings, device) for camera in training_data.cameras]
    with (output / "train.jsonl").open("a") as log:
        for step, (pixels, indices) in enumerate(
            batches(
                training_data,
                sampler,
                start_step,
                end_step,
                device,
                batch_size=settings["batch_size"],
                loader_workers=settings["loader_workers"],
                seed=settings["seed"],
            ),
            start_step,
        ):
            optimizer.zero_grad(set_to_none=True)
            images, alphas, metadata = [], [], []
            for index in indices:
                camera_idx, frame_idx = divmod(index, len(training_data.frames))
                image, alpha, meta = render(
                    model,
                    cameras[camera_idx],
                    float(training_data.times[frame_idx]),
                    marginal_threshold=settings["marginal_threshold"],
                )
                images.append(image)
                alphas.append(alpha)
                metadata.append(meta)
            loss, terms = objective(torch.stack(images), torch.stack(alphas), pixels[:, :3], pixels[:, 3:], step=step)
            loss.backward()
            changed, counts = topology.update(model, optimizer, step)
            optimizer.step()
            topology.refresh_sh_threshold(model)
            if not changed and 0 < step <= settings["prune_until"]:
                accumulate_statistics(model, metadata)
            if step % settings["log_every"] == 0 or step + 1 == end_step:
                record = {name: float(value.detach()) for name, value in {**terms, "loss": loss}.items()}
                if not all(math.isfinite(value) for value in record.values()):
                    raise RuntimeError(f"Nonfinite loss at step {step}")
                record.update(
                    step=step + 1,
                    points=len(model),
                    degree=model.degree,
                    seconds=time.monotonic() - started,
                    peak_memory_bytes=torch.cuda.max_memory_allocated(device),
                    **counts,
                )
                log.write(json.dumps(record) + "\n")
                log.flush()
                print(json.dumps(record), flush=True)
            retain = step + 1 in settings["checkpoint_steps"]
            if (step + 1) % settings["save_every"] == 0 or step + 1 == end_step or retain:
                background_rng = (
                    objective.background_generator.get_state() if objective.background_generator is not None else None
                )
                save_checkpoint(
                    checkpoint,
                    model,
                    optimizer,
                    topology,
                    sampler,
                    training_data,
                    settings,
                    step + 1,
                    fingerprint,
                    background_rng,
                    weights_identity,
                )
                if retain:
                    # latest.pt is atomically replaced; this inode stays valid and costs no second copy.
                    for suffix in (".pt", ".npz"):
                        saved = checkpoint.with_name(f"step-{step + 1:06d}{suffix}")
                        if saved.exists():
                            saved.unlink()
                        saved.hardlink_to(checkpoint.with_suffix(suffix))
    return checkpoint
