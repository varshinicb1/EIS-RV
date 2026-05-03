"""
VANL Research Pipeline
========================
Continuous research paper ingestion and dataset generation pipeline
for nanomaterials and electrochemical systems.

This module provides:
    - Paper fetching from arXiv, CrossRef, Semantic Scholar APIs
    - PDF/text extraction and scientific data parsing
    - Structured storage in SQLite with CSV/JSON export
    - Deduplication and continuous update scheduling

All extracted data is traceable to its source paper. Confidence scores
are assigned to each extracted field. No values are fabricated --
fields that cannot be extracted are stored as NULL.
"""

__version__ = "0.1.0"
