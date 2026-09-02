"""Classic GVHMR inference used by 4DAnyone.

The official demo imports training, evaluation, visualization, and
moving-camera modules eagerly. This file keeps the released static-camera path
in one place without exposing Hydra or backend abstractions to 4DAnyone users.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import itertools
import json
import os
import subprocess
import sys
import types
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fdanyone.errors import AssetError, VideoContractError
from fdanyone.motion.result import SMPL_PARAMETER_NAMES, MotionResult
from fdanyone.vendor.pytorch3d_compat import install_if_needed as install_pytorch3d_compat
from fdanyone.video import CanonicalClip

GVHMR_ASSETS = (
    "inputs/checkpoints/gvhmr/gvhmr_siga24_release.ckpt",
    "inputs/checkpoints/hmr2/epoch=10-step=25000.ckpt",
    "inputs/checkpoints/vitpose/vitpose-h-multi-coco.pth",
    "inputs/checkpoints/yolo/yolov8x.pt",
    "inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz",
)


def validate_gvhmr(root: str | Path) -> tuple[Path, str]:
    """Locate the GVHMR checkout and files consumed by inference."""

    path = Path(root).expanduser().resolve()
    required = ("hmr4d/__init__.py", "tools/demo/demo.py", *GVHMR_ASSETS)
    missing = [relative for relative in required if not (path / relative).is_file()]
    if missing:
        formatted = "\n  - ".join(missing)
        raise AssetError(
            f"GVHMR is incomplete under {path}. Run `git submodule update --init third_party/GVHMR`, "
            f"`python scripts/download_model.py`, and `python scripts/download_smplx.py`; missing:\n"
            f"  - {formatted}"
        )
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AssetError(f"GVHMR must be a git checkout: {path}") from exc
    if len(revision) != 40:
        raise AssetError(f"Cannot identify the GVHMR revision at {path}.")
    return path, revision


def hydra_override(name: str, value: str | Path) -> str:
    """Quote a path for the internal GVHMR Hydra config."""

    if not name.isidentifier():
        raise ValueError(f"Invalid Hydra field name: {name!r}.")
    return f"{name}={json.dumps(str(value), ensure_ascii=False)}"


@contextmanager
def gvhmr_imports(root: Path) -> Iterator[None]:
    """Temporarily import GVHMR as if its checkout were the working tree."""

    old_cwd = Path.cwd()
    root_text = str(root)
    already_present = root_text in sys.path
    if not already_present:
        sys.path.insert(0, root_text)
    os.chdir(root)
    try:
        yield
    finally:
        os.chdir(old_cwd)
        if not already_present:
            with contextlib.suppress(ValueError):
                sys.path.remove(root_text)


@contextmanager
def _legacy_checkpoint_loading():
    """Restore pre-2.6 ``torch.load`` behavior for trusted GVHMR assets."""

    name = "TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"
    previous = os.environ.get(name)
    os.environ[name] = "1"
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"Environment variable TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD detected.*",
                category=UserWarning,
            )
            yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def _install_optional_import_stubs() -> None:
    """Avoid visualization and moving-camera dependencies we never call."""

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("Wis3D visualization is not part of 4DAnyone inference.")

    if importlib.util.find_spec("wis3d") is None:
        module = types.ModuleType("hmr4d.utils.wis3d_utils")
        module.make_wis3d = unavailable
        module.add_motion_as_lines = unavailable
        sys.modules[module.__name__] = module

    def moving_camera_unavailable(*_args, **_kwargs):
        raise RuntimeError("SimpleVO is unavailable in the static-camera 4DAnyone runtime.")

    module = types.ModuleType("hmr4d.utils.preproc.relpose.simple_vo")
    module.SimpleVO = moving_camera_unavailable
    sys.modules[module.__name__] = module


def _register_inference_store() -> None:
    """Register only the Hydra groups referenced by GVHMR's demo config."""

    _install_optional_import_stubs()
    for module in (
        "hmr4d.model.gvhmr.gvhmr_pl_demo",
        "hmr4d.model.gvhmr.utils.endecoder",
        "hmr4d.network.gvhmr.relative_transformer",
    ):
        importlib.import_module(module)

    # GVHMR installs a colored handler on the root logger. Remove only that
    # duplicate because the public pipeline already owns a handler.
    logger_module = sys.modules.get("hmr4d.utils.pylogger")
    logger = getattr(logger_module, "Log", None)
    handler = getattr(logger_module, "ch", None)
    if (
        logger is not None
        and handler in logger.handlers
        and any(candidate is not handler for candidate in logger.handlers)
    ):
        logger.removeHandler(handler)


def _run_preprocess(cfg) -> None:
    """Run tracker, ViTPose, and image-feature extraction."""

    import torch
    from hmr4d.utils.geo.hmr_cam import get_bbx_xys_from_xyxy
    from hmr4d.utils.preproc.tracker import Tracker
    from hmr4d.utils.preproc.vitfeat_extractor import Extractor
    from hmr4d.utils.preproc.vitpose import VitPoseExtractor
    from hmr4d.utils.pylogger import Log

    if not bool(cfg.static_cam):
        raise ValueError("4DAnyone requires GVHMR static_cam=true.")

    Log.info("[Preprocess] Start!")
    started = Log.time()
    video_path = cfg.video_path
    paths = cfg.paths

    if not Path(paths.bbx).exists():
        tracker = Tracker()
        bbx_xyxy = tracker.get_one_track(video_path).float()
        bbx_xys = get_bbx_xys_from_xyxy(bbx_xyxy, base_enlarge=1.2).float()
        torch.save({"bbx_xyxy": bbx_xyxy, "bbx_xys": bbx_xys}, paths.bbx)
        del tracker
    else:
        bbx_xys = torch.load(paths.bbx, weights_only=True)["bbx_xys"]
        Log.info("[Preprocess] bbx (xyxy, xys) from %s", paths.bbx)

    if not Path(paths.vitpose).exists():
        extractor = VitPoseExtractor()
        torch.save(extractor.extract(video_path, bbx_xys), paths.vitpose)
        del extractor
    else:
        Log.info("[Preprocess] vitpose from %s", paths.vitpose)

    if not Path(paths.vit_features).exists():
        extractor = Extractor()
        torch.save(extractor.extract_video_features(video_path, bbx_xys), paths.vit_features)
        del extractor
    else:
        Log.info("[Preprocess] vit_features from %s", paths.vit_features)

    Log.info("[Preprocess] End. Time elapsed: %.2fs", Log.time() - started)


