"""
Raman Spectroscopy API Routes
==============================
REST API endpoints for Raman spectroscopy analysis.

Endpoints:
- POST /api/v1/raman/upload - Upload and analyze Raman spectrum
- POST /api/v1/raman/analyze - Analyze uploaded spectrum with custom config
- GET /api/v1/raman/materials - Get material identification database
- POST /api/v1/raman/identify - Identify material from spectrum

Author: VidyuthLabs
Date: May 4, 2026
"""

import logging
import tempfile
import os
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, Field

from src.backend.core.engines.raman_engine import (
    RamanAnalyzer,
    RamanAnalysisConfig,
    RamanSpectrum,
    import_raman_data,
    identify_material,
    RAMAN_MATERIAL_DATABASE,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/raman", tags=["raman"])


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════

class RamanAnalysisRequest(BaseModel):
    """Request model for Raman analysis configuration."""
    # Baseline correction
    baseline_method: str = Field("airpls", description="Baseline correction method")
    baseline_lambda: float = Field(1e5, ge=1e2, le=1e8, description="Smoothness parameter")
    baseline_p: float = Field(0.001, ge=0.0001, le=0.1, description="Asymmetry parameter")
    polynomial_order: int = Field(5, ge=2, le=10, description="Polynomial order")
    
    # Denoising
    denoise_method: str = Field("savgol", description="Denoising method")
    savgol_window: int = Field(11, ge=5, le=51, description="Savitzky-Golay window")
    savgol_polyorder: int = Field(3, ge=2, le=5, description="Savitzky-Golay polynomial order")
    
    # Peak detection
    peak_detection: bool = Field(True, description="Enable peak detection")
    peak_prominence: float = Field(50.0, ge=1.0, le=1000.0, description="Minimum peak prominence")
    peak_min_distance: int = Field(10, ge=1, le=100, description="Minimum peak distance")
    
    # Peak fitting
    peak_fitting: bool = Field(True, description="Enable peak fitting")
    peak_model: str = Field("lorentzian", description="Peak model (lorentzian/gaussian)")
    
    # Normalization
    normalize: bool = Field(True, description="Enable normalization")
    normalization_method: str = Field("minmax", description="Normalization method")


class RamanUploadRequest(BaseModel):
    """Request model for quick Raman upload with default settings."""
    sample_id: Optional[str] = Field(None, description="Sample identifier")
    laser_wavelength_nm: Optional[float] = Field(None, description="Laser wavelength (nm)")
    laser_power_mW: Optional[float] = Field(None, description="Laser power (mW)")
    integration_time_s: Optional[float] = Field(None, description="Integration time (s)")
    temperature_C: Optional[float] = Field(None, description="Temperature (°C)")


# ═══════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/upload")
async def upload_raman_spectrum(
    file: UploadFile = File(...),
    sample_id: Optional[str] = None,
    laser_wavelength_nm: Optional[float] = None,
    laser_power_mW: Optional[float] = None,
    integration_time_s: Optional[float] = None,
    temperature_C: Optional[float] = None,
):
    """
    Upload and analyze Raman spectrum with default settings.
    
    **Supported File Formats:**
    - Tab-separated (.txt)
    - Comma-separated (.csv)
    - Space-separated text files
    
    **File Format:**
    - Two columns: Wavenumber (cm⁻¹) and Intensity
    - Header lines starting with '#' are ignored
    - Example:
      ```
      #Wave    #Intensity
      3000     27.9
      2999     16.8
      ...
      ```
    
    **Returns:**
    - Analyzed spectrum with baseline correction, peaks, and material identification
    """
    logger.info(f"Uploading Raman spectrum: {file.filename}")
    
    # Validate file type
    if not file.filename.endswith(('.txt', '.csv', '.TXT', '.CSV')):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload .txt or .csv file."
        )
    
    # Save uploaded file temporarily
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Import spectrum
        spectrum = import_raman_data(tmp_path)
        
        # Add metadata
        spectrum.sample_id = sample_id or ""
        spectrum.laser_wavelength_nm = laser_wavelength_nm
        spectrum.laser_power_mW = laser_power_mW
        spectrum.integration_time_s = integration_time_s
        spectrum.temperature_C = temperature_C
        spectrum.source_file = file.filename
        
        # Analyze with default settings
        config = RamanAnalysisConfig()
        analyzer = RamanAnalyzer(config)
        analyzed_spectrum = analyzer.analyze(spectrum)
        
        # Identify material
        material_matches = identify_material(analyzed_spectrum)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        # Return results
        result = analyzed_spectrum.to_dict()
        result["material_matches"] = material_matches
        result["analysis_config"] = {
            "baseline_method": config.baseline_method,
            "denoise_method": config.denoise_method,
            "peak_detection": config.peak_detection,
            "normalization": config.normalize,
        }
        
        logger.info(f"Analysis complete: {len(analyzed_spectrum.peaks)} peaks detected")
        return result
    
    except Exception as e:
        logger.error(f"Raman analysis failed: {e}")
        # Clean up temp file if it exists
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze")
async def analyze_raman_spectrum(
    file: UploadFile = File(...),
    config: RamanAnalysisRequest = None,
):
    """
    Upload and analyze Raman spectrum with custom configuration.
    
    **Advanced Analysis Options:**
    - Custom baseline correction methods (airPLS, AsLS, polynomial, morphological)
    - Adjustable denoising parameters
    - Peak detection sensitivity tuning
    - Peak fitting with Lorentzian or Gaussian models
    - Multiple normalization methods
    
    **Returns:**
    - Fully analyzed spectrum with all processing steps
    """
    logger.info(f"Analyzing Raman spectrum with custom config: {file.filename}")
    
    # Validate file type
    if not file.filename.endswith(('.txt', '.csv', '.TXT', '.CSV')):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload .txt or .csv file."
        )
    
    # Save uploaded file temporarily
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Import spectrum
        spectrum = import_raman_data(tmp_path)
        spectrum.source_file = file.filename
        
        # Create analysis config
        if config is None:
            analysis_config = RamanAnalysisConfig()
        else:
            analysis_config = RamanAnalysisConfig(
                baseline_method=config.baseline_method,
                baseline_lambda=config.baseline_lambda,
                baseline_p=config.baseline_p,
                polynomial_order=config.polynomial_order,
                denoise_method=config.denoise_method,
                savgol_window=config.savgol_window,
                savgol_polyorder=config.savgol_polyorder,
                peak_detection=config.peak_detection,
                peak_prominence=config.peak_prominence,
                peak_min_distance=config.peak_min_distance,
                peak_fitting=config.peak_fitting,
                peak_model=config.peak_model,
                normalize=config.normalize,
                normalization_method=config.normalization_method,
            )
        
        # Analyze
        analyzer = RamanAnalyzer(analysis_config)
        analyzed_spectrum = analyzer.analyze(spectrum)
        
        # Identify material
        material_matches = identify_material(analyzed_spectrum)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        # Return results
        result = analyzed_spectrum.to_dict()
        result["material_matches"] = material_matches
        result["analysis_config"] = {
            "baseline_method": analysis_config.baseline_method,
            "baseline_lambda": analysis_config.baseline_lambda,
            "denoise_method": analysis_config.denoise_method,
            "peak_detection": analysis_config.peak_detection,
            "peak_model": analysis_config.peak_model,
            "normalization_method": analysis_config.normalization_method,
        }
        
        logger.info(f"Custom analysis complete: {len(analyzed_spectrum.peaks)} peaks detected")
        return result
    
    except Exception as e:
        logger.error(f"Raman analysis failed: {e}")
        # Clean up temp file if it exists
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/materials")
async def get_material_database():
    """
    Get the Raman material identification database.
    
    **Returns:**
    - Dictionary of known materials with their characteristic Raman peaks
    - Useful for manual peak identification and method development
    """
    return {
        "materials": RAMAN_MATERIAL_DATABASE,
        "total_materials": len(RAMAN_MATERIAL_DATABASE),
        "description": "Raman-active materials database with characteristic peaks"
    }


