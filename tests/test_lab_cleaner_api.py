"""
Lab Cleaner API — Route & Logic Tests
=======================================
Tests the lab_cleaner_routes endpoints and calibration logic
without needing a running server (direct function calls).

Run:
    py -3.12 tests/test_lab_cleaner_api.py
"""

import sys, json, math, asyncio, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "backend" / "ml"))

_results = []
def check(name, cond, detail=""):
    status = "✅ PASS" if cond else "❌ FAIL"
    _results.append((name, cond, detail))
    print(f"  {status}  {name}" + (f"  [{detail}]" if detail else ""))
    return cond

def section(t):
    print(f"\n{'='*60}\n  {t}\n{'='*60}")

# ── 1. Calibration endpoint logic ─────────────────────────────────────────
section("1. Calibration Logic (direct)")

from src.backend.ml.data_collection.calibration_analyzer import (
    analyze_calibration, _parse_conc, _find_peak, _to_uA
)

# Test with actual cleaned data
CLEANED_DPV = ROOT / "data/cleaned/fog/DPV FOG/DPV FOG_Sheet3_all.json"
if CLEANED_DPV.exists():
    result = analyze_calibration(CLEANED_DPV)
    check("Calibration: no error",           "error" not in result)
    check("Calibration: R² > 0.99",          result.get("r_squared", 0) > 0.99,
          f"R²={result.get('r_squared')}")
    check("Calibration: sensitivity > 0",    result.get("sensitivity_uA_per_uM", 0) > 0)
    check("Calibration: LOD computed",       result.get("lod_uM") is not None)
    check("Calibration: LOQ > LOD",
          (result.get("loq_uM") or 0) > (result.get("lod_uM") or 0))
    check("Calibration: equation present",   "equation" in result)
    check("Calibration: peak_table present", "peak_table" in result)
    check("Calibration: 9 non-buffer pts",   result.get("n_points") == 9,
          str(result.get("n_points")))
    check("Calibration: linear_range tuple", len(result.get("linear_range", [])) == 2)
else:
    print("  ⚠ Cleaned DPV not found — run cleaner first")

# Test with Gomutra
CLEANED_GOM = ROOT / "data/cleaned/fog/GOMUTRA CONCENTRATION STUDIES/GOMUTRA CONCENTRATION STUDIES_Sheet1_all.json"
if CLEANED_GOM.exists():
    result_g = analyze_calibration(CLEANED_GOM)
    check("Gomutra: R² > 0.99",  result_g.get("r_squared", 0) > 0.99,
          f"R²={result_g.get('r_squared')}")
    check("Gomutra: 11 pts",     result_g.get("n_points") == 11,
          str(result_g.get("n_points")))

# ── 2. Calibration with synthetic data ───────────────────────────────────
section("2. Calibration — Synthetic Data")

# Perfect linear calibration: I = 2*C + 0.1
concs  = [1, 5, 10, 20, 30, 40, 50]
inets  = [2*c + 0.1 + np.random.normal(0, 0.05) for c in concs]

# Build fake series dict
fake_series = {}
for c, inet in zip(concs, inets):
    label = f"{c} µM"
    # Create 10-point voltammogram with peak at inet
    pot = np.linspace(0.3, 0.7, 10).tolist()
    cur = [0.1] * 5 + [inet] + [0.1] * 4
    fake_series[label] = {"potential_v": pot, "current_a": cur}
fake_series["buffer"] = {"potential_v": np.linspace(0.3, 0.7, 10).tolist(),
                          "current_a": [0.1] * 10}

# Write to temp JSON
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump({"series_clean": fake_series}, f)
    tmp_path = f.name

result_synth = analyze_calibration(tmp_path)
Path(tmp_path).unlink()

check("Synthetic: no error",        "error" not in result_synth)
check("Synthetic: R² > 0.99",       result_synth.get("r_squared", 0) > 0.99,
      f"R²={result_synth.get('r_squared')}")
check("Synthetic: sensitivity ≈ 2", abs(result_synth.get("sensitivity_uA_per_uM", 0) - 2.0) < 0.5,
      f"sens={result_synth.get('sensitivity_uA_per_uM'):.3f}")
check("Synthetic: 7 non-buffer pts", result_synth.get("n_points") == 7)

# ── 3. Autonomous Cleaner — API-level ────────────────────────────────────
section("3. Autonomous Cleaner — File Processing")

from src.backend.ml.data_collection.autonomous_data_cleaner import (
    AutonomousDataCleaner, FormatDetector, CHIEISParser, EISCleaner
)

