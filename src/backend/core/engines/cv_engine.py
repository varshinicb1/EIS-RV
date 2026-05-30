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
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

# ── pyMECSim integration ──────────────────────────────────────────
# pyMECSim wraps the MECSim Fortran engine for mechanism-based CV
# simulation (E, EC, ECE, catalytic, etc.).  The import is optional:
# when pymecsim is not installed the flag HAS_PYMECSIM is False and
# simulate_mecsim() falls back to the built-in Nicholson-Shain engine.
try:
    from pymecsim import (
        Specie as _MecSpecie,
        ChargeTransfer as _MecChargeTransfer,
        ChemicalReaction as _MecChemicalReaction,
        Mechanism as _MecMechanism,
        DCVoltammetry as _MecDCVoltammetry,
        Voltammetry as _MecVoltammetry,
        PlanarElectrode as _MecPlanarElectrode,
        Experiment as _MecExperiment,
        MECSIM as _MECSIM,
    )
    HAS_PYMECSIM = True
except ImportError:
    HAS_PYMECSIM = False

# Rust PyO3 acceleration (raman_core_rs) - prefer over pure Python fallback for CV
try:
    import raman_core_rs as _rust_cv  # type: ignore
    _HAS_RUST_CV = True
except ImportError:
    _HAS_RUST_CV = False

logger = logging.getLogger(__name__)

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
    C_red_bulk_M: float = 0.0          # Bulk reductant concentration (0 = only Ox in solution)
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
    areal_capacitance_F_cm2: Optional[float] = None
    volumetric_capacitance_F_cm3: Optional[float] = None

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
                "areal_capacitance_F_cm2": self.areal_capacitance_F_cm2,
                "volumetric_capacitance_F_cm3": self.volumetric_capacitance_F_cm3,
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


def simulate_mecsim(
    params: CVParameters,
    mechanism: str = "E",
    *,
    kf_chem: float = 1e4,
    kb_chem: float = 1e4,
    kf_chem2: float = 1e4,
    kb_chem2: float = 1e4,
    D_product_cm2_s: float = 7.6e-6,
    C_product_initial_M: float = 0.0,
    n_points: int = 2000,
) -> CVResult:
    """
    Simulate CV using the MECSim engine (pyMECSim).
    """
    if not HAS_PYMECSIM:
        raise ImportError("pyMECSim is not available.")
        
    p = params
    A_eff = p.electrode_area_cm2 * p.roughness_factor
    
    # Define species
    ox = _MecSpecie(name="Ox", D=p.D_ox_cm2_s, C=p.C_ox_bulk_M * 1e-3) # C in mol/cm3
    red = _MecSpecie(name="Red", D=p.D_red_cm2_s, C=p.C_red_bulk_M * 1e-3)
    
    species = [ox, red]
    reactions = []
    
    # E step
    e_step = _MecChargeTransfer(
        ox=ox.name, 
        red=red.name, 
        E0=p.E_formal_V, 
        k0=p.k0_cm_s, 
        alpha=p.alpha,
        n=p.n_electrons
    )
    reactions.append(e_step)
    
    if mechanism in ['EC', 'ECE']:
        prod = _MecSpecie(name="Prod", D=D_product_cm2_s, C=C_product_initial_M * 1e-3)
        species.append(prod)
        c_step = _MecChemicalReaction(
            reagents=[red.name],
            products=[prod.name],
            kf=kf_chem,
            kb=kb_chem
        )
        reactions.append(c_step)
        
    if mechanism == 'ECE':
        prod2 = _MecSpecie(name="Prod2", D=D_product_cm2_s, C=0.0)
        species.append(prod2)
        e_step2 = _MecChargeTransfer(
            ox=prod.name,
            red=prod2.name,
            E0=p.E_formal_V - 0.2, # Arbitrary shift for second E step
            k0=p.k0_cm_s,
            alpha=p.alpha,
            n=p.n_electrons
        )
        reactions.append(e_step2)

    mec = _MecMechanism(species=species, reactions=reactions)
    
    # Experiment parameters
    volt = _MecDCVoltammetry(
        E_start=p.E_start_V,
        E_rev=p.E_vertex1_V,
        v=p.scan_rate_V_s,
        T=p.temperature_K,
        cycles=p.n_cycles
    )
    
    electrode = _MecPlanarElectrode(area=A_eff, temp=p.temperature_K)
    
    exp = _MecExperiment(mechanism=mec, voltammetry=volt, electrode=electrode)
    
    # Create MECSIM runner
    runner = _MECSIM()
    
    try:
        # Run simulation
        result_df = runner.run(exp)
        E = result_df['E'].values
        i_faradaic = result_df['I'].values  # MECSim returns total faradaic current
        time = result_df['t'].values
    except Exception as e:
        logger.error(f"MECSim simulation failed: {e}")
        raise RuntimeError(f"MECSim execution failed: {e}")
        
    n_total = len(E)
    
    # Add capacitive current manually
    dE = np.diff(E, prepend=E[0])
    dt = np.diff(time, prepend=time[0])
    valid_dt = dt > 1e-6
    v_actual = np.zeros_like(E)
    v_actual[valid_dt] = dE[valid_dt] / dt[valid_dt]
    i_capacitive = p.Cdl_F_cm2 * A_eff * v_actual
    
    i_total = i_faradaic + i_capacitive
    
    return CVResult(
        E=E,
        i_total=i_total,
        i_faradaic=i_faradaic,
        i_capacitive=i_capacitive,
        time=time,
        params=p
    )


