"""
Configuration for the research pipeline.
"""

import os

# Base directories.
# This file lives at src/backend/research/config.py, so the project root is
# three levels up. (Previously this file lived two levels deep under vanl/;
# don't drop a level if the file moves again.)
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(PIPELINE_DIR, "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "datasets", "research")
DB_PATH = os.path.join(DATA_DIR, "papers.db")
PDF_CACHE_DIR = os.path.join(DATA_DIR, "pdf_cache")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
LOG_DIR = os.path.join(DATA_DIR, "logs")

# Ensure directories exist
for d in [DATA_DIR, PDF_CACHE_DIR, EXPORT_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

# API configuration (no keys required for these public APIs)
ARXIV_API_URL = "http://export.arxiv.org/api/query"
CROSSREF_API_URL = "https://api.crossref.org/works"
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

# Rate limiting (seconds between requests)
ARXIV_DELAY = 3.0        # arXiv requires >= 3s between requests
CROSSREF_DELAY = 1.0
SEMANTIC_SCHOLAR_DELAY = 1.0

# Search queries for nanomaterial / EIS domain
SEARCH_QUERIES = [
    "electrochemical impedance spectroscopy nanomaterial",
    "supercapacitor graphene MnO2 EIS",
    "screen printed electrode impedance",
    "printed battery nanomaterial",
    "MnO2 supercapacitor electrochemical",
    "graphene oxide electrode impedance spectroscopy",
    "PEDOT PSS electrode EIS",
    "carbon nanotube supercapacitor impedance",
    "nanocomposite electrode Nyquist",
    "hydrothermal synthesis electrode material",
    "sol-gel nanomaterial electrode characterization",
    "electrodeposition thin film impedance",
    "polyaniline supercapacitor EIS",
    "NiO nanostructure electrode",
    "Fe2O3 anode impedance spectroscopy",
]

# Maximum papers per query per source
MAX_PAPERS_PER_QUERY = 20

# Scheduling
UPDATE_INTERVAL_HOURS = 24

# Logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_LEVEL = "INFO"
