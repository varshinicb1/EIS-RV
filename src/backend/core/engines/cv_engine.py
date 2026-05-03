"""
Virtual Cyclic Voltammetry (CV) Engine
========================================
Physics-based CV simulation using Butler-Volmer kinetics
and semi-infinite linear diffusion (Randles-Sevcik framework).

Governing equations:
    i(E) = i_faradaic(E) + i_capacitive(E)

    Faradaic current (reversible):
        i_f = nFAC₀√(πDv) × χ(σt)
        where χ is the dimensionless current function (Nicholson-Shain)

    Faradaic current (quasi-reversible, Butler-Volmer):
        i_f = nFAk₀[C_O(0,t)exp(-αf(E-E⁰)) - C_R(0,t)exp((1-α)f(E-E⁰))]
        where f = F/RT

    Capacitive current:
        i_cap = C_dl × dE/dt = C_dl × v  (for sweep)

    Randles-Sevcik (peak current, reversible):
        i_p = 0.4463 × n^(3/2) × F^(3/2) × A × C₀ × √(Dv/(RT))

Physical constants:
    F = 96485 C/mol
    R = 8.314 J/(mol·K)
    T = 298.15 K (25°C default)

References:
    - Bard & Faulkner, Electrochemical Methods, 3rd Ed.
    - Nicholson & Shain, Anal. Chem. 36, 706-723 (1964)
    - Compton & Banks, Understanding Voltammetry, 3rd Ed.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

# Physical constants
F = 96485.33212  # Faraday constant, C/mol
R = 8.314462618  # Gas constant, J/(mol·K)


@dataclass
class CVParameters:
    """Parameters for cyclic voltammetry simulation."""
    # Electrode
    electrode_area_cm2: float = 0.0707  # 3mm diameter (πr²)
    roughness_factor: float = 1.0       # Effective/geometric area ratio

    # Redox couple
    E_formal_V: float = 0.23           # Formal potential vs ref (V)
    n_electrons: int = 1               # Number of electrons transferred
    C_ox_bulk_M: float = 5e-3          # Bulk oxidant concentration (mol/L)
    C_red_bulk_M: float = 5e-3         # Bulk reductant concentration
    D_ox_cm2_s: float = 7.6e-6        # Diffusion coefficient of Ox (cm²/s)
    D_red_cm2_s: float = 7.6e-6       # Diffusion coefficient of Red

    # Kinetics
    k0_cm_s: float = 0.01             # Standard rate constant (cm/s)
    alpha: float = 0.5                 # Charge transfer coefficient

    # Double layer
    Cdl_F_cm2: float = 20e-6          # Double-layer capacitance (F/cm²)
    Rs_ohm: float = 10.0              # Uncompensated resistance (Ω)

    # Scan
    E_start_V: float = -0.3           # Start potential (V)
    E_vertex1_V: float = 0.8          # First vertex potential
    E_vertex2_V: float = -0.3         # Second vertex (= start for simple CV)
    scan_rate_V_s: float = 0.05       # Scan rate (V/s)
    n_cycles: int = 1                 # Number of cycles
    temperature_K: float = 298.15     # Temperature (K)

    @property
    def E_range(self) -> Tuple[float, float]:
        """Potential window."""
        return min(self.E_start_V, self.E_vertex2_V), self.E_vertex1_V

    @property
    def f(self) -> float:
        """F/(RT) at operating temperature."""
        return F / (R * self.temperature_K)


@dataclass
class CVResult:
    """Complete CV simulation result."""
    E: np.ndarray          # Potential array (V)
    i_total: np.ndarray    # Total current (A)
    i_faradaic: np.ndarray # Faradaic current (A)
    i_capacitive: np.ndarray  # Capacitive current (A)
    time: np.ndarray       # Time array (s)
    params: CVParameters

    # Derived quantities
    i_pa: float = 0.0      # Anodic peak current (A)
    i_pc: float = 0.0      # Cathodic peak current (A)
    E_pa: float = 0.0      # Anodic peak potential (V)
    E_pc: float = 0.0      # Cathodic peak potential (V)
    delta_Ep: float = 0.0  # Peak separation (V)
    charge_anodic_C: float = 0.0   # Anodic charge (C)
    charge_cathodic_C: float = 0.0 # Cathodic charge (C)
    specific_capacitance_F_g: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "E": self.E.tolist(),
            "i_total": self.i_total.tolist(),
            "i_faradaic": self.i_faradaic.tolist(),
            "i_capacitive": self.i_capacitive.tolist(),
            "time": self.time.tolist(),
            "analysis": {
                "i_pa_A": float(self.i_pa),
                "i_pc_A": float(self.i_pc),
                "i_pa_mA": float(self.i_pa * 1e3),
                "i_pc_mA": float(self.i_pc * 1e3),
                "E_pa_V": float(self.E_pa),
                "E_pc_V": float(self.E_pc),
                "delta_Ep_mV": float(self.delta_Ep * 1e3),
                "E_half_V": float((self.E_pa + self.E_pc) / 2),
                "ip_ratio": float(abs(self.i_pa / self.i_pc)) if self.i_pc != 0 else None,
                "charge_anodic_mC": float(self.charge_anodic_C * 1e3),
                "charge_cathodic_mC": float(self.charge_cathodic_C * 1e3),
                "coulombic_efficiency_pct": float(
                    abs(self.charge_cathodic_C / self.charge_anodic_C) * 100
                ) if self.charge_anodic_C != 0 else None,
                "specific_capacitance_F_g": self.specific_capacitance_F_g,
                "reversibility": self._classify_reversibility(),
            },
            "randles_sevcik": {
                "i_p_theoretical_A": float(self._randles_sevcik_ip()),
                "D_apparent_cm2_s": float(self._apparent_D()),
            },
        }

    def _classify_reversibility(self) -> str:
        """Classify the electrochemical reversibility."""
        if self.delta_Ep < 0.065:
            return "reversible (Nernstian)"
        elif self.delta_Ep < 0.200:
            return "quasi-reversible"
        else:
            return "irreversible"

    def _randles_sevcik_ip(self) -> float:
        """Theoretical peak current from Randles-Sevcik equation.

        i_p = 0.4463 · n^(3/2) · F^(3/2) · A · C · √(Dv/RT)

        Units: D in cm²/s, C in mol/cm³ (= M × 1e-3), A in cm²
        → i_p in Amperes. Constant 0.4463 is correct for these SI-cgs units
        (Bard & Faulkner, 3rd Ed., eq. 6.2.18).
        """
        p = self.params
        A_eff = p.electrode_area_cm2 * p.roughness_factor
        C = p.C_ox_bulk_M * 1e-3  # mol/cm³
        n = p.n_electrons
        v = p.scan_rate_V_s
        D = p.D_ox_cm2_s
        T = p.temperature_K
        return 0.4463 * n**1.5 * F**1.5 * A_eff * C * np.sqrt(D * v / (R * T))

    def _apparent_D(self) -> float:
        """Calculate apparent D from measured peak current."""
        p = self.params
        A_eff = p.electrode_area_cm2 * p.roughness_factor
        C = p.C_ox_bulk_M * 1e-3  # mol/cm³
        n = p.n_electrons
        v = p.scan_rate_V_s
        T = p.temperature_K
        ip = abs(self.i_pa) if self.i_pa != 0 else 1e-10
        # ip = 0.4463 * n^1.5 * F^1.5 * A * C * sqrt(Dv/RT)
        # D = (ip / (0.4463 * n^1.5 * F^1.5 * A * C))² * RT / v
        factor = 0.4463 * n**1.5 * F**1.5 * A_eff * C
        if factor < 1e-30:
            return 1e-6
        return (ip / factor)**2 * R * T / v


def _solve_tridiag(a, b, c, d):
    """Thomas algorithm for tridiagonal systems."""
    n = len(d)
    cp = np.empty(n)
    dp = np.empty(n)
    x = np.empty(n)
    cp[0] = c[0] / max(abs(b[0]), 1e-30) * np.sign(b[0]) if b[0] != 0 else 0
    dp[0] = d[0] / max(abs(b[0]), 1e-30) * np.sign(b[0]) if b[0] != 0 else 0
    for i in range(1, n):
        denom = b[i] - a[i] * cp[i-1]
        if abs(denom) < 1e-30:
            denom = 1e-30
        cp[i] = c[i] / denom if i < n-1 else 0
        dp[i] = (d[i] - a[i] * dp[i-1]) / denom
    x[n-1] = dp[n-1]
    for i in range(n-2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i+1]
    return x


def simulate_cv(params: CVParameters, n_points: int = 2000) -> CVResult:
    """
    Simulate a cyclic voltammogram using the semianalytical
    convolution method (Nicholson-Shain theory).

    Uses the convolution integral relating surface flux to concentration:
        C_O(0,t) = C_O* - (1/sqrt(pi*D)) * integral[j(tau)/sqrt(t-tau) dtau]

    This is the same approach used by Gamry Echem Analyst. Numerically
    stable and accurate for all kinetic regimes.
    """
    p = params
    v = p.scan_rate_V_s
    A_eff = p.electrode_area_cm2 * p.roughness_factor

    E_wave, t_wave = _build_potential_waveform(p, n_points)
    dt = t_wave[1] - t_wave[0] if len(t_wave) > 1 else 1e-4
    n_total = len(E_wave)

    C_bulk_ox = p.C_ox_bulk_M * 1e-3  # mol/cm3
    C_bulk_red = p.C_red_bulk_M * 1e-3

    i_faradaic = np.zeros(n_total)
    i_capacitive = np.zeros(n_total)

    # Precompute convolution kernel: S[m] = 2*sqrt(dt/(pi*D)) * (sqrt(m+1) - sqrt(m))
    sqrt_vals = np.sqrt(np.arange(n_total + 1, dtype=np.float64))
    S_diff_ox = sqrt_vals[1:] - sqrt_vals[:-1]
    S_diff_red = S_diff_ox.copy()
    coeff_ox = 2.0 * np.sqrt(dt / (np.pi * p.D_ox_cm2_s))
    coeff_red = 2.0 * np.sqrt(dt / (np.pi * p.D_red_cm2_s))

    flux_history = np.zeros(n_total)

    for k in range(n_total):
        E = E_wave[k]
        eta = E - p.E_formal_V
        f_val = p.f

        arg_fwd = np.clip(-p.alpha * p.n_electrons * f_val * eta, -30, 30)
        arg_rev = np.clip((1 - p.alpha) * p.n_electrons * f_val * eta, -30, 30)
        kf = p.k0_cm_s * np.exp(arg_fwd)
        kb = p.k0_cm_s * np.exp(arg_rev)

        # Surface concentrations from convolution
        if k > 0:
            conv_ox = coeff_ox * np.dot(flux_history[:k], S_diff_ox[k-1::-1][:k])
            conv_red = coeff_red * np.dot(flux_history[:k], S_diff_red[k-1::-1][:k])
        else:
            conv_ox = 0.0
            conv_red = 0.0

        C_ox_surf = max(C_bulk_ox - conv_ox, 0.0)
        C_red_surf = max(C_bulk_red + conv_red, 0.0)

        # Implicit solve for flux:
        # j = kf*(C_ox_surf - j*S0_ox) - kb*(C_red_surf + j*S0_red)
        S0_ox = coeff_ox * S_diff_ox[0]
        S0_red = coeff_red * S_diff_red[0]
        denom = 1.0 + kf * S0_ox + kb * S0_red
        j_net = (kf * C_ox_surf - kb * C_red_surf) / max(denom, 1e-30)

        flux_history[k] = j_net
        i_faradaic[k] = p.n_electrons * F * A_eff * j_net

        # Capacitive current
        if k > 0:
            dE_dt = (E_wave[k] - E_wave[k-1]) / dt
        else:
            dE_dt = v
        i_capacitive[k] = p.Cdl_F_cm2 * A_eff * dE_dt

    i_total = i_faradaic + i_capacitive

    result = CVResult(
        E=E_wave,
        i_total=i_total,
        i_faradaic=i_faradaic,
        i_capacitive=i_capacitive,
        time=t_wave,
        params=params,
    )
    _analyze_peaks(result)
    return result


def _build_potential_waveform(
    params: CVParameters, n_per_segment: int
) -> Tuple[np.ndarray, np.ndarray]:
    """Build triangular potential waveform for CV."""
    segments = []

    for cycle in range(params.n_cycles):
        # Forward sweep: E_start → E_vertex1
        seg1 = np.linspace(params.E_start_V, params.E_vertex1_V, n_per_segment, endpoint=False)
        segments.append(seg1)

        # Reverse sweep: E_vertex1 → E_vertex2
        seg2 = np.linspace(params.E_vertex1_V, params.E_vertex2_V, n_per_segment, endpoint=False)
        segments.append(seg2)

        if params.E_vertex2_V != params.E_start_V:
            seg3 = np.linspace(params.E_vertex2_V, params.E_start_V, n_per_segment // 2, endpoint=True)
            segments.append(seg3)

    E = np.concatenate(segments)

    # Time from scan rate: dt = dE / v
    dt = abs(E[1] - E[0]) / params.scan_rate_V_s if len(E) > 1 else 1e-4
    t = np.arange(len(E)) * dt

    return E, t


def _analyze_peaks(result: CVResult):
    """Find anodic and cathodic peaks in the CV.

    Detects sweep direction from E_start vs E_vertex1 so the forward
    sweep is correctly identified regardless of scan direction.
    """
    E = result.E
    i = result.i_total
    n = len(E)
    p = result.params

    half = n // 2 if n > 10 else n

    # Determine if forward sweep is anodic (E_start < E_vertex1) or cathodic
    forward_is_anodic = p.E_start_V < p.E_vertex1_V

    i_fwd = i[:half]
    i_rev = i[half:]

    if forward_is_anodic:
        # Forward sweep → anodic peak (positive max)
        if len(i_fwd) > 0:
            idx_pa = np.argmax(i_fwd)
            result.i_pa = float(i_fwd[idx_pa])
            result.E_pa = float(E[idx_pa])
        # Reverse sweep → cathodic peak (negative min)
        if len(i_rev) > 0:
            idx_pc = np.argmin(i_rev)
            result.i_pc = float(i_rev[idx_pc])
            result.E_pc = float(E[half + idx_pc])
    else:
        # Forward sweep is cathodic (scanning negative first)
        if len(i_fwd) > 0:
            idx_pc = np.argmin(i_fwd)
            result.i_pc = float(i_fwd[idx_pc])
            result.E_pc = float(E[idx_pc])
        if len(i_rev) > 0:
            idx_pa = np.argmax(i_rev)
            result.i_pa = float(i_rev[idx_pa])
            result.E_pa = float(E[half + idx_pa])

    result.delta_Ep = abs(result.E_pa - result.E_pc)

    # Charge integration
    dt = result.time[1] - result.time[0] if len(result.time) > 1 else 1e-4
    # Use np.trapezoid (numpy 2.x) or np.trapz (numpy 1.x)
    _integrate = getattr(np, 'trapezoid', getattr(np, 'trapz', None))
    result.charge_anodic_C = float(_integrate(np.maximum(i, 0), result.time))
    result.charge_cathodic_C = float(abs(_integrate(np.minimum(i, 0), result.time)))


def randles_sevcik_ip(
    n: int, A_cm2: float, C_M: float, D_cm2_s: float, v_V_s: float, T_K: float = 298.15
) -> float:
    """
    Calculate theoretical peak current using Randles-Sevcik equation.

    i_p = 0.4463 × n^(3/2) × F^(3/2) × A × C × √(Dv/RT)

    Args:
        n: Number of electrons
        A_cm2: Electrode area (cm²)
        C_M: Bulk concentration (mol/L)
        D_cm2_s: Diffusion coefficient (cm²/s)
        v_V_s: Scan rate (V/s)
        T_K: Temperature (K)

    Returns:
        Peak current in Amperes
    """
    C = C_M * 1e-3  # mol/cm³
    return 0.4463 * n**1.5 * F**1.5 * A_cm2 * C * np.sqrt(D_cm2_s * v_V_s / (R * T_K))


def scan_rate_study(
    params: CVParameters,
    scan_rates: List[float] = None,
) -> Dict:
    """
    Run CV at multiple scan rates for diffusion analysis.

    Returns ip vs v^(1/2) data for Randles-Sevcik analysis.
    """
    if scan_rates is None:
        scan_rates = [0.005, 0.010, 0.020, 0.050, 0.100, 0.200, 0.500]

    results = []
    for v in scan_rates:
        p = CVParameters(**{
            k: getattr(params, k) for k in params.__dataclass_fields__
        })
        p.scan_rate_V_s = v
        cv = simulate_cv(p, n_points=1000)
        results.append({
            "scan_rate_V_s": v,
            "scan_rate_mV_s": v * 1e3,
            "sqrt_v": np.sqrt(v),
            "i_pa_A": cv.i_pa,
            "i_pc_A": cv.i_pc,
            "i_pa_mA": cv.i_pa * 1e3,
            "i_pc_mA": cv.i_pc * 1e3,
            "E_pa_V": cv.E_pa,
            "E_pc_V": cv.E_pc,
            "delta_Ep_mV": cv.delta_Ep * 1e3,
        })

    return {
        "scan_rates": scan_rates,
        "data": results,
        "analysis": {
            "sqrt_v": [r["sqrt_v"] for r in results],
            "i_pa_mA": [r["i_pa_mA"] for r in results],
            "i_pc_mA": [r["i_pc_mA"] for r in results],
        },
    }
