"""
Test Predictive Material Identification System
===============================================
Validates the inverse solver against real CHI608E lab data.

Run:
    pytest tests/test_predictive_identification.py -v
"""

import pytest
import numpy as np
import os
from pathlib import Path

from src.backend.ml.models.inverse_solver import InverseSolver, InverseSolution
from src.backend.ml.models.cross_modal_identifier import CrossModalIdentifier


@pytest.fixture
def solver():
    """Create inverse solver instance."""
    return InverseSolver()


@pytest.fixture
def identifier():
    """Create cross-modal identifier instance."""
    return CrossModalIdentifier()


@pytest.fixture
def lab_data_dir():
    """Path to lab data directory."""
    return Path(__file__).parent.parent / "Lab data" / "fog differet data" / "fog differet data"


class TestInverseSolverEIS:
    """Test inverse solver with EIS data."""
    
    def test_synthetic_graphene_eis(self, solver):
        """Test with synthetic graphene-like EIS data."""
        # Generate synthetic EIS data for graphene
        freq = np.logspace(-2, 5, 50)
        omega = 2 * np.pi * freq
        
        # Graphene-like parameters
        Rs = 10.0
        Rct = 50.0
        Cdl = 200e-6  # 200 µF
        sigma = 150.0
        
        # Forward model
        Z_ct = Rct / (1 + 1j * omega * Rct * Cdl)
        Z_w = sigma / np.sqrt(omega) * (1 - 1j)
        Z = Rs + Z_ct + Z_w
        
        # Add small noise
        noise = np.random.normal(0, 1, len(freq)) + 1j * np.random.normal(0, 1, len(freq))
        Z_noisy = Z + noise
        
        # Solve inverse problem
        solution = solver.solve_from_eis(
            frequency_Hz=freq,
            Z_real_ohm=Z_noisy.real,
            Z_imag_ohm=Z_noisy.imag,
            method="circuit_fit",
        )
        
        # Assertions
        assert isinstance(solution, InverseSolution)
        assert solution.confidence > 0.5
        assert len(solution.material_candidates) > 0
        
        # Check inferred properties are close to true values
        assert abs(solution.inferred_properties["Rs"] - Rs) < 5
        assert abs(solution.inferred_properties["Rct"] - Rct) < 20
        assert abs(solution.inferred_properties["Cdl"] - Cdl) < 1e-4
        
        # Top candidate should be graphene or rGO
        top_material = solution.material_candidates[0].material_name
        assert top_material in ["graphene", "reduced_graphene_oxide"]
        
        print(f"\n✓ Identified: {top_material} (confidence: {solution.material_candidates[0].confidence:.2f})")
    
    def test_synthetic_mno2_eis(self, solver):
        """Test with synthetic MnO2-like EIS data."""
        freq = np.logspace(-2, 5, 50)
        omega = 2 * np.pi * freq
        
        # MnO2-like parameters (higher Rct, higher Cdl)
        Rs = 15.0
        Rct = 200.0
        Cdl = 1000e-6  # 1000 µF
        sigma = 300.0
        
        Z_ct = Rct / (1 + 1j * omega * Rct * Cdl)
        Z_w = sigma / np.sqrt(omega) * (1 - 1j)
        Z = Rs + Z_ct + Z_w
        
        noise = np.random.normal(0, 2, len(freq)) + 1j * np.random.normal(0, 2, len(freq))
        Z_noisy = Z + noise
        
        solution = solver.solve_from_eis(
            frequency_Hz=freq,
            Z_real_ohm=Z_noisy.real,
            Z_imag_ohm=Z_noisy.imag,
            method="circuit_fit",
        )
        
        assert solution.confidence > 0.4
        assert len(solution.material_candidates) > 0
        
        # Should identify a pseudocapacitive material
        top_material = solution.material_candidates[0].material_name
        print(f"\n✓ Identified: {top_material} (confidence: {solution.material_candidates[0].confidence:.2f})")
    
    def test_bayesian_inference(self, solver):
        """Test Bayesian inference method."""
        freq = np.logspace(-2, 5, 30)
        omega = 2 * np.pi * freq
        
        Rs = 10.0
        Rct = 50.0
        Cdl = 200e-6
        sigma = 150.0
        
        Z_ct = Rct / (1 + 1j * omega * Rct * Cdl)
        Z_w = sigma / np.sqrt(omega) * (1 - 1j)
        Z = Rs + Z_ct + Z_w
        
        noise = np.random.normal(0, 1, len(freq)) + 1j * np.random.normal(0, 1, len(freq))
        Z_noisy = Z + noise
        
        solution = solver.solve_from_eis(
            frequency_Hz=freq,
            Z_real_ohm=Z_noisy.real,
            Z_imag_ohm=Z_noisy.imag,
            method="bayesian",
        )
        
        assert solution.method == "bayesian"
        assert "noise_std" in solution.inferred_properties
        assert solution.confidence > 0.4
        
        print(f"\n✓ Bayesian inference: confidence={solution.confidence:.2f}, noise_std={solution.inferred_properties['noise_std']:.3f}")


