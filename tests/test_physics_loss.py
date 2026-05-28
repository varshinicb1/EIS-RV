"""
Physics-Informed Loss — Dedicated Tests
=========================================
Exhaustive tests for all 4 electrochemical constraints.

Run:
    py -3.12 tests/test_physics_loss.py
"""

import sys, math
from pathlib import Path
import torch
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src" / "backend" / "ml"))

from models.physics_informed_loss import PhysicsInformedLoss, PhysicsAugmentedLoss

_results = []
def check(name, cond, detail=""):
    status = "✅ PASS" if cond else "❌ FAIL"
    _results.append((name, cond, detail))
    print(f"  {status}  {name}" + (f"  [{detail}]" if detail else ""))
    return cond

def section(t):
    print(f"\n{'='*60}\n  {t}\n{'='*60}")

B = 4

def _preds(ipa=1.0, ipc=-1.0, epa=0.3, epc=-0.3, rev=0.9):
    return {
        "peaks":         torch.tensor([[ipa, ipc, epa, epc, 0, 0, 0, 0, 0, 0]] * B, dtype=torch.float32),
        "reversibility": torch.tensor([rev] * B),
        "mechanism":     torch.randn(B, 5),
        "parameters":    torch.randn(B, 5),
    }

# ── 1. Butler-Volmer ──────────────────────────────────────────────────────
section("1. Butler-Volmer Constraint")

bv = PhysicsInformedLoss(lambda_bv=1.0, lambda_rs=0, lambda_nernst=0, lambda_charge=0)

# Perfect reversible: |ipa| = |ipc|, high rev → zero penalty
p_perfect = _preds(ipa=1.0, ipc=-1.0, rev=0.95)
loss_perfect, bd = bv(p_perfect)
check("BV: symmetric peaks, high rev → ~0 penalty",
      loss_perfect.item() < 0.01, f"{loss_perfect.item():.6f}")

# Asymmetric peaks, high rev → large penalty
p_asym = _preds(ipa=3.0, ipc=-0.5, rev=0.95)
loss_asym, _ = bv(p_asym)
check("BV: asymmetric peaks, high rev → large penalty",
      loss_asym.item() > 0.5, f"{loss_asym.item():.4f}")

# Asymmetric peaks, low rev → small penalty (irreversible is expected to be asymmetric)
p_irrev = _preds(ipa=3.0, ipc=-0.5, rev=0.05)
loss_irrev, _ = bv(p_irrev)
check("BV: asymmetric peaks, low rev → smaller penalty",
      loss_irrev.item() < loss_asym.item(), f"{loss_irrev.item():.4f} < {loss_asym.item():.4f}")

check("BV: breakdown key present", "bv_loss" in bd)
check("BV: lambda scales loss",
      abs(bv(p_asym)[0].item() - PhysicsInformedLoss(lambda_bv=2.0, lambda_rs=0, lambda_nernst=0, lambda_charge=0)(p_asym)[0].item() / 2) < 0.01)

# ── 2. Randles-Ševčík ────────────────────────────────────────────────────
section("2. Randles-Ševčík Constraint")

rs = PhysicsInformedLoss(lambda_bv=0, lambda_rs=1.0, lambda_nernst=0, lambda_charge=0)

# Physical: ipa > 0, ipc < 0
p_phys = _preds(ipa=1.0, ipc=-1.0)
loss_phys, _ = rs(p_phys)
check("RS: physical signs → zero penalty", loss_phys.item() == 0.0, f"{loss_phys.item():.6f}")

# Unphysical: ipa < 0 (wrong sign)
p_unphys = _preds(ipa=-1.0, ipc=1.0)
loss_unphys, _ = rs(p_unphys)
check("RS: wrong signs → positive penalty", loss_unphys.item() > 0, f"{loss_unphys.item():.4f}")

