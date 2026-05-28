"""
Hydrothermal Materials Discovery API Routes
============================================
Exposes the Autonomous Hydrothermal Materials Discovery Engine
through FastAPI endpoints under /api/v2/hydrothermal/.

All endpoints follow the verification-first philosophy:
- No fake data returned
- Every response includes confidence, provenance, uncertainty
- NIM_NOT_CONFIGURED returns 503 (not fake values)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/hydrothermal", tags=["Hydrothermal Discovery"])


# ── Request / Response models ─────────────────────────────────────────────────

class DiscoverRequest(BaseModel):
    goal: str = Field(..., description="Scientific objective, e.g. 'high-capacitance alkaline supercapacitor'")
    target_properties: Dict[str, Any] = Field(default_factory=dict, description="Target material properties")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Synthesis/lab constraints")
    n_candidates: int = Field(default=5, ge=1, le=8, description="Number of ranked candidates")


class SynthesizeRequest(BaseModel):
    material: str = Field(..., description="Target material formula or name")
    application: str = Field(default="electrochemical", description="Intended application")
    scale_mL: float = Field(default=50.0, ge=5.0, le=500.0, description="Autoclave volume in mL")
    constraints: Optional[Dict[str, Any]] = Field(default=None)


class InterpretRequest(BaseModel):
    cv_data: Optional[Dict[str, Any]] = None
    eis_data: Optional[Dict[str, Any]] = None
    material_context: str = ""


class FeedbackRequest(BaseModel):
    candidate_material: str
    experiment_result: str
    characterisation: Dict[str, Any] = Field(default_factory=dict)
    electrochemical_data: Optional[Dict[str, Any]] = None
    success: bool = True


class FailureRequest(BaseModel):
    material: str
    conditions: Dict[str, Any] = Field(default_factory=dict)
    failure_mode: str
    notes: str = ""


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/status")
def hydrothermal_status():
    """Engine status — NIM availability, inventory count, graph size."""
    try:
        from src.backend.core.engines.hydrothermal_engine import _load_inventory, get_graph
        from src.ai_engine.nim_client import NIMClient
        inv = _load_inventory()
        nim = NIMClient()
        graph = get_graph()
        return {
            "engine": "Autonomous Hydrothermal Materials Discovery Engine",
            "version": "1.0",
            "nim_configured": nim.configured,
            "nim_model": nim.default_model if nim.configured else None,
            "inventory_total": inv.get("total", 0),
            "knowledge_graph": {"nodes": graph["node_count"], "edges": graph["edge_count"]},
            "capabilities": [
                "goal_driven_inverse_design",
                "hydrothermal_synthesis_planning",
                "electrochemical_interpretation",
                "failure_tracking",
                "human_in_the_loop_feedback",
                "knowledge_graph",
            ],
        }
    except Exception as e:
        logger.error("hydrothermal_status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inventory")
def get_inventory(
    category: Optional[str] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
):
    """
    Return the lab chemical inventory.
    Supports filtering by category, hydrothermal_role, and free-text search.
    """
    try:
        from src.backend.core.engines.hydrothermal_engine import get_inventory
        return get_inventory(category=category, role=role, search=search)
    except Exception as e:
        logger.error("get_inventory: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discover")
def discover_materials(req: DiscoverRequest):
    """
    Goal-driven inverse design.
    Given a scientific goal and target properties, returns ranked material
    candidates with synthesis feasibility, confidence scores, and precursor
    availability checks against the lab inventory.

    Returns 503 if NIM is not configured — never returns fabricated data.
    """
    try:
        from src.backend.core.engines.hydrothermal_engine import discover
        result = discover(
            goal=req.goal,
            target_properties=req.target_properties,
            constraints=req.constraints,
            n_candidates=req.n_candidates,
        )
        if result.get("error") == "NIM_NOT_CONFIGURED":
            raise HTTPException(
                status_code=503,
                detail="NVIDIA API key not configured. Set NVIDIA_API_KEY to enable AI discovery."
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("discover_materials: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthesize")
def plan_synthesis(req: SynthesizeRequest):
    """
    Generate a detailed hydrothermal synthesis route for a given material.
    Returns step-by-step protocol with: precursors (checked against inventory),
    hydrothermal conditions, post-processing, characterisation checklist,
    safety notes, and confidence scoring.

    Returns 503 if NIM is not configured — never returns fabricated protocols.
    """
    try:
        from src.backend.core.engines.hydrothermal_engine import synthesize
        result = synthesize(
            material=req.material,
            application=req.application,
            scale_mL=req.scale_mL,
            constraints=req.constraints,
        )
        if result.get("error") == "NIM_NOT_CONFIGURED":
            raise HTTPException(
                status_code=503,
                detail="NVIDIA API key not configured. Set NVIDIA_API_KEY to enable synthesis planning."
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("plan_synthesis: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interpret")
def interpret_data(req: InterpretRequest):
    """
    Electrochemical data interpretation engine.
    Correlates CV/EIS signatures with material states and synthesis quality.
    Suggests synthesis optimisations based on electrochemical evidence.
    """
    try:
        from src.backend.core.engines.hydrothermal_engine import interpret_electrochemistry
        result = interpret_electrochemistry(
            cv_data=req.cv_data,
            eis_data=req.eis_data,
            material_context=req.material_context,
        )
        if result.get("error") == "NIM_NOT_CONFIGURED":
            raise HTTPException(status_code=503, detail="NVIDIA API key not configured.")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("interpret_data: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    """
    Human-in-the-loop feedback ingestion.
    Submit experimental results to update the knowledge graph and
    failure tracker. This is the highest-trust data source.
    """
    try:
        from src.backend.core.engines.hydrothermal_engine import ingest_feedback
        return ingest_feedback(
            candidate_material=req.candidate_material,
            experiment_result=req.experiment_result,
            characterisation=req.characterisation,
            electrochemical_data=req.electrochemical_data,
            success=req.success,
        )
    except Exception as e:
        logger.error("submit_feedback: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/failures/record")
def record_failure_route(req: FailureRequest):
    """Record a failed synthesis for future candidate penalisation."""
    try:
        from src.backend.core.engines.hydrothermal_engine import record_failure
        record_failure(
            material=req.material,
            conditions=req.conditions,
            failure_mode=req.failure_mode,
            notes=req.notes,
        )
        return {"status": "recorded", "material": req.material, "failure_mode": req.failure_mode}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/failures")
def get_failures(material: Optional[str] = None):
    """Retrieve recorded synthesis failures, optionally filtered by material."""
    try:
        from src.backend.core.engines.hydrothermal_engine import get_failures
        return {"failures": get_failures(material=material)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-graph")
def knowledge_graph():
    """Return the current scientific knowledge graph (nodes + edges)."""
    try:
        from src.backend.core.engines.hydrothermal_engine import get_graph
        return get_graph()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inventory/categories")
def inventory_categories():
    """Return all available chemical categories with descriptions."""
    try:
        from src.backend.core.engines.hydrothermal_engine import _load_inventory
        inv = _load_inventory()
        return {"categories": inv.get("categories", {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inventory/roles")
def inventory_roles():
    """Return all available hydrothermal roles and which chemicals fill them."""
    try:
        from src.backend.core.engines.hydrothermal_engine import _load_inventory
        inv = _load_inventory()
        roles: dict[str, list[str]] = {}
        for c in inv.get("chemicals", []):
            for r in c.get("hydrothermal_role", []):
                roles.setdefault(r, []).append(c["name"])
        return {"roles": roles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
