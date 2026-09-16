"""Inspect CUDA's logical devices in a short-lived process, outside the web server."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def available_gpus() -> list[str]:
    """Keep CUDA ordering/masking while releasing the probe's CUDA context on exit."""
    result = subprocess.run(
        [sys.executable, "-m", "fdanyone.space.gpus"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def main() -> None:
    try:
        import torch
    except ModuleNotFoundError as exc:
        if exc.name != "torch":
            raise
        names = []
    else:
        names = (
            [torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())]
            if torch.cuda.is_available()
            else []
        )
    print(json.dumps(names))


if __name__ == "__main__":
    main()
