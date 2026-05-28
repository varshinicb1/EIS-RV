"""
Equivalent Circuit Fitting Module
==================================
Fit equivalent circuit models to experimental EIS data using
Complex Nonlinear Least Squares (CNLS).

Supported Circuits:
- Randles circuit (Rs + (Cdl || (Rct + W)))
- Modified Randles with CPE
- Custom circuits

Author: VidyuthLabs
Date: May 1, 2026
"""

import numpy as np
from scipy.optimize import least_squares, differential_evolution
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional impedance.py backend for circuit fitting
# ---------------------------------------------------------------------------
try:
    from impedance.models.circuits import CustomCircuit
    HAS_IMPEDANCEPY = True
    logger.debug("impedance.py is available – CustomCircuit backend enabled")
except ImportError:
    HAS_IMPEDANCEPY = False
    logger.debug("impedance.py not found – falling back to built-in scipy backend")

# Mapping from RĀMAN Studio model names to impedance.py circuit strings.
# impedance.py uses 'p(X,Y)' for parallel elements, '-' for series,
# 'R0' for resistor, 'C1' for capacitor, 'CPE1' for CPE, 'W1' for Warburg.
IMPEDANCEPY_CIRCUIT_MAP: Dict[str, str] = {
    'randles': 'R0-p(R1,C1)-W1',
    'randles_cpe': 'R0-p(R1,CPE1)-W1',
    'rc': 'R0-C1',
    'r_cpe': 'R0-CPE1',
}

# Maps our parameter-dict keys to the ordering expected by impedance.py
# for each circuit string in IMPEDANCEPY_CIRCUIT_MAP.
_PARAM_ORDER: Dict[str, list] = {
    'randles': ['Rs', 'Rct', 'Cdl', 'sigma_w'],
    'randles_cpe': ['Rs', 'Rct', 'Q', 'n', 'sigma_w'],
    'rc': ['R', 'C'],
    'r_cpe': ['R', 'Q', 'n'],
}


@dataclass
class FitResult:
    """Result from circuit fitting."""
    # Fitted parameters
    parameters: Dict[str, float]
    parameter_errors: Dict[str, float]
    
    # Fitted impedance
    Z_fit_real: np.ndarray
    Z_fit_imag: np.ndarray
    
    # Goodness of fit
    chi_squared: float
    reduced_chi_squared: float
    residuals: np.ndarray
    
    # Metadata
    circuit_model: str
    n_iterations: int
    success: bool
    message: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "parameters": self.parameters,
            "parameter_errors": self.parameter_errors,
            "Z_fit_real": self.Z_fit_real.tolist(),
            "Z_fit_imag": self.Z_fit_imag.tolist(),
            "chi_squared": float(self.chi_squared),
            "reduced_chi_squared": float(self.reduced_chi_squared),
            "circuit_model": self.circuit_model,
            "n_iterations": self.n_iterations,
            "success": self.success,
            "message": self.message
        }


