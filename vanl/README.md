# VANL - Virtual Autonomous Nanomaterials Lab

**Physics-Informed Digital Twin Platform for Printed Electronics & Nanomaterial Electrochemistry**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🎯 Overview

VANL is a comprehensive simulation platform for electrochemical devices and printed electronics. It combines rigorous physics models with machine learning to predict material properties, optimize compositions, and simulate device performance.

### Key Features

- **8 Physics Engines**: EIS, CV, GCD, Ink Formulation, Biosensors, Batteries, Supercapacitors, Materials
- **50+ Materials Database**: Literature-sourced properties with full provenance
- **Bayesian Optimization**: Autonomous material discovery
- **Research Pipeline**: Automated literature mining from arXiv, CrossRef, Semantic Scholar
- **Uncertainty Quantification**: 90% confidence intervals on all predictions
- **REST API**: FastAPI-based with automatic OpenAPI documentation

---

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd vanl

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
python -m uvicorn vanl.backend.main:app --reload --port 8000
```

### First API Call

```bash
# Health check
curl http://localhost:8000/api/health

# Simulate EIS
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"Rs": 10, "Rct": 100, "Cdl": 1e-5, "sigma_warburg": 50, "n_cpe": 0.9}'
```

### Web Interface

Open browser: `http://localhost:8000/`

---

## 📚 Documentation

### API Endpoints

#### Core Electrochemistry

- `GET /api/health` - Health check
- `GET /api/materials` - List materials database
- `POST /api/predict` - Predict EIS from composition + synthesis
- `POST /api/simulate` - Direct EIS simulation
- `POST /api/optimize` - Bayesian optimization
- `POST /api/validate/kk` - Kramers-Kronig validation
- `GET /api/validate/perovskite` - Validate against experimental data

#### Printed Electronics

- `POST /api/pe/ink/simulate` - Ink formulation & rheology
- `POST /api/pe/supercap/simulate` - Supercapacitor device
- `POST /api/pe/battery/simulate` - Printed battery
- `POST /api/pe/biosensor/simulate` - Biosensor performance

#### Research Pipeline

- `GET /api/pipeline/stats` - Database statistics
- `POST /api/pipeline/search` - Search extracted data

### Interactive API Docs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 🔬 Physics Models

### EIS (Electrochemical Impedance Spectroscopy)

**Model:** Modified Randles Circuit
```
Z(ω) = Rs + 1/(Y_CPE(jω) + 1/(Rct + Z_W(ω)))
```

**Components:**
- Rs: Solution resistance
- Rct: Charge transfer resistance
- CPE: Constant Phase Element (non-ideal capacitance)
- Z_W: Warburg impedance (diffusion)

**References:**
- Bard & Faulkner, "Electrochemical Methods" 3rd Ed.
- Orazem & Tribollet, "Electrochemical Impedance Spectroscopy" (2008)

### CV (Cyclic Voltammetry)

**Model:** Butler-Volmer + Nicholson-Shain Convolution
```
i(E) = i_faradaic(E) + i_capacitive(E)
```

**Features:**
- Semi-infinite planar diffusion
- Quasi-reversible kinetics
- Peak detection & analysis
- Randles-Sevcik validation

**References:**
- Nicholson & Shain, Anal. Chem. 36, 706-723 (1964)
- Compton & Banks, "Understanding Voltammetry" 3rd Ed.

### Ink Formulation

**Models:**
- Krieger-Dougherty viscosity
- Percolation theory for conductivity
- Ohnesorge/Reynolds/Weber printability

**Printing Methods Supported:**
- Screen printing
- Inkjet
- Aerosol jet
- Gravure, Flexography, Slot-die, Spray, Blade coating

**References:**
- Derby, Annu. Rev. Mater. Res. 40, 395-414 (2010)
- Kamyshny & Magdassi, Small 10, 3515-3535 (2014)

### Biosensors

**Models:**
- Michaelis-Menten enzyme kinetics
- Cottrell chronoamperometry
- Randles-Sevcik voltammetry
- LOD/LOQ (IUPAC 3σ/10σ method)

**Detection Modes:**
- Amperometric
- Impedimetric
- Voltammetric (DPV/SWV)
- Potentiometric

**Analytes:** Glucose, lactate, cholesterol, dopamine, uric acid, cortisol, DNA, pH

### Batteries

**Models:**
- Single Particle Model (SPM)
- Butler-Volmer charge transfer
- Peukert's law for rate capability
- SEI growth aging model

**Chemistries:**
- Zn-MnO₂ (alkaline)
- Ag₂O-Zn (silver oxide)
- LiFePO₄ (Li-ion)
- LiCoO₂ (Li-ion)

### Supercapacitors

**Models:**
- Transmission Line Model (TLM) for porous electrodes
- Series capacitance combination
- ESR breakdown analysis
- Ragone plot generation

