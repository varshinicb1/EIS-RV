"""
MADSci Experiment Management API Routes
=======================================
REST API endpoints for experiment campaign management.

Endpoints:
- Campaign management
- Experiment execution
- Resource tracking
- Closed-loop autonomy

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from src.backend.experiments.experiment_manager import (
    get_experiment_manager,
    CampaignStatus,
    ExperimentStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/experiments", tags=["experiments"])


# ── Request/Response Models ─────────────────────────────────────

class CreateCampaignRequest(BaseModel):
    name: str = Field(..., description="Campaign name")
    description: str = Field(..., description="Campaign description")
    objective: str = Field(..., description="maximize, minimize, or target")
    target_metric: str = Field(..., description="Metric to optimize")
    target_value: Optional[float] = Field(None, description="Target value (for target objective)")
    max_experiments: int = Field(100, ge=1, le=1000, description="Maximum experiments")
    max_duration_hours: float = Field(168.0, ge=1.0, le=720.0, description="Maximum duration")
    stopping_criteria: Optional[List[str]] = Field(None, description="Stopping criteria")


class AddExperimentRequest(BaseModel):
    campaign_id: str = Field(..., description="Campaign ID")
    name: str = Field(..., description="Experiment name")
    parameters: Dict[str, Any] = Field(..., description="Experiment parameters")
    workflow_id: Optional[str] = Field(None, description="Workflow ID to execute")


class ExecuteExperimentRequest(BaseModel):
    campaign_id: str = Field(..., description="Campaign ID")
    experiment_id: str = Field(..., description="Experiment ID")


class ClosedLoopRequest(BaseModel):
    campaign_id: str = Field(..., description="Campaign ID")
    max_iterations: int = Field(10, ge=1, le=100, description="Maximum iterations")


class AddResourceRequest(BaseModel):
    resource_type: str = Field(..., description="Resource type (material, equipment, reagent)")
    name: str = Field(..., description="Resource name")
    quantity: float = Field(..., ge=0, description="Quantity")
    unit: str = Field(..., description="Unit (g, mL, unit, etc.)")
    cost_per_unit: float = Field(0.0, ge=0, description="Cost per unit")


class ConsumeResourceRequest(BaseModel):
    resource_id: str = Field(..., description="Resource ID")
    quantity: float = Field(..., gt=0, description="Quantity to consume")


# ── Status Endpoint ─────────────────────────────────────────────

@router.get("/status")
async def get_status():
    """
    Get experiment manager status.
    
    Returns:
        Status information including campaigns and resources
    """
    manager = get_experiment_manager()
    
    campaigns = manager.list_campaigns()
    resources = manager.list_resources()
    
    return {
        "n_campaigns": len(campaigns),
        "n_running": sum(1 for c in campaigns if c.status == CampaignStatus.RUNNING),
        "n_completed": sum(1 for c in campaigns if c.status == CampaignStatus.COMPLETED),
        "n_resources": len(resources),
        "n_materials": sum(1 for r in resources if r.resource_type == "material"),
        "n_equipment": sum(1 for r in resources if r.resource_type == "equipment"),
    }


# ── Campaign Management ─────────────────────────────────────────

@router.post("/campaigns/create")
async def create_campaign(req: CreateCampaignRequest):
    """
    Create a new experiment campaign.
    
    A campaign is a series of experiments designed to achieve
    a specific objective (e.g., maximize capacitance).
    
    Returns:
        Created campaign details
    """
    manager = get_experiment_manager()
    
    try:
        campaign = manager.create_campaign(
            name=req.name,
            description=req.description,
            objective=req.objective,
            target_metric=req.target_metric,
            target_value=req.target_value,
            max_experiments=req.max_experiments,
            max_duration_hours=req.max_duration_hours,
            stopping_criteria=req.stopping_criteria,
        )
        
        return {
            "status": "success",
            "campaign": campaign.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"Campaign creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/list")
async def list_campaigns(status: Optional[str] = None):
    """
    List all campaigns.
    
    Optionally filter by status (planned, running, completed, etc.).
    
    Returns:
        List of campaigns
    """
    manager = get_experiment_manager()
    
    try:
        campaigns = manager.list_campaigns(status=status)
        
        return {
            "status": "success",
            "n_campaigns": len(campaigns),
            "campaigns": [c.to_dict() for c in campaigns],
        }
        
    except Exception as e:
        logger.error(f"Campaign listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """
    Get campaign details.
    
    Returns:
        Campaign details including all experiments
    """
    manager = get_experiment_manager()
    
    campaign = manager.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {
        "status": "success",
        "campaign": campaign.to_dict(),
        "experiments": [e.to_dict() for e in campaign.experiments],
    }


@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str):
    """
    Start a campaign.
    
    Changes status from planned to running.
    
    Returns:
        Updated campaign
    """
    manager = get_experiment_manager()
    
    try:
        campaign = manager.start_campaign(campaign_id)
        
        return {
            "status": "success",
            "campaign": campaign.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"Campaign start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/{campaign_id}/stop")
async def stop_campaign(campaign_id: str, reason: str = "manual"):
    """
    Stop a campaign.
    
    Changes status from running to completed.
    
    Returns:
        Updated campaign
    """
    manager = get_experiment_manager()
    
    try:
        campaign = manager.stop_campaign(campaign_id, reason=reason)
        
        return {
            "status": "success",
            "campaign": campaign.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"Campaign stop failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Experiment Management ───────────────────────────────────────

@router.post("/experiments/add")
async def add_experiment(req: AddExperimentRequest):
    """
    Add an experiment to a campaign.
    
    The experiment will be in pending status until executed.
    
    Returns:
        Created experiment
    """
    manager = get_experiment_manager()
    
    try:
        experiment = manager.add_experiment(
            campaign_id=req.campaign_id,
            name=req.name,
            parameters=req.parameters,
            workflow_id=req.workflow_id,
        )
        
        return {
            "status": "success",
            "experiment": experiment.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"Experiment addition failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments/execute")
async def execute_experiment(req: ExecuteExperimentRequest):
    """
    Execute an experiment.
    
    Runs the experiment (via workflow if specified) and
    collects results.
    
    Returns:
        Completed experiment with results
    """
    manager = get_experiment_manager()
    
    try:
        experiment = manager.execute_experiment(
            campaign_id=req.campaign_id,
            experiment_id=req.experiment_id,
        )
        
        return {
            "status": "success",
            "experiment": experiment.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"Experiment execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments/{campaign_id}/{experiment_id}")
async def get_experiment(campaign_id: str, experiment_id: str):
    """
    Get experiment details.
    
    Returns:
        Experiment details including results
    """
    manager = get_experiment_manager()
    
    experiment = manager.get_experiment(campaign_id, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    return {
        "status": "success",
        "experiment": experiment.to_dict(),
    }


# ── Closed-Loop Autonomy ────────────────────────────────────────

@router.post("/campaigns/{campaign_id}/suggest")
async def suggest_next_experiment(campaign_id: str):
    """
    Suggest next experiment for a campaign.
    
    Uses campaign results to suggest optimal next experiment.
    
    Returns:
        Suggested experiment parameters
    """
    manager = get_experiment_manager()
    
    try:
        suggestion = manager.suggest_next_experiment(campaign_id)
        
        if not suggestion:
            return {
                "status": "no_suggestion",
                "message": "No more experiments suggested (stopping criteria met)",
            }
        
        return {
            "status": "success",
            "suggestion": suggestion,
        }
        
    except Exception as e:
        logger.error(f"Suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/closed-loop")
async def run_closed_loop(req: ClosedLoopRequest):
    """
    Run closed-loop autonomous campaign.
    
    Automatically suggests, executes, and analyzes experiments
    until stopping criteria are met.
    
    Pipeline:
    1. Suggest next experiment
    2. Execute experiment
    3. Analyze results
    4. Update campaign
    5. Check stopping criteria
    6. Repeat
    
    Returns:
        Campaign results with all iterations
    """
    manager = get_experiment_manager()
    
    try:
        results = manager.run_closed_loop(
            campaign_id=req.campaign_id,
            max_iterations=req.max_iterations,
        )
        
        # Get updated campaign
        campaign = manager.get_campaign(req.campaign_id)
        
        return {
            "status": "success",
            "results": results,
            "campaign": campaign.to_dict() if campaign else None,
        }
        
    except Exception as e:
        logger.error(f"Closed-loop execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Resource Management ─────────────────────────────────────────

@router.post("/resources/add")
async def add_resource(req: AddResourceRequest):
    """
    Add a resource to the inventory.
    
    Resources can be materials, equipment, or reagents.
    
    Returns:
        Created resource
    """
    manager = get_experiment_manager()
    
    try:
        resource = manager.add_resource(
            resource_type=req.resource_type,
            name=req.name,
            quantity=req.quantity,
            unit=req.unit,
            cost_per_unit=req.cost_per_unit,
        )
        
        return {
            "status": "success",
            "resource": resource.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"Resource addition failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources/list")
async def list_resources(resource_type: Optional[str] = None):
    """
    List all resources.
    
    Optionally filter by type (material, equipment, reagent).
    
    Returns:
        List of resources
    """
    manager = get_experiment_manager()
    
    try:
        resources = manager.list_resources(resource_type=resource_type)
        
        return {
            "status": "success",
            "n_resources": len(resources),
            "resources": [r.to_dict() for r in resources],
        }
        
    except Exception as e:
        logger.error(f"Resource listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources/{resource_id}")
async def get_resource(resource_id: str):
    """
    Get resource details.
    
    Returns:
        Resource details
    """
    manager = get_experiment_manager()
    
    resource = manager.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    return {
        "status": "success",
        "resource": resource.to_dict(),
    }


@router.post("/resources/consume")
async def consume_resource(req: ConsumeResourceRequest):
    """
    Consume a quantity of a resource.
    
    Updates resource inventory.
    
    Returns:
        Updated resource
    """
    manager = get_experiment_manager()
    
    try:
        resource = manager.consume_resource(
            resource_id=req.resource_id,
            quantity=req.quantity,
        )
        
        return {
            "status": "success",
            "resource": resource.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"Resource consumption failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Analytics ───────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/analytics")
async def get_campaign_analytics(campaign_id: str):
    """
    Get campaign analytics.
    
    Returns:
        Analytics including cost, performance, convergence
    """
    manager = get_experiment_manager()
    
    campaign = manager.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Calculate analytics
    completed = [e for e in campaign.experiments if e.status == ExperimentStatus.COMPLETED]
    
    if not completed:
        return {
            "status": "success",
            "analytics": {
                "n_experiments": 0,
                "total_cost": 0.0,
                "avg_cost": 0.0,
                "best_metric": None,
                "improvement": None,
            }
        }
    
    # Cost analytics
    total_cost = sum(e.cost for e in completed)
    avg_cost = total_cost / len(completed)
    
    # Performance analytics
    metric_values = [e.metrics.get(campaign.target_metric) for e in completed if campaign.target_metric in e.metrics]
    
    if metric_values:
        first_value = metric_values[0]
        best_value = campaign.best_metric_value
        
        if campaign.objective == "maximize":
            improvement = ((best_value - first_value) / first_value * 100) if first_value else 0
        else:
            improvement = ((first_value - best_value) / first_value * 100) if first_value else 0
    else:
        improvement = None
    
    return {
        "status": "success",
        "analytics": {
            "n_experiments": len(completed),
            "total_cost": total_cost,
            "avg_cost": avg_cost,
            "best_metric": campaign.best_metric_value,
            "improvement_percent": improvement,
            "convergence": {
                "converged": campaign.status == CampaignStatus.COMPLETED,
                "iterations": len(completed),
            }
        }
    }
