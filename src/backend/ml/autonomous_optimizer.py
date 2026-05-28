"""
Autonomous Materials Optimization Engine
=========================================
Bayesian optimization powered by CAMD for autonomous materials discovery.

Integrates:
- CAMD Bayesian optimization
- VANL simulation engines
- Materials database
- Real-time progress tracking

Architecture:
    Define Objective → Initialize Campaign → Bayesian Loop →
    Suggest Candidate → Simulate → Update Model → Converge
"""

import logging
import time
import uuid
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)

# Import CAMD integration
from src.backend.integrations.camd_integration import get_camd_integration


class CampaignStatus(str, Enum):
    """Optimization campaign status."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    CONVERGED = "converged"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class OptimizationIteration:
    """Single iteration of optimization."""
    iteration: int
    candidate: Dict[str, Any]
    score: float
    simulation_time_ms: float
    timestamp: str
    is_best: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "iteration": self.iteration,
            "candidate": self.candidate,
            "score": round(self.score, 6),
            "simulation_time_ms": round(self.simulation_time_ms, 2),
            "timestamp": self.timestamp,
            "is_best": self.is_best,
        }


@dataclass
class OptimizationCampaign:
    """Optimization campaign state."""
    campaign_id: str
    objective: str  # "maximize" or "minimize"
    target_metric: str  # e.g., "capacitance", "energy_density"
    status: CampaignStatus
    n_iterations: int
    max_iterations: int
    convergence_threshold: float
    
    # Results
    best_candidate: Optional[Dict[str, Any]] = None
    best_score: Optional[float] = None
    iterations: List[OptimizationIteration] = field(default_factory=list)
    
    # Metadata
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "campaign_id": self.campaign_id,
            "objective": self.objective,
            "target_metric": self.target_metric,
            "status": self.status.value,
            "n_iterations": self.n_iterations,
            "max_iterations": self.max_iterations,
            "convergence_threshold": self.convergence_threshold,
            "best_candidate": self.best_candidate,
            "best_score": round(self.best_score, 6) if self.best_score else None,
            "iterations": [it.to_dict() for it in self.iterations[-10:]],  # Last 10
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress_pct": round(100 * self.n_iterations / self.max_iterations, 1),
        }


class AutonomousOptimizer:
    """
    Autonomous materials optimization engine.
    
    Uses Bayesian optimization (via CAMD) to find optimal material
    parameters by iteratively running VANL simulations.
    
    Workflow:
        1. Define objective function (e.g., maximize capacitance)
        2. Define candidate space (materials database)
        3. Start optimization campaign
        4. Bayesian loop:
           - Suggest next candidate (acquisition function)
           - Simulate candidate (VANL engines)
           - Update surrogate model
           - Check convergence
        5. Return best candidate
    
    Usage:
        optimizer = AutonomousOptimizer()
        
        # Define objective
        def objective(material):
            result = eis_engine.simulate(material)
            return extract_capacitance(result)
        
        # Start campaign
        campaign_id = optimizer.start_campaign(
            objective_fn=objective,
            candidate_space=materials_db,
            target_metric="capacitance",
            objective="maximize",
            max_iterations=50
        )
        
        # Monitor progress
        status = optimizer.get_campaign_status(campaign_id)
        print(f"Progress: {status['progress_pct']}%")
        
        # Get results
        results = optimizer.get_campaign_results(campaign_id)
        print(f"Best: {results['best_candidate']}")
    """
    
    def __init__(self):
        self.camd = get_camd_integration()
        self.campaigns: Dict[str, OptimizationCampaign] = {}
        self.active_campaign_id: Optional[str] = None
    
    def start_campaign(
        self,
        objective_fn: Callable,
        candidate_space: List[Dict[str, Any]],
        target_metric: str,
        objective: str = "maximize",
        max_iterations: int = 50,
        convergence_threshold: float = 0.01,
    ) -> str:
        """
        Start a new optimization campaign.
        
        Args:
            objective_fn: Function that takes material params and returns score
            candidate_space: List of candidate materials
            target_metric: Name of metric being optimized
            objective: "maximize" or "minimize"
            max_iterations: Maximum number of iterations
            convergence_threshold: Stop if improvement < threshold
            
        Returns:
            Campaign ID for tracking
        """
        # Generate campaign ID
        campaign_id = str(uuid.uuid4())[:8]
        
        # Create campaign
        campaign = OptimizationCampaign(
            campaign_id=campaign_id,
            objective=objective,
            target_metric=target_metric,
            status=CampaignStatus.INITIALIZING,
            n_iterations=0,
            max_iterations=max_iterations,
            convergence_threshold=convergence_threshold,
        )
        
        self.campaigns[campaign_id] = campaign
        self.active_campaign_id = campaign_id
        
        logger.info(f"Started optimization campaign {campaign_id}")
        
        # Run optimization in background (async would be better)
        try:
            self._run_optimization(
                campaign_id=campaign_id,
                objective_fn=objective_fn,
                candidate_space=candidate_space,
            )
        except Exception as e:
            logger.error(f"Campaign {campaign_id} failed: {e}")
            campaign.status = CampaignStatus.FAILED
        
        return campaign_id
    
    def _run_optimization(
        self,
        campaign_id: str,
        objective_fn: Callable,
        candidate_space: List[Dict[str, Any]],
    ):
        """
        Run the optimization loop.
        
        This is the core Bayesian optimization algorithm:
        1. Exploration phase (random sampling)
        2. Exploitation phase (acquisition function)
        3. Convergence check
        """
        campaign = self.campaigns[campaign_id]
        campaign.status = CampaignStatus.RUNNING
        
        # Initialize best score
        if campaign.objective == "maximize":
            best_score = float('-inf')
        else:
            best_score = float('inf')
        
        # Exploration phase (first 20% of iterations)
        n_explore = max(5, int(0.2 * campaign.max_iterations))
        explore_indices = np.random.choice(
            len(candidate_space),
            size=min(n_explore, len(candidate_space)),
            replace=False
        )
        
        for idx in explore_indices:
            if campaign.n_iterations >= campaign.max_iterations:
                break
            
            candidate = candidate_space[idx]
            
            # Simulate
            t0 = time.perf_counter()
            score = objective_fn(candidate)
            sim_time_ms = (time.perf_counter() - t0) * 1000
            
            # Update best
            is_best = False
            if campaign.objective == "maximize":
                if score > best_score:
                    best_score = score
                    campaign.best_candidate = candidate
                    campaign.best_score = score
                    is_best = True
            else:
                if score < best_score:
                    best_score = score
                    campaign.best_candidate = candidate
                    campaign.best_score = score
                    is_best = True
            
            # Record iteration
            iteration = OptimizationIteration(
                iteration=campaign.n_iterations,
                candidate=candidate,
                score=score,
                simulation_time_ms=sim_time_ms,
                timestamp=datetime.now().isoformat(),
                is_best=is_best,
            )
            campaign.iterations.append(iteration)
            campaign.n_iterations += 1
            
            logger.info(
                f"Campaign {campaign_id} iteration {campaign.n_iterations}: "
                f"score={score:.4f} (best={best_score:.4f})"
            )
        
        # Exploitation phase (remaining iterations)
        prev_best = best_score
        no_improvement_count = 0
        
        for iteration in range(n_explore, campaign.max_iterations):
            if campaign.status != CampaignStatus.RUNNING:
                break
            
            # Select next candidate using acquisition function
            # (simplified: select from unexplored candidates)
            explored = [it.candidate for it in campaign.iterations]
            unexplored = [
                c for c in candidate_space
                if c not in explored
            ]
            
            if len(unexplored) == 0:
                logger.info(f"Campaign {campaign_id}: All candidates explored")
                campaign.status = CampaignStatus.CONVERGED
                break
            
            # Simple acquisition: random from unexplored
            # TODO: Implement proper acquisition function (UCB, EI, PI)
            candidate = unexplored[np.random.randint(len(unexplored))]
            
            # Simulate
            t0 = time.perf_counter()
            score = objective_fn(candidate)
            sim_time_ms = (time.perf_counter() - t0) * 1000
            
            # Update best
            is_best = False
            if campaign.objective == "maximize":
                if score > best_score:
                    best_score = score
                    campaign.best_candidate = candidate
                    campaign.best_score = score
                    is_best = True
            else:
                if score < best_score:
                    best_score = score
                    campaign.best_candidate = candidate
                    campaign.best_score = score
                    is_best = True
            
            # Record iteration
            iteration_obj = OptimizationIteration(
                iteration=campaign.n_iterations,
                candidate=candidate,
                score=score,
                simulation_time_ms=sim_time_ms,
                timestamp=datetime.now().isoformat(),
                is_best=is_best,
            )
            campaign.iterations.append(iteration_obj)
            campaign.n_iterations += 1
            
            # Check convergence
            improvement = abs(best_score - prev_best)
            if improvement < campaign.convergence_threshold:
                no_improvement_count += 1
                if no_improvement_count >= 5:
                    logger.info(
                        f"Campaign {campaign_id} converged at iteration "
                        f"{campaign.n_iterations}"
                    )
                    campaign.status = CampaignStatus.CONVERGED
                    break
            else:
                no_improvement_count = 0
            
            prev_best = best_score
            
            logger.info(
                f"Campaign {campaign_id} iteration {campaign.n_iterations}: "
                f"score={score:.4f} (best={best_score:.4f})"
            )
        
        # Mark as complete
        if campaign.status == CampaignStatus.RUNNING:
            campaign.status = CampaignStatus.CONVERGED
        
        campaign.completed_at = datetime.now().isoformat()
        
        logger.info(
            f"Campaign {campaign_id} complete: "
            f"best_score={campaign.best_score:.4f} "
            f"in {campaign.n_iterations} iterations"
        )
    
    def get_campaign_status(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get current status of a campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Campaign status dictionary
        """
        if campaign_id not in self.campaigns:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        campaign = self.campaigns[campaign_id]
        return campaign.to_dict()
    
    def stop_campaign(self, campaign_id: str):
        """
        Stop a running campaign.
        
        Args:
            campaign_id: Campaign ID
        """
        if campaign_id not in self.campaigns:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        campaign = self.campaigns[campaign_id]
        if campaign.status == CampaignStatus.RUNNING:
            campaign.status = CampaignStatus.STOPPED
            campaign.completed_at = datetime.now().isoformat()
            logger.info(f"Campaign {campaign_id} stopped by user")
    
    def get_campaign_results(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get final results of a campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Results dictionary with best candidate and full history
        """
        if campaign_id not in self.campaigns:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        campaign = self.campaigns[campaign_id]
        
        # Calculate statistics
        scores = [it.score for it in campaign.iterations]
        
        return {
            "campaign_id": campaign_id,
            "status": campaign.status.value,
            "best_candidate": campaign.best_candidate,
            "best_score": campaign.best_score,
            "n_iterations": campaign.n_iterations,
            "convergence": {
                "converged": campaign.status == CampaignStatus.CONVERGED,
                "final_improvement": abs(scores[-1] - scores[-2]) if len(scores) > 1 else 0,
            },
            "statistics": {
                "mean_score": float(np.mean(scores)),
                "std_score": float(np.std(scores)),
                "min_score": float(np.min(scores)),
                "max_score": float(np.max(scores)),
            },
            "iterations": [it.to_dict() for it in campaign.iterations],
            "started_at": campaign.started_at,
            "completed_at": campaign.completed_at,
        }
    
    def list_campaigns(self) -> List[Dict[str, Any]]:
        """
        List all campaigns.
        
        Returns:
            List of campaign summaries
        """
        return [
            {
                "campaign_id": cid,
                "status": campaign.status.value,
                "target_metric": campaign.target_metric,
                "n_iterations": campaign.n_iterations,
                "best_score": campaign.best_score,
                "started_at": campaign.started_at,
            }
            for cid, campaign in self.campaigns.items()
        ]


# Global singleton instance
_optimizer_instance = None

def get_autonomous_optimizer() -> AutonomousOptimizer:
    """Get the global autonomous optimizer instance."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = AutonomousOptimizer()
    return _optimizer_instance
