"""Execute the ordinary inference entrypoint in an owned, cancellable process."""

from __future__ import annotations

import json
import logging
import sys
import traceback
from pathlib import Path


def write_status(path: Path, message: str, fraction: float, **fields) -> None:
    """Readers always see one complete status document."""

    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"message": message, "fraction": fraction, **fields}) + "\n")
    temporary.replace(path)


class ProgressHandler(logging.Handler):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def emit(self, record: logging.LogRecord) -> None:
        write_status(self.path, record.getMessage(), float(record.fraction))


def main(request_path: str) -> int:
    request = Path(request_path)
    status = request.with_name("status.json")
    logger = logging.getLogger("fdanyone.progress")
    logger.setLevel(logging.INFO)
    handler = ProgressHandler(status)
    logger.addHandler(handler)
    try:
        from inference import inference

        options = json.loads(request.read_text())
        summary = inference(**options)
        write_status(status, "Inference complete", 1.0, summary=summary)
    except Exception as exc:
        write_status(status, str(exc) or type(exc).__name__, 0.0, error=True)
        traceback.print_exc()
        return 1
    finally:
        logger.removeHandler(handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
