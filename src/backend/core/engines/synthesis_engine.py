"""
Virtual Synthesis Engine
=========================
Surrogate model that maps (composition + synthesis parameters) →
structural descriptors.

This emulates the physical/chemical transformations occurring during
nanomaterial synthesis. The model captures known relationships:

    1. Temperature →↑ crystallinity (Arrhenius-like kinetics)
    2. Duration →↑ particle size (Ostwald ripening: r³ ∝ t)
    3. Graphene content →↑ conductivity (percolation network)
    4. Metal oxide content →↑ pseudocapacitance but ↓ conductivity
    5. Porosity depends on synthesis method and template agents
    6. Surface area ∝ 1/particle_size (for spherical particles)

Two modes:
    1. Physics-heuristic: Analytical approximations (always available)
    2. ML-surrogate: Trained neural network (when model is available)
"""

import numpy as np
from typing import Optional
from .materials import (
    MaterialComposition, SynthesisParameters, StructuralDescriptors,
    SynthesisMethod, MATERIAL_DATABASE
)


class SynthesisEngine:
    """
    Virtual synthesis engine that predicts structural descriptors
    from composition and synthesis parameters.
    """

    def __init__(self, ml_model=None):
        """
        Args:
            ml_model: Optional trained ML model with .predict(X) method.
                      If None, uses physics-heuristic model.
        """
        self._ml_model = ml_model

    def synthesize(
        self,
        composition: MaterialComposition,
        synthesis: SynthesisParameters,
    ) -> StructuralDescriptors:
        """
        Simulate synthesis and return predicted structural descriptors.

        This is the core surrogate function:
            f(composition, synthesis_params) → structural_descriptors
        """
        if self._ml_model is not None:
            return self._predict_ml(composition, synthesis)

        return self._predict_heuristic(composition, synthesis)

    def _predict_heuristic(
        self,
        comp: MaterialComposition,
        synth: SynthesisParameters,
    ) -> StructuralDescriptors:
        """
        Physics-informed heuristic model.

        Each descriptor is estimated from composition-weighted base
        properties, modified by synthesis conditions.

        These are NOT random — they follow established materials
        science principles with approximate quantitative relationships.
        """
        # ─────── Base properties from composition ───────

        # Effective conductivity (logarithmic mixing for percolation)
        base_conductivity = comp.effective_conductivity

        # Weighted theoretical surface area
        base_sa = comp.weighted_surface_area

        # Check for pseudocapacitive components
        has_pseudo = comp.has_pseudocapacitive

        # ─────── Synthesis method effects ───────

        method = synth.method
        temp = synth.temperature_C
        duration = synth.duration_hours

        # Method-specific modifiers
        method_effects = {
            SynthesisMethod.HYDROTHERMAL: {
                "crystallinity_boost": 0.3,
                "porosity_base": 0.35,
                "size_factor": 1.0,
            },
            SynthesisMethod.ELECTRODEPOSITION: {
                "crystallinity_boost": 0.15,
                "porosity_base": 0.25,
                "size_factor": 0.6,
            },
            SynthesisMethod.DROP_CASTING: {
                "crystallinity_boost": 0.0,
                "porosity_base": 0.5,
                "size_factor": 2.0,
            },
            SynthesisMethod.SPIN_COATING: {
                "crystallinity_boost": 0.05,
                "porosity_base": 0.15,
                "size_factor": 0.8,
            },
            SynthesisMethod.CVD: {
                "crystallinity_boost": 0.4,
                "porosity_base": 0.1,
                "size_factor": 0.3,
            },
            SynthesisMethod.SOLVOTHERMAL: {
                "crystallinity_boost": 0.25,
                "porosity_base": 0.4,
                "size_factor": 0.9,
            },
            SynthesisMethod.SOL_GEL: {
                "crystallinity_boost": 0.1,
                "porosity_base": 0.55,
                "size_factor": 0.7,
            },
            SynthesisMethod.COPRECIPITATION: {
                "crystallinity_boost": 0.05,
                "porosity_base": 0.45,
                "size_factor": 1.2,
            },
        }

        effects = method_effects.get(method, method_effects[SynthesisMethod.DROP_CASTING])

        # ─────── Crystallinity ───────
        # Increases with temperature (Arrhenius-like)
        # Increases with duration (kinetic)
        T_ref = 100.0  # Reference temperature
        crystallinity = 0.3 + effects["crystallinity_boost"]
        crystallinity += 0.3 * (1 - np.exp(-temp / T_ref))  # Temperature effect
        crystallinity += 0.1 * (1 - np.exp(-duration / 6.0))  # Duration effect
        crystallinity = np.clip(crystallinity, 0.1, 0.98)

        # ─────── Particle Size ───────
        # Ostwald ripening: particle size ∝ t^(1/3)
        # Higher temperature accelerates growth
        base_size = 10.0 * effects["size_factor"]  # nm
        size_growth = base_size * (duration / 6.0) ** (1.0 / 3.0)
        temp_acceleration = 1.0 + 2.0 * (temp / 200.0) ** 2
        particle_size = base_size + size_growth * temp_acceleration

        # Add noise proportional to the measurement uncertainty
        particle_size = np.clip(particle_size, 2.0, 500.0)

        # ─────── Surface Area ───────
        # For spherical particles: SA = 6/(ρ_eff * d) [m²/g]
        # d in meters, ρ in kg/m³ → SA in m²/kg → divide by 1000 for m²/g
        rho_eff = 2000  # kg/m³ effective density (weighted average)
        d_m = particle_size * 1e-9  # nm → m
        sa_spherical = 6.0 / (rho_eff * d_m) / 1000  # m²/kg → m²/g
        # Blend with composition-weighted theoretical SA
        sa_blend_factor = 0.3 + 0.7 * effects["porosity_base"]
        surface_area = (0.4 * sa_spherical + 0.6 * base_sa) * sa_blend_factor
        surface_area = np.clip(surface_area, 5.0, 3000.0)

        # ─────── Porosity ───────
        # Depends on synthesis method + composition + conditions
        porosity = effects["porosity_base"]
        # High temperature can close pores (sintering)
        porosity -= 0.1 * (temp / 200.0) ** 2
        # Longer synthesis can fill pores
        porosity -= 0.05 * (duration / 24.0)
        # Carbon materials tend to maintain porosity
        carbon_frac = sum(
            comp.components.get(m, 0) for m in
            ["graphene", "reduced_graphene_oxide", "carbon_black", "CNT"]
        )
        porosity += 0.1 * carbon_frac
        porosity = np.clip(porosity, 0.05, 0.85)

        # ─────── Conductivity ───────
        # Modified by crystallinity and synthesis conditions
        conductivity = base_conductivity
        conductivity *= (0.3 + 0.7 * crystallinity)  # Crystallinity effect
        # Higher porosity reduces effective conductivity (Bruggeman)
        conductivity *= (1 - porosity) ** 1.5
        conductivity = np.clip(conductivity, 1e-6, 1e7)

        # ─────── Defect Density ───────
        # Decreases with crystallinity and temperature
        # Increases with rapid synthesis and low pH
        defect_density = 0.3
        defect_density -= 0.2 * crystallinity
        defect_density += 0.1 * (1 - temp / 200.0)
        defect_density += 0.1 * abs(synth.pH - 7.0) / 7.0  # Extreme pH creates defects
        defect_density = np.clip(defect_density, 0.01, 0.6)

        # ─────── Layer Thickness ───────
        # For thin film synthesis, depends on method and duration
        thickness = 50.0  # Base nm
        if method == SynthesisMethod.SPIN_COATING:
            thickness = 20 + 5 * synth.concentration_mM / 10
        elif method == SynthesisMethod.ELECTRODEPOSITION:
            thickness = 30 + 50 * duration  # Linear growth
        elif method == SynthesisMethod.CVD:
            thickness = 10 + 20 * duration
        else:
            thickness = 50 + 100 * (synth.concentration_mM / 50) * duration

        thickness = np.clip(thickness, 5.0, 5000.0)

        return StructuralDescriptors(
            porosity=float(porosity),
            surface_area_m2_g=float(surface_area),
            conductivity_S_m=float(conductivity),
            defect_density=float(defect_density),
            layer_thickness_nm=float(thickness),
            crystallinity=float(crystallinity),
            particle_size_nm=float(particle_size),
        )

    def _predict_ml(
        self,
        comp: MaterialComposition,
        synth: SynthesisParameters,
    ) -> StructuralDescriptors:
        """
        ML surrogate prediction.
        Concatenates composition vector + synthesis vector → model → descriptors.
        """
        X = np.concatenate([comp.to_vector(), synth.to_vector()]).reshape(1, -1)
        outputs = self._ml_model.predict(X)[0]

        # Decode from model output space
        return StructuralDescriptors(
            porosity=float(np.clip(outputs[0], 0.01, 0.95)),
            surface_area_m2_g=float(np.clip(10 ** (outputs[1] * 4), 5, 3000)),
            conductivity_S_m=float(np.clip(10 ** (outputs[2] * 7), 1e-6, 1e7)),
            defect_density=float(np.clip(outputs[3], 0.01, 0.6)),
            layer_thickness_nm=float(np.clip(10 ** (outputs[4] * 4), 5, 5000)),
            crystallinity=float(np.clip(outputs[5], 0.1, 0.98)),
            particle_size_nm=float(np.clip(10 ** (outputs[6] * 3), 2, 500)),
        )

    def set_ml_model(self, model):
        """Hot-swap the ML surrogate model."""
        self._ml_model = model
