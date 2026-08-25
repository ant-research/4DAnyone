# Third-party notices

The root Apache-2.0 license applies only to first-party 4DAnyone code. The following components and assets retain their own terms.

## GVHMR

- Upstream source: <https://github.com/zju3dv/GVHMR>
- Pinned upstream revision: `6ec3ca39336c50492c0fae65fba2fb831fc7d866`
- Location: `third_party/GVHMR`
- License: `third_party/GVHMR/LICENSE`

4DAnyone uses the official upstream source without a GVHMR source patch. The pinned revision is immutable and can be fetched anonymously from the upstream repository.

GVHMR, HMR2, ViTPose, YOLO, SMPL, and SMPL-X model files are not bundled in 4DAnyone. The complete public inference closure is anchored by the immutable Hugging Face revision frozen in `fdanyone/assets.py`. Users obtain those files through the applicable upstream or licensed setup flows.

GVHMR permits use, copying, modification, and distribution for educational, research, and non-profit purposes only. It requires modifications based on the work to be open source and prohibits commercial use. Its checkpoints and transitive model assets may have additional terms.

## BiRefNet

- Upstream source and model: <https://huggingface.co/ZhengPeng7/BiRefNet>
- Pinned model revision: `e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4`
- Upstream code: <https://github.com/ZhengPeng7/BiRefNet>
- License: MIT, copied at `third_party/licenses/BIREFNET_LICENSE`

The adaptive preprocessing path downloads the pinned BiRefNet configuration, inference source, and weights on demand. It uses the resulting foreground masks for source cropping and source-framing analysis. Those downloaded files retain their upstream terms.

## PyTorch3D compatibility subset

- Upstream source: <https://github.com/facebookresearch/pytorch3d>
- Upstream revision: `f34104cf6ebefacd7b7e07955ee7aaa823e616ac`
- Location: `fdanyone/vendor/pytorch3d_compat`
- License: BSD 3-Clause, copied at `fdanyone/vendor/pytorch3d_compat/LICENSE`

Classic GVHMR imports PyTorch3D rotation conversions through a broader training-time module surface. 4DAnyone retains the two upstream source files needed by inference, plus small first-party module aliases and a native PyTorch fallback for an imported optional KNN helper. The renderer and compiled PyTorch3D operators are not included or required. `UPSTREAM.md` and `VENDORED_FILES.txt` record the exact retained closure and source hashes.

## Pexels example media

- Source platform: <https://www.pexels.com/>
- Location: `data/source/pexels`
- Terms: <https://www.pexels.com/license/>

