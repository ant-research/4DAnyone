"""Direct, registry-free loading of the frozen Wan/SpaTem inference stack."""

from __future__ import annotations

import gc
from dataclasses import dataclass
from pathlib import Path

from fdanyone.assets import BaseAssets
from fdanyone.config import INFERENCE
from fdanyone.errors import AssetError, ConfigurationError

WAN22_TI2V_5B_CONFIG = {
    "has_image_input": False,
    "patch_size": (1, 2, 2),
    "in_dim": 48,
    "dim": 3072,
    "ffn_dim": 14336,
    "freq_dim": 256,
    "text_dim": 4096,
    "out_dim": 48,
    "num_heads": 24,
    "num_layers": 30,
    "eps": 1e-6,
    "seperated_timestep": True,
    "require_clip_embedding": False,
    "require_vae_embedding": False,
    "fuse_vae_embedding_in_latents": True,
}


@dataclass
class LoadedPipeline:
    pipe: object

    def release_text_encoder(self) -> None:
        """Release T5 after the single fixed prompt has been encoded."""

        import torch

        self.pipe.text_encoder = None
        self.pipe.prompter.text_encoder = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def _load_checkpoint(path: Path):
    try:
        from safetensors.torch import load_file
    except ImportError as exc:
        raise AssetError("safetensors is required to load the 4DAnyone checkpoint.") from exc
    return load_file(str(path), device="cpu")


def _strict_assign(module, state_dict: dict, label: str) -> None:
    """Load into a meta-initialized module without a second parameter copy."""

    try:
        incompatible = module.load_state_dict(state_dict, strict=True, assign=True)
    except TypeError as exc:
        raise ConfigurationError("4DAnyone requires PyTorch >=2.8 for assign-based model loading.") from exc
    except RuntimeError as exc:
        raise AssetError(f"{label} is incompatible with the released architecture: {exc}") from exc
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise AssetError(
            f"{label} strict load failed; missing={incompatible.missing_keys}, "
            f"unexpected={incompatible.unexpected_keys}"
        )


