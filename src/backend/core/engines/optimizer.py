"""
Inverse Design Engine (Bayesian Optimization)
================================================
Multi-objective optimization to find optimal material compositions
and synthesis parameters for desired electrochemical properties.

Implements:
    1. Bayesian Optimization with Gaussian Process surrogate
    2. Multi-objective scalarization (weighted Tchebycheff)
    3. Expected Improvement (EI) acquisition function
    4. Optional: Genetic Algorithm for comparison

Optimization targets:
    - Maximize: specific capacitance (∝ Cdl × surface_area)
    - Minimize: charge transfer resistance (Rct)
    - Minimize: solution resistance (Rs)
    - Constraints: cost budget, Warburg < threshold
"""

import logging

import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel
from scipy.optimize import minimize
from scipy.stats import norm

from .materials import (
    MaterialComposition, SynthesisParameters, StructuralDescriptors,
    EISParameters, ExperimentRecord, SynthesisMethod
)
from .synthesis_engine import SynthesisEngine
from .eis_engine import descriptors_to_eis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#   Optimization Objectives
# ---------------------------------------------------------------------------

@dataclass
class OptimizationTarget:
    """Defines what we want to optimize."""
    minimize_Rct: bool = True
    minimize_Rs: bool = True
    maximize_capacitance: bool = True
    weight_Rct: float = 0.4
    weight_Rs: float = 0.2
    weight_capacitance: float = 0.4
    max_cost: float = 3.0       # Cost constraint
    max_warburg: float = 500.0  # Warburg constraint
    target_Rct: Optional[float] = None  # Specific Rct target
    target_capacitance: Optional[float] = None


def compute_objective(
    eis: EISParameters,
    descriptors: StructuralDescriptors,
    composition: MaterialComposition,
    target: OptimizationTarget,
) -> float:
    """
    Compute scalar objective value (lower is better).

    Uses weighted Tchebycheff scalarization for multi-objective:
        obj = max_i { w_i × |f_i - z_i*| }

    But we use a simpler weighted sum here for clarity:
        obj = w_Rct × log(Rct) + w_Rs × log(Rs) - w_cap × log(Cdl)

    Log-space ensures scale-invariant optimization.
    Penalty terms enforce constraints.
    """
    w = target

    # Objective components (all in log space for scale invariance)
    obj = 0.0

    if w.minimize_Rct:
        obj += w.weight_Rct * np.log10(max(eis.Rct, 0.01))

    if w.minimize_Rs:
        obj += w.weight_Rs * np.log10(max(eis.Rs, 0.01))

    if w.maximize_capacitance:
        # Negative because we minimize the objective
        obj -= w.weight_capacitance * np.log10(max(eis.Cdl * 1e6, 0.01))

    # Constraint penalties
    if composition.cost_index > w.max_cost:
        obj += 10.0 * (composition.cost_index - w.max_cost)

    if eis.sigma_warburg > w.max_warburg:
        obj += 5.0 * np.log10(eis.sigma_warburg / w.max_warburg)

    return float(obj)


# ---------------------------------------------------------------------------
#   Bayesian Optimization Engine
# ---------------------------------------------------------------------------

