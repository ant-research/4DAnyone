"""Wan/SpaTem DiT graph used by the released 4DAnyone checkpoint.

This module intentionally contains one inference architecture. The public
method always uses video self-attention, layer-local multiview attention,
ViewPack source tokens, frozen text context, and precomputed RGB-pose features.
Training-only adapters and alternate Wan model families are outside the reader
runtime.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from einops import rearrange, repeat

try:
    import flash_attn_interface

    FLASH_ATTN_3_AVAILABLE = True
except (ImportError, OSError, RuntimeError):
    FLASH_ATTN_3_AVAILABLE = False

try:
    from sageattention import sageattn

    SAGE_ATTN_AVAILABLE = True
except (ImportError, OSError, RuntimeError):
    SAGE_ATTN_AVAILABLE = False


LATENT_CHANNELS = 48
MODEL_DIM = 3072
FFN_DIM = 14336
FREQUENCY_DIM = 256
TEXT_DIM = 4096
NUM_HEADS = 24
NUM_LAYERS = 30
PATCH_SIZE = (1, 2, 2)
NORM_EPSILON = 1e-6

# A converted FP64 chunk and its complex product coexist. Accounting for both
# gives the same one-view production chunk as the original 768 MiB
# single-allocation limit, while naming the actual temporary budget.
ROPE_TEMPORARY_BUDGET_BYTES = 1536 * 1024**2
ATTENTION_BACKEND_PRIORITY = ("flash_attn_3", "sageattention", "sdpa")


def get_attention_backend() -> str:
    """Return the implementation selected by the release auto policy."""

    availability = {
        "flash_attn_3": FLASH_ATTN_3_AVAILABLE,
        "sageattention": SAGE_ATTN_AVAILABLE,
        "sdpa": True,
    }
    return next(backend for backend in ATTENTION_BACKEND_PRIORITY if availability[backend])


def attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, num_heads: int) -> torch.Tensor:
    """Evaluate attention with the backend selected by the release policy."""

    backend = get_attention_backend()
    if backend == "flash_attn_3":
        q = rearrange(q, "b s (n d) -> b s n d", n=num_heads)
        k = rearrange(k, "b s (n d) -> b s n d", n=num_heads)
        v = rearrange(v, "b s (n d) -> b s n d", n=num_heads)
        output = flash_attn_interface.flash_attn_func(q, k, v)
        if isinstance(output, tuple):
            output = output[0]
        return rearrange(output, "b s n d -> b s (n d)", n=num_heads)
    q = rearrange(q, "b s (n d) -> b n s d", n=num_heads)
    k = rearrange(k, "b s (n d) -> b n s d", n=num_heads)
    v = rearrange(v, "b s (n d) -> b n s d", n=num_heads)
    output = sageattn(q, k, v) if backend == "sageattention" else F.scaled_dot_product_attention(q, k, v)
    return rearrange(output, "b n s d -> b s (n d)", n=num_heads)


def modulate(x: torch.Tensor, shift: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
    return x * (1 + scale) + shift


def sinusoidal_embedding_1d(dim: int, position: torch.Tensor) -> torch.Tensor:
    sinusoid = torch.outer(
        position.to(torch.float64),
        torch.pow(
            10000,
            -torch.arange(dim // 2, dtype=torch.float64, device=position.device).div(dim // 2),
        ),
    )
    return torch.cat([torch.cos(sinusoid), torch.sin(sinusoid)], dim=1).to(position.dtype)


def precompute_freqs_cis(dim: int, end: int = 1024, theta: float = 10000.0) -> torch.Tensor:
    frequencies = 1.0 / (theta ** (torch.arange(0, dim, 2)[: dim // 2].double() / dim))
    phases = torch.outer(torch.arange(end, device=frequencies.device), frequencies)
    return torch.polar(torch.ones_like(phases), phases)


def precompute_freqs_cis_3d(
    dim: int,
    end: int = 1024,
    theta: float = 10000.0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    return (
        precompute_freqs_cis(dim - 2 * (dim // 3), end, theta),
        precompute_freqs_cis(dim // 3, end, theta),
        precompute_freqs_cis(dim // 3, end, theta),
    )


def gelu_tanh(x: torch.Tensor) -> torch.Tensor:
    """Apply tanh-GELU while reusing its inference input buffer."""

    if torch.is_grad_enabled():
        return F.gelu(x, approximate="tanh")
    return torch.ops.aten.gelu_.default(x, approximate="tanh")


def _rotate_rope_chunk(chunk: torch.Tensor, freqs: torch.Tensor) -> torch.Tensor:
    complex_chunk = torch.view_as_complex(
        chunk.to(torch.float64).reshape(chunk.shape[0], chunk.shape[1], chunk.shape[2], -1, 2)
    )
    return torch.view_as_real(complex_chunk * freqs).reshape_as(chunk)


def rope_apply(x: torch.Tensor, freqs: torch.Tensor, num_heads: int) -> torch.Tensor:
    """Apply the checkpoint's FP64 RoPE with bounded temporary storage."""

    headed = rearrange(x, "b s (n d) -> b s n d", n=num_heads)
    fp64_bytes = headed[0].numel() * torch.empty((), dtype=torch.float64).element_size()
    temporary_bytes_per_batch = 2 * fp64_bytes
    batch_chunk = max(
        1,
        min(headed.shape[0], ROPE_TEMPORARY_BUDGET_BYTES // temporary_bytes_per_batch),
    )

    if torch.is_grad_enabled():
        chunks = []
        for start in range(0, headed.shape[0], batch_chunk):
            chunk = headed[start : start + batch_chunk]
            chunks.append(_rotate_rope_chunk(chunk, freqs).flatten(2).to(headed.dtype))
        return torch.cat(chunks, dim=0)

    output = torch.empty_like(headed)
    for start in range(0, headed.shape[0], batch_chunk):
        chunk = headed[start : start + batch_chunk]
        output[start : start + batch_chunk].copy_(_rotate_rope_chunk(chunk, freqs))
    return output.flatten(2)


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-5) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def _normalize_float(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.rsqrt(x.pow(2).mean(dim=-1, keepdim=True) + self.eps)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        dtype = x.dtype
        return self._normalize_float(x.float()).to(dtype) * self.weight


class SelfAttention(nn.Module):
    def __init__(self, dim: int, num_heads: int, eps: float = NORM_EPSILON) -> None:
        super().__init__()
        self.num_heads = num_heads
        self.q = nn.Linear(dim, dim)
        self.k = nn.Linear(dim, dim)
        self.v = nn.Linear(dim, dim)
        self.o = nn.Linear(dim, dim)
        self.norm_q = RMSNorm(dim, eps=eps)
        self.norm_k = RMSNorm(dim, eps=eps)

    def forward(self, x: torch.Tensor, freqs: torch.Tensor) -> torch.Tensor:
        q = self.norm_q(self.q(x))
        k = self.norm_k(self.k(x))
        v = self.v(x)
        q = rope_apply(q, freqs, self.num_heads)
        k = rope_apply(k, freqs, self.num_heads)
        return self.o(attention(q, k, v, self.num_heads))


class CrossAttention(nn.Module):
    def __init__(self, dim: int, num_heads: int, eps: float = NORM_EPSILON) -> None:
        super().__init__()
        self.num_heads = num_heads
        self.q = nn.Linear(dim, dim)
        self.k = nn.Linear(dim, dim)
        self.v = nn.Linear(dim, dim)
        self.o = nn.Linear(dim, dim)
        self.norm_q = RMSNorm(dim, eps=eps)
        self.norm_k = RMSNorm(dim, eps=eps)

    def forward(self, x: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        q = self.norm_q(self.q(x))
        k = self.norm_k(self.k(context))
        v = self.v(context)
        return self.o(attention(q, k, v, self.num_heads))


class DiTBlock(nn.Module):
    """One frozen video + multiview + prompt + FFN transformer block."""

    def __init__(self) -> None:
        super().__init__()
        self.self_attn = SelfAttention(MODEL_DIM, NUM_HEADS)
        self.cross_attn = CrossAttention(MODEL_DIM, NUM_HEADS)
        self.norm1 = nn.LayerNorm(MODEL_DIM, eps=NORM_EPSILON, elementwise_affine=False)
        self.norm2 = nn.LayerNorm(MODEL_DIM, eps=NORM_EPSILON, elementwise_affine=False)
        self.norm3 = nn.LayerNorm(MODEL_DIM, eps=NORM_EPSILON)
        self.ffn = nn.Sequential(
            nn.Linear(MODEL_DIM, FFN_DIM),
            nn.GELU(approximate="tanh"),
            nn.Linear(FFN_DIM, MODEL_DIM),
        )
        self.modulation = nn.Parameter(torch.randn(1, 6, MODEL_DIM) / MODEL_DIM**0.5)

        self.modulation_mvs = nn.Parameter(torch.randn(1, 3, MODEL_DIM) / MODEL_DIM**0.5)
        self.norm1_mvs = nn.LayerNorm(MODEL_DIM, eps=NORM_EPSILON, elementwise_affine=False)
        self.self_attn_mvs = SelfAttention(MODEL_DIM, NUM_HEADS)

    def _feed_forward(self, x: torch.Tensor) -> torch.Tensor:
        hidden = self.ffn[0](x)
        hidden = gelu_tanh(hidden)
        return self.ffn[2](hidden)

    def _multiview_attention(
        self,
        x: torch.Tensor,
        shift: torch.Tensor,
        scale: torch.Tensor,
        multiview_freqs: torch.Tensor,
        shape: tuple[int, int, int, int],
    ) -> torch.Tensor:
        views, frames, height, width = shape
        x = rearrange(
            modulate(self.norm1_mvs(x), shift, scale),
            "v (f h w) c -> f (v h w) c",
            v=views,
            f=frames,
            h=height,
            w=width,
        )
        x = self.self_attn_mvs(x, multiview_freqs)
        return rearrange(
            x,
            "f (v h w) c -> v (f h w) c",
            v=views,
            f=frames,
            h=height,
            w=width,
        )

    def forward(
        self,
        x: torch.Tensor,
        context: torch.Tensor,
        time_modulation: torch.Tensor,
        spatial_freqs: torch.Tensor,
        multiview_freqs: torch.Tensor,
        shape: tuple[int, int, int, int],
    ) -> torch.Tensor:
        shift_msa, scale_msa, gate_msa, shift_mlp, scale_mlp, gate_mlp = (
            self.modulation.to(dtype=time_modulation.dtype, device=time_modulation.device) + time_modulation
        ).chunk(6, dim=1)

        x = x + gate_msa * self.self_attn(modulate(self.norm1(x), shift_msa, scale_msa), spatial_freqs)

        shift_mvs, scale_mvs, gate_mvs = (
            self.modulation_mvs.to(dtype=time_modulation.dtype, device=time_modulation.device)
            + time_modulation[:, :3, :]
        ).chunk(3, dim=1)
        x = x + gate_mvs * self._multiview_attention(
            x,
            shift_mvs,
            scale_mvs,
            multiview_freqs,
            shape,
        )

        x = x + self.cross_attn(self.norm3(x), repeat(context, "1 l c -> v l c", v=x.shape[0]))

        residual = self._feed_forward(modulate(self.norm2(x), shift_mlp, scale_mlp))
        return x + gate_mlp * residual


class Head(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(MODEL_DIM, eps=NORM_EPSILON, elementwise_affine=False)
        self.head = nn.Linear(MODEL_DIM, LATENT_CHANNELS * math.prod(PATCH_SIZE))
        self.modulation = nn.Parameter(torch.randn(1, 2, MODEL_DIM) / MODEL_DIM**0.5)

    def forward(self, x: torch.Tensor, time_embedding: torch.Tensor) -> torch.Tensor:
        time_embedding = time_embedding[:, None, :]
        shift, scale = (
            self.modulation.to(dtype=time_embedding.dtype, device=time_embedding.device) + time_embedding
        ).chunk(2, dim=1)
        return self.head(self.norm(x) * (1 + scale) + shift)


def pad_for_3d_conv(x: torch.Tensor, kernel_size: tuple[int, int, int]) -> torch.Tensor:
    """Replicate-pad a video so every dimension is divisible by a kernel."""

    _, _, frames, height, width = x.shape
    temporal, vertical, horizontal = kernel_size
    pad_frames = (temporal - frames % temporal) % temporal
    pad_height = (vertical - height % vertical) % vertical
    pad_width = (horizontal - width % horizontal) % horizontal
    if pad_frames == pad_height == pad_width == 0:
        return x
    return F.pad(x, (0, pad_width, 0, pad_height, 0, pad_frames), mode="replicate")


class ViewPackEmbedding(nn.Module):
    """Pack four half-resolution reference views into one token grid."""

    def __init__(self) -> None:
        super().__init__()
        temporal, vertical, horizontal = PATCH_SIZE
        self.proj_2x = nn.Conv3d(
            LATENT_CHANNELS,
            MODEL_DIM,
            kernel_size=(temporal, vertical * 2, horizontal * 2),
            stride=(temporal, vertical * 2, horizontal * 2),
        )
        # The released checkpoint contains this trained partition even though
        # public inference uses exactly four 2x references.
        self.proj_4x = nn.Conv3d(
            LATENT_CHANNELS,
            MODEL_DIM,
            kernel_size=(temporal, vertical * 4, horizontal * 4),
            stride=(temporal, vertical * 4, horizontal * 4),
        )


class FourDAnyoneDiT(nn.Module):
    """Exact immutable inference graph for the released model checkpoint."""

    def __init__(self) -> None:
        super().__init__()
        self.patch_embedding = nn.Conv3d(
            LATENT_CHANNELS,
            MODEL_DIM,
            kernel_size=PATCH_SIZE,
            stride=PATCH_SIZE,
        )
        self.text_embedding = nn.Sequential(
            nn.Linear(TEXT_DIM, MODEL_DIM),
            nn.GELU(approximate="tanh"),
            nn.Linear(MODEL_DIM, MODEL_DIM),
        )
        self.time_embedding = nn.Sequential(
            nn.Linear(FREQUENCY_DIM, MODEL_DIM),
            nn.SiLU(),
            nn.Linear(MODEL_DIM, MODEL_DIM),
        )
        self.time_projection = nn.Sequential(nn.SiLU(), nn.Linear(MODEL_DIM, MODEL_DIM * 6))
        self.blocks = nn.ModuleList(DiTBlock() for _ in range(NUM_LAYERS))
        self.head = Head()
        self.viewpack_embedding = ViewPackEmbedding()
        self.freqs: tuple[torch.Tensor, torch.Tensor, torch.Tensor] = ()

    def _patchify(self, x: torch.Tensor) -> tuple[torch.Tensor, tuple[int, int, int]]:
        embedded = self.patch_embedding(x)
        grid_size = tuple(embedded.shape[2:])
        tokens = rearrange(embedded, "b c f h w -> b (f h w) c").contiguous()
        return tokens, grid_size

    @staticmethod
    def _unpatchify(x: torch.Tensor, grid_size: tuple[int, int, int]) -> torch.Tensor:
        return rearrange(
            x,
            "b (f h w) (x y z c) -> b c (f x) (h y) (w z)",
            f=grid_size[0],
            h=grid_size[1],
            w=grid_size[2],
            x=PATCH_SIZE[0],
            y=PATCH_SIZE[1],
            z=PATCH_SIZE[2],
        )

    def _spatial_frequencies(
        self,
        frames: int,
        height: int,
        width: int,
        device: torch.device,
    ) -> torch.Tensor:
        return (
            torch.cat(
                [
                    self.freqs[0][:frames].view(frames, 1, 1, -1).expand(frames, height, width, -1),
                    self.freqs[1][:height].view(1, height, 1, -1).expand(frames, height, width, -1),
                    self.freqs[2][:width].view(1, 1, width, -1).expand(frames, height, width, -1),
                ],
                dim=-1,
            )
            .reshape(frames * height * width, 1, -1)
            .to(device)
        )

    def _multiview_frequencies(
        self,
        views: int,
        height: int,
        width: int,
        device: torch.device,
    ) -> torch.Tensor:
        return (
            torch.cat(
                [
                    self.freqs[0][:views].view(views, 1, 1, -1).expand(views, height, width, -1),
                    self.freqs[1][:height].view(1, height, 1, -1).expand(views, height, width, -1),
                    self.freqs[2][:width].view(1, 1, width, -1).expand(views, height, width, -1),
                ],
                dim=-1,
            )
            .reshape(views * height * width, 1, -1)
            .to(device)
        )

    def _pack_sources(
        self,
        x: torch.Tensor,
        sources: torch.Tensor,
        grid_size: tuple[int, int, int],
    ) -> tuple[torch.Tensor, int]:
        source_views = int(sources.shape[0])
        if source_views == 1:
            primary_source = sources
            reference_sources = None
        elif source_views == 5:
            primary_source = sources[:1]
            reference_sources = sources[1:]
        else:
            raise ValueError(f"4DAnyone requires 1 or 5 source views, got {source_views}.")

        primary_tokens, _ = self._patchify(primary_source)
        x = torch.cat([x, primary_tokens], dim=0)
        packed_views = 1

        if reference_sources is not None:
            projection = self.viewpack_embedding.proj_2x
            reference_sources = pad_for_3d_conv(reference_sources, projection.kernel_size)
            packed = projection(reference_sources)
            packed = rearrange(packed, "(g1 g2) c f h w -> 1 c f (g1 h) (g2 w)", g1=2, g2=2)
            frames, height, width = grid_size
            packed = packed[:, :, :frames, :height, :width]
            packed = rearrange(packed, "1 c f h w -> 1 (f h w) c").to(dtype=x.dtype)
            x = torch.cat([x, packed], dim=0)
            packed_views += 1
        return x, packed_views

    @staticmethod
    def _add_pose_features(
        x: torch.Tensor,
        pose_features: torch.Tensor,
        null_pose_feature: torch.Tensor,
        target_views: int,
        packed_views: int,
        grid_size: tuple[int, int, int],
    ) -> torch.Tensor:
        frames, height, width = grid_size
        expected_pose = (target_views, MODEL_DIM, frames, height, width)
        expected_null = (packed_views, MODEL_DIM, frames, height, width)
        if tuple(pose_features.shape) != expected_pose:
            raise ValueError(f"Expected pose features {expected_pose}, got {tuple(pose_features.shape)}.")
        if tuple(null_pose_feature.shape) != expected_null:
            raise ValueError(f"Expected null pose features {expected_null}, got {tuple(null_pose_feature.shape)}.")
        pose_tokens = rearrange(pose_features, "v c f h w -> v (f h w) c")
        null_tokens = rearrange(null_pose_feature, "v c f h w -> v (f h w) c")
        if torch.is_grad_enabled():
            return torch.cat([x[:target_views] + pose_tokens, x[target_views:] + null_tokens], dim=0)
        x[:target_views].add_(pose_tokens)
        x[target_views:].add_(null_tokens)
        return x

    def forward(
        self,
        *,
        x: torch.Tensor,
        x_src: torch.Tensor,
        timestep: torch.Tensor,
        context: torch.Tensor,
        pose_features: torch.Tensor,
        null_pose_feature: torch.Tensor,
    ) -> torch.Tensor:
        context = self.text_embedding(context)
        target_views = int(x.shape[0])
        x, grid_size = self._patchify(x)
        frames, height, width = grid_size
        spatial_freqs = self._spatial_frequencies(frames, height, width, x.device)

        x, packed_views = self._pack_sources(x, x_src, grid_size)
        timestep = torch.cat([timestep, torch.zeros(packed_views, dtype=timestep.dtype, device=timestep.device)])
        time_embedding = self.time_embedding(sinusoidal_embedding_1d(FREQUENCY_DIM, timestep).to(x.dtype))
        time_modulation = self.time_projection(time_embedding).unflatten(1, (6, MODEL_DIM))

        x = self._add_pose_features(
            x,
            pose_features,
            null_pose_feature,
            target_views,
            packed_views,
            grid_size,
        )
        total_views = target_views + packed_views
        multiview_freqs = self._multiview_frequencies(total_views, height, width, x.device)
        shape = (total_views, frames, height, width)
        for block in self.blocks:
            x = block(x, context, time_modulation, spatial_freqs, multiview_freqs, shape)

        x = x[:target_views]
        time_embedding = time_embedding[:target_views]
        return self._unpatchify(self.head(x, time_embedding), grid_size)
