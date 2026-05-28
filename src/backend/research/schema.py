"""
Database Schema
=================
SQLite schema for research paper storage.

Tables:
    papers          -- Metadata for each paper (title, authors, DOI, etc.)
    materials       -- Extracted material components with ratios
    synthesis       -- Synthesis method, temperature, duration
    eis_data        -- Extracted EIS parameters (Rct, Rs, Cdl, etc.)
    extractions     -- Provenance log linking every extracted value to source

All extracted fields carry a confidence score (0.0-1.0).
NULL means the field was not found -- never fabricated.
"""

import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Papers table: one row per unique publication
CREATE TABLE IF NOT EXISTS papers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    authors         TEXT,              -- JSON array of author names
    abstract        TEXT,
    doi             TEXT UNIQUE,
    arxiv_id        TEXT,
    semantic_scholar_id TEXT,
    year            INTEGER,
    journal         TEXT,
    url             TEXT,
    pdf_url         TEXT,
    source_api      TEXT,              -- 'arxiv', 'crossref', 'semantic_scholar'
    application     TEXT,              -- 'supercapacitor', 'biosensor', 'battery', etc.
    full_text       TEXT,              -- extracted full text (if available)
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed       INTEGER DEFAULT 0, -- 0=unprocessed, 1=processed, -1=failed
    processing_error TEXT
);

-- Materials table: extracted material components
CREATE TABLE IF NOT EXISTS materials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        INTEGER NOT NULL,
    component       TEXT NOT NULL,      -- e.g. 'graphene', 'MnO2', 'PEDOT:PSS'
    ratio_value     REAL,              -- numeric ratio if found
    ratio_unit      TEXT,              -- 'wt%', 'mol%', 'mg/mL', etc.
    role            TEXT,              -- 'active_material', 'binder', 'substrate', etc.
    confidence      REAL DEFAULT 0.0,  -- 0.0-1.0 extraction confidence
    source_section  TEXT,              -- section/page where found
    FOREIGN KEY (paper_id) REFERENCES papers(id)
);

-- Synthesis table: extraction conditions
CREATE TABLE IF NOT EXISTS synthesis (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        INTEGER NOT NULL,
    method          TEXT,              -- 'hydrothermal', 'sol-gel', 'drop_casting', etc.
    temperature_C   REAL,
    duration_hours  REAL,
    pH              REAL,
    atmosphere      TEXT,              -- 'air', 'N2', 'Ar', etc.
    substrate       TEXT,              -- 'GCE', 'ITO', 'screen-printed', etc.
    confidence      REAL DEFAULT 0.0,
    source_section  TEXT,
    FOREIGN KEY (paper_id) REFERENCES papers(id)
);

-- EIS data table: extracted electrochemical parameters
CREATE TABLE IF NOT EXISTS eis_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        INTEGER NOT NULL,
    Rs_ohm          REAL,              -- solution resistance
    Rct_ohm         REAL,              -- charge transfer resistance
    Cdl_F           REAL,              -- double layer capacitance
    sigma_warburg   REAL,              -- Warburg coefficient
    capacitance_F_g REAL,              -- specific capacitance (F/g)
    capacitance_mF_cm2 REAL,           -- areal capacitance
    scan_rate_mV_s  REAL,
    freq_min_Hz     REAL,
    freq_max_Hz     REAL,
    electrolyte     TEXT,              -- e.g. '1M KOH', '0.5M H2SO4'
    measurement_type TEXT,             -- 'EIS', 'CV', 'GCD'
    confidence      REAL DEFAULT 0.0,
    source_section  TEXT,
    FOREIGN KEY (paper_id) REFERENCES papers(id)
);

-- Extraction provenance log
CREATE TABLE IF NOT EXISTS extractions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        INTEGER NOT NULL,
    target_table    TEXT NOT NULL,      -- 'materials', 'synthesis', 'eis_data'
    target_id       INTEGER,           -- row id in target table
    field_name      TEXT NOT NULL,      -- e.g. 'Rct_ohm', 'temperature_C'
    raw_text        TEXT,              -- the original text snippet
    extracted_value TEXT,              -- what was extracted
    confidence      REAL DEFAULT 0.0,
    extraction_method TEXT,            -- 'regex', 'nlp', 'table_parse'
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id)
);

-- Pipeline run log
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at     TIMESTAMP,
    papers_fetched  INTEGER DEFAULT 0,
    papers_processed INTEGER DEFAULT 0,
    papers_failed   INTEGER DEFAULT 0,
    queries_run     INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'running'  -- 'running', 'completed', 'failed'
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_arxiv ON papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_materials_paper ON materials(paper_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_paper ON synthesis(paper_id);
CREATE INDEX IF NOT EXISTS idx_eis_paper ON eis_data(paper_id);
CREATE INDEX IF NOT EXISTS idx_papers_processed ON papers(processed);
"""


def init_database(db_path: str) -> sqlite3.Connection:
    """Initialize the SQLite database and create tables."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    logger.info("Database initialized at %s", db_path)
    return conn


def get_connection(db_path: str) -> sqlite3.Connection:
    """Get a connection to the database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