def simulate_cv(params: CVParameters, n_points: int = 2000, mechanism: str = 'E', use_mecsim: bool = False) -> CVResult:
    """
    Simulate a cyclic voltammogram.
    """
    if use_mecsim and HAS_PYMECSIM:
        logger.info(f"Using pyMECSim backend for {mechanism} mechanism")
        try:
            res = simulate_mecsim(params, mechanism=mechanism, n_points=n_points)
            _analyze_peaks(res)
            return res
        except Exception as e:
            logger.warning(f"pyMECSim failed: {e}. Falling back to analytical Nicholson-Shain solver.")
    
    # Prefer Rust PyO3 CV engine (replaces pure Python Nicholson-Shain fallback where possible)
    if _HAS_RUST_CV:
        try:
            p = _rust_cv.PyCVParams()
            p.area_cm2 = float(params.electrode_area_cm2)
            p.roughness = float(params.roughness_factor)
            p.E_formal_V = float(params.E_formal_V)
            p.n_electrons = int(params.n_electrons)
            p.C_ox_M = float(params.C_ox_bulk_M)
            p.C_red_M = float(params.C_red_bulk_M)
            p.D_ox_cm2s = float(params.D_ox_cm2_s)
            p.D_red_cm2s = float(params.D_red_cm2_s)
            p.k0_cm_s = float(params.k0_cm_s)
            p.alpha = float(params.alpha)
            p.Cdl_F_cm2 = float(params.Cdl_F_cm2)
            p.Rs_ohm = float(params.Rs_ohm)
            p.E_start_V = float(params.E_start_V)
            p.E_vertex_V = float(params.E_vertex1_V)
            p.E_end_V = float(getattr(params, 'E_vertex2_V', params.E_vertex1_V))
            p.scan_rate_V_s = float(params.scan_rate_V_s)
            p.n_cycles = int(params.n_cycles)
            p.temperature_K = float(params.temperature_K)
            rust_res = _rust_cv.simulate_cv_py(p, int(n_points))
            res = CVResult(
                E=np.asarray(rust_res.E),
                i_total=np.asarray(rust_res.i_total),
                i_faradaic=np.asarray(rust_res.i_faradaic),
                i_capacitive=np.asarray(rust_res.i_capacitive),
                time=np.asarray(rust_res.time),
                params=params,
                i_pa=float(rust_res.i_pa),
                i_pc=float(rust_res.i_pc),
                E_pa=float(rust_res.E_pa),
                E_pc=float(rust_res.E_pc),
                delta_Ep=float(rust_res.dEp),
            )
            logger.info("Using Rust (PyO3) CV solver")
            return res
        except Exception as e:
            logger.warning(f"Rust CV solver failed: {e}. Falling back to Python Nicholson-Shain.")

    # Fallback to standard Nicholson-Shain
    logger.info("Using analytical Nicholson-Shain solver")
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

    # Precompute convolution kernel coefficients
    coeff_ox = 2.0 * np.sqrt(dt / (np.pi * p.D_ox_cm2_s))
    coeff_red = 2.0 * np.sqrt(dt / (np.pi * p.D_red_cm2_s))

    flux_history = np.zeros(n_total)

    sqrt_vals = np.sqrt(np.arange(n_total + 1, dtype=np.float64))
    S_diff_ext = sqrt_vals[1:] - sqrt_vals[:-1]

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
            conv_ox = coeff_ox * np.dot(flux_history[:k], S_diff_ext[k-1::-1][:k])
            conv_red = coeff_red * np.dot(flux_history[:k], S_diff_ext[k-1::-1][:k])
        else:
            conv_ox = 0.0
            conv_red = 0.0

        C_ox_surf = max(C_bulk_ox - conv_ox, 0.0)
        C_red_surf = max(C_bulk_red + conv_red, 0.0)

        # Implicit solve for flux
        S0_ox = coeff_ox * S_diff_ext[0]
        S0_red = coeff_red * S_diff_ext[0]
        denom = 1.0 + kf * S0_ox + kb * S0_red
        j_net = (kf * C_ox_surf - kb * C_red_surf) / max(denom, 1e-30)

        flux_history[k] = j_net
        i_faradaic[k] = p.n_electrons * F * A_eff * j_net

        # Capacitive current: i_cap = Cdl * A * dE/dt
        if k > 0:
            dE_dt = (E_wave[k] - E_wave[k-1]) / dt
        else:
            dE_dt = v if p.E_start_V < p.E_vertex1_V else -v
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
    """Build triangular potential waveform for CV.

    Each segment uses the same number of points so that dt is uniform
    across the entire waveform. A uniform dt is required for the
    convolution kernel in simulate_cv to be correct.
    """
    segments = []

    for cycle in range(params.n_cycles):
        # Forward sweep: E_start → E_vertex1
        seg1 = np.linspace(params.E_start_V, params.E_vertex1_V, n_per_segment, endpoint=False)
        segments.append(seg1)

        # Reverse sweep: E_vertex1 → E_vertex2
        seg2 = np.linspace(params.E_vertex1_V, params.E_vertex2_V, n_per_segment, endpoint=False)
        segments.append(seg2)

        # Return sweep (only when vertex2 ≠ start, e.g. staircase or offset CV)
        if not np.isclose(params.E_vertex2_V, params.E_start_V):
            # Use the same n_per_segment to keep dt uniform
            seg3 = np.linspace(params.E_vertex2_V, params.E_start_V, n_per_segment, endpoint=True)
            segments.append(seg3)

    E = np.concatenate(segments)

    # Time from scan rate: dt = |dE| / v  (uniform because all segments have same step)
    dt = abs(E[1] - E[0]) / params.scan_rate_V_s if len(E) > 1 else 1e-4
    t = np.arange(len(E)) * dt

    return E, t


