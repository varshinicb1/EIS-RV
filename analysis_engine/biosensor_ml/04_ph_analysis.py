"""
Script 04 — pH Study Analysis
Robust separation of anodic sweeps, polynomial-fit optimization,
and Nernstian analysis of peak potential shift.
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
from config import DATA_PROC, DATA_FEAT, FIG_DIR, CSV_DIR, UA_PEAK_V

UA_WINDOW = (0.350, 0.680)


def get_anodic_sweep(ph_group_df):
    """
    Split 200-row CV into two 100-row sweeps, return the ascending one.
    Detection: check if FIRST HALF of data (by row_idx) has ascending potential.
    """
    df_idx = ph_group_df.sort_values("row_idx")
    half        = len(df_idx) // 2
    first_half  = df_idx.iloc[:half]
    second_half = df_idx.iloc[half:]

    fp = first_half.potential_V.values
    is_asc = float(fp[-1]) > float(fp[0])

    anodic = first_half if is_asc else second_half
    return anodic.sort_values("potential_V")


def extract_anodic_peak(anodic_df):
    mask = ((anodic_df.potential_V >= UA_WINDOW[0]) &
            (anodic_df.potential_V <= UA_WINDOW[1]))
    g = anodic_df[mask] if mask.sum() >= 5 else anodic_df
    pot = g.potential_V.values
    cur = g.current_A.values
    if len(cur) >= 9:
        wl = min(7, len(cur) - (1 - len(cur) % 2))
        cur = savgol_filter(cur, wl, polyorder=3)
    idx = int(np.argmax(cur))
    return float(cur[idx]), float(pot[idx])


def plot_ph_analysis(ph_vals, ipas_uA, eps_mV, ph_fit, ipa_fit,
                     slope_mVpH, r2_nernst, anodic_data, ph_df):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    cmap = matplotlib.colormaps["coolwarm"]
    n    = len(ph_vals)

    # Panel A: Anodic sweeps
    ax = axes[0]
    for i, ph in enumerate(ph_vals):
        adf = anodic_data[ph]
        mask = ((adf.potential_V >= 0.2) & (adf.potential_V <= 0.8))
        ad = adf[mask] if mask.sum() > 5 else adf
        ax.plot(ad.potential_V.values, ad.current_A.values * 1e6,
                color=cmap(i / max(n-1, 1)), lw=1.4, label=f"pH {int(ph)}")
    ax.axvline(UA_PEAK_V, color="crimson", ls=":", lw=1.0, alpha=0.7)
    ax.set_xlabel("Potential (V vs Ag/AgCl)")
    ax.set_ylabel("Current (µA)")
    ax.set_title("(a) Anodic CV — pH 4–9 at FOG/GCE")
    ax.legend(fontsize=8, ncol=2)

    # Panel B: Ipa vs pH with spline fit
    ax2 = axes[1]
    ax2.bar(ph_vals, ipas_uA, color=[cmap(i/max(n-1,1)) for i in range(n)],
            edgecolor="white", linewidth=0.8, alpha=0.8)
    ax2.plot(ph_fit, ipa_fit, "k-", lw=2.0, label="Spline fit")
    opt_ph = float(ph_fit[np.argmax(ipa_fit)])
    ax2.axvline(opt_ph, color="navy", ls="--", lw=1.2,
                label=f"Opt. pH ≈ {opt_ph:.1f}")
    ax2.set_xlabel("pH")
    ax2.set_ylabel("I$_{pa}$ (µA)")
    ax2.set_title("(b) I$_{pa}$ vs pH")
    ax2.legend(fontsize=8)

    # Panel C: Ep vs pH — Nernstian
    ax3 = axes[2]
    ph_arr = np.array(ph_vals, dtype=float)
    ep_arr = np.array(eps_mV, dtype=float)
    # Use only the points that shift monotonically (exclude outliers)
    diff    = np.diff(ep_arr)
    consistent = np.concatenate([[True], diff < 20])  # exclude big upward jumps
    ph_c    = ph_arr[consistent]
    ep_c    = ep_arr[consistent]

    ax3.scatter(ph_arr, ep_arr, color="#E05C3A", s=80, zorder=4,
                edgecolors="#8b3a26", linewidths=0.7, label="All data")
    if len(ph_c) >= 3:
        coeffs = np.polyfit(ph_c, ep_c, 1)
        ph_fit_ep = np.linspace(ph_vals[0]-0.1, ph_vals[-1]+0.1, 100)
        ax3.plot(ph_fit_ep, np.polyval(coeffs, ph_fit_ep), "b-", lw=1.8,
                 label=f"Slope = {slope_mVpH:.1f} mV/pH\nR² = {r2_nernst:.3f}")
    ax3.axhline(-59 + ep_arr[3], color="gray", ls=":", lw=1.0,
                alpha=0.7)  # visual guide
    ax3.set_xlabel("pH")
    ax3.set_ylabel("E$_p$ (mV vs Ag/AgCl)")
    ax3.set_title("(c) E$_p$ vs pH — Nernstian analysis")
    ax3.legend(fontsize=8)

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_pH_analysis.{ext}")
    plt.close(fig)

    # CSV exports
    csv_anodic = []
    for ph in ph_vals:
        adf = anodic_data[ph]
        mask = (adf.potential_V >= 0.2) & (adf.potential_V <= 0.8)
        ad = adf[mask] if mask.sum() > 5 else adf
        for _, row in ad.iterrows():
            csv_anodic.append({"pH": ph, "potential_V": row.potential_V,
                                "current_uA": row.current_A * 1e6})
    pd.DataFrame(csv_anodic).to_csv(CSV_DIR / "ph_anodic_sweeps.csv", index=False)

    pd.DataFrame({"pH": ph_vals, "Ipa_uA": ipas_uA, "Ep_mV": eps_mV}).to_csv(
        CSV_DIR / "ph_peak_summary.csv", index=False)
    pd.DataFrame({"pH_fine": ph_fit, "Ipa_spline_uA": ipa_fit}).to_csv(
        CSV_DIR / "ph_spline_fit.csv", index=False)


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 04 — pH Study Analysis")
    print("=" * 60)

    ph_df   = pd.read_csv(DATA_PROC / "ph_clean.csv")
    ph_vals = sorted(ph_df.pH.unique())

    ipas, eps, anodic_data = [], [], {}
    print(f"\n  {'pH':>4}  {'Ipa (µA)':>12}  {'Ep (mV)':>10}  1st-half direction")
    print("  " + "-" * 50)

    for ph in ph_vals:
        g  = ph_df[ph_df.pH == ph]
        an = get_anodic_sweep(g)
        Ipa, Ep = extract_anodic_peak(an)
        ipas.append(Ipa)
        eps.append(Ep)
        anodic_data[ph] = an
        # Detect 1st half direction
        fp = g.sort_values("row_idx").iloc[:100].potential_V.values
        dir_str = "anodic" if fp[-1] > fp[0] else "cathodic"
        print(f"  {int(ph):>4}  {Ipa*1e6:>12.4f}  {Ep*1000:>10.1f}  "
              f"1st half = {dir_str}")

    ipas_uA = [v * 1e6 for v in ipas]
    eps_mV  = [v * 1000 for v in eps]

    # Spline fit for smooth pH optimum
    ph_arr_f = np.array(ph_vals, dtype=float)
    ipa_arr_f = np.array(ipas_uA, dtype=float)
    spl      = UnivariateSpline(ph_arr_f, ipa_arr_f, s=0, k=min(3, len(ph_vals)-1))
    ph_fine  = np.linspace(ph_vals[0], ph_vals[-1], 300)
    ipa_fine = spl(ph_fine)
    opt_ph   = float(ph_fine[np.argmax(ipa_fine)])

    # Verify with raw data
    raw_opt_ph = ph_vals[int(np.argmax(ipas_uA))]
    print(f"\n── pH Optimisation ──────────────────────────────────")
    print(f"  Raw maximum Ipa at pH {raw_opt_ph} ({max(ipas_uA):.4f} µA)")
    print(f"  Spline optimum   pH {opt_ph:.1f}")
    print(f"  Paper: pH 8  {'✓' if raw_opt_ph == 8 else '⚠'}")

    # Nernstian slope — use monotonically decreasing Ep region
    ep_arr = np.array(eps_mV)
    ph_arr = np.array(ph_vals, dtype=float)
    # Exclude pH 9 if it jumps up (anomalous)
    diff   = np.diff(ep_arr)
    good   = np.concatenate([[True], diff < 50])
    ph_c, ep_c = ph_arr[good], ep_arr[good]
    if len(ph_c) >= 3:
        coeffs     = np.polyfit(ph_c, ep_c, 1)
        slope_mVpH = float(coeffs[0])
        yhat       = np.polyval(coeffs, ph_c)
        r2         = float(1 - np.sum((ep_c - yhat)**2) /
                           np.sum((ep_c - ep_c.mean())**2)) if len(ph_c) > 2 \
                     else float("nan")
    else:
        coeffs = np.polyfit(ph_arr, ep_arr, 1)
        slope_mVpH = float(coeffs[0])
        r2 = float("nan")

    print(f"\n── Nernstian Analysis ───────────────────────────────")
    print(f"  Ep vs pH slope = {slope_mVpH:.1f} mV/pH")
    print(f"  Expected (2e⁻/2H⁺) = −59 mV/pH")
    nernst_ok = "✓" if abs(slope_mVpH - (-59)) < 25 else \
                "⚠ (possible mixed mechanism or outlier at pH 9)"
    print(f"  Status: {nernst_ok}")
    if not np.isnan(r2):
        print(f"  R² = {r2:.3f}")

    plot_ph_analysis(ph_vals, ipas_uA, eps_mV, ph_fine, ipa_fine,
                     slope_mVpH, r2 if not np.isnan(r2) else 0,
                     anodic_data, ph_df)

    pd.DataFrame({"pH": ph_vals, "Ipa_uA": ipas_uA,
                  "Ep_mV": eps_mV}).to_csv(DATA_FEAT / "ph_features.csv",
                                            index=False)
    pd.Series({"optimal_pH": raw_opt_ph, "slope_mVpH": slope_mVpH,
               "R2_Nernst": r2}).to_csv(DATA_FEAT / "ph_summary.csv")
    print("\n✓ pH analysis complete → reports/figures/  |  CSVs → reports/plot_csvs/")
