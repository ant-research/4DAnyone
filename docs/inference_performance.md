# Inference performance

This page reports inference efficiency for the [6-view full-orbit](../README.md#6-view-full-orbit) example using:

```bash
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 6
```

Each configuration reports the median of three runs.

## Denoising

This table compares denoising time across attention backends.

- `SDPA`, `FlashAttention-3`, and `SageAttention`: denoising time using each attention backend.
- `Peak CUDA allocated`: maximum live tensor allocation during generation. It was identical across the tested backends on each GPU.
- `GPU memory`: total device memory capacity.
- `—`: backend unavailable on that GPU.

| GPU | SDPA (min) | FlashAttention-3 (min) | SageAttention (min) | Peak CUDA allocated (GiB) | GPU memory (GiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| H200 | 8.87 | 7.55 | 7.59 | 25.37 | 139.81 |
| H20-3E | 19.55 | 15.63 | 12.89 | 25.37 | 139.81 |
| RTX 5880 Ada | 20.28 | — | 17.51 | 24.21 | 47.37 |
| RTX A6000 | 22.41 | — | 21.78 | 24.06 | 47.53 |

> [!NOTE]
> SageAttention results use the official `sageattn` entry point, which automatically dispatches an architecture-specific kernel for each GPU.

## Preprocessing

This table reports preprocessing time before generation.

- `GVHMR`: tracking, ViTPose, image-feature extraction, and motion prediction.
- `Skeleton extraction`: target-view skeleton-condition rendering.

| GPU | GVHMR (min) | Skeleton extraction (min) |
| --- | ---: | ---: |
| H200 | 0.94 | 0.57 |
| H20-3E | 0.97 | 0.55 |
| RTX 5880 Ada | 0.94 | 1.00 |
| RTX A6000 | 1.70 | 1.06 |
