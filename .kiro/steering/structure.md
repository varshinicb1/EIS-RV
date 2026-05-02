# Project Structure

## Repository Organization

This is a **multi-project repository** containing two main applications:

1. **VANL** (Virtual Autonomous Nanomaterials Lab) - Physics simulation platform
2. **AnalyteX MicroWell Designer** - CAD tool for electrode substrate design

## Top-Level Structure

```
EIS-RV/
├── vanl/                          # Main simulation platform
├── analytex_microwell_designer/   # CAD design tool
├── EIS-RV/                        # Legacy/additional modules
├── .kiro/                         # Kiro AI assistant configuration
├── .github/                       # GitHub workflows and CI/CD
├── Dockerfile                     # Production container for VANL
├── docker-compose.yml             # Multi-container orchestration
├── app.yaml                       # Google Cloud Run config
├── cloudbuild.yaml                # Cloud Build configuration
└── *.pdf, *.docx                  # Research papers and documentation
```

## VANL Structure

```
vanl/
├── backend/
│   ├── main.py                    # FastAPI application entry point
│   ├── api/
│   │   ├── routes.py              # Core electrochemistry endpoints
│   │   └── pe_routes.py           # Printed electronics endpoints
│   ├── core/                      # Physics simulation engines
│   │   ├── eis_engine.py          # Impedance spectroscopy
│   │   ├── cv_engine.py           # Cyclic voltammetry
│   │   ├── gcd_engine.py          # Charge-discharge
│   │   ├── ink_engine.py          # Ink formulation & rheology
│   │   ├── supercap_device_engine.py  # Supercapacitor device
│   │   ├── battery_engine.py      # Battery device (SPM)
│   │   ├── biosensor_engine.py    # Biosensor simulation
│   │   ├── materials.py           # Material representations
│   │   ├── materials_db.py        # 48-material database
│   │   ├── synthesis_engine.py    # Synthesis simulation
│   │   ├── optimizer.py           # Bayesian optimization
│   │   ├── autonomous.py          # Autonomous experiment loop
│   │   ├── kk_validation.py       # Kramers-Kronig validation
│   │   ├── uncertainty.py         # Uncertainty quantification
│   │   ├── validation.py          # Dataset validation
│   │   └── data_loader.py         # External data loading
│   ├── ml/
│   │   ├── models.py              # Neural network surrogates
│   │   └── training.py            # Model training pipeline
│   └── tests/
│       └── test_core.py           # Unit tests (30+ tests)
├── frontend/
│   ├── index.html                 # Single-page application
│   ├── app.js                     # Frontend logic (Plotly.js)
│   └── style.css                  # Dark theme styling
├── research_pipeline/             # Automated literature mining
│   ├── pipeline.py                # Paper fetching & processing
│   ├── search.py                  # Full-text search
│   ├── schema.py                  # SQLite schema
│   ├── fetchers/                  # arXiv, Crossref, Semantic Scholar
│   └── processors/                # Text extraction & analysis
├── datasets/
│   ├── synthetic/                 # Generated datasets
│   ├── external/                  # External datasets
│   └── research/                  # Research pipeline outputs
└── requirements.txt               # Python dependencies
```

## AnalyteX MicroWell Designer Structure

```
analytex_microwell_designer/
├── main.py                        # GUI application entry point
├── generate_example.py            # Headless STEP generator
├── requirements.txt               # pip dependencies
├── environment.yml                # conda environment
├── analytex/
│   ├── core/                      # CAD and physics engines
│   │   ├── geometry_engine.py     # Parametric CAD (CadQuery/OCC)
│   │   ├── constraints.py         # Scientific constraint validation
│   │   ├── validation.py          # Manufacturing validation
│   │   ├── droplet_sim.py         # Droplet simulation (Young-Laplace)
│   │   ├── presets.py             # Built-in preset library
│   │   └── exporter.py            # STEP/STL export
│   ├── ui/                        # PyQt6 GUI components
│   │   ├── main_window.py         # Main application window
│   │   ├── parameter_panel.py     # Left panel (inputs)
│   │   ├── viewer_widget.py       # Center 3D viewer (OpenGL)
│   │   ├── validation_panel.py    # Right panel (validation/export)
│   │   ├── sweep_dialog.py        # Parametric sweep dialog
│   │   └── styles.py              # Dark engineering theme
│   └── utils/
│       ├── mesh_utils.py          # OCC→mesh conversion
│       └── profile_io.py          # Profile save/load (JSON)
├── presets/                       # Built-in preset JSON files
│   ├── standard_well.json
│   ├── high_sensitivity.json
│   ├── low_volume.json
│   └── array_sensing.json
└── output/                        # Default export directory (STEP/STL)
```

## Key Architectural Patterns

### VANL Backend
- **Separation of Concerns**: API routes (`api/`) separate from physics engines (`core/`)
- **Engine Pattern**: Each simulation type has dedicated engine module
- **Dual API**: Core electrochemistry vs. printed electronics endpoints
- **Static Frontend**: Frontend served as static files from backend

### AnalyteX Designer
- **MVC Pattern**: Core logic (`core/`) separate from UI (`ui/`)
- **Parametric Design**: All geometry generated from parameters (no hardcoded shapes)
- **Validation Pipeline**: Scientific constraints → Manufacturing checks → Export
- **Preset System**: JSON-based design profiles for reusability

## File Naming Conventions

### Python Modules
- Snake_case for all Python files: `eis_engine.py`, `materials_db.py`
- Test files prefixed with `test_`: `test_core.py`
- Private/internal files prefixed with `_`: `_test_engines.py`

### Configuration Files
- YAML for environments: `environment.yml`, `app.yaml`
- JSON for data: `*.json` (presets, profiles)
- TXT for dependencies: `requirements.txt`

### Output Files
- CAD exports: `*.step` (ISO 10303), `*.stl` (mesh)
- Default output directory: `output/`

## Import Conventions

### VANL
```python
# Absolute imports from vanl root
from vanl.backend.core.eis_engine import simulate_eis
from vanl.backend.api.routes import router
```

### AnalyteX
```python
# Relative imports within analytex package
from analytex.core.geometry_engine import GeometryEngine
from analytex.ui.main_window import MainWindow
```

## Entry Points

- **VANL API**: `vanl/backend/main.py` (FastAPI app)
- **AnalyteX GUI**: `analytex_microwell_designer/main.py` (PyQt6 app)
- **AnalyteX Headless**: `analytex_microwell_designer/generate_example.py`
- **Tests**: `pytest vanl/backend/tests/` or `pytest analytex_microwell_designer/tests/`
