# 3DGS reconstruction with Nerfstudio

Export one synchronized multi-view frame from 4DAnyone and reconstruct it as a 3D Gaussian Splatting (3DGS) scene with Nerfstudio Splatfacto.

## Installation

Install Nerfstudio in a new environment by following the [official installation guide](https://docs.nerf.studio/quickstart/installation.html), then install:

```bash
pip install huggingface-hub safetensors
```

## Export

Run the exporter in the 4DAnyone inference environment:

```bash
conda activate 4danyone
python scripts/export_nerfstudio.py \
    --data_dir data/fdanyone/pexels/2785536-uhd_2160_3840_25fps \
    --output_dir data/ns_data/pexels/2785536-uhd_2160_3840_25fps/frame_000 \
    --frame_index 0
```

The exported Nerfstudio data is written to:

```bash
data/ns_data/pexels/<clip>/frame_000/
├── transforms.json
├── sparse_pcd.ply                 # visual-hull initialization
├── images/00.png ... <N-1>.png
└── masks/00.png ... <N-1>.png
```

## Train

Standard Splatfacto:

```bash
ns-train splatfacto \
    --data data/ns_data/pexels/2785536-uhd_2160_3840_25fps/frame_000 \
    --output-dir data/ns_outputs/pexels/2785536-uhd_2160_3840_25fps/frame_000 \
    --pipeline.model.background-color random
```

Splatfacto with perceptual loss:

```bash
python scripts/train_nerfstudio.py splatfacto-perceptual \
    --data data/ns_data/pexels/2785536-uhd_2160_3840_25fps/frame_000 \
    --output-dir data/ns_outputs/pexels/2785536-uhd_2160_3840_25fps/frame_000 \
    --pipeline.model.background-color random \
    --pipeline.model.perceptual-loss-weight 0.4 \
    --pipeline.model.perceptual-compute-dtype bfloat16
```

If the GPU supports `bfloat16`, we recommend enabling it to accelerate training.

## View

Launch the viewer with the config path printed by training:

```bash
python scripts/view_nerfstudio.py \
    --load-config <training-output>/config.yml \
    --viewer.websocket-port 7007
```

For a remote viewer, forward the same port from the workstation:

```bash
ssh -N -L 7007:127.0.0.1:7007 <server>
```

Example 3DGS reconstruction in the Nerfstudio viewer:

![Example 3DGS reconstruction in the Nerfstudio viewer](assets/nerfstudio-example.jpg)

> [!note]
> This guide reconstructs a static 3DGS from a single synchronized timestamp and cannot reproduce the 4DGS results shown in our work.
>
> The FreeTimeGS implementation used in the paper is not publicly available. We are evaluating open-source alternatives for a reproducible 4DGS pipeline.
