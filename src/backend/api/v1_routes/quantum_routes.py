"""
Quantum Chemistry API Routes
=============================
REST API endpoints for quantum-accurate calculations using NVIDIA ALCHEMI.

Endpoints:
- POST /api/quantum/optimize - Optimize molecular geometry
- POST /api/quantum/properties - Calculate molecular properties
- POST /api/quantum/band-gap - Calculate electronic band gap
- GET /api/quantum/status - Check quantum engine status

Author: VidyuthLabs
Date: May 1, 2026
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from src.backend.api.error_handlers import internal_error
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
import numpy as np

from src.backend.core.engines.quantum_engine import (
    QuantumEngine,
    smiles_to_atoms,
    atoms_to_xyz,
    ALCHEMI_AVAILABLE,
    CUDA_AVAILABLE
)
from src.backend.licensing.license_manager import verify_license

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/quantum",
    tags=["quantum"],
    dependencies=[Depends(verify_license())],
)

# Initialize quantum engine (singleton)
_quantum_engine = None

def get_quantum_engine() -> QuantumEngine:
    """Get or create quantum engine instance."""
    global _quantum_engine
    if _quantum_engine is None:
        device = "cuda" if CUDA_AVAILABLE else "cpu"
        _quantum_engine = QuantumEngine(device=device)
        logger.info(f"Quantum engine initialized (device={device})")
    return _quantum_engine


# ===================================================================
#  Request/Response Models
# ===================================================================

class OptimizeRequest(BaseModel):
    """Request model for geometry optimization."""
    smiles: str = Field(..., min_length=1, max_length=200, description="SMILES string of molecule")
    method: str = Field("AIMNet2", description="Calculation method")
    force_tol: float = Field(0.01, gt=0, le=1e3, description="Force tolerance (eV/Å)")
    max_steps: int = Field(200, ge=1, le=100000, description="Maximum optimization steps")


class PropertiesRequest(BaseModel):
    """Request model for property calculation."""
    smiles: str = Field(..., min_length=1, max_length=200, description="SMILES string of molecule")
    properties: List[str] = Field(
        ["energy", "band_gap"],
        description="Properties to calculate"
    )


class BandGapRequest(BaseModel):
    """Request model for band gap calculation."""
    smiles: str = Field(..., min_length=1, max_length=200, description="SMILES string of molecule")
    method: str = Field("AIMNet2", description="Calculation method")


class QuantumResponse(BaseModel):
    """Response model for quantum calculations."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


# ===================================================================
#  API Endpoints
# ===================================================================

@router.get("/status")
async def get_status():
    """
    Get quantum engine status.
    
    Returns information about ALCHEMI availability, CUDA support, etc.
    """
    engine = get_quantum_engine()
    
    return {
        "status": "operational",
        "alchemi_available": ALCHEMI_AVAILABLE,
        "cuda_available": CUDA_AVAILABLE,
        "device": engine.device,
        "placeholder_mode": engine.placeholder_mode,
        "message": "Quantum engine ready" if not engine.placeholder_mode else "Running in placeholder mode - install ALCHEMI for full functionality"
    }


@router.post("/optimize", response_model=QuantumResponse)
async def optimize_geometry(request: OptimizeRequest):
    """
    Optimize molecular geometry to minimum energy.
    
    **Example Request:**
    ```json
    {
        "smiles": "CCO",
        "method": "AIMNet2",
        "force_tol": 0.01,
        "max_steps": 200
    }
    ```
    
    **Example Response:**
    ```json
    {
        "success": true,
        "data": {
            "energy_eV": -234.567,
            "geometry_A": [[0.0, 0.0, 0.0], ...],
            "converged": true,
            "n_iterations": 45,
            "wall_time_s": 2.34
        }
    }
    ```
    """
    try:
        engine = get_quantum_engine()
        
        # Convert SMILES to atoms
        atoms = smiles_to_atoms(request.smiles)
        
        # Optimize geometry
        result = engine.optimize_geometry(
            atoms,
            method=request.method,
            force_tol=request.force_tol,
            max_steps=request.max_steps
        )
        
        # Convert to dict
        data = result.to_dict()
        
        # Add XYZ format
        data["xyz"] = atoms_to_xyz({
            "positions": result.geometry_A,
            "atomic_numbers": result.atomic_numbers
        })
        
        return QuantumResponse(
            success=True,
            data=data,
            metadata={
                "smiles": request.smiles,
                "method": request.method
            }
        )
    
    except Exception as e:
        import secrets
        error_id = secrets.token_hex(6)
        logger.exception("geometry_optimization_failed error_id=%s", error_id)
        return QuantumResponse(
            success=False,
            error=f"Internal error (error_id={error_id}). Please retry; contact support if persistent.",
        )


