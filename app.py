"""Launch 4DAnyone Space in the inference environment."""

from __future__ import annotations

import os
import signal
import sys

from fdanyone.attention import validate_attention_backend
from fdanyone.cli import check_arguments
from fdanyone.errors import ConfigurationError, FourDAnyoneError
from fdanyone.space.task import SpaceConfig, repository_path, resolve_task


def launch(
    video_path: str | None = None,
    output_dir: str | None = None,
    model_dir: str = "models",
    gvhmr_root: str = "third_party/GVHMR",
    cache_dir: str = "outputs/space",
    gpu_ids: list[int] | None = None,
    attention_backend: str = "auto",
    server_name: str = "127.0.0.1",
    server_port: int = 7860,
) -> None:
    """Launch 4DAnyone Space for interactive inference and visualization.

    Relative paths use the code repository root.

    Args:
        video_path: Source video for a new task.
        output_dir: Task result directory. Omit video_path to view or resume it.
            New tasks default to a new directory under data/4danyone/<clip>/.
        model_dir: Model root; missing public checkpoints download here.
        gvhmr_root: Path to the GVHMR source checkout.
        cache_dir: Logs, body geometry, and scene recordings.
        gpu_ids: Initially selected GPU IDs, e.g. [0] or [0,1].
            Omit to select all CUDA-visible GPUs, as in the CLI.
        attention_backend: auto, sdpa, sageattention, or flash_attn_3.
        server_name: Server bind address.
        server_port: Server port, from 1 to 65535.
    """
    validate_attention_backend(attention_backend)
    if isinstance(server_port, bool) or not isinstance(server_port, int) or not 1 <= server_port <= 65535:
        raise ConfigurationError("server_port must be an integer from 1 to 65535.")
    video_path, output_dir = resolve_task(video_path, output_dir)
    config = SpaceConfig(
        output_dir=output_dir,
        cache_dir=repository_path(cache_dir).resolve(),
        model_dir=repository_path(model_dir).resolve(),
        gvhmr_root=repository_path(gvhmr_root).resolve(),
        gpu_ids=tuple(gpu_ids) if gpu_ids is not None else None,
        attention_backend=attention_backend,
        video_path=video_path,
    )
    _serve(config, server_name=server_name, server_port=server_port)


def _serve(config: SpaceConfig, *, server_name: str, server_port: int) -> None:
    cache_dir = config.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Gradio's shared /tmp/gradio may belong to another user on a GPU host.
    # Set this before importing Gradio, which initializes its upload cache.
    os.environ.setdefault("GRADIO_TEMP_DIR", str(cache_dir / "gradio"))
    try:
        from fdanyone.space.server import create_app
        from fdanyone.web import serve
    except ImportError as exc:
        raise SystemExit(
            f"GUI dependency unavailable: {exc}. Install requirements.txt and requirements-gui.txt."
        ) from exc

    def shutdown(_signum, _frame):
        raise SystemExit(0)

    previous_sigterm = signal.signal(signal.SIGTERM, shutdown)
    try:
        print(f"Output Directory: {config.output_dir}", flush=True)
        app = create_app(config, server_name=server_name, server_port=server_port)
        serve(app, host=server_name, port=server_port)
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)


def main() -> None:
    from fire import Fire

    try:
        args = sys.argv[1:]
        if any(arg in ("--help", "-h") for arg in args):
            args = ["--help"]
        else:
            check_arguments(launch, args)
        Fire(launch, command=args)
    except KeyboardInterrupt:
        pass
    except FourDAnyoneError as exc:
        message = " ".join(line.strip() for line in str(exc).splitlines())
        print(f"error: {message}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
