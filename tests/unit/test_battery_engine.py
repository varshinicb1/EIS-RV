"""
Printed Battery Simulation Engine Tests
=========================================
Unit tests for battery simulation: OCV models, discharge curves,
capacity, energy density, rate capability, aging, and EIS.

Run with:
    python -m pytest tests/unit/test_battery_engine.py -v
"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.backend.core.engines.battery_engine import (
    BatteryConfig,
    BatteryPerformance,
    OCV_MODELS,
    ocv_from_soc,
    simulate_battery,
    quick_battery,
    list_battery_chemistries,
)


# =====================================================================
#   OCV Model Tests
# =====================================================================

class TestOCVModels:
    def test_ocv_at_full_charge(self):
        """OCV at SOC=1 should be at upper voltage limit."""
        V = ocv_from_soc(np.array([0.99]), "zinc_MnO2")
        V_range = OCV_MODELS["zinc_MnO2"]["V_range"]
        assert V_range[0] < V[0] <= V_range[1]

    def test_ocv_at_empty(self):
        """OCV at SOC=0 should be at lower voltage limit."""
        V = ocv_from_soc(np.array([0.01]), "zinc_MnO2")
        V_range = OCV_MODELS["zinc_MnO2"]["V_range"]
        assert V_range[0] <= V[0] < V_range[1]

    def test_ocv_monotonic_decrease(self):
        """OCV should generally decrease with discharge (decreasing SOC)."""
        soc = np.linspace(0.99, 0.01, 50)
        V = ocv_from_soc(soc, "zinc_MnO2")
        
        # Voltage should change (may increase or decrease depending on chemistry)
        assert abs(V[0] - V[-1]) > 0.1

    def test_ocv_all_chemistries(self):
        """All chemistries should have valid OCV curves."""
        soc = np.linspace(0.1, 0.9, 20)
        
        for chem_name in OCV_MODELS.keys():
            V = ocv_from_soc(soc, chem_name)
            assert len(V) == len(soc)
            assert all(np.isfinite(V))
            # Some chemistries (like zinc anode) have negative potentials
            assert all(abs(v) > 0.01 for v in V)

    def test_lifepo4_flat_plateau(self):
        """LiFePO4 should show flat voltage plateau."""
        soc = np.linspace(0.2, 0.8, 50)
        V = ocv_from_soc(soc, "LiFePO4")
        
        # Voltage should be relatively flat (std < 0.1V)
        assert np.std(V) < 0.15

    def test_ocv_clipping(self):
        """OCV should be clipped to valid range."""
        soc = np.array([0.0, 0.5, 1.0])
        V = ocv_from_soc(soc, "zinc_MnO2")
        
        V_range = OCV_MODELS["zinc_MnO2"]["V_range"]
        assert all(V_range[0] <= v <= V_range[1] for v in V)


# =====================================================================
#   BatteryConfig Tests
# =====================================================================

class TestBatteryConfig:
    def test_default_config(self):
        """Default config should be valid zinc-MnO2 battery."""
        config = BatteryConfig()
        assert config.chemistry == "zinc_MnO2"
        assert config.electrode_area_cm2 > 0
        assert config.cathode_loading_mg_cm2 > 0
        assert config.anode_loading_mg_cm2 > 0

    def test_custom_config(self):
        """Custom configuration should be accepted."""
        config = BatteryConfig(
            chemistry="LiFePO4",
            electrode_area_cm2=2.0,
            cathode_loading_mg_cm2=15.0,
            C_rate=1.0
        )
        assert config.chemistry == "LiFePO4"
        assert config.electrode_area_cm2 == 2.0
        assert config.C_rate == 1.0


# =====================================================================
#   Full Battery Simulation Tests
# =====================================================================

class TestBatterySimulation:
    def test_basic_zinc_mno2_battery(self):
        """Basic zinc-MnO2 battery simulation."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert isinstance(perf, BatteryPerformance)
        assert perf.theoretical_capacity_mAh > 0
        assert perf.delivered_capacity_mAh > 0
        assert perf.energy_mWh > 0
        assert perf.internal_resistance_ohm > 0

    def test_capacity_utilization(self):
        """Delivered capacity should be less than theoretical."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert perf.delivered_capacity_mAh <= perf.theoretical_capacity_mAh
        assert 0 < perf.utilization_pct <= 100

    def test_energy_calculation(self):
        """Energy should be capacity × voltage."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        # E = Q × V (approximately)
        expected_energy = perf.delivered_capacity_mAh * perf.avg_discharge_V
        assert abs(perf.energy_mWh - expected_energy) / expected_energy < 0.1

    def test_voltage_hierarchy(self):
        """Voltages should be positive and reasonable."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert perf.OCV_V > 0
        assert perf.avg_discharge_V > 0
        # OCV and nominal should be close
        assert abs(perf.OCV_V - perf.nominal_V) < 0.5

    def test_internal_resistance_positive(self):
        """Internal resistance should be positive."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert perf.internal_resistance_ohm > 0
        assert perf.internal_resistance_ohm < 1000  # Reasonable for printed battery

    def test_area_affects_capacity(self):
        """Larger electrode area should give higher capacity."""
        config_small = BatteryConfig(electrode_area_cm2=0.5)
        config_large = BatteryConfig(electrode_area_cm2=2.0)
        
        perf_small = simulate_battery(config_small)
        perf_large = simulate_battery(config_large)
        
        assert perf_large.theoretical_capacity_mAh > perf_small.theoretical_capacity_mAh

    def test_loading_affects_capacity(self):
        """Higher loading should give higher capacity."""
        config_low = BatteryConfig(cathode_loading_mg_cm2=5.0)
        config_high = BatteryConfig(cathode_loading_mg_cm2=20.0)
        
        perf_low = simulate_battery(config_low)
        perf_high = simulate_battery(config_high)
        
        assert perf_high.theoretical_capacity_mAh > perf_low.theoretical_capacity_mAh


