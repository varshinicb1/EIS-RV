"""
Supercapacitor Device Engine Tests
====================================
Unit tests for full-cell supercapacitor device simulation: capacitance,
ESR, energy/power density, GCD, Ragone plot, EIS, and cycling stability.

Run with:
    python -m pytest vanl/backend/tests/test_supercap_device_engine.py -v
"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from vanl.backend.core.supercap_device_engine import (
    ElectrodeSpec,
    ElectrolyteSpec,
    DeviceConfig,
    DevicePerformance,
    simulate_device,
    quick_supercap_simulation,
)


# =====================================================================
#   ElectrodeSpec Tests
# =====================================================================

class TestElectrodeSpec:
    def test_default_electrode(self):
        """Default electrode should be valid."""
        electrode = ElectrodeSpec()
        assert electrode.material_name == "activated_carbon"
        assert electrode.specific_capacitance_F_g > 0
        assert electrode.thickness_um > 0

    def test_area_calculation(self):
        """Area calculation should be correct."""
        electrode = ElectrodeSpec(length_mm=10, width_mm=5)
        assert electrode.area_cm2() == 0.5  # 10*5/100

    def test_thickness_conversion(self):
        """Thickness conversion should be correct."""
        electrode = ElectrodeSpec(thickness_um=100)
        assert electrode.thickness_cm() == 0.01  # 100e-4

    def test_mass_conversion(self):
        """Mass conversion should be correct."""
        electrode = ElectrodeSpec(active_mass_mg=10)
        assert electrode.mass_g() == 0.01  # 10e-3


# =====================================================================
#   ElectrolyteSpec Tests
# =====================================================================

class TestElectrolyteSpec:
    def test_default_electrolyte(self):
        """Default electrolyte should be valid."""
        electrolyte = ElectrolyteSpec()
        assert electrolyte.conductivity_S_m > 0
        assert electrolyte.voltage_window_V > 0

    def test_custom_electrolyte(self):
        """Custom electrolyte should be accepted."""
        electrolyte = ElectrolyteSpec(
            name="6M KOH",
            conductivity_S_m=60.0,
            voltage_window_V=1.2
        )
        assert electrolyte.name == "6M KOH"
        assert electrolyte.conductivity_S_m == 60.0


# =====================================================================
#   DeviceConfig Tests
# =====================================================================

class TestDeviceConfig:
    def test_default_config(self):
        """Default config should be valid symmetric device."""
        config = DeviceConfig()
        assert config.is_symmetric
        assert config.electrode_pos is not None
        assert config.electrode_neg is not None

    def test_symmetric_device(self):
        """Symmetric device should have same electrodes."""
        config = DeviceConfig(is_symmetric=True)
        assert config.is_symmetric


# =====================================================================
#   Full Device Simulation Tests
# =====================================================================

class TestDeviceSimulation:
    def test_basic_simulation(self):
        """Basic device simulation should produce valid results."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert isinstance(perf, DevicePerformance)
        assert perf.C_device_F > 0
        assert perf.ESR_ohm > 0
        assert perf.energy_Wh_kg > 0
        assert perf.power_W_kg > 0

    def test_symmetric_capacitance(self):
        """Symmetric device: C_device = C_electrode / 2."""
        electrode = ElectrodeSpec(
            specific_capacitance_F_g=150,
            active_mass_mg=1.0
        )
        config = DeviceConfig(
            electrode_pos=electrode,
            electrode_neg=electrode,
            is_symmetric=True
        )
        perf = simulate_device(config)
        
        C_electrode = 150 * 0.001  # F
        expected_C = C_electrode / 2
        assert abs(perf.C_device_F - expected_C) / expected_C < 0.1

    def test_specific_capacitance(self):
        """Specific capacitance should be normalized by mass."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        total_mass_g = (config.electrode_pos.mass_g() + 
                       config.electrode_neg.mass_g())
        expected_C_specific = perf.C_device_F / total_mass_g
        
        assert abs(perf.C_specific_F_g - expected_C_specific) / expected_C_specific < 0.1

    def test_areal_capacitance(self):
        """Areal capacitance should be normalized by area."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        area_cm2 = config.electrode_pos.area_cm2()
        expected_C_areal = perf.C_device_F * 1e3 / area_cm2  # mF/cm²
        
        assert abs(perf.C_areal_mF_cm2 - expected_C_areal) / expected_C_areal < 0.1

    def test_mass_affects_capacitance(self):
        """Higher mass should give higher device capacitance."""
        electrode_small = ElectrodeSpec(active_mass_mg=0.5)
        electrode_large = ElectrodeSpec(active_mass_mg=2.0)
        
        config_small = DeviceConfig(
            electrode_pos=electrode_small,
            electrode_neg=electrode_small
        )
        config_large = DeviceConfig(
            electrode_pos=electrode_large,
            electrode_neg=electrode_large
        )
        
        perf_small = simulate_device(config_small)
        perf_large = simulate_device(config_large)
        
        assert perf_large.C_device_F > perf_small.C_device_F


