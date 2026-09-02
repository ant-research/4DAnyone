# Inference performance

This page reports matched inference efficiency for the default Wan2.2 5B Turbo LoRA and the unfused base model on the [6-view full-orbit](../README.md#6-view-full-orbit) example:

```bash
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 6
```

The command above uses Turbo by default. Add `--enable_turbo=False` to run the base model. Each denoising configuration below is the median of three complete runs from the same source revision.

## Denoising

These tables compare denoising time across attention backends for the Turbo and base models.

- `SDPA`, `FlashAttention-3`, and `SageAttention`: denoising time using each attention backend.
- `Peak CUDA allocated`: maximum live tensor allocation observed across the three runs and available attention backends for each GPU and model profile.
- `GPU memory`: total device memory capacity.
- `—`: backend unavailable on that GPU.

### Turbo (default)

| GPU | SDPA (min) | FlashAttention-3 (min) | SageAttention (min) | Peak CUDA allocated (GiB) | GPU memory (GiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| H200 | 0.98 | 0.77 | 0.78 | 26.63 | 139.81 |
| H20-3E | 3.22 | 2.55 | 2.10 | 26.63 | 139.81 |
| RTX 5880 Ada | 3.51 | — | 3.04 | 25.47 | 47.37 |
| RTX A6000 | 3.80 | — | 3.71 | 24.91 | 47.53 |

### Base

| GPU | SDPA (min) | FlashAttention-3 (min) | SageAttention (min) | Peak CUDA allocated (GiB) | GPU memory (GiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| H200 | 5.35 | 4.03 | 4.09 | 26.63 | 139.81 |
| H20-3E | 18.71 | 14.73 | 11.98 | 26.63 | 139.81 |
| RTX 5880 Ada | 20.40 | — | 17.58 | 25.47 | 47.37 |
| RTX A6000 | 22.02 | — | 21.42 | 24.91 | 47.53 |

### Base / Turbo speedup

Each value divides the Base median by the Turbo median for the same GPU and attention backend.

| GPU | SDPA | FlashAttention-3 | SageAttention |
| --- | ---: | ---: | ---: |
| H200 | 5.45× | 5.26× | 5.23× |
| H20-3E | 5.81× | 5.78× | 5.69× |
| RTX 5880 Ada | 5.81× | — | 5.79× |
| RTX A6000 | 5.79× | — | 5.77× |

> [!NOTE]
> FlashAttention-3 is available on the tested SM90 GPUs and unavailable on RTX A6000 (SM86) and RTX 5880 Ada (SM89). SageAttention results use the official `sageattn` entry point, which dispatches an architecture-specific kernel.

## Preprocessing

Preprocessing is shared by Turbo and Base, so it is reported once. These profile-independent values are retained from the preceding release benchmark; this refresh remeasured the matched denoising path.

- `GVHMR`: tracking, ViTPose, image-feature extraction, and motion prediction.
- `Skeleton extraction`: target-view skeleton-condition rendering.

| GPU | GVHMR (min) | Skeleton extraction (min) |
| --- | ---: | ---: |
| H200 | 0.94 | 0.57 |
| H20-3E | 0.97 | 0.55 |
| RTX 5880 Ada | 0.94 | 1.00 |
| RTX A6000 | 1.70 | 1.06 |
