"""
Autonomous Hydrothermal Materials Discovery Engine
====================================================
Implements the system prompt philosophy:

  INPUTS → normalisation → ontology mapping → graph construction →
  verification → simulation/prediction → optimisation →
  candidate ranking → human experimental validation →
  feedback ingestion → continuous refinement

This module is the core orchestration intelligence.  It does NOT:
  - invent numerical values
  - fabricate synthesis conditions
  - hallucinate references
  - return unsupported conclusions

Every output includes confidence, uncertainty, provenance and assumptions.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Inventory ────────────────────────────────────────────────────────────────

_INVENTORY_PATH = Path(__file__).parent.parent.parent / "data" / "lab_inventory.json"
_inventory_cache: dict | None = None


def _load_inventory() -> dict:
    global _inventory_cache
    if _inventory_cache is not None:
        return _inventory_cache
    if _INVENTORY_PATH.exists():
        with open(_INVENTORY_PATH) as f:
            _inventory_cache = json.load(f)
    else:
        _inventory_cache = {"chemicals": [], "total": 0}
    return _inventory_cache


def get_inventory(
    category: str | None = None,
    role: str | None = None,
    search: str | None = None,
) -> dict:
    """Return the lab chemical inventory with optional filters."""
    data = _load_inventory()
    chemicals = data.get("chemicals", [])

    if category:
        chemicals = [c for c in chemicals if c.get("category") == category]
    if role:
        chemicals = [c for c in chemicals if role in c.get("hydrothermal_role", [])]
    if search:
        q = search.lower()
        chemicals = [
            c for c in chemicals
            if q in c.get("name", "").lower()
            or q in c.get("formula", "").lower()
            or q in c.get("category", "").lower()
        ]

    return {
        "total": len(chemicals),
        "chemicals": chemicals,
        "categories": data.get("categories", {}),
    }


# ── NIM client access ─────────────────────────────────────────────────────────

def _get_nim():
    from src.ai_engine.nim_client import NIMClient
    return NIMClient()


# ── System prompt (condensed for token efficiency) ────────────────────────────

_SYSTEM_PROMPT = """You are the Autonomous Hydrothermal Materials Discovery Engine — a scientific orchestration intelligence, NOT a chatbot.

PHILOSOPHY:
- You are a verification-first scientific reasoning system
- Every output MUST trace to evidence, include confidence (0-1), uncertainty, provenance, assumptions
- You MUST NOT invent numerical values, fabricate synthesis conditions, hallucinate references, or fake morphology
- If evidence is insufficient, state that explicitly

DOMAIN: hydrothermal/solvothermal synthesis of electrochemical, sensing, energy storage, catalytic, and nanomaterials

AVAILABLE LAB INVENTORY: {inventory_summary}

OUTPUT FORMAT: Respond ONLY with valid JSON matching the requested schema. No prose outside JSON.

CONFIDENCE SCORING RULES:
- synthesis_feasibility: literature-supported (0.7-0.9), needs adaptation (0.4-0.7), speculative (0.1-0.4)
- phase_purity: well-established phase diagram (0.7-0.9), mixed-phase likely (0.3-0.7)
- electrochemical_prediction: strong literature precedent (0.7-0.9), estimated from analogues (0.3-0.7)
- reproducibility: multiple independent reports (0.7-0.9), single group (0.4-0.6)