def _analyze_peaks(result: CVResult):
    """Find anodic and cathodic peaks in the CV.

    Detects peak signs from the actual current data rather than assuming
    the sweep direction determines which half is anodic/cathodic.
    Skips the first 10% of each half to avoid the startup transient.
    """
    from scipy.signal import find_peaks as _find_peaks

    E = result.E
    i = result.i_total
    n = len(E)
    p = result.params

    half = n // 2 if n > 10 else n
    skip = max(1, half // 10)

    i_fwd = i[skip:half]
    i_rev = i[half + skip:]
    E_fwd = E[skip:half]
    E_rev = E[half + skip:]

    min_dist = max(5, len(i_fwd) // 20) if len(i_fwd) > 0 else 5

    # Detect which half contains the anodic peak (positive max) and which
    # contains the cathodic peak (negative min) from the actual data.
    max_fwd = float(i_fwd.max()) if len(i_fwd) > 0 else 0.0
    min_fwd = float(i_fwd.min()) if len(i_fwd) > 0 else 0.0
    max_rev = float(i_rev.max()) if len(i_rev) > 0 else 0.0
    min_rev = float(i_rev.min()) if len(i_rev) > 0 else 0.0

    # Anodic peak is in whichever half has the larger positive maximum
    fwd_is_anodic = max_fwd >= max_rev

    if fwd_is_anodic:
        # Forward sweep → anodic peak
        if len(i_fwd) > 0:
            peaks_fwd, _ = _find_peaks(i_fwd, distance=min_dist)
            if len(peaks_fwd) > 0:
                best = peaks_fwd[np.argmax(i_fwd[peaks_fwd])]
            else:
                best = int(np.argmax(i_fwd))
            result.i_pa = float(i_fwd[best])
            result.E_pa = float(E_fwd[best])

        # Reverse sweep → cathodic peak
        if len(i_rev) > 0:
            peaks_rev, _ = _find_peaks(-i_rev, distance=min_dist)
            if len(peaks_rev) > 0:
                best = peaks_rev[np.argmin(i_rev[peaks_rev])]
            else:
                best = int(np.argmin(i_rev))
            result.i_pc = float(i_rev[best])
            result.E_pc = float(E_rev[best])
    else:
        # Reverse sweep → anodic peak
        if len(i_rev) > 0:
            peaks_rev, _ = _find_peaks(i_rev, distance=min_dist)
            if len(peaks_rev) > 0:
                best = peaks_rev[np.argmax(i_rev[peaks_rev])]
            else:
                best = int(np.argmax(i_rev))
            result.i_pa = float(i_rev[best])
            result.E_pa = float(E_rev[best])

        # Forward sweep → cathodic peak
        if len(i_fwd) > 0:
            peaks_fwd, _ = _find_peaks(-i_fwd, distance=min_dist)
            if len(peaks_fwd) > 0:
                best = peaks_fwd[np.argmin(i_fwd[peaks_fwd])]
            else:
                best = int(np.argmin(i_fwd))
            result.i_pc = float(i_fwd[best])
            result.E_pc = float(E_fwd[best])

    result.delta_Ep = abs(result.E_pa - result.E_pc)

    # Charge integration
    dt = result.time[1] - result.time[0] if len(result.time) > 1 else 1e-4
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


# ═══════════════════════════════════════════════════════════════════
#   pyMECSim INTEGRATION — mechanism-based CV via MECSim engine
# ═══════════════════════════════════════════════════════════════════

def simulate_mecsim(
    params: CVParameters,
    mechanism: str = "E",
    *,
    kf_chem: float = 1e4,
    kb_chem: float = 1e4,
    kf_chem2: float = 1e4,
    kb_chem2: float = 1e4,
    D_product_cm2_s: float = 7.6e-6,
    C_product_initial_M: float = 0.0,
    n_points: int = 2000,
) -> CVResult:
    """Simulate a cyclic voltammogram using the MECSim Fortran engine
    via pyMECSim, supporting multi-step reaction mechanisms.

    Supported mechanism codes
    -------------------------
    - ``'E'``   — Simple electron transfer:  Ox + e ⇌ Red
    - ``'EC'``  — Electron transfer + following chemical step:
                  Ox + e ⇌ Red ;  Red → Product   (kf_chem / kb_chem)
    - ``'ECE'`` — Two electron transfers with an intervening chemical
                  step:  Ox + e ⇌ Red ;  Red → Int  (kf_chem / kb_chem) ;
                  Int + e ⇌ Product  (uses same k0, alpha, E_formal)

    Parameters
    ----------
    params : CVParameters
        Standard CV parameter object (electrode area, kinetics, scan,
        temperature, etc.).
    mechanism : str
        One of ``'E'``, ``'EC'``, ``'ECE'`` (case-insensitive).
    kf_chem : float
        Forward rate constant for the first chemical step (s⁻¹).
        Only used for ``'EC'`` and ``'ECE'`` mechanisms.
    kb_chem : float
        Backward rate constant for the first chemical step (s⁻¹).
    kf_chem2 : float
        Forward rate constant for the second chemical step (``'ECE'``
        only).
    kb_chem2 : float
        Backward rate constant for the second chemical step (``'ECE'``
        only).
    D_product_cm2_s : float
        Diffusion coefficient for the product / intermediate species
        (cm²/s).
    C_product_initial_M : float
        Initial concentration of the product / intermediate species
        (mol/L).  Defaults to 0 (product absent at start).
    n_points : int
        Number of points per segment in the CV waveform.

    Returns
    -------
    CVResult
        The same result type returned by :func:`simulate_cv`, so
        downstream code does not need to know which backend was used.

    Fallback
    --------
    If ``pymecsim`` is not installed, or the MECSim binary cannot be
    found at runtime, the function logs a warning and delegates to
    :func:`simulate_cv` (pure-Python Nicholson-Shain engine), which
    only supports simple ``'E'`` kinetics.

    Raises
    ------
    ValueError
        If *mechanism* is not one of the recognised codes.

    Examples
    --------
    >>> result = simulate_mecsim(CVParameters(), mechanism='EC',
    ...                          kf_chem=1e3, kb_chem=0.0)
    >>> result.E_pa  # anodic peak potential
    """
    mechanism = mechanism.upper().strip()
    if mechanism not in ("E", "EC", "ECE"):
        raise ValueError(
            f"Unsupported mechanism '{mechanism}'. Choose from 'E', 'EC', 'ECE'."
        )

    # ── Fallback path ─────────────────────────────────────────────
    if not HAS_PYMECSIM:
        logger.warning(
            "pyMECSim not installed — falling back to built-in "
            "Nicholson-Shain CV engine (mechanism='E' only)."
        )
        return simulate_cv(params, n_points=n_points)

    # ── Build pyMECSim objects ────────────────────────────────────
    try:
        logger.info(
            "simulate_mecsim: using pyMECSim backend, mechanism=%s", mechanism
        )

        # --- Species ---
        # Convert bulk concentrations from mol/L to mol/cm³ (MECSim units)
        C_ox = params.C_ox_bulk_M * 1e-3
        C_red = params.C_red_bulk_M * 1e-3
        C_prod = C_product_initial_M * 1e-3

        Ox = _MecSpecie("Ox", D=params.D_ox_cm2_s, C0=C_ox)
        Red = _MecSpecie("Red", D=params.D_red_cm2_s, C0=C_red)

        reactions = []

        # --- E step: Ox + e ⇌ Red ---
        R1 = _MecChargeTransfer(
            reactants=[(Ox, 1), ("e", params.n_electrons)],
            products=[(Red, 1)],
            E0=params.E_formal_V,
            ks=params.k0_cm_s,
            alpha=params.alpha,
        )
        reactions.append(R1)

        if mechanism in ("EC", "ECE"):
            # Additional intermediate / product species
            Int = _MecSpecie("Int", D=D_product_cm2_s, C0=C_prod)

            # --- C step: Red → Int ---
            R2 = _MecChemicalReaction(
                reactants=[(Red, 1)],
                products=[(Int, 1)],
                kf=kf_chem,
                kb=kb_chem,
            )
            reactions.append(R2)

        if mechanism == "ECE":
            Prod2 = _MecSpecie("Prod2", D=D_product_cm2_s, C0=0.0)

            # --- Second E step: Int + e ⇌ Prod2 ---
            R3 = _MecChargeTransfer(
                reactants=[(Int, 1), ("e", params.n_electrons)],
                products=[(Prod2, 1)],
                E0=params.E_formal_V,
                ks=params.k0_cm_s,
                alpha=params.alpha,
            )
            reactions.append(R3)

        # --- Mechanism, Voltammetry, Electrode ---
        mech = _MecMechanism(reactions)

        cv_load = _MecDCVoltammetry(
            E_start=params.E_start_V,
            E_rev=params.E_vertex1_V,
            N=params.n_cycles,
            nu=params.scan_rate_V_s,
            T=params.temperature_K,
            Rh=params.Rs_ohm,
        )
        volt = _MecVoltammetry(objs=[cv_load])

        electrode = _MecPlanarElectrode(
            area=params.electrode_area_cm2 * params.roughness_factor
        )

        exp = _MecExperiment(mech, electrode=electrode, voltammetry=volt)

        # --- Run ---
        sim = _MECSIM(exp=exp)
        T_arr, V_arr, I_arr = sim.solve()

        # pyMECSim returns numpy arrays of time (ms), voltage (V),
        # and current (A).  Convert time from ms → s.
        time_s = T_arr * 1e-3

        # Build a CVResult that matches the contract of simulate_cv()
        # (i_capacitive is not modelled by MECSim, set to zero).
        i_cap = np.zeros_like(I_arr)

        result = CVResult(
            E=V_arr,
            i_total=I_arr,
            i_faradaic=I_arr,       # MECSim current is purely faradaic
            i_capacitive=i_cap,
            time=time_s,
            params=params,
        )
        _analyze_peaks(result)

        logger.info(
            "simulate_mecsim: completed — i_pa=%.3e A, i_pc=%.3e A, "
            "ΔEp=%.1f mV",
            result.i_pa, result.i_pc, result.delta_Ep * 1e3,
        )
        return result

    except Exception as exc:
        # Any runtime failure (missing binary, divergence, etc.)
        # falls back to the pure-Python engine.
        logger.warning(
            "pyMECSim simulation failed (%s); falling back to built-in "
            "Nicholson-Shain engine.",
            exc,
        )
        return simulate_cv(params, n_points=n_points)

