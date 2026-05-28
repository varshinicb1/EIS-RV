"""
API endpoints for knowledge graph queries.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/api/v2/graph", tags=["knowledge-graph"])

kg = None

def get_kg():
    global kg
    if kg is None:
        from src.backend.graph.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
    return kg

class MaterialRequest(BaseModel):
    material: str
    max_depth: int = 2

class AnalyteRequest(BaseModel):
    analyte: str

@router.get("/material_relationships")
async def get_material_relationships(material: str, max_depth: int = 2) -> List[Dict[str, Any]]:
    """Get materials related to the given material."""
    try:
        graph = get_kg()
        return graph.find_related_materials(material, max_depth)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/unexplored_combinations")
async def get_unexplored_combinations(analyte: str) -> List[Dict[str, Any]]:
    """Find materials that could detect the analyte but haven't been tested."""
    try:
        graph = get_kg()
        return graph.find_unexplored_combinations(analyte)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/synthesis_trends/{material}")
async def get_synthesis_trends(material: str) -> List[Dict[str, Any]]:
    """Get synthesis method trends for a material."""
    try:
        graph = get_kg()
        return graph.get_synthesis_trends(material)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
