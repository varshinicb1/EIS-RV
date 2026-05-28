"""
Script 02 — DPV Feature Extraction
Extracts 7 electrochemical descriptors from each DPV sweep via
baseline-corrected peak analysis. Integrates the dedicated calibration curve
(10-700 µM) as the primary analytical calibration, with the DPV scans
(1-70 µM) for ML feature extraction and low-range sensitivity.
Saves 800-dpi figures + Origin-compatible CSV for every plot.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d
from scipy.integrate import trapezoid
from config import (DATA_PROC, DATA_FEAT, FIG_DIR, CSV_DIR,
                    UA_PEAK_V, GCE_AREA_CM2, CONC_CMAP)

CMAP = matplotlib.colormaps[CONC_CMAP]


# ── Baseline correction ────────────────────────────────────────────────────────
def linear_baseline(potential, current,
                    pre_window=(0.370, 0.430),
                    post_window=(0.555, 0.625)):
    mask_pre  = (potential >= pre_window[0]) & (potential <= pre_window[1])
    mask_post = (potential >= post_window[0]) & (potential <= post_window[1])
    mask      = mask_pre | mask_post
    if mask.sum() < 4:
        idx  = np.concatenate([np.arange(6), np.arange(len(potential)-6,
                                                        len(potential))])
        mask = np.zeros(len(potential), dtype=bool)
        mask[idx] = True
    coeffs = np.polyfit(potential[mask], current[mask], 1)
    return np.polyval(coeffs, potential), coeffs


# ── Feature extraction per sweep ───────────────────────────────────────────────
def extract_features(potential, current, smooth=True):
    pot = np.asarray(potential, dtype=float)
    cur = np.asarray(current,   dtype=float)
    order = np.argsort(pot)
    pot, cur = pot[order], cur[order]

    cur_sm = savgol_filter(cur, window_length=7, polyorder=3) \
             if (smooth and len(cur) >= 9) else cur.copy()

    baseline, bl_coeffs = linear_baseline(pot, cur_sm)
    cur_bc = cur_sm - baseline

    interp_raw = interp1d(pot, cur, kind="cubic",
                           bounds_error=False, fill_value="extrapolate")
    Ip_raw_475 = float(interp_raw(UA_PEAK_V))

    ua_mask  = (pot >= 0.430) & (pot <= 0.540)
    if ua_mask.sum() < 3:
        ua_mask = np.ones(len(pot), dtype=bool)
    local_idx = int(np.argmax(cur_bc[ua_mask]))
    peak_idx  = int(np.where(ua_mask)[0][local_idx])
    Ip_bc     = float(cur_bc[peak_idx])
    Ep        = float(pot[peak_idx])

    half  = Ip_bc / 2.0
    above = np.where(cur_bc >= half)[0]
    FWHM  = float(pot[above[-1]] - pot[above[0]]) \
            if len(above) >= 2 else float("nan")

    auc_m = (pot >= Ep - 0.08) & (pot <= Ep + 0.08)
    AUC   = float(trapezoid(np.maximum(cur_bc[auc_m], 0), pot[auc_m]))

    pre_m = pot <= 0.425
    noise = float(np.std(cur_sm[pre_m])) if pre_m.sum() > 2 else float("nan")
    SNR   = float(Ip_bc / noise) if (noise > 0) else float("nan")
    bl_at_Ep = float(np.polyval(bl_coeffs, Ep))

    return {
        "Ip_corrected":   Ip_bc,
        "Ip_raw_475V":    Ip_raw_475,
        "Ep_V":           Ep,
        "FWHM_V":         FWHM,
        "AUC":            AUC,
        "SNR":            SNR,
        "baseline_noise": noise,
        "bl_at_Ep":       bl_at_Ep,
    }


# ── LoD / LoQ from buffer baseline noise ─────────────────────────────────────
def compute_lod_loq(features_df, slope):
    """
    σ_blank = baseline_noise of the buffer (0 µM) sweep only.
    Falls back to linear-fit residuals if no buffer noise available.
    Using buffer-only noise avoids inflating sigma with signal from low-[UA] sweeps.
    """
    buf = features_df[features_df.concentration_uM == 0]
    if len(buf) > 0 and not np.isnan(buf["baseline_noise"].values[0]):
        sigma = float(buf["baseline_noise"].values[0])
    else:
        # fallback: residual std of UA calibration fit
        ua   = features_df[features_df.concentration_uM > 0]
        x, y = ua.concentration_uM.values, ua.Ip_raw_475V.values
        yhat = np.polyval(np.polyfit(x, y, 1), x)
        sigma = float(np.std(y - yhat, ddof=1))
    return 3.3 * sigma / abs(slope), 10.0 * sigma / abs(slope)


# ── Figure + CSV: DPV overview ─────────────────────────────────────────────────
def plot_all(df_dpv, feat_df, slope, intercept, r2,
             calib_df, calib_slope, calib_int, calib_r2):
    fig, axes = plt.subplots(1, 4, figsize=(20, 4.5))

    ua_df  = df_dpv[df_dpv.concentration_uM > 0]
    buf_df = df_dpv[df_dpv.concentration_uM == 0]
    concs  = sorted(ua_df.concentration_uM.unique())
    n      = len(concs)

    # Panel A: raw DPV voltammograms
    ax = axes[0]
    bg = buf_df.groupby("potential_V")["current_uA"].mean()
    ax.plot(bg.index, bg.values, color="#888888", lw=1.2, ls="--", label="Buffer")
    for i, c in enumerate(concs):
        g = ua_df[ua_df.concentration_uM == c].groupby(
            "potential_V")["current_uA"].mean()
        ax.plot(g.index, g.values, color=CMAP(i / (n - 1)), lw=1.4,
                label=f"{int(c) if c == int(c) else c} µM")
    ax.axvline(UA_PEAK_V, color="crimson", ls=":", lw=1.0, alpha=0.7)
    ax.set_xlabel("Potential (V vs Ag/AgCl)")
    ax.set_ylabel("Current (µA)")
    ax.set_title("(a) DPV — UA at FOG/GCE")
    ax.legend(fontsize=6.5, ncol=2, loc="upper left")

    # Panel B: baseline-corrected peaks
    ax2 = axes[1]
    csv_bc_rows = []
    for i, c in enumerate(concs):
        g   = df_dpv[df_dpv.concentration_uM == c].sort_values("potential_V")
        pot = g.potential_V.values
        cur = g.current_uA.values
        sm  = savgol_filter(cur, 7, 3) if len(cur) >= 9 else cur
        bl, _ = linear_baseline(pot, sm)
        bc = sm - bl
        ax2.plot(pot, bc, color=CMAP(i / (n - 1)), lw=1.4,
                 label=f"{int(c) if c == int(c) else c} µM")
        for pv, bv in zip(pot, bc):
            csv_bc_rows.append({"concentration_uM": c, "potential_V": pv,
                                 "current_bc_uA": bv})
    ax2.axhline(0, color="#333", lw=0.7, ls="--")
    ax2.axvline(UA_PEAK_V, color="crimson", ls=":", lw=1.0, alpha=0.7)
    ax2.set_xlabel("Potential (V vs Ag/AgCl)")
    ax2.set_ylabel("ΔI (µA, baseline corrected)")
    ax2.set_title("(b) Baseline-corrected DPV peaks")
    ax2.legend(fontsize=6.5, ncol=2)

    # Panel C: DPV scan calibration (1-70 µM)
    ax3 = axes[2]
    feat_ua = feat_df[feat_df.concentration_uM > 0].sort_values("concentration_uM")
    x       = feat_ua.concentration_uM.values
    y       = feat_ua.Ip_raw_475V.values
    x_fit   = np.linspace(0, x.max() * 1.05, 200)
    y_fit   = slope * x_fit + intercept
    ax3.scatter(x, y, color="#2BA84A", s=55, zorder=4, label="DPV scans (1-70 µM)",
                edgecolors="#1a6b2e", linewidths=0.5)
    ax3.plot(x_fit, y_fit, "r-", lw=1.8,
             label=f"y = {slope:.5f}x + {intercept:.4f}\nR² = {r2:.4f}")
    ax3.set_xlabel("[UA] (µM)")
    ax3.set_ylabel("I$_p$ at 0.475 V (µA)")
    ax3.set_title("(c) DPV calibration (1–70 µM)")
    ax3.legend(fontsize=8)

    # Panel D: dedicated calibration curve (10-700 µM)
    ax4 = axes[3]
    xc  = calib_df.concentration_uM.values
    yc  = calib_df.current_uA.values
    xc_fit = np.linspace(0, xc.max() * 1.05, 200)
    yc_fit = calib_slope * xc_fit + calib_int
    ax4.scatter(xc, yc, color="#E05C3A", s=55, zorder=4,
                edgecolors="#8b3a26", linewidths=0.5, label="Calib. curve (10-700 µM)")
    ax4.plot(xc_fit, yc_fit, "b-", lw=1.8,
             label=f"y = {calib_slope:.6f}x + {calib_int:.4f}\nR² = {calib_r2:.4f}")
    ax4.set_xlabel("[UA] (µM)")
    ax4.set_ylabel("Current (µA)")
    ax4.set_title("(d) Dedicated calibration curve")
    ax4.legend(fontsize=8)

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_DPV_overview.{ext}")
    plt.close(fig)

    # CSV exports
    raw_csv = []
    for c in [0.0] + concs:
        g = df_dpv[df_dpv.concentration_uM == c].groupby("potential_V")["current_uA"].mean()
        for pv, iv in zip(g.index, g.values):
            raw_csv.append({"concentration_uM": c, "potential_V": pv, "current_uA": iv})
    pd.DataFrame(raw_csv).to_csv(CSV_DIR / "dpv_raw_voltammograms.csv", index=False)
    pd.DataFrame(csv_bc_rows).to_csv(CSV_DIR / "dpv_baseline_corrected.csv", index=False)

    # Calibration CSV
    cal_dpv = pd.DataFrame({"concentration_uM": x, "Ip_raw_475V_uA": y,
                             "fit_uA": np.polyval([slope, intercept], x)})
    cal_dpv.to_csv(CSV_DIR / "dpv_calibration_1to70uM.csv", index=False)

    cal_ded = pd.DataFrame({"concentration_uM": xc, "current_uA": yc,
                             "fit_uA": np.polyval([calib_slope, calib_int], xc)})
    cal_ded.to_csv(CSV_DIR / "calib_curve_10to700uM.csv", index=False)


# ── Figure + CSV: DPV corrected (zoomed) ──────────────────────────────────────
def plot_corrected(df_dpv, feat_df, slope, intercept, r2):
    """Larger 2-panel: overlay + calibration — publication main figure."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    ua_df = df_dpv[df_dpv.concentration_uM > 0]
    concs = sorted(ua_df.concentration_uM.unique())
    n     = len(concs)

    ax = axes[0]
    csv_rows = []
    for i, c in enumerate(concs):
        g   = ua_df[ua_df.concentration_uM == c].sort_values("potential_V")
        pot = g.potential_V.values
        cur = g.current_uA.values
        sm  = savgol_filter(cur, 7, 3) if len(cur) >= 9 else cur
        bl, _ = linear_baseline(pot, sm)
        bc = sm - bl
        mask = (pot >= 0.38) & (pot <= 0.62)
        ax.plot(pot[mask], bc[mask], color=CMAP(i / (n-1)), lw=1.6,
                label=f"{int(c) if c==int(c) else c} µM")
        for pv, bv in zip(pot[mask], bc[mask]):
            csv_rows.append({"concentration_uM": c, "potential_V": pv,
                              "current_bc_uA": bv})
    ax.axhline(0, color="#333", lw=0.7, ls="--")
    ax.axvline(UA_PEAK_V, color="crimson", ls=":", lw=1.2, alpha=0.8,
               label=f"UA peak {UA_PEAK_V} V")
    ax.set_xlabel("Potential (V vs Ag/AgCl)")
    ax.set_ylabel("ΔI$_p$ (µA)")
    ax.set_title("(a) Baseline-corrected DPV — UA at FOG/GCE")
    ax.legend(fontsize=7.5, ncol=2)

    ax2 = axes[1]
    feat_ua = feat_df[feat_df.concentration_uM > 0].sort_values("concentration_uM")
    x       = feat_ua.concentration_uM.values
    y       = feat_ua.Ip_corrected.values
    x_fit   = np.linspace(0, x.max() * 1.05, 200)
    y_fit   = np.polyval(np.polyfit(x, y, 1), x_fit)
    r2_bc   = float(1 - np.sum((y - np.polyval(np.polyfit(x, y, 1), x))**2) /
                    np.sum((y - y.mean())**2))
    ax2.scatter(x, y, color="#2BA84A", s=60, zorder=4, edgecolors="#1a6b2e", lw=0.5)
    ax2.plot(x_fit, y_fit, "r-", lw=1.8,
             label=f"Slope = {np.polyfit(x,y,1)[0]:.5f} µA/µM\nR² = {r2_bc:.4f}")
    ax2.set_xlabel("[UA] (µM)")
    ax2.set_ylabel("ΔI$_p$ (µA, baseline-corrected)")
    ax2.set_title("(b) Baseline-corrected peak vs [UA]")
    ax2.legend(fontsize=9)

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_DPV_corrected.{ext}")
    plt.close(fig)

    pd.DataFrame(csv_rows).to_csv(CSV_DIR / "dpv_corrected_zoom.csv", index=False)
    pd.DataFrame({"concentration_uM": x, "Ip_corrected_uA": y}).to_csv(
        CSV_DIR / "dpv_corrected_calibration.csv", index=False)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("STEP 02 — DPV Feature Extraction")
    print("=" * 60)

    df_dpv  = pd.read_csv(DATA_PROC / "dpv_clean.csv")
    calib_df = pd.read_csv(DATA_PROC / "calib_curve.csv")
    concs   = sorted(df_dpv.concentration_uM.unique())

    records = []
    for c in concs:
        g    = df_dpv[df_dpv.concentration_uM == c].sort_values("potential_V")
        feat = extract_features(g.potential_V.values, g.current_uA.values)
        feat["concentration_uM"] = c
        records.append(feat)

    feat_df = pd.DataFrame(records)
    feat_df.to_csv(DATA_FEAT / "dpv_features.csv", index=False)

    print("\nFeature table (DPV scans, µA units):")
    print(feat_df[["concentration_uM", "Ip_corrected", "Ip_raw_475V",
                   "Ep_V", "FWHM_V", "AUC", "SNR"]].to_string(index=False))

    # ── DPV scan calibration (1-70 µM) ────────────────────────────────────────
    feat_ua = feat_df[feat_df.concentration_uM > 0]
    x       = feat_ua.concentration_uM.values
    y       = feat_ua.Ip_raw_475V.values
    coeffs  = np.polyfit(x, y, 1)
    slope, intercept = float(coeffs[0]), float(coeffs[1])
    yhat    = np.polyval(coeffs, x)
    r2      = float(1 - np.sum((y - yhat)**2) / np.sum((y - y.mean())**2))

    LoD, LoQ   = compute_lod_loq(feat_df, slope)
    sensitivity = abs(slope) / GCE_AREA_CM2

    # ── Dedicated calibration curve (10-700 µM) ────────────────────────────────
    xc      = calib_df.concentration_uM.values
    yc      = calib_df.current_uA.values
    cc      = np.polyfit(xc, yc, 1)
    calib_slope, calib_int = float(cc[0]), float(cc[1])
    yc_hat  = np.polyval(cc, xc)
    calib_r2 = float(1 - np.sum((yc - yc_hat)**2) / np.sum((yc - yc.mean())**2))
    calib_sensitivity = abs(calib_slope) / GCE_AREA_CM2

    # LoD from dedicated curve using buffer noise from DPV scan (correct approach:
    # blank noise ÷ calibration slope)
    buf_row = feat_df[feat_df.concentration_uM == 0]
    if len(buf_row) > 0 and not np.isnan(buf_row["baseline_noise"].values[0]):
        sigma_calib = float(buf_row["baseline_noise"].values[0])
    else:
        sigma_calib = float(np.std(yc - yc_hat, ddof=1))
    LoD_calib = 3.3 * sigma_calib / abs(calib_slope)
    LoQ_calib = 10.0 * sigma_calib / abs(calib_slope)

    plot_all(df_dpv, feat_df, slope, intercept, r2,
             calib_df, calib_slope, calib_int, calib_r2)
    plot_corrected(df_dpv, feat_df, slope, intercept, r2)

    print(f"\n── DPV Scan Calibration (1–70 µM) ─────────────────────")
    print(f"  Equation   : I = {slope:.6f}·[UA] + {intercept:.5f}  (µA/µM)")
    print(f"  R²         : {r2:.4f}")
    print(f"  LoD        : {LoD:.4f} µM  ({LoD*1000:.2f} nM)")
    print(f"  LoQ        : {LoQ:.4f} µM  ({LoQ*1000:.2f} nM)")
    print(f"  Sensitivity: {sensitivity:.6f} µA·µM⁻¹·cm⁻²")

    print(f"\n── Dedicated Calibration Curve (10–700 µM) ─────────────")
    print(f"  Equation   : I = {calib_slope:.6f}·[UA] + {calib_int:.5f}  (µA/µM)")
    print(f"  R²         : {calib_r2:.4f}")
    print(f"  LoD        : {LoD_calib:.4f} µM  ({LoD_calib*1000:.2f} nM)")
    print(f"  LoQ        : {LoQ_calib:.4f} µM  ({LoQ_calib*1000:.2f} nM)")
    print(f"  Sensitivity: {calib_sensitivity:.6f} µA·µM⁻¹·cm⁻²")

    print(f"\n── Validation vs manuscript ─────────────────────────────")
    print(f"  Paper: y=0.0047x+0.24, R²=0.9924, LoD=0.307 µM (instrument units)")
    r2_status = "✓" if r2 >= 0.990 else "⚠ check peak extraction"
    print(f"  DPV R² status: {r2_status}")

    summary = {
        "slope_dpv_uA_per_uM":        slope,
        "intercept_dpv_uA":           intercept,
        "R2_dpv":                     r2,
        "LoD_dpv_uM":                 LoD,
        "LoQ_dpv_uM":                 LoQ,
        "sensitivity_dpv_uA_uM_cm2":  sensitivity,
        "slope_calib_uA_per_uM":      calib_slope,
        "intercept_calib_uA":         calib_int,
        "R2_calib":                   calib_r2,
        "LoD_calib_uM":               LoD_calib,
        "LoQ_calib_uM":               LoQ_calib,
        "sensitivity_calib_uA_uM_cm2":calib_sensitivity,
        "GCE_area_cm2":               GCE_AREA_CM2,
        # legacy keys for downstream scripts
        "sensitivity_per_uM_cm2":     sensitivity,
        "slope":                      slope,
        "intercept":                  intercept,
        "R2":                         r2,
        "LoD_uM":                     LoD,
        "LoQ_uM":                     LoQ,
    }
    pd.Series(summary).to_csv(DATA_FEAT / "dpv_calibration_summary.csv")
    print("\n✓ Figures → reports/figures/  |  CSVs → reports/plot_csvs/")
    print("✓ Feature table → data/features/dpv_features.csv")
