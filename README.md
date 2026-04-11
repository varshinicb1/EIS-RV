# VANL — Virtual Autonomous Nanomaterials Lab

**Physics-informed digital twin platform for printed electronics: supercapacitors, batteries, biosensors.**

> Ink formulation → printing simulation → device physics → electrochemical characterization — all in one platform.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue)

---

## 🔬 What is VANL?

VANL is a **research-grade simulation platform** that provides physics-based digital twins for the entire printed electronics workflow. Every simulation uses validated physical models — **no fabricated data**.

### Simulation Engines

| Engine | Model | Key Outputs |
|--------|-------|-------------|
| **EIS** | Modified Randles circuit (Rs + CPE ∥ (Rct + Zw)) | Nyquist, Bode, circuit parameters |
| **CV** | Butler-Volmer + Nicholson-Shain | Voltammograms, peak analysis, reversibility |
| **GCD** | Constant current with IR drop + pseudocapacitance | Charge-discharge curves, specific capacitance |
| **Ink Engine** | Krieger-Dougherty + Herschel-Bulkley + percolation | Viscosity, printability (Oh/Re/We/Z), conductivity |
| **Supercapacitor** | EDLC + pseudocap + TLM + Ragone | Device capacitance, energy/power density, cycling |
| **Battery** | SPM + Butler-Volmer + Peukert + OCV polynomials | Discharge curves, rate capability, aging, EIS |
| **Biosensor** | Michaelis-Menten + Randles-Sevcik + Cottrell | Calibration, LOD/LOQ, chronoamperometry, DPV |

### Additional Features

- **Materials Database**: 48 literature-sourced materials with validated properties (NIST, Materials Project)
- **Bayesian Optimization**: Autonomous material composition optimization with Gaussian Process surrogate
- **Uncertainty Quantification**: 90% confidence intervals on all predictions
- **Kramers-Kronig Validation**: Data quality checks for EIS spectra
- **Research Pipeline**: Automated literature mining from 2,400+ papers with DOI tracing
- **Cost Analysis**: Reagent-level cost estimation with scale-up projections

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/EIS-RV.git
cd EIS-RV

# Install dependencies
pip install -r vanl/requirements.txt

# Run the server
python -m uvicorn vanl.backend.main:app --reload --port 8000
```

Open http://localhost:8000 for the full frontend interface, or http://localhost:8000/docs for the Swagger API documentation.

### Run Tests

```bash
python -m pytest vanl/backend/tests/test_core.py -v
```

---

## 📁 Project Structure

```
EIS-RV/
├── vanl/                           # Virtual Autonomous Nanomaterials Lab
│   ├── backend/
│   │   ├── main.py                 # FastAPI application entry point
│   │   ├── api/
│   │   │   ├── routes.py           # Core API endpoints (EIS, CV, GCD, predict, optimize)
│   │   │   └── pe_routes.py        # Printed electronics endpoints (ink, supercap, battery, biosensor)
│   │   ├── core/
│   │   │   ├── eis_engine.py       # Electrochemical Impedance Spectroscopy
│   │   │   ├── cv_engine.py        # Cyclic Voltammetry
│   │   │   ├── gcd_engine.py       # Galvanostatic Charge-Discharge
│   │   │   ├── ink_engine.py       # Conductive Ink Formulation & Rheology
│   │   │   ├── supercap_device_engine.py  # Supercapacitor Device
│   │   │   ├── battery_engine.py   # Printed Battery (SPM)
│   │   │   ├── biosensor_engine.py # Electrochemical Biosensor
│   │   │   ├── materials.py        # Material representations & physics
│   │   │   ├── materials_db.py     # 48-material literature database
│   │   │   ├── synthesis_engine.py # Synthesis simulation
│   │   │   ├── optimizer.py        # Bayesian optimization
│   │   │   ├── autonomous.py       # Autonomous experiment loop
│   │   │   ├── kk_validation.py    # Kramers-Kronig validation
│   │   │   ├── uncertainty.py      # Uncertainty quantification
│   │   │   ├── validation.py       # Perovskite dataset validation
│   │   │   └── data_loader.py      # External dataset loading
│   │   ├── ml/
│   │   │   ├── models.py           # Neural network surrogate models
│   │   │   └── training.py         # Model training pipeline
│   │   └── tests/
│   │       └── test_core.py        # 30 unit tests (all passing)
│   ├── frontend/
│   │   ├── index.html              # Single-page application
│   │   ├── app.js                  # Frontend logic (Plotly.js charts)
│   │   └── style.css               # Scientist-grade dark theme
│   ├── research_pipeline/          # Automated literature mining
│   │   ├── pipeline.py             # Paper fetching & processing
│   │   ├── search.py               # Full-text search
│   │   ├── schema.py               # SQLite schema
│   │   └── fetchers/               # arXiv, Crossref, Semantic Scholar
│   ├── datasets/                   # Generated & external datasets
│   └── requirements.txt
├── analytex_microwell_designer/    # Companion tool: SPE MicroWell Designer
└── README.md
```

---

## 🔌 API Endpoints

### Core Electrochemistry
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/materials` | List materials |
| GET | `/api/materials/full` | Full 48-material database |
| POST | `/api/simulate` | EIS simulation from circuit parameters |
| POST | `/api/predict` | Material → EIS prediction with UQ |
| POST | `/api/optimize` | Bayesian optimization |
| POST | `/api/cv/simulate` | Cyclic voltammetry simulation |
| POST | `/api/gcd/simulate` | GCD simulation |
| POST | `/api/validate/kk` | Kramers-Kronig validation |
| POST | `/api/cost/estimate` | Cost analysis |

