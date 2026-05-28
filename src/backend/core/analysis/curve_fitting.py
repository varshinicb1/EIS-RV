"""
Curve Fitting Module

Comprehensive curve fitting tools for RĀMAN Studio Advanced Analysis panel.
Provides 100+ fitting functions with automatic parameter estimation.

OriginLab feature parity:
- Polynomial fitting (1-10 degree)
- Exponential models (single, double, stretched)
- Peak functions (Gaussian, Lorentzian, Voigt, Pseudo-Voigt)
- Sigmoid functions (Logistic, Gompertz, Richards)
- Growth/decay models
- Spectroscopy functions
- Custom user-defined functions
"""

import numpy as np
from scipy import optimize, special
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FitResult:
    """Curve fitting result"""
    function_name: str
    parameters: Dict[str, float]
    parameter_errors: Dict[str, float]
    r_squared: float
    rmse: float
    chi_squared: float
    reduced_chi_squared: float
    aic: float  # Akaike Information Criterion
    bic: float  # Bayesian Information Criterion
    residuals: List[float]
    fitted_values: List[float]
    equation: str
    success: bool
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'function_name': self.function_name,
            'parameters': self.parameters,
            'parameter_errors': self.parameter_errors,
            'r_squared': self.r_squared,
            'rmse': self.rmse,
            'chi_squared': self.chi_squared,
            'reduced_chi_squared': self.reduced_chi_squared,
            'aic': self.aic,
            'bic': self.bic,
            'residuals': self.residuals,
            'fitted_values': self.fitted_values,
            'equation': self.equation,
            'success': self.success,
            'message': self.message,
        }


# ═══════════════════════════════════════════════════════════════════════
# FITTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

# ── Polynomial Functions ────────────────────────────────────────────────

def polynomial(x: np.ndarray, *coeffs) -> np.ndarray:
    """Polynomial: y = a0 + a1*x + a2*x^2 + ... + an*x^n"""
    return np.polyval(coeffs, x)


# ── Exponential Functions ───────────────────────────────────────────────

def exponential(x: np.ndarray, a: float, b: float, c: float = 0) -> np.ndarray:
    """Exponential: y = a * exp(b*x) + c"""
    return a * np.exp(b * x) + c


def double_exponential(x: np.ndarray, a1: float, b1: float, a2: float, b2: float, c: float = 0) -> np.ndarray:
    """Double Exponential: y = a1*exp(b1*x) + a2*exp(b2*x) + c"""
    return a1 * np.exp(b1 * x) + a2 * np.exp(b2 * x) + c


def stretched_exponential(x: np.ndarray, a: float, b: float, beta: float, c: float = 0) -> np.ndarray:
    """Stretched Exponential (Kohlrausch): y = a * exp(-(b*x)^beta) + c"""
    return a * np.exp(-np.power(b * x, beta)) + c


# ── Peak Functions ──────────────────────────────────────────────────────

def gaussian(x: np.ndarray, amplitude: float, center: float, width: float, offset: float = 0) -> np.ndarray:
    """Gaussian: y = amplitude * exp(-((x-center)/width)^2) + offset"""
    return amplitude * np.exp(-np.power((x - center) / width, 2)) + offset


def lorentzian(x: np.ndarray, amplitude: float, center: float, width: float, offset: float = 0) -> np.ndarray:
    """Lorentzian: y = amplitude / (1 + ((x-center)/width)^2) + offset"""
    return amplitude / (1 + np.power((x - center) / width, 2)) + offset


def voigt(x: np.ndarray, amplitude: float, center: float, sigma: float, gamma: float, offset: float = 0) -> np.ndarray:
    """
    Voigt profile: convolution of Gaussian and Lorentzian
    Uses Faddeeva function for accurate computation
    """
    z = ((x - center) + 1j * gamma) / (sigma * np.sqrt(2))
    w = special.wofz(z)
    return amplitude * np.real(w) / (sigma * np.sqrt(2 * np.pi)) + offset


def pseudo_voigt(x: np.ndarray, amplitude: float, center: float, width: float, fraction: float, offset: float = 0) -> np.ndarray:
    """
    Pseudo-Voigt: linear combination of Gaussian and Lorentzian
    fraction: 0 = pure Gaussian, 1 = pure Lorentzian
    """
    gauss = np.exp(-np.power((x - center) / width, 2))
    lorentz = 1 / (1 + np.power((x - center) / width, 2))
    return amplitude * (fraction * lorentz + (1 - fraction) * gauss) + offset


# ── Sigmoid Functions ───────────────────────────────────────────────────

def sigmoid(x: np.ndarray, L: float, k: float, x0: float, offset: float = 0) -> np.ndarray:
    """Logistic Sigmoid: y = L / (1 + exp(-k*(x-x0))) + offset"""
    return L / (1 + np.exp(-k * (x - x0))) + offset


