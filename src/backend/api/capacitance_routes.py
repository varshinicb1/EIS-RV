"""
Capacitance Calculation API Routes
===================================
Endpoints for calculating specific capacitance from CV data using
standard electrochemistry equations.

Author: VidyuthLabs
Date: May 13, 2026
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.backend.core.capacitance_calculator import (
    get_capacitance_calculator,
    CapacitanceResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/capacitance", tags=["capacitance"])


# ── Request Models ──────────────────────────────────────────────

class CVCapacitanceRequest(BaseModel):
    """Request for calculating capacitance from CV data."""
    potential: List[float] = Field(..., description="Potential array (V)", min_items=10)
    current: List[float] = Field(..., description="Current array (A)", min_items=10)
    scan_rate_mV_s: float = Field(..., gt=0, description="Scan rate (mV/s)")
    mass_g: Optional[float] = Field(None, gt=0, description="Mass of active material (g)")
    area_cm2: Optional[float] = Field(None, gt=0, description="Electrode area (cm²)")
    volume_cm3: Optional[float] = Field(None, gt=0, description="Volume of active material (cm³)")
    calculate_reversibility: bool = Field(True, description="Calculate reversibility metrics")


class AverageCurrentRequest(BaseModel):
    """Request for simplified capacitance calculation from average current."""
    average_current_A: float = Field(..., gt=0, description="Average current (A)")
    scan_rate_mV_s: float = Field(..., gt=0, description="Scan rate (mV/s)")
    mass_g: Optional[float] = Field(None, gt=0, description="Mass of active material (g)")
    area_cm2: Optional[float] = Field(None, gt=0, description="Electrode area (cm²)")


class MultiScanRateRequest(BaseModel):
    """Request for multi-scan-rate analysis."""
    cv_data: List[Dict[str, Any]] = Field(
        ...,
        description="List of CV data dicts with 'potential', 'current', 'scan_rate_mV_s'",
        min_items=2
    )
    mass_g: Optional[float] = Field(None, gt=0)
    area_cm2: Optional[float] = Field(None, gt=0)


class RagoneRequest(BaseModel):
    """Request for Ragone plot (energy/power) analysis."""
    capacitance_F_g: float = Field(..., gt=0, description="Specific capacitance (F/g)")
    potential_window_V: float = Field(..., gt=0, description="Potential window (V)")
    mass_g: float = Field(..., gt=0, description="Mass of active material (g)")
    esr_ohm: Optional[float] = Field(None, gt=0, description="Equivalent series resistance (Ω)")


# ── Endpoints ───────────────────────────────────────────────────

@router.post("/from-cv")
async def calculate_from_cv(request: CVCapacitanceRequest) -> Dict:
    """
    Calculate specific capacitance from CV data.
    
    Uses standard equation: Cs = ∫I dV / (2 × m × ΔV × ν)
    
    Returns:
        - specific_capacitance_F_g: Gravimetric capacitance (F/g)
        - areal_capacitance_F_cm2: Areal capacitance (F/cm²)
        - volumetric_capacitance_F_cm3: Volumetric capacitance (F/cm³)
        - charge_coulombs: Total charge (C)
        - reversibility: Reversibility metric (0-1)
        - coulombic_efficiency: Coulombic efficiency
    """
    try:
        calculator = get_capacitance_calculator()
        
        result = calculator.from_cv_data(
            potential=request.potential,
            current=request.current,
            scan_rate_mV_s=request.scan_rate_mV_s,
            mass_g=request.mass_g,
            area_cm2=request.area_cm2,
            volume_cm3=request.volume_cm3,
            calculate_reversibility=request.calculate_reversibility,
        )
        
        return {
            "success": True,
            "result": result.to_dict(),
            "equation": "Cs = ∫I dV / (2 × m × ΔV × ν)",
            "reference": "Stoller & Ruoff (2010), Energy Environ. Sci., 3(9), 1294-1301",
        }
        
    except Exception as e:
        logger.error(f"Capacitance calculation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/from-average-current")
async def calculate_from_average_current(request: AverageCurrentRequest) -> Dict:
    """
    Calculate capacitance from average current (simplified method).
    
    Uses: C = I_avg / ν
    
    Faster but less accurate than full CV integration.
    """
    try:
        calculator = get_capacitance_calculator()
        
        result = calculator.from_average_current(
            average_current_A=request.average_current_A,
            scan_rate_mV_s=request.scan_rate_mV_s,
            mass_g=request.mass_g,
            area_cm2=request.area_cm2,
        )
        
        return {
            "success": True,
            "result": result.to_dict(),
            "equation": "C = I_avg / ν",
            "note": "Simplified method - use full CV integration for accurate results",
        }
        
    except Exception as e:
        logger.error(f"Capacitance calculation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/multi-scan-rate")
async def multi_scan_rate_analysis(request: MultiScanRateRequest) -> Dict:
    """
    Analyze capacitance at multiple scan rates.
    
    Useful for:
    - Determining rate capability
    - Identifying diffusion-limited vs. capacitive behavior
    - Optimizing scan rate for measurements
    
    Returns:
        - results: List of CapacitanceResult for each scan rate
        - scan_rates: List of scan rates (mV/s)
        - capacitances: List of capacitances (F/g or F/cm²)
        - rate_capability: % retention from lowest to highest rate
        - best_capacitance: Maximum capacitance observed
    """
    try:
        calculator = get_capacitance_calculator()
        
        analysis = calculator.multi_scan_rate_analysis(
            cv_data_list=request.cv_data,
            mass_g=request.mass_g,
            area_cm2=request.area_cm2,
        )
        
        # Convert results to dicts
        analysis['results'] = [r.to_dict() for r in analysis['results']]
        
        return {
            "success": True,
            "analysis": analysis,
            "interpretation": {
                "rate_capability": f"{analysis['rate_capability']:.1f}%",
                "performance": (
                    "Excellent" if analysis['rate_capability'] > 80 else
                    "Good" if analysis['rate_capability'] > 60 else
                    "Moderate" if analysis['rate_capability'] > 40 else
                    "Poor"
                ),
            },
        }
        
    except Exception as e:
        logger.error(f"Multi-scan-rate analysis failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ragone-analysis")
async def ragone_analysis(request: RagoneRequest) -> Dict:
    """
    Calculate energy and power density for Ragone plot.
    
    Returns:
        - energy_density_Wh_kg: Energy density (Wh/kg)
        - power_density_W_kg: Power density (W/kg)
        
    Used for comparing supercapacitor performance.
    """
    try:
        calculator = get_capacitance_calculator()
        
        result = calculator.energy_power_analysis(
            capacitance_F_g=request.capacitance_F_g,
            potential_window_V=request.potential_window_V,
            mass_g=request.mass_g,
            esr_ohm=request.esr_ohm,
        )
        
        return {
            "success": True,
            "result": result,
            "equations": {
                "energy": "E = 0.5 × C × V² / 3.6 (Wh/kg)",
                "power": "P = V² / (4 × ESR × m) (W/kg)",
            },
        }
        
    except Exception as e:
        logger.error(f"Ragone analysis failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/equations")
async def get_equations() -> Dict:
    """
    Get all standard equations for capacitance calculations.
    
    Returns reference equations from literature.
    """
    return {
        "equations": {
            "gravimetric_specific_capacitance": {
                "formula": "Cs = ∫I dV / (2 × m × ΔV × ν)",
                "units": "F/g",
                "variables": {
                    "∫I dV": "Area under CV curve (Coulombs)",
                    "m": "Mass of active material (g)",
                    "ΔV": "Potential window (V)",
                    "ν": "Scan rate (V/s)",
                    "2": "Factor accounting for both anodic and cathodic scans",
                },
            },
            "areal_specific_capacitance": {
                "formula": "Ca = ∫I dV / (2 × A × ΔV × ν)",
                "units": "F/cm²",
                "variables": {
                    "A": "Electrode area (cm²)",
                },
            },
            "volumetric_specific_capacitance": {
                "formula": "Cv = ∫I dV / (2 × V × ΔV × ν)",
                "units": "F/cm³",
                "variables": {
                    "V": "Volume of active material (cm³)",
                },
            },
            "simplified_from_average_current": {
                "formula": "C = I_avg / ν",
                "units": "F",
                "note": "Less accurate but faster calculation",
            },
            "energy_density": {
                "formula": "E = 0.5 × C × V² / 3.6",
                "units": "Wh/kg",
                "variables": {
                    "C": "Specific capacitance (F/g)",
                    "V": "Potential window (V)",
                    "3.6": "Conversion factor J to Wh",
                },
            },
            "power_density": {
                "formula": "P = V² / (4 × ESR × m)",
                "units": "W/kg",
                "variables": {
                    "ESR": "Equivalent series resistance (Ω)",
                    "m": "Mass (g)",
                },
            },
        },
        "references": [
            {
                "authors": "Stoller, M. D., & Ruoff, R. S.",
                "title": "Best practice methods for determining an electrode material's performance for ultracapacitors",
                "journal": "Energy & Environmental Science",
                "year": 2010,
                "volume": "3(9)",
                "pages": "1294-1301",
                "doi": "10.1039/C0EE00074D",
            },
            {
                "authors": "Conway, B. E.",
                "title": "Electrochemical Supercapacitors: Scientific Fundamentals and Technological Applications",
                "publisher": "Springer",
                "year": 1999,
                "isbn": "978-0306457364",
            },
        ],
    }


@router.get("/best-practices")
async def get_best_practices() -> Dict:
    """
    Get best practices for CV capacitance measurements.
    
    Based on Stoller & Ruoff (2010) recommendations.
    """
    return {
        "best_practices": {
            "scan_rate": {
                "recommendation": "Use multiple scan rates (5-200 mV/s)",
                "reason": "Identify rate-dependent behavior and diffusion limitations",
                "typical_values": [5, 10, 20, 50, 100, 200],  # mV/s
            },
            "potential_window": {
                "recommendation": "Use maximum stable potential window",
                "reason": "Maximize energy density without electrolyte decomposition",
                "aqueous": "0.8-1.2 V",
                "organic": "2.5-3.0 V",
                "ionic_liquid": "3.0-4.0 V",
            },
            "electrode_preparation": {
                "active_material": "80-90 wt%",
                "binder": "5-10 wt% (PVDF, Nafion)",
                "conductive_additive": "5-10 wt% (carbon black, CNT)",
                "loading": "1-10 mg/cm²",
            },
            "measurement_conditions": {
                "temperature": "25°C (controlled)",
                "cycles": "Minimum 5 cycles for stabilization",
                "data_points": "Minimum 100 points per cycle",
            },
            "data_quality": {
                "reversibility": "> 0.8 for good capacitive behavior",
                "coulombic_efficiency": "> 0.95 for stable cycling",
                "IR_drop": "< 10% of potential window",
            },
        },
        "common_mistakes": [
            "Using only one scan rate (doesn't reveal rate capability)",
            "Not accounting for current collector mass",
            "Ignoring IR drop in potential window",
            "Using too high scan rate (diffusion-limited)",
            "Not stabilizing electrode before measurement",
        ],
    }