# Mixed: ipa > 0 but ipc > 0 (both positive, wrong)
p_mixed = _preds(ipa=1.0, ipc=0.5)
loss_mixed, _ = rs(p_mixed)
check("RS: positive ipc → penalty", loss_mixed.item() > 0, f"{loss_mixed.item():.4f}")

# ── 3. Nernst Equation ───────────────────────────────────────────────────
section("3. Nernst Equation Constraint")

nernst = PhysicsInformedLoss(lambda_bv=0, lambda_rs=0, lambda_nernst=1.0, lambda_charge=0)
delta_ep_theory = 59e-3  # 59 mV for n=1

# Perfect: ΔEp = 59 mV, high rev
p_nernst_ok = _preds(epa=0.3, epc=0.3 - delta_ep_theory, rev=0.95)
loss_nernst_ok, _ = nernst(p_nernst_ok)
check("Nernst: ΔEp=59mV, high rev → ~0 penalty",
      loss_nernst_ok.item() < 0.001, f"{loss_nernst_ok.item():.6f}")

# Wrong: ΔEp = 200 mV, high rev → large penalty
p_nernst_bad = _preds(epa=0.3, epc=0.3 - 0.2, rev=0.95)
loss_nernst_bad, _ = nernst(p_nernst_bad)
check("Nernst: ΔEp=200mV, high rev → penalty",
      loss_nernst_bad.item() > 0.01, f"{loss_nernst_bad.item():.4f}")

# Low rev: penalty should be small regardless of ΔEp
p_nernst_irrev = _preds(epa=0.3, epc=0.3 - 0.2, rev=0.05)
loss_nernst_irrev, _ = nernst(p_nernst_irrev)
check("Nernst: ΔEp=200mV, low rev → smaller penalty",
      loss_nernst_irrev.item() < loss_nernst_bad.item(),
      f"{loss_nernst_irrev.item():.4f} < {loss_nernst_bad.item():.4f}")

# ── 4. Charge Conservation ───────────────────────────────────────────────
section("4. Charge Conservation Constraint")

charge = PhysicsInformedLoss(lambda_bv=0, lambda_rs=0, lambda_nernst=0, lambda_charge=1.0)
p_dummy = _preds()

N = 2000
t = torch.linspace(0, 2 * math.pi, N)

# Zero charge: i = sin(t), E = sin(t) → ∫sin·d(sin) = ∫sin·cos dt = 0
v_sin = torch.sin(t).unsqueeze(0).expand(B, -1)
i_sin = torch.sin(t).unsqueeze(0).expand(B, -1)
loss_zero, _ = charge(p_dummy, v_sin, i_sin)
check("Charge: ∫sin·d(sin) ≈ 0", loss_zero.item() < 0.01, f"{loss_zero.item():.6f}")

# Non-zero charge: i = cos(t), E = sin(t) → ∫cos·d(sin) = ∫cos²dt = π
i_cos = torch.cos(t).unsqueeze(0).expand(B, -1)
loss_nonzero, _ = charge(p_dummy, v_sin, i_cos)
check("Charge: ∫cos·d(sin) ≠ 0 → penalty", loss_nonzero.item() > 0.1, f"{loss_nonzero.item():.4f}")

check("Charge: zero < nonzero", loss_zero.item() < loss_nonzero.item())

# No voltage/current → zero charge loss
loss_no_vc, _ = charge(p_dummy)
check("Charge: no V/I → zero loss", loss_no_vc.item() == 0.0, f"{loss_no_vc.item():.6f}")

# ── 5. Combined Loss ─────────────────────────────────────────────────────
section("5. Combined Loss")

combined = PhysicsInformedLoss(lambda_bv=0.1, lambda_rs=0.1, lambda_nernst=0.1, lambda_charge=0.05)

total, bd = combined(p_dummy, v_sin, i_cos)
check("Combined: total > 0",          total.item() > 0)
check("Combined: 5 breakdown keys",   len(bd) == 5)
check("Combined: total = sum",
      abs(bd["total"] - (bd["bv_loss"] + bd["rs_loss"] + bd["nernst_loss"] + bd["charge_loss"])) < 1e-5)

