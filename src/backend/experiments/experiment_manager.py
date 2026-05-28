"""
MADSci Experiment Manager for RĀMAN Studio
==========================================
Full experiment management with closed-loop autonomy.

Features:
- Campaign planning and tracking
- Resource management (materials, equipment)
- Data collection and storage
- Analysis pipelines
- Closed-loop decision making
- Multi-day campaigns
- Automatic stopping criteria

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json

logger = logging.getLogger(__name__)


class CampaignStatus(str, Enum):
    """Campaign execution status."""
    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExperimentStatus(str, Enum):
    """Individual experiment status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StoppingCriterion(str, Enum):
    """Stopping criteria for campaigns."""
    MAX_EXPERIMENTS = "max_experiments"
    CONVERGENCE = "convergence"
    TIME_LIMIT = "time_limit"
    PERFORMANCE_THRESHOLD = "performance_threshold"
    MANUAL = "manual"


@dataclass
class Resource:
    """Represents a lab resource (material, equipment, etc.)."""
    resource_id: str
    resource_type: str  # "material", "equipment", "reagent"
    name: str
    quantity: float
    unit: str
    cost_per_unit: float = 0.0
    available: bool = True
    location: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "name": self.name,
            "quantity": self.quantity,
            "unit": self.unit,
            "cost_per_unit": self.cost_per_unit,
            "available": self.available,
            "location": self.location,
            "metadata": self.metadata,
        }


@dataclass
class Experiment:
    """Represents a single experiment in a campaign."""
    experiment_id: str
    campaign_id: str
    name: str
    parameters: Dict[str, Any]
    workflow_id: Optional[str] = None
    status: ExperimentStatus = ExperimentStatus.PENDING
    results: Optional[Dict[str, Any]] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    resources_used: List[str] = field(default_factory=list)
    cost: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "campaign_id": self.campaign_id,
            "name": self.name,
            "parameters": self.parameters,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "results": self.results,
            "metrics": self.metrics,
            "resources_used": self.resources_used,
            "cost": self.cost,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


@dataclass
class Campaign:
    """Represents an experiment campaign."""
    campaign_id: str
    name: str
    description: str
    objective: str  # "maximize", "minimize", "target"
    target_metric: str
    target_value: Optional[float] = None
    max_experiments: int = 100
    max_duration_hours: float = 168.0  # 1 week default
    stopping_criteria: List[StoppingCriterion] = field(default_factory=list)
    status: CampaignStatus = CampaignStatus.PLANNED
    experiments: List[Experiment] = field(default_factory=list)
    best_experiment: Optional[str] = None
    best_metric_value: Optional[float] = None
    total_cost: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "description": self.description,
            "objective": self.objective,
            "target_metric": self.target_metric,
            "target_value": self.target_value,
            "max_experiments": self.max_experiments,
            "max_duration_hours": self.max_duration_hours,
            "stopping_criteria": [c.value for c in self.stopping_criteria],
            "status": self.status.value,
            "n_experiments": len(self.experiments),
            "n_completed": sum(1 for e in self.experiments if e.status == ExperimentStatus.COMPLETED),
            "n_failed": sum(1 for e in self.experiments if e.status == ExperimentStatus.FAILED),
            "best_experiment": self.best_experiment,
            "best_metric_value": self.best_metric_value,
            "total_cost": self.total_cost,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }


