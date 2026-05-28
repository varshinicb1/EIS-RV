"""
Pre-flight check for RĀMAN Studio
==================================
Verifies that the developer's local environment can build and import the app.

Honest version. Earlier revisions of this script reported "✓ Security
Features" by iterating a hardcoded list of `(name, True)` tuples and
"✓ 21 CFR Part 11 Compliance" by the same trick. Those sections have
been removed because they did not actually verify anything.

What this script DOES verify:
  - Python version is supported (3.11–3.13)
  - Required packages can be imported
  - Backend entry points (src/backend/api/server.py and friends) exist
  - The C++ engine source tree is present
  - The frontend entry points exist
  - Optional NVIDIA API key is loadable

What this script does NOT verify:
  - That security features actually work (covered by the test suite)
  - That the C++ engine is built (run `python3 scripts/build_cpp.py`)
  - That the frontend is built (run `cd src/frontend && npm run build`)

Exit code is 0 if no errors, 1 if any error, 0 if only warnings.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---- ANSI helpers ----------------------------------------------------------

GREEN, RED, YELLOW, BLUE, RESET, BOLD = (
    "\033[92m", "\033[91m", "\033[93m", "\033[94m", "\033[0m", "\033[1m"
)


def header(text: str) -> None:
    print(f"\n{BOLD}{BLUE}{'=' * 60}{RESET}")
    print(f"{BOLD}{BLUE}{text:^60}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 60}{RESET}\n")


def ok(text: str) -> None:
    print(f"{GREEN}[OK]{RESET} {text}")


def err(text: str) -> None:
    print(f"{RED}[ERROR]{RESET} {text}")


def warn(text: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {text}")


def info(text: str) -> None:
    print(f"[INFO] {text}")


errors: list[str] = []
warnings: list[str] = []


# ---- 1. Python version -----------------------------------------------------

header("1. Python environment")

py = sys.version_info
info(f"Python {py.major}.{py.minor}.{py.micro}  ({sys.executable})")

if (3, 11) <= (py.major, py.minor) <= (3, 13):
    ok(f"Python {py.major}.{py.minor} is supported")
elif (py.major, py.minor) >= (3, 14):
    warn(f"Python {py.major}.{py.minor} may break some optional ML deps; 3.11–3.13 are tested")
    warnings.append(f"Python {py.major}.{py.minor} not in tested range")
else:
    err(f"Python {py.major}.{py.minor} is too old; need 3.11+")
    errors.append("python<3.11")


# ---- 2. Required packages --------------------------------------------------

header("2. Required packages")

# (import_name, optional)
PACKAGES: list[tuple[str, bool]] = [
    ("numpy",       False),
    ("scipy",       False),
    ("fastapi",     False),
    ("uvicorn",     False),
    ("pydantic",    False),
    ("requests",    False),
    ("dotenv",      False),  # python-dotenv
    ("sklearn",     True),   # scikit-learn — needed for optimizer
    ("pandas",      True),   # used by data_loader
    ("alembic",     True),   # only needed for migrations
    ("sqlalchemy",  True),
    ("psycopg2",    True),   # only if DATABASE_URL points at Postgres
]

for name, optional in PACKAGES:
    try:
        mod = importlib.import_module(name)
        ver = getattr(mod, "__version__", "?")
        ok(f"{name} {ver}")
    except ImportError:
        if optional:
            warn(f"{name}: not installed (optional)")
            warnings.append(f"missing optional: {name}")
        else:
            err(f"{name}: not installed")
            errors.append(f"missing required: {name}")


# ---- 3. File structure -----------------------------------------------------

header("3. File structure")

REQUIRED = [
    "src/backend/api/server.py",
    "src/desktop/main.js",
    "src/frontend/index.html",
    "src/frontend/src/App.jsx",
    "engine_core/CMakeLists.txt",
    "engine_core/src/eis_solver.cpp",

    # Physics + analysis engines
    "src/backend/core/engines/eis_engine.py",
    "src/backend/core/engines/cv_engine.py",
    "src/backend/core/engines/gcd_engine.py",
    "src/backend/core/engines/battery_engine.py",
    "src/backend/core/engines/biosensor_engine.py",
    "src/backend/core/engines/materials_db.py",
    "src/backend/core/engines/circuit_fitting.py",
    "src/backend/core/engines/drt_analysis.py",
    "src/backend/core/engines/kk_validation.py",

    # API routers mounted by src/backend/api/server.py
    "src/backend/api/v1_routes/routes.py",
    "src/backend/api/v1_routes/data_routes.py",

    # Research pipeline + datasets
    "src/backend/research/pipeline.py",
    "data/datasets/research/papers.db",

    "package.json",
    ".env.example",
    "README.md",
]

for path in REQUIRED:
    if Path(path).exists():
        ok(path)
    else:
        err(f"missing: {path}")
        errors.append(f"missing file: {path}")


# ---- 4. Environment --------------------------------------------------------

header("4. Environment")

env_keys = [
    ("NVIDIA_API_KEY", True),   # optional — only needed for cloud AI
    ("PORT",            True),
    ("LOG_LEVEL",       True),
]

for key, optional in env_keys:
    val = os.environ.get(key)
    if val:
        # Don't print key contents; just confirm presence.
        ok(f"{key} is set")
    elif optional:
        info(f"{key} not set (optional)")
    else:
        err(f"{key} not set")
        errors.append(f"missing env: {key}")


# ---- 5. FastAPI app loads --------------------------------------------------

header("5. Backend imports")

# Make sure the project root is on sys.path so `import src...` works.
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.backend.api import server  # noqa: F401
    routes = [r for r in server.app.routes if hasattr(r, "methods")]
    ok(f"src.backend.api.server imports cleanly ({len(routes)} routes)")
except Exception as e:  # broad — we want to surface anything
    err(f"src.backend.api.server failed to import: {e}")
    errors.append(f"server import: {e}")


# ---- Final report ----------------------------------------------------------

header("Final report")

if errors:
    print(f"{RED}{BOLD}{len(errors)} error(s):{RESET}")
    for e in errors:
        print(f"  {RED}-{RESET} {e}")

if warnings:
    print(f"{YELLOW}{BOLD}{len(warnings)} warning(s):{RESET}")
    for w in warnings:
        print(f"  {YELLOW}-{RESET} {w}")

if not errors and not warnings:
    print(f"{GREEN}{BOLD}All checks passed.{RESET}")
elif not errors:
    print(f"{GREEN}{BOLD}No errors (warnings only).{RESET}")

sys.exit(1 if errors else 0)
