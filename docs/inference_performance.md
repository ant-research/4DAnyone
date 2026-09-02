# Inference performance

We compare **4DAnyone-Turbo**, the default accelerated model, with **4DAnyone-Base**, the original model described in the paper.

## Quality comparison

We evaluate 32 validation scenes: 16 from DNA-Rendering, 8 from MVGameHuman, and 8 from SynCamVideo. Both models use identical target cameras, 25-frame clips, seed 42, and foreground-masked metrics; 4DAnyone-Turbo uses 4 denoising steps with scheduler shift 5, while 4DAnyone-Base uses 50 steps, serving as an upper-bound quality reference for our method.

| Model | Denoising steps | PSNR ↑ | SSIM ↑ | LPIPS ↓ |
| --- | ---: | ---: | ---: | ---: |
| 4DAnyone-Turbo | 4 | 25.48 | 0.895 | **0.072** |
| 4DAnyone-Base | 50 | **25.69** | **0.899** | 0.073 |

The two models achieve comparable quality across PSNR, SSIM, and LPIPS.

## Denoising performance

We measure 4DAnyone-Turbo with 4 denoising steps and 4DAnyone-Base with 24 steps on the [6-view full-orbit](../README.md#6-view-full-orbit) example:

```bash
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 6
```

Each reported denoising time is the median of three complete runs from the same source revision.

These tables compare denoising time across attention backends for both models.

- `SDPA`, `FlashAttention-3`, and `SageAttention`: denoising time using each attention backend.
- `Peak CUDA allocated`: maximum live tensor allocation across all runs and available attention backends.
- `GPU memory`: total device memory capacity.
- `—`: backend unavailable on that GPU.

### 4DAnyone-Turbo

| GPU | SDPA (min) | FlashAttention-3 (min) | SageAttention (min) | Peak CUDA allocated (GiB) | GPU memory (GiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| H200 | 0.98 | 0.77 | 0.78 | 26.63 | 139.81 |
| H20-3E | 3.22 | 2.55 | 2.10 | 26.63 | 139.81 |
| RTX 5880 Ada | 3.51 | — | 3.04 | 25.47 | 47.37 |
| RTX A6000 | 3.80 | — | 3.71 | 24.91 | 47.53 |

### 4DAnyone-Base

| GPU | SDPA (min) | FlashAttention-3 (min) | SageAttention (min) | Peak CUDA allocated (GiB) | GPU memory (GiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| H200 | 5.35 | 4.03 | 4.09 | 26.63 | 139.81 |
| H20-3E | 18.71 | 14.73 | 11.98 | 26.63 | 139.81 |
| RTX 5880 Ada | 20.40 | — | 17.58 | 25.47 | 47.37 |
| RTX A6000 | 22.02 | — | 21.42 | 24.91 | 47.53 |

### Speedup

Speedup is calculated by dividing the 4DAnyone-Base median by the 4DAnyone-Turbo median for the same GPU and attention backend.

| GPU | SDPA | FlashAttention-3 | SageAttention |
| --- | ---: | ---: | ---: |
| H200 | 5.45× | 5.26× | 5.23× |
| H20-3E | 5.81× | 5.78× | 5.69× |
| RTX 5880 Ada | 5.81× | — | 5.79× |
| RTX A6000 | 5.79× | — | 5.77× |

> [!NOTE]
> SageAttention results use the official `sageattn` entry point, which automatically dispatches an architecture-specific kernel for each GPU.

## Preprocessing performance

Preprocessing is identical for both models and therefore reported once.

- `GVHMR`: tracking, ViTPose, image-feature extraction, and motion prediction.
- `Skeleton extraction`: target-view skeleton-condition rendering.

| GPU | GVHMR (min) | Skeleton extraction (min) |
| --- | ---: | ---: |
| H200 | 0.94 | 0.57 |
| H20-3E | 0.97 | 0.55 |
| RTX 5880 Ada | 0.94 | 1.00 |
| RTX A6000 | 1.70 | 1.06 |