class ExperimentManager:
    """
    MADSci Experiment Manager.
    
    Manages full experiment campaigns with:
    - Campaign planning and tracking
    - Resource management
    - Data collection
    - Closed-loop decision making
    - Automatic stopping criteria
    """
    
    def __init__(self):
        self.campaigns: Dict[str, Campaign] = {}
        self.resources: Dict[str, Resource] = {}
        self._initialize_default_resources()
    
    def _initialize_default_resources(self):
        """Initialize default lab resources."""
        # Materials
        materials = [
            ("graphene", "material", 100.0, "g", 50.0),
            ("CNT", "material", 50.0, "g", 100.0),
            ("MXene", "material", 25.0, "g", 200.0),
            ("PEDOT:PSS", "material", 500.0, "mL", 20.0),
        ]
        
        for name, rtype, qty, unit, cost in materials:
            resource_id = f"mat_{name.lower()}"
            self.resources[resource_id] = Resource(
                resource_id=resource_id,
                resource_type=rtype,
                name=name,
                quantity=qty,
                unit=unit,
                cost_per_unit=cost,
            )
        
        # Equipment
        equipment = [
            ("potentiostat", "equipment", 1.0, "unit", 0.0),
            ("raman_spectrometer", "equipment", 1.0, "unit", 0.0),
            ("spin_coater", "equipment", 1.0, "unit", 0.0),
        ]
        
        for name, rtype, qty, unit, cost in equipment:
            resource_id = f"eq_{name}"
            self.resources[resource_id] = Resource(
                resource_id=resource_id,
                resource_type=rtype,
                name=name,
                quantity=qty,
                unit=unit,
                cost_per_unit=cost,
            )
    
    # ── Campaign Management ─────────────────────────────────────
    
    def create_campaign(
        self,
        name: str,
        description: str,
        objective: str,
        target_metric: str,
        target_value: Optional[float] = None,
        max_experiments: int = 100,
        max_duration_hours: float = 168.0,
        stopping_criteria: Optional[List[str]] = None,
    ) -> Campaign:
        """
        Create a new experiment campaign.
        
        Args:
            name: Campaign name
            description: Campaign description
            objective: "maximize", "minimize", or "target"
            target_metric: Metric to optimize (e.g., "capacitance")
            target_value: Target value (for "target" objective)
            max_experiments: Maximum number of experiments
            max_duration_hours: Maximum campaign duration
            stopping_criteria: List of stopping criteria
        
        Returns:
            Created campaign
        """
        campaign_id = f"camp_{uuid.uuid4().hex[:8]}"
        
        # Convert stopping criteria strings to enum
        criteria = []
        if stopping_criteria:
            for c in stopping_criteria:
                try:
                    criteria.append(StoppingCriterion(c))
                except ValueError:
                    logger.warning(f"Unknown stopping criterion: {c}")
        
        # Default stopping criteria
        if not criteria:
            criteria = [
                StoppingCriterion.MAX_EXPERIMENTS,
                StoppingCriterion.TIME_LIMIT,
            ]
        
        campaign = Campaign(
            campaign_id=campaign_id,
            name=name,
            description=description,
            objective=objective,
            target_metric=target_metric,
            target_value=target_value,
            max_experiments=max_experiments,
            max_duration_hours=max_duration_hours,
            stopping_criteria=criteria,
        )
        
        self.campaigns[campaign_id] = campaign
        logger.info(f"Created campaign: {campaign_id} - {name}")
        
        return campaign
    
    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get campaign by ID."""
        return self.campaigns.get(campaign_id)
    
    def list_campaigns(
        self,
        status: Optional[str] = None
    ) -> List[Campaign]:
        """List all campaigns, optionally filtered by status."""
        campaigns = list(self.campaigns.values())
        
        if status:
            try:
                status_enum = CampaignStatus(status)
                campaigns = [c for c in campaigns if c.status == status_enum]
            except ValueError:
                logger.warning(f"Unknown status: {status}")
        
        return campaigns
    
    def start_campaign(self, campaign_id: str) -> Campaign:
        """Start a campaign."""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        if campaign.status != CampaignStatus.PLANNED:
            raise ValueError(f"Campaign already started: {campaign_id}")
        
        campaign.status = CampaignStatus.RUNNING
        campaign.started_at = datetime.now()
        
        logger.info(f"Started campaign: {campaign_id}")
        
        return campaign
    
    def stop_campaign(
        self,
        campaign_id: str,
        reason: str = "manual"
    ) -> Campaign:
        """Stop a campaign."""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        if campaign.status != CampaignStatus.RUNNING:
            raise ValueError(f"Campaign not running: {campaign_id}")
        
        campaign.status = CampaignStatus.COMPLETED
        campaign.completed_at = datetime.now()
        campaign.metadata["stop_reason"] = reason
        
        logger.info(f"Stopped campaign: {campaign_id} (reason: {reason})")
        
        return campaign
    
    # ── Experiment Management ───────────────────────────────────
    
    def add_experiment(
        self,
        campaign_id: str,
        name: str,
        parameters: Dict[str, Any],
        workflow_id: Optional[str] = None,
    ) -> Experiment:
        """Add an experiment to a campaign."""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        experiment_id = f"exp_{uuid.uuid4().hex[:8]}"
        
        experiment = Experiment(
            experiment_id=experiment_id,
            campaign_id=campaign_id,
            name=name,
            parameters=parameters,
            workflow_id=workflow_id,
        )
        
        campaign.experiments.append(experiment)
        
        logger.info(f"Added experiment: {experiment_id} to campaign {campaign_id}")
        
        return experiment
    
    def get_experiment(
        self,
        campaign_id: str,
        experiment_id: str
    ) -> Optional[Experiment]:
        """Get experiment by ID."""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return None
        
        for exp in campaign.experiments:
            if exp.experiment_id == experiment_id:
                return exp
        
        return None
    
    def execute_experiment(
        self,
        campaign_id: str,
        experiment_id: str
    ) -> Experiment:
        """
        Execute an experiment.
        
        This would integrate with Phase 3 workflows to actually run
        the experiment. For now, we simulate execution.
        """
        experiment = self.get_experiment(campaign_id, experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        if experiment.status != ExperimentStatus.PENDING:
            raise ValueError(f"Experiment already executed: {experiment_id}")
        
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now()
        
        logger.info(f"Executing experiment: {experiment_id}")
        
        # Simulate execution (would integrate with workflows)
        import time
        time.sleep(0.5)  # Simulate work
        
        # Simulate results
        experiment.results = {
            "capacitance": 150.0 + (hash(experiment_id) % 50),
            "stability": 0.85 + (hash(experiment_id) % 15) / 100,
            "cost": 25.0 + (hash(experiment_id) % 10),
        }
        
        experiment.metrics = {
            "capacitance": experiment.results["capacitance"],
            "stability": experiment.results["stability"],
        }
        
        experiment.cost = experiment.results["cost"]
        experiment.status = ExperimentStatus.COMPLETED
        experiment.completed_at = datetime.now()
        
        # Update campaign
        campaign = self.get_campaign(campaign_id)
        campaign.total_cost += experiment.cost
        
        # Update best experiment
        metric_value = experiment.metrics.get(campaign.target_metric)
        if metric_value is not None:
            if campaign.best_metric_value is None:
                campaign.best_experiment = experiment_id
                campaign.best_metric_value = metric_value
            elif campaign.objective == "maximize" and metric_value > campaign.best_metric_value:
                campaign.best_experiment = experiment_id
                campaign.best_metric_value = metric_value
            elif campaign.objective == "minimize" and metric_value < campaign.best_metric_value:
                campaign.best_experiment = experiment_id
                campaign.best_metric_value = metric_value
        
        logger.info(f"Completed experiment: {experiment_id}")
        
        return experiment
    
    # ── Closed-Loop Decision Making ────────────────────────────
    
    def suggest_next_experiment(
        self,
        campaign_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Suggest next experiment based on campaign results.
        
        Uses simple heuristics for now. Would integrate with
        Phase 2 Bayesian optimization for smarter suggestions.
        """
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return None
        
        # Check stopping criteria
        if self._should_stop_campaign(campaign):
            return None
        
        # Get completed experiments
        completed = [e for e in campaign.experiments if e.status == ExperimentStatus.COMPLETED]
        
        if not completed:
            # First experiment - use default parameters
            return {
                "name": f"Experiment {len(campaign.experiments) + 1}",
                "parameters": {
                    "Rs": 10.0,
                    "Rct": 100.0,
                    "Cdl": 1e-5,
                },
                "rationale": "Initial exploration",
            }
        
        # Find best experiment
        best_exp = None
        best_value = None
        
        for exp in completed:
            value = exp.metrics.get(campaign.target_metric)
            if value is None:
                continue
            
            if best_value is None:
                best_exp = exp
                best_value = value
            elif campaign.objective == "maximize" and value > best_value:
                best_exp = exp
                best_value = value
            elif campaign.objective == "minimize" and value < best_value:
                best_exp = exp
                best_value = value
        
        if not best_exp:
            return None
        
        # Suggest variation of best experiment
        new_params = best_exp.parameters.copy()
        
        # Perturb parameters slightly
        for key in new_params:
            if isinstance(new_params[key], (int, float)):
                new_params[key] *= (1.0 + (hash(str(len(completed))) % 20 - 10) / 100)
        
        return {
            "name": f"Experiment {len(campaign.experiments) + 1}",
            "parameters": new_params,
            "rationale": f"Variation of best experiment ({best_exp.experiment_id})",
        }
    
    def _should_stop_campaign(self, campaign: Campaign) -> bool:
        """Check if campaign should stop based on stopping criteria."""
        # Max experiments
        if StoppingCriterion.MAX_EXPERIMENTS in campaign.stopping_criteria:
            if len(campaign.experiments) >= campaign.max_experiments:
                logger.info(f"Campaign {campaign.campaign_id} reached max experiments")
                return True
        
        # Time limit
        if StoppingCriterion.TIME_LIMIT in campaign.stopping_criteria:
            if campaign.started_at:
                elapsed = datetime.now() - campaign.started_at
                if elapsed.total_seconds() / 3600 >= campaign.max_duration_hours:
                    logger.info(f"Campaign {campaign.campaign_id} reached time limit")
                    return True
        
        # Performance threshold
        if StoppingCriterion.PERFORMANCE_THRESHOLD in campaign.stopping_criteria:
            if campaign.target_value is not None and campaign.best_metric_value is not None:
                if campaign.objective == "target":
                    # Within 5% of target
                    if abs(campaign.best_metric_value - campaign.target_value) / campaign.target_value < 0.05:
                        logger.info(f"Campaign {campaign.campaign_id} reached performance threshold")
                        return True
        
        # Convergence (simple check - no improvement in last 10 experiments)
        if StoppingCriterion.CONVERGENCE in campaign.stopping_criteria:
            completed = [e for e in campaign.experiments if e.status == ExperimentStatus.COMPLETED]
            if len(completed) >= 20:
                recent = completed[-10:]
                recent_best = max(
                    (e.metrics.get(campaign.target_metric, 0) for e in recent),
                    default=0
                )
                if campaign.best_metric_value and recent_best < campaign.best_metric_value * 1.01:
                    logger.info(f"Campaign {campaign.campaign_id} converged")
                    return True
        
        return False
    
    def run_closed_loop(
        self,
        campaign_id: str,
        max_iterations: int = 10
    ) -> Dict[str, Any]:
        """
        Run closed-loop autonomous campaign.
        
        Pipeline:
        1. Suggest next experiment
        2. Execute experiment
        3. Analyze results
        4. Update campaign
        5. Check stopping criteria
        6. Repeat
        """
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        if campaign.status != CampaignStatus.RUNNING:
            self.start_campaign(campaign_id)
        
        results = {
            "campaign_id": campaign_id,
            "iterations": [],
            "stopped_reason": None,
        }
        
        for i in range(max_iterations):
            logger.info(f"Closed-loop iteration {i+1}/{max_iterations}")
            
            # Check stopping criteria
            if self._should_stop_campaign(campaign):
                results["stopped_reason"] = "stopping_criteria_met"
                break
            
            # Suggest next experiment
            suggestion = self.suggest_next_experiment(campaign_id)
            if not suggestion:
                results["stopped_reason"] = "no_more_suggestions"
                break
            
            # Add and execute experiment
            experiment = self.add_experiment(
                campaign_id=campaign_id,
                name=suggestion["name"],
                parameters=suggestion["parameters"],
            )
            
            experiment = self.execute_experiment(campaign_id, experiment.experiment_id)
            
            # Record iteration
            results["iterations"].append({
                "iteration": i + 1,
                "experiment_id": experiment.experiment_id,
                "parameters": experiment.parameters,
                "metrics": experiment.metrics,
                "cost": experiment.cost,
            })
        
        # Stop campaign if completed
        if results["stopped_reason"]:
            self.stop_campaign(campaign_id, results["stopped_reason"])
        
        return results
    
    # ── Resource Management ─────────────────────────────────────
    
    def add_resource(
        self,
        resource_type: str,
        name: str,
        quantity: float,
        unit: str,
        cost_per_unit: float = 0.0,
    ) -> Resource:
        """Add a resource to the inventory."""
        resource_id = f"{resource_type[:3]}_{uuid.uuid4().hex[:8]}"
        
        resource = Resource(
            resource_id=resource_id,
            resource_type=resource_type,
            name=name,
            quantity=quantity,
            unit=unit,
            cost_per_unit=cost_per_unit,
        )
        
        self.resources[resource_id] = resource
        
        logger.info(f"Added resource: {resource_id} - {name}")
        
        return resource
    
    def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get resource by ID."""
        return self.resources.get(resource_id)
    
    def list_resources(
        self,
        resource_type: Optional[str] = None
    ) -> List[Resource]:
        """List all resources, optionally filtered by type."""
        resources = list(self.resources.values())
        
        if resource_type:
            resources = [r for r in resources if r.resource_type == resource_type]
        
        return resources
    
    def consume_resource(
        self,
        resource_id: str,
        quantity: float
    ) -> Resource:
        """Consume a quantity of a resource."""
        resource = self.get_resource(resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_id}")
        
        if resource.quantity < quantity:
            raise ValueError(f"Insufficient resource: {resource_id}")
        
        resource.quantity -= quantity
        
        if resource.quantity <= 0:
            resource.available = False
        
        logger.info(f"Consumed {quantity} {resource.unit} of {resource.name}")
        
        return resource


# ── Singleton Instance ──────────────────────────────────────────

_experiment_manager = None

def get_experiment_manager() -> ExperimentManager:
    """Get singleton experiment manager instance."""
    global _experiment_manager
    if _experiment_manager is None:
        _experiment_manager = ExperimentManager()
    return _experiment_manager
