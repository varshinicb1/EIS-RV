"""
Tests for the autonomous closed-loop discovery engine
======================================================
Covers the orchestrator (invent → digital-twin synthesis → multi-technique
characterisation → score → loop) plus the module-level background runner.

All runs are forced offline (``use_nim=False``) so the suite is deterministic
and needs no network or NVIDIA_API_KEY.
"""

import time

import pytest

from src.backend.core.engines.closed_loop import (
    ClosedLoopDiscovery,
    RecipeTarget,
    closed_loop_result,
    closed_loop_status,
    run_closed_loop_sync,
    start_closed_loop,
    stop_closed_loop,
)
from src.backend.core.engines.materials import (
    MaterialComposition,
    SynthesisMethod,
    SynthesisParameters,
)


@pytest.fixture
def engine():
    return ClosedLoopDiscovery()


@pytest.fixture
def sample_recipe():
    comp = MaterialComposition(components={"graphene": 0.6, "NiO": 0.4})
    synth = SynthesisParameters(
        method=SynthesisMethod.HYDROTHERMAL,
        temperature_C=160.0, duration_hours=8.0, pH=9.0,
    )
    return comp, synth


class TestRecipeTarget:
    def test_defaults_and_serialisation(self):
        t = RecipeTarget()
        d = t.to_dict()
        assert d["target_capacitance_F_g"] == 400.0
        assert 0.0 <= d["perfection_threshold"] <= 1.0
        # Weights should sum to 1.0 (weighted mean).
        assert abs(sum(d["weights"].values()) - 1.0) < 1e-9


class TestCharacterise:
    def test_runs_all_techniques(self, engine, sample_recipe):
        comp, synth = sample_recipe
        results = engine.characterise(comp, synth)
        for key in ("descriptors", "eis", "cv", "gcd", "drt"):
            assert key in results
        # EIS should be physically sensible.
        assert results["eis"]["Rct_ohm"] > 0
        assert results["eis"]["n_points"] == 100
        # A pseudocapacitive composition should yield non-trivial capacitance.
        assert results["gcd"]["specific_capacitance_F_g"] > 0

    def test_pseudocapacitance_increases_capacitance(self, engine):
        """A pseudocapacitive oxide should beat a pure-carbon EDLC electrode."""
        carbon = MaterialComposition(components={"graphene": 1.0})
        oxide = MaterialComposition(components={"graphene": 0.5, "NiO": 0.5})
        synth = SynthesisParameters(method=SynthesisMethod.HYDROTHERMAL)
        cs_carbon = engine.characterise(carbon, synth)["gcd"]["specific_capacitance_F_g"]
        cs_oxide = engine.characterise(oxide, synth)["gcd"]["specific_capacitance_F_g"]
        assert cs_oxide > cs_carbon


class TestScore:
    def test_score_in_unit_interval(self, engine, sample_recipe):
        comp, synth = sample_recipe
        results = engine.characterise(comp, synth)
        scored = engine.score(results, RecipeTarget(), feasibility=0.8)
        assert 0.0 <= scored["overall"] <= 1.0
        for sub in scored["subscores"].values():
            assert 0.0 <= sub <= 1.0

    def test_lower_rct_scores_higher_kinetics(self, engine):
        target = RecipeTarget()
        base = engine.characterise(
            MaterialComposition(components={"graphene": 0.6, "NiO": 0.4}),
            SynthesisParameters(method=SynthesisMethod.HYDROTHERMAL),
        )
        low = dict(base)
        high = dict(base)
        low["eis"] = {**base["eis"], "Rct_ohm": 600.0}
        high["eis"] = {**base["eis"], "Rct_ohm": 20000.0}
        s_low = engine.score(low, target, 0.8)["subscores"]["kinetics"]
        s_high = engine.score(high, target, 0.8)["subscores"]["kinetics"]
        assert s_low > s_high

    def test_feasibility_penalties(self, engine):
        harsh = SynthesisParameters(
            method=SynthesisMethod.HYDROTHERMAL,
            temperature_C=260.0, duration_hours=48.0, pH=0.5,
        )
        gentle = SynthesisParameters(
            method=SynthesisMethod.HYDROTHERMAL,
            temperature_C=160.0, duration_hours=8.0, pH=7.0,
        )
        comp = MaterialComposition(components={"graphene": 0.6, "NiO": 0.4})
        assert engine._feasibility(harsh, comp) < engine._feasibility(gentle, comp)


class TestRun:
    def test_run_returns_best_recipe(self, engine):
        res = engine.run(max_iterations=12, seed=7, use_nim=False)
        assert res["iterations_run"] >= 1
        assert res["used_nim"] is False
        pr = res["perfect_recipe"]
        assert pr is not None
        assert "composition" in pr and "synthesis" in pr and "results" in pr
        assert 0.0 <= pr["score"] <= 1.0
        # History entries are summarised and monotonic in iteration index.
        iters = [h["iteration"] for h in res["history"]]
        assert iters == sorted(iters)

    def test_run_is_deterministic(self, engine):
        a = engine.run(max_iterations=10, seed=3, use_nim=False)
        b = engine.run(max_iterations=10, seed=3, use_nim=False)
        assert a["perfect_recipe"]["score"] == b["perfect_recipe"]["score"]
        assert (a["perfect_recipe"]["composition"]
                == b["perfect_recipe"]["composition"])

    def test_converges_to_perfect_recipe(self):
        """With a modest budget the loop should usually cross the threshold."""
        res = run_closed_loop_sync(max_iterations=40, seed=7, use_nim=False)
        assert res["converged"] is True
        assert res["perfect_recipe"]["score"] >= res["target"]["perfection_threshold"]


class TestBackgroundRunner:
    def test_start_status_result(self):
        # Ensure a clean state if a previous test left it running.
        stop_closed_loop()
        time.sleep(0.2)
        out = start_closed_loop(
            target=RecipeTarget(perfection_threshold=0.6), max_iterations=15, seed=1,
        )
        assert out["status"] in ("started", "already_running")

        # Poll until the background thread finishes (bounded).
        deadline = time.time() + 60
        while time.time() < deadline:
            status = closed_loop_status()
            if not status["running"]:
                break
            time.sleep(0.5)

        status = closed_loop_status()
        assert status["running"] is False
        assert "thread" not in status  # thread handle is never serialised
        result = closed_loop_result()
        assert result["perfect_recipe"] is not None

    def test_stop_is_idempotent(self):
        assert stop_closed_loop()["status"] == "stop_requested"
        assert stop_closed_loop()["status"] == "stop_requested"
