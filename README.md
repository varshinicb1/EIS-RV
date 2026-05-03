# RĀMAN Studio

Desktop application for electrochemical analysis. Imports data from VidyuthLabs
AnalyteX devices, runs simulation engines (EIS, CV, GCD), and helps researchers
explore materials.

> **Status**: pre-1.0, work in progress. The product is honest about what it
> does today; see [What works today](#what-works-today) and [Known
> limitations](#known-limitations) below.

---

## Pricing intent

- **$5 / month** (₹400 / month) per user, single device.
- **30-day free trial**, no credit card required at signup.
- Hardware-bound activation; the license is verified locally with an embedded
  public key.

The licensing system is being rebuilt; see [Roadmap](#roadmap).

---

## Architecture (current)

- **Desktop shell**: Electron 28 + React (Vite). Source under `src/desktop/` and
  `src/frontend/`.
- **Local backend**: FastAPI + Uvicorn, spawned by Electron as a sidecar
  process. Source under `src/backend/`.
- **Physics engine**: C++ library (`engine_core/`) exposing EIS, CV, DRT, and a
  circuit fitter to Python via pybind11. Eigen + OpenMP, no CUDA.
- **AI agent (optional)**: A locally-hosted Qwen-1.5-1.8B chat model with a
  LoRA adapter trained on electrochemistry Q&A. Lives in `src/ai_engine/`.
  Uses NVIDIA NIM only when the user supplies their own API key — see
  [NVIDIA / NIM](#nvidia--nim).
- **Research pipeline (optional)**: arXiv / Crossref / Semantic Scholar
  scrapers and a local SQLite cache. Lives under `vanl/research_pipeline/` and
  is being folded into `src/` over time.

---

## What works today

| Area | Status |
|---|---|
| EIS simulation (Randles + CPE, Warburg) | Implemented in C++, validated within ±10–15% on the included test cases |
| CV simulation (Butler–Volmer + Nicholson semi-integral) | Implemented in C++; known issue with `Rs_ohm` not yet wired through |
| GCD simulation | Implemented in Python (`vanl/`) |
| DRT analysis (Tikhonov regularisation) | Implemented in C++; uses projected gradient, not Lawson–Hanson NNLS |
| Circuit fitting (Levenberg–Marquardt) | Implemented in C++; numerical Jacobian |
| File-based project save/load | Plaintext JSON today; encrypted format planned |
| AnalyteX CSV / JSON import | Works |
| PDF / HTML report export | Works |
| Local AI agent (Qwen-1.5-1.8B + LoRA) | Works if model weights are present under `models/Raman-Qwen-Agent/` |

## Known limitations

These are documented openly so users (and ourselves) know not to depend on
them yet.

- **Licensing is not enforced.** The current build is effectively trial-mode
  for everyone. Real licensing (Ed25519-signed tokens, hardware binding,
  online activation) is being built — see Roadmap.
- **Project files are stored as plaintext JSON.** Encrypted-at-rest project
  format will land with the licensing rework.
- **NVIDIA NIM integration** is not active in any default configuration.
  Earlier code targeted endpoints that don't exist on `integrate.api.nvidia.com`;
  that is being rewritten to use the OpenAI-compatible chat-completions API.
- **The C++ engine ships only EIS, CV, DRT, and a circuit fitter.** DPV,
  supercapacitor (EDLC + pseudocap), single-particle battery, and biosensor
  engines mentioned in earlier docs are **not** in `engine_core/` yet.
- **The frontend renderer port is being unified.** Earlier builds had the
  Electron sidecar on `:8000` while the React UI talked to `:8001`; in a
  packaged build that meant the UI fell back to client-side JavaScript
  approximations without telling the user. This is being fixed.
- **Telemetry/dashboards in the UI** still show some `Math.random()` values
  pending wiring to real backend metrics. Affected components carry a
  `// TODO: real telemetry` marker.
- **Auto-update** has no signature verification configured. Do not enable
  auto-update against a public release channel until that is fixed.

---

## Quick start (developers)

```bash
# Python backend
python3.12 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r vanl/requirements.txt   # consolidated requirements file is on the way

# C++ engine
python3 scripts/build_cpp.py --test

# Desktop shell
cd src/frontend && npm install && cd -
npm install
npm run dev
```

The desktop app talks to the backend over `127.0.0.1`. No data leaves the
machine in the default configuration.

To configure the optional NVIDIA NIM integration, copy `.env.example` to `.env`
and set `NVIDIA_API_KEY`. Get a key (free tier available) at
<https://build.nvidia.com>. The `.env` file is gitignored.

---

## NVIDIA / NIM

NVIDIA NIM is used for two opt-in features:

1. **Materials chat** against a hosted LLM (`meta/llama-3.1-70b-instruct` by
   default), via the OpenAI-compatible endpoint at
   `https://integrate.api.nvidia.com/v1/chat/completions`.
2. **Property look-ups** against published NIMs that take SMILES / structure
   inputs.

If `NVIDIA_API_KEY` is not set, RĀMAN Studio runs in fully-local mode: the
local Qwen agent answers chat queries and the materials database returns
cached values. There is no silent cloud fallback.

---

## Roadmap (next phases)

These are the real next steps. They replace the WEEK_x / PHASE_x status
markdowns that lived in this repo previously.

| Phase | Goal | Roughly |
|---|---|---|
| **0 — Stop the bleeding** | Rotate leaked secrets, drop false-claim docs, gate CI, fix CSP, dedupe deps. | _Done — see SECURITY.md_ |
| **1 — Architecture consolidation** | One backend (`src/`), one port, retire the older `vanl/` shell while preserving its physics engines. | Days |
| **2 — Real licensing** | Ed25519-signed license tokens, hardware-bound, 30-day trial without CC, small license server. | Week |
| **3 — Encrypted projects + auth** | Replace plaintext JSON with the `ProjectManager` encryption path, derive keys from license + hardware. | Days |
| **4 — NVIDIA NIM done right** | OpenAI-compatible client, real materials DB, per-user token budget. | Week |
| **5 — C++ engine bug fixes** | `Rs_ohm` wiring, per-species flux convolution, real CN at boundaries, real Lawson–Hanson NNLS, KK validity verdict. | Week |
| **6 — UI honesty pass** | Remove `Math.random()` placeholders, single backend port, validation that doesn't hand-rig pass conditions. | Days |
| **7 — Test suite rewrite** | Real assertions, encryption round-trips, license tampering tests. | Week |
| **8 — Build + ship** | Signed Windows installer, signed AppImage, signature-verified auto-updater. | Week |

---

## Repository layout

```
src/
├── backend/          FastAPI app, simulation routes, licensing scaffolding
├── frontend/         Electron renderer (React + Vite)
├── desktop/          Electron main + preload
└── ai_engine/        Local Qwen + LoRA agent, NVIDIA NIM client (being rewritten)

engine_core/          C++ physics library (Eigen + OpenMP, pybind11 bindings)

vanl/                 Older Python backend; physics engines + research pipeline.
                      Being folded into src/ over time.

tests/                Unit + integration tests (rewrite in progress)
scripts/              Build helpers (C++, Electron, Nuitka)
docs/                 Research papers and (eventually) user guide
```

---

## Honesty note

If you are reviewing this repo and find a claim in any document that is
contradicted by the code, treat the code as authoritative and please open an
issue. Earlier versions of this README and several other markdown files
contained marketing claims (e.g. “10/10 security”, “8 physics engines”, “21 CFR
Part 11 compliant”) that the implementation did not back up. Those claims
have been removed.

---

## License

Commercial. © VidyuthLabs.

## Contact

VidyuthLabs — <support@vidyuthlabs.co.in>