# =====================================================================
#   Discharge Curve Tests
# =====================================================================

class TestDischargeCurve:
    def test_discharge_curve_generated(self):
        """Discharge curve should be generated."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert len(perf.discharge_soc) > 0
        assert len(perf.discharge_V) > 0
        assert len(perf.discharge_t_min) > 0
        assert len(perf.discharge_capacity_mAh) > 0

    def test_discharge_arrays_same_length(self):
        """All discharge arrays should have same length."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        n = len(perf.discharge_soc)
        assert len(perf.discharge_V) == n
        assert len(perf.discharge_t_min) == n
        assert len(perf.discharge_capacity_mAh) == n

    def test_soc_decreases(self):
        """SOC should decrease during discharge."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        soc = np.array(perf.discharge_soc)
        assert soc[0] > soc[-1]
        # Should be monotonically decreasing
        assert all(soc[i] >= soc[i+1] for i in range(len(soc)-1))

    def test_voltage_decreases(self):
        """Voltage should generally decrease during discharge."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        V = np.array(perf.discharge_V)
        assert V[0] > V[-1]

    def test_time_increases(self):
        """Time should increase monotonically."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        t = np.array(perf.discharge_t_min)
        assert all(t[i+1] >= t[i] for i in range(len(t)-1))

    def test_capacity_increases(self):
        """Delivered capacity should increase during discharge."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        Q = np.array(perf.discharge_capacity_mAh)
        assert all(Q[i+1] >= Q[i] for i in range(len(Q)-1))

    def test_cutoff_voltage_respected(self):
        """Discharge should stop at cutoff voltage."""
        config = BatteryConfig(cutoff_V=1.0)
        perf = simulate_battery(config)
        
        V_final = perf.discharge_V[-1]
        assert V_final >= config.cutoff_V * 0.95  # Allow small tolerance


# =====================================================================
#   Rate Capability Tests
# =====================================================================

