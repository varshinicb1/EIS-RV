# AnalyteX MicroWell Designer

> Professional parametric design tool for electrochemical micro-well electrode substrates with scientifically accurate 3D model generation (STEP/STL).

---

## Overview

AnalyteX MicroWell Designer generates CAD-accurate 3D models of micro-well substrates used for electrochemical sensing, optimized for:

- **Drop-casting** of functional inks
- **Controlled liquid confinement** via capillary forces
- **Reproducible electrochemical measurements** (CV, EIS, DPV)

All geometry is generated as **watertight BRep solids** using OpenCascade (via CadQuery), exported as **ISO 10303 STEP files** ready for 3D printing or CNC machining.

---

## Features

| Feature | Description |
|---------|-------------|
| **Parametric Well Geometry** | Diameter, depth, taper angle, fillet radius, bottom fillet |
| **Array Layouts** | Single, linear, rectangular, hexagonal patterns |
| **Scientific Constraints** | Bond number, wall angle, contact-line pinning, volume compatibility |
| **Multi-Electrode Layout** | Working (WE), reference (RE), counter (CE) electrode regions |
| **Contact Channels** | Grooves for copper tape, contact pads, snap-fit connectors |
| **Surface Engineering** | Hydrophilic/hydrophobic zone configuration with contact angles |
| **Droplet Simulation** | Young-Laplace spherical cap model with evaporation estimates |
| **3D Preview** | Real-time OpenGL viewer with rotate/zoom/pan and electrode annotations |
| **Design Validation** | Manufacturing checks (FDM/SLA/CNC) + scientific constraint validation |
| **STEP/STL Export** | ISO 10303 compliant STEP files + STL for slicers |
| **Parametric Sweep** | Generate multiple variants by sweeping any parameter |
| **Preset Library** | 6 built-in presets for common electrochemical configurations |
| **Save/Load Profiles** | JSON-based design profile persistence |

---

## Installation

### Option 1: Conda (Recommended)

CadQuery installs most reliably via conda:

```bash
# Create and activate environment
conda env create -f environment.yml
conda activate analytex

# Launch the application
python main.py
```

### Option 2: Conda + pip (Manual)

```bash
# Create conda environment
conda create -n analytex python=3.11
conda activate analytex

# Install CadQuery (OpenCascade kernel)
conda install -c conda-forge cadquery

# Install GUI and visualization
pip install PyQt6 pyqtgraph PyOpenGL numpy
```

### Option 3: pip only

> ⚠ CadQuery via pip may require additional build tools on some systems.

```bash
pip install cadquery PyQt6 pyqtgraph PyOpenGL numpy
```

---

## Usage

### GUI Application

```bash
cd analytex_microwell_designer
python main.py
```

### Headless STEP Generation (no GUI required)

```bash
python generate_example.py
```

This generates three example STEP files in the `output/` directory:
- `standard_single_well.step` — 3mm diameter, 1mm deep well
- `array_4x2_well.step` — 4×2 rectangular well array
- `high_sensitivity_well.step` — 2mm tapered well

---

## User Interface

