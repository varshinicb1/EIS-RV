"""
ML Prediction Routes
====================
API endpoints for machine learning model predictions.

Endpoints:
- POST /api/v1/ml/predict/cv          - Predict CV (single model)
- POST /api/v1/ml/predict/cv/ensemble - Predict CV with uncertainty (ensemble)
- GET  /api/v1/ml/models/status       - Model status
- GET  /api/v1/ml/models/info         - Detailed model info

Author: VidyuthLabs
Date: May 6, 2026
"""

import logging
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np
import torch
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["Machine Learning"])

# ── Global model state ────────────────────────────────────────────────────
_cv_model = None
_cv_model_device = None
_cv_ensemble = None
_cv_ensemble_device = None
_anomaly_detector = None
_anomaly_detector_device = None

# Normalization stats (from training)
CV_VOLTAGE_MEAN = 0.0
CV_VOLTAGE_STD  = 1.0
CV_CURRENT_MEAN = 0.0
CV_CURRENT_STD  = 1.0

_MECHANISM_NAMES = [
    "Reversible (Nernstian)",
    "Quasi-reversible",
    "Irreversible",
    "Catalytic",
    "Adsorption-controlled",
]

_MODEL_DIR = Path(__file__).parent.parent.parent.parent.parent / "models"


# ── Pydantic models ───────────────────────────────────────────────────────

class CVPredictionRequest(BaseModel):
    voltage: List[float] = Field(..., min_items=10)
    current: List[float] = Field(..., min_items=10)

    class Config:
        json_schema_extra = {
            "example": {
                "voltage": list(np.linspace(-0.5, 0.5, 20).tolist()),
                "current": list(np.sin(np.linspace(0, 2 * 3.14, 20)).tolist()),
            }
        }


class CVPredictionResponse(BaseModel):
    mechanism: List[float]
    mechanism_class: int
    mechanism_name: str
    reversibility: float
    reversibility_category: str
    peaks: List[float]
    parameters: List[float]
    species: List[float]
    inference_time_ms: float


class CVEnsemblePredictionResponse(BaseModel):
    # Mean predictions
    mechanism: List[float]
    mechanism_class: int
    mechanism_name: str
    reversibility: float
    reversibility_category: str
    peaks: List[float]
    parameters: List[float]
    # Uncertainty (std across ensemble)
    reversibility_uncertainty: float
    mechanism_uncertainty: List[float]
    peaks_uncertainty: List[float]
    parameters_uncertainty: List[float]
    # Confidence
    mechanism_confidence: float
    # Metadata
    n_models: int
    inference_time_ms: float
    uncertainty_level: str   # "low" / "medium" / "high"


class AnomalyRequest(BaseModel):
    current: List[float] = Field(..., min_items=10,
        description="CV current array (A)")


class AnomalyResponse(BaseModel):
    is_anomaly: bool
    anomaly_score: float          # 0-1 normalised (higher = more anomalous)
    reconstruction_error: float   # raw MSE
    threshold: float              # threshold used
    quality: str                  # "normal" | "suspicious" | "anomaly"
    inference_time_ms: float


# ── Helpers ───────────────────────────────────────────────────────────────

def _preprocess(voltage: List[float], current: List[float]) -> torch.Tensor:
    v = np.array(voltage, dtype=np.float32)
    c = np.array(current, dtype=np.float32)
    if len(v) != 2000:
        x_old = np.linspace(0, 1, len(v))
        x_new = np.linspace(0, 1, 2000)
        v = np.interp(x_new, x_old, v).astype(np.float32)
        c = np.interp(x_new, x_old, c).astype(np.float32)
    v = (v - CV_VOLTAGE_MEAN) / CV_VOLTAGE_STD
    c = (c - CV_CURRENT_MEAN) / CV_CURRENT_STD
    data = np.stack([v, c], axis=-1)
    return torch.tensor(data, dtype=torch.float32).unsqueeze(0)


def _mechanism_name(cls: int) -> str:
    return _MECHANISM_NAMES[cls] if 0 <= cls < len(_MECHANISM_NAMES) else "Unknown"


