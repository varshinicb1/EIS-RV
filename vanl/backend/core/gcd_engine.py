"""
Virtual Galvanostatic Charge-Discharge (GCD) Engine
=====================================================
Physics-based GCD simulation for supercapacitors and batteries.

Governing equations:

    Supercapacitor (ideal EDLC):
        V(t) = V₀ + (I/C)t - I×Rs         (charging)
        V(t) = V₀ - (I/C)t - I×Rs         (discharging)
        where IR drop = I × Rs at transitions

    Supercapacitor (with pseudocapacitance):
        V(t) = V₀ + (I/C_total)t + η_ct(t)
        where C_total = C_dl + C_pseudo
        η_ct accounts for charge-transfer overpotential

    Battery:
        V(t) = E_eq(SOC) - I×R_internal - η_ct - η_diff
        E_eq follows Nernst equation: E = E⁰ + (RT/nF)ln(SOC/(1-SOC))

Key outputs:
    - Specific capacitance: Cs = I×Δt / (m×ΔV)
    - Energy density: E = ½CΔV² / m  (Wh/kg)
    - Power density: P = E/Δt  (W/kg)
    - Coulombic efficiency: η = t_discharge/t_charge × 100%

References:
    - Conway, Electrochemical Supercapacitors, Springer (1999)
    - Gogotsi & Simon, Science 334, 917 (2011)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

F = 96485.33212  # C/mol
R = 8.314462618  # J/(mol·K)


@dataclass
class GCDParameters:
    """Parameters for galvanostatic charge-discharge simulation."""
    # Electrode
    electrode_area_cm2: float = 0.0707   # cm²
    active_mass_mg: float = 1.0          # mg of active material
    roughness_factor: float = 1.0

    # Capacitance model
    Cdl_F: float = 1e-3                  # Double-layer capacitance (F)
    C_pseudo_F: float = 0.0              # Pseudocapacitance (F)
    Rs_ohm: float = 5.0                  # Series resistance (Ω)
    Rct_ohm: float = 50.0               # Charge transfer resistance (Ω)
    ESR_ohm: float = 0.0                 # Equivalent series resistance (auto-computed if 0)

    # Battery mode
    is_battery: bool = False
    capacity_mAh: float = 0.0           # Battery capacity (mAh)
    E_eq_V: float = 0.0                 # Equilibrium potential (V)
    n_electrons: int = 1

    # Operating conditions
    current_A: float = 1e-3              # Applied current (A)
    current_density_A_g: float = 0.0     # A/g (overrides current_A if > 0)
    V_min: float = 0.0                   # Lower voltage limit (V)
    V_max: float = 1.0                   # Upper voltage limit (V)
    n_cycles: int = 3                    # Number of charge-discharge cycles
    temperature_K: float = 298.15        # K

    @property
    def total_capacitance_F(self) -> float:
        return self.Cdl_F + self.C_pseudo_F

    @property
    def applied_current_A(self) -> float:
        if self.current_density_A_g > 0 and self.active_mass_mg > 0:
            return self.current_density_A_g * self.active_mass_mg * 1e-3
        return self.current_A

    @property
    def total_resistance_ohm(self) -> float:
        if self.ESR_ohm > 0:
            return self.ESR_ohm
        return self.Rs_ohm + self.Rct_ohm * 0.1  # Approximate ESR


@dataclass
class GCDResult:
    """Complete GCD simulation result."""
    time: np.ndarray           # Time array (s)
    voltage: np.ndarray        # Voltage array (V)
    current: np.ndarray        # Current array (A)
    cycle_indices: List[Tuple[int, int]]  # Start/end index for each cycle
    params: GCDParameters

    # Per-cycle analysis
    cycle_data: List[Dict] = field(default_factory=list)

    # Summary
    avg_specific_capacitance_F_g: float = 0.0
    avg_energy_Wh_kg: float = 0.0
    avg_power_W_kg: float = 0.0
    avg_coulombic_efficiency_pct: float = 0.0
    capacity_retention_pct: float = 100.0

    def to_dict(self) -> dict:
        return {
            "time_s": self.time.tolist(),
            "voltage_V": self.voltage.tolist(),
            "current_A": self.current.tolist(),
            "cycle_data": self.cycle_data,
            "summary": {
                "specific_capacitance_F_g": round(self.avg_specific_capacitance_F_g, 2),
                "energy_density_Wh_kg": round(self.avg_energy_Wh_kg, 4),
                "power_density_W_kg": round(self.avg_power_W_kg, 2),
                "coulombic_efficiency_pct": round(self.avg_coulombic_efficiency_pct, 1),
                "capacity_retention_pct": round(self.capacity_retention_pct, 1),
                "ESR_ohm": round(self.params.total_resistance_ohm, 3),
                "IR_drop_V": round(2 * self.params.applied_current_A * self.params.total_resistance_ohm, 4),
            },
        }


def simulate_gcd(params: GCDParameters, dt: float = 0.01) -> GCDResult:
    """
    Simulate galvanostatic charge-discharge cycles.

    For supercapacitor mode:
        Solves dV/dt = I/C with IR drop and charge-transfer effects.

    For battery mode:
        Tracks SOC and uses Nernst-based OCV curve with overpotentials.

    Args:
        params: GCD simulation parameters
        dt: Time step (s)

    Returns:
        GCDResult with full voltage-time data and per-cycle analysis
    """
    I = params.applied_current_A
    if I <= 0:
        raise ValueError("Current must be positive")

    mass_kg = params.active_mass_mg * 1e-6  # mg -> kg

    if params.is_battery:
        return _simulate_battery_gcd(params, dt)

    # --- Supercapacitor mode ---
    C_total = params.total_capacitance_F
    if C_total <= 0:
        raise ValueError("Total capacitance must be positive")

    R_total = params.total_resistance_ohm
    V_range = params.V_max - params.V_min

    # Estimate time per half-cycle
    t_half = C_total * V_range / I
    t_total = t_half * 2 * params.n_cycles * 1.1  # 10% margin

    n_steps = int(t_total / dt) + 1
    max_steps = 500000  # Safety limit
    if n_steps > max_steps:
        dt = t_total / max_steps
        n_steps = max_steps

    time_arr = np.zeros(n_steps)
    voltage_arr = np.zeros(n_steps)
    current_arr = np.zeros(n_steps)

    V = params.V_min
    charging = True
    cycle = 0
    step = 0
    cycle_indices = []
    cycle_start = 0

    # Pseudocapacitive contribution (voltage-dependent)
    has_pseudo = params.C_pseudo_F > 0

    while step < n_steps - 1 and cycle < params.n_cycles:
        # Current direction
        i_applied = I if charging else -I

        # IR drop at transitions
        IR_drop = i_applied * R_total

        # Effective capacitance (can vary with voltage for pseudocap)
        if has_pseudo:
            # Pseudocapacitance has voltage dependence (simplified Gaussian peak)
            V_norm = (V - params.V_min) / V_range
            pseudo_factor = 1.0 + 0.5 * np.exp(-((V_norm - 0.5)**2) / 0.08)
            C_eff = params.Cdl_F + params.C_pseudo_F * pseudo_factor
        else:
            C_eff = C_total

        # Voltage change
        dV = i_applied * dt / C_eff

        # Self-discharge (small leakage)
        V_new = V + dV - V * 1e-5 * dt

        # Check limits
        if charging and V_new >= params.V_max:
            V_new = params.V_max
            charging = False

        if not charging and V_new <= params.V_min:
            V_new = params.V_min
            charging = True
            cycle += 1
            cycle_indices.append((cycle_start, step))
            cycle_start = step + 1

        time_arr[step] = step * dt
        voltage_arr[step] = V_new
        current_arr[step] = i_applied
        V = V_new
        step += 1

    # Trim arrays
    time_arr = time_arr[:step]
    voltage_arr = voltage_arr[:step]
    current_arr = current_arr[:step]

    # If last cycle incomplete, still add it
    if cycle_start < step:
        cycle_indices.append((cycle_start, step - 1))

    result = GCDResult(
        time=time_arr,
        voltage=voltage_arr,
        current=current_arr,
        cycle_indices=cycle_indices,
        params=params,
    )

    _analyze_gcd_cycles(result, mass_kg)

    return result


def _simulate_battery_gcd(params: GCDParameters, dt: float) -> GCDResult:
    """Simulate battery GCD using Nernst equation + overpotentials."""
    I = params.applied_current_A
    cap_As = params.capacity_mAh * 3.6  # mAh -> coulombs

    if cap_As <= 0:
        raise ValueError("Battery capacity must be positive")

    mass_kg = params.active_mass_mg * 1e-6
    R_total = params.total_resistance_ohm
    f = F / (R * params.temperature_K)

    # Estimate time
    t_charge = cap_As / I
    t_total = t_charge * 2 * params.n_cycles * 1.2

    n_steps = min(int(t_total / dt) + 1, 500000)
    dt = t_total / n_steps

    time_arr = np.zeros(n_steps)
    voltage_arr = np.zeros(n_steps)
    current_arr = np.zeros(n_steps)

    SOC = 0.01  # Start near empty
    charging = True
    cycle = 0
    step = 0
    cycle_indices = []
    cycle_start = 0

    while step < n_steps - 1 and cycle < params.n_cycles:
        i_applied = I if charging else -I

        # State of charge update
        dSOC = i_applied * dt / cap_As
        SOC_new = np.clip(SOC + dSOC, 0.001, 0.999)

        # Open circuit voltage (Nernst)
        E_oc = params.E_eq_V + (R * params.temperature_K) / (params.n_electrons * F) * np.log(SOC_new / (1 - SOC_new))

        # Terminal voltage
        V = E_oc + i_applied * R_total

        # Clamp
        V = np.clip(V, params.V_min, params.V_max)

        if charging and (SOC_new >= 0.99 or V >= params.V_max):
            charging = False

        if not charging and (SOC_new <= 0.01 or V <= params.V_min):
            charging = True
            cycle += 1
            cycle_indices.append((cycle_start, step))
            cycle_start = step + 1

        time_arr[step] = step * dt
        voltage_arr[step] = V
        current_arr[step] = i_applied
        SOC = SOC_new
        step += 1

    time_arr = time_arr[:step]
    voltage_arr = voltage_arr[:step]
    current_arr = current_arr[:step]

    if cycle_start < step:
        cycle_indices.append((cycle_start, step - 1))

    result = GCDResult(
        time=time_arr,
        voltage=voltage_arr,
        current=current_arr,
        cycle_indices=cycle_indices,
        params=params,
    )

    _analyze_gcd_cycles(result, mass_kg)

    return result


def _analyze_gcd_cycles(result: GCDResult, mass_kg: float):
    """Analyze each charge-discharge cycle."""
    p = result.params
    I = p.applied_current_A
    V_range = p.V_max - p.V_min

    capacitances = []
    energies = []
    powers = []
    efficiencies = []

    for idx, (start, end) in enumerate(result.cycle_indices):
        if end <= start:
            continue

        t_cycle = result.time[start:end+1]
        V_cycle = result.voltage[start:end+1]
        I_cycle = result.current[start:end+1]

        # Split into charge and discharge
        charge_mask = I_cycle > 0
        discharge_mask = I_cycle < 0

        t_charge = np.sum(charge_mask) * (t_cycle[1] - t_cycle[0]) if len(t_cycle) > 1 else 0
        t_discharge = np.sum(discharge_mask) * (t_cycle[1] - t_cycle[0]) if len(t_cycle) > 1 else 0

        # Specific capacitance: Cs = I × Δt / (m × ΔV)
        if mass_kg > 0 and V_range > 0 and t_discharge > 0:
            Cs = I * t_discharge / (mass_kg * 1e3 * V_range)  # F/g
        else:
            Cs = 0

        # Energy: E = ½ C V² (in Wh/kg)
        if mass_kg > 0 and Cs > 0:
            E_wh_kg = 0.5 * Cs * V_range**2 / 3.6  # F/g × V² / 3600 × 1000
        else:
            E_wh_kg = 0

        # Power: P = E/t
        if t_discharge > 0 and E_wh_kg > 0:
            P_w_kg = E_wh_kg * 3600 / t_discharge  # Wh/kg × 3600 / s = W/kg
        else:
            P_w_kg = 0

        # Coulombic efficiency
        if t_charge > 0:
            eta = (t_discharge / t_charge) * 100
        else:
            eta = 0

        cycle_info = {
            "cycle": idx + 1,
            "t_charge_s": round(t_charge, 3),
            "t_discharge_s": round(t_discharge, 3),
            "specific_capacitance_F_g": round(Cs, 2),
            "energy_Wh_kg": round(E_wh_kg, 4),
            "power_W_kg": round(P_w_kg, 2),
            "coulombic_efficiency_pct": round(eta, 1),
        }

        result.cycle_data.append(cycle_info)
        capacitances.append(Cs)
        energies.append(E_wh_kg)
        powers.append(P_w_kg)
        efficiencies.append(eta)

    if capacitances:
        result.avg_specific_capacitance_F_g = float(np.mean(capacitances))
        result.avg_energy_Wh_kg = float(np.mean(energies))
        result.avg_power_W_kg = float(np.mean(powers))
        result.avg_coulombic_efficiency_pct = float(np.mean(efficiencies))
        if len(capacitances) > 1 and capacitances[0] > 0:
            result.capacity_retention_pct = float(capacitances[-1] / capacitances[0] * 100)


def rate_capability_study(
    params: GCDParameters,
    current_densities_A_g: List[float] = None,
) -> Dict:
    """
    Run GCD at multiple current densities for rate capability analysis.

    Returns specific capacitance vs current density.
    """
    if current_densities_A_g is None:
        current_densities_A_g = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0]

    results = []
    for j in current_densities_A_g:
        p = GCDParameters(**{
            k: getattr(params, k) for k in params.__dataclass_fields__
        })
        p.current_density_A_g = j
        p.n_cycles = 1
        gcd = simulate_gcd(p)
        results.append({
            "current_density_A_g": j,
            "specific_capacitance_F_g": gcd.avg_specific_capacitance_F_g,
            "energy_Wh_kg": gcd.avg_energy_Wh_kg,
            "power_W_kg": gcd.avg_power_W_kg,
        })

    return {
        "current_densities": current_densities_A_g,
        "data": results,
    }
