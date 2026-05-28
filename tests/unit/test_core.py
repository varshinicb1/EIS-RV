"""
VANL Core Module Tests
========================
Unit tests for materials, synthesis engine, EIS engine, dataset generation,
and Bayesian optimizer.

Run with:
    python -m pytest tests/unit/test_core.py -v
"""

import sys
import os
import numpy as np
import pytest

# Ensure vanl is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.backend.core.engines.materials import (
    MaterialComposition,
    SynthesisParameters,
    StructuralDescriptors,
    EISParameters,
    SynthesisMethod,
    MATERIAL_DATABASE,
)
from src.backend.core.engines.synthesis_engine import SynthesisEngine
from src.backend.core.engines.eis_engine import (
    randles_impedance,
    simulate_eis,
    descriptors_to_eis,
    quick_simulate,
)
from src.backend.core.engines.dataset_gen import (
    generate_synthesis_dataset,
    generate_eis_dataset,
)
from src.backend.core.engines.optimizer import (
    BayesianOptimizer,
    OptimizationTarget,
    compute_objective,
)


# =====================================================================
#   MaterialComposition Tests
# =====================================================================

class TestMaterialComposition:
    def test_normalization(self):
        """Components should be normalized to sum to 1."""
        comp = MaterialComposition(components={"graphene": 3.0, "MnO2": 1.0})
        total = sum(comp.components.values())
        assert abs(total - 1.0) < 1e-10

    def test_single_component(self):
        comp = MaterialComposition(components={"graphene": 1.0})
        assert comp.components["graphene"] == 1.0

    def test_to_vector(self):
        comp = MaterialComposition(components={"graphene": 0.7, "MnO2": 0.3})
        vec = comp.to_vector()
        assert isinstance(vec, np.ndarray)
        assert len(vec) == len(MATERIAL_DATABASE)
        assert abs(vec.sum() - 1.0) < 1e-10

    def test_from_vector_roundtrip(self):
        comp = MaterialComposition(components={"graphene": 0.5, "CNT": 0.5})
        vec = comp.to_vector()
        comp2 = MaterialComposition.from_vector(vec)
        vec2 = comp2.to_vector()
        np.testing.assert_allclose(vec, vec2, atol=1e-6)

    def test_effective_conductivity(self):
        """Pure graphene should have high conductivity."""
        comp = MaterialComposition(components={"graphene": 1.0})
        sigma = comp.effective_conductivity
        assert sigma > 1e4  # Graphene is highly conductive

    def test_cost_index(self):
        comp = MaterialComposition(components={"graphene": 0.5, "carbon_black": 0.5})
        cost = comp.cost_index
        assert 0 < cost < 5

    def test_pseudocapacitive_detection(self):
        comp_no_pseudo = MaterialComposition(components={"graphene": 1.0})
        assert not comp_no_pseudo.has_pseudocapacitive

        comp_pseudo = MaterialComposition(components={"graphene": 0.5, "MnO2": 0.5})
        assert comp_pseudo.has_pseudocapacitive


# =====================================================================
#   SynthesisParameters Tests
# =====================================================================

class TestSynthesisParameters:
    def test_default_values(self):
        synth = SynthesisParameters()
        assert synth.temperature_C == 120.0
        assert synth.pH == 7.0

    def test_to_vector(self):
        synth = SynthesisParameters()
        vec = synth.to_vector()
        assert isinstance(vec, np.ndarray)
        # 5 continuous params + 8 method one-hot = 13
        assert len(vec) == 5 + len(SynthesisMethod)

    def test_to_dict(self):
        synth = SynthesisParameters(method=SynthesisMethod.CVD, temperature_C=180)
        d = synth.to_dict()
        assert d["method"] == "cvd"
        assert d["temperature_C"] == 180


# =====================================================================
#   StructuralDescriptors Tests
# =====================================================================

class TestStructuralDescriptors:
    def test_to_vector(self):
        desc = StructuralDescriptors()
        vec = desc.to_vector()
        assert isinstance(vec, np.ndarray)
        assert len(vec) == 7
        assert all(np.isfinite(vec))

    def test_to_dict_roundtrip(self):
        desc = StructuralDescriptors(porosity=0.35, surface_area_m2_g=800)
        d = desc.to_dict()
        assert abs(d["porosity"] - 0.35) < 0.001
        assert abs(d["surface_area_m2_g"] - 800) < 1


# =====================================================================
#   EISParameters Tests
# =====================================================================

class TestEISParameters:
    def test_to_vector(self):
        eis = EISParameters()
        vec = eis.to_vector()
        assert isinstance(vec, np.ndarray)
        assert len(vec) == 5

    def test_from_vector_roundtrip(self):
        eis = EISParameters(Rs=5, Rct=200, Cdl=2e-5, sigma_warburg=30, n_cpe=0.85)
        vec = eis.to_vector()
        eis2 = EISParameters.from_vector(vec)
        assert abs(eis2.Rs - eis.Rs) / eis.Rs < 0.05
        assert abs(eis2.Rct - eis.Rct) / eis.Rct < 0.05


# =====================================================================
#   SynthesisEngine Tests
# =====================================================================

