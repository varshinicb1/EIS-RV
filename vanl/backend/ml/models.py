"""
Surrogate ML Models
=====================
Scikit-learn based surrogates for:
  1. Synthesis Model:  (composition + synthesis) → structural descriptors
  2. EIS Model:        structural descriptors → EIS parameters

Uses GradientBoostingRegressor wrapped in MultiOutputRegressor
for robust, out-of-the-box performance on tabular data.
"""

import logging
import os
import pickle
from typing import Optional, Tuple

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_squared_error, r2_score

from ..core.materials import (
    MaterialComposition, SynthesisParameters, StructuralDescriptors,
    EISParameters, MATERIAL_DATABASE
)

logger = logging.getLogger(__name__)

__all__ = ["SynthesisSurrogate", "EISSurrogate", "load_model", "save_model"]

MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_models")


class SynthesisSurrogate:
    """
    ML surrogate: (composition_vector, synthesis_vector) → structural_descriptors.

    Architecture: StandardScaler → GradientBoosting × 7 outputs
    Each output (porosity, surface_area, conductivity, ...) is trained
    independently but wrapped for convenience.
    """

    def __init__(self, model_type: str = "gbr"):
        """
        Args:
            model_type: 'gbr' (GradientBoosting) or 'mlp' (neural net)
        """
        self.model_type = model_type
        self.scaler_X = StandardScaler()
        self.scaler_Y = StandardScaler()
        self._fitted = False

        if model_type == "mlp":
            base = MLPRegressor(
                hidden_layer_sizes=(128, 64, 32),
                activation="relu",
                max_iter=500,
                early_stopping=True,
                validation_fraction=0.1,
                random_state=42,
            )
        else:
            base = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42,
            )

        self.model = MultiOutputRegressor(base)

    def fit(self, X: np.ndarray, Y: np.ndarray) -> dict:
        """
        Train the synthesis surrogate.

        Args:
            X: Input features (n_samples, n_features)
            Y: Output descriptors (n_samples, 7)

        Returns:
            Training metrics dictionary
        """
        logger.info("Training SynthesisSurrogate (%s) on %d samples...",
                     self.model_type, len(X))

        X_scaled = self.scaler_X.fit_transform(X)
        Y_scaled = self.scaler_Y.fit_transform(Y)

        self.model.fit(X_scaled, Y_scaled)
        self._fitted = True

        # Compute training metrics
        Y_pred_scaled = self.model.predict(X_scaled)
        Y_pred = self.scaler_Y.inverse_transform(Y_pred_scaled)

        mse = mean_squared_error(Y, Y_pred)
        r2 = r2_score(Y, Y_pred)

        metrics = {
            "mse": float(mse),
            "r2": float(r2),
            "n_samples": len(X),
            "n_features": X.shape[1],
            "n_outputs": Y.shape[1],
        }
        logger.info("  Training MSE=%.6f, R²=%.4f", mse, r2)
        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict structural descriptors from composition + synthesis."""
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        X_scaled = self.scaler_X.transform(X)
        Y_pred_scaled = self.model.predict(X_scaled)
        return self.scaler_Y.inverse_transform(Y_pred_scaled)

    def predict_descriptors(
        self,
        composition: MaterialComposition,
        synthesis: SynthesisParameters,
    ) -> StructuralDescriptors:
        """High-level prediction returning a StructuralDescriptors object."""
        material_keys = sorted(MATERIAL_DATABASE.keys())
        x = np.concatenate([
            composition.to_vector(material_keys),
            synthesis.to_vector()
        ]).reshape(1, -1)

        y = self.predict(x)[0]

        return StructuralDescriptors(
            porosity=float(np.clip(y[0], 0.01, 0.95)),
            surface_area_m2_g=float(np.clip(10 ** (y[1] * 4), 5, 3000)),
            conductivity_S_m=float(np.clip(10 ** (y[2] * 7), 1e-6, 1e7)),
            defect_density=float(np.clip(y[3], 0.01, 0.6)),
            layer_thickness_nm=float(np.clip(10 ** (y[4] * 4), 5, 5000)),
            crystallinity=float(np.clip(y[5], 0.1, 0.98)),
            particle_size_nm=float(np.clip(10 ** (y[6] * 3), 2, 500)),
        )


class EISSurrogate:
    """
    ML surrogate: structural_descriptors → EIS parameters.

    Architecture: StandardScaler → GradientBoosting × 5 outputs
    Outputs are in log-space for Rs, Rct, Cdl, sigma_warburg + linear n_cpe.
    """

    def __init__(self, model_type: str = "gbr"):
        self.model_type = model_type
        self.scaler_X = StandardScaler()
        self.scaler_Y = StandardScaler()
        self._fitted = False

        if model_type == "mlp":
            base = MLPRegressor(
                hidden_layer_sizes=(64, 32, 16),
                activation="relu",
                max_iter=500,
                early_stopping=True,
                validation_fraction=0.1,
                random_state=42,
            )
        else:
            base = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42,
            )

        self.model = MultiOutputRegressor(base)

    def fit(self, X: np.ndarray, Y: np.ndarray) -> dict:
        """
        Train the EIS surrogate.

        Args:
            X: Structural descriptors (n_samples, 7)
            Y: EIS parameters in log-space (n_samples, 5)

        Returns:
            Training metrics
        """
        logger.info("Training EISSurrogate (%s) on %d samples...",
                     self.model_type, len(X))

        X_scaled = self.scaler_X.fit_transform(X)
        Y_scaled = self.scaler_Y.fit_transform(Y)

        self.model.fit(X_scaled, Y_scaled)
        self._fitted = True

        Y_pred_scaled = self.model.predict(X_scaled)
        Y_pred = self.scaler_Y.inverse_transform(Y_pred_scaled)

        mse = mean_squared_error(Y, Y_pred)
        r2 = r2_score(Y, Y_pred)

        metrics = {
            "mse": float(mse),
            "r2": float(r2),
            "n_samples": len(X),
            "n_features": X.shape[1],
            "n_outputs": Y.shape[1],
        }
        logger.info("  Training MSE=%.6f, R²=%.4f", mse, r2)
        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict EIS parameters from structural descriptors."""
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        X_scaled = self.scaler_X.transform(X)
        Y_pred_scaled = self.model.predict(X_scaled)
        return self.scaler_Y.inverse_transform(Y_pred_scaled)

    def predict_eis(self, descriptors: StructuralDescriptors) -> EISParameters:
        """High-level prediction returning EISParameters object."""
        x = descriptors.to_vector().reshape(1, -1)
        y = self.predict(x)[0]
        return EISParameters.from_vector(y)


def save_model(model, name: str, directory: Optional[str] = None):
    """Save a trained model to disk."""
    d = directory or MODEL_DIR
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{name}.pkl")
    with open(path, "wb") as f:
        pickle.dump(model, f)
    logger.info("Model saved: %s", path)
    return path


def load_model(name: str, directory: Optional[str] = None):
    """Load a trained model from disk."""
    d = directory or MODEL_DIR
    path = os.path.join(d, f"{name}.pkl")
    with open(path, "rb") as f:
        model = pickle.load(f)
    logger.info("Model loaded: %s", path)
    return model
