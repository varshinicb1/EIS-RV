"""
Printed Battery Simulation Engine
====================================
Physics-based simulation for thin-film and printed batteries:
zinc-carbon, zinc-MnO2, lithium thin-film, and solid-state.

Models:
    - Single Particle Model (SPM) for intercalation kinetics
    - Butler-Volmer for charge transfer
    - Solid-state diffusion (Fick's 2nd law, spherical)
    - Peukert's law for rate capability
    - Calendar & cycle aging (SEI growth model)
    - Open Circuit Voltage from thermodynamic models
    - Printed battery corrections (contact resistance, film non-uniformity)

References:
    [1] Newman & Thomas-Alyea, "Electrochemical Systems" 3rd Ed.
    [2] Doyle, Fuller, Newman, J. Electrochem. Soc. 140, 1526 (1993)
    [3] Zeng et al., "Printed Batteries" Chem. Rev. 122, 16994 (2022)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Open Circuit Voltage Models ────────────────────────────────────
# OCV(SOC) polynomials fitted from literature data

OCV_MODELS = {
    "LiFePO4": {
        # Polynomial from Plett (2004) / Chen (2006) — validated flat plateau ~3.4V
        "coeffs": [3.4323, -0.4023, 0.5836, -0.5561, 0.2127, -0.0289],
        "V_range": (2.5, 3.65), "capacity_mAh_g": 170,
        "description": "LiFePO₄ cathode — flat voltage plateau ~3.4V",
    },
    "LiCoO2": {
        "coeffs": [4.1843, -0.5436, -1.0372, 2.7456, -2.5281, 0.8324],
        "V_range": (3.0, 4.2), "capacity_mAh_g": 140,
        "description": "LiCoO₂ cathode — sloping profile 3.0-4.2V",
    },
    "graphite": {
        "coeffs": [0.1493, 0.8493, -3.3592, 6.0817, -4.9013, 1.4835],
        "V_range": (0.01, 0.5), "capacity_mAh_g": 372,
        "description": "Graphite anode — staged intercalation",
    },
    "MnO2_alkaline": {
        "coeffs": [1.55, -0.15, -0.3, 0.1, 0.0, 0.0],
        "V_range": (0.9, 1.55), "capacity_mAh_g": 308,
        "description": "MnO₂ alkaline cathode — primary cell",
    },
    "zinc": {
        "coeffs": [-1.35, 0.05, 0.02, 0.0, 0.0, 0.0],
        "V_range": (-1.4, -1.2), "capacity_mAh_g": 820,
        "description": "Zinc anode — alkaline/neutral systems",
    },
    "zinc_MnO2": {
        "coeffs": [1.60, -0.25, -0.15, 0.05, 0.0, 0.0],
        "V_range": (0.9, 1.6), "capacity_mAh_g": 225,
        "description": "Zn-MnO₂ full cell — printed primary battery",
    },
    "silver_zinc": {
        "coeffs": [1.60, -0.1, -0.05, 0.02, 0.0, 0.0],
        "V_range": (1.2, 1.6), "capacity_mAh_g": 150,
        "description": "Ag₂O-Zn printed battery",
    },
}


def ocv_from_soc(soc: np.ndarray, chemistry: str) -> np.ndarray:
    """
    Calculate OCV from State of Charge using polynomial model.

    OCV(SOC) = Σ aᵢ · SOCⁱ
    """
    model = OCV_MODELS.get(chemistry, OCV_MODELS["zinc_MnO2"])
    coeffs = model["coeffs"]
    soc = np.clip(soc, 0.01, 0.99)
    V = np.zeros_like(soc, dtype=float)
    for i, c in enumerate(coeffs):
        V += c * soc ** i
    V_min, V_max = model["V_range"]
    return np.clip(V, V_min, V_max)


@dataclass
class BatteryConfig:
    """Printed battery device configuration."""
    # Chemistry
    chemistry: str = "zinc_MnO2"
    cathode_material: str = "MnO2"
    anode_material: str = "zinc"

    # Electrode geometry (printed)
    electrode_area_cm2: float = 1.0
    cathode_thickness_um: float = 100.0
    anode_thickness_um: float = 80.0
    cathode_loading_mg_cm2: float = 10.0         # active material loading
    anode_loading_mg_cm2: float = 8.0

    # Material properties
    cathode_capacity_mAh_g: float = 308.0
    anode_capacity_mAh_g: float = 820.0
    cathode_porosity: float = 0.35
    anode_porosity: float = 0.40
    cathode_conductivity_S_m: float = 10.0
    anode_conductivity_S_m: float = 1.7e7

    # Electrolyte
    electrolyte_type: str = "alkaline"            # alkaline, acidic, organic, gel, solid
    electrolyte_conductivity_S_m: float = 20.0
    separator_thickness_um: float = 25.0

    # Kinetics
    exchange_current_density_A_cm2: float = 5e-3
    alpha: float = 0.5
    D_solid_cm2_s: float = 1e-12                 # solid-state diffusion
    particle_radius_um: float = 5.0

    # Device
    n_cells_series: int = 1
    packaging: str = "printed_flexible"
    temperature_C: float = 25.0

    # Simulation
    C_rate: float = 0.5                          # Discharge rate
    cutoff_V: float = 0.9
    max_V: float = 1.6


@dataclass
class BatteryPerformance:
    """Complete battery performance metrics."""
    # Capacity
    theoretical_capacity_mAh: float = 0.0
    delivered_capacity_mAh: float = 0.0
    areal_capacity_mAh_cm2: float = 0.0
    utilization_pct: float = 0.0

    # Energy
    energy_mWh: float = 0.0
    energy_density_Wh_kg: float = 0.0
    energy_density_Wh_L: float = 0.0
    areal_energy_mWh_cm2: float = 0.0

    # Power
    power_mW: float = 0.0
    power_density_W_kg: float = 0.0

    # Voltage
    OCV_V: float = 0.0
    nominal_V: float = 0.0
    avg_discharge_V: float = 0.0
    internal_resistance_ohm: float = 0.0

    # Rate capability
    rate_capacity: Dict[str, float] = field(default_factory=dict)

    # Aging
    capacity_retention_pct: Dict[str, float] = field(default_factory=dict)

    # Discharge curve
    discharge_soc: List[float] = field(default_factory=list)
    discharge_V: List[float] = field(default_factory=list)
    discharge_t_min: List[float] = field(default_factory=list)
    discharge_capacity_mAh: List[float] = field(default_factory=list)

    # EIS
    eis_freq: List[float] = field(default_factory=list)
    eis_Z_real: List[float] = field(default_factory=list)
    eis_Z_imag: List[float] = field(default_factory=list)

    # Ragone
    ragone_E: List[float] = field(default_factory=list)
    ragone_P: List[float] = field(default_factory=list)

    # Self-discharge
    self_discharge_pct_per_month: float = 0.0

    def to_dict(self) -> dict:
        return {
            "theoretical_capacity_mAh": round(self.theoretical_capacity_mAh, 3),
            "delivered_capacity_mAh": round(self.delivered_capacity_mAh, 3),
            "areal_capacity_mAh_cm2": round(self.areal_capacity_mAh_cm2, 3),
            "utilization_pct": round(self.utilization_pct, 1),
            "energy_mWh": round(self.energy_mWh, 3),
            "energy_density_Wh_kg": round(self.energy_density_Wh_kg, 2),
            "energy_density_Wh_L": round(self.energy_density_Wh_L, 2),
            "areal_energy_mWh_cm2": round(self.areal_energy_mWh_cm2, 3),
            "power_mW": round(self.power_mW, 3),
            "power_density_W_kg": round(self.power_density_W_kg, 2),
            "OCV_V": round(self.OCV_V, 3),
            "nominal_V": round(self.nominal_V, 3),
            "avg_discharge_V": round(self.avg_discharge_V, 3),
            "internal_resistance_ohm": round(self.internal_resistance_ohm, 3),
            "rate_capability": self.rate_capacity,
            "aging": self.capacity_retention_pct,
            "discharge_curve": {
                "SOC": self.discharge_soc,
                "voltage_V": self.discharge_V,
                "time_min": self.discharge_t_min,
                "capacity_mAh": self.discharge_capacity_mAh,
            },
            "eis": {
                "frequencies": self.eis_freq,
                "Z_real": self.eis_Z_real,
                "Z_imag_neg": [-z for z in self.eis_Z_imag],
            },
            "ragone": {"E_Wh_kg": self.ragone_E, "P_W_kg": self.ragone_P},
            "self_discharge_pct_per_month": round(self.self_discharge_pct_per_month, 1),
        }


# ═══════════════════════════════════════════════════════════════════
#   MAIN SIMULATION
# ═══════════════════════════════════════════════════════════════════

def simulate_battery(config: BatteryConfig) -> BatteryPerformance:
    """
    Full printed battery simulation.

    Pipeline:
        1. Capacity calculation (limiting electrode)
        2. Internal resistance (all components)
        3. Discharge curve simulation (SPM + Butler-Volmer)
        4. Energy & power metrics
        5. Rate capability (Peukert's law)
        6. Aging prediction
        7. EIS simulation
        8. Ragone plot
    """
    perf = BatteryPerformance()
    A = config.electrode_area_cm2

    # ── 1. Capacity ──
    Q_cathode = config.cathode_loading_mg_cm2 * A * config.cathode_capacity_mAh_g / 1000
    Q_anode = config.anode_loading_mg_cm2 * A * config.anode_capacity_mAh_g / 1000
    perf.theoretical_capacity_mAh = min(Q_cathode, Q_anode) * config.n_cells_series

    # ── 2. Internal resistance ──
    R_int = _calculate_internal_resistance(config)
    perf.internal_resistance_ohm = R_int

    # ── 3. OCV ──
    soc_full = np.array([0.99])
    perf.OCV_V = float(ocv_from_soc(soc_full, config.chemistry)[0]) * config.n_cells_series

    # ── 4. Discharge simulation ──
    _simulate_discharge(perf, config, R_int)

    # ── 5. Energy & Power ──
    _calculate_energy_power(perf, config)

    # ── 6. Rate capability ──
    _rate_capability(perf, config, R_int)

    # ── 7. Aging ──
    _predict_aging(perf, config)

    # ── 8. EIS ──
    _simulate_battery_eis(perf, config, R_int)

    # ── 9. Ragone ──
    _battery_ragone(perf, config)

    # Self-discharge
    if config.electrolyte_type in ("alkaline", "acidic"):
        perf.self_discharge_pct_per_month = 5.0
    elif config.electrolyte_type == "organic":
        perf.self_discharge_pct_per_month = 2.0
    else:
        perf.self_discharge_pct_per_month = 1.0

    return perf


def _calculate_internal_resistance(config: BatteryConfig) -> float:
    """Total internal resistance from all components."""
    A = config.electrode_area_cm2
    A_m2 = A * 1e-4  # cm² → m²

    # Cathode electronic resistance: R = L / (σ · A)
    L_cathode_m = config.cathode_thickness_um * 1e-6  # µm → m
    R_cathode = L_cathode_m / (
        max(config.cathode_conductivity_S_m, 1e-8) * A_m2
    )
    # Bruggeman correction for porosity
    R_cathode /= (1 - config.cathode_porosity) ** 1.5

    # Anode
    L_anode_m = config.anode_thickness_um * 1e-6
    R_anode = L_anode_m / (
        max(config.anode_conductivity_S_m, 1e-6) * A_m2
    )

    # Electrolyte
    total_thickness_m = (config.cathode_thickness_um + config.anode_thickness_um +
                         config.separator_thickness_um) * 1e-6  # µm → m
    R_electrolyte = total_thickness_m / (
        config.electrolyte_conductivity_S_m * A_m2
    )

    # Contact resistance (printed electrode—current collector interface)
    R_contact = 0.5  # Typical for well-fabricated printed electrodes

    # Charge transfer resistance (Butler-Volmer at equilibrium)
    RT_F = 0.0257  # RT/F at 25°C
    R_ct = RT_F / (config.exchange_current_density_A_cm2 * A)

    R_total = R_cathode + R_anode + R_electrolyte + R_contact + R_ct
    return max(R_total, 0.1)


def _simulate_discharge(
    perf: BatteryPerformance, config: BatteryConfig, R_int: float
):
    """Simulate galvanostatic discharge using Single Particle Model."""
    Q = perf.theoretical_capacity_mAh  # mAh
    I = Q * config.C_rate / 1000  # Discharge current in A

    n_steps = 500
    soc = np.linspace(0.99, 0.01, n_steps)

    # OCV at each SOC
    V_ocv = ocv_from_soc(soc, config.chemistry) * config.n_cells_series

    # Overpotential: η = I·R + η_activation + η_concentration
    eta_ohmic = I * R_int

    # Activation overpotential (Butler-Volmer linearized at low η)
    RT_F = 0.0257
    j = I / config.electrode_area_cm2
    j0 = config.exchange_current_density_A_cm2
    eta_activation = RT_F * np.arcsinh(j / (2 * j0))

    # Concentration overpotential (increases at low SOC)
    eta_concentration = 0.05 * (1 / (soc + 0.01) - 1)
    eta_concentration = np.clip(eta_concentration, 0, 0.5)

    # Terminal voltage
    V_terminal = V_ocv - eta_ohmic - eta_activation - eta_concentration

    # Find cutoff
    cutoff_idx = np.where(V_terminal < config.cutoff_V)[0]
    if len(cutoff_idx) > 0:
        end_idx = cutoff_idx[0]
    else:
        end_idx = n_steps

    soc_used = soc[:end_idx]
    V_used = V_terminal[:end_idx]

    # Time and capacity
    Q_delivered = Q * (0.99 - soc_used[-1]) if end_idx > 1 else 0
    perf.delivered_capacity_mAh = Q_delivered
    perf.utilization_pct = (Q_delivered / Q) * 100 if Q > 0 else 0

    t_total_h = Q_delivered / (I * 1000) if I > 0 else 0
    t_array = np.linspace(0, t_total_h * 60, end_idx)  # minutes

    cap_array = np.linspace(0, Q_delivered, end_idx)

    perf.discharge_soc = soc_used.tolist()
    perf.discharge_V = V_used.tolist()
    perf.discharge_t_min = t_array.tolist()
    perf.discharge_capacity_mAh = cap_array.tolist()

    perf.avg_discharge_V = float(np.mean(V_used)) if len(V_used) > 0 else 0
    perf.nominal_V = float(np.median(V_used)) if len(V_used) > 0 else 0
    perf.areal_capacity_mAh_cm2 = Q_delivered / config.electrode_area_cm2


def _calculate_energy_power(perf: BatteryPerformance, config: BatteryConfig):
    """Calculate energy and power densities."""
    A = config.electrode_area_cm2
    E_mWh = perf.delivered_capacity_mAh * perf.avg_discharge_V
    perf.energy_mWh = E_mWh
    perf.areal_energy_mWh_cm2 = E_mWh / A

    # Mass estimate
    cathode_mass_g = config.cathode_loading_mg_cm2 * A / 1000
    anode_mass_g = config.anode_loading_mg_cm2 * A / 1000
    electrolyte_mass_g = A * config.separator_thickness_um * 1e-4 * 1.2  # ~1.2 g/cm³
    packaging_mass_g = 0.5  # Approximate for printed flexible
    total_mass_g = cathode_mass_g + anode_mass_g + electrolyte_mass_g + packaging_mass_g

    # Volume estimate
    total_thickness_cm = (config.cathode_thickness_um + config.anode_thickness_um +
                          config.separator_thickness_um + 50) * 1e-4  # +50µm packaging
    volume_cm3 = A * total_thickness_cm

    perf.energy_density_Wh_kg = E_mWh / (total_mass_g * 1000) if total_mass_g > 0 else 0
    perf.energy_density_Wh_L = E_mWh / (volume_cm3 * 1000) if volume_cm3 > 0 else 0

    I = perf.theoretical_capacity_mAh * config.C_rate / 1000
    perf.power_mW = perf.avg_discharge_V * I * 1000
    perf.power_density_W_kg = perf.power_mW / (total_mass_g * 1000) if total_mass_g > 0 else 0


def _rate_capability(
    perf: BatteryPerformance, config: BatteryConfig, R_int: float
):
    """Simulate rate capability using Peukert's law and SPM."""
    Q = perf.theoretical_capacity_mAh
    c_rates = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]

    # Peukert exponent: 1.15 for Zn-MnO2 printed, 1.1 for Li-ion
    # (1.25 is too high for printed batteries; use chemistry-specific values)
    if "zinc" in config.chemistry.lower() or "MnO2" in config.chemistry:
        k_peukert = 1.15
    else:
        k_peukert = 1.10

    for C in c_rates:
        I = Q * C / 1000  # A
        # Peukert capacity loss
        Q_eff = Q * (config.C_rate / C) ** (k_peukert - 1)
        # Also reduce for high-rate overpotential
        eta_high = I * R_int
        V_avg = perf.OCV_V - eta_high
        if V_avg < config.cutoff_V:
            Q_eff = Q_eff * 0.1  # Barely delivers
        Q_eff = min(Q_eff, Q)

        perf.rate_capacity[f"{C}C"] = round(Q_eff / Q * 100, 1)


