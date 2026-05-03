"""
Alchemist Canvas combinatorial generator
=========================================

Given a researcher-selected set of *blocks* from the curated materials
database, enumerate every reasonable composite (1 to ``max_components``
components, with mass fractions stepped by ``step_pct``), evaluate each
candidate against simple-but-grounded mixture rules, and rank the survivors
by how well they meet the user's constraints (target capacitance,
conductivity floor, cost ceiling, etc.).

Why:

  - The previous AlchemistCanvas simply asked an LLM for a "synthesis
    protocol" for an arbitrary user-typed formula. That gave the user free
    rein to hallucinate non-existent materials. **No combinator path
    here ever invents a material**; we strictly draw from the curated DB.
  - Mixture rules used:

      conductivity_S_m   ≈ Σ wᵢ · σᵢ            (weighted average,
                                                  upper-bound for parallel
                                                  conduction; OK for
                                                  composites > percolation
                                                  threshold)
      density_g_cm3      ≈ Σ wᵢ · ρᵢ            (mass-fraction average)
      capacitance_F_g    ≈ Σ wᵢ · Cᵢ            (where Cᵢ = typical_capacitance
                                                  for pseudocapacitive blocks,
                                                  derived from typical_Cdl ·
                                                  surface_area otherwise)
      cost_relative      ≈ Σ wᵢ · cᵢ
      stability_score    = product of per-material electrochemical_window
                           contributions, clipped to [0, 1]

    These are deliberately first-order; rule-of-mixtures is what most
    research papers eyeball before fab. For "publish-grade" estimates
    the user is meant to follow up with an actual synthesis + EIS run.

  - We DO NOT call any LLM in the inner loop. Every number out is
    deterministic from the inputs. The caller may optionally pass the
    top-N candidates to a separate `/api/v2/alchemi/chat` call to draft
    a synthesis protocol, but the mixture properties we report stay
    grounded.
"""
from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from src.backend.core.engines.materials import MATERIAL_DATABASE

logger = logging.getLogger(__name__)


# ── Library blocks (extends MATERIAL_DATABASE with derived fields) ────

def get_library() -> list[dict[str, Any]]:
    """
    Return the canonical block list for the AlchemistCanvas. Each entry
    has the fields the front-end needs, plus a derived `category` and
    `display_name`.
    """
    out = []
    for key, m in MATERIAL_DATABASE.items():
        out.append({
            "key": key,
            "display_name": _humanise(key),
            "formula": m.get("formula", key),
            "type": m.get("type", "unknown"),
            "category": _categorise(m),
            # Headline numbers for the UI card
            "conductivity_S_m": m.get("bulk_conductivity"),
            "surface_area_m2_g": m.get("theoretical_surface_area"),
            "density_g_cm3": m.get("density"),
            "cost_factor": m.get("cost_factor"),
            "pseudocapacitive": m.get("pseudocapacitive", False),
            "electrochemical_window_V": m.get("electrochemical_window"),
            "typical_capacitance_F_g": m.get("typical_capacitance"),
            "typical_Cdl_F_cm2": m.get("typical_Cdl"),
        })
    out.sort(key=lambda x: x["display_name"])
    return out


def _humanise(key: str) -> str:
    overrides = {
        "MnO2": "MnO₂",
        "Fe2O3": "Fe₂O₃",
        "NiMoO4": "NiMoO₄",
        "NiO": "NiO",
        "CNT": "Carbon nanotubes",
        "PEDOT_PSS": "PEDOT:PSS",
        "carbon_black": "Carbon black",
        "graphene": "Graphene",
        "reduced_graphene_oxide": "Reduced graphene oxide",
        "polyaniline": "Polyaniline (PANI)",
        "gold_nanoparticles": "Gold nanoparticles",
    }
    return overrides.get(key, key.replace("_", " ").title())


def _categorise(m: dict[str, Any]) -> str:
    t = (m.get("type") or "").lower()
    if "carbon" in t:
        return "Carbon"
    if "polymer" in t:
        return "Conducting polymer"
    if "metal_oxide" in t:
        return "Metal oxide"
    if "metal" in t and "oxide" not in t:
        return "Metal"
    return "Other"