**Features:**
- Symmetric & asymmetric devices
- Self-discharge modeling
- Cycling stability prediction
- CV at multiple scan rates

---

## 🗄️ Materials Database

### Categories

- **Carbon Materials** (11): Graphene, rGO, GO, CNT, SWCNT, MWCNT, carbon black, activated carbon, graphite, carbon aerogel, carbon fiber
- **Metal Oxides** (15): MnO₂, NiO, Fe₂O₃, Fe₃O₄, Co₃O₄, RuO₂, TiO₂, ZnO, V₂O₅, CuO, WO₃, SnO₂, MoO₃, Nb₂O₅, NiCo₂O₄
- **Conducting Polymers** (4): PEDOT:PSS, polyaniline, polypyrrole, polythiophene
- **Noble Metals** (3): Au NP, Ag NP, Pt NP
- **Battery Materials** (5): LiFePO₄, LiCoO₂, NMC_811, Li₄Ti₅O₁₂, silicon
- **Perovskites** (4): BaTiO₃, SrTiO₃, LaMnO₃, MAPbI₃
- **Additives** (2+): Nafion, PVDF

### Properties Included

- Conductivity (S/m)
- Surface area (m²/g)
- Density (g/cm³)
- Crystal structure
- Electrochemical window (V)
- Specific capacitance (F/g)
- Diffusion coefficient (cm²/s)
- Cost ($/g)
- Literature sources (DOIs)

---

## 🤖 Research Pipeline

### Automated Literature Mining

**Sources:**
- arXiv (physics, materials science)
- CrossRef (peer-reviewed journals)
- Semantic Scholar (AI-powered search)
- Materials Project (computational database)

**Extraction:**
- Material compositions
- Synthesis methods (temperature, pH, duration)
- EIS parameters (Rs, Rct, Cdl, capacitance)
- Performance metrics

**Database Schema:**
```sql
papers (id, title, authors, abstract, doi, arxiv_id, year, ...)
materials (paper_id, component, ratio, confidence, ...)
synthesis (paper_id, method, temperature_C, pH, ...)
eis_data (paper_id, Rs_ohm, Rct_ohm, Cdl_F, capacitance_F_g, ...)
```

### Running the Pipeline

```bash
# Run full pipeline
python -m vanl.research_pipeline.scheduler --run-once

# Scheduled updates (every 24h)
python -m vanl.research_pipeline.scheduler --daemon

# Query database
python -m vanl.research_pipeline.search --material "graphene" --application "supercapacitor"
```

---

## 🧪 Examples

### Example 1: Material Prediction

```python
import requests

response = requests.post("http://localhost:8000/api/predict", json={
    "composition": {
        "graphene": 0.6,
        "MnO2": 0.3,
        "carbon_black": 0.1
    },
    "synthesis": {
        "method": "hydrothermal",
        "temperature_C": 120,
        "duration_hours": 6,
        "pH": 7
    }
})

result = response.json()
print(f"Predicted Rct: {result['eis_params']['Rct_ohm']} Ω")
print(f"Capacitance: {result['eis_params']['Cdl_F']} F")
```

### Example 2: Bayesian Optimization

```python
response = requests.post("http://localhost:8000/api/optimize", json={
    "materials": ["graphene", "MnO2", "carbon_black"],
    "n_iterations": 30,
    "weight_Rct": 0.4,
    "weight_Rs": 0.2,
    "weight_capacitance": 0.4,
    "max_cost": 3.0
})

best = response.json()["best_result"]
print(f"Optimal composition: {best['composition']}")
print(f"Objective value: {best['objective_value']}")
```

### Example 3: Ink Formulation

```python
response = requests.post("http://localhost:8000/api/pe/ink/simulate", json={
    "filler_material": "graphene",
    "filler_loading_wt_pct": 10.0,
    "particle_size_nm": 500,
    "aspect_ratio": 100,
    "primary_solvent": "water",
    "print_method": "screen_printing"
})

ink = response.json()
print(f"Viscosity: {ink['viscosity_mPas']} mPa·s")
print(f"Sheet resistance: {ink['sheet_resistance_ohm_sq']} Ω/□")
print(f"Printability score: {ink['printability_score']}")
```

### Example 4: Biosensor Design

```python
response = requests.post("http://localhost:8000/api/pe/biosensor/simulate", json={
    "analyte": "glucose",
    "sensor_type": "amperometric",
    "electrode_material": "carbon_black",
    "modifier": "enzyme",
    "area_mm2": 7.07,
    "enzyme_loading_U_cm2": 10.0,
    "pH": 7.4,
    "applied_potential_V": 0.6
})

biosensor = response.json()
print(f"Sensitivity: {biosensor['sensitivity_uA_mM']} µA/mM")
print(f"LOD: {biosensor['LOD_uM']} µM")
print(f"Linear range: {biosensor['linear_range_mM']} mM")
```

