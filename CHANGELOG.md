# Changelog

All notable changes to RĀMAN Studio are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0] — 2026-05-03

First release in which RĀMAN Studio is intended for direct use by external
researchers. The full app should now feel coherent without hand-holding:
every panel hits a real backend route, every paid route is license-gated,
and every error path produces a sanitized user-visible message rather than
a Python traceback.

### Added

- **Lab Data panel + xlsx upload** — drop an AnalyteX-style multi-sheet xlsx
  (CV / GCD / EIS) and the backend importer derives rows + raw arrays into
  an encrypted-at-rest dataset. Tabs for Upload / Rows / Analysis / Suggestions.
- **Supercap analyzer** (`src/backend/supercap/`) — extracts specific
  capacitance from CV (integration), GCD (linear discharge slope + IR drop),
  and EIS (`-1/(2πf·Z″)` at low frequency). Aggregate path computes Trasatti
  *b*-value, retention, Coulombic η, energy/power density, and a Nyquist-shape
  diagnosis.
- **NIM-grounded supercap recommender** — `POST /api/v2/supercap/suggest-next`
  sends the structured analysis report (not raw arrays) to the configured
  NVIDIA NIM model and returns ranked next-iteration suggestions with risk
  flags.
- **Encrypted lab data store** (`src/backend/lab/dataset_manager.py`) — Fernet
  + PBKDF2-SHA256 (600k iterations) with the key derived from the local
  hardware fingerprint. Datasets never leave the machine in clear text.
- **Real Ed25519 license tokens** — server-side issued, client-side verified
  with hardware binding. Trial state is anchored to the install so the same
  trial can't be replayed on another machine.
- **AlchemistCanvas wired to real synthesis** — replaces a 3-second
  `setTimeout` chain that fabricated steps and properties with real calls
  to `/api/v2/alchemi/properties` (curated DB → NIM fallback) and
  `/api/v2/alchemi/chat` (JSON-only synthesis protocol with rationale).
  The reasoning log shows source provenance.
- **Toaster** — global `RAMAN_TOAST` event + `<Toaster/>` component.
  Replaces every `alert(...)` and "no-op button" failure mode.
- **API security tests** — TestClient suite that asserts every paid route
  returns 403 without a license, that responses never contain stack traces,
  and that Pydantic bounds reject obviously bad input.
- **Vitest + RTL frontend tests** — Toaster + AlchemistCanvas smoke tests.
- **GitHub Actions release workflow** — tag `v*.*.*` builds Windows / Linux /
  macOS Electron installers and attaches them to a GitHub Release. Code
  signing is wired to env-var secrets (CSC_LINK / APPLE_ID etc.) so a cert
  can be supplied without touching workflow yaml.
- **CHANGELOG.md, CONTRIBUTING.md, SECURITY.md** as a real shipping triplet.

### Changed

- **Frontend cold-start cut from ~2.0 MB to ~795 KB** via Vite `manualChunks`
  and `React.lazy()` of 17 non-default panels. `three-vendor` (714 KB) and
  `pdf-vendor` (574 KB) are now off the critical path.
- **Backend cleanup** — 25 `except: pass` sites converted to
  `except Exception: logger.warning(...)` so silent error swallowing leaves
  a trail. PubChem fetch now retries with exponential backoff on transient
  failures (429 / 5xx / timeouts). `print()` calls in library code replaced
  with structured logging.

### Security

- **Closed 7 unauthenticated endpoint groups** — agent, data, nvidia, pe,
  quantum, vanl-legacy `/api`, and the `/ws/telemetry` WebSocket are now
  license-gated. The WebSocket explicitly closes with policy-violation
  (1008) on invalid license.
- **No more stack-trace leaks** — installs a global FastAPI exception
  handler that wraps both `HTTPException(5xx)` and unhandled `Exception`,
  logs the full traceback server-side with an `error_id`, and returns a
  sanitized JSON body containing only that id and a generic message. 33
  call sites that did `raise HTTPException(500, str(e))` now use
  `internal_error(e, op=...)`.
- **Tightened Pydantic input bounds** — 53 numeric fields, 18 string
  fields, and 14 List[float] fields now have physical / sane ranges so a
  caller cannot trigger arithmetic overflow or OOM by sending
  `temperature_K=-500` or a 1-million-element impedance array.

### Repo hygiene

- Untracked `.venv_new/` (8755 files) and `models/Raman-Qwen-Agent/checkpoint-*`
  (110 files); repository drops from 359 MB to 28 MB.
- `datasets/*.xlsx` and `data/datasets/` added to `.gitignore` so user lab
  data stays off the public tree.
- Removed legacy `EIS-RV/EIS-RV-backups/`, `vanl/` subproject, and root
  cleanup notes (~241 deleted files, ~420k lines).

## [2.0.0] — 2026-04-26

- Renamed and reorganized to `src/backend/` + `src/frontend/` + `engine_core/`.
- Initial integration of the C++ physics engine (Eigen + OpenMP) via pybind11.
- Lin-KK Schönleber μ statistic, hybrid Nernstian/Butler-Volmer CV solver.
- 19 React panels covering EIS, CV, GCD, DRT, Circuit fitting, Toolkit,
  Materials Explorer, AlchemistCanvas, Biosensor, Battery, Reports,
  Workspace, Profile, etc.

[Unreleased]: https://github.com/varshinicb1/EIS-RV/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/varshinicb1/EIS-RV/releases/tag/v2.1.0
[2.0.0]: https://github.com/varshinicb1/EIS-RV/releases/tag/v2.0.0
