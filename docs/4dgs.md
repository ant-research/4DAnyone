# 4D Gaussian reconstruction

Reconstruct a dynamic Gaussian scene from a 4DAnyone result, then render a 360°
orbit video or explore it in the browser.

## Install

Install the following dependencies in the `4danyone` environment:

```bash
pip install --no-build-isolation -r requirements-4dgs.txt
```

## Usage

Train a 4DGS model using the 4DAnyone inference results:

```bash
python reconstruct.py \
    --data_dir "data/4danyone/pexels/10331522-uhd_2160_4096_25fps" \
    --output_dir "data/4dgs/pexels/10331522-uhd_2160_4096_25fps"
```

After training, the following outputs are available:

```text
data/4dgs/pexels/10331522-uhd_2160_4096_25fps/
├── render/
│   ├── rgb.mp4          # 360° orbit video
│   ├── alpha/           # per-frame alpha masks
│   ├── trajectory.json  # rendered camera poses and timestamps
│   └── render.json      # rendering metadata
├── checkpoints/
│   ├── latest.pt        # resume training
│   └── latest.npz       # render or view
├── data/                # prepared training data
│   ├── images/          # decoded training views
│   ├── fmasks/          # foreground masks
│   ├── cameras.json     # camera calibration
│   └── metadata.json    # frame IDs and frame rate
├── initialization/      # carved points (.npy) and metadata.json
├── run.json             # source and recipe identity for resume
├── config.json          # saved training configuration
└── train.jsonl          # training losses, point counts and timings
```

## Interactive viewer

Load the trained NPZ model:

```bash
python reconstruct.py view \
    --model "data/4dgs/pexels/10331522-uhd_2160_4096_25fps/checkpoints/latest.npz"
```

Open **http://127.0.0.1:7861/** and select a scene.
To view another model, run the command in another terminal. Ctrl+C closes that scene.

For a remote GPU server, forward the port first:

```bash
ssh -N -L 7861:127.0.0.1:7861 <gpu-server>
```

<table>
  <tr>
    <td align="center" width="33%"><strong>Wusan 2</strong><br><video src="https://github.com/user-attachments/assets/c37f73ba-d402-4337-b6b9-c366c30c272c" width="240" controls muted></video><br><a href="https://huggingface.co/AntResearch/4DAnyone/resolve/main/data/4dgs/examples/wusan-2.npz?download=true">Download NPZ</a></td>
    <td align="center" width="33%"><strong>Pexels Fashion</strong><br><video src="https://github.com/user-attachments/assets/d3d971dd-77db-4c02-941b-33c11a3b1354" width="240" controls muted></video><br><a href="https://huggingface.co/AntResearch/4DAnyone/resolve/main/data/4dgs/examples/pexels-fashion.npz?download=true">Download NPZ</a></td>
    <td align="center" width="33%"><strong>Zhang Weili</strong><br><video src="https://github.com/user-attachments/assets/528fc72d-9093-4600-b922-97320dd14018" width="240" controls muted></video><br><a href="https://huggingface.co/AntResearch/4DAnyone/resolve/main/data/4dgs/examples/zhang-weili.npz?download=true">Download NPZ</a></td>
  </tr>
  <tr>
    <td align="center" width="33%"><strong>Chris</strong><br><video src="https://github.com/user-attachments/assets/d97c65d8-d554-413c-9bc9-2b5447645135" width="240" controls muted></video><br><a href="https://huggingface.co/AntResearch/4DAnyone/resolve/main/data/4dgs/examples/chris.npz?download=true">Download NPZ</a></td>
    <td align="center" width="33%"><strong>EngineAI T800</strong><br><video src="https://github.com/user-attachments/assets/0d3df05a-95d3-4b1e-af30-800c88ed3118" width="240" controls muted></video><br><a href="https://huggingface.co/AntResearch/4DAnyone/resolve/main/data/4dgs/examples/engineai-t800.npz?download=true">Download NPZ</a></td>
    <td align="center" width="33%"><strong>RobotAmu</strong><br><video src="https://github.com/user-attachments/assets/ffd6963d-b2c4-46de-8798-4077e36c1631" width="240" controls muted></video><br><a href="https://huggingface.co/AntResearch/4DAnyone/resolve/main/data/4dgs/examples/robotamu.npz?download=true">Download NPZ</a></td>
  </tr>
</table>

> [!NOTE]
> This implementation is based on [Fudan 4DGS](https://github.com/LogosIntelligenceLab/4d-gaussian-splatting) and [EasyVolcap](https://github.com/zju3dv/EasyVolcap).
> Its visual quality and training speed do not yet match the FreeTimeGS results reported in the paper.

## Options

### Training

For all training options, run `python reconstruct.py --help`.

| Argument | Default | Description |
| --- | --- | --- |
| `--resume` | `True` | Continue interrupted work or return if complete. `False` replaces reconstruction products and restarts with supplied options and default settings. |
| `--steps` | `100000` | Total training steps; densification ends halfway through. |
| `--batch_size` | `4` | Lower to reduce GPU memory usage. |
| `--image_scale` | `1.0` | Training resolution scale. |
| `--perceptual_weight` | `0.5` | VGG feature loss weight; `0` disables it. |
| `--perceptual_start_step` | `75000` | Step at which VGG loss starts. |

### Rendering

Render another video from a trained model:

```bash
python reconstruct.py render \
    --model "data/4dgs/pexels/10331522-uhd_2160_4096_25fps/checkpoints/latest.npz" \
    --output "<render_output_dir>"
```

For all rendering options, run `python reconstruct.py render --help`.

| Argument | Default | Description |
| --- | --- | --- |
| `--background` | `black` | Background color: `black`, `white` or `gray`. |
| `--time` | `None` | Animate by default; set a time in seconds to freeze at the nearest trained timestamp. |

### Viewer

For all viewer options, run `python reconstruct.py view --help`.

| Argument | Default | Description |
| --- | --- | --- |
| `--port` | `7861` | Shared port for independently launched viewers. |
| `--device` | `cuda` | Rendering device, such as `cuda:1`. |
| `--max_fps` | `30` | Maximum playback frame rate. |