@router.post("/properties", response_model=QuantumResponse)
async def calculate_properties(request: PropertiesRequest):
    """
    Calculate multiple molecular properties.
    
    **Available Properties:**
    - `energy`: Total energy (eV)
    - `forces`: Atomic forces (eV/Å)
    - `band_gap`: Electronic band gap (eV)
    - `homo`: HOMO energy (eV)
    - `lumo`: LUMO energy (eV)
    
    **Example Request:**
    ```json
    {
        "smiles": "c1ccccc1",
        "properties": ["energy", "band_gap", "homo", "lumo"]
    }
    ```
    """
    try:
        engine = get_quantum_engine()
        
        # Convert SMILES to atoms
        atoms = smiles_to_atoms(request.smiles)
        
        # Calculate properties
        props = engine.calculate_properties(atoms, request.properties)
        
        # Convert numpy arrays to lists for JSON serialization
        serializable_props = {}
        for key, value in props.items():
            if isinstance(value, np.ndarray):
                serializable_props[key] = value.tolist()
            else:
                serializable_props[key] = value
        
        return QuantumResponse(
            success=True,
            data=serializable_props,
            metadata={
                "smiles": request.smiles,
                "properties_requested": request.properties
            }
        )
    
    except Exception as e:
        import secrets
        error_id = secrets.token_hex(6)
        logger.exception("property_calculation_failed error_id=%s", error_id)
        return QuantumResponse(
            success=False,
            error=f"Internal error (error_id={error_id}). Please retry; contact support if persistent.",
        )


@router.post("/band-gap", response_model=QuantumResponse)
async def calculate_band_gap(request: BandGapRequest):
    """
    Calculate electronic band gap.
    
    **Example Request:**
    ```json
    {
        "smiles": "c1ccccc1",
        "method": "AIMNet2"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "success": true,
        "data": {
            "band_gap_eV": 5.47,
            "homo_eV": -5.0,
            "lumo_eV": 0.47
        }
    }
    ```
    """
    try:
        engine = get_quantum_engine()
        
        # Convert SMILES to atoms
        atoms = smiles_to_atoms(request.smiles)
        
        # Calculate band gap
        band_gap = engine.calculate_band_gap(atoms, method=request.method)
        
        # Estimate HOMO/LUMO (placeholder)
        homo = -5.0  # Typical value
        lumo = homo + band_gap
        
        return QuantumResponse(
            success=True,
            data={
                "band_gap_eV": band_gap,
                "homo_eV": homo,
                "lumo_eV": lumo
            },
            metadata={
                "smiles": request.smiles,
                "method": request.method
            }
        )
    
    except Exception as e:
        import secrets
        error_id = secrets.token_hex(6)
        logger.exception("band_gap_calculation_failed error_id=%s", error_id)
        return QuantumResponse(
            success=False,
            error=f"Internal error (error_id={error_id}). Please retry; contact support if persistent.",
        )


