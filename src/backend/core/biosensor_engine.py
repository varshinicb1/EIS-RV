"""
RĀMAN Studio — Biosensor Fabrication Simulation Engine
=======================================================
End-to-end electrochemical biosensor design: electrode patterning,
surface chemistry (SAM/functionalization), ink formulation,
coating physics (spin/dip/inkjet), and performance prediction.
"""
import numpy as np
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ── Electrode Pattern Library ──────────────────────────────────────

ELECTRODE_PATTERNS = {
    "interdigitated": {
        "name": "Interdigitated Array (IDA)",
        "desc": "High surface area for impedimetric biosensors",
        "fingers": 10, "width_um": 50, "gap_um": 50, "length_um": 2000,
        "area_cm2": 0.02, "perimeter_cm": 8.0,
    },
    "disk": {
        "name": "Disk Microelectrode",
        "desc": "Classic 3-electrode cell geometry",
        "diameter_um": 3000, "area_cm2": 0.0707, "perimeter_cm": 0.942,
    },
    "screen_printed": {
        "name": "Screen-Printed Electrode (SPE)",
        "desc": "Low-cost disposable biosensor platform",
        "we_diameter_um": 4000, "re_type": "Ag/AgCl", "ce_material": "Carbon",
        "area_cm2": 0.1257, "perimeter_cm": 1.257,
    },
    "microwell_array": {
        "name": "Microwell Array",
        "desc": "High-throughput parallel sensing",
        "wells": 96, "well_diameter_um": 200, "pitch_um": 500,
        "area_cm2": 0.003, "perimeter_cm": 0.628,
    },
    "vidyutx_v1": {
        "name": "VidyutX V1.0 (VidyuthLabs)",
        "desc": "High-fidelity gold ENIG PCB biosensor platform",
        "we_diameter_um": 4000, "re_type": "Gold", "ce_material": "Gold",
        "substrate": "FR4/Polyimide", "metallization": "ENIG",
        "area_cm2": 0.1257, "perimeter_cm": 1.257,
    },
    "microfluidic": {
        "name": "Microfluidic Channel Cell",
        "desc": "PDMS flow cell with integrated 3-electrode system",
        "channel_width_um": 400, "channel_height_um": 100,
        "channel_length_mm": 10, "flow_rate_uL_min": 10,
        "we_diameter_um": 700, "re_type": "Ag/AgCl", "ce_material": "Pt",
        "substrate": "PDMS/Glass", "volume_nL": 400,
        "area_cm2": 0.00385, "perimeter_cm": 0.22,
    },
}

# ── Ink Formulation Database ───────────────────────────────────────

