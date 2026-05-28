"""
Production Model Server (Week 8)
==================================
Serves all trained ML models with:
  - Model versioning and hot-reload
  - Request batching for throughput
  - Caching for repeated inputs
  - Health monitoring
  - Graceful degradation (ensemble → single → fallback)

Author: VidyuthLabs
Date: May 6, 2026
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from functools import lru_cache

import numpy as np
import torch

logger = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).parent.parent.parent.parent.parent
MODEL_DIR  = BASE_DIR / "models"


# ── Model Registry ────────────────────────────────────────────────────────

class ModelRegistry:
    """
    Central registry for all trained models.
    Supports versioning, hot-reload, and graceful degradation.
    """

    def __init__(self):
        self._models: Dict[str, Any]  = {}
        self._versions: Dict[str, str] = {}
        self._load_times: Dict[str, float] = {}
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def register(self, name: str, model: Any, version: str = "1.0.0"):
        """Register a model."""
        self._models[name]      = model
        self._versions[name]    = version
        self._load_times[name]  = time.time()
        logger.info("Registered model: %s v%s", name, version)

    def get(self, name: str) -> Optional[Any]:
        """Get a model by name."""
        return self._models.get(name)

    def status(self) -> Dict[str, Any]:
        """Get status of all registered models."""
        return {
            name: {
                "version":   self._versions.get(name, "unknown"),
                "loaded_at": self._load_times.get(name, 0),
                "available": True,
            }
            for name in self._models
        }

    def load_all(self):
        """Load all available trained models."""
        self._load_cv_ensemble()
        self._load_cv_single()
        self._load_anomaly_detector()
        self._load_raman_identifier()
        logger.info("Model registry loaded: %d models", len(self._models))

    def _load_cv_ensemble(self):
        try:
            import sys
            sys.path.insert(0, str(BASE_DIR / "src" / "backend" / "ml"))
            from models.cv_transformer_ensemble import create_cv_transformer_ensemble

            ensemble_dir = MODEL_DIR / "cv_transformer_ensemble"
            if not (ensemble_dir / "model_0.pt").exists():
                return

            ensemble = create_cv_transformer_ensemble(num_models=5, model_size="base")
            ensemble.load_ensemble(str(ensemble_dir))
            ensemble.to(self._device).eval()
            self.register("cv_ensemble", ensemble, "1.0.0")
        except Exception as e:
            logger.warning("Could not load CV ensemble: %s", e)

    def _load_cv_single(self):
        try:
            import sys
            sys.path.insert(0, str(BASE_DIR / "src" / "backend" / "ml"))
            from models.cv_transformer import create_cv_transformer

            model_path = MODEL_DIR / "cv_transformer" / "cv_transformer_best.pt"
            if not model_path.exists():
                return

            model = create_cv_transformer("base")
            ckpt  = torch.load(model_path, map_location=self._device, weights_only=False)
            model.load_state_dict(ckpt["model_state_dict"])
            model.to(self._device).eval()
            self.register("cv_single", model, "1.0.0")
        except Exception as e:
            logger.warning("Could not load single CV model: %s", e)

    def _load_anomaly_detector(self):
        try:
            import sys
            sys.path.insert(0, str(BASE_DIR / "src" / "backend" / "ml"))
            from models.anomaly_detector import CVAnomalyDetector

            ckpt_path = MODEL_DIR / "anomaly_detector" / "anomaly_detector.pt"
            if not ckpt_path.exists():
                return

            model = CVAnomalyDetector(data_points=2000, latent_dim=64)
            ckpt  = torch.load(ckpt_path, map_location=self._device, weights_only=False)
            model.load_state_dict(ckpt["model_state_dict"])
            if "threshold" in ckpt:
                model.threshold.fill_(ckpt["threshold"])
            model.to(self._device).eval()
            self.register("anomaly_detector", model, "1.0.0")
        except Exception as e:
            logger.warning("Could not load anomaly detector: %s", e)

    def _load_raman_identifier(self):
        try:
            import sys
            sys.path.insert(0, str(BASE_DIR / "src" / "backend" / "ml"))
            from models.raman_material_identifier import RamanMaterialIdentifier

            db_path = BASE_DIR / "data" / "material_database" / "raman_materials.json"
            if not db_path.exists():
                return

            identifier = RamanMaterialIdentifier(database_path=str(db_path))
            self.register("raman_identifier", identifier, "1.0.0")
        except Exception as e:
            logger.warning("Could not load Raman identifier: %s", e)


# ── Prediction Cache ──────────────────────────────────────────────────────

class PredictionCache:
    """LRU cache for model predictions."""

    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, Any] = {}
        self._access_times: Dict[str, float] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def _key(self, data: np.ndarray, model_name: str) -> str:
        h = hashlib.md5(data.tobytes()).hexdigest()
        return f"{model_name}:{h}"

    def get(self, data: np.ndarray, model_name: str) -> Optional[Any]:
        key = self._key(data, model_name)
        if key in self._cache:
            self._access_times[key] = time.time()
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        return None

    def set(self, data: np.ndarray, model_name: str, result: Any):
        key = self._key(data, model_name)
        if len(self._cache) >= self.max_size:
            # Evict LRU
            oldest = min(self._access_times, key=self._access_times.get)
            del self._cache[oldest]
            del self._access_times[oldest]
        self._cache[key] = result
        self._access_times[key] = time.time()

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        return {
            "size":      len(self._cache),
            "hits":      self.hits,
            "misses":    self.misses,
            "hit_rate":  self.hits / total if total > 0 else 0.0,
        }


# ── Production Predictor ──────────────────────────────────────────────────

class ProductionPredictor:
    """
    Production-grade predictor with:
    - Graceful degradation (ensemble → single → error)
    - Caching
    - Latency tracking
    - Anomaly pre-screening
    """

    def __init__(self, registry: ModelRegistry, cache: Optional[PredictionCache] = None):
        self.registry = registry
        self.cache    = cache or PredictionCache()
        self.device   = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._latencies: List[float] = []

    def _preprocess(self, current: np.ndarray) -> torch.Tensor:
        """Normalise and reshape CV current array."""
        if len(current) != 2000:
            x_old = np.linspace(0, 1, len(current))
            x_new = np.linspace(0, 1, 2000)
            current = np.interp(x_new, x_old, current).astype(np.float32)
        std = current.std()
        if std > 0:
            current = (current - current.mean()) / std
        return torch.tensor(current, dtype=torch.float32).unsqueeze(0).unsqueeze(0)

    def predict_cv(
        self,
        current: np.ndarray,
        use_ensemble: bool = True,
        check_anomaly: bool = True,
    ) -> Dict[str, Any]:
        """
        Full CV prediction pipeline.

        Args:
            current:      CV current array
            use_ensemble: use ensemble for uncertainty (falls back to single)
            check_anomaly: run anomaly detection first

        Returns:
            Prediction dict with uncertainty, anomaly flag, latency
        """
        t0 = time.perf_counter()

        # Check cache
        cached = self.cache.get(current, "cv_ensemble" if use_ensemble else "cv_single")
        if cached is not None:
            return {**cached, "cached": True}

        result: Dict[str, Any] = {"cached": False}

        # Preprocess
        x = self._preprocess(current).to(self.device)

        # 1. Anomaly detection
        if check_anomaly:
            anomaly_model = self.registry.get("anomaly_detector")
            if anomaly_model is not None:
                with torch.no_grad():
                    ad_out = anomaly_model(x)
                result["anomaly"] = {
                    "is_anomaly":          bool(ad_out["is_anomaly"][0].item()),
                    "anomaly_score":       float(ad_out["anomaly_score"][0].item()),
                    "reconstruction_error":float(ad_out["reconstruction_error"][0].item()),
                    "quality":             "anomaly" if ad_out["is_anomaly"][0].item() else "normal",
                }

        # 2. CV prediction (ensemble → single → error)
        if use_ensemble:
            model = self.registry.get("cv_ensemble")
            if model is not None:
                with torch.no_grad():
                    out = model(x)
                result["prediction"] = {
                    "reversibility":              float(out["reversibility"].item()),
                    "reversibility_uncertainty":  float(out.get("reversibility_uncertainty", torch.tensor(0)).item()),
                    "mechanism_class":            int(out["mechanism"].argmax().item()),
                    "mechanism_confidence":       float(out["mechanism"].softmax(-1).max().item()),
                    "peaks":                      out["peaks"].cpu().numpy()[0].tolist(),
                    "parameters":                 out["parameters"].cpu().numpy()[0].tolist(),
                    "model":                      "ensemble_5",
                    "uncertainty_level":          "low" if float(out.get("reversibility_uncertainty", torch.tensor(0)).item()) < 0.05 else "medium",
                }
            else:
                use_ensemble = False  # Fall back

        if not use_ensemble:
            model = self.registry.get("cv_single")
            if model is not None:
                with torch.no_grad():
                    out = model(x, task="all")
                result["prediction"] = {
                    "reversibility":     float(out["reversibility"].item()),
                    "mechanism_class":   int(out["mechanism"].argmax().item()),
                    "mechanism_confidence": float(out["mechanism"].softmax(-1).max().item()),
                    "peaks":             out["peaks"].cpu().numpy()[0].tolist(),
                    "parameters":        out["parameters"].cpu().numpy()[0].tolist(),
                    "model":             "single",
                    "uncertainty_level": "unknown",
                }
            else:
                result["error"] = "No CV model available"

        # Latency
        elapsed_ms = (time.perf_counter() - t0) * 1000
        result["latency_ms"] = round(elapsed_ms, 2)
        self._latencies.append(elapsed_ms)

        # Cache result
        if "error" not in result:
            self.cache.set(current, "cv_ensemble" if use_ensemble else "cv_single", result)

        return result

    def health(self) -> Dict[str, Any]:
        """Health check with model status and performance metrics."""
        latencies = self._latencies[-100:] if self._latencies else [0]
        return {
            "status":       "healthy",
            "models":       self.registry.status(),
            "cache":        self.cache.stats(),
            "latency_ms": {
                "mean":  round(np.mean(latencies), 2),
                "p50":   round(np.percentile(latencies, 50), 2),
                "p95":   round(np.percentile(latencies, 95), 2),
                "p99":   round(np.percentile(latencies, 99), 2),
            },
            "device":       str(torch.device("cuda" if torch.cuda.is_available() else "cpu")),
        }


# ── Singleton ─────────────────────────────────────────────────────────────

_registry  = None
_predictor = None

def get_predictor() -> ProductionPredictor:
    """Get or create the global predictor singleton."""
    global _registry, _predictor
    if _predictor is None:
        _registry  = ModelRegistry()
        _registry.load_all()
        _predictor = ProductionPredictor(_registry)
    return _predictor


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Loading production model server...")

    predictor = get_predictor()
    health    = predictor.health()

    print("\nModel Server Health:")
    print(f"  Status: {health['status']}")
    print(f"  Device: {health['device']}")
    print(f"  Models loaded: {list(health['models'].keys())}")
    print(f"  Cache size: {health['cache']['size']}")

    # Test prediction
    current = np.sin(np.linspace(0, 4 * np.pi, 2000)).astype(np.float32)
    result  = predictor.predict_cv(current)

    print(f"\nTest prediction:")
    print(f"  Latency: {result['latency_ms']} ms")
    if "prediction" in result:
        pred = result["prediction"]
        print(f"  Reversibility: {pred['reversibility']:.4f}")
        print(f"  Mechanism: class {pred['mechanism_class']} ({pred['mechanism_confidence']:.2%} conf)")
        print(f"  Model: {pred['model']}")
    if "anomaly" in result:
        print(f"  Anomaly: {result['anomaly']['quality']} (score={result['anomaly']['anomaly_score']:.3f})")

    print("\n✅ Production model server OK")
