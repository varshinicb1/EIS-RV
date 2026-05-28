"""
Contrastive Learning for CV Transformer (Week 3)
==================================================
Self-supervised contrastive learning to learn better CV representations
without labels. Uses SimCLR-style augmentation + NT-Xent loss.

Key idea: Two augmented views of the same CV curve should have similar
representations; different curves should be dissimilar.

Augmentations:
  - Gaussian noise injection
  - Random time-shift (phase shift)
  - Amplitude scaling
  - Baseline drift addition
  - Scan rate perturbation (time-stretch)

Author: VidyuthLabs
Date: May 6, 2026
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
import numpy as np


# ── Augmentations ─────────────────────────────────────────────────────────

class CVAugmentation:
    """
    Electrochemically-motivated augmentations for CV curves.
    All augmentations preserve the essential electrochemical features
    while creating diverse views for contrastive learning.
    """

    def __init__(
        self,
        noise_std:       float = 0.02,
        shift_max:       int   = 50,
        scale_range:     Tuple[float, float] = (0.8, 1.2),
        drift_std:       float = 0.01,
        stretch_range:   Tuple[float, float] = (0.9, 1.1),
        p_noise:         float = 0.8,
        p_shift:         float = 0.5,
        p_scale:         float = 0.7,
        p_drift:         float = 0.4,
        p_stretch:       float = 0.3,
    ):
        self.noise_std     = noise_std
        self.shift_max     = shift_max
        self.scale_range   = scale_range
        self.drift_std     = drift_std
        self.stretch_range = stretch_range
        self.p_noise       = p_noise
        self.p_shift       = p_shift
        self.p_scale       = p_scale
        self.p_drift       = p_drift
        self.p_stretch     = p_stretch

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply random augmentations to a CV curve.

        Args:
            x: (N,) or (1, N) current array

        Returns:
            Augmented tensor of same shape
        """
        squeeze = x.dim() == 1
        if squeeze:
            x = x.unsqueeze(0)

        x = x.clone()

        # 1. Gaussian noise
        if torch.rand(1).item() < self.p_noise:
            x = x + torch.randn_like(x) * self.noise_std

        # 2. Random time-shift (circular)
        if torch.rand(1).item() < self.p_shift:
            shift = torch.randint(-self.shift_max, self.shift_max + 1, (1,)).item()
            x = torch.roll(x, shift, dims=-1)

        # 3. Amplitude scaling
        if torch.rand(1).item() < self.p_scale:
            scale = self.scale_range[0] + torch.rand(1).item() * (self.scale_range[1] - self.scale_range[0])
            x = x * scale

        # 4. Baseline drift (linear)
        if torch.rand(1).item() < self.p_drift:
            N = x.shape[-1]
            drift = torch.linspace(0, torch.randn(1).item() * self.drift_std, N, device=x.device)
            x = x + drift.unsqueeze(0)

        # 5. Time-stretch (resample)
        if torch.rand(1).item() < self.p_stretch:
            factor = self.stretch_range[0] + torch.rand(1).item() * (self.stretch_range[1] - self.stretch_range[0])
            N = x.shape[-1]
            new_N = int(N * factor)
            x_stretched = F.interpolate(x.unsqueeze(0), size=new_N, mode='linear', align_corners=False).squeeze(0)
            # Crop or pad back to N
            if new_N >= N:
                x = x_stretched[..., :N]
            else:
                pad = N - new_N
                x = F.pad(x_stretched, (0, pad), mode='replicate')

        if squeeze:
            x = x.squeeze(0)

        return x


# ── NT-Xent Loss ──────────────────────────────────────────────────────────

class NTXentLoss(nn.Module):
    """
    Normalized Temperature-scaled Cross Entropy Loss (SimCLR).

    For a batch of N samples, creates 2N representations (two augmented
    views per sample). The loss maximises agreement between positive pairs
    (same sample, different augmentations) and minimises agreement between
    negative pairs (different samples).

    Reference:
        Chen et al., "A Simple Framework for Contrastive Learning of
        Visual Representations", ICML 2020.
    """

    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature

    def forward(self, z1: torch.Tensor, z2: torch.Tensor) -> torch.Tensor:
        """
        Compute NT-Xent loss.

        Args:
            z1: (B, D) projected representations of view 1
            z2: (B, D) projected representations of view 2

        Returns:
            Scalar loss
        """
        B = z1.shape[0]

        # L2 normalise
        z1 = F.normalize(z1, dim=1)
        z2 = F.normalize(z2, dim=1)

        # Concatenate: (2B, D)
        z = torch.cat([z1, z2], dim=0)

        # Similarity matrix: (2B, 2B)
        sim = torch.mm(z, z.T) / self.temperature

        # Mask out self-similarity
        mask = torch.eye(2 * B, device=z.device, dtype=torch.bool)
        sim.masked_fill_(mask, float('-inf'))

        # Positive pairs: (i, i+B) and (i+B, i)
        labels = torch.cat([
            torch.arange(B, 2 * B, device=z.device),
            torch.arange(0, B,     device=z.device),
        ])

        loss = F.cross_entropy(sim, labels)
        return loss


