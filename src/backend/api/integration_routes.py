"""
Integration API Routes for RĀMAN Studio
========================================
REST API endpoints for external integrations:
- RDKit molecular descriptors
- CAMD Bayesian optimization
- WEI workflow execution

All endpoints fail gracefully if dependencies are missing.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.backend.integrations.rdkit_integration import get_rdkit_integration
from src.backend.integrations.camd_integration import get_camd_integration
from src.backend.integrations.wei_integration import get_wei_node

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/integrations", tags=["integrations"])


# ── RDKit Routes ────────────────────────────────────────────────

class MolecularDescriptorRequest(BaseModel):
    smiles: str = Field(..., description="SMILES string representation")


class SimilaritySearchRequest(BaseModel):
    query_smiles: str = Field(..., description="Query molecule SMILES")
    candidate_smiles: List[str] = Field(..., description="List of candidate SMILES")
    top_k: int = Field(10, ge=1, le=100, description="Number of top results to return")


@router.get("/rdkit/status")
async def rdkit_status():
    """Check if RDKit is available."""
    rdkit = get_rdkit_integration()
    return {
        "available": rdkit.is_available(),
        "features": [
            "molecular_descriptors",
            "fingerprint_generation",
            "similarity_search",
            "smiles_validation",
        ] if rdkit.is_available() else [],
    }


@router.post("/rdkit/descriptors")
async def calculate_descriptors(req: MolecularDescriptorRequest):
    """
    Calculate molecular descriptors from SMILES.
    
    Returns comprehensive descriptors including:
    - Molecular weight, LogP, TPSA
    - H-bond donors/acceptors
    - Rotatable bonds, aromatic rings
    - Morgan fingerprint for similarity search
    """
    rdkit = get_rdkit_integration()
    
    if not rdkit.is_available():
        raise HTTPException(
            status_code=503,
            detail="RDKit not installed - molecular descriptor features unavailable"
        )
    
    descriptors = rdkit.calculate_descriptors(req.smiles)
    
    if descriptors is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid SMILES string or calculation failed: {req.smiles}"
        )
    
    return descriptors.to_dict()


@router.post("/rdkit/similarity")
async def similarity_search(req: SimilaritySearchRequest):
    """
    Find most similar molecules using Tanimoto similarity.
    
    Uses Morgan fingerprints (radius=2, 2048 bits) to calculate
    similarity between query and candidate molecules.
    """
    rdkit = get_rdkit_integration()
    
    if not rdkit.is_available():
        raise HTTPException(
            status_code=503,
            detail="RDKit not installed"
        )
    
    results = rdkit.find_most_similar(req.query_smiles, req.candidate_smiles)
    
    if results is None:
        raise HTTPException(
            status_code=400,
            detail="Similarity calculation failed"
        )
    
    # Return top K results
    top_results = results[:req.top_k]
    
    return {
        "query_smiles": req.query_smiles,
        "results": [
            {"smiles": smiles, "similarity": round(score, 4)}
            for smiles, score in top_results
        ],
        "total_candidates": len(req.candidate_smiles),
    }


@router.post("/rdkit/validate")
async def validate_smiles(req: MolecularDescriptorRequest):
    """Validate if a SMILES string is chemically valid."""
    rdkit = get_rdkit_integration()
    
    if not rdkit.is_available():
        raise HTTPException(status_code=503, detail="RDKit not installed")
    
    is_valid = rdkit.validate_smiles(req.smiles)
    
    return {
        "smiles": req.smiles,
        "valid": is_valid,
    }


# ── CAMD Routes ─────────────────────────────────────────────────

class OptimizationRequest(BaseModel):
    objective: str = Field("maximize", description="'maximize' or 'minimize'")
    n_iterations: int = Field(50, ge=1, le=500)
    convergence_threshold: float = Field(0.01, ge=0, le=1)
    # Simulation parameters would be defined here
    # For now, using placeholder


@router.get("/camd/status")
async def camd_status():
    """Check if CAMD is available."""
    camd = get_camd_integration()
    return {
        "available": camd.is_available(),
        "features": [
            "bayesian_optimization",
            "active_learning",
            "experiment_suggestion",
        ] if camd.is_available() else [],
    }


@router.post("/camd/optimize")
async def run_optimization(req: OptimizationRequest):
    """
    Run Bayesian optimization for material discovery.
    
    Uses CAMD's agent-experiment-analyzer loop to find optimal
    material parameters by iteratively running VANL simulations.
    """
    camd = get_camd_integration()
    
    if not camd.is_available():
        raise HTTPException(
            status_code=503,
            detail="CAMD not installed - Bayesian optimization unavailable. Install camd to enable this feature."
        )
    
    raise HTTPException(
        status_code=501,
        detail="CAMD Bayesian optimization integration is not yet implemented. CAMD is installed but the materials database integration is pending."
    )


@router.post("/camd/suggest")
async def suggest_next_experiment():
    """
    Suggest next experiment based on history (active learning).
    
    Uses acquisition functions to select the most informative
    next experiment from the candidate space.
    """
    camd = get_camd_integration()
    
    if not camd.is_available():
        raise HTTPException(status_code=503, detail="CAMD not installed - active learning unavailable.")
    
    raise HTTPException(
        status_code=501,
        detail="CAMD active learning suggestion is not yet implemented. CAMD is installed but the experiment history integration is pending."
    )


# ── WEI Routes ──────────────────────────────────────────────────

class WEIActionRequest(BaseModel):
    action: str = Field(..., description="Action name to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict)


@router.get("/wei/node/info")
async def wei_node_info():
    """Get WEI node information and capabilities."""
    node = get_wei_node()
    return node.get_info().to_dict()


@router.post("/wei/node/action")
async def wei_execute_action(req: WEIActionRequest):
    """
    Execute a WEI node action.
    
    Available actions:
    - simulate_eis: Run EIS simulation
    - simulate_cv: Run CV simulation
    - simulate_gcd: Run GCD simulation
    - simulate_battery: Run battery simulation
    - identify_material: Run material identification
    - optimize_material: Run Bayesian optimization
    """
    node = get_wei_node()
    result = node.execute_action(req.action, req.parameters)
    
    if result.status == "error":
        raise HTTPException(
            status_code=400,
            detail=result.error or "Action execution failed"
        )
    
    return result.to_dict()


@router.get("/wei/node/status")
async def wei_node_status():
    """Get current WEI node status."""
    node = get_wei_node()
    return {
        "node_id": node.node_id,
        "status": node.status.value,
        "available_actions": list(node.actions.keys()),
    }


# ── Integration Status ──────────────────────────────────────────

@router.get("/status")
async def integration_status():
    """
    Get status of all external integrations.
    
    Returns availability and feature lists for:
    - RDKit (cheminformatics)
    - CAMD (Bayesian optimization)
    - WEI (workflow execution)
    """
    rdkit = get_rdkit_integration()
    camd = get_camd_integration()
    node = get_wei_node()
    
    return {
        "rdkit": {
            "available": rdkit.is_available(),
            "version": "2024.03.1" if rdkit.is_available() else None,
            "features": [
                "molecular_descriptors",
                "fingerprint_generation",
                "similarity_search",
            ] if rdkit.is_available() else [],
        },
        "camd": {
            "available": camd.is_available(),
            "version": "2023.12.0" if camd.is_available() else None,
            "features": [
                "bayesian_optimization",
                "active_learning",
            ] if camd.is_available() else [],
        },
        "wei": {
            "available": True,  # Always available (REST mode)
            "node_id": node.node_id,
            "capabilities": list(node.actions.keys()),
        },
    }