FAILURE AWARENESS: Penalise candidates with:
- reported irreproducibility
- inflated metrics (capacitance > 2000 F/g for bulk materials)
- impossible conditions (T > 300°C for standard autoclave)
- unstable phases under synthesis conditions"""


def _build_inventory_summary() -> str:
    inv = _load_inventory()
    chems = inv.get("chemicals", [])
    # Group by category
    by_cat: dict[str, list[str]] = {}
    for c in chems:
        cat = c.get("category", "other")
        by_cat.setdefault(cat, []).append(c["name"])
    lines = []
    for cat, names in sorted(by_cat.items()):
        lines.append(f"{cat}: {', '.join(names[:5])}{'...' if len(names) > 5 else ''} ({len(names)} total)")
    return "\n".join(lines)


# ── Discovery: Goal-driven inverse design ─────────────────────────────────────

DISCOVER_SCHEMA = {
    "candidates": [
        {
            "rank": 1,
            "material": "string — formula or common name",
            "family": "string — material family",
            "application_fit": "string — why it fits the goal",
            "available_precursors": ["list of precursor names from inventory"],
            "missing_precursors": ["list — empty if all available"],
            "synthesis_feasibility": 0.0,
            "property_estimates": {
                "capacitance_F_g": "number or null",
                "conductivity_S_cm": "number or null",
                "band_gap_eV": "number or null",
                "notes": "string"
            },
            "confidence": {
                "synthesis_feasibility": 0.0,
                "phase_purity": 0.0,
                "electrochemical_prediction": 0.0,
                "reproducibility": 0.0
            },
            "provenance": "string — key literature support",
            "assumptions": ["list of assumptions made"],
            "warnings": ["list of known failure modes or caveats"]
        }
    ],
    "reasoning": "string — scientific rationale for the candidate set",
    "search_space_reduction": "string — how this narrows the experimental space",
    "hitl_request": "string — what to synthesise and characterise first"
}


def discover(
    goal: str,
    target_properties: dict,
    constraints: dict,
    n_candidates: int = 5,
) -> dict:
    """
    Goal-driven inverse design.

    Parameters
    ----------
    goal : str
        Scientific objective, e.g. "high-capacitance alkaline supercapacitor electrode"
    target_properties : dict
        e.g. {"capacitance_F_g": ">500", "conductivity": "high", "stability_cycles": ">5000"}
    constraints : dict
        e.g. {"max_temperature_C": 200, "available_only": True, "avoid_toxic": True}
    n_candidates : int
        Number of ranked candidates to return (max 8)
    """
    nim = _get_nim()
    if not nim.configured:
        return {
            "error": "NIM_NOT_CONFIGURED",
            "message": "Set NVIDIA_API_KEY to enable AI-powered discovery.",
            "candidates": [],
            "reasoning": "Engine unavailable — no API key.",
        }

    n_candidates = min(n_candidates, 8)
    inv_summary = _build_inventory_summary()

    user_prompt = f"""Perform goal-driven inverse design for:

GOAL: {goal}

TARGET PROPERTIES:
{json.dumps(target_properties, indent=2)}

CONSTRAINTS:
{json.dumps(constraints, indent=2)}

Return exactly {n_candidates} ranked candidate materials.

For each candidate:
1. Verify precursors exist in the lab inventory
2. Estimate synthesis feasibility for hydrothermal/solvothermal route
3. Estimate electrochemical properties from literature (with confidence)
4. Flag any known failure modes

