"""
Autonomous Research Pipeline Engine
Self-building material intelligence database

This module continuously mines scientific literature, extracts experimental data,
and builds comprehensive material databases for electrochemistry applications.
"""

__version__ = "1.0.0"
__author__ = "VidyuthLabs"

from .literature_miner import LiteratureMiner
from .data_extractor import DataExtractor
from .material_database import MaterialDatabase
from .recommendation_engine import MaterialRecommender
from .identification_engine import SampleIdentifier

__all__ = [
    'LiteratureMiner',
    'DataExtractor',
    'MaterialDatabase',
    'MaterialRecommender',
    'SampleIdentifier'
]