@router.get("/methods")
async def get_analysis_methods():
    """
    Get available analysis methods and their descriptions.
    
    **Returns:**
    - Available baseline correction methods
    - Available denoising methods
    - Available peak models
    - Available normalization methods
    """
    return {
        "baseline_methods": {
            "airpls": {
                "name": "Adaptive iteratively reweighted penalized least squares",
                "description": "State-of-the-art baseline correction, handles complex baselines",
                "reference": "Zhao et al. (2007)",
                "recommended": True
            },
            "als": {
                "name": "Asymmetric least squares",
                "description": "Fast baseline correction with asymmetric weighting",
                "reference": "Eilers & Boelens (2005)",
                "recommended": True
            },
            "polynomial": {
                "name": "Polynomial fitting",
                "description": "Simple polynomial baseline, good for smooth baselines",
                "reference": "Classical method",
                "recommended": False
            },
            "morphological": {
                "name": "Morphological baseline (BubbleFill)",
                "description": "Morphological opening for baseline estimation",
                "reference": "Perez-Guaita et al. (2023)",
                "recommended": True
            }
        },
        "denoise_methods": {
            "savgol": {
                "name": "Savitzky-Golay filter",
                "description": "Polynomial smoothing filter, preserves peak shape",
                "recommended": True
            },
            "moving_average": {
                "name": "Moving average",
                "description": "Simple moving average filter",
                "recommended": False
            },
            "wavelet": {
                "name": "Wavelet denoising",
                "description": "Wavelet transform denoising (requires pywt)",
                "recommended": True
            },
            "none": {
                "name": "No denoising",
                "description": "Skip denoising step",
                "recommended": False
            }
        },
        "peak_models": {
            "lorentzian": {
                "name": "Lorentzian",
                "description": "Lorentzian peak shape (typical for Raman)",
                "recommended": True
            },
            "gaussian": {
                "name": "Gaussian",
                "description": "Gaussian peak shape",
                "recommended": False
            },
            "voigt": {
                "name": "Voigt",
                "description": "Voigt profile (convolution of Lorentzian and Gaussian)",
                "recommended": False,
                "status": "Not yet implemented"
            }
        },
        "normalization_methods": {
            "minmax": {
                "name": "Min-max normalization",
                "description": "Scale to [0, 1] range",
                "recommended": True
            },
            "area": {
                "name": "Area normalization",
                "description": "Normalize by total spectral area",
                "recommended": True
            },
            "vector": {
                "name": "Vector normalization",
                "description": "L2 norm normalization",
                "recommended": False
            },
            "snv": {
                "name": "Standard normal variate",
                "description": "Mean-center and scale by standard deviation",
                "recommended": True
            }
        }
    }


@router.get("/health")
async def raman_health_check():
    """
    Health check for Raman analysis engine.
    
    **Returns:**
    - Engine status and available features
    """
    return {
        "status": "healthy",
        "engine": "raman_spectroscopy",
        "version": "1.0.0",
        "features": {
            "baseline_correction": True,
            "denoising": True,
            "peak_detection": True,
            "peak_fitting": True,
            "material_identification": True,
            "supported_formats": [".txt", ".csv"]
        },
        "algorithms": {
            "baseline": ["airPLS", "AsLS", "polynomial", "morphological"],
            "denoising": ["Savitzky-Golay", "wavelet", "moving_average"],
            "peak_models": ["Lorentzian", "Gaussian"]
        }
    }