INK_FORMULATIONS = {
    "carbon_paste": {
        "name": "Carbon Paste Ink",
        "components": [
            {"material": "Graphite powder", "wt_pct": 60, "role": "Conductor"},
            {"material": "Mineral oil (Nujol)", "wt_pct": 35, "role": "Binder"},
            {"material": "Nafion 5%", "wt_pct": 5, "role": "Ion-exchange membrane"},
        ],
        "viscosity_Pa_s": 50.0, "conductivity_S_m": 1e3,
        "contact_angle_deg": 65, "particle_size_um": 5.0,
        "cure_temp_C": 25, "cure_time_min": 60,
    },
    "gold_nanoparticle": {
        "name": "Gold Nanoparticle Ink",
        "components": [
            {"material": "AuNP (20nm)", "wt_pct": 40, "role": "Conductor"},
            {"material": "Toluene", "wt_pct": 45, "role": "Solvent"},
            {"material": "Dodecanethiol", "wt_pct": 10, "role": "Stabilizer"},
            {"material": "Ethyl cellulose", "wt_pct": 5, "role": "Binder"},
        ],
        "viscosity_Pa_s": 12.0, "conductivity_S_m": 4.1e7,
        "contact_angle_deg": 45, "particle_size_um": 0.02,
        "cure_temp_C": 250, "cure_time_min": 30,
    },
    "silver_nanowire": {
        "name": "Silver Nanowire Ink",
        "components": [
            {"material": "AgNW (L/D=500)", "wt_pct": 2, "role": "Conductor"},
            {"material": "Isopropanol", "wt_pct": 88, "role": "Solvent"},
            {"material": "HPMC", "wt_pct": 5, "role": "Viscosity modifier"},
            {"material": "Triton X-100", "wt_pct": 5, "role": "Surfactant"},
        ],
        "viscosity_Pa_s": 8.0, "conductivity_S_m": 6.3e7,
        "contact_angle_deg": 30, "particle_size_um": 0.05,
        "cure_temp_C": 150, "cure_time_min": 20,
    },
    "conductive_polymer": {
        "name": "PEDOT:PSS Ink",
        "components": [
            {"material": "PEDOT:PSS (1.3wt%)", "wt_pct": 65, "role": "Conductor"},
            {"material": "Ethylene glycol", "wt_pct": 5, "role": "Secondary dopant"},
            {"material": "DMSO", "wt_pct": 5, "role": "Conductivity enhancer"},
            {"material": "Water", "wt_pct": 25, "role": "Solvent"},
        ],
        "viscosity_Pa_s": 15.0, "conductivity_S_m": 1e3,
        "contact_angle_deg": 20, "particle_size_um": 0.001,
        "cure_temp_C": 120, "cure_time_min": 15,
    },
}

# ── Surface Chemistry ─────────────────────────────────────────────

SAM_LIBRARY = {
    "thiol_gold": {
        "name": "Thiol-Gold SAM",
        "chemistry": "Au—S—(CH₂)ₙ—COOH",
        "linker": "11-Mercaptoundecanoic acid (MUA)",
        "binding_energy_eV": 1.8,
        "coverage_molecules_cm2": 4.6e14,
        "thickness_nm": 1.5,
        "activation": "EDC/NHS coupling",
        "target_compatibility": ["Antibody", "Aptamer", "Enzyme", "Protein"],
    },
    "silane_oxide": {
        "name": "Silane-Oxide SAM",
        "chemistry": "SiO₂—O—Si—(CH₂)ₙ—NH₂",
        "linker": "APTES (3-Aminopropyltriethoxysilane)",
        "binding_energy_eV": 4.5,
        "coverage_molecules_cm2": 3.1e14,
        "thickness_nm": 0.8,
        "activation": "Glutaraldehyde crosslinking",
        "target_compatibility": ["Antibody", "Enzyme", "DNA"],
    },
    "biotin_streptavidin": {
        "name": "Biotin-Streptavidin Bridge",
        "chemistry": "Surface—Biotin···Streptavidin—Biotin—Probe",
        "linker": "Biotinylated PEG thiol",
        "binding_energy_eV": 0.87,
        "coverage_molecules_cm2": 2.5e13,
        "thickness_nm": 5.0,
        "activation": "Streptavidin incubation",
        "target_compatibility": ["Biotinylated antibody", "Biotinylated DNA"],
    },
    "diazonium": {
        "name": "Diazonium Grafting",
        "chemistry": "C—C₆H₄—R (covalent C-C bond)",
        "linker": "4-Nitrobenzenediazonium tetrafluoroborate",
        "binding_energy_eV": 3.7,
        "coverage_molecules_cm2": 1.2e15,
        "thickness_nm": 2.0,
        "activation": "Electrochemical reduction",
        "target_compatibility": ["Aptamer", "Small molecule", "Peptide"],
    },
}

# ── Coating Physics ────────────────────────────────────────────────