def _reversibility_category(score: float) -> str:
    if score < 0.3:
        return "Irreversible"
    elif score < 0.7:
        return "Quasi-reversible"
    return "Reversible"


def _uncertainty_level(std: float) -> str:
    if std < 0.05:
        return "low"
    elif std < 0.15:
        return "medium"
    return "high"


# ── Model loading ─────────────────────────────────────────────────────────

def load_cv_model() -> bool:
    """Load single CV Transformer model."""
    global _cv_model, _cv_model_device
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from ml.models.cv_transformer import create_cv_transformer

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model_path = _MODEL_DIR / "cv_transformer" / "cv_transformer_best.pt"

        if not model_path.exists():
            logger.warning("Single CV model not found at %s", model_path)
            return False

        model = create_cv_transformer("base")
        ckpt = torch.load(model_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        model.to(device).eval()

        _cv_model = model
        _cv_model_device = device
        logger.info("Single CV model loaded on %s", device)
        return True
    except Exception as e:
        logger.error("Failed to load single CV model: %s", e)
        return False


def load_cv_ensemble() -> bool:
    """Load CV Transformer ensemble (5 models) for uncertainty quantification."""
    global _cv_ensemble, _cv_ensemble_device
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from ml.models.cv_transformer_ensemble import create_cv_transformer_ensemble

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        ensemble_dir = _MODEL_DIR / "cv_transformer_ensemble"

        if not ensemble_dir.exists():
            logger.warning("Ensemble directory not found: %s", ensemble_dir)
            return False

        # Check all 5 model files exist
        missing = [f for i in range(5) if not (ensemble_dir / f"model_{i}.pt").exists()
                   for f in [f"model_{i}.pt"]]
        if missing:
            logger.warning("Missing ensemble model files: %s", missing)
            return False

        ensemble = create_cv_transformer_ensemble(num_models=5, model_size="base")
        ensemble.load_ensemble(str(ensemble_dir))
        ensemble.to(device).eval()

        _cv_ensemble = ensemble
        _cv_ensemble_device = device
        logger.info("CV ensemble (5 models) loaded on %s", device)
        return True
    except Exception as e:
        logger.error("Failed to load CV ensemble: %s", e)
        return False


def load_anomaly_detector() -> bool:
    """Load trained CVAnomalyDetector."""
    global _anomaly_detector, _anomaly_detector_device
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from ml.models.anomaly_detector import CVAnomalyDetector

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        ckpt_path = _MODEL_DIR / "anomaly_detector" / "anomaly_detector.pt"

        if not ckpt_path.exists():
            logger.warning("Anomaly detector not found at %s", ckpt_path)
            return False

        model = CVAnomalyDetector(data_points=2000, latent_dim=64)
        ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        # Restore threshold from checkpoint
        if "threshold" in ckpt:
            model.threshold.fill_(ckpt["threshold"])
        model.to(device).eval()

        _anomaly_detector = model
        _anomaly_detector_device = device
        logger.info("Anomaly detector loaded on %s (threshold=%.4f)",
                    device, float(model.threshold))
        return True
    except Exception as e:
        logger.error("Failed to load anomaly detector: %s", e)
        return False


# ── Prediction endpoints ──────────────────────────────────────────────────

@router.post("/predict/cv", response_model=CVPredictionResponse)
async def predict_cv(request: CVPredictionRequest):
    """Predict CV characteristics using single trained transformer model."""
    if _cv_model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CV model not loaded.",
        )
    if len(request.voltage) != len(request.current):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="voltage and current must have the same length.",
        )
    try:
        data = _preprocess(request.voltage, request.current).to(_cv_model_device)
        t0 = time.perf_counter()
        with torch.no_grad():
            out = _cv_model(data, task="all")
            if _cv_model_device.type == "cuda":
                torch.cuda.synchronize()
        elapsed_ms = (time.perf_counter() - t0) * 1000

        mechanism = out["mechanism"].cpu().numpy()[0].tolist()
        mech_cls  = int(np.argmax(mechanism))
        rev       = float(out["reversibility"].cpu().item())

        return CVPredictionResponse(
            mechanism=mechanism,
            mechanism_class=mech_cls,
            mechanism_name=_mechanism_name(mech_cls),
            reversibility=rev,
            reversibility_category=_reversibility_category(rev),
            peaks=out["peaks"].cpu().numpy()[0].tolist(),
            parameters=out["parameters"].cpu().numpy()[0].tolist(),
            species=out["species"].cpu().numpy()[0].tolist(),
            inference_time_ms=round(elapsed_ms, 2),
        )
    except Exception as e:
        logger.error("CV prediction failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")


