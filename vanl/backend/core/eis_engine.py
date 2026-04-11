"""
Virtual EIS (Electrochemical Impedance Spectroscopy) Engine
=============================================================
Physics-based impedance simulation using equivalent circuit models.

The core model is the **modified Randles circuit**:

    Z(ω) = Rs + 1 / (Y_CPE(jω) + 1/(Rct + Z_W(ω)))

Where:
    - Rs  = solution/ohmic resistance
    - Rct = charge transfer resistance (Faradaic)
    - Y_CPE = CPE admittance = Q₀(jω)^n  (generalizes ideal Cdl)
    - Z_W  = Warburg impedance = σ(1-j)/√ω  (semi-infinite diffusion)

For finite-length diffusion (bounded Warburg):
    Z_W = σ √(2/(jωτ_d)) × tanh(√(jωτ_d))
    where τ_d = L²/D (diffusion time constant)

Physical constants & conventions:
    - ω = 2πf  (angular frequency, rad/s)
    - f: frequency in Hz (typically 0.01 Hz to 1 MHz)
    - Impedance Z = Z' + jZ'' (Z' = real, Z'' = imaginary)
    - Nyquist plot: Z' vs -Z'' (convention: -Z'' on y-axis)
    - Bode plot: |Z| and phase vs log(f)
"""

import numpy as np
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass
from .materials import EISParameters, StructuralDescriptors


# ---------------------------------------------------------------------------
#   Equivalent Circuit Impedance Calculations
# ---------------------------------------------------------------------------

def randles_impedance(
    freq: np.ndarray,
    Rs: float,
    Rct: float,
    Cdl: float,
    sigma_w: float,
    n_cpe: float = 1.0,
    use_bounded_warburg: bool = False,
    diffusion_length_um: float = 100.0,
    diffusion_coeff_cm2_s: float = 1e-6,
) -> np.ndarray:
    """
    Calculate impedance of a modified Randles circuit.

    Z(ω) = Rs + Z_parallel

    where Z_parallel = 1 / (Y_CPE + 1/Z_faradaic)
    Y_CPE = Cdl × (jω)^n       [CPE admittance]
    Z_faradaic = Rct + Z_warburg

    Args:
        freq: Frequency array (Hz)
        Rs: Solution resistance (Ω)
        Rct: Charge transfer resistance (Ω)
        Cdl: Double layer capacitance (F) or CPE parameter Q₀
        sigma_w: Warburg coefficient (Ω·s^(-1/2))
        n_cpe: CPE exponent (1.0 = ideal capacitor, <1 = distributed)
        use_bounded_warburg: If True, use finite-length Warburg
        diffusion_length_um: Diffusion layer thickness (µm)
        diffusion_coeff_cm2_s: Diffusion coefficient (cm²/s)

    Returns:
        Z: Complex impedance array (Z' + jZ'')
    """
    omega = 2.0 * np.pi * freq  # Angular frequency

    # CPE admittance: Y_CPE = Q₀(jω)^n
    # For n=1, this reduces to Y = jωC (ideal capacitor)
    Y_cpe = Cdl * (1j * omega) ** n_cpe

    # Warburg impedance
    if use_bounded_warburg:
        Z_w = _bounded_warburg(omega, sigma_w, diffusion_length_um,
                                diffusion_coeff_cm2_s)
    else:
        Z_w = _semi_infinite_warburg(omega, sigma_w)

    # Faradaic impedance
    Z_faradaic = Rct + Z_w

    # Parallel combination: Z_p = 1 / (Y_CPE + 1/Z_faradaic)
    Z_parallel = 1.0 / (Y_cpe + 1.0 / Z_faradaic)

    # Total: Z = Rs + Z_parallel
    Z_total = Rs + Z_parallel

    return Z_total


def _semi_infinite_warburg(omega: np.ndarray, sigma_w: float) -> np.ndarray:
    """
    Semi-infinite Warburg impedance.

    Z_W = σ_w × (1 - j) / √ω

    Physical basis: diffusion of redox species from bulk solution
    to electrode surface. Valid when diffusion layer thickness >> √(2D/ω).
    """
    if sigma_w < 1e-6:
        return np.zeros_like(omega, dtype=complex)

    sqrt_omega = np.sqrt(np.maximum(omega, 1e-12))
    return sigma_w * (1.0 - 1j) / sqrt_omega


