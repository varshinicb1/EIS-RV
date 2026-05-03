"""
Biosensor Simulation Engine Tests
===================================
Unit tests for biosensor simulation: enzyme kinetics, electrochemical detection,
calibration curves, LOD/LOQ calculation, and performance metrics.

Run with:
    python -m pytest tests/unit/test_biosensor_engine.py -v
"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.backend.core.engines.biosensor_engine import (
    BiosensorConfig,
    BiosensorPerformance,
    BiosensorType,
    ANALYTE_DB,
    simulate_biosensor,
    michaelis_menten,
    randles_sevcik_peak_current,
    cottrell_current,
    quick_biosensor,
    list_analytes,
)


# =====================================================================
#   BiosensorConfig Tests
# =====================================================================

class TestBiosensorConfig:
    def test_default_config(self):
        """Default config should be valid glucose biosensor."""
        config = BiosensorConfig()
        assert config.sensor_type == BiosensorType.AMPEROMETRIC
        assert config.analyte == "glucose"
        assert config.working_electrode_area_mm2 > 0
        assert config.enzyme_loading_U_cm2 > 0

    def test_custom_config(self):
        """Custom configuration should be accepted."""
        config = BiosensorConfig(
            analyte="lactate",
            sensor_type=BiosensorType.IMPEDIMETRIC,
            working_electrode_area_mm2=10.0,
            modifier="enzyme"
        )
        assert config.analyte == "lactate"
        assert config.sensor_type == BiosensorType.IMPEDIMETRIC


# =====================================================================
#   Enzyme Kinetics Tests
# =====================================================================

class TestEnzymeKinetics:
    def test_michaelis_menten_zero_substrate(self):
        """Zero substrate should give zero velocity."""
        v = michaelis_menten(np.array([0.0]), Vmax=100, Km=10)
        assert abs(v[0]) < 1e-10

    def test_michaelis_menten_saturation(self):
        """High substrate should approach Vmax."""
        S_high = np.array([1000.0])  # >> Km
        v = michaelis_menten(S_high, Vmax=100, Km=10)
        assert v[0] > 95  # Should be close to Vmax

    def test_michaelis_menten_half_max(self):
        """At S = Km, velocity should be Vmax/2."""
        Km = 10.0
        Vmax = 100.0
        v = michaelis_menten(np.array([Km]), Vmax=Vmax, Km=Km)
        assert abs(v[0] - Vmax/2) < 1

    def test_michaelis_menten_shape(self):
        """MM curve should be hyperbolic."""
        S = np.linspace(0, 100, 50)
        v = michaelis_menten(S, Vmax=100, Km=10)
        
        assert len(v) == len(S)
        assert all(np.isfinite(v))
        # Should be monotonically increasing
        assert all(v[i+1] >= v[i] for i in range(len(v)-1))


# =====================================================================
#   Electrochemical Models Tests
# =====================================================================

class TestElectrochemicalModels:
    def test_randles_sevcik_positive(self):
        """Peak current should be positive."""
        i_p = randles_sevcik_peak_current(
            n=2, A_cm2=0.07, D_cm2_s=6.7e-6,
            C_M=1e-3, v_V_s=0.05
        )
        assert i_p > 0

    def test_randles_sevcik_scan_rate_dependence(self):
        """Peak current should scale with sqrt(scan rate)."""
        i_slow = randles_sevcik_peak_current(
            n=2, A_cm2=0.07, D_cm2_s=6.7e-6,
            C_M=1e-3, v_V_s=0.01
        )
        i_fast = randles_sevcik_peak_current(
            n=2, A_cm2=0.07, D_cm2_s=6.7e-6,
            C_M=1e-3, v_V_s=0.1
        )
        # i_p ∝ √v, so 10x scan rate → √10 ≈ 3.16x current
        ratio = i_fast / i_slow
        assert 3.0 < ratio < 3.5

    def test_cottrell_time_dependence(self):
        """Cottrell current should decay as 1/√t."""
        t = np.array([1.0, 4.0, 16.0])
        i = cottrell_current(
            n=2, F=96485, A_cm2=0.07,
            D_cm2_s=6.7e-6, C_M=1e-3, t_s=t
        )
        
        # i(t) ∝ 1/√t, so i(4)/i(1) = √(1/4) = 0.5
        assert abs(i[1] / i[0] - 0.5) < 0.1
        assert abs(i[2] / i[0] - 0.25) < 0.1

    def test_cottrell_all_positive(self):
        """Cottrell current should always be positive."""
        t = np.linspace(0.1, 100, 50)
        i = cottrell_current(
            n=2, F=96485, A_cm2=0.07,
            D_cm2_s=6.7e-6, C_M=1e-3, t_s=t
        )
        assert all(i > 0)


# =====================================================================
#   Full Biosensor Simulation Tests
# =====================================================================

class TestBiosensorSimulation:
    def test_basic_glucose_sensor(self):
        """Basic glucose biosensor simulation."""
        config = BiosensorConfig(analyte="glucose")
        perf = simulate_biosensor(config)
        
        assert isinstance(perf, BiosensorPerformance)
        assert perf.sensitivity_uA_mM > 0
        assert perf.LOD_uM > 0
        assert perf.LOQ_uM > perf.LOD_uM
        assert 0 < perf.R_squared <= 1

    def test_enzymatic_vs_direct(self):
        """Enzymatic sensor should have different kinetics than direct."""
        config_enzyme = BiosensorConfig(
            analyte="glucose",
            modifier="enzyme"
        )
        config_direct = BiosensorConfig(
            analyte="dopamine",
            modifier="none"
        )
        
        perf_enzyme = simulate_biosensor(config_enzyme)
        perf_direct = simulate_biosensor(config_direct)
        
        # Enzymatic should show Michaelis-Menten kinetics
        assert perf_enzyme.Km_mM > 0
        assert perf_enzyme.Vmax_uA > 0

    def test_calibration_curve_generated(self):
        """Calibration curve should be generated."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert len(perf.concentrations_mM) > 0
        assert len(perf.responses_uA) > 0
        assert len(perf.concentrations_mM) == len(perf.responses_uA)
        assert perf.calibration_slope > 0

    def test_linear_range_valid(self):
        """Linear range should be within calibration range."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert len(perf.linear_range_mM) == 2
        assert perf.linear_range_mM[1] > perf.linear_range_mM[0]
        assert perf.linear_range_mM[0] >= 0

    def test_lod_loq_relationship(self):
        """LOQ should be ~3.3x LOD (10σ vs 3σ)."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        ratio = perf.LOQ_uM / perf.LOD_uM
        assert 3.0 < ratio < 3.5

    def test_sensitivity_area_normalized(self):
        """Area-normalized sensitivity should be calculated."""
        config_small = BiosensorConfig(working_electrode_area_mm2=5.0)
        config_large = BiosensorConfig(working_electrode_area_mm2=20.0)
        
        perf_small = simulate_biosensor(config_small)
        perf_large = simulate_biosensor(config_large)
        
        # Both should have positive sensitivity
        assert perf_small.sensitivity_uA_mM > 0
        assert perf_large.sensitivity_uA_mM > 0
        # Area-normalized values should be positive
        assert perf_small.sensitivity_uA_mM_cm2 > 0
        assert perf_large.sensitivity_uA_mM_cm2 > 0

    def test_enzyme_loading_affects_sensitivity(self):
        """Higher enzyme loading should affect performance."""
        config_low = BiosensorConfig(enzyme_loading_U_cm2=5.0, modifier="enzyme")
        config_high = BiosensorConfig(enzyme_loading_U_cm2=20.0, modifier="enzyme")
        
        perf_low = simulate_biosensor(config_low)
        perf_high = simulate_biosensor(config_high)
        
        # Both should have positive Vmax when enzyme is present
        assert perf_low.Vmax_uA > 0
        assert perf_high.Vmax_uA > 0
        # Higher loading should give higher Vmax
        assert perf_high.Vmax_uA > perf_low.Vmax_uA

    def test_response_time_calculated(self):
        """Response time should be positive and reasonable."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert perf.response_time_s > 0
        assert perf.response_time_s < 300  # Should be < 5 minutes


# =====================================================================
#   Chronoamperometry Tests
# =====================================================================

class TestChronoamperometry:
    def test_chronoamp_curve_generated(self):
        """Chronoamperometry curve should be generated."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert len(perf.chronoamp_t) > 0
        assert len(perf.chronoamp_i) > 0
        assert len(perf.chronoamp_t) == len(perf.chronoamp_i)

    def test_chronoamp_decay(self):
        """Current should decay over time (Cottrell behavior)."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        currents = np.array(perf.chronoamp_i)
        # Current should generally decrease or stabilize
        assert currents[0] > currents[-1] * 0.5


# =====================================================================
#   DPV/Voltammetry Tests
# =====================================================================

class TestVoltammetry:
    def test_dpv_curve_generated(self):
        """DPV curve should be generated."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert len(perf.dpv_E) > 0
        assert len(perf.dpv_i) > 0
        assert len(perf.dpv_E) == len(perf.dpv_i)

    def test_dpv_peak_detected(self):
        """DPV should show a peak."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert perf.peak_potential_V > 0
        assert perf.peak_current_uA > 0
        
        # Peak should be within voltage range
        E_min = min(perf.dpv_E)
        E_max = max(perf.dpv_E)
        assert E_min < perf.peak_potential_V < E_max


# =====================================================================
#   EIS Tests
# =====================================================================

class TestBiosensorEIS:
    def test_eis_data_generated(self):
        """EIS data should be generated."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert "frequencies" in perf.eis_data
        assert "baseline" in perf.eis_data
        assert "with_analyte" in perf.eis_data

    def test_eis_analyte_changes_rct(self):
        """Analyte binding should change Rct."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert perf.Rct_ohm > 0
        assert perf.Rct_with_analyte_ohm > 0
        assert abs(perf.Rct_change_pct) > 0.1  # Should show measurable change

    def test_impedimetric_increases_rct(self):
        """Impedimetric sensor should show Rct increase with analyte."""
        config = BiosensorConfig(sensor_type=BiosensorType.IMPEDIMETRIC)
        perf = simulate_biosensor(config)
        
        # Binding blocks electron transfer → Rct increases
        assert perf.Rct_with_analyte_ohm > perf.Rct_ohm


# =====================================================================
#   Stability Tests
# =====================================================================

class TestStability:
    def test_stability_predicted(self):
        """Stability metrics should be predicted."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert perf.operational_stability_hours > 0
        assert perf.shelf_life_days > 0

    def test_enzyme_stability_reasonable(self):
        """Enzyme biosensor should have realistic stability."""
        config = BiosensorConfig(modifier="enzyme")
        perf = simulate_biosensor(config)
        
        # Typical enzyme biosensor: hours to days operational
        assert 1 < perf.operational_stability_hours < 100
        assert 7 < perf.shelf_life_days < 365

    def test_temperature_affects_stability(self):
        """Higher temperature should reduce stability."""
        config_low = BiosensorConfig(temperature_C=25)
        config_high = BiosensorConfig(temperature_C=50)
        
        perf_low = simulate_biosensor(config_low)
        perf_high = simulate_biosensor(config_high)
        
        assert perf_low.operational_stability_hours > perf_high.operational_stability_hours


