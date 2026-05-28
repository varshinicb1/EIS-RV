"""
Multi-Modal Fusion for Electrochemical Analysis (Week 4)
=========================================================
Fuses CV, EIS, and metadata into a unified representation.

Architecture:
  CV Encoder    → CV embedding (256-d)
  EIS Encoder   → EIS embedding (256-d)
  Metadata MLP  → Metadata embedding (64-d)
  Cross-Attention Fusion → Fused representation (256-d)
  Task Heads    → Predictions

Author: VidyuthLabs
Date: May 6, 2026
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple


# ── EIS Encoder ───────────────────────────────────────────────────────────

class EISEncoder(nn.Module):
    """
    Encodes EIS spectra (Nyquist data) into a fixed-size embedding.

    Input: (B, N, 2) — [Zreal, Zimag] pairs at N frequencies
    Output: (B, embed_dim)
    """

    def __init__(self, embed_dim: int = 256, n_heads: int = 4, n_layers: int = 3):
        super().__init__()
        self.input_proj = nn.Linear(2, embed_dim)
        encoder_layer   = nn.TransformerEncoderLayer(
            d_model=embed_dim, nhead=n_heads,
            dim_feedforward=embed_dim * 4,
            dropout=0.1, batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.pool        = nn.AdaptiveAvgPool1d(1)
        self.norm        = nn.LayerNorm(embed_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, N, 2) — [Zreal, Zimag]
        Returns:
            (B, embed_dim)
        """
        h = self.input_proj(x)          # (B, N, embed_dim)
        h = self.transformer(h)          # (B, N, embed_dim)
        h = h.transpose(1, 2)            # (B, embed_dim, N)
        h = self.pool(h).squeeze(-1)     # (B, embed_dim)
        return self.norm(h)


# ── Metadata Encoder ──────────────────────────────────────────────────────

