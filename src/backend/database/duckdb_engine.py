"""
DuckDB Analytical Engine
==========================
High-performance columnar storage for:
  - Normalized materials database
  - Research paper metadata + extracted data
  - Simulation results (EIS, CV, battery, etc.)

Every datapoint has: value, unit, conditions, source DOI, confidence.

Usage:
    from src.backend.database.duckdb_engine import AnalyticsDB
    db = AnalyticsDB("db/raman_analytics.duckdb")
    db.initialize()
    db.query("SELECT * FROM materials WHERE category='carbon'")
"""

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# DuckDB import with graceful fallback
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    logger.warning("duckdb not installed — analytics engine unavailable. "
                   "Install: pip install duckdb")


# ── Normalized Schema ──────────────────────────────────────

SCHEMA_SQL = """
-- Materials: canonical entries with unique IDs
CREATE TABLE IF NOT EXISTS materials (
    material_id    INTEGER PRIMARY KEY,
    canonical_name VARCHAR NOT NULL UNIQUE,
    formula        VARCHAR,
    category       VARCHAR,       -- carbon, metal_oxide, polymer, metal, battery
    subcategory    VARCHAR,
    crystal_system VARCHAR,
    space_group    VARCHAR,
    density_g_cm3  DOUBLE,
    bandgap_eV     DOUBLE,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Material aliases (many names → one canonical)
CREATE TABLE IF NOT EXISTS material_aliases (
    alias_id       INTEGER PRIMARY KEY,
    material_id    INTEGER REFERENCES materials(material_id),
    alias_name     VARCHAR NOT NULL,
    source         VARCHAR
);

-- Material properties (each row = one measured property)
CREATE TABLE IF NOT EXISTS material_properties (
    prop_id        INTEGER PRIMARY KEY,
    material_id    INTEGER REFERENCES materials(material_id),
    property_name  VARCHAR NOT NULL,   -- conductivity_S_m, surface_area_m2_g, etc.
    value          DOUBLE NOT NULL,
    unit           VARCHAR NOT NULL,
    conditions     VARCHAR,            -- JSON: {"temperature_K": 298, "electrolyte": "1M KOH"}
    source_doi     VARCHAR,
    source_ref     VARCHAR,
    confidence     DOUBLE DEFAULT 0.8, -- 0.0-1.0
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Synthesis methods
CREATE TABLE IF NOT EXISTS synthesis_methods (
    synthesis_id   INTEGER PRIMARY KEY,
    material_id    INTEGER REFERENCES materials(material_id),
    method_name    VARCHAR NOT NULL,   -- hydrothermal, CVD, electrodeposition, etc.
    temperature_C  DOUBLE,
    duration_hours DOUBLE,
    precursors     VARCHAR,            -- JSON array
    solvent        VARCHAR,
    pH             DOUBLE,
    atmosphere     VARCHAR,
    source_doi     VARCHAR,
    confidence     DOUBLE DEFAULT 0.7,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Electrochemical measurements (linked to material + conditions)
CREATE TABLE IF NOT EXISTS electrochemical_data (
    echem_id       INTEGER PRIMARY KEY,
    material_id    INTEGER REFERENCES materials(material_id),
    technique      VARCHAR NOT NULL,   -- EIS, CV, GCD, DPV, SWV
    parameter_name VARCHAR NOT NULL,   -- Rs_ohm, Rct_ohm, Cdl_F, i_pa_A, etc.
    value          DOUBLE NOT NULL,
    unit           VARCHAR NOT NULL,
    electrode_area_cm2  DOUBLE,
    electrolyte    VARCHAR,
    scan_rate_V_s  DOUBLE,
    temperature_K  DOUBLE DEFAULT 298.15,
    conditions     VARCHAR,            -- JSON for additional context
    source_doi     VARCHAR,
    confidence     DOUBLE DEFAULT 0.7,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Simulation results (cached for re-use)
CREATE TABLE IF NOT EXISTS simulation_cache (
    sim_id         INTEGER PRIMARY KEY,
    engine_name    VARCHAR NOT NULL,   -- eis, cv, battery, supercap, biosensor
    params_hash    VARCHAR NOT NULL,   -- SHA256 of params JSON
    params_json    VARCHAR NOT NULL,   -- Full params for reproducibility
    result_json    VARCHAR NOT NULL,   -- Full result
    compute_time_s DOUBLE,
    engine_version VARCHAR,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Research papers
CREATE TABLE IF NOT EXISTS papers (
    paper_id       INTEGER PRIMARY KEY,
    title          VARCHAR NOT NULL,
    authors        VARCHAR,            -- JSON array
    abstract       VARCHAR,
    doi            VARCHAR UNIQUE,
    arxiv_id       VARCHAR,
    year           INTEGER,
    journal        VARCHAR,
    url            VARCHAR,
    source_api     VARCHAR,            -- arxiv, crossref, semantic_scholar
    processed      BOOLEAN DEFAULT FALSE,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Entity links: Material → Synthesis → Structure → Electrochemistry → Device
CREATE TABLE IF NOT EXISTS entity_links (
    link_id        INTEGER PRIMARY KEY,
    source_table   VARCHAR NOT NULL,
    source_id      INTEGER NOT NULL,
    target_table   VARCHAR NOT NULL,
    target_id      INTEGER NOT NULL,
    relationship   VARCHAR,            -- "synthesized_by", "measured_in", etc.
    paper_id       INTEGER REFERENCES papers(paper_id),
    confidence     DOUBLE DEFAULT 0.5,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_mat_category ON materials(category);
CREATE INDEX IF NOT EXISTS idx_prop_material ON material_properties(material_id);
CREATE INDEX IF NOT EXISTS idx_echem_material ON electrochemical_data(material_id);
CREATE INDEX IF NOT EXISTS idx_echem_technique ON electrochemical_data(technique);
CREATE INDEX IF NOT EXISTS idx_sim_hash ON simulation_cache(params_hash);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
"""