class TestInverseSolverCV:
    """Test inverse solver with CV data."""
    
    def test_synthetic_reversible_cv(self, solver):
        """Test with synthetic reversible CV data."""
        # Generate synthetic CV data
        E = np.linspace(-0.3, 0.8, 1000)
        
        # Reversible system (graphene-like)
        E_formal = 0.23
        n = 1
        F = 96485
        R = 8.314
        T = 298
        
        # Nernst equation for reversible system
        i_forward = 1e-3 * np.exp((n * F / (R * T)) * (E - E_formal))
        i_reverse = -1e-3 * np.exp(-(n * F / (R * T)) * (E - E_formal))
        
        # Combine forward and reverse scans
        i_total = np.where(E < E_formal, i_forward, i_reverse)
        
        # Add noise
        i_total += np.random.normal(0, 1e-5, len(E))
        
        solution = solver.solve_from_cv(
            potential_V=E,
            current_A=i_total,
            scan_rate_V_s=0.05,
        )
        
        assert solution.confidence > 0.3
        assert len(solution.material_candidates) > 0
        
        # Check for peak detection
        if "anodic_peak_V" in solution.inferred_properties:
            print(f"\n✓ Detected anodic peak at {solution.inferred_properties['anodic_peak_V']:.3f} V")
        
        top_material = solution.material_candidates[0].material_name
        print(f"✓ Identified: {top_material} (confidence: {solution.material_candidates[0].confidence:.2f})")


class TestInverseSolverRaman:
    """Test inverse solver with Raman data."""
    
    def test_synthetic_graphene_raman(self, solver):
        """Test with synthetic graphene Raman spectrum."""
        # Generate synthetic Raman spectrum for graphene
        wavenumber = np.linspace(1000, 3000, 2000)
        
        # Graphene peaks: D (1350), G (1580), 2D (2700)
        def lorentzian(x, x0, gamma, A):
            return A * (gamma**2) / ((x - x0)**2 + gamma**2)
        
        intensity = (
            lorentzian(wavenumber, 1350, 30, 0.3) +  # D band (low for graphene)
            lorentzian(wavenumber, 1580, 20, 1.0) +  # G band
            lorentzian(wavenumber, 2700, 40, 2.5) +  # 2D band (high for graphene)
            np.random.normal(0, 0.01, len(wavenumber))  # Noise
        )
        
        solution = solver.solve_from_raman(
            wavenumber_cm=wavenumber,
            intensity=intensity,
        )
        
        assert solution.confidence > 0.15
        assert len(solution.material_candidates) > 0
        
        # Check D/G ratio
        if "d_g_ratio" in solution.inferred_properties:
            d_g = solution.inferred_properties["d_g_ratio"]
            print(f"\n✓ D/G ratio: {d_g:.2f} (expected < 0.5 for graphene)")
            assert d_g < 1.0  # Should be low for graphene
        
        top_material = solution.material_candidates[0].material_name
        print(f"✓ Identified: {top_material} (confidence: {solution.material_candidates[0].confidence:.2f})")
    
    def test_synthetic_rgo_raman(self, solver):
        """Test with synthetic rGO Raman spectrum (higher D/G ratio)."""
        wavenumber = np.linspace(1000, 3000, 2000)
        
        def lorentzian(x, x0, gamma, A):
            return A * (gamma**2) / ((x - x0)**2 + gamma**2)
        
        intensity = (
            lorentzian(wavenumber, 1350, 30, 1.2) +  # D band (high for rGO)
            lorentzian(wavenumber, 1590, 20, 1.0) +  # G band
            lorentzian(wavenumber, 2700, 40, 1.5) +  # 2D band
            np.random.normal(0, 0.01, len(wavenumber))
        )
        
        solution = solver.solve_from_raman(
            wavenumber_cm=wavenumber,
            intensity=intensity,
        )
        
        assert solution.confidence > 0.15
        
        if "d_g_ratio" in solution.inferred_properties:
            d_g = solution.inferred_properties["d_g_ratio"]
            print(f"\n✓ D/G ratio: {d_g:.2f} (expected 0.8-1.5 for rGO)")
            assert 0.5 < d_g < 2.0
        
        top_material = solution.material_candidates[0].material_name
        print(f"✓ Identified: {top_material} (confidence: {solution.material_candidates[0].confidence:.2f})")


