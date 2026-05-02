"""
RĀMAN Studio — Core Test Suite
================================
Tests for simulation engines, cache, unit converter, and data importer.
"""

import pytest
import math
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# ── Unit Converter Tests ───────────────────────────────────

class TestUnitConverter:
    def test_randles_sevcik(self):
        from src.backend.core.unit_converter import randles_sevcik
        result = randles_sevcik(n=1, A_cm2=0.0707, D_cm2s=7.6e-6, C_M=5e-3, v_Vs=0.1)
        assert "ip_A" in result
        assert result["ip_A"] > 0
        assert "ip_µA" in result

    def test_nernst(self):
        from src.backend.core.unit_converter import nernst
        result = nernst(E0_V=0.0, n=1, C_ox_M=1.0, C_red_M=1.0, T_K=298.15)
        assert "E_V" in result
        assert abs(result["E_V"]) < 0.001  # Equal concentrations → E = E0

    def test_nernst_concentration_effect(self):
        from src.backend.core.unit_converter import nernst
        result = nernst(E0_V=0.0, n=1, C_ox_M=10.0, C_red_M=1.0, T_K=298.15)
        assert result["E_V"] > 0  # Higher oxidant → positive shift

    def test_cottrell(self):
        from src.backend.core.unit_converter import cottrell
        result = cottrell(n=1, A_cm2=0.0707, D_cm2s=7.6e-6, C_M=5e-3, t_s=1.0)
        assert "i_A" in result
        assert result["i_A"] > 0


# ── Cache Tests ────────────────────────────────────────────

class TestCache:
    def test_memory_cache_set_get(self):
        from src.backend.core.cache import cache_set, cache_get
        cache_set("test:key1", {"value": 42}, ttl=60)
        result = cache_get("test:key1")
        assert result is not None
        assert result["value"] == 42

    def test_cache_miss(self):
        from src.backend.core.cache import cache_get
        result = cache_get("test:nonexistent_key_xyz")
        assert result is None

    def test_cache_stats(self):
        from src.backend.core.cache import get_stats
        stats = get_stats()
        assert "backend" in stats
        assert stats["backend"] in ("redis", "memory")


# ── Data Importer Tests ───────────────────────────────────

class TestDataImporter:
    def test_csv_parse(self):
        from src.backend.core.data_importer import parse_file
        csv = "frequency,z_real,z_imag\n100,50,-30\n1000,45,-20\n10000,42,-10\n"
        result = parse_file(csv, "test.csv")
        assert result is not None
        assert "format" in result
        assert result["format"] == "csv"

    def test_detect_format_csv(self):
        from src.backend.core.data_importer import parse_file
        csv = "freq,Zre,Zim\n1,1,1"
        result = parse_file(csv, "test.csv")
        assert result["format"] == "csv"

    def test_detect_format_gamry(self):
        from src.backend.core.data_importer import parse_file
        gamry = "EXPLAIN\nLABEL\tGamry Data\nTABLE\nPt\tT\tVf\n1\t0\t1\n"
        result = parse_file(gamry, "test.dta")
        assert result["format"] == "gamry_dta"

    def test_detect_format_biologic(self):
        from src.backend.core.data_importer import parse_file
        biologic = "Nb header lines : 2\nfreq\tRe(Z)\t-Im(Z)\n1\t2\t3\n"
        result = parse_file(biologic, "test.mpt")
        assert result["format"] == "biologic_mpt"

    def test_detect_format_zview(self):
        from src.backend.core.data_importer import parse_file
        zview = "ZView Data\nfreq\tZ'\tZ''\n1\t2\t3\n"
        result = parse_file(zview, "test.z")
        assert result["format"] == "zview_z"


# ── Native Bridge / Engine Tests ───────────────────────────

class TestEngines:
    def test_cpp_module_loads(self):
        """Test that the C++ engine .so loads correctly."""
        try:
            sys.path.insert(0, os.path.join(
                os.path.dirname(__file__), '..', '..', 'engine_core', 'build'))
            import raman_core
            exports = [x for x in dir(raman_core) if not x.startswith('_')]
            assert len(exports) >= 10
        except ImportError:
            pytest.skip("C++ module not compiled")

    def test_eis_simulation(self):
        """Test EIS via C++ if available, else skip."""
        try:
            sys.path.insert(0, os.path.join(
                os.path.dirname(__file__), '..', '..', 'engine_core', 'build'))
            import raman_core
            params = raman_core.EISParams()
            params.Rs = 10
            params.Rct = 100
            params.Cdl = 1e-5
            params.sigma_w = 50
            params.n_cpe = 0.9
            result = raman_core.simulate_eis(params)
            assert len(result.Z_real) > 0
            assert len(result.Z_imag) > 0
            # High freq → Z ≈ Rs
            assert abs(result.Z_real[-1] - 10.0) < 5.0
        except ImportError:
            pytest.skip("C++ module not compiled")

    def test_drt_computation(self):
        """Test DRT solver."""
        try:
            sys.path.insert(0, os.path.join(
                os.path.dirname(__file__), '..', '..', 'engine_core', 'build'))
            import raman_core
            import numpy as np
            # Generate synthetic data from Randles circuit
            params = raman_core.EISParams()
            params.Rs = 10; params.Rct = 100; params.Cdl = 1e-5
            params.sigma_w = 50; params.n_cpe = 0.9
            eis = raman_core.simulate_eis(params, 0.01, 1e6, 50)

            drt_params = raman_core.DRTParams()
            drt_params.n_tau = 50
            result = raman_core.compute_drt(
                eis.frequencies, eis.Z_real, eis.Z_imag, drt_params)
            assert len(result.tau) == 50
            assert len(result.gamma) == 50
            assert result.R_inf > 0
        except ImportError:
            pytest.skip("C++ module not compiled")


# ── Physics Validation Tests ──────────────────────────────

class TestPhysics:
    def test_randles_sevcik_proportional_to_sqrt_v(self):
        """ip should be proportional to √ν."""
        from src.backend.core.unit_converter import randles_sevcik
        ip1 = randles_sevcik(1, 0.0707, 7.6e-6, 5e-3, 0.01)["ip_A"]
        ip2 = randles_sevcik(1, 0.0707, 7.6e-6, 5e-3, 0.04)["ip_A"]
        # ip2/ip1 should ≈ √(0.04/0.01) = 2.0
        ratio = ip2 / ip1
        assert abs(ratio - 2.0) < 0.01

    def test_nernst_59mv_per_decade(self):
        """At 298K, E shifts ~59mV/n per 10x concentration change."""
        from src.backend.core.unit_converter import nernst
        E1 = nernst(0.0, 1, 1.0, 1.0)["E_V"]
        E2 = nernst(0.0, 1, 10.0, 1.0)["E_V"]
        shift = (E2 - E1) * 1000  # mV
        assert abs(shift - 59.16) < 2.0  # ~59 mV per decade


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
