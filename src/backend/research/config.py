"""
Configuration for the research pipeline.

The set of search queries used by the literature-mining pipeline is
exposed two ways:

  - ``SEARCH_QUERIES`` (this module) is the *built-in* default.
  - ``user_queries.json`` in the data dir overrides it once the user
    has saved a custom list. ``get_search_queries()`` returns whichever
    is currently active; the API endpoints in server.py call into
    ``set_search_queries()`` to persist.

That separation keeps the install-time defaults read-only while still
letting researchers point the pipeline at their own queries without
touching the source.
"""

import json
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


# ── User-overridable search queries ────────────────────────────

USER_QUERIES_FILE = os.path.join(DATA_DIR, "user_queries.json")


def get_search_queries() -> list[str]:
    """
    Return the active search query list. User overrides win; falls
    back to the built-in ``SEARCH_QUERIES`` constant.
    """
    try:
        if os.path.exists(USER_QUERIES_FILE):
            with open(USER_QUERIES_FILE) as f:
                data = json.load(f)
            qs = data.get("queries") if isinstance(data, dict) else data
            if isinstance(qs, list) and all(isinstance(q, str) for q in qs):
                return [q.strip() for q in qs if q.strip()]
    except Exception:
        pass
    return list(SEARCH_QUERIES)


def set_search_queries(queries: list[str]) -> list[str]:
    """
    Persist a custom query list. Pass ``[]`` to clear and revert to
    the built-in defaults. Returns the active list after the write.
    """
    cleaned = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
    os.makedirs(DATA_DIR, exist_ok=True)
    if not cleaned:
        # Wipe the override file so the constant becomes active again.
        try: os.remove(USER_QUERIES_FILE)
        except FileNotFoundError: pass
        except OSError: pass
        return list(SEARCH_QUERIES)
    tmp = USER_QUERIES_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"queries": cleaned}, f, indent=2)
    os.replace(tmp, USER_QUERIES_FILE)
    return cleaned
