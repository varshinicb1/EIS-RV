"""
Material Identification API Routes
===================================
Enhanced AI-powered material identification endpoints.

Combines RDKit molecular fingerprints with ML models for
accurate material identification from electrochemical data.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from src.backend.ml.material_identifier import get_material_identifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/material-id", tags=["material-identification"])


# ── Request Models ──────────────────────────────────────────────

class EISIdentificationRequest(BaseModel):
    frequencies: List[float] = Field(..., description="Frequency array (Hz)")
    Z_real: List[float] = Field(..., description="Real impedance (Ω)")
    Z_imag: List[float] = Field(..., description="Imaginary impedance (Ω)")
    top_k: int = Field(3, ge=1, le=10, description="Number of top candidates")


class CVIdentificationRequest(BaseModel):
    potential: List[float] = Field(..., description="Potential array (V)")
    current: List[float] = Field(..., description="Current array (A)")
    top_k: int = Field(3, ge=1, le=10)


class RamanIdentificationRequest(BaseModel):
    wavenumber: List[float] = Field(..., description="Raman shift (cm^-1)")
    intensity: List[float] = Field(..., description="Raman intensity (a.u.)")
    top_k: int = Field(3, ge=1, le=10)


class TrainModelRequest(BaseModel):
    test_size: float = Field(0.2, ge=0.1, le=0.5)
    force_retrain: bool = Field(False)


# ── Status & Info ───────────────────────────────────────────────

@router.get("/status")
async def get_status():
    """
    Get material identification system status.
    
    Returns:
        - ML model status (trained/untrained)
        - Number of materials in database
        - RDKit availability
        - Feature extraction capabilities
    """
    identifier = get_material_identifier()
    
    return {
        "ml_model_trained": identifier.trained,
        "n_materials": len(identifier.materials_db),
        "rdkit_available": identifier.rdkit.is_available(),
        "features": {
            "eis_identification": True,
            "cv_identification": True,
            "raman_identification": True,
            "multi_modal_fusion": False,  # Future feature
        },
    }


@router.get("/materials")
async def list_materials():
    """
    List all materials in the database.
    
    Returns:
        List of materials with names, SMILES, and properties
    """
    identifier = get_material_identifier()
    
    materials = [
        {
            "name": m.get("name"),
            "smiles": m.get("smiles"),
            "category": m.get("category", "unknown"),
            "has_rdkit_descriptors": "rdkit_descriptors" in m,
        }
        for m in identifier.materials_db
    ]
    
    return {
        "materials": materials,
        "total": len(materials),
    }


# ── Training ────────────────────────────────────────────────────

@router.post("/train")
async def train_model(req: TrainModelRequest):
    """
    Train ML model on materials database.
    
    Trains a Random Forest classifier on extracted features
    from the materials database. Requires at least 10 materials.
    
    Returns:
        Training metrics (accuracy, n_train, n_test)
    """
    identifier = get_material_identifier()
    
    if identifier.trained and not req.force_retrain:
        return {
            "status": "already_trained",
            "message": "Model already trained. Use force_retrain=true to retrain.",
        }
    
    if len(identifier.materials_db) == 0:
        raise HTTPException(
            status_code=400,
            detail="No materials in database. Load materials first."
        )
    
    metrics = identifier.train_model(test_size=req.test_size)
    
    if "error" in metrics:
        raise HTTPException(status_code=400, detail=metrics["error"])
    
    return {
        "status": "trained",
        "metrics": metrics,
    }


# ── Identification ──────────────────────────────────────────────

@router.post("/identify/eis")
async def identify_from_eis(req: EISIdentificationRequest):
    """
    Identify material from EIS data.
    
    Extracts features (Rs, Rct, Cdl, Warburg) from EIS spectrum
    and predicts material using ML model + RDKit similarity.
    
    Returns:
        - Best match material with confidence score
        - Alternative candidates
        - Synthesis route (if available)
        - Material properties
    """
    identifier = get_material_identifier()
    
    if len(identifier.materials_db) == 0:
        raise HTTPException(
            status_code=400,
            detail="No materials in database. Load materials first."
        )
    
    if len(req.frequencies) != len(req.Z_real) or len(req.frequencies) != len(req.Z_imag):
        raise HTTPException(
            status_code=400,
            detail="frequencies, Z_real, and Z_imag must have equal length"
        )
    
    try:
        prediction = identifier.identify_from_eis(
            frequencies=req.frequencies,
            Z_real=req.Z_real,
            Z_imag=req.Z_imag,
            top_k=req.top_k
        )
        
        return prediction.to_dict()
        
    except Exception as e:
        logger.error(f"EIS identification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/identify/cv")
async def identify_from_cv(req: CVIdentificationRequest):
    """
    Identify material from CV data.
    
    Extracts features (peak currents, reversibility) from CV curve
    and predicts material using ML model.
    
    Returns:
        Material prediction with confidence and alternatives
    """
    identifier = get_material_identifier()
    
    if len(identifier.materials_db) == 0:
        raise HTTPException(
            status_code=400,
            detail="No materials in database"
        )
    
    if len(req.potential) != len(req.current):
        raise HTTPException(
            status_code=400,
            detail="potential and current must have equal length"
        )
    
    try:
        # Extract CV features
        features = identifier.extract_cv_features(req.potential, req.current)
        
        # For now, use rule-based identification
        # TODO: Implement CV-specific ML model
        prediction = identifier._physics_based_identification(features, req.top_k)
        
        return prediction.to_dict()
        
    except Exception as e:
        logger.error(f"CV identification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/identify/raman")
async def identify_from_raman(req: RamanIdentificationRequest):
    """
    Identify material from Raman spectroscopy data.
    
    Extracts features (D/G band positions, I_D/I_G ratio) from
    Raman spectrum and predicts material.
    
    Returns:
        Material prediction with confidence and alternatives
    """
    identifier = get_material_identifier()
    
    if len(identifier.materials_db) == 0:
        raise HTTPException(
            status_code=400,
            detail="No materials in database"
        )
    
    if len(req.wavenumber) != len(req.intensity):
        raise HTTPException(
            status_code=400,
            detail="wavenumber and intensity must have equal length"
        )
    
    try:
        # Extract Raman features
        features = identifier.extract_raman_features(req.wavenumber, req.intensity)
        
        # Use rule-based identification
        prediction = identifier._physics_based_identification(features, req.top_k)
        
        return prediction.to_dict()
        
    except Exception as e:
        logger.error(f"Raman identification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Database Management ─────────────────────────────────────────

@router.post("/database/load")
async def load_database(db_path: str):
    """
    Load materials database from JSON file.
    
    Args:
        db_path: Path to materials database JSON
        
    Returns:
        Number of materials loaded
    """
    identifier = get_material_identifier()
    
    try:
        n_loaded = identifier.load_materials_database(db_path)
        
        if n_loaded == 0:
            raise HTTPException(
                status_code=400,
                detail="Failed to load materials database"
            )
        
        return {
            "status": "loaded",
            "n_materials": n_loaded,
            "rdkit_descriptors_calculated": identifier.rdkit.is_available(),
        }
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Database file not found: {db_path}"
        )
    except Exception as e:
        logger.error(f"Database load failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features/eis")
async def extract_eis_features(
    frequencies: List[float],
    Z_real: List[float],
    Z_imag: List[float]
):
    """
    Extract features from EIS data without identification.
    
    Useful for debugging and understanding feature extraction.
    
    Returns:
        Extracted features (Rs, Rct, Cdl, Warburg coefficient)
    """
    identifier = get_material_identifier()
    
    if len(frequencies) != len(Z_real) or len(frequencies) != len(Z_imag):
        raise HTTPException(
            status_code=400,
            detail="Array length mismatch"
        )
    
    try:
        features = identifier.extract_eis_features(frequencies, Z_real, Z_imag)
        
        return {
            "Rs": features.Rs,
            "Rct": features.Rct,
            "Cdl": features.Cdl,
            "warburg_coeff": features.warburg_coeff,
        }
        
    except Exception as e:
        logger.error(f"Feature extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