# ── Constraints ──────────────────────────────────────────────────────

@dataclass
class Constraints:
    """User-supplied targets / budgets."""
    # Required-floor performance
    min_capacitance_F_g: Optional[float] = None
    min_conductivity_S_m: Optional[float] = None
    min_voltage_window_V: Optional[float] = None
    # Caps
    max_cost_relative: Optional[float] = None        # rule-of-mixtures average
    max_density_g_cm3: Optional[float] = None
    # Search shape
    max_components: int = 3
    step_pct: int = 25                               # mass-fraction step (25 → quarters)
    require_all_selected: bool = False               # if True, every selected block must appear

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class Candidate:
    """One enumerated composite."""
    composition: dict[str, float]            # block_key -> mass fraction (sums to 1.0)
    components: list[str]                    # ordered like the front-end displays
    fractions: list[float]
    properties: dict[str, Any]               # derived properties (mixture rules)
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "composition": self.composition,
            "components": self.components,
            "fractions": [round(f, 4) for f in self.fractions],
            "properties": self.properties,
            "score": round(self.score, 3),
            "reasons": self.reasons,
        }


# ── Mixture-rule property estimator ──────────────────────────────────

def _estimate_capacitance_F_g(block_key: str, m: dict[str, Any]) -> float:
    """
    Headline capacitance contribution for one block. Uses the typical
    pseudocapacitance value when available (MnO₂, PEDOT:PSS, …); for
    EDLC carbons we derive from typical_Cdl × surface area.
    """
    if m.get("typical_capacitance"):
        return float(m["typical_capacitance"])
    cdl = m.get("typical_Cdl")
    sa = m.get("theoretical_surface_area")
    if cdl is not None and sa is not None:
        # Cdl is F/cm²; SA is m²/g = 10⁴ cm²/g.
        return float(cdl) * float(sa) * 1e4
    return 0.0


def evaluate_composite(composition: dict[str, float]) -> dict[str, Any]:
    """
    Compute mixture-rule properties for a composition mapping
    block_key → mass fraction. The fractions must sum to 1.0; we
    re-normalise defensively.
    """
    if not composition:
        return {}

    total = sum(composition.values())
    if total <= 0:
        return {}
    norm = {k: v / total for k, v in composition.items()}

    cond = 0.0
    dens = 0.0
    cap  = 0.0
    cost = 0.0
    sa   = 0.0
    win  = 1.0
    pseudo_fraction = 0.0

    for key, frac in norm.items():
        m = MATERIAL_DATABASE.get(key)
        if m is None:
            continue
        cond += frac * float(m.get("bulk_conductivity", 0.0) or 0.0)
        dens += frac * float(m.get("density", 0.0) or 0.0)
        cost += frac * float(m.get("cost_factor", 0.5) or 0.5)
        sa   += frac * float(m.get("theoretical_surface_area", 0.0) or 0.0)
        cap  += frac * _estimate_capacitance_F_g(key, m)
        # Stability: take the minimum window across components (the weakest
        # link sets the cell voltage).
        w = float(m.get("electrochemical_window", 0.0) or 0.0)
        if w > 0:
            win = min(win, w)
        if m.get("pseudocapacitive"):
            pseudo_fraction += frac

    return {
        "conductivity_S_m":            cond,
        "density_g_cm3":               dens,
        "capacitance_F_g":             cap,
        "surface_area_m2_g":           sa,
        "cost_relative":               cost,
        "voltage_window_V":            win,
        "pseudocapacitive_fraction":   pseudo_fraction,
        "energy_density_Wh_per_kg":    0.5 * cap * win * win / 3.6,   # E = ½ C V² in Wh/kg
    }


# ── Candidate enumeration ───────────────────────────────────────────

