# Contributing to RĀMAN Studio

Thanks for taking the time. RĀMAN Studio is a small commercial project from
[VidyuthLabs](https://vidyuthlabs.co.in); we still welcome external code,
issues, and improvements that align with the roadmap. This document explains
how to set up a working tree, what the layout means, and what we expect from
patches.

## Repository layout

```
src/
├── backend/        FastAPI sidecar (port 8000), all paid routes
│   ├── api/        Routers + global error handler
│   ├── core/       Shared engines (EIS, CV, DRT, materials)
│   ├── lab/        Encrypted-at-rest user lab data store
│   ├── licensing/  Ed25519 license tokens + hardware fingerprint
│   ├── supercap/   Specific-capacitance analyzer (Cs, b-value, etc.)
│   └── research/   Pipeline scheduler + scientific parser
├── frontend/       Vite + React 19 renderer (one folder per panel)
└── ai_engine/      NIM client + AlchemiBridge (NVIDIA NIM integration)

engine_core/        C++ physics engine (Eigen + OpenMP) with pybind11 bindings
tests/              pytest suite (unit/, integration/)
.github/workflows/  CI (test + lint + Trivy + Docker) and release workflows
```

Anything outside `src/` and `engine_core/` is supporting material — scripts,
docs, build artifacts, resources.

## Local setup

You will need:

- Python 3.11 or 3.12
- Node 20+
- A C++17 compiler, CMake ≥ 3.20, Eigen 3, pybind11 (only if you want to build
  the native engine; Python fallback works without)

Clone, install, and verify:

```bash
git clone https://github.com/varshinicb1/EIS-RV.git
cd EIS-RV

# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest --ignore=tests/integration -q       # ~13s, 381 passing

# Frontend
cd src/frontend
npm install --legacy-peer-deps
npm run test                                # 7 passing
npm run build                               # ~5s, drops 60 KB main chunk
cd ../..

# (Optional) C++ engine
cd engine_core && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DRAMAN_BUILD_TESTS=ON
cmake --build . -j$(nproc)
ctest --output-on-failure
```

Run the desktop shell:

```bash
# Terminal 1
python -m uvicorn src.backend.api.server:app --port 8000 --reload

# Terminal 2
cd src/frontend && npm run dev               # Vite on :5173

# Terminal 3
npm run dev                                   # Electron loads :5173
```

## Patches we accept

- Bug fixes with a regression test.
- New backend routes that follow the existing pattern (Pydantic schema,
  license gate, sanitized error handler, structured logging).
- New panels that wire a real backend route. Mock-data UI demos are not
  accepted — researchers expect every button to do something.
- C++ engine improvements with a corresponding `engine_core/tests/*.cpp`
  case.
- Performance work that's measured (`pytest-benchmark`, `vite build` chunk
  size, etc.).

## Patches we don't accept

- Changes that disable hooks (`--no-verify`), bypass code signing, or
  silence ruff/eslint/mypy without justification.
- New `print()` calls in library code (use `logger.info` / `.warning` /
  `.exception`).
- New `except Exception: pass` (silently swallows failures — see how
  `src/backend/api/server.py` writes `logger.exception` instead).
- New `raise HTTPException(500, str(e))` (use `internal_error(e, op=...)`
  from `src.backend.api.error_handlers`).
- Frontend `alert(...)` (use the `RAMAN_TOAST` event — see
  `src/frontend/src/components/layout/Toaster.jsx`).
- Inventing API endpoints that don't exist on `integrate.api.nvidia.com/v1`.
  See `src/ai_engine/nim_client.py` for the docstring on this.
- Committing user lab data, real license tokens, real API keys, or anything
  matching `.gitignore` — gitleaks runs in CI.

## Pre-commit hooks

Install once per checkout:

```bash
pip install pre-commit
pre-commit install
```

Hooks include trailing-whitespace, end-of-file-fixer, ruff (with `--ignore E501`),
JSON/YAML syntax check, large-file gate (2 MB), private-key detection, and a
local hook that forbids new `print()` calls in library code.

## Commit messages

We follow Conventional Commits loosely:

```
fix(api): tighten Pydantic input bounds to reject obviously bad inputs
feat(supercap): NIM-grounded next-iteration recommender
chore(repo): untrack .venv_new and Raman-Qwen training checkpoints
```

Keep the subject under 70 characters. Use the body to explain *why*, not what
the diff already shows.

Co-author every commit you push:

```
Co-Authored-By: Your Name <you@example.com>
```

## Tests

- Add a unit test for any backend bug fix (`tests/unit/`).
- Add a vitest test for any frontend bug fix (`src/frontend/test/`).
- Integration tests (ROS, hardware) live in `tests/integration/` and are
  excluded from regular CI runs.
- Coverage gate is currently 55%. PRs that drop coverage will fail CI.

## Releases

Tag-driven. Push a `v*.*.*` tag and `.github/workflows/release.yml` builds
Windows / Linux / macOS Electron installers, signs them if cert env-vars are
present, and attaches them to a new GitHub Release. See `CHANGELOG.md` for
the format we expect.

## Code of conduct

Be kind. We will remove patches, comments, or contributors that aren't.

## License

All contributions are accepted under the project's commercial license (see
`LICENSE_COMMERCIAL`). By submitting a pull request you confirm you have the
right to license your contribution under those terms.
