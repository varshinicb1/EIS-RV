"""
Autonomous Closed-Loop Discovery
================================
The "AI lab operating system" loop described in the RĀMAN Studio vision:

    invent  →  digital-twin synthesis  →  multi-technique characterisation
            →  score against a "perfect recipe" target  →  learn  →  repeat
            until a reproducible recipe crosses the perfection threshold.

Unlike the combinatorial ``DiscoveryLoop`` (biosensor LoD search) and the
single-objective Bayesian ``AutonomousLab`` (EIS only), this orchestrator:

  1. **Invents** a candidate (composition over the known material database +
     hydrothermal synthesis parameters). When ``NVIDIA_API_KEY`` is set it
     asks a NIM to propose the next candidate and reason about it; otherwise a
     deterministic, seeded guided sampler explores then exploits around the
     best recipe found so far.
  2. **Synthesises** it in-silico through the existing ``SynthesisEngine``
     (the hydrothermal digital twin) to obtain structural descriptors.
  3. **Characterises** it across the full technique suite that ships with the
     app — EIS (Randles+CPE), CV (Butler-Volmer/Nicholson), GCD (EDLC +
     pseudocapacitance) and DRT (Tikhonov) — all real physics engines.
  4. **Scores** the result with a transparent composite objective and keeps
     the best recipe. Poor candidates are recorded as failures so the
     hydrothermal knowledge graph can penalise them.
  5. **Stops** as soon as a candidate crosses ``perfection_threshold`` (a
     "perfect recipe" has been found) or ``max_iterations`` is reached.

Every number is produced by a physics engine — nothing is fabricated. The
loop runs fully offline; NIM only enriches candidate proposals and adds a
natural-language assessment when a key is available.
"""
from __future__ import annotations

import json
import logging
import math
import random
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .materials import (
    MATERIAL_DATABASE,
    MaterialComposition,
    SynthesisMethod,
    SynthesisParameters,
)
from .synthesis_engine import SynthesisEngine
from .eis_engine import descriptors_to_eis, simulate_eis
from .cv_engine import CVParameters, simulate_cv
from .gcd_engine import GCDParameters, simulate_gcd
from .drt_analysis import DRTAnalyzer

logger = logging.getLogger(__name__)

__all__ = [
    "RecipeTarget",
    "ClosedLoopDiscovery",
    "get_closed_loop",
    "start_closed_loop",
    "stop_closed_loop",
    "closed_loop_status",
    "closed_loop_result",
    "run_closed_loop_sync",
]

# Materials the proposer is allowed to combine. Restricted to entries that the
# physics database knows about so every descriptor lookup is grounded.
_CONDUCTORS = ["graphene", "reduced_graphene_oxide", "carbon_black", "CNT"]
_ACTIVES = ["MnO2", "Fe2O3", "NiO", "NiMoO4", "polyaniline", "PEDOT_PSS"]


