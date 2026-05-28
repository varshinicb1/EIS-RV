"""
Comprehensive ML Pipeline Tests
=================================
Tests the full ML pipeline:
  1. Physics-informed loss (all 4 constraints)
  2. CV Transformer model (forward pass, output shapes)
  3. Ensemble model (uncertainty quantification)
  4. Anomaly detector (reconstruction, threshold)
  5. Raman material identifier (peak matching, confidence)
  6. Integration (end-to-end prediction pipeline)

Run:
    py -3.12 tests/test_ml_pipeline.py
"""

import sys
import json
import math
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "backend" / "ml"))

_results = []

def check(name, condition, detail=""):
    status = "✅ PASS" if condition else "❌ FAIL"
    _results.append((name, condition, detail))
    print(f"  {status}  {name}" + (f"  [{detail}]" if detail else ""))
    return condition

def section(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 — PHYSICS-INFORMED LOSS
# ═══════════════════════════════════════════════════════════════════════════
section("1. Physics-Informed Loss")

from models.physics_informed_loss import PhysicsInformedLoss, PhysicsAugmentedLoss

B, N = 4, 2000
torch.manual_seed(42)

# Synthetic predictions
preds = {
    "peaks":         torch.randn(B, 10),
    "reversibility": torch.sigmoid(torch.randn(B)),
    "mechanism":     torch.randn(B, 5),
    "parameters":    torch.randn(B, 5),
}
t = torch.linspace(0, 2 * math.pi, N)
voltage = torch.sin(t).unsqueeze(0).expand(B, -1)
current = torch.cos(t).unsqueeze(0).expand(B, -1) * 1e-6

loss_fn = PhysicsInformedLoss(lambda_bv=0.1, lambda_rs=0.1, lambda_nernst=0.1, lambda_charge=0.05)
total, breakdown = loss_fn(preds, voltage, current)

check("Physics loss: returns scalar tensor",  total.dim() == 0)
check("Physics loss: total > 0",              total.item() > 0, f"{total.item():.6f}")
check("Physics loss: breakdown has 5 keys",   len(breakdown) == 5, str(list(breakdown.keys())))
check("Physics loss: BV loss present",        "bv_loss" in breakdown)
check("Physics loss: RS loss present",        "rs_loss" in breakdown)
check("Physics loss: Nernst loss present",    "nernst_loss" in breakdown)
check("Physics loss: charge loss present",    "charge_loss" in breakdown)
check("Physics loss: total = sum of parts",
      abs(breakdown["total"] - (breakdown["bv_loss"] + breakdown["rs_loss"] +
                                 breakdown["nernst_loss"] + breakdown["charge_loss"])) < 1e-5,
      f"total={breakdown['total']:.6f}")

# Test with zero physics weight
loss_zero = PhysicsInformedLoss(lambda_bv=0, lambda_rs=0, lambda_nernst=0, lambda_charge=0)
total_zero, _ = loss_zero(preds, voltage, current)
check("Physics loss: zero weights → zero loss", total_zero.item() == 0.0, str(total_zero.item()))

# Test PhysicsAugmentedLoss
class _DummyTaskLoss(torch.nn.Module):
    def forward(self, predictions, targets):
        return predictions["reversibility"].mean()

aug_fn  = PhysicsAugmentedLoss(_DummyTaskLoss(), physics_weight=0.1)
targets = {k: torch.zeros_like(v) for k, v in preds.items()}
aug_total, aug_breakdown = aug_fn(preds, targets, voltage, current)
check("Augmented loss: returns scalar",    aug_total.dim() == 0)
check("Augmented loss: has task_loss key", "task_loss" in aug_breakdown)
check("Augmented loss: has phys_total key","phys_total" in aug_breakdown)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2 — CV TRANSFORMER MODEL
# ═══════════════════════════════════════════════════════════════════════════
section("2. CV Transformer Model")

from models.cv_transformer import create_cv_transformer

model = create_cv_transformer("base")
model.eval()

n_params = sum(p.numel() for p in model.parameters())
check("CV Transformer: created successfully", model is not None)
check("CV Transformer: ~5.8M parameters",
      4_000_000 < n_params < 8_000_000, f"{n_params:,}")

# Forward pass
x = torch.randn(2, 1, 2000)
with torch.no_grad():
    out = model(x, task="all")

check("CV Transformer: forward pass succeeds", out is not None)
check("CV Transformer: mechanism output (B,5)",
      out["mechanism"].shape == (2, 5), str(out["mechanism"].shape))
check("CV Transformer: reversibility output (B,) or (B,1)",
      out["reversibility"].shape in [(2,), (2, 1)], str(out["reversibility"].shape))
check("CV Transformer: peaks output (B,10)",
      out["peaks"].shape == (2, 10), str(out["peaks"].shape))
check("CV Transformer: parameters output (B,5)",
      out["parameters"].shape == (2, 5), str(out["parameters"].shape))
check("CV Transformer: reversibility in [0,1]",
      bool((out["reversibility"] >= 0).all() and (out["reversibility"] <= 1).all()))
check("CV Transformer: no NaN in outputs",
      not any(torch.isnan(v).any() for v in out.values()))


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3 — ENSEMBLE MODEL
# ═══════════════════════════════════════════════════════════════════════════
section("3. CV Transformer Ensemble")

ENSEMBLE_DIR = ROOT / "models" / "cv_transformer_ensemble"

if ENSEMBLE_DIR.exists() and (ENSEMBLE_DIR / "model_0.pt").exists():
    from models.cv_transformer_ensemble import create_cv_transformer_ensemble

    ensemble = create_cv_transformer_ensemble(num_models=5, model_size="base")
    ensemble.load_ensemble(str(ENSEMBLE_DIR))
    ensemble.eval()

    check("Ensemble: loaded 5 models", len(ensemble.models) == 5, str(len(ensemble.models)))

    x = torch.randn(1, 1, 2000)
    with torch.no_grad():
        out = ensemble(x)

    check("Ensemble: forward pass succeeds", out is not None)
    check("Ensemble: reversibility present",  "reversibility" in out)
    check("Ensemble: mechanism present",       "mechanism" in out)

    # Check uncertainty fields
    has_uncertainty = any("uncertainty" in k for k in out.keys())
    check("Ensemble: uncertainty fields present", has_uncertainty,
          str([k for k in out.keys() if "uncertainty" in k]))

    rev = float(out["reversibility"].item())
    check("Ensemble: reversibility in [0,1]", 0 <= rev <= 1, f"{rev:.4f}")
else:
    print("  ⚠ Ensemble models not found — skipping (run train_ensemble.py first)")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4 — ANOMALY DETECTOR
# ═══════════════════════════════════════════════════════════════════════════
section("4. Anomaly Detector")

from models.anomaly_detector import CVAnomalyDetector

detector = CVAnomalyDetector(data_points=2000, latent_dim=64)
detector.eval()

n_params_ad = sum(p.numel() for p in detector.parameters())
check("Anomaly detector: created", detector is not None)
check("Anomaly detector: has parameters", n_params_ad > 0, f"{n_params_ad:,}")

# Forward pass
x_ad = torch.randn(2, 1, 2000)
with torch.no_grad():
    out_ad = detector(x_ad)

check("Anomaly detector: reconstruction present",       "reconstruction" in out_ad)
check("Anomaly detector: reconstruction_error present", "reconstruction_error" in out_ad)
check("Anomaly detector: is_anomaly present",           "is_anomaly" in out_ad)
check("Anomaly detector: anomaly_score present",        "anomaly_score" in out_ad)
check("Anomaly detector: reconstruction shape (2,1,2000)",
      out_ad["reconstruction"].shape == (2, 1, 2000), str(out_ad["reconstruction"].shape))
check("Anomaly detector: error shape (2,)",
      out_ad["reconstruction_error"].shape == (2,), str(out_ad["reconstruction_error"].shape))
check("Anomaly detector: error >= 0",
      bool((out_ad["reconstruction_error"] >= 0).all()))

# Test with trained weights if available
ANOMALY_PATH = ROOT / "models" / "anomaly_detector" / "anomaly_detector.pt"
if ANOMALY_PATH.exists():
    ckpt = torch.load(ANOMALY_PATH, map_location="cpu", weights_only=False)
    detector.load_state_dict(ckpt["model_state_dict"])
    if "threshold" in ckpt:
        detector.threshold.fill_(ckpt["threshold"])

    check("Anomaly detector: weights loaded",   True)
    check("Anomaly detector: threshold > 0",
          float(detector.threshold) > 0, f"{float(detector.threshold):.4f}")

    # Normal signal should have lower error than random noise
    normal_signal = torch.sin(torch.linspace(0, 4*math.pi, 2000)).unsqueeze(0).unsqueeze(0)
    noise_signal  = torch.randn(1, 1, 2000) * 10

    with torch.no_grad():
        out_normal = detector(normal_signal)
        out_noise  = detector(noise_signal)

    err_normal = float(out_normal["reconstruction_error"][0])
    err_noise  = float(out_noise["reconstruction_error"][0])
    check("Anomaly detector: noise has higher error than sine",
          err_noise > err_normal, f"noise={err_noise:.4f} > normal={err_normal:.4f}")
else:
    print("  ⚠ Trained anomaly detector not found — skipping weight tests")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5 — RAMAN MATERIAL IDENTIFIER
# ═══════════════════════════════════════════════════════════════════════════
section("5. Raman Material Identifier")

from models.raman_material_identifier import RamanMaterialIdentifier

DB_PATH = ROOT / "data" / "material_database" / "raman_materials.json"
if DB_PATH.exists():
    identifier = RamanMaterialIdentifier(database_path=str(DB_PATH))

    check("Raman identifier: loaded",
          len(identifier.materials) > 0, f"{len(identifier.materials)} materials")

    # Test graphene identification (G=1580, 2D=2700)
    graphene_peaks = [
        {"position_cm": 1582, "intensity": 1.0},
        {"position_cm": 2698, "intensity": 4.0},
    ]
    matches = identifier.identify_material(graphene_peaks, top_n=3, min_confidence=0.3)
    check("Raman: graphene peaks → match found",  len(matches) > 0)
    if matches:
        check("Raman: top match is graphene/carbon",
              "carbon" in matches[0].category.lower() or "graphene" in matches[0].name.lower(),
              f"top={matches[0].name}")
        check("Raman: confidence > 0.8",
              matches[0].confidence > 0.8, f"{matches[0].confidence:.3f}")

    # Test silicon (520 cm⁻¹)
    si_peaks = [{"position_cm": 520.5, "intensity": 1.0}]
    si_matches = identifier.identify_material(si_peaks, top_n=3, min_confidence=0.5)
    check("Raman: silicon peak → match found", len(si_matches) > 0)
    if si_matches:
        check("Raman: silicon identified",
              "silicon" in si_matches[0].name.lower() or "semiconductor" in si_matches[0].category.lower(),
              f"top={si_matches[0].name}")

    # Test empty peaks
    empty_matches = identifier.identify_material([], top_n=3)
    check("Raman: empty peaks → empty result", len(empty_matches) == 0)

    # Test search
    results = identifier.search_materials("graphene")
    check("Raman: search 'graphene' returns results", len(results) > 0, f"{len(results)} results")

    # Test statistics
    stats = identifier.get_statistics()
    check("Raman: statistics has total_materials", "total_materials" in stats)
    check("Raman: statistics has categories",       "categories" in stats)
    check("Raman: total_materials > 0",             stats["total_materials"] > 0)
else:
    print("  ⚠ Raman DB not found — skipping")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6 — PHYSICS LOSS ELECTROCHEMICAL CORRECTNESS
# ═══════════════════════════════════════════════════════════════════════════
section("6. Physics Loss — Electrochemical Correctness")

# Test Butler-Volmer: reversible system should have low BV penalty
# For reversible: ipa ≈ ipc → ratio ≈ 1
preds_rev = {
    "peaks":         torch.tensor([[1.0, -1.0, 0.3, -0.3, 0, 0, 0, 0, 0, 0]]),  # ipa=1, ipc=-1
    "reversibility": torch.tensor([0.95]),  # highly reversible
    "mechanism":     torch.randn(1, 5),
    "parameters":    torch.randn(1, 5),
}
preds_irrev = {
    "peaks":         torch.tensor([[2.0, -0.5, 0.3, -0.3, 0, 0, 0, 0, 0, 0]]),  # ipa=2, ipc=-0.5 (asymmetric)
    "reversibility": torch.tensor([0.95]),  # claims reversible but peaks are asymmetric
    "mechanism":     torch.randn(1, 5),
    "parameters":    torch.randn(1, 5),
}

bv_fn = PhysicsInformedLoss(lambda_bv=1.0, lambda_rs=0, lambda_nernst=0, lambda_charge=0)
loss_rev,   _ = bv_fn(preds_rev)
loss_irrev, _ = bv_fn(preds_irrev)

check("BV: symmetric peaks → lower penalty than asymmetric",
      loss_rev.item() < loss_irrev.item(),
      f"rev={loss_rev.item():.4f} < irrev={loss_irrev.item():.4f}")

# Test Randles-Ševčík: positive anodic peak current
preds_physical = {
    "peaks":         torch.tensor([[1.0, -1.0, 0, 0, 0, 0, 0, 0, 0, 0]]),  # ipa>0, ipc<0
    "reversibility": torch.tensor([0.5]),
    "mechanism":     torch.randn(1, 5),
    "parameters":    torch.randn(1, 5),
}
preds_unphysical = {
    "peaks":         torch.tensor([[-1.0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0]]),  # ipa<0 (wrong sign)
    "reversibility": torch.tensor([0.5]),
    "mechanism":     torch.randn(1, 5),
    "parameters":    torch.randn(1, 5),
}
rs_fn = PhysicsInformedLoss(lambda_bv=0, lambda_rs=1.0, lambda_nernst=0, lambda_charge=0)
loss_phys,   _ = rs_fn(preds_physical)
loss_unphys, _ = rs_fn(preds_unphysical)

check("RS: physical peak signs → lower penalty",
      loss_phys.item() < loss_unphys.item(),
      f"physical={loss_phys.item():.4f} < unphysical={loss_unphys.item():.4f}")

# Test charge conservation: sine wave should have near-zero charge
t = torch.linspace(0, 2 * math.pi, 2000)
v_sine = torch.sin(t).unsqueeze(0)
i_cosine = torch.cos(t).unsqueeze(0)  # ∫cos·d(sin) = ∫cos²dt ≠ 0 over full cycle
# But ∫i dE where E=sin(t) and i=cos(t): dE = cos(t)dt, so ∫cos²dt = π ≠ 0
# Use i = sin(t) for zero charge: ∫sin·d(sin) = ∫sin·cos dt = 0 over full cycle
i_zero_charge = torch.sin(t).unsqueeze(0)

charge_fn = PhysicsInformedLoss(lambda_bv=0, lambda_rs=0, lambda_nernst=0, lambda_charge=1.0)
preds_dummy = {"peaks": torch.zeros(1, 10), "reversibility": torch.tensor([0.5]),
               "mechanism": torch.zeros(1, 5), "parameters": torch.zeros(1, 5)}
loss_nonzero, _ = charge_fn(preds_dummy, v_sine, i_cosine)
loss_zero,    _ = charge_fn(preds_dummy, v_sine, i_zero_charge)

check("Charge: zero-charge signal → lower penalty",
      loss_zero.item() < loss_nonzero.item(),
      f"zero={loss_zero.item():.6f} < nonzero={loss_nonzero.item():.6f}")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7 — INTEGRATION: END-TO-END PREDICTION
# ═══════════════════════════════════════════════════════════════════════════
section("7. Integration — End-to-End Prediction")

# Simulate a CV curve (sine wave approximation)
t_cv = torch.linspace(0, 4 * math.pi, 2000)
voltage_cv = torch.sin(t_cv)
current_cv = 0.5 * torch.sin(t_cv + 0.3) + 0.1 * torch.randn(2000)

# Preprocess (normalize, reshape)
v_norm = (voltage_cv - voltage_cv.mean()) / (voltage_cv.std() + 1e-8)
c_norm = (current_cv - current_cv.mean()) / (current_cv.std() + 1e-8)
x_cv   = torch.stack([v_norm, c_norm], dim=-1).unsqueeze(0)  # (1, 2000, 2)

# Single model prediction
model_single = create_cv_transformer("base")
model_single.eval()

# The model expects (B, 1, N) or (B, N, 2) depending on implementation
# Try (B, 1, N) with current only
x_current = c_norm.unsqueeze(0).unsqueeze(0)  # (1, 1, 2000)
with torch.no_grad():
    try:
        out_single = model_single(x_current, task="all")
        check("Integration: single model prediction succeeds", True)
        check("Integration: reversibility in [0,1]",
              0 <= float(out_single["reversibility"].item()) <= 1,
              f"{float(out_single['reversibility'].item()):.4f}")
        check("Integration: mechanism has 5 classes",
              out_single["mechanism"].shape[-1] == 5)
    except Exception as e:
        check("Integration: single model prediction succeeds", False, str(e))

# Physics loss on prediction
try:
    phys_total, phys_bd = loss_fn(out_single, voltage_cv.unsqueeze(0), c_norm.unsqueeze(0))
    check("Integration: physics loss on prediction succeeds", True)
    check("Integration: physics loss is finite",
          math.isfinite(phys_total.item()), f"{phys_total.item():.4f}")
except Exception as e:
    check("Integration: physics loss on prediction succeeds", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8 — MODEL FILES EXIST
# ═══════════════════════════════════════════════════════════════════════════
section("8. Model Files — Existence & Integrity")

model_checks = {
    "Ensemble model_0.pt":    ROOT / "models/cv_transformer_ensemble/model_0.pt",
    "Ensemble model_4.pt":    ROOT / "models/cv_transformer_ensemble/model_4.pt",
    "Ensemble metadata.json": ROOT / "models/cv_transformer_ensemble/ensemble_metadata.json",
    "Anomaly detector.pt":    ROOT / "models/anomaly_detector/anomaly_detector.pt",
    "Attention summary.png":  ROOT / "models/cv_transformer/attention_visualizations/attention_summary.png",
}
for name, path in model_checks.items():
    check(f"File exists: {name}", path.exists())

# Check ensemble metadata
meta_path = ROOT / "models/cv_transformer_ensemble/ensemble_metadata.json"
if meta_path.exists():
    meta = json.loads(meta_path.read_text())
    check("Ensemble metadata: has val_losses",  "val_losses" in meta or "models" in meta)

# Check anomaly training results
results_path = ROOT / "models/anomaly_detector/training_results.json"
if results_path.exists():
    res = json.loads(results_path.read_text())
    check("Anomaly results: best_val_loss present", "best_val_loss" in res)
    check("Anomaly results: threshold present",     "threshold" in res)
    check("Anomaly results: threshold > 0",
          res.get("threshold", 0) > 0, f"{res.get('threshold'):.4f}")


# ═══════════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ═══════════════════════════════════════════════════════════════════════════
total  = len(_results)
passed = sum(1 for _, ok, _ in _results if ok)
failed = total - passed
pct    = 100 * passed / total if total else 0

print(f"\n{'='*65}")
print(f"  FINAL RESULTS")
print(f"{'='*65}")
print(f"  Passed:  {passed}/{total}  ({pct:.1f}%)")
print(f"  Failed:  {failed}")

if failed:
    print(f"\n  Failed tests:")
    for name, ok, detail in _results:
        if not ok:
            print(f"    ✗ {name}" + (f"  [{detail}]" if detail else ""))

print()
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