# =====================================================================
#   Selectivity Tests
# =====================================================================

class TestSelectivity:
    def test_selectivity_estimated(self):
        """Selectivity ratios should be estimated."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert len(perf.selectivity_ratio) > 0
        assert all(0 <= v <= 1 for v in perf.selectivity_ratio.values())

    def test_enzyme_improves_selectivity(self):
        """Enzyme should provide better selectivity than direct detection."""
        config_enzyme = BiosensorConfig(modifier="enzyme")
        config_direct = BiosensorConfig(modifier="none")
        
        perf_enzyme = simulate_biosensor(config_enzyme)
        perf_direct = simulate_biosensor(config_direct)
        
        # Enzyme should have lower interferent response
        avg_enzyme = np.mean(list(perf_enzyme.selectivity_ratio.values()))
        avg_direct = np.mean(list(perf_direct.selectivity_ratio.values()))
        assert avg_enzyme < avg_direct


# =====================================================================
#   Recommendations Tests
# =====================================================================

class TestRecommendations:
    def test_recommendations_generated(self):
        """Recommendations should be generated."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert isinstance(perf.recommendations, list)

    def test_high_lod_recommendation(self):
        """High LOD should trigger recommendation."""
        config = BiosensorConfig(
            enzyme_loading_U_cm2=1.0,  # Low loading → high LOD
            working_electrode_area_mm2=1.0
        )
        perf = simulate_biosensor(config)
        
        if perf.LOD_uM > 100:
            assert len(perf.recommendations) > 0


