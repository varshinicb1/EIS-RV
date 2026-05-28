"""
Script 05 — ML-Assisted UA Concentration Prediction
With only 9 single-replica measurements (one per concentration), this script:
  1. Establishes linear calibration (primary, matches manuscript)
  2. Runs LOCO-CV across regularised / nonparametric models
  3. GPR on Ip_raw_475V for calibration with 95 % prediction intervals
  4. Feature importance (permutation-based) — precursor to SHAP in Script 07
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
import joblib

from sklearn.linear_model import LinearRegression, Ridge
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.cross_decomposition import PLSRegression
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.inspection import permutation_importance

from config import DATA_FEAT, DATA_PROC, FIG_DIR, CSV_DIR, MODELS_DIR

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

# Feature set — coarse-to-fine: single (linear), curated multi (ML)
FEATURES_MULTI = ["Ip_raw_475V", "Ip_corrected", "AUC", "FWHM_V"]
FEATURE_SINGLE = "Ip_raw_475V"    # primary analytical signal
TARGET = "concentration_uM"


# ── Helpers ───────────────────────────────────────────────────────────────────
def loco_cv(X, y, pipe):
    """Leave-One-Concentration-Out (= LOO for unique concentrations)."""
    n = len(y)
    preds = np.full(n, np.nan)
    for i in range(n):
        idx_tr = [j for j in range(n) if j != i]
        pipe.fit(X[idx_tr], y[idx_tr])
        preds[i] = float(pipe.predict(X[[i]])[0])
    return preds


def rel_error_pct(y_true, y_pred):
    """Mean absolute relative error (%), ignoring divide-by-zero."""
    ok = np.abs(y_true) > 1e-9
    return float(np.mean(np.abs((y_true[ok] - y_pred[ok]) / y_true[ok])) * 100)


def metrics(y, preds):
    r2   = float(r2_score(y, preds))
    rmse = float(np.sqrt(mean_squared_error(y, preds)))
    mae  = float(mean_absolute_error(y, preds))
    re   = rel_error_pct(y, preds)
    return r2, rmse, mae, re


# ── Models ────────────────────────────────────────────────────────────────────
def build_models():
    k = ConstantKernel(1.0, (0.01, 100)) * RBF(5.0, (0.5, 50))
    mods = {
        "Linear Reg.": Pipeline([("sc", StandardScaler()),
                                  ("m",  LinearRegression())]),
        "Ridge α=1":   Pipeline([("sc", StandardScaler()),
                                  ("m",  Ridge(alpha=1.0))]),
        "Ridge α=5":   Pipeline([("sc", StandardScaler()),
                                  ("m",  Ridge(alpha=5.0))]),
        "SVR-RBF":     Pipeline([("sc", StandardScaler()),
                                  ("m",  SVR(C=10, epsilon=0.5, gamma="scale"))]),
        "Rand. Forest":Pipeline([("sc", StandardScaler()),
                                  ("m",  RandomForestRegressor(
                                      n_estimators=200, max_depth=2,
                                      min_samples_leaf=2, random_state=42))]),
        "KNN k=3":     Pipeline([("sc", StandardScaler()),
                                  ("m",  KNeighborsRegressor(n_neighbors=3))]),
        "PLS 2-comp":  Pipeline([("sc", StandardScaler()),
                                  ("m",  PLSRegression(n_components=2))]),
        "GPR (multi)": Pipeline([("sc", StandardScaler()),
                                  ("m",  GaussianProcessRegressor(
                                      kernel=k, n_restarts_optimizer=10,
                                      normalize_y=True, alpha=1e-3))]),
    }
    if HAS_XGB:
        mods["XGBoost"] = Pipeline([
            ("sc", StandardScaler()),
            ("m",  XGBRegressor(n_estimators=50, max_depth=2,
                                learning_rate=0.15, subsample=0.9,
                                colsample_bytree=0.9, random_state=42,
                                verbosity=0)),
        ])
    return mods


# ── GPR 1-D calibration ───────────────────────────────────────────────────────
def fit_gpr_1d(x1d, y):
    """GPR on single feature (Ip_raw_475V) — monotone kernel."""
    k = ConstantKernel(50.0, (1.0, 1000)) * RBF(0.03, (0.001, 0.5))
    gpr = GaussianProcessRegressor(kernel=k, n_restarts_optimizer=15,
                                    normalize_y=True, alpha=1e-5)
    gpr.fit(x1d.reshape(-1, 1), y)
    return gpr


# ── Figures ───────────────────────────────────────────────────────────────────
def plot_model_comparison(results_df):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    names = results_df["Model"].tolist()
    x = np.arange(len(names))

    ax = axes[0]
    cols = ["#2BA84A" if v >= 0.97 else "#3A7EC0" if v >= 0.90 else "#E05C3A"
            for v in results_df["R2_LOCO"]]
    bars = ax.bar(x, results_df["R2_LOCO"], color=cols, edgecolor="white", lw=0.8)
    ax.axhline(0.99, color="gold", ls="--", lw=1.1, label="R²=0.99")
    ax.axhline(0.95, color="silver", ls=":", lw=1.0, label="R²=0.95")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("LOCO-CV R²")
    ax.set_title("(a) LOCO-CV R² by model (multi-feature)")
    ax.set_ylim(max(-0.1, results_df["R2_LOCO"].min() - 0.08), 1.04)
    ax.legend(fontsize=8)
    for bar, v in zip(bars, results_df["R2_LOCO"]):
        ax.text(bar.get_x() + bar.get_width()/2,
                max(bar.get_height(), 0) + 0.01,
                f"{v:.3f}", ha="center", fontsize=7, rotation=90)

    ax2 = axes[1]
    ax2.bar(x, results_df["RMSE_LOCO"], color="#3A7EC0", edgecolor="white", lw=0.8)
    ax2.set_xticks(x); ax2.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
    ax2.set_ylabel("LOCO-CV RMSE (µM)")
    ax2.set_title("(b) LOCO-CV RMSE by model")
    for bar, v in zip(ax2.patches, results_df["RMSE_LOCO"]):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15,
                 f"{v:.1f}", ha="center", fontsize=7)

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_ML_comparison.{ext}")
    plt.close(fig)
    results_df.to_csv(CSV_DIR / "ml_model_comparison.csv", index=False)


def plot_gpr_calibration(x1d, y, concs, gpr):
    """GPR 1-D calibration with 95% CI ribbon."""
    x_fine = np.linspace(x1d.min() * 0.98, x1d.max() * 1.02, 200)
    y_mu, y_std = gpr.predict(x_fine.reshape(-1, 1), return_std=True)
    y_pred_pts, _ = gpr.predict(x1d.reshape(-1, 1), return_std=True)

    # LOCO-CV parity for GPR 1D
    preds_loco = np.full(len(y), np.nan)
    for i in range(len(y)):
        idx_tr = [j for j in range(len(y)) if j != i]
        g_tmp = fit_gpr_1d(x1d[idx_tr], y[idx_tr])
        preds_loco[i] = float(g_tmp.predict(x1d[[i]].reshape(-1, 1))[0])

    r2_loco = float(r2_score(y, preds_loco))
    rmse_loco = float(np.sqrt(mean_squared_error(y, preds_loco)))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Panel A — GPR calibration curve
    ax = axes[0]
    ax.fill_between(x_fine, y_mu - 1.96*y_std, y_mu + 1.96*y_std,
                    alpha=0.20, color="#2BA84A", label="95% PI (GPR)")
    ax.plot(x_fine, y_mu, "g-", lw=2.0, label="GPR mean (all data)")
    # Linear fit for comparison
    c_lin = np.polyfit(x1d, y, 1)
    ax.plot(x_fine, np.polyval(c_lin, x_fine), "b--", lw=1.2,
            alpha=0.7, label=f"Linear R²={r2_score(y, np.polyval(c_lin, x1d)):.3f}")
    ax.scatter(x1d, y, color="#E05C3A", s=80, zorder=5,
               edgecolors="#8b3a26", lw=0.7, label="Measured")
    ax.set_xlabel("$I_p$ at 0.475 V (instrument units)")
    ax.set_ylabel("[UA] (µM)")
    ax.set_title("(a) GPR Calibration with 95% PI")
    ax.legend(fontsize=8)

    # Panel B — parity
    ax2 = axes[1]
    lims = [0, max(y) * 1.08]
    ax2.plot(lims, lims, "k--", lw=1.0, alpha=0.5, label="Ideal")
    ax2.scatter(y, preds_loco, color="#3A7EC0", s=80, zorder=4,
                edgecolors="#1e4f7a", lw=0.7)
    for yi, pi, ci in zip(y, preds_loco, concs):
        ax2.annotate(f"{int(ci)}", (yi, pi),
                     textcoords="offset points", xytext=(4, 2), fontsize=7)
    ax2.set_xlabel("Actual [UA] (µM)")
    ax2.set_ylabel("GPR-LOCO Predicted [UA] (µM)")
    ax2.set_title(f"(b) GPR LOO Parity — R²={r2_loco:.3f}, RMSE={rmse_loco:.1f} µM")
    ax2.legend(fontsize=8)
    ax2.set_xlim(lims); ax2.set_ylim(lims)

    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_ML_GPR.{ext}")
    plt.close(fig)

    pd.DataFrame({"x_fine": x_fine, "gpr_mean": y_mu,
                  "gpr_95ci_lo": y_mu - 1.96*y_std,
                  "gpr_95ci_hi": y_mu + 1.96*y_std}).to_csv(
        CSV_DIR / "gpr_calibration_curve.csv", index=False)
    pd.DataFrame({"actual_uM": y, "gpr_loco_pred_uM": preds_loco,
                  "concentration_uM": concs}).to_csv(
        CSV_DIR / "gpr_parity.csv", index=False)
    return r2_loco, rmse_loco, preds_loco


def plot_parity_grid(y, all_preds, names):
    """Small-multiple parity plots for all models."""
    n = len(names)
    ncols = min(3, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(5*ncols, 4.5*nrows))
    axes = np.array(axes).ravel()
    lims = [0, max(y) * 1.08]
    cmap = matplotlib.colormaps["tab10"]

    for k, (name, preds) in enumerate(zip(names, all_preds)):
        ax = axes[k]
        r2, rmse, mae, _ = metrics(y, preds)
        ax.plot(lims, lims, "k--", lw=0.8, alpha=0.5)
        ax.scatter(y, preds, color=cmap(k % 10), s=60, zorder=4,
                   edgecolors="black", lw=0.4)
        ax.set_xlim(lims); ax.set_ylim(lims)
        ax.set_xlabel("Actual (µM)", fontsize=9)
        ax.set_ylabel("Predicted (µM)", fontsize=9)
        ax.set_title(f"{name}\nR²={r2:.3f}, RMSE={rmse:.1f} µM", fontsize=9)

    for k in range(len(names), len(axes)):
        axes[k].set_visible(False)

    plt.suptitle("LOCO-CV Parity Plots — Multi-Feature Models", fontsize=12)
    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_ML_parity.{ext}")
    plt.close(fig)

    parity_rows = []
    for name, preds in zip(names, all_preds):
        for yi, pi in zip(y, preds):
            parity_rows.append({"model": name, "actual_uM": yi, "pred_uM": pi})
    pd.DataFrame(parity_rows).to_csv(CSV_DIR / "ml_parity_all_models.csv", index=False)


def plot_permutation_importance(X, y, feat_names, best_pipe, best_name):
    """Permutation feature importance (model-agnostic)."""
    best_pipe.fit(X, y)
    r = permutation_importance(best_pipe, X, y, n_repeats=30,
                               random_state=42, scoring="r2")
    idx = np.argsort(r.importances_mean)[::-1]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(np.arange(len(idx)), r.importances_mean[idx],
           yerr=r.importances_std[idx], color="#3A7EC0",
           edgecolor="white", capsize=4)
    ax.set_xticks(np.arange(len(idx)))
    ax.set_xticklabels([feat_names[i] for i in idx], rotation=20, ha="right")
    ax.set_ylabel("Mean R² decrease")
    ax.set_title(f"Permutation Feature Importance — {best_name}")
    plt.tight_layout()
    for ext in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"Fig_ML_importance.{ext}")
    plt.close(fig)

    imp_df = pd.DataFrame({
        "feature": [feat_names[i] for i in idx],
        "mean_R2_decrease": r.importances_mean[idx],
        "std_R2_decrease":  r.importances_std[idx],
    })
    imp_df.to_csv(CSV_DIR / "ml_permutation_importance.csv", index=False)
    return {feat_names[i]: float(r.importances_mean[i]) for i in range(len(feat_names))}


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("STEP 05 — ML-Assisted Concentration Prediction")
    print("=" * 60)

    feat_df = pd.read_csv(DATA_FEAT / "dpv_features.csv")
    ua_df   = feat_df[feat_df[TARGET] > 0].copy().reset_index(drop=True)

    X_multi = ua_df[FEATURES_MULTI].values.astype(float)
    x1d     = ua_df[FEATURE_SINGLE].values.astype(float)
    y       = ua_df[TARGET].values.astype(float)
    concs   = y.copy()

    print(f"\n  Samples         : {len(y)} UA concentrations")
    print(f"  Feature set     : {FEATURES_MULTI}")
    print(f"  Primary feature : {FEATURE_SINGLE}")
    print(f"  Concentrations  : {sorted(concs.tolist())} µM")

    # ── 1. Multi-feature LOCO-CV ──────────────────────────────────────────────
    models  = build_models()
    records = []
    all_preds = []
    all_names = []

    print(f"\n{'Model':16s} {'R²(LOCO)':>9} {'RMSE(µM)':>10} "
          f"{'MAE(µM)':>9} {'RE(%)':>8}")
    print("  " + "-" * 55)

    for name, pipe in models.items():
        preds = loco_cv(X_multi, y, pipe)
        r2, rmse, mae, re = metrics(y, preds)
        records.append({"Model": name, "R2_LOCO": r2,
                        "RMSE_LOCO": rmse, "MAE_LOCO": mae, "RE_LOCO": re})
        all_preds.append(preds)
        all_names.append(name)
        flag = "★" if r2 >= 0.97 else ("✓" if r2 >= 0.92 else "⚠")
        print(f"  {name:16s} {r2:>9.4f} {rmse:>10.3f} {mae:>9.3f} {re:>8.1f} {flag}")

    results_df = pd.DataFrame(records).sort_values("R2_LOCO", ascending=False)
    results_df.to_csv(DATA_FEAT / "ml_model_comparison.csv", index=False)

    best_row  = results_df.iloc[0]
    best_name = best_row["Model"]
    best_r2   = best_row["R2_LOCO"]
    print(f"\n  Best LOCO-CV model : {best_name}  (R²={best_r2:.4f})")

    # ── 2. GPR 1-D calibration with uncertainty ───────────────────────────────
    print("\n── GPR 1-D Calibration (Ip_raw_475V) ───────────────────")
    gpr_1d = fit_gpr_1d(x1d, y)
    joblib.dump(gpr_1d, MODELS_DIR / "gpr_1d_ua_model.pkl")
    gpr_loco_r2, gpr_loco_rmse, gpr_loco_preds = plot_gpr_calibration(
        x1d, y, concs, gpr_1d)
    print(f"  GPR (1-D) LOCO-CV  R² = {gpr_loco_r2:.4f}")
    print(f"  GPR (1-D) LOCO-CV RMSE = {gpr_loco_rmse:.2f} µM")

    # ── 3. LoD / LoQ from best-model LOO residuals ───────────────────────────
    # Use 1D linear (primary method, matches script 02)
    lin_pipe = Pipeline([("sc", StandardScaler()), ("m", LinearRegression())])
    lin_preds_1d = loco_cv(x1d.reshape(-1, 1), y, lin_pipe)
    r2_lin, rmse_lin, mae_lin, re_lin = metrics(y, lin_preds_1d)
    sigma_resid = float(np.std(y - lin_preds_1d, ddof=1))
    LoD_ml = 3.3 * sigma_resid
    LoQ_ml = 10.0 * sigma_resid

    # Load electrochemical LoD for comparison
    try:
        cal_sum = pd.read_csv(DATA_FEAT / "dpv_calibration_summary.csv",
                              index_col=0, header=None).squeeze()
        LoD_ec = float(cal_sum.loc["LoD_uM"])
        LoQ_ec = float(cal_sum.loc["LoQ_uM"])
    except Exception:
        LoD_ec = LoQ_ec = float("nan")

    print(f"\n── Linear LOCO-CV (Ip_raw_475V only) ───────────────────")
    print(f"  R²={r2_lin:.4f}  RMSE={rmse_lin:.2f} µM  σ_resid={sigma_resid:.3f} µM")
    print(f"\n── Detection Limits ─────────────────────────────────────")
    print(f"  ML LOCO residual  LoD = {LoD_ml:.3f} µM  ({LoD_ml*1000:.1f} nM)")
    print(f"  ML LOCO residual  LoQ = {LoQ_ml:.3f} µM  ({LoQ_ml*1000:.1f} nM)")
    print(f"  Electrochemical   LoD = {LoD_ec:.3f} µM  ({LoD_ec*1000:.1f} nM)  [from script 02]")

    # ── 4. Permutation importance of best model ───────────────────────────────
    best_pipe = models[best_name]
    feat_imp  = plot_permutation_importance(X_multi, y, FEATURES_MULTI,
                                            best_pipe, best_name)
    print(f"\n── Permutation Feature Importance ({best_name}) ─────────")
    for fn, vi in sorted(feat_imp.items(), key=lambda t: -t[1]):
        print(f"  {fn:20s} : {vi:.4f}")

    # ── 5. Plots ──────────────────────────────────────────────────────────────
    plot_model_comparison(results_df)
    plot_parity_grid(y, all_preds, all_names)

    # ── 6. Save multi-feature best model ──────────────────────────────────────
    best_pipe.fit(X_multi, y)
    joblib.dump(best_pipe, MODELS_DIR / "best_ml_ua_model.pkl")

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = {
        "best_model": best_name,
        "best_R2_LOCO": best_r2,
        "Linear1D_R2_LOCO": r2_lin,
        "Linear1D_RMSE_LOCO_uM": rmse_lin,
        "GPR1D_R2_LOCO": gpr_loco_r2,
        "GPR1D_RMSE_LOCO_uM": gpr_loco_rmse,
        "ML_LoD_uM": LoD_ml,
        "ML_LoQ_uM": LoQ_ml,
        "EC_LoD_uM": LoD_ec,
        "EC_LoQ_uM": LoQ_ec,
        "sigma_residual_uM": sigma_resid,
        "feat_imp_Ip_raw_475V": feat_imp.get("Ip_raw_475V", float("nan")),
        "feat_imp_Ip_corrected": feat_imp.get("Ip_corrected", float("nan")),
        "feat_imp_AUC": feat_imp.get("AUC", float("nan")),
        "feat_imp_FWHM_V": feat_imp.get("FWHM_V", float("nan")),
    }
    pd.Series(summary).to_csv(DATA_FEAT / "ml_summary.csv")

    # ── 6. Dedicated calibration curve linear model ───────────────────────────
    try:
        calib_df = pd.read_csv(DATA_PROC / "calib_curve.csv")
        xcc = calib_df.concentration_uM.values
        ycc = calib_df.current_uA.values
        cc  = np.polyfit(xcc, ycc, 1)
        ycc_hat = np.polyval(cc, xcc)
        r2_calib = float(1 - np.sum((ycc - ycc_hat)**2) /
                         np.sum((ycc - ycc.mean())**2))
        print(f"\n── Dedicated Calibration Curve (10–700 µM) ─────────")
        print(f"  Slope    = {cc[0]:.6f} µA/µM   R² = {r2_calib:.4f}")
        calib_line = pd.DataFrame({
            "concentration_uM": xcc, "current_uA": ycc,
            "fit_uA": ycc_hat, "residual_uA": ycc - ycc_hat
        })
        calib_line.to_csv(CSV_DIR / "ml_calib_curve_fit.csv", index=False)
    except Exception as e:
        print(f"  (Calib curve not loaded: {e})")

    print(f"\n✓ ML analysis complete → reports/figures/ & models/  |  CSVs → reports/plot_csvs/")
    print(f"  Saved: Fig_ML_comparison, Fig_ML_GPR, Fig_ML_parity, Fig_ML_importance")