def _load_dit(checkpoint_path: Path, dtype):
    import torch

    from fdanyone.vendor.diffsynth.models.wan_video_dit import WanModel, precompute_freqs_cis_3d
    from fdanyone.vendor.diffsynth.pipelines.wan_video_spatem import WanVideoSpaTemPipeline

    with torch.device("meta"):
        dit = WanModel(**WAN22_TI2V_5B_CONFIG)
        shell = WanVideoSpaTemPipeline(device="cpu", torch_dtype=dtype)
        shell.dit = dit
        shell.init_spatem_modules(
            disable_video_attn=INFERENCE.disable_video_attention,
            use_4d_attn=INFERENCE.use_4d_attention,
            use_mvs_attn=INFERENCE.use_mvs_attention,
            use_src_self_attn=INFERENCE.use_source_self_attention,
            use_src_cross_attn=INFERENCE.use_source_cross_attention,
            freqs_src_shift=INFERENCE.freqs_src_shift,
            range_mvs_attn=INFERENCE.mvs_attention_range,
            # ``ViewPack`` is the upstream module name for RCP references.
            use_viewpack=True,
            use_pose_encoder=INFERENCE.use_pose_encoder,
            pose_encoder_type=INFERENCE.pose_encoder_type,
            use_cam_encoder=INFERENCE.use_camera_encoder,
            use_lbm=INFERENCE.use_lbm,
        )
    state_dict = _load_checkpoint(checkpoint_path)
    _strict_assign(dit, state_dict, "4DAnyone DiT checkpoint")
    del state_dict
    # ``freqs`` is a derived, non-persistent tensor and therefore is not in the
    # state dict populated above.
    dit.freqs = precompute_freqs_cis_3d(WAN22_TI2V_5B_CONFIG["dim"] // WAN22_TI2V_5B_CONFIG["num_heads"])
    return dit.eval().requires_grad_(False)


def _load_vae(path: Path, dtype):
    import torch

    from fdanyone.vendor.diffsynth.models.wan_video_vae import WanVideoVAE38

    state_dict = torch.load(path, map_location="cpu", weights_only=True)
    state_dict = WanVideoVAE38.state_dict_converter().from_civitai(state_dict)
    with torch.device("meta"):
        vae = WanVideoVAE38()
    _strict_assign(vae, state_dict, "Wan2.2 VAE")
    del state_dict
    # Wan's latent normalization tensors are plain attributes rather than
    # registered buffers, so materialize them after meta initialization.
    mean = (
        -0.2289,
        -0.0052,
        -0.1323,
        -0.2339,
        -0.2799,
        0.0174,
        0.1838,
        0.1557,
        -0.1382,
        0.0542,
        0.2813,
        0.0891,
        0.1570,
        -0.0098,
        0.0375,
        -0.1825,
        -0.2246,
        -0.1207,
        -0.0698,
        0.5109,
        0.2665,
        -0.2108,
        -0.2158,
        0.2502,
        -0.2055,
        -0.0322,
        0.1109,
        0.1567,
        -0.0729,
        0.0899,
        -0.2799,
        -0.1230,
        -0.0313,
        -0.1649,
        0.0117,
        0.0723,
        -0.2839,
        -0.2083,
        -0.0520,
        0.3748,
        0.0152,
        0.1957,
        0.1433,
        -0.2944,
        0.3573,
        -0.0548,
        -0.1681,
        -0.0667,
    )
    std = (
        0.4765,
        1.0364,
        0.4514,
        1.1677,
        0.5313,
        0.4990,
        0.4818,
        0.5013,
        0.8158,
        1.0344,
        0.5894,
        1.0901,
        0.6885,
        0.6165,
        0.8454,
        0.4978,
        0.5759,
        0.3523,
        0.7135,
        0.6804,
        0.5833,
        1.4146,
        0.8986,
        0.5659,
        0.7069,
        0.5338,
        0.4889,
        0.4917,
        0.4069,
        0.4999,
        0.6866,
        0.4093,
        0.5709,
        0.6065,
        0.6415,
        0.4944,
        0.5726,
        1.2042,
        0.5458,
        1.6887,
        0.3971,
        1.0600,
        0.3943,
        0.5537,
        0.5444,
        0.4089,
        0.7468,
        0.7744,
    )
    vae.mean = torch.tensor(mean)
    vae.std = torch.tensor(std)
    vae.scale = [vae.mean, 1.0 / vae.std]
    return vae.to(dtype=dtype).eval().requires_grad_(False)


def _load_text_encoder(path: Path, dtype):
    import torch

    from fdanyone.vendor.diffsynth.models.wan_video_text_encoder import WanTextEncoder

    state_dict = torch.load(path, map_location="cpu", weights_only=True)
    state_dict = WanTextEncoder.state_dict_converter().from_civitai(state_dict)
    with torch.device("meta"):
        text_encoder = WanTextEncoder()
    _strict_assign(text_encoder, state_dict, "Wan T5 text encoder")
    del state_dict
    return text_encoder.to(dtype=dtype).eval().requires_grad_(False)


def load_pipeline(
    *,
    checkpoint_path: str | Path,
    assets: BaseAssets,
    device: str,
) -> LoadedPipeline:
    """Load exactly the runtime models required by the released checkpoint."""

    import torch

    from fdanyone.vendor.diffsynth.pipelines.wan_video_spatem import WanVideoSpaTemPipeline

    dtype = torch.bfloat16
    pipe = WanVideoSpaTemPipeline(device=device, torch_dtype=dtype, tokenizer_path=str(assets.tokenizer))
    pipe.dit = _load_dit(Path(checkpoint_path), dtype)
    pipe.vae = _load_vae(assets.vae, dtype)
    pipe.text_encoder = _load_text_encoder(assets.text_encoder, dtype)
    pipe.prompter.fetch_models(pipe.text_encoder)
    pipe.height_division_factor = pipe.vae.upsampling_factor * 2
    pipe.width_division_factor = pipe.vae.upsampling_factor * 2
    return LoadedPipeline(pipe=pipe)


def load_denoiser(*, checkpoint_path: str | Path, device: str):
    """Load the DiT and scheduler required by one distributed worker."""

    import torch

    from fdanyone.vendor.diffsynth.pipelines.wan_video_spatem import WanVideoSpaTemPipeline

    dtype = torch.bfloat16
    pipe = WanVideoSpaTemPipeline(device=device, torch_dtype=dtype)
    pipe.dit = _load_dit(Path(checkpoint_path), dtype)
    return pipe