class TestSynthesisEngine:
    def setup_method(self):
        self.engine = SynthesisEngine()

    def test_basic_synthesis(self):
        comp = MaterialComposition(components={"graphene": 0.7, "MnO2": 0.3})
        synth = SynthesisParameters()
        desc = self.engine.synthesize(comp, synth)

        assert isinstance(desc, StructuralDescriptors)
        assert 0 < desc.porosity < 1
        assert desc.surface_area_m2_g > 0
        assert desc.conductivity_S_m > 0

    def test_temperature_affects_crystallinity(self):
        """Higher temperature should increase crystallinity."""
        comp = MaterialComposition(components={"graphene": 1.0})
        low_T = SynthesisParameters(temperature_C=50)
        high_T = SynthesisParameters(temperature_C=180)

        desc_low = self.engine.synthesize(comp, low_T)
        desc_high = self.engine.synthesize(comp, high_T)
        assert desc_high.crystallinity > desc_low.crystallinity

    def test_all_synthesis_methods(self):
        """All synthesis methods should produce valid results."""
        comp = MaterialComposition(components={"graphene": 0.5, "MnO2": 0.5})
        for method in SynthesisMethod:
            synth = SynthesisParameters(method=method)
            desc = self.engine.synthesize(comp, synth)
            assert 0 < desc.porosity < 1
            assert desc.conductivity_S_m > 0


# =====================================================================
#   EIS Engine Tests
# =====================================================================

class TestEISEngine:
    def test_randles_impedance_shape(self):
        freq = np.logspace(-2, 6, 100)
        Z = randles_impedance(freq, Rs=10, Rct=100, Cdl=1e-5, sigma_w=50)
        assert Z.shape == freq.shape
        assert np.all(np.isfinite(Z))

    def test_high_freq_limit(self):
        """At very high frequencies, Z → Rs."""
        freq = np.array([1e8])
        Z = randles_impedance(freq, Rs=10, Rct=100, Cdl=1e-5, sigma_w=50)
        assert abs(Z[0].real - 10) < 5  # Should be close to Rs

    def test_simulate_eis(self):
        params = EISParameters(Rs=5, Rct=200, Cdl=2e-5, sigma_warburg=30)
        result = simulate_eis(params)

        assert len(result.frequencies) == 100
        assert len(result.Z_real) == 100
        assert len(result.Z_imag) == 100
        assert all(np.isfinite(result.Z_real))
        assert all(np.isfinite(result.Z_magnitude))

    def test_descriptors_to_eis(self):
        desc = StructuralDescriptors()
        eis = descriptors_to_eis(desc)

        assert isinstance(eis, EISParameters)
        assert eis.Rs > 0
        assert eis.Rct > 0
        assert eis.Cdl > 0
        assert 0.5 <= eis.n_cpe <= 1.0

    def test_quick_simulate(self):
        data = quick_simulate(Rs=10, Rct=100)
        assert "nyquist" in data
        assert "bode_mag" in data
        assert "bode_phase" in data
        assert len(data["frequencies"]) == 100

    def test_nyquist_data_format(self):
        """Nyquist plot should have Z' on x and -Z'' on y."""
        params = EISParameters()
        result = simulate_eis(params)
        x, y = result.nyquist_data()
        assert len(x) == len(y)
        assert all(isinstance(v, float) for v in x[:5])


# =====================================================================
#   Dataset Generation Tests
# =====================================================================

class TestDatasetGeneration:
    def test_synthesis_dataset(self):
        X, Y, records = generate_synthesis_dataset(n_samples=50, seed=42)

        assert X.shape[0] == 50
        assert Y.shape[0] == 50
        assert Y.shape[1] == 7  # 7 structural descriptors
        assert len(records) == 50
        assert all(np.isfinite(X.flat))
        assert all(np.isfinite(Y.flat))

    def test_eis_dataset(self):
        X, Y, records = generate_eis_dataset(n_samples=50, seed=42)

        assert X.shape[0] == 50
        assert Y.shape[0] == 50
        assert Y.shape[1] == 5  # 5 EIS parameters
        assert len(records) == 50
        assert all(np.isfinite(X.flat))
        assert all(np.isfinite(Y.flat))

    def test_dataset_reproducibility(self):
        """Same seed should produce same data."""
        X1, Y1, _ = generate_eis_dataset(n_samples=20, seed=99)
        X2, Y2, _ = generate_eis_dataset(n_samples=20, seed=99)
        np.testing.assert_array_equal(X1, X2)
        np.testing.assert_array_equal(Y1, Y2)


# =====================================================================
#   Optimizer Tests
# =====================================================================

class TestOptimizer:
    def test_compute_objective(self):
        eis = EISParameters(Rs=10, Rct=100, Cdl=1e-5, sigma_warburg=50)
        desc = StructuralDescriptors()
        comp = MaterialComposition(components={"graphene": 1.0})
        target = OptimizationTarget()

        obj = compute_objective(eis, desc, comp, target)
        assert isinstance(obj, float)
        assert np.isfinite(obj)

    def test_bayesian_optimizer_init(self):
        opt = BayesianOptimizer(
            active_materials=["graphene", "MnO2"],
            seed=42,
        )
        assert opt.dim == 5  # 2 materials + 3 synth params
        assert len(opt.bounds) == 5

    def test_suggest_random(self):
        """Before GP is fitted, should suggest random points."""
        opt = BayesianOptimizer(active_materials=["graphene", "MnO2"])
        suggestions = opt.suggest_next(3)
        assert len(suggestions) == 3
        assert all(len(s) == 5 for s in suggestions)

    def test_run_optimization_short(self):
        """Run a small optimization to verify the loop works."""
        opt = BayesianOptimizer(
            active_materials=["graphene", "MnO2"],
            seed=42,
        )
        history = opt.run_optimization(n_iterations=3, n_initial=3, verbose=False)
        assert len(history) == 6  # 3 initial + 3 iterations

        best = opt.get_best()
        assert best is not None
        assert best.eis_params is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