class CircuitFitter:
    """
    Fit equivalent circuit models to EIS data using CNLS.
    
    Uses Complex Nonlinear Least Squares (CNLS) with:
    - Levenberg-Marquardt algorithm
    - Differential evolution for global optimization
    - Automatic initial guess generation
    - Parameter bounds
    """
    
    def __init__(self):
        """Initialize circuit fitter."""
        self.circuit_models = {
            "randles": self._randles_circuit,
            "randles_cpe": self._randles_cpe_circuit,
            "rc": self._rc_circuit,
            "r_cpe": self._r_cpe_circuit
        }
    
    def fit_circuit(
        self,
        frequencies: np.ndarray,
        Z_real: np.ndarray,
        Z_imag: np.ndarray,
        circuit_model: str = "randles_cpe",
        initial_guess: Optional[Dict[str, float]] = None,
        bounds: Optional[Dict[str, Tuple[float, float]]] = None,
        method: str = "lm"  # "lm" or "de" (differential evolution)
    ) -> FitResult:
        """
        Fit equivalent circuit to EIS data.

        When impedance.py is installed and the requested *circuit_model* has an
        entry in :data:`IMPEDANCEPY_CIRCUIT_MAP`, the fit is delegated to
        ``impedance.models.circuits.CustomCircuit.fit()`` which uses
        ``scipy.optimize.curve_fit`` internally with EIS-aware default bounds
        (e.g. CPE exponent capped at 1).

        If impedance.py is **not** installed, or the circuit model has no
        mapping, the method transparently falls back to the built-in scipy
        least-squares / differential-evolution backend — every existing code
        path is preserved.

        Args:
            frequencies: Frequency array (Hz)
            Z_real: Real impedance (Ω)
            Z_imag: Imaginary impedance (Ω)
            circuit_model: Circuit model name
            initial_guess: Initial parameter guess
            bounds: Parameter bounds
            method: Optimization method ("lm" or "de")

        Returns:
            FitResult object
        """
        logger.info(f"Fitting {circuit_model} circuit using {method} method")

        # Validate circuit model
        if circuit_model not in self.circuit_models:
            raise ValueError(f"Unknown circuit model: {circuit_model}")

        # Generate initial guess if not provided (needed for both backends)
        if initial_guess is None:
            initial_guess = self._generate_initial_guess(
                frequencies, Z_real, Z_imag, circuit_model
            )

        # ------------------------------------------------------------------
        # PATH A – impedance.py backend (preferred when available)
        # ------------------------------------------------------------------
        if (
            HAS_IMPEDANCEPY
            and circuit_model in IMPEDANCEPY_CIRCUIT_MAP
            and circuit_model in _PARAM_ORDER
        ):
            try:
                return self._fit_with_impedancepy(
                    frequencies, Z_real, Z_imag,
                    circuit_model, initial_guess,
                )
            except Exception as exc:
                # If the impedance.py path fails for any reason, fall through
                # to the scipy backend so the user still gets a result.
                logger.warning(
                    "impedance.py backend failed (%s), falling back to scipy",
                    exc,
                )

        # ------------------------------------------------------------------
        # PATH B – built-in scipy backend (original code, used as fallback)
        # ------------------------------------------------------------------
        logger.info("Using built-in scipy backend for circuit fitting")

        circuit_func = self.circuit_models[circuit_model]

        # Generate bounds if not provided
        if bounds is None:
            bounds = self._generate_bounds(circuit_model, initial_guess)

        # Convert to arrays for optimization
        param_names = list(initial_guess.keys())
        x0 = np.array([initial_guess[p] for p in param_names])
        lower_bounds = np.array([bounds[p][0] for p in param_names])
        upper_bounds = np.array([bounds[p][1] for p in param_names])

        # Define residual function for CNLS
        def residual_func(params):
            # Calculate model impedance
            param_dict = {name: val for name, val in zip(param_names, params)}
            Z_model = circuit_func(frequencies, param_dict)

            # Complex residuals (real and imaginary parts)
            residuals_real = Z_real - np.real(Z_model)
            residuals_imag = Z_imag - np.imag(Z_model)

            # Combine residuals
            return np.concatenate([residuals_real, residuals_imag])

        # Optimize
        if method == "lm":
            # Levenberg-Marquardt
            result = least_squares(
                residual_func,
                x0,
                bounds=(lower_bounds, upper_bounds),
                method='trf',  # Trust Region Reflective
                max_nfev=10000
            )

            fitted_params = result.x
            n_iterations = result.nfev
            success = result.success
            message = result.message

        elif method == "de":
            # Differential Evolution (global optimization)
            result = differential_evolution(
                lambda params: np.sum(residual_func(params)**2),
                bounds=list(zip(lower_bounds, upper_bounds)),
                maxiter=1000,
                seed=42
            )

            fitted_params = result.x
            n_iterations = result.nit
            success = result.success
            message = result.message

        else:
            raise ValueError(f"Unknown method: {method}")

        # Calculate fitted impedance
        param_dict = {name: val for name, val in zip(param_names, fitted_params)}
        Z_fit = circuit_func(frequencies, param_dict)
        Z_fit_real = np.real(Z_fit)
        Z_fit_imag = np.imag(Z_fit)

        # Calculate goodness of fit
        residuals = residual_func(fitted_params)
        chi_squared = np.sum(residuals**2)
        n_data = len(frequencies) * 2  # Real + imaginary
        n_params = len(fitted_params)
        reduced_chi_squared = chi_squared / (n_data - n_params)

        # Estimate parameter errors (from Jacobian)
        try:
            # Calculate Jacobian
            jac = result.jac if hasattr(result, 'jac') else None
            if jac is not None:
                # Covariance matrix
                cov = np.linalg.inv(jac.T @ jac) * reduced_chi_squared
                param_errors = {name: np.sqrt(cov[i, i]) for i, name in enumerate(param_names)}
            else:
                param_errors = {name: 0.0 for name in param_names}
        except:
            param_errors = {name: 0.0 for name in param_names}

        return FitResult(
            parameters=param_dict,
            parameter_errors=param_errors,
            Z_fit_real=Z_fit_real,
            Z_fit_imag=Z_fit_imag,
            chi_squared=chi_squared,
            reduced_chi_squared=reduced_chi_squared,
            residuals=residuals,
            circuit_model=circuit_model,
            n_iterations=n_iterations,
            success=success,
            message=message
        )

    # ------------------------------------------------------------------
    # impedance.py integration helpers
    # ------------------------------------------------------------------

    def _fit_with_impedancepy(
        self,
        frequencies: np.ndarray,
        Z_real: np.ndarray,
        Z_imag: np.ndarray,
        circuit_model: str,
        initial_guess: Dict[str, float],
    ) -> FitResult:
        """
        Delegate fitting to impedance.py's ``CustomCircuit``.

        This internal helper is called by :meth:`fit_circuit` when
        ``HAS_IMPEDANCEPY`` is True and the circuit has a known mapping.

        impedance.py API recap (from ``circuits.py`` & ``fitting.py``):
          * ``CustomCircuit(circuit=..., initial_guess=[...])``
          * ``.fit(frequencies, Z_complex)`` — mutates the object in-place,
            stores ``parameters_`` (np.ndarray) and ``conf_`` (np.ndarray)
          * ``.predict(frequencies)`` — returns complex Z_fit
          * ``.get_param_names()`` — returns (name_list, unit_list)

        Returns:
            FitResult with parameters, errors, fitted impedance, etc.
        """
        logger.info("Using impedance.py backend for circuit fitting")

        circuit_string = IMPEDANCEPY_CIRCUIT_MAP[circuit_model]
        param_order = _PARAM_ORDER[circuit_model]

        # Build the initial-guess list in the element order expected by
        # impedance.py (same order as elements appear in the circuit string).
        ig_list = [float(initial_guess[p]) for p in param_order]

        # Construct CustomCircuit — constructor validates ig length vs circuit
        circ = CustomCircuit(
            circuit=circuit_string,
            initial_guess=ig_list,
        )

        # impedance.py expects complex impedance as a 1-D ndarray of complex128
        Z_complex = np.array(Z_real + 1j * Z_imag, dtype=complex)
        freq_arr = np.array(frequencies, dtype=float)

        # Fit (calls scipy.optimize.curve_fit under the hood)
        circ.fit(freq_arr, Z_complex)

        # Extract fitted parameter values & confidence intervals
        fitted_values = circ.parameters_  # np.ndarray
        conf_intervals = circ.conf_       # np.ndarray (1-σ)

        # Map back to our named-parameter dicts using get_param_names()
        imp_names, _ = circ.get_param_names()
        param_dict: Dict[str, float] = {}
        param_errors: Dict[str, float] = {}

        # impedance.py names like 'R0', 'R1', 'C1', 'CPE1_0', 'CPE1_1', 'W1'
        # We map them back to our canonical names.
        # Build a positional map: our param_order[i] ↔ imp_names[i]
        for i, our_name in enumerate(param_order):
            imp_name = imp_names[i] if i < len(imp_names) else f"p{i}"
            param_dict[our_name] = float(fitted_values[i])
            if conf_intervals is not None and i < len(conf_intervals):
                param_errors[our_name] = float(conf_intervals[i])
            else:
                param_errors[our_name] = 0.0

        # Predict fitted impedance
        Z_fit = circ.predict(freq_arr)
        Z_fit_real = np.real(Z_fit)
        Z_fit_imag = np.imag(Z_fit)

        # Compute residuals & chi-squared
        residuals_real = Z_real - Z_fit_real
        residuals_imag = Z_imag - Z_fit_imag
        residuals = np.concatenate([residuals_real, residuals_imag])
        chi_squared = float(np.sum(residuals ** 2))
        n_data = len(frequencies) * 2
        n_params = len(fitted_values)
        reduced_chi_squared = chi_squared / max(n_data - n_params, 1)

        return FitResult(
            parameters=param_dict,
            parameter_errors=param_errors,
            Z_fit_real=Z_fit_real,
            Z_fit_imag=Z_fit_imag,
            chi_squared=chi_squared,
            reduced_chi_squared=reduced_chi_squared,
            residuals=residuals,
            circuit_model=circuit_model,
            n_iterations=-1,  # impedance.py does not expose iteration count
            success=True,
            message="Fitted using impedance.py CustomCircuit backend",
        )

    def fit_custom_circuit(
        self,
        frequencies: np.ndarray,
        Z_real: np.ndarray,
        Z_imag: np.ndarray,
        circuit_string: str,
        initial_guess: Optional[list] = None,
        constants: Optional[Dict[str, float]] = None,
    ) -> FitResult:
        """
        Fit a user-defined circuit specified as a raw impedance.py string.

        This method **requires** impedance.py to be installed.  It exposes
        the full power of impedance.py's element library (R, C, L, W, Wo, Ws,
        CPE, La, G, Gs, TLMQ, T, K, Zarc) and arbitrary series/parallel
        topologies.

        Args:
            frequencies: Frequency array (Hz).
            Z_real: Real part of measured impedance (Ω).
            Z_imag: Imaginary part of measured impedance (Ω).
            circuit_string: impedance.py circuit descriptor, e.g.
                ``'R0-p(R1-Wo1,CPE1)'``.
            initial_guess: Flat list of initial parameter values in the
                order they appear in the circuit string.  If *None*,
                impedance.py will require one anyway and raise.
            constants: Dict of parameters to hold fixed during fitting,
                e.g. ``{"R0": 0.1}``.

        Returns:
            FitResult with fitted parameters keyed by impedance.py names
            (e.g. ``'R0'``, ``'CPE1_0'``, ``'CPE1_1'``).

        Raises:
            RuntimeError: If impedance.py is not installed.
            ValueError: If *initial_guess* is not provided or has wrong length.
        """
        if not HAS_IMPEDANCEPY:
            raise RuntimeError(
                "impedance.py is required for fit_custom_circuit() but is not "
                "installed. Install it with: pip install impedance"
            )

        logger.info(
            "Fitting custom circuit '%s' using impedance.py backend",
            circuit_string,
        )

        if initial_guess is None:
            raise ValueError(
                "initial_guess is required for custom circuit fitting"
            )

        circ = CustomCircuit(
            circuit=circuit_string,
            initial_guess=list(initial_guess),
            constants=constants or {},
        )

        Z_complex = np.array(Z_real + 1j * Z_imag, dtype=complex)
        freq_arr = np.array(frequencies, dtype=float)

        circ.fit(freq_arr, Z_complex)

        # Extract results
        imp_names, _ = circ.get_param_names()
        fitted_values = circ.parameters_
        conf_intervals = circ.conf_

        param_dict = {
            name: float(fitted_values[i])
            for i, name in enumerate(imp_names)
        }
        param_errors = {
            name: float(conf_intervals[i])
            if conf_intervals is not None and i < len(conf_intervals)
            else 0.0
            for i, name in enumerate(imp_names)
        }

        Z_fit = circ.predict(freq_arr)
        Z_fit_real = np.real(Z_fit)
        Z_fit_imag = np.imag(Z_fit)

        residuals_real = Z_real - Z_fit_real
        residuals_imag = Z_imag - Z_fit_imag
        residuals = np.concatenate([residuals_real, residuals_imag])
        chi_squared = float(np.sum(residuals ** 2))
        n_data = len(frequencies) * 2
        n_params = len(fitted_values)
        reduced_chi_squared = chi_squared / max(n_data - n_params, 1)

        return FitResult(
            parameters=param_dict,
            parameter_errors=param_errors,
            Z_fit_real=Z_fit_real,
            Z_fit_imag=Z_fit_imag,
            chi_squared=chi_squared,
            reduced_chi_squared=reduced_chi_squared,
            residuals=residuals,
            circuit_model=f"custom({circuit_string})",
            n_iterations=-1,
            success=True,
            message="Fitted using impedance.py CustomCircuit (custom string)",
        )
    
    # Circuit models
    
    def _randles_circuit(self, freq: np.ndarray, params: Dict[str, float]) -> np.ndarray:
        """
        Randles circuit: Rs + (Cdl || (Rct + W))
        
        Parameters:
            Rs: Solution resistance (Ω)
            Rct: Charge transfer resistance (Ω)
            Cdl: Double layer capacitance (F)
            sigma_w: Warburg coefficient (Ω·s^(-1/2))
        """
        Rs = params['Rs']
        Rct = params['Rct']
        Cdl = params['Cdl']
        sigma_w = params['sigma_w']
        
        omega = 2 * np.pi * freq
        
        # Warburg impedance
        Z_w = sigma_w * (1 - 1j) / np.sqrt(omega)
        
        # Capacitor impedance
        Z_c = 1 / (1j * omega * Cdl)
        
        # Parallel combination: Cdl || (Rct + W)
        Z_parallel = 1 / (1/Z_c + 1/(Rct + Z_w))
        
        # Total impedance
        Z_total = Rs + Z_parallel
        
        return Z_total
    
    def _randles_cpe_circuit(self, freq: np.ndarray, params: Dict[str, float]) -> np.ndarray:
        """
        Modified Randles circuit with CPE: Rs + (CPE || (Rct + W))
        
        Parameters:
            Rs: Solution resistance (Ω)
            Rct: Charge transfer resistance (Ω)
            Q: CPE parameter (F·s^(n-1))
            n: CPE exponent (0-1)
            sigma_w: Warburg coefficient (Ω·s^(-1/2))
        """
        Rs = params['Rs']
        Rct = params['Rct']
        Q = params['Q']
        n = params['n']
        sigma_w = params['sigma_w']
        
        omega = 2 * np.pi * freq
        
        # CPE impedance
        Z_cpe = 1 / (Q * (1j * omega)**n)
        
        # Warburg impedance
        Z_w = sigma_w * (1 - 1j) / np.sqrt(omega)
        
        # Parallel combination: CPE || (Rct + W)
        Z_parallel = 1 / (1/Z_cpe + 1/(Rct + Z_w))
        
        # Total impedance
        Z_total = Rs + Z_parallel
        
        return Z_total
    
    def _rc_circuit(self, freq: np.ndarray, params: Dict[str, float]) -> np.ndarray:
        """
        Simple RC circuit: R + (1/jωC)
        
        Parameters:
            R: Resistance (Ω)
            C: Capacitance (F)
        """
        R = params['R']
        C = params['C']
        
        omega = 2 * np.pi * freq
        Z_c = 1 / (1j * omega * C)
        
        return R + Z_c
    
    def _r_cpe_circuit(self, freq: np.ndarray, params: Dict[str, float]) -> np.ndarray:
        """
        R-CPE circuit: R + CPE
        
        Parameters:
            R: Resistance (Ω)
            Q: CPE parameter (F·s^(n-1))
            n: CPE exponent (0-1)
        """
        R = params['R']
        Q = params['Q']
        n = params['n']
        
        omega = 2 * np.pi * freq
        Z_cpe = 1 / (Q * (1j * omega)**n)
        
        return R + Z_cpe
    
    # Helper methods
    
    def _generate_initial_guess(
        self,
        frequencies: np.ndarray,
        Z_real: np.ndarray,
        Z_imag: np.ndarray,
        circuit_model: str
    ) -> Dict[str, float]:
        """
        Generate initial parameter guess from data.

        Uses heuristics based on impedance spectrum shape.
        Frequency-order-agnostic: works whether data is sorted
        high-to-low (CHI608E default) or low-to-high.
        """
        # High-frequency Rs = Z_real at the highest measured frequency
        hf_idx = int(np.argmax(frequencies))
        lf_idx = int(np.argmin(frequencies))

        Rs = float(Z_real[hf_idx])
        Rs = max(Rs, 0.1)

        # Low-frequency total resistance = Rs + Rct
        R_total = float(Z_real[lf_idx])
        Rct = max(R_total - Rs, 1.0)

        # Estimate capacitance from the peak of -Z_imag (semicircle top)
        peak_idx = int(np.argmax(-Z_imag))
        if 0 < peak_idx < len(frequencies):
            f_peak = float(frequencies[peak_idx])
            omega_peak = 2 * np.pi * f_peak
            # For RC: ω_peak = 1/(Rct*C)  →  C = 1/(ω_peak * Rct)
            Cdl = 1.0 / (omega_peak * Rct) if Rct > 0 else 1e-5
        else:
            Cdl = 1e-5
        Cdl = float(np.clip(Cdl, 1e-9, 1.0))

        # Warburg coefficient from low-frequency Warburg region.
        # Z_real ≈ Rs + Rct + σ/√ω  →  slope of Z_real vs 1/√(2πf) = σ
        # Use the 5 lowest-frequency points (sorted ascending by freq).
        sort_idx = np.argsort(frequencies)
        f_lf = frequencies[sort_idx[:5]]
        Zr_lf = Z_real[sort_idx[:5]]
        if len(f_lf) >= 2:
            x_w = 1.0 / np.sqrt(2 * np.pi * f_lf)
            slope = float(np.polyfit(x_w, Zr_lf, 1)[0])
            sigma_w = max(abs(slope), 0.1)
        else:
            sigma_w = 10.0
        sigma_w = float(np.clip(sigma_w, 0.1, 10000.0))

        Q = Cdl
        n = 0.9

        if circuit_model == "randles":
            return {'Rs': Rs, 'Rct': Rct, 'Cdl': Cdl, 'sigma_w': sigma_w}
        elif circuit_model == "randles_cpe":
            return {'Rs': Rs, 'Rct': Rct, 'Q': Q, 'n': n, 'sigma_w': sigma_w}
        elif circuit_model == "rc":
            return {'R': Rs, 'C': Cdl}
        elif circuit_model == "r_cpe":
            return {'R': Rs, 'Q': Q, 'n': n}
        else:
            return {}
    
    def _generate_bounds(
        self,
        circuit_model: str,
        initial_guess: Dict[str, float]
    ) -> Dict[str, Tuple[float, float]]:
        """
        Generate parameter bounds that are data-adaptive.

        Each bound is set to [guess/1000, guess*1000] (6 decades of range)
        with hard physical limits. This prevents the optimizer from hitting
        the bounds on high-Rct samples (e.g., bare GCE with Rct > 100 kΩ).
        """
        bounds = {}

        for param, value in initial_guess.items():
            if param in ('Rs', 'Rct', 'R'):
                # Resistance: 0.01 Ω to 100 MΩ, centred on guess
                lo = max(0.01, value * 1e-3)
                hi = min(1e8, value * 1e3)
                bounds[param] = (lo, hi)
            elif param in ('Cdl', 'C', 'Q'):
                # Capacitance / CPE: 1 pF to 10 F
                lo = max(1e-12, value * 1e-3)
                hi = min(10.0, value * 1e3)
                bounds[param] = (lo, hi)
            elif param == 'n':
                bounds[param] = (0.3, 1.0)
            elif param == 'sigma_w':
                lo = max(0.01, value * 1e-3)
                hi = min(1e6, value * 1e3)
                bounds[param] = (lo, hi)
            else:
                lo = value * 0.01 if value > 0 else -abs(value) * 100
                hi = value * 100 if value > 0 else abs(value) * 0.01
                bounds[param] = (min(lo, hi), max(lo, hi))

        return bounds