def _predict_aging(perf: BatteryPerformance, config: BatteryConfig):
    """Predict capacity retention over cycles using SEI growth model."""
    # SEI growth: capacity loss ∝ √(cycle number) for Li-ion
    # For Zn-based: more linear degradation due to dendrite/shape change
    is_zinc = "zinc" in config.chemistry.lower()

    if is_zinc:
        k_aging = 0.05  # % loss per cycle (linear)
        for N in [10, 50, 100, 500]:
            retention = max(100 - k_aging * N, 20)
            perf.capacity_retention_pct[f"{N}_cycles"] = round(retention, 1)
    else:
        k_aging = 0.5  # SEI growth factor
        for N in [100, 500, 1000, 5000]:
            retention = 100 * np.exp(-k_aging * np.sqrt(N) / 100)
            perf.capacity_retention_pct[f"{N}_cycles"] = round(max(retention, 50), 1)


def _simulate_battery_eis(
    perf: BatteryPerformance, config: BatteryConfig, R_int: float
):
    """Battery EIS using Randles circuit with finite-length Warburg."""
    frequencies = np.logspace(-2, 5, 70)
    omega = 2 * np.pi * frequencies

    Rs = R_int * 0.3  # Ohmic portion
    Rct = R_int * 0.4  # Charge transfer
    C_dl = 1e-5  # 10 µF
    sigma_w = 20.0  # Warburg coefficient

    # Bounded Warburg for solid-state diffusion
    tau_d = (config.particle_radius_um * 1e-4) ** 2 / max(config.D_solid_cm2_s, 1e-15)

    Z_total = np.zeros(len(frequencies), dtype=complex)

    for i, w in enumerate(omega):
        # CPE
        n_cpe = 0.85
        Y_cpe = C_dl * (1j * w) ** n_cpe

        # Bounded Warburg
        x = np.sqrt(1j * w * tau_d)
        if abs(x) > 20:
            Z_w = sigma_w * np.sqrt(2 / (1j * w * tau_d + 1e-30))
        else:
            Z_w = sigma_w * np.tanh(x) / (x + 1e-30)

        # Parallel
        Z_faradaic = Rct + Z_w
        Z_parallel = 1.0 / (Y_cpe + 1.0 / Z_faradaic)

        Z_total[i] = Rs + Z_parallel

    perf.eis_freq = frequencies.tolist()
    perf.eis_Z_real = np.real(Z_total).tolist()
    perf.eis_Z_imag = np.imag(Z_total).tolist()


