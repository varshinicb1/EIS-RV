"""
RĀMAN Studio — Unit Conversion Toolkit
========================================
Comprehensive electrochemistry unit conversions for researchers.

Covers all common conversions that PhD students and engineers need daily:
- Capacitance (F, µF, mF, F/g, F/cm²)
- Current (A, mA, µA, mA/cm²)
- Resistance (Ω, kΩ, MΩ, Ω·cm²)
- Potential (V, mV)
- Frequency (Hz, kHz, MHz, rad/s)
- Concentration (M, mM, µM, nM)
- Diffusion coefficient (cm²/s, m²/s)
- Energy/Power density (Wh/kg, Wh/L, W/kg, W/L)
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Conversion Tables ─────────────────────────────────────────────

CONVERSIONS = {
    # Capacitance
    "capacitance": {
        "F":    1.0,
        "mF":   1e-3,
        "µF":   1e-6,
        "nF":   1e-9,
        "pF":   1e-12,
    },
    # Specific capacitance (requires mass parameter)
    "specific_capacitance": {
        "F/g":   1.0,
        "mF/g":  1e-3,
        "F/kg":  1e-3,
    },
    # Areal capacitance (requires area parameter)
    "areal_capacitance": {
        "F/cm²":  1.0,
        "µF/cm²": 1e-6,
        "mF/cm²": 1e-3,
    },
    # Current
    "current": {
        "A":   1.0,
        "mA":  1e-3,
        "µA":  1e-6,
        "nA":  1e-9,
    },
    # Current density
    "current_density": {
        "A/cm²":   1.0,
        "mA/cm²":  1e-3,
        "µA/cm²":  1e-6,
        "A/m²":    1e-4,
    },
    # Resistance
    "resistance": {
        "Ω":   1.0,
        "mΩ":  1e-3,
        "kΩ":  1e3,
        "MΩ":  1e6,
    },
    # Area-specific resistance
    "asr": {
        "Ω·cm²":  1.0,
        "mΩ·cm²": 1e-3,
        "kΩ·cm²": 1e3,
    },
    # Potential
    "potential": {
        "V":   1.0,
        "mV":  1e-3,
        "µV":  1e-6,
    },
    # Frequency
    "frequency": {
        "Hz":    1.0,
        "kHz":   1e3,
        "MHz":   1e6,
        "rad/s": 0.15915494309189535,  # 1/(2π)
    },
    # Concentration
    "concentration": {
        "M":   1.0,
        "mM":  1e-3,
        "µM":  1e-6,
        "nM":  1e-9,
        "pM":  1e-12,
    },
    # Diffusion coefficient
    "diffusion": {
        "cm²/s": 1.0,
        "m²/s":  1e4,
    },
    # Energy density
    "energy_density": {
        "Wh/kg":  1.0,
        "mWh/g":  1.0,
        "kWh/kg": 1e3,
        "J/g":    1 / 3.6,
        "kJ/kg":  1 / 3.6,
    },
    # Power density
    "power_density": {
        "W/kg":  1.0,
        "mW/g":  1.0,
        "kW/kg": 1e3,
    },
}


def convert_unit(value: float, from_unit: str, to_unit: str,
                 category: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert a value between electrochemistry units.

    If category is not provided, auto-detects from the unit strings.
    Returns dict with converted value and metadata.
    """
    # Auto-detect category
    if not category:
        for cat_name, cat_units in CONVERSIONS.items():
            if from_unit in cat_units and to_unit in cat_units:
                category = cat_name
                break

    if not category:
        return {"error": f"Cannot find matching category for '{from_unit}' → '{to_unit}'"}

    cat = CONVERSIONS.get(category)
    if not cat:
        return {"error": f"Unknown category: {category}"}

    from_factor = cat.get(from_unit)
    to_factor = cat.get(to_unit)

    if from_factor is None:
        return {"error": f"Unknown unit '{from_unit}' in category '{category}'"}
    if to_factor is None:
        return {"error": f"Unknown unit '{to_unit}' in category '{category}'"}

    # Convert: value_in_base = value * from_factor, then divide by to_factor
    base_value = value * from_factor
    result = base_value / to_factor

    return {
        "value": result,
        "from_unit": from_unit,
        "to_unit": to_unit,
        "category": category,
        "formula": f"{value} {from_unit} × ({from_factor}/{to_factor}) = {result} {to_unit}",
    }


def list_categories() -> Dict[str, list]:
    """Return all supported categories and their units."""
    return {cat: list(units.keys()) for cat, units in CONVERSIONS.items()}


# ── Common Electrochemistry Calculations ──────────────────────────

def randles_sevcik(n: int, A_cm2: float, D_cm2s: float, C_M: float,
                   v_Vs: float) -> Dict[str, float]:
    """
    Randles-Ševčík equation for peak current in CV.

    ip = 0.4463 × n^(3/2) × F^(3/2) × A × D^(1/2) × C × v^(1/2) / (R×T)^(1/2)

    Simplified at 25°C:
    ip = (2.69e5) × n^(3/2) × A × D^(1/2) × C × v^(1/2)
    """
    import math
    ip = 2.69e5 * (n ** 1.5) * A_cm2 * math.sqrt(D_cm2s) * C_M * math.sqrt(v_Vs)
    return {
        "ip_A": ip,
        "ip_mA": ip * 1e3,
        "ip_µA": ip * 1e6,
        "n_electrons": n,
        "area_cm2": A_cm2,
        "D_cm2s": D_cm2s,
        "C_M": C_M,
        "scan_rate_Vs": v_Vs,
        "equation": "Randles-Ševčík (25°C)",
    }


def cottrell(n: int, A_cm2: float, D_cm2s: float, C_M: float,
             t_s: float) -> Dict[str, float]:
    """
    Cottrell equation for chronoamperometry.

    i(t) = n × F × A × D^(1/2) × C / (π × t)^(1/2)
    """
    import math
    F = 96485.3329
    i = n * F * A_cm2 * math.sqrt(D_cm2s) * C_M / math.sqrt(math.pi * t_s)
    return {
        "i_A": i,
        "i_mA": i * 1e3,
        "i_µA": i * 1e6,
        "time_s": t_s,
        "equation": "Cottrell",
    }


def nernst(E0_V: float, n: int, C_ox_M: float, C_red_M: float,
           T_K: float = 298.15) -> Dict[str, float]:
    """
    Nernst equation for equilibrium potential.

    E = E0 + (RT/nF) × ln(C_ox / C_red)
    """
    import math
    R = 8.314462
    F = 96485.3329
    if C_red_M <= 0 or C_ox_M <= 0:
        return {"error": "Concentrations must be positive"}
    E = E0_V + (R * T_K / (n * F)) * math.log(C_ox_M / C_red_M)
    return {
        "E_V": round(E, 6),
        "E_mV": round(E * 1000, 3),
        "E0_V": E0_V,
        "RT_nF_mV": round(R * T_K / (n * F) * 1000, 2),
        "equation": "Nernst",
    }
