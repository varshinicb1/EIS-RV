from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from reference_plots import analyze_cv


DEFAULT_BASE = Path("output/final_verified_av")


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def export(csv_path: str | Path = "AV.csv", output_dir: str | Path = DEFAULT_BASE) -> list[Path]:
    base = Path(output_dir)
    data_dir = base / "plot_data_csv"
    result = analyze_cv(csv_path)
    dataset = result["dataset"]
    potential = result["potential"]
    currents = result["currents"]
    scan_rates = result["scan_rates"]
    b_values = result["b_values"]
    r_squared = result["r_squared"]
    dunn = result["dunn"]
    scaling = result["scaling"]
    q = result["qkpca"]
    cap_map = result["cap_map"]
    regime = result["regime"]
    ising = result["ising"]

    paths: list[Path] = []

    header = ["potential_V"] + [f"I_{int(sr)}mVs_A" for sr in scan_rates]
    rows = [
        [float(v)] + [float(x) for x in dataset.currents_raw[i, :]]
        for i, v in enumerate(dataset.potential_raw)
    ]
    path = data_dir / "01_cv_overlay_raw_loop.csv"
    write_csv(path, header, rows)
    paths.append(path)

    header = ["potential_V"] + [f"abs_I_{int(sr)}mVs_A" for sr in scan_rates]
    rows = [[float(v)] + [float(x) for x in np.abs(currents[i, :])] for i, v in enumerate(potential)]
    path = data_dir / "02_current_heatmap_abs_current.csv"
    write_csv(path, header, rows)
    paths.append(path)

    header = ["potential_V", "b_value", "r_squared", "regime_threshold", "ising_state"]
    rows = [
        [float(v), float(b_values[i]), float(r_squared[i]), float(regime[i]), int(ising[i])]
        for i, v in enumerate(potential)
    ]
    path = data_dir / "03_b_values_and_regimes.csv"
    write_csv(path, header, rows)
    paths.append(path)

    header = ["potential_V"] + [f"cap_fraction_{int(sr)}mVs" for sr in scan_rates]
    rows = [[float(v)] + [float(x) for x in cap_map[i, :]] for i, v in enumerate(potential)]
    path = data_dir / "04_capacitive_fraction_map.csv"
    write_csv(path, header, rows)
    paths.append(path)

    header = ["potential_V"]
    for sr in scan_rates:
        header += [f"total_{int(sr)}mVs_A", f"cap_{int(sr)}mVs_A", f"diff_{int(sr)}mVs_A"]
    rows = []
    for i, v in enumerate(potential):
        row = [float(v)]
        for j in range(len(scan_rates)):
            row += [
                float(currents[i, j]),
                float(dunn["cap_current"][i, j]),
                float(dunn["dif_current"][i, j]),
            ]
        rows.append(row)
    path = data_dir / "05_dunn_decomposition_currents.csv"
    write_csv(path, header, rows)
    paths.append(path)

    header = ["scan_rate_mV_s", "cap_fraction", "diffusion_fraction"]
    rows = [
        [float(sr), float(dunn["cap_frac"][i]), float(dunn["dif_frac"][i])]
        for i, sr in enumerate(scan_rates)
    ]
    path = data_dir / "06_dunn_fractions_by_scan_rate.csv"
    write_csv(path, header, rows)
    paths.append(path)

    sqrt_v = scaling["sqrt_v"]
    header = [
        "scan_rate_mV_s",
        "sqrt_scan_rate",
        "anodic_peak_A",
        "cathodic_peak_A",
        "abs_cathodic_peak_A",
        "anodic_fit_A",
        "cathodic_fit_A",
    ]
    rows = []
    for i, sr in enumerate(scan_rates):
        rows.append(
            [
                float(sr),
                float(sqrt_v[i]),
                float(scaling["anodic_peaks"][i]),
                float(scaling["cathodic_peaks"][i]),
                float(abs(scaling["cathodic_peaks"][i])),
                float(scaling["anodic_slope"] * sqrt_v[i] + scaling["anodic_intercept"]),
                float(scaling["cathodic_slope"] * sqrt_v[i] + scaling["cathodic_intercept"]),
            ]
        )
    path = data_dir / "07_peak_scaling_points_and_fits.csv"
    write_csv(path, header, rows)
    paths.append(path)

    header = ["scan_rate_mV_s"] + [f"K_{int(sr)}mVs" for sr in scan_rates]
    rows = [
        [float(sr)] + [float(q["kernel"][i, j]) for j in range(len(scan_rates))]
        for i, sr in enumerate(scan_rates)
    ]
    path = data_dir / "08_quantum_kernel_matrix.csv"
    write_csv(path, header, rows)
    paths.append(path)

    scores = q["scores_rate"]
    header = ["scan_rate_mV_s", "qkpca_1", "qkpca_2"]
    rows = [
        [float(sr), float(scores[i, 0]), float(scores[i, 1])]
        for i, sr in enumerate(scan_rates)
    ]
    path = data_dir / "09_quantum_kpca_scores.csv"
    write_csv(path, header, rows)
    paths.append(path)

    header = ["eigen_index", "eigenvalue", "explained_variance"]
    ev = q["explained_variance"]
    rows = [
        [i + 1, float(q["eigenvalues"][i]), float(ev[i]) if i < len(ev) else ""]
        for i in range(len(q["eigenvalues"]))
    ]
    path = data_dir / "10_quantum_kpca_eigenvalues.csv"
    write_csv(path, header, rows)
    paths.append(path)

    header = ["scan_rate_mV_s", "cap_fraction", "diffusion_fraction", "anodic_peak_A", "abs_cathodic_peak_A"]
    rows = [
        [
            float(sr),
            float(dunn["cap_frac"][i]),
            float(dunn["dif_frac"][i]),
            float(scaling["anodic_peaks"][i]),
            float(abs(scaling["cathodic_peaks"][i])),
        ]
        for i, sr in enumerate(scan_rates)
    ]
    path = data_dir / "11_summary_table_data.csv"
    write_csv(path, header, rows)
    paths.append(path)

    return paths


if __name__ == "__main__":
    for item in export():
        print(item)
