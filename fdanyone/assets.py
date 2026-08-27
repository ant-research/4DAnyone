"""Locate the model files used by 4DAnyone.

Every published file is anchored by one immutable Hugging Face revision and
downloaded on demand. ``fdanyone.download`` fetches missing files;
the resolvers here only locate them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fdanyone.errors import AssetError

HF_REPO_ID = "AntResearch/4DAnyone"
HF_REVISION = "442816913e7cc75be2ede1a5c93a86d936d032f1"

BIREFNET_REPO_ID = "ZhengPeng7/BiRefNet"
BIREFNET_REVISION = "e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4"
BIREFNET_DIR = "birefnet"
BIREFNET_FILES = (
    "BiRefNet_config.py",
    "birefnet.py",
    "config.json",
    "model.safetensors",
)

CHECKPOINT = "4danyone/model.safetensors"
MHR70_REGRESSOR = "4danyone/smplx_to_goliath70.pt"
WAN_VAE = "4danyone/Wan2.2_VAE.pth"
PROMPT_CONTEXT = "4danyone/prompt_context.safetensors"

GVHMR_CHECKPOINT = "gvhmr/gvhmr_siga24_release.ckpt"
HMR2_CHECKPOINT = "gvhmr/epoch=10-step=25000.ckpt"
VITPOSE_CHECKPOINT = "gvhmr/vitpose-h-multi-coco.pth"
YOLO_CHECKPOINT = "gvhmr/yolov8x.pt"
PERCEPTUAL_VGG19 = "perceptual/imagenet-vgg-verydeep-19-conv.safetensors"

SMPLX_MODEL = "body_models/smplx/SMPLX_NEUTRAL.npz"

MODEL_FILES = (
    CHECKPOINT,
    MHR70_REGRESSOR,
    WAN_VAE,
    PROMPT_CONTEXT,
    GVHMR_CHECKPOINT,
    HMR2_CHECKPOINT,
    VITPOSE_CHECKPOINT,
    YOLO_CHECKPOINT,
    PERCEPTUAL_VGG19,
)

EXAMPLE_FILES = (
    "data/source/pexels/10331522-uhd_2160_4096_25fps.mp4",
    "data/source/pexels/15443888_1080_1920_100fps.mp4",
    "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4",
    "data/source/pexels/5385965-uhd_2160_4096_25fps.mp4",
    "data/source/pexels/5390224-uhd_2160_4096_30fps.mp4",
    "data/source/pexels/5390836-uhd_2160_4096_30fps.mp4",
    "data/source/pexels/5435720-uhd_2160_4096_25fps.mp4",
    "data/source/pexels/5885633-hd_1080_1920_25fps.mp4",
    "data/source/pexels/5999210-uhd_2160_4096_25fps.mp4",
    "data/source/pexels/6003989-uhd_2160_3840_30fps.mp4",
    "data/source/pexels/6191453-uhd_2160_4096_25fps.mp4",
    "data/source/pexels/6616344-hd_1080_1920_25fps.mp4",
    "data/source/pexels/6980035-uhd_2160_4096_30fps.mp4",
    "data/source/pexels/7017803-hd_1080_1920_30fps.mp4",
    "data/source/pexels/7080903-hd_1080_1920_30fps.mp4",
    "data/source/pexels/7341232-uhd_2160_3840_25fps.mp4",
    "data/source/pexels/7480858-uhd_2160_3840_25fps.mp4",
    "data/source/pexels/7716891-uhd_2160_4096_25fps.mp4",
    "data/source/pexels/8059623-hd_1080_1920_25fps.mp4",
    "data/source/pexels/8431510-uhd_2160_4096_25fps.mp4",
)

# Upstream GVHMR resolves its model files relative to its own checkout, so the
# install commands link each downloaded file to the location GVHMR expects.
GVHMR_LINKS = (
    (GVHMR_CHECKPOINT, "inputs/checkpoints/gvhmr/gvhmr_siga24_release.ckpt"),
    (HMR2_CHECKPOINT, "inputs/checkpoints/hmr2/epoch=10-step=25000.ckpt"),
    (VITPOSE_CHECKPOINT, "inputs/checkpoints/vitpose/vitpose-h-multi-coco.pth"),
    (YOLO_CHECKPOINT, "inputs/checkpoints/yolo/yolov8x.pt"),
    (SMPLX_MODEL, "inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz"),
)


@dataclass(frozen=True)
class BaseAssets:
    vae: Path
    prompt_context: Path


def _require_file(path: Path, label: str, command: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise AssetError(f"{label} does not exist: {resolved}. Run `python {command}` to install it.")
    return resolved


def resolve_checkpoint(path: str | Path | None = None, model_dir: str | Path = "models") -> Path:
    if path is not None:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_file():
            raise AssetError(f"Checkpoint override does not exist: {resolved}")
        return resolved
    return _require_file(Path(model_dir) / CHECKPOINT, "Checkpoint", "scripts/download_model.py")


def resolve_regressor(path: str | Path | None = None, model_dir: str | Path = "models") -> Path:
    if path is not None:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_file():
            raise AssetError(f"MHR70 regressor override does not exist: {resolved}")
        return resolved
    return _require_file(Path(model_dir) / MHR70_REGRESSOR, "MHR70 regressor", "scripts/download_model.py")


def resolve_foreground_model(model_dir: str | Path = "models") -> Path:
    root = Path(model_dir).expanduser() / BIREFNET_DIR
    for relative in BIREFNET_FILES:
        _require_file(root / relative, "BiRefNet file", "scripts/download_model.py")
    return root.resolve()


def resolve_perceptual_vgg19(model_dir: str | Path = "models") -> Path:
    """Resolve the converted VGG-19 weights used by perceptual reconstruction."""

    return _require_file(
        Path(model_dir) / PERCEPTUAL_VGG19,
        "Perceptual VGG-19 weights",
        "scripts/download_model.py",
    )


def resolve_base_assets(model_dir: str | Path = "models") -> BaseAssets:
    """Resolve the local VAE and frozen prompt conditioning."""

    root = Path(model_dir).expanduser()
    return BaseAssets(
        vae=_require_file(root / WAN_VAE, "VAE", "scripts/download_model.py"),
        prompt_context=_require_file(root / PROMPT_CONTEXT, "Prompt conditioning", "scripts/download_model.py"),
    )
