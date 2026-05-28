"""
NVIDIA Material Discovery Integration
========================================
Connects RĀMAN Studio to NVIDIA NIM inference endpoints for:

1. Material Discovery — Generate candidate material compositions
   for target electrochemical properties.
2. Synthesis Route Generation — Suggest optimal synthesis pathways
   for a given material, grounded in literature data.
3. Application-Matched Material Recommendation — Given a target
   application (e.g., "Pb2+ detection"), return the best
   nanomaterial + electrode architecture ranked by predicted
   performance.

Requires:
    NVIDIA_API_KEY  (set in .env, obtained from https://build.nvidia.com)

Author: VidyuthLabs
Date: May 8, 2026
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/llama-3.1-nemotron-70b-instruct"
FALLBACK_MODEL = "meta/llama-3.1-8b-instruct"
MAX_TOKENS = 2048
TEMPERATURE = 0.3  # Low temperature for deterministic, grounded answers


@dataclass
class MaterialCandidate:
    """A candidate material returned by NVIDIA discovery."""
    name: str
    formula: str
    category: str
    predicted_properties: Dict[str, Any] = field(default_factory=dict)
    synthesis_route: str = ""
    confidence: float = 0.0
    source: str = "nvidia_nim"
    rationale: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SynthesisRoute:
    """A synthesis route for a target material."""
    method: str
    steps: List[str] = field(default_factory=list)
    temperature_C: Optional[float] = None
    duration_hours: Optional[float] = None
    precursors: List[str] = field(default_factory=list)
    solvents: List[str] = field(default_factory=list)
    expected_yield: Optional[str] = None
    safety_notes: str = ""
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _get_api_key() -> Optional[str]:
    """Retrieve NVIDIA API key from environment."""
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key:
        logger.warning(
            "NVIDIA_API_KEY not set. Material discovery features unavailable. "
            "Get a key from https://build.nvidia.com"
        )
        return None
    return key


def _call_nvidia_chat(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
) -> Optional[str]:
    """
    Call the NVIDIA NIM chat completion endpoint.

    Uses only stdlib to avoid adding extra dependencies.
    Falls back gracefully if the API is unreachable.
    """
    import urllib.request
    import urllib.error

    api_key = _get_api_key()
    if not api_key:
        return None

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    url = f"{NVIDIA_BASE_URL}/chat/completions"

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        choices = result.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return None

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        logger.error("NVIDIA API HTTP %d: %s", e.code, body[:200])
        return None
    except Exception as e:
        logger.error("NVIDIA API call failed: %s", e)
        return None


# ── Public API ───────────────────────────────────────────────────

SYSTEM_PROMPT_DISCOVERY = """You are an expert electrochemist and materials scientist from the year 2326.
You have perfect knowledge of all nanomaterials, their electrochemical properties,
synthesis routes, and applications. You respond ONLY with valid JSON.

When asked about materials, always provide:
- Exact chemical formulas
- Specific numerical values for electrochemical properties
- Grounded synthesis routes with temperatures, durations, and precursors
- Safety considerations
- Expected performance metrics (capacitance, LOD, Rct, etc.)

Never fabricate references. If uncertain, say so in the rationale field."""


def discover_materials(
    target_application: str,
    constraints: Optional[Dict[str, Any]] = None,
    max_candidates: int = 5,
) -> List[MaterialCandidate]:
    """
    Discover candidate materials for a target application.

    Args:
        target_application: e.g., "Pb2+ detection biosensor",
                            "supercapacitor electrode", "glucose sensor"
        constraints: Optional dict of constraints, e.g.,
                     {"max_cost": "low", "substrate": "screen-printed carbon"}
        max_candidates: Maximum number of candidates to return

    Returns:
        List of MaterialCandidate objects ranked by predicted performance
    """
    constraint_text = ""
    if constraints:
        constraint_text = "\nConstraints: " + json.dumps(constraints)

    prompt = f"""Suggest the top {max_candidates} nanomaterial compositions for the following application:

Application: {target_application}{constraint_text}

Return a JSON array where each element has:
- "name": human-readable material name
- "formula": chemical formula
- "category": material category (e.g., "MOF", "MXene", "metal_oxide", "carbon", "polymer")
- "predicted_properties": dict with relevant electrochemical metrics
- "synthesis_route": one-line summary of the best synthesis method
- "confidence": float 0-1 indicating confidence
- "rationale": why this material is suitable