def _load_data(cfg):
    """Build the static-camera tensors consumed by GVHMR."""

    import torch
    from hmr4d.utils.geo.hmr_cam import estimate_K
    from hmr4d.utils.geo_transform import compute_cam_angvel
    from hmr4d.utils.video_io_utils import get_video_lwh

    if not bool(cfg.static_cam):
        raise ValueError("4DAnyone requires GVHMR static_cam=true.")
    paths = cfg.paths
    length, width, height = get_video_lwh(cfg.video_path)
    rotation_world_to_camera = torch.eye(3).repeat(length, 1, 1)
    intrinsics = estimate_K(width, height).repeat(length, 1, 1)
    return {
        "length": torch.tensor(length),
        "bbx_xys": torch.load(paths.bbx, weights_only=True)["bbx_xys"],
        "kp2d": torch.load(paths.vitpose, weights_only=True),
        "K_fullimg": intrinsics,
        "cam_angvel": compute_cam_angvel(rotation_world_to_camera),
        "f_imgseq": torch.load(paths.vit_features, weights_only=True),
    }


def _verify_gvhmr_decode(clip: CanonicalClip, working_video: Path, reader_factory) -> None:
    """Ensure GVHMR's own video reader sees the canonical RGB frames."""

    import numpy as np

    reader = reader_factory(str(working_video))
    sentinel = object()
    try:
        for index, (actual, expected) in enumerate(itertools.zip_longest(reader, clip.rgb_frames, fillvalue=sentinel)):
            if actual is sentinel or expected is sentinel or not np.array_equal(actual, expected):
                raise VideoContractError(f"GVHMR decoded a different canonical frame at index {index}.")
    finally:
        close = getattr(reader, "close", None)
        if close is not None:
            close()


def run_gvhmr(
    *,
    clip: CanonicalClip,
    working_video: str | Path,
    output_dir: str | Path,
    gvhmr_root: str | Path,
    device: str,
) -> MotionResult:
    """Recover static-camera human motion from the canonical source clip."""

    root, revision = validate_gvhmr(gvhmr_root)
    working_video = Path(working_video).expanduser().resolve()
    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    with gvhmr_imports(root), _legacy_checkpoint_loading():
        install_pytorch3d_compat()
        import hydra
        import torch
        from hmr4d.model.gvhmr.gvhmr_pl_demo import DemoPL
        from hmr4d.utils.net_utils import detach_to_cpu
        from hmr4d.utils.video_io_utils import get_video_reader
        from hydra import compose, initialize_config_module
        from omegaconf import open_dict

        _register_inference_store()
        with initialize_config_module(version_base="1.3", config_module="hmr4d.configs"):
            cfg = compose(
                config_name="demo",
                overrides=[
                    hydra_override("video_name", working_video.stem),
                    "static_cam=true",
                    "verbose=false",
                    "use_dpvo=false",
                    hydra_override("output_root", output_root),
                ],
            )
        Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)
        Path(cfg.preprocess_dir).mkdir(parents=True, exist_ok=True)
        with open_dict(cfg):
            cfg.video_path = str(working_video)

        _verify_gvhmr_decode(clip, working_video, get_video_reader)
        _run_preprocess(cfg)
        data = _load_data(cfg)
        if int(data["length"]) != len(clip.frames):
            raise RuntimeError(f"GVHMR decoded {int(data['length'])} frames, expected {len(clip.frames)}.")
        observed_keypoints_2d = data["kp2d"].detach().cpu()
        model: DemoPL = hydra.utils.instantiate(cfg.model, _recursive_=False)
        model.load_pretrained_model(cfg.ckpt_path)
        model = model.eval().to(device)
        with torch.inference_mode():
            prediction = detach_to_cpu(model.predict(data, static_cam=True))
        del model, data
        torch.cuda.empty_cache()

    result = MotionResult(
        gvhmr_revision=revision,
        fps=clip.fps,
        frame_timestamps_sec=tuple(float(frame.canonical_timestamp) for frame in clip.frames),
        source_frame_indices=tuple(frame.source_index for frame in clip.frames),
        source_pts=tuple(frame.source_pts for frame in clip.frames),
        source_size_bytes=clip.source_size_bytes,
        source_mtime_ns=clip.source_mtime_ns,
        image_height=clip.height,
        image_width=clip.width,
        smpl_params_global={name: prediction["smpl_params_global"][name] for name in SMPL_PARAMETER_NAMES},
        smpl_params_incam={name: prediction["smpl_params_incam"][name] for name in SMPL_PARAMETER_NAMES},
        K_fullimg=prediction["K_fullimg"],
        observed_keypoints_2d=observed_keypoints_2d,
    )
    result.validate(expected_frames=len(clip.frames))
    return result
