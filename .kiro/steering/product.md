# Product Overview

## VANL — Virtual Autonomous Nanomaterials Lab

Physics-informed digital twin platform for printed electronics research. Provides validated simulation engines for the entire printed electronics workflow: ink formulation → printing simulation → device physics → electrochemical characterization.

### Core Capabilities

**Electrochemical Simulation Engines:**
- **EIS** (Electrochemical Impedance Spectroscopy): Modified Randles circuit with CPE
- **CV** (Cyclic Voltammetry): Butler-Volmer kinetics with Nicholson-Shain analysis
- **GCD** (Galvanostatic Charge-Discharge): Constant current with IR drop modeling

**Printed Electronics Digital Twins:**
- **Ink Engine**: Rheology, printability metrics (Oh/Re/We/Z), percolation conductivity
- **Supercapacitor Device**: EDLC + pseudocapacitance with Ragone analysis
- **Battery Device**: Single Particle Model with Butler-Volmer kinetics
- **Biosensor**: Michaelis-Menten enzyme kinetics with electrochemical detection

**Research Tools:**
- Materials database (48 literature-sourced materials with validated properties)
- Bayesian optimization for autonomous material discovery
- Uncertainty quantification (90% confidence intervals)
- Kramers-Kronig validation for data quality
- Cost analysis with reagent-level estimation

### Companion Tool: AnalyteX MicroWell Designer

Parametric CAD tool for designing electrochemical micro-well electrode substrates. Generates scientifically accurate 3D models (STEP/STL) with:
- Parametric well geometry (diameter, depth, taper, fillets)
- Array layouts (single, linear, rectangular, hexagonal)
- Scientific constraint validation (Bond number, contact-line pinning)
- Droplet simulation (Young-Laplace spherical cap model)
- Real-time 3D preview with OpenGL

## Target Users

Research scientists and engineers working on:
- Printed electronics (supercapacitors, batteries, sensors)
- Electrochemical characterization
- Material formulation and optimization
- Screen-printed electrode (SPE) design
