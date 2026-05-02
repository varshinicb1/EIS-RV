"""
C++ Engine Bridge — Python Fallback Wrapper
=============================================
Provides a unified interface that uses C++ (raman_core) when available,
and falls back to the existing Python implementations otherwise.

Usage:
    from src.backend.core.native_bridge import eis_simulate, cv_simulate

    # Automatically uses C++ if compiled, Python otherwise
    result = eis_simulate(Rs=10, Rct=100, Cdl=1e-5, sigma_w=50)
"""

import logging
import time
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Try loading C++ engine ─────────────────────────────────

try:
    import raman_core
    CPP_AVAILABLE = True
    logger.info("✅ C++ engine (raman_core) loaded — version %s",
                raman_core.__version__)
except ImportError:
    CPP_AVAILABLE = False
    logger.info("ℹ️  C++ engine not available — using Python fallback")


def eis_simulate(
    Rs: float = 10.0,
    Rct: float = 100.0,
    Cdl: float = 1e-5,
    sigma_w: float = 50.0,
    n_cpe: float = 0.9,
    f_min: float = 0.01,
    f_max: float = 1e6,
    n_points: int = 100,
    bounded_warburg: bool = False,
    diff_length_um: float = 100.0,
    diff_coeff: float = 1e-6,
    force_python: bool = False,
) -> Dict:
    """
    Simulate EIS (modified Randles circuit).

    Returns dict with: frequencies, Z_real, Z_imag, Z_magnitude, Z_phase.
    All as numpy arrays.
    """
    t0 = time.perf_counter()

    if CPP_AVAILABLE and not force_python:
        # ── C++ path ───────────────────────────────────────
        params = raman_core.EISParams()
        params.Rs = Rs
        params.Rct = Rct
        params.Cdl = Cdl
        params.sigma_w = sigma_w
        params.n_cpe = n_cpe
        params.bounded_w = bounded_warburg
        params.diff_len_um = diff_length_um
        params.diff_coeff = diff_coeff

        result = raman_core.simulate_eis(params, f_min, f_max, n_points)

        elapsed = time.perf_counter() - t0
        logger.debug("EIS (C++): %.2f ms, %d points", elapsed * 1000, n_points)

        return {
            "engine": "cpp",
            "compute_time_s": elapsed,
            "frequencies": np.array(result.frequencies),
            "Z_real": np.array(result.Z_real),
            "Z_imag": np.array(result.Z_imag),
            "Z_magnitude": np.array(result.Z_magnitude),
            "Z_phase": np.array(result.Z_phase),
        }
    else:
        # ── Python fallback ────────────────────────────────
        try:
            from vanl.backend.core.eis_engine import EISEngine
            engine = EISEngine()
            result = engine.simulate(
                Rs=Rs, Rct=Rct, Cdl=Cdl, sigma_w=sigma_w,
                n=n_cpe, f_min=f_min, f_max=f_max,
                num_points=n_points,
            )
            elapsed = time.perf_counter() - t0
            logger.debug("EIS (Python): %.2f ms", elapsed * 1000)

            return {
                "engine": "python",
                "compute_time_s": elapsed,
                "frequencies": np.array(result.get("frequencies", [])),
                "Z_real": np.array(result.get("Z_real", [])),
                "Z_imag": np.array(result.get("Z_imag", [])),
                "Z_magnitude": np.array(result.get("Z_magnitude", [])),
                "Z_phase": np.array(result.get("Z_phase", [])),
            }
        except ImportError:
            raise RuntimeError(
                "Neither C++ engine nor Python fallback available. "
                "Build the C++ engine or ensure vanl.backend.core is accessible."
            )


def cv_simulate(
    area_cm2: float = 0.0707,
    E_formal_V: float = 0.23,
    n_electrons: int = 1,
    C_ox_M: float = 5e-3,
    D_ox_cm2s: float = 7.6e-6,
    k0_cm_s: float = 0.01,
    alpha: float = 0.5,
    E_start_V: float = -0.3,
    E_vertex_V: float = 0.8,
    scan_rate_V_s: float = 0.05,
    n_points: int = 2000,
    force_python: bool = False,
) -> Dict:
    """
    Simulate cyclic voltammetry (Butler-Volmer).

    Returns dict with: E, i_total, i_faradaic, i_capacitive, peak analysis.
    """
    t0 = time.perf_counter()

    if CPP_AVAILABLE and not force_python:
        params = raman_core.CVParams()
        params.area_cm2 = area_cm2
        params.E_formal_V = E_formal_V
        params.n_electrons = n_electrons
        params.C_ox_M = C_ox_M
        params.D_ox_cm2s = D_ox_cm2s
        params.D_red_cm2s = D_ox_cm2s
        params.k0_cm_s = k0_cm_s
        params.alpha = alpha
        params.E_start_V = E_start_V
        params.E_vertex_V = E_vertex_V
        params.E_end_V = E_start_V
        params.scan_rate_V_s = scan_rate_V_s

        result = raman_core.simulate_cv(params, n_points)
        elapsed = time.perf_counter() - t0

        return {
            "engine": "cpp",
            "compute_time_s": elapsed,
            "E": np.array(result.E),
            "i_total": np.array(result.i_total),
            "i_faradaic": np.array(result.i_faradaic),
            "i_capacitive": np.array(result.i_capacitive),
            "peaks": {
                "i_pa": result.i_pa,
                "i_pc": result.i_pc,
                "E_pa": result.E_pa,
                "E_pc": result.E_pc,
                "dEp": result.dEp,
            },
        }
    else:
        try:
            from vanl.backend.core.cv_engine import CVEngine
            engine = CVEngine()
            result = engine.simulate(
                scan_rate=scan_rate_V_s,
                E_start=E_start_V,
                E_vertex=E_vertex_V,
                concentration=C_ox_M,
                diffusion_coeff=D_ox_cm2s,
            )
            elapsed = time.perf_counter() - t0

            return {
                "engine": "python",
                "compute_time_s": elapsed,
                "E": np.array(result.get("potential", [])),
                "i_total": np.array(result.get("current", [])),
                "peaks": result.get("peak_analysis", {}),
            }
        except ImportError:
            raise RuntimeError("No CV engine available (C++ or Python)")


def get_engine_info() -> Dict:
    """Return info about which engine is active."""
    return {
        "cpp_available": CPP_AVAILABLE,
        "cpp_version": getattr(raman_core, "__version__", None) if CPP_AVAILABLE else None,
        "python_fallback": True,
    }