# Zero weights → zero total
zero_fn = PhysicsInformedLoss(lambda_bv=0, lambda_rs=0, lambda_nernst=0, lambda_charge=0)
total_zero, _ = zero_fn(p_dummy, v_sin, i_cos)
check("Combined: all-zero weights → zero total", total_zero.item() == 0.0)

# Gradient flows
p_grad = {k: v.requires_grad_(True) if v.is_floating_point() else v for k, v in p_dummy.items()}
total_grad, _ = combined(p_grad, v_sin, i_cos)
total_grad.backward()
check("Combined: gradients flow to peaks",
      p_grad["peaks"].grad is not None and p_grad["peaks"].grad.abs().sum() > 0)
check("Combined: gradients flow to reversibility",
      p_grad["reversibility"].grad is not None)

# ── 6. PhysicsAugmentedLoss ──────────────────────────────────────────────
section("6. PhysicsAugmentedLoss Wrapper")

class _TaskLoss(torch.nn.Module):
    def forward(self, preds, targets):
        return preds["reversibility"].mean()

aug = PhysicsAugmentedLoss(_TaskLoss(), physics_weight=0.1,
                            lambda_bv=0.1, lambda_rs=0.1, lambda_nernst=0.1, lambda_charge=0.05)
targets = {k: torch.zeros_like(v) for k, v in p_dummy.items()}
total_aug, bd_aug = aug(p_dummy, targets, v_sin, i_cos)

check("Augmented: returns scalar",         total_aug.dim() == 0)
check("Augmented: task_loss in breakdown", "task_loss" in bd_aug)
check("Augmented: phys_total in breakdown","phys_total" in bd_aug)
check("Augmented: total > task_loss",
      total_aug.item() > bd_aug["task_loss"],
      f"total={total_aug.item():.4f} > task={bd_aug['task_loss']:.4f}")

# physics_weight=0 → total = task_loss
aug_zero = PhysicsAugmentedLoss(_TaskLoss(), physics_weight=0.0)
total_zero_aug, bd_zero = aug_zero(p_dummy, targets, v_sin, i_cos)
check("Augmented: physics_weight=0 → total=task_loss",
      abs(total_zero_aug.item() - bd_zero["task_loss"]) < 1e-6)

# ── 7. Edge Cases ────────────────────────────────────────────────────────
section("7. Edge Cases")

# Single sample
p_single = {k: v[:1] for k, v in p_dummy.items()}
total_s, _ = combined(p_single, v_sin[:1], i_cos[:1])
check("Edge: batch_size=1 works", total_s.dim() == 0)

# Large batch
p_large = {k: v.repeat(8, *([1] * (v.dim()-1))) for k, v in p_dummy.items()}
total_l, _ = combined(p_large, v_sin.repeat(8, 1), i_cos.repeat(8, 1))
check("Edge: batch_size=32 works", total_l.dim() == 0)

# Missing peaks key
p_no_peaks = {k: v for k, v in p_dummy.items() if k != "peaks"}
total_np, _ = combined(p_no_peaks)
check("Edge: missing peaks → graceful (zero BV/RS/Nernst)", total_np.item() >= 0)

# NaN-free outputs
check("Edge: no NaN in total",    not math.isnan(total.item()))
check("Edge: no Inf in total",    not math.isinf(total.item()))

# ── Final ─────────────────────────────────────────────────────────────────
total_t  = len(_results)
passed   = sum(1 for _, ok, _ in _results if ok)
failed   = total_t - passed
print(f"\n{'='*60}\n  RESULTS: {passed}/{total_t}  ({100*passed/total_t:.1f}%)\n{'='*60}")
if failed:
    for name, ok, detail in _results:
        if not ok:
            print(f"  ✗ {name}" + (f"  [{detail}]" if detail else ""))
if __name__ == "__main__":
    import sys; sys.exit(0 if failed == 0 else 1)
