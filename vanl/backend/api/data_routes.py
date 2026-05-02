"""
Data Analysis API Routes
=========================
REST API endpoints for importing and analyzing real electrochemical data.

Endpoints:
- POST /api/data/import - Import data from various potentiostat formats
- POST /api/data/fit-circuit - Fit equivalent circuit to EIS data
- POST /api/data/drt - Calculate Distribution of Relaxation Times
- GET /api/data/formats - List supported file formats
- POST /api/data/optimize-lambda - Find optimal DRT regularization parameter

Author: VidyuthLabs
Date: May 1, 2026
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
import logging
import tempfile
import os

from vanl.backend.core.data_import import (
    DataImporter,
    EISData,
    CVData
)
from vanl.backend.core.circuit_fitting import (
    CircuitFitter,
    FitResult
)
from vanl.backend.core.drt_analysis import (
    DRTAnalyzer,
    DRTResult
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/data", tags=["data-analysis"])

# Initialize modules (singletons)
_data_importer = None
_circuit_fitter = None
_drt_analyzer = None


def get_data_importer() -> DataImporter:
    """Get or create data importer instance."""
    global _data_importer
    if _data_importer is None:
        _data_importer = DataImporter()
        logger.info("Data importer initialized")
    return _data_importer


def get_circuit_fitter() -> CircuitFitter:
    """Get or create circuit fitter instance."""
    global _circuit_fitter
    if _circuit_fitter is None:
        _circuit_fitter = CircuitFitter()
        logger.info("Circuit fitter initialized")
    return _circuit_fitter


def get_drt_analyzer() -> DRTAnalyzer:
    """Get or create DRT analyzer instance."""
    global _drt_analyzer
    if _drt_analyzer is None:
        _drt_analyzer = DRTAnalyzer()
        logger.info("DRT analyzer initialized")
    return _drt_analyzer


# ===================================================================
#  Request/Response Models
# ===================================================================

class ImportResponse(BaseModel):
    """Response model for data import."""
    success: bool
    data_type: str  # "eis" or "cv"
    data: Dict[str, Any]
    message: str


class FitCircuitRequest(BaseModel):
    """Request model for circuit fitting."""
    frequencies: List[float] = Field(..., description="Frequency array (Hz)")
    Z_real: List[float] = Field(..., description="Real impedance (Ω)")
    Z_imag: List[float] = Field(..., description="Imaginary impedance (Ω)")
    circuit_model: str = Field("randles_cpe", description="Circuit model name")
    method: str = Field("lm", description="Optimization method (lm or de)")
    initial_guess: Optional[Dict[str, float]] = Field(None, description="Initial parameter guess")
    bounds: Optional[Dict[str, Tuple[float, float]]] = Field(None, description="Parameter bounds")


class FitCircuitResponse(BaseModel):
    """Response model for circuit fitting."""
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DRTRequest(BaseModel):
    """Request model for DRT calculation."""
    frequencies: List[float] = Field(..., description="Frequency array (Hz)")
    Z_real: List[float] = Field(..., description="Real impedance (Ω)")
    Z_imag: List[float] = Field(..., description="Imaginary impedance (Ω)")
    lambda_reg: float = Field(1e-3, description="Regularization parameter")
    tau_min: float = Field(1e-6, description="Minimum time constant (s)")
    tau_max: float = Field(1e3, description="Maximum time constant (s)")
    n_tau: int = Field(100, description="Number of time constant points")
    method: str = Field("tikhonov", description="Regularization method")


class DRTResponse(BaseModel):
    """Response model for DRT calculation."""
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class OptimizeLambdaRequest(BaseModel):
    """Request model for lambda optimization."""
    frequencies: List[float] = Field(..., description="Frequency array (Hz)")
    Z_real: List[float] = Field(..., description="Real impedance (Ω)")
    Z_imag: List[float] = Field(..., description="Imaginary impedance (Ω)")
    lambda_range: Tuple[float, float] = Field((1e-5, 1e-1), description="Lambda range")
    n_lambda: int = Field(20, description="Number of lambda values to test")


# ===================================================================
#  API Endpoints
# ===================================================================

@router.get("/formats")
async def get_supported_formats():
    """
    Get list of supported data formats.
    
    Returns information about all supported potentiostat formats
    and their file extensions.
    """
    formats = [
        {
            "name": "Gamry",
            "format_id": "gamry_dta",
            "extensions": [".DTA", ".dta"],
            "description": "Gamry Instruments data files",
            "supports": ["EIS", "CV"]
        },
        {
            "name": "Metrohm Autolab",
            "format_id": "autolab_txt",
            "extensions": [".txt", ".TXT"],
            "description": "Metrohm Autolab text files",
            "supports": ["EIS", "CV"]
        },
        {
            "name": "BioLogic",
            "format_id": "biologic_mpt",
            "extensions": [".mpt", ".MPT"],
            "description": "BioLogic EC-Lab data files",
            "supports": ["EIS", "CV"]
        },
        {
            "name": "Generic CSV",
            "format_id": "generic_csv",
            "extensions": [".csv", ".CSV"],
            "description": "Generic CSV files with freq, Z_real, Z_imag columns",
            "supports": ["EIS", "CV"]
        },
        {
            "name": "AnalyteX Native",
            "format_id": "analytex",
            "extensions": [".json"],
            "description": "AnalyteX native JSON format with metadata",
            "supports": ["EIS", "CV"]
        }
    ]
    
    return {
        "supported_formats": formats,
        "total_formats": len(formats),
        "auto_detection": True
    }


@router.post("/import", response_model=ImportResponse)
async def import_data(
    file: UploadFile = File(...),
    data_type: str = Form("eis"),
    format_type: str = Form("auto")
):
    """
    Import electrochemical data from file.
    
    **Supported Data Types:**
    - `eis`: Electrochemical Impedance Spectroscopy
    - `cv`: Cyclic Voltammetry
    
    **Supported Formats:**
    - `auto`: Auto-detect format (recommended)
    - `gamry_dta`: Gamry Instruments (.DTA)
    - `autolab_txt`: Metrohm Autolab (.txt)
    - `biologic_mpt`: BioLogic (.mpt)
    - `generic_csv`: Generic CSV
    - `analytex`: AnalyteX native JSON
    
    **Example Usage:**
    ```bash
    curl -X POST "http://localhost:8001/api/data/import" \\
         -F "file=@my_eis_data.DTA" \\
         -F "data_type=eis" \\
         -F "format_type=auto"
    ```
    """
    try:
        importer = get_data_importer()
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            # Import data based on type
            if data_type.lower() == "eis":
                data = importer.import_eis_data(tmp_path, format_type)
                data_dict = data.to_dict()
            elif data_type.lower() == "cv":
                data = importer.import_cv_data(tmp_path, format_type)
                data_dict = data.to_dict()
            else:
                raise ValueError(f"Unknown data type: {data_type}")
            
            return ImportResponse(
                success=True,
                data_type=data_type.lower(),
                data=data_dict,
                message=f"Successfully imported {data_type.upper()} data from {file.filename}"
            )
        
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except Exception as e:
        logger.error(f"Data import failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fit-circuit", response_model=FitCircuitResponse)
async def fit_circuit(request: FitCircuitRequest):
    """
    Fit equivalent circuit model to EIS data.
    
    **Supported Circuit Models:**
    - `randles`: Randles circuit (Rs + (Cdl || (Rct + W)))
    - `randles_cpe`: Modified Randles with CPE (Rs + (CPE || (Rct + W)))
    - `rc`: Simple RC circuit
    - `r_cpe`: R-CPE circuit
    
    **Optimization Methods:**
    - `lm`: Levenberg-Marquardt (fast, local optimization)
    - `de`: Differential Evolution (slower, global optimization)
    
    **Example Request:**
    ```json
    {
        "frequencies": [0.01, 0.1, 1, 10, 100, 1000],
        "Z_real": [110, 105, 95, 50, 20, 12],
        "Z_imag": [-5, -15, -30, -25, -10, -2],
        "circuit_model": "randles_cpe",
        "method": "lm"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "success": true,
        "result": {
            "parameters": {
                "Rs": 10.5,
                "Rct": 95.3,
                "Q": 1.2e-5,
                "n": 0.89,
                "sigma_w": 45.2
            },
            "parameter_errors": {...},
            "chi_squared": 0.0234,
            "reduced_chi_squared": 0.0039,
            "success": true
        }
    }
    ```
    """
    try:
        import numpy as np
        
        fitter = get_circuit_fitter()
        
        # Convert lists to numpy arrays
        frequencies = np.array(request.frequencies)
        Z_real = np.array(request.Z_real)
        Z_imag = np.array(request.Z_imag)
        
        # Fit circuit
        result = fitter.fit_circuit(
            frequencies=frequencies,
            Z_real=Z_real,
            Z_imag=Z_imag,
            circuit_model=request.circuit_model,
            initial_guess=request.initial_guess,
            bounds=request.bounds,
            method=request.method
        )
        
        return FitCircuitResponse(
            success=True,
            result=result.to_dict()
        )
    
    except Exception as e:
        logger.error(f"Circuit fitting failed: {e}")
        return FitCircuitResponse(
            success=False,
            error=str(e)
        )


@router.post("/drt", response_model=DRTResponse)
async def calculate_drt(request: DRTRequest):
    """
    Calculate Distribution of Relaxation Times (DRT) from EIS data.
    
    DRT analysis reveals hidden electrochemical processes by deconvolving
    the impedance spectrum into a distribution of time constants.
    
    **Regularization Methods:**
    - `tikhonov`: Tikhonov regularization (2nd derivative penalty)
    - `ridge`: Ridge regression (L2 penalty)
    
    **Example Request:**
    ```json
    {
        "frequencies": [0.01, 0.1, 1, 10, 100, 1000],
        "Z_real": [110, 105, 95, 50, 20, 12],
        "Z_imag": [-5, -15, -30, -25, -10, -2],
        "lambda_reg": 0.001,
        "method": "tikhonov"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "success": true,
        "result": {
            "tau": [1e-6, 1e-5, ..., 1e3],
            "gamma": [0.1, 2.5, ..., 0.05],
            "peaks": [
                {
                    "tau": 0.001,
                    "gamma": 15.3,
                    "frequency_Hz": 159.2,
                    "process": "charge_transfer"
                }
            ],
            "chi_squared": 0.0123,
            "n_peaks": 2
        }
    }
    ```
    """
    try:
        import numpy as np
        
        analyzer = get_drt_analyzer()
        
        # Convert lists to numpy arrays
        frequencies = np.array(request.frequencies)
        Z_real = np.array(request.Z_real)
        Z_imag = np.array(request.Z_imag)
        
        # Calculate DRT
        result = analyzer.calculate_drt(
            frequencies=frequencies,
            Z_real=Z_real,
            Z_imag=Z_imag,
            lambda_reg=request.lambda_reg,
            tau_min=request.tau_min,
            tau_max=request.tau_max,
            n_tau=request.n_tau,
            method=request.method
        )
        
        return DRTResponse(
            success=True,
            result=result.to_dict()
        )
    
    except Exception as e:
        logger.error(f"DRT calculation failed: {e}")
        return DRTResponse(
            success=False,
            error=str(e)
        )


@router.post("/optimize-lambda")
async def optimize_lambda(request: OptimizeLambdaRequest):
    """
    Find optimal regularization parameter for DRT using L-curve method.
    
    The L-curve method plots residual norm vs solution norm for different
    lambda values. The optimal lambda is at the corner of the L-curve,
    balancing data fit and solution smoothness.
    
    **Example Request:**
    ```json
    {
        "frequencies": [0.01, 0.1, 1, 10, 100, 1000],
        "Z_real": [110, 105, 95, 50, 20, 12],
        "Z_imag": [-5, -15, -30, -25, -10, -2],
        "lambda_range": [1e-5, 1e-1],
        "n_lambda": 20
    }
    ```
    
    **Example Response:**
    ```json
    {
        "success": true,
        "optimal_lambda": 0.00234,
        "residual_norms": [10.5, 8.3, ..., 0.5],
        "solution_norms": [150.2, 120.5, ..., 5.3],
        "lambda_values": [1e-5, ..., 1e-1]
    }
    ```
    """
    try:
        import numpy as np
        
        analyzer = get_drt_analyzer()
        
        # Convert lists to numpy arrays
        frequencies = np.array(request.frequencies)
        Z_real = np.array(request.Z_real)
        Z_imag = np.array(request.Z_imag)
        
        # Optimize lambda
        optimal_lambda, residual_norms, solution_norms = analyzer.optimize_lambda(
            frequencies=frequencies,
            Z_real=Z_real,
            Z_imag=Z_imag,
            lambda_range=request.lambda_range,
            n_lambda=request.n_lambda
        )
        
        # Generate lambda values for plotting
        lambda_values = np.logspace(
            np.log10(request.lambda_range[0]),
            np.log10(request.lambda_range[1]),
            request.n_lambda
        )
        
        return {
            "success": True,
            "optimal_lambda": float(optimal_lambda),
            "residual_norms": residual_norms,
            "solution_norms": solution_norms,
            "lambda_values": lambda_values.tolist(),
            "message": f"Optimal λ = {optimal_lambda:.2e}"
        }
    
    except Exception as e:
        logger.error(f"Lambda optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/examples")
async def get_examples():
    """
    Get example data for testing data analysis endpoints.
    
    Returns synthetic EIS data that can be used to test circuit fitting
    and DRT analysis.
    """
    import numpy as np
    
    # Generate synthetic EIS data (Randles circuit)
    frequencies = np.logspace(-2, 5, 50)
    omega = 2 * np.pi * frequencies
    
    # Parameters
    Rs = 10.0
    Rct = 100.0
    Cdl = 1e-5
    sigma_w = 50.0
    
    # Calculate impedance
    Z_w = sigma_w * (1 - 1j) / np.sqrt(omega)
    Z_c = 1 / (1j * omega * Cdl)
    Z_parallel = 1 / (1/Z_c + 1/(Rct + Z_w))
    Z = Rs + Z_parallel
    
    Z_real = np.real(Z)
    Z_imag = np.imag(Z)
    
    # Add small noise
    noise_level = 0.01
    Z_real += np.random.randn(len(Z_real)) * noise_level * np.mean(np.abs(Z_real))
    Z_imag += np.random.randn(len(Z_imag)) * noise_level * np.mean(np.abs(Z_imag))
    
    return {
        "description": "Synthetic EIS data from Randles circuit",
        "true_parameters": {
            "Rs": Rs,
            "Rct": Rct,
            "Cdl": Cdl,
            "sigma_w": sigma_w
        },
        "data": {
            "frequencies": frequencies.tolist(),
            "Z_real": Z_real.tolist(),
            "Z_imag": Z_imag.tolist()
        },
        "usage": {
            "fit_circuit": "POST /api/data/fit-circuit with this data",
            "drt": "POST /api/data/drt with this data"
        }
    }


# ===================================================================
#  Health Check
# ===================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for data analysis module."""
    try:
        importer = get_data_importer()
        fitter = get_circuit_fitter()
        analyzer = get_drt_analyzer()
        
        return {
            "status": "healthy",
            "modules": {
                "data_importer": "operational",
                "circuit_fitter": "operational",
                "drt_analyzer": "operational"
            },
            "supported_formats": len(importer.supported_formats),
            "supported_circuits": len(fitter.circuit_models)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
