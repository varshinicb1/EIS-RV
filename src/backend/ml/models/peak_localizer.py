"""
Peak Localization for CV Curves (Week 5)
==========================================
Sequence-to-sequence model that localizes redox peaks in CV curves.
Handles multi-peak systems (e.g., multi-redox biosensors).

Architecture:
  CV Transformer encoder → Peak detection head (per-point classification)
  → Peak regression head (exact position + height)

Outputs per time-step:
  - is_peak: probability of being a peak (binary)
  - peak_type: anodic / cathodic / none
  - peak_height: relative height above baseline

Author: VidyuthLabs
Date: May 6, 2026
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple
import numpy as np


class PeakLocalizationHead(nn.Module):
    """
    Per-timestep peak localization head.

    Takes encoder hidden states and predicts:
      - is_peak: (B, N) probability of peak at each position
      - peak_type: (B, N, 3) logits for [none, anodic, cathodic]
      - peak_height: (B, N) relative height
    """

    def __init__(self, d_model: int = 256, dropout: float = 0.1):
        super().__init__()
        self.conv1 = nn.Conv1d(d_model, 128, kernel_size=5, padding=2)
        self.conv2 = nn.Conv1d(128, 64, kernel_size=3, padding=1)
        self.norm1 = nn.BatchNorm1d(128)
        self.norm2 = nn.BatchNorm1d(64)
        self.drop  = nn.Dropout(dropout)

        self.head_is_peak    = nn.Conv1d(64, 1, kernel_size=1)
        self.head_peak_type  = nn.Conv1d(64, 3, kernel_size=1)
        self.head_peak_height= nn.Conv1d(64, 1, kernel_size=1)

    def forward(self, hidden: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Args:
            hidden: (B, N, d_model) encoder hidden states

        Returns:
            dict with is_peak, peak_type, peak_height
        """
        x = hidden.transpose(1, 2)  # (B, d_model, N)

        x = F.gelu(self.norm1(self.conv1(x)))
        x = self.drop(x)
        x = F.gelu(self.norm2(self.conv2(x)))
        x = self.drop(x)

        is_peak    = torch.sigmoid(self.head_is_peak(x)).squeeze(1)    # (B, N)
        peak_type  = self.head_peak_type(x).transpose(1, 2)             # (B, N, 3)
        peak_height= self.head_peak_height(x).squeeze(1)                # (B, N)

        return {
            "is_peak":     is_peak,
            "peak_type":   peak_type,
            "peak_height": peak_height,
        }


