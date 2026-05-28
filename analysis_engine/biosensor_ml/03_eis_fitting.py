"""
Script 03 — EIS Analysis
Robust parameter extraction using high-frequency intercept (Rs) and
semicircle apex method (Rct ≈ 2×|Z''_max|).
Adds PCA electrode fingerprinting.
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
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from config import DATA_PROC, DATA_FEAT, FIG_DIR, CSV_DIR, COLORS

ELECTRODE_ORDER = ["Bare GCE", "Fe2O3/GCE", "rGO/GCE", "FOG/GCE"]
PAPER_RCT = {"Bare GCE": 71500, "Fe2O3/GCE": 111800,
             "rGO/GCE": 842, "FOG/GCE": 216}


def extract_eis_params(freq, zreal, zimag):
    """
    Robust parameter extraction from EIS data.
    Rs  = Z' at highest frequency (HF real-axis intercept).
    Rct = 2 × max(-Z'') — valid for semicircle whose apex is captured.
    """
    idx_hf  = np.argmax(freq)
    Rs      = float(zreal[idx_hf])
    Rct     = float(2.0 * np.max(-zimag))    # zimag is negative, so -zimag > 0
    Zw_at1Hz = float(-zimag[np.argmin(freq)]) # Warburg contribution at 1 Hz
    sigma   = Zw_at1Hz / np.sqrt(2 * np.pi * 1.0)   # Warburg coefficient estimate
    return {"Rs_ohm": Rs, "Rct_ohm": Rct, "sigma_W": sigma}


def build_feature_matrix(eis_df):
    records, labels = [], []
    for el in ELECTRODE_ORDER:
        g   = eis_df[eis_df.electrode == el].sort_values("freq_Hz")
        zm  = np.log10(np.maximum(g.Zmag_ohm.values,  1e-3))
        ph  = g.phase_deg.values
        zr  = np.log10(np.maximum(g.Zreal_ohm.values, 1e-3))
        zi  = np.log10(np.maximum(-g.Zimag_ohm.values, 1e-3))
        records.append(np.concatenate([zm, ph, zr, zi]))
        labels.append(el)
    return np.array(records), labels


def plot_nyquist_bode(eis_df):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    ax_n, ax_bm, ax_bp = axes

    for el in ELECTRODE_ORDER:
        g   = eis_df[eis_df.electrode == el].sort_values("freq_Hz", ascending=False)
        fr  = g.freq_Hz.values
        zr  = g.Zreal_ohm.values
        zin = -g.Zimag_ohm.values
        zm  = g.Zmag_ohm.values
        ph  = g.phase_deg.values
        col = COLORS[el]

        ax_n.plot(zr, zin, "o-", color=col, ms=4, lw=1.2, label=el)
        ax_bm.semilogx(fr, 20*np.log10(zm), "o-", color=col, ms=3, lw=1.2, label=el)
        ax_bp.semilogx(fr, ph, "o-", color=col, ms=3, lw=1.2, label=el)

    ax_n.set_xlabel("Z' (Ω)"); ax_n.set_ylabel("−Z'' (Ω)")
    ax_n.set_title("(a) Nyquist"); ax_n.legend(fontsize=8)
    ax_bm.set_xlabel("Frequency (Hz)"); ax_bm.set_ylabel("|Z| (dBΩ)")
    ax_bm.set_title("(b) Bode — Magnitude"); ax_bm.legend(fontsize=8)
    ax_bp.set_xlabel("Frequency (Hz)"); ax_bp.set_ylabel("Phase (°)")
    ax_bp.set_title("(c) Bode — Phase"); ax_bp.legend(fontsize=8)
    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_EIS_full.{ext}")
    plt.close(fig)

    # Zoom on low-impedance electrodes
    fig2, ax2 = plt.subplots(figsize=(6, 5))
    for el in ["rGO/GCE", "FOG/GCE"]:
        g  = eis_df[eis_df.electrode == el].sort_values("freq_Hz", ascending=False)
        ax2.plot(g.Zreal_ohm.values, -g.Zimag_ohm.values, "o-",
                 color=COLORS[el], ms=5, lw=1.4, label=el)
    ax2.set_xlabel("Z' (Ω)"); ax2.set_ylabel("−Z'' (Ω)")
    ax2.set_title("Nyquist — rGO/GCE & FOG/GCE (zoom)")
    ax2.legend(fontsize=9)
    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig2.savefig(FIG_DIR / f"Fig_EIS_zoom.{ext}")
    plt.close(fig2)

    # CSV exports
    csv_rows = []
    for el in ELECTRODE_ORDER:
        g = eis_df[eis_df.electrode == el].sort_values("freq_Hz", ascending=False)
        for _, row in g.iterrows():
            csv_rows.append({"electrode": el, "freq_Hz": row.freq_Hz,
                              "Zreal_ohm": row.Zreal_ohm, "Zimag_ohm": row.Zimag_ohm,
                              "neg_Zimag_ohm": -row.Zimag_ohm,
                              "Zmag_dB": 20*np.log10(row.Zmag_ohm),
                              "phase_deg": row.phase_deg})
    pd.DataFrame(csv_rows).to_csv(CSV_DIR / "eis_nyquist_bode.csv", index=False)


def plot_rct_bar(params_df):
    names = params_df["electrode"].tolist()
    rcts  = params_df["Rct_ohm"].tolist()
    paper = [PAPER_RCT[n] for n in names]
    cols  = [COLORS[n] for n in names]
    x     = np.arange(len(names))
    w     = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    b1 = ax.bar(x - w/2, rcts,  w, color=cols, label="This work",
                edgecolor="white")
    b2 = ax.bar(x + w/2, paper, w, color=cols, label="Paper (ZView)",
                alpha=0.45, edgecolor="black", linewidth=0.8)
    ax.set_yscale("log")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=10)
    ax.set_ylabel("R$_{ct}$ (Ω, log scale)")
    ax.set_title("Charge-transfer resistance — extracted vs. paper")
    ax.legend()
    for bar, v in zip(b1, rcts):
        ax.text(bar.get_x() + bar.get_width()/2, v * 1.5,
                f"{v:.0f}", ha="center", fontsize=8)
    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_EIS_Rct.{ext}")
    plt.close(fig)

    pd.DataFrame({"electrode": names, "Rct_this_work_ohm": rcts,
                  "Rct_paper_ohm": paper}).to_csv(
        CSV_DIR / "eis_rct_comparison.csv", index=False)


def plot_pca(X, labels):
    scaler = StandardScaler()
    Xp     = PCA(n_components=2).fit_transform(scaler.fit_transform(X))
    evr    = PCA(n_components=2).fit(scaler.fit_transform(X)).explained_variance_ratio_

    fig, ax = plt.subplots(figsize=(6, 5))
    for i, el in enumerate(labels):
        ax.scatter(Xp[i, 0], Xp[i, 1], color=COLORS[el], s=200,
                   zorder=4, edgecolors="black", linewidths=0.8)
        ax.annotate(el, (Xp[i, 0], Xp[i, 1]),
                    textcoords="offset points", xytext=(6, 4), fontsize=9)
    ax.set_xlabel(f"PC1 ({evr[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({evr[1]*100:.1f}%)")
    ax.set_title("PCA of EIS spectra — electrode fingerprinting")
    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_EIS_PCA.{ext}")
    plt.close(fig)

    pd.DataFrame({"electrode": labels, "PC1": Xp[:, 0], "PC2": Xp[:, 1]}).to_csv(
        CSV_DIR / "eis_pca.csv", index=False)
    return evr


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("STEP 03 — EIS Analysis")
    print("=" * 60)

    eis_df  = pd.read_csv(DATA_PROC / "eis_clean.csv")
    records = []

    for el in ELECTRODE_ORDER:
        g   = eis_df[eis_df.electrode == el].sort_values("freq_Hz", ascending=False)
        p   = extract_eis_params(g.freq_Hz.values, g.Zreal_ohm.values,
                                  g.Zimag_ohm.values)
        p["electrode"] = el
        records.append(p)

    params_df = pd.DataFrame(records)
    params_df.to_csv(DATA_FEAT / "eis_parameters.csv", index=False)

    print("\nExtracted EIS parameters (apex method):")
    print(f"  {'Electrode':14s} {'Rs (Ω)':>10} {'Rct (Ω)':>12} "
          f"{'Paper Rct':>12} {'Error%':>8}")
    print("  " + "-" * 56)
    for _, row in params_df.iterrows():
        el   = row["electrode"]
        pval = PAPER_RCT[el]
        err  = abs(row["Rct_ohm"] - pval) / pval * 100
        flag = "✓" if err < 30 else "⚠"
        print(f"  {el:14s} {row['Rs_ohm']:>10.1f} {row['Rct_ohm']:>12.1f} "
              f"{pval:>12d} {err:>7.1f}% {flag}")

    # Verify ordering
    r = params_df.set_index("electrode")["Rct_ohm"]
    ok = r["FOG/GCE"] < r["rGO/GCE"] < r["Bare GCE"]
    print(f"\n  Rct ordering FOG < rGO < Bare: {'✓' if ok else '⚠'}")

    # PCA
    X, labels = build_feature_matrix(eis_df)
    evr = plot_pca(X, labels)
    print(f"\nPCA: PC1={evr[0]*100:.1f}%, PC2={evr[1]*100:.1f}% "
          f"({sum(evr)*100:.1f}% total variance explained)")

    plot_nyquist_bode(eis_df)
    plot_rct_bar(params_df)

    params_df.to_csv(CSV_DIR / "eis_parameters.csv", index=False)
    print("\n✓ EIS analysis complete → reports/figures/  |  CSVs → reports/plot_csvs/")