def simulate_spin_coating(viscosity_Pa_s, spin_rpm, spin_time_s, density_kg_m3=1200):
    """Meyerhofer model for spin coating thickness, clamped for biosensor inks."""
    omega = spin_rpm * 2 * np.pi / 60
    # Use mPa·s scale for the model (real inks are diluted for spin coating)
    effective_visc = viscosity_Pa_s * 1e-3  # diluted for spin coating application
    kinematic_visc = effective_visc / density_kg_m3
    thickness_m = (3 * kinematic_visc / (2 * omega**2 * spin_time_s)) ** (1/3)
    thickness_nm = max(50, min(5000, thickness_m * 1e9))
    uniformity_pct = max(85, 99 - (viscosity_Pa_s / 10))
    return {
        "thickness_nm": round(float(thickness_nm), 1),
        "uniformity_pct": round(float(uniformity_pct), 1),
        "method": "Spin Coating (Meyerhofer model)",
        "params": {"rpm": spin_rpm, "time_s": spin_time_s},
    }

def simulate_dip_coating(viscosity_Pa_s, withdrawal_speed_mm_s, surface_tension_N_m=0.03, density_kg_m3=1200):
    """Landau-Levich equation for dip coating thickness."""
    U = withdrawal_speed_mm_s * 1e-3
    Ca = viscosity_Pa_s * U / surface_tension_N_m
    thickness_m = 0.94 * (viscosity_Pa_s * 1e-3 * U) ** (2/3) / (surface_tension_N_m ** (1/6) * (density_kg_m3 * 9.81) ** (1/2))
    thickness_nm = max(50, min(5000, abs(thickness_m) * 1e9))
    return {
        "thickness_nm": round(float(thickness_nm), 1),
        "capillary_number": float(f"{Ca:.4e}"),
        "method": "Dip Coating (Landau-Levich)",
        "params": {"speed_mm_s": withdrawal_speed_mm_s},
    }

def simulate_inkjet_printing(viscosity_Pa_s, surface_tension_N_m=0.03, density_kg_m3=1200, droplet_volume_pL=10):
    """Ohnesorge number analysis for inkjet printability."""
    nozzle_d = 21e-6  # 21 um nozzle
    Re = density_kg_m3 * 1.0 * nozzle_d / viscosity_Pa_s
    We = density_kg_m3 * 1.0**2 * nozzle_d / surface_tension_N_m
    Oh = np.sqrt(We) / Re if Re > 0 else 999
    Z = 1 / Oh if Oh > 0 else 0
    printable = 1 < Z < 14
    drop_d = (6 * droplet_volume_pL * 1e-18 / np.pi) ** (1/3) * 1e6
    thickness_nm = droplet_volume_pL * 0.1  # rough approximation
    return {
        "thickness_nm": round(float(thickness_nm), 1),
        "ohnesorge_number": round(float(Oh), 4),
        "Z_parameter": round(float(Z), 2),
        "printable": printable,
        "droplet_diameter_um": round(float(drop_d), 1),
        "method": "Inkjet (Ohnesorge analysis)",
    }

# ── Performance Prediction ─────────────────────────────────────────

def predict_biosensor_performance(pattern, ink, sam, coating, analyte="Glucose"):
    """Predict biosensor performance metrics from fabrication parameters."""
    area = pattern.get("area_cm2", 0.1)
    sigma = ink.get("conductivity_S_m", 1e3)
    thickness = coating.get("thickness_nm", 100)
    coverage = sam.get("coverage_molecules_cm2", 1e14)
    binding_E = sam.get("binding_energy_eV", 1.0)

    # Sensitivity (A/M/cm²) — higher conductivity and coverage = better
    sensitivity = sigma * coverage * 1e-18 * area
    sensitivity = max(1e-3, min(1e3, sensitivity))

    # Limit of Detection (M) — lower is better
    noise_floor = 1e-9 / (sigma * area * thickness * 1e-7 + 1e-12)
    lod = max(1e-15, noise_floor * 3)

    # Linear range
    linear_max = coverage * area * 1e-14 / 6.022e23 * 1e6

    # Response time (s) — thinner films = faster diffusion
    diffusion_time = (thickness * 1e-9) ** 2 / (1e-9)  # D ~ 1e-9 m²/s
    response_time = max(0.1, float(diffusion_time))

    # Stability (days) — stronger binding = longer life
    stability_days = int(binding_E * 30)

    # Selectivity score
    selectivity = min(99, 70 + binding_E * 10)

    return {
        "analyte": analyte,
        "sensitivity_uA_mM_cm2": round(float(sensitivity), 4),
        "lod_M": float(f"{lod:.2e}"),
        "linear_range_M": f"1e-6 to {linear_max:.2e}",
        "response_time_s": round(float(response_time), 2),
        "stability_days": stability_days,
        "selectivity_pct": round(float(selectivity), 1),
        "reproducibility_rsd_pct": round(max(1, 15 - sigma / 1e7), 1),
    }

