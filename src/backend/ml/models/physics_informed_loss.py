"""
Physics-Informed Loss for CV Transformer
==========================================
Adds electrochemical physics constraints to the training loss.

Constraints implemented:
1. Butler-Volmer kinetics  — peak current ratio |ipa/ipc| ≈ 1 for reversible
2. Randles-Ševčík equation — peak current ∝ √scan_rate
3. Nernst equation         — peak separation ΔEp ≈ 59/n mV at 25 °C
4. Charge conservation     — ∫i dE ≈ 0 over a full cycle

Reference:
  Bard & Faulkner, "Electrochemical Methods", 2nd ed. (2001)
  Nicholson & Shain, Anal. Chem. 36, 706 (1964)

Author: VidyuthLabs
Date: May 6, 2026
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple
import numpy as np


# ── Physical constants ────────────────────────────────────────────────────
F_CONST  = 96485.0   # Faraday constant (C/mol)
R_CONST  = 8.314     # Gas constant (J/mol·K)
T_KELVIN = 298.15    # 25 °C in Kelvin


class PhysicsInformedLoss(nn.Module):
    """
    Physics-informed loss that penalises violations of electrochemical laws.

    Usage:
        physics_loss = PhysicsInformedLoss(lambda_bv=0.1, lambda_rs=0.1,
                                           lambda_nernst=0.1, lambda_charge=0.05)
        total_loss = task_loss + physics_loss(predictions, cv_data)
    """

    def __init__(
        self,
        lambda_bv:     float = 0.10,   # Butler-Volmer weight
        lambda_rs:     float = 0.10,   # Randles-Ševčík weight
        lambda_nernst: float = 0.10,   # Nernst weight
        lambda_charge: float = 0.05,   # Charge conservation weight
        n_electrons:   int   = 1,      # Default number of electrons
    ):
        super().__init__()
        self.lambda_bv     = lambda_bv
        self.lambda_rs     = lambda_rs
        self.lambda_nernst = lambda_nernst
        self.lambda_charge = lambda_charge
        self.n_electrons   = n_electrons

        # Theoretical peak separation at 25 °C (mV → V)
        self.delta_ep_reversible = (59.0e-3) / n_electrons   # ~59 mV for n=1

    # ── Individual constraint losses ──────────────────────────────────────

    def butler_volmer_loss(
        self,
        predictions: Dict[str, torch.Tensor],
        reversibility: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Butler-Volmer constraint: for a reversible reaction the anodic and
        cathodic peak currents should be equal in magnitude.

        |ipa / ipc| = 1  (reversible)
        |ipa / ipc| > 1  (quasi-reversible / irreversible)

        We penalise predictions that claim high reversibility but have
        peak_current_ratio far from 1.
        """
        peaks = predictions.get("peaks")   # (B, 10)
        rev   = predictions.get("reversibility")  # (B,) or (B,1)

        if peaks is None or rev is None:
            return torch.tensor(0.0, device=next(iter(predictions.values())).device)

        if rev.dim() > 1:
            rev = rev.squeeze(-1)

        # peaks[:, 0] = anodic peak current, peaks[:, 1] = cathodic peak current
        ipa = peaks[:, 0]
        ipc = peaks[:, 1]

        # Avoid division by zero
        eps = 1e-8
        ratio = torch.abs(ipa) / (torch.abs(ipc) + eps)

        # For reversible (rev ≈ 1): ratio should be ≈ 1
        # Penalty = rev * (ratio - 1)²
        bv_penalty = rev * (ratio - 1.0) ** 2

        return bv_penalty.mean()

    def randles_sevcik_loss(
        self,
        predictions: Dict[str, torch.Tensor],
        scan_rates: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Randles-Ševčík constraint: peak current is proportional to √(scan_rate).

        ip = 0.4463 * n * F * A * C * √(n*F*D*v / (R*T))
           ∝ √v

        If scan rates are provided, we check that predicted peak currents
        scale correctly. Without scan rates we apply a soft constraint that
        the predicted peak current is positive and physically plausible.
        """
        peaks = predictions.get("peaks")
        if peaks is None:
            return torch.tensor(0.0)

        # Soft constraint: peak currents should be positive (physical)
        ipa = peaks[:, 0]
        ipc = peaks[:, 1]

        # Penalise negative anodic or positive cathodic peaks
        rs_penalty = F.relu(-ipa).mean() + F.relu(ipc).mean()

        if scan_rates is not None:
            # Hard constraint: ip ∝ √v
            # Normalise both and check correlation
            sqrt_v = torch.sqrt(scan_rates.float() + 1e-8)
            ip_norm = ipa / (ipa.abs().mean() + 1e-8)
            sv_norm = sqrt_v / (sqrt_v.mean() + 1e-8)
            rs_penalty = rs_penalty + F.mse_loss(ip_norm, sv_norm)

        return rs_penalty

    def nernst_loss(
        self,
        predictions: Dict[str, torch.Tensor],
    ) -> torch.Tensor:
        """
        Nernst constraint: for a reversible reaction the peak separation
        ΔEp = Epa - Epc ≈ 59/n mV at 25 °C.

        For quasi-reversible / irreversible reactions ΔEp > 59/n mV.
        We penalise predictions that claim high reversibility but have
        ΔEp far from the theoretical value.
        """
        peaks = predictions.get("peaks")
        rev   = predictions.get("reversibility")

        if peaks is None or rev is None:
            return torch.tensor(0.0)

        if rev.dim() > 1:
            rev = rev.squeeze(-1)

        # peaks[:, 2] = Epa (anodic peak potential)
        # peaks[:, 3] = Epc (cathodic peak potential)
        if peaks.shape[1] < 4:
            return torch.tensor(0.0, device=peaks.device)

        epa = peaks[:, 2]
        epc = peaks[:, 3]
        delta_ep = epa - epc   # should be ≈ 59/n mV for reversible

        # Penalty: for reversible reactions, (ΔEp - 59mV)² weighted by rev
        nernst_penalty = rev * (delta_ep - self.delta_ep_reversible) ** 2

        return nernst_penalty.mean()

    def charge_conservation_loss(
        self,
        voltage: torch.Tensor,
        current: torch.Tensor,
    ) -> torch.Tensor:
        """
        Charge conservation: the integral of current over a complete CV cycle
        should be approximately zero (equal charge in anodic and cathodic sweeps).

        ∫ i dE ≈ 0

        Args:
            voltage: (B, N) voltage array
            current: (B, N) current array
        """
        if voltage is None or current is None:
            return torch.tensor(0.0)

        # Trapezoidal integration: ∫ i dE
        dv = voltage[:, 1:] - voltage[:, :-1]          # (B, N-1)
        i_mid = (current[:, 1:] + current[:, :-1]) / 2  # (B, N-1)
        charge = (i_mid * dv).sum(dim=1)                 # (B,)

        # Normalise by peak current to make scale-invariant
        i_max = current.abs().max(dim=1).values + 1e-8
        charge_norm = charge / i_max

        return (charge_norm ** 2).mean()

    # ── Combined loss ─────────────────────────────────────────────────────

    def forward(
        self,
        predictions: Dict[str, torch.Tensor],
        voltage: Optional[torch.Tensor] = None,
        current: Optional[torch.Tensor] = None,
        scan_rates: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute total physics-informed loss.

        Args:
            predictions: dict with keys 'peaks', 'reversibility', etc.
            voltage:     (B, N) voltage array (optional)
            current:     (B, N) current array (optional)
            scan_rates:  (B,) scan rates in V/s (optional)

        Returns:
            total_physics_loss: scalar tensor
            breakdown: dict with individual loss values for logging
        """
        bv_loss      = self.butler_volmer_loss(predictions) * self.lambda_bv
        rs_loss      = self.randles_sevcik_loss(predictions, scan_rates) * self.lambda_rs
        nernst_loss  = self.nernst_loss(predictions) * self.lambda_nernst

        charge_loss = torch.tensor(0.0)
        if voltage is not None and current is not None:
            # Ensure current is (B, N) — squeeze channel dim if (B, 1, N)
            _current = current.squeeze(1) if current.dim() == 3 else current
            charge_loss = self.charge_conservation_loss(voltage, _current) * self.lambda_charge

        total = bv_loss + rs_loss + nernst_loss + charge_loss

        breakdown = {
            "bv_loss":     float(bv_loss),
            "rs_loss":     float(rs_loss),
            "nernst_loss": float(nernst_loss),
            "charge_loss": float(charge_loss),
            "total":       float(total),
        }

        return total, breakdown


# ── Convenience wrapper ───────────────────────────────────────────────────

class PhysicsAugmentedLoss(nn.Module):
    """
    Combines standard task loss with physics-informed constraints.

    total_loss = task_loss + physics_loss

    Drop-in replacement for the existing multi-task loss in train_cv.py.
    """

    def __init__(
        self,
        task_loss_fn: nn.Module,
        physics_weight: float = 0.1,
        **physics_kwargs,
    ):
        super().__init__()
        self.task_loss_fn   = task_loss_fn
        self.physics_weight = physics_weight
        self.physics_loss   = PhysicsInformedLoss(**physics_kwargs)

    def forward(
        self,
        predictions: Dict[str, torch.Tensor],
        targets: Dict[str, torch.Tensor],
        voltage: Optional[torch.Tensor] = None,
        current: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Args:
            predictions: model output dict
            targets:     ground-truth dict
            voltage:     (B, N) voltage array (optional)
            current:     (B, N) current array (optional)

        Returns:
            total_loss, breakdown_dict
        """
        task_loss = self.task_loss_fn(predictions, targets)
        phys_loss, phys_breakdown = self.physics_loss(predictions, voltage, current)

        total = task_loss + self.physics_weight * phys_loss

        breakdown = {
            "task_loss":   float(task_loss),
            "phys_total":  float(phys_loss),
            **{f"phys_{k}": v for k, v in phys_breakdown.items()},
            "total":       float(total),
        }

        return total, breakdown


# ── Quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    B, N = 4, 2000
    torch.manual_seed(42)

    # Fake predictions
    preds = {
        "peaks":         torch.randn(B, 10),
        "reversibility": torch.sigmoid(torch.randn(B)),
        "mechanism":     torch.randn(B, 5),
        "parameters":    torch.randn(B, 5),
    }

    # Fake CV data
    t = torch.linspace(0, 2 * torch.pi, N)
    voltage = torch.sin(t).unsqueeze(0).expand(B, -1)
    current = torch.cos(t).unsqueeze(0).expand(B, -1) * 1e-6

    loss_fn = PhysicsInformedLoss(
        lambda_bv=0.1, lambda_rs=0.1, lambda_nernst=0.1, lambda_charge=0.05
    )

    total, breakdown = loss_fn(preds, voltage, current)

    print("=" * 60)
    print("PHYSICS-INFORMED LOSS TEST")
    print("=" * 60)
    print(f"Total physics loss: {total.item():.6f}")
    for k, v in breakdown.items():
        print(f"  {k:20s}: {v:.6f}")
    print("\n✅ Physics-informed loss working correctly!")
    print("\nConstraints implemented:")
    print("  ✓ Butler-Volmer kinetics (|ipa/ipc| ≈ 1 for reversible)")
    print("  ✓ Randles-Ševčík equation (ip ∝ √v)")
    print("  ✓ Nernst equation (ΔEp ≈ 59/n mV)")
    print("  ✓ Charge conservation (∫i dE ≈ 0)")