FOG_DIR = ROOT / "Lab data/fog differet data/fog differet data"
if FOG_DIR.exists():
    with tempfile.TemporaryDirectory() as tmpdir:
        cleaner = AutonomousDataCleaner(output_dir=tmpdir)
        summary = cleaner.clean_directory(FOG_DIR)

        check("Cleaner: 6 files",     summary["total_files"] == 6)
        check("Cleaner: all success", summary["success"] == 6)
        check("Cleaner: summary.json", (Path(tmpdir) / "cleaning_summary.json").exists())

        # Verify EIS output
        eis_csvs = list(Path(tmpdir).rglob("*eis_fog*.csv"))
        check("Cleaner: EIS FOG CSV",  len(eis_csvs) > 0)
        if eis_csvs:
            import csv
            rows = list(csv.reader(eis_csvs[0].read_text().splitlines()))
            check("Cleaner: EIS header correct",
                  rows[0] == ["freq_hz", "zreal_ohm", "zimag_ohm", "zmag_ohm", "phase_deg"])
            check("Cleaner: EIS 61 rows", len(rows) - 1 == 61, str(len(rows)-1))
            # Physical validity
            freqs  = [float(r[0]) for r in rows[1:]]
            zreals = [float(r[1]) for r in rows[1:]]
            zimajs = [float(r[2]) for r in rows[1:]]
            check("Cleaner: EIS freqs positive",  all(f > 0 for f in freqs))
            check("Cleaner: EIS Zreal positive",  all(z > 0 for z in zreals))
            check("Cleaner: EIS Zimag negative",  all(z < 0 for z in zimajs))
            check("Cleaner: EIS sorted desc",     freqs == sorted(freqs, reverse=True))

        # Verify DPV output
        dpv_csvs = list(Path(tmpdir).rglob("*Sheet3*10_µM*.csv"))
        check("Cleaner: DPV 10µM CSV", len(dpv_csvs) > 0)
        if dpv_csvs:
            rows = list(csv.reader(dpv_csvs[0].read_text().splitlines()))
            check("Cleaner: DPV header", rows[0] == ["potential_v", "current_a"])
            check("Cleaner: DPV 53 rows", len(rows) - 1 == 53, str(len(rows)-1))
            # No NaN
            check("Cleaner: DPV no NaN",
                  not any("nan" in r[0].lower() or "nan" in r[1].lower() for r in rows[1:]))
else:
    print("  ⚠ FOG directory not found")

# ── 4. EIS Quality Metrics ────────────────────────────────────────────────
section("4. EIS Quality Metrics")

import openpyxl
EIS_FOG = ROOT / "Lab data/fog differet data/fog differet data/EIS FOG.xlsx"
if EIS_FOG.exists():
    wb = openpyxl.load_workbook(EIS_FOG, data_only=True)
    parsed = CHIEISParser().parse(wb.active)
    cleaned = EISCleaner().clean(parsed)
    qr = cleaned["quality_report"]

    check("EIS FOG: Rs ≈ 3.5 Ω",   abs(qr["rs_ohm"] - 3.5) < 0.5,   f"Rs={qr['rs_ohm']}")
    check("EIS FOG: Rct ≈ 106 Ω",  abs(qr["rct_ohm"] - 106) < 10,   f"Rct={qr['rct_ohm']}")
    check("EIS FOG: 61 clean rows", qr["cleaned_rows"] == 61)
    check("EIS FOG: no issues",     len(qr.get("issues", [])) == 0,
          str(qr.get("issues", [])))

# ── 5. Route Imports ──────────────────────────────────────────────────────
section("5. Route Module Imports")

try:
    from src.backend.api.v1_routes.lab_cleaner_routes import router
    check("lab_cleaner_routes: imports OK", True)
    route_paths = [r.path for r in router.routes]
    check("Route: /clean exists",       any("/clean" in p for p in route_paths),
          str(route_paths))
    check("Route: /calibration exists", any("/calibration" in p for p in route_paths))
    check("Route: /ai-analyze exists",  any("/ai-analyze" in p for p in route_paths))
    check("Route: /status exists",      any("/status" in p for p in route_paths))
except Exception as e:
    check("lab_cleaner_routes: imports OK", False, str(e))

try:
    from src.backend.api.v1_routes.raman_material_routes import raman_material_bp
    check("raman_material_routes: imports OK", True)
    raman_paths = [r.path for r in raman_material_bp.routes]
    check("Raman route: /identify exists",
          any("/identify" in p for p in raman_paths), str(raman_paths))
    check("Raman route: /materials exists",
          any("/materials" in p for p in raman_paths))
    check("Raman route: /database/stats exists",
          any("stats" in p for p in raman_paths))
except Exception as e:
    check("raman_material_routes: imports OK", False, str(e))

# ── Final ─────────────────────────────────────────────────────────────────
total_t = len(_results)
passed  = sum(1 for _, ok, _ in _results if ok)
failed  = total_t - passed
print(f"\n{'='*60}\n  RESULTS: {passed}/{total_t}  ({100*passed/total_t:.1f}%)\n{'='*60}")
if failed:
    for name, ok, detail in _results:
        if not ok:
            print(f"  ✗ {name}" + (f"  [{detail}]" if detail else ""))
if __name__ == "__main__":
    import sys; sys.exit(0 if failed == 0 else 1)