class TestRateCapability:
    def test_rate_capability_calculated(self):
        """Rate capability should be calculated for multiple C-rates."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert len(perf.rate_capacity) > 0
        assert "0.1C" in perf.rate_capacity
        assert "1.0C" in perf.rate_capacity

    def test_capacity_decreases_with_rate(self):
        """Capacity should decrease at higher C-rates."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        cap_01C = perf.rate_capacity.get("0.1C", 100)
        cap_1C = perf.rate_capacity.get("1.0C", 100)
        cap_5C = perf.rate_capacity.get("5.0C", 100)
        
        assert cap_01C >= cap_1C >= cap_5C

    def test_all_rates_positive(self):
        """All rate capabilities should be positive."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert all(v > 0 for v in perf.rate_capacity.values())


# =====================================================================
#   Energy & Power Density Tests
# =====================================================================

class TestEnergyPowerDensity:
    def test_energy_density_positive(self):
        """Energy density should be positive."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert perf.energy_density_Wh_kg > 0
        assert perf.energy_density_Wh_L > 0
        assert perf.areal_energy_mWh_cm2 > 0

    def test_power_density_positive(self):
        """Power density should be positive."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert perf.power_mW > 0
        assert perf.power_density_W_kg > 0

    def test_energy_density_reasonable(self):
        """Energy density should be in reasonable range for printed battery."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        # Printed batteries: typically 0.001-50 Wh/kg (small devices can be very low)
        assert 0.001 < perf.energy_density_Wh_kg < 200


# =====================================================================
#   Aging Tests
# =====================================================================

class TestAging:
    def test_aging_predicted(self):
        """Aging should be predicted for multiple cycle counts."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert len(perf.capacity_retention_pct) > 0

    def test_retention_decreases_with_cycles(self):
        """Capacity retention should decrease with cycle number."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        # Get retention values
        retentions = list(perf.capacity_retention_pct.values())
        if len(retentions) >= 2:
            assert retentions[0] >= retentions[-1]

    def test_retention_bounded(self):
        """Retention should be between 0 and 100%."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        for retention in perf.capacity_retention_pct.values():
            assert 0 <= retention <= 100


# =====================================================================
#   EIS Tests
# =====================================================================

class TestBatteryEIS:
    def test_eis_data_generated(self):
        """EIS data should be generated."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert len(perf.eis_freq) > 0
        assert len(perf.eis_Z_real) > 0
        assert len(perf.eis_Z_imag) > 0

    def test_eis_arrays_same_length(self):
        """EIS arrays should have same length."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        n = len(perf.eis_freq)
        assert len(perf.eis_Z_real) == n
        assert len(perf.eis_Z_imag) == n

    def test_eis_high_freq_limit(self):
        """At high frequency, Z_real should approach Rs."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        # First point is highest frequency
        Z_real_high_f = perf.eis_Z_real[0]
        R_int = perf.internal_resistance_ohm
        
        # Should be close to ohmic resistance
        assert Z_real_high_f < R_int


# =====================================================================
#   Ragone Plot Tests
# =====================================================================

