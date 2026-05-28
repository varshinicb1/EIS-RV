from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.ensemble import IsolationForest
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from export_plot_data_csvs import export as export_plot_data
from electrochem_suite import analyze_file as analyze_generic_file, detect_technique
from make_formulas_pdf import build as build_formulas_pdf
from make_plots_workbook import build as build_workbook, verify as verify_workbook
from reference_plots import (
    analyze_cv,
    export_all,
    export_pdf_layout_figures,
)
from verify_calculations import audit


APP_OUTPUT = Path("output/rvce_app")


@dataclass
class SampleRun:
    sample_id: str
    source_name: str
    csv_path: Path
    output_dir: Path
    metrics: dict
    technique: str = "CV"
    plots: list[str] | None = None
    workbook: str = "AV_CV_Analysis_Plots_With_Data.xlsx"


def safe_stem(name: str) -> str:
    chars = []
    for ch in Path(name).stem:
        chars.append(ch if ch.isalnum() or ch in ("-", "_") else "_")
    stem = "".join(chars).strip("_")
    return stem or "sample"


def write_uploaded_file(file_storage, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(file_storage.filename or f"sample_{uuid.uuid4().hex}.csv").name
    path = target_dir / filename
    file_storage.save(path)
    return path


def _artifact_manifest(output_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            rows.append(
                {
                    "name": path.name,
                    "relative_path": str(path.relative_to(output_dir)).replace("\\", "/"),
                    "size_bytes": path.stat().st_size,
                    "kind": path.suffix.lower().lstrip(".") or "file",
                }
            )
    return rows


def _zip_dir(source_dir: Path, zip_path: Path) -> Path:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file() and path != zip_path:
                zf.write(path, path.relative_to(source_dir))
    return zip_path


def _extract_ml_feature_rows(sample: SampleRun) -> tuple[list[dict], np.ndarray]:
    result = analyze_cv(sample.csv_path)
    scan_rates = result["scan_rates"]
    q = result["qkpca"]
    features = q["features"]
    rows = []
    for i, sr in enumerate(scan_rates):
        rows.append(
            {
                "sample_id": sample.sample_id,
                "source_file": sample.source_name,
                "scan_rate_mV_s": float(sr),
                "qkpca_1": float(q["scores_rate"][i, 0]),
                "qkpca_2": float(q["scores_rate"][i, 1]),
            }
        )
    return rows, features


def train_ml_diagnostics(samples: list[SampleRun], output_dir: Path) -> dict:
    ml_dir = output_dir / "ml"
    ml_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    feature_blocks = []
    for sample in samples:
        sample_rows, features = _extract_ml_feature_rows(sample)
        rows.extend(sample_rows)
        feature_blocks.append(features)

    X = np.vstack(feature_blocks)
    X_scaled = StandardScaler().fit_transform(X)
    n = len(rows)
    k2 = min(2, n)
    k3 = min(3, n)

    if k2 >= 2:
        rows_k2 = KMeans(n_clusters=k2, random_state=42, n_init=20).fit_predict(X_scaled)
        gmm = GaussianMixture(n_components=k2, random_state=42).fit(X_scaled).predict(X_scaled)
        agg = AgglomerativeClustering(n_clusters=k2).fit_predict(X_scaled)
    else:
        rows_k2 = gmm = agg = np.zeros(n, dtype=int)
    if k3 >= 2:
        rows_k3 = KMeans(n_clusters=k3, random_state=42, n_init=20).fit_predict(X_scaled)
    else:
        rows_k3 = np.zeros(n, dtype=int)
    db = DBSCAN(eps=1.25, min_samples=2).fit_predict(X_scaled)
    iso = IsolationForest(random_state=42, contamination="auto").fit(X_scaled)
    anomaly_score = iso.decision_function(X_scaled)
    anomaly_label = iso.predict(X_scaled)

    for i, row in enumerate(rows):
        row.update(
            {
                "kmeans_2": int(rows_k2[i]),
                "kmeans_3": int(rows_k3[i]),
                "gmm_2": int(gmm[i]),
                "agglomerative_2": int(agg[i]),
                "dbscan": int(db[i]),
                "isolation_forest_score": float(anomaly_score[i]),
                "isolation_forest_label": int(anomaly_label[i]),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(ml_dir / "ml_model_assignments.csv", index=False)

    fig, ax = plt.subplots(figsize=(6.5, 4.5), constrained_layout=True)
    for sample_id, group in df.groupby("sample_id"):
        ax.scatter(group["qkpca_1"], group["qkpca_2"], s=45, label=sample_id)
        for _, item in group.iterrows():
            ax.text(item["qkpca_1"], item["qkpca_2"], f" {int(item['scan_rate_mV_s'])}", fontsize=7)
    ax.set_xlabel("Quantum KPCA 1")
    ax.set_ylabel("Quantum KPCA 2")
    ax.set_title("ML diagnostic embedding")
    ax.grid(True, alpha=0.25, lw=0.4)
    ax.legend(frameon=True, fontsize=7)
    fig.savefig(ml_dir / "ml_embedding.png", dpi=900, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    summary = {
        "models": [
            "Quantum-kernel PCA embedding",
            "KMeans k=2",
            "KMeans k=3 when enough rows exist",
            "GaussianMixture k=2",
            "Agglomerative clustering k=2",
            "DBSCAN",
            "IsolationForest anomaly scoring",
        ],
        "n_feature_rows": int(n),
        "n_features_per_curve": int(X.shape[1]),
        "note": "Unsupervised diagnostics only; supervised trainers require labels.",
    }
    (ml_dir / "ml_model_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run_single_sample(
    csv_path: Path,
    output_dir: Path,
    sample_id: str | None = None,
    dpi: int = 900,
    style: str = "reference",
    technique: str = "auto",
    material_query: str | None = None,
    mp_api_key: str | None = None,
    nvidia_api_key: str | None = None,
    enable_ai: bool = False,
    palette: str = "turbo",
    plot_titles: dict | None = None,
) -> SampleRun:
    sample_id = sample_id or safe_stem(csv_path.name)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_copy = output_dir / csv_path.name
    if csv_path.resolve() != source_copy.resolve():
        shutil.copy2(csv_path, source_copy)

    detected = detect_technique(source_copy, technique)
    if detected != "cv":
        result = analyze_generic_file(
            source_copy,
            output_dir,
            sample_id=sample_id,
            technique=detected,
            dpi=dpi,
            style=style,
            material_query=material_query,
            mp_api_key=mp_api_key,
            nvidia_api_key=nvidia_api_key,
            enable_ai=enable_ai,
        )
        manifest = _artifact_manifest(output_dir)
        (output_dir / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        _zip_dir(output_dir, output_dir / f"{sample_id}_all_outputs.zip")
        return SampleRun(
            sample_id,
            csv_path.name,
            source_copy,
            output_dir,
            result.metrics,
            technique=result.technique,
            plots=result.plots,
            workbook=result.workbook,
        )

    metrics = export_all(source_copy, output_dir, dpi=dpi, palette=palette, plot_titles=plot_titles)
    metrics["technique"] = "CV"
    metrics["dpi"] = dpi
    metrics["style"] = style
    audit(source_copy, output_dir / "audit")
    export_plot_data(source_copy, output_dir)
    build_formulas_pdf(output_dir / "CV_Analysis_Formulas_and_References.pdf")
    workbook = build_workbook(output_dir, csv_path=source_copy)
    verify_workbook(workbook)

    manifest = _artifact_manifest(output_dir)
    (output_dir / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _zip_dir(output_dir, output_dir / f"{sample_id}_all_outputs.zip")

    return SampleRun(
        sample_id,
        csv_path.name,
        source_copy,
        output_dir,
        metrics,
        technique="CV",
        plots=[Path(item["file"]).name for item in metrics.get("exports", [])],
        workbook=workbook.name,
    )


def run_job(
    upload_paths: list[Path],
    job_id: str | None = None,
    dpi: int = 900,
    style: str = "reference",
    technique: str = "auto",
    material_query: str | None = None,
    mp_api_key: str | None = None,
    nvidia_api_key: str | None = None,
    enable_ai: bool = False,
    palette: str = "turbo",
    plot_titles: dict | None = None,
) -> dict:
    job_id = job_id or uuid.uuid4().hex[:12]
    job_dir = APP_OUTPUT / job_id
    samples_dir = job_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    runs: list[SampleRun] = []
    for idx, path in enumerate(upload_paths, start=1):
        sample_id = f"{idx:02d}_{safe_stem(path.name)}"
        runs.append(
            run_single_sample(
                path,
                samples_dir / sample_id,
                sample_id=sample_id,
                dpi=dpi,
                style=style,
                technique=technique,
                material_query=material_query,
                mp_api_key=mp_api_key,
                nvidia_api_key=nvidia_api_key,
                enable_ai=enable_ai,
                palette=palette,
                plot_titles=plot_titles,
            )
        )

    comparison = {}
    cv_runs = [r for r in runs if r.technique == "CV"]
    if len(cv_runs) >= 2:
        train_ml_diagnostics(cv_runs, job_dir)
        comparison["ml_summary"] = "ml/ml_model_summary.json"
    if len(cv_runs) >= 3:
        comparison_dir = job_dir / "comparison"
        export_pdf_layout_figures([r.csv_path for r in cv_runs[:3]], comparison_dir, dpi=dpi, reuse_single=False)
        comparison["fig4_comparison"] = "comparison/fig4_pdf_layout_example.png"
        comparison["fig5_comparison"] = "comparison/fig5_pdf_layout_example.png"

    summary = {
        "job_id": job_id,
        "settings": {"dpi": dpi, "style": style, "technique": technique, "ai_enabled": enable_ai},
        "samples": [
            {
                "sample_id": r.sample_id,
                "source_name": r.source_name,
                "technique": r.technique,
                "output_dir": str(r.output_dir.relative_to(job_dir)).replace("\\", "/"),
                "workbook": r.workbook,
                "plots": r.plots or [],
                "download_zip": f"{r.sample_id}_all_outputs.zip",
                "metrics": r.metrics,
                "mean_b": r.metrics.get("mean_b"),
                "mean_cap_fraction": r.metrics.get("mean_cap_fraction"),
                "scan_rates": r.metrics.get("scan_rates", []),
            }
            for r in runs
        ],
        "comparison": comparison,
    }
    (job_dir / "job_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (job_dir / "artifact_manifest.json").write_text(json.dumps(_artifact_manifest(job_dir), indent=2), encoding="utf-8")
    _zip_dir(job_dir, job_dir / f"rvce_cnd_lab_cv_analysis_{job_id}.zip")
    return summary
