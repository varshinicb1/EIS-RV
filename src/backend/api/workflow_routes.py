"""
Workflow API Routes
===================
REST API endpoints for workflow management and execution.

Endpoints:
- GET /api/v2/workflows/templates - List workflow templates
- POST /api/v2/workflows/create - Create workflow from template
- POST /api/v2/workflows/execute - Execute workflow
- GET /api/v2/workflows/{id}/status - Get workflow status
- POST /api/v2/workflows/{id}/cancel - Cancel workflow
- GET /api/v2/workflows/{id}/results - Get workflow results
- WS /api/v2/workflows/{id}/ws - Real-time progress updates

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.backend.workflows.workflow_engine import (
    get_workflow_engine,
    Workflow,
    WorkflowNode,
    NodeType,
    WorkflowStatus,
)
from src.backend.workflows.workflow_templates import (
    WorkflowTemplates,
    get_template,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/workflows", tags=["workflows"])

# WebSocket connections for real-time updates
active_websockets: Dict[str, List[WebSocket]] = {}


# ── Request Models ──────────────────────────────────────────────

class CreateWorkflowRequest(BaseModel):
    template_id: str = Field(..., description="Template identifier")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Template parameters")
    workflow_name: Optional[str] = Field(None, description="Custom workflow name")


class ExecuteWorkflowRequest(BaseModel):
    workflow_id: str = Field(..., description="Workflow ID to execute")


class CreateCustomWorkflowRequest(BaseModel):
    name: str = Field(..., description="Workflow name")
    description: str = Field(..., description="Workflow description")
    nodes: List[Dict[str, Any]] = Field(..., description="Workflow nodes")


# ── Template Endpoints ──────────────────────────────────────────

@router.get("/templates")
async def list_templates():
    """
    List all available workflow templates.
    
    Returns:
        List of workflow templates with descriptions and parameters
    """
    templates = WorkflowTemplates.list_templates()
    
    return {
        "templates": templates,
        "total": len(templates),
    }


@router.get("/templates/{template_id}")
async def get_template_info(template_id: str):
    """
    Get detailed information about a workflow template.
    
    Args:
        template_id: Template identifier
        
    Returns:
        Template details including example parameters
    """
    templates = {t["id"]: t for t in WorkflowTemplates.list_templates()}
    
    if template_id not in templates:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    
    template = templates[template_id]
    
    # Add example parameters
    examples = {
        "full_characterization": {
            "material_params": {
                "Rs": 10.0,
                "Rct": 100.0,
                "Cdl": 1e-5,
                "sigma_w": 50.0,
            }
        },
        "optimization_loop": {
            "target_metric": "capacitance",
            "max_iterations": 50,
        },
        "autonomous_discovery": {
            "application": "supercapacitor electrode",
        },
        "quality_control": {
            "reference_data": {
                "parameters": {"Rs": 10.0, "Rct": 100.0},
                "expected_results": {"capacitance": 150.0},
            },
            "tolerance": 0.1,
        },
        "parallel_screening": {
            "materials": [
                {"Rs": 10.0, "Rct": 100.0, "Cdl": 1e-5},
                {"Rs": 8.0, "Rct": 120.0, "Cdl": 1.2e-5},
                {"Rs": 12.0, "Rct": 90.0, "Cdl": 0.9e-5},
            ]
        },
    }
    
    template["example_parameters"] = examples.get(template_id, {})
    
    return template


# ── Workflow Management ─────────────────────────────────────────

@router.post("/create")
async def create_workflow(req: CreateWorkflowRequest):
    """
    Create a workflow from a template.
    
    Args:
        req: Workflow creation request
        
    Returns:
        Created workflow with ID
    """
    try:
        # Get template
        workflow = get_template(req.template_id, **req.parameters)
        
        # Override name if provided
        if req.workflow_name:
            workflow.name = req.workflow_name
        
        # Register with engine
        engine = get_workflow_engine()
        engine.register_workflow(workflow)
        
        return {
            "workflow_id": workflow.workflow_id,
            "name": workflow.name,
            "description": workflow.description,
            "status": workflow.status.value,
            "nodes": [node.to_dict() for node in workflow.nodes],
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-custom")
async def create_custom_workflow(req: CreateCustomWorkflowRequest):
    """
    Create a custom workflow from scratch.
    
    Args:
        req: Custom workflow request
        
    Returns:
        Created workflow with ID
    """
    try:
        import uuid
        
        workflow = Workflow(
            workflow_id=f"custom_{uuid.uuid4().hex[:8]}",
            name=req.name,
            description=req.description,
        )
        
        # Add nodes
        for node_data in req.nodes:
            node = WorkflowNode(
                node_id=node_data["node_id"],
                node_type=NodeType(node_data["node_type"]),
                name=node_data["name"],
                action=node_data["action"],
                parameters=node_data.get("parameters", {}),
                dependencies=node_data.get("dependencies", []),
                max_retries=node_data.get("max_retries", 3),
                timeout_seconds=node_data.get("timeout_seconds", 300),
            )
            workflow.add_node(node)
        
        # Register with engine
        engine = get_workflow_engine()
        engine.register_workflow(workflow)
        
        return {
            "workflow_id": workflow.workflow_id,
            "name": workflow.name,
            "description": workflow.description,
            "status": workflow.status.value,
            "nodes": [node.to_dict() for node in workflow.nodes],
        }
        
    except Exception as e:
        logger.error(f"Failed to create custom workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_workflows():
    """
    List all registered workflows.
    
    Returns:
        List of workflows with status
    """
    engine = get_workflow_engine()
    
    workflows = [
        {
            "workflow_id": wf.workflow_id,
            "name": wf.name,
            "description": wf.description,
            "status": wf.status.value,
            "created_at": wf.created_at.isoformat(),
            "n_nodes": len(wf.nodes),
        }
        for wf in engine.workflows.values()
    ]
    
    return {
        "workflows": workflows,
        "total": len(workflows),
    }


# ── Workflow Execution ──────────────────────────────────────────

@router.post("/execute")
async def execute_workflow(req: ExecuteWorkflowRequest):
    """
    Execute a workflow.
    
    Args:
        req: Execution request
        
    Returns:
        Execution started confirmation
    """
    engine = get_workflow_engine()
    workflow = engine.get_workflow(req.workflow_id)
    
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {req.workflow_id}")
    
    if workflow.status == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Workflow is already running")
    
    # Start execution in background
    async def run_workflow():
        try:
            await engine.execute_workflow(
                workflow,
                progress_callback=lambda wf, node: _broadcast_progress(wf.workflow_id, node)
            )
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
    
    asyncio.create_task(run_workflow())
    
    return {
        "workflow_id": workflow.workflow_id,
        "status": "started",
        "message": f"Workflow {workflow.workflow_id} execution started",
    }


@router.get("/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """
    Get workflow execution status.
    
    Args:
        workflow_id: Workflow ID
        
    Returns:
        Current workflow status and progress
    """
    engine = get_workflow_engine()
    workflow = engine.get_workflow(workflow_id)
    
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")
    
    # Calculate progress
    total_nodes = len(workflow.nodes)
    completed_nodes = sum(1 for node in workflow.nodes if node.status == "completed")
    failed_nodes = sum(1 for node in workflow.nodes if node.status == "failed")
    running_nodes = sum(1 for node in workflow.nodes if node.status == "running")
    
    progress = (completed_nodes / total_nodes * 100) if total_nodes > 0 else 0
    
    return {
        "workflow_id": workflow.workflow_id,
        "name": workflow.name,
        "status": workflow.status.value,
        "progress": progress,
        "total_nodes": total_nodes,
        "completed_nodes": completed_nodes,
        "failed_nodes": failed_nodes,
        "running_nodes": running_nodes,
        "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
        "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
    }


@router.get("/{workflow_id}/results")
async def get_workflow_results(workflow_id: str):
    """
    Get workflow execution results.
    
    Args:
        workflow_id: Workflow ID
        
    Returns:
        Complete workflow results
    """
    engine = get_workflow_engine()
    workflow = engine.get_workflow(workflow_id)
    
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")
    
    return workflow.to_dict()


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """
    Cancel a running workflow.
    
    Args:
        workflow_id: Workflow ID
        
    Returns:
        Cancellation confirmation
    """
    engine = get_workflow_engine()
    workflow = engine.get_workflow(workflow_id)
    
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")
    
    if workflow.status != WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Workflow is not running")
    
    workflow.status = WorkflowStatus.CANCELLED
    
    # Broadcast cancellation
    await _broadcast_progress(workflow_id, None, event="cancelled")
    
    return {
        "workflow_id": workflow_id,
        "status": "cancelled",
        "message": f"Workflow {workflow_id} cancelled",
    }


# ── WebSocket for Real-Time Updates ────────────────────────────

@router.websocket("/{workflow_id}/ws")
async def workflow_websocket(websocket: WebSocket, workflow_id: str):
    """
    WebSocket endpoint for real-time workflow progress updates.
    
    Sends updates on:
    - Node started
    - Node completed
    - Node failed
    - Workflow completed
    - Workflow failed
    
    Usage:
        ws = new WebSocket('ws://localhost:8000/api/v2/workflows/{workflow_id}/ws')
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            console.log('Node:', data.node_id, 'Status:', data.status)
        }
    """
    await websocket.accept()
    
    # Register WebSocket
    if workflow_id not in active_websockets:
        active_websockets[workflow_id] = []
    active_websockets[workflow_id].append(websocket)
    
    logger.info(f"WebSocket connected for workflow {workflow_id}")
    
    try:
        # Send initial status
        engine = get_workflow_engine()
        workflow = engine.get_workflow(workflow_id)
        
        if workflow:
            await websocket.send_json({
                "event": "connected",
                "workflow_id": workflow_id,
                "status": workflow.status.value,
            })
        else:
            await websocket.send_json({
                "event": "error",
                "message": f"Workflow {workflow_id} not found",
            })
            await websocket.close()
            return
        
        # Keep connection alive
        while True:
            try:
                # Wait for message from client (ping/pong)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                
                # Send current status
                await websocket.send_json({
                    "event": "status_update",
                    "workflow_id": workflow_id,
                    "status": workflow.status.value,
                })
                
            except asyncio.TimeoutError:
                # Send periodic heartbeat
                await websocket.send_json({"event": "heartbeat"})
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for workflow {workflow_id}")
    finally:
        # Unregister WebSocket
        if workflow_id in active_websockets:
            active_websockets[workflow_id].remove(websocket)
            if len(active_websockets[workflow_id]) == 0:
                del active_websockets[workflow_id]


async def _broadcast_progress(workflow_id: str, node: Optional[WorkflowNode], event: str = "node_update"):
    """Broadcast progress update to all WebSocket clients."""
    if workflow_id not in active_websockets:
        return
    
    data = {
        "event": event,
        "workflow_id": workflow_id,
    }
    
    if node:
        data["node"] = node.to_dict()
    
    dead_sockets = []
    for ws in active_websockets[workflow_id]:
        try:
            await ws.send_json(data)
        except Exception:
            dead_sockets.append(ws)
    
    # Remove dead sockets
    for ws in dead_sockets:
        active_websockets[workflow_id].remove(ws)