class PeakLocalizationLoss(nn.Module):
    """
    Combined loss for peak localization.

    Components:
      1. Binary cross-entropy for is_peak (with class weighting for rare peaks)
      2. Cross-entropy for peak_type (only at peak positions)
      3. MSE for peak_height (only at peak positions)
    """

    def __init__(
        self,
        peak_weight:   float = 10.0,  # Weight for positive (peak) class
        type_weight:   float = 1.0,
        height_weight: float = 0.5,
    ):
        super().__init__()
        self.peak_weight   = peak_weight
        self.type_weight   = type_weight
        self.height_weight = height_weight

    def forward(
        self,
        predictions: Dict[str, torch.Tensor],
        targets:     Dict[str, torch.Tensor],
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Args:
            predictions: dict from PeakLocalizationHead
            targets: dict with is_peak_gt, peak_type_gt, peak_height_gt

        Returns:
            total_loss, breakdown
        """
        is_peak_pred    = predictions["is_peak"]
        peak_type_pred  = predictions["peak_type"]
        peak_height_pred= predictions["peak_height"]

        is_peak_gt      = targets.get("is_peak_gt",     torch.zeros_like(is_peak_pred))
        peak_type_gt    = targets.get("peak_type_gt",   torch.zeros_like(is_peak_pred, dtype=torch.long))
        peak_height_gt  = targets.get("peak_height_gt", torch.zeros_like(is_peak_pred))

        # 1. Peak detection loss (weighted BCE)
        pos_weight = torch.tensor([self.peak_weight], device=is_peak_pred.device)
        peak_loss  = F.binary_cross_entropy_with_logits(
            torch.logit(is_peak_pred.clamp(1e-6, 1 - 1e-6)),
            is_peak_gt,
            pos_weight=pos_weight,
        )

        # 2. Peak type loss (only at peak positions)
        peak_mask = is_peak_gt > 0.5
        if peak_mask.any():
            type_loss = F.cross_entropy(
                peak_type_pred[peak_mask],
                peak_type_gt[peak_mask],
            )
        else:
            type_loss = torch.tensor(0.0, device=is_peak_pred.device)

        # 3. Peak height loss (only at peak positions)
        if peak_mask.any():
            height_loss = F.mse_loss(
                peak_height_pred[peak_mask],
                peak_height_gt[peak_mask],
            )
        else:
            height_loss = torch.tensor(0.0, device=is_peak_pred.device)

        total = peak_loss + self.type_weight * type_loss + self.height_weight * height_loss

        return total, {
            "peak_loss":   float(peak_loss),
            "type_loss":   float(type_loss),
            "height_loss": float(height_loss),
            "total":       float(total),
        }


class PeakExtractor:
    """
    Post-processing: extract discrete peaks from continuous predictions.

    Uses non-maximum suppression to find peak positions.
    """

    def __init__(
        self,
        threshold:    float = 0.5,
        min_distance: int   = 20,
        max_peaks:    int   = 10,
    ):
        self.threshold    = threshold
        self.min_distance = min_distance
        self.max_peaks    = max_peaks

    def extract(
        self,
        is_peak:     torch.Tensor,
        peak_type:   torch.Tensor,
        peak_height: torch.Tensor,
        wavenumber:  Optional[torch.Tensor] = None,
    ) -> List[Dict]:
        """
        Extract discrete peaks from continuous predictions.

        Args:
            is_peak:     (N,) peak probability
            peak_type:   (N, 3) type logits
            peak_height: (N,) height
            wavenumber:  (N,) position axis (optional)

        Returns:
            List of peak dicts with position, type, height, confidence
        """
        is_peak_np = is_peak.cpu().numpy()
        N = len(is_peak_np)

        # Find local maxima above threshold
        peaks = []
        for i in range(1, N - 1):
            if (is_peak_np[i] > self.threshold and
                is_peak_np[i] >= is_peak_np[i - 1] and
                is_peak_np[i] >= is_peak_np[i + 1]):
                peaks.append(i)

        # Non-maximum suppression
        peaks_nms = []
        for p in sorted(peaks, key=lambda i: -is_peak_np[i]):
            if all(abs(p - q) >= self.min_distance for q in peaks_nms):
                peaks_nms.append(p)
            if len(peaks_nms) >= self.max_peaks:
                break

        # Build result
        result = []
        type_names = ["none", "anodic", "cathodic"]
        for idx in sorted(peaks_nms):
            peak_type_idx = int(peak_type[idx].argmax().item())
            result.append({
                "index":      idx,
                "position":   float(wavenumber[idx]) if wavenumber is not None else float(idx),
                "confidence": float(is_peak_np[idx]),
                "type":       type_names[peak_type_idx],
                "height":     float(peak_height[idx].item()),
            })

        return result


# ── Quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing Peak Localization...")

    B, N, D = 4, 2000, 256

    # Fake hidden states
    hidden = torch.randn(B, N, D)

    head = PeakLocalizationHead(d_model=D)
    out  = head(hidden)

    print(f"  is_peak shape:     {out['is_peak'].shape}")
    print(f"  peak_type shape:   {out['peak_type'].shape}")
    print(f"  peak_height shape: {out['peak_height'].shape}")

    # Test loss
    loss_fn = PeakLocalizationLoss()
    targets = {
        "is_peak_gt":     torch.zeros(B, N),
        "peak_type_gt":   torch.zeros(B, N, dtype=torch.long),
        "peak_height_gt": torch.zeros(B, N),
    }
    # Add some fake peaks
    targets["is_peak_gt"][:, 500] = 1.0
    targets["is_peak_gt"][:, 1200] = 1.0
    targets["peak_type_gt"][:, 500] = 1   # anodic
    targets["peak_type_gt"][:, 1200] = 2  # cathodic

    total, breakdown = loss_fn(out, targets)
    print(f"  Loss: {total.item():.4f}")
    print(f"  Breakdown: {breakdown}")

    # Test extractor
    extractor = PeakExtractor(threshold=0.3, min_distance=20)
    peaks = extractor.extract(out["is_peak"][0], out["peak_type"][0], out["peak_height"][0])
    print(f"  Extracted {len(peaks)} peaks")

    n_params = sum(p.numel() for p in head.parameters())
    print(f"  Parameters: {n_params:,}")
    print("✅ Peak localization module OK")