# =====================================================================
#   ESR Tests
# =====================================================================

class TestESR:
    def test_esr_positive(self):
        """ESR should be positive."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert perf.ESR_ohm > 0

    def test_esr_breakdown(self):
        """ESR breakdown should sum to total ESR."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert len(perf.ESR_breakdown) > 0
        total_from_breakdown = sum(perf.ESR_breakdown.values())
        
        assert abs(total_from_breakdown - perf.ESR_ohm) / perf.ESR_ohm < 0.01

    def test_esr_components_positive(self):
        """All ESR components should be positive."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        for component, value in perf.ESR_breakdown.items():
            assert value >= 0, f"{component} should be non-negative"

    def test_conductivity_affects_esr(self):
        """Higher conductivity should reduce ESR."""
        electrode_low = ElectrodeSpec(conductivity_S_m=100)
        electrode_high = ElectrodeSpec(conductivity_S_m=10000)
        
        config_low = DeviceConfig(
            electrode_pos=electrode_low,
            electrode_neg=electrode_low
        )
        config_high = DeviceConfig(
            electrode_pos=electrode_high,
            electrode_neg=electrode_high
        )
        
        perf_low = simulate_device(config_low)
        perf_high = simulate_device(config_high)
        
        assert perf_low.ESR_ohm > perf_high.ESR_ohm


# =====================================================================
#   Energy & Power Tests
# =====================================================================

class TestEnergyPower:
    def test_energy_calculation(self):
        """Energy should be E = 0.5 * C * V²."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        C = perf.C_device_F
        V = perf.voltage_window_V
        total_mass_g = (config.electrode_pos.mass_g() + 
                       config.electrode_neg.mass_g())
        
        E_J = 0.5 * C * V**2
        E_Wh_kg_expected = E_J / (3600 * total_mass_g * 1e-3)
        
        assert abs(perf.energy_Wh_kg - E_Wh_kg_expected) / E_Wh_kg_expected < 0.1

    def test_power_calculation(self):
        """Power should be P = V²/(4*ESR)."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        V = perf.voltage_window_V
        ESR = perf.ESR_ohm
        total_mass_g = (config.electrode_pos.mass_g() + 
                       config.electrode_neg.mass_g())
        
        P_W = V**2 / (4 * ESR)
        P_W_kg_expected = P_W / (total_mass_g * 1e-3)
        
        assert abs(perf.power_W_kg - P_W_kg_expected) / P_W_kg_expected < 0.2

    def test_voltage_window_affects_energy(self):
        """Larger voltage window should give higher energy."""
        electrolyte_1V = ElectrolyteSpec(voltage_window_V=1.0)
        electrolyte_2V = ElectrolyteSpec(voltage_window_V=2.0)
        
        config_1V = DeviceConfig(electrolyte=electrolyte_1V)
        config_2V = DeviceConfig(electrolyte=electrolyte_2V)
        
        perf_1V = simulate_device(config_1V)
        perf_2V = simulate_device(config_2V)
        
        # E ∝ V², so 2x voltage → 4x energy
        ratio = perf_2V.energy_Wh_kg / perf_1V.energy_Wh_kg
        assert 3.5 < ratio < 4.5

    def test_max_current_calculated(self):
        """Max current should be calculated."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert perf.max_current_A > 0


