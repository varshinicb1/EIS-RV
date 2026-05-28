"""
compare_plots.py — Multi-job comparison grid generator.

Usage (via JSON config):
    python compare_plots.py <config_json_path>

Config schema:
    {
        "job_entries": [
            {"csv_path": "...", "label": "Sample A"},
            ...
        ],
        "plot_types": ["fig4a_cv_overlay", "fig5e_kinetic_regime", ...],
        "palette": "turbo",
        "dpi": 300,
        "output_path": "/tmp/rvce_compare/<id>/comparison.png",
        "plot_titles": {}
    }

Outputs: JSON to stdout with {ok, output_path, width_px, height_px} or {ok=false, error}.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from reference_plots import (
    analyze_cv,
    apply_reference_style,
    AVAILABLE_PALETTES,
    _scan_colors,
    _set_custom_title,
    _eng_formatter,
    _panel_label,
    _regime_ising_like,
    _cap_fraction_map,
    quantum_kernel_pca_analysis,
)
from matplotlib.colors import ListedColormap
from PIL import Image


PLOT_LABELS = {
    "fig4a_cv_overlay":       "CV Overlay",
    "fig4b_current_heatmap":  "|I(V,ν)| Heatmap",
    "fig4c_peak_scaling":     "Randles-Ševčík",
    "fig5a_ising_segmentation": "Ising Segmentation",
    "fig5b_quantum_kpca":     "Quantum-Kernel PCA",
    "fig5c_b_value_heatmap":  "b-Value Heatmap",
    "fig5d_cap_fraction_map": "Cap. Fraction Map",
    "fig5e_kinetic_regime":   "Kinetic Regime (DD/CD)",
    "fig5f_pointwise_scaling":"Pointwise b-Value",
}

ALL_PLOT_TYPES = list(PLOT_LABELS.keys())


def _draw_cell(ax: plt.Axes, result: dict, plot_type: str, palette: str, title: str = "") -> None:
    safe = palette if palette in AVAILABLE_PALETTES else "turbo"
    potential = result["potential"]
    currents = result["currents"]
    scan_rates = result["scan_rates"]

    if plot_type == "fig4a_cv_overlay":
        dataset = result["dataset"]
        colors = _scan_colors(len(scan_rates), safe)
        for j, (sr, c) in enumerate(zip(scan_rates, colors)):
            ax.plot(dataset.potential_raw, dataset.currents_raw[:, j], color=c, lw=0.75)
        ax.axhline(0, color="0.6", lw=0.35)
        ax.set_xlabel("V (V)", fontsize=6)
        ax.set_ylabel("I (A)", fontsize=6)
        ax.yaxis.set_major_formatter(_eng_formatter())

    elif plot_type == "fig4b_current_heatmap":
        hp = safe if safe in AVAILABLE_PALETTES else "viridis"
        ax.imshow(np.abs(currents).T, origin="lower", aspect="auto",
                  extent=[potential.min(), potential.max(), scan_rates.min(), scan_rates.max()],
                  cmap=hp)
        ax.set_xlabel("V (V)", fontsize=6)
        ax.set_ylabel("ν (mV/s)", fontsize=6)

    elif plot_type == "fig4c_peak_scaling":
        from analysis import peak_scaling_analysis
        scaling = result["scaling"]
        sqrt_v = scaling["sqrt_v"]
        y = np.abs(scaling["cathodic_peaks"])
        fit_x = np.linspace(float(sqrt_v.min()), float(sqrt_v.max()), 100)
        fit_y = scaling["cathodic_slope"] * fit_x + scaling["cathodic_intercept"]
        ax.scatter(sqrt_v, y, color="#c99a1e", marker="x", s=10)
        ax.plot(fit_x, fit_y, color="#d6a928", lw=0.75,
                label=f"R²={scaling['cathodic_r2']:.3f}")
        ax.set_xlabel(r"√ν", fontsize=6)
        ax.set_ylabel(r"|Ip| (A)", fontsize=6)
        ax.yaxis.set_major_formatter(_eng_formatter())
        ax.legend(fontsize=5, frameon=True)

    elif plot_type == "fig5a_ising_segmentation":
        ising = result["ising"]
        ax.imshow(ising[np.newaxis, :], origin="lower", aspect="auto",
                  extent=[potential.min(), potential.max(), 0, 1],
                  cmap=ListedColormap(["#d62728", "#1f77b4"]), vmin=0, vmax=1)
        ax.set_yticks([0.25, 0.75], ["DD", "CD"], fontsize=5)
        ax.set_xlabel("V (V)", fontsize=6)

    elif plot_type == "fig5b_quantum_kpca":
        scores = result["qkpca"]["scores_rate"]
        ax.scatter(scores[:, 0], scores[:, 1], marker="x", color="#7b3f8f", s=14)
        for sr, x, y in zip(scan_rates, scores[:, 0], scores[:, 1]):
            ax.text(x, y, f" {int(sr)}", fontsize=4.5, color="#9a1f1f", va="center")
        ax.set_xlabel("QKPCA 1", fontsize=6)
        ax.set_ylabel("QKPCA 2", fontsize=6)
        ax.grid(True, lw=0.25, alpha=0.3)

    elif plot_type == "fig5c_b_value_heatmap":
        b = result["b_values"]
        ax.imshow(np.clip(b, 0, 1.2)[np.newaxis, :], origin="lower", aspect="auto",
                  extent=[potential.min(), potential.max(), 0, 1],
                  cmap="RdYlBu_r", vmin=0.4, vmax=1.05)
        ax.set_yticks([])
        ax.set_xlabel("V (V)", fontsize=6)

    elif plot_type == "fig5d_cap_fraction_map":
        cap = result["cap_map"]
        hp = safe if safe in AVAILABLE_PALETTES else "viridis"
        ax.imshow(cap.T, origin="lower", aspect="auto",
                  extent=[potential.min(), potential.max(), scan_rates.min(), scan_rates.max()],
                  cmap=hp, vmin=0, vmax=1)
        ax.set_xlabel("V (V)", fontsize=6)
        ax.set_ylabel("ν (mV/s)", fontsize=6)

    elif plot_type == "fig5e_kinetic_regime":
        ising = result["ising"]
        ising_tile = np.tile(ising, (len(scan_rates), 1))
        ax.imshow(ising_tile, origin="lower", aspect="auto",
                  extent=[potential.min(), potential.max(), scan_rates.min(), scan_rates.max()],
                  cmap=ListedColormap(["#d62728", "#1f77b4"]), vmin=0, vmax=1)
        ax.set_xlabel("V (V)", fontsize=6)
        ax.set_ylabel("ν (mV/s)", fontsize=6)

    elif plot_type == "fig5f_pointwise_scaling":
        b = result["b_values"]
        ax.plot(potential, b, color="#1f6f9e", lw=0.75)
        ax.axhline(1.0, color="#d62728", ls="--", lw=0.6)
        ax.axhline(0.5, color="#2ca02c", ls="--", lw=0.6)
        ax.axhline(0.75, color="#ff7f0e", ls=":", lw=0.5)
        ax.set_xlabel("V (V)", fontsize=6)
        ax.set_ylabel("b value", fontsize=6)

    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontsize(5)

    if title:
        ax.set_title(title, fontfamily="Times New Roman", fontweight="bold", fontsize=11)


def generate_comparison(
    job_entries: list[dict],
    plot_types: list[str],
    palette: str = "turbo",
    dpi: int = 300,
    plot_titles: dict | None = None,
    output_path: str | Path | None = None,
) -> dict:
    """
    Generate a comparison grid PNG.

    job_entries: list of {"csv_path": str, "label": str}
    plot_types:  subset of ALL_PLOT_TYPES
    Returns: {"ok": True, "output_path": str, "width_px": int, "height_px": int}
    """
    apply_reference_style()
    n_jobs = len(job_entries)
    n_plots = len(plot_types)
    if n_jobs == 0 or n_plots == 0:
        return {"ok": False, "error": "No jobs or plot types specified."}

    results = []
    labels = []
    for entry in job_entries:
        try:
            r = analyze_cv(entry["csv_path"])
            results.append(r)
            labels.append(entry.get("label", Path(entry["csv_path"]).stem))
        except Exception as e:
            return {"ok": False, "error": f"Failed to analyze {entry['csv_path']}: {e}"}

    cell_w = 3.2
    cell_h = 2.5
    label_col_w = 1.4
    header_row_h = 0.5

    fig_w = label_col_w + n_plots * cell_w
    fig_h = header_row_h + n_jobs * cell_h

    fig, axes = plt.subplots(
        n_jobs, n_plots,
        figsize=(fig_w, fig_h),
        constrained_layout=True,
        squeeze=False,
    )
    fig.patch.set_facecolor("white")

    pt = plot_titles or {}

    for row, (result, label) in enumerate(zip(results, labels)):
        for col, plot_type in enumerate(plot_types):
            ax = axes[row, col]
            title_text = pt.get(plot_type, "") if row == 0 else ""
            _draw_cell(ax, result, plot_type, palette, title=title_text)

            if col == 0:
                ax.annotate(
                    label,
                    xy=(-0.28, 0.5),
                    xycoords="axes fraction",
                    fontsize=7,
                    fontweight="bold",
                    rotation=90,
                    va="center",
                    ha="center",
                    clip_on=False,
                )
            if row == 0 and not title_text:
                ax.set_title(PLOT_LABELS.get(plot_type, plot_type), fontsize=7, fontweight="bold")

    if output_path is None:
        output_path = Path("/tmp") / "comparison.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    width_px = height_px = 0
    with Image.open(output_path) as img:
        width_px, height_px = img.width, img.height

    return {
        "ok": True,
        "output_path": str(output_path),
        "width_px": width_px,
        "height_px": height_px,
        "n_jobs": n_jobs,
        "n_plots": n_plots,
    }


def main() -> None:
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "Usage: compare_plots.py <config_json_path>"}))
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(json.dumps({"ok": False, "error": f"Config not found: {config_path}"}))
        sys.exit(1)

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Bad config JSON: {e}"}))
        sys.exit(1)

    try:
        result = generate_comparison(
            job_entries=config.get("job_entries", []),
            plot_types=config.get("plot_types") or ALL_PLOT_TYPES,
            palette=config.get("palette", "turbo"),
            dpi=config.get("dpi", 300),
            plot_titles=config.get("plot_titles"),
            output_path=config.get("output_path"),
        )
        print(json.dumps(result))
        sys.exit(0 if result.get("ok") else 1)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
