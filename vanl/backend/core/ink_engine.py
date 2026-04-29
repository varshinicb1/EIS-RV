"""
Ink Formulation & Rheology Engine for Printed Electronics
============================================================
Physics-based simulation of conductive ink properties, printability,
and film formation for screen printing, inkjet, and aerosol jet.

Models implemented:
    - Herschel-Bulkley rheology: τ = τ_y + K·γ̇^n
    - Cross model (shear-thinning): η = η_∞ + (η_0 - η_∞)/(1+(λγ̇)^m)
    - Krieger-Dougherty for particle-loaded inks
    - Ohnesorge/Reynolds/Weber printability window
    - Percolation theory for conductive films
    - Coffee-ring & Marangoni drying models
    - Sheet resistance from film microstructure

Physical constants & references:
    [1] Derby, B. "Inkjet Printing of Functional and Structural Materials"
        Annu. Rev. Mater. Res. 40, 395-414 (2010)
    [2] Kamyshny & Magdassi, "Conductive Nanomaterials for Printed Electronics"
        Small 10, 3515-3535 (2014)
    [3] Secor et al. "Inkjet Printing of High Conductivity, Flexible Graphene
        Patterns" J. Phys. Chem. Lett. 4, 1347-1351 (2013)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class PrintMethod(str, Enum):
    SCREEN = "screen_printing"
    INKJET = "inkjet"
    AEROSOL_JET = "aerosol_jet"
    GRAVURE = "gravure"
    FLEXOGRAPHY = "flexography"
    SLOT_DIE = "slot_die"
    SPRAY = "spray_coating"
    BLADE = "blade_coating"


class SolventType(str, Enum):
    WATER = "water"
    NMP = "nmp"
    DMF = "dmf"
    ETHANOL = "ethanol"
    IPA = "isopropanol"
    TOLUENE = "toluene"
    ETHYLENE_GLYCOL = "ethylene_glycol"
    TERPINEOL = "terpineol"
    CYCLOHEXANONE = "cyclohexanone"


# ── Solvent Properties Database ────────────────────────────────────
SOLVENT_DB = {
    "water": {"viscosity_mPas": 1.0, "surface_tension_mN_m": 72.0,
              "density_kg_m3": 998, "boiling_C": 100, "vapor_pressure_kPa": 3.17,
              "dielectric": 80.1, "evap_rate_rel": 1.0},
    "nmp": {"viscosity_mPas": 1.65, "surface_tension_mN_m": 40.7,
            "density_kg_m3": 1028, "boiling_C": 202, "vapor_pressure_kPa": 0.04,
            "dielectric": 32.2, "evap_rate_rel": 0.01},
    "dmf": {"viscosity_mPas": 0.92, "surface_tension_mN_m": 37.1,
            "density_kg_m3": 944, "boiling_C": 153, "vapor_pressure_kPa": 0.36,
            "dielectric": 36.7, "evap_rate_rel": 0.08},
    "ethanol": {"viscosity_mPas": 1.2, "surface_tension_mN_m": 22.3,
                "density_kg_m3": 789, "boiling_C": 78, "vapor_pressure_kPa": 5.95,
                "dielectric": 24.5, "evap_rate_rel": 3.3},
    "isopropanol": {"viscosity_mPas": 2.04, "surface_tension_mN_m": 23.0,
                    "density_kg_m3": 786, "boiling_C": 82.6, "vapor_pressure_kPa": 4.4,
                    "dielectric": 17.9, "evap_rate_rel": 2.8},
    "toluene": {"viscosity_mPas": 0.59, "surface_tension_mN_m": 28.4,
                "density_kg_m3": 867, "boiling_C": 111, "vapor_pressure_kPa": 2.93,
                "dielectric": 2.38, "evap_rate_rel": 2.0},
    "ethylene_glycol": {"viscosity_mPas": 16.1, "surface_tension_mN_m": 47.7,
                        "density_kg_m3": 1113, "boiling_C": 197, "vapor_pressure_kPa": 0.01,
                        "dielectric": 37.0, "evap_rate_rel": 0.005},
    "terpineol": {"viscosity_mPas": 40.0, "surface_tension_mN_m": 33.0,
                  "density_kg_m3": 935, "boiling_C": 219, "vapor_pressure_kPa": 0.02,
                  "dielectric": 3.2, "evap_rate_rel": 0.003},
    "cyclohexanone": {"viscosity_mPas": 2.02, "surface_tension_mN_m": 34.4,
                      "density_kg_m3": 947, "boiling_C": 156, "vapor_pressure_kPa": 0.53,
                      "dielectric": 18.3, "evap_rate_rel": 0.15},
}

# ── Printability Windows (shear rate, viscosity range) ─────────────
PRINT_WINDOWS = {
    PrintMethod.SCREEN: {"shear_rate_range": (10, 1000), "viscosity_range_Pas": (1, 100),
                         "film_thickness_um": (1, 50), "resolution_um": 50},
    PrintMethod.INKJET: {"shear_rate_range": (1e4, 1e6), "viscosity_range_Pas": (0.002, 0.025),
                         "film_thickness_um": (0.05, 5), "resolution_um": 20},
    PrintMethod.AEROSOL_JET: {"shear_rate_range": (1e3, 1e5), "viscosity_range_Pas": (0.001, 1.0),
                              "film_thickness_um": (0.1, 10), "resolution_um": 10},
    PrintMethod.GRAVURE: {"shear_rate_range": (1e3, 1e5), "viscosity_range_Pas": (0.05, 0.5),
                          "film_thickness_um": (0.5, 10), "resolution_um": 30},
    PrintMethod.FLEXOGRAPHY: {"shear_rate_range": (1e2, 1e4), "viscosity_range_Pas": (0.05, 0.5),
                              "film_thickness_um": (0.5, 5), "resolution_um": 40},
    PrintMethod.SLOT_DIE: {"shear_rate_range": (10, 1e3), "viscosity_range_Pas": (0.01, 10),
                           "film_thickness_um": (0.1, 200), "resolution_um": 100},
    PrintMethod.SPRAY: {"shear_rate_range": (1e4, 1e6), "viscosity_range_Pas": (0.001, 0.05),
                        "film_thickness_um": (0.01, 2), "resolution_um": 500},
    PrintMethod.BLADE: {"shear_rate_range": (1, 100), "viscosity_range_Pas": (0.1, 50),
                        "film_thickness_um": (1, 500), "resolution_um": 1000},
}


@dataclass
class InkFormulation:
    """Complete ink formulation specification."""
    # Filler particles
    filler_material: str = "graphene"
    filler_loading_wt_pct: float = 5.0          # wt%
    particle_size_nm: float = 500.0              # mean particle/flake size
    aspect_ratio: float = 100.0                  # L/d for flakes/tubes
    particle_density_kg_m3: float = 2200.0       # density of filler

    # Solvent system
    primary_solvent: str = "water"
    co_solvent: Optional[str] = None
    co_solvent_fraction: float = 0.0             # vol fraction of co-solvent

    # Binder
    binder_type: str = "none"                    # CMC, PVP, EC, PVDF, none
    binder_wt_pct: float = 0.0

    # Surfactant/dispersant
    surfactant: Optional[str] = None             # SDS, Triton X-100, etc.
    surfactant_wt_pct: float = 0.0

    # Additives
    viscosity_modifier_wt_pct: float = 0.0
    defoamer_wt_pct: float = 0.0

    # Target process
    print_method: PrintMethod = PrintMethod.SCREEN

    def filler_vol_fraction(self) -> float:
        """Convert wt% to volume fraction using densities."""
        solv = SOLVENT_DB.get(self.primary_solvent, SOLVENT_DB["water"])
        rho_s = solv["density_kg_m3"]
        rho_f = self.particle_density_kg_m3
        w = self.filler_loading_wt_pct / 100
        phi = (w / rho_f) / (w / rho_f + (1 - w) / rho_s)
        return phi


@dataclass
class InkProperties:
    """Computed ink properties from formulation."""
    # Rheology
    viscosity_mPas: float = 0.0
    viscosity_at_shear: Dict[str, float] = field(default_factory=dict)
    yield_stress_Pa: float = 0.0
    shear_thinning_index: float = 1.0           # n in power-law
    thixotropic_index: float = 1.0

    # Surface properties
    surface_tension_mN_m: float = 0.0
    contact_angle_deg: float = 0.0

    # Printability metrics
    ohnesorge_number: float = 0.0
    reynolds_number: float = 0.0
    weber_number: float = 0.0
    Z_parameter: float = 0.0                    # 1/Oh, should be 1-10 for inkjet
    printability_score: float = 0.0             # 0-1

    # Film properties (after drying)
    wet_film_thickness_um: float = 0.0
    dry_film_thickness_um: float = 0.0
    sheet_resistance_ohm_sq: float = 0.0
    conductivity_S_m: float = 0.0
    transparency_pct: float = 0.0

    # Percolation
    percolation_threshold_vol_pct: float = 0.0
    above_percolation: bool = False

    # Stability
    sedimentation_rate_um_s: float = 0.0
    shelf_life_days: float = 0.0

    # Drying
    drying_time_s: float = 0.0
    coffee_ring_risk: str = "low"

    # Warnings/recommendations
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "viscosity_mPas": round(self.viscosity_mPas, 2),
            "viscosity_at_shear": self.viscosity_at_shear,
            "yield_stress_Pa": round(self.yield_stress_Pa, 4),
            "shear_thinning_index": round(self.shear_thinning_index, 3),
            "surface_tension_mN_m": round(self.surface_tension_mN_m, 2),
            "contact_angle_deg": round(self.contact_angle_deg, 1),
            "ohnesorge_number": round(self.ohnesorge_number, 4),
            "reynolds_number": round(self.reynolds_number, 2),
            "weber_number": round(self.weber_number, 2),
            "Z_parameter": round(self.Z_parameter, 2),
            "printability_score": round(self.printability_score, 3),
            "wet_film_thickness_um": round(self.wet_film_thickness_um, 2),
            "dry_film_thickness_um": round(self.dry_film_thickness_um, 3),
            "sheet_resistance_ohm_sq": round(self.sheet_resistance_ohm_sq, 2),
            "conductivity_S_m": round(self.conductivity_S_m, 2),
            "transparency_pct": round(self.transparency_pct, 1),
            "percolation_threshold_vol_pct": round(self.percolation_threshold_vol_pct, 2),
            "above_percolation": bool(self.above_percolation),
            "sedimentation_rate_um_s": round(self.sedimentation_rate_um_s, 4),
            "shelf_life_days": round(self.shelf_life_days, 1),
            "drying_time_s": round(self.drying_time_s, 1),
            "coffee_ring_risk": self.coffee_ring_risk,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }


# ═══════════════════════════════════════════════════════════════════
#   RHEOLOGY MODELS
# ═══════════════════════════════════════════════════════════════════

def krieger_dougherty_viscosity(
    eta_solvent: float, phi: float, phi_max: float = 0.64,
    intrinsic_eta: float = 2.5
) -> float:
    """
    Krieger-Dougherty model for particle-loaded suspensions.

    η/η_s = (1 - φ/φ_max)^(-[η]·φ_max)

    Args:
        eta_solvent: Solvent viscosity (Pa·s)
        phi: Volume fraction of particles
        phi_max: Maximum packing fraction (0.64 for random spheres)
        intrinsic_eta: Intrinsic viscosity [η] (2.5 for spheres, higher for rods)
    """
    if phi >= phi_max * 0.99:
        return eta_solvent * 1e6  # Practically solid
    ratio = 1.0 - phi / phi_max
    exponent = -intrinsic_eta * phi_max
    return eta_solvent * ratio ** exponent


def herschel_bulkley(shear_rate: np.ndarray, tau_y: float, K: float, n: float) -> np.ndarray:
    """
    Herschel-Bulkley model: τ = τ_y + K·γ̇^n

    Returns apparent viscosity η = τ/γ̇
    """
    gamma_dot = np.maximum(shear_rate, 1e-10)
    tau = tau_y + K * gamma_dot ** n
    return tau / gamma_dot


def cross_model(
    shear_rate: np.ndarray, eta_0: float, eta_inf: float,
    lambda_c: float, m: float
) -> np.ndarray:
    """
    Cross model for shear-thinning fluids.

    η = η_∞ + (η_0 - η_∞) / (1 + (λ·γ̇)^m)
    """
    gamma_dot = np.maximum(shear_rate, 1e-10)
    return eta_inf + (eta_0 - eta_inf) / (1 + (lambda_c * gamma_dot) ** m)


# ═══════════════════════════════════════════════════════════════════
#   PERCOLATION THEORY
# ═══════════════════════════════════════════════════════════════════

def percolation_threshold(aspect_ratio: float, geometry: str = "3D") -> float:
    """
    Estimate percolation threshold from aspect ratio.

    For high-aspect-ratio fillers (CNT, graphene flakes):
        φ_c ≈ 0.7 / AR  (excluded volume theory, Balberg 1984)
    For spheres: φ_c ≈ 0.16 (3D) or 0.45 (2D)

    Returns: volume fraction at percolation threshold
    """
    if aspect_ratio <= 1:
        return 0.16 if geometry == "3D" else 0.45
    # Excluded volume theory for rods/flakes
    phi_c = 0.7 / aspect_ratio
    return np.clip(phi_c, 0.001, 0.16)


def percolation_conductivity(
    phi: float, phi_c: float, sigma_filler: float,
    t_exponent: float = 2.0
) -> float:
    """
    Power-law conductivity above percolation threshold.

    σ = σ_0 · (φ - φ_c)^t   for φ > φ_c

    Args:
        phi: Volume fraction of conductive filler
        phi_c: Percolation threshold
        sigma_filler: Bulk conductivity of filler (S/m)
        t_exponent: Universal critical exponent (≈2.0 for 3D)

    Returns: Film conductivity (S/m)
    """
    if phi <= phi_c:
        return 1e-10  # Below percolation - insulating
    # Pre-factor typically 0.01-0.1 of bulk filler conductivity
    sigma_0 = sigma_filler * 0.05
    return sigma_0 * (phi - phi_c) ** t_exponent


# ═══════════════════════════════════════════════════════════════════
#   PRINTABILITY ANALYSIS
# ═══════════════════════════════════════════════════════════════════

def printability_numbers(
    density_kg_m3: float, viscosity_Pas: float,
    surface_tension_N_m: float, drop_diameter_m: float = 50e-6,
    velocity_m_s: float = 5.0
) -> Tuple[float, float, float, float]:
    """
    Calculate dimensionless numbers for inkjet printability.

    Oh = η / √(ρ·σ·L)           Ohnesorge number
    Re = ρ·v·L / η              Reynolds number
    We = ρ·v²·L / σ             Weber number
    Z  = 1/Oh                    Printability parameter

    For good jetting: 1 < Z < 10 (Derby criterion)
    Z < 1: viscosity too high (no drop formation)
    Z > 10: satellite drops form
    """
    L = drop_diameter_m
    Oh = viscosity_Pas / np.sqrt(density_kg_m3 * surface_tension_N_m * L)
    Re = density_kg_m3 * velocity_m_s * L / max(viscosity_Pas, 1e-10)
    We = density_kg_m3 * velocity_m_s**2 * L / max(surface_tension_N_m, 1e-10)
    Z = 1.0 / max(Oh, 1e-10)
    return Oh, Re, We, Z


def compute_printability_score(
    formulation: InkFormulation, properties: InkProperties
) -> float:
    """
    Composite printability score (0-1) based on method-specific requirements.
    """
    method = formulation.print_method
    window = PRINT_WINDOWS[method]
    score = 1.0
    warnings = []

    v_min, v_max = window["viscosity_range_Pas"]
    eta = properties.viscosity_mPas * 1e-3  # Convert to Pa·s

    if eta < v_min:
        score *= max(0, 1.0 - (v_min - eta) / v_min)
        warnings.append(f"Viscosity too low ({properties.viscosity_mPas:.1f} mPa·s) for {method.value}")
    elif eta > v_max:
        score *= max(0, 1.0 - (eta - v_max) / v_max)
        warnings.append(f"Viscosity too high ({properties.viscosity_mPas:.1f} mPa·s) for {method.value}")

    if method == PrintMethod.INKJET:
        if properties.Z_parameter < 1:
            score *= 0.3
            warnings.append("Z < 1: viscous regime, poor drop formation")
        elif properties.Z_parameter > 10:
            score *= 0.6
            warnings.append("Z > 10: satellite drops likely")
        elif 1 <= properties.Z_parameter <= 10:
            # Optimal range — bonus
            score *= min(1.0, properties.Z_parameter / 4.0)

    if properties.sedimentation_rate_um_s > 1.0:
        score *= 0.7
        warnings.append("High sedimentation risk — add stabilizer")

    properties.warnings.extend(warnings)
    return np.clip(score, 0, 1)


# ═══════════════════════════════════════════════════════════════════
#   DRYING & FILM FORMATION
# ═══════════════════════════════════════════════════════════════════

def film_drying_time(
    wet_thickness_um: float, evap_rate_rel: float,
    temperature_C: float = 25.0, area_mm2: float = 100.0
) -> float:
    """
    Estimate drying time for printed film.

    Simple model: t_dry ∝ thickness / evaporation_rate
    Temperature accelerates via Clausius-Clapeyron approximation.
    """
    base_rate = 0.1 * evap_rate_rel  # µm/s base evaporation rate
    # Temperature correction (doubles roughly every 15°C above 25°C)
    temp_factor = 2.0 ** ((temperature_C - 25.0) / 15.0)
    rate = base_rate * temp_factor
    return wet_thickness_um / max(rate, 1e-6)


def coffee_ring_assessment(
    contact_angle_deg: float, evap_rate_rel: float,
    particle_size_nm: float
) -> str:
    """
    Assess coffee-ring effect risk.

    Low contact angle + high evap rate → strong coffee ring
    Marangoni flow (co-solvent) or high viscosity can suppress it.
    """
    if contact_angle_deg < 20 and evap_rate_rel > 1.0:
        return "high"
    elif contact_angle_deg < 40 or evap_rate_rel > 2.0:
        return "medium"
    return "low"


def sedimentation_rate(
    particle_size_m: float, density_particle: float,
    density_fluid: float, viscosity_Pas: float
) -> float:
    """
    Stokes sedimentation velocity.

    v_s = (2/9) · (ρ_p - ρ_f) · g · r² / η
    """
    r = particle_size_m / 2.0
    g = 9.81
    delta_rho = abs(density_particle - density_fluid)
    v = (2.0 / 9.0) * delta_rho * g * r**2 / max(viscosity_Pas, 1e-10)
    return abs(v)


# ═══════════════════════════════════════════════════════════════════
#   MAIN SIMULATION
# ═══════════════════════════════════════════════════════════════════

def simulate_ink(formulation: InkFormulation) -> InkProperties:
    """
    Complete ink property simulation from formulation.

    Pipeline:
        1. Solvent properties lookup
        2. Rheology calculation (Krieger-Dougherty + shear-thinning)
        3. Surface tension estimation
        4. Printability analysis (Oh, Re, We, Z)
        5. Percolation & conductivity
        6. Film thickness & sheet resistance
        7. Stability assessment
        8. Drying analysis
    """
    props = InkProperties()
    warnings = []
    recs = []

    # 1. Solvent properties
    solv = SOLVENT_DB.get(formulation.primary_solvent, SOLVENT_DB["water"])

    # Mix solvent properties if co-solvent
    if formulation.co_solvent and formulation.co_solvent_fraction > 0:
        co_solv = SOLVENT_DB.get(formulation.co_solvent, SOLVENT_DB["water"])
        f2 = formulation.co_solvent_fraction
        f1 = 1 - f2
        eta_solv = solv["viscosity_mPas"] * f1 + co_solv["viscosity_mPas"] * f2
        sigma_solv = solv["surface_tension_mN_m"] * f1 + co_solv["surface_tension_mN_m"] * f2
        rho_solv = solv["density_kg_m3"] * f1 + co_solv["density_kg_m3"] * f2
        evap_rate = solv["evap_rate_rel"] * f1 + co_solv["evap_rate_rel"] * f2
    else:
        eta_solv = solv["viscosity_mPas"]
        sigma_solv = solv["surface_tension_mN_m"]
        rho_solv = solv["density_kg_m3"]
        evap_rate = solv["evap_rate_rel"]

    # 2. Rheology
    phi = formulation.filler_vol_fraction()
    # Adjust phi_max and intrinsic viscosity for non-spherical particles
    if formulation.aspect_ratio > 10:
        phi_max = 0.64 / (1 + 0.1 * np.log10(formulation.aspect_ratio))
        # Simha (1940) rod formula: [η] ≈ AR / (5·ln(2·AR) - 1.5) for AR >> 1
        AR = formulation.aspect_ratio
        intrinsic_eta = AR / (5 * np.log(2 * AR) - 1.5)
        intrinsic_eta = np.clip(intrinsic_eta, 2.5, 50)
    else:
        phi_max = 0.64
        intrinsic_eta = 2.5

    eta_base_mPas = krieger_dougherty_viscosity(
        eta_solv * 1e-3, phi, phi_max, intrinsic_eta
    ) * 1e3  # back to mPa·s

    # Binder contribution (thickener)
    binder_factor = 1.0 + 5.0 * (formulation.binder_wt_pct / 100) ** 0.8
    eta_base_mPas *= binder_factor

    # Viscosity modifier
    eta_base_mPas *= (1.0 + 3.0 * formulation.viscosity_modifier_wt_pct / 100)

    props.viscosity_mPas = eta_base_mPas

    # Shear-thinning behavior (common in particle-laden inks)
    n_shear = 1.0 - 0.3 * min(phi / 0.1, 1.0)  # More particles → more shear-thinning
    props.shear_thinning_index = max(n_shear, 0.3)

    # Yield stress (for screen printing pastes)
    if phi > 0.05:
        props.yield_stress_Pa = 0.5 * (phi / 0.1) ** 2.5
    else:
        props.yield_stress_Pa = 0.0

    # Viscosity at different shear rates
    shear_rates = [1, 10, 100, 1000, 10000, 100000]
    for sr in shear_rates:
        # Simple power-law correction
        eta_at_sr = eta_base_mPas * (sr / 100) ** (props.shear_thinning_index - 1)
        props.viscosity_at_shear[str(sr)] = round(max(eta_at_sr, 0.5), 2)

    # 3. Surface tension
    # Surfactant reduces surface tension
    if formulation.surfactant_wt_pct > 0:
        # Typical surfactant reduces by 20-40 mN/m
        reduction = min(30, 20 * (formulation.surfactant_wt_pct / 0.5) ** 0.5)
        sigma_solv -= reduction
    # Particles slightly increase surface tension
    sigma_solv += 2.0 * phi
    props.surface_tension_mN_m = max(sigma_solv, 15.0)

    # Contact angle estimation (on glass substrate)
    props.contact_angle_deg = 30 + 40 * (props.surface_tension_mN_m / 72.0)

    # 4. Printability numbers
    rho_ink = rho_solv * (1 - phi) + formulation.particle_density_kg_m3 * phi
    Oh, Re, We, Z = printability_numbers(
        rho_ink, props.viscosity_mPas * 1e-3,
        props.surface_tension_mN_m * 1e-3
    )
    props.ohnesorge_number = Oh
    props.reynolds_number = Re
    props.weber_number = We
    props.Z_parameter = Z

    # 5. Percolation & conductivity
    phi_c = percolation_threshold(formulation.aspect_ratio)
    props.percolation_threshold_vol_pct = phi_c * 100

    # Get filler conductivity from materials DB or use estimate
    sigma_filler = _estimate_filler_conductivity(formulation.filler_material)
    sigma_film = percolation_conductivity(phi, phi_c, sigma_filler)
    props.conductivity_S_m = sigma_film
    props.above_percolation = phi > phi_c

    # 6. Film properties
    window = PRINT_WINDOWS[formulation.print_method]
    t_min, t_max = window["film_thickness_um"]
    props.wet_film_thickness_um = (t_min + t_max) / 2  # Typical

    # Dry film thickness (solvent evaporates, only solids remain)
    solid_fraction = phi + formulation.binder_wt_pct / 100
    props.dry_film_thickness_um = props.wet_film_thickness_um * max(solid_fraction, 0.01)

    # Sheet resistance
    if sigma_film > 1e-5:
        t_m = props.dry_film_thickness_um * 1e-6  # to meters
        props.sheet_resistance_ohm_sq = 1.0 / (sigma_film * max(t_m, 1e-9))
    else:
        props.sheet_resistance_ohm_sq = 1e12

    # Transparency (Beer-Lambert approximation)
    alpha_abs = 2e4 * phi  # Absorption coefficient estimate
    props.transparency_pct = 100 * np.exp(-alpha_abs * props.dry_film_thickness_um * 1e-6)

    # 7. Stability
    v_sed = sedimentation_rate(
        formulation.particle_size_nm * 1e-9,
        formulation.particle_density_kg_m3,
        rho_solv,
        props.viscosity_mPas * 1e-3
    )
    props.sedimentation_rate_um_s = v_sed * 1e6  # m/s → µm/s

    # Shelf life estimate (time for 10% height sedimentation)
    if v_sed > 0:
        # Assuming ~50mm column height, 10% = 5mm
        props.shelf_life_days = (5e-3 / max(v_sed, 1e-15)) / 86400
        props.shelf_life_days = min(props.shelf_life_days, 365)
    else:
        props.shelf_life_days = 365

    # 8. Drying
    props.drying_time_s = film_drying_time(
        props.wet_film_thickness_um, evap_rate
    )
    props.coffee_ring_risk = coffee_ring_assessment(
        props.contact_angle_deg, evap_rate, formulation.particle_size_nm
    )

    # Printability score
    props.printability_score = compute_printability_score(formulation, props)

    # Recommendations
    if not props.above_percolation:
        recs.append(
            f"Filler loading ({formulation.filler_loading_wt_pct:.1f}wt%) is below "
            f"percolation threshold ({phi_c*100:.2f}vol%). Increase loading for conductivity."
        )
    if props.sheet_resistance_ohm_sq > 1000:
        recs.append("Sheet resistance >1kΩ/□. Consider post-treatment (sintering, compression).")
    if props.coffee_ring_risk == "high":
        recs.append("Add co-solvent (e.g., ethylene glycol) to induce Marangoni flow and suppress coffee ring.")
    if formulation.print_method == PrintMethod.INKJET and props.Z_parameter > 10:
        recs.append("Add viscosity modifier or increase particle loading to bring Z into 1-10 range.")

    props.warnings.extend(warnings)
    props.recommendations.extend(recs)

    return props


def rheology_curve(formulation: InkFormulation, n_points: int = 50) -> dict:
    """
    Generate full rheology flow curve (viscosity vs shear rate).

    Returns data suitable for plotting.
    """
    solv = SOLVENT_DB.get(formulation.primary_solvent, SOLVENT_DB["water"])
    phi = formulation.filler_vol_fraction()

    if formulation.aspect_ratio > 10:
        phi_max = 0.64 / (1 + 0.1 * np.log10(formulation.aspect_ratio))
        # Simha (1940) rod formula: [η] ≈ AR / (5·ln(2·AR) - 1.5) for AR >> 1
        AR = formulation.aspect_ratio
        intrinsic_eta = AR / (5 * np.log(2 * AR) - 1.5)
        intrinsic_eta = np.clip(intrinsic_eta, 2.5, 50)
    else:
        phi_max = 0.64
        intrinsic_eta = 2.5

    eta_0 = krieger_dougherty_viscosity(
        solv["viscosity_mPas"] * 1e-3, phi, phi_max, intrinsic_eta
    )  # Pa·s

    n_shear = 1.0 - 0.3 * min(phi / 0.1, 1.0)
    tau_y = 0.5 * (phi / 0.1) ** 2.5 if phi > 0.05 else 0.0

    shear_rates = np.logspace(-1, 6, n_points)
    K = eta_0 * 100 ** (1 - n_shear)  # Consistency index

    eta_values = herschel_bulkley(shear_rates, tau_y, K, n_shear)
    tau_values = eta_values * shear_rates

    # Mark print method window
    window = PRINT_WINDOWS[formulation.print_method]
    sr_min, sr_max = window["shear_rate_range"]

    return {
        "shear_rate": shear_rates.tolist(),
        "viscosity_Pas": eta_values.tolist(),
        "shear_stress_Pa": tau_values.tolist(),
        "print_window": {"shear_rate_min": sr_min, "shear_rate_max": sr_max},
        "model": "Herschel-Bulkley",
        "params": {"tau_y": tau_y, "K": K, "n": n_shear},
    }


def percolation_curve(
    filler_material: str, aspect_ratio: float = 100,
    n_points: int = 50
) -> dict:
    """
    Generate conductivity vs filler loading curve showing percolation transition.
    """
    sigma_filler = _estimate_filler_conductivity(filler_material)
    phi_c = percolation_threshold(aspect_ratio)

    phi_values = np.linspace(0, min(phi_c * 5, 0.3), n_points)
    sigma_values = np.array([
        percolation_conductivity(p, phi_c, sigma_filler)
        for p in phi_values
    ])

    # Convert to wt% (approximate, assuming density ratio ~2)
    wt_pct = phi_values * 100 * 2.0

    return {
        "vol_fraction_pct": (phi_values * 100).tolist(),
        "wt_pct_approx": wt_pct.tolist(),
        "conductivity_S_m": sigma_values.tolist(),
        "percolation_threshold_vol_pct": phi_c * 100,
        "filler_bulk_conductivity_S_m": sigma_filler,
    }


# ═══════════════════════════════════════════════════════════════════
#   HELPERS
# ═══════════════════════════════════════════════════════════════════

def _estimate_filler_conductivity(material_name: str) -> float:
    """Estimate filler conductivity from name."""
    conductivity_map = {
        "graphene": 1e6, "reduced_graphene_oxide": 1e4, "graphene_oxide": 0.1,
        "CNT": 1e5, "SWCNT": 1e6, "MWCNT": 1e5,
        "carbon_black": 5e4, "activated_carbon": 1e3, "graphite": 3.3e5,
        "silver_nanoparticles": 6.3e7, "gold_nanoparticles": 4.1e7,
        "copper_nanoparticles": 5.96e7, "PEDOT_PSS": 1000,
        "MnO2": 1e-5, "NiO": 1e-2, "MXene": 1e4,
    }
    return conductivity_map.get(material_name, 1e3)


def list_solvents() -> List[dict]:
    """List available solvents with properties."""
    return [
        {"name": k, **v} for k, v in SOLVENT_DB.items()
    ]


def list_print_methods() -> List[dict]:
    """List print methods with specifications."""
    return [
        {"method": k.value, **v}
        for k, v in PRINT_WINDOWS.items()
    ]
