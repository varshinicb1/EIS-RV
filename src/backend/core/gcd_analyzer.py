"""
GCD (Galvanostatic Charge-Discharge) Analyzer
===============================================
Extracts supercapacitor performance metrics from GCD data:
  - Specific Capacitance (F/g)
  - Energy Density (Wh/kg)
  - Power Density (W/kg)
  - Coulombic Efficiency (%)
  - IR Drop (V)

Supports CHI instrument .xlsx exports and generic CSV/TXT.

Author: VidyuthLabs
Date: May 8, 2026
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GCDResult:
    """Result of a GCD analysis."""
    specific_capacitance_Fg: float = 0.0
    energy_density_Whkg: float = 0.0
    power_density_Wkg: float = 0.0
    coulombic_efficiency_pct: float = 0.0
    ir_drop_V: float = 0.0
    discharge_time_s: float = 0.0
    charge_time_s: float = 0.0
    potential_window_V: float = 0.0
    current_density_Ag: float = 0.0
    num_cycles: int = 0
    cycle_data: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "specific_capacitance_Fg": round(self.specific_capacitance_Fg, 2),
            "energy_density_Whkg": round(self.energy_density_Whkg, 4),
            "power_density_Wkg": round(self.power_density_Wkg, 2),
            "coulombic_efficiency_pct": round(self.coulombic_efficiency_pct, 2),
            "ir_drop_V": round(self.ir_drop_V, 4),
            "discharge_time_s": round(self.discharge_time_s, 4),
            "charge_time_s": round(self.charge_time_s, 4),
            "potential_window_V": round(self.potential_window_V, 4),
            "current_density_Ag": round(self.current_density_Ag, 6),
            "num_cycles": self.num_cycles,
        }


class GCDAnalyzer:
    """
    Analyzer for Galvanostatic Charge-Discharge curves.
    
    Extracts supercapacitor metrics from time-potential data
    recorded at a known constant current.
    """

    def analyze(
        self,
        time: np.ndarray,
        potential: np.ndarray,
        current_A: float = 1e-3,
        mass_g: float = 1e-3,
        area_cm2: float = 0.0707,
    ) -> GCDResult:
        """
        Analyze GCD data.

        Args:
            time: Time array in seconds
            potential: Potential array in Volts
            current_A: Applied constant current in Amperes
            mass_g: Active material mass in grams
            area_cm2: Electrode area in cm² (default: 3mm dia GCE)

        Returns:
            GCDResult with all computed metrics
        """
        result = GCDResult()
        
        if len(time) < 10 or len(potential) < 10:
            logger.warning("GCD data too short for analysis")
            return result

        # Current density
        current_density = current_A / mass_g  # A/g
        result.current_density_Ag = current_density

        # Find charge and discharge segments
        # GCD: potential rises (charge) then falls (discharge)
        # Find the peak (switch point from charge to discharge)
        peak_idx = np.argmax(potential)
        
        if peak_idx < 2 or peak_idx >= len(potential) - 2:
            # Try to find turnaround by derivative
            dp = np.diff(potential)
            sign_changes = np.where(np.diff(np.sign(dp)))[0]
            if len(sign_changes) > 0:
                peak_idx = sign_changes[0] + 1
            else:
                peak_idx = len(potential) // 2

        # Charge segment
        t_charge = time[:peak_idx + 1]
        v_charge = potential[:peak_idx + 1]

        # Discharge segment
        t_discharge = time[peak_idx:]
        v_discharge = potential[peak_idx:]

        if len(t_charge) > 1:
            result.charge_time_s = t_charge[-1] - t_charge[0]
        if len(t_discharge) > 1:
            result.discharge_time_s = t_discharge[-1] - t_discharge[0]

        # Potential window (exclude IR drop region)
        v_max = potential[peak_idx]
        v_min = potential[-1] if len(potential) > 0 else 0

        # IR Drop: sudden voltage drop at the start of discharge
        if len(v_discharge) > 3:
            # IR drop = difference between peak and the first "stable" discharge point
            # Use the voltage difference over the first ~2% of discharge time
            n_ir = max(2, len(v_discharge) // 50)
            ir_drop = v_discharge[0] - v_discharge[n_ir]
            result.ir_drop_V = abs(ir_drop)
        
        # Effective potential window (after IR drop)
        delta_v = v_max - v_min - result.ir_drop_V
        if delta_v <= 0:
            delta_v = v_max - v_min
        result.potential_window_V = abs(delta_v)

        # Specific Capacitance: C = I * Δt / (m * ΔV)
        if result.potential_window_V > 0 and mass_g > 0:
            cs = (current_A * result.discharge_time_s) / (mass_g * result.potential_window_V)
            result.specific_capacitance_Fg = cs

        # Energy Density: E = 0.5 * C * ΔV² / 3.6 (Wh/kg)
        if result.specific_capacitance_Fg > 0:
            result.energy_density_Whkg = (
                0.5 * result.specific_capacitance_Fg * result.potential_window_V ** 2 / 3.6
            )

        # Power Density: P = E / t_discharge * 3600 (W/kg)
        if result.discharge_time_s > 0 and result.energy_density_Whkg > 0:
            result.power_density_Wkg = (
                result.energy_density_Whkg * 3600 / result.discharge_time_s
            )

        # Coulombic Efficiency: η = t_discharge / t_charge * 100
        if result.charge_time_s > 0:
            result.coulombic_efficiency_pct = (
                result.discharge_time_s / result.charge_time_s * 100
            )

        # Detect number of cycles
        dp = np.diff(potential)
        sign_changes = np.where(np.diff(np.sign(dp)))[0]
        result.num_cycles = max(1, len(sign_changes) // 2)

        return result

    def analyze_from_dataset(self, dataset, **kwargs) -> Dict[str, Any]:
        """
        Analyze a CHIDataset that contains GCD data.
        
        Args:
            dataset: CHIDataset from chi_parser
            **kwargs: current_A, mass_g, area_cm2

        Returns:
            Dict with GCD analysis results
        """
        time_arr = dataset.get_column("time")
        pot_arr = dataset.get_column("potential")

        if time_arr is None or pot_arr is None:
            return {"error": "No time/potential columns found for GCD analysis"}

        result = self.analyze(
            time=time_arr,
            potential=pot_arr,
            current_A=kwargs.get("current_A", 1e-3),
            mass_g=kwargs.get("mass_g", 1e-3),
            area_cm2=kwargs.get("area_cm2", 0.0707),
        )

        return {
            **result.to_dict(),
            "plot_data": {
                "time": time_arr.tolist(),
                "potential": pot_arr.tolist(),
            }
        }


# Module API
_analyzer: GCDAnalyzer = None


def get_gcd_analyzer() -> GCDAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = GCDAnalyzer()
    return _analyzer