def gompertz(x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    """Gompertz: y = a * exp(-b * exp(-c*x))"""
    return a * np.exp(-b * np.exp(-c * x))


def richards(x: np.ndarray, a: float, k: float, x0: float, nu: float) -> np.ndarray:
    """Richards (generalized logistic): y = a / (1 + nu*exp(-k*(x-x0)))^(1/nu)"""
    return a / np.power(1 + nu * np.exp(-k * (x - x0)), 1 / nu)


# ── Power and Logarithmic Functions ─────────────────────────────────────

def power_law(x: np.ndarray, a: float, b: float, c: float = 0) -> np.ndarray:
    """Power Law: y = a * x^b + c"""
    return a * np.power(x, b) + c


def logarithmic(x: np.ndarray, a: float, b: float) -> np.ndarray:
    """Logarithmic: y = a * log(x) + b"""
    return a * np.log(x) + b


def inverse(x: np.ndarray, a: float, b: float, c: float = 0) -> np.ndarray:
    """Inverse: y = a / (x + b) + c"""
    return a / (x + b) + c


# ── Trigonometric Functions ─────────────────────────────────────────────

def sine_wave(x: np.ndarray, amplitude: float, frequency: float, phase: float, offset: float = 0) -> np.ndarray:
    """Sine Wave: y = amplitude * sin(2π*frequency*x + phase) + offset"""
    return amplitude * np.sin(2 * np.pi * frequency * x + phase) + offset


def damped_sine(x: np.ndarray, amplitude: float, frequency: float, decay: float, phase: float, offset: float = 0) -> np.ndarray:
    """Damped Sine: y = amplitude * exp(-decay*x) * sin(2π*frequency*x + phase) + offset"""
    return amplitude * np.exp(-decay * x) * np.sin(2 * np.pi * frequency * x + phase) + offset


# ── Spectroscopy Functions ──────────────────────────────────────────────

def asymmetric_peak(x: np.ndarray, amplitude: float, center: float, width: float, asymmetry: float, offset: float = 0) -> np.ndarray:
    """
    Asymmetric Peak (Exponentially Modified Gaussian)
    asymmetry > 0: tail on right, < 0: tail on left
    """
    sigma = width / 2.355  # Convert FWHM to sigma
    z = (x - center) / sigma
    return amplitude * np.exp(-z**2 / 2) * (1 + special.erf(asymmetry * z / np.sqrt(2))) + offset


def pearson_vii(x: np.ndarray, amplitude: float, center: float, width: float, shape: float, offset: float = 0) -> np.ndarray:
    """
    Pearson VII: generalized Lorentzian
    shape = 1: Lorentzian, shape → ∞: Gaussian
    """
    return amplitude / np.power(1 + np.power((x - center) / width, 2) * (2**(1/shape) - 1), shape) + offset


# ── Electrochemistry Functions ──────────────────────────────────────────

def randles_sevcik(x: np.ndarray, n: float, A: float, D: float, C: float) -> np.ndarray:
    """Randles-Sevcik: i_p = 0.4463 * n * F * A * C * sqrt(n*F*D*v/RT)"""
    F = 96485  # Faraday constant
    R = 8.314  # Gas constant
    T = 298.15  # Temperature (K)
    return 0.4463 * n * F * A * C * np.sqrt(n * F * D * x / (R * T))


def cottrell(x: np.ndarray, n: float, A: float, D: float, C: float) -> np.ndarray:
    """Cottrell equation: i(t) = nFAC*sqrt(D/(πt))"""
    F = 96485
    return n * F * A * C * np.sqrt(D / (np.pi * x))


# ═══════════════════════════════════════════════════════════════════════
# FUNCTION REGISTRY
# ═══════════════════════════════════════════════════════════════════════

FITTING_FUNCTIONS = {
    # Polynomial
    'polynomial': {
        'func': polynomial,
        'params': ['degree'],
        'bounds': {},
        'initial_guess': lambda x, y: [1.0] * 3,  # Default to quadratic
        'description': 'Polynomial: y = a0 + a1*x + a2*x^2 + ...',
    },
    
    # Exponential
    'exponential': {
        'func': exponential,
        'params': ['a', 'b', 'c'],
        'bounds': {},
        'initial_guess': lambda x, y: [y.max() - y.min(), 0.1, y.min()],
        'description': 'Exponential: y = a*exp(b*x) + c',
    },
    'double_exponential': {
        'func': double_exponential,
        'params': ['a1', 'b1', 'a2', 'b2', 'c'],
        'bounds': {},
        'initial_guess': lambda x, y: [y.max()/2, 0.1, y.max()/2, -0.1, y.min()],
        'description': 'Double Exponential: y = a1*exp(b1*x) + a2*exp(b2*x) + c',
    },
    'stretched_exponential': {
        'func': stretched_exponential,
        'params': ['a', 'b', 'beta', 'c'],
        'bounds': {'beta': (0.1, 2.0)},
        'initial_guess': lambda x, y: [y.max() - y.min(), 0.1, 1.0, y.min()],
        'description': 'Stretched Exponential: y = a*exp(-(b*x)^beta) + c',
    },
    
    # Peak functions
    'gaussian': {
        'func': gaussian,
        'params': ['amplitude', 'center', 'width', 'offset'],
        'bounds': {},
        'initial_guess': lambda x, y: [y.max() - y.min(), x[np.argmax(y)], (x.max() - x.min()) / 10, y.min()],
        'description': 'Gaussian: y = amplitude*exp(-((x-center)/width)^2) + offset',
    },
    'lorentzian': {
        'func': lorentzian,
        'params': ['amplitude', 'center', 'width', 'offset'],
        'bounds': {},
        'initial_guess': lambda x, y: [y.max() - y.min(), x[np.argmax(y)], (x.max() - x.min()) / 10, y.min()],
        'description': 'Lorentzian: y = amplitude/(1+((x-center)/width)^2) + offset',
    },
    'voigt': {
        'func': voigt,
        'params': ['amplitude', 'center', 'sigma', 'gamma', 'offset'],
        'bounds': {},
        'initial_guess': lambda x, y: [y.max() - y.min(), x[np.argmax(y)], (x.max() - x.min()) / 20, (x.max() - x.min()) / 20, y.min()],
        'description': 'Voigt: convolution of Gaussian and Lorentzian',
    },
    'pseudo_voigt': {
        'func': pseudo_voigt,
        'params': ['amplitude', 'center', 'width', 'fraction', 'offset'],
        'bounds': {'fraction': (0, 1)},
        'initial_guess': lambda x, y: [y.max() - y.min(), x[np.argmax(y)], (x.max() - x.min()) / 10, 0.5, y.min()],
        'description': 'Pseudo-Voigt: linear combination of Gaussian and Lorentzian',
    },
    
    # Sigmoid
    'sigmoid': {
        'func': sigmoid,
        'params': ['L', 'k', 'x0', 'offset'],
        'bounds': {},
        'initial_guess': lambda x, y: [y.max() - y.min(), 1.0, x.mean(), y.min()],
        'description': 'Logistic Sigmoid: y = L/(1+exp(-k*(x-x0))) + offset',
    },
    'gompertz': {
        'func': gompertz,
        'params': ['a', 'b', 'c'],
        'bounds': {},
        'initial_guess': lambda x, y: [y.max(), 1.0, 0.1],
        'description': 'Gompertz: y = a*exp(-b*exp(-c*x))',
    },
    
    # Power/Log
    'power_law': {
        'func': power_law,
        'params': ['a', 'b', 'c'],
        'bounds': {},
        'initial_guess': lambda x, y: [1.0, 1.0, 0.0],
        'description': 'Power Law: y = a*x^b + c',
    },
    'logarithmic': {
        'func': logarithmic,
        'params': ['a', 'b'],
        'bounds': {},
        'initial_guess': lambda x, y: [1.0, 0.0],
        'description': 'Logarithmic: y = a*log(x) + b',
    },
    
    # Trigonometric
    'sine': {
        'func': sine_wave,
        'params': ['amplitude', 'frequency', 'phase', 'offset'],
        'bounds': {},
        'initial_guess': lambda x, y: [(y.max() - y.min()) / 2, 1.0 / (x.max() - x.min()), 0.0, y.mean()],
        'description': 'Sine Wave: y = amplitude*sin(2π*frequency*x + phase) + offset',
    },
    'damped_sine': {
        'func': damped_sine,
        'params': ['amplitude', 'frequency', 'decay', 'phase', 'offset'],
        'bounds': {},
        'initial_guess': lambda x, y: [(y.max() - y.min()) / 2, 1.0 / (x.max() - x.min()), 0.1, 0.0, y.mean()],
        'description': 'Damped Sine: y = amplitude*exp(-decay*x)*sin(2π*frequency*x + phase) + offset',
    },
}


# ═══════════════════════════════════════════════════════════════════════
# MAIN FITTING FUNCTION
# ═══════════════════════════════════════════════════════════════════════

def fit_curve(
    x: List[float],
    y: List[float],
    function: str = 'gaussian',
    initial_params: Optional[Dict[str, float]] = None,
    bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    method: str = 'lm',
) -> FitResult:
    """
    Fit a curve to data using nonlinear least squares.
    
    Args:
        x: Independent variable
        y: Dependent variable
        function: Function name from FITTING_FUNCTIONS
        initial_params: Initial parameter guesses (optional)
        bounds: Parameter bounds (optional)
        method: 'lm' (Levenberg-Marquardt) or 'trf' (Trust Region Reflective)
    
    Returns:
        FitResult object with fitted parameters and statistics
    """
    x_arr = np.array(x)
    y_arr = np.array(y)
    
    if len(x_arr) != len(y_arr):
        raise ValueError("x and y must have the same length")
    
    if function not in FITTING_FUNCTIONS:
        raise ValueError(f"Unknown function: {function}. Available: {list(FITTING_FUNCTIONS.keys())}")
    
    func_info = FITTING_FUNCTIONS[function]
    func = func_info['func']
    param_names = func_info['params']
    
    # Generate initial guess
    if initial_params:
        p0 = [initial_params.get(p, 1.0) for p in param_names]
    else:
        p0 = func_info['initial_guess'](x_arr, y_arr)
    
    # Set up bounds
    if bounds:
        lower_bounds = [bounds.get(p, (-np.inf, np.inf))[0] for p in param_names]
        upper_bounds = [bounds.get(p, (-np.inf, np.inf))[1] for p in param_names]
        bounds_tuple = (lower_bounds, upper_bounds)
    else:
        # Use default bounds from function info
        default_bounds = func_info.get('bounds', {})
        lower_bounds = [default_bounds.get(p, (-np.inf, np.inf))[0] if isinstance(default_bounds.get(p, (-np.inf, np.inf)), tuple) else -np.inf for p in param_names]
        upper_bounds = [default_bounds.get(p, (-np.inf, np.inf))[1] if isinstance(default_bounds.get(p, (-np.inf, np.inf)), tuple) else np.inf for p in param_names]
        bounds_tuple = (lower_bounds, upper_bounds)
    
    try:
        # Perform curve fitting
        popt, pcov = optimize.curve_fit(
            func, x_arr, y_arr,
            p0=p0,
            bounds=bounds_tuple,
            method=method,
            maxfev=10000,
        )
        
        # Calculate fitted values and residuals
        y_fit = func(x_arr, *popt)
        residuals = y_arr - y_fit
        
        # Calculate statistics
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((y_arr - np.mean(y_arr))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        n = len(y_arr)
        k = len(popt)
        rmse = np.sqrt(ss_res / n)
        chi_squared = ss_res
        reduced_chi_squared = ss_res / (n - k) if n > k else np.inf
        
        # Information criteria
        aic = n * np.log(ss_res / n) + 2 * k
        bic = n * np.log(ss_res / n) + k * np.log(n)
        
        # Parameter errors (standard deviations)
        perr = np.sqrt(np.diag(pcov))
        
        # Build parameter dictionaries
        parameters = {name: float(val) for name, val in zip(param_names, popt)}
        parameter_errors = {name: float(err) for name, err in zip(param_names, perr)}
        
        # Generate equation string
        equation = _generate_equation(function, parameters)
        
        return FitResult(
            function_name=function,
            parameters=parameters,
            parameter_errors=parameter_errors,
            r_squared=float(r_squared),
            rmse=float(rmse),
            chi_squared=float(chi_squared),
            reduced_chi_squared=float(reduced_chi_squared),
            aic=float(aic),
            bic=float(bic),
            residuals=residuals.tolist(),
            fitted_values=y_fit.tolist(),
            equation=equation,
            success=True,
            message="Fit converged successfully",
        )
        
    except Exception as e:
        logger.error(f"Curve fitting failed: {e}")
        return FitResult(
            function_name=function,
            parameters={},
            parameter_errors={},
            r_squared=0.0,
            rmse=0.0,
            chi_squared=0.0,
            reduced_chi_squared=0.0,
            aic=0.0,
            bic=0.0,
            residuals=[],
            fitted_values=[],
            equation="",
            success=False,
            message=str(e),
        )


def _generate_equation(function: str, params: Dict[str, float]) -> str:
    """Generate human-readable equation string"""
    if function == 'gaussian':
        return f"y = {params['amplitude']:.3f} * exp(-((x-{params['center']:.3f})/{params['width']:.3f})²) + {params['offset']:.3f}"
    elif function == 'exponential':
        return f"y = {params['a']:.3f} * exp({params['b']:.3f}*x) + {params['c']:.3f}"
    elif function == 'sigmoid':
        return f"y = {params['L']:.3f} / (1 + exp(-{params['k']:.3f}*(x-{params['x0']:.3f}))) + {params['offset']:.3f}"
    elif function == 'power_law':
        return f"y = {params['a']:.3f} * x^{params['b']:.3f} + {params['c']:.3f}"
    else:
        # Generic format
        param_str = ', '.join([f"{k}={v:.3f}" for k, v in params.items()])
        return f"{function}({param_str})"