# =====================================================================
#   GCD Waveform Tests
# =====================================================================

class TestGCDWaveform:
    def test_gcd_generated(self):
        """GCD waveform should be generated."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert len(perf.gcd_time_s) > 0
        assert len(perf.gcd_voltage_V) > 0

    def test_gcd_arrays_same_length(self):
        """GCD time and voltage arrays should have same length."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert len(perf.gcd_time_s) == len(perf.gcd_voltage_V)

    def test_gcd_voltage_range(self):
        """GCD voltage should be within 0 to V_max."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        V_max = config.electrolyte.voltage_window_V
        voltages = np.array(perf.gcd_voltage_V)
        
        assert all(0 <= v <= V_max * 1.1 for v in voltages)

    def test_gcd_time_monotonic(self):
        """GCD time should increase monotonically."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        times = np.array(perf.gcd_time_s)
        assert all(times[i+1] >= times[i] for i in range(len(times)-1))

    def test_gcd_shows_cycles(self):
        """GCD should show charge-discharge cycles."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        voltages = np.array(perf.gcd_voltage_V)
        # Should have both increasing and decreasing segments
        diffs = np.diff(voltages)
        has_increase = any(diffs > 0)
        has_decrease = any(diffs < 0)
        
        assert has_increase and has_decrease


# =====================================================================
#   Ragone Plot Tests
# =====================================================================

class TestRagonePlot:
    def test_ragone_generated(self):
        """Ragone plot data should be generated."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert len(perf.ragone_E_Wh_kg) > 0
        assert len(perf.ragone_P_W_kg) > 0

    def test_ragone_arrays_same_length(self):
        """Ragone E and P arrays should have same length."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert len(perf.ragone_E_Wh_kg) == len(perf.ragone_P_W_kg)

    def test_ragone_tradeoff(self):
        """Ragone plot should show energy-power tradeoff."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        if len(perf.ragone_E_Wh_kg) > 2:
            E = np.array(perf.ragone_E_Wh_kg)
            P = np.array(perf.ragone_P_W_kg)
            
            # Energy should generally decrease as power increases
            # (inverse relationship)
            assert E[0] > E[-1] or P[0] < P[-1]

    def test_ragone_values_positive(self):
        """All Ragone values should be positive."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert all(e > 0 for e in perf.ragone_E_Wh_kg)
        assert all(p > 0 for p in perf.ragone_P_W_kg)


# =====================================================================
#   EIS Tests
# =====================================================================

class TestDeviceEIS:
    def test_eis_generated(self):
        """EIS data should be generated."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert len(perf.eis_freq) > 0
        assert len(perf.eis_Z_real) > 0
        assert len(perf.eis_Z_imag) > 0

    def test_eis_arrays_same_length(self):
        """EIS arrays should have same length."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        n = len(perf.eis_freq)
        assert len(perf.eis_Z_real) == n
        assert len(perf.eis_Z_imag) == n

    def test_eis_frequencies_increasing(self):
        """EIS frequencies should be in increasing order."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        freqs = np.array(perf.eis_freq)
        assert all(freqs[i+1] >= freqs[i] for i in range(len(freqs)-1))

    def test_eis_high_freq_limit(self):
        """At high frequency, Z_real should approach ESR."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        # First point is lowest frequency in our implementation
        # Last point is highest frequency
        Z_real_high_f = perf.eis_Z_real[-1]
        
        # Should be close to ESR
        assert Z_real_high_f < perf.ESR_ohm * 2


# =====================================================================
#   Cycling Stability Tests
# =====================================================================

class TestCyclingStability:
    def test_retention_calculated(self):
        """Capacity retention should be calculated."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert perf.retention_1000 > 0
        assert perf.retention_10000 > 0

    def test_retention_decreases(self):
        """Retention should decrease with more cycles."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert perf.retention_10000 <= perf.retention_1000

    def test_retention_bounded(self):
        """Retention should be between 0 and 100%."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert 0 <= perf.retention_1000 <= 100
        assert 0 <= perf.retention_10000 <= 100

    def test_temperature_affects_stability(self):
        """Higher temperature should reduce stability."""
        config_low = DeviceConfig(temperature_C=25)
        config_high = DeviceConfig(temperature_C=60)
        
        perf_low = simulate_device(config_low)
        perf_high = simulate_device(config_high)
        
        assert perf_low.retention_10000 >= perf_high.retention_10000


