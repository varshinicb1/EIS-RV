"""
Raman Material Database API Routes
===================================
FastAPI router for Raman material identification and database management.

Endpoints:
- POST /api/v1/raman/identify            - Identify material from peaks
- POST /api/v1/raman/identify-mixture    - Identify mixture components
- GET  /api/v1/raman/materials           - List all materials
- GET  /api/v1/raman/materials/search    - Search materials
- GET  /api/v1/raman/materials/category/{category} - Get by category
- GET  /api/v1/raman/materials/{id}      - Get material by ID
- POST /api/v1/raman/materials           - Add new material
- PUT  /api/v1/raman/materials/{id}      - Update material
- GET  /api/v1/raman/database/stats      - Database statistics
- GET  /api/v1/raman/categories          - List categories
- GET  /api/v1/raman/health              - Health check

Author: VidyuthLabs
Date: May 6, 2026
"""

import logging
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.backend.ml.models.raman_material_identifier import (
    RamanMaterialIdentifier,
    add_material_to_database,
    update_material_in_database,
)

logger = logging.getLogger(__name__)

# ── Router ────────────────────────────────────────────────────────────────
raman_material_bp = APIRouter(prefix="/api/v1/raman", tags=["Raman Materials"])

# ── Identifier singleton ──────────────────────────────────────────────────
_DB_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "data" / "material_database" / "raman_materials.json"
)
identifier = RamanMaterialIdentifier(database_path=str(_DB_PATH))


# ── Pydantic models ───────────────────────────────────────────────────────

class PeakIn(BaseModel):
    position_cm: float
    intensity: float = 1.0


class IdentifyRequest(BaseModel):
    peaks: List[PeakIn]
    wavenumber: Optional[List[float]] = None
    intensity: Optional[List[float]] = None
    top_n: int = Field(5, ge=1, le=20)
    min_confidence: float = Field(0.3, ge=0.0, le=1.0)


class MixtureRequest(BaseModel):
    peaks: List[PeakIn]
    wavenumber: Optional[List[float]] = None
    intensity: Optional[List[float]] = None
    max_components: int = Field(3, ge=1, le=5)
    min_confidence: float = Field(0.4, ge=0.0, le=1.0)


class AddMaterialRequest(BaseModel):
    material_id: str
    name: str
    category: str
    reference_peaks: List[Dict[str, Any]]
    formula: Optional[str] = None
    description: Optional[str] = None
    identification_criteria: Optional[Dict[str, Any]] = None
    references: Optional[List[Dict[str, Any]]] = None


class UpdateMaterialRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    reference_peaks: Optional[List[Dict[str, Any]]] = None
    identification_criteria: Optional[Dict[str, Any]] = None


# ── Identification endpoints ──────────────────────────────────────────────

@raman_material_bp.post("/identify")
async def identify_material(req: IdentifyRequest):
    """Identify material from detected Raman peaks."""
    try:
        peaks = [{"position_cm": p.position_cm, "intensity": p.intensity} for p in req.peaks]
        wn = np.array(req.wavenumber) if req.wavenumber else None
        inten = np.array(req.intensity) if req.intensity else None

        matches = identifier.identify_material(
            detected_peaks=peaks,
            wavenumber=wn,
            intensity=inten,
            top_n=req.top_n,
            min_confidence=req.min_confidence,
        )
        return {"success": True, "matches": [m.to_dict() for m in matches], "n_matches": len(matches)}
    except Exception as e:
        logger.error("Material identification failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@raman_material_bp.post("/identify-mixture")
async def identify_mixture(req: MixtureRequest):
    """Identify multiple materials in a mixture."""
    try:
        peaks = [{"position_cm": p.position_cm, "intensity": p.intensity} for p in req.peaks]
        wn = np.array(req.wavenumber) if req.wavenumber else None
        inten = np.array(req.intensity) if req.intensity else None

        components = identifier.identify_mixture(
            detected_peaks=peaks,
            wavenumber=wn,
            intensity=inten,
            max_components=req.max_components,
            min_confidence=req.min_confidence,
        )
        return {"success": True, "components": [c.to_dict() for c in components], "n_components": len(components)}
    except Exception as e:
        logger.error("Mixture identification failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Database query endpoints ──────────────────────────────────────────────

@raman_material_bp.get("/materials")
async def list_materials(
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List all materials, optionally filtered by category."""
    materials = identifier.get_materials_by_category(category) if category else identifier.materials
    total = len(materials)
    return {
        "success": True,
        "materials": materials[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@raman_material_bp.get("/materials/search")
async def search_materials(q: str = Query(..., min_length=1)):
    """Search materials by name, formula, or description."""
    results = identifier.search_materials(q)
    return {"success": True, "results": results, "query": q, "count": len(results)}


@raman_material_bp.get("/materials/category/{category}")
async def get_by_category(category: str):
    """Get all materials in a category."""
    materials = identifier.get_materials_by_category(category)
    return {"success": True, "materials": materials, "category": category, "count": len(materials)}


@raman_material_bp.get("/materials/{material_id}")
async def get_material(material_id: str):
    """Get a single material by ID."""
    material = identifier.get_material_by_id(material_id)
    if material is None:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found")
    return {"success": True, "material": material}


# ── Database management endpoints ─────────────────────────────────────────

@raman_material_bp.post("/materials")
async def add_material(req: AddMaterialRequest):
    """Add a new material to the database."""
    material = req.dict(exclude_none=True)
    success = add_material_to_database(str(_DB_PATH), material)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add material to database")
    identifier.load_database()
    return {"success": True, "message": "Material added", "material_id": req.material_id}


@raman_material_bp.put("/materials/{material_id}")
async def update_material(material_id: str, req: UpdateMaterialRequest):
    """Update an existing material."""
    updates = req.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    success = update_material_in_database(str(_DB_PATH), material_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail=f"Material '{material_id}' not found")
    identifier.load_database()
    return {"success": True, "message": "Material updated", "material_id": material_id}


# ── Utility endpoints ─────────────────────────────────────────────────────

@raman_material_bp.get("/database/stats")
async def database_stats():
    """Get database statistics."""
    return {"success": True, "statistics": identifier.get_statistics()}


@raman_material_bp.get("/categories")
async def list_categories():
    """List all material categories."""
    stats = identifier.get_statistics()
    return {"success": True, "categories": sorted(stats["categories"].keys())}


@raman_material_bp.get("/health")
async def health():
    """Health check."""
    return {
        "success": True,
        "status": "healthy",
        "database_loaded": len(identifier.materials) > 0,
        "n_materials": len(identifier.materials),
    }