# =====================================================================
#   Analyte Database Tests
# =====================================================================

class TestAnalyteDatabase:
    def test_all_analytes_have_properties(self):
        """All analytes should have required properties."""
        required_keys = ["MW", "D_cm2_s", "n_electrons"]
        
        for analyte_name, props in ANALYTE_DB.items():
            for key in required_keys:
                assert key in props, f"{analyte_name} missing {key}"

    def test_list_analytes(self):
        """list_analytes should return all analytes."""
        analytes = list_analytes()
        assert len(analytes) > 0
        assert all("name" in a for a in analytes)
        assert all("MW" in a for a in analytes)

    def test_glucose_properties(self):
        """Glucose should have correct properties."""
        glucose = ANALYTE_DB["glucose"]
        assert glucose["MW"] == 180.16
        assert glucose["enzyme"] == "glucose_oxidase"
        assert glucose["n_electrons"] == 2


# =====================================================================
#   Quick Simulation Tests
# =====================================================================

class TestQuickSimulation:
    def test_quick_biosensor(self):
        """Quick biosensor simulation should work."""
        result = quick_biosensor(analyte="glucose")
        
        assert isinstance(result, dict)
        assert "sensitivity_uA_mM" in result
        assert "LOD_uM" in result
        assert "calibration" in result

    def test_quick_biosensor_custom_params(self):
        """Quick simulation with custom parameters."""
        result = quick_biosensor(
            analyte="lactate",
            electrode_material="carbon_black",
            modifier="enzyme",
            area_mm2=10.0
        )
        
        assert result["sensitivity_uA_mM"] > 0
        assert result["LOD_uM"] > 0


