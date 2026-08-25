# Inference performance

This page reports inference efficiency for the [6-view full-orbit](../README.md#6-view-full-orbit) example using:

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 6
```

Each configuration reports the median of three runs.

| GPU | Backend | GVHMR (min) | Skeleton extraction (min) | Denoising (min) | Peak CUDA allocated (GiB) |
| --- | --- | ---: | ---: | ---: | ---: |
| H200 | SDPA | 0.94 | 0.57 | 9.17 | 43.34 |
| H200 | FlashAttention-3 | 0.94 | 0.57 | 7.84 | 43.34 |
| H20-3E | SDPA | 0.97 | 0.55 | 20.59 | 43.34 |
| H20-3E | FlashAttention-3 | 0.97 | 0.55 | 16.62 | 43.34 |
| RTX A6000 | SDPA | 1.70 | 1.06 | 22.93 | 43.32 |

Metrics are defined as follows:

- `GVHMR`: tracking, ViTPose, image-feature extraction, and motion prediction.
- `Skeleton extraction`: target-view skeleton-condition rendering.
- `Denoising`: the generation stage affected by the attention backend.
- `Peak CUDA allocated`: the maximum live tensor allocation during generation.

> [!NOTE]
> On supported GPUs, FlashAttention-3 is selected automatically once installed.
