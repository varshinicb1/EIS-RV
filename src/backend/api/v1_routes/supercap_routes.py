"""
Supercapacitor analysis routes.

  GET  /api/v2/supercap/analyze/{dataset_id}        — full Cs/b/ESR/Ragone report
  POST /api/v2/supercap/analyze/raw                 — same, but with arrays in the body
  POST /api/v2/supercap/suggest-next                — NIM-powered next-experiment recommendation

All routes are gated by a license / trial. The recommender uses the
configured NVIDIA NIM and feeds it ONLY the structured analysis report
plus the user's stated target — never the raw arrays — so the prompt
stays small and the model has clear ground truth.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.ai_engine.alchemi_bridge import AlchemiBridge
from src.ai_engine.nim_client import NIMError
from src.backend.lab.dataset_manager import (
    DatasetIntegrityError,
    DatasetNotFound,
    LabError,
    get_lab_dataset_manager,
)
from src.backend.licensing.license_manager import verify_license
from src.backend.supercap.analyzer import (
    SupercapAnalyzer,
    report_to_dict,
)


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v2/supercap",
    tags=["supercap"],
    dependencies=[Depends(verify_license())],
)


# ---- helpers --------------------------------------------------------


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _build_analyzer(p: "AnalyzeOpts") -> SupercapAnalyzer:
    return SupercapAnalyzer(
        mass_g=p.mass_g,
        area_cm2=p.area_cm2,
        gcd_current_A=(p.gcd_current_mA / 1000.0) if p.gcd_current_mA else None,
        eis_freq_Hz=p.eis_freq_Hz,
        eis_fmax_Hz=p.eis_fmax_Hz,
        eis_fmin_Hz=p.eis_fmin_Hz,
    )


# ---- schemas --------------------------------------------------------


class AnalyzeOpts(BaseModel):
    """Lab metadata not present in the raw arrays."""
    mass_g:           Optional[float] = Field(None, gt=0,  description="Active material mass in g.")
    area_cm2:         Optional[float] = Field(None, gt=0,  description="Geometric electrode area.")
    gcd_current_mA:   Optional[float] = Field(1.0, gt=0,   description="Applied GCD current in mA.")
    eis_freq_Hz:      Optional[list[float]] = Field(None,  description="Per-point frequency vector. If omitted, log-spaced fmax→fmin is assumed.")
    eis_fmax_Hz:      float = Field(1e5, gt=0)
    eis_fmin_Hz:      float = Field(1e-2, gt=0)


class AnalyzeRawRequest(AnalyzeOpts):
    cv:  list[dict[str, Any]] = Field(default_factory=list,
        description="List of {scan_rate_mV_s, potential_V[], current_A[]}.")
    gcd: list[dict[str, Any]] = Field(default_factory=list,
        description="List of {cycle, time_s[], voltage_V[]}.")
    eis: Optional[dict[str, Any]] = Field(None,
        description="{Z_real_ohm[], Z_imag_ohm[]} (and optional frequency_Hz[]).")


class SuggestNextRequest(BaseModel):
    dataset_id: str = Field(..., description="Encrypted lab dataset to analyse.")
    target:     str = Field(..., min_length=3, max_length=500,
                            description="Plain-language goal, e.g. 'Cs > 200 F/g, retention > 90% over 1000 cycles'.")
    n_suggestions: int = Field(3, ge=1, le=8)
    options:    Optional[AnalyzeOpts] = None


# ---- raw-arrays analyzer (no encrypted store needed) ---------------


@router.post("/analyze/raw")
async def analyze_raw(req: AnalyzeRawRequest = Body(...)) -> dict[str, Any]:
    """
    Analyse a CV/GCD/EIS payload directly. Useful for one-off datasets
    that aren't stored, or for the `import_agv_xlsx.py`-style frontend
    flow that lifts arrays from a file in-memory.
    """
    analyzer = _build_analyzer(req)

    cv_results: list[Any] = []
    for scan in req.cv:
        try:
            scan_rate_V_s = float(scan.get("scan_rate_V_s") or
                                   (scan["scan_rate_mV_s"] / 1000.0))
            cv_results.append(analyzer.analyze_cv(
                scan_rate_V_s,
                list(scan["potential_V"]),
                list(scan["current_A"]),
            ))
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(400, f"bad CV entry: {e}")

    gcd_results: list[Any] = []
    for g in req.gcd:
        try:
            gcd_results.append(analyzer.analyze_gcd(
                int(g["cycle"]),
                list(g["time_s"]),
                list(g["voltage_V"]),
            ))
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(400, f"bad GCD entry: {e}")

    eis_result = None
    if req.eis:
        try:
            eis_result = analyzer.analyze_eis(
                list(req.eis["Z_real_ohm"]),
                list(req.eis["Z_imag_ohm"]),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(400, f"bad EIS entry: {e}")

    report = analyzer.aggregate(cv_results, gcd_results, eis_result)
    return report_to_dict(report)


# ---- analyze a stored dataset --------------------------------------


def _harvest_arrays_from_dataset(dataset) -> dict[str, list[dict[str, Any]]]:
    """
    Reconstruct CV / GCD / EIS arrays from the dataset rows' ``conditions``
    blob. The importer stuffed the raw arrays under ``raw_*`` keys.
    """
    cv: list[dict[str, Any]] = []
    gcd: list[dict[str, Any]] = []
    eis: Optional[dict[str, Any]] = None
    for row in dataset.rows:
        conds = row.get("conditions") or {}
        exp = conds.get("experiment")
        if exp == "CV" and "raw_potential_V" in conds and "raw_current_A" in conds:
            cv.append({
                "scan_rate_V_s": float(conds.get("scan_rate_V_s")
                                         or conds.get("scan_rate_mV_s", 50) / 1000.0),
                "potential_V": list(conds["raw_potential_V"]),
                "current_A":   list(conds["raw_current_A"]),
            })
        elif exp == "GCD" and "raw_time_s" in conds and "raw_voltage_V" in conds:
            gcd.append({
                "cycle":     int(conds.get("cycle", 0)),
                "time_s":    list(conds["raw_time_s"]),
                "voltage_V": list(conds["raw_voltage_V"]),
            })
        elif exp == "EIS" and "raw_Z_real_ohm" in conds and "raw_Z_imag_ohm" in conds:
            eis = {
                "Z_real_ohm":   list(conds["raw_Z_real_ohm"]),
                "Z_imag_ohm":   list(conds["raw_Z_imag_ohm"]),
                "frequency_Hz": list(conds.get("raw_frequency_Hz") or []),
                "f_max_Hz":     conds.get("f_max_Hz"),
                "f_min_Hz":     conds.get("f_min_Hz"),
            }
    return {"cv": cv, "gcd": gcd, "eis": [eis] if eis else []}


@router.get("/analyze/{dataset_id}")
async def analyze_dataset(
    dataset_id: str,
    mass_g:           Optional[float] = Query(None, gt=0),
    area_cm2:         Optional[float] = Query(None, gt=0),
    gcd_current_mA:   float = Query(1.0, gt=0),
    eis_fmax_Hz:      float = Query(1e5, gt=0),
    eis_fmin_Hz:      float = Query(1e-2, gt=0),
) -> dict[str, Any]:
    """
    Run the supercap analysis on a stored lab dataset. Lab metadata
    that isn't in the raw arrays (mass, applied current, frequency
    range) comes in as query parameters with sensible defaults so the
    Swagger UI is one-click.
    """
    try:
        ds = get_lab_dataset_manager().get_dataset(dataset_id)
    except DatasetNotFound:
        raise HTTPException(404, "dataset not found")
    except DatasetIntegrityError as e:
        raise HTTPException(409, f"dataset integrity error: {e}")
    except LabError as e:
        raise HTTPException(400, str(e))

    harvested = _harvest_arrays_from_dataset(ds)
    if not (harvested["cv"] or harvested["gcd"] or harvested["eis"]):
        raise HTTPException(
            400,
            f"dataset {ds.name!r} does not contain raw CV/GCD/EIS arrays. "
            f"Re-import via scripts/import_agv_xlsx.py to capture them, or use POST /analyze/raw.",
        )

    eis_payload: Optional[dict[str, Any]] = None
    if harvested["eis"]:
        eis_payload = harvested["eis"][0]
    eis_freq_from_data = (eis_payload or {}).get("frequency_Hz") or None
    eis_fmax_resolved = ((eis_payload or {}).get("f_max_Hz") or eis_fmax_Hz)
    eis_fmin_resolved = ((eis_payload or {}).get("f_min_Hz") or eis_fmin_Hz)

    analyzer = SupercapAnalyzer(
        mass_g=mass_g,
        area_cm2=area_cm2,
        gcd_current_A=gcd_current_mA / 1000.0,
        eis_freq_Hz=eis_freq_from_data if eis_freq_from_data else None,
        eis_fmax_Hz=eis_fmax_resolved,
        eis_fmin_Hz=eis_fmin_resolved,
    )

    cv_results = [
        analyzer.analyze_cv(s["scan_rate_V_s"], s["potential_V"], s["current_A"])
        for s in harvested["cv"]
    ]
    gcd_results = [
        analyzer.analyze_gcd(g["cycle"], g["time_s"], g["voltage_V"])
        for g in harvested["gcd"]
    ]
    eis_result = (
        analyzer.analyze_eis(eis_payload["Z_real_ohm"], eis_payload["Z_imag_ohm"])
        if eis_payload else None
    )
    report = analyzer.aggregate(cv_results, gcd_results, eis_result)

    return {
        "dataset_id":   ds.id,
        "dataset_name": ds.name,
        "n_cv":         len(cv_results),
        "n_gcd":        len(gcd_results),
        "has_eis":      eis_result is not None,
        "options_used": {
            "mass_g":         mass_g,
            "area_cm2":       area_cm2,
            "gcd_current_mA": gcd_current_mA,
            "eis_fmax_Hz":    eis_fmax_resolved,
            "eis_fmin_Hz":    eis_fmin_resolved,
            "frequency_vector_from_data": bool(eis_freq_from_data),
        },
        "report":       report_to_dict(report),
    }


# ---- iteration recommender -----------------------------------------


_RECOMMENDER_SYSTEM = (
    "You are an expert electrochemistry process engineer. Given a "
    "structured supercapacitor characterisation report and the user's "
    "stated target, propose CONCRETE next-iteration changes — formulation, "
    "electrolyte, electrode preparation, test conditions — that are most "
    "likely to close the gap between current performance and the target. "
    "Be quantitative when possible (mass loading, scan rate, voltage "
    "window, electrolyte composition). Cite specific anomalies in the "
    "report (b-value, retention, ipa/ipc asymmetry, Nyquist shape, "
    "Coulombic efficiency) when explaining WHY each suggestion is likely "
    "to help. NEVER fabricate values that aren't supported by the data; "
    "say 'unknown' if you'd need additional data."
)


def _recommender_user_prompt(report: dict[str, Any], target: str, n: int) -> str:
    summary = report.get("summary") or {}
    cv_overview = report.get("cv") or []
    gcd_overview = report.get("gcd") or []
    eis_overview = report.get("eis") or {}

    # Drop the heavy raw-arrays section — recommender only needs the report.
    parts = [
        f"### Target\n{target}",
        f"### Number of suggestions requested\n{n}",
        "### Headline numbers",
        f"- Cs by method (F): {summary.get('cs_F')}",
        f"- Cs by method (F/g): {summary.get('cs_F_per_g')}",
        f"- Trasatti b-value: {summary.get('b_value')} (R²={summary.get('b_value_r_squared')})",
        f"- Surface fraction: {summary.get('surface_fraction')}; "
            f"Diffusion fraction: {summary.get('diffusion_fraction')}",
        f"- Capacitance retention: {summary.get('capacitance_retention_pct')}%",
        f"- Average Coulombic efficiency: {summary.get('average_coulombic_efficiency_pct')}%",
        f"- Energy density: {summary.get('energy_density_Wh_per_kg')} Wh/kg",
        f"- Power density: {summary.get('power_density_W_per_kg')} W/kg",
        "### CV per scan rate",
    ]
    for cv in cv_overview[:12]:
        parts.append(
            f"  v={cv.get('scan_rate_mV_s'):.0f} mV/s  Cs={cv.get('cs_F'):.4g} F  "
            f"ipa={cv.get('ipa_uA'):+.0f} µA  ipc={cv.get('ipc_uA'):+.0f} µA  "
            f"ΔV={cv.get('delta_v_V'):.3f} V"
        )
    parts.append("### GCD per cycle (only summary fields)")
    for g in gcd_overview[:20]:
        parts.append(
            f"  cycle {g.get('cycle')}: Cs={g.get('cs_F')} F  "
            f"η={g.get('coulombic_efficiency')}  IR drop={g.get('ir_drop_V')} V  "
            f"flags={g.get('quality_flags')}"
        )
    if eis_overview:
        parts.append("### EIS")
        parts.append(
            f"  Rs={eis_overview.get('rs_ohm')} Ω  "
            f"Cs(low f)={eis_overview.get('cs_low_freq_F')} F  "
            f"shape={eis_overview.get('nyquist_shape')!r}  "
            f"knee f={eis_overview.get('knee_frequency_Hz')} Hz"
        )
    parts.append("### Diagnostics already raised")
    for d in summary.get("diagnostics") or []:
        parts.append(f"  • {d}")

    parts.append(
        "\n### Output format\n"
        "Return ONLY a JSON object with this shape (no markdown):\n"
        '{"suggestions": [\n'
        '  {"title": "<short title>",\n'
        '   "what_to_change": "<concrete experimental change>",\n'
        '   "why": "<explanation tied to specific report values>",\n'
        '   "expected_effect_on_Cs": "<+X%, -Y%, or qualitative>",\n'
        '   "risk": "low|medium|high",\n'
        '   "data_needed_to_evaluate": "<what to measure next>"\n'
        '  }, ... up to N items],\n'
        ' "overall_diagnosis": "<one-sentence summary>"\n'
        '}'
    )
    return "\n".join(parts)


@router.post("/suggest-next")
async def suggest_next(req: SuggestNextRequest = Body(...)) -> dict[str, Any]:
    """
    Look the dataset up, run the analyzer, hand the structured report
    to the configured NIM with the user's target, return the model's
    JSON recommendations.

    The model gets ONLY the report and the target — never the raw
    arrays. That keeps the prompt small and the answer grounded in the
    derived numbers.
    """
    try:
        ds = get_lab_dataset_manager().get_dataset(req.dataset_id)
    except DatasetNotFound:
        raise HTTPException(404, "dataset not found")
    except DatasetIntegrityError as e:
        raise HTTPException(409, f"dataset integrity error: {e}")
    except LabError as e:
        raise HTTPException(400, str(e))

    harvested = _harvest_arrays_from_dataset(ds)
    if not (harvested["cv"] or harvested["gcd"] or harvested["eis"]):
        raise HTTPException(
            400,
            f"dataset {ds.name!r} has no raw arrays. "
            "Re-import via scripts/import_agv_xlsx.py.",
        )

    eis_payload: Optional[dict[str, Any]] = (
        harvested["eis"][0] if harvested["eis"] else None
    )
    opts = req.options or AnalyzeOpts()
    analyzer = SupercapAnalyzer(
        mass_g=opts.mass_g,
        area_cm2=opts.area_cm2,
        gcd_current_A=(opts.gcd_current_mA / 1000.0) if opts.gcd_current_mA else None,
        eis_freq_Hz=(eis_payload or {}).get("frequency_Hz") or opts.eis_freq_Hz,
        eis_fmax_Hz=opts.eis_fmax_Hz,
        eis_fmin_Hz=opts.eis_fmin_Hz,
    )
    cv_r = [analyzer.analyze_cv(s["scan_rate_V_s"], s["potential_V"], s["current_A"])
            for s in harvested["cv"]]
    gcd_r = [analyzer.analyze_gcd(g["cycle"], g["time_s"], g["voltage_V"])
             for g in harvested["gcd"]]
    eis_r = (analyzer.analyze_eis(eis_payload["Z_real_ohm"], eis_payload["Z_imag_ohm"])
             if eis_payload else None)
    report = analyzer.aggregate(cv_r, gcd_r, eis_r)
    report_dict = report_to_dict(report)

    bridge = AlchemiBridge()
    if not bridge.client.configured:
        return {
            "available": False,
            "reason": (
                "NVIDIA_API_KEY is not set. Recommendations require a "
                "configured NIM (set NVIDIA_API_KEY in .env)."
            ),
            "report": report_dict,
        }

    user_prompt = _recommender_user_prompt(report_dict, req.target, req.n_suggestions)
    try:
        suggestions = bridge.client.chat_json(
            user_prompt,
            schema_hint=(
                '{"suggestions": [{"title", "what_to_change", "why", '
                '"expected_effect_on_Cs", "risk", "data_needed_to_evaluate"}], '
                '"overall_diagnosis"}'
            ),
            system=_RECOMMENDER_SYSTEM,
            temperature=0.4,
            max_tokens=1500,
        )
    except NIMError as e:
        return {
            "available": False,
            "reason": f"NIM call failed: {e}",
            "status": e.status,
            "report": report_dict,
        }

    if not isinstance(suggestions, dict):
        return {
            "available": False,
            "reason": "model returned non-object JSON",
            "raw":     suggestions,
            "report":  report_dict,
        }

    return {
        "available":     True,
        "dataset_id":    ds.id,
        "dataset_name":  ds.name,
        "target":        req.target,
        "diagnosis":     suggestions.get("overall_diagnosis"),
        "suggestions":   suggestions.get("suggestions") or [],
        "report":        report_dict,
    }