Return ONLY the JSON array, no markdown fences."""

    response = _call_nvidia_chat(prompt, system_prompt=SYSTEM_PROMPT_DISCOVERY)

    if not response:
        logger.info("NVIDIA API unavailable; returning built-in fallback candidates")
        return _get_fallback_candidates(target_application)

    try:
        # Parse response — handle potential markdown fencing
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        candidates_data = json.loads(text)

        candidates = []
        for item in candidates_data[:max_candidates]:
            candidates.append(MaterialCandidate(
                name=item.get("name", "Unknown"),
                formula=item.get("formula", ""),
                category=item.get("category", "unknown"),
                predicted_properties=item.get("predicted_properties", {}),
                synthesis_route=item.get("synthesis_route", ""),
                confidence=float(item.get("confidence", 0.5)),
                rationale=item.get("rationale", ""),
            ))

        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Failed to parse NVIDIA response: %s", e)
        return _get_fallback_candidates(target_application)


def suggest_synthesis(
    material_name: str,
    material_formula: str,
    target_form: str = "nanoparticles",
) -> List[SynthesisRoute]:
    """
    Suggest synthesis routes for a given material.

    Args:
        material_name: e.g., "MoS2", "ZIF-67"
        material_formula: chemical formula
        target_form: desired morphology (nanoparticles, thin_film, nanosheets, etc.)

    Returns:
        List of SynthesisRoute objects
    """
    prompt = f"""Provide the top 3 synthesis routes for preparing {material_name} ({material_formula})
in the form of {target_form}.

Return a JSON array where each element has:
- "method": synthesis method name (e.g., "hydrothermal", "CVD", "electrodeposition")
- "steps": array of step-by-step instructions
- "temperature_C": processing temperature in Celsius (null if ambient)
- "duration_hours": total processing time in hours
- "precursors": array of chemical precursors needed
- "solvents": array of solvents used
- "expected_yield": expected yield description
- "safety_notes": safety considerations
- "references": array of DOI strings for relevant papers (empty if unsure)

Return ONLY the JSON array, no markdown fences."""

    response = _call_nvidia_chat(prompt, system_prompt=SYSTEM_PROMPT_DISCOVERY)

    if not response:
        return _get_fallback_synthesis(material_name)

    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        routes_data = json.loads(text)

        routes = []
        for item in routes_data[:3]:
            routes.append(SynthesisRoute(
                method=item.get("method", "unknown"),
                steps=item.get("steps", []),
                temperature_C=item.get("temperature_C"),
                duration_hours=item.get("duration_hours"),
                precursors=item.get("precursors", []),
                solvents=item.get("solvents", []),
                expected_yield=item.get("expected_yield"),
                safety_notes=item.get("safety_notes", ""),
                references=item.get("references", []),
            ))
        return routes

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Failed to parse synthesis response: %s", e)
        return _get_fallback_synthesis(material_name)


def recommend_we_coating(
    target_analyte: str,
    electrode_substrate: str = "screen-printed carbon",
    technique: str = "CV",
) -> Dict[str, Any]:
    """
    Recommend the optimal Working Electrode (WE) nanomaterial coating
    for detecting a specific analyte.

    Args:
        target_analyte: e.g., "Pb2+", "glucose", "cortisol", "dopamine"
        electrode_substrate: base electrode material
        technique: electrochemical technique (CV, EIS, DPV, SWV, etc.)

    Returns:
        Dict with recommendation details
    """
    prompt = f"""You are an expert electrochemist. Recommend the BEST nanomaterial coating
for a working electrode to detect {target_analyte}.

Context:
- Electrode substrate: {electrode_substrate}
- Primary technique: {technique}
- Goal: Maximum sensitivity and selectivity for {target_analyte}

Return a JSON object with:
- "primary_coating": best nanomaterial name and formula
- "secondary_modifier": optional secondary modifier (e.g., enzyme, aptamer, MIP)
- "coating_method": recommended deposition method
- "expected_lod": expected limit of detection with units
- "expected_sensitivity": expected sensitivity with units
- "linear_range": expected linear range
- "selectivity_strategy": how selectivity is achieved
- "rationale": detailed scientific rationale
- "alternatives": array of 2 alternative coating options (name + formula each)

