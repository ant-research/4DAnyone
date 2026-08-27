import torch
import torch.nn as nn
import numpy as np
from torch.nn import init

# PoseEncoder is a 3D version of PoseNet in MimicMotion. Copyright Tencent;
# the source is licensed under Apache-2.0:
# https://github.com/Tencent/MimicMotion/blob/c053153a1d124abae8c08568925ae88debc63001/mimicmotion/modules/pose_net.py


class PoseEncoder(nn.Module):
    def __init__(self, out_dim=5120, in_channels=3):
        super().__init__()

        if out_dim in (5120, 1536):
            # Wan2.1-T2V-14B / 1.3B
            t_strides = (1, 1, 1, 2, 2)  # downsampled by 4
            s_strides = (2, 2, 1, 2, 2)  # downsampled by 16
            kernel_size = (3, 3, 3)
        elif out_dim == 3072:
            # Wan2.2-TI2V-5B
            t_strides = (1, 1, 1, 2, 2)  # downsampled by 4
            s_strides = (2, 2, 2, 2, 2)  # downsampled by 32
            kernel_size = (3, 4, 4)
        else:
            raise ValueError(f"Invalid out_dim: {out_dim}")

        strides = [(t, s, s) for t, s in zip(t_strides, s_strides)]

        self.conv_layers = nn.Sequential(
            nn.Conv3d(in_channels, in_channels, kernel_size=3, stride=1, padding=1),
            nn.SiLU(inplace=True),
            nn.Conv3d(in_channels, 16, kernel_size=kernel_size, stride=strides[0], padding=(1, 1, 1)),
            nn.SiLU(inplace=True),
            nn.Conv3d(16, 16, kernel_size=3, stride=1, padding=1),
            nn.SiLU(inplace=True),
            nn.Conv3d(16, 32, kernel_size=kernel_size, stride=strides[1], padding=(1, 1, 1)),
            nn.SiLU(inplace=True),
            nn.Conv3d(32, 32, kernel_size=3, stride=1, padding=1),
            nn.SiLU(inplace=True),
            nn.Conv3d(32, 64, kernel_size=kernel_size, stride=strides[2], padding=(1, 1, 1)),
            nn.SiLU(inplace=True),
            nn.Conv3d(64, 64, kernel_size=3, stride=1, padding=1),
            nn.SiLU(inplace=True),
            nn.Conv3d(64, 128, kernel_size=kernel_size, stride=strides[3], padding=(1, 1, 1)),
            nn.SiLU(inplace=True),
            nn.Conv3d(128, 128, kernel_size=3, stride=1, padding=1),
            nn.SiLU(inplace=True),
            nn.Conv3d(128, 256, kernel_size=kernel_size, stride=strides[4], padding=(1, 1, 1)),
            nn.SiLU(inplace=True),
        )

        self.final_proj = nn.Conv3d(256, out_dim, kernel_size=1)

        self.scale = nn.Parameter(torch.ones(1) * 2.0)

        self._initialize_weights()

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv3d):
                # He (Kaiming) initialization in fan‑in mode
                receptive = np.prod(m.kernel_size) * m.in_channels
                init.normal_(m.weight, mean=0.0, std=np.sqrt(2.0 / receptive))
                if m.bias is not None:
                    init.zeros_(m.bias)
        # start with zero output so model behaves like unconditional
        init.zeros_(self.final_proj.weight)
        if self.final_proj.bias is not None:
            init.zeros_(self.final_proj.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, C, F, H, W) -> latent grid matching the DiT patch tokens.
        Wan2.1 uses F/4, H/16, W/16; Wan2.2-TI2V-5B uses F/4, H/32, W/32.
        """
        # Wan pattern: 1 -> 4 -> 4 -> ...
        x = torch.cat([x[:, :, :1].repeat(1, 1, 3, 1, 1), x], dim=2)

        x = self.conv_layers(x)
        x = self.final_proj(x)
        return x * self.scale
