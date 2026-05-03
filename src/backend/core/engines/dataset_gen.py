"""
Synthetic Dataset Generator
==============================
Generates physics-informed training data for ML surrogate models.

The generated data is NOT random — it follows established materials
science relationships to ensure the trained models learn physically
meaningful patterns.

Two datasets are generated:
    1. Synthesis dataset: (composition, synthesis_params) → structural_descriptors
    2. EIS dataset: structural_descriptors → EIS_parameters

The generator samples the parameter space comprehensively, with
extra density in experimentally relevant regions (e.g., Graphene+MnO2).
"""

import logging
import numpy as np
import json
import os
from typing import List, Tuple, Dict
from .materials import (
    MaterialComposition, SynthesisParameters, StructuralDescriptors,
    EISParameters, SynthesisMethod, Solvent, MATERIAL_DATABASE
)
from .synthesis_engine import SynthesisEngine
from .eis_engine import descriptors_to_eis

logger = logging.getLogger(__name__)

__all__ = [
    "generate_synthesis_dataset",
    "generate_eis_dataset",
    "generate_and_save_datasets",
]


def generate_synthesis_dataset(
    n_samples: int = 5000,
    seed: int = 42,
    noise_level: float = 0.05,
) -> Tuple[np.ndarray, np.ndarray, List[dict]]:
    """
    Generate training data: (composition + synthesis) → structural descriptors.

    Sampling strategy:
        - 40% uniform random compositions
        - 30% binary/ternary material blends (common in literature)
        - 30% focused on graphene-based composites

    Returns:
        X: Input features (n_samples, n_features)
        Y: Output descriptors (n_samples, 7)
        records: List of full experiment dictionaries
    """
    rng = np.random.default_rng(seed)
    engine = SynthesisEngine()

    material_keys = sorted(MATERIAL_DATABASE.keys())
    n_materials = len(material_keys)

    X_list = []
    Y_list = []
    records = []

    methods = list(SynthesisMethod)
    n_methods = len(methods)

    for i in range(n_samples):
        # === Sample composition ===
        if i < n_samples * 0.4:
            # Uniform random with Dirichlet distribution
            n_active = rng.integers(1, min(5, n_materials + 1))
            active_idx = rng.choice(n_materials, n_active, replace=False)
            alphas = rng.uniform(0.5, 3.0, n_active)
            fractions = rng.dirichlet(alphas)
            components = {material_keys[idx]: float(f)
                          for idx, f in zip(active_idx, fractions)}

        elif i < n_samples * 0.7:
            # Binary/ternary blends
            n_active = rng.integers(2, 4)
            active_idx = rng.choice(n_materials, n_active, replace=False)
            fractions = rng.dirichlet(np.ones(n_active) * 2.0)
            components = {material_keys[idx]: float(f)
                          for idx, f in zip(active_idx, fractions)}

        else:
            # Graphene-based composites (most common in EIS literature)
            carbon_mat = rng.choice(["graphene", "reduced_graphene_oxide", "CNT"])
            carbon_frac = rng.uniform(0.3, 0.8)

            remaining = 1.0 - carbon_frac
            n_others = rng.integers(1, 3)
            other_mats = [m for m in material_keys if m != carbon_mat]
            other_idx = rng.choice(len(other_mats), n_others, replace=False)
            other_fracs = rng.dirichlet(np.ones(n_others)) * remaining

            components = {carbon_mat: float(carbon_frac)}
            for idx, f in zip(other_idx, other_fracs):
                components[other_mats[idx]] = float(f)

        composition = MaterialComposition(components=components)

        # === Sample synthesis parameters ===
        method = methods[int(rng.integers(0, n_methods))]
        temp = float(rng.uniform(25, 200))
        duration = float(rng.uniform(0.5, 24))
        pH = float(rng.uniform(1, 14))
        concentration = float(rng.uniform(5, 100))

        synthesis = SynthesisParameters(
            method=method,
            temperature_C=temp,
            duration_hours=duration,
            pH=pH,
            concentration_mM=concentration,
        )

        # === Generate descriptors using heuristic model ===
        descriptors = engine.synthesize(composition, synthesis)

        # Add controlled noise (measurement uncertainty)
        if noise_level > 0:
            descriptors.porosity += float(rng.normal(0, noise_level * 0.1))
            descriptors.porosity = float(np.clip(descriptors.porosity, 0.01, 0.95))

            sa_noise = float(rng.normal(0, noise_level * descriptors.surface_area_m2_g * 0.1))
            descriptors.surface_area_m2_g = float(max(5.0, descriptors.surface_area_m2_g + sa_noise))

            cond_log_noise = float(rng.normal(0, noise_level * 0.5))
            descriptors.conductivity_S_m = float(np.clip(
                descriptors.conductivity_S_m * (10 ** cond_log_noise), 1e-6, 1e7
            ))

            descriptors.crystallinity += float(rng.normal(0, noise_level * 0.05))
            descriptors.crystallinity = float(np.clip(descriptors.crystallinity, 0.1, 0.98))

        # === Build feature vectors ===
        x = np.concatenate([composition.to_vector(material_keys), synthesis.to_vector()])
        y = descriptors.to_vector()

        X_list.append(x)
        Y_list.append(y)
        records.append({
            "composition": composition.to_dict(),
            "synthesis": synthesis.to_dict(),
            "descriptors": descriptors.to_dict(),
        })

    return np.array(X_list), np.array(Y_list), records


