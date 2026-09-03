<p align="center"><a href="https://4danyone.github.io/"><img src="docs/assets/logo_title.png" width="300" alt="4DAnyone"></a></p>

<h2 align="center">4DAnyone: Create Anyone in 4D from a Casual Monocular Video</h2>

<p align="center"><a href="https://4danyone.github.io/"><strong>Project Page</strong></a> &nbsp;|&nbsp; <a href="https://arxiv.org/abs/2608.20335"><strong>Paper</strong></a></p>

<p align="center"><img src="docs/assets/teaser.gif" width="100%" alt="4DAnyone teaser"></p>

<p align="center">4DAnyone turns a casual monocular video into multi-view videos, enabling downstream 4DGS reconstruction.</p>

## News

- **2026-09-02**: Released **4DAnyone-Turbo**, achieving a **5.58×** denoising speedup over the base 4DAnyone model. See [Inference performance](docs/inference_performance.md) for details.
- **2026-08-28**: Achieved a **1.42×** end-to-end speedup for the complete 24-view generation pipeline.
- **2026-08-28**: Reduced peak GPU memory to **25.4 GiB** while slightly improving speed.

## Installation

```bash
git clone https://github.com/ant-research/4DAnyone.git
cd 4DAnyone
git submodule update --init third_party/GVHMR

conda create -n 4danyone python=3.11 -y
conda activate 4danyone
pip install -r requirements.txt
```

Missing models and examples are downloaded automatically on first use. You can also download them manually:

```bash
python scripts/download_smplx.py
python scripts/download_model.py
python scripts/download_example.py
```

## Inference

We provide two models: **4DAnyone-Turbo** for faster four-step denoising and **4DAnyone-Base** with the standard denoising schedule. Both models achieve comparable generation quality. 4DAnyone-Turbo is enabled by default. Set `--enable_turbo=False` to use 4DAnyone-Base.

4DAnyone supports flexible target-view counts, pitch layers, and yaw coverage. Here are several common camera configurations:

### 6-View Full Orbit

A compact 360° layout for basic coverage. Start here for an initial test.

```bash
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 6
```

<p align="left"><img src="docs/assets/inference-6-views.jpg" width="600" alt="Six evenly spaced target cameras on one full orbit"></p>

### 24-View Full Orbit

A dense 360° layout with broad angular coverage, suitable for 4DGS reconstruction.

```bash
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 24
```

<p align="left"><img src="docs/assets/inference-24-views.jpg" width="600" alt="Twenty-four evenly spaced target cameras on one full orbit"></p>

### 48-View Full Orbit, Three Pitch Layers

This layout distributes views across three pitch rings for broader coverage, enabling free-viewpoint 4DGS rendering.

```bash
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 16 --layer_pitches '[-10,15,35]'
```

<p align="left"><img src="docs/assets/inference-48-views-3-layers.jpg" width="600" alt="Forty-eight target cameras arranged over three pitch layers"></p>

### 24-View Frontal Arc, Two Pitch Layers

A two-layer layout for dense coverage across the frontal 180° arc.

```bash
python inference.py \
    --video_path "data/source/pexels/2785536-uhd_2160_3840_25fps.mp4" \
    --views_per_layer 12 --layer_pitches '[0,30]' --start_yaw -90 --yaw_span 180
```

<p align="left"><img src="docs/assets/inference-24-views-front-180.jpg" width="600" alt="Twenty-four target cameras distributed over two pitch layers along the frontal 180-degree arc"></p>

### Key Arguments

Run `python inference.py --help` for the full list.

- `views_per_layer`: number of evenly spaced views per pitch layer. It must be divisible by 4 or 6.
- `layer_pitches`: pitch angles in degrees, one per layer. Positive values place cameras above the subject. Total views are `views_per_layer × len(layer_pitches)`.
- `start_yaw`: horizontal angle of the first view, in degrees. Yaw `0` is the front view.
- `yaw_span`: horizontal range covered by each camera layer, in degrees.
- `gpu_ids`: GPU IDs used for parallel pose/VAE view stages and target denoising. Defaults to all visible GPUs.
- `enable_turbo`: whether to use 4DAnyone-Turbo. Enabled by default.

### Output

With the default `--data_dir data`, results follow this layout. See the [output documentation](docs/output.md) for the complete format.

```text
data/
├── gvhmr/results/<clip>/          # reusable motion-recovery result
└── fdanyone/<clip>/
    ├── metadata.json              # run settings, timings, resources
    ├── cameras.json               # the final N-camera rig
    ├── skeletons/00.mp4 ... <N-1>.mp4
    └── videos/
        ├── sparse/{00,04,09,12,14,19}.mp4  # default 24-view RCP proposals
        └── dense/00.mp4 ... <N-1>.mp4       # generated target views
```

### Inference Efficiency

For faster inference on supported GPUs, optionally install [FlashAttention-3](https://github.com/Dao-AILab/flash-attention/tree/main/hopper) or [SageAttention](https://github.com/thu-ml/SageAttention). Runtime selection follows one fixed order: FlashAttention-3, SageAttention, then PyTorch SDPA.

See [Inference performance](docs/inference_performance.md) for measured 6-view runtimes and peak GPU memory usage on H20-3E, H200, RTX 5880 Ada, and RTX A6000 GPUs.

### Custom Data

Use an input video that:

- is 720p or higher, with 1080p recommended.
- uses a 9:16 portrait aspect ratio.
- shows one person in a full-body or upper-body shot.
- has at least 121 frames.
- contains only mild camera motion.

## 3DGS Reconstruction

See the [nerfstudio guide](docs/nerfstudio.md) for details.

## Roadmap

### Peak Memory Optimization

- [x] Reduce peak GPU memory below 32 GB through pose precomputation and memory-efficient operators.

### Inference Acceleration

- [x] Achieve up to 1.42× end-to-end speedup by parallelizing pose encoding and VAE processing across GPUs.
- [x] Achieve a **5.58×** denoising speedup with 4DAnyone-Turbo.

### Reconstruction

- [x] Support 3DGS reconstruction with nerfstudio.
- [ ] Support 4DGS reconstruction with an open-source method.

## Citation

If you find 4DAnyone useful or interesting, please cite our work and consider giving the repository a star ⭐:

```bibtex
@article{jin2026fdanyone,
  title={4DAnyone: Create Anyone in 4D from a Casual Monocular Video},
  author={Jin, Yudong and Xie, Tao and Zhang, Qihang and Shen, Zehong and Xu, Zhen and Shen, Yujun and Bao, Hujun and Zhou, Xiaowei and Xu, Yinghao},
  journal={arXiv preprint arXiv:2608.20335},
  year={2026},
  url={https://arxiv.org/abs/2608.20335}
}
```