class AnalyticsDB:
    """
    DuckDB-backed analytical database for RĀMAN Studio.

    Thread-safe, supports concurrent reads, analytical queries
    over materials, electrochemical data, and simulation results.
    """

    def __init__(self, db_path: str = "db/raman_analytics.duckdb"):
        if not DUCKDB_AVAILABLE:
            raise RuntimeError("duckdb is required. Install: pip install duckdb")

        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = duckdb.connect(db_path)
        logger.info("DuckDB connected: %s", db_path)

    def initialize(self):
        """Create schema tables if they don't exist."""
        self._conn.execute(SCHEMA_SQL)
        logger.info("DuckDB schema initialized")

    def query(self, sql: str, params: Optional[tuple] = None) -> List[Dict]:
        """Execute query and return list of dicts."""
        if params:
            result = self._conn.execute(sql, params)
        else:
            result = self._conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def execute(self, sql: str, params: Optional[tuple] = None):
        """Execute a write query."""
        if params:
            self._conn.execute(sql, params)
        else:
            self._conn.execute(sql)

    def insert_material(self, name: str, formula: str, category: str,
                        subcategory: str = "", **kwargs) -> int:
        """Insert a canonical material, returns material_id."""
        self._conn.execute(
            "INSERT INTO materials (canonical_name, formula, category, subcategory, "
            "crystal_system, space_group, density_g_cm3, bandgap_eV) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (name, formula, category, subcategory,
             kwargs.get("crystal_system"), kwargs.get("space_group"),
             kwargs.get("density_g_cm3"), kwargs.get("bandgap_eV"))
        )
        result = self._conn.execute(
            "SELECT material_id FROM materials WHERE canonical_name = ?", (name,)
        ).fetchone()
        return result[0] if result else -1

    def insert_property(self, material_id: int, prop_name: str,
                        value: float, unit: str, **kwargs):
        """Insert a material property with provenance."""
        self._conn.execute(
            "INSERT INTO material_properties "
            "(material_id, property_name, value, unit, conditions, "
            "source_doi, source_ref, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (material_id, prop_name, value, unit,
             kwargs.get("conditions"), kwargs.get("source_doi"),
             kwargs.get("source_ref"), kwargs.get("confidence", 0.8))
        )

    def get_material_summary(self, name: str) -> Optional[Dict]:
        """Get full material summary with all properties."""
        rows = self.query(
            "SELECT m.*, mp.property_name, mp.value, mp.unit, mp.confidence "
            "FROM materials m "
            "LEFT JOIN material_properties mp ON m.material_id = mp.material_id "
            "WHERE m.canonical_name = ?", (name,)
        )
        if not rows:
            return None

        summary = {
            "material_id": rows[0]["material_id"],
            "name": rows[0]["canonical_name"],
            "formula": rows[0]["formula"],
            "category": rows[0]["category"],
            "properties": {}
        }
        for row in rows:
            if row["property_name"]:
                summary["properties"][row["property_name"]] = {
                    "value": row["value"],
                    "unit": row["unit"],
                    "confidence": row["confidence"],
                }
        return summary

    def search_materials(self, category: Optional[str] = None,
                         min_conductivity: Optional[float] = None) -> List[Dict]:
        """Search materials with filters."""
        sql = "SELECT DISTINCT m.* FROM materials m"
        conditions = []
        params = []

        if min_conductivity is not None:
            sql += " JOIN material_properties mp ON m.material_id = mp.material_id"
            conditions.append("mp.property_name = 'conductivity_S_m' AND mp.value >= ?")
            params.append(min_conductivity)

        if category:
            conditions.append("m.category = ?")
            params.append(category)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        return self.query(sql, tuple(params) if params else None)

    def close(self):
        """Close DuckDB connection."""
        self._conn.close()
        logger.info("DuckDB closed")