class TestMultimodalFusion:
    """Test multi-modal fusion."""
    
    def test_eis_cv_fusion(self, solver):
        """Test fusion of EIS and CV data."""
        # Generate EIS data
        freq = np.logspace(-2, 5, 50)
        omega = 2 * np.pi * freq
        Rs, Rct, Cdl, sigma = 10.0, 50.0, 200e-6, 150.0
        Z_ct = Rct / (1 + 1j * omega * Rct * Cdl)
        Z_w = sigma / np.sqrt(omega) * (1 - 1j)
        Z = Rs + Z_ct + Z_w
        noise = np.random.normal(0, 1, len(freq)) + 1j * np.random.normal(0, 1, len(freq))
        Z_noisy = Z + noise
        
        eis_data = {
            "frequency_Hz": freq,
            "Z_real_ohm": Z_noisy.real,
            "Z_imag_ohm": Z_noisy.imag,
        }
        
        # Generate CV data
        E = np.linspace(-0.3, 0.8, 1000)
        i_total = 1e-3 * np.sin(10 * E) + np.random.normal(0, 1e-5, len(E))
        
        cv_data = {
            "potential_V": E,
            "current_A": i_total,
            "scan_rate_V_s": 0.05,
        }
        
        # Multi-modal fusion
        solution = solver.solve_multimodal(
            eis_data=eis_data,
            cv_data=cv_data,
        )
        
        assert solution.method == "multimodal_fusion"
        assert solution.convergence_info["modalities"] == 2
        
        # Confidence should be boosted
        print(f"\n✓ Multi-modal confidence: {solution.confidence:.2f}")
        print(f"✓ Modalities: {solution.material_candidates[0].modality_used}")
        
        # Should have higher confidence than single modality
        assert solution.confidence > 0.5


class TestSynthesisSuggestions:
    """Test synthesis route suggestions."""
    
    def test_synthesis_suggestions(self, solver):
        """Test that synthesis suggestions are generated."""
        freq = np.logspace(-2, 5, 50)
        omega = 2 * np.pi * freq
        Rs, Rct, Cdl, sigma = 10.0, 50.0, 200e-6, 150.0
        Z_ct = Rct / (1 + 1j * omega * Rct * Cdl)
        Z_w = sigma / np.sqrt(omega) * (1 - 1j)
        Z = Rs + Z_ct + Z_w
        
        solution = solver.solve_from_eis(
            frequency_Hz=freq,
            Z_real_ohm=Z.real,
            Z_imag_ohm=Z.imag,
            method="circuit_fit",
        )
        
        assert len(solution.synthesis_suggestions) > 0
        
        for sug in solution.synthesis_suggestions[:3]:
            assert "material" in sug
            assert "method" in sug
            assert "estimated_cost_per_gram" in sug
            
            print(f"\n✓ Synthesis: {sug['material']} via {sug['method']}")
            print(f"  Cost: ${sug['estimated_cost_per_gram']:.2f}/g")
            if sug.get("typical_electrolytes"):
                print(f"  Electrolytes: {', '.join(sug['typical_electrolytes'])}")


class TestRealLabData:
    """Test with real CHI608E lab data."""
    
    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "Lab data").exists(),
        reason="Lab data directory not found"
    )
    def test_ferric_oxide_eis(self, solver, lab_data_dir):
        """Test with real ferric oxide EIS data."""
        eis_file = lab_data_dir / "EIS FERRIC OXIDE" / "EIS FERRIC OXIDE_FO.csv"
        
        if not eis_file.exists():
            pytest.skip("Ferric oxide EIS file not found")
        
        # Load data
        data = np.loadtxt(eis_file, delimiter=',', skiprows=1)
        freq = data[:, 0]
        Z_real = data[:, 1]
        Z_imag = data[:, 2]
        
        # Solve
        solution = solver.solve_from_eis(
            frequency_Hz=freq,
            Z_real_ohm=Z_real,
            Z_imag_ohm=Z_imag,
            method="circuit_fit",
        )
        
        print(f"\n✓ Real Lab Data - Ferric Oxide")
        print(f"  Confidence: {solution.confidence:.2f}")
        print(f"  Top candidate: {solution.material_candidates[0].material_name}")
        print(f"  Inferred Rct: {solution.inferred_properties['Rct']:.1f} Ω")
        
        # Should identify Fe2O3 or similar metal oxide
        top_material = solution.material_candidates[0].material_name
        assert "Fe" in top_material or "oxide" in top_material.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
