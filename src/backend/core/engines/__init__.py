"""
VANL Core Modules
==================
Material representations, synthesis simulation, EIS engine,
Bayesian optimizer, and autonomous experiment loop.

Public API:
    - MaterialComposition, SynthesisParameters, StructuralDescriptors
    - EISParameters, ExperimentRecord
    - SynthesisEngine
    - simulate_eis, descriptors_to_eis, quick_simulate
    - BayesianOptimizer, OptimizationTarget  (requires scikit-learn)
    - AutonomousLab, LabConfig               (requires scikit-learn)
    - generate_and_save_datasets
"""

# ── Always-available imports (numpy only) ──────────────────────────
from .materials import (
    MaterialComposition,
    SynthesisParameters,
    StructuralDescriptors,
    EISParameters,
    ExperimentRecord,
    SynthesisMethod,
    Solvent,
    ElectrodeType,
    MATERIAL_DATABASE,
)
from .synthesis_engine import SynthesisEngine
from .eis_engine import (
    simulate_eis,
    descriptors_to_eis,
    quick_simulate,
    EISResult,
    randles_impedance,
)
from .dataset_gen import (
    generate_synthesis_dataset,
    generate_eis_dataset,
    generate_and_save_datasets,
)

# ── New validation & uncertainty modules ───────────────────────────
from .kk_validation import (
    KKValidationResult,
    kramers_kronig_validate,
    kk_residuals,
)
from .uncertainty import (
    UncertaintyBounds,
    PredictionWithUncertainty,
    predict_with_uncertainty,
    compute_eis_uncertainty,
)
from .data_loader import (
    ExternalEISData,
    load_perovskite_eis,
    load_custom_csv,
    list_available_datasets,
)

# ── Optional imports (require scikit-learn + scipy) ────────────────
try:
    from .optimizer import (
        BayesianOptimizer,
        OptimizationTarget,
        compute_objective,
    )
    from .autonomous import AutonomousLab, LabConfig
    _HAS_OPTIMIZATION = True
except ImportError:
    _HAS_OPTIMIZATION = False

# ── Optional: validation (requires scipy for fitting) ──────────────
try:
    from .validation import (
        fit_randles_to_data,
        validate_against_perovskites,
        generate_validation_report,
        FitResult,
        ValidationReport,
    )
    _HAS_VALIDATION = True
except ImportError:
    _HAS_VALIDATION = False

__all__ = [
    # Materials
    "MaterialComposition", "SynthesisParameters", "StructuralDescriptors",
    "EISParameters", "ExperimentRecord", "SynthesisMethod", "Solvent",
    "ElectrodeType", "MATERIAL_DATABASE",
    # Engines
    "SynthesisEngine", "simulate_eis", "descriptors_to_eis",
    "quick_simulate", "EISResult", "randles_impedance",
    # Dataset
    "generate_synthesis_dataset", "generate_eis_dataset",
    "generate_and_save_datasets",
    # KK Validation
    "KKValidationResult", "kramers_kronig_validate", "kk_residuals",
    # Uncertainty
    "UncertaintyBounds", "PredictionWithUncertainty",
    "predict_with_uncertainty", "compute_eis_uncertainty",
    # Data loading
    "ExternalEISData", "load_perovskite_eis", "load_custom_csv",
    "list_available_datasets",
]

if _HAS_OPTIMIZATION:
    __all__ += [
        "BayesianOptimizer", "OptimizationTarget", "compute_objective",
        "AutonomousLab", "LabConfig",
    ]

if _HAS_VALIDATION:
    __all__ += [
        "fit_randles_to_data", "validate_against_perovskites",
        "generate_validation_report", "FitResult", "ValidationReport",
    ]