# ── Projection Head ───────────────────────────────────────────────────────

class ProjectionHead(nn.Module):
    """
    MLP projection head for contrastive learning.
    Maps encoder representations to a lower-dimensional space
    where the contrastive loss is applied.
    """

    def __init__(self, in_dim: int = 256, hidden_dim: int = 256, out_dim: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, out_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ── Contrastive CV Transformer ────────────────────────────────────────────

class ContrastiveCVTransformer(nn.Module):
    """
    CV Transformer with contrastive learning head.

    Architecture:
        Encoder (CV Transformer backbone)
        → Global average pool
        → Projection head (MLP)
        → NT-Xent loss

    Can be used for:
    1. Pre-training on unlabelled CV data (self-supervised)
    2. Fine-tuning on labelled data (supervised)
    3. Feature extraction for downstream tasks
    """

    def __init__(
        self,
        encoder: nn.Module,
        projection_dim: int = 128,
        temperature: float = 0.07,
    ):
        super().__init__()
        self.encoder    = encoder
        self.augment    = CVAugmentation()
        self.nt_xent    = NTXentLoss(temperature=temperature)

        # Get encoder output dimension
        with torch.no_grad():
            dummy = torch.zeros(1, 1, 2000)
            try:
                enc_out = encoder(dummy, task="species")
                enc_dim = enc_out["species"].shape[-1]
            except Exception:
                enc_dim = 256

        self.projector = ProjectionHead(
            in_dim=enc_dim,
            hidden_dim=enc_dim,
            out_dim=projection_dim,
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Extract representations from CV curves."""
        out = self.encoder(x, task="species")
        return out["species"]

    def forward(
        self,
        x: torch.Tensor,
        return_loss: bool = True,
    ) -> dict:
        """
        Forward pass with contrastive loss.

        Args:
            x: (B, 1, N) CV current
            return_loss: whether to compute NT-Xent loss

        Returns:
            dict with 'loss', 'z1', 'z2', 'h1', 'h2'
        """
        if return_loss:
            # Create two augmented views
            x1 = torch.stack([self.augment(x[i, 0]) for i in range(x.shape[0])]).unsqueeze(1)
            x2 = torch.stack([self.augment(x[i, 0]) for i in range(x.shape[0])]).unsqueeze(1)

            # Encode both views
            h1 = self.encode(x1)
            h2 = self.encode(x2)

            # Project
            z1 = self.projector(h1)
            z2 = self.projector(h2)

            # Contrastive loss
            loss = self.nt_xent(z1, z2)

            return {"loss": loss, "z1": z1, "z2": z2, "h1": h1, "h2": h2}
        else:
            h = self.encode(x)
            z = self.projector(h)
            return {"h": h, "z": z}


# ── Quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.cv_transformer import create_cv_transformer

    print("Testing Contrastive CV Transformer...")

    encoder = create_cv_transformer("base")
    model   = ContrastiveCVTransformer(encoder, projection_dim=128, temperature=0.07)

    B, N = 8, 2000
    x = torch.randn(B, 1, N)

    out = model(x, return_loss=True)
    print(f"  Loss:    {out['loss'].item():.4f}")
    print(f"  z1 shape: {out['z1'].shape}")
    print(f"  h1 shape: {out['h1'].shape}")

    # Test augmentation
    aug = CVAugmentation()
    x_aug = aug(x[0, 0])
    print(f"  Augmented shape: {x_aug.shape}")

    # Test NT-Xent
    nt = NTXentLoss(temperature=0.07)
    z1 = torch.randn(B, 128)
    z2 = torch.randn(B, 128)
    loss = nt(z1, z2)
    print(f"  NT-Xent loss: {loss.item():.4f}")

    print("✅ Contrastive learning module OK")