def _bounded_warburg(
    omega: np.ndarray,
    sigma_w: float,
    L_um: float,
    D_cm2_s: float,
) -> np.ndarray:
    """
    Bounded (finite-length) Warburg impedance.

    Z_W = (σ_w / √(jωτ_d)) × tanh(√(jωτ_d))

    where τ_d = L²/D is the diffusion time constant.

    This accounts for finite diffusion layer thickness, e.g., in
    thin-layer cells or porous electrodes.
    """
    if sigma_w < 1e-6:
        return np.zeros_like(omega, dtype=complex)

    L_cm = L_um * 1e-4
    tau_d = L_cm ** 2 / max(D_cm2_s, 1e-12)

    x = np.sqrt(1j * omega * tau_d)

    # Numerically stable tanh for large arguments
    tanh_x = np.tanh(x)

    Z_w = sigma_w * tanh_x / (x + 1e-30)
    return Z_w


# ---------------------------------------------------------------------------
#   EIS Data Generation
# ---------------------------------------------------------------------------

@dataclass
class EISResult:
    """Complete EIS simulation result."""
    frequencies: np.ndarray        # Hz
    Z_real: np.ndarray             # Ω (real part)
    Z_imag: np.ndarray             # Ω (imaginary part)
    Z_magnitude: np.ndarray        # |Z| in Ω
    Z_phase: np.ndarray            # Phase in degrees
    params: EISParameters

    def nyquist_data(self) -> Tuple[list, list]:
        """Return (Z_real, -Z_imag) for Nyquist plot."""
        return self.Z_real.tolist(), (-self.Z_imag).tolist()

    def bode_magnitude_data(self) -> Tuple[list, list]:
        """Return (log10(f), log10|Z|) for Bode magnitude plot."""
        return np.log10(self.frequencies).tolist(), np.log10(self.Z_magnitude).tolist()

    def bode_phase_data(self) -> Tuple[list, list]:
        """Return (log10(f), phase°) for Bode phase plot."""
        return np.log10(self.frequencies).tolist(), self.Z_phase.tolist()

    def to_dict(self) -> dict:
        return {
            "frequencies": self.frequencies.tolist(),
            "Z_real": self.Z_real.tolist(),
            "Z_imag": self.Z_imag.tolist(),
            "Z_magnitude": self.Z_magnitude.tolist(),
            "Z_phase": self.Z_phase.tolist(),
            "nyquist": {"x": self.Z_real.tolist(), "y": (-self.Z_imag).tolist()},
            "bode_mag": {
                "x": np.log10(self.frequencies).tolist(),
                "y": np.log10(self.Z_magnitude).tolist()
            },
            "bode_phase": {
                "x": np.log10(self.frequencies).tolist(),
                "y": self.Z_phase.tolist()
            },
            "params": self.params.to_dict(),
        }


def simulate_eis(
    params: EISParameters,
    freq_range: Tuple[float, float] = (0.01, 1e6),
    n_points: int = 100,
    use_bounded_warburg: bool = False,
) -> EISResult:
    """
    Generate complete EIS data from circuit parameters.

    Args:
        params: EIS circuit parameters (Rs, Rct, Cdl, σ_w, n_CPE)
        freq_range: (f_min, f_max) in Hz
        n_points: Number of frequency points (log-spaced)
        use_bounded_warburg: Use finite-length Warburg model

    Returns:
        EISResult with frequencies, impedance data, and plot-ready arrays
    """
    # Log-spaced frequency array
    frequencies = np.logspace(
        np.log10(freq_range[0]),
        np.log10(freq_range[1]),
        n_points
    )

    # Compute complex impedance
    Z = randles_impedance(
        frequencies,
        Rs=params.Rs,
        Rct=params.Rct,
        Cdl=params.Cdl,
        sigma_w=params.sigma_warburg,
        n_cpe=params.n_cpe,
        use_bounded_warburg=use_bounded_warburg,
    )

    Z_real = np.real(Z)
    Z_imag = np.imag(Z)
    Z_mag = np.abs(Z)
    Z_phase = np.degrees(np.arctan2(Z_imag, Z_real))

    return EISResult(
        frequencies=frequencies,
        Z_real=Z_real,
        Z_imag=Z_imag,
        Z_magnitude=Z_mag,
        Z_phase=Z_phase,
        params=params,
    )


# ---------------------------------------------------------------------------
#   Physics-Informed EIS Parameter Estimation
# ---------------------------------------------------------------------------