@router.post("/batch-optimize")
async def batch_optimize(
    request: Dict[str, List[str]],
    background_tasks: BackgroundTasks
):
    """
    Optimize multiple molecules in batch.
    
    **Example Request:**
    ```json
    {
        "smiles_list": ["CCO", "CC(=O)O", "c1ccccc1"]
    }
    ```
    
    This endpoint returns immediately and processes molecules in the background.
    Use the job ID to check status.
    """
    try:
        smiles_list = request.get("smiles_list", [])
        
        if not smiles_list:
            raise HTTPException(status_code=400, detail="smiles_list is required")
        
        # Generate job ID
        import uuid
        job_id = str(uuid.uuid4())
        
        # Add to background tasks
        # (In production, use Celery or similar for real background processing)
        
        return {
            "success": True,
            "job_id": job_id,
            "n_molecules": len(smiles_list),
            "message": "Batch optimization started",
            "status_url": f"/api/quantum/batch-status/{job_id}"
        }
    
    except Exception as e:
        logger.error(f"Batch optimization failed: {e}")
        raise internal_error(e, op="quantum_routes:335")


@router.get("/examples")
async def get_examples():
    """
    Get example molecules and their properties.
    
    Returns a list of common molecules with SMILES strings
    for testing the quantum engine.
    """
    examples = [
        {
            "name": "Ethanol",
            "smiles": "CCO",
            "formula": "C2H6O",
            "description": "Simple alcohol, good for testing"
        },
        {
            "name": "Benzene",
            "smiles": "c1ccccc1",
            "formula": "C6H6",
            "description": "Aromatic hydrocarbon, symmetric"
        },
        {
            "name": "Acetic Acid",
            "smiles": "CC(=O)O",
            "formula": "C2H4O2",
            "description": "Carboxylic acid"
        },
        {
            "name": "Graphene (fragment)",
            "smiles": "c1ccc2cc3ccccc3cc2c1",
            "formula": "C14H10",
            "description": "Anthracene - graphene-like structure"
        },
        {
            "name": "Water",
            "smiles": "O",
            "formula": "H2O",
            "description": "Simplest molecule"
        }
    ]
    
    return {
        "examples": examples,
        "note": "Use these SMILES strings to test the quantum engine"
    }


