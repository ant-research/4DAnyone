# Inference Performance

This report provides practical runtime and GPU-memory references for running 4DAnyone on common GPUs.

## Turbo vs. Base

### Generation Quality

The 4-step Turbo model achieves quality comparable to a 50-step Base reference:

| Model | Denoising steps | PSNR ↑ | SSIM ↑ | LPIPS ↓ |
| --- | ---: | ---: | ---: | ---: |
| 4DAnyone-Turbo | 4 | 25.48 | 0.895 | 0.072 |
| 4DAnyone-Base | 50 | 25.69 | 0.899 | 0.073 |

### Denoising Speedup

For the 6-view example, Turbo uses 4 denoising steps and Base uses 24. The values show Turbo's speedup over Base on the same GPU and attention backend.

| GPU | SDPA | FlashAttention-3 | SageAttention |
| --- | ---: | ---: | ---: |
| H200 | 5.49× | 5.35× | 5.12× |
| H20-3E | 5.83× | 5.78× | 5.73× |
| RTX 5880 Ada | 5.79× | — | 5.80× |
| RTX A6000 | 5.77× | — | 5.75× |
| RTX 4090 | 5.85× | — | 5.78× |

## 4DAnyone-Turbo Performance

The performance tables below use the following terms:

- `SDPA`, `FlashAttention-3`, and `SageAttention`: denoising time for each attention backend.
- `Peak CUDA allocated`: maximum live tensor memory during generation.
- `GPU memory`: total memory capacity per GPU.
- `—`: backend or workload unavailable on that GPU.

> [!note]
> SageAttention results use the official `sageattn` entry point, which automatically dispatches an architecture-specific kernel for each GPU.

### 6-View Full Orbit

The [6-view full-orbit](../README.md#6-view-full-orbit) benchmark uses the following command:

```bash
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 6
```

| GPU | SDPA (min) | FlashAttention-3 (min) | SageAttention (min) | Peak CUDA allocated (GB) | GPU memory (GB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| H200 | 0.97 | 0.76 | 0.80 | 24.06 | 139.81 |
| H20-3E | 3.21 | 2.54 | 2.09 | 24.06 | 139.81 |
| RTX 5880 Ada | 3.47 | — | 2.99 | 24.06 | 47.37 |
| RTX A6000 | 3.78 | — | 3.69 | 24.06 | 47.53 |
| RTX 4090 | 2.71 | — | 2.13 | 22.18 | 23.52 |

### 24-View Full Orbit

The [24-view full-orbit](../README.md#24-view-full-orbit) benchmark runs 4DAnyone-Turbo on a single GPU:

```bash
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 24
```

For 24-view generation, the pipeline first denoises six RCP views to use as references and then denoises the 24 target views. The table reports the total time for both stages.

| GPU | SDPA (min) | FlashAttention-3 (min) | SageAttention (min) | Peak CUDA allocated (GB) | GPU memory (GB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| H200 | 5.11 | 3.90 | 3.90 | 24.06 | 139.81 |
| H20-3E | 17.66 | 13.86 | 11.24 | 24.06 | 139.81 |
| RTX 5880 Ada | 18.84 | — | 16.14 | 24.06 | 47.37 |
| RTX A6000 | 20.55 | — | 19.98 | 24.06 | 47.53 |
| RTX 4090 | 16.20 | — | — | 22.18 | 23.52 |

## 4DAnyone-Base Performance

The 6-view 4DAnyone-Base benchmark uses 24 denoising steps:

```bash
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 6 \
    --enable_turbo=False
```

| GPU | SDPA (min) | FlashAttention-3 (min) | SageAttention (min) | Peak CUDA allocated (GB) | GPU memory (GB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| H200 | 5.33 | 4.05 | 4.09 | 24.06 | 139.81 |
| H20-3E | 18.68 | 14.70 | 11.98 | 24.06 | 139.81 |
| RTX 5880 Ada | 20.10 | — | 17.36 | 24.06 | 47.37 |
| RTX A6000 | 21.82 | — | 21.20 | 24.06 | 47.53 |
| RTX 4090 | 15.86 | — | 12.29 | 22.18 | 23.52 |

## Preprocessing Performance

GVHMR and skeleton extraction run before denoising and are shared by both models. These 6-view timings can vary with CPU and storage performance.

- `GVHMR`: tracking, ViTPose, image-feature extraction, and motion prediction.
- `Skeleton extraction`: target-view skeleton-condition rendering.

| GPU | GVHMR (min) | Skeleton extraction (min) |
| --- | ---: | ---: |
| H200 | 1.20 | 1.25 |
| H20-3E | 1.08 | 1.27 |
| RTX 5880 Ada | 0.98 | 1.00 |
| RTX A6000 | 1.57 | 2.12 |
| RTX 4090 | 0.72 | 0.73 |