@router.post("/predict/cv/ensemble", response_model=CVEnsemblePredictionResponse)
async def predict_cv_ensemble(request: CVPredictionRequest):
    """
    Predict CV characteristics with uncertainty quantification.

    Uses an ensemble of 5 independently trained models. Returns mean
    predictions plus standard deviation (uncertainty) for each output.
    """
    if _cv_ensemble is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CV ensemble not loaded. Run train_ensemble.py first.",
        )
    if len(request.voltage) != len(request.current):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="voltage and current must have the same length.",
        )
    try:
        data = _preprocess(request.voltage, request.current).to(_cv_ensemble_device)
        t0 = time.perf_counter()
        with torch.no_grad():
            out = _cv_ensemble(data)
            if _cv_ensemble_device.type == "cuda":
                torch.cuda.synchronize()
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Mean predictions
        rev_mean  = float(out["reversibility"].cpu().item())
        mech_mean = out["mechanism"].cpu().numpy()[0].tolist()
        mech_cls  = int(np.argmax(mech_mean))

        # Uncertainty (std)
        rev_std   = float(out.get("reversibility_uncertainty", torch.tensor(0.0)).cpu().item())
        mech_std  = out.get("mechanism_uncertainty", torch.zeros(5)).cpu().numpy()[0].tolist() \
                    if "mechanism_uncertainty" in out else [0.0] * 5
        peaks_mean = out["peaks"].cpu().numpy()[0].tolist()
        peaks_std  = out.get("peaks_uncertainty", torch.zeros_like(out["peaks"])).cpu().numpy()[0].tolist() \
                     if "peaks_uncertainty" in out else [0.0] * len(peaks_mean)
        params_mean = out["parameters"].cpu().numpy()[0].tolist()
        params_std  = out.get("parameters_uncertainty", torch.zeros_like(out["parameters"])).cpu().numpy()[0].tolist() \
                      if "parameters_uncertainty" in out else [0.0] * len(params_mean)

        mech_conf = float(np.max(np.exp(mech_mean) / np.sum(np.exp(mech_mean))))

        return CVEnsemblePredictionResponse(
            mechanism=mech_mean,
            mechanism_class=mech_cls,
            mechanism_name=_mechanism_name(mech_cls),
            reversibility=rev_mean,
            reversibility_category=_reversibility_category(rev_mean),
            peaks=peaks_mean,
            parameters=params_mean,
            reversibility_uncertainty=rev_std,
            mechanism_uncertainty=mech_std,
            peaks_uncertainty=peaks_std,
            parameters_uncertainty=params_std,
            mechanism_confidence=mech_conf,
            n_models=5,
            inference_time_ms=round(elapsed_ms, 2),
            uncertainty_level=_uncertainty_level(rev_std),
        )
    except Exception as e:
        logger.error("Ensemble prediction failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Ensemble prediction failed: {e}")


