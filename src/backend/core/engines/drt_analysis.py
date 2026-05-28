"""
Distribution of Relaxation Times (DRT) Analysis
================================================
Calculate DRT from EIS data using Tikhonov regularization.

The DRT γ(τ) represents the distribution of time constants in the system:
    Z(ω) = R_∞ + ∫ γ(τ) / (1 + jωτ) dτ

This reveals hidden processes in impedance data that are difficult to
identify from Nyquist plots alone.

References:
- Boukamp, B. A. (2015). Electrochimica Acta, 154, 35-46.
- Wan et al. (2015). Electrochimica Acta, 184, 483-499.

Author: VidyuthLabs
Date: May 1, 2026
"""

import numpy as np
from scipy.linalg import solve
from scipy.signal import find_peaks
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional pyDRTtools backend for DRT analysis
# ---------------------------------------------------------------------------
try:
    import pyDRTtools
    from pyDRTtools.runs import EIS_object as PyDRT_EIS, simple_run as pydrt_simple_run
    from pyDRTtools import basics as pydrt_basics
    HAS_PYDRTTOOLS = True
    logger.debug("pyDRTtools is available – DRT backend enabled")
except ImportError:
    HAS_PYDRTTOOLS = False
    logger.debug("pyDRTtools not found – falling back to built-in Tikhonov solver")


@dataclass
class DRTResult:
    """Result from DRT analysis."""
    # DRT data
    tau: np.ndarray          # Time constants (s)
    gamma: np.ndarray        # DRT values (Ω)
    
    # Fitted impedance
    Z_fit_real: np.ndarray
    Z_fit_imag: np.ndarray
    
    # Peaks (identified processes)
    peaks: List[Dict[str, float]]
    
    # Regularization
    lambda_reg: float
    
    # Goodness of fit
    chi_squared: float
    residuals: np.ndarray
    
    # Metadata
    method: str
    success: bool
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "tau": self.tau.tolist(),
            "gamma": self.gamma.tolist(),
            "Z_fit_real": self.Z_fit_real.tolist(),
            "Z_fit_imag": self.Z_fit_imag.tolist(),
            "peaks": self.peaks,
            "lambda_reg": float(self.lambda_reg),
            "chi_squared": float(self.chi_squared),
            "method": self.method,
            "success": self.success,
            "n_peaks": len(self.peaks)
        }