class MetadataEncoder(nn.Module):
    """
    Encodes experimental metadata into an embedding.

    Metadata features:
      - scan_rate (V/s)
      - electrode_area (cm²)
      - temperature (°C)
      - electrolyte_pH
      - concentration (M)
      - electrode_type (one-hot: GCE, ITO, Au, Pt, Carbon)
    """

    ELECTRODE_TYPES = ["GCE", "ITO", "Au", "Pt", "Carbon", "Other"]
    N_NUMERIC       = 5   # scan_rate, area, temp, pH, conc
    N_ELECTRODE     = len(ELECTRODE_TYPES)
    INPUT_DIM       = N_NUMERIC + N_ELECTRODE

    def __init__(self, embed_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(self.INPUT_DIM, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Linear(128, embed_dim),
            nn.LayerNorm(embed_dim),
        )

    def forward(self, meta: Dict[str, torch.Tensor]) -> torch.Tensor:
        """
        Args:
            meta: dict with keys matching metadata features
        Returns:
            (B, embed_dim)
        """
        B = next(iter(meta.values())).shape[0]
        device = next(iter(meta.values())).device

        # Numeric features (normalised)
        numeric = torch.stack([
            meta.get("scan_rate",    torch.zeros(B, device=device)) / 1.0,
            meta.get("area",         torch.ones(B,  device=device)) / 1.0,
            meta.get("temperature",  torch.full((B,), 25.0, device=device)) / 100.0,
            meta.get("pH",           torch.full((B,), 7.0,  device=device)) / 14.0,
            meta.get("concentration",torch.ones(B,  device=device)) / 1.0,
        ], dim=1)  # (B, 5)

        # Electrode type (one-hot)
        electrode_idx = meta.get("electrode_type", torch.zeros(B, dtype=torch.long, device=device))
        electrode_oh  = F.one_hot(electrode_idx.clamp(0, self.N_ELECTRODE - 1),
                                   num_classes=self.N_ELECTRODE).float()  # (B, 6)

        x = torch.cat([numeric, electrode_oh], dim=1)  # (B, 11)
        return self.net(x)


# ── Cross-Attention Fusion ────────────────────────────────────────────────

class CrossAttentionFusion(nn.Module):
    """
    Fuses multiple modality embeddings using cross-attention.

    Each modality attends to all others, then outputs are combined.
    """

    def __init__(self, embed_dim: int = 256, n_heads: int = 8, dropout: float = 0.1):
        super().__init__()
        self.cv_to_eis  = nn.MultiheadAttention(embed_dim, n_heads, dropout=dropout, batch_first=True)
        self.eis_to_cv  = nn.MultiheadAttention(embed_dim, n_heads, dropout=dropout, batch_first=True)
        self.norm_cv    = nn.LayerNorm(embed_dim)
        self.norm_eis   = nn.LayerNorm(embed_dim)
        self.ffn        = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim * 4, embed_dim),
        )
        self.norm_out   = nn.LayerNorm(embed_dim)

    def forward(
        self,
        cv_emb:  torch.Tensor,
        eis_emb: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            cv_emb:  (B, embed_dim)
            eis_emb: (B, embed_dim)
        Returns:
            (B, embed_dim) fused representation
        """
        # Add sequence dimension for attention
        cv  = cv_emb.unsqueeze(1)   # (B, 1, D)
        eis = eis_emb.unsqueeze(1)  # (B, 1, D)

        # Cross-attention
        cv_attended,  _ = self.cv_to_eis(cv,  eis, eis)
        eis_attended, _ = self.eis_to_cv(eis, cv,  cv)

        cv_out  = self.norm_cv(cv_emb  + cv_attended.squeeze(1))
        eis_out = self.norm_eis(eis_emb + eis_attended.squeeze(1))

        # Concatenate and project
        fused = torch.cat([cv_out, eis_out], dim=1)  # (B, 2D)
        out   = self.ffn(fused)                        # (B, D)
        return self.norm_out(out)


# ── Multi-Modal Fusion Model ──────────────────────────────────────────────

class MultiModalElectrochemModel(nn.Module):
    """
    Multi-modal electrochemical analysis model.

    Fuses CV, EIS, and metadata for improved predictions.
    Falls back gracefully when modalities are missing.

    Outputs:
      - reversibility (scalar)
      - mechanism (5 classes)
      - peaks (10 values)
      - parameters (5 values)
      - material_embedding (256-d, for material identification)
    """

    def __init__(
        self,
        cv_encoder:   nn.Module,
        embed_dim:    int = 256,
        meta_dim:     int = 64,
        n_heads:      int = 8,
        dropout:      float = 0.1,
    ):
        super().__init__()
        self.cv_encoder   = cv_encoder
        self.eis_encoder  = EISEncoder(embed_dim=embed_dim)
        self.meta_encoder = MetadataEncoder(embed_dim=meta_dim)
        self.fusion       = CrossAttentionFusion(embed_dim, n_heads, dropout)

        # Projection for metadata to match embed_dim
        self.meta_proj = nn.Linear(meta_dim, embed_dim)

        # Task heads
        fused_dim = embed_dim
        self.head_reversibility = nn.Sequential(
            nn.Linear(fused_dim, 64), nn.ReLU(), nn.Linear(64, 1), nn.Sigmoid()
        )
        self.head_mechanism = nn.Sequential(
            nn.Linear(fused_dim, 128), nn.ReLU(), nn.Linear(128, 5)
        )
        self.head_peaks = nn.Sequential(
            nn.Linear(fused_dim, 128), nn.ReLU(), nn.Linear(128, 10)
        )
        self.head_parameters = nn.Sequential(
            nn.Linear(fused_dim, 64), nn.ReLU(), nn.Linear(64, 5)
        )
        self.head_material = nn.Sequential(
            nn.Linear(fused_dim, embed_dim), nn.LayerNorm(embed_dim)
        )

    def forward(
        self,
        cv:   torch.Tensor,
        eis:  Optional[torch.Tensor] = None,
        meta: Optional[Dict[str, torch.Tensor]] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Args:
            cv:   (B, 1, N) CV current
            eis:  (B, N_eis, 2) EIS [Zreal, Zimag] — optional
            meta: dict of metadata tensors — optional

        Returns:
            dict with task predictions
        """
        # CV encoding
        cv_out = self.cv_encoder(cv, task="species")
        cv_emb = cv_out["species"]  # (B, embed_dim)

        # EIS encoding (if available)
        if eis is not None:
            eis_emb = self.eis_encoder(eis)
            fused   = self.fusion(cv_emb, eis_emb)
        else:
            fused = cv_emb

        # Metadata (if available) — add as residual
        if meta is not None:
            meta_emb = self.meta_proj(self.meta_encoder(meta))
            fused    = fused + meta_emb

        # Task predictions
        return {
            "reversibility":       self.head_reversibility(fused).squeeze(-1),
            "mechanism":           self.head_mechanism(fused),
            "peaks":               self.head_peaks(fused),
            "parameters":          self.head_parameters(fused),
            "material_embedding":  self.head_material(fused),
            "fused_embedding":     fused,
        }


# ── Quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.cv_transformer import create_cv_transformer

    print("Testing Multi-Modal Fusion Model...")

    cv_encoder = create_cv_transformer("base")
    model      = MultiModalElectrochemModel(cv_encoder, embed_dim=256)

    B = 4
    cv   = torch.randn(B, 1, 2000)
    eis  = torch.randn(B, 61, 2)   # 61 frequency points
    meta = {
        "scan_rate":    torch.tensor([0.05, 0.1, 0.05, 0.2]),
        "area":         torch.ones(B),
        "temperature":  torch.full((B,), 25.0),
        "pH":           torch.full((B,), 7.0),
        "concentration":torch.ones(B),
        "electrode_type": torch.zeros(B, dtype=torch.long),
    }

    # CV only
    out_cv = model(cv)
    print(f"  CV only — reversibility: {out_cv['reversibility'].shape}")

    # CV + EIS
    out_cv_eis = model(cv, eis=eis)
    print(f"  CV+EIS — reversibility: {out_cv_eis['reversibility'].shape}")

    # CV + EIS + metadata
    out_full = model(cv, eis=eis, meta=meta)
    print(f"  Full — reversibility: {out_full['reversibility'].shape}")
    print(f"  Full — material_embedding: {out_full['material_embedding'].shape}")

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Total parameters: {n_params:,}")
    print("✅ Multi-modal fusion module OK")