@router.post("/detect/anomaly", response_model=AnomalyResponse)
async def detect_anomaly(request: AnomalyRequest):
    """
    Detect anomalies in a CV measurement using the trained autoencoder.

    Returns an anomaly score (0-1), reconstruction error, and quality label.
    Use this for real-time quality control before running ML predictions.
    """
    if _anomaly_detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anomaly detector not loaded.",
        )
    try:
        # Preprocess: resample to 2000 pts, shape (1, 1, 2000)
        c = np.array(request.current, dtype=np.float32)
        if len(c) != 2000:
            x_old = np.linspace(0, 1, len(c))
            x_new = np.linspace(0, 1, 2000)
            c = np.interp(x_new, x_old, c).astype(np.float32)
        tensor = torch.tensor(c, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
        tensor = tensor.to(_anomaly_detector_device)

        t0 = time.perf_counter()
        with torch.no_grad():
            out = _anomaly_detector(tensor)
            if _anomaly_detector_device.type == "cuda":
                torch.cuda.synchronize()
        elapsed_ms = (time.perf_counter() - t0) * 1000

        recon_error = float(out["reconstruction_error"][0].cpu())
        threshold   = float(_anomaly_detector.threshold)
        is_anomaly  = bool(out["is_anomaly"][0].cpu())

        # Normalised score 0-1 (sigmoid-like)
        score = float(out["anomaly_score"][0].cpu())
        score_norm = float(1 / (1 + np.exp(-score)))  # sigmoid

        if not is_anomaly and score_norm < 0.4:
            quality = "normal"
        elif not is_anomaly:
            quality = "suspicious"
        else:
            quality = "anomaly"

        return AnomalyResponse(
            is_anomaly=is_anomaly,
            anomaly_score=round(score_norm, 4),
            reconstruction_error=round(recon_error, 6),
            threshold=round(threshold, 6),
            quality=quality,
            inference_time_ms=round(elapsed_ms, 2),
        )
    except Exception as e:
        logger.error("Anomaly detection failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {e}")


# ── Status / info endpoints ───────────────────────────────────────────────

@router.get("/models/status")
async def get_models_status():
    """Get status of all loaded ML models."""
    return {
        "cv_transformer": {
            "loaded": _cv_model is not None,
            "device": str(_cv_model_device) if _cv_model_device else None,
        },
        "cv_ensemble": {
            "loaded": _cv_ensemble is not None,
            "device": str(_cv_ensemble_device) if _cv_ensemble_device else None,
            "n_models": 5,
            "uncertainty_quantification": _cv_ensemble is not None,
        },
        "anomaly_detector": {
            "loaded": _anomaly_detector is not None,
            "device": str(_anomaly_detector_device) if _anomaly_detector_device else None,
            "threshold": round(float(_anomaly_detector.threshold), 4) if _anomaly_detector else None,
        },
    }


@router.get("/models/info")
async def get_models_info():
    """Detailed information about loaded ML models."""
    info: Dict[str, Any] = {}

    if _cv_model is not None:
        info["cv_transformer"] = {
            "name": "CV Transformer (single)",
            "version": "1.0.0",
            "architecture": "Transformer (Base)",
            "parameters": 5_838_841,
            "model_size_mb": 61.99,
            "device": str(_cv_model_device),
            "input_shape": "(batch, 2000, 2)",
            "output_tasks": ["mechanism (5)", "reversibility", "peaks (10)", "parameters (5)", "species (100)"],
        }

    if _cv_ensemble is not None:
        info["cv_ensemble"] = {
            "name": "CV Transformer Ensemble",
            "version": "1.0.0",
            "n_models": 5,
            "parameters_per_model": 5_838_841,
            "total_parameters": 5 * 5_838_841,
            "model_size_mb": 5 * 61.99,
            "device": str(_cv_ensemble_device),
            "uncertainty_quantification": True,
            "outputs": [
                "reversibility (mean ± std)",
                "mechanism (mean ± std)",
                "peaks (mean ± std)",
                "parameters (mean ± std)",
            ],
            "training": {
                "dataset": "EBIO",
                "samples": 694,
                "seeds": [42, 43, 44, 45, 46],
                "early_stopping_epoch": 16,
            },
        }

    if not info:
        raise HTTPException(status_code=503, detail="No models loaded")

    return info


# ── Startup ───────────────────────────────────────────────────────────────

@router.on_event("startup")
async def startup_event():
    """Load all ML models on startup."""
    logger.info("Loading ML models...")
    single_ok   = load_cv_model()
    ensemble_ok = load_cv_ensemble()
    anomaly_ok  = load_anomaly_detector()
    logger.info(
        "ML models: single=%s  ensemble=%s  anomaly=%s",
        "OK" if single_ok else "FAIL",
        "OK" if ensemble_ok else "FAIL",
        "OK" if anomaly_ok else "FAIL",
    )