def _fraction_grid(n: int, step_pct: int) -> Iterable[tuple[float, ...]]:
    """
    All `n`-tuples of mass fractions that:
      - sum to 1.0
      - each is a multiple of step_pct/100 ∈ (0, 1]
    Yields tuples in mass-fraction units (0.0–1.0).
    """
    if n < 1:
        return
    if step_pct < 5 or step_pct > 100 or 100 % step_pct != 0:
        raise ValueError(f"step_pct must divide 100 (got {step_pct})")
    units = 100 // step_pct
    # Generate all length-n compositions of `units` integer parts where each
    # part is ≥ 1 (no zero-fraction components — those would imply an
    # unselected block).
    if n == 1:
        yield (1.0,)
        return

    def rec(remaining: int, slots: int, prefix: tuple[int, ...]):
        if slots == 1:
            if remaining >= 1:
                yield prefix + (remaining,)
            return
        # leave at least 1 for each of the remaining slots
        for k in range(1, remaining - (slots - 1) + 1):
            yield from rec(remaining - k, slots - 1, prefix + (k,))

    for parts in rec(units, n, ()):
        yield tuple(p / units for p in parts)


def enumerate_candidates(
    selected: list[str],
    constraints: Constraints,
) -> list[Candidate]:
    """
    Walk every k-subset of `selected` for k ∈ [1, max_components], every
    mass-fraction permutation of that subset, evaluate, and keep the ones
    that pass the floor / cap filters.
    """
    selected = [s for s in dict.fromkeys(selected) if s in MATERIAL_DATABASE]
    if not selected:
        return []
    k_max = min(constraints.max_components, len(selected))
    if constraints.require_all_selected:
        k_min = len(selected)
        k_max = len(selected)
    else:
        k_min = 1

    candidates: list[Candidate] = []
    for k in range(k_min, k_max + 1):
        for combo in itertools.combinations(selected, k):
            for fracs in _fraction_grid(k, constraints.step_pct):
                composition = dict(zip(combo, fracs))
                props = evaluate_composite(composition)
                if not _passes(props, constraints):
                    continue
                cand = Candidate(
                    composition=composition,
                    components=list(combo),
                    fractions=list(fracs),
                    properties=props,
                )
                cand.score, cand.reasons = _score(props, constraints)
                candidates.append(cand)
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def _passes(props: dict[str, Any], c: Constraints) -> bool:
    if c.min_capacitance_F_g  is not None and props.get("capacitance_F_g",  0) < c.min_capacitance_F_g:  return False
    if c.min_conductivity_S_m is not None and props.get("conductivity_S_m", 0) < c.min_conductivity_S_m: return False
    if c.min_voltage_window_V is not None and props.get("voltage_window_V", 0) < c.min_voltage_window_V: return False
    if c.max_cost_relative    is not None and props.get("cost_relative",    1e9) > c.max_cost_relative:    return False
    if c.max_density_g_cm3    is not None and props.get("density_g_cm3",    1e9) > c.max_density_g_cm3:    return False
    return True


def _score(props: dict[str, Any], c: Constraints) -> tuple[float, list[str]]:
    """
    Composite score: 0.5·capacitance/target + 0.3·conductivity/target +
    0.2·(1 − cost/budget). Targets default to sensible scales when
    constraints aren't set.
    """
    reasons: list[str] = []
    cap_t  = c.min_capacitance_F_g  or 200.0
    cond_t = c.min_conductivity_S_m or 1.0
    cost_b = c.max_cost_relative    or 1.0

    cap   = props.get("capacitance_F_g", 0)
    cond  = props.get("conductivity_S_m", 0)
    cost  = props.get("cost_relative", 1.0)
    win   = props.get("voltage_window_V", 0)

    cap_term  = min(cap / cap_t, 2.0)              # capped at 2× target
    cond_term = min(cond / cond_t, 2.0)
    cost_term = max(0.0, 1.0 - (cost / cost_b))    # 0 when at budget, 1 when free
    win_term  = min(win / 1.0, 2.0)

    score = 0.45 * cap_term + 0.25 * cond_term + 0.15 * cost_term + 0.15 * win_term

    if cap >= cap_t:   reasons.append(f"meets capacitance target ({cap:.0f} ≥ {cap_t:.0f} F/g)")
    if cond >= cond_t: reasons.append(f"conductivity {cond:.2g} S/m above floor")
    if cost <= cost_b: reasons.append(f"cost {cost:.2f} within budget")
    if win >= 1.0:     reasons.append(f"{win:.2f} V working window (acceptable)")

    return score, reasons