```
┌──────────────────────────────────────────────────────────────┐
│  File  Edit  Presets  Tools  View  Help                      │
├──────────┬──────────────────────────┬────────────────────────┤
│ LEFT     │  CENTER                  │  RIGHT                 │
│ PANEL    │  3D VIEWER               │  PANEL                 │
│          │                          │                        │
│ Well     │  ┌────────────────────┐  │  Validation            │
│ Geometry │  │                    │  │  ───────────           │
│ ────── │  │   3D Preview       │  │  ✓ Bond Number OK      │
│ Ø [3.0]  │  │   (OpenGL)         │  │  ✓ Wall Angle OK      │
│ h [1.0]  │  │                    │  │  ⚠ Edge Fillet        │
│ α [3.0°] │  │                    │  │                        │
│ r [0.1]  │  └────────────────────┘  │  Simulation            │
│          │  Reset|Top|Front|Side    │  ──────────            │
│ Substrate│                          │  Vol: 5.2 µL           │
│ Array    │                          │  Fill: 73%             │
│ Surface  │                          │                        │
│ Electrode│                          │  Export                │
│ Channels │                          │  ──────                │
│          │                          │  [STEP] [STL]          │
│ [Generate]│                         │                        │
├──────────┴──────────────────────────┴────────────────────────┤
│  ✓ Model generated — 1 well, 11.0 × 11.0 × 2.5 mm          │
└──────────────────────────────────────────────────────────────┘
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `F5` | Generate Model |
| `F6` | Run Validation |
| `Ctrl+E` | Export STEP |
| `Ctrl+S` | Save Profile |
| `Ctrl+O` | Load Profile |
| `Ctrl+Shift+S` | Parametric Sweep |
| `Home` | Reset Camera |

---

## Scientific Background

### Capillary Confinement (Bond Number)

The Bond number determines whether surface tension (capillary forces) or gravity dominates liquid behavior:

```
Bo = ρgL² / γ
```

Where:
- ρ = liquid density (998 kg/m³ for water)
- g = gravitational acceleration (9.81 m/s²)
- L = well radius (characteristic length)
- γ = surface tension (72.8 mN/m for water at 20°C)

**Criterion:** Bo < 0.3 for excellent capillary confinement.

### Contact-Line Pinning (Gibbs Criterion)

Sharp edges at the well rim pin the liquid contact line, preventing spillover. The edge fillet radius must be significantly smaller than the capillary length:

```
λ_c = √(γ / ρg) ≈ 2.73 mm
```

**Criterion:** fillet_radius < 0.27 mm (0.1 × λ_c)

### Droplet Volume (Spherical Cap)

For a sessile droplet confined in a cylindrical well with contact angle θ:

```
R_sphere = r_well / sin(θ)
h_cap = R_sphere × (1 - cos(θ))
V = πh²(3R - h) / 3
```

### Evaporation Model

Diffusion-limited evaporation (Hu & Larson):

```
dm/dt ≈ -π × D × r × Δc × f(θ)
f(θ) ≈ 0.27θ² + 1.30
```

---

## Project Structure

```
analytex_microwell_designer/
├── main.py                         # Application entry point
├── generate_example.py             # Headless STEP generator
├── requirements.txt                # pip dependencies
├── environment.yml                 # conda environment
├── README.md                       # This file
│
├── analytex/
│   ├── __init__.py
│   ├── core/
│   │   ├── geometry_engine.py      # Parametric CAD kernel (CadQuery/OCC)
│   │   ├── constraints.py          # Scientific constraint validation
│   │   ├── validation.py           # Manufacturing validation engine
│   │   ├── droplet_sim.py          # Droplet simulation (Young-Laplace)
│   │   ├── presets.py              # Built-in preset library
│   │   └── exporter.py            # STEP/STL export module
│   │
│   ├── ui/
│   │   ├── main_window.py          # Main application window
│   │   ├── parameter_panel.py      # Left panel (parameter inputs)
│   │   ├── viewer_widget.py        # Center 3D viewer (OpenGL)
│   │   ├── validation_panel.py     # Right panel (validation/sim/export)
│   │   ├── sweep_dialog.py         # Parametric sweep dialog
│   │   └── styles.py              # Dark engineering UI theme
│   │
│   └── utils/
│       ├── mesh_utils.py           # OCC→mesh conversion for viewer
│       └── profile_io.py           # Profile save/load
│
├── presets/                        # Built-in preset JSON files
│   ├── standard_well.json
│   ├── high_sensitivity.json
│   ├── low_volume.json
│   └── array_sensing.json
│
└── output/                        # Default export directory
```

---

## Built-in Presets

| Preset | Diameter | Depth | Taper | Volume | Use Case |
|--------|----------|-------|-------|--------|----------|
| Standard Electrochemical Well | 3.0 mm | 1.0 mm | 3° | ~7 µL | General CV/EIS |
| High-Sensitivity Well | 2.0 mm | 1.5 mm | 2° | ~4.7 µL | Trace detection |
| Low-Volume Micro-Well | 1.0 mm | 0.5 mm | 1° | ~0.4 µL | Precious samples |
| Array-Based Sensing | 3.0×8 | 1.0 mm | 3° | ~56 µL | Multiplexed sensing |
| Three-Electrode Cell | 4.0 mm | 1.2 mm | 3° | ~15 µL | Full EC cell |
| SPE Compatible Well | 5.0 mm | 1.0 mm | 5° | ~19 µL | Screen-printed electrodes |

---

## Architecture

```
DesignProfile (parameters)
    │
    ├── GeometryEngine.generate()  →  CadQuery Workplane (BRep solid)
    │       │
    │       ├── Substrate creation (rounded rectangle extrude)
    │       ├── Well cutting (frustum boolean subtraction)
    │       ├── Electrode layout (RE/CE pad recesses)
    │       ├── Contact channels (groove/pad cuts)
    │       └── Fillet application
    │
    ├── validate_design()          →  ConstraintReport
    │       ├── Bond number check
    │       ├── Wall angle check
    │       ├── Edge sharpness check
    │       └── Volume compatibility check
    │
    ├── validate_for_manufacturing() → ValidationReport
    │       ├── Feature size checks
    │       ├── Wall thickness checks
    │       └── Overhang checks
    │
    ├── compute_droplet_profile()  →  DropletProfile
    │       ├── Spherical cap geometry
    │       ├── Volume / fill ratio
    │       └── Laplace pressure
    │
    └── export_step() / export_stl() → STEP / STL file
```

---

## Requirements

- **Python** 3.10+
- **CadQuery** 2.4+ (OpenCascade kernel)
- **PyQt6** 6.5+
- **pyqtgraph** 0.13+
- **PyOpenGL** 3.1+
- **NumPy** 1.24+

---

## License

This software is provided for research and educational purposes.

---

## Credits

- **CAD Kernel:** [CadQuery](https://github.com/CadQuery/cadquery) / OpenCascade
- **GUI Framework:** [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- **3D Visualization:** [pyqtgraph](https://www.pyqtgraph.org/)
