"""
Kramers-Kronig Validation Module
===================================
Implements the Kramers-Kronig (KK) consistency check for EIS data.

The KK relations are integral transforms that connect the real and
imaginary parts of impedance for any causal, linear, time-invariant system:

    Z''(ω₀) = -(2ω₀/π) ∫₀^∞ [Z'(ω) - Z'(∞)] / (ω² - ω₀²) dω

    Z'(ω₀) = Z'(∞) + (2/π) ∫₀^∞ [ω·Z''(ω) - ω₀·Z''(ω₀)] / (ω² - ω₀²) dω

If KK residuals exceed ~1-2%, the data may indicate:
    - Non-linear behavior
    - System instability during measurement
    - Instrumentation artifacts
    - Insufficiently slow/fast frequency limits

References:
    Boukamp, B.A. "A Linear Kronig-Kramers Transform Test for
    Immittance Data Validation", J. Electrochem. Soc. 142 (1995) 1885.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional impedance.py backend for linear Kramers-Kronig validation
# ---------------------------------------------------------------------------
try:
    from impedance.validation import linKK
    HAS_IMPEDANCEPY = True
    logger.debug("impedance.py is available – linKK backend enabled")
except ImportError:
    HAS_IMPEDANCEPY = False
    logger.debug("impedance.py not found – falling back to built-in KK backend")

__all__ = [
    "KKValidationResult",
    "kramers_kronig_validate",
    "kk_residuals",
]


@dataclass
class KKValidationResult:
    """Result of a Kramers-Kronig validation check."""

    # Per-point residuals (%)
    residuals_real: np.ndarray = field(default_factory=lambda: np.array([]))
    residuals_imag: np.ndarray = field(default_factory=lambda: np.array([]))

    # Summary statistics
    mean_residual_real: float = 0.0
    mean_residual_imag: float = 0.0
    max_residual_real: float = 0.0
    max_residual_imag: float = 0.0
    rms_residual: float = 0.0

    # Reconstructed spectra from KK transform
    Z_real_kk: np.ndarray = field(default_factory=lambda: np.array([]))
    Z_imag_kk: np.ndarray = field(default_factory=lambda: np.array([]))

    # Quality verdict
    quality: str = "unknown"  # "excellent", "good", "marginal", "fail"
    is_valid: bool = False
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "quality": self.quality,
            "is_valid": self.is_valid,
            "message": self.message,
            "mean_residual_real_pct": round(self.mean_residual_real, 3),
            "mean_residual_imag_pct": round(self.mean_residual_imag, 3),
            "max_residual_real_pct": round(self.max_residual_real, 3),
            "max_residual_imag_pct": round(self.max_residual_imag, 3),
            "rms_residual_pct": round(self.rms_residual, 3),
            "residuals_real": self.residuals_real.tolist(),
            "residuals_imag": self.residuals_imag.tolist(),
            "Z_real_kk": self.Z_real_kk.tolist(),
            "Z_imag_kk": self.Z_imag_kk.tolist(),
        }


def _lin_kk_fit(
    omega: np.ndarray,
    Z_real: np.ndarray,
    Z_imag: np.ndarray,
    n_rc: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Linear Kramers-Kronig test using the Boukamp method.

    Fits the impedance data with a series of (R||C) elements (Voigt circuit)
    distributed logarithmically in time constant space.

    Key improvement over the naive implementation: the tau grid is extended
    one decade beyond the measured frequency range on each side. This prevents
    the large residuals at the band edges that occur when the Voigt circuit
    cannot represent the tails of the relaxation distribution — a common
    artefact with CHI608E data at 100 kHz where instrument inductance causes
    apparent non-KK behaviour that is actually just bandwidth limitation.

    Reference: Schönleber et al., Electrochimica Acta 131 (2014) 20-27.
    """
    n = len(omega)

    # Number of RC elements: use n (not n//2) for better coverage
    if n_rc is None:
        n_rc = max(n, 10)

    # Extend tau grid one decade beyond the measured range on each side.
    # This is the key fix for high-frequency residuals in CHI608E data.
    tau_min = 1.0 / (omega.max() * 10.0)   # one decade above highest freq
    tau_max = 1.0 / (omega.min() * 0.1)    # one decade below lowest freq
    tau = np.logspace(np.log10(tau_min), np.log10(tau_max), n_rc)

    # Build design matrix — vectorised for speed
    # Z_RC(ω, τ) = R / (1 + jωτ)
    # Real: R / (1 + ω²τ²)
    # Imag: -Rωτ / (1 + ω²τ²)
    wt2 = (omega[:, np.newaxis] * tau[np.newaxis, :]) ** 2   # (n, n_rc)
    denom = 1.0 + wt2

    A_real = np.zeros((n, n_rc + 1))
    A_imag = np.zeros((n, n_rc + 1))

    # Rs column (constant offset, real part only)
    A_real[:, 0] = 1.0

    A_real[:, 1:] = 1.0 / denom
    A_imag[:, 1:] = -(omega[:, np.newaxis] * tau[np.newaxis, :]) / denom

    # Stack real and imaginary parts
    A = np.vstack([A_real, A_imag])
    b = np.concatenate([Z_real, Z_imag])

    # Solve with non-negative least squares (R values must be ≥ 0)
    try:
        from scipy.optimize import nnls
        x, _ = nnls(A, b)
    except ImportError:
        x, _, _, _ = np.linalg.lstsq(A, b, rcond=None)

    # Reconstruct impedance from fit
    Z_real_fit = A_real @ x
    Z_imag_fit = A_imag @ x

    return Z_real_fit, Z_imag_fit


