"""
Autonomous Optimization API Routes
===================================
REST API and WebSocket endpoints for Bayesian optimization campaigns.

Features:
- Start/stop optimization campaigns
- Real-time progress updates via WebSocket
- Campaign history and results
- Multi-objective optimization support
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.backend.ml.autonomous_optimizer import get_autonomous_optimizer, CampaignStatus
from src.backend.ml.material_identifier import get_material_identifier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional PyBOP backend for battery parameter optimization
# ---------------------------------------------------------------------------
try:
    import pybop
    HAS_PYBOP = True
    logger.debug("PyBOP is available – battery parameter estimation enabled")
except ImportError:
    HAS_PYBOP = False
    logger.debug("PyBOP not found – battery parameter estimation disabled")

router = APIRouter(prefix="/api/v2/optimize", tags=["optimization"])

# WebSocket connections for real-time updates
active_websockets: Dict[str, List[WebSocket]] = {}


# ── Request Models ──────────────────────────────────────────────

class StartCampaignRequest(BaseModel):
    target_metric: str = Field(..., description="Metric to optimize (e.g., 'capacitance')")
    objective: str = Field("maximize", description="'maximize' or 'minimize'")
    max_iterations: int = Field(50, ge=1, le=500)
    convergence_threshold: float = Field(0.01, ge=0, le=1)
    simulation_type: str = Field("eis", description="'eis', 'cv', or 'gcd'")
    parameter_space: Optional[Dict[str, Any]] = Field(None, description="Custom parameter ranges")


class StopCampaignRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Reason for stopping")


class BatteryOptimizationRequest(BaseModel):
    experimental_data: Dict[str, List[float]] = Field(..., description="Dict with keys time_s, voltage_V, current_A")
    chemistry: str = Field("NMC", description="Battery chemistry (e.g. 'NMC', 'LFP')")
    parameters_to_estimate: List[str] = Field(..., description="List of PyBaMM parameter names to estimate (e.g. 'Negative electrode active material volume fraction')")


# ── Status & Info ───────────────────────────────────────────────

@router.get("/status")
async def get_optimizer_status():
    """
    Get autonomous optimizer status.
    
    Returns:
        - Number of active campaigns
        - Number of completed campaigns
        - CAMD availability
        - System capabilities
    """
    optimizer = get_autonomous_optimizer()
    
    campaigns = optimizer.list_campaigns()
    active = [c for c in campaigns if c["status"] == "running"]
    completed = [c for c in campaigns if c["status"] in ["converged", "stopped"]]
    
    return {
        "active_campaigns": len(active),
        "completed_campaigns": len(completed),
        "total_campaigns": len(campaigns),
        "camd_available": optimizer.camd.is_available(),
        "capabilities": {
            "bayesian_optimization": True,
            "multi_objective": False,  # Future feature
            "parallel_execution": False,  # Future feature
            "real_time_updates": True,
        },
    }


@router.get("/campaigns")
async def list_campaigns():
    """
    List all optimization campaigns.
    
    Returns:
        List of campaigns with status, metrics, and results
    """
    optimizer = get_autonomous_optimizer()
    campaigns = optimizer.list_campaigns()
    
    return {
        "campaigns": campaigns,
        "total": len(campaigns),
    }


# ── Campaign Management ─────────────────────────────────────────

@router.post("/start")
async def start_campaign(req: StartCampaignRequest):
    """
    Start a new optimization campaign.
    
    Launches a Bayesian optimization loop that:
    1. Suggests next candidate material
    2. Simulates using VANL engines
    3. Updates surrogate model
    4. Checks convergence
    5. Repeats until converged or max iterations
    
    Returns:
        Campaign ID for tracking progress
    """
    optimizer = get_autonomous_optimizer()
    identifier = get_material_identifier()
    
    # Check if materials database is loaded
    if len(identifier.materials_db) == 0:
        raise HTTPException(
            status_code=400,
            detail="Materials database not loaded. Load database first."
        )
    
    # Define objective function based on simulation type
    if req.simulation_type == "eis":
        objective_fn = _create_eis_objective(req.target_metric)
    elif req.simulation_type == "cv":
        objective_fn = _create_cv_objective(req.target_metric)
    elif req.simulation_type == "gcd":
        objective_fn = _create_gcd_objective(req.target_metric)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown simulation type: {req.simulation_type}"
        )
    
    # Start campaign
    try:
        campaign_id = optimizer.start_campaign(
            objective_fn=objective_fn,
            candidate_space=identifier.materials_db,
            target_metric=req.target_metric,
            objective=req.objective,
            max_iterations=req.max_iterations,
            convergence_threshold=req.convergence_threshold,
        )
        
        return {
            "campaign_id": campaign_id,
            "status": "started",
            "message": f"Optimization campaign {campaign_id} started",
        }
        
    except Exception as e:
        logger.error(f"Failed to start campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/status")
async def get_campaign_status(campaign_id: str):
    """
    Get current status of a campaign.
    
    Returns:
        - Current iteration
        - Best score so far
        - Progress percentage
        - Recent iterations
    """
    optimizer = get_autonomous_optimizer()
    
    try:
        status = optimizer.get_campaign_status(campaign_id)
        return status
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{campaign_id}/stop")
async def stop_campaign(campaign_id: str, req: StopCampaignRequest):
    """
    Stop a running campaign.
    
    The campaign will finish the current iteration and then stop.
    Results up to that point will be saved.
    """
    optimizer = get_autonomous_optimizer()
    
    try:
        optimizer.stop_campaign(campaign_id)
        
        # Notify WebSocket clients
        await _broadcast_campaign_update(campaign_id, {
            "event": "campaign_stopped",
            "reason": req.reason or "User requested stop",
        })
        
        return {
            "campaign_id": campaign_id,
            "status": "stopped",
            "message": "Campaign stopped successfully",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{campaign_id}/results")
async def get_campaign_results(campaign_id: str):
    """
    Get final results of a campaign.
    
    Returns:
        - Best candidate material
        - Best score achieved
        - Full iteration history
        - Convergence statistics
    """
    optimizer = get_autonomous_optimizer()
    
    try:
        results = optimizer.get_campaign_results(campaign_id)
        return results
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── WebSocket for Real-Time Updates ────────────────────────────

@router.websocket("/{campaign_id}/ws")
async def campaign_websocket(websocket: WebSocket, campaign_id: str):
    """
    WebSocket endpoint for real-time campaign updates.
    
    Sends updates on:
    - New iteration completed
    - Best score updated
    - Campaign status changed
    - Convergence detected
    
    Usage:
        ws = new WebSocket('ws://localhost:8000/api/v2/optimize/{campaign_id}/ws')
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            console.log('Iteration:', data.iteration, 'Score:', data.score)
        }
    """
    await websocket.accept()
    
    # Register WebSocket
    if campaign_id not in active_websockets:
        active_websockets[campaign_id] = []
    active_websockets[campaign_id].append(websocket)
    
    logger.info(f"WebSocket connected for campaign {campaign_id}")
    
    try:
        # Send initial status
        optimizer = get_autonomous_optimizer()
        try:
            status = optimizer.get_campaign_status(campaign_id)
            await websocket.send_json({
                "event": "connected",
                "campaign_id": campaign_id,
                "status": status,
            })
        except ValueError:
            await websocket.send_json({
                "event": "error",
                "message": f"Campaign {campaign_id} not found",
            })
            await websocket.close()
            return
        
        # Keep connection alive and send periodic updates
        while True:
            try:
                # Wait for message from client (ping/pong)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                
                # Send current status
                status = optimizer.get_campaign_status(campaign_id)
                await websocket.send_json({
                    "event": "status_update",
                    "status": status,
                })
                
            except asyncio.TimeoutError:
                # Send periodic heartbeat
                await websocket.send_json({"event": "heartbeat"})
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for campaign {campaign_id}")
    finally:
        # Unregister WebSocket
        if campaign_id in active_websockets:
            active_websockets[campaign_id].remove(websocket)
            if len(active_websockets[campaign_id]) == 0:
                del active_websockets[campaign_id]


async def _broadcast_campaign_update(campaign_id: str, data: Dict[str, Any]):
    """Broadcast update to all WebSocket clients for a campaign."""
    if campaign_id not in active_websockets:
        return
    
    dead_sockets = []
    for ws in active_websockets[campaign_id]:
        try:
            await ws.send_json(data)
        except Exception:
            dead_sockets.append(ws)
    
    # Remove dead sockets
    for ws in dead_sockets:
        active_websockets[campaign_id].remove(ws)


# ── Objective Function Factories ────────────────────────────────

def _create_eis_objective(target_metric: str):
    """Create objective function for EIS optimization."""
    from src.backend.core.native_bridge import eis_simulate
    
    def objective(material: Dict[str, Any]) -> float:
        """Simulate EIS and extract target metric."""
        # Get material parameters
        Rs = material.get("features", {}).get("Rs", 10.0)
        Rct = material.get("features", {}).get("Rct", 100.0)
        Cdl = material.get("features", {}).get("Cdl", 1e-5)
        
        # Simulate
        result = eis_simulate(
            Rs=Rs,
            Rct=Rct,
            Cdl=Cdl,
            sigma_w=50.0,
            n_cpe=0.9,
            f_min=0.01,
            f_max=1e6,
            n_points=50,
        )
        
        # Extract metric
        if target_metric == "capacitance":
            # Estimate capacitance from impedance
            Z_imag = result["Z_imag"]
            freq = result["frequencies"]
            omega = 2 * 3.14159 * freq[len(freq)//2]
            C = -1 / (omega * Z_imag[len(Z_imag)//2])
            return abs(C) * 1e6  # Convert to µF
        
        elif target_metric == "conductivity":
            # Lower Rs = higher conductivity
            return 1.0 / Rs
        
        else:
            # Default: use stored property
            return material.get("properties", {}).get(target_metric, 0.0)
    
    return objective


def _create_cv_objective(target_metric: str):
    """Create objective function for CV optimization."""
    from src.backend.core.native_bridge import cv_simulate
    
    def objective(material: Dict[str, Any]) -> float:
        """Simulate CV and extract target metric."""
        # Simulate
        result = cv_simulate(
            area_cm2=0.0707,
            E_formal_V=0.23,
            n_electrons=1,
            C_ox_M=5e-3,
            D_ox_cm2s=7.6e-6,
            k0_cm_s=0.01,
            alpha=0.5,
            E_start_V=-0.3,
            E_vertex_V=0.8,
            scan_rate_V_s=0.05,
            n_points=1000,
        )
        
        # Extract metric
        if target_metric == "peak_current":
            i_total = result["i_total"]
            return max(abs(i_total))
        
        else:
            return material.get("properties", {}).get(target_metric, 0.0)
    
    return objective


def _create_gcd_objective(target_metric: str):
    """Create objective function for GCD optimization."""
    from src.backend.core.engines.gcd_engine import GCDParameters, simulate_gcd
    
    def objective(material: Dict[str, Any]) -> float:
        """Simulate GCD and extract target metric."""
        # Get material parameters
        Cdl = material.get("features", {}).get("Cdl", 1e-3)
        Rs = material.get("features", {}).get("Rs", 5.0)
        Rct = material.get("features", {}).get("Rct", 50.0)
        
        # Simulate
        params = GCDParameters(
            Cdl_F=Cdl,
            C_pseudo_F=0,
            Rs_ohm=Rs,
            Rct_ohm=Rct,
            current_A=1e-3,
            V_min=0,
            V_max=1.0,
            n_cycles=3,
            active_mass_mg=1.0,
        )
        
        result = simulate_gcd(params)
        result_dict = result.to_dict()
        
        # Extract metric
        if target_metric == "capacitance":
            return result_dict["summary"]["specific_capacitance_F_g"]
        
        elif target_metric == "energy_density":
            return result_dict["summary"]["energy_density_Wh_kg"]
        
        elif target_metric == "power_density":
            return result_dict["summary"]["power_density_W_kg"]
        
        else:
            return material.get("properties", {}).get(target_metric, 0.0)
    
    return objective


# ── Suggestion Engine ───────────────────────────────────────────

@router.post("/suggest")
async def suggest_next_experiment(
    history: List[Dict[str, Any]],
    candidate_space: List[Dict[str, Any]],
):
    """
    Suggest next experiment based on history (active learning).
    
    Uses acquisition functions to select the most informative
    next experiment from the candidate space.
    
    Args:
        history: List of previous experiments with results
        candidate_space: Available candidates
        
    Returns:
        Suggested candidate with acquisition score
    """
    optimizer = get_autonomous_optimizer()
    
    if not optimizer.camd.is_available():
        raise HTTPException(
            status_code=503,
            detail="CAMD not available - cannot suggest experiments"
        )
    
    # Use CAMD to suggest next experiment
    suggestion = optimizer.camd.suggest_next_experiment(history, candidate_space)
    
    if suggestion is None:
        raise HTTPException(
            status_code=400,
            detail="No more candidates to explore"
        )
    
    return {
        "suggested_candidate": suggestion,
        "acquisition_score": 0.85,  # Placeholder
        "reason": "High uncertainty region with potential for improvement",
    }


# ── Battery Parameter Estimation ────────────────────────────────

@router.post("/battery")
async def optimize_battery_parameters(req: BatteryOptimizationRequest):
    """
    Estimate battery parameters from experimental data using PyBOP.
    """
    if not HAS_PYBOP:
        raise HTTPException(
            status_code=503,
            detail="PyBOP is not installed. Battery parameter estimation is unavailable."
        )

    try:
        # Prepare experimental data for PyBOP
        # PyBOP expects a Dataset object
        time_data = req.experimental_data.get("time_s")
        voltage_data = req.experimental_data.get("voltage_V")
        current_data = req.experimental_data.get("current_A")

        if not time_data or not voltage_data or not current_data:
            raise ValueError("experimental_data must contain time_s, voltage_V, and current_A arrays.")

        dataset = pybop.Dataset({
            "Time [s]": time_data,
            "Current function [A]": current_data,
            "Terminal voltage [V]": voltage_data
        })

        # Define model based on chemistry
        if req.chemistry.upper() == "LFP":
            model = pybop.lithium_ion.SPM(parameter_set=pybop.ParameterSet("Prada2013"))
        elif req.chemistry.upper() == "LICOO2":
            model = pybop.lithium_ion.SPM(parameter_set=pybop.ParameterSet("Marquis2019"))
        else:
            model = pybop.lithium_ion.SPM(parameter_set=pybop.ParameterSet("Chen2020"))

        # Define parameters to estimate
        parameters = pybop.Parameters()
        
        # We need realistic bounds, so we apply a +/- 50% bound to the default parameter value
        for param_name in req.parameters_to_estimate:
            default_value = model.parameter_set[param_name]
            parameters.declare(
                pybop.Parameter(
                    param_name,
                    prior=pybop.Uniform(default_value * 0.5, default_value * 1.5),
                    bounds=[default_value * 0.5, default_value * 1.5],
                )
            )

        # Set up optimization problem
        problem = pybop.FittingProblem(
            model,
            parameters,
            dataset,
            signal=["Terminal voltage [V]"],
        )

        # Choose optimiser
        optimiser = pybop.CMAES(problem)
        optimiser.set_max_iterations(100)

        # Run optimisation
        results = optimiser.run()

        # Format output
        estimated_params = {}
        for idx, param in enumerate(parameters):
            estimated_params[param.name] = float(results.x[idx])

        return {
            "status": "success",
            "estimated_parameters": estimated_params,
            "cost": float(results.fval),
            "message": "Optimization completed successfully"
        }

    except Exception as e:
        logger.error(f"Battery optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