def _battery_ragone(perf: BatteryPerformance, config: BatteryConfig):
    """Generate battery Ragone plot."""
    Q = perf.theoretical_capacity_mAh
    R = perf.internal_resistance_ohm

    A = config.electrode_area_cm2
    total_mass_kg = (config.cathode_loading_mg_cm2 + config.anode_loading_mg_cm2) * A * 1e-6

    if total_mass_kg < 1e-12 or Q < 1e-9:
        return

    c_rates = np.logspace(-1, 1.5, 25)

    for C in c_rates:
        I = Q * C / 1000  # A
        V_avg = perf.OCV_V - I * R
        if V_avg < config.cutoff_V:
            continue
        Q_eff = Q * (config.C_rate / C) ** 0.25
        Q_eff = min(Q_eff, Q)
        E_Wh = Q_eff * V_avg / 1000
        t_h = Q_eff / (I * 1000) if I > 0 else 0
        P_W = E_Wh / max(t_h, 1e-9)

        perf.ragone_E.append(round(E_Wh / total_mass_kg, 2))
        perf.ragone_P.append(round(P_W / total_mass_kg, 2))


# ═══════════════════════════════════════════════════════════════════
#   QUICK HELPERS
# ═══════════════════════════════════════════════════════════════════

def quick_battery(
    chemistry: str = "zinc_MnO2",
    area_cm2: float = 1.0,
    C_rate: float = 0.5,
) -> dict:
    """Quick printed battery simulation."""
    config = BatteryConfig(
        chemistry=chemistry,
        electrode_area_cm2=area_cm2,
        C_rate=C_rate,
    )
    # Set chemistry-specific defaults
    if chemistry == "zinc_MnO2":
        config.cathode_capacity_mAh_g = 308
        config.anode_capacity_mAh_g = 820
        config.cutoff_V = 0.9
        config.max_V = 1.6
    elif chemistry == "silver_zinc":
        config.cathode_capacity_mAh_g = 150
        config.anode_capacity_mAh_g = 820
        config.cutoff_V = 1.2
        config.max_V = 1.6
    elif chemistry == "LiFePO4":
        config.cathode_capacity_mAh_g = 170
        config.anode_capacity_mAh_g = 372
        config.cutoff_V = 2.5
        config.max_V = 3.65
        config.electrolyte_type = "organic"
        config.electrolyte_conductivity_S_m = 1.0

    return simulate_battery(config).to_dict()


def list_battery_chemistries() -> List[dict]:
    """List available battery chemistries."""
    return [
        {"name": k, **{kk: vv for kk, vv in v.items() if kk != "coeffs"}}
        for k, v in OCV_MODELS.items()
    ]
