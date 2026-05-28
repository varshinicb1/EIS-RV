"""
Lab Data Cleaner + AI Analysis Routes
=======================================
FastAPI endpoints for the autonomous data cleaner and NVIDIA-powered
AI analysis of electrochemical lab data.

Endpoints:
  POST /api/v1/lab-cleaner/clean          - Clean uploaded xlsx file
  POST /api/v1/lab-cleaner/calibration    - Compute calibration curve
  POST /api/v1/lab-cleaner/ai-analyze     - AI analysis via NVIDIA NIM
  GET  /api/v1/lab-cleaner/status         - Service health

Author: VidyuthLabs
Date: May 6, 2026
"""

import io
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lab-cleaner", tags=["Lab Cleaner"])

# ── Pydantic models ───────────────────────────────────────────────────────

class CalibrationRequest(BaseModel):
    series: Dict[str, Any] = Field(..., description="Cleaned series dict from cleaner output")

class AIAnalysisRequest(BaseModel):
    cleaning_result: Dict[str, Any] = Field(..., description="Full cleaning result from /clean")
    calibration_result: Optional[Dict[str, Any]] = Field(None, description="Calibration result (optional)")
    context: Optional[str] = Field(None, description="Extra context (electrode type, analyte, etc.)")


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_cleaner():
    from src.backend.ml.data_collection.autonomous_data_cleaner import AutonomousDataCleaner
    return AutonomousDataCleaner()

def _get_calibration_analyzer():
    from src.backend.ml.data_collection.calibration_analyzer import analyze_calibration
    return analyze_calibration

def _get_nim_client():
    from src.ai_engine.nim_client import get_default_client
    return get_default_client()


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/status")
async def status():
    """Health check and NIM availability."""
    nim_ok = False
    nim_model = None
    try:
        client = _get_nim_client()
        nim_ok    = client.configured
        nim_model = client.default_model
    except Exception:
        pass
    return {
        "status": "ok",
        "cleaner": "ready",
        "nim_configured": nim_ok,
        "nim_model": nim_model,
    }


@router.post("/clean")
async def clean_file(file: UploadFile = File(...)):
    """
    Upload an xlsx file and get back cleaned data.

    Automatically detects format (CHI EIS, interleaved DPV/CV, etc.),
    cleans all sheets, and returns structured JSON.
    """
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(400, "Only .xlsx files are supported")

    content = await file.read()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write uploaded file to temp dir
        in_path  = Path(tmpdir) / file.filename
        out_dir  = Path(tmpdir) / "cleaned"
        in_path.write_bytes(content)

        try:
            cleaner = _get_cleaner()
            cleaner.output_dir = out_dir
            result  = cleaner.clean_file(in_path)
        except Exception as e:
            logger.error("Cleaning failed: %s", e, exc_info=True)
            raise HTTPException(500, f"Cleaning failed: {e}")

        # Read all generated JSON files and embed them in the response
        cleaned_data = {}
        for sheet_name, sheet_info in result.get("sheets", {}).items():
            sheet_data = {"format": sheet_info.get("format"), "quality_report": {}}

            # Find JSON output for this sheet
            stem = result["stem"]
            safe_sheet = sheet_name.replace(" ", "_").replace("/", "_")
            json_files = list(out_dir.rglob(f"*{safe_sheet}*_all.json")) + \
                         list(out_dir.rglob(f"*{safe_sheet}*_meta.json"))

            for jf in json_files:
                try:
                    jdata = json.loads(jf.read_text(encoding="utf-8"))
                    if "_meta" in jf.name:
                        sheet_data["metadata"]       = jdata.get("metadata", {})
                        sheet_data["quality_report"] = jdata.get("quality_report", {})
                    else:
                        sheet_data["series"]  = jdata.get("series_clean") or jdata.get("series", {})
                        sheet_data["type"]    = jdata.get("type", "VOLTAMMETRY")
                except Exception:
                    pass

            # For EIS: embed the cleaned CSV data directly
            csv_files = list(out_dir.rglob(f"*{safe_sheet}*.csv"))
            if csv_files and sheet_info.get("format") == "chi_eis":
                try:
                    lines = csv_files[0].read_text(encoding="utf-8").splitlines()
                    header = lines[0].split(",")
                    rows   = [dict(zip(header, r.split(","))) for r in lines[1:] if r]
                    sheet_data["eis_data"] = rows
                except Exception:
                    pass

            cleaned_data[sheet_name] = sheet_data

        return {
            "success":      result["success"],
            "filename":     file.filename,
            "stem":         result["stem"],
            "sheets":       result["sheets"],
            "cleaned_data": cleaned_data,
            "output_files": len(result.get("output_files", [])),
        }