@dataclass
class RecipeTarget:
    """
    Defines what a "perfect recipe" looks like for a supercapacitor-style
    electrode, plus the weights of each sub-objective. All sub-scores are
    normalised to [0, 1]; the overall score is their weighted mean.

    The kinetics sub-score is log-scaled between an "excellent" and a "poor"
    charge-transfer resistance because Rct produced by the physics-informed
    EIS model spans several orders of magnitude. Bounds were calibrated to the
    range the engine actually produces for these material families.
    """
    target_capacitance_F_g: float = 400.0   # aspirational specific capacitance
    excellent_Rct_ohm: float = 600.0        # Rct at/below which kinetics = 1.0
    poor_Rct_ohm: float = 20000.0           # Rct at/above which kinetics = 0.0
    ideal_delta_Ep_mV: float = 59.0         # Nernstian reversibility (1 e-)
    perfection_threshold: float = 0.80      # overall score that ends the loop

    weight_capacitance: float = 0.35
    weight_kinetics: float = 0.30           # low Rct (log-scaled)
    weight_reversibility: float = 0.20      # CV peak separation + symmetry
    weight_feasibility: float = 0.15        # synthesis feasibility

    def to_dict(self) -> dict:
        return {
            "target_capacitance_F_g": self.target_capacitance_F_g,
            "excellent_Rct_ohm": self.excellent_Rct_ohm,
            "poor_Rct_ohm": self.poor_Rct_ohm,
            "ideal_delta_Ep_mV": self.ideal_delta_Ep_mV,
            "perfection_threshold": self.perfection_threshold,
            "weights": {
                "capacitance": self.weight_capacitance,
                "kinetics": self.weight_kinetics,
                "reversibility": self.weight_reversibility,
                "feasibility": self.weight_feasibility,
            },
        }


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _pseudocapacitance_F(comp: MaterialComposition, active_mass_mg: float,
                         utilisation: float) -> float:
    """
    Estimate faradaic pseudocapacitance contributed by the composition.

    C_pseudo = Σ_i  frac_i · C_theoretical_i(F/g) · mass(g) · utilisation
    where utilisation is the accessible fraction of theoretical capacity.
    Only pseudocapacitive entries in the material database contribute.
    """
    mass_g = active_mass_mg * 1e-3
    c = 0.0
    for mat, frac in comp.components.items():
        info = MATERIAL_DATABASE.get(mat, {})
        if info.get("pseudocapacitive") and info.get("typical_capacitance"):
            c += frac * float(info["typical_capacitance"]) * mass_g * utilisation
    return c


