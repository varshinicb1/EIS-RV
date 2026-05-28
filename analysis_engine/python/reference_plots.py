"""
Reference-style CV plotting and validation.

The figures follow the visual grammar of the reference PDF where possible:
multi-panel white figures, compact serif typography, small panel labels,
thin axes, right-side colorbars, and scan-rate legends.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import ListedColormap, BoundaryNorm
from PIL import Image

from loader import load_cv_dataset, load_cv_file, select_branch
from analysis import (
    compute_b_values,
    dunn_decomposition,
    peak_scaling_analysis,
    kinetic_regime_map,
    pca_analysis,
)
from plotter import (
    plot_b_values,
    plot_b_value_heatmap,
    plot_current_heatmap,
    plot_cv_overlay,
    plot_dunn_decomposition,
    plot_dunn_fractions,
    plot_pca,
    plot_peak_scaling,
    plot_summary_table,
)


def apply_reference_style() -> None:
    matplotlib.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 8,
            "axes.labelsize": 9,
            "axes.titlesize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 6.5,
            "axes.linewidth": 0.8,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "lines.linewidth": 1.05,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def _panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.13,
        1.08,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        fontweight="bold",
        clip_on=False,
    )


def _eng_formatter() -> mticker.EngFormatter:
    return mticker.EngFormatter(unit="A", sep="")


AVAILABLE_PALETTES = [
    "turbo", "plasma", "viridis", "inferno", "magma", "cividis",
    "rainbow", "jet", "cool", "spring", "summer", "autumn", "winter",
    "tab10", "tab20", "Set1", "Set2", "Set3", "Paired",
    "RdYlBu", "RdYlGn", "Spectral", "coolwarm", "seismic",
    "PiYG", "PRGn", "BrBG", "PuOr", "RdGy", "RdBu",
    "YlOrRd", "YlOrBr", "YlGnBu", "GnBu", "OrRd", "PuRd",
    "Blues", "Greens", "Reds", "Purples", "Oranges", "Greys",
]


def _scan_colors(n: int, palette: str = "turbo"):
    safe = palette if palette in AVAILABLE_PALETTES else "turbo"
    cmap = plt.get_cmap(safe)
    discrete = ("tab10", "tab20", "Set1", "Set2", "Set3", "Paired")
    if safe in discrete:
        return [cmap(i % cmap.N) for i in range(n)]
    return [cmap(i / max(n - 1, 1)) for i in range(n)]


def _set_custom_title(ax: plt.Axes, title: str) -> None:
    """Apply Times New Roman Bold 18pt custom title."""
    if title:
        ax.set_title(title, fontfamily="Times New Roman", fontweight="bold", fontsize=18, pad=8)


def _set_layout_pads(fig: plt.Figure, **kwargs) -> None:
    engine = fig.get_layout_engine()
    if engine is not None and hasattr(engine, "set"):
        engine.set(**kwargs)


def _cap_fraction_map(currents: np.ndarray, dunn: dict) -> np.ndarray:
    cap = np.abs(dunn["cap_current"])
    dif = np.abs(dunn["dif_current"])
    return cap / np.maximum(cap + dif, 1e-30)


def _regime_ising_like(b_values: np.ndarray, smooth_penalty: float = 0.18) -> np.ndarray:
    """
    Deterministic two-state segmentation inspired by the Ising/QUBO panel.

    State 1 = capacitive-dominated, state 0 = diffusion-influenced.
    A dynamic-programming smoothness penalty discourages single-pixel flips.
    """
    b = np.nan_to_num(b_values, nan=0.75)
    cost_diff = (b - 0.5) ** 2
    cost_cap = (b - 1.0) ** 2
    n = len(b)
    dp = np.zeros((n, 2), dtype=float)
    prev = np.zeros((n, 2), dtype=int)
    dp[0] = [cost_diff[0], cost_cap[0]]
    for i in range(1, n):
        for state, cost in enumerate((cost_diff[i], cost_cap[i])):
            stay = dp[i - 1, state]
            flip = dp[i - 1, 1 - state] + smooth_penalty
            if stay <= flip:
                dp[i, state] = stay + cost
                prev[i, state] = state
            else:
                dp[i, state] = flip + cost
                prev[i, state] = 1 - state
    states = np.zeros(n, dtype=int)
    states[-1] = int(dp[-1, 1] < dp[-1, 0])
    for i in range(n - 2, -1, -1):
        states[i] = prev[i + 1, states[i + 1]]
    return states


def _resample_curve_features(
    potential: np.ndarray,
    currents: np.ndarray,
    n_features: int = 24,
) -> np.ndarray:
    """Represent each scan-rate curve by normalized, evenly sampled shape features."""
    grid = np.linspace(float(np.min(potential)), float(np.max(potential)), n_features)
    features = np.zeros((currents.shape[1], n_features), dtype=float)
    for j in range(currents.shape[1]):
        curve = np.interp(grid, potential, currents[:, j])
        curve = curve - float(np.mean(curve))
        scale = float(np.max(np.abs(curve)))
        if scale > 0:
            curve = curve / scale
        features[j, :] = curve
    features = features - np.mean(features, axis=0, keepdims=True)
    std = np.std(features, axis=0, keepdims=True)
    features = features / np.where(std > 1e-12, std, 1.0)
    return np.clip(features / 3.0, -1.0, 1.0) * (np.pi / 2.0)


def quantum_kernel_pca_analysis(
    potential: np.ndarray,
    currents: np.ndarray,
    scan_rates: np.ndarray,
    n_features: int = 24,
    n_components: int = 2,
) -> dict:
    """
    Angle-encoded fidelity-kernel PCA for scan-rate CV curves.

    Feature map:
        |phi(x)> = tensor_k Ry(x_k)|0>

    Kernel:
        K_ij = |<phi(x_i)|phi(x_j)>|^2
             = product_k cos^2((x_ik - x_jk)/2)
    """
    features = _resample_curve_features(potential, currents, n_features=n_features)
    n = features.shape[0]
    kernel = np.ones((n, n), dtype=float)
    for i in range(n):
        for j in range(n):
            delta = (features[i] - features[j]) / 2.0
            kernel[i, j] = float(np.prod(np.cos(delta) ** 2))
    kernel = (kernel + kernel.T) / 2.0
    np.fill_diagonal(kernel, 1.0)

    one = np.ones((n, n), dtype=float) / n
    centered = kernel - one @ kernel - kernel @ one + one @ kernel @ one
    centered = (centered + centered.T) / 2.0
    eigvals, eigvecs = np.linalg.eigh(centered)
    order = np.argsort(eigvals)[::-1]
    eigvals = np.clip(eigvals[order], 0.0, None)
    eigvecs = eigvecs[:, order]
    keep = min(n_components, n)
    scores = eigvecs[:, :keep] * np.sqrt(np.maximum(eigvals[:keep], 0.0))
    total = float(np.sum(eigvals))
    explained = eigvals[:keep] / total if total > 0 else np.zeros(keep)
    return {
        "features": features,
        "kernel": kernel,
        "centered_kernel": centered,
        "eigenvalues": eigvals,
        "scores_rate": scores,
        "explained_variance": explained,
        "scan_rates": np.array(scan_rates, dtype=float),
    }


def analyze_cv(csv_path: str | Path, branch: str = "forward") -> dict:
    dataset = load_cv_dataset(str(csv_path))
    selected = select_branch(dataset, branch=branch)
    potential, currents, scan_rates = load_cv_file(str(csv_path), branch=selected.name)
    b_values, r_squared, log_a = compute_b_values(potential, currents, scan_rates)
    dunn = dunn_decomposition(potential, currents, scan_rates)
    scaling = peak_scaling_analysis(potential, currents, scan_rates)
    regime = kinetic_regime_map(b_values, dunn)
    pca = pca_analysis(currents, scan_rates)
    qkpca = quantum_kernel_pca_analysis(potential, currents, np.array(scan_rates, dtype=float))
    ising = _regime_ising_like(b_values)
    cap_map = _cap_fraction_map(currents, dunn)
    return {
        "dataset": dataset,
        "selected_branch": selected,
        "potential": potential,
        "currents": currents,
        "scan_rates": np.array(scan_rates, dtype=float),
        "b_values": b_values,
        "r_squared": r_squared,
        "log_a": log_a,
        "dunn": dunn,
        "scaling": scaling,
        "regime": regime,
        "pca": pca,
        "qkpca": qkpca,
        "ising": ising,
        "cap_map": cap_map,
    }


def plot_reference_cv_suite(result: dict, sample_label: str = "AV.csv") -> plt.Figure:
    dataset = result["dataset"]
    potential = result["potential"]
    currents = result["currents"]
    scan_rates = result["scan_rates"]
    scaling = result["scaling"]

    fig, axes = plt.subplots(1, 3, figsize=(8.9, 2.45), constrained_layout=True)
    _set_layout_pads(fig, w_pad=0.06, h_pad=0.04, wspace=0.08, hspace=0.05)
    colors = _scan_colors(len(scan_rates))

    ax = axes[0]
    for j, (sr, color) in enumerate(zip(scan_rates, colors)):
        ax.plot(
            dataset.potential_raw,
            dataset.currents_raw[:, j],
            color=color,
            lw=0.85,
            label=f"{int(sr)} mV/s",
        )
    ax.axhline(0, color="0.55", lw=0.45)
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("Current I (A)")
    ax.yaxis.set_major_formatter(_eng_formatter())
    ax.legend(loc="upper left", frameon=False, ncol=1, handlelength=1.4)
    ax.set_title(f"CV overlay ({sample_label})")
    _panel_label(ax, "(a)")

    ax = axes[1]
    im = ax.imshow(
        np.abs(currents).T,
        origin="lower",
        aspect="auto",
        extent=[potential.min(), potential.max(), scan_rates.min(), scan_rates.max()],
        cmap="viridis",
    )
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel(r"Scan rate $v$ (mV s$^{-1}$)")
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.ax.yaxis.set_major_formatter(_eng_formatter())
    cbar.set_label(r"$|I|$(A)", labelpad=2)
    ax.set_title(r"$|I(V,v)|$ heatmap")
    _panel_label(ax, "(b)")

    ax = axes[2]
    sqrt_v = scaling["sqrt_v"]
    y = np.abs(scaling["cathodic_peaks"])
    fit_x = np.linspace(float(sqrt_v.min()), float(sqrt_v.max()), 200)
    fit_y = scaling["cathodic_slope"] * fit_x + scaling["cathodic_intercept"]
    ax.scatter(sqrt_v, y, color="#c99a1e", marker="x", s=16, label="data")
    ax.plot(fit_x, fit_y, color="#d6a928", lw=0.9, label=f"fit ($R^2$={scaling['cathodic_r2']:.3f})")
    ax.set_xlabel(r"$\sqrt{v}$ (mV/s)$^{1/2}$")
    ax.set_ylabel(r"$|I_{peak}|$ (A)")
    ax.yaxis.set_major_formatter(_eng_formatter())
    ax.legend(loc="upper left", frameon=True, fontsize=5.5)
    ax.set_title("Peak scaling")
    _panel_label(ax, "(c)")
    return fig


def plot_reference_kinetic_suite(result: dict, sample_label: str = "AV.csv") -> plt.Figure:
    potential = result["potential"]
    scan_rates = result["scan_rates"]
    b_values = result["b_values"]
    cap_map = result["cap_map"]
    ising = result["ising"]
    qkpca = result["qkpca"]
    regime = result["regime"]

    fig, axes = plt.subplots(2, 3, figsize=(8.9, 4.9), constrained_layout=True)
    _set_layout_pads(fig, w_pad=0.06, h_pad=0.05, wspace=0.08, hspace=0.08)

    ax = axes[0, 0]
    ax.imshow(
        ising[np.newaxis, :],
        origin="lower",
        aspect="auto",
        extent=[potential.min(), potential.max(), 0, 1],
        cmap=ListedColormap(["white", "#e6a400"]),
        vmin=0,
        vmax=1,
    )
    ax.set_yticks([0.15, 0.85], ["DD", "CD"])
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("Ising state")
    ax.set_title(f"Ising kinetic segmentation ({sample_label})")
    _panel_label(ax, "(a)")

    ax = axes[0, 1]
    scores = qkpca["scores_rate"]
    ax.scatter(scores[:, 0], scores[:, 1], marker="x", color="#7b3f8f", s=22)
    for sr, x, y in zip(scan_rates, scores[:, 0], scores[:, 1]):
        ax.text(x, y, f" {int(sr)}", color="#9a1f1f", fontsize=6, va="center")
    ax.set_xlabel("Quantum KPCA 1")
    ax.set_ylabel("Quantum KPCA 2")
    ax.set_title("Quantum-kernel PCA scan-rate map")
    ax.grid(True, lw=0.35, alpha=0.35)
    _panel_label(ax, "(b)")

    ax = axes[0, 2]
    im = ax.imshow(
        np.clip(b_values, 0, 1.2)[np.newaxis, :],
        origin="lower",
        aspect="auto",
        extent=[potential.min(), potential.max(), 0, 1],
        cmap="viridis",
        vmin=0.4,
        vmax=1.05,
    )
    ax.set_yticks([])
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("Cu-doping x (%)")
    ax.set_title("$b$-value heatmap")
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label("$b$ value", labelpad=2)
    _panel_label(ax, "(c)")

    ax = axes[1, 0]
    im = ax.imshow(
        cap_map.T,
        origin="lower",
        aspect="auto",
        extent=[potential.min(), potential.max(), scan_rates.min(), scan_rates.max()],
        cmap="viridis",
        vmin=0,
        vmax=1,
    )
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel(r"Scan rate $v$ (mV s$^{-1}$)")
    ax.set_title("Capacitive-fraction map")
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label(r"$F_{cap}(V)$", labelpad=2)
    _panel_label(ax, "(d)")

    ax = axes[1, 1]
    ising_tile = np.tile(ising, (len(scan_rates), 1))
    regime_cmap = ListedColormap(["#d62728", "#1f77b4"])
    im = ax.imshow(
        ising_tile,
        origin="lower",
        aspect="auto",
        extent=[potential.min(), potential.max(), scan_rates.min(), scan_rates.max()],
        cmap=regime_cmap,
        vmin=0,
        vmax=1,
    )
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel(r"Scan rate $v$ (mV s$^{-1}$)")
    ax.set_title("Kinetic regime (DD / CD)")
    cbar = fig.colorbar(im, ax=ax, pad=0.02, ticks=[0.25, 0.75])
    cbar.set_ticklabels(["DD", "CD"])
    _panel_label(ax, "(e)")

    ax = axes[1, 2]
    ax.plot(potential, b_values, color="#1f6f9e", lw=0.85)
    ax.axhline(1.0, color="#d62728", ls="--", lw=0.75, label="b=1")
    ax.axhline(0.5, color="#2ca02c", ls="--", lw=0.75, label="b=0.5")
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("$b$ value")
    ax.set_title("Pointwise scaling")
    ax.legend(loc="upper right", frameon=True)
    _panel_label(ax, "(f)")

    return fig


# ── Individual panel plots (fig4 a/b/c and fig5 a–f) ─────────────────────────
# Each function reproduces the exact panel code from plot_reference_cv_suite /
# plot_reference_kinetic_suite in a standalone figure.  figsize is chosen so
# the single panel fills the same visual proportion as it did inside the
# combined figure (original per-panel dimensions were ~3" × 2.45").

def plot_fig4a_cv_overlay(result: dict, sample_label: str = "", title: str = "", palette: str = "turbo") -> plt.Figure:
    dataset = result["dataset"]
    scan_rates = result["scan_rates"]
    colors = _scan_colors(len(scan_rates), palette)
    fig, ax = plt.subplots(figsize=(4.5, 3.5), constrained_layout=True)
    for j, (sr, color) in enumerate(zip(scan_rates, colors)):
        ax.plot(
            dataset.potential_raw,
            dataset.currents_raw[:, j],
            color=color,
            lw=0.85,
            label=f"{int(sr)} mV/s",
        )
    ax.axhline(0, color="0.55", lw=0.45)
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("Current I (A)")
    ax.yaxis.set_major_formatter(_eng_formatter())
    ax.legend(loc="upper left", frameon=False, ncol=1, handlelength=1.4)
    _set_custom_title(ax, title)
    _panel_label(ax, "(a)")
    return fig


def plot_fig4b_current_heatmap(result: dict, title: str = "", palette: str = "viridis") -> plt.Figure:
    potential = result["potential"]
    currents = result["currents"]
    scan_rates = result["scan_rates"]
    fig, ax = plt.subplots(figsize=(4.5, 3.5), constrained_layout=True)
    safe_palette = palette if palette in AVAILABLE_PALETTES else "viridis"
    im = ax.imshow(
        np.abs(currents).T,
        origin="lower",
        aspect="auto",
        extent=[potential.min(), potential.max(), scan_rates.min(), scan_rates.max()],
        cmap=safe_palette,
    )
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel(r"Scan rate $v$ (mV s$^{-1}$)")
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.ax.yaxis.set_major_formatter(_eng_formatter())
    cbar.set_label(r"$|I|$(A)", labelpad=2)
    _set_custom_title(ax, title)
    _panel_label(ax, "(b)")
    return fig


def plot_fig4c_peak_scaling(result: dict, title: str = "") -> plt.Figure:
    scaling = result["scaling"]
    fig, ax = plt.subplots(figsize=(4.5, 3.5), constrained_layout=True)
    sqrt_v = scaling["sqrt_v"]
    y = np.abs(scaling["cathodic_peaks"])
    fit_x = np.linspace(float(sqrt_v.min()), float(sqrt_v.max()), 200)
    fit_y = scaling["cathodic_slope"] * fit_x + scaling["cathodic_intercept"]
    ax.scatter(sqrt_v, y, color="#c99a1e", marker="x", s=16, label="data")
    ax.plot(fit_x, fit_y, color="#d6a928", lw=0.9, label=f"fit ($R^2$={scaling['cathodic_r2']:.3f})")
    ax.set_xlabel(r"$\sqrt{v}$ (mV/s)$^{1/2}$")
    ax.set_ylabel(r"$|I_{peak}|$ (A)")
    ax.yaxis.set_major_formatter(_eng_formatter())
    ax.legend(loc="upper left", frameon=True, fontsize=5.5)
    _set_custom_title(ax, title)
    _panel_label(ax, "(c)")
    return fig


def plot_fig5a_ising_segmentation(result: dict, sample_label: str = "", title: str = "") -> plt.Figure:
    potential = result["potential"]
    ising = result["ising"]
    fig, ax = plt.subplots(figsize=(4.5, 3.5), constrained_layout=True)
    ax.imshow(
        ising[np.newaxis, :],
        origin="lower",
        aspect="auto",
        extent=[potential.min(), potential.max(), 0, 1],
        cmap=ListedColormap(["#d62728", "#1f77b4"]),
        vmin=0,
        vmax=1,
    )
    ax.set_yticks([0.25, 0.75], ["DD", "CD"])
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("Ising state")
    _set_custom_title(ax, title)
    _panel_label(ax, "(a)")
    return fig


def plot_fig5b_quantum_kpca(result: dict, title: str = "") -> plt.Figure:
    qkpca = result["qkpca"]
    scan_rates = result["scan_rates"]
    fig, ax = plt.subplots(figsize=(4.5, 3.5), constrained_layout=True)
    scores = qkpca["scores_rate"]
    ax.scatter(scores[:, 0], scores[:, 1], marker="x", color="#7b3f8f", s=22)
    for sr, x, y in zip(scan_rates, scores[:, 0], scores[:, 1]):
        ax.text(x, y, f" {int(sr)}", color="#9a1f1f", fontsize=6, va="center")
    ax.set_xlabel("Quantum KPCA 1")
    ax.set_ylabel("Quantum KPCA 2")
    _set_custom_title(ax, title)
    ax.grid(True, lw=0.35, alpha=0.35)
    _panel_label(ax, "(b)")
    return fig


def plot_fig5c_b_value_heatmap(result: dict, title: str = "", palette: str = "RdYlBu_r") -> plt.Figure:
    potential = result["potential"]
    b_values = result["b_values"]
    safe_palette = palette if palette in AVAILABLE_PALETTES or palette.endswith("_r") else "RdYlBu_r"
    fig, ax = plt.subplots(figsize=(4.5, 3.5), constrained_layout=True)
    im = ax.imshow(
        np.clip(b_values, 0, 1.2)[np.newaxis, :],
        origin="lower",
        aspect="auto",
        extent=[potential.min(), potential.max(), 0, 1],
        cmap=safe_palette,
        vmin=0.4,
        vmax=1.05,
    )
    ax.set_yticks([])
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("")
    _set_custom_title(ax, title)
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label("$b$ value", labelpad=2)
    _panel_label(ax, "(c)")
    return fig


def plot_fig5d_cap_fraction_map(result: dict, title: str = "", palette: str = "viridis") -> plt.Figure:
    potential = result["potential"]
    cap_map = result["cap_map"]
    scan_rates = result["scan_rates"]
    safe_palette = palette if palette in AVAILABLE_PALETTES else "viridis"
    fig, ax = plt.subplots(figsize=(4.5, 3.5), constrained_layout=True)
    im = ax.imshow(
        cap_map.T,
        origin="lower",
        aspect="auto",
        extent=[potential.min(), potential.max(), scan_rates.min(), scan_rates.max()],
        cmap=safe_palette,
        vmin=0,
        vmax=1,
    )
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel(r"Scan rate $v$ (mV s$^{-1}$)")
    _set_custom_title(ax, title)
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label(r"$F_{cap}(V)$", labelpad=2)
    _panel_label(ax, "(d)")
    return fig


def plot_fig5e_kinetic_regime(result: dict, title: str = "") -> plt.Figure:
    potential = result["potential"]
    ising = result["ising"]
    scan_rates = result["scan_rates"]
    fig, ax = plt.subplots(figsize=(4.5, 3.5), constrained_layout=True)
    ising_tile = np.tile(ising, (len(scan_rates), 1))
    regime_cmap = ListedColormap(["#d62728", "#1f77b4"])
    im = ax.imshow(
        ising_tile,
        origin="lower",
        aspect="auto",
        extent=[potential.min(), potential.max(), scan_rates.min(), scan_rates.max()],
        cmap=regime_cmap,
        vmin=0,
        vmax=1,
    )
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel(r"Scan rate $v$ (mV s$^{-1}$)")
    _set_custom_title(ax, title)
    cbar = fig.colorbar(im, ax=ax, pad=0.02, ticks=[0.25, 0.75])
    cbar.set_ticklabels(["DD", "CD"])
    _panel_label(ax, "(e)")
    return fig


def plot_fig5f_pointwise_scaling(result: dict, title: str = "") -> plt.Figure:
    potential = result["potential"]
    b_values = result["b_values"]
    fig, ax = plt.subplots(figsize=(4.5, 3.5), constrained_layout=True)
    ax.plot(potential, b_values, color="#1f6f9e", lw=0.85)
    ax.axhline(1.0, color="#d62728", ls="--", lw=0.75, label="b=1 (EDLC)")
    ax.axhline(0.5, color="#2ca02c", ls="--", lw=0.75, label="b=0.5 (diffusion)")
    ax.axhline(0.75, color="#ff7f0e", ls=":", lw=0.65, label="b=0.75 (threshold)")
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("$b$ value")
    _set_custom_title(ax, title)
    ax.legend(loc="upper right", frameon=True, fontsize=6)
    _panel_label(ax, "(f)")
    return fig


def _save_figure(fig: plt.Figure, path: Path, dpi: int) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    info = {"file": str(path), "dpi": dpi}
    if path.suffix.lower() in {".png", ".tif", ".tiff"}:
        with Image.open(path) as image:
            info.update({"width_px": image.width, "height_px": image.height})
            if image.info.get("dpi"):
                info["embedded_dpi"] = tuple(round(v, 2) for v in image.info["dpi"])
    plt.close(fig)
    return info


def _subset_scan_rates(result: dict, max_rate: float | None = 50.0) -> dict:
    """Return a shallow result copy with scan-rate arrays limited for PDF-style panels."""
    if max_rate is None:
        return result
    mask = result["scan_rates"] <= max_rate
    if not np.any(mask):
        return result
    out = dict(result)
    out["scan_rates"] = result["scan_rates"][mask]
    out["currents"] = result["currents"][:, mask]
    raw_dataset = result["dataset"]
    raw_copy = type(raw_dataset)(
        raw_dataset.potential_raw,
        raw_dataset.currents_raw[:, mask],
        [float(v) for v in result["scan_rates"][mask]],
        raw_dataset.branches,
    )
    out["dataset"] = raw_copy
    out["b_values"], out["r_squared"], out["log_a"] = compute_b_values(
        out["potential"], out["currents"], out["scan_rates"]
    )
    out["dunn"] = dunn_decomposition(out["potential"], out["currents"], out["scan_rates"])
    out["scaling"] = peak_scaling_analysis(out["potential"], out["currents"], out["scan_rates"])
    out["regime"] = kinetic_regime_map(out["b_values"], out["dunn"])
    out["pca"] = pca_analysis(out["currents"], out["scan_rates"])
    out["qkpca"] = quantum_kernel_pca_analysis(out["potential"], out["currents"], out["scan_rates"])
    out["ising"] = _regime_ising_like(out["b_values"])
    out["cap_map"] = _cap_fraction_map(out["currents"], out["dunn"])
    return out


def _composition_grid(results: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    v_min = max(float(np.min(r["potential"])) for r in results)
    v_max = min(float(np.max(r["potential"])) for r in results)
    n = min(len(r["potential"]) for r in results)
    if v_min >= v_max:
        v_min = min(float(np.min(r["potential"])) for r in results)
        v_max = max(float(np.max(r["potential"])) for r in results)
    return np.linspace(v_min, v_max, n), np.array([0.0, 5.0, 10.0])


def _interp_series(result: dict, values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    return np.interp(grid, result["potential"], values)


def _interp_matrix(result: dict, matrix: np.ndarray, grid: np.ndarray) -> np.ndarray:
    out = np.zeros((len(grid), matrix.shape[1]), dtype=float)
    for j in range(matrix.shape[1]):
        out[:, j] = np.interp(grid, result["potential"], matrix[:, j])
    return out


def plot_pdf_fig4(results: list[dict], labels: list[str]) -> plt.Figure:
    """Build a 3x3 Fig. 4 style panel set for x=0/5/10 CV analysis."""
    fig, axes = plt.subplots(3, 3, figsize=(8.95, 6.25), constrained_layout=True)
    _set_layout_pads(fig, w_pad=0.045, h_pad=0.035, wspace=0.07, hspace=0.08)
    panel = iter(["(a)", "(b)", "(c)", "(d)", "(e)", "(f)", "(g)", "(h)", "(i)"])

    for col, (result, label) in enumerate(zip(results, labels)):
        ax = axes[0, col]
        colors = _scan_colors(len(result["scan_rates"]))
        for j, (sr, color) in enumerate(zip(result["scan_rates"], colors)):
            ax.plot(
                result["dataset"].potential_raw,
                result["dataset"].currents_raw[:, j],
                color=color,
                lw=0.8,
                label=f"{int(sr)} mV/s",
            )
        ax.axhline(0, color="0.6", lw=0.35)
        ax.set_xlabel("Potential V(V)")
        ax.set_ylabel("Current I (A)")
        ax.yaxis.set_major_formatter(_eng_formatter())
        ax.legend(loc="upper left", frameon=False, fontsize=5.4, handlelength=1.1)
        ax.text(0.94, 0.08, f"{next(panel)} {label}", transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5)

    for col, (result, label) in enumerate(zip(results, labels)):
        ax = axes[1, col]
        im = ax.imshow(
            np.abs(result["currents"]).T,
            origin="lower",
            aspect="auto",
            extent=[
                result["potential"].min(),
                result["potential"].max(),
                result["scan_rates"].min(),
                result["scan_rates"].max(),
            ],
            cmap="viridis",
        )
        ax.set_xlabel("Potential V(V)")
        ax.set_ylabel(r"Scan rate $v$ (mV s$^{-1}$)")
        ax.text(0.94, 0.08, f"{next(panel)} {label}", transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5, color="white")
        cbar = fig.colorbar(im, ax=ax, pad=0.015, fraction=0.045)
        cbar.ax.yaxis.set_major_formatter(_eng_formatter())
        cbar.set_label(r"$|I|$(A)", fontsize=6, labelpad=1)
        cbar.ax.tick_params(labelsize=5.5)

    for col, (result, label) in enumerate(zip(results, labels)):
        ax = axes[2, col]
        scaling = result["scaling"]
        sqrt_v = scaling["sqrt_v"]
        y = np.abs(scaling["cathodic_peaks"])
        fit_x = np.linspace(float(sqrt_v.min()), float(sqrt_v.max()), 200)
        fit_y = scaling["cathodic_slope"] * fit_x + scaling["cathodic_intercept"]
        ax.scatter(sqrt_v, y, marker="x", color="#c99a1e", s=12, label="data")
        ax.plot(fit_x, fit_y, color="#d6a928", lw=0.75, label=f"fit ($R^2$={scaling['cathodic_r2']:.3f})")
        ax.set_xlabel(r"$\sqrt{v}$ (mV/s)$^{1/2}$")
        ax.set_ylabel(r"$|I_{peak}|$ (A)")
        ax.yaxis.set_major_formatter(_eng_formatter())
        ax.legend(loc="upper left", fontsize=5.3, frameon=True)
        ax.grid(True, lw=0.25, alpha=0.3)
        ax.text(0.94, 0.08, f"{next(panel)} {label}", transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5)
    return fig


def plot_pdf_fig5(results: list[dict], labels: list[str]) -> plt.Figure:
    """Build a 3x3 Fig. 5 style panel set for x=0/5/10 kinetic decomposition."""
    fig, axes = plt.subplots(3, 3, figsize=(8.95, 6.35), constrained_layout=True)
    _set_layout_pads(fig, w_pad=0.045, h_pad=0.035, wspace=0.07, hspace=0.08)
    panel = iter(["(a)", "(b)", "(c)", "(d)", "(e)", "(f)", "(g)", "(h)", "(i)"])

    for col, (result, label) in enumerate(zip(results, labels)):
        ax = axes[0, col]
        ax.imshow(
            result["ising"][np.newaxis, :],
            origin="lower",
            aspect="auto",
            extent=[result["potential"].min(), result["potential"].max(), 0, 1],
            cmap=ListedColormap(["white", "#e6a400"]),
            vmin=0,
            vmax=1,
        )
        ax.set_yticks([0.15, 0.85], ["DD", "CD"])
        ax.set_xlabel("Potential V(V)")
        ax.set_ylabel("Ising state")
        ax.set_title(f"Ising Kinetic segmentation ({label})", fontsize=7.2)
        _panel_label(ax, next(panel))

    for col, (result, label) in enumerate(zip(results, labels)):
        ax = axes[1, col]
        scores = result["qkpca"]["scores_rate"]
        ax.scatter(scores[:, 0], scores[:, 1], marker="x", color="#7b3f8f", s=16)
        for sr, x, y in zip(result["scan_rates"], scores[:, 0], scores[:, 1]):
            ax.text(x, y, f" {int(sr)}", color="#9a1f1f", fontsize=6, va="center")
        ax.set_xlabel("Quantum KPCA 1")
        ax.set_ylabel("Quantum KPCA 2")
        ax.set_title(f"Quantum kernel PCA ({label})", fontsize=7.2)
        ax.grid(True, lw=0.25, alpha=0.35)
        _panel_label(ax, next(panel))

    grid, doping = _composition_grid(results)
    b_map = np.vstack([_interp_series(r, r["b_values"], grid) for r in results])
    cap_50 = []
    regime_rows = []
    for result in results:
        idx = int(np.argmin(np.abs(result["scan_rates"] - 50.0)))
        cap_50.append(_interp_series(result, result["cap_map"][:, idx], grid))
        regime_rows.append(_interp_series(result, result["ising"].astype(float), grid))
    cap_map = np.vstack(cap_50)
    regime_map = np.vstack(regime_rows)

    ax = axes[2, 0]
    im = ax.imshow(
        b_map,
        origin="lower",
        aspect="auto",
        extent=[grid.min(), grid.max(), doping.min(), doping.max()],
        cmap="viridis",
        vmin=float(np.nanmin(b_map)),
        vmax=float(np.nanmax(b_map)),
    )
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("Cu-doping x (%)")
    ax.text(0.5, 0.88, "$b$-value heatmap", transform=ax.transAxes, color="white", ha="center", fontsize=7, fontweight="bold")
    _panel_label(ax, next(panel))
    cbar = fig.colorbar(im, ax=ax, pad=0.015, fraction=0.045)
    cbar.set_label("$b$ value", fontsize=6, labelpad=1)
    cbar.ax.tick_params(labelsize=5.5)

    ax = axes[2, 1]
    im = ax.imshow(
        cap_map,
        origin="lower",
        aspect="auto",
        extent=[grid.min(), grid.max(), doping.min(), doping.max()],
        cmap="viridis",
        vmin=0,
        vmax=1,
    )
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("Cu-doping x (%)")
    ax.text(
        0.5,
        0.86,
        "Capacitive-fraction heatmap\nat 50 mV/s",
        transform=ax.transAxes,
        color="white",
        ha="center",
        fontsize=7,
        fontweight="bold",
    )
    _panel_label(ax, next(panel))
    cbar = fig.colorbar(im, ax=ax, pad=0.015, fraction=0.045)
    cbar.set_label(r"Capacitive fraction $F_{cap}(V)$", fontsize=6, labelpad=1)
    cbar.ax.tick_params(labelsize=5.5)

    ax = axes[2, 2]
    im = ax.imshow(
        regime_map,
        origin="lower",
        aspect="auto",
        extent=[grid.min(), grid.max(), doping.min(), doping.max()],
        cmap="viridis",
        vmin=0,
        vmax=1,
    )
    ax.set_xlabel("Potential V(V)")
    ax.set_ylabel("Cu-doping x (%)")
    ax.text(
        0.5,
        0.86,
        "Kinetic regime heatmap\nIsing state (0=diffusion, 1=capacitive)",
        transform=ax.transAxes,
        color="white",
        ha="center",
        fontsize=6.3,
        fontweight="bold",
    )
    _panel_label(ax, next(panel))
    cbar = fig.colorbar(im, ax=ax, pad=0.015, fraction=0.045)
    cbar.set_label("Ising state", fontsize=6, labelpad=1)
    cbar.ax.tick_params(labelsize=5.5)
    return fig


def _caption_text(fig_no: int) -> str:
    if fig_no == 4:
        return (
            "Fig. 4. (a)-(c) CV overlays of x = 0, 5, 10% Cu-doping in CoCr2O4 "
            "nanoparticles. I vs V at available scan rates from the supplied CSV files. "
            "(d)-(f) |I(V,v)| heatmaps with potential V vs scan rate v and color as "
            "absolute current |I|. (g)-(i) Linear regression of |Ipeak| vs sqrt(v)."
        )
    return (
        "Fig. 5. (a)-(c) Ising/QUBO-formulated kinetic segmentation for x = 0, 5, "
        "and 10% Cu-doped CoCr2O4. (d)-(f) Kernel-PCA embedding of scan-rate-dependent "
        "CV shapes. (g) b-value heatmap across Cu doping. (h) Capacitive fraction "
        "heatmap from Dunn analysis at the available rate closest to 50 mV/s. "
        "(i) Kinetic regime map from Ising-style segmentation."
    )


def export_pdf_layout_figures(
    composition_paths: list[str | Path],
    output_dir: str | Path,
    dpi: int = 900,
    branch: str = "forward",
    reuse_single: bool = False,
) -> dict:
    if len(composition_paths) == 1 and reuse_single:
        composition_paths = [composition_paths[0], composition_paths[0], composition_paths[0]]
    if len(composition_paths) != 3:
        raise ValueError("Provide three CSV paths for x=0, x=5, x=10, or set reuse_single=True for a layout example.")
    apply_reference_style()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [_subset_scan_rates(analyze_cv(path, branch=branch), max_rate=50.0) for path in composition_paths]
    labels = ["x=0", "x=5%", "x=10%"]
    exports = [
        _save_figure(plot_pdf_fig4(results, labels), output_dir / "fig4_pdf_layout_example.png", dpi),
        _save_figure(plot_pdf_fig5(results, labels), output_dir / "fig5_pdf_layout_example.png", dpi),
    ]
    captions = {"fig4": _caption_text(4), "fig5": _caption_text(5)}
    (output_dir / "fig4_caption.txt").write_text(captions["fig4"], encoding="utf-8")
    (output_dir / "fig5_caption.txt").write_text(captions["fig5"], encoding="utf-8")
    metrics = {
        "composition_paths": [str(Path(p)) for p in composition_paths],
        "reuse_single_csv_layout_example": bool(len(set(map(str, composition_paths))) == 1),
        "scan_rate_rule": "Uses scan rates <= 50 mV/s when available to match the reference PDF style.",
        "exports": exports,
        "caption_files": ["fig4_caption.txt", "fig5_caption.txt"],
    }
    (output_dir / "pdf_layout_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def _metrics(result: dict) -> dict:
    dataset = result["dataset"]
    branch = result["selected_branch"]
    scaling = result["scaling"]
    dunn = result["dunn"]
    b_values = result["b_values"]
    r_squared = result["r_squared"]
    potential = result["potential"]
    currents = result["currents"]
    scan_rates = result["scan_rates"]
    return {
        "raw_rows": int(len(dataset.potential_raw)),
        "raw_unique_potentials": int(len(np.unique(dataset.potential_raw))),
        "detected_branches": [
            {
                "name": item.name,
                "direction": item.direction,
                "rows": int(len(item.potential)),
                "start_idx": int(item.start_idx),
                "end_idx": int(item.end_idx),
                "v_start": float(item.potential[0]),
                "v_end": float(item.potential[-1]),
            }
            for item in dataset.branches
        ],
        "analysis_branch": branch.name,
        "analysis_points": int(len(potential)),
        "potential_min": float(np.min(potential)),
        "potential_max": float(np.max(potential)),
        "scan_rates": [float(v) for v in scan_rates],
        "current_min": float(np.min(currents)),
        "current_max": float(np.max(currents)),
        "mean_b": float(np.nanmean(b_values)),
        "median_b": float(np.nanmedian(b_values)),
        "mean_r_squared": float(np.nanmean(r_squared)),
        "mean_cap_fraction": float(dunn["total_cap_frac"]),
        "cap_fraction_by_rate": [float(v) for v in dunn["cap_frac"]],
        "anodic_peak_r2": float(scaling["anodic_r2"]),
        "cathodic_peak_r2": float(scaling["cathodic_r2"]),
        "anodic_peaks": [float(v) for v in scaling["anodic_peaks"]],
        "cathodic_peaks": [float(v) for v in scaling["cathodic_peaks"]],
        "quantum_kernel": {
            "feature_map": "product Ry angle encoding; K_ij = product_k cos^2((x_ik - x_jk)/2)",
            "kernel_matrix": result["qkpca"]["kernel"].round(12).tolist(),
            "centered_kernel_eigenvalues": [float(v) for v in result["qkpca"]["eigenvalues"]],
            "explained_variance_first_two": [float(v) for v in result["qkpca"]["explained_variance"]],
            "scores_rate": result["qkpca"]["scores_rate"].round(12).tolist(),
        },
    }


def _write_summary_csv(result: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scaling = result["scaling"]
    dunn = result["dunn"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scan_rate_mV_s",
                "sqrt_scan_rate",
                "cap_fraction",
                "diffusion_fraction",
                "anodic_peak_A",
                "cathodic_peak_A",
            ]
        )
        for i, sr in enumerate(result["scan_rates"]):
            writer.writerow(
                [
                    float(sr),
                    float(scaling["sqrt_v"][i]),
                    float(dunn["cap_frac"][i]),
                    float(dunn["dif_frac"][i]),
                    float(scaling["anodic_peaks"][i]),
                    float(scaling["cathodic_peaks"][i]),
                ]
            )


def export_all(
    csv_path: str | Path,
    output_dir: str | Path,
    dpi: int = 900,
    branch: str = "forward",
    plot_titles: dict | None = None,
    palette: str = "turbo",
) -> dict:
    if not (150 <= dpi <= 1200):
        raise ValueError("Use a DPI between 150 and 1200 for exports.")
    apply_reference_style()
    result = analyze_cv(csv_path, branch=branch)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_label = Path(csv_path).stem
    t = plot_titles or {}

    individual_plots = [
        ("fig4a_cv_overlay.png",        plot_fig4a_cv_overlay(result, sample_label, title=t.get("fig4a_cv_overlay", ""), palette=palette)),
        ("fig4b_current_heatmap.png",   plot_fig4b_current_heatmap(result, title=t.get("fig4b_current_heatmap", ""), palette=palette)),
        ("fig4c_peak_scaling.png",      plot_fig4c_peak_scaling(result, title=t.get("fig4c_peak_scaling", ""))),
        ("fig5a_ising_segmentation.png",plot_fig5a_ising_segmentation(result, sample_label, title=t.get("fig5a_ising_segmentation", ""))),
        ("fig5b_quantum_kpca.png",      plot_fig5b_quantum_kpca(result, title=t.get("fig5b_quantum_kpca", ""))),
        ("fig5c_b_value_heatmap.png",   plot_fig5c_b_value_heatmap(result, title=t.get("fig5c_b_value_heatmap", ""), palette=palette)),
        ("fig5d_cap_fraction_map.png",  plot_fig5d_cap_fraction_map(result, title=t.get("fig5d_cap_fraction_map", ""), palette=palette)),
        ("fig5e_kinetic_regime.png",    plot_fig5e_kinetic_regime(result, title=t.get("fig5e_kinetic_regime", ""))),
        ("fig5f_pointwise_scaling.png", plot_fig5f_pointwise_scaling(result, title=t.get("fig5f_pointwise_scaling", ""))),
    ]
    exports = [_save_figure(fig, output_dir / name, dpi) for name, fig in individual_plots]

    metrics = _metrics(result)
    metrics["exports"] = exports
    (output_dir / "analysis_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    _write_summary_csv(result, output_dir / "summary_table.csv")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reference-style high-DPI CV figures.")
    parser.add_argument("csv_path", nargs="?", default="AV.csv")
    parser.add_argument("--output", default="output/reference_style")
    parser.add_argument("--dpi", type=int, default=900)
    parser.add_argument("--branch", default="forward")
    parser.add_argument("--x0", default=None, help="CSV for x=0 composition")
    parser.add_argument("--x5", default=None, help="CSV for x=5% composition")
    parser.add_argument("--x10", default=None, help="CSV for x=10% composition")
    args = parser.parse_args()
    metrics = export_all(args.csv_path, args.output, dpi=args.dpi, branch=args.branch)
    if args.x0 and args.x5 and args.x10:
        metrics["real_three_composition_pdf_layout"] = export_pdf_layout_figures(
            [args.x0, args.x5, args.x10],
            args.output,
            dpi=args.dpi,
            branch=args.branch,
            reuse_single=False,
        )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