def descriptors_to_eis(
    descriptors: StructuralDescriptors,
    electrode_area_cm2: float = 0.07,  # 3mm diameter well
    electrolyte_conductivity_S_m: float = 1.0,  # e.g., 0.1M KCl
    cell_constant: float = 1.0,
) -> EISParameters:
    """
    Estimate EIS parameters from structural descriptors using
    physics-informed relationships.

    This is NOT a black-box model — each parameter has a clear
    physical derivation:

    Rs ∝ 1/σ_electrolyte + 1/σ_electrode
    Rct ∝ exp(ΔG‡/kT) / (n·F·j₀·A)   [Butler-Volmer]
    Cdl ∝ ε·ε₀·A / d                   [Helmholtz model]
    σ_w ∝ 1 / (n²F²A√D·C)             [Warburg coefficient]

    Where A is the electrochemically active surface area,
    which depends on geometric area × roughness factor.
    """
    # ── Rs (Solution Resistance) ──
    # Rs = cell_constant / κ_solution + R_electrode
    # Electrode resistance depends on film conductivity and thickness
    R_solution = cell_constant / max(electrolyte_conductivity_S_m, 0.01)
    film_thickness_m = descriptors.layer_thickness_nm * 1e-9
    R_electrode = film_thickness_m / (
        max(descriptors.conductivity_S_m, 0.01) * electrode_area_cm2 * 1e-4
    )
    Rs = R_solution + R_electrode
    Rs = np.clip(Rs, 0.5, 500)

    # ── Roughness factor ──
    # Real surface area / geometric area
    # Higher porosity and surface area → larger roughness factor
    roughness = 1.0 + (descriptors.surface_area_m2_g / 100.0) * (
        0.5 + 0.5 * descriptors.porosity
    )
    effective_area_cm2 = electrode_area_cm2 * roughness

    # ── Rct (Charge Transfer Resistance) ──
    # Rct = RT / (nF × j₀ × A_eff)
    # j₀ (exchange current density) increases with:
    #   - active site density (∝ defect_density × surface_area)
    #   - crystallinity (better electron pathways)
    #   - conductivity (faster electron supply)
    RT_nF = 0.0257  # RT/F at 25°C for n=1 (volts)

    # Exchange current density proxy (A/cm²)
    j0 = 1e-4 * (
        (1.0 + 5.0 * descriptors.defect_density) *  # Active sites
        (0.3 + 0.7 * descriptors.crystallinity) *     # Electron pathway quality
        np.log10(max(descriptors.conductivity_S_m, 1) + 1) / 7.0  # Conductivity boost
    )
    j0 = np.clip(j0, 1e-8, 1e-1)

    Rct = RT_nF / (j0 * effective_area_cm2)
    Rct = np.clip(Rct, 0.1, 100000)

    # ── Cdl (Double-Layer Capacitance) ──
    # Cdl = ε × ε₀ × A_eff / d_Helmholtz
    # Typical EDLC: 10-40 µF/cm² for flat surfaces
    # Pseudocapacitive: can be much higher
    Cdl_per_cm2 = 20e-6  # F/cm² (base value for carbon)
    Cdl = Cdl_per_cm2 * effective_area_cm2
    Cdl = np.clip(Cdl, 1e-9, 1e-1)

    # ── Warburg coefficient ──
    # σ_w = RT / (n²F²A√(2D)C)
    # Higher porosity → more tortuous diffusion paths → higher σ_w
    # Higher crystallinity → more ordered structure → lower σ_w
    D_eff = 1e-6 * (1 - 0.5 * descriptors.porosity) * (
        0.5 + 0.5 * descriptors.crystallinity
    )  # cm²/s
    D_eff = max(D_eff, 1e-10)

    C_bulk = 5e-6  # mol/cm³ (5 mM redox species)
    F = 96485  # C/mol

    sigma_w = RT_nF / (F * effective_area_cm2 * np.sqrt(2 * D_eff) * C_bulk)
    sigma_w = np.clip(sigma_w, 0.1, 5000)

    # ── CPE exponent ──
    # n = 1 for ideally smooth surfaces
    # Decreases with surface roughness/heterogeneity
    n_cpe = 0.95 - 0.15 * descriptors.porosity - 0.1 * descriptors.defect_density
    n_cpe = np.clip(n_cpe, 0.5, 1.0)

    return EISParameters(
        Rs=float(Rs),
        Rct=float(Rct),
        Cdl=float(Cdl),
        sigma_warburg=float(sigma_w),
        n_cpe=float(n_cpe),
    )


# ---------------------------------------------------------------------------
#   Quick Simulation Helper
# ---------------------------------------------------------------------------

def quick_simulate(
    Rs: float = 10.0,
    Rct: float = 100.0,
    Cdl: float = 1e-5,
    sigma_w: float = 50.0,
    n_cpe: float = 0.9,
) -> dict:
    """
    One-call EIS simulation. Returns plot-ready data.

    Example:
        data = quick_simulate(Rs=5, Rct=200, Cdl=2e-5)
        # data["nyquist"]["x"], data["nyquist"]["y"]
    """
    params = EISParameters(Rs=Rs, Rct=Rct, Cdl=Cdl,
                            sigma_warburg=sigma_w, n_cpe=n_cpe)
    result = simulate_eis(params)
    return result.to_dict()