class ClosedLoopDiscovery:
    """Stateless engine: callers pass a target + iteration budget to ``run``."""

    def __init__(self) -> None:
        self.synth_engine = SynthesisEngine()
        self.drt = DRTAnalyzer()

    # ── 1. Invent ──────────────────────────────────────────────────────────
    def propose(
        self,
        rng: random.Random,
        best: Optional[Dict[str, Any]],
        explore: bool,
        use_nim: bool,
    ) -> Tuple[MaterialComposition, SynthesisParameters, str]:
        """Return (composition, synthesis params, source-tag)."""
        if use_nim:
            nim_candidate = self._propose_nim(best)
            if nim_candidate is not None:
                return (*nim_candidate, "nim")
        comp, synth = self._propose_sampler(rng, best, explore)
        return comp, synth, "sampler"

    def _propose_sampler(
        self,
        rng: random.Random,
        best: Optional[Dict[str, Any]],
        explore: bool,
    ) -> Tuple[MaterialComposition, SynthesisParameters]:
        """Deterministic guided sampler: explore broadly, then exploit best."""
        if best is not None and not explore:
            # Exploit: perturb the best recipe found so far. Half the time we
            # nudge the conductive scaffold up and synthesis hotter/longer,
            # because lower Rct (better kinetics) is driven by electronic
            # conductivity and crystallinity — a physically-motivated move.
            comp = dict(best["composition"]["components"])
            keys = list(comp.keys())
            k = rng.choice(keys)
            comp[k] = max(0.05, comp[k] + rng.uniform(-0.15, 0.15))
            conductors = [m for m in comp if m in _CONDUCTORS]
            if conductors and rng.random() < 0.5:
                c = rng.choice(conductors)
                comp[c] = comp[c] + rng.uniform(0.0, 0.2)
            synth_d = best["synthesis"]
            temp_bias = rng.uniform(0, 30) if rng.random() < 0.5 else 0.0
            temperature = float(_jitter(rng, synth_d["temperature_C"] + temp_bias, 20, 80, 220))
            duration = float(_jitter(rng, synth_d["duration_hours"], 3, 2, 48))
            pH = float(_jitter(rng, synth_d["pH"], 1.5, 1, 14))
        else:
            # Explore: a conductive scaffold + 1-2 active phases.
            conductor = rng.choice(_CONDUCTORS)
            n_active = rng.choice([1, 1, 2])
            actives = rng.sample(_ACTIVES, n_active)
            comp = {conductor: rng.uniform(0.2, 0.5)}
            for a in actives:
                comp[a] = rng.uniform(0.2, 0.6)
            temperature = rng.uniform(120, 200)
            duration = rng.uniform(4, 24)
            pH = rng.uniform(2, 12)

        composition = MaterialComposition(components=comp)
        synth = SynthesisParameters(
            method=SynthesisMethod.HYDROTHERMAL,
            temperature_C=temperature,
            duration_hours=duration,
            pH=pH,
            concentration_mM=rng.uniform(20, 100),
        )
        return composition, synth

    def _propose_nim(
        self, best: Optional[Dict[str, Any]]
    ) -> Optional[Tuple[MaterialComposition, SynthesisParameters]]:
        """Ask a NIM to invent the next candidate. Returns None on any failure."""
        try:
            from src.ai_engine.nim_client import get_default_client

            client = get_default_client()
            if not client.configured:
                return None

            allowed = _CONDUCTORS + _ACTIVES
            best_note = ""
            if best is not None:
                best_note = (
                    f"\nBest recipe so far scored {best['score']:.3f}: "
                    f"{json.dumps(best['composition']['components'])} via "
                    f"{json.dumps(best['synthesis'])}. Propose something likely "
                    f"to score higher (refine or diversify)."
                )
            prompt = (
                "You are designing a hydrothermal supercapacitor electrode. "
                f"Choose 2-3 materials ONLY from this list: {allowed}. "
                "Give mass fractions that sum to ~1 (include one conductive "
                "carbon and at least one pseudocapacitive oxide/polymer). "
                "Pick hydrothermal synthesis conditions. " + best_note +
                " Respond with JSON: {\"components\": {\"<material>\": <fraction>}, "
                "\"temperature_C\": <80-220>, \"duration_hours\": <2-48>, "
                "\"pH\": <1-14>}."
            )
            data = client.chat_json(prompt)
            if not isinstance(data, dict):
                return None
            raw = data.get("components", {})
            comp = {
                k: float(v) for k, v in raw.items()
                if k in MATERIAL_DATABASE and float(v) > 0
            }
            if not comp:
                return None
            composition = MaterialComposition(components=comp)
            synth = SynthesisParameters(
                method=SynthesisMethod.HYDROTHERMAL,
                temperature_C=float(min(220, max(80, data.get("temperature_C", 160)))),
                duration_hours=float(min(48, max(2, data.get("duration_hours", 8)))),
                pH=float(min(14, max(1, data.get("pH", 7)))),
            )
            return composition, synth
        except Exception as exc:  # noqa: BLE001 — NIM is best-effort
            logger.warning("NIM proposal failed, using sampler: %s", exc)
            return None

    # ── 2-3. Synthesise + characterise across techniques ────────────────────
    def characterise(
        self, comp: MaterialComposition, synth: SynthesisParameters
    ) -> Dict[str, Any]:
        """Run the digital-twin synthesis + full technique suite."""
        descriptors = self.synth_engine.synthesize(comp, synth)
        eis_params = descriptors_to_eis(descriptors)
        eis = simulate_eis(eis_params)

        # CV — reuse the EIS-derived Rs and a kinetics proxy from crystallinity.
        cv_params = CVParameters(
            Rs_ohm=float(eis_params.Rs),
            Cdl_F_cm2=20e-6,
            k0_cm_s=float(0.001 + 0.02 * descriptors.crystallinity),
        )
        cv = simulate_cv(cv_params)

        # GCD — EDLC from EIS + faradaic pseudocapacitance from composition.
        utilisation = _clip01(0.3 + 0.5 * descriptors.porosity
                              + 0.2 * descriptors.crystallinity)
        active_mass_mg = 1.0
        c_pseudo = _pseudocapacitance_F(comp, active_mass_mg, utilisation)
        gcd_params = GCDParameters(
            Cdl_F=float(eis_params.Cdl),
            C_pseudo_F=float(c_pseudo),
            Rs_ohm=float(eis_params.Rs),
            Rct_ohm=float(eis_params.Rct),
            active_mass_mg=active_mass_mg,
            current_density_A_g=1.0,
            V_max=1.0,
            n_cycles=3,
        )
        gcd = simulate_gcd(gcd_params)

        # DRT — deconvolve the simulated EIS spectrum.
        try:
            drt = self.drt.calculate_drt(eis.frequencies, eis.Z_real, eis.Z_imag)
            drt_peaks = len(getattr(drt, "peaks", []) or [])
        except Exception as exc:  # noqa: BLE001 — DRT is diagnostic only
            logger.warning("DRT failed: %s", exc)
            drt_peaks = 0

        return {
            "descriptors": descriptors.to_dict(),
            "eis": {
                "Rs_ohm": float(eis_params.Rs),
                "Rct_ohm": float(eis_params.Rct),
                "Cdl_F": float(eis_params.Cdl),
                "n_points": int(len(eis.frequencies)),
            },
            "cv": {
                "delta_Ep_mV": float(cv.delta_Ep * 1e3),
                "ip_ratio": float(abs(cv.i_pa / cv.i_pc)) if cv.i_pc else None,
            },
            "gcd": {
                "specific_capacitance_F_g": float(gcd.avg_specific_capacitance_F_g),
                "coulombic_efficiency_pct": float(gcd.avg_coulombic_efficiency_pct),
                "capacity_retention_pct": float(gcd.capacity_retention_pct),
                "energy_density_Wh_kg": float(gcd.avg_energy_Wh_kg),
            },
            "drt": {"n_peaks": drt_peaks},
        }

    # ── 4. Score ────────────────────────────────────────────────────────────
    def score(self, results: Dict[str, Any], target: RecipeTarget,
              feasibility: float) -> Dict[str, Any]:
        cap = results["gcd"]["specific_capacitance_F_g"]
        rct = results["eis"]["Rct_ohm"]
        d_ep = results["cv"]["delta_Ep_mV"]
        ip_ratio = results["cv"]["ip_ratio"]

        s_cap = _clip01(cap / target.target_capacitance_F_g)
        # Kinetics: log-scaled between excellent (=1) and poor (=0) Rct.
        if rct <= 0:
            s_kin = 1.0
        else:
            lo, hi = math.log10(target.excellent_Rct_ohm), math.log10(target.poor_Rct_ohm)
            s_kin = _clip01((hi - math.log10(rct)) / (hi - lo))
        # Reversibility: closeness of ΔEp to ideal and ip ratio to 1.
        s_dep = _clip01(1.0 - abs(d_ep - target.ideal_delta_Ep_mV) / 200.0)
        s_sym = _clip01(1.0 - abs((ip_ratio or 0.0) - 1.0)) if ip_ratio else 0.5
        s_rev = 0.6 * s_dep + 0.4 * s_sym
        s_feas = _clip01(feasibility)

        overall = (
            target.weight_capacitance * s_cap
            + target.weight_kinetics * s_kin
            + target.weight_reversibility * s_rev
            + target.weight_feasibility * s_feas
        )
        return {
            "overall": round(float(overall), 4),
            "subscores": {
                "capacitance": round(s_cap, 4),
                "kinetics": round(s_kin, 4),
                "reversibility": round(s_rev, 4),
                "feasibility": round(s_feas, 4),
            },
        }

    @staticmethod
    def _feasibility(synth: SynthesisParameters, comp: MaterialComposition) -> float:
        """Heuristic synthesis feasibility for a hydrothermal route."""
        f = 0.9
        if synth.temperature_C > 200:
            f -= 0.2
        if synth.duration_hours > 36:
            f -= 0.1
        if synth.pH < 2 or synth.pH > 13:
            f -= 0.15
        if len(comp.components) > 3:
            f -= 0.1
        return float(max(0.2, min(1.0, f)))

    # ── 5. Loop ──────────────────────────────────────────────────────────────
    def run(
        self,
        target: Optional[RecipeTarget] = None,
        max_iterations: int = 40,
        seed: int = 0,
        use_nim: bool = False,
        should_continue=None,
        on_iteration=None,
    ) -> Dict[str, Any]:
        """
        Execute the closed loop synchronously.

        Parameters
        ----------
        should_continue : callable | None
            Optional ``() -> bool`` checked each iteration so a background
            runner can request a graceful stop.
        on_iteration : callable | None
            Optional ``(state: dict) -> None`` progress callback.
        """
        target = target or RecipeTarget()
        rng = random.Random(seed)
        history: List[Dict[str, Any]] = []
        best: Optional[Dict[str, Any]] = None
        failures = 0
        converged = False
        stall = 0
        # After this many non-improving iterations, switch back to sustained
        # exploration (random restarts) to escape local optima; we stay in
        # exploration until a better recipe is found.
        patience = max(3, max_iterations // 10)

        for i in range(1, max_iterations + 1):
            if should_continue is not None and not should_continue():
                break

            # Explore for the first third; afterwards exploit around the best,
            # but resume exploration whenever progress stalls.
            explore = (
                best is None
                or i <= max(1, max_iterations // 3)
                or stall >= patience
            )
            comp, synth, source = self.propose(rng, best, explore, use_nim)
            feasibility = self._feasibility(synth, comp)

            try:
                results = self.characterise(comp, synth)
            except Exception as exc:  # noqa: BLE001
                logger.warning("characterise failed at iter %d: %s", i, exc)
                failures += 1
                continue

            scored = self.score(results, target, feasibility)
            record = {
                "iteration": i,
                "source": source,
                "composition": comp.to_dict(),
                "synthesis": synth.to_dict(),
                "feasibility": feasibility,
                "results": results,
                "score": scored["overall"],
                "subscores": scored["subscores"],
            }
            history.append(record)

            if best is None or record["score"] > best["score"]:
                best = record
                stall = 0
            else:
                # Under-performing candidate — log it as a failure signal.
                failures += 1
                stall += 1
                _record_failure_safe(comp, synth, record["score"])

            if on_iteration is not None:
                on_iteration({
                    "iteration": i,
                    "best_score": best["score"] if best else 0.0,
                    "best_material": _fmt_components(best) if best else None,
                    "last_score": record["score"],
                })

            if best and best["score"] >= target.perfection_threshold:
                converged = True
                break

        return {
            "converged": converged,
            "iterations_run": len(history),
            "failures": failures,
            "target": target.to_dict(),
            "perfect_recipe": best,
            "history": [
                {"iteration": h["iteration"], "score": h["score"],
                 "source": h["source"], "material": _fmt_components(h)}
                for h in history
            ],
            "used_nim": use_nim,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _jitter(rng: random.Random, value: float, spread: float,
            lo: float, hi: float) -> float:
    return max(lo, min(hi, value + rng.uniform(-spread, spread)))


def _fmt_components(record: Dict[str, Any]) -> str:
    comp = record["composition"]["components"]
    return " + ".join(f"{k}({v:.2f})" for k, v in comp.items())


def _record_failure_safe(comp: MaterialComposition,
                         synth: SynthesisParameters, score: float) -> None:
    """Best-effort: feed weak candidates into the hydrothermal failure graph."""
    try:
        from .hydrothermal_engine import record_failure

        record_failure(
            material=" + ".join(comp.components.keys()),
            conditions=synth.to_dict(),
            failure_mode="below_target_score",
            notes=f"closed-loop score {score:.3f}",
        )
    except Exception:  # noqa: BLE001 — purely advisory
        pass


# ════════════════════════════════════════════════════════════════════════════
# Background-thread runner (mirrors DiscoveryLoop semantics)
# ════════════════════════════════════════════════════════════════════════════

_CL_STATE: Dict[str, Any] = {
    "running": False,
    "iteration": 0,
    "best_score": 0.0,
    "best_material": None,
    "converged": False,
    "started_at": None,
    "stopped_at": None,
    "error": None,
    "result": None,
    "thread": None,
}
_CL_LOCK = threading.Lock()
_ENGINE: Optional[ClosedLoopDiscovery] = None


def get_closed_loop() -> ClosedLoopDiscovery:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ClosedLoopDiscovery()
    return _ENGINE


def _nim_available() -> bool:
    try:
        from src.ai_engine.nim_client import get_default_client

        return bool(get_default_client().configured)
    except Exception:  # noqa: BLE001
        return False


def run_closed_loop_sync(
    target: Optional[RecipeTarget] = None,
    max_iterations: int = 40,
    seed: int = 0,
    use_nim: Optional[bool] = None,
) -> Dict[str, Any]:
    """Run the loop synchronously and return the full result (used by tests
    and the bounded end-to-end verification endpoint)."""
    if use_nim is None:
        use_nim = _nim_available()
    return get_closed_loop().run(
        target=target, max_iterations=max_iterations, seed=seed, use_nim=use_nim,
    )


def _run_background(target: RecipeTarget, max_iterations: int,
                    seed: int, use_nim: bool) -> None:
    def should_continue() -> bool:
        with _CL_LOCK:
            return _CL_STATE["running"]

    def on_iteration(state: Dict[str, Any]) -> None:
        with _CL_LOCK:
            _CL_STATE["iteration"] = state["iteration"]
            _CL_STATE["best_score"] = state["best_score"]
            _CL_STATE["best_material"] = state["best_material"]

    try:
        result = get_closed_loop().run(
            target=target, max_iterations=max_iterations, seed=seed,
            use_nim=use_nim, should_continue=should_continue,
            on_iteration=on_iteration,
        )
        with _CL_LOCK:
            _CL_STATE["result"] = result
            _CL_STATE["converged"] = result["converged"]
    except Exception as exc:  # noqa: BLE001
        logger.exception("closed-loop background run failed")
        with _CL_LOCK:
            _CL_STATE["error"] = str(exc)
    finally:
        with _CL_LOCK:
            _CL_STATE["running"] = False
            _CL_STATE["stopped_at"] = datetime.now(timezone.utc).isoformat()


def start_closed_loop(
    target: Optional[RecipeTarget] = None,
    max_iterations: int = 40,
    seed: int = 0,
) -> Dict[str, Any]:
    target = target or RecipeTarget()
    with _CL_LOCK:
        if _CL_STATE["running"]:
            return {"status": "already_running", "iteration": _CL_STATE["iteration"]}
        _CL_STATE.update({
            "running": True, "iteration": 0, "best_score": 0.0,
            "best_material": None, "converged": False, "error": None,
            "result": None, "started_at": datetime.now(timezone.utc).isoformat(),
            "stopped_at": None,
        })
    use_nim = _nim_available()
    t = threading.Thread(
        target=_run_background,
        args=(target, max_iterations, seed, use_nim),
        daemon=True, name="ClosedLoopDiscovery",
    )
    _CL_STATE["thread"] = t
    t.start()
    return {"status": "started", "max_iterations": max_iterations,
            "use_nim": use_nim, "target": target.to_dict()}


def stop_closed_loop() -> Dict[str, Any]:
    with _CL_LOCK:
        _CL_STATE["running"] = False
    return {"status": "stop_requested"}


def closed_loop_status() -> Dict[str, Any]:
    with _CL_LOCK:
        return {k: v for k, v in _CL_STATE.items() if k != "thread"}


def closed_loop_result() -> Dict[str, Any]:
    with _CL_LOCK:
        result = _CL_STATE.get("result")
    if result is None:
        return {"status": "no_result", "message": "Run the closed loop first."}
    return result