def generate_eis_dataset(
    n_samples: int = 5000,
    seed: int = 123,
    noise_level: float = 0.03,
) -> Tuple[np.ndarray, np.ndarray, List[dict]]:
    """
    Generate training data: structural_descriptors → EIS parameters.

    Uses the physics-informed descriptors_to_eis() function as ground truth,
    then adds realistic noise to simulate measurement variability.

    Returns:
        X: Structural descriptor vectors (n_samples, 7)
        Y: EIS parameter vectors (n_samples, 5)
        records: Full experiment records
    """
    rng = np.random.default_rng(seed)

    X_list = []
    Y_list = []
    records = []

    for i in range(n_samples):
        # Sample structural descriptors with reasonable distributions
        porosity = float(rng.beta(2, 3))  # Peaked around 0.3-0.4
        surface_area = float(10 ** rng.uniform(1, 3.5))  # 10 - 3000 m²/g
        conductivity = float(10 ** rng.uniform(-3, 6))  # 0.001 - 1M S/m
        defect_density = float(rng.beta(2, 5))  # Peaked around 0.1-0.2
        thickness = float(10 ** rng.uniform(1, 3.5))  # 10 - 3000 nm
        crystallinity = float(rng.beta(3, 2))  # Peaked around 0.5-0.7
        particle_size = float(10 ** rng.uniform(0.5, 2.5))  # 3 - 300 nm

        descriptors = StructuralDescriptors(
            porosity=porosity,
            surface_area_m2_g=surface_area,
            conductivity_S_m=conductivity,
            defect_density=defect_density,
            layer_thickness_nm=thickness,
            crystallinity=crystallinity,
            particle_size_nm=particle_size,
        )

        # Get physics-based EIS parameters
        eis = descriptors_to_eis(descriptors)

        # Add measurement noise
        if noise_level > 0:
            eis.Rs *= float(10 ** rng.normal(0, noise_level))
            eis.Rct *= float(10 ** rng.normal(0, noise_level))
            eis.Cdl *= float(10 ** rng.normal(0, noise_level))
            eis.sigma_warburg *= float(10 ** rng.normal(0, noise_level))
            eis.n_cpe += float(rng.normal(0, noise_level * 0.3))
            eis.n_cpe = float(np.clip(eis.n_cpe, 0.5, 1.0))

        x = descriptors.to_vector()
        y = eis.to_vector()

        X_list.append(x)
        Y_list.append(y)
        records.append({
            "descriptors": descriptors.to_dict(),
            "eis_params": eis.to_dict(),
        })

    return np.array(X_list), np.array(Y_list), records


def generate_and_save_datasets(
    output_dir: str = "datasets",
    n_synthesis: int = 5000,
    n_eis: int = 5000,
):
    """Generate and save both datasets to disk."""
    os.makedirs(output_dir, exist_ok=True)

    logger.info("Generating synthesis dataset (%d samples)...", n_synthesis)
    X_syn, Y_syn, records_syn = generate_synthesis_dataset(n_synthesis)
    np.save(os.path.join(output_dir, "synthesis_X.npy"), X_syn)
    np.save(os.path.join(output_dir, "synthesis_Y.npy"), Y_syn)
    with open(os.path.join(output_dir, "synthesis_records.json"), "w") as f:
        json.dump(records_syn[:100], f, indent=2)  # Save sample
    logger.info("  Saved: X=%s, Y=%s", X_syn.shape, Y_syn.shape)

    logger.info("Generating EIS dataset (%d samples)...", n_eis)
    X_eis, Y_eis, records_eis = generate_eis_dataset(n_eis)
    np.save(os.path.join(output_dir, "eis_X.npy"), X_eis)
    np.save(os.path.join(output_dir, "eis_Y.npy"), Y_eis)
    with open(os.path.join(output_dir, "eis_records.json"), "w") as f:
        json.dump(records_eis[:100], f, indent=2)
    logger.info("  Saved: X=%s, Y=%s", X_eis.shape, Y_eis.shape)

    return output_dir