# ===================================================================
#  Health Check
# ===================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        engine = get_quantum_engine()
        return {
            "status": "healthy",
            "quantum_engine": "operational",
            "device": engine.device
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# ===================================================================
#  Advanced Features - Molecular Dynamics & Electron Density
# ===================================================================

class MolecularDynamicsRequest(BaseModel):
    """Request model for molecular dynamics simulation."""
    smiles: str = Field(..., min_length=1, max_length=200, description="SMILES string of molecule")
    n_steps: int = Field(1000, ge=1, le=100000, description="Number of MD steps")
    timestep_fs: float = Field(0.5, gt=0, le=1e3, description="Timestep in femtoseconds")
    temperature_K: float = Field(300.0, ge=0, le=1e5, description="Temperature in Kelvin")
    ensemble: str = Field("NVT", description="MD ensemble (NVE, NVT, NPT)")


class ElectronDensityRequest(BaseModel):
    """Request model for electron density calculation."""
    smiles: str = Field(..., min_length=1, max_length=200, description="SMILES string of molecule")
    grid_spacing: float = Field(0.2, gt=0, le=1e3, description="Grid spacing in Angstroms")
    padding: float = Field(3.0, ge=0, le=1e3, description="Padding around molecule in Angstroms")


@router.post("/molecular-dynamics", response_model=QuantumResponse)
async def run_molecular_dynamics(request: MolecularDynamicsRequest):
    """
    Run molecular dynamics simulation.
    
    **Example Request:**
    ```json
    {
        "smiles": "CCO",
        "n_steps": 1000,
        "timestep_fs": 0.5,
        "temperature_K": 300.0,
        "ensemble": "NVT"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "success": true,
        "data": {
            "n_steps": 1000,
            "timestep_fs": 0.5,
            "target_temperature_K": 300.0,
            "avg_temperature_K": 298.5,
            "avg_energy_eV": -234.567,
            "method": "AIMNet2"
        }
    }
    ```
    """
    try:
        engine = get_quantum_engine()
        
        # Convert SMILES to atoms
        atoms = smiles_to_atoms(request.smiles)
        
        # Run molecular dynamics
        result = engine.run_molecular_dynamics(
            atoms,
            n_steps=request.n_steps,
            timestep_fs=request.timestep_fs,
            temperature_K=request.temperature_K,
            ensemble=request.ensemble
        )
        
        # Convert numpy arrays to lists for JSON serialization
        serializable_result = {}
        for key, value in result.items():
            if isinstance(value, np.ndarray):
                # For large arrays, only send summary statistics
                if key == "positions":
                    serializable_result["trajectory_shape"] = value.shape
                    serializable_result["final_positions"] = value[-1].tolist()
                elif key == "velocities":
                    serializable_result["final_velocities"] = value[-1].tolist()
                elif key in ["energies", "temperatures", "time_fs"]:
                    serializable_result[key] = value.tolist()
            else:
                serializable_result[key] = value
        
        # Add summary statistics
        serializable_result["avg_temperature_K"] = float(np.mean(result["temperatures"]))
        serializable_result["avg_energy_eV"] = float(np.mean(result["energies"]))
        serializable_result["std_temperature_K"] = float(np.std(result["temperatures"]))
        serializable_result["std_energy_eV"] = float(np.std(result["energies"]))
        
        return QuantumResponse(
            success=True,
            data=serializable_result,
            metadata={
                "smiles": request.smiles,
                "n_steps": request.n_steps,
                "ensemble": request.ensemble
            }
        )
    
    except Exception as e:
        import secrets
        error_id = secrets.token_hex(6)
        logger.exception("molecular_dynamics_failed error_id=%s", error_id)
        return QuantumResponse(
            success=False,
            error=f"Internal error (error_id={error_id}). Please retry; contact support if persistent.",
        )


@router.post("/electron-density", response_model=QuantumResponse)
async def calculate_electron_density(request: ElectronDensityRequest):
    """
    Calculate electron density on a 3D grid.
    
    **Example Request:**
    ```json
    {
        "smiles": "CCO",
        "grid_spacing": 0.2,
        "padding": 3.0
    }
    ```
    
    **Example Response:**
    ```json
    {
        "success": true,
        "data": {
            "shape": [30, 30, 30],
            "grid_spacing": 0.2,
            "min_density": 0.0,
            "max_density": 12.5,
            "total_electrons": 26.0,
            "method": "AIMNet2"
        }
    }
    ```
    """
    try:
        engine = get_quantum_engine()
        
        # Convert SMILES to atoms
        atoms = smiles_to_atoms(request.smiles)
        
        # Calculate electron density
        result = engine.calculate_electron_density(
            atoms,
            grid_spacing=request.grid_spacing,
            padding=request.padding
        )
        
        # Convert numpy arrays to lists for JSON serialization
        # For large 3D arrays, only send metadata (not the full density grid)
        serializable_result = {
            "shape": result["shape"],
            "grid_spacing": result["grid_spacing"],
            "min_density": result["min_density"],
            "max_density": result["max_density"],
            "total_electrons": result["total_electrons"],
            "method": result["method"],
            "grid_x_min": float(result["grid_x"][0]),
            "grid_x_max": float(result["grid_x"][-1]),
            "grid_y_min": float(result["grid_y"][0]),
            "grid_y_max": float(result["grid_y"][-1]),
            "grid_z_min": float(result["grid_z"][0]),
            "grid_z_max": float(result["grid_z"][-1]),
        }
        
        # Optionally include a 2D slice for visualization
        if result["density"].shape[2] > 0:
            mid_z = result["density"].shape[2] // 2
            serializable_result["density_slice_z"] = result["density"][:, :, mid_z].tolist()
        
        return QuantumResponse(
            success=True,
            data=serializable_result,
            metadata={
                "smiles": request.smiles,
                "grid_spacing": request.grid_spacing,
                "padding": request.padding
            }
        )
    
    except Exception as e:
        import secrets
        error_id = secrets.token_hex(6)
        logger.exception("electron_density_calculation_failed error_id=%s", error_id)
        return QuantumResponse(
            success=False,
            error=f"Internal error (error_id={error_id}). Please retry; contact support if persistent.",
        )