---

## 🧪 Testing

### Run Tests

```bash
# All tests
pytest vanl/backend/tests/ -v

# Specific module
pytest vanl/backend/tests/test_core.py -v

# With coverage
pytest vanl/backend/tests/ --cov=vanl --cov-report=html
```

### Current Coverage

- ✅ Core modules: 85%
- ⚠️ New engines: 0% (tests needed)
- ⚠️ API routes: 0% (integration tests needed)

---

## 🏗️ Architecture

```
vanl/
├── backend/
│   ├── api/              # FastAPI routes
│   │   ├── routes.py     # Core electrochemistry endpoints
│   │   └── pe_routes.py  # Printed electronics endpoints
│   ├── core/             # Physics engines
│   │   ├── eis_engine.py
│   │   ├── cv_engine.py
│   │   ├── gcd_engine.py
│   │   ├── ink_engine.py
│   │   ├── biosensor_engine.py
│   │   ├── battery_engine.py
│   │   ├── supercap_device_engine.py
│   │   ├── materials.py
│   │   ├── materials_db.py
│   │   ├── synthesis_engine.py
│   │   ├── optimizer.py
│   │   ├── kk_validation.py
│   │   └── uncertainty.py
│   ├── ml/               # Machine learning models
│   └── tests/            # Unit tests
├── frontend/             # Web UI
│   ├── index.html
│   ├── app.js
│   └── style.css
├── research_pipeline/    # Automated literature mining
│   ├── pipeline.py
│   ├── fetchers/
│   ├── processors/
│   └── schema.py
└── datasets/             # Data storage
    ├── external/         # Experimental datasets
    ├── synthetic/        # Generated training data
    └── research/         # Mined literature data
```

---

## 🔒 Security (Production)

**⚠️ Current Status:** Development-only, not production-ready

**Required for Production:**
1. Add JWT authentication
2. Add rate limiting
3. Restrict CORS origins
4. Add HTTPS enforcement
5. Add input sanitization
6. Add API key management
7. Add security headers

See `VANL_COMPREHENSIVE_REVIEW.md` for detailed security recommendations.

---

## 🚢 Deployment

### Docker (Recommended)

```bash
# Build image
docker build -t vanl:latest .

# Run container
docker run -p 8000:8000 vanl:latest
```

### Docker Compose

```bash
docker-compose up -d
```

### Production (Gunicorn)

```bash
gunicorn vanl.backend.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

---

## 📊 Performance

### Benchmarks (Intel i7, 16GB RAM)

| Operation | Time | Throughput |
|-----------|------|------------|
| EIS simulation (100 pts) | 2 ms | 500 req/s |
| CV simulation (2000 pts) | 50 ms | 20 req/s |
| Material prediction | 10 ms | 100 req/s |
| Bayesian optimization (30 iter) | 5 s | - |

### Optimization Tips

1. Use caching for repeated simulations
2. Reduce CV points for faster computation
3. Use async for long-running tasks
4. Consider GPU for ML models

---

## 🤝 Contributing

We welcome contributions! Please see `CONTRIBUTING.md` for guidelines.

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run linting
ruff check vanl/
black vanl/

# Run type checking
mypy vanl/
```

---

## 📄 License

MIT License - see `LICENSE` file for details.

---

## 📚 Citation

If you use VANL in your research, please cite:

```bibtex
@software{vanl2026,
  title={VANL: Virtual Autonomous Nanomaterials Lab},
  author={VidyuthLabs},
  year={2026},
  url={https://github.com/your-org/vanl}
}
```

---

## 🙏 Acknowledgments

### Physics Models
- Bard & Faulkner - Electrochemical Methods
- Newman & Thomas-Alyea - Electrochemical Systems
- Conway - Electrochemical Supercapacitors

### Data Sources
- Materials Project (materialsproject.org)
- NIST Standard Reference Data
- arXiv, CrossRef, Semantic Scholar

### Libraries
- FastAPI, NumPy, SciPy, scikit-learn
- Plotly, 3Dmol.js, Three.js

---

## 📞 Contact

- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions
- **Email:** support@vidyuthlabs.com

---

## 🗺️ Roadmap

### v1.0 (Current)
- ✅ 8 physics engines
- ✅ 50+ materials database
- ✅ Research pipeline
- ✅ REST API

### v1.1 (Next)
- ⏳ Complete test coverage
- ⏳ Production security
- ⏳ Docker deployment
- ⏳ CI/CD pipeline

### v2.0 (Future)
- 🔮 GPU acceleration
- 🔮 Real-time collaboration
- 🔮 Mobile app
- 🔮 Lab equipment integration

---

**Built with ❤️ by VidyuthLabs**