### Printed Electronics
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/pe/ink/simulate` | Ink formulation simulation |
| POST | `/api/pe/ink/rheology` | Full rheology flow curve |
| POST | `/api/pe/supercap/simulate` | Supercapacitor device |
| POST | `/api/pe/battery/simulate` | Printed battery |
| POST | `/api/pe/biosensor/simulate` | Electrochemical biosensor |
| POST | `/api/pe/device/structure` | 3D device layer stack |

---

## 🧪 Example API Calls

### EIS Simulation
```bash
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"Rs": 10, "Rct": 100, "Cdl": 1e-5, "sigma_warburg": 50, "n_cpe": 0.9}'
```

### Ink Formulation
```bash
curl -X POST http://localhost:8000/api/pe/ink/simulate \
  -H "Content-Type: application/json" \
  -d '{"filler_material": "graphene", "filler_loading_wt_pct": 10, "print_method": "screen_printing"}'
```

### Battery Simulation
```bash
curl -X POST http://localhost:8000/api/pe/battery/simulate \
  -H "Content-Type: application/json" \
  -d '{"chemistry": "zinc_MnO2", "area_cm2": 1.0, "C_rate": 0.5}'
```

---

## 📚 Physics Models & References

1. **EIS**: Randles circuit with CPE (Lasia, "Electrochemical Impedance Spectroscopy", 2014)
2. **CV**: Butler-Volmer kinetics (Bard & Faulkner, "Electrochemical Methods", 2001)
3. **Ink Rheology**: Krieger-Dougherty + Herschel-Bulkley (Derby, Annu. Rev. Mater. Res. 40, 2010)
4. **Percolation**: Excluded volume theory (Balberg, Phys. Rev. B 33, 1984)
5. **Battery**: Single Particle Model (Newman & Thomas-Alyea, "Electrochemical Systems", 2004)
6. **Biosensor**: Michaelis-Menten enzyme kinetics (Bartlett, "Bioelectrochemistry", 2008)
7. **Supercapacitor**: Transmission Line Model (Conway, "Electrochemical Supercapacitors", 1999)

---

## 🛠️ Development

```bash
# Run with auto-reload for development
python -m uvicorn vanl.backend.main:app --reload --port 8000

# Run tests
python -m pytest vanl/backend/tests/ -v

# Generate datasets
python -c "from vanl.backend.core.dataset_gen import generate_and_save_datasets; generate_and_save_datasets()"
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built with ⚡ by VidyuthLabs — Physics-first engineering for printed electronics.*
