"""Shared BiRefNet inference for source clips and generated views."""

from __future__ import annotations

import gc
from collections.abc import Iterable, Iterator
from contextlib import closing
from itertools import islice
from pathlib import Path

import numpy as np
from PIL import Image

from fdanyone.config import FOREGROUND


def _validate_frames(frames, shape):
    if len(shape) != 3 or shape[-1] != 3 or any(frame.dtype != np.uint8 or frame.shape != shape for frame in frames):
        raise ValueError("Foreground frames must share one RGB uint8 raster.")


def iter_foreground_masks(
    frames: Iterable[np.ndarray],
    model_path: str | Path,
    device: str,
    *,
    batch_size: int = FOREGROUND.batch_size,
) -> Iterator[np.ndarray]:
    """Yield full-raster uint8 masks, loading one batch of RGB frames at a time.

    Close the iterator if consumption stops early to release the model promptly.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive.")
    frames = iter(frames)
    batch = tuple(islice(frames, batch_size))
    if not batch:
        raise ValueError("Foreground inference requires at least one frame.")
    shape = batch[0].shape
    _validate_frames(batch, shape)

    import torch
    from torchvision import transforms
    from torchvision.transforms.functional import to_pil_image
    from transformers import AutoModelForImageSegmentation

    model = AutoModelForImageSegmentation.from_pretrained(
        str(Path(model_path).expanduser().resolve()),
        local_files_only=True,
        trust_remote_code=True,
    )
    try:
        model = model.eval().half().to(device)
        transform = transforms.Compose(
            [
                transforms.Resize(FOREGROUND.image_size),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
        while batch:
            _validate_frames(batch, shape)
            images = [Image.fromarray(frame, mode="RGB") for frame in batch]
            inputs = torch.stack([transform(image) for image in images]).to(device=device, dtype=torch.float16)
            with torch.inference_mode():
                predictions = model(inputs)[-1].sigmoid().cpu()
            del inputs
            for image, prediction in zip(images, predictions, strict=True):
                mask = to_pil_image(prediction).resize(image.size).convert("L")
                yield np.asarray(mask, dtype=np.uint8).copy()
            del predictions, images, batch
            batch = tuple(islice(frames, batch_size))
    finally:
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def predict_foreground_masks(
    frames: tuple[np.ndarray, ...],
    model_path: str | Path,
    device: str,
    *,
    batch_size: int = FOREGROUND.batch_size,
) -> np.ndarray:
    """Return full-raster 8-bit foreground masks for an in-memory clip."""
    if not frames:
        raise ValueError("Foreground inference requires at least one frame.")
    _validate_frames(frames, frames[0].shape)
    with closing(iter_foreground_masks(frames, model_path, device, batch_size=batch_size)) as masks:
        return np.stack(list(masks))
