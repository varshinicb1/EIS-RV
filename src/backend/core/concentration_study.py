"""
Concentration Study Analyzer
================================
Analyzes dose-response data from multi-concentration electrochemical
experiments (DPV, SWV, amperometry).

Specifically designed for the Gomutra concentration study format:
  - Buffer baseline + sequential analyte additions (10–500 µL)
  - Paired potential/current columns
  - Auto-detects peak current shift and builds dose-response curve

Author: VidyuthLabs
Date: May 8, 2026
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

import numpy as np
from scipy import stats
from scipy.optimize import curve_fit

logger = logging.getLogger(__name__)


@dataclass
class DosePoint:
    """Single dose-response point."""
    volume_uL: float
    peak_current_A: float
    peak_potential_V: float
    delta_current_A: float  # relative to buffer


@dataclass
class DoseResponseResult:
    """Complete dose-response analysis."""
    points: List[DosePoint]
    linear_slope: float        # A/µL
    linear_intercept: float
    linear_r_squared: float
    linear_range: Tuple[float, float]  # µL
    dynamic_range: Tuple[float, float]
    saturation_current_A: Optional[float]
    equation: str
    analyte_name: str

    def to_dict(self) -> dict:
        return {
            "points": [
                {
                    "volume_uL": p.volume_uL,
                    "peak_current_A": p.peak_current_A,
                    "peak_potential_V": p.peak_potential_V,
                    "delta_current_A": p.delta_current_A,
                }
                for p in self.points
            ],
            "linear_slope_A_per_uL": self.linear_slope,
            "linear_intercept_A": self.linear_intercept,
            "linear_r_squared": round(self.linear_r_squared, 6),
            "linear_range_uL": list(self.linear_range),
            "dynamic_range_uL": list(self.dynamic_range),
            "saturation_current_A": self.saturation_current_A,
            "equation": self.equation,
            "analyte_name": self.analyte_name,
        }


class ConcentrationStudyAnalyzer:
    """Analyzes multi-concentration electrochemical studies."""

    def analyze_xlsx(
        self,
        file_path: str,
        analyte_name: str = "analyte",
        sheet_name: Optional[str] = None,
    ) -> DoseResponseResult:
        """
        Analyze a multi-concentration DPV .xlsx file.

        Expected format:
          Row 1: 'potential (V)', 'current (A)', ...
          Row 2: None, 'buffer', None, '10 µl', None, '50 µl', ...
          Row 3+: paired [Potential, Current] data

        Args:
            file_path: Path to .xlsx file
            analyte_name: Name of the analyte
            sheet_name: Specific sheet to use (default: first)
        """
        import openpyxl

        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb[sheet_name] if sheet_name else wb.active

        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))

        if len(rows) < 5:
            raise ValueError("Insufficient data rows")

        # Find concentration labels row
        concentrations = []  # (current_col_idx, volume_uL)
        buffer_cur_col = None
        label_row_idx = None

        for i in range(min(5, len(rows))):
            row = rows[i]
            found = []
            buf_col = None
            for j, val in enumerate(row):
                if val is None:
                    continue
                s = str(val).strip()
                s_low = s.lower()

                if s_low == "buffer":
                    buf_col = j  # buffer label IS at the current column
                    continue

                # Skip structural labels
                if s_low in ("potential (v)", "current (a)", "potential", "current", ""):
                    continue

                # Match volume labels: "10 µl", "50 µl", "100 µl"
                # The µ char may come through garbled (cp1252 encoding issue)
                m = re.match(r"^(\d+(?:\.\d+)?)\s*.?[lL]$", s)
                if m:
                    found.append((j, float(m.group(1))))  # label IS the current column
                    continue

                # Match just numbers (if volume context)
                m2 = re.match(r"^(\d+(?:\.\d+)?)$", s_low)
                if m2 and float(m2.group(1)) >= 5:
                    found.append((j, float(m2.group(1))))

            if len(found) >= 3:
                label_row_idx = i
                concentrations = found
                buffer_cur_col = buf_col
                break

        if not concentrations:
            raise ValueError("Could not find concentration labels in file")

        # Find data start
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

        # Extract buffer baseline
        buffer_currents = None
        if buffer_cur_col is not None:
            buf_data = []
            for i in range(data_start, len(rows)):
                row = rows[i]
                try:
                    if buffer_cur_col < len(row) and row[buffer_cur_col] is not None:
                        buf_data.append(float(row[buffer_cur_col]))
                except (ValueError, TypeError):
                    continue
            if buf_data:
                buffer_currents = np.array(buf_data)

        # Extract each concentration curve
        dose_points = []
        for cur_col, volume in concentrations:
            pot_col = cur_col - 1
            potentials = []
            currents = []

            for i in range(data_start, len(rows)):
                row = rows[i]
                try:
                    if pot_col < len(row) and cur_col < len(row):
                        pot = row[pot_col]
                        cur = row[cur_col]
                        if pot is not None and cur is not None:
                            potentials.append(float(pot))
                            currents.append(float(cur))
                except (ValueError, TypeError):
                    continue

            if len(potentials) >= 5:
                pot_arr = np.array(potentials)
                cur_arr = np.array(currents)

                # Baseline subtraction
                if buffer_currents is not None and len(buffer_currents) == len(cur_arr):
                    delta = cur_arr - buffer_currents
                else:
                    delta = cur_arr

                # Find peak (max absolute delta)
                peak_idx = np.argmax(np.abs(delta))
                dose_points.append(DosePoint(
                    volume_uL=volume,
                    peak_current_A=cur_arr[peak_idx],
                    peak_potential_V=pot_arr[peak_idx],
                    delta_current_A=delta[peak_idx],
                ))

        if len(dose_points) < 3:
            raise ValueError(f"Only {len(dose_points)} dose points extracted, need >= 3")

        # Sort by volume
        dose_points.sort(key=lambda p: p.volume_uL)

        # Linear regression on delta currents
        volumes = np.array([p.volume_uL for p in dose_points])
        deltas = np.array([p.delta_current_A for p in dose_points])

        # Find best linear range (try all consecutive subsets >= 3 points)
        best_r2 = -1
        best_start = 0
        best_end = len(volumes)

        for start in range(len(volumes)):
            for end in range(start + 3, len(volumes) + 1):
                sl, ic, rv, _, _ = stats.linregress(volumes[start:end], deltas[start:end])
                r2 = rv ** 2
                if r2 > best_r2:
                    best_r2 = r2
                    best_start = start
                    best_end = end

        # Use best linear range
        lin_vols = volumes[best_start:best_end]
        lin_dels = deltas[best_start:best_end]
        slope, intercept, r_value, _, _ = stats.linregress(lin_vols, lin_dels)
        r_squared = r_value ** 2

        # Saturation estimation (max delta current)
        saturation = float(np.max(np.abs(deltas)))

        # Dynamic range = full range of volumes
        dynamic_range = (float(volumes.min()), float(volumes.max()))
        linear_range = (float(lin_vols.min()), float(lin_vols.max()))

        equation = f"ΔI = {slope:.4e} * V + {intercept:.4e} (R² = {r_squared:.4f})"

        return DoseResponseResult(
            points=dose_points,
            linear_slope=slope,
            linear_intercept=intercept,
            linear_r_squared=r_squared,
            linear_range=linear_range,
            dynamic_range=dynamic_range,
            saturation_current_A=saturation,
            equation=equation,
            analyte_name=analyte_name,
        )
