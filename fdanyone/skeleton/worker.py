"""Private subprocess entry point for licensed body-model conditioning."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fdanyone.device import select_cuda_device
from fdanyone.motion.result import MotionResult
from fdanyone.skeleton.pipeline import build_skeleton_conditioning
from fdanyone.video import load_canonical_working_clip
from fdanyone.views import ViewPlan


def main(request_path: str) -> None:
    request = json.loads(Path(request_path).read_text())
    device, _ = select_cuda_device(request["device"])
    clip = load_canonical_working_clip(request["working_video"], request["clip_metadata"])
    motion = MotionResult.load(request["motion_result_dir"])
    build_skeleton_conditioning(
        motion=motion,
        clip=clip,
        regressor_path=request["regressor_path"],
        foreground_model_path=request["foreground_model_path"],
        gvhmr_root=request["gvhmr_root"],
        output_dir=request["output_dir"],
        device=device,
        view_plan=ViewPlan.from_dict(request["view_plan"]),
        reference_video_paths=tuple(Path(path) for path in request["reference_video_paths"]),
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m fdanyone.skeleton.worker REQUEST.json")
    main(sys.argv[1])