def _integral_kk_transform(
    omega: np.ndarray,
    Z_real: np.ndarray,
    Z_imag: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Direct integral Kramers-Kronig transform.

    Computes both directions:
        Z_real → Z_imag_kk (using the real→imag KK relation)
        Z_imag → Z_real_kk (using the imag→real KK relation)
    """
    n = len(omega)
    Z_real_inf = Z_real[-1]  # High-frequency limit approximation
    Z_real_shifted = Z_real - Z_real_inf

    Z_imag_kk = np.zeros(n)
    Z_real_kk = np.zeros(n)

    for i in range(n):
        omega_0 = omega[i]
        intg_imag = np.zeros(n)
        intg_real = np.zeros(n)

        for j in range(n):
            if i == j:
                continue
            denom = omega[j] ** 2 - omega_0 ** 2
            if abs(denom) < 1e-30:
                continue
            intg_imag[j] = Z_real_shifted[j] / denom
            intg_real[j] = (omega[j] * Z_imag[j]) / denom

        Z_imag_kk[i] = -(2.0 * omega_0 / np.pi) * np.trapz(intg_imag, omega)
        Z_real_kk[i] = Z_real_inf + (2.0 / np.pi) * np.trapz(intg_real, omega)

    return Z_real_kk, Z_imag_kk


def kk_residuals(
    Z_real: np.ndarray,
    Z_imag: np.ndarray,
    Z_real_fit: np.ndarray,
    Z_imag_fit: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate KK residuals as percentage deviations.

    Δ_real(%) = 100 × (Z'_data - Z'_KK) / |Z_data|
    Δ_imag(%) = 100 × (Z''_data - Z''_KK) / |Z_data|
    """
    Z_mag = np.sqrt(Z_real ** 2 + Z_imag ** 2)
    Z_mag = np.maximum(Z_mag, 1e-15)

    res_real = 100.0 * (Z_real - Z_real_fit) / Z_mag
    res_imag = 100.0 * (Z_imag - Z_imag_fit) / Z_mag

    return res_real, res_imag


def kramers_kronig_validate(
    frequencies: np.ndarray,
    Z_real: np.ndarray,
    Z_imag: np.ndarray,
    method: str = "lin_kk",
    threshold_excellent: float = 0.5,
    threshold_good: float = 1.0,
    threshold_marginal: float = 2.5,
) -> KKValidationResult:
    """
    Perform Kramers-Kronig validation on EIS data.

    When impedance.py is installed and *method* is ``"lin_kk"``, the
    validation is delegated to ``impedance.validation.linKK`` which
    implements the Schönleber et al. (2014) algorithm with automatic
    determination of the optimal number of RC elements via the μ
    (under-/over-fitting) criterion.  This typically yields tighter
    residuals than the built-in NNLS Boukamp method.

    If impedance.py is **not** installed, the function falls back to the
    original built-in implementation, preserving full backward
    compatibility.

    Args:
        frequencies: Frequency array (Hz)
        Z_real: Real impedance (Ω)
        Z_imag: Imaginary impedance (Ω)
        method: "lin_kk" (Boukamp) or "integral" (direct transform)
        threshold_excellent: RMS residual below this → excellent
        threshold_good: RMS residual below this → good
        threshold_marginal: RMS residual below this → marginal

    Returns:
        KKValidationResult with residuals, quality score, and verdict
    """
    result = KKValidationResult()

    if len(frequencies) < 5:
        result.quality = "insufficient_data"
        result.is_valid = False
        result.message = "Need at least 5 frequency points for KK validation"
        return result

    # Sort by frequency (ascending) — both backends need this
    sort_idx = np.argsort(frequencies)
    frequencies_sorted = np.array(frequencies[sort_idx], dtype=float)
    Z_real = Z_real[sort_idx].copy()
    Z_imag = Z_imag[sort_idx].copy()
    omega = 2.0 * np.pi * frequencies_sorted

    try:
        # --------------------------------------------------------------
        # PATH A – impedance.py linKK backend (preferred)
        # --------------------------------------------------------------
        if HAS_IMPEDANCEPY and method == "lin_kk":
            try:
                logger.info("Using impedance.py linKK backend for KK validation")

                # impedance.py linKK signature:
                #   linKK(f, Z, c=0.85, max_M=50, fit_type='real', add_cap=False)
                # Returns: M, mu, Z_fit, resids_real, resids_imag
                Z_complex = np.array(Z_real + 1j * Z_imag, dtype=complex)

                M, mu, Z_fit_complex, resids_real_raw, resids_imag_raw = linKK(
                    frequencies_sorted,
                    Z_complex,
                    c=0.85,
                    max_M=50,
                    fit_type='real',
                )

                Z_real_fit = np.real(Z_fit_complex)
                Z_imag_fit = np.imag(Z_fit_complex)

                # linKK returns residuals normalised by |Z|, already fractional.
                # Convert to percentage for consistency with our API.
                res_real = resids_real_raw * 100.0
                res_imag = resids_imag_raw * 100.0

                logger.debug(
                    "linKK converged with M=%d RC elements, μ=%.4f", M, mu
                )

                result.Z_real_kk = Z_real_fit
                result.Z_imag_kk = Z_imag_fit
                result.residuals_real = res_real
                result.residuals_imag = res_imag

            except Exception as exc:
                logger.warning(
                    "impedance.py linKK failed (%s), falling back to built-in",
                    exc,
                )
                # Fall through to PATH B
                Z_real_fit = Z_imag_fit = None
        else:
            Z_real_fit = Z_imag_fit = None

        # --------------------------------------------------------------
        # PATH B – built-in backend (fallback)
        # --------------------------------------------------------------
        if Z_real_fit is None or Z_imag_fit is None:
            logger.info("Using built-in KK backend for validation")
            if method == "lin_kk":
                Z_real_fit, Z_imag_fit = _lin_kk_fit(omega, Z_real, Z_imag)
            else:
                Z_real_fit, Z_imag_fit = _integral_kk_transform(
                    omega, Z_real, Z_imag
                )

            result.Z_real_kk = Z_real_fit
            result.Z_imag_kk = Z_imag_fit

            # Calculate residuals
            res_real, res_imag = kk_residuals(
                Z_real, Z_imag, Z_real_fit, Z_imag_fit
            )
            result.residuals_real = res_real
            result.residuals_imag = res_imag

        # Summary statistics (common to both paths)
        res_real = result.residuals_real
        res_imag = result.residuals_imag

        result.mean_residual_real = float(np.mean(np.abs(res_real)))
        result.mean_residual_imag = float(np.mean(np.abs(res_imag)))
        result.max_residual_real = float(np.max(np.abs(res_real)))
        result.max_residual_imag = float(np.max(np.abs(res_imag)))

        rms = float(np.sqrt(np.mean(res_real ** 2 + res_imag ** 2)))
        result.rms_residual = rms

        # Quality verdict
        if rms < threshold_excellent:
            result.quality = "excellent"
            result.is_valid = True
            result.message = (
                f"Excellent KK compliance (RMS={rms:.2f}%). "
                "Data is consistent with a causal, linear, stable system."
            )
        elif rms < threshold_good:
            result.quality = "good"
            result.is_valid = True
            result.message = (
                f"Good KK compliance (RMS={rms:.2f}%). "
                "Minor deviations within acceptable range."
            )
        elif rms < threshold_marginal:
            result.quality = "marginal"
            result.is_valid = True
            result.message = (
                f"Marginal KK compliance (RMS={rms:.2f}%). "
                "Some frequency ranges show non-ideal behavior. "
                "Check for drift or non-linearity."
            )
        else:
            result.quality = "fail"
            result.is_valid = False
            result.message = (
                f"KK validation failed (RMS={rms:.2f}%). "
                "Significant deviations detected. Data may be unreliable "
                "due to system instability, non-linearity, or measurement artifacts."
            )

        logger.info(
            "KK validation: %s (RMS=%.2f%%, mean_real=%.2f%%, mean_imag=%.2f%%)",
            result.quality, rms,
            result.mean_residual_real, result.mean_residual_imag,
        )

    except Exception as e:
        logger.error("KK validation failed: %s", e)
        result.quality = "error"
        result.is_valid = False
        result.message = f"KK computation error: {str(e)}"

    return result
