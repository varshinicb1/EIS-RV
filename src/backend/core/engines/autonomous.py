"""
Autonomous Experiment Loop
=============================
Manage the iterative Propose → Simulate → Evaluate → Improve cycle.

This module orchestrates the entire virtual lab workflow:
    1. Propose: Use optimizer to suggest next material composition
    2. Simulate: Run virtual synthesis + EIS prediction
    3. Evaluate: Compute objective function
    4. Improve: Update surrogate model and suggest better experiments

The loop maintains persistent state (experiment history) and
supports pausing/resuming optimization campaigns.
"""

import logging

import json
import os
import time
from typing import List, Optional, Dict
from dataclasses import dataclass, field

from .materials import (
    MaterialComposition, SynthesisParameters, StructuralDescriptors,
    EISParameters, ExperimentRecord, SynthesisMethod
)
from .synthesis_engine import SynthesisEngine
from .eis_engine import descriptors_to_eis, simulate_eis
from .optimizer import BayesianOptimizer, OptimizationTarget, compute_objective

logger = logging.getLogger(__name__)

__all__ = ["AutonomousLab", "LabConfig"]


@dataclass
class LabConfig:
    """Configuration for an autonomous lab session."""
    active_materials: List[str] = field(
        default_factory=lambda: ["graphene", "MnO2", "carbon_black"]
    )
    n_initial: int = 10
    n_iterations: int = 50
    target: OptimizationTarget = field(default_factory=OptimizationTarget)
    save_path: str = "lab_session"


class AutonomousLab:
    """
    Virtual Autonomous Nanomaterials Lab.

    Manages the closed-loop optimization of electrode materials:
        propose → synthesize → characterize → optimize → repeat

    Usage:
        lab = AutonomousLab(config)
        lab.initialize()

        # Run single step
        record = lab.step()

        # Or run N steps
        records = lab.run(n_steps=20)

        # Get best result
        best = lab.get_best()
    """

    def __init__(self, config: Optional[LabConfig] = None):
        self.config = config or LabConfig()
        self.synthesis_engine = SynthesisEngine()
        self.optimizer = BayesianOptimizer(
            active_materials=self.config.active_materials,
            synthesis_engine=self.synthesis_engine,
            target=self.config.target,
        )
        self.history: List[ExperimentRecord] = []
        self.iteration = 0
        self._initialized = False

    def initialize(self, n_initial: Optional[int] = None):
        """
        Initialize with random experiments to seed the GP surrogate.
        """
        n = n_initial or self.config.n_initial

        for i in range(n):
            x = self.optimizer.suggest_next(1)[0]
            obj, record = self.optimizer._evaluate(x)
            self.optimizer.observe(x, obj, record)
            self.history.append(record)
            self.iteration += 1

        self._initialized = True

    def step(self) -> ExperimentRecord:
        """
        Run a single optimization step:
            1. Suggest next experiment (BO with EI)
            2. Run virtual experiment
            3. Record observation
            4. Return result
        """
        if not self._initialized:
            self.initialize()

        suggestions = self.optimizer.suggest_next(1)
        x = suggestions[0]

        obj, record = self.optimizer._evaluate(x)
        self.optimizer.observe(x, obj, record)
        self.history.append(record)
        self.iteration += 1

        return record

    def run(self, n_steps: int = 10) -> List[ExperimentRecord]:
        """Run multiple optimization steps."""
        records = []
        for _ in range(n_steps):
            record = self.step()
            records.append(record)
        return records

    def predict_material(
        self,
        composition: Dict[str, float],
        synthesis: Optional[Dict] = None,
    ) -> dict:
        """
        One-shot prediction: predict EIS for a given material.

        Args:
            composition: Material ratios, e.g., {"graphene": 0.6, "MnO2": 0.4}
            synthesis: Optional synthesis params dict

        Returns:
            Dictionary with descriptors, EIS params, and plot data
        """
        comp = MaterialComposition(components=composition)

        if synthesis:
            synth = SynthesisParameters(
                method=SynthesisMethod(synthesis.get("method", "hydrothermal")),
                temperature_C=synthesis.get("temperature_C", 120),
                duration_hours=synthesis.get("duration_hours", 6),
                pH=synthesis.get("pH", 7),
            )
        else:
            synth = SynthesisParameters()

        descriptors = self.synthesis_engine.synthesize(comp, synth)
        eis_params = descriptors_to_eis(descriptors)
        eis_result = simulate_eis(eis_params)

        return {
            "composition": comp.to_dict(),
            "synthesis": synth.to_dict(),
            "descriptors": descriptors.to_dict(),
            "eis_params": eis_params.to_dict(),
            "eis_data": eis_result.to_dict(),
        }

    def optimize_material(
        self,
        materials: List[str],
        n_iterations: int = 30,
        target: Optional[Dict] = None,
    ) -> dict:
        """
        Run optimization for specified materials.

        Args:
            materials: List of material names
            n_iterations: Number of BO iterations
            target: Optimization target overrides

        Returns:
            Best result and optimization history
        """
        opt_target = OptimizationTarget()
        if target:
            if "weight_Rct" in target:
                opt_target.weight_Rct = target["weight_Rct"]
            if "weight_Rs" in target:
                opt_target.weight_Rs = target["weight_Rs"]
            if "weight_capacitance" in target:
                opt_target.weight_capacitance = target["weight_capacitance"]
            if "max_cost" in target:
                opt_target.max_cost = target["max_cost"]

        optimizer = BayesianOptimizer(
            active_materials=materials,
            synthesis_engine=self.synthesis_engine,
            target=opt_target,
        )

        # Initialize
        for _ in range(5):
            x = optimizer.suggest_next(1)[0]
            obj, record = optimizer._evaluate(x)
            optimizer.observe(x, obj, record)

        # Optimize
        for _ in range(n_iterations):
            x = optimizer.suggest_next(1)[0]
            obj, record = optimizer._evaluate(x)
            optimizer.observe(x, obj, record)

        best = optimizer.get_best()
        best_eis = simulate_eis(best.eis_params)

        return {
            "best": best.to_dict(),
            "best_eis_data": best_eis.to_dict(),
            "history": [r.to_dict() for r in optimizer.history],
            "convergence": [float(y) for y in optimizer.Y_observed],
        }

    def get_best(self) -> Optional[ExperimentRecord]:
        """Return the best experiment from history."""
        return self.optimizer.get_best()

    def get_history(self) -> List[dict]:
        """Return experiment history."""
        return [r.to_dict() for r in self.history]

    def save_session(self, filepath: Optional[str] = None):
        """Save lab session to disk."""
        path = filepath or f"{self.config.save_path}.json"
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        data = {
            "config": {
                "active_materials": self.config.active_materials,
                "n_initial": self.config.n_initial,
                "n_iterations": self.config.n_iterations,
            },
            "iteration": self.iteration,
            "history": self.get_history(),
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