The companion Hugging Face repository distributes eight modified 121-frame excerpts for running the public demo. They are installed under the location above on demand. The excerpts derive from Pexels videos [10331522](https://www.pexels.com/video/10331522/), [2785536](https://www.pexels.com/video/2785536/), [5435720](https://www.pexels.com/video/5435720/), [5885633](https://www.pexels.com/video/5885633/), [5999210](https://www.pexels.com/video/5999210/), [6980035](https://www.pexels.com/video/6980035/), [7080903](https://www.pexels.com/video/7080903/), and [7480858](https://www.pexels.com/video/7480858/). Pexels permits its media to be used and modified for free and does not require attribution. The source links are retained for provenance and creator credit.

## DiffSynth-Studio inference runtime

- Public source: <https://github.com/modelscope/DiffSynth-Studio>
- Public base revision: `04e39f7de53df7276a7b40ca1791c2a393e05ff3`
- Original experiment fork revision: `c00782d90c872c97bda4745a9e6a41a0a4a7c4db`
- Location: `fdanyone/vendor/diffsynth`
- License: Apache-2.0, copied at `fdanyone/vendor/diffsynth/LICENSE`

`UPSTREAM.md`, `UPSTREAM.patch`, and `VENDORED_FILES.txt` in that directory record the exact provenance, research patch, and retained file set.

Two retained DiffSynth files carry code-level upstream attribution:

- `models/wan_video_pose_encoder.py` derives its pose network from [Tencent/MimicMotion](https://github.com/Tencent/MimicMotion/tree/c053153a1d124abae8c08568925ae88debc63001), Copyright Tencent, under Apache-2.0.
- `models/wan_video_camera_controller.py` contains camera-coordinate helpers from [hehao13/CameraCtrl](https://github.com/hehao13/CameraCtrl), under Apache-2.0. The exact retained bytes remain identified through the DiffSynth public-base revision above.

## Sapiens2-derived Goliath/MHR schema material

- Source project: <https://github.com/facebookresearch/sapiens2>
- Source revision: `0e51c12d7c7257d88431b2d50e523a7b03004854`
- Source file: `sapiens/pose/configs/_base_/keypoints308.py`
- Retained material: the exact MHR70 name/order and Goliath40 link closure needed to reproduce model conditioning
- First-party Apache-2.0 material: RGB palette, color assignment policy, and renderer implementation in `fdanyone/skeleton`
- License copy: `third_party/licenses/SAPIENS2_LICENSE.md`

No Sapiens2 model weights are distributed by this repository.

The retained schema material is conservatively treated as Sapiens2-derived and the complete agreement is included rather than assuming that the root Apache-2.0 license applies. The agreement contains explicit prohibited-use terms, including surveillance, biometric processing, identification or re-identification, deepfakes or deceptive content, and the other activities listed in section 1(b)(vi).

## Model and body assets

The 4DAnyone checkpoint and sanitized MHR70 sparse regression tensors are first-party release artifacts licensed under Apache-2.0, published at the Hugging Face revision frozen in `fdanyone/assets.py`. The regressor file also embeds the exact keypoint-name order required to interpret those tensors. That schema material retains the Sapiens2 notice above and is not relicensed by the tensor license. Wan VAE/T5/tokenizer, GVHMR checkpoints, HMR2, ViTPose, detector weights, and SMPL-X body models remain third-party assets. The redistributable files are mirrored by the companion Hugging Face repository. Users obtain SMPL-X from its official site and remain responsible for every applicable license.

The frozen base-model assets come from the official [Wan2.2-TI2V-5B](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) repository at revision `37685f96025fc1425edccdd4b2bca3836ae917ff` and the official [Wan2.1-T2V-1.3B](https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B) repository at revision `3f40b6dc4ca5c02dd23c9db74d9d2ccb82903b86`. Their official model cards license those model assets under Apache-2.0. The redistributed copies are pinned by the frozen Hugging Face revision.

The MHR70 asset is a sanitized inference artifact containing only the sparse support/weight tensors, keypoint names, and a path-free structural schema. The first-party regression tensors are redistributed under Apache-2.0. The embedded name/order metadata remains covered by the schema notice above.

That regressor was trained by the 4DAnyone project on DNA-Rendering frames, using outputs from [SAM 3D Body](https://github.com/facebookresearch/sam-3d-body) and the [Momentum Human Rig](https://github.com/facebookresearch/MHR) conversion tools. SAM 3D Body is governed by the SAM License, MHR source is Apache-2.0, and DNA-Rendering access requires a separate signed dataset agreement. The regressor is not bundled in the source repository. Its Hugging Face model card must retain these source-model and dataset citations alongside the split tensor/schema license declaration in this notice.

## VGG-19 perceptual reconstruction

- Loss reference: [Crowdsampling the Plenoptic Function](https://github.com/zhengqili/Crowdsampling-the-Plenoptic-Function/tree/f5216f312cf82d77f8d20454b5eeb3930324630a), released under MIT in its upstream README
- VGG-19 model: [Oxford Visual Geometry Group](https://www.robots.ox.ac.uk/~vgg/research/very_deep/)
- MatConvNet distribution: [imagenet-vgg-verydeep-19](https://www.vlfeat.org/matconvnet/pretrained/), source MD5 `106118b7cf60435e6d8e04f6a6dc3657`
- Model license: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)

The optional `splatfacto-perceptual` method uses a custom pixel-plus-feature objective rather than standard LPIPS. The companion Hugging Face repository contains a modified copy of the VGG-19 model: MatConvNet filters are transposed into PyTorch layout and serialized as safetensors, while the unused classifier and final two convolution layers are omitted. The retained tensor values are otherwise unchanged. Credit remains with Karen Simonyan and Andrew Zisserman. Users must preserve that attribution and the CC BY 4.0 license when redistributing the converted weights.