# =====================================================================
#   Self-Discharge Tests
# =====================================================================

class TestSelfDischarge:
    def test_self_discharge_calculated(self):
        """Self-discharge should be calculated."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert perf.self_discharge_V_per_hour >= 0
        assert perf.voltage_after_24h_pct >= 0

    def test_voltage_retention_bounded(self):
        """Voltage after 24h should be between 0 and 100%."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert 0 <= perf.voltage_after_24h_pct <= 100

    def test_electrolyte_affects_self_discharge(self):
        """Organic electrolyte should have lower self-discharge than aqueous."""
        electrolyte_aqueous = ElectrolyteSpec(type="aqueous")
        electrolyte_organic = ElectrolyteSpec(type="organic")
        
        config_aqueous = DeviceConfig(electrolyte=electrolyte_aqueous)
        config_organic = DeviceConfig(electrolyte=electrolyte_organic)
        
        perf_aqueous = simulate_device(config_aqueous)
        perf_organic = simulate_device(config_organic)
        
        assert perf_organic.voltage_after_24h_pct >= perf_aqueous.voltage_after_24h_pct


# =====================================================================
#   CV Tests
# =====================================================================

class TestCV:
    def test_cv_data_generated(self):
        """CV data should be generated for multiple scan rates."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert len(perf.cv_data) > 0

    def test_cv_multiple_scan_rates(self):
        """CV should be generated for multiple scan rates."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert len(perf.cv_data) >= 3  # At least 3 scan rates

    def test_cv_data_structure(self):
        """Each CV should have E and i arrays."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        for scan_rate, data in perf.cv_data.items():
            assert "E_V" in data
            assert "i_A" in data
            assert len(data["E_V"]) == len(data["i_A"])

    def test_cv_rectangular_shape(self):
        """CV should show approximately rectangular shape for EDLC."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        # Get first scan rate data
        first_cv = list(perf.cv_data.values())[0]
        currents = np.array(first_cv["i_A"])
        
        # Should have both positive and negative currents
        assert any(currents > 0) and any(currents < 0)


# =====================================================================
#   Quick Simulation Tests
# =====================================================================

class TestQuickSimulation:
    def test_quick_simulation(self):
        """Quick simulation should work."""
        result = quick_supercap_simulation()
        
        assert isinstance(result, dict)
        assert "C_device_F" in result
        assert "energy_Wh_kg" in result
        assert "ESR_ohm" in result

    def test_quick_simulation_custom_params(self):
        """Quick simulation with custom parameters."""
        result = quick_supercap_simulation(
            material="activated_carbon",
            capacitance_F_g=200,
            mass_mg=2.0,
            voltage_V=1.2
        )
        
        assert result["C_device_F"] > 0
        assert result["energy_Wh_kg"] > 0


# =====================================================================
#   Serialization Tests
# =====================================================================

