"""
Enhanced Data Extraction System
Modular extractors for scientific papers
"""

from .base_extractor import BaseExtractor
from .pdf_parser import PDFParser
from .table_extractor import TableExtractor
from .figure_digitizer import FigureDigitizer
from .nlp_extractor import NLPExtractor

__all__ = [
    'BaseExtractor',
    'PDFParser',
    'TableExtractor',
    'FigureDigitizer',
    'NLPExtractor'
]