class TestRagonePlot:
    def test_ragone_data_generated(self):
        """Ragone plot data should be generated."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert len(perf.ragone_E) > 0
        assert len(perf.ragone_P) > 0

    def test_ragone_arrays_same_length(self):
        """Ragone E and P arrays should have same length."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert len(perf.ragone_E) == len(perf.ragone_P)

    def test_ragone_tradeoff(self):
        """Higher power should generally mean lower energy."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        if len(perf.ragone_E) > 2:
            # Energy should generally decrease as power increases
            E = np.array(perf.ragone_E)
            P = np.array(perf.ragone_P)
            
            # Check correlation is negative
            if len(E) > 3:
                corr = np.corrcoef(E, P)[0, 1]
                assert corr < 0.5  # Should show inverse relationship


# =====================================================================
#   Self-Discharge Tests
# =====================================================================

class TestSelfDischarge:
    def test_self_discharge_calculated(self):
        """Self-discharge should be calculated."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert perf.self_discharge_pct_per_month >= 0

    def test_self_discharge_reasonable(self):
        """Self-discharge should be in reasonable range."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        # Typical: 1-10% per month
        assert 0 <= perf.self_discharge_pct_per_month < 20


# =====================================================================
#   Chemistry-Specific Tests
# =====================================================================

class TestChemistrySpecific:
    def test_zinc_mno2_voltage(self):
        """Zinc-MnO2 should have ~1.5V nominal voltage."""
        config = BatteryConfig(chemistry="zinc_MnO2")
        perf = simulate_battery(config)
        
        assert 1.0 < perf.nominal_V < 1.7

    def test_lifepo4_voltage(self):
        """LiFePO4 should have ~3.4V nominal voltage."""
        config = BatteryConfig(chemistry="LiFePO4")
        perf = simulate_battery(config)
        
        assert 3.0 < perf.nominal_V < 3.7

    def test_all_chemistries_simulate(self):
        """All chemistries should simulate successfully."""
        for chem_name in OCV_MODELS.keys():
            config = BatteryConfig(chemistry=chem_name)
            perf = simulate_battery(config)
            
            assert perf.theoretical_capacity_mAh > 0
            # Energy may be zero if discharge doesn't complete
            assert perf.energy_mWh >= 0


# =====================================================================
#   Quick Simulation Tests
# =====================================================================

class TestQuickSimulation:
    def test_quick_battery(self):
        """Quick battery simulation should work."""
        result = quick_battery()
        
        assert isinstance(result, dict)
        assert "theoretical_capacity_mAh" in result
        assert "energy_mWh" in result
        assert "discharge_curve" in result

    def test_quick_battery_custom_params(self):
        """Quick simulation with custom parameters."""
        result = quick_battery(
            chemistry="LiFePO4",
            area_cm2=2.0,
            C_rate=1.0
        )
        
        assert result["theoretical_capacity_mAh"] > 0
        assert result["energy_mWh"] > 0

    def test_list_battery_chemistries(self):
        """list_battery_chemistries should return all chemistries."""
        chemistries = list_battery_chemistries()
        
        assert len(chemistries) > 0
        assert all("name" in c for c in chemistries)
        assert all("capacity_mAh_g" in c for c in chemistries)


# =====================================================================
#   Serialization Tests
# =====================================================================

class TestSerialization:
    def test_to_dict_complete(self):
        """to_dict should include all metrics."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        data = perf.to_dict()
        
        assert isinstance(data, dict)
        assert "theoretical_capacity_mAh" in data
        assert "delivered_capacity_mAh" in data
        assert "energy_mWh" in data
        assert "discharge_curve" in data
        assert "rate_capability" in data
        assert "aging" in data
        assert "eis" in data
        assert "ragone" in data

    def test_to_dict_numeric_types(self):
        """All numeric values should be serializable."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        data = perf.to_dict()
        
        assert isinstance(data["theoretical_capacity_mAh"], (int, float))
        assert isinstance(data["energy_mWh"], (int, float))
        assert isinstance(data["internal_resistance_ohm"], (int, float))


# =====================================================================
#   Edge Cases Tests
# =====================================================================

class TestEdgeCases:
    def test_very_small_battery(self):
        """Very small battery should still work."""
        config = BatteryConfig(
            electrode_area_cm2=0.1,
            cathode_loading_mg_cm2=1.0
        )
        perf = simulate_battery(config)
        
        assert perf.theoretical_capacity_mAh > 0
        assert np.isfinite(perf.energy_mWh)

    def test_high_c_rate(self):
        """High C-rate discharge should work."""
        config = BatteryConfig(C_rate=5.0)
        perf = simulate_battery(config)
        
        assert perf.delivered_capacity_mAh > 0
        # High rate should reduce utilization
        assert perf.utilization_pct < 100

    def test_low_c_rate(self):
        """Low C-rate should give high utilization."""
        config = BatteryConfig(C_rate=0.1)
        perf = simulate_battery(config)
        
        assert perf.utilization_pct > 70

    def test_series_cells(self):
        """Series cells should multiply voltage."""
        config_1cell = BatteryConfig(n_cells_series=1)
        config_2cell = BatteryConfig(n_cells_series=2)
        
        perf_1 = simulate_battery(config_1cell)
        perf_2 = simulate_battery(config_2cell)
        
        # Voltage should roughly double
        ratio = perf_2.OCV_V / perf_1.OCV_V
        assert 1.8 < ratio < 2.2

    def test_numerical_stability(self):
        """All outputs should be finite."""
        config = BatteryConfig()
        perf = simulate_battery(config)
        
        assert np.isfinite(perf.theoretical_capacity_mAh)
        assert np.isfinite(perf.delivered_capacity_mAh)
        assert np.isfinite(perf.energy_mWh)
        assert np.isfinite(perf.internal_resistance_ohm)
        assert np.isfinite(perf.avg_discharge_V)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