# ── 3D Geometry Generator ──────────────────────────────────────────

def generate_electrode_3d(pattern_key="screen_printed", thickness_nm=100):
    """Generate 3D mesh vertices for electrode visualization."""
    pattern = ELECTRODE_PATTERNS.get(pattern_key, ELECTRODE_PATTERNS["screen_printed"])
    layers = []

    if pattern_key == "interdigitated":
        fingers = pattern.get("fingers", 10)
        w = pattern.get("width_um", 50) / 1000  # mm
        g = pattern.get("gap_um", 50) / 1000
        l = pattern.get("length_um", 2000) / 1000
        for i in range(fingers):
            x = i * (w + g)
            side = "anode" if i % 2 == 0 else "cathode"
            layers.append({
                "type": "finger", "side": side,
                "x": round(x, 3), "y": 0, "z": 0,
                "width": round(w, 3), "length": round(l, 3),
                "height": round(thickness_nm / 1e6, 6),
            })
    elif pattern_key == "disk":
        d = pattern.get("diameter_um", 3000) / 1000
        layers.append({"type": "disk", "cx": 0, "cy": 0, "radius": round(d/2, 3),
                        "height": round(thickness_nm / 1e6, 6)})
    elif pattern_key == "screen_printed":
        d = pattern.get("we_diameter_um", 4000) / 1000
        layers.append({"type": "working_electrode", "cx": 0, "cy": 0,
                        "radius": round(d/2, 3), "height": round(thickness_nm / 1e6, 6)})
        layers.append({"type": "reference_electrode", "cx": round(d*0.8, 3), "cy": 0,
                        "radius": round(d/6, 3), "height": round(thickness_nm / 1e6, 6),
                        "material": pattern.get("re_type", "Ag/AgCl")})
        layers.append({"type": "counter_electrode", "cx": 0, "cy": round(d*0.8, 3),
                        "radius": round(d/3, 3), "height": round(thickness_nm / 1e6, 6),
                        "material": pattern.get("ce_material", "Carbon")})
    elif pattern_key == "microwell_array":
        wells = min(pattern.get("wells", 96), 96)
        wd = pattern.get("well_diameter_um", 200) / 1000
        pitch = pattern.get("pitch_um", 500) / 1000
        cols = int(np.ceil(np.sqrt(wells)))
        for i in range(wells):
            r, c = divmod(i, cols)
            layers.append({"type": "well", "cx": round(c*pitch, 3),
                            "cy": round(r*pitch, 3), "radius": round(wd/2, 3),
                            "height": round(thickness_nm / 1e6, 6)})

    return {"pattern": pattern_key, "layers": layers, "info": pattern}

# ── Full Biosensor Simulation ──────────────────────────────────────

