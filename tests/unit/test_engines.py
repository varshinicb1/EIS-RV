"""
Test FastAPI v2 endpoints — Battery & GCD simulation API.
Validates that the new server routes return correct data shapes.
"""

import pytest
import numpy as np
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestBatteryEngine:
    """Validate battery simulation via direct engine call."""

    def test_zinc_mno2_discharge(self):
        from src.backend.core.engines.battery_engine import BatteryConfig, simulate_battery

        config = BatteryConfig(chemistry="zinc_MnO2", electrode_area_cm2=1.0, C_rate=0.5)
        result = simulate_battery(config)

        assert result.delivered_capacity_mAh > 0
        assert result.energy_mWh > 0
        assert result.utilization_pct > 30  # Reasonable utilization
        assert len(result.discharge_V) > 10
        assert result.internal_resistance_ohm > 0

    def test_lithium_chemistry(self):
        from src.backend.core.engines.battery_engine import BatteryConfig, simulate_battery

        config = BatteryConfig(
            chemistry="LiFePO4",
            cathode_capacity_mAh_g=170,
            anode_capacity_mAh_g=372,
            cutoff_V=2.5,
            max_V=3.65,
            electrolyte_type="organic",
        )
        result = simulate_battery(config)
        assert result.OCV_V > 2.5  # LFP should have OCV above cutoff

    def test_ragone_data(self):
        from src.backend.core.engines.battery_engine import BatteryConfig, simulate_battery

        config = BatteryConfig(chemistry="zinc_MnO2")
        result = simulate_battery(config)
        assert len(result.ragone_E) > 3
        assert len(result.ragone_P) == len(result.ragone_E)
        # Energy should be positive
        assert all(e > 0 for e in result.ragone_E)

    def test_rate_capability(self):
        from src.backend.core.engines.battery_engine import BatteryConfig, simulate_battery

        config = BatteryConfig(chemistry="zinc_MnO2")
        result = simulate_battery(config)
        assert "0.5C" in result.rate_capacity
        assert result.rate_capacity["0.1C"] >= result.rate_capacity["5.0C"]

    def test_discharge_curve_monotonic(self):
        from src.backend.core.engines.battery_engine import BatteryConfig, simulate_battery

        config = BatteryConfig(chemistry="zinc_MnO2", C_rate=1.0)
        result = simulate_battery(config)
        V = result.discharge_V
        # Voltage should generally decrease (allowing small numerical noise)
        diffs = [V[i+1] - V[i] for i in range(len(V) - 1)]
        # Most differences should be negative (decreasing voltage)
        assert sum(1 for d in diffs if d <= 0.001) > len(diffs) * 0.9


class TestGCDEngine:
    """Validate GCD simulation engine."""

    def test_basic_edlc(self):
        from src.backend.core.engines.gcd_engine import GCDParameters, simulate_gcd

        params = GCDParameters(
            Cdl_F=1e-3,
            current_A=1e-3,
            V_max=1.0,
            n_cycles=3,
            active_mass_mg=1.0,
        )
        result = simulate_gcd(params)
        assert len(result.time) > 10
        assert len(result.voltage) == len(result.time)
        assert result.avg_specific_capacitance_F_g > 0

    def test_pseudocapacitance(self):
        from src.backend.core.engines.gcd_engine import GCDParameters, simulate_gcd

        params = GCDParameters(
            Cdl_F=2e-3,
            C_pseudo_F=5e-3,
            current_A=0.5e-3,
            V_max=0.8,
            n_cycles=2,
            active_mass_mg=1.0,
        )
        result = simulate_gcd(params)
        # Pseudocap should increase capacitance
        assert result.avg_specific_capacitance_F_g > 0

    def test_cycle_data(self):
        from src.backend.core.engines.gcd_engine import GCDParameters, simulate_gcd

        params = GCDParameters(Cdl_F=5e-3, current_A=5e-3, V_max=1.0, n_cycles=5)
        result = simulate_gcd(params)
        assert len(result.cycle_data) >= 3  # At least 3 complete cycles
        for cd in result.cycle_data:
            assert cd["specific_capacitance_F_g"] >= 0
            assert cd["coulombic_efficiency_pct"] > 50

    def test_coulombic_efficiency(self):
        from src.backend.core.engines.gcd_engine import GCDParameters, simulate_gcd

        params = GCDParameters(
            Cdl_F=10e-3,
            Rs_ohm=0.5,
            Rct_ohm=2.0,
            current_A=10e-3,
            V_max=1.0,
            n_cycles=3,
            active_mass_mg=2.0,
        )
        result = simulate_gcd(params)
        # With low resistance, efficiency should be high
        assert result.avg_coulombic_efficiency_pct > 80

    def test_voltage_within_bounds(self):
        from src.backend.core.engines.gcd_engine import GCDParameters, simulate_gcd

        params = GCDParameters(Cdl_F=1e-3, V_min=0.0, V_max=1.0, n_cycles=2)
        result = simulate_gcd(params)
        assert all(0 <= v <= 1.1 for v in result.voltage)  # Small tolerance


class TestSupercapDeviceEngine:
    """Validate supercapacitor device simulation."""

    def test_basic_device(self):
        from src.backend.core.engines.supercap_device_engine import DeviceConfig, simulate_device

        config = DeviceConfig()
        perf = simulate_device(config)
        assert perf.C_device_F > 0
        assert perf.ESR_ohm > 0
        assert perf.energy_Wh_kg > 0
        assert perf.power_W_kg > 0

    def test_ragone_plot(self):
        from src.backend.core.engines.supercap_device_engine import DeviceConfig, simulate_device

        config = DeviceConfig()
        perf = simulate_device(config)
        assert len(perf.ragone_E_Wh_kg) > 5
        assert len(perf.ragone_P_W_kg) == len(perf.ragone_E_Wh_kg)

    def test_eis_data(self):
        from src.backend.core.engines.supercap_device_engine import DeviceConfig, simulate_device

        config = DeviceConfig()
        perf = simulate_device(config)
        assert len(perf.eis_freq) == 80
        assert len(perf.eis_Z_real) == 80
        assert len(perf.eis_Z_imag) == 80


class TestAPISchema:
    """Test that API response schemas match expected frontend format."""

    def test_battery_to_dict(self):
        from src.backend.core.engines.battery_engine import BatteryConfig, simulate_battery

        config = BatteryConfig()
        result = simulate_battery(config)
        d = result.to_dict()
        # Verify all required keys
        assert "theoretical_capacity_mAh" in d
        assert "delivered_capacity_mAh" in d
        assert "discharge_curve" in d
        assert "SOC" in d["discharge_curve"]
        assert "ragone" in d
        assert "eis" in d

    def test_gcd_to_dict(self):
        from src.backend.core.engines.gcd_engine import GCDParameters, simulate_gcd

        params = GCDParameters(Cdl_F=1e-3, n_cycles=2)
        result = simulate_gcd(params)
        d = result.to_dict()
        assert "time_s" in d
        assert "voltage_V" in d
        assert "summary" in d
        assert "specific_capacitance_F_g" in d["summary"]