Return ONLY the JSON object, no markdown fences."""

    response = _call_nvidia_chat(prompt, system_prompt=SYSTEM_PROMPT_DISCOVERY)

    if not response:
        return _get_fallback_recommendation(target_analyte, electrode_substrate)

    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        return json.loads(text)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Failed to parse recommendation: %s", e)
        return _get_fallback_recommendation(target_analyte, electrode_substrate)


# ── Fallback Knowledge Base (No API Required) ───────────────────

_FALLBACK_MATERIALS = {
    "Pb2+": [
        MaterialCandidate("Bismuth Film on rGO", "Bi/rGO", "composite",
                          {"LOD": "0.1 ppb", "linear_range": "0.5-120 ppb", "technique": "SWASV"},
                          "Electrodeposition of Bi on drop-cast rGO/GCE", 0.95,
                          rationale="Bi film electrodes are the gold standard for lead detection, replacing toxic mercury."),
        MaterialCandidate("Gold Nanoparticles on MWCNTs", "AuNP/MWCNT", "composite",
                          {"LOD": "0.05 ppb", "linear_range": "0.1-100 ppb", "technique": "DPASV"},
                          "Chemical reduction of HAuCl4 onto MWCNT-modified SPE", 0.90,
                          rationale="AuNPs enhance electron transfer; MWCNTs provide high surface area for Pb2+ accumulation."),
    ],
    "glucose": [
        MaterialCandidate("GOx/Chitosan/AuNP", "GOx/Chi/Au", "bio-composite",
                          {"LOD": "5 µM", "sensitivity": "65 µA/mM/cm²", "linear_range": "0.01-8 mM"},
                          "Layer-by-layer: AuNP electrodeposition → chitosan drop-cast → GOx immobilization", 0.95,
                          rationale="Enzymatic glucose sensor with GOx provides high selectivity. AuNPs enhance DET."),
        MaterialCandidate("NiCo2O4 Nanosheets", "NiCo2O4", "metal_oxide",
                          {"LOD": "0.17 µM", "sensitivity": "2010 µA/mM/cm²", "linear_range": "0.001-3.0 mM"},
                          "Hydrothermal synthesis on Ni foam, 150°C, 6h", 0.90,
                          rationale="Non-enzymatic sensor. Spinel oxide provides excellent electrocatalytic glucose oxidation in alkaline media."),
    ],
    "dopamine": [
        MaterialCandidate("rGO/MoS2/AuNP", "rGO/MoS2/Au", "composite",
                          {"LOD": "0.05 µM", "sensitivity": "420 µA/mM/cm²", "linear_range": "0.1-200 µM"},
                          "MoS2 nanosheets on rGO via hydrothermal, then AuNP electrodeposition", 0.92,
                          rationale="MoS2/rGO heterostructure enhances π-π stacking with dopamine. AuNPs catalyze oxidation."),
    ],
    "cortisol": [
        MaterialCandidate("Anti-cortisol Ab/SAM/AuNP/SPE", "Ab/SAM/Au/SPE", "immunosensor",
                          {"LOD": "0.1 ng/mL", "linear_range": "0.5-200 ng/mL", "technique": "EIS"},
                          "SAM on AuNP-modified SPE → antibody conjugation via EDC/NHS", 0.88,
                          rationale="Label-free impedimetric immunosensor. SAM provides oriented antibody attachment."),
    ],
    "supercapacitor": [
        MaterialCandidate("NiCo-LDH on Carbon Cloth", "NiCo-LDH/CC", "composite",
                          {"specific_capacitance": "2350 F/g at 1 A/g", "cycle_retention": "94% after 10000 cycles"},
                          "Electrodeposition on carbon cloth, 25°C, 10 min", 0.93,
                          rationale="LDH nanosheets directly grown on CC give binder-free electrode with ultrafast ion diffusion."),
        MaterialCandidate("Ti3C2Tx MXene/PANI", "Ti3C2Tx/PANI", "composite",
                          {"specific_capacitance": "503 F/g at 1 A/g", "cycle_retention": "98% after 5000 cycles"},
                          "In-situ polymerization of aniline on delaminated Ti3C2Tx", 0.90,
                          rationale="MXene provides metallic conductivity; PANI adds pseudocapacitance."),
    ],
}


def _get_fallback_candidates(target_application: str) -> List[MaterialCandidate]:
    """Return built-in candidates when NVIDIA API is unavailable."""
    app_lower = target_application.lower()
    for key, candidates in _FALLBACK_MATERIALS.items():
        if key.lower() in app_lower:
            return candidates
    # Generic fallback
    return [
        MaterialCandidate(
            "rGO/AuNP Composite", "rGO/Au", "composite",
            {"Rct": "< 50 Ω", "surface_area": "> 500 m²/g"},
            "Hummers method → reduction → HAuCl4 chemical reduction",
            0.70,
            rationale="General-purpose high-performance electrode material with excellent conductivity and biocompatibility.",
        )
    ]


def _get_fallback_synthesis(material_name: str) -> List[SynthesisRoute]:
    """Return a generic synthesis route when NVIDIA API is unavailable."""
    return [SynthesisRoute(
        method="hydrothermal",
        steps=[
            f"Dissolve precursors for {material_name} in DI water",
            "Transfer to Teflon-lined autoclave",
            "Heat at 180°C for 12 hours",
            "Cool naturally to room temperature",
            "Wash with DI water and ethanol (3x each)",
            "Dry at 60°C overnight",
        ],
        temperature_C=180.0,
        duration_hours=12.0,
        precursors=["See literature for specific precursors"],
        solvents=["DI water", "ethanol"],
        expected_yield="~70-80%",
        safety_notes="Use fume hood. Autoclave may build pressure.",
    )]


def _get_fallback_recommendation(
    target_analyte: str, substrate: str
) -> Dict[str, Any]:
    """Return a built-in recommendation when NVIDIA API is unavailable."""
    app_lower = target_analyte.lower()
    if "pb" in app_lower or "lead" in app_lower:
        return {
            "primary_coating": "Bismuth nanoparticles on reduced graphene oxide (Bi/rGO)",
            "secondary_modifier": "None (non-enzymatic)",
            "coating_method": "Drop-casting rGO suspension + Bi electrodeposition",
            "expected_lod": "0.1 ppb",
            "expected_sensitivity": "15 µA/ppb",
            "linear_range": "0.5-120 ppb",
            "selectivity_strategy": "Bi film provides selective stripping peaks for Pb2+ vs Cd2+, Cu2+",
            "rationale": "Bi is the environmentally friendly replacement for mercury film electrodes. rGO enhances surface area and electron transfer kinetics.",
            "alternatives": [
                {"name": "AuNP/MWCNT", "formula": "Au/MWCNT"},
                {"name": "Fe3O4/Chitosan/GCE", "formula": "Fe3O4/Chi"},
            ],
        }
    # Generic
    return {
        "primary_coating": f"rGO/AuNP composite for {target_analyte} detection",
        "secondary_modifier": "Application-specific biorecognition element",
        "coating_method": "Drop-casting + electrodeposition",
        "expected_lod": "Depends on analyte",
        "expected_sensitivity": "Depends on analyte",
        "linear_range": "Depends on analyte",
        "selectivity_strategy": "Biorecognition element (antibody/aptamer/MIP)",
        "rationale": "rGO/AuNP is a versatile high-surface-area platform adaptable to most analytes.",
        "alternatives": [
            {"name": "MWCNT/PEDOT:PSS", "formula": "MWCNT/PEDOT:PSS"},
            {"name": "MoS2/AuNP", "formula": "MoS2/Au"},
        ],
    }


# ── CLI Entry Point ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python nvidia_integration.py <application>")
        print("Example: python nvidia_integration.py 'Pb2+ detection biosensor'")
        sys.exit(1)

    application = " ".join(sys.argv[1:])
    print(f"\n{'='*70}")
    print(f"  NVIDIA Material Discovery: {application}")
    print(f"{'='*70}\n")

    candidates = discover_materials(application)
    for i, c in enumerate(candidates, 1):
        print(f"{i}. {c.name} ({c.formula})")
        print(f"   Category: {c.category}")
        print(f"   Confidence: {c.confidence:.2f}")
        print(f"   Properties: {c.predicted_properties}")
        print(f"   Synthesis: {c.synthesis_route}")
        print(f"   Rationale: {c.rationale}")
        print()
