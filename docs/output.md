# Output

With the default `--data_dir data`, each inference run writes:

```text
data/
├── gvhmr/results/<clip>/
│   ├── motion.json
│   └── motion.safetensors
└── fdanyone/<clip>/
    ├── metadata.json
    ├── cameras.json
    ├── skeletons/00.mp4 ... <N-1>.mp4
    └── videos/
        ├── sparse/*.mp4                 # RCP proposal views, when used
        └── dense/00.mp4 ... <N-1>.mp4  # final target views
```

`<clip>` is the input filename without its extension, and `N` is the number of target views.

## Files

- `videos/dense/` contains the generated target-view videos.
- `videos/sparse/` contains intermediate proposal views for larger camera layouts.
- `skeletons/` contains pose-conditioning videos aligned with the target views.
- `cameras.json` contains camera intrinsics and poses for every target view.
- `metadata.json` records the input, generation settings, model versions, timings, and worker metrics when target denoising uses multiple GPUs.
- `gvhmr/results/` caches the recovered input motion for reuse.

All output videos contain 121 frames at 704×1280, use the selected output FPS, and contain no audio.

## Nerfstudio export

See the [3DGS reconstruction guide](nerfstudio.md) for details.