class TestSerialization:
    def test_to_dict_complete(self):
        """to_dict should include all metrics."""
        config = DeviceConfig()
        perf = simulate_device(config)
        data = perf.to_dict()
        
        assert isinstance(data, dict)
        assert "C_device_F" in data
        assert "ESR_ohm" in data
        assert "energy_Wh_kg" in data
        assert "power_W_kg" in data
        assert "gcd" in data
        assert "ragone" in data
        assert "eis" in data
        assert "cv_data" in data

    def test_to_dict_numeric_types(self):
        """All numeric values should be serializable."""
        config = DeviceConfig()
        perf = simulate_device(config)
        data = perf.to_dict()
        
        assert isinstance(data["C_device_F"], (int, float))
        assert isinstance(data["ESR_ohm"], (int, float))
        assert isinstance(data["energy_Wh_kg"], (int, float))


# =====================================================================
#   Edge Cases Tests
# =====================================================================

class TestEdgeCases:
    def test_very_small_device(self):
        """Very small device should still work."""
        electrode = ElectrodeSpec(active_mass_mg=0.1)
        config = DeviceConfig(
            electrode_pos=electrode,
            electrode_neg=electrode
        )
        perf = simulate_device(config)
        
        assert perf.C_device_F > 0
        assert np.isfinite(perf.energy_Wh_kg)

    def test_very_large_device(self):
        """Very large device should still work."""
        electrode = ElectrodeSpec(
            active_mass_mg=100,
            length_mm=100,
            width_mm=100
        )
        config = DeviceConfig(
            electrode_pos=electrode,
            electrode_neg=electrode
        )
        perf = simulate_device(config)
        
        assert perf.C_device_F > 0
        assert np.isfinite(perf.energy_Wh_kg)

    def test_high_capacitance_material(self):
        """High capacitance material should work."""
        electrode = ElectrodeSpec(specific_capacitance_F_g=500)
        config = DeviceConfig(
            electrode_pos=electrode,
            electrode_neg=electrode
        )
        perf = simulate_device(config)
        
        assert perf.C_specific_F_g > 100  # Should be reasonably high

    def test_low_conductivity(self):
        """Low conductivity should increase ESR."""
        electrode = ElectrodeSpec(conductivity_S_m=1)
        config = DeviceConfig(
            electrode_pos=electrode,
            electrode_neg=electrode
        )
        perf = simulate_device(config)
        
        assert perf.ESR_ohm > 1  # Should be relatively high

    def test_different_electrolyte_types(self):
        """All electrolyte types should work."""
        for elec_type in ["aqueous", "organic", "ionic_liquid", "gel", "solid"]:
            electrolyte = ElectrolyteSpec(type=elec_type)
            config = DeviceConfig(electrolyte=electrolyte)
            perf = simulate_device(config)
            
            assert perf.C_device_F > 0
            assert perf.energy_Wh_kg > 0

    def test_numerical_stability(self):
        """All outputs should be finite."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert np.isfinite(perf.C_device_F)
        assert np.isfinite(perf.ESR_ohm)
        assert np.isfinite(perf.energy_Wh_kg)
        assert np.isfinite(perf.power_W_kg)
        assert all(np.isfinite(v) for v in perf.gcd_voltage_V)
        assert all(np.isfinite(v) for v in perf.eis_Z_real)


# =====================================================================
#   Performance Metrics Tests
# =====================================================================

class TestPerformanceMetrics:
    def test_charge_discharge_time(self):
        """Charge and discharge times should be calculated."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert perf.charge_time_s > 0
        assert perf.discharge_time_s > 0

    def test_volumetric_capacitance(self):
        """Volumetric capacitance should be calculated."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert perf.C_volumetric_F_cm3 > 0

    def test_areal_energy(self):
        """Areal energy density should be calculated."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert perf.energy_mWh_cm2 > 0

    def test_areal_power(self):
        """Areal power density should be calculated."""
        config = DeviceConfig()
        perf = simulate_device(config)
        
        assert perf.power_mW_cm2 > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