class DRTAnalyzer:
    """
    Calculate Distribution of Relaxation Times (DRT) from EIS data.
    
    Uses Tikhonov regularization to solve the ill-posed inverse problem:
        Z(ω) = R_∞ + ∫ γ(τ) / (1 + jωτ) dτ
    
    The regularization parameter λ controls the smoothness of the solution.
    """
    
    def __init__(self):
        """Initialize DRT analyzer."""
        self.process_types = {
            "charge_transfer": (1e-4, 1e-1),      # 0.1 ms to 100 ms
            "diffusion": (1e-1, 1e2),             # 100 ms to 100 s
            "adsorption": (1e1, 1e4),             # 10 s to 10000 s
            "double_layer": (1e-6, 1e-3)          # 1 µs to 1 ms
        }
    
    def calculate_drt(
        self,
        frequencies: np.ndarray,
        Z_real: np.ndarray,
        Z_imag: np.ndarray,
        lambda_reg: float = 1e-3,
        tau_min: float = 1e-6,
        tau_max: float = 1e3,
        n_tau: int = 100,
        method: str = "tikhonov"
    ) -> DRTResult:
        """
        Calculate DRT from EIS data.

        When pyDRTtools is installed, the DRT is computed using its radial
        basis function (RBF) discretisation and CVXOPT quadratic-programming
        solver with explicit non-negativity constraints.  This is
        mathematically superior to the built-in approach because:

        1. RBF expansion (Gaussian by default) yields smoother γ(τ) than
           simple trapezoidal discretisation.
        2. Positivity is enforced *during* the solve (QP constraint) rather
           than clamped *after* (``np.maximum(gamma, 0)``).
        3. pyDRTtools implements the regularisation-parameter selection
           methods from Wan et al. (2015) and Maradesa et al. (2023).

        If pyDRTtools is **not** installed the function falls back to the
        built-in Tikhonov / ridge solver, preserving full backward
        compatibility.

        Args:
            frequencies: Frequency array (Hz)
            Z_real: Real impedance (Ω)
            Z_imag: Imaginary impedance (Ω)
            lambda_reg: Regularization parameter (smaller = less smooth)
            tau_min: Minimum time constant (s)
            tau_max: Maximum time constant (s)
            n_tau: Number of time constant points
            method: Regularization method ("tikhonov" or "ridge")

        Returns:
            DRTResult object
        """
        logger.info(f"Calculating DRT using {method} regularization (λ={lambda_reg})")

        # ------------------------------------------------------------------
        # PATH A – pyDRTtools backend (preferred when available)
        # ------------------------------------------------------------------
        if HAS_PYDRTTOOLS and method == "tikhonov":
            try:
                return self._calculate_drt_pydrttools(
                    frequencies, Z_real, Z_imag, lambda_reg,
                )
            except Exception as exc:
                logger.warning(
                    "pyDRTtools backend failed (%s), falling back to built-in",
                    exc,
                )

        # ------------------------------------------------------------------
        # PATH B – built-in scipy backend (original code, used as fallback)
        # ------------------------------------------------------------------
        logger.info("Using built-in scipy backend for DRT calculation")

        # Generate time constant grid (log-spaced)
        tau = np.logspace(np.log10(tau_min), np.log10(tau_max), n_tau)

        # Build system matrix A using the correct DRT discretisation.
        # The DRT integral is:
        #   Z(ω) = R∞ + ∫ γ(τ)/(1+jωτ) d(ln τ)
        # Discretised with trapezoidal weights in log-τ space:
        #   Z(ωᵢ) ≈ R∞ + Σⱼ γⱼ · Δ(ln τ)ⱼ / (1 + jωᵢτⱼ)
        # So A[i,j] = Δ(ln τ)ⱼ / (1 + jωᵢτⱼ)   (NOT τⱼ in numerator)

        omega = 2 * np.pi * frequencies
        n_freq = len(frequencies)

        # Trapezoidal weights in log-τ space
        log_tau = np.log(tau)
        delta_log_tau = np.diff(log_tau)
        delta_log_tau = np.concatenate([[delta_log_tau[0]], delta_log_tau])

        # Build matrix A — vectorised: shape (n_freq, n_tau)
        A = delta_log_tau[np.newaxis, :] / (
            1 + 1j * omega[:, np.newaxis] * tau[np.newaxis, :]
        )

        # Separate real and imaginary parts
        A_real = np.real(A)
        A_imag = np.imag(A)

        # Stack matrices
        A_full = np.vstack([A_real, A_imag])

        # Estimate R_infinity (high-frequency resistance)
        R_inf = Z_real[-1] if len(Z_real) > 0 else 0.0

        # Subtract R_infinity from data
        Z_real_corrected = Z_real - R_inf

        # Stack data
        Z_data = np.concatenate([Z_real_corrected, Z_imag])

        # Solve regularized problem
        if method == "tikhonov":
            gamma = self._tikhonov_solve(A_full, Z_data, lambda_reg)
        elif method == "ridge":
            gamma = self._ridge_solve(A_full, Z_data, lambda_reg)
        else:
            raise ValueError(f"Unknown method: {method}")

        # Ensure non-negative
        gamma = np.maximum(gamma, 0)

        # Calculate fitted impedance
        Z_fit = R_inf + A @ gamma
        Z_fit_real = np.real(Z_fit)
        Z_fit_imag = np.imag(Z_fit)

        # Calculate residuals and normalised chi²
        residuals_real = Z_real - Z_fit_real
        residuals_imag = Z_imag - Z_fit_imag
        residuals = np.concatenate([residuals_real, residuals_imag])
        # Normalise by |Z| so chi² is dimensionless and comparable across datasets
        Z_mag = np.sqrt(Z_real**2 + Z_imag**2)
        Z_mag_safe = np.maximum(Z_mag, 1e-15)
        chi_squared = float(np.sum((residuals_real / Z_mag_safe)**2 + (residuals_imag / Z_mag_safe)**2))

        # Detect peaks
        peaks = self._detect_peaks(tau, gamma)

        return DRTResult(
            tau=tau,
            gamma=gamma,
            Z_fit_real=Z_fit_real,
            Z_fit_imag=Z_fit_imag,
            peaks=peaks,
            lambda_reg=lambda_reg,
            chi_squared=chi_squared,
            residuals=residuals,
            method=method,
            success=True
        )

    # ------------------------------------------------------------------
    # pyDRTtools integration helper
    # ------------------------------------------------------------------

    def _calculate_drt_pydrttools(
        self,
        frequencies: np.ndarray,
        Z_real: np.ndarray,
        Z_imag: np.ndarray,
        lambda_reg: float,
    ) -> DRTResult:
        """
        Delegate DRT calculation to pyDRTtools.

        pyDRTtools API recap (from ``runs.py`` and ``basics.py``):

        * ``EIS_object(freq, Z_prime, Z_double_prime)`` — constructor that
          stores frequency, real & imaginary impedance and sets
          ``tau = 1/freq`` as default collocation points.
        * ``simple_run(entry, rbf_type, data_used, induct_used, der_used,
          cv_type, reg_param, shape_control, coeff)`` — performs ridge
          (Tikhonov) regression with RBF discretisation.  Mutates *entry*
          in-place, populating ``entry.gamma``, ``entry.out_tau_vec``,
          ``entry.mu_Z_re``, ``entry.mu_Z_im``, ``entry.R``, ``entry.L``,
          and ``entry.lambda_value``.
        * ``basics.assemble_A_re / assemble_A_im`` — build discretisation
          matrices for each RBF type.
        * ``basics.assemble_M_1 / assemble_M_2`` — build derivative
          penalty matrices.
        * ``basics.x_to_gamma`` — map coefficient vector to γ(τ) on a
          fine τ grid.

        Returns:
            DRTResult populated from pyDRTtools output.
        """
        logger.info("Using pyDRTtools backend for DRT calculation")

        freq_arr = np.array(frequencies, dtype=float)
        Z_re_arr = np.array(Z_real, dtype=float)
        Z_im_arr = np.array(Z_imag, dtype=float)

        # pyDRTtools expects data sorted from high → low frequency
        # (tau = 1/freq ascending ↔ freq descending)
        sort_idx = np.argsort(freq_arr)[::-1]  # descending frequency
        freq_arr = freq_arr[sort_idx]
        Z_re_arr = Z_re_arr[sort_idx]
        Z_im_arr = Z_im_arr[sort_idx]

        # Build pyDRTtools EIS_object
        entry = PyDRT_EIS(freq_arr, Z_re_arr, Z_im_arr)

        # Run Tikhonov ("simple") DRT with the user-supplied λ
        entry = pydrt_simple_run(
            entry,
            rbf_type='Gaussian',
            data_used='Combined Re-Im Data',
            induct_used=1,               # include inductance column
            der_used='1st order',
            cv_type='custom',            # use our λ directly
            reg_param=float(lambda_reg),
            shape_control='FWHM Coefficient',
            coeff=0.5,
        )

        # Extract results
        tau_out = np.array(entry.out_tau_vec, dtype=float)
        gamma_out = np.array(entry.gamma, dtype=float).flatten()

        # Reconstruct fitted impedance from pyDRTtools matrices
        Z_fit_real = np.array(entry.mu_Z_re, dtype=float)
        Z_fit_imag = np.array(entry.mu_Z_im, dtype=float)

        # Un-sort back to original frequency order
        unsort_idx = np.argsort(sort_idx)
        Z_fit_real = Z_fit_real[unsort_idx]
        Z_fit_imag = Z_fit_imag[unsort_idx]

        # Use original (un-sorted) Z for residuals
        residuals_real = np.array(Z_real, dtype=float) - Z_fit_real
        residuals_imag = np.array(Z_imag, dtype=float) - Z_fit_imag
        residuals = np.concatenate([residuals_real, residuals_imag])

        Z_mag = np.sqrt(np.array(Z_real)**2 + np.array(Z_imag)**2)
        Z_mag_safe = np.maximum(Z_mag, 1e-15)
        chi_squared = float(
            np.sum(
                (residuals_real / Z_mag_safe) ** 2
                + (residuals_imag / Z_mag_safe) ** 2
            )
        )

        # Detect peaks on the pyDRTtools output
        peaks = self._detect_peaks(tau_out, gamma_out)

        actual_lambda = float(
            getattr(entry, 'lambda_value', lambda_reg)
        )

        return DRTResult(
            tau=tau_out,
            gamma=gamma_out,
            Z_fit_real=Z_fit_real,
            Z_fit_imag=Z_fit_imag,
            peaks=peaks,
            lambda_reg=actual_lambda,
            chi_squared=chi_squared,
            residuals=residuals,
            method="tikhonov (pyDRTtools)",
            success=True,
        )
    
    def _tikhonov_solve(
        self,
        A: np.ndarray,
        b: np.ndarray,
        lambda_reg: float
    ) -> np.ndarray:
        """
        Solve Tikhonov regularized problem:
            min ||Ax - b||² + λ||Lx||²
        
        where L is the regularization matrix (typically 1st or 2nd derivative).
        
        Solution: x = (A^T A + λL^T L)^(-1) A^T b
        """
        n = A.shape[1]
        
        # Regularization matrix (2nd derivative for smoothness)
        L = self._build_regularization_matrix(n, order=2)
        
        # Normal equations with regularization
        ATA = A.T @ A
        ATb = A.T @ b
        LTL = L.T @ L
        
        # Solve
        x = solve(ATA + lambda_reg * LTL, ATb, assume_a='pos')
        
        return x
    
    def _ridge_solve(
        self,
        A: np.ndarray,
        b: np.ndarray,
        lambda_reg: float
    ) -> np.ndarray:
        """
        Solve ridge regression problem:
            min ||Ax - b||² + λ||x||²
        
        Solution: x = (A^T A + λI)^(-1) A^T b
        """
        n = A.shape[1]
        
        # Normal equations with ridge penalty
        ATA = A.T @ A
        ATb = A.T @ b
        
        # Solve
        x = solve(ATA + lambda_reg * np.eye(n), ATb, assume_a='pos')
        
        return x
    
    def _build_regularization_matrix(self, n: int, order: int = 2) -> np.ndarray:
        """
        Build regularization matrix for derivatives.
        
        Args:
            n: Size of matrix
            order: Derivative order (1 or 2)
        
        Returns:
            Regularization matrix L
        """
        if order == 1:
            # 1st derivative (penalizes slope)
            L = np.zeros((n-1, n))
            for i in range(n-1):
                L[i, i] = -1
                L[i, i+1] = 1
        
        elif order == 2:
            # 2nd derivative (penalizes curvature)
            L = np.zeros((n-2, n))
            for i in range(n-2):
                L[i, i] = 1
                L[i, i+1] = -2
                L[i, i+2] = 1
        
        else:
            raise ValueError(f"Unsupported derivative order: {order}")
        
        return L
    
    def _detect_peaks(
        self,
        tau: np.ndarray,
        gamma: np.ndarray,
        prominence: float = 0.1
    ) -> List[Dict[str, float]]:
        """
        Detect peaks in DRT spectrum and identify processes.
        
        Args:
            tau: Time constants (s)
            gamma: DRT values (Ω)
            prominence: Minimum peak prominence (relative to max)
        
        Returns:
            List of peak dictionaries with tau, gamma, and process type
        """
        # Find peaks
        peak_indices, properties = find_peaks(
            gamma,
            prominence=prominence * np.max(gamma),
            width=2
        )
        
        peaks = []
        for idx in peak_indices:
            tau_peak = tau[idx]
            gamma_peak = gamma[idx]
            
            # Identify process type based on time constant
            process_type = self._identify_process(tau_peak)
            
            peaks.append({
                "tau": float(tau_peak),
                "gamma": float(gamma_peak),
                "frequency_Hz": float(1 / (2 * np.pi * tau_peak)),
                "process": process_type
            })
        
        # Sort by tau
        peaks.sort(key=lambda p: p["tau"])
        
        return peaks
    
    def _identify_process(self, tau: float) -> str:
        """
        Identify electrochemical process based on time constant.
        
        Args:
            tau: Time constant (s)
        
        Returns:
            Process type string
        """
        for process, (tau_min, tau_max) in self.process_types.items():
            if tau_min <= tau <= tau_max:
                return process
        
        return "unknown"
    
    def optimize_lambda(
        self,
        frequencies: np.ndarray,
        Z_real: np.ndarray,
        Z_imag: np.ndarray,
        lambda_range: Tuple[float, float] = (1e-5, 1e-1),
        n_lambda: int = 20
    ) -> Tuple[float, List[float], List[float]]:
        """
        Find optimal regularization parameter using L-curve method.
        
        The L-curve plots ||Ax - b||² vs ||Lx||² for different λ values.
        The optimal λ is at the corner of the L-curve.
        
        The system matrix A depends only on omega and tau (not on λ), so it
        is built once and reused across all λ evaluations for efficiency.
        """
        logger.info("Optimising regularisation parameter using L-curve")
        
        lambda_values = np.logspace(
            np.log10(lambda_range[0]),
            np.log10(lambda_range[1]),
            n_lambda
        )
        
        # Pre-build the system matrix once — it does not depend on λ
        omega = 2 * np.pi * frequencies
        tau_min = 1.0 / omega.max()
        tau_max = 1.0 / omega.min()
        tau = np.logspace(np.log10(tau_min), np.log10(tau_max), 100)
        log_tau = np.log(tau)
        delta_log_tau = np.diff(log_tau)
        delta_log_tau = np.concatenate([[delta_log_tau[0]], delta_log_tau])
        A_complex = delta_log_tau[np.newaxis, :] / (
            1 + 1j * omega[:, np.newaxis] * tau[np.newaxis, :]
        )
        A_real_part = np.real(A_complex)
        A_imag_part = np.imag(A_complex)
        A_full = np.vstack([A_real_part, A_imag_part])
        R_inf = Z_real[-1] if len(Z_real) > 0 else 0.0
        Z_data = np.concatenate([Z_real - R_inf, Z_imag])
        n = A_full.shape[1]
        L = self._build_regularization_matrix(n, order=2)
        LTL = L.T @ L
        ATA = A_full.T @ A_full
        ATb = A_full.T @ Z_data
        
        residual_norms = []
        solution_norms = []
        
        for lam in lambda_values:
            from scipy.linalg import solve
            x = solve(ATA + lam * LTL, ATb, assume_a='pos')
            x = np.maximum(x, 0)
            residuals = Z_data - A_full @ x
            residual_norms.append(float(np.linalg.norm(residuals)))
            solution_norms.append(float(np.linalg.norm(x)))
        
        # Find corner of L-curve (maximum curvature heuristic)
        p1 = np.array([residual_norms[0], solution_norms[0]])
        p2 = np.array([residual_norms[-1], solution_norms[-1]])
        
        max_dist = 0
        optimal_idx = n_lambda // 2
        
        for i in range(1, n_lambda - 1):
            p = np.array([residual_norms[i], solution_norms[i]])
            dist = np.abs(np.cross(p2 - p1, p1 - p)) / (np.linalg.norm(p2 - p1) + 1e-30)
            if dist > max_dist:
                max_dist = dist
                optimal_idx = i
        
        optimal_lambda = float(lambda_values[optimal_idx])
        logger.info(f"Optimal λ = {optimal_lambda:.2e}")
        
        return optimal_lambda, residual_norms, solution_norms


