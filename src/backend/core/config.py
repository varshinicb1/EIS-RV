"""
RĀMAN Studio — Centralized Configuration
==========================================
Single source of truth for paths, ports, and feature flags.
"""
import os
from pathlib import Path

# ── Project Paths ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)
CACHE_DIR = DATA_DIR / "materials_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Server Configuration ──────────────────────────────────────────
SERVER_HOST = os.getenv("RAMAN_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("RAMAN_PORT", "8000"))
API_PREFIX = "/api/v2"

# ── Database ──────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://raman_admin:changeme123@localhost:5434/raman_enterprise"
)

# ── External APIs (hardcoded for binary distribution) ───────────────
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "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")
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
MP_API_KEY = os.getenv("MP_API_KEY", "52BYY8xRx5VB9yngqLT2F8ESXLqX9ilO")

# Google Drive (hardcoded for binary)
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "1W1jAhamHkAKklwlVJae5Mmg3mtB-lId8")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    ""  # Set via env var or compile-time injection
)

# ── Feature Flags ─────────────────────────────────────────────────
ENABLE_HARDWARE_BRIDGE = os.getenv("ENABLE_HARDWARE", "true").lower() == "true"
ENABLE_AI_ENGINE = os.getenv("ENABLE_AI", "true").lower() == "true"

# ── Timeouts ──────────────────────────────────────────────────────
HTTP_TIMEOUT_S = int(os.getenv("HTTP_TIMEOUT", "15"))
NVIDIA_TIMEOUT_S = int(os.getenv("NVIDIA_TIMEOUT", "120"))

# ── Version ───────────────────────────────────────────────────────
VERSION = "2.0.0"
