"""
Training Pipeline
===================
End-to-end pipeline for generating synthetic data, training surrogate
models, evaluating them, and persisting to disk.

Usage:
    python -m vanl.backend.ml.training
"""

import logging
import os
import sys
import json
import time
from typing import Dict

import numpy as np
from sklearn.model_selection import train_test_split

# Add parent to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from vanl.backend.core.dataset_gen import (
    generate_synthesis_dataset,
    generate_eis_dataset,
)
from vanl.backend.ml.models import (
    SynthesisSurrogate,
    EISSurrogate,
    save_model,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def train_synthesis_model(
    n_samples: int = 5000,
    model_type: str = "gbr",
    test_size: float = 0.2,
    output_dir: str = None,
) -> Dict:
    """
    Train synthesis surrogate: (composition, synthesis) → structural descriptors.

    Returns:
        Dictionary with train/test metrics and model path
    """
    logger.info("=" * 60)
    logger.info("TRAINING SYNTHESIS SURROGATE MODEL")
    logger.info("=" * 60)

    # Generate data
    t0 = time.time()
    X, Y, records = generate_synthesis_dataset(n_samples=n_samples)
    logger.info("Generated %d synthesis samples in %.1fs", n_samples, time.time() - t0)
    logger.info("  X shape: %s, Y shape: %s", X.shape, Y.shape)

    # Train/test split
    X_train, X_test, Y_train, Y_test = train_test_split(
        X, Y, test_size=test_size, random_state=42
    )

    # Train
    model = SynthesisSurrogate(model_type=model_type)
    t0 = time.time()
    train_metrics = model.fit(X_train, Y_train)
    train_time = time.time() - t0
    logger.info("  Training time: %.1fs", train_time)

    # Evaluate on test set
    Y_pred = model.predict(X_test)
    from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
    test_mse = float(mean_squared_error(Y_test, Y_pred))
    test_r2 = float(r2_score(Y_test, Y_pred))
    test_mae = float(mean_absolute_error(Y_test, Y_pred))

    # Per-output R² scores
    descriptor_names = [
        "porosity", "surface_area", "conductivity",
        "defect_density", "layer_thickness", "crystallinity", "particle_size"
    ]
    per_output_r2 = {}
    for i, name in enumerate(descriptor_names):
        r2_i = float(r2_score(Y_test[:, i], Y_pred[:, i]))
        per_output_r2[name] = r2_i
        logger.info("    %s R² = %.4f", name, r2_i)

    logger.info("  Test MSE=%.6f, R²=%.4f, MAE=%.6f", test_mse, test_r2, test_mae)

    # Save model
    d = output_dir or os.path.join(os.path.dirname(__file__), "saved_models")
    model_path = save_model(model, "synthesis_surrogate", d)

    results = {
        "model_type": model_type,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "train_time_s": train_time,
        "train_metrics": train_metrics,
        "test_mse": test_mse,
        "test_r2": test_r2,
        "test_mae": test_mae,
        "per_output_r2": per_output_r2,
        "model_path": model_path,
    }
    return results


def train_eis_model(
    n_samples: int = 5000,
    model_type: str = "gbr",
    test_size: float = 0.2,
    output_dir: str = None,
) -> Dict:
    """
    Train EIS surrogate: structural_descriptors → EIS parameters.

    Returns:
        Dictionary with train/test metrics and model path
    """
    logger.info("=" * 60)
    logger.info("TRAINING EIS SURROGATE MODEL")
    logger.info("=" * 60)

    # Generate data
    t0 = time.time()
    X, Y, records = generate_eis_dataset(n_samples=n_samples)
    logger.info("Generated %d EIS samples in %.1fs", n_samples, time.time() - t0)
    logger.info("  X shape: %s, Y shape: %s", X.shape, Y.shape)

    # Train/test split
    X_train, X_test, Y_train, Y_test = train_test_split(
        X, Y, test_size=test_size, random_state=42
    )

    # Train
    model = EISSurrogate(model_type=model_type)
    t0 = time.time()
    train_metrics = model.fit(X_train, Y_train)
    train_time = time.time() - t0
    logger.info("  Training time: %.1fs", train_time)

    # Evaluate
    Y_pred = model.predict(X_test)
    from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
    test_mse = float(mean_squared_error(Y_test, Y_pred))
    test_r2 = float(r2_score(Y_test, Y_pred))
    test_mae = float(mean_absolute_error(Y_test, Y_pred))

    # Per-output R²
    eis_names = ["Rs", "Rct", "Cdl", "sigma_warburg", "n_cpe"]
    per_output_r2 = {}
    for i, name in enumerate(eis_names):
        r2_i = float(r2_score(Y_test[:, i], Y_pred[:, i]))
        per_output_r2[name] = r2_i
        logger.info("    %s R² = %.4f", name, r2_i)

    logger.info("  Test MSE=%.6f, R²=%.4f, MAE=%.6f", test_mse, test_r2, test_mae)

    # Save model
    d = output_dir or os.path.join(os.path.dirname(__file__), "saved_models")
    model_path = save_model(model, "eis_surrogate", d)

    results = {
        "model_type": model_type,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "train_time_s": train_time,
        "train_metrics": train_metrics,
        "test_mse": test_mse,
        "test_r2": test_r2,
        "test_mae": test_mae,
        "per_output_r2": per_output_r2,
        "model_path": model_path,
    }
    return results


def train_all(
    n_samples: int = 5000,
    model_type: str = "gbr",
    output_dir: str = None,
) -> Dict:
    """Train both surrogate models and save report."""
    d = output_dir or os.path.join(os.path.dirname(__file__), "saved_models")

    synthesis_results = train_synthesis_model(n_samples, model_type, output_dir=d)
    eis_results = train_eis_model(n_samples, model_type, output_dir=d)

    report = {
        "synthesis_model": synthesis_results,
        "eis_model": eis_results,
    }

    # Save training report
    report_path = os.path.join(d, "training_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Training report saved: %s", report_path)

    return report


if __name__ == "__main__":
    report = train_all(n_samples=5000, model_type="gbr")

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"  Synthesis R² = {report['synthesis_model']['test_r2']:.4f}")
    print(f"  EIS R²       = {report['eis_model']['test_r2']:.4f}")
    print(f"  Models saved to: {report['synthesis_model']['model_path']}")
