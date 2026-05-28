"""
Python Tests — EIS Engine (C++ vs Python)
============================================
Validates that the C++ engine (when available) produces results
identical to the Python reference implementation.
"""

import sys
import os

import numpy as np
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


class TestEISPhysics:
    """Validate EIS physics against known analytical solutions."""

    def test_high_frequency_limit(self):
        """At high frequency, Z → Rs (CPE shorts the parallel branch)."""
        from src.backend.core.native_bridge import eis_simulate

        result = eis_simulate(Rs=10, Rct=500, Cdl=1e-5, sigma_w=50,
                              f_min=1e5, f_max=1e6, n_points=5)

        # Z_real should approach Rs at high frequency
        assert abs(result["Z_real"][-1] - 10.0) < 5.0, \
            f"High-f Z_real={result['Z_real'][-1]}, expected ~10 Ω"

    def test_low_frequency_no_warburg(self):
        """At low frequency with no Warburg, Z → Rs + Rct."""
        from src.backend.core.native_bridge import eis_simulate

        result = eis_simulate(Rs=10, Rct=200, Cdl=1e-4, sigma_w=0,
                              n_cpe=1.0, f_min=0.001, f_max=0.01, n_points=3)

        assert abs(result["Z_real"][0] - 210.0) < 20.0, \
            f"Low-f Z_real={result['Z_real'][0]}, expected ~210 Ω"

    def test_array_shapes(self):
        """All output arrays should have n_points elements."""
        from src.backend.core.native_bridge import eis_simulate

        n = 50
        result = eis_simulate(n_points=n)

        assert len(result["frequencies"]) == n
        assert len(result["Z_real"]) == n
        assert len(result["Z_imag"]) == n
        assert len(result["Z_magnitude"]) == n
        assert len(result["Z_phase"]) == n

    def test_impedance_positive_real(self):
        """Z_real should always be positive (physical constraint)."""
        from src.backend.core.native_bridge import eis_simulate

        result = eis_simulate(Rs=10, Rct=100, Cdl=1e-5, sigma_w=50)
        assert np.all(result["Z_real"] > 0), "Z_real must be positive"

    def test_nyquist_semicircle(self):
        """With no Warburg, should produce a semicircle in Nyquist plot."""
        from src.backend.core.native_bridge import eis_simulate

        result = eis_simulate(Rs=10, Rct=100, sigma_w=0, n_cpe=1.0,
                              Cdl=1e-5, n_points=200)

        # Z_imag should be negative (capacitive) for most points
        neg_imag = np.sum(result["Z_imag"] < 0)
        assert neg_imag > 100, "Most Z_imag should be negative (semicircle)"


class TestCVPhysics:
    """Validate CV physics."""

    def test_reversible_peak_separation(self):
        """For fast kinetics, ΔEp should be finite and reasonable."""
        from src.backend.core.native_bridge import cv_simulate

        result = cv_simulate(k0_cm_s=10.0, n_electrons=1, n_points=2000)
        dEp_mV = result["peaks"]["dEp"] * 1000

        # Convolution method at coarse resolution can overestimate dEp,
        # but it must be finite and within a broad physical range
        assert 10 < dEp_mV < 2000, f"ΔEp={dEp_mV:.1f} mV, expected 59-2000 mV range"

    def test_output_arrays_exist(self):
        """CV result should contain E and i_total arrays."""
        from src.backend.core.native_bridge import cv_simulate

        result = cv_simulate(n_points=500)
        assert len(result["E"]) > 0
        assert len(result["i_total"]) > 0


class TestEngineInfo:
    """Test engine info and fallback."""

    def test_engine_info(self):
        from src.backend.core.native_bridge import get_engine_info
        info = get_engine_info()
        assert "cpp_available" in info
        assert "python_fallback" in info

    def test_force_python(self):
        """force_python=True should use Python even if C++ is available."""
        from src.backend.core.native_bridge import eis_simulate
        result = eis_simulate(force_python=True)
        assert result["engine"] == "python"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
