"""
Biosensor Simulation Engine
===============================
Physics-based simulation of electrochemical biosensors for printed electronics.

Covers:
    1. Amperometric biosensors (enzyme electrodes)
    2. Impedimetric biosensors (label-free detection)
    3. Potentiometric biosensors (ion-selective)
    4. Voltammetric biosensors (DPV, SWV detection)

Physics models:
    - Michaelis-Menten enzyme kinetics: v = Vmax·[S]/(Km + [S])
    - Randles-Sevcik for diffusion-controlled voltammetry
    - Cottrell equation for chronoamperometry
    - Langmuir adsorption isotherm for surface binding
    - EIS model for impedimetric detection (Rct shift)
    - LOD/LOQ calculation (IUPAC 3σ/10σ method)

References:
    [1] Bard & Faulkner, "Electrochemical Methods" 3rd Ed.
    [2] Turner et al., "Biosensors: Fundamentals and Applications" (2015)
    [3] Ronkainen et al., "Electrochemical biosensors" Chem. Soc. Rev. 39,
        1747-1763 (2010)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class BiosensorType(str, Enum):
    AMPEROMETRIC = "amperometric"
    IMPEDIMETRIC = "impedimetric"
    POTENTIOMETRIC = "potentiometric"
    VOLTAMMETRIC = "voltammetric"


class AnalyteClass(str, Enum):
    GLUCOSE = "glucose"
    LACTATE = "lactate"
    CHOLESTEROL = "cholesterol"
    UREA = "urea"
    CREATININE = "creatinine"
    CORTISOL = "cortisol"
    DOPAMINE = "dopamine"
    ASCORBIC_ACID = "ascorbic_acid"
    URIC_ACID = "uric_acid"
    DNA = "dna"
    PROTEIN = "protein"
    BACTERIA = "bacteria"
    VIRUS = "virus"
    HEAVY_METAL = "heavy_metal"
    PESTICIDE = "pesticide"
    PH = "pH"
    CUSTOM = "custom"


# ── Analyte Properties Database ────────────────────────────────────
ANALYTE_DB = {
    "glucose": {
        "MW": 180.16, "D_cm2_s": 6.7e-6, "physiological_mM": (3.9, 6.1),
        "pathological_mM": (0.5, 30), "enzyme": "glucose_oxidase",
        "Km_mM": 25, "Vmax_rel": 1.0, "n_electrons": 2,
        "E_detection_V": 0.6, "mediator": "ferrocene",
    },
    "lactate": {
        "MW": 90.08, "D_cm2_s": 1.0e-5, "physiological_mM": (0.5, 2.2),
        "pathological_mM": (0.1, 25), "enzyme": "lactate_oxidase",
        "Km_mM": 3.0, "Vmax_rel": 0.8, "n_electrons": 2,
        "E_detection_V": 0.5, "mediator": "prussian_blue",
    },
    "cholesterol": {
        "MW": 386.65, "D_cm2_s": 3e-6, "physiological_mM": (3.1, 5.2),
        "pathological_mM": (0.5, 15), "enzyme": "cholesterol_oxidase",
        "Km_mM": 0.5, "Vmax_rel": 0.6, "n_electrons": 2,
        "E_detection_V": 0.5,
    },
    "dopamine": {
        "MW": 153.18, "D_cm2_s": 6.0e-6, "physiological_mM": (0.01e-3, 0.1e-3),
        "pathological_mM": (0, 1e-3), "enzyme": None,
        "n_electrons": 2, "E_detection_V": 0.2, "E_formal_V": 0.18,
    },
    "uric_acid": {
        "MW": 168.11, "D_cm2_s": 5.0e-6, "physiological_mM": (0.2, 0.42),
        "pathological_mM": (0.05, 1.0), "enzyme": "uricase",
        "Km_mM": 0.1, "Vmax_rel": 0.9, "n_electrons": 2,
        "E_detection_V": 0.35,
    },
    "cortisol": {
        "MW": 362.46, "D_cm2_s": 4e-6, "physiological_mM": (0.14e-3, 0.69e-3),
        "pathological_mM": (0, 2e-3), "enzyme": None,
        "n_electrons": 1, "E_detection_V": 0.3,
        "binding_type": "immunoassay", "Ka_M": 1e9,
    },
    "DNA": {
        "MW": 330e3, "D_cm2_s": 1e-7, "n_electrons": 1,
        "binding_type": "hybridization", "Ka_M": 1e8,
    },
    "pH": {
        "MW": 1.008, "D_cm2_s": 9.3e-5, "n_electrons": 1,
        "sensitivity_mV_pH": -59.16,  # Nernstian
    },
}


@dataclass
class BiosensorConfig:
    """Complete biosensor specification for printed SPE."""
    # Sensor type
    sensor_type: BiosensorType = BiosensorType.AMPEROMETRIC
    analyte: str = "glucose"

    # Electrode geometry (printed SPE)
    working_electrode_area_mm2: float = 7.07     # 3mm diameter
    working_electrode_material: str = "carbon_black"
    reference_electrode: str = "Ag/AgCl"
    counter_electrode: str = "carbon"

    # Surface modification
    modifier: str = "none"                        # enzyme, antibody, aptamer, MIP, nanocomposite
    enzyme_loading_U_cm2: float = 10.0           # enzyme units per cm²
    modifier_thickness_nm: float = 100.0

    # Electrode properties
    conductivity_S_m: float = 5e4
    roughness_factor: float = 1.5
    Cdl_uF_cm2: float = 20.0                    # Double layer capacitance

    # Solution
    pH: float = 7.4
    temperature_C: float = 25.0
    ionic_strength_M: float = 0.15               # physiological
    buffer: str = "PBS"

    # Detection parameters
    applied_potential_V: float = 0.6              # for amperometric
    scan_rate_mV_s: float = 50.0                 # for voltammetric
    frequency_Hz: float = 1000.0                 # for impedimetric
    pulse_amplitude_mV: float = 50.0             # for DPV/SWV


@dataclass
class BiosensorPerformance:
    """Complete biosensor characterization results."""
    # Sensitivity
    sensitivity_uA_mM: float = 0.0
    sensitivity_uA_mM_cm2: float = 0.0          # area-normalized
    linear_range_mM: List[float] = field(default_factory=lambda: [0, 0])

    # Detection limits
    LOD_uM: float = 0.0                          # Limit of Detection (3σ)
    LOQ_uM: float = 0.0                          # Limit of Quantification (10σ)

    # Calibration curve
    concentrations_mM: List[float] = field(default_factory=list)
    responses_uA: List[float] = field(default_factory=list)
    calibration_slope: float = 0.0
    calibration_intercept: float = 0.0
    R_squared: float = 0.0

    # Kinetics
    Km_mM: float = 0.0
    Vmax_uA: float = 0.0
    response_time_s: float = 0.0

    # Selectivity
    selectivity_ratio: Dict[str, float] = field(default_factory=dict)

    # Stability
    operational_stability_hours: float = 0.0
    shelf_life_days: float = 0.0

    # EIS characterization
    Rct_ohm: float = 0.0
    Rct_with_analyte_ohm: float = 0.0
    Rct_change_pct: float = 0.0

    # Voltammetric peaks
    peak_potential_V: float = 0.0
    peak_current_uA: float = 0.0

    # Curves
    dpv_E: List[float] = field(default_factory=list)
    dpv_i: List[float] = field(default_factory=list)
    chronoamp_t: List[float] = field(default_factory=list)
    chronoamp_i: List[float] = field(default_factory=list)
    eis_data: dict = field(default_factory=dict)

    # Physical AI relevance
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "sensitivity_uA_mM": round(self.sensitivity_uA_mM, 4),
            "sensitivity_uA_mM_cm2": round(self.sensitivity_uA_mM_cm2, 3),
            "linear_range_mM": self.linear_range_mM,
            "LOD_uM": round(self.LOD_uM, 3),
            "LOQ_uM": round(self.LOQ_uM, 3),
            "calibration": {
                "concentrations_mM": self.concentrations_mM,
                "responses_uA": self.responses_uA,
                "slope": round(self.calibration_slope, 4),
                "intercept": round(self.calibration_intercept, 4),
                "R_squared": round(self.R_squared, 4),
            },
            "Km_mM": round(self.Km_mM, 3),
            "Vmax_uA": round(self.Vmax_uA, 3),
            "response_time_s": round(self.response_time_s, 2),
            "Rct_ohm": round(self.Rct_ohm, 2),
            "Rct_with_analyte_ohm": round(self.Rct_with_analyte_ohm, 2),
            "Rct_change_pct": round(self.Rct_change_pct, 1),
            "peak_potential_V": round(self.peak_potential_V, 3),
            "peak_current_uA": round(self.peak_current_uA, 3),
            "operational_stability_hours": round(self.operational_stability_hours, 1),
            "shelf_life_days": round(self.shelf_life_days, 0),
            "dpv": {"E_V": self.dpv_E, "i_uA": self.dpv_i},
            "chronoamperometry": {"t_s": self.chronoamp_t, "i_uA": self.chronoamp_i},
            "eis": self.eis_data,
            "selectivity": self.selectivity_ratio,
            "recommendations": self.recommendations,
        }


# ═══════════════════════════════════════════════════════════════════
#   ENZYME KINETICS
# ═══════════════════════════════════════════════════════════════════

def michaelis_menten(S: np.ndarray, Vmax: float, Km: float) -> np.ndarray:
    """
    Michaelis-Menten enzyme kinetics.

    v = Vmax · [S] / (Km + [S])

    Args:
        S: Substrate concentration (mM)
        Vmax: Maximum reaction velocity
        Km: Michaelis constant (mM) — [S] at which v = Vmax/2
    """
    return Vmax * S / (Km + S)


def randles_sevcik_peak_current(
    n: int, A_cm2: float, D_cm2_s: float,
    C_M: float, v_V_s: float, T_K: float = 298.15
) -> float:
    """
    Randles-Sevcik equation for peak current.

    i_p = 2.69 × 10⁵ · n^(3/2) · A · D^(1/2) · C · v^(1/2)

    (at 25°C for reversible system)
    """
    return 2.69e5 * n**1.5 * A_cm2 * np.sqrt(D_cm2_s) * C_M * np.sqrt(v_V_s)


def cottrell_current(
    n: int, F: float, A_cm2: float, D_cm2_s: float,
    C_M: float, t_s: np.ndarray
) -> np.ndarray:
    """
    Cottrell equation for chronoamperometric response.

    i(t) = nFAD^(1/2)C / (π^(1/2) · t^(1/2))

    Valid for semi-infinite linear diffusion.
    """
    F_const = 96485  # C/mol
    return n * F_const * A_cm2 * np.sqrt(D_cm2_s) * C_M / (
        np.sqrt(np.pi * np.maximum(t_s, 1e-6))
    )


# ═══════════════════════════════════════════════════════════════════
#   MAIN BIOSENSOR SIMULATION
# ═══════════════════════════════════════════════════════════════════

def simulate_biosensor(config: BiosensorConfig) -> BiosensorPerformance:
    """
    Complete biosensor simulation pipeline.

    1. Calculate electrode active area
    2. Generate calibration curve (Michaelis-Menten or linear)
    3. Calculate LOD/LOQ
    4. Simulate chronoamperometry
    5. Simulate DPV/SWV
    6. Simulate EIS response
    7. Predict stability
    8. Generate recommendations
    """
    perf = BiosensorPerformance()
    analyte_props = ANALYTE_DB.get(config.analyte, ANALYTE_DB["glucose"])

    A_cm2 = config.working_electrode_area_mm2 * 1e-2  # mm² → cm²
    A_eff = A_cm2 * config.roughness_factor

    # ── 1. Enzyme kinetics / direct electrochemistry ──
    if analyte_props.get("enzyme") and config.modifier != "none":
        # Enzymatic biosensor
        Km = analyte_props["Km_mM"]
        # Vmax depends on enzyme loading and electrode area
        Vmax_uA = (config.enzyme_loading_U_cm2 * A_eff *
                   analyte_props.get("Vmax_rel", 1.0) * 10.0)  # ~10 µA at saturation
        perf.Km_mM = Km
        perf.Vmax_uA = Vmax_uA
    else:
        Km = 100  # Large Km → linear response
        Vmax_uA = 100  # Direct electrochemistry

    # ── 2. Calibration curve ──
    _generate_calibration(perf, analyte_props, config, A_eff, Km, Vmax_uA)

    # ── 3. Response time ──
    D = analyte_props.get("D_cm2_s", 5e-6)
    L = config.modifier_thickness_nm * 1e-7  # cm
    perf.response_time_s = L**2 / (2 * D) + 0.5  # Diffusion + electronics

    # ── 4. Chronoamperometry ──
    _simulate_chronoamp(perf, analyte_props, config, A_eff)

    # ── 5. DPV/SWV ──
    _simulate_dpv(perf, analyte_props, config, A_eff)

    # ── 6. EIS ──
    _simulate_biosensor_eis(perf, analyte_props, config, A_eff)

    # ── 7. Stability ──
    _predict_stability(perf, config)

    # ── 8. Selectivity ──
    _estimate_selectivity(perf, config)

    # ── 9. Recommendations ──
    _generate_recommendations(perf, config, analyte_props)

    return perf


def _generate_calibration(
    perf: BiosensorPerformance, analyte_props: dict,
    config: BiosensorConfig, A_eff: float, Km: float, Vmax_uA: float
):
    """Generate calibration curve and extract analytical figures of merit."""
    # Concentration range
    phys_range = analyte_props.get("physiological_mM", (0.01, 10))
    path_range = analyte_props.get("pathological_mM", (0.001, 50))
    C_min = path_range[0] * 0.1
    C_max = path_range[1] * 1.5
    if C_min <= 0:
        C_min = 1e-4

    concentrations = np.logspace(np.log10(max(C_min, 1e-6)), np.log10(C_max), 30)

    # Response: Michaelis-Menten
    responses = michaelis_menten(concentrations, Vmax_uA, Km)

    # Add noise (realistic baseline noise)
    # Baseline noise from electrode double-layer (Johnson-Nyquist + 1/f)
    # Typical for carbon SPE: ~10-50 nA RMS; use 1% of Vmax or 50 nA minimum
    noise_std = max(0.05, Vmax_uA * 0.01)  # µA
    responses_noisy = responses + np.random.normal(0, noise_std, len(responses))

    perf.concentrations_mM = concentrations.tolist()
    perf.responses_uA = responses_noisy.tolist()

    # Linear range: where response is 5-80% of Vmax (Michaelis-Menten linear region)
    mask_linear = (responses > Vmax_uA * 0.05) & (responses < Vmax_uA * 0.5)
    if np.sum(mask_linear) > 3:
        C_lin = concentrations[mask_linear]
        R_lin = responses[mask_linear]
        # Linear fit
        coeffs = np.polyfit(C_lin, R_lin, 1)
        perf.calibration_slope = coeffs[0]
        perf.calibration_intercept = coeffs[1]
        perf.sensitivity_uA_mM = coeffs[0]
        perf.sensitivity_uA_mM_cm2 = coeffs[0] / A_eff

        # R²
        R_pred = np.polyval(coeffs, C_lin)
        ss_res = np.sum((R_lin - R_pred)**2)
        ss_tot = np.sum((R_lin - np.mean(R_lin))**2)
        perf.R_squared = 1 - ss_res / max(ss_tot, 1e-20)

        perf.linear_range_mM = [round(C_lin[0], 4), round(C_lin[-1], 4)]

    # LOD = 3σ/slope, LOQ = 10σ/slope
    if perf.sensitivity_uA_mM > 0:
        sigma_baseline = noise_std
        perf.LOD_uM = 3 * sigma_baseline / perf.sensitivity_uA_mM * 1000  # mM → µM
        perf.LOQ_uM = 10 * sigma_baseline / perf.sensitivity_uA_mM * 1000
    else:
        perf.LOD_uM = float('inf')
        perf.LOQ_uM = float('inf')


def _simulate_chronoamp(
    perf: BiosensorPerformance, analyte_props: dict,
    config: BiosensorConfig, A_eff: float
):
    """Simulate chronoamperometric response."""
    D = analyte_props.get("D_cm2_s", 5e-6)
    n = analyte_props.get("n_electrons", 2)
    C_test = 1e-3  # 1 mM test concentration (mol/L = M)

    t = np.linspace(0.01, 60, 200)  # 60 seconds
    # C_test = 1e-3 mol/L; Cottrell needs mol/cm³: 1 mol/L = 1e-3 mol/cm³
    # so C_test / 1000 = 1e-6 mol/cm³ — correct unit conversion
    i_cottrell = cottrell_current(n, 96485, A_eff, D, C_test / 1000, t)

    # Add steady-state enzyme response
    if analyte_props.get("enzyme"):
        i_steady = perf.Vmax_uA * 1e-6 * C_test / (
            analyte_props.get("Km_mM", 25) + C_test * 1000
        )
        # Transition from Cottrell to steady-state
        tau = perf.response_time_s
        i_total = i_cottrell * np.exp(-t / tau) + i_steady * (1 - np.exp(-t / tau))
    else:
        i_total = i_cottrell

    perf.chronoamp_t = t.tolist()
    perf.chronoamp_i = (i_total * 1e6).tolist()  # A → µA


def _simulate_dpv(
    perf: BiosensorPerformance, analyte_props: dict,
    config: BiosensorConfig, A_eff: float
):
    """Simulate Differential Pulse Voltammetry (DPV) response."""
    E_detect = analyte_props.get("E_detection_V", 0.3)
    E_formal = analyte_props.get("E_formal_V", E_detect)
    n = analyte_props.get("n_electrons", 2)
    D = analyte_props.get("D_cm2_s", 5e-6)

    E = np.linspace(E_formal - 0.3, E_formal + 0.3, 200)
    dE = config.pulse_amplitude_mV * 1e-3  # V

    # DPV: Δi = nFAD^(1/2)C / √(πt_p) × [...]
    # Simplified Gaussian-like peak
    sigma_peak = 0.05 / n  # Peak half-width depends on n
    C_test = 1e-3  # 1 mM

    i_peak_max = randles_sevcik_peak_current(
        n, A_eff, D, C_test / 1000, config.scan_rate_mV_s * 1e-3
    )

    # DPV gives sharper peaks than CV
    i_dpv = i_peak_max * 2 * np.exp(-0.5 * ((E - E_formal) / sigma_peak)**2)

    # Add baseline slope
    i_dpv += 0.05 * i_peak_max * (E - E[0])

    perf.dpv_E = E.tolist()
    perf.dpv_i = (i_dpv * 1e6).tolist()  # A → µA

    # Peak metrics
    peak_idx = np.argmax(i_dpv)
    perf.peak_potential_V = E[peak_idx]
    perf.peak_current_uA = i_dpv[peak_idx] * 1e6


def _simulate_biosensor_eis(
    perf: BiosensorPerformance, analyte_props: dict,
    config: BiosensorConfig, A_eff: float
):
    """Simulate biosensor EIS response (before and after analyte binding)."""
    from .eis_engine import randles_impedance

    frequencies = np.logspace(-1, 5, 60)

    # Base electrode parameters
    Rs = 50.0  # Solution resistance
    Cdl = config.Cdl_uF_cm2 * 1e-6 * A_eff  # F
    sigma_w = 30.0

    # Rct depends on electrode material and modification
    Rct_base = 500.0  # Bare electrode
    if config.modifier == "enzyme":
        Rct_base *= 1.5  # Enzyme layer adds resistance
    elif config.modifier == "antibody":
        Rct_base *= 2.0

    # Base EIS
    Z_base = randles_impedance(frequencies, Rs, Rct_base, Cdl, sigma_w, n_cpe=0.9)

    # After analyte binding — Rct changes
    # For impedimetric: binding increases Rct (blocking electron transfer)
    # For enzymatic: catalysis decreases Rct
    if config.sensor_type == BiosensorType.IMPEDIMETRIC:
        Rct_analyte = Rct_base * 1.4  # 40% increase
    else:
        Rct_analyte = Rct_base * 0.7  # 30% decrease (catalysis)

    Z_analyte = randles_impedance(frequencies, Rs, Rct_analyte, Cdl, sigma_w, n_cpe=0.9)

    perf.Rct_ohm = Rct_base
    perf.Rct_with_analyte_ohm = Rct_analyte
    perf.Rct_change_pct = (Rct_analyte - Rct_base) / Rct_base * 100

    perf.eis_data = {
        "frequencies": frequencies.tolist(),
        "baseline": {
            "Z_real": np.real(Z_base).tolist(),
            "Z_imag_neg": (-np.imag(Z_base)).tolist(),
        },
        "with_analyte": {
            "Z_real": np.real(Z_analyte).tolist(),
            "Z_imag_neg": (-np.imag(Z_analyte)).tolist(),
        },
    }


def _predict_stability(perf: BiosensorPerformance, config: BiosensorConfig):
    """Predict operational and storage stability."""
    # Base stability depends on recognition element
    if config.modifier == "enzyme":
        perf.operational_stability_hours = 4.0  # Typical for GOx
        perf.shelf_life_days = 30
    elif config.modifier == "antibody":
        perf.operational_stability_hours = 2.0
        perf.shelf_life_days = 14
    elif config.modifier == "aptamer":
        perf.operational_stability_hours = 8.0
        perf.shelf_life_days = 90
    elif config.modifier == "MIP":
        perf.operational_stability_hours = 24.0
        perf.shelf_life_days = 180
    else:
        perf.operational_stability_hours = 100.0  # Direct electrochemistry
        perf.shelf_life_days = 365

    # Temperature correction
    T = config.temperature_C
    if T > 37:
        degrade_factor = 2 ** ((T - 37) / 10)
        perf.operational_stability_hours /= degrade_factor
        perf.shelf_life_days /= degrade_factor


def _estimate_selectivity(perf: BiosensorPerformance, config: BiosensorConfig):
    """Estimate selectivity against common interferents."""
    interferents = {
        "ascorbic_acid": 0.05,
        "uric_acid": 0.03,
        "acetaminophen": 0.02,
        "dopamine": 0.01,
    }

    if config.modifier == "enzyme":
        # Enzyme provides good selectivity
        perf.selectivity_ratio = {k: v * 0.1 for k, v in interferents.items()}
    elif config.modifier == "antibody":
        perf.selectivity_ratio = {k: v * 0.01 for k, v in interferents.items()}
    else:
        # Poor selectivity without recognition element
        perf.selectivity_ratio = interferents


def _generate_recommendations(
    perf: BiosensorPerformance, config: BiosensorConfig,
    analyte_props: dict
):
    """Generate actionable recommendations."""
    recs = []

    if perf.LOD_uM > 100:
        recs.append("LOD is high. Consider: (1) nanostructured electrode surface, "
                     "(2) signal amplification with nanoparticles, (3) preconcentration step.")

    if perf.sensitivity_uA_mM_cm2 < 1:
        recs.append("Low sensitivity. Try: (1) increase enzyme loading, "
                     "(2) use mediator-modified electrode, (3) add CNT/graphene to ink.")

    phys = analyte_props.get("physiological_mM", (0.01, 10))
    if perf.linear_range_mM[1] < phys[1]:
        recs.append(f"Linear range ({perf.linear_range_mM[1]:.2f} mM) doesn't cover "
                    f"physiological max ({phys[1]} mM). Reduce enzyme loading or use membrane.")

    if perf.response_time_s > 30:
        recs.append("Response time >30s. Consider thinner modifier layer or higher porosity electrode.")

    if config.modifier == "none":
        recs.append("No recognition element. For selective detection, immobilize "
                    "enzyme/antibody/aptamer on electrode surface.")

    perf.recommendations = recs


# ═══════════════════════════════════════════════════════════════════
#   QUICK SIMULATION HELPERS
# ═══════════════════════════════════════════════════════════════════

def quick_biosensor(
    analyte: str = "glucose",
    electrode_material: str = "carbon_black",
    modifier: str = "enzyme",
    area_mm2: float = 7.07,
) -> dict:
    """Quick biosensor simulation with minimal parameters."""
    config = BiosensorConfig(
        analyte=analyte,
        working_electrode_material=electrode_material,
        modifier=modifier,
        working_electrode_area_mm2=area_mm2,
    )
    return simulate_biosensor(config).to_dict()


def list_analytes() -> List[dict]:
    """List available analytes with properties."""
    result = []
    for name, props in ANALYTE_DB.items():
        result.append({
            "name": name,
            "MW": props.get("MW"),
            "physiological_range_mM": props.get("physiological_mM"),
            "pathological_range_mM": props.get("pathological_mM"),
            "enzyme": props.get("enzyme"),
            "n_electrons": props.get("n_electrons", 2),
            "detection_potential_V": props.get("E_detection_V"),
        })
    return result
