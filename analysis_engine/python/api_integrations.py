from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApiResult:
    ok: bool
    source: str
    message: str
    data: Any = None


def infer_formula_from_text(text: str) -> str | None:
    aliases = {
        "ferric oxide": "Fe2O3",
        "iron oxide": "Fe2O3",
        "hematite": "Fe2O3",
        "rgo": "C",
        "graphene oxide": "C",
        "graphene": "C",
        "cobalt chromite": "CoCr2O4",
        "cocr2o4": "CoCr2O4",
    }
    lowered = text.lower()
    for key, formula in aliases.items():
        if key in lowered:
            return formula
    match = re.search(r"\b(?:[A-Z][a-z]?\d*){2,}\b", text)
    return match.group(0) if match else None


def materials_project_lookup(query: str | None, api_key: str | None = None, max_results: int = 5) -> ApiResult:
    formula = infer_formula_from_text(query or "") if query else None
    if not formula:
        return ApiResult(False, "Materials Project", "No material formula/name was supplied or inferred.")

    key = api_key or os.getenv("MP_API_KEY") or os.getenv("MATERIALS_PROJECT_API_KEY")
    if not key:
        return ApiResult(False, "Materials Project", "MP_API_KEY is not configured; material lookup was skipped.")

    try:
        from mp_api.client import MPRester
    except Exception as exc:
        return ApiResult(False, "Materials Project", f"mp-api is not installed or importable: {exc}")

    try:
        fields = [
            "material_id",
            "formula_pretty",
            "band_gap",
            "energy_above_hull",
            "formation_energy_per_atom",
            "is_stable",
            "symmetry",
        ]
        with MPRester(api_key=key) as mpr:
            docs = mpr.materials.summary.search(formula=formula, fields=fields)[:max_results]
        rows = []
        for doc in docs:
            symmetry = getattr(doc, "symmetry", None)
            rows.append(
                {
                    "material_id": str(getattr(doc, "material_id", "")),
                    "formula": getattr(doc, "formula_pretty", ""),
                    "band_gap_eV": getattr(doc, "band_gap", None),
                    "energy_above_hull_eV_atom": getattr(doc, "energy_above_hull", None),
                    "formation_energy_eV_atom": getattr(doc, "formation_energy_per_atom", None),
                    "is_stable": getattr(doc, "is_stable", None),
                    "crystal_system": getattr(symmetry, "crystal_system", None) if symmetry else None,
                    "space_group": getattr(symmetry, "symbol", None) if symmetry else None,
                }
            )
        if not rows:
            return ApiResult(False, "Materials Project", f"No Materials Project matches found for {formula}.")
        return ApiResult(True, "Materials Project", f"Found {len(rows)} candidate materials for {formula}.", rows)
    except Exception as exc:
        return ApiResult(False, "Materials Project", f"Materials Project lookup failed: {exc}")


def nvidia_nim_commentary(summary: dict, api_key: str | None = None, model: str | None = None) -> ApiResult:
    key = api_key or os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY")
    if not key:
        return ApiResult(False, "NVIDIA NIM", "NVIDIA_API_KEY is not configured; AI commentary was skipped.")

    try:
        import requests
    except Exception as exc:
        return ApiResult(False, "NVIDIA NIM", f"requests is not installed or importable: {exc}")

    base_url = os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    selected_model = model or os.getenv("NVIDIA_NIM_MODEL", "nvidia/llama-3.1-nemotron-nano-8b-v1")
    prompt = (
        "You are an electrochemistry analysis assistant. Give concise, cautious, "
        "auditable comments for the following analysis. Do not invent material claims. "
        "Flag uncertainty and suggest checks.\n\n"
        + json.dumps(summary, indent=2, default=str)[:12000]
    )
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": "You write rigorous electrochemistry analysis notes."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 900,
            },
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        return ApiResult(True, "NVIDIA NIM", "AI commentary generated.", {"model": selected_model, "text": text})
    except Exception as exc:
        return ApiResult(False, "NVIDIA NIM", f"NVIDIA NIM commentary failed: {exc}")