@router.post("/calibration")
async def compute_calibration(req: CalibrationRequest):
    """
    Compute calibration curve from a cleaned series dict.

    Pass the `series` field from a cleaned DPV/CV sheet.
    Returns sensitivity, LOD, LOQ, R², equation.
    """
    try:
        from src.backend.ml.data_collection.calibration_analyzer import (
            _parse_conc, _find_peak, _to_uA
        )
        import numpy as np

        series = req.series
        if not series:
            raise HTTPException(400, "Empty series")

        # Build peak table
        peak_table = {}
        buffer_i   = None

        for label, s in series.items():
            pot  = np.array(s.get("potential_v", []))
            cur  = np.array(s.get("current_a",   []))
            if len(pot) == 0:
                continue
            e_pk, i_pk = _find_peak(pot, cur)
            conc = _parse_conc(label)
            peak_table[label] = {
                "concentration": conc,
                "e_peak_v":      round(e_pk, 5),
                "i_peak_a":      round(i_pk, 12),
            }
            if label.lower() == "buffer" or conc == 0.0:
                buffer_i = i_pk

        for row in peak_table.values():
            row["i_net_a"] = round(row["i_peak_a"] - (buffer_i or 0.0), 12)

        valid = [
            (row["concentration"], row["i_net_a"])
            for row in peak_table.values()
            if row["concentration"] is not None and row["concentration"] > 0
        ]

        if len(valid) < 3:
            return {"peak_table": peak_table, "error": "Need ≥ 3 concentration points"}

        valid.sort(key=lambda x: x[0])
        concs     = np.array([v[0] for v in valid])
        inets_raw = np.array([v[1] for v in valid])
        inets     = _to_uA(inets_raw)

        # Best linear range
        best_r2 = 0.0; best_range = (float(concs[0]), float(concs[-1])); best_fit = None
        for i in range(len(concs)):
            for j in range(i + 2, len(concs) + 1):
                c_sub = concs[i:j]; i_sub = inets[i:j]
                coeffs = np.polyfit(c_sub, i_sub, 1)
                i_pred = np.polyval(coeffs, c_sub)
                ss_res = np.sum((i_sub - i_pred) ** 2)
                ss_tot = np.sum((i_sub - i_sub.mean()) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
                if r2 > best_r2 and len(c_sub) >= 3:
                    best_r2 = r2; best_range = (float(c_sub[0]), float(c_sub[-1])); best_fit = coeffs

        if best_fit is None:
            best_fit = np.polyfit(concs, inets, 1)

        slope     = float(best_fit[0])
        intercept = float(best_fit[1])
        i_pred    = np.polyval(best_fit, concs)
        sigma     = float(np.std(inets - i_pred))
        lod       = 3  * sigma / abs(slope) if slope != 0 else None
        loq       = 10 * sigma / abs(slope) if slope != 0 else None

        return {
            "peak_table":                peak_table,
            "linear_range":              best_range,
            "sensitivity_uA_per_uM":     round(slope, 6),
            "intercept_uA":              round(intercept, 6),
            "r_squared":                 round(best_r2, 6),
            "lod_uM":                    round(lod, 4) if lod else None,
            "loq_uM":                    round(loq, 4) if loq else None,
            "equation":                  f"I (µA) = {slope:.4f}·C + {intercept:.4f}",
            "n_points":                  len(valid),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Calibration failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Calibration failed: {e}")


@router.post("/ai-analyze")
async def ai_analyze(req: AIAnalysisRequest):
    """
    AI analysis of cleaned electrochemical data via NVIDIA NIM.

    Sends the cleaning results + calibration to the configured NIM model
    and returns a structured scientific interpretation.
    """
    try:
        client = _get_nim_client()
    except Exception as e:
        raise HTTPException(503, f"NIM client unavailable: {e}")

    if not client.configured:
        raise HTTPException(503, "NVIDIA API key not configured. Set NVIDIA_API_KEY in .env")

    # Build a rich prompt from the data
    cr  = req.cleaning_result
    cal = req.calibration_result
    ctx = req.context or ""

    # Summarise EIS data
    eis_summary = []
    for sheet_name, sheet in cr.get("cleaned_data", {}).items():
        qr = sheet.get("quality_report", {})
        if qr.get("rs_ohm") is not None:
            eis_summary.append(
                f"  - {sheet_name}: Rs={qr['rs_ohm']} Ω, Rct={qr['rct_ohm']} Ω, "
                f"f_char={qr.get('f_char_hz')} Hz"
            )

    # Summarise DPV/CV series
    series_summary = []
    for sheet_name, sheet in cr.get("cleaned_data", {}).items():
        series = sheet.get("series", {})
        if series:
            n_series = len(series)
            labels   = list(series.keys())[:5]
            series_summary.append(
                f"  - {sheet_name}: {n_series} concentration series "
                f"({', '.join(labels)}{'...' if n_series > 5 else ''})"
            )

    # Calibration summary
    cal_text = ""
    if cal and "equation" in cal:
        cal_text = f"""
Calibration curve:
  Equation: {cal['equation']}
  R²: {cal.get('r_squared')}
  Sensitivity: {cal.get('sensitivity_uA_per_uM')} µA/µM
  Linear range: {cal.get('linear_range')}
  LOD: {cal.get('lod_uM')} µM
  LOQ: {cal.get('loq_uM')} µM"""

    prompt = f"""You are an expert electrochemist. Analyze the following lab data from a cleaned electrochemical dataset and provide a detailed scientific interpretation.

File: {cr.get('filename', 'unknown')}
{f'Context: {ctx}' if ctx else ''}

EIS Data (Electrochemical Impedance Spectroscopy):
{chr(10).join(eis_summary) if eis_summary else '  No EIS data'}

Voltammetry Data (DPV/CV):
{chr(10).join(series_summary) if series_summary else '  No voltammetry data'}
{cal_text}

Please provide:
1. **Electrode Performance Assessment**: Interpret the EIS data (Rs, Rct values). What do they tell us about the electrode material and electron transfer kinetics?
2. **Sensor Performance**: Based on the calibration curve, evaluate the sensor's analytical performance (sensitivity, LOD, LOQ, linear range). Is this suitable for the intended application?
3. **Comparison**: If multiple electrodes are present, rank them by performance and explain why.
4. **Mechanistic Insights**: What electrochemical mechanisms are likely occurring based on the peak potentials and current responses?
5. **Recommendations**: What improvements would you suggest to enhance performance?
6. **Publication Readiness**: Is this data of sufficient quality for publication? What additional experiments are needed?

Be specific, cite the actual numbers from the data, and provide actionable insights."""

    try:
        from src.ai_engine.nim_client import NIMError
        completion = client.chat(
            [
                {"role": "system", "content": "You are an expert electrochemist specializing in biosensors, modified electrodes, and electroanalytical chemistry. Provide rigorous, quantitative analysis."},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        return {
            "success":   True,
            "analysis":  completion.text,
            "model":     completion.model,
            "tokens":    completion.total_tokens,
            "prompt_tokens": getattr(completion, "prompt_tokens", None),
        }
    except Exception as e:
        logger.error("NIM analysis failed: %s", e, exc_info=True)
        raise HTTPException(500, f"AI analysis failed: {e}")
