"""
Script 07 — SHAP Explainability for ML Concentration Model
Uses the best-performing model (Ridge α=1) and a tree-based model
(Random Forest) for SHAP analysis. Generates publication-quality
waterfall, summary, and dependence plots.
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
import shap
import joblib
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import r2_score
from config import DATA_FEAT, FIG_DIR, CSV_DIR, MODELS_DIR

FEATURES  = ["Ip_raw_475V", "Ip_corrected", "AUC", "FWHM_V"]
FEAT_NICE = ["$I_p$ (raw)", "$I_p$ (corr.)", "AUC", "FWHM"]
TARGET    = "concentration_uM"


def shap_linear(X_sc, y, feat_names):
    """SHAP for Ridge — exact (LinearExplainer)."""
    ridge = Ridge(alpha=1.0)
    ridge.fit(X_sc, y)
    explainer = shap.LinearExplainer(ridge, X_sc)
    shap_vals = explainer(X_sc)
    return ridge, shap_vals


def shap_tree(X_sc, y, feat_names):
    """SHAP for RF — exact (TreeExplainer)."""
    rf = RandomForestRegressor(n_estimators=500, max_depth=3,
                               min_samples_leaf=2, random_state=42)
    rf.fit(X_sc, y)
    explainer = shap.TreeExplainer(rf)
    shap_vals = explainer(X_sc)
    return rf, shap_vals


def plot_shap_summary(shap_values, feat_nice, concs, title, out_stem):
    """Summary dot plot (beeswarm-style) using matplotlib."""
    vals = shap_values.values          # (n_samples, n_features)
    n, f = vals.shape
    feat_order = np.argsort(np.abs(vals).mean(axis=0))[::-1]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Panel A — mean |SHAP| bar
    ax = axes[0]
    mean_abs = np.abs(vals).mean(axis=0)
    sorted_idx = np.argsort(mean_abs)
    y_pos = np.arange(f)
    ax.barh(y_pos, mean_abs[sorted_idx], color="#3A7EC0", edgecolor="white")
    ax.set_yticks(y_pos)
    ax.set_yticklabels([feat_nice[i] for i in sorted_idx], fontsize=10)
    ax.set_xlabel("Mean |SHAP value| (µM)")
    ax.set_title(f"(a) Feature importance — {title}")

    # Panel B — dot plot (beeswarm approximation)
    ax2 = axes[1]
    cmap = matplotlib.colormaps["coolwarm"]
    X_data = shap_values.data

    for k, fi in enumerate(feat_order):
        x_vals = vals[:, fi]
        f_vals = X_data[:, fi]
        f_norm = (f_vals - f_vals.min()) / (np.ptp(f_vals) + 1e-12)
        y_jitter = k + np.random.default_rng(42).uniform(-0.2, 0.2, n)
        ax2.scatter(x_vals, y_jitter, c=[cmap(v) for v in f_norm],
                    s=50, alpha=0.85, zorder=3)

    ax2.set_yticks(np.arange(f))
    ax2.set_yticklabels([feat_nice[i] for i in feat_order], fontsize=10)
    ax2.axvline(0, color="gray", lw=0.8)
    ax2.set_xlabel("SHAP value (µM)")
    ax2.set_title(f"(b) SHAP beeswarm — {title}")
    sm = plt.cm.ScalarMappable(cmap="coolwarm",
                                norm=plt.Normalize(0, 1))
    plt.colorbar(sm, ax=ax2, label="Feature value (low → high)", shrink=0.7)

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"{out_stem}.{ext}")
    plt.close(fig)
    return mean_abs


def plot_shap_dependence(shap_values, feat_nice, primary_feat_idx,
                         concs, out_stem):
    """SHAP dependence plot for the primary feature vs concentration."""
    vals   = shap_values.values
    X_data = shap_values.data

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    cmap = matplotlib.colormaps["plasma"]
    c_norm = (concs - concs.min()) / (np.ptp(concs) + 1e-12)

    for k, fi in enumerate([primary_feat_idx, 1]):  # Ip_raw + Ip_corrected
        ax = axes[k]
        sc = ax.scatter(X_data[:, fi], vals[:, fi],
                        c=[cmap(v) for v in c_norm], s=80, zorder=4,
                        edgecolors="black", lw=0.4)
        ax.axhline(0, color="gray", lw=0.8, ls="--")
        ax.set_xlabel(feat_nice[fi])
        ax.set_ylabel(f"SHAP value for {feat_nice[fi]} (µM)")
        ax.set_title(f"({'ab'[k]}) SHAP dependence — {feat_nice[fi]}")
        plt.colorbar(plt.cm.ScalarMappable(
            cmap="plasma", norm=plt.Normalize(concs.min(), concs.max())),
            ax=ax, label="[UA] (µM)", shrink=0.7)

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"{out_stem}.{ext}")
    plt.close(fig)


def plot_waterfall_grid(shap_values, feat_nice, concs, out_stem):
    """Waterfall-style bar chart for each sample."""
    vals    = shap_values.values
    base    = float(shap_values.base_values[0]) \
              if hasattr(shap_values, "base_values") else 0.0
    n, f    = vals.shape
    nrow    = int(np.ceil(n / 3))
    fig, axes = plt.subplots(nrow, 3, figsize=(14, 4.5 * nrow))
    axes = np.array(axes).ravel()

    colors = ["#E05C3A" if v > 0 else "#3A7EC0" for v in [1, -1]]

    for i in range(n):
        ax   = axes[i]
        fv   = vals[i]
        sort_idx = np.argsort(np.abs(fv))[::-1]
        y_pos    = np.arange(f)
        cols     = ["#E05C3A" if v > 0 else "#3A7EC0" for v in fv[sort_idx]]
        ax.barh(y_pos, fv[sort_idx], color=cols, edgecolor="white", lw=0.5)
        ax.set_yticks(y_pos)
        ax.set_yticklabels([feat_nice[j] for j in sort_idx], fontsize=8)
        ax.set_xlabel("SHAP value (µM)", fontsize=8)
        ax.set_title(f"[UA] = {int(concs[i])} µM", fontsize=9)
        ax.axvline(0, color="gray", lw=0.7)

    for i in range(n, len(axes)):
        axes[i].set_visible(False)

    plt.suptitle("SHAP Waterfall — Individual Predictions", fontsize=12)
    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"{out_stem}.{ext}")
    plt.close(fig)


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 07 — SHAP Explainability")
    print("=" * 60)

    feat_df = pd.read_csv(DATA_FEAT / "dpv_features.csv")
    ua_df   = feat_df[feat_df[TARGET] > 0].copy().reset_index(drop=True)
    X_raw   = ua_df[FEATURES].values.astype(float)
    y       = ua_df[TARGET].values.astype(float)
    concs   = y.copy()

    sc      = StandardScaler()
    X_sc    = sc.fit_transform(X_raw)

    print(f"\n  Samples  : {len(y)}")
    print(f"  Features : {FEATURES}")

    # ── Ridge SHAP ────────────────────────────────────────────────────────────
    print("\n── Ridge (α=1) SHAP ─────────────────────────────────────")
    ridge, shap_ridge = shap_linear(X_sc, y, FEATURES)
    y_pred_r = ridge.predict(X_sc)
    r2_r = float(r2_score(y, y_pred_r))
    print(f"  Training R² = {r2_r:.4f}")

    # Give SHAP values access to original feature values for display
    shap_ridge.data    = X_sc   # scaled values (consistent with explainer)
    shap_ridge.feature_names = FEAT_NICE

    imp_ridge = plot_shap_summary(shap_ridge, FEAT_NICE, concs,
                                   "Ridge α=1", "Fig_SHAP_ridge_summary")
    plot_waterfall_grid(shap_ridge, FEAT_NICE, concs, "Fig_SHAP_ridge_waterfall")
    plot_shap_dependence(shap_ridge, FEAT_NICE, 0, concs,
                          "Fig_SHAP_ridge_dependence")

    print(f"\n  Feature importances (mean |SHAP|, µM):")
    for fn, vi in zip(FEAT_NICE, imp_ridge):
        print(f"    {fn:20s} : {vi:.4f}")

    # ── Random Forest SHAP ────────────────────────────────────────────────────
    print("\n── Random Forest SHAP ───────────────────────────────────")
    rf, shap_rf = shap_tree(X_sc, y, FEATURES)
    y_pred_rf = rf.predict(X_sc)
    r2_rf = float(r2_score(y, y_pred_rf))
    print(f"  Training R² (RF, all data) = {r2_rf:.4f}")

    shap_rf.data         = X_sc
    shap_rf.feature_names = FEAT_NICE

    imp_rf = plot_shap_summary(shap_rf, FEAT_NICE, concs,
                                "Random Forest", "Fig_SHAP_rf_summary")
    plot_shap_dependence(shap_rf, FEAT_NICE, 0, concs,
                          "Fig_SHAP_rf_dependence")

    print(f"\n  Feature importances (mean |SHAP|, µM):")
    for fn, vi in zip(FEAT_NICE, imp_rf):
        print(f"    {fn:20s} : {vi:.4f}")

    # ── Summary comparison ────────────────────────────────────────────────────
    print("\n── Cross-model feature importance ranking ────────────────")
    print(f"  {'Feature':20s} {'Ridge':>10} {'RF':>10}")
    print("  " + "-" * 42)
    for fn, vr, vrf in zip(FEAT_NICE, imp_ridge, imp_rf):
        print(f"  {fn:20s} {vr:>10.4f} {vrf:>10.4f}")

    # Save importance table
    imp_df = pd.DataFrame({
        "feature":          FEATURES,
        "feature_nice":     FEAT_NICE,
        "SHAP_ridge_mean":  imp_ridge.tolist(),
        "SHAP_rf_mean":     imp_rf.tolist(),
    })
    imp_df.to_csv(DATA_FEAT / "shap_feature_importance.csv", index=False)
    imp_df.to_csv(CSV_DIR / "shap_feature_importance.csv", index=False)

    # Per-sample SHAP values for both models
    shap_ridge_df = pd.DataFrame(shap_ridge.values, columns=FEAT_NICE)
    shap_ridge_df.insert(0, "concentration_uM", concs)
    shap_ridge_df.to_csv(CSV_DIR / "shap_ridge_values.csv", index=False)

    shap_rf_df = pd.DataFrame(shap_rf.values, columns=FEAT_NICE)
    shap_rf_df.insert(0, "concentration_uM", concs)
    shap_rf_df.to_csv(CSV_DIR / "shap_rf_values.csv", index=False)

    # Feature values (scaled) for dependence plots
    feat_vals_df = pd.DataFrame(X_sc, columns=FEAT_NICE)
    feat_vals_df.insert(0, "concentration_uM", concs)
    feat_vals_df.to_csv(CSV_DIR / "shap_feature_values_scaled.csv", index=False)

    # Save models
    joblib.dump({"ridge": ridge, "rf": rf, "scaler": sc},
                MODELS_DIR / "shap_models.pkl")

    print("\n✓ SHAP analysis complete → reports/figures/  |  CSVs → reports/plot_csvs/")