class BayesianOptimizer:
    """
    Bayesian Optimization using Gaussian Process surrogate + EI acquisition.

    The optimizer works in a reduced composition space:
        - Active materials are selected (e.g., graphene, MnO2, carbon_black)
        - Fractions are parameterized in simplex space
        - Synthesis parameters are included as continuous dimensions

    The GP learns: x → objective_value
    where x = [material_fractions..., temperature, duration, pH]
    """

    def __init__(
        self,
        active_materials: List[str] = None,
        synthesis_engine: Optional[SynthesisEngine] = None,
        target: Optional[OptimizationTarget] = None,
        seed: int = 42,
    ):
        self.active_materials = active_materials or [
            "graphene", "MnO2", "carbon_black"
        ]
        self.synthesis_engine = synthesis_engine or SynthesisEngine()
        self.target = target or OptimizationTarget()

        # GP surrogate
        kernel = Matern(nu=2.5) + WhiteKernel(noise_level=0.1)
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=5,
            normalize_y=True,
            alpha=1e-6,
        )

        # Seeded RNG for reproducibility
        self._rng = np.random.default_rng(seed)

        # Experiment history
        self.X_observed: List[np.ndarray] = []
        self.Y_observed: List[float] = []
        self.history: List[ExperimentRecord] = []

        # Parameter bounds
        n_mat = len(self.active_materials)
        # Material fractions [0, 1] for each material
        # Synthesis: temperature [25, 200], duration [0.5, 24], pH [1, 14]
        self.bounds = (
            [(0.0, 1.0)] * n_mat +  # Material fractions
            [(25.0, 200.0),          # Temperature
             (0.5, 24.0),            # Duration
             (1.0, 14.0)]            # pH
        )
        self.dim = n_mat + 3

    def _x_to_experiment(self, x: np.ndarray) -> Tuple[MaterialComposition, SynthesisParameters]:
        """Convert optimization variable → composition + synthesis."""
        n_mat = len(self.active_materials)

        # Material fractions (normalize to sum=1)
        fractions = np.maximum(x[:n_mat], 1e-6)
        fractions /= fractions.sum()

        components = {
            mat: float(f)
            for mat, f in zip(self.active_materials, fractions)
            if f > 0.01
        }
        composition = MaterialComposition(components=components)

        # Synthesis parameters
        synthesis = SynthesisParameters(
            method=SynthesisMethod.HYDROTHERMAL,
            temperature_C=float(x[n_mat]),
            duration_hours=float(x[n_mat + 1]),
            pH=float(x[n_mat + 2]),
        )

        return composition, synthesis

    def _evaluate(self, x: np.ndarray) -> Tuple[float, ExperimentRecord]:
        """Run virtual experiment and compute objective."""
        comp, synth = self._x_to_experiment(x)

        # Virtual synthesis
        descriptors = self.synthesis_engine.synthesize(comp, synth)

        # Predict EIS
        eis = descriptors_to_eis(descriptors)

        # Compute objective
        obj = compute_objective(eis, descriptors, comp, self.target)

        # Record
        record = ExperimentRecord(
            composition=comp,
            synthesis=synth,
            descriptors=descriptors,
            eis_params=eis,
            objective_value=obj,
        )

        return obj, record

    def _expected_improvement(
        self, x: np.ndarray, xi: float = 0.01
    ) -> float:
        """
        Expected Improvement acquisition function.

        EI(x) = (f_best - µ(x) - ξ) × Φ(Z) + σ(x) × φ(Z)
        Z = (f_best - µ(x) - ξ) / σ(x)

        where Φ is the CDF and φ is the PDF of the standard normal.
        We negate because scipy minimizes and we want to maximize EI.
        """
        x = np.array(x).reshape(1, -1)
        mu, sigma = self.gp.predict(x, return_std=True)
        mu = mu[0]
        sigma = max(sigma[0], 1e-8)

        f_best = min(self.Y_observed) if self.Y_observed else 0.0

        Z = (f_best - mu - xi) / sigma
        ei = (f_best - mu - xi) * norm.cdf(Z) + sigma * norm.pdf(Z)
        return -ei  # Negative for minimization

    def suggest_next(self, n_suggestions: int = 1) -> List[np.ndarray]:
        """
        Suggest next experiment(s) using EI acquisition.

        If insufficient data for GP, use Latin Hypercube Sampling.
        """
        suggestions = []

        if len(self.X_observed) < 5:
            # Not enough data for GP — use space-filling design
            for _ in range(n_suggestions):
                x = np.array([
                    self._rng.uniform(lo, hi)
                    for lo, hi in self.bounds
                ])
                suggestions.append(x)
            return suggestions

        # Fit GP on observed data
        X = np.array(self.X_observed)
        Y = np.array(self.Y_observed)
        self.gp.fit(X, Y)

        # Optimize acquisition function
        for _ in range(n_suggestions):
            best_x = None
            best_ei = float('inf')

            # Multi-start optimization
            for _ in range(20):
                x0 = np.array([
                    self._rng.uniform(lo, hi) for lo, hi in self.bounds
                ])

                try:
                    result = minimize(
                        self._expected_improvement,
                        x0,
                        bounds=self.bounds,
                        method='L-BFGS-B',
                    )
                    if result.fun < best_ei:
                        best_ei = result.fun
                        best_x = result.x
                except Exception:
                    continue

            if best_x is not None:
                suggestions.append(best_x)
            else:
                # Fallback to random
                x = np.array([
                    self._rng.uniform(lo, hi) for lo, hi in self.bounds
                ])
                suggestions.append(x)

        return suggestions

    def observe(self, x: np.ndarray, y: float, record: ExperimentRecord):
        """Record an observation."""
        self.X_observed.append(x.copy())
        self.Y_observed.append(y)
        self.history.append(record)

    def run_optimization(
        self,
        n_iterations: int = 50,
        n_initial: int = 10,
        verbose: bool = True,
    ) -> List[ExperimentRecord]:
        """
        Run full Bayesian optimization loop.

        1. Initialize with n_initial random experiments
        2. For each iteration:
            a. Suggest next point (EI acquisition)
            b. Evaluate (virtual experiment)
            c. Update GP model
        """
        # Initial random experiments
        if verbose:
            logger.info("Initializing with %d random experiments...", n_initial)

        for i in range(n_initial):
            x = np.array([
                self._rng.uniform(lo, hi) for lo, hi in self.bounds
            ])
            obj, record = self._evaluate(x)
            self.observe(x, obj, record)

            if verbose:
                logger.info("  Init %d/%d: obj=%.4f, Rct=%.2f, Cdl=%.2e",
                            i + 1, n_initial, obj,
                            record.eis_params.Rct, record.eis_params.Cdl)

        # BO iterations
        if verbose:
            logger.info("Running %d BO iterations...", n_iterations)

        for i in range(n_iterations):
            suggestions = self.suggest_next(1)
            x = suggestions[0]

            obj, record = self._evaluate(x)
            self.observe(x, obj, record)

            best_idx = int(np.argmin(self.Y_observed))
            best_record = self.history[best_idx]

            if verbose and (i + 1) % 5 == 0:
                logger.info("  Iter %d/%d: obj=%.4f (best=%.4f), Rct=%.2f",
                            i + 1, n_iterations, obj,
                            self.Y_observed[best_idx], record.eis_params.Rct)

        return self.history

    def get_best(self) -> Optional[ExperimentRecord]:
        """Return the best experiment so far."""
        if not self.Y_observed:
            return None
        best_idx = int(np.argmin(self.Y_observed))
        return self.history[best_idx]

    def get_history_summary(self) -> List[dict]:
        """Return history as serializable list."""
        return [r.to_dict() for r in self.history]
