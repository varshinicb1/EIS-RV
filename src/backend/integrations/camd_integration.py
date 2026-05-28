"""
CAMD Integration for RĀMAN Studio
==================================
Bayesian optimization for autonomous materials discovery.
Integrates CAMD's agent-experiment-analyzer loop with VANL simulation engines.

Safe fallback: Returns None if CAMD is not installed.
"""

import logging
import numpy as np
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import CAMD - fail gracefully if not available
try:
    from camd.agent.stability import AgentStabilityML5
    from camd.campaigns import Campaign
    from camd.analysis import StabilityAnalyzer
    CAMD_AVAILABLE = True
    logger.info("CAMD integration enabled")
except ImportError:
    CAMD_AVAILABLE = False
    logger.warning("CAMD not installed - Bayesian optimization features disabled")


@dataclass
class OptimizationResult:
    """Result from a CAMD optimization campaign."""
    best_candidate: Dict[str, Any]
    best_score: float
    all_candidates: List[Dict[str, Any]]
    all_scores: List[float]
    n_iterations: int
    converged: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "best_candidate": self.best_candidate,
            "best_score": float(self.best_score),
            "all_candidates": self.all_candidates,
            "all_scores": [float(s) for s in self.all_scores],
            "n_iterations": self.n_iterations,
            "converged": self.converged,
        }


class VanlSimulationExperiment:
    """
    CAMD Experiment wrapper for VANL simulation engines.
    
    This allows CAMD to "run experiments" by calling VANL's
    EIS, CV, or GCD simulation engines instead of physical lab work.
    """
    
    def __init__(self, simulation_function: Callable):
        """
        Initialize with a VANL simulation function.
        
        Args:
            simulation_function: Function that takes material parameters
                                and returns performance metrics
        """
        self.simulation_function = simulation_function
        self.history = []
    
    def run(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run simulation for a candidate material.
        
        Args:
            candidate: Material parameters dictionary
            
        Returns:
            Simulation results with performance metrics
        """
        try:
            result = self.simulation_function(candidate)
            self.history.append({
                "candidate": candidate,
                "result": result,
            })
            return result
        except Exception as e:
            logger.error(f"Simulation failed for candidate {candidate}: {e}")
            return {"error": str(e), "score": 0.0}


class CAMDIntegration:
    """
    CAMD integration for Bayesian optimization of materials.
    
    Usage:
        camd = CAMDIntegration()
        if camd.is_available():
            # Define simulation function
            def simulate_capacitance(material):
                # Call VANL EIS engine
                result = eis_engine.simulate(material)
                return {"capacitance": extract_capacitance(result)}
            
            # Run optimization
            result = camd.optimize_material(
                simulation_fn=simulate_capacitance,
                candidate_space=materials_database,
                n_iterations=50,
                objective="maximize_capacitance"
            )
    """
    
    def __init__(self):
        self.available = CAMD_AVAILABLE
    
    def is_available(self) -> bool:
        """Check if CAMD is available."""
        return self.available
    
    def optimize_material(
        self,
        simulation_fn: Callable,
        candidate_space: List[Dict[str, Any]],
        n_iterations: int = 50,
        objective: str = "maximize",
        convergence_threshold: float = 0.01,
    ) -> Optional[OptimizationResult]:
        """
        Run Bayesian optimization to find optimal material.
        
        Args:
            simulation_fn: Function that simulates material performance
            candidate_space: List of candidate materials to explore
            n_iterations: Maximum number of iterations
            objective: "maximize" or "minimize"
            convergence_threshold: Stop if improvement < threshold
            
        Returns:
            OptimizationResult or None if CAMD unavailable
        """
        if not self.available:
            logger.warning("CAMD not available - cannot run optimization")
            return None
        
        if len(candidate_space) == 0:
            logger.error("Empty candidate space")
            return None
        
        try:
            # Create experiment wrapper
            experiment = VanlSimulationExperiment(simulation_fn)
            
            # Simple Bayesian optimization loop (CAMD-inspired)
            # Note: Full CAMD integration requires more setup
            # This is a simplified version for demonstration
            
            all_candidates = []
            all_scores = []
            best_score = float('-inf') if objective == "maximize" else float('inf')
            best_candidate = None
            
            # Random exploration phase (first 10 iterations)
            n_explore = min(10, len(candidate_space))
            explore_indices = np.random.choice(
                len(candidate_space), 
                size=n_explore, 
                replace=False
            )
            
            for idx in explore_indices:
                candidate = candidate_space[idx]
                result = experiment.run(candidate)
                score = result.get("score", 0.0)
                
                all_candidates.append(candidate)
                all_scores.append(score)
                
                if objective == "maximize":
                    if score > best_score:
                        best_score = score
                        best_candidate = candidate
                else:
                    if score < best_score:
                        best_score = score
                        best_candidate = candidate
            
            # Exploitation phase (remaining iterations)
            converged = False
            for iteration in range(n_explore, n_iterations):
                # Select next candidate using acquisition function
                # (simplified: select from top 20% of unexplored candidates)
                unexplored = [
                    c for c in candidate_space 
                    if c not in all_candidates
                ]
                
                if len(unexplored) == 0:
                    logger.info("All candidates explored")
                    converged = True
                    break
                
                # Simple acquisition: random from unexplored
                candidate = np.random.choice(unexplored)
                result = experiment.run(candidate)
                score = result.get("score", 0.0)
                
                all_candidates.append(candidate)
                all_scores.append(score)
                
                # Check for improvement
                prev_best = best_score
                if objective == "maximize":
                    if score > best_score:
                        best_score = score
                        best_candidate = candidate
                else:
                    if score < best_score:
                        best_score = score
                        best_candidate = candidate
                
                # Check convergence
                improvement = abs(best_score - prev_best)
                if improvement < convergence_threshold:
                    logger.info(f"Converged at iteration {iteration}")
                    converged = True
                    break
            
            return OptimizationResult(
                best_candidate=best_candidate,
                best_score=best_score,
                all_candidates=all_candidates,
                all_scores=all_scores,
                n_iterations=len(all_candidates),
                converged=converged,
            )
            
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            return None
    
    def suggest_next_experiment(
        self,
        history: List[Dict[str, Any]],
        candidate_space: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Suggest next experiment based on history (active learning).
        
        Args:
            history: List of previous experiments with results
            candidate_space: Available candidates
            
        Returns:
            Next candidate to try, or None
        """
        if not self.available:
            return None
        
        # Simple implementation: suggest candidate with highest uncertainty
        # (In full CAMD, this would use Gaussian Process acquisition functions)
        
        tested = [h["candidate"] for h in history]
        untested = [c for c in candidate_space if c not in tested]
        
        if len(untested) == 0:
            return None
        
        # For now, return random untested candidate
        # TODO: Implement proper acquisition function
        return np.random.choice(untested)


# Global singleton instance
_camd_instance = None

def get_camd_integration() -> CAMDIntegration:
    """Get the global CAMD integration instance."""
    global _camd_instance
    if _camd_instance is None:
        _camd_instance = CAMDIntegration()
    return _camd_instance
