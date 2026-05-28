"""
Calibration Curve Analyzer
============================
Automatically computes calibration curves, LOD, LOQ, and sensitivity
from cleaned DPV/CV concentration series data.

Author: VidyuthLabs
Date: May 6, 2026
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def _parse_conc(label: str) -> Optional[float]:
    """Parse concentration value from label string, normalise to µM or µL."""
    label = label.strip()
    if label.lower() == "buffer":
        return 0.0
    m = re.search(r"([\d.]+)\s*(µM|µm|uM|nM|mM|µL|µl|uL|ul|ml|mL)", label, re.IGNORECASE)
    if not m:
        return None
    val  = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "nm":
        val /= 1000
    elif unit == "mm":
        val *= 1000
    return val


def _find_peak(potential: np.ndarray, current: np.ndarray) -> Tuple[float, float]:
    """Find the peak (max |current|) in a voltammogram."""
    idx = int(np.argmax(np.abs(current)))
    return float(potential[idx]), float(current[idx])


def _to_uA(values: np.ndarray) -> np.ndarray:
    """Convert current array to µA if it appears to be in A."""
    if np.abs(values).max() < 0.01:
        return values * 1e6
    return values   # already µA


def analyze_calibration(json_path: str | Path) -> Dict:
    """
    Analyze a cleaned concentration series JSON file.

    Returns calibration results with sensitivity, LOD, LOQ, R².
    """
    data   = json.loads(Path(json_path).read_text(encoding="utf-8"))
    series = data.get("series_clean") or data.get("series", {})

    if not series:
        return {"error": "No series data found"}

    # ── Build peak table ──────────────────────────────────────────────────
    peak_table = {}
    for label, s in series.items():
        pot  = np.array(s["potential_v"])
        cur  = np.array(s["current_a"])
        e_pk, i_pk = _find_peak(pot, cur)
        conc = _parse_conc(label)
        peak_table[label] = {
            "concentration": conc,
            "e_peak_v":      round(e_pk, 5),
            "i_peak_a":      round(i_pk, 12),
        }

    # ── Buffer baseline ───────────────────────────────────────────────────
    buffer_i = None
    for label, row in peak_table.items():
        if label.lower() == "buffer" or row["concentration"] == 0.0:
            buffer_i = row["i_peak_a"]
            break

    # ── Net current ───────────────────────────────────────────────────────
    for row in peak_table.values():
        raw_net = row["i_peak_a"] - (buffer_i or 0.0)
        row["i_net_a"] = round(raw_net, 12)

    # ── Filter valid concentration points ─────────────────────────────────
    valid = [
        (row["concentration"], row["i_net_a"])
        for row in peak_table.values()
        if row["concentration"] is not None and row["concentration"] > 0
    ]

    if len(valid) < 3:
        return {
            "peak_table": peak_table,
            "error": "Not enough concentration points for calibration (need ≥ 3)",
        }

    valid.sort(key=lambda x: x[0])
    concs     = np.array([v[0] for v in valid])
    inets_raw = np.array([v[1] for v in valid])
    inets     = _to_uA(inets_raw)   # ensure µA

    # ── Find best linear range (R² > 0.99) ───────────────────────────────
    best_r2    = 0.0
    best_range = (float(concs[0]), float(concs[-1]))
    best_fit   = None

    for i in range(len(concs)):
        for j in range(i + 2, len(concs) + 1):
            c_sub = concs[i:j]
            i_sub = inets[i:j]
            coeffs = np.polyfit(c_sub, i_sub, 1)
            i_pred = np.polyval(coeffs, c_sub)
            ss_res = np.sum((i_sub - i_pred) ** 2)
            ss_tot = np.sum((i_sub - i_sub.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            if r2 > best_r2 and len(c_sub) >= 3:
                best_r2    = r2
                best_range = (float(c_sub[0]), float(c_sub[-1]))
                best_fit   = coeffs

    if best_fit is None:
        best_fit = np.polyfit(concs, inets, 1)

    slope     = float(best_fit[0])
    intercept = float(best_fit[1])

    # ── LOD / LOQ ─────────────────────────────────────────────────────────
    i_pred    = np.polyval(best_fit, concs)
    residuals = inets - i_pred
    sigma     = float(np.std(residuals))
    lod       = 3  * sigma / abs(slope) if slope != 0 else None
    loq       = 10 * sigma / abs(slope) if slope != 0 else None

    return {
        "source":                    str(json_path),
        "peak_table":                peak_table,
        "linear_range":              best_range,
        "sensitivity_uA_per_uM":     round(slope, 6),
        "intercept_uA":              round(intercept, 6),
        "r_squared":                 round(best_r2, 6),
        "lod_uM":                    round(lod, 4) if lod else None,
        "loq_uM":                    round(loq, 4) if loq else None,
        "equation":                  f"I (µA) = {slope:.4f}·C + {intercept:.4f}",
        "n_points":                  len(valid),
    }


if __name__ == "__main__":
    import argparse, sys
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Calibration Curve Analyzer")
    parser.add_argument("json_file", help="Path to *_all.json from autonomous cleaner")
    args = parser.parse_args()

    result = analyze_calibration(args.json_file)

    print("=" * 60)
    print("CALIBRATION CURVE ANALYSIS")
    print("=" * 60)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"\nEquation:    {result['equation']}")
    print(f"R²:          {result['r_squared']:.6f}")
    print(f"Sensitivity: {result['sensitivity_uA_per_uM']:.4f} µA/µM")
    print(f"Linear range:{result['linear_range'][0]:.1f} – {result['linear_range'][1]:.1f} µM")
    print(f"LOD:         {result['lod_uM']} µM")
    print(f"LOQ:         {result['loq_uM']} µM")

    print(f"\n{'Concentration':<15} {'E_peak (V)':>12} {'I_peak':>14} {'I_net':>12}")
    print("-" * 58)
    for label, row in result["peak_table"].items():
        c    = row['concentration']
        ep   = row['e_peak_v']
        ip   = row['i_peak_a']
        inet = row['i_net_a']
        # Display in µA if values are small
        if abs(ip) < 0.01:
            ip_str   = f"{ip*1e6:.4f} µA"
            inet_str = f"{inet*1e6:.4f} µA"
        else:
            ip_str   = f"{ip:.4f} µA"
            inet_str = f"{inet:.4f} µA"
        print(f"{label:<15} {ep:>12.5f} {ip_str:>14} {inet_str:>12}")
