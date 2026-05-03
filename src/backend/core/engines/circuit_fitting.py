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
        
        # Get circuit function
        if circuit_model not in self.circuit_models:
            raise ValueError(f"Unknown circuit model: {circuit_model}")
        
        circuit_func = self.circuit_models[circuit_model]
        
        # Generate initial guess if not provided
        if initial_guess is None:
            initial_guess = self._generate_initial_guess(
                frequencies, Z_real, Z_imag, circuit_model
            )
        
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
        """
        # High-frequency resistance (Rs)
        Rs = Z_real[-1] if len(Z_real) > 0 else 10.0
        
        # Low-frequency resistance (Rs + Rct)
        R_total = Z_real[0] if len(Z_real) > 0 else 100.0
        Rct = max(R_total - Rs, 1.0)
        
        # Estimate capacitance from peak frequency
        peak_idx = np.argmax(-Z_imag)
        if peak_idx > 0 and peak_idx < len(frequencies):
            f_peak = frequencies[peak_idx]
            omega_peak = 2 * np.pi * f_peak
            # For RC circuit: ω_peak = 1/(RC)
            Cdl = 1 / (omega_peak * Rct) if Rct > 0 else 1e-5
        else:
            Cdl = 1e-5
        
        # Estimate Warburg coefficient
        # From low-frequency slope
        if len(frequencies) > 5:
            low_freq_idx = slice(0, 5)
            slope = np.polyfit(np.sqrt(1/frequencies[low_freq_idx]), Z_real[low_freq_idx], 1)[0]
            sigma_w = abs(slope) if abs(slope) > 0 else 10.0
        else:
            sigma_w = 10.0
        
        # CPE parameters
        Q = Cdl  # Initial guess: Q ≈ Cdl
        n = 0.9  # Typical value
        
        # Generate guess based on circuit model
        if circuit_model == "randles":
            return {
                'Rs': Rs,
                'Rct': Rct,
                'Cdl': Cdl,
                'sigma_w': sigma_w
            }
        elif circuit_model == "randles_cpe":
            return {
                'Rs': Rs,
                'Rct': Rct,
                'Q': Q,
                'n': n,
                'sigma_w': sigma_w
            }
        elif circuit_model == "rc":
            return {
                'R': Rs,
                'C': Cdl
            }
        elif circuit_model == "r_cpe":
            return {
                'R': Rs,
                'Q': Q,
                'n': n
            }
        else:
            return {}
    
    def _generate_bounds(
        self,
        circuit_model: str,
        initial_guess: Dict[str, float]
    ) -> Dict[str, Tuple[float, float]]:
        """
        Generate parameter bounds.
        
        Uses reasonable physical bounds based on typical values.
        """
        bounds = {}
        
        for param, value in initial_guess.items():
            if param in ['Rs', 'Rct', 'R']:
                # Resistance: 0.1 Ω to 1 MΩ
                bounds[param] = (0.1, 1e6)
            elif param in ['Cdl', 'C']:
                # Capacitance: 1 nF to 1 F
                bounds[param] = (1e-9, 1.0)
            elif param == 'Q':
                # CPE parameter: 1 nF to 1 F
                bounds[param] = (1e-9, 1.0)
            elif param == 'n':
                # CPE exponent: 0.5 to 1.0
                bounds[param] = (0.5, 1.0)
            elif param == 'sigma_w':
                # Warburg coefficient: 0.1 to 10000
                bounds[param] = (0.1, 10000.0)
            else:
                # Default: ±10x initial value
                bounds[param] = (value * 0.1, value * 10.0)
        
        return bounds