def simulate_biosensor(
    pattern_key: str = "screen_printed",
    ink_key: str = "carbon_paste",
    sam_key: str = "thiol_gold",
    coating_method: str = "spin",
    analyte: str = "Glucose",
    spin_rpm: int = 3000,
    spin_time_s: int = 30,
    dip_speed_mm_s: float = 1.0,
) -> Dict[str, Any]:
    """Run full biosensor fabrication simulation."""
    t0 = time.time()

    pattern = ELECTRODE_PATTERNS.get(pattern_key, ELECTRODE_PATTERNS["screen_printed"])
    ink = INK_FORMULATIONS.get(ink_key, INK_FORMULATIONS["carbon_paste"])
    sam = SAM_LIBRARY.get(sam_key, SAM_LIBRARY["thiol_gold"])

    # Coating simulation
    if coating_method == "spin":
        coating = simulate_spin_coating(ink["viscosity_Pa_s"], spin_rpm, spin_time_s)
    elif coating_method == "dip":
        coating = simulate_dip_coating(ink["viscosity_Pa_s"], dip_speed_mm_s)
    elif coating_method == "inkjet":
        coating = simulate_inkjet_printing(ink["viscosity_Pa_s"])
    else:
        coating = simulate_spin_coating(ink["viscosity_Pa_s"], 3000, 30)

    # 3D geometry
    geometry_3d = generate_electrode_3d(pattern_key, coating["thickness_nm"])

    # Performance prediction
    performance = predict_biosensor_performance(pattern, ink, sam, coating, analyte)

    # EIS/CV sync from biosensor parameters
    sigma = ink["conductivity_S_m"]
    area = pattern.get("area_cm2", 0.1)
    electrochem_sync = {
        "eis": {
            "Rs_ohm": round(1.0 / (sigma * area * 1e-4 + 1e-12), 3),
            "Rct_ohm": round(performance["response_time_s"] * 100, 2),
            "Cdl_F": float(f"{area * 20e-6:.4e}"),
            "sigma_w": round(50 / (sigma / 1e3 + 1), 2),
        },
        "cv": {
            "scan_rate_mV_s": 50,
            "E_range_V": [-0.6, 0.8],
            "peak_current_uA": round(float(performance["sensitivity_uA_mM_cm2"] * area * 5), 3),
        },
    }

    elapsed = time.time() - t0

    return {
        "pattern": {**pattern, "key": pattern_key},
        "ink": {**ink, "key": ink_key},
        "surface_chemistry": {**sam, "key": sam_key},
        "coating": coating,
        "geometry_3d": geometry_3d,
        "performance": performance,
        "electrochem_sync": electrochem_sync,
        "fabrication_steps": _generate_fab_steps(pattern_key, ink_key, sam_key, coating_method, analyte),
        "compute_time_ms": round(elapsed * 1000, 2),
    }

def _generate_fab_steps(pattern_key, ink_key, sam_key, coating_method, analyte):
    """Generate detailed fabrication protocol steps."""
    ink = INK_FORMULATIONS.get(ink_key, {})
    sam = SAM_LIBRARY.get(sam_key, {})
    steps = [
        {"step": 1, "phase": "Substrate Preparation",
         "action": "Clean substrate (glass/PET/Si) with acetone, IPA, and DI water sonication (5 min each). Dry under N₂ stream.",
         "duration_min": 20, "critical": True},
        {"step": 2, "phase": "Electrode Patterning",
         "action": f"Define {ELECTRODE_PATTERNS.get(pattern_key,{}).get('name','electrode')} pattern using photolithography or laser ablation. Pattern resolution: ±5 μm.",
         "duration_min": 45, "critical": True},
        {"step": 3, "phase": "Ink Preparation",
         "action": f"Prepare {ink.get('name','ink')}: " + ", ".join([f"{c['material']} ({c['wt_pct']}%)" for c in ink.get('components',[])]) + ". Homogenize by sonication for 30 min.",
         "duration_min": 40, "critical": False},
        {"step": 4, "phase": f"Coating ({coating_method.title()})",
         "action": f"Deposit ink via {coating_method} coating. Cure at {ink.get('cure_temp_C',120)}°C for {ink.get('cure_time_min',30)} min.",
         "duration_min": ink.get("cure_time_min", 30) + 5, "critical": True},
        {"step": 5, "phase": "Surface Functionalization",
         "action": f"Apply {sam.get('name','SAM')}: Immerse in 1 mM {sam.get('linker','linker')} solution for 16 hours. Rinse thoroughly.",
         "duration_min": 960, "critical": True},
        {"step": 6, "phase": "Bioreceptor Activation",
         "action": f"Activate surface via {sam.get('activation','coupling')}. Incubate with {analyte} antibody/enzyme (10 μg/mL) for 2 hours at 4°C.",
         "duration_min": 150, "critical": True},
        {"step": 7, "phase": "Blocking",
         "action": "Block non-specific sites with 1% BSA in PBS for 1 hour at room temperature.",
         "duration_min": 60, "critical": False},
        {"step": 8, "phase": "Quality Control",
         "action": "Verify electrode integrity via CV (-0.5 to 0.8V, 50 mV/s). Confirm SAM coverage via EIS (0.1-100kHz). Expected Rct increase: 200-500%.",
         "duration_min": 30, "critical": True},
    ]
    return steps

