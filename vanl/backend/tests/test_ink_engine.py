"""
Ink Formulation & Rheology Engine Tests
=========================================
Unit tests for ink formulation, rheology models, percolation theory,
printability analysis, and film formation.

Run with:
    python -m pytest vanl/backend/tests/test_ink_engine.py -v
"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from vanl.backend.core.ink_engine import (
    InkFormulation,
    InkProperties,
    PrintMethod,
    SolventType,
    SOLVENT_DB,
    PRINT_WINDOWS,
    simulate_ink,
    rheology_curve,
    percolation_curve,
    krieger_dougherty_viscosity,
    herschel_bulkley,
    cross_model,
    percolation_threshold,
    percolation_conductivity,
    printability_numbers,
    film_drying_time,
    coffee_ring_assessment,
    sedimentation_rate,
    list_solvents,
    list_print_methods,
)


# =====================================================================
#   InkFormulation Tests
# =====================================================================

class TestInkFormulation:
    def test_default_formulation(self):
        """Default formulation should be valid."""
        ink = InkFormulation()
        assert ink.filler_material == "graphene"
        assert ink.filler_loading_wt_pct == 5.0
        assert ink.primary_solvent == "water"
        assert ink.print_method == PrintMethod.SCREEN

    def test_filler_vol_fraction_conversion(self):
        """Weight % to volume fraction conversion."""
        ink = InkFormulation(filler_loading_wt_pct=10.0)
        phi = ink.filler_vol_fraction()
        assert 0 < phi < 1
        assert phi < 0.1  # Should be less than wt% due to density difference

    def test_high_loading(self):
        """High filler loading should give higher volume fraction."""
        ink_low = InkFormulation(filler_loading_wt_pct=1.0)
        ink_high = InkFormulation(filler_loading_wt_pct=20.0)
        assert ink_high.filler_vol_fraction() > ink_low.filler_vol_fraction()

    def test_co_solvent_mixing(self):
        """Co-solvent should be properly handled."""
        ink = InkFormulation(
            primary_solvent="water",
            co_solvent="ethanol",
            co_solvent_fraction=0.3
        )
        assert ink.co_solvent == "ethanol"
        assert ink.co_solvent_fraction == 0.3


# =====================================================================
#   Rheology Models Tests
# =====================================================================

class TestRheologyModels:
    def test_krieger_dougherty_zero_loading(self):
        """Zero particle loading should give solvent viscosity."""
        eta_solv = 1e-3  # Pa·s
        eta = krieger_dougherty_viscosity(eta_solv, phi=0.0)
        assert abs(eta - eta_solv) < 1e-10

    def test_krieger_dougherty_increases_with_loading(self):
        """Viscosity should increase with particle loading."""
        eta_solv = 1e-3
        eta_low = krieger_dougherty_viscosity(eta_solv, phi=0.05)
        eta_high = krieger_dougherty_viscosity(eta_solv, phi=0.3)
        assert eta_high > eta_low > eta_solv

    def test_krieger_dougherty_diverges_at_phi_max(self):
        """Viscosity should diverge near maximum packing."""
        eta_solv = 1e-3
        eta = krieger_dougherty_viscosity(eta_solv, phi=0.63, phi_max=0.64)
        assert eta > eta_solv * 100  # Should be very high

    def test_herschel_bulkley_shape(self):
        """Herschel-Bulkley should give shear-thinning behavior."""
        shear_rates = np.logspace(0, 3, 50)
        eta = herschel_bulkley(shear_rates, tau_y=1.0, K=0.5, n=0.7)
        assert len(eta) == len(shear_rates)
        assert all(np.isfinite(eta))
        # Shear-thinning: viscosity decreases with shear rate
        assert eta[0] > eta[-1]

    def test_cross_model_limits(self):
        """Cross model should approach eta_0 at low shear, eta_inf at high shear."""
        eta_0 = 100.0
        eta_inf = 1.0
        shear_low = np.array([1e-3])
        shear_high = np.array([1e6])
        
        eta_low = cross_model(shear_low, eta_0, eta_inf, lambda_c=1.0, m=0.8)
        eta_high = cross_model(shear_high, eta_0, eta_inf, lambda_c=1.0, m=0.8)
        
        assert abs(eta_low[0] - eta_0) < 5  # Close to eta_0
        assert abs(eta_high[0] - eta_inf) < 1  # Close to eta_inf


# =====================================================================
#   Percolation Theory Tests
# =====================================================================

class TestPercolationTheory:
    def test_percolation_threshold_spheres(self):
        """Spheres should have percolation threshold ~0.16."""
        phi_c = percolation_threshold(aspect_ratio=1.0)
        assert 0.15 < phi_c < 0.17

    def test_percolation_threshold_high_aspect_ratio(self):
        """High aspect ratio fillers should have lower percolation threshold."""
        phi_c_spheres = percolation_threshold(aspect_ratio=1.0)
        phi_c_rods = percolation_threshold(aspect_ratio=100.0)
        assert phi_c_rods < phi_c_spheres

    def test_percolation_conductivity_below_threshold(self):
        """Below percolation, conductivity should be near zero."""
        phi_c = 0.01
        sigma = percolation_conductivity(phi=0.005, phi_c=phi_c, sigma_filler=1e6)
        assert sigma < 1e-5

    def test_percolation_conductivity_above_threshold(self):
        """Above percolation, conductivity should increase with loading."""
        phi_c = 0.01
        sigma_low = percolation_conductivity(phi=0.015, phi_c=phi_c, sigma_filler=1e6)
        sigma_high = percolation_conductivity(phi=0.05, phi_c=phi_c, sigma_filler=1e6)
        assert sigma_high > sigma_low > 1e-5

    def test_percolation_curve_generation(self):
        """Percolation curve should show transition."""
        data = percolation_curve("graphene", aspect_ratio=100, n_points=50)
        assert len(data["vol_fraction_pct"]) == 50
        assert len(data["conductivity_S_m"]) == 50
        assert data["percolation_threshold_vol_pct"] > 0
        # Conductivity should jump at percolation
        conductivities = np.array(data["conductivity_S_m"])
        assert conductivities[-1] > conductivities[0] * 100


# =====================================================================
#   Printability Analysis Tests
# =====================================================================

class TestPrintabilityAnalysis:
    def test_printability_numbers_calculation(self):
        """Printability numbers should be dimensionless and positive."""
        Oh, Re, We, Z = printability_numbers(
            density_kg_m3=1000,
            viscosity_Pas=0.01,
            surface_tension_N_m=0.05,
            drop_diameter_m=50e-6,
            velocity_m_s=5.0
        )
        assert Oh > 0
        assert Re > 0
        assert We > 0
        assert Z > 0
        assert abs(Z - 1/Oh) < 0.01  # Z = 1/Oh

    def test_inkjet_printability_window(self):
        """Inkjet should have Z between 1 and 10 for good jetting."""
        # Good inkjet ink
        Oh, Re, We, Z = printability_numbers(
            density_kg_m3=1000,
            viscosity_Pas=0.01,
            surface_tension_N_m=0.03,
            drop_diameter_m=50e-6,
            velocity_m_s=5.0
        )
        assert 1 < Z < 10  # Derby criterion

    def test_print_windows_exist(self):
        """All print methods should have defined windows."""
        for method in PrintMethod:
            assert method in PRINT_WINDOWS
            window = PRINT_WINDOWS[method]
            assert "shear_rate_range" in window
            assert "viscosity_range_Pas" in window
            assert "film_thickness_um" in window


# =====================================================================
#   Film Formation & Drying Tests
# =====================================================================

class TestFilmFormation:
    def test_drying_time_increases_with_thickness(self):
        """Thicker films should take longer to dry."""
        t_thin = film_drying_time(wet_thickness_um=10, evap_rate_rel=1.0)
        t_thick = film_drying_time(wet_thickness_um=100, evap_rate_rel=1.0)
        assert t_thick > t_thin

    def test_drying_time_decreases_with_temperature(self):
        """Higher temperature should speed up drying."""
        t_low = film_drying_time(wet_thickness_um=50, evap_rate_rel=1.0, temperature_C=25)
        t_high = film_drying_time(wet_thickness_um=50, evap_rate_rel=1.0, temperature_C=80)
        assert t_high < t_low

    def test_coffee_ring_assessment(self):
        """Coffee ring risk should be assessed correctly."""
        # High risk: low contact angle + high evaporation
        risk_high = coffee_ring_assessment(contact_angle_deg=15, evap_rate_rel=3.0, particle_size_nm=100)
        assert risk_high == "high"
        
        # Low risk: high contact angle + low evaporation
        risk_low = coffee_ring_assessment(contact_angle_deg=60, evap_rate_rel=0.5, particle_size_nm=100)
        assert risk_low == "low"

    def test_sedimentation_rate_stokes(self):
        """Larger particles should sediment faster."""
        v_small = sedimentation_rate(
            particle_size_m=100e-9,
            density_particle=2200,
            density_fluid=1000,
            viscosity_Pas=0.001
        )
        v_large = sedimentation_rate(
            particle_size_m=1e-6,
            density_particle=2200,
            density_fluid=1000,
            viscosity_Pas=0.001
        )
        assert v_large > v_small


# =====================================================================
#   Full Ink Simulation Tests
# =====================================================================

class TestInkSimulation:
    def test_basic_simulation(self):
        """Basic ink simulation should produce valid results."""
        ink = InkFormulation()
        props = simulate_ink(ink)
        
        assert isinstance(props, InkProperties)
        assert props.viscosity_mPas > 0
        assert props.surface_tension_mN_m > 0
        assert 0 <= props.printability_score <= 1
        assert props.sheet_resistance_ohm_sq > 0

    def test_graphene_ink_conductivity(self):
        """Graphene ink above percolation should be conductive."""
        ink = InkFormulation(
            filler_material="graphene",
            filler_loading_wt_pct=10.0,
            aspect_ratio=100
        )
        props = simulate_ink(ink)
        
        assert props.above_percolation
        assert props.conductivity_S_m > 1
        assert props.sheet_resistance_ohm_sq < 1e6

    def test_low_loading_insulating(self):
        """Low filler loading should be below percolation."""
        ink = InkFormulation(filler_loading_wt_pct=0.5)
        props = simulate_ink(ink)
        
        assert not props.above_percolation
        assert props.conductivity_S_m < 1e-5

    def test_inkjet_formulation(self):
        """Inkjet ink should have appropriate viscosity."""
        ink = InkFormulation(
            print_method=PrintMethod.INKJET,
            filler_loading_wt_pct=2.0,
            primary_solvent="water"
        )
        props = simulate_ink(ink)
        
        # Inkjet requires low viscosity (2-25 mPa·s)
        assert 0.5 < props.viscosity_mPas < 50
        assert props.Z_parameter > 0  # Should be positive (may be outside ideal window)

    def test_screen_printing_formulation(self):
        """Screen printing ink should have high viscosity."""
        ink = InkFormulation(
            print_method=PrintMethod.SCREEN,
            filler_loading_wt_pct=15.0,
            binder_wt_pct=5.0
        )
        props = simulate_ink(ink)
        
        # Screen printing requires higher viscosity than inkjet
        assert props.viscosity_mPas > 1.5  # Higher than pure solvent
        assert props.yield_stress_Pa > 0

    def test_binder_increases_viscosity(self):
        """Adding binder should increase viscosity."""
        ink_no_binder = InkFormulation(binder_wt_pct=0.0)
        ink_with_binder = InkFormulation(binder_wt_pct=5.0)
        
        props_no = simulate_ink(ink_no_binder)
        props_with = simulate_ink(ink_with_binder)
        
        assert props_with.viscosity_mPas > props_no.viscosity_mPas

    def test_surfactant_reduces_surface_tension(self):
        """Surfactant should reduce surface tension."""
        ink_no_surf = InkFormulation(surfactant_wt_pct=0.0)
        ink_with_surf = InkFormulation(surfactant_wt_pct=1.0)
        
        props_no = simulate_ink(ink_no_surf)
        props_with = simulate_ink(ink_with_surf)
        
        assert props_with.surface_tension_mN_m < props_no.surface_tension_mN_m

    def test_viscosity_at_different_shear_rates(self):
        """Viscosity should be calculated at multiple shear rates."""
        ink = InkFormulation(filler_loading_wt_pct=10.0)
        props = simulate_ink(ink)
        
        assert len(props.viscosity_at_shear) > 0
        assert "100" in props.viscosity_at_shear
        assert "10000" in props.viscosity_at_shear

    def test_recommendations_generated(self):
        """Simulation should generate recommendations."""
        ink = InkFormulation(filler_loading_wt_pct=0.5)  # Below percolation
        props = simulate_ink(ink)
        
        assert len(props.recommendations) > 0
        # Should recommend increasing loading
        assert any("percolation" in rec.lower() for rec in props.recommendations)

    def test_to_dict_serialization(self):
        """Properties should serialize to dict."""
        ink = InkFormulation()
        props = simulate_ink(ink)
        data = props.to_dict()
        
        assert isinstance(data, dict)
        assert "viscosity_mPas" in data
        assert "conductivity_S_m" in data
        assert "printability_score" in data
        assert isinstance(data["viscosity_mPas"], (int, float))


# =====================================================================
#   Rheology Curve Tests
# =====================================================================

class TestRheologyCurve:
    def test_rheology_curve_generation(self):
        """Rheology curve should show shear-thinning."""
        ink = InkFormulation(filler_loading_wt_pct=10.0)
        data = rheology_curve(ink, n_points=50)
        
        assert len(data["shear_rate"]) == 50
        assert len(data["viscosity_Pas"]) == 50
        assert len(data["shear_stress_Pa"]) == 50
        assert "print_window" in data
        
        # Shear-thinning: viscosity decreases with shear rate
        viscosities = np.array(data["viscosity_Pas"])
        assert viscosities[0] > viscosities[-1]

    def test_rheology_curve_print_window(self):
        """Print window should be marked in rheology curve."""
        ink = InkFormulation(print_method=PrintMethod.INKJET)
        data = rheology_curve(ink)
        
        window = data["print_window"]
        assert "shear_rate_min" in window
        assert "shear_rate_max" in window
        assert window["shear_rate_max"] > window["shear_rate_min"]


# =====================================================================
#   Solvent Database Tests
# =====================================================================

class TestSolventDatabase:
    def test_all_solvents_have_properties(self):
        """All solvents should have required properties."""
        required_keys = ["viscosity_mPas", "surface_tension_mN_m", "density_kg_m3",
                        "boiling_C", "vapor_pressure_kPa", "evap_rate_rel"]
        
        for solvent_name, props in SOLVENT_DB.items():
            for key in required_keys:
                assert key in props, f"{solvent_name} missing {key}"
                assert props[key] > 0

    def test_list_solvents(self):
        """list_solvents should return all solvents."""
        solvents = list_solvents()
        assert len(solvents) == len(SOLVENT_DB)
        assert all("name" in s for s in solvents)
        assert all("viscosity_mPas" in s for s in solvents)

    def test_list_print_methods(self):
        """list_print_methods should return all methods."""
        methods = list_print_methods()
        assert len(methods) == len(PRINT_WINDOWS)
        assert all("method" in m for m in methods)


# =====================================================================
#   Edge Cases & Validation Tests
# =====================================================================

class TestEdgeCases:
    def test_zero_filler_loading(self):
        """Zero filler should give pure solvent properties."""
        ink = InkFormulation(filler_loading_wt_pct=0.0)
        props = simulate_ink(ink)
        
        assert not props.above_percolation
        assert props.conductivity_S_m <= 1e-10

    def test_very_high_filler_loading(self):
        """Very high filler loading should still compute."""
        ink = InkFormulation(filler_loading_wt_pct=50.0)
        props = simulate_ink(ink)
        
        assert props.viscosity_mPas > 5  # Should be more viscous than pure solvent
        assert np.isfinite(props.viscosity_mPas)

    def test_all_print_methods_simulate(self):
        """All print methods should simulate successfully."""
        for method in PrintMethod:
            ink = InkFormulation(print_method=method)
            props = simulate_ink(ink)
            assert props.viscosity_mPas > 0
            assert 0 <= props.printability_score <= 1

    def test_all_solvents_simulate(self):
        """All solvents should simulate successfully."""
        for solvent in ["water", "nmp", "ethanol", "toluene"]:
            ink = InkFormulation(primary_solvent=solvent)
            props = simulate_ink(ink)
            assert props.viscosity_mPas > 0

    def test_numerical_stability(self):
        """Simulation should be numerically stable."""
        ink = InkFormulation()
        props = simulate_ink(ink)
        
        # Check all numeric fields are finite
        assert np.isfinite(props.viscosity_mPas)
        assert np.isfinite(props.surface_tension_mN_m)
        assert np.isfinite(props.conductivity_S_m)
        assert np.isfinite(props.sheet_resistance_ohm_sq)
        assert np.isfinite(props.printability_score)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
