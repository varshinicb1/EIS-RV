"""
Advanced Physics Validation API Routes for RĀMAN Studio
=======================================================
REST API endpoints for LAMMPS and Quantum ESPRESSO integrations.

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.backend.physics import (
    get_lammps_integration,
    get_qe_integration,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/physics", tags=["physics"])


# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class InterfaceSimulationRequest(BaseModel):
    """Request for electrode-electrolyte interface simulation."""
    material: str = Field(..., description="Electrode material (e.g., 'graphene')")
    electrolyte: str = Field(..., description="Electrolyte composition (e.g., '1M NaCl')")
    voltage: float = Field(0.0, description="Applied voltage (V)")
    temperature: float = Field(300.0, description="Temperature (K)")
    n_steps: int = Field(100000, description="Number of MD steps")


class DiffusionRequest(BaseModel):
    """Request for diffusion coefficient calculation."""
    material: str = Field(..., description="Electrode material")
    electrolyte: str = Field(..., description="Electrolyte composition")
    temperature: float = Field(300.0, description="Temperature (K)")
    n_steps: int = Field(50000, description="Number of MD steps")


class RDFRequest(BaseModel):
    """Request for radial distribution function."""
    material: str = Field(..., description="Electrode material")
    electrolyte: str = Field(..., description="Electrolyte composition")
    r_max: float = Field(10.0, description="Maximum distance (Angstroms)")
    n_bins: int = Field(100, description="Number of bins")


class BandStructureRequest(BaseModel):
    """Request for band structure calculation."""
    material: str = Field(..., description="Material name")
    structure: Optional[Dict[str, Any]] = Field(None, description="Crystal structure")
    k_path: Optional[List[str]] = Field(None, description="High-symmetry k-point path")


class DOSRequest(BaseModel):
    """Request for density of states calculation."""
    material: str = Field(..., description="Material name")
    structure: Optional[Dict[str, Any]] = Field(None, description="Crystal structure")
    energy_range: List[float] = Field([-10.0, 10.0], description="Energy range (eV)")
    n_points: int = Field(1000, description="Number of energy points")


class WorkFunctionRequest(BaseModel):
    """Request for work function calculation."""
    material: str = Field(..., description="Material name")
    structure: Optional[Dict[str, Any]] = Field(None, description="Crystal structure")
    surface: str = Field("001", description="Surface orientation")


class ParameterExtractionRequest(BaseModel):
    """Request for VANL parameter extraction."""
    source: str = Field(..., description="Source of data ('lammps' or 'qe')")
    material: str = Field(..., description="Material name")
    data: Dict[str, Any] = Field(..., description="Simulation results")


# ═══════════════════════════════════════════════════════════════
# Status Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/status")
async def get_status():
    """Get physics integration status."""
    try:
        lammps = get_lammps_integration()
        qe = get_qe_integration()
        
        return {
            "status": "success",
            "lammps": lammps.get_status(),
            "quantum_espresso": qe.get_status(),
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# LAMMPS Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/lammps/interface")
async def simulate_interface(request: InterfaceSimulationRequest):
    """
    Simulate electrode-electrolyte interface using LAMMPS.
    
    Returns capacitance, charge density, ion density profile, etc.
    """
    try:
        lammps = get_lammps_integration()
        
        results = lammps.simulate_interface(
            material=request.material,
            electrolyte=request.electrolyte,
            voltage=request.voltage,
            temperature=request.temperature,
            n_steps=request.n_steps,
        )
        
        return {
            "status": "success",
            "results": results.to_dict(),
        }
    except Exception as e:
        logger.error(f"Error simulating interface: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lammps/diffusion")
async def calculate_diffusion(request: DiffusionRequest):
    """
    Calculate ion diffusion coefficients using LAMMPS.
    
    Returns diffusion coefficients for cations and anions.
    """
    try:
        lammps = get_lammps_integration()
        
        results = lammps.calculate_diffusion_coefficient(
            material=request.material,
            electrolyte=request.electrolyte,
            temperature=request.temperature,
            n_steps=request.n_steps,
        )
        
        return {
            "status": "success",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error calculating diffusion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lammps/rdf")
async def compute_rdf(request: RDFRequest):
    """
    Compute radial distribution function using LAMMPS.
    
    Returns g(r) for the electrode-electrolyte system.
    """
    try:
        lammps = get_lammps_integration()
        
        rdf = lammps.compute_rdf(
            material=request.material,
            electrolyte=request.electrolyte,
            r_max=request.r_max,
            n_bins=request.n_bins,
        )
        
        return {
            "status": "success",
            "rdf": rdf,
        }
    except Exception as e:
        logger.error(f"Error computing RDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lammps/extract-parameters")
async def extract_lammps_parameters(request: ParameterExtractionRequest):
    """
    Extract VANL parameters from LAMMPS results.
    
    Returns Cdl, Rct, Rs, etc. for use in VANL simulations.
    """
    try:
        lammps = get_lammps_integration()
        
        # Reconstruct InterfaceResults from data
        from src.backend.physics.lammps_integration import InterfaceResults
        
        interface_results = InterfaceResults(
            capacitance=request.data.get("capacitance", 10.0),
            charge_density=request.data.get("charge_density", 0.0),
            potential_drop=request.data.get("potential_drop", 1.0),
            ion_density_profile=request.data.get("ion_density_profile", []),
            diffusion_coefficient=request.data.get("diffusion_coefficient", 1e-9),
            rdf=request.data.get("rdf"),
        )
        
        parameters = lammps.extract_vanl_parameters(interface_results)
        
        return {
            "status": "success",
            "parameters": parameters,
        }
    except Exception as e:
        logger.error(f"Error extracting parameters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lammps/simulations")
async def list_lammps_simulations():
    """List all LAMMPS simulations."""
    try:
        lammps = get_lammps_integration()
        simulations = lammps.list_simulations()
        
        return {
            "status": "success",
            "simulations": [sim.to_dict() for sim in simulations],
        }
    except Exception as e:
        logger.error(f"Error listing simulations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Quantum ESPRESSO Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/qe/bands")
async def calculate_band_structure(request: BandStructureRequest):
    """
    Calculate electronic band structure using Quantum ESPRESSO.
    
    Returns k-points, eigenvalues, Fermi energy, band gap.
    """
    try:
        qe = get_qe_integration()
        
        band_structure = qe.calculate_band_structure(
            material=request.material,
            structure=request.structure,
            k_path=request.k_path,
        )
        
        return {
            "status": "success",
            "band_structure": band_structure.to_dict(),
        }
    except Exception as e:
        logger.error(f"Error calculating band structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qe/dos")
async def calculate_dos(request: DOSRequest):
    """
    Calculate density of states using Quantum ESPRESSO.
    
    Returns energies and DOS values.
    """
    try:
        qe = get_qe_integration()
        
        dos = qe.calculate_dos(
            material=request.material,
            structure=request.structure,
            energy_range=tuple(request.energy_range),
            n_points=request.n_points,
        )
        
        return {
            "status": "success",
            "dos": dos.to_dict(),
        }
    except Exception as e:
        logger.error(f"Error calculating DOS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qe/work-function")
async def calculate_work_function(request: WorkFunctionRequest):
    """
    Calculate work function using Quantum ESPRESSO.
    
    Returns work function, vacuum level, Fermi level, surface dipole.
    """
    try:
        qe = get_qe_integration()
        
        work_function = qe.calculate_work_function(
            material=request.material,
            structure=request.structure,
            surface=request.surface,
        )
        
        return {
            "status": "success",
            "work_function": work_function.to_dict(),
        }
    except Exception as e:
        logger.error(f"Error calculating work function: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qe/extract-parameters")
async def extract_qe_parameters(request: ParameterExtractionRequest):
    """
    Extract VANL parameters from Quantum ESPRESSO results.
    
    Returns conductivity, Rct, Cdl, work function, band gap.
    """
    try:
        qe = get_qe_integration()
        
        # Reconstruct results from data
        from src.backend.physics.quantum_espresso_integration import (
            BandStructure,
            DensityOfStates,
            WorkFunction,
        )
        
        band_data = request.data.get("band_structure", {})
        dos_data = request.data.get("dos", {})
        wf_data = request.data.get("work_function", {})
        
        band_structure = BandStructure(
            k_points=band_data.get("k_points", []),
            eigenvalues=band_data.get("eigenvalues", []),
            fermi_energy=band_data.get("fermi_energy", 0.0),
            band_gap=band_data.get("band_gap", 0.0),
            is_metal=band_data.get("is_metal", True),
        )
        
        dos = DensityOfStates(
            energies=dos_data.get("energies", []),
            dos=dos_data.get("dos", []),
            fermi_energy=dos_data.get("fermi_energy", 0.0),
        )
        
        work_function = WorkFunction(
            work_function=wf_data.get("work_function", 4.5),
            vacuum_level=wf_data.get("vacuum_level", 8.5),
            fermi_level=wf_data.get("fermi_level", 0.0),
            surface_dipole=wf_data.get("surface_dipole", 0.5),
        )
        
        parameters = qe.extract_vanl_parameters(
            band_structure, dos, work_function
        )
        
        return {
            "status": "success",
            "parameters": parameters,
        }
    except Exception as e:
        logger.error(f"Error extracting parameters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qe/calculations")
async def list_qe_calculations():
    """List all Quantum ESPRESSO calculations."""
    try:
        qe = get_qe_integration()
        calculations = qe.list_calculations()
        
        return {
            "status": "success",
            "calculations": [calc.to_dict() for calc in calculations],
        }
    except Exception as e:
        logger.error(f"Error listing calculations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Combined Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/validate-material")
async def validate_material(
    material: str,
    electrolyte: str = "1M NaCl",
    voltage: float = 0.0,
    temperature: float = 300.0,
):
    """
    Complete physics validation for a material.
    
    Runs both LAMMPS and Quantum ESPRESSO calculations and
    extracts VANL parameters.
    """
    try:
        lammps = get_lammps_integration()
        qe = get_qe_integration()
        
        # Run LAMMPS interface simulation
        interface_results = lammps.simulate_interface(
            material=material,
            electrolyte=electrolyte,
            voltage=voltage,
            temperature=temperature,
        )
        
        # Run Quantum ESPRESSO calculations
        band_structure = qe.calculate_band_structure(material=material)
        dos = qe.calculate_dos(material=material)
        work_function = qe.calculate_work_function(material=material)
        
        # Extract VANL parameters from both sources
        lammps_params = lammps.extract_vanl_parameters(interface_results)
        qe_params = qe.extract_vanl_parameters(
            band_structure, dos, work_function
        )
        
        # Combine parameters
        combined_params = {
            "lammps": lammps_params,
            "quantum_espresso": qe_params,
            "recommended": {
                "Cdl": (lammps_params["Cdl"] + qe_params["Cdl"]) / 2,
                "Rct": (lammps_params["Rct"] + qe_params["Rct"]) / 2,
                "Rs": lammps_params["Rs"],
                "n": lammps_params["n"],
                "conductivity": qe_params["conductivity"],
                "work_function": qe_params["work_function"],
                "band_gap": qe_params["band_gap"],
            },
        }
        
        return {
            "status": "success",
            "material": material,
            "electrolyte": electrolyte,
            "interface_results": interface_results.to_dict(),
            "band_structure": band_structure.to_dict(),
            "dos": dos.to_dict(),
            "work_function": work_function.to_dict(),
            "parameters": combined_params,
        }
    except Exception as e:
        logger.error(f"Error validating material: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/materials/validated")
async def list_validated_materials():
    """
    List materials that have been validated with physics simulations.
    """
    try:
        # This would query a database in production
        # For now, return a static list
        validated_materials = [
            {
                "material": "graphene",
                "validated": True,
                "lammps_runs": 5,
                "qe_runs": 3,
                "last_validated": "2026-05-12T10:00:00Z",
            },
            {
                "material": "carbon",
                "validated": True,
                "lammps_runs": 3,
                "qe_runs": 2,
                "last_validated": "2026-05-12T09:00:00Z",
            },
        ]
        
        return {
            "status": "success",
            "materials": validated_materials,
        }
    except Exception as e:
        logger.error(f"Error listing validated materials: {e}")
        raise HTTPException(status_code=500, detail=str(e))
