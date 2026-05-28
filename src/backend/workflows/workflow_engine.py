"""
Workflow Execution Engine for RĀMAN Studio
==========================================
Orchestrates multi-step autonomous experiments using WEI-compatible nodes.

Features:
- Visual workflow builder support
- Parallel and sequential execution
- Error handling and retry logic
- Real-time progress tracking
- Workflow templates
- Resource management

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import logging
import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    """Workflow node types."""
    SIMULATION = "simulation"
    ANALYSIS = "analysis"
    DECISION = "decision"
    DATA_TRANSFORM = "data_transform"
    EXTERNAL_API = "external_api"
    PARALLEL = "parallel"
    LOOP = "loop"


class NodeStatus(str, Enum):
    """Node execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowNode:
    """
    A single node in a workflow.
    
    Represents one step in the autonomous experiment workflow.
    """
    node_id: str
    node_type: NodeType
    name: str
    action: str  # Action to execute (e.g., "simulate_eis", "identify_material")
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # Node IDs this depends on
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "name": self.name,
            "action": self.action,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class Workflow:
    """
    A complete workflow definition.
    
    Represents an autonomous experiment workflow with multiple steps.
    """
    workflow_id: str
    name: str
    description: str
    nodes: List[WorkflowNode] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "nodes": [node.to_dict() for node in self.nodes],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }
    
    def add_node(self, node: WorkflowNode):
        """Add a node to the workflow."""
        self.nodes.append(node)
    
    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None
    
    def get_ready_nodes(self) -> List[WorkflowNode]:
        """Get nodes that are ready to execute (all dependencies met)."""
        ready = []
        for node in self.nodes:
            if node.status != NodeStatus.PENDING:
                continue
            
            # Check if all dependencies are completed
            deps_met = True
            for dep_id in node.dependencies:
                dep_node = self.get_node(dep_id)
                if not dep_node or dep_node.status != NodeStatus.COMPLETED:
                    deps_met = False
                    break
            
            if deps_met:
                ready.append(node)
        
        return ready


