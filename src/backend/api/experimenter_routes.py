"""
API endpoints for autonomous experiment recommendation.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/api/v2/experimenter", tags=["autonomous-experimenter"])

experimenter = None

def get_experimenter():
    global experimenter
    if experimenter is None:
        from src.backend.research.autonomous_experimenter import AutonomousExperimenter
        from src.backend.graph.knowledge_graph import KnowledgeGraph
        from src.backend.embeddings.vector_store import VectorStore
        kg = KnowledgeGraph()
        vs = VectorStore()
        experimenter = AutonomousExperimenter("data/datasets/research/papers.db", kg_client=kg, vector_store=vs)
    return experimenter

class MaterialRecommendationRequest(BaseModel):
    analyte: str
    limit: int = 5

class SynthesisOptimizationRequest(BaseModel):
    material: str

class RecipeGenerationRequest(BaseModel):
    materials: List[str]
    target_analyte: str

class ExperimentSuggestionRequest(BaseModel):
    research_goal: str

@router.post("/recommend_materials")
async def recommend_materials(req: MaterialRecommendationRequest) -> List[Dict[str, Any]]:
    """Recommend materials to detect a specific analyte."""
    try:
        exp = get_experimenter()
        return exp.recommend_materials_for_analyte(req.analyte, req.limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/optimize_synthesis")
async def optimize_synthesis(req: SynthesisOptimizationRequest) -> Dict[str, Any]:
    """Suggest optimal synthesis parameters for a material."""
    try:
        exp = get_experimenter()
        return exp.optimize_synthesis(req.material)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate_recipe")
async def generate_recipe(req: RecipeGenerationRequest) -> Dict[str, Any]:
    """Generate experimental recipe for material combination."""
    try:
        exp = get_experimenter()
        return exp.generate_recipe(req.materials, req.target_analyte)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/suggest_experiments")
async def suggest_experiments(req: ExperimentSuggestionRequest) -> List[Dict[str, Any]]:
    """Suggest experiments based on research goal."""
    try:
        exp = get_experimenter()
        return exp.suggest_experiments(req.research_goal)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
