"""
Advanced Analysis API Routes

FastAPI endpoints for the Advanced Analysis panel.
Provides statistical analysis, curve fitting, signal processing, and peak analysis.

Routes:
- POST /api/v2/analysis/statistics - Statistical analysis
- POST /api/v2/analysis/curve-fit - Curve fitting
- POST /api/v2/analysis/signal-process - Signal processing (planned)
- POST /api/v2/analysis/peak-detect - Peak detection (planned)
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/analysis", tags=["analysis"])


# ═══════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════

class StatisticsRequest(BaseModel):
    """Request for statistical analysis"""
    data: List[float] = Field(..., description="Data array to analyze")
    analysis_type: str = Field("descriptive", description="Type of analysis: descriptive, normality, ttest, anova, correlation, regression")
    # For t-test
    group2: Optional[List[float]] = Field(None, description="Second group for two-sample t-test")
    mu: float = Field(0.0, description="Population mean for one-sample t-test")
    alternative: str = Field("two-sided", description="Alternative hypothesis: two-sided, less, greater")
    # For ANOVA
    groups: Optional[List[List[float]]] = Field(None, description="Multiple groups for ANOVA")
    # For correlation/regression
    x: Optional[List[float]] = Field(None, description="Independent variable for correlation/regression")
    y: Optional[List[float]] = Field(None, description="Dependent variable for correlation/regression")
    method: str = Field("pearson", description="Correlation method: pearson, spearman, kendall")


class CurveFitRequest(BaseModel):
    """Request for curve fitting"""
    x: List[float] = Field(..., description="Independent variable")
    y: List[float] = Field(..., description="Dependent variable")
    function: str = Field("gaussian", description="Fitting function name")
    initial_params: Optional[Dict[str, float]] = Field(None, description="Initial parameter guesses")
    bounds: Optional[Dict[str, tuple]] = Field(None, description="Parameter bounds")
    method: str = Field("lm", description="Fitting method: lm (Levenberg-Marquardt) or trf (Trust Region)")


# ═══════════════════════════════════════════════════════════════════════
# STATISTICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@router.post("/statistics")
async def analyze_statistics(req: StatisticsRequest):
    """
    Perform statistical analysis on data.
    
    Supports:
    - Descriptive statistics (mean, std, quartiles, etc.)
    - Normality tests (Shapiro-Wilk, Kolmogorov-Smirnov, etc.)
    - T-tests (one-sample, two-sample, paired)
    - ANOVA (one-way)
    - Correlation analysis (Pearson, Spearman, Kendall)
    - Linear regression
    """
    try:
        from src.backend.core.analysis.statistics import (
            descriptive_statistics,
            normality_test,
            t_test,
            anova_one_way,
            correlation_analysis,
            linear_regression,
        )
        
        if req.analysis_type == "descriptive":
            result = descriptive_statistics(req.data)
            return result.to_dict()
        
        elif req.analysis_type == "normality":
            result = normality_test(req.data)
            return result
        
        elif req.analysis_type == "ttest":
            result = t_test(
                group1=req.data,
                group2=req.group2,
                mu=req.mu,
                alternative=req.alternative,
            )
            return result
        
        elif req.analysis_type == "anova":
            if not req.groups:
                raise HTTPException(400, "ANOVA requires 'groups' parameter")
            result = anova_one_way(*req.groups)
            return result
        
        elif req.analysis_type == "correlation":
            if not req.x or not req.y:
                raise HTTPException(400, "Correlation requires 'x' and 'y' parameters")
            result = correlation_analysis(
                x=req.x,
                y=req.y,
                method=req.method,
            )
            return result
        
        elif req.analysis_type == "regression":
            if not req.x or not req.y:
                raise HTTPException(400, "Regression requires 'x' and 'y' parameters")
            result = linear_regression(x=req.x, y=req.y)
            return result
        
        else:
            raise HTTPException(400, f"Unknown analysis type: {req.analysis_type}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Statistics analysis failed: {e}", exc_info=True)
        raise HTTPException(500, f"Analysis failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════
# CURVE FITTING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@router.post("/curve-fit")
async def fit_curve_endpoint(req: CurveFitRequest):
    """
    Fit a curve to data using nonlinear least squares.
    
    Supports 100+ fitting functions including:
    - Polynomial (1-10 degree)
    - Exponential (single, double, stretched)
    - Peak functions (Gaussian, Lorentzian, Voigt, Pseudo-Voigt)
    - Sigmoid (Logistic, Gompertz, Richards)
    - Power law, logarithmic
    - Trigonometric (sine, damped sine)
    - Spectroscopy functions
    """
    try:
        from src.backend.core.analysis.curve_fitting import fit_curve
        
        result = fit_curve(
            x=req.x,
            y=req.y,
            function=req.function,
            initial_params=req.initial_params,
            bounds=req.bounds,
            method=req.method,
        )
        
        return result.to_dict()
    
    except Exception as e:
        logger.error(f"Curve fitting failed: {e}", exc_info=True)
        raise HTTPException(500, f"Curve fitting failed: {str(e)}")


@router.get("/curve-fit/functions")
async def list_fitting_functions():
    """
    List all available fitting functions with descriptions.
    """
    try:
        from src.backend.core.analysis.curve_fitting import FITTING_FUNCTIONS
        
        functions = []
        for name, info in FITTING_FUNCTIONS.items():
            functions.append({
                'name': name,
                'description': info['description'],
                'parameters': info['params'],
            })
        
        return {
            'functions': functions,
            'count': len(functions),
        }
    
    except Exception as e:
        logger.error(f"Failed to list fitting functions: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to list functions: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════
# SIGNAL PROCESSING ENDPOINTS (Placeholder)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/signal-process")
async def process_signal(data: Dict[str, Any]):
    """
    Signal processing tools (FFT, wavelet, filtering, convolution).
    
    Coming soon!
    """
    raise HTTPException(501, "Signal processing not yet implemented")


# ═══════════════════════════════════════════════════════════════════════
# PEAK ANALYSIS ENDPOINTS (Placeholder)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/peak-detect")
async def detect_peaks(data: Dict[str, Any]):
    """
    Peak detection, fitting, and integration.
    
    Coming soon!
    """
    raise HTTPException(501, "Peak analysis not yet implemented")
