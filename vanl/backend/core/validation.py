"""
Model Validation Module
=========================
Validates VANL's EIS models against experimental data.

Key capabilities:
    1. Circuit parameter fitting via least-squares optimization
    2. Comparison of fitted parameters against model predictions
    3. Goodness-of-fit metrics (RMSE, R², residual analysis)
    4. Validation report generation

This module closes the gap between "the software runs" and
"a scientist can trust the outputs" by providing concrete
comparisons against real experimental spectra.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

import numpy as np

from .materials import EISParameters
from .eis_engine import randles_impedance, simulate_eis
from .kk_validation import kramers_kronig_validate, KKValidationResult
from .data_loader import ExternalEISData, load_perovskite_eis

logger = logging.getLogger(__name__)

__all__ = [
    "FitResult",
    "ValidationReport",
    "fit_randles_to_data",
    "validate_against_perovskites",
    "generate_validation_report",
]


@dataclass
class FitResult:
    """Result of fitting Randles circuit to experimental data."""

    # Fitted parameters
    params: EISParameters = field(default_factory=EISParameters)

    # Fit quality
    rmse: float = 0.0
    rmse_relative: float = 0.0  # RMSE / max(|Z|)
    r_squared: float = 0.0
    n_points: int = 0
    converged: bool = False
    message: str = ""

    # Residuals
    residuals_real: np.ndarray = field(default_factory=lambda: np.array([]))
    residuals_imag: np.ndarray = field(default_factory=lambda: np.array([]))

    # KK validation of the input data
    kk_result: Optional[KKValidationResult] = None

    def to_dict(self) -> dict:
        d = {
            "params": self.params.to_dict(),
            "rmse": round(self.rmse, 4),
            "rmse_relative_pct": round(self.rmse_relative * 100, 2),
            "r_squared": round(self.r_squared, 4),
            "n_points": self.n_points,
            "converged": self.converged,
            "message": self.message,
        }
        if self.kk_result:
            d["kk_validation"] = self.kk_result.to_dict()
        return d


@dataclass
class ValidationReport:
    """Complete validation report comparing model vs experiment."""

    spectra_count: int = 0
    fitted_count: int = 0
    kk_passed_count: int = 0

    # Parameter-level validation
    param_stats: Dict[str, dict] = field(default_factory=dict)

    # Individual fit results
    fits: List[dict] = field(default_factory=list)

    # Overall assessment
    overall_message: str = ""

    def to_dict(self) -> dict:
        return {
            "spectra_count": self.spectra_count,
            "fitted_count": self.fitted_count,
            "kk_passed_count": self.kk_passed_count,
            "param_stats": self.param_stats,
            "fits": self.fits,
            "overall_message": self.overall_message,
        }


def _objective_randles(
    params_vec: np.ndarray,
    freq: np.ndarray,
    Z_real_exp: np.ndarray,
    Z_imag_exp: np.ndarray,
) -> float:
    """Objective function for Randles circuit fitting."""
    Rs, Rct, log_Cdl, sigma_w, n_cpe = params_vec

    Cdl = 10 ** log_Cdl
    n_cpe = np.clip(n_cpe, 0.5, 1.0)

    Z_model = randles_impedance(
        freq, Rs=Rs, Rct=Rct, Cdl=Cdl,
        sigma_w=sigma_w, n_cpe=n_cpe,
    )

    Z_real_model = np.real(Z_model)
    Z_imag_model = np.imag(Z_model)

    # Weighted sum of squared errors (weight by 1/|Z|² for scale invariance)
    Z_mag = np.sqrt(Z_real_exp ** 2 + Z_imag_exp ** 2)
    weights = 1.0 / np.maximum(Z_mag ** 2, 1e-20)

    err_real = (Z_real_model - Z_real_exp) ** 2 * weights
    err_imag = (Z_imag_model - Z_imag_exp) ** 2 * weights

    return float(np.sum(err_real + err_imag))


def fit_randles_to_data(
    frequencies: np.ndarray,
    Z_real: np.ndarray,
    Z_imag: np.ndarray,
    run_kk: bool = True,
) -> FitResult:
    """
    Fit a modified Randles circuit to experimental EIS data.

    Uses Nelder-Mead optimization (no gradient required, robust for
    noisy impedance data). Falls back to differential evolution if
    Nelder-Mead fails.

    Args:
        frequencies: Frequency array (Hz)
        Z_real: Real impedance (Ω)
        Z_imag: Imaginary impedance (Ω)
        run_kk: Whether to run KK validation on the data first

    Returns:
        FitResult with fitted parameters and quality metrics
    """
    result = FitResult()
    result.n_points = len(frequencies)

    # KK validation first
    if run_kk and len(frequencies) >= 5:
        result.kk_result = kramers_kronig_validate(frequencies, Z_real, Z_imag)

    # Initial parameter estimates from data
    Rs_init = float(np.min(Z_real))  # Rs ≈ high-frequency Z_real intercept
    Z_mag = np.sqrt(Z_real ** 2 + Z_imag ** 2)
    Rct_init = float(np.max(Z_real) - Rs_init)  # Rct ≈ semicircle diameter
    Rct_init = max(Rct_init, 1.0)

    # Cdl estimate from peak frequency: ω_peak ≈ 1/(Rct·Cdl)
    imag_min_idx = np.argmin(Z_imag)  # Most negative Z_imag
    if imag_min_idx > 0 and imag_min_idx < len(frequencies) - 1:
        f_peak = frequencies[imag_min_idx]
        Cdl_init = 1.0 / (2 * np.pi * f_peak * Rct_init)
    else:
        Cdl_init = 1e-5

    Cdl_init = np.clip(Cdl_init, 1e-9, 1e-1)
    sigma_init = 50.0
    n_cpe_init = 0.9

    x0 = np.array([Rs_init, Rct_init, np.log10(Cdl_init), sigma_init, n_cpe_init])

    # Bounds
    bounds = [
        (0.01, 1e5),        # Rs
        (0.1, 1e6),         # Rct
        (-10, -1),          # log10(Cdl)
        (0.0, 1e4),         # sigma_w
        (0.5, 1.0),         # n_cpe
    ]

    try:
        from scipy.optimize import minimize, differential_evolution

        # Try Nelder-Mead first (fast)
        res = minimize(
            _objective_randles, x0,
            args=(frequencies, Z_real, Z_imag),
            method="Nelder-Mead",
            options={"maxiter": 5000, "xatol": 1e-8, "fatol": 1e-10},
        )

        # If Nelder-Mead doesn't converge well, try differential evolution
        if not res.success or res.fun > 1.0:
            res2 = differential_evolution(
                _objective_randles,
                bounds=bounds,
                args=(frequencies, Z_real, Z_imag),
                maxiter=500,
                seed=42,
                tol=1e-8,
            )
            if res2.fun < res.fun:
                res = res2

        Rs_fit, Rct_fit, log_Cdl_fit, sigma_fit, n_cpe_fit = res.x
        Cdl_fit = 10 ** log_Cdl_fit
        n_cpe_fit = np.clip(n_cpe_fit, 0.5, 1.0)

        result.params = EISParameters(
            Rs=float(Rs_fit),
            Rct=float(Rct_fit),
            Cdl=float(Cdl_fit),
            sigma_warburg=float(max(0, sigma_fit)),
            n_cpe=float(n_cpe_fit),
        )
        result.converged = res.success

        # Compute fit quality
        Z_fit = randles_impedance(
            frequencies, Rs=Rs_fit, Rct=Rct_fit, Cdl=Cdl_fit,
            sigma_w=max(0, sigma_fit), n_cpe=n_cpe_fit,
        )
        Z_real_fit = np.real(Z_fit)
        Z_imag_fit = np.imag(Z_fit)

        result.residuals_real = Z_real - Z_real_fit
        result.residuals_imag = Z_imag - Z_imag_fit

        total_error = np.sqrt(result.residuals_real ** 2 + result.residuals_imag ** 2)
        result.rmse = float(np.sqrt(np.mean(total_error ** 2)))
        result.rmse_relative = result.rmse / float(np.max(Z_mag) + 1e-10)

        # R² (coefficient of determination)
        Z_combined_exp = np.concatenate([Z_real, Z_imag])
        Z_combined_fit = np.concatenate([Z_real_fit, Z_imag_fit])
        ss_res = np.sum((Z_combined_exp - Z_combined_fit) ** 2)
        ss_tot = np.sum((Z_combined_exp - np.mean(Z_combined_exp)) ** 2)
        result.r_squared = float(1.0 - ss_res / (ss_tot + 1e-15))

        result.message = (
            f"Fit {'converged' if res.success else 'did not converge'}. "
            f"R²={result.r_squared:.4f}, RMSE={result.rmse:.2f} Ω"
        )

    except ImportError:
        # Scipy not available — use manual grid search as fallback
        result.converged = False
        result.message = "scipy not available for optimization"

        # Very basic grid search
        best_obj = float('inf')
        best_x = x0.copy()
        for Rs_try in np.linspace(max(0.1, Rs_init * 0.5), Rs_init * 2, 10):
            for Rct_try in np.linspace(max(1, Rct_init * 0.5), Rct_init * 2, 10):
                x_try = np.array([Rs_try, Rct_try, np.log10(Cdl_init), sigma_init, n_cpe_init])
                obj = _objective_randles(x_try, frequencies, Z_real, Z_imag)
                if obj < best_obj:
                    best_obj = obj
                    best_x = x_try.copy()

        Rs_fit, Rct_fit, log_Cdl_fit, sigma_fit, n_cpe_fit = best_x
        result.params = EISParameters(
            Rs=float(Rs_fit), Rct=float(Rct_fit),
            Cdl=float(10 ** log_Cdl_fit),
            sigma_warburg=float(max(0, sigma_fit)),
            n_cpe=float(np.clip(n_cpe_fit, 0.5, 1.0)),
        )
        result.message = "Fallback grid search (scipy unavailable)"

    except Exception as e:
        result.message = f"Fit error: {str(e)}"
        logger.error("Randles fitting failed: %s", e)

    return result


def validate_against_perovskites(
    max_spectra: int = 28,
    temperature_filter: Optional[float] = None,
) -> ValidationReport:
    """
    Validate VANL's Randles circuit fitter against real perovskite EIS data.

    For each spectrum:
        1. Run KK check on the raw data
        2. Fit Randles circuit parameters
        3. Record fit quality and extracted parameters
    """
    report = ValidationReport()

    try:
        spectra = load_perovskite_eis(temperature_filter=temperature_filter)
    except FileNotFoundError:
        report.overall_message = "Perovskite dataset not found. Run the data download first."
        return report

    if not spectra:
        report.overall_message = "No spectra loaded from perovskite dataset."
        return report

    report.spectra_count = min(len(spectra), max_spectra)

    # Collect all fitted parameter values for statistical summary
    param_collections = {
        "Rs": [], "Rct": [], "Cdl": [],
        "sigma_warburg": [], "n_cpe": [],
    }

    for spectrum in spectra[:max_spectra]:
        fit = fit_randles_to_data(
            spectrum.frequencies,
            spectrum.Z_real,
            spectrum.Z_imag,
            run_kk=True,
        )

        fit_dict = fit.to_dict()
        fit_dict["spectrum_name"] = spectrum.name
        fit_dict["temperature"] = spectrum.temperature
        fit_dict["n_points"] = len(spectrum.frequencies)
        report.fits.append(fit_dict)

        if fit.converged or fit.r_squared > 0.8:
            report.fitted_count += 1
            param_collections["Rs"].append(fit.params.Rs)
            param_collections["Rct"].append(fit.params.Rct)
            param_collections["Cdl"].append(fit.params.Cdl)
            param_collections["sigma_warburg"].append(fit.params.sigma_warburg)
            param_collections["n_cpe"].append(fit.params.n_cpe)

        if fit.kk_result and fit.kk_result.is_valid:
            report.kk_passed_count += 1

    # Statistical summary of fitted parameters
    for name, values in param_collections.items():
        if values:
            arr = np.array(values)
            report.param_stats[name] = {
                "mean": float(np.mean(arr)),
                "median": float(np.median(arr)),
                "std": float(np.std(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "count": len(values),
            }

    # Overall assessment
    fit_rate = report.fitted_count / max(report.spectra_count, 1)
    kk_rate = report.kk_passed_count / max(report.spectra_count, 1)

    report.overall_message = (
        f"Validated against {report.spectra_count} perovskite EIS spectra. "
        f"Successful fits: {report.fitted_count}/{report.spectra_count} ({fit_rate:.0%}). "
        f"KK-compliant spectra: {report.kk_passed_count}/{report.spectra_count} ({kk_rate:.0%}). "
        f"Fitted parameter ranges provide experimental reference for model calibration."
    )

    logger.info(report.overall_message)
    return report


def generate_validation_report() -> dict:
    """
    Generate a complete validation report.

    This is the main entry point for validation.
    Returns a dictionary suitable for API response or JSON export.
    """
    report = validate_against_perovskites()
    return report.to_dict()