# =====================================================================
#   Serialization Tests
# =====================================================================

class TestSerialization:
    def test_to_dict_complete(self):
        """to_dict should include all metrics."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        data = perf.to_dict()
        
        assert isinstance(data, dict)
        assert "sensitivity_uA_mM" in data
        assert "LOD_uM" in data
        assert "LOQ_uM" in data
        assert "calibration" in data
        assert "dpv" in data
        assert "chronoamperometry" in data
        assert "eis" in data

    def test_to_dict_numeric_types(self):
        """All numeric values should be serializable."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        data = perf.to_dict()
        
        # Check key numeric fields are numbers
        assert isinstance(data["sensitivity_uA_mM"], (int, float))
        assert isinstance(data["LOD_uM"], (int, float))
        assert isinstance(data["calibration"]["R_squared"], (int, float))


# =====================================================================
#   Edge Cases Tests
# =====================================================================

class TestEdgeCases:
    def test_zero_enzyme_loading(self):
        """Zero enzyme loading should still compute."""
        config = BiosensorConfig(enzyme_loading_U_cm2=0.0, modifier="none")
        perf = simulate_biosensor(config)
        
        assert perf.sensitivity_uA_mM > 0

    def test_very_small_electrode(self):
        """Very small electrode should still work."""
        config = BiosensorConfig(working_electrode_area_mm2=0.1)
        perf = simulate_biosensor(config)
        
        assert perf.sensitivity_uA_mM > 0
        assert np.isfinite(perf.LOD_uM)

    def test_all_sensor_types(self):
        """All sensor types should simulate."""
        for sensor_type in BiosensorType:
            config = BiosensorConfig(sensor_type=sensor_type)
            perf = simulate_biosensor(config)
            assert perf.sensitivity_uA_mM > 0

    def test_numerical_stability(self):
        """All outputs should be finite."""
        config = BiosensorConfig()
        perf = simulate_biosensor(config)
        
        assert np.isfinite(perf.sensitivity_uA_mM)
        assert np.isfinite(perf.LOD_uM)
        assert np.isfinite(perf.LOQ_uM)
        assert np.isfinite(perf.response_time_s)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
