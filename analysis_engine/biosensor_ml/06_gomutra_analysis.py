"""
Script 06 — Gomutra Real-Sample Analysis
Extracts anodic UA peak from each Gomutra-spiked CV, maps to concentration
via the DPV calibration, estimates recovery and matrix effect.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
from scipy.interpolate import UnivariateSpline
from config import DATA_PROC, DATA_FEAT, FIG_DIR, CSV_DIR, UA_PEAK_V, COLORS

UA_WIN = (0.350, 0.680)


def get_anodic_sweep(df_vol):
    """Return the ascending (anodic) half of a CV stored as 200 sequential rows."""
    df_s   = df_vol.sort_values("row_idx")
    half   = len(df_s) // 2
    first  = df_s.iloc[:half]
    second = df_s.iloc[half:]
    fp     = first.potential_V.values
    is_asc = float(fp[-1]) > float(fp[0])
    return (first if is_asc else second).sort_values("potential_V")


def extract_peak(an_df, window=UA_WIN):
    mask = (an_df.potential_V >= window[0]) & (an_df.potential_V <= window[1])
    g    = an_df[mask] if mask.sum() >= 5 else an_df
    pot  = g.potential_V.values
    cur  = g.current_A.values
    if len(cur) >= 9:
        wl  = min(7, len(cur) - (1 - len(cur) % 2))
        cur = savgol_filter(cur, wl, polyorder=3)
    idx = int(np.argmax(cur))
    return float(cur[idx]), float(pot[idx])


def load_calibration():
    """Load DPV calibration slope (current_raw / µM)."""
    cal = pd.read_csv(DATA_FEAT / "dpv_calibration_summary.csv",
                      index_col=0, header=None).squeeze()
    return float(cal.loc["slope"]), float(cal.loc["intercept"])


def plot_gomutra_cv(vol_vals, anodic_data):
    cmap = matplotlib.colormaps["plasma"]
    n    = len(vol_vals)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    ax = axes[0]
    for i, vol in enumerate(vol_vals):
        adf  = anodic_data[vol]
        mask = (adf.potential_V >= 0.2) & (adf.potential_V <= 0.8)
        ad   = adf[mask] if mask.sum() > 5 else adf
        lbl  = "Buffer" if vol == 0 else f"{int(vol)} µL"
        ax.plot(ad.potential_V.values, ad.current_A.values * 1e6,
                color=cmap(i / max(n-1, 1)), lw=1.2, label=lbl)
    ax.axvline(UA_PEAK_V, color="crimson", ls=":", lw=1.0, alpha=0.7)
    ax.set_xlabel("Potential (V vs Ag/AgCl)")
    ax.set_ylabel("Current (µA)")
    ax.set_title("(a) Anodic CV — Gomutra volumes at FOG/GCE")
    ax.legend(fontsize=6.5, ncol=2)

    ax2 = axes[1]
    non_buf = [(v, anodic_data[v]) for v in vol_vals if v > 0]
    vols_nb = [v for v, _ in non_buf]
    ipas_nb = []
    for vol, adf in non_buf:
        Ipa, _ = extract_peak(adf)
        ipas_nb.append(Ipa * 1e6)
    # spline for smooth trend
    if len(vols_nb) >= 4:
        spl = UnivariateSpline(vols_nb, ipas_nb, s=0, k=min(3, len(vols_nb)-1))
        v_fine = np.linspace(vols_nb[0], vols_nb[-1], 300)
        ax2.plot(v_fine, spl(v_fine), "k-", lw=1.8, label="Spline fit")
    ax2.scatter(vols_nb, ipas_nb, color="#2BA84A", s=70, zorder=4,
                edgecolors="#1a6b2e", lw=0.7, label="Measured")
    ax2.set_xlabel("Gomutra volume (µL)")
    ax2.set_ylabel("$I_{pa}$ (µA)")
    ax2.set_title("(b) $I_{pa}$ vs Gomutra volume")
    ax2.legend(fontsize=9)

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_Gomutra_CV.{ext}")
    plt.close(fig)

    csv_rows = []
    for i, vol in enumerate(vol_vals):
        adf  = anodic_data[vol]
        mask = (adf.potential_V >= 0.2) & (adf.potential_V <= 0.8)
        ad   = adf[mask] if mask.sum() > 5 else adf
        for _, row in ad.iterrows():
            csv_rows.append({"volume_uL": vol, "potential_V": row.potential_V,
                              "current_uA": row.current_A * 1e6})
    pd.DataFrame(csv_rows).to_csv(CSV_DIR / "gomutra_anodic_sweeps.csv", index=False)


def plot_recovery(vol_vals_nb, ipas_uA_nb, concs_pred, dpv_slope, dpv_int):
    """Calibration transfer and recovery plot."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    ax = axes[0]
    x_fit = np.linspace(0, max(ipas_uA_nb)*1.1, 200)
    # map µA back to instrument current units (DPV calibration is in raw units)
    # Note: Gomutra current is in A (physical), DPV was in instrument units
    # We report Ipa directly and compare relative to buffer
    ax.scatter(vol_vals_nb, ipas_uA_nb, color="#E05C3A", s=80, zorder=4,
               edgecolors="#8b3a26", lw=0.7, label="$I_{pa}$ (µA)")
    ax.set_xlabel("Gomutra volume (µL)")
    ax.set_ylabel("$I_{pa}$ (µA)")
    ax.set_title("(a) Anodic peak current vs Gomutra volume")
    ax.legend(fontsize=9)

    ax2 = axes[1]
    # Recovery relative to buffer (volume 0)
    ax2.bar(vol_vals_nb, concs_pred, color="#3A7EC0", edgecolor="white", lw=0.8)
    ax2.set_xlabel("Gomutra volume (µL)")
    ax2.set_ylabel("Predicted ΔI$_{pa}$ (µA, above buffer)")
    ax2.set_title("(b) Signal increase above buffer baseline")

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_Gomutra_recovery.{ext}")
    plt.close(fig)

    pd.DataFrame({"volume_uL": vol_vals_nb, "Ipa_uA": ipas_uA_nb,
                  "delta_Ipa_uA": concs_pred}).to_csv(
        CSV_DIR / "gomutra_recovery.csv", index=False)


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 06 — Gomutra Real-Sample Analysis")
    print("=" * 60)

    gom_df   = pd.read_csv(DATA_PROC / "gomutra_clean.csv")
    vol_vals = sorted(gom_df.volume_uL.unique())

    ipas, eps, anodic_data = [], [], {}
    buf_ipa = None

    print(f"\n  {'Volume (µL)':>12}  {'Ipa (µA)':>12}  {'Ep (mV)':>10}  "
          f"{'ΔIpa vs buf (µA)':>18}")
    print("  " + "-" * 60)

    for vol in vol_vals:
        g  = gom_df[gom_df.volume_uL == vol]
        an = get_anodic_sweep(g)
        Ipa, Ep = extract_peak(an)
        ipas.append(Ipa)
        eps.append(Ep)
        anodic_data[vol] = an
        if vol == 0:
            buf_ipa = Ipa
        delta = (Ipa - buf_ipa) * 1e6 if buf_ipa is not None else float("nan")
        print(f"  {'Buffer' if vol==0 else str(int(vol)):>12}  "
              f"{Ipa*1e6:>12.4f}  {Ep*1000:>10.1f}  {delta:>18.4f}")

    ipas_uA = [v * 1e6 for v in ipas]
    eps_mV  = [v * 1000 for v in eps]
    buf_ipa_uA = buf_ipa * 1e6

    # Signal above buffer
    delta_ipa = [v - buf_ipa_uA for v in ipas_uA]

    vol_vals_nb  = [v for v in vol_vals if v > 0]
    ipas_uA_nb   = [ipas_uA[i] for i, v in enumerate(vol_vals) if v > 0]
    delta_ipa_nb = [delta_ipa[i] for i, v in enumerate(vol_vals) if v > 0]
    eps_mV_nb    = [eps_mV[i] for i, v in enumerate(vol_vals) if v > 0]

    # Peak volume — optimal Gomutra volume
    opt_idx = int(np.argmax(ipas_uA_nb))
    opt_vol = vol_vals_nb[opt_idx]
    max_ipa = ipas_uA_nb[opt_idx]
    print(f"\n── Optimal Gomutra volume: {int(opt_vol)} µL  (Ipa = {max_ipa:.4f} µA)")

    # Gomutra UA calibration: linear fit of ΔIpa vs volume
    vols_arr  = np.array(vol_vals_nb, dtype=float)
    delta_arr = np.array(delta_ipa_nb, dtype=float)
    # Only use the monotonically increasing region (up to peak)
    good_mask = vols_arr <= opt_vol
    if good_mask.sum() >= 3:
        coeffs_g = np.polyfit(vols_arr[good_mask], delta_arr[good_mask], 1)
        yhat_g   = np.polyval(coeffs_g, vols_arr[good_mask])
        r2_g     = float(1 - np.sum((delta_arr[good_mask] - yhat_g)**2) /
                         np.sum((delta_arr[good_mask] - delta_arr[good_mask].mean())**2))
        slope_g  = float(coeffs_g[0])  # µA/µL
        print(f"\n── Linear range (0–{int(opt_vol)} µL) ──────────────────────")
        print(f"  ΔIpa = {slope_g:.5f} × Vol + {float(coeffs_g[1]):.5f}")
        print(f"  R² = {r2_g:.4f}")
    else:
        r2_g = slope_g = float("nan")
        print("\n  Insufficient points for linear fit in increasing region")

    # Saturation / matrix effect analysis
    print(f"\n── Matrix Effect Analysis ─────────────────────────────")
    print(f"  Buffer baseline  Ipa = {buf_ipa_uA:.4f} µA")
    print(f"  Max signal gain  ΔIpa = {max(delta_ipa_nb):.4f} µA "
          f"at {int(opt_vol)} µL")
    # Signal at 100 µL (paper's reported volume if available)
    v100_arr = [v for v in vol_vals_nb if int(v) == 100]
    if v100_arr:
        idx100   = vol_vals_nb.index(v100_arr[0])
        delta100 = delta_ipa_nb[idx100]
        print(f"  ΔIpa at 100 µL  = {delta100:.4f} µA")

    # Sensitivity: µA per µL of gomutra
    print(f"  Sensitivity     = {slope_g:.5f} µA/µL  (linear region)")

    # Save features
    out_df = pd.DataFrame({
        "volume_uL":   vol_vals,
        "Ipa_uA":      ipas_uA,
        "Ep_mV":       eps_mV,
        "delta_Ipa_uA": delta_ipa,
    })
    out_df.to_csv(DATA_FEAT / "gomutra_features.csv", index=False)

    summary = {
        "buffer_Ipa_uA":   buf_ipa_uA,
        "opt_volume_uL":   opt_vol,
        "max_delta_Ipa_uA": max(delta_ipa_nb),
        "linear_slope_uA_per_uL": slope_g,
        "linear_R2":       r2_g,
        "n_volumes":       len(vol_vals_nb),
    }
    pd.Series(summary).to_csv(DATA_FEAT / "gomutra_summary.csv")

    plot_gomutra_cv(vol_vals, anodic_data)
    plot_recovery(vol_vals_nb, ipas_uA_nb, delta_ipa_nb, None, None)

    out_df.to_csv(CSV_DIR / "gomutra_features.csv", index=False)
    print("\n✓ Gomutra analysis complete → reports/figures/  |  CSVs → reports/plot_csvs/")
