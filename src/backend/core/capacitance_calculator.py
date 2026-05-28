"""
Specific Capacitance Calculator from Cyclic Voltammetry
========================================================
Implements standard equations from electrochemistry literature for calculating
specific capacitance from CV data.

Standard Equations (from literature):
-------------------------------------
1. **Gravimetric Specific Capacitance (F/g)**:
   Cs = ∫I dV / (2 × m × ΔV × ν)
   
   Where:
   - ∫I dV = Area under CV curve (charge, Coulombs)
   - m = Mass of active material (g)
   - ΔV = Potential window (V)
   - ν = Scan rate (V/s)
   - Factor of 2 accounts for both anodic and cathodic scans

2. **Areal Specific Capacitance (F/cm²)**:
   Ca = ∫I dV / (2 × A × ΔV × ν)
   
   Where:
   - A = Electrode area (cm²)

3. **Volumetric Specific Capacitance (F/cm³)**:
   Cv = ∫I dV / (2 × V × ΔV × ν)
   
   Where:
   - V = Volume of active material (cm³)

4. **From Average Current (simplified)**:
   C = I_avg / ν
   
   Where:
   - I_avg = Average current over the CV cycle (A)
   - ν = Scan rate (V/s)

References:
-----------
- Stoller, M. D., & Ruoff, R. S. (2010). Best practice methods for determining 
  an electrode material's performance for ultracapacitors. Energy & Environmental 
  Science, 3(9), 1294-1301.
- Conway, B. E. (1999). Electrochemical Supercapacitors: Scientific Fundamentals 
  and Technological Applications. Springer.
- ResearchGate discussions on CV capacitance calculations

Author: VidyuthLabs
Date: May 13, 2026
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
from scipy import signal
from scipy.interpolate import UnivariateSpline

logger = logging.getLogger(__name__)


@dataclass
class CapacitanceResult:
    """Results from capacitance calculation."""
    
    # Primary results
    specific_capacitance_F_g: Optional[float] = None
    areal_capacitance_F_cm2: Optional[float] = None
    volumetric_capacitance_F_cm3: Optional[float] = None
    total_capacitance_F: Optional[float] = None
    
    # Intermediate values
    charge_coulombs: float = 0.0
    average_current_A: float = 0.0
    potential_window_V: float = 0.0
    scan_rate_V_s: float = 0.0
    
    # Input parameters
    mass_g: Optional[float] = None
    area_cm2: Optional[float] = None
    volume_cm3: Optional[float] = None
    
    # Quality metrics
    reversibility: float = 0.0  # Ratio of anodic/cathodic charges
    coulombic_efficiency: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "specific_capacitance_F_g": self.specific_capacitance_F_g,
            "areal_capacitance_F_cm2": self.areal_capacitance_F_cm2,
            "volumetric_capacitance_F_cm3": self.volumetric_capacitance_F_cm3,
            "total_capacitance_F": self.total_capacitance_F,
            "charge_coulombs": self.charge_coulombs,
            "average_current_A": self.average_current_A,
            "potential_window_V": self.potential_window_V,
            "scan_rate_V_s": self.scan_rate_V_s,
            "mass_g": self.mass_g,
            "area_cm2": self.area_cm2,
            "volume_cm3": self.volume_cm3,
            "reversibility": self.reversibility,
            "coulombic_efficiency": self.coulombic_efficiency,
        }


class CapacitanceCalculator:
    """
    Calculate specific capacitance from cyclic voltammetry data.
    
    Implements standard equations from electrochemistry literature.
    
    Usage:
        calculator = CapacitanceCalculator()
        
        # From CV data
        result = calculator.from_cv_data(
            potential=[...],  # V
            current=[...],    # A
            mass_g=0.001,     # 1 mg
            scan_rate_mV_s=50
        )
        
        print(f"Specific capacitance: {result.specific_capacitance_F_g:.2f} F/g")
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def from_cv_data(
        self,
        potential: List[float],
        current: List[float],
        scan_rate_mV_s: float,
        mass_g: Optional[float] = None,
        area_cm2: Optional[float] = None,
        volume_cm3: Optional[float] = None,
        calculate_reversibility: bool = True,
        baseline_correction: bool = True,
    ) -> CapacitanceResult:
        """
        Calculate specific capacitance from CV data with proper baseline correction.
        
        Args:
            potential: Potential array (V)
            current: Current array (A)
            scan_rate_mV_s: Scan rate (mV/s)
            mass_g: Mass of active material (g)
            area_cm2: Electrode area (cm²)
            volume_cm3: Volume of active material (cm³)
            calculate_reversibility: Whether to calculate reversibility metrics
            baseline_correction: Whether to apply baseline correction
            
        Returns:
            CapacitanceResult with all calculated values
        """
        E = np.array(potential)
        I = np.array(current)
        scan_rate_V_s = scan_rate_mV_s / 1000.0  # Convert mV/s to V/s
        
        # Validate inputs
        if len(E) != len(I):
            raise ValueError("Potential and current arrays must have same length")
        if len(E) < 10:
            raise ValueError("Need at least 10 data points for reliable calculation")
        if scan_rate_V_s <= 0:
            raise ValueError("Scan rate must be positive")
        
        # Detect turning points (where scan direction changes)
        turning_points = self._detect_turning_points(E)
        
        if len(turning_points) < 2:
            # Fallback: assume single cycle with midpoint split
            turning_points = [0, len(E) // 2, len(E) - 1]
        
        # Apply baseline correction if requested
        if baseline_correction:
            I = self._baseline_correction(E, I)
        
        # Calculate potential window
        potential_window = np.max(E) - np.min(E)
        
        # Calculate charge (area under CV curve) using trapezoidal integration
        try:
            charge_total = np.trapezoid(np.abs(I), E)  # Coulombs
        except AttributeError:
            charge_total = np.trapz(np.abs(I), E)  # Coulombs
        
        # Split into anodic and cathodic scans using detected turning points
        forward_start = turning_points[0]
        forward_end = turning_points[1]
        reverse_start = turning_points[1]
        reverse_end = turning_points[-1]
        
        # Forward scan (anodic)
        E_forward = E[forward_start:forward_end]
        I_forward = I[forward_start:forward_end]
        try:
            charge_anodic = np.trapezoid(np.abs(I_forward), E_forward)
        except AttributeError:
            charge_anodic = np.trapz(np.abs(I_forward), E_forward)
        
        # Reverse scan (cathodic)
        E_reverse = E[reverse_start:reverse_end]
        I_reverse = I[reverse_start:reverse_end]
        try:
            charge_cathodic = np.trapezoid(np.abs(I_reverse), E_reverse)
        except AttributeError:
            charge_cathodic = np.trapz(np.abs(I_reverse), E_reverse)
        
        # Average current
        average_current = np.mean(np.abs(I))
        
        # Calculate reversibility with proper peak analysis
        if calculate_reversibility:
            reversibility, coulombic_efficiency = self._calculate_reversibility(
                E_forward, I_forward, E_reverse, I_reverse
            )
        else:
            reversibility = 0.0
            coulombic_efficiency = 0.0
        
        # Calculate capacitances using standard equation:
        # C = ∫I dV / (2 × m × ΔV × ν)
        # Factor of 2 accounts for both anodic and cathodic scans
        
        result = CapacitanceResult(
            charge_coulombs=charge_total,
            average_current_A=average_current,
            potential_window_V=potential_window,
            scan_rate_V_s=scan_rate_V_s,
            mass_g=mass_g,
            area_cm2=area_cm2,
            volume_cm3=volume_cm3,
            reversibility=reversibility,
            coulombic_efficiency=coulombic_efficiency,
        )
        
        # Gravimetric specific capacitance (F/g)
        if mass_g is not None and mass_g > 0:
            result.specific_capacitance_F_g = charge_total / (
                2 * mass_g * potential_window * scan_rate_V_s
            )
            result.total_capacitance_F = result.specific_capacitance_F_g * mass_g
        
        # Areal specific capacitance (F/cm²)
        if area_cm2 is not None and area_cm2 > 0:
            result.areal_capacitance_F_cm2 = charge_total / (
                2 * area_cm2 * potential_window * scan_rate_V_s
            )
        
        # Volumetric specific capacitance (F/cm³)
        if volume_cm3 is not None and volume_cm3 > 0:
            result.volumetric_capacitance_F_cm3 = charge_total / (
                2 * volume_cm3 * potential_window * scan_rate_V_s
            )
        
        self.logger.info(
            f"Calculated capacitance: "
            f"Cs={result.specific_capacitance_F_g:.2f} F/g, "
            f"Q={charge_total:.6f} C, "
            f"ΔV={potential_window:.3f} V, "
            f"ν={scan_rate_V_s:.4f} V/s, "
            f"Reversibility={reversibility:.3f}"
        )
        
        return result
    
    def _detect_turning_points(self, E: np.ndarray) -> List[int]:
        """
        Detect turning points in CV scan using derivative analysis.
        
        Args:
            E: Potential array
            
        Returns:
            List of indices where scan direction changes
        """
        # Calculate derivative (dE/dt)
        dE = np.diff(E)
        
        # Find sign changes (where derivative changes sign)
        sign_changes = np.where(np.diff(np.sign(dE)))[0] + 1
        
        # Always include start and end points
        turning_points = [0] + list(sign_changes) + [len(E) - 1]
        
        return sorted(set(turning_points))
    
    def _baseline_correction(self, E: np.ndarray, I: np.ndarray) -> np.ndarray:
        """
        Apply baseline correction to remove capacitive background.
        
        Uses spline fitting to estimate and subtract baseline.
        
        Args:
            E: Potential array
            I: Current array
            
        Returns:
            Baseline-corrected current array
        """
        try:
            # Fit a low-order spline to estimate baseline
            # Use smoothing to avoid overfitting
            spline = UnivariateSpline(E, I, s=len(E) * np.std(I) ** 2, k=3)
            baseline = spline(E)
            
            # Subtract baseline
            I_corrected = I - baseline
            
            return I_corrected
        except Exception as e:
            self.logger.warning(f"Baseline correction failed: {e}. Using raw data.")
            return I
    
    def _calculate_reversibility(
        self,
        E_forward: np.ndarray,
        I_forward: np.ndarray,
        E_reverse: np.ndarray,
        I_reverse: np.ndarray
    ) -> Tuple[float, float]:
        """
        Calculate reversibility using proper peak analysis.
        
        Args:
            E_forward: Forward scan potential
            I_forward: Forward scan current
            E_reverse: Reverse scan potential
            I_reverse: Reverse scan current
            
        Returns:
            (reversibility, coulombic_efficiency)
        """
        try:
            # Find peaks in forward scan (anodic)
            peaks_forward, _ = signal.find_peaks(I_forward, prominence=np.std(I_forward))
            if len(peaks_forward) > 0:
                peak_current_anodic = I_forward[peaks_forward[0]]
                peak_potential_anodic = E_forward[peaks_forward[0]]
            else:
                peak_current_anodic = np.max(I_forward)
                peak_potential_anodic = E_forward[np.argmax(I_forward)]
            
            # Find peaks in reverse scan (cathodic) - look for negative peaks
            peaks_reverse, _ = signal.find_peaks(-I_reverse, prominence=np.std(I_reverse))
            if len(peaks_reverse) > 0:
                peak_current_cathodic = abs(I_reverse[peaks_reverse[0]])
                peak_potential_cathodic = E_reverse[peaks_reverse[0]]
            else:
                peak_current_cathodic = abs(np.min(I_reverse))
                peak_potential_cathodic = E_reverse[np.argmin(I_reverse)]
            
            # Calculate peak current ratio (reversibility)
            if peak_current_anodic > 0 and peak_current_cathodic > 0:
                reversibility = min(peak_current_anodic, peak_current_cathodic) / \
                               max(peak_current_anodic, peak_current_cathodic)
            else:
                reversibility = 0.0
            
            # Calculate charge ratio (coulombic efficiency)
            try:
                charge_anodic = np.trapezoid(np.abs(I_forward), E_forward)
                charge_cathodic = np.trapezoid(np.abs(I_reverse), E_reverse)
            except AttributeError:
                charge_anodic = np.trapz(np.abs(I_forward), E_forward)
                charge_cathodic = np.trapz(np.abs(I_reverse), E_reverse)
            
            if charge_anodic > 0:
                coulombic_efficiency = charge_cathodic / charge_anodic
            else:
                coulombic_efficiency = 0.0
            
            return reversibility, coulombic_efficiency
            
        except Exception as e:
            self.logger.warning(f"Reversibility calculation failed: {e}")
            return 0.0, 0.0
    
    def from_average_current(
        self,
        average_current_A: float,
        scan_rate_mV_s: float,
        mass_g: Optional[float] = None,
        area_cm2: Optional[float] = None,
    ) -> CapacitanceResult:
        """
        Calculate capacitance from average current (simplified method).
        
        Uses: C = I_avg / ν
        
        Args:
            average_current_A: Average current (A)
            scan_rate_mV_s: Scan rate (mV/s)
            mass_g: Mass of active material (g)
            area_cm2: Electrode area (cm²)
            
        Returns:
            CapacitanceResult
        """
        scan_rate_V_s = scan_rate_mV_s / 1000.0
        
        # Total capacitance
        total_capacitance = average_current_A / scan_rate_V_s
        
        result = CapacitanceResult(
            total_capacitance_F=total_capacitance,
            average_current_A=average_current_A,
            scan_rate_V_s=scan_rate_V_s,
            mass_g=mass_g,
            area_cm2=area_cm2,
        )
        
        # Specific capacitances
        if mass_g is not None and mass_g > 0:
            result.specific_capacitance_F_g = total_capacitance / mass_g
        
        if area_cm2 is not None and area_cm2 > 0:
            result.areal_capacitance_F_cm2 = total_capacitance / area_cm2
        
        return result
    
    def multi_scan_rate_analysis(
        self,
        cv_data_list: List[Dict],
        mass_g: Optional[float] = None,
        area_cm2: Optional[float] = None,
    ) -> Dict:
        """
        Analyze capacitance at multiple scan rates.
        
        Useful for determining rate capability and identifying
        diffusion-limited vs. capacitive behavior.
        
        Args:
            cv_data_list: List of dicts with keys:
                - 'potential': List[float]
                - 'current': List[float]
                - 'scan_rate_mV_s': float
            mass_g: Mass of active material (g)
            area_cm2: Electrode area (cm²)
            
        Returns:
            Dict with:
                - 'results': List[CapacitanceResult]
                - 'scan_rates': List[float]
                - 'capacitances': List[float]
                - 'rate_capability': float (% retention from lowest to highest rate)
        """
        results = []
        scan_rates = []
        capacitances = []
        
        for cv_data in cv_data_list:
            result = self.from_cv_data(
                potential=cv_data['potential'],
                current=cv_data['current'],
                scan_rate_mV_s=cv_data['scan_rate_mV_s'],
                mass_g=mass_g,
                area_cm2=area_cm2,
            )
            results.append(result)
            scan_rates.append(cv_data['scan_rate_mV_s'])
            
            if result.specific_capacitance_F_g is not None:
                capacitances.append(result.specific_capacitance_F_g)
            elif result.areal_capacitance_F_cm2 is not None:
                capacitances.append(result.areal_capacitance_F_cm2)
            else:
                capacitances.append(result.total_capacitance_F or 0)
        
        # Calculate rate capability
        if len(capacitances) >= 2:
            rate_capability = (capacitances[-1] / capacitances[0]) * 100
        else:
            rate_capability = 100.0
        
        return {
            'results': results,
            'scan_rates': scan_rates,
            'capacitances': capacitances,
            'rate_capability': rate_capability,
            'best_capacitance': max(capacitances) if capacitances else 0,
            'worst_capacitance': min(capacitances) if capacitances else 0,
        }
    
    def energy_power_analysis(
        self,
        capacitance_F_g: float,
        potential_window_V: float,
        mass_g: float,
        esr_ohm: Optional[float] = None,
    ) -> Dict:
        """
        Calculate energy and power density (Ragone plot values).
        
        Args:
            capacitance_F_g: Specific capacitance (F/g)
            potential_window_V: Potential window (V)
            mass_g: Mass of active material (g)
            esr_ohm: Equivalent series resistance (Ω)
            
        Returns:
            Dict with energy_density_Wh_kg and power_density_W_kg
        """
        # Energy density: E = 0.5 × C × V² / 3.6  (Wh/kg)
        # Factor of 3.6 converts J to Wh
        energy_density_Wh_kg = (
            0.5 * capacitance_F_g * (potential_window_V ** 2) / 3.6
        ) * 1000  # Convert to Wh/kg
        
        # Power density: P = V² / (4 × ESR × m)  (W/kg)
        if esr_ohm is not None and esr_ohm > 0 and mass_g > 0:
            power_density_W_kg = (
                (potential_window_V ** 2) / (4 * esr_ohm * mass_g)
            ) * 1000  # Convert to W/kg
        else:
            # Estimate from capacitance (assumes fast discharge)
            power_density_W_kg = energy_density_Wh_kg * 3600  # 1 second discharge
        
        return {
            'energy_density_Wh_kg': energy_density_Wh_kg,
            'power_density_W_kg': power_density_W_kg,
            'capacitance_F_g': capacitance_F_g,
            'potential_window_V': potential_window_V,
        }


# Global singleton
_calculator_instance = None

def get_capacitance_calculator() -> CapacitanceCalculator:
    """Get the global capacitance calculator instance."""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = CapacitanceCalculator()
    return _calculator_instance
