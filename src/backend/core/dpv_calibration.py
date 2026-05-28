"""
DPV Calibration Curve Builder
================================
Builds analytical calibration curves from multi-concentration DPV data.
Extracts peak currents, fits linear regression, and calculates:
  - LOD (3σ/slope)
  - LOQ (10σ/slope)
  - Sensitivity (slope / electrode area)
  - Linear range
  - R² correlation coefficient

Supports CHI608E DPV exports with paired potential/current columns.

Author: VidyuthLabs
Date: May 8, 2026
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class CalibrationPoint:
    """Single calibration point."""
    concentration: float       # in µM
    concentration_unit: str
    peak_current_A: float
    peak_potential_V: float


@dataclass
class CalibrationResult:
    """Complete calibration curve result."""
    points: List[CalibrationPoint]
    slope: float               # A/µM
    intercept: float           # A
    r_squared: float
    lod: float                 # µM
    loq: float                 # µM
    sensitivity: float         # µA/µM (or µA/µM/cm² if area provided)
    linear_range: Tuple[float, float]  # µM
    equation: str
    electrode_area_cm2: float = 0.0707  # default GCE 3mm diameter

    def to_dict(self) -> dict:
        return {
            "points": [
                {
                    "concentration": p.concentration,
                    "unit": p.concentration_unit,
                    "peak_current_A": p.peak_current_A,
                    "peak_potential_V": p.peak_potential_V,
                }
                for p in self.points
            ],
            "slope_A_per_uM": self.slope,
            "intercept_A": self.intercept,
            "r_squared": round(self.r_squared, 6),
            "lod_uM": round(self.lod, 4),
            "loq_uM": round(self.loq, 4),
            "sensitivity_uA_per_uM_cm2": round(self.sensitivity, 4),
            "linear_range_uM": list(self.linear_range),
            "equation": self.equation,
            "electrode_area_cm2": self.electrode_area_cm2,
        }


class DPVCalibrationBuilder:
    """Builds calibration curves from multi-concentration DPV data."""

    def __init__(self, electrode_area_cm2: float = 0.0707):
        """
        Args:
            electrode_area_cm2: Working electrode geometric area (default: 3mm GCE)
        """
        self.electrode_area = electrode_area_cm2

    def build_from_xlsx(self, file_path: str) -> CalibrationResult:
        """
        Build calibration from a CHI608E DPV .xlsx with multi-concentration columns.

        Expected format: paired columns [Potential, Current] for each concentration,
        with concentration labels in header row.

        Args:
            file_path: Path to DPV .xlsx file

        Returns:
            CalibrationResult with LOD, sensitivity, etc.
        """
        import openpyxl

        wb = openpyxl.load_workbook(file_path, data_only=True)

        # Try each sheet to find calibration data
        for ws in wb:
            result = self._try_parse_sheet(ws)
            if result is not None:
                return result

        raise ValueError("No valid calibration data found in any sheet")

    def _try_parse_sheet(self, ws) -> Optional[CalibrationResult]:
        """Try to parse a single worksheet for calibration data."""
        import re

        # Read all rows
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))

        if len(rows) < 5:
            return None

        # Strategy: find the row with concentration labels like "1 µM", "5 µm",
        # "300", "buffer" etc. These sit in a header row.
        # Data is paired: [Pot_1, Cur_1, Pot_2, Cur_2, ...]
        # Concentration labels appear at even column indices (0,2,4...) or odd.
        concentrations = []  # list of (current_col_idx, concentration_value)
        conc_unit = "uM"
        label_row_idx = None
        buffer_col_idx = None

        for i in range(min(5, len(rows))):
            row = rows[i]
            concs = []
            buf_idx = None
            for j, val in enumerate(row):
                if val is None:
                    continue
                s = str(val).strip()
                s_low = s.lower()

                if s_low == "buffer":
                    buf_idx = j
                    continue

                # Skip structural headers
                if s_low in ("potential (v)", "current (a)", "potential", "current",
                             "none", ""):
                    continue

                # Match: "300", "1 µM", "5 µm", "10 µM"
                m = re.match(r"^([\d.]+)\s*(?:µ|u|μ)?\s*(?:M|m|l|L)?$", s)
                if m:
                    conc_val = float(m.group(1))
                    # The current column is the NEXT column (j+1) in paired format
                    concs.append((j + 1, conc_val))

            if len(concs) >= 3:
                label_row_idx = i
                concentrations = concs
                buffer_col_idx = buf_idx + 1 if buf_idx is not None else None
                break

        if not concentrations:
            return None

        # Find data start (first row after labels with numeric data)
        data_start = label_row_idx + 1
        for i in range(label_row_idx + 1, len(rows)):
            row = rows[i]
            if row and row[0] is not None:
                try:
                    float(row[0])
                    data_start = i
                    break
                except (ValueError, TypeError):
                    continue

        # Extract buffer baseline (if available)
        buffer_currents = []
        if buffer_col_idx is not None:
            for i in range(data_start, len(rows)):
                row = rows[i]
                try:
                    if buffer_col_idx < len(row) and row[buffer_col_idx] is not None:
                        buffer_currents.append(float(row[buffer_col_idx]))
                except (ValueError, TypeError):
                    continue
        buffer_arr = np.array(buffer_currents) if buffer_currents else None

        # Extract each concentration's DPV curve
        cal_points = []
        for cur_col, conc in concentrations:
            potentials = []
            currents = []
            pot_col = cur_col - 1  # Potential is always one column before current

            for i in range(data_start, len(rows)):
                row = rows[i]
                try:
                    if pot_col < len(row) and cur_col < len(row):
                        pot = row[pot_col]
                        cur = row[cur_col]
                        if pot is not None and cur is not None:
                            potentials.append(float(pot))
                            currents.append(float(cur))
                except (ValueError, TypeError, IndexError):
                    continue

            if len(potentials) >= 5:
                pot_arr = np.array(potentials)
                cur_arr = np.array(currents)

                # Subtract buffer baseline if available
                if buffer_arr is not None and len(buffer_arr) == len(cur_arr):
                    cur_corrected = cur_arr - buffer_arr
                else:
                    cur_corrected = cur_arr

                # Find peak current (maximum in corrected signal)
                peak_idx = np.argmax(cur_corrected)
                cal_points.append(CalibrationPoint(
                    concentration=conc,
                    concentration_unit=conc_unit,
                    peak_current_A=cur_corrected[peak_idx],
                    peak_potential_V=pot_arr[peak_idx],
                ))

        if len(cal_points) < 3:
            return None

        # Sort by concentration
        cal_points.sort(key=lambda p: p.concentration)

        # Extract arrays
        concs = np.array([p.concentration for p in cal_points])
        currents = np.array([p.peak_current_A for p in cal_points])

        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(concs, currents)
        r_squared = r_value ** 2

        # LOD and LOQ from residuals
        predicted = slope * concs + intercept
        residuals = currents - predicted
        sigma = np.std(residuals)

        lod = 3 * sigma / abs(slope) if slope != 0 else float("inf")
        loq = 10 * sigma / abs(slope) if slope != 0 else float("inf")

        # Sensitivity in µA/µM/cm²
        sensitivity = abs(slope) * 1e6 / self.electrode_area  # Convert A to µA

        # Linear range
        linear_range = (float(concs.min()), float(concs.max()))

        # Equation string
        equation = f"I = {slope:.4e} * C + {intercept:.4e} (R² = {r_squared:.4f})"

        return CalibrationResult(
            points=cal_points,
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            lod=lod,
            loq=loq,
            sensitivity=sensitivity,
            linear_range=linear_range,
            equation=equation,
            electrode_area_cm2=self.electrode_area,
        )


# Module API
_builder: Optional[DPVCalibrationBuilder] = None


def get_calibration_builder(area: float = 0.0707) -> DPVCalibrationBuilder:
    global _builder
    if _builder is None:
        _builder = DPVCalibrationBuilder(area)
    return _builder