def quick_drt_test():
    """Quick test of DRT analysis."""
    print("🧪 Testing DRT Analysis...")
    print("=" * 60)
    
    # Generate synthetic EIS data (Randles circuit)
    frequencies = np.logspace(-2, 5, 50)
    omega = 2 * np.pi * frequencies
    
    # Parameters
    Rs = 10.0
    Rct = 100.0
    Cdl = 1e-5
    sigma_w = 50.0
    
    # Calculate impedance
    Z_w = sigma_w * (1 - 1j) / np.sqrt(omega)
    Z_c = 1 / (1j * omega * Cdl)
    Z_parallel = 1 / (1/Z_c + 1/(Rct + Z_w))
    Z = Rs + Z_parallel
    
    Z_real = np.real(Z)
    Z_imag = np.imag(Z)
    
    # Add noise
    noise_level = 0.01
    Z_real += np.random.randn(len(Z_real)) * noise_level * np.mean(np.abs(Z_real))
    Z_imag += np.random.randn(len(Z_imag)) * noise_level * np.mean(np.abs(Z_imag))
    
    # Calculate DRT
    analyzer = DRTAnalyzer()
    result = analyzer.calculate_drt(
        frequencies, Z_real, Z_imag,
        lambda_reg=1e-3
    )
    
    print("\n✅ DRT calculation successful!")
    print(f"   Number of peaks: {len(result.peaks)}")
    print(f"   Chi-squared: {result.chi_squared:.6f}")
    print(f"   Lambda: {result.lambda_reg:.2e}")
    
    if result.peaks:
        print("\n   Detected processes:")
        for i, peak in enumerate(result.peaks):
            print(f"   {i+1}. τ = {peak['tau']:.2e} s, "
                  f"f = {peak['frequency_Hz']:.2f} Hz, "
                  f"process = {peak['process']}")
    
    print("\n" + "=" * 60)
    print("✅ DRT test complete!")


if __name__ == "__main__":
    quick_drt_test()
