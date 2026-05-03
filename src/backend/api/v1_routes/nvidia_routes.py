"""
NVIDIA Intelligence API Routes
================================
Endpoints for NVIDIA NIM integration and paper validation.
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.backend.api.error_handlers import internal_error
from pydantic import BaseModel, Field

from src.backend.core.engines.nvidia_intelligence import get_nvidia_intelligence
from src.backend.core.engines.paper_validator import get_paper_validator
from src.backend.licensing.license_manager import verify_license

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/nvidia",
    tags=["nvidia_intelligence"],
    dependencies=[Depends(verify_license())],
)


# ══════════════════════════════════════════════════════════════════════
#   Request/Response Models
# ══════════════════════════════════════════════════════════════════════

class MaterialPredictionRequest(BaseModel):
    formula: str = Field(..., min_length=1, max_length=200, description="Chemical formula (e.g., 'LiFePO4')")
    properties: List[str] = Field(
        ["band_gap", "formation_energy", "stability"],
        description="Properties to predict"
    )


class CrystalStructureRequest(BaseModel):
    formula: str = Field(..., min_length=1, max_length=200, description="Chemical formula")
    space_group: Optional[int] = Field(None, ge=1, le=230, description="Space group number (1-230)")


class LiteratureSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000, description="Search query")
    max_results: int = Field(10, ge=1, le=1000, description="Maximum results")


class SynthesisOptimizationRequest(BaseModel):
    target_properties: Dict = Field(..., description="Target properties")
    constraints: Dict = Field(..., description="Constraints")


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000, description="Question for materials expert")
    context: Optional[Dict] = Field(None, description="Optional context")


class ValidationRequest(BaseModel):
    material: str = Field(..., min_length=1, max_length=200, description="Material name")
    property_name: str = Field(..., min_length=1, max_length=200, description="Property name")
    simulated_value: float = Field(..., description="Simulated value")
    tolerance: float = Field(0.2, gt=0, le=1e3, description="Acceptable error tolerance")


class EISValidationRequest(BaseModel):
    material: str = Field(..., min_length=1, max_length=200, description="Material name")
    Z_real: List[float] = Field(..., max_length=100000, description="Real impedance")
    Z_imag: List[float] = Field(..., max_length=100000, description="Imaginary impedance")
    capacitance: Optional[float] = Field(None, ge=0, le=1e6, description="Capacitance")


# ══════════════════════════════════════════════════════════════════════
#   NVIDIA Intelligence Endpoints
# ══════════════════════════════════════════════════════════════════════

@router.post("/predict")
async def predict_material_properties(request: MaterialPredictionRequest):
    """
    Predict material properties using NVIDIA AI models.
    
    Returns: Predicted properties with confidence scores
    """
    try:
        nvidia = get_nvidia_intelligence()
        result = nvidia.predict_material_properties(
            formula=request.formula,
            properties=request.properties
        )
        return result
    except Exception as e:
        logger.error(f"Material prediction error: {e}")
        raise internal_error(e, op="nvidia_routes:91")


@router.post("/crystal")
async def generate_crystal_structure(request: CrystalStructureRequest):
    """
    Generate 3D crystal structure for visualization.
    
    Returns: Crystal structure in CIF-like format
    """
    try:
        nvidia = get_nvidia_intelligence()
        result = nvidia.generate_crystal_structure(
            formula=request.formula,
            space_group=request.space_group
        )
        return result
    except Exception as e:
        logger.error(f"Crystal generation error: {e}")
        raise internal_error(e, op="nvidia_routes:110")


@router.post("/literature")
async def search_literature(request: LiteratureSearchRequest):
    """
    Search scientific literature using NVIDIA BioMegatron.
    
    Returns: List of relevant papers
    """
    try:
        nvidia = get_nvidia_intelligence()
        results = nvidia.query_literature(
            query=request.query,
            max_results=request.max_results
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Literature search error: {e}")
        raise internal_error(e, op="nvidia_routes:129")


@router.post("/optimize-synthesis")
async def optimize_synthesis(request: SynthesisOptimizationRequest):
    """
    Use NVIDIA AI to suggest optimal synthesis parameters.
    
    Returns: Suggested synthesis parameters
    """
    try:
        nvidia = get_nvidia_intelligence()
        result = nvidia.optimize_synthesis(
            target_properties=request.target_properties,
            constraints=request.constraints
        )
        return result
    except Exception as e:
        logger.error(f"Synthesis optimization error: {e}")
        raise internal_error(e, op="nvidia_routes:148")


@router.post("/chat")
async def chat_materials_expert(request: ChatRequest):
    """
    Chat with NVIDIA's materials science AI expert.
    
    Returns: AI response
    """
    try:
        nvidia = get_nvidia_intelligence()
        response = nvidia.chat_materials_expert(
            question=request.question,
            context=request.context
        )
        return {"response": response}
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise internal_error(e, op="nvidia_routes:167")


@router.get("/status")
async def nvidia_status():
    """
    Check NVIDIA API status.
    
    Returns: Status information
    """
    nvidia = get_nvidia_intelligence()
    return {
        "enabled": nvidia.enabled,
        "api_key_set": bool(nvidia.api_key),
        "features": [
            "material_prediction",
            "crystal_generation",
            "literature_search",
            "synthesis_optimization",
            "materials_chat"
        ] if nvidia.enabled else []
    }


# ══════════════════════════════════════════════════════════════════════
#   Paper Validation Endpoints
# ══════════════════════════════════════════════════════════════════════

@router.post("/validate")
async def validate_property(request: ValidationRequest):
    """
    Validate simulated property against research literature.
    
    Returns: Validation result with literature comparison
    """
    try:
        validator = get_paper_validator()
        result = validator.validate_material_property(
            material=request.material,
            property_name=request.property_name,
            simulated_value=request.simulated_value,
            tolerance=request.tolerance
        )
        
        return {
            "material": result.material,
            "property": result.property_name,
            "simulated_value": result.simulated_value,
            "literature_mean": result.mean_literature,
            "literature_std": result.std_literature,
            "literature_values": result.literature_values,
            "literature_sources": result.literature_sources,
            "error_percent": result.error_percent,
            "within_std": result.within_std,
            "confidence": result.confidence,
            "recommendation": result.recommendation
        }
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise internal_error(e, op="nvidia_routes:226")


@router.post("/validate-eis")
async def validate_eis_spectrum(request: EISValidationRequest):
    """
    Validate entire EIS spectrum against literature.
    
    Returns: Comprehensive validation report
    """
    try:
        validator = get_paper_validator()
        spectrum = {
            "Z_real": request.Z_real,
            "Z_imag": request.Z_imag
        }
        if request.capacitance:
            spectrum["capacitance"] = request.capacitance
        
        result = validator.validate_eis_spectrum(
            simulated_spectrum=spectrum,
            material=request.material
        )
        return result
    except Exception as e:
        logger.error(f"EIS validation error: {e}")
        raise internal_error(e, op="nvidia_routes:252")


@router.get("/validation-status")
async def validation_status():
    """
    Check paper validation system status.
    
    Returns: Status information
    """
    validator = get_paper_validator()
    return {
        "enabled": validator.enabled,
        "database_path": validator.db_path,
        "features": [
            "property_validation",
            "eis_validation",
            "literature_comparison"
        ] if validator.enabled else []
    }
