"""
MADSci Experiment Management Module
===================================
Full experiment campaign management with closed-loop autonomy.
"""

from .experiment_manager import (
    ExperimentManager,
    Campaign,
    Experiment,
    Resource,
    CampaignStatus,
    ExperimentStatus,
    StoppingCriterion,
    get_experiment_manager,
)

__all__ = [
    "ExperimentManager",
    "Campaign",
    "Experiment",
    "Resource",
    "CampaignStatus",
    "ExperimentStatus",
    "StoppingCriterion",
    "get_experiment_manager",
]