class WorkflowEngine:
    """
    Workflow execution engine.
    
    Orchestrates the execution of multi-step workflows with:
    - Dependency resolution
    - Parallel execution
    - Error handling and retries
    - Real-time progress tracking
    
    Usage:
        engine = WorkflowEngine()
        
        # Create workflow
        workflow = Workflow(
            workflow_id="exp_001",
            name="Material Characterization",
            description="Full EIS + CV + Raman characterization"
        )
        
        # Add nodes
        workflow.add_node(WorkflowNode(
            node_id="eis_1",
            node_type=NodeType.SIMULATION,
            name="Run EIS",
            action="simulate_eis",
            parameters={"Rs": 10.0, "Rct": 100.0}
        ))
        
        # Execute
        await engine.execute_workflow(workflow)
    """
    
    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.action_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default action handlers."""
        # Import WEI node for simulation actions
        from src.backend.integrations.wei_integration import get_wei_node
        wei_node = get_wei_node()
        
        # Register all WEI actions
        for action_name in wei_node.actions.keys():
            self.action_handlers[action_name] = lambda params, action=action_name: (
                wei_node.execute_action(action, params).to_dict()
            )
        
        # Register custom actions
        self.action_handlers["identify_material_ml"] = self._action_identify_material_ml
        self.action_handlers["optimize_bayesian"] = self._action_optimize_bayesian
        self.action_handlers["data_transform"] = self._action_data_transform
        self.action_handlers["decision_gate"] = self._action_decision_gate
    
    def register_workflow(self, workflow: Workflow):
        """Register a workflow for execution."""
        self.workflows[workflow.workflow_id] = workflow
        logger.info(f"Registered workflow: {workflow.workflow_id}")
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        return self.workflows.get(workflow_id)
    
    async def execute_workflow(
        self,
        workflow: Workflow,
        progress_callback: Optional[Callable] = None
    ) -> Workflow:
        """
        Execute a workflow.
        
        Args:
            workflow: Workflow to execute
            progress_callback: Optional callback for progress updates
            
        Returns:
            Completed workflow with results
        """
        logger.info(f"Starting workflow execution: {workflow.workflow_id}")
        
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now()
        
        try:
            while True:
                # Get nodes ready to execute
                ready_nodes = workflow.get_ready_nodes()
                
                if not ready_nodes:
                    # Check if workflow is complete
                    all_done = all(
                        node.status in [NodeStatus.COMPLETED, NodeStatus.SKIPPED, NodeStatus.FAILED]
                        for node in workflow.nodes
                    )
                    
                    if all_done:
                        # Check if any failed
                        any_failed = any(
                            node.status == NodeStatus.FAILED
                            for node in workflow.nodes
                        )
                        
                        workflow.status = WorkflowStatus.FAILED if any_failed else WorkflowStatus.COMPLETED
                        workflow.completed_at = datetime.now()
                        break
                    
                    # Wait for running nodes
                    await asyncio.sleep(0.1)
                    continue
                
                # Execute ready nodes in parallel
                tasks = [
                    self._execute_node(workflow, node, progress_callback)
                    for node in ready_nodes
                ]
                
                await asyncio.gather(*tasks)
            
            logger.info(f"Workflow completed: {workflow.workflow_id} - Status: {workflow.status}")
            return workflow
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            workflow.status = WorkflowStatus.FAILED
            workflow.completed_at = datetime.now()
            raise
    
    async def _execute_node(
        self,
        workflow: Workflow,
        node: WorkflowNode,
        progress_callback: Optional[Callable] = None
    ):
        """Execute a single node."""
        logger.info(f"Executing node: {node.node_id} ({node.name})")
        
        node.status = NodeStatus.RUNNING
        node.started_at = datetime.now()
        
        if progress_callback:
            await progress_callback(workflow, node)
        
        try:
            # Get action handler
            handler = self.action_handlers.get(node.action)
            if not handler:
                raise ValueError(f"Unknown action: {node.action}")
            
            # Resolve parameter references (e.g., ${node_id.result.value})
            resolved_params = self._resolve_parameters(workflow, node.parameters)
            
            # Execute with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(handler, resolved_params),
                timeout=node.timeout_seconds
            )
            
            node.result = result
            node.status = NodeStatus.COMPLETED
            node.completed_at = datetime.now()
            
            logger.info(f"Node completed: {node.node_id}")
            
        except asyncio.TimeoutError:
            logger.error(f"Node timeout: {node.node_id}")
            node.error = f"Timeout after {node.timeout_seconds}s"
            
            # Retry if possible
            if node.retry_count < node.max_retries:
                node.retry_count += 1
                node.status = NodeStatus.PENDING
                logger.info(f"Retrying node: {node.node_id} (attempt {node.retry_count}/{node.max_retries})")
            else:
                node.status = NodeStatus.FAILED
                node.completed_at = datetime.now()
                
        except Exception as e:
            logger.error(f"Node execution failed: {node.node_id} - {e}")
            node.error = str(e)
            
            # Retry if possible
            if node.retry_count < node.max_retries:
                node.retry_count += 1
                node.status = NodeStatus.PENDING
                logger.info(f"Retrying node: {node.node_id} (attempt {node.retry_count}/{node.max_retries})")
            else:
                node.status = NodeStatus.FAILED
                node.completed_at = datetime.now()
        
        if progress_callback:
            await progress_callback(workflow, node)
    
    def _resolve_parameters(
        self,
        workflow: Workflow,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Resolve parameter references.
        
        Supports syntax like: ${node_id.result.value}
        """
        resolved = {}
        
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # Parse reference: ${node_id.result.value}
                ref = value[2:-1]
                parts = ref.split(".")
                
                if len(parts) >= 2:
                    node_id = parts[0]
                    node = workflow.get_node(node_id)
                    
                    if node and node.result:
                        # Navigate through result
                        result = node.result
                        for part in parts[1:]:
                            if isinstance(result, dict):
                                result = result.get(part)
                            else:
                                break
                        
                        resolved[key] = result
                    else:
                        resolved[key] = None
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        
        return resolved
    
    # ── Custom Action Handlers ──────────────────────────────────
    
    def _action_identify_material_ml(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Identify material using ML model."""
        from src.backend.ml.material_identifier import get_material_identifier
        
        identifier = get_material_identifier()
        
        # Determine modality
        if "frequencies" in params:
            prediction = identifier.identify_from_eis(
                frequencies=params["frequencies"],
                Z_real=params["Z_real"],
                Z_imag=params["Z_imag"],
                top_k=params.get("top_k", 3)
            )
        elif "potential" in params:
            prediction = identifier.identify_from_cv(
                potential=params["potential"],
                current=params["current"],
                top_k=params.get("top_k", 3)
            )
        elif "wavenumber" in params:
            prediction = identifier.identify_from_raman(
                wavenumber=params["wavenumber"],
                intensity=params["intensity"],
                top_k=params.get("top_k", 3)
            )
        else:
            raise ValueError("Unknown modality for material identification")
        
        return prediction.to_dict()
    
    def _action_optimize_bayesian(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run Bayesian optimization."""
        from src.backend.ml.autonomous_optimizer import get_autonomous_optimizer
        
        optimizer = get_autonomous_optimizer()
        
        # Start optimization campaign
        campaign_id = optimizer.start_campaign(
            objective_fn=params["objective_fn"],
            candidate_space=params["candidate_space"],
            target_metric=params["target_metric"],
            objective=params.get("objective", "maximize"),
            max_iterations=params.get("max_iterations", 50),
        )
        
        # Wait for completion (simplified - in reality would be async)
        # For now, return campaign ID
        return {
            "campaign_id": campaign_id,
            "status": "started",
        }
    
    def _action_data_transform(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data between nodes."""
        import numpy as np
        
        data = params.get("data", [])
        operation = params.get("operation", "identity")
        
        if operation == "normalize":
            data = np.array(data)
            data = (data - data.min()) / (data.max() - data.min())
            return {"data": data.tolist()}
        
        elif operation == "extract_peaks":
            # Simple peak detection
            data = np.array(data)
            peaks = []
            for i in range(1, len(data) - 1):
                if data[i] > data[i-1] and data[i] > data[i+1]:
                    peaks.append(i)
            return {"peaks": peaks, "peak_values": data[peaks].tolist()}
        
        else:
            return {"data": data}
    
    def _action_decision_gate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Decision gate for conditional workflow execution."""
        condition = params.get("condition", "true")
        value = params.get("value")
        threshold = params.get("threshold")
        
        if condition == "greater_than":
            decision = value > threshold
        elif condition == "less_than":
            decision = value < threshold
        elif condition == "equals":
            decision = value == threshold
        else:
            decision = True
        
        return {
            "decision": decision,
            "value": value,
            "threshold": threshold,
        }


# Global singleton
_workflow_engine = None

def get_workflow_engine() -> WorkflowEngine:
    """Get the global workflow engine instance."""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine
