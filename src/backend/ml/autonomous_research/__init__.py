"""
Autonomous Research Pipeline Engine
Self-building material intelligence database

This module continuously mines scientific literature, extracts experimental data,
and builds comprehensive material databases for electrochemistry applications.
"""

__version__ = "1.0.0"
__author__ = "VidyuthLabs"

from .extractors.figure_digitizer import FigureDigitizer
from .extractors.nlp_extractor import NLPExtractor

__all__ = [
    'FigureDigitizer',
    'NLPExtractor'
]