Respond with VALID JSON only, matching this schema:
{json.dumps(DISCOVER_SCHEMA, indent=2)}"""

    system = _SYSTEM_PROMPT.format(inventory_summary=inv_summary)

    try:
        result = nim.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        text = result.text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        parsed["model"] = result.model
        parsed["tokens"] = result.total_tokens
        return parsed
    except json.JSONDecodeError as e:
        logger.error("discover: JSON parse error: %s", e)
        return {"error": "PARSE_ERROR", "raw": result.text[:500], "candidates": []}
    except Exception as e:
        logger.error("discover: NIM call failed: %s", e)
        return {"error": str(e), "candidates": []}


# ── Synthesis planning ─────────────────────────────────────────────────────────

SYNTHESIS_SCHEMA = {
    "material": "string",
    "method": "hydrothermal | solvothermal | co-precipitation | sol-gel",
    "precursors": [
        {
            "chemical": "name from inventory",
            "role": "string",
            "concentration_mM": "number",
            "mass_mg_per_50mL": "number",
            "available": True
        }
    ],
    "conditions": {
        "solvent": "string",
        "total_volume_mL": 50,
        "pH_initial": "number",
        "pH_adjuster": "string or null",
        "temperature_C": "number",
        "dwell_time_h": "number",
        "pressure_atm_estimated": "number",
        "autoclave_fill_fraction": "number (0.6–0.8 recommended)",
        "stirring": "string",
        "atmosphere": "air | N2 | Ar"
    },
    "post_processing": [
        {
            "step": "string",
            "temperature_C": "number or null",
            "duration_h": "number or null",
            "atmosphere": "string or null",
            "purpose": "string"
        }
    ],
    "expected_morphology": "string",
    "expected_phase": "string",
    "characterisation_checklist": ["XRD", "SEM", "BET", "CV", "EIS"],
    "safety_notes": ["list of hazards and PPE requirements"],
    "confidence": {
        "synthesis_feasibility": 0.0,
        "phase_purity": 0.0,
        "morphology": 0.0,
        "reproducibility": 0.0
    },
    "provenance": "string",
    "assumptions": ["list"],
    "warnings": ["list"]
}


def synthesize(
    material: str,
    application: str,
    scale_mL: float = 50.0,
    constraints: dict | None = None,
) -> dict:
    """
    Generate a detailed hydrothermal synthesis route for a given material.
    """
    nim = _get_nim()
    if not nim.configured:
        return {
            "error": "NIM_NOT_CONFIGURED",
            "message": "Set NVIDIA_API_KEY to enable synthesis planning.",
        }

    inv = _load_inventory()
    available_names = [c["name"] for c in inv.get("chemicals", [])]

    user_prompt = f"""Plan a complete hydrothermal/solvothermal synthesis route for:

MATERIAL: {material}
APPLICATION: {application}
SCALE: {scale_mL} mL autoclave

AVAILABLE PRECURSORS (use only these):
{chr(10).join(f'  - {n}' for n in available_names)}

CONSTRAINTS: {json.dumps(constraints or {}, indent=2)}

Requirements:
- Prioritise available precursors; mark any external procurement needed
- Temperature MUST be ≤ 220°C (standard Teflon autoclave limit)
- Include step-by-step post-processing (washing, drying, annealing if needed)
- Include realistic confidence scores based on literature evidence
- Flag safety hazards

Respond with VALID JSON only, matching this schema:
{json.dumps(SYNTHESIS_SCHEMA, indent=2)}"""

    system = _SYSTEM_PROMPT.format(
        inventory_summary=f"{len(available_names)} chemicals available (see precursors list above)"
    )

    try:
        result = nim.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
            temperature=0.2,
            max_tokens=2500,
        )
        text = result.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        parsed["model"] = result.model
        parsed["tokens"] = result.total_tokens
        return parsed
    except json.JSONDecodeError as e:
        logger.error("synthesize: JSON parse error: %s", e)
        return {"error": "PARSE_ERROR", "raw": result.text[:500] if hasattr(result, 'text') else str(e)}
    except Exception as e:
        logger.error("synthesize: NIM call failed: %s", e)
        return {"error": str(e)}


# ── Electrochemical interpretation ─────────────────────────────────────────────

INTERPRET_SCHEMA = {
    "material_candidates": ["list of materials consistent with this electrochemical signature"],
    "cv_analysis": {
        "redox_couples": ["list of identified redox peaks with assignments"],
        "charge_storage_mechanism": "EDLC | faradaic | pseudocapacitive | battery-like | mixed",
        "estimated_capacitance_F_g": "number or null",
        "confidence": 0.0
    },
    "eis_analysis": {
        "circuit_assignment": "string",
        "Rs_interpretation": "string",
        "Rct_interpretation": "string",
        "diffusion_regime": "string",
        "confidence": 0.0
    },
    "synthesis_implications": "string — what the electrochemical signature implies about synthesis quality",
    "recommended_optimisations": ["list of synthesis parameter changes to try"],
    "confidence": 0.0,
    "provenance": "string",
    "warnings": ["list"]
}


def interpret_electrochemistry(
    cv_data: dict | None = None,
    eis_data: dict | None = None,
    material_context: str = "",
) -> dict:
    """Interpret electrochemical data and correlate with synthesis/material state."""
    nim = _get_nim()
    if not nim.configured:
        return {"error": "NIM_NOT_CONFIGURED"}

    data_desc = []
    if cv_data:
        data_desc.append(f"CV data: {json.dumps(cv_data)[:800]}")
    if eis_data:
        data_desc.append(f"EIS data (fitted params): {json.dumps(eis_data)[:800]}")
    if material_context:
        data_desc.append(f"Material context: {material_context}")

    if not data_desc:
        return {"error": "NO_DATA", "message": "Provide CV and/or EIS data for interpretation."}

    user_prompt = f"""Interpret the following electrochemical data scientifically:

{chr(10).join(data_desc)}

Correlate with expected material states.
Identify charge storage mechanism.
Suggest synthesis optimisations based on what the electrochemistry reveals.

Respond with VALID JSON only:
{json.dumps(INTERPRET_SCHEMA, indent=2)}"""

    try:
        result = nim.chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT.format(inventory_summary="(not needed for interpretation)")},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        text = result.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        logger.error("interpret_electrochemistry: %s", e)
        return {"error": str(e)}


# ── Knowledge graph helpers ───────────────────────────────────────────────────

# In-memory graph: nodes are dicts, edges are {from, to, relation}
_graph_nodes: list[dict] = []
_graph_edges: list[dict] = []


def add_graph_node(node_type: str, label: str, properties: dict | None = None) -> str:
    nid = f"{node_type}:{label}:{int(time.time()*1000)}"
    _graph_nodes.append({"id": nid, "type": node_type, "label": label, "properties": properties or {}})
    return nid


def add_graph_edge(from_id: str, to_id: str, relation: str) -> None:
    _graph_edges.append({"from": from_id, "to": to_id, "relation": relation})


def get_graph() -> dict:
    return {"nodes": _graph_nodes, "edges": _graph_edges,
            "node_count": len(_graph_nodes), "edge_count": len(_graph_edges)}


# ── Failure tracking ──────────────────────────────────────────────────────────

_failures: list[dict] = []


def record_failure(material: str, conditions: dict, failure_mode: str, notes: str = "") -> None:
    _failures.append({
        "material": material,
        "conditions": conditions,
        "failure_mode": failure_mode,
        "notes": notes,
        "timestamp": time.time(),
    })
    logger.warning("Hydrothermal failure recorded: %s — %s", material, failure_mode)


def get_failures(material: str | None = None) -> list[dict]:
    if material:
        return [f for f in _failures if material.lower() in f["material"].lower()]
    return list(_failures)


# ── Feedback ingestion ────────────────────────────────────────────────────────

_feedback: list[dict] = []


def ingest_feedback(
    candidate_material: str,
    experiment_result: str,
    characterisation: dict,
    electrochemical_data: dict | None = None,
    success: bool = True,
) -> dict:
    """Record human experimental validation results."""
    entry = {
        "material": candidate_material,
        "success": success,
        "result": experiment_result,
        "characterisation": characterisation,
        "electrochemical_data": electrochemical_data or {},
        "timestamp": time.time(),
    }
    _feedback.append(entry)

    # Update knowledge graph
    nid = add_graph_node("experiment", candidate_material, {"success": success, "result": experiment_result})
    add_graph_edge(nid, f"material:{candidate_material}", "characterised_by")

    # Record failures for future penalisation
    if not success:
        record_failure(
            candidate_material,
            characterisation.get("conditions", {}),
            experiment_result,
            notes="Human validation feedback",
        )

    return {"status": "recorded", "entry": entry, "graph_node": nid}