def optimize_biosensor(analyte: str, constraints: Dict[str, Any]) -> Dict[str, Any]:
    """
    Heuristic biosensor configuration selector.
    
    Evaluates all available electrode/ink/SAM combinations from the built-in
    library and returns the best-performing configuration based on the
    physics-based performance prediction model.
    
    NOTE: This is a deterministic grid search over the built-in library,
    not an AI-driven optimization. For true ML-based optimization,
    integrate with a Bayesian optimizer or neural surrogate model.
    """
    t0 = time.time()
    
    # Grid search: evaluate all combinations
    best_score = -1
    best_config = None
    best_sim = None
    iterations = 0
    
    for pattern_key in ELECTRODE_PATTERNS:
        for ink_key in INK_FORMULATIONS:
            for sam_key in SAM_LIBRARY:
                for coating_method in ["spin", "dip", "inkjet"]:
                    iterations += 1
                    try:
                        sim = simulate_biosensor(
                            pattern_key=pattern_key,
                            ink_key=ink_key,
                            sam_key=sam_key,
                            coating_method=coating_method,
                            analyte=analyte,
                        )
                        # Score: maximize sensitivity, minimize LoD
                        perf = sim["performance"]
                        score = perf["sensitivity_uA_mM_cm2"] * perf["selectivity_pct"]
                        if score > best_score:
                            best_score = score
                            best_config = {
                                "pattern": pattern_key,
                                "ink": ink_key,
                                "sam": sam_key,
                                "coating": coating_method,
                            }
                            best_sim = sim
                    except Exception as e:
                        logger.debug(f"Combination {pattern_key}/{ink_key}/{sam_key}/{coating_method} failed: {e}")
    
    if best_config is None:
        # Fallback to default
        best_config = {"pattern": "vidyutx_v1", "ink": "gold_nanoparticle", "sam": "thiol_gold", "coating": "inkjet"}
        best_sim = simulate_biosensor(pattern_key="vidyutx_v1", ink_key="gold_nanoparticle",
                                      sam_key="thiol_gold", coating_method="inkjet", analyte=analyte)
    
    elapsed = time.time() - t0
    
    return {
        "status": "success",
        "optimization_time_ms": round(elapsed * 1000, 2),
        "combinations_evaluated": iterations,
        "method": "exhaustive_grid_search",
        "optimal_configuration": best_config,
        "simulation_result": best_sim,
        "references": [
            {"note": "Meyerhofer spin coating model — J. Appl. Phys. 49, 3993 (1978)"},
            {"note": "Landau-Levich dip coating theory — Acta Physicochimica URSS 17, 42 (1942)"},
            {"note": "Ohnesorge number for inkjet printability — Annu. Rev. Fluid Mech. 30, 85 (1998)"},
        ]
    }
