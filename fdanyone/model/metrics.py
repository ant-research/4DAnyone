"""Stage-local wall-time and CUDA-memory measurements for generation."""

from __future__ import annotations

import time
from contextlib import contextmanager


class GenerationMetrics:
    """Measure independent stages while preserving an end-to-end CUDA peak."""

    def __init__(self, device_index: int) -> None:
        self.device_index = device_index
        self.elapsed_seconds: dict[str, float] = {}
        self.stage_peak_vram_bytes: dict[str, dict[str, int]] = {}
        self._active_stage: str | None = None

    @contextmanager
    def stage(self, name: str):
        """Measure one non-overlapping stage."""

        import torch

        if self._active_stage is not None:
            raise RuntimeError(f"Cannot start stage {name!r} while {self._active_stage!r} is active.")
        if name in self.elapsed_seconds:
            raise RuntimeError(f"Generation stage {name!r} was measured more than once.")

        self._active_stage = name
        torch.cuda.synchronize(self.device_index)
        torch.cuda.reset_peak_memory_stats(self.device_index)
        started = time.monotonic()
        try:
            yield
        finally:
            torch.cuda.synchronize(self.device_index)
            self.elapsed_seconds[name] = time.monotonic() - started
            self.merge_cuda_peak(
                name,
                allocated_bytes=int(torch.cuda.max_memory_allocated(self.device_index)),
                reserved_bytes=int(torch.cuda.max_memory_reserved(self.device_index)),
            )
            self._active_stage = None

    def merge_cuda_peak(self, name: str, *, allocated_bytes: int, reserved_bytes: int) -> None:
        """Merge a child-process/device measurement into a named stage."""

        if allocated_bytes < 0 or reserved_bytes < 0:
            raise ValueError("CUDA memory measurements cannot be negative.")
        previous = self.stage_peak_vram_bytes.get(name, {})
        self.stage_peak_vram_bytes[name] = {
            "allocated": max(allocated_bytes, previous.get("allocated", 0)),
            "reserved": max(reserved_bytes, previous.get("reserved", 0)),
        }

    @property
    def peak_vram_allocated_bytes(self) -> int:
        return max((record["allocated"] for record in self.stage_peak_vram_bytes.values()), default=0)

    @property
    def peak_vram_reserved_bytes(self) -> int:
        return max((record["reserved"] for record in self.stage_peak_vram_bytes.values()), default=0)
