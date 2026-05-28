"""
plotter.py — Publication-grade matplotlib figure generation for CV analysis.

Design philosophy:
  - White background, no chart junk
  - constrained_layout=True on every figure → no clipped labels
  - Scientific tick formatting (engineering notation for small currents)
  - Colormap: tab10 for multi-scan overlays; viridis for heatmaps
  - All figures returned as matplotlib Figure objects (caller saves or embeds)
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.gridspec import GridSpec

# ── Global rcParams for publication quality ───────────────────────────────
matplotlib.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "legend.frameon": True,
    "legend.framealpha": 0.9,
    "legend.edgecolor": "#cccccc",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "lines.linewidth": 1.5,
    "image.cmap": "viridis",
    "pdf.fonttype": 42,   # TrueType fonts in PDF → editable in Illustrator
    "svg.fonttype": "none",
})

# Publication themes (10 grade palettes)
THEMES = {
    "Set1 (Reference)": ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#ffff33", "#a65628", "#f781bf", "#999999", "#444444"],
    "Classic (tab10)": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"],
    "Nature / NPG": ["#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F", "#8491B6", "#91D1C2", "#DC0000", "#7E6148", "#B09C85"],
    "Science / AAAS": ["#BC3C29", "#0072B5", "#20854E", "#E18727", "#7876B1", "#6F99AD", "#FFDC91", "#EE4C97", "#505050", "#111111"],
    "Lancet": ["#00468B", "#ED0000", "#42B540", "#0099B4", "#925E9F", "#FDAF91", "#AD002A", "#ADB6B6", "#333333", "#777777"],
    "IEEE": ["#0062B2", "#D95319", "#EDB120", "#7E2F8E", "#77AC30", "#4DBEEE", "#A2142F", "#000000", "#555555", "#888888"],
    "Viridis": ["#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"],
    "Plasma": ["#0d0887", "#46039f", "#7201a8", "#9c179e", "#bd3786", "#d8576b", "#ed7953", "#fb9f3a", "#fdca26", "#f0f921"],
    "Muted": ["#488f31", "#75a452", "#9eb975", "#c5ce9b", "#ebe2c3", "#e0b88c", "#d48c5c", "#c55f37", "#b33126", "#800000"],
    "Coolwarm": ["#3b4cc0", "#5172db", "#6f96f4", "#93b5ff", "#c0d4f5", "#f1c2a8", "#f29375", "#e45f49", "#c62c26", "#b40426"]
}

CURRENT_THEME = "Set1 (Reference)"

def _get_scan_rate_colors(scan_rates, theme=None):
    """Return a list of colors cycling through a theme for multiple scan rates."""
    t_name = theme or CURRENT_THEME
    colors = THEMES.get(t_name, THEMES["Set1 (Reference)"])
    return [colors[i % len(colors)] for i in range(len(scan_rates))]

def _apply_axis_style(ax, xlabel=None, ylabel=None):
    """Applies Times New Roman bold 18pt font and inward ticks on all four sides."""
    if xlabel:
        ax.set_xlabel(xlabel, fontname="Times New Roman", fontsize=18, fontweight="bold")
    if ylabel:
        ax.set_ylabel(ylabel, fontname="Times New Roman", fontsize=18, fontweight="bold")

    # Inward ticks pointing inwards on all sides
    ax.tick_params(direction="in", top=True, right=True, which="both", labelsize=14)

    # Update tick label fonts
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontname("Times New Roman")

def _setup_current_axis(ax, label: str = "Current I (A)"):
    """Uses regular float formatting without engineering notation (no mA, uA)."""
    formatter = mticker.ScalarFormatter()
    formatter.set_scientific(False)
    formatter.set_powerlimits((-4, 4))
    ax.yaxis.set_major_formatter(formatter)
    _apply_axis_style(ax, ylabel=label)


_eng_fmt = mticker.EngFormatter(unit="A", places=1)



# ══════════════════════════════════════════════════════════════════════════════
#  1. CV OVERLAY PLOT
# ══════════════════════════════════════════════════════════════════════════════

def plot_cv_overlay(
    potential: np.ndarray,
    currents: np.ndarray,
    scan_rates: list[float],
    smooth: bool = False,
    linewidth: float = 1.5,
    font_size: int = 11,
    theme: str | None = None,
) -> plt.Figure:
    """
    Multi-scan CV overlay: Current vs Potential.
    One subplot per scan rate is NOT used — all overlaid on one axes.
    """
    from scipy.signal import savgol_filter

    matplotlib.rcParams["font.size"] = font_size
    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)

    colors = _get_scan_rate_colors(scan_rates, theme=theme)

    for j, (sr, color) in enumerate(zip(scan_rates, colors)):
        curr = currents[:, j]
        if smooth and len(curr) >= 15:
            win = min(15, len(curr) // 5 * 2 + 1)
            if win % 2 == 0:
                win += 1
            curr = savgol_filter(curr, window_length=win, polyorder=3)
        ax.plot(
            potential, curr,
            color=color, linewidth=linewidth,
            label=f"{int(sr)} mV/s",
        )

    ax.axhline(0, color="black", linewidth=0.5, linestyle="--", alpha=0.4)
    _setup_current_axis(ax, label="Current I (A)")
    _apply_axis_style(ax, xlabel="Potential V(V)")

    # Legend inside the plot with white background and thin border
    if len(scan_rates) > 6:
        legend = ax.legend(
            loc="upper left", bbox_to_anchor=(1.01, 1),
            borderaxespad=0, ncol=1, frameon=True, facecolor="white", edgecolor="#cccccc"
        )
        fig.set_size_inches(8.5, 5)
    else:
        legend = ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#cccccc")

    for text in legend.get_texts():
        text.set_fontname("Times New Roman")

    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  2. CURRENT HEATMAP (Voltage × Scan Rate)
# ══════════════════════════════════════════════════════════════════════════════

def plot_current_heatmap(
    potential: np.ndarray,
    currents: np.ndarray,
    scan_rates: list[float],
    theme: str | None = None,
) -> plt.Figure:
    """
    2D heatmap: x=scan rate, y=potential, color=current.
    Uses pcolormesh for correct cell alignment.
    """
    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)

    sr_arr = np.array(scan_rates, dtype=float)
    # pcolormesh requires edges — compute midpoint-based edges
    v_edges = np.concatenate([
        [potential[0] - (potential[1] - potential[0]) / 2],
        (potential[:-1] + potential[1:]) / 2,
        [potential[-1] + (potential[-1] - potential[-2]) / 2],
    ])
    sr_edges = np.concatenate([
        [sr_arr[0] - (sr_arr[1] - sr_arr[0]) / 2] if len(sr_arr) > 1 else [sr_arr[0] * 0.9],
        (sr_arr[:-1] + sr_arr[1:]) / 2,
        [sr_arr[-1] + (sr_arr[-1] - sr_arr[-2]) / 2] if len(sr_arr) > 1 else [sr_arr[0] * 1.1],
    ])

    # currents is (N_pot, N_sr); pcolormesh(X, Y, Z): X→cols, Y→rows
    # We want x=scan_rate, y=potential
    pcm = ax.pcolormesh(
        sr_edges, v_edges, currents,
        cmap="RdBu_r", shading="flat",
    )
    cbar = fig.colorbar(pcm, ax=ax, pad=0.02)
    cbar.set_label("Current I (A)", fontname="Times New Roman", fontsize=14, fontweight="bold")

    formatter = mticker.ScalarFormatter()
    formatter.set_scientific(False)
    formatter.set_powerlimits((-4, 4))
    cbar.formatter = formatter
    cbar.update_ticks()

    for t_label in cbar.ax.get_yticklabels():
        t_label.set_fontname("Times New Roman")

    _apply_axis_style(ax, xlabel="Scan Rate (mV/s)", ylabel="Potential V(V)")


    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  3. b-VALUE ANALYSIS PLOTS
# ══════════════════════════════════════════════════════════════════════════════

def plot_b_values(
    potential: np.ndarray,
    b_values: np.ndarray,
    r_squared: np.ndarray,
    theme: str | None = None,
) -> plt.Figure:
    """
    b-value vs potential, with R² overlay.
    Horizontal reference lines at b=0.5 (diffusion) and b=1.0 (capacitive).
    """
    fig, axes = plt.subplots(2, 1, figsize=(7, 6), constrained_layout=True,
                              sharex=True)

    ax1, ax2 = axes

    # Filter NaN regions
    valid = ~np.isnan(b_values)

    ax1.plot(potential[valid], b_values[valid], color="#1a6faf", linewidth=1.5)
    ax1.axhline(1.0, color="#d62728", linestyle="--", linewidth=1.0,
                label="b=1 (capacitive)")
    ax1.axhline(0.5, color="#2ca02c", linestyle="--", linewidth=1.0,
                label="b=0.5 (diffusion)")

    _apply_axis_style(ax1, ylabel="b-value")
    ax1.set_ylim(
        max(0, np.nanmin(b_values) - 0.1),
        min(1.5, np.nanmax(b_values) + 0.1),
    )
    legend = ax1.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#cccccc")
    for text in legend.get_texts():
        text.set_fontname("Times New Roman")

    ax2.plot(potential[valid], r_squared[valid], color="#6b4c9a", linewidth=1.5)
    ax2.axhline(0.95, color="gray", linestyle=":", linewidth=0.8)
    _apply_axis_style(ax2, xlabel="Potential V(V)", ylabel="R² (fit quality)")
    ax2.set_ylim(0, 1.05)

    return fig


def plot_b_value_heatmap(
    potential: np.ndarray,
    b_values: np.ndarray,
    theme: str | None = None,
) -> plt.Figure:
    """
    Single-axis colormap of b-value vs potential (1D strip heatmap).
    Useful for spatial mapping of kinetic regime.
    """
    fig, ax = plt.subplots(figsize=(8, 2.0), constrained_layout=True)

    valid = ~np.isnan(b_values)
    bv_plot = b_values.copy()
    bv_plot[~valid] = np.nanmean(b_values)

    norm = Normalize(vmin=0.4, vmax=1.1)
    sm = ScalarMappable(cmap="coolwarm", norm=norm)
    sm.set_array([])

    colors = sm.cmap(norm(bv_plot))
    for i in range(len(potential) - 1):
        ax.axvspan(potential[i], potential[i + 1], color=colors[i], alpha=0.9)

    cbar = fig.colorbar(sm, ax=ax, orientation="vertical", pad=0.01)
    cbar.set_label("b-value", fontname="Times New Roman", fontsize=14, fontweight="bold")

    for t_label in cbar.ax.get_yticklabels():
        t_label.set_fontname("Times New Roman")

    _apply_axis_style(ax, xlabel="Potential V(V)")
    ax.set_yticks([])

    ax.set_title("b-value Spatial Map  (blue=diffusion, red=capacitive)")

    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  4. DUNN DECOMPOSITION PLOTS
# ══════════════════════════════════════════════════════════════════════════════

def plot_dunn_decomposition(
    potential: np.ndarray,
    currents: np.ndarray,
    dunn_result: dict,
    scan_rates: list[float],
    scan_rate_idx: int = -1,
) -> plt.Figure:
    """
    Show total, capacitive, and diffusive current at a selected scan rate.
    Default: last (highest) scan rate.
    """
    j = scan_rate_idx
    sr = scan_rates[j]

    total = currents[:, j]
    cap = dunn_result["cap_current"][:, j]
    dif = dunn_result["dif_current"][:, j]

    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)

    ax.plot(potential, total, color="black", linewidth=1.8, label="Total", zorder=3)
    ax.fill_between(potential, cap, alpha=0.5, color="#2196F3",
                    label=f"Capacitive ({dunn_result['cap_frac'][j]*100:.1f}%)")
    ax.fill_between(potential, dif, alpha=0.5, color="#FF9800",
                    label=f"Diffusion ({dunn_result['dif_frac'][j]*100:.1f}%)")

    ax.axhline(0, color="black", linewidth=0.5, linestyle="--", alpha=0.4)
    ax.set_xlabel("Potential (V)")
    _setup_current_axis(ax)
    ax.legend(loc="upper left")
    ax.set_title(
        f"Dunn Decomposition at {int(sr)} mV/s\n"
        f"[i(V,v) = k₁v + k₂√v]"
    )

    return fig


def plot_dunn_fractions(
    scan_rates: list[float],
    dunn_result: dict,
) -> plt.Figure:
    """
    Stacked bar chart of capacitive vs diffusive charge fraction per scan rate.
    """
    sr_arr = np.array(scan_rates, dtype=float)
    cap_frac = dunn_result["cap_frac"] * 100
    dif_frac = dunn_result["dif_frac"] * 100

    fig, ax = plt.subplots(figsize=(7, 4.5), constrained_layout=True)

    x = np.arange(len(sr_arr))
    w = 0.55
    ax.bar(x, cap_frac, width=w, color="#2196F3", label="Capacitive")
    ax.bar(x, dif_frac, width=w, bottom=cap_frac, color="#FF9800", label="Diffusion")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(s)}" for s in sr_arr], rotation=45, ha="right")
    ax.set_xlabel("Scan Rate (mV/s)")
    ax.set_ylabel("Charge Fraction (%)")
    ax.set_ylim(0, 110)
    ax.axhline(100, color="gray", linewidth=0.5)
    ax.legend(loc="upper right")
    ax.set_title("Capacitive vs Diffusion Contribution per Scan Rate")

    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  5. PEAK ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def plot_peaks(
    potential: np.ndarray,
    current: np.ndarray,
    peaks: dict,
    scan_rate: float,
) -> plt.Figure:
    """
    Single CV curve with detected peaks annotated.
    """
    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)

    ax.plot(potential, current, color="#1a1a1a", linewidth=1.5)
    ax.axhline(0, color="gray", linewidth=0.5, linestyle="--", alpha=0.4)

    # Anodic peaks
    if len(peaks["anodic_idx"]) > 0:
        ax.scatter(
            peaks["anodic_potential"], peaks["anodic_current"],
            color="#d62728", zorder=5, s=60, marker="^",
            label="Anodic peak",
        )

    # Cathodic peaks
    if len(peaks["cathodic_idx"]) > 0:
        ax.scatter(
            peaks["cathodic_potential"], peaks["cathodic_current"],
            color="#1f77b4", zorder=5, s=60, marker="v",
            label="Cathodic peak",
        )

    if peaks["peak_separation"] is not None:
        ax.set_title(
            f"Peak Analysis — {int(scan_rate)} mV/s  "
            f"(ΔEp = {peaks['peak_separation']*1000:.1f} mV)"
        )
    else:
        ax.set_title(f"Peak Analysis — {int(scan_rate)} mV/s")

    ax.set_xlabel("Potential (V)")
    _setup_current_axis(ax)
    ax.legend(loc="best")

    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  6. PEAK SCALING (Ip vs sqrt(v))
# ══════════════════════════════════════════════════════════════════════════════

def plot_peak_scaling(scaling: dict, scan_rates: list[float]) -> plt.Figure:
    """
    Ip vs sqrt(v) for anodic and cathodic peaks, with linear fit.
    """
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), constrained_layout=True)

    sqrt_v = scaling["sqrt_v"]
    fit_x = np.linspace(sqrt_v.min(), sqrt_v.max(), 200)

    for ax, key_peak, key_slope, key_int, key_r2, title, color in [
        (axes[0],
         "anodic_peaks", "anodic_slope", "anodic_intercept", "anodic_r2",
         "Anodic Peak Current vs √v", "#d62728"),
        (axes[1],
         "cathodic_peaks", "cathodic_slope", "cathodic_intercept", "cathodic_r2",
         "|Cathodic Peak Current| vs √v", "#1f77b4"),
    ]:
        ydata = scaling[key_peak] if "anodic" in key_peak else np.abs(scaling[key_peak])
        fit_y = scaling[key_slope] * fit_x + scaling[key_int]

        ax.scatter(sqrt_v, ydata, color=color, s=50, zorder=5, label="Data")
        ax.plot(fit_x, fit_y, color="black", linewidth=1.2, linestyle="--",
                label=f"Fit  R²={scaling[key_r2]:.4f}")

        ax.set_xlabel("√(Scan Rate)  (√[mV/s])")
        ax.yaxis.set_major_formatter(_eng_fmt)
        ax.set_ylabel("Peak Current (A)")
        ax.set_title(title)
        ax.legend(loc="upper left")

    fig.suptitle("Peak Current Scaling Analysis  (Randles-Ševčík Diagnostic)",
                 fontsize=12, y=1.02)

    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  7. KINETIC REGIME MAP
# ══════════════════════════════════════════════════════════════════════════════

def plot_kinetic_regime(
    potential: np.ndarray,
    regime: np.ndarray,
    b_values: np.ndarray,
) -> plt.Figure:
    """
    Two-panel: regime strip + b-value line for comparison.
    """
    fig = plt.figure(figsize=(8, 4), constrained_layout=True)
    gs = GridSpec(2, 1, figure=fig, height_ratios=[1, 3], hspace=0.05)

    ax_strip = fig.add_subplot(gs[0])
    ax_b = fig.add_subplot(gs[1], sharex=ax_strip)

    # Regime color strip
    cmap_reg = matplotlib.colors.ListedColormap(["#FF9800", "#BDBDBD", "#2196F3"])
    norm_reg = matplotlib.colors.BoundaryNorm([0, 0.25, 0.75, 1.0], cmap_reg.N)
    for i in range(len(potential) - 1):
        ax_strip.axvspan(
            potential[i], potential[i + 1],
            color=cmap_reg(norm_reg(regime[i])), alpha=0.85
        )
    ax_strip.set_yticks([])
    ax_strip.set_ylabel("Regime", fontsize=9)
    ax_strip.set_title(
        "Kinetic Regime Map  (orange=diffusion, grey=mixed, blue=capacitive)"
    )

    # b-value line
    valid = ~np.isnan(b_values)
    ax_b.plot(potential[valid], b_values[valid], color="#1a6faf", linewidth=1.5)
    ax_b.axhline(1.0, color="#d62728", linestyle="--", linewidth=0.9, label="b=1")
    ax_b.axhline(0.5, color="#2ca02c", linestyle="--", linewidth=0.9, label="b=0.5")
    ax_b.set_ylabel("b-value")
    ax_b.set_xlabel("Potential (V)")
    ax_b.legend(loc="upper right")

    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  8. PCA PLOTS
# ══════════════════════════════════════════════════════════════════════════════

def plot_pca(pca_result: dict) -> plt.Figure:
    """
    Two-panel PCA: voltage-point embedding and scan-rate embedding.
    """
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)

    # Voltage-point PCA (colored by index = potential order)
    ax = axes[0]
    scores_v = pca_result["pca_scores_voltage"]
    ev_v = pca_result["explained_variance_voltage"]
    n_pts = len(scores_v)

    sc = ax.scatter(
        scores_v[:, 0], scores_v[:, 1],
        c=np.arange(n_pts), cmap="plasma",
        s=8, alpha=0.7, rasterized=True,
    )
    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Potential index (low→high V)")
    ax.set_xlabel(f"PC1 ({ev_v[0]*100:.1f}% var)")
    ax.set_ylabel(f"PC2 ({ev_v[1]*100:.1f}% var)" if len(ev_v) > 1 else "PC2")
    ax.set_title("PCA — Voltage Points")

    # Scan-rate PCA (labeled by scan rate value)
    ax2 = axes[1]
    scores_r = pca_result["pca_scores_rate"]
    ev_r = pca_result["explained_variance_rate"]
    scan_rates = pca_result["scan_rates"]

    norm_sr = Normalize(vmin=scan_rates.min(), vmax=scan_rates.max())
    colors_sr = plt.get_cmap("viridis")(norm_sr(scan_rates))

    for i, (sr, color) in enumerate(zip(scan_rates, colors_sr)):
        ax2.scatter(scores_r[i, 0], scores_r[i, 1], color=color, s=60, zorder=5)
        ax2.annotate(
            f"{int(sr)}",
            (scores_r[i, 0], scores_r[i, 1]),
            fontsize=8, ha="center", va="bottom",
            xytext=(0, 4), textcoords="offset points",
        )

    ax2.set_xlabel(f"PC1 ({ev_r[0]*100:.1f}% var)")
    ax2.set_ylabel(f"PC2 ({ev_r[1]*100:.1f}% var)" if len(ev_r) > 1 else "PC2")
    ax2.set_title("PCA — Scan Rate Curves (mV/s)")

    fig.suptitle("PCA Embedding Analysis", fontsize=12)

    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  SUMMARY STATISTICS TABLE (text figure)
# ══════════════════════════════════════════════════════════════════════════════

def plot_summary_table(
    scan_rates: list[float],
    b_values: np.ndarray,
    dunn_result: dict,
    scaling: dict,
) -> plt.Figure:
    """
    Render a clean statistics table as a matplotlib figure.
    """
    sr_arr = np.array(scan_rates, dtype=float)
    avg_b = np.nanmean(b_values)

    col_labels = ["Scan Rate\n(mV/s)", "Cap Fraction\n(%)", "Dif Fraction\n(%)",
                  "Anodic Ip\n(A)", "|Cathodic Ip|\n(A)"]
    rows = []
    for j, sr in enumerate(sr_arr):
        rows.append([
            f"{int(sr)}",
            f"{dunn_result['cap_frac'][j]*100:.1f}",
            f"{dunn_result['dif_frac'][j]*100:.1f}",
            f"{scaling['anodic_peaks'][j]:.3e}",
            f"{abs(scaling['cathodic_peaks'][j]):.3e}",
        ])

    fig, ax = plt.subplots(
        figsize=(9, max(2.5, 0.4 * len(rows) + 1.5)),
        constrained_layout=True,
    )
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)

    # Style header row
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#E3F2FD")
        table[0, j].set_text_props(fontweight="bold")

    ax.set_title(
        f"Summary Statistics  |  Mean b = {avg_b:.3f}  |  "
        f"Mean Cap Fraction = {dunn_result['total_cap_frac']*100:.1f}%",
        pad=10,
    )

    return fig
