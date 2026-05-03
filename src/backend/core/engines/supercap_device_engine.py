"""
Supercapacitor Device Simulator — Full Cell Physics
=====================================================
Complete device-level simulation for symmetric and asymmetric supercapacitors,
including printed electrode devices.

Physics models:
    - Electrode: EDLC + pseudocapacitance (Helmholtz/Gouy-Chapman/Stern)
    - Device: series/parallel electrode capacitance combination
    - Transmission Line Model (TLM) for porous electrodes
    - Self-discharge modeling (leakage current & charge redistribution)
    - Ragone plot generation (E vs P density)
    - Cycling stability (capacity fade)
    - Printed electrode corrections (contact resistance, film uniformity)

References:
    [1] Conway, "Electrochemical Supercapacitors" (1999)
    [2] Béguin & Frackowiak, "Supercapacitors" (2013)
    [3] Zhang & Zhao, "Flexible and Stretchable Electronics" (2019)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ElectrodeSpec:
    """Electrode specification for supercapacitor device."""
    # Material
    material_name: str = "activated_carbon"
    specific_capacitance_F_g: float = 150.0     # F/g (from CV/GCD)
    conductivity_S_m: float = 1e3               # electrode material

    # Geometry (for printed electrodes)
    length_mm: float = 10.0
    width_mm: float = 10.0
    thickness_um: float = 50.0                   # printed film thickness
    active_mass_mg: float = 1.0                  # active material mass
    porosity: float = 0.4                        # film porosity

    # Electrode properties
    density_g_cm3: float = 0.5
    surface_area_m2_g: float = 1000.0            # BET

    # Contact
    contact_resistance_ohm: float = 0.5          # substrate-to-electrode
    sheet_resistance_ohm_sq: float = 100.0       # collector sheet resistance

    def area_cm2(self) -> float:
        return (self.length_mm * self.width_mm) / 100.0

    def thickness_cm(self) -> float:
        return self.thickness_um * 1e-4

    def mass_g(self) -> float:
        return self.active_mass_mg * 1e-3


@dataclass
class ElectrolyteSpec:
    """Electrolyte specification."""
    name: str = "1M H2SO4"
    conductivity_S_m: float = 38.0               # ionic conductivity
    voltage_window_V: float = 1.0                # electrochemical window
    concentration_M: float = 1.0
    viscosity_mPas: float = 1.0
    type: str = "aqueous"                         # aqueous, organic, ionic_liquid, gel, solid


@dataclass
class DeviceConfig:
    """Full supercapacitor device configuration."""
    electrode_pos: ElectrodeSpec = field(default_factory=ElectrodeSpec)
    electrode_neg: ElectrodeSpec = field(default_factory=ElectrodeSpec)
    electrolyte: ElectrolyteSpec = field(default_factory=ElectrolyteSpec)
    separator_thickness_um: float = 25.0
    separator_porosity: float = 0.6
    is_symmetric: bool = True
    packaging: str = "printed_flexible"           # coin_cell, pouch, printed_flexible
    temperature_C: float = 25.0


@dataclass
class DevicePerformance:
    """Complete device performance metrics."""
    # Capacitance
    C_device_F: float = 0.0
    C_specific_F_g: float = 0.0                  # per total electrode mass
    C_areal_mF_cm2: float = 0.0                  # per geometric area
    C_volumetric_F_cm3: float = 0.0

    # Energy & Power
    energy_Wh_kg: float = 0.0
    energy_mWh_cm2: float = 0.0                  # areal energy
    power_W_kg: float = 0.0
    power_mW_cm2: float = 0.0

    # Resistance
    ESR_ohm: float = 0.0
    ESR_breakdown: Dict[str, float] = field(default_factory=dict)

    # Operating
    voltage_window_V: float = 0.0
    max_current_A: float = 0.0
    charge_time_s: float = 0.0
    discharge_time_s: float = 0.0

    # Ragone data
    ragone_E_Wh_kg: List[float] = field(default_factory=list)
    ragone_P_W_kg: List[float] = field(default_factory=list)

    # Cycling
    retention_1000: float = 0.0                  # % retention at 1000 cycles
    retention_10000: float = 0.0                 # % at 10000 cycles

    # Self-discharge
    self_discharge_V_per_hour: float = 0.0
    voltage_after_24h_pct: float = 0.0

    # GCD waveform
    gcd_time_s: List[float] = field(default_factory=list)
    gcd_voltage_V: List[float] = field(default_factory=list)

    # CV curves at different scan rates
    cv_data: Dict[str, dict] = field(default_factory=dict)

    # EIS
    eis_freq: List[float] = field(default_factory=list)
    eis_Z_real: List[float] = field(default_factory=list)
    eis_Z_imag: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "C_device_F": round(self.C_device_F, 6),
            "C_device_mF": round(self.C_device_F * 1e3, 3),
            "C_specific_F_g": round(self.C_specific_F_g, 2),
            "C_areal_mF_cm2": round(self.C_areal_mF_cm2, 3),
            "C_volumetric_F_cm3": round(self.C_volumetric_F_cm3, 2),
            "energy_Wh_kg": round(self.energy_Wh_kg, 3),
            "energy_mWh_cm2": round(self.energy_mWh_cm2, 4),
            "power_W_kg": round(self.power_W_kg, 2),
            "power_mW_cm2": round(self.power_mW_cm2, 3),
            "ESR_ohm": round(self.ESR_ohm, 3),
            "ESR_breakdown": {k: round(v, 4) for k, v in self.ESR_breakdown.items()},
            "voltage_window_V": round(self.voltage_window_V, 2),
            "max_current_mA": round(self.max_current_A * 1e3, 3),
            "charge_time_s": round(self.charge_time_s, 2),
            "discharge_time_s": round(self.discharge_time_s, 2),
            "ragone": {"E_Wh_kg": self.ragone_E_Wh_kg, "P_W_kg": self.ragone_P_W_kg},
            "retention_1000_cycles_pct": round(self.retention_1000, 1),
            "retention_10000_cycles_pct": round(self.retention_10000, 1),
            "self_discharge_V_per_hour": round(self.self_discharge_V_per_hour, 4),
            "voltage_after_24h_pct": round(self.voltage_after_24h_pct, 1),
            "gcd": {"time_s": self.gcd_time_s, "voltage_V": self.gcd_voltage_V},
            "cv_data": self.cv_data,
            "eis": {
                "frequencies": self.eis_freq,
                "Z_real": self.eis_Z_real,
                "Z_imag_neg": [-z for z in self.eis_Z_imag],
            },
        }


# ═══════════════════════════════════════════════════════════════════
#   DEVICE SIMULATION
# ═══════════════════════════════════════════════════════════════════

def simulate_device(config: DeviceConfig) -> DevicePerformance:
    """
    Full supercapacitor device simulation.

    Pipeline:
        1. Electrode capacitance (EDLC + pseudo)
        2. Device capacitance (series combination)
        3. ESR calculation (all resistance components)
        4. Energy & power density
        5. GCD waveform simulation
        6. Ragone plot generation
        7. EIS simulation with TLM
        8. Cycling stability prediction
        9. Self-discharge modeling
    """
    perf = DevicePerformance()
    epos = config.electrode_pos
    eneg = config.electrode_neg

    # ── 1. Electrode capacitance ──
    C_pos = epos.specific_capacitance_F_g * epos.mass_g()  # F
    C_neg = eneg.specific_capacitance_F_g * eneg.mass_g()

    # ── 2. Device capacitance (series) ──
    if config.is_symmetric:
        C_neg = C_pos
        perf.C_device_F = C_pos / 2  # 1/C = 1/C1 + 1/C2 => C/2
    else:
        perf.C_device_F = (C_pos * C_neg) / (C_pos + C_neg)

    total_mass_g = epos.mass_g() + eneg.mass_g()
    total_area_cm2 = epos.area_cm2()
    total_volume_cm3 = (
        epos.area_cm2() * epos.thickness_cm() +
        eneg.area_cm2() * eneg.thickness_cm() +
        epos.area_cm2() * config.separator_thickness_um * 1e-4
    )

    perf.C_specific_F_g = perf.C_device_F / max(total_mass_g, 1e-9)
    perf.C_areal_mF_cm2 = perf.C_device_F * 1e3 / max(total_area_cm2, 1e-9)
    perf.C_volumetric_F_cm3 = perf.C_device_F / max(total_volume_cm3, 1e-9)

    # ── 3. ESR calculation ──
    # Components: electrode bulk, contact, electrolyte, separator
    R_electrode_pos = _electrode_resistance(epos)
    R_electrode_neg = _electrode_resistance(eneg)
    R_contact = epos.contact_resistance_ohm + eneg.contact_resistance_ohm
    R_electrolyte = _electrolyte_resistance(config)
    R_separator = _separator_resistance(config)

    perf.ESR_ohm = R_electrode_pos + R_electrode_neg + R_contact + R_electrolyte + R_separator
    perf.ESR_breakdown = {
        "R_electrode_pos": R_electrode_pos,
        "R_electrode_neg": R_electrode_neg,
        "R_contact": R_contact,
        "R_electrolyte": R_electrolyte,
        "R_separator": R_separator,
    }

    # ── 4. Energy & Power ──
    V = config.electrolyte.voltage_window_V
    perf.voltage_window_V = V

    # E = 0.5 * C * V²
    E_J = 0.5 * perf.C_device_F * V ** 2
    perf.energy_Wh_kg = E_J / (3600 * total_mass_g * 1e-3)  # J → Wh/kg
    perf.energy_mWh_cm2 = E_J / (3.6 * total_area_cm2)       # J → mWh/cm²

    # P_max = V²/(4·ESR)  (matched load)
    P_max_W = V**2 / (4 * max(perf.ESR_ohm, 1e-6))
    perf.power_W_kg = P_max_W / (total_mass_g * 1e-3)
    perf.power_mW_cm2 = P_max_W * 1e3 / total_area_cm2

    # Max current (limited by ESR and voltage)
    perf.max_current_A = V / (2 * max(perf.ESR_ohm, 1e-6))

    # Charge/discharge time at 1 A/g
    I_1Ag = total_mass_g * 1e-3  # 1 A/g × mass_kg
    perf.charge_time_s = perf.C_device_F * V / max(I_1Ag, 1e-9)
    perf.discharge_time_s = perf.charge_time_s * 0.95  # ~95% coulombic

    # ── 5. GCD waveform ──
    _simulate_gcd_waveform(perf, config, n_cycles=3)

    # ── 6. Ragone plot ──
    _generate_ragone(perf, config, total_mass_g)

    # ── 7. EIS with TLM ──
    _simulate_device_eis(perf, config)

    # ── 8. Cycling stability ──
    _predict_cycling(perf, config)

    # ── 9. Self-discharge ──
    _model_self_discharge(perf, config)

    # ── 10. CV at multiple scan rates ──
    _simulate_device_cv(perf, config)

    return perf


# ═══════════════════════════════════════════════════════════════════
#   RESISTANCE MODELS
# ═══════════════════════════════════════════════════════════════════

def _electrode_resistance(electrode: ElectrodeSpec) -> float:
    """Electrode bulk + ionic resistance in porous structure."""
    # Electronic resistance through film: R = L / (σ · A)
    # area_cm2() * 1e-4 → m²; thickness_cm() * 1e-2 → m
    # R = m / (S/m · m²) = Ω  ✓
    R_electronic = 1.0 / (
        max(electrode.conductivity_S_m, 1e-6) *
        electrode.area_cm2() * 1e-4 /
        max(electrode.thickness_cm() * 1e-2, 1e-9)
    )
    # Correct for porosity (Bruggeman)
    tortuosity = (1 - electrode.porosity) ** (-0.5)
    R_ionic = tortuosity * 0.5 / max(electrode.area_cm2() * 1e-4, 1e-9)
    return R_electronic + R_ionic


def _electrolyte_resistance(config: DeviceConfig) -> float:
    """Bulk electrolyte resistance between electrodes."""
    sep_thickness_m = config.separator_thickness_um * 1e-6
    area_m2 = config.electrode_pos.area_cm2() * 1e-4
    return sep_thickness_m / (
        config.electrolyte.conductivity_S_m * max(area_m2, 1e-9)
    )


def _separator_resistance(config: DeviceConfig) -> float:
    """Separator contribution (tortuous ionic path)."""
    tortuosity = 1.0 / max(config.separator_porosity, 0.1)
    return tortuosity * 0.1  # Small additional contribution


# ═══════════════════════════════════════════════════════════════════
#   GCD WAVEFORM
# ═══════════════════════════════════════════════════════════════════

def _simulate_gcd_waveform(
    perf: DevicePerformance, config: DeviceConfig, n_cycles: int = 3
):
    """Generate realistic GCD waveform with IR drop and non-linearity."""
    C = perf.C_device_F
    V_max = config.electrolyte.voltage_window_V
    ESR = perf.ESR_ohm
    total_mass_g = config.electrode_pos.mass_g() + config.electrode_neg.mass_g()
    I = total_mass_g * 1e-3  # 1 A/g

    if C < 1e-12 or I < 1e-15:
        return

    dt = V_max * C / (I * 500)  # ~500 points per half-cycle
    time_points = []
    voltage_points = []
    t = 0

    for cyc in range(n_cycles):
        # Charge
        V = I * ESR  # IR drop at start
        for _ in range(500):
            V += I * dt / C
            if V >= V_max:
                V = V_max
                break
            time_points.append(t)
            voltage_points.append(V)
            t += dt

        # Discharge
        V = V_max - I * ESR  # IR drop
        for _ in range(500):
            V -= I * dt / C
            if V <= 0:
                V = 0
                break
            time_points.append(t)
            voltage_points.append(V)
            t += dt

    perf.gcd_time_s = [round(x, 6) for x in time_points]
    perf.gcd_voltage_V = [round(x, 6) for x in voltage_points]


# ═══════════════════════════════════════════════════════════════════
#   RAGONE PLOT
# ═══════════════════════════════════════════════════════════════════

def _generate_ragone(
    perf: DevicePerformance, config: DeviceConfig, total_mass_g: float
):
    """
    Generate Ragone plot data (E vs P) at different C-rates.

    E = 0.5·C·(V² - (I·ESR)²) / (mass)
    P = E / t_discharge
    """
    C = perf.C_device_F
    V = config.electrolyte.voltage_window_V
    ESR = perf.ESR_ohm
    mass_kg = total_mass_g * 1e-3

    if mass_kg < 1e-12 or C < 1e-15:
        return

    # Different current densities (A/g): 0.1 to 100
    A_g_values = np.logspace(-1, 2, 30)

    E_list = []
    P_list = []

    for A_g in A_g_values:
        I = A_g * mass_kg  # Current in A
        IR_drop = I * ESR
        if IR_drop >= V:
            continue  # Can't operate at this rate
        V_eff = V - IR_drop
        E_J = 0.5 * C * V_eff**2
        t_dis = C * V_eff / max(I, 1e-15)
        E_Wh_kg = E_J / (3600 * mass_kg)
        P_W_kg = E_Wh_kg * 3600 / max(t_dis, 1e-9)
        E_list.append(round(E_Wh_kg, 4))
        P_list.append(round(P_W_kg, 2))

    perf.ragone_E_Wh_kg = E_list
    perf.ragone_P_W_kg = P_list


# ═══════════════════════════════════════════════════════════════════
#   DEVICE EIS (Transmission Line Model)
# ═══════════════════════════════════════════════════════════════════

def _simulate_device_eis(perf: DevicePerformance, config: DeviceConfig):
    """
    Simulate device-level EIS using Transmission Line Model (TLM).

    TLM models the distributed resistance-capacitance along porous electrode:
    Z_TLM = √(R_ion·Z_el) · coth(√(R_ion/Z_el))

    where R_ion = ionic resistance per unit length
          Z_el = element impedance (CPE | R_ct)
    """
    frequencies = np.logspace(-2, 5, 80)
    omega = 2 * np.pi * frequencies

    C = perf.C_device_F
    ESR = perf.ESR_ohm

    # Simplified TLM: Z = ESR + 1/(jωC) with distributed correction
    R_ion = ESR * 0.3  # Ionic resistance in pores
    R_ct = ESR * 0.2   # Charge transfer

    Z_total = np.zeros(len(frequencies), dtype=complex)

    for i, w in enumerate(omega):
        # CPE element
        n_cpe = 0.92
        Y_cpe = C * (1j * w) ** n_cpe

        # Warburg for diffusion in pores
        sigma_w = 5.0
        Z_w = sigma_w * (1 - 1j) / np.sqrt(max(w, 1e-12))

        # Faradaic branch
        Z_f = R_ct + Z_w

        # TLM impedance
        Z_el = 1.0 / (Y_cpe + 1.0 / Z_f)
        x = np.sqrt(R_ion * (1.0 / Z_el + 1e-20))

        # coth with numerical stability
        if abs(x) > 20:
            Z_tlm = np.sqrt(R_ion * Z_el)
        else:
            Z_tlm = np.sqrt(R_ion * Z_el) * (np.cosh(x) / (np.sinh(x) + 1e-30))

        Z_total[i] = ESR * 0.5 + Z_tlm  # Add ohmic resistance

    perf.eis_freq = frequencies.tolist()
    perf.eis_Z_real = np.real(Z_total).tolist()
    perf.eis_Z_imag = np.imag(Z_total).tolist()


# ═══════════════════════════════════════════════════════════════════
#   CYCLING STABILITY
# ═══════════════════════════════════════════════════════════════════

def _predict_cycling(perf: DevicePerformance, config: DeviceConfig):
    """
    Predict cycling stability using empirical degradation models.

    Retention ≈ 100% × exp(-k × N^β)

    k depends on: material type, voltage window, temperature
    β ≈ 0.5 for EDLC, 0.3-0.7 for pseudocapacitive
    """
    # Base degradation rate
    k = 1e-4  # Base for carbon EDLC

    # Material-dependent correction
    if config.electrode_pos.specific_capacitance_F_g > 300:
        k *= 3  # Pseudocapacitive degrades faster

    # Voltage window stress
    V_ratio = config.electrolyte.voltage_window_V / 1.0
    k *= V_ratio ** 2

    # Temperature acceleration (Arrhenius-like)
    T = config.temperature_C
    k *= np.exp(0.02 * (T - 25))

    beta = 0.5

    perf.retention_1000 = 100.0 * np.exp(-k * 1000 ** beta)
    perf.retention_10000 = 100.0 * np.exp(-k * 10000 ** beta)

    perf.retention_1000 = max(perf.retention_1000, 50)
    perf.retention_10000 = max(perf.retention_10000, 30)


# ═══════════════════════════════════════════════════════════════════
#   SELF-DISCHARGE
# ═══════════════════════════════════════════════════════════════════

def _model_self_discharge(perf: DevicePerformance, config: DeviceConfig):
    """
    Model self-discharge through leakage resistance.

    V(t) = V₀ × exp(-t / (R_leak × C))

    R_leak depends on electrolyte type and separator quality.
    """
    C = perf.C_device_F
    V0 = config.electrolyte.voltage_window_V

    # Leakage resistance (higher = better)
    R_leak_base = {
        "aqueous": 1e4,
        "organic": 1e5,
        "ionic_liquid": 5e5,
        "gel": 5e4,
        "solid": 1e6,
    }.get(config.electrolyte.type, 1e4)

    tau = R_leak_base * max(C, 1e-12)  # Time constant (s)

    # V drop per hour
    if tau > 0:
        perf.self_discharge_V_per_hour = V0 * (1 - np.exp(-3600 / tau))
    else:
        perf.self_discharge_V_per_hour = V0

    # Voltage after 24h (%)
    if tau > 0:
        V_24h = V0 * np.exp(-86400 / tau)
        perf.voltage_after_24h_pct = (V_24h / V0) * 100
    else:
        perf.voltage_after_24h_pct = 0


# ═══════════════════════════════════════════════════════════════════
#   DEVICE CV
# ═══════════════════════════════════════════════════════════════════

def _simulate_device_cv(perf: DevicePerformance, config: DeviceConfig):
    """
    Simulate CV at multiple scan rates for device-level analysis.
    """
    C = perf.C_device_F
    ESR = perf.ESR_ohm
    V_max = config.electrolyte.voltage_window_V

    scan_rates = [5, 10, 20, 50, 100, 200]  # mV/s

    for sr_mVs in scan_rates:
        sr = sr_mVs * 1e-3  # V/s
        n_pts = 200
        E = np.linspace(0, V_max, n_pts)

        # Forward scan: i = C·dV/dt + V/R_leak
        i_forward = C * sr + E / 1e5  # Capacitive + leakage
        # Add ESR distortion
        i_forward += E * sr / max(ESR, 1e-6) * 0.01

        # Reverse scan
        E_rev = E[::-1]
        i_reverse = -C * sr + E_rev / 1e5
        i_reverse -= E_rev * sr / max(ESR, 1e-6) * 0.01

        E_full = np.concatenate([E, E_rev])
        i_full = np.concatenate([i_forward, i_reverse])

        perf.cv_data[f"{sr_mVs}mV_s"] = {
            "E_V": E_full.tolist(),
            "i_A": i_full.tolist(),
            "i_mA": (i_full * 1e3).tolist(),
        }


# ═══════════════════════════════════════════════════════════════════
#   QUICK HELPERS
# ═══════════════════════════════════════════════════════════════════

def quick_supercap_simulation(
    material: str = "activated_carbon",
    capacitance_F_g: float = 150.0,
    mass_mg: float = 1.0,
    area_mm2: float = 100.0,
    thickness_um: float = 50.0,
    electrolyte: str = "1M H2SO4",
    voltage_V: float = 1.0,
) -> dict:
    """Quick supercapacitor device simulation with minimal parameters."""
    espec = ElectrodeSpec(
        material_name=material,
        specific_capacitance_F_g=capacitance_F_g,
        active_mass_mg=mass_mg,
        length_mm=np.sqrt(area_mm2),
        width_mm=np.sqrt(area_mm2),
        thickness_um=thickness_um,
    )

    electrolyte_conductivities = {
        "1M H2SO4": 38.0, "6M KOH": 60.0, "1M Na2SO4": 8.0,
        "1M TEABF4/ACN": 5.0, "EMIMBF4": 1.5,
    }

    espec_elec = ElectrolyteSpec(
        name=electrolyte,
        conductivity_S_m=electrolyte_conductivities.get(electrolyte, 10.0),
        voltage_window_V=voltage_V,
    )

    config = DeviceConfig(
        electrode_pos=espec,
        electrode_neg=espec,
        electrolyte=espec_elec,
        is_symmetric=True,
    )

    return simulate_device(config).to_dict()
