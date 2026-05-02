"""
SQLite Application State Engine
=================================
Lightweight state management for:
  - User projects & sessions
  - Application settings
  - License state
  - UI preferences
  - Recent files

This is intentionally separate from the analytics DB (DuckDB)
to keep app state fast and portable.
"""

import json
import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    settings     TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recent_files (
    file_path  TEXT PRIMARY KEY,
    project_id TEXT,
    file_type  TEXT,
    opened_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS session_log (
    session_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    event_data  TEXT,
    timestamp   TEXT DEFAULT (datetime('now'))
);
"""


class StateDB:
    """SQLite-backed application state manager."""

    def __init__(self, db_path: str = "db/raman_state.sqlite"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        logger.info("StateDB connected: %s", db_path)

    def initialize(self):
        """Create schema."""
        self._conn.executescript(STATE_SCHEMA)
        self._conn.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get an app setting."""
        row = self._conn.execute(
            "SELECT value FROM app_settings WHERE key=?", (key,)
        ).fetchone()
        if row:
            try:
                return json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                return row["value"]
        return default

    def set_setting(self, key: str, value: Any):
        """Set an app setting."""
        self._conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (key, json.dumps(value))
        )
        self._conn.commit()

    def log_event(self, event_type: str, data: Optional[Dict] = None):
        """Log a session event."""
        self._conn.execute(
            "INSERT INTO session_log (event_type, event_data) VALUES (?, ?)",
            (event_type, json.dumps(data) if data else None)
        )
        self._conn.commit()

    def close(self):
        self._conn.close()
