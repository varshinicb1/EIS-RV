"""
CHI Instruments Universal File Parser
=======================================
Parses electrochemical data files from CH Instruments potentiostats
(CHI608E, CHI660E, CHI760E, etc.).

Supports:
  - EIS (A.C. Impedance): Freq, Z', Z", |Z|, Phase
  - DPV (Differential Pulse Voltammetry): Potential, Current
  - CV (Cyclic Voltammetry): Potential, Current
  - CA (Chronoamperometry): Time, Current
  - Raman spectroscopy (.txt tab-separated: Wavenumber, Intensity)

Handles both .xlsx and .csv exports from CHI software.
Auto-detects technique from file headers.

Author: VidyuthLabs
Date: May 8, 2026
"""

import re
import logging
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CHIMetadata:
    """Metadata extracted from a CHI instrument file header."""
    date: str = ""
    technique: str = ""           # EIS, DPV, CV, CA, LSV, SWV, Raman
    instrument_model: str = ""    # CHI608E, CHI660E, etc.
    file_path: str = ""           # Original file path from instrument
    init_e_v: Optional[float] = None
    final_e_v: Optional[float] = None
    high_freq_hz: Optional[float] = None
    low_freq_hz: Optional[float] = None
    amplitude_v: Optional[float] = None
    scan_rate_vs: Optional[float] = None
    quiet_time_s: Optional[float] = None
    sample_interval_v: Optional[float] = None
    pulse_amplitude_v: Optional[float] = None
    pulse_width_s: Optional[float] = None
    sensitivity_av: Optional[float] = None
    raw_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class CHIDataColumn:
    """A single data column with name and unit."""
    name: str
    unit: str
    data: np.ndarray


@dataclass
class CHIDataset:
    """Complete parsed dataset from a CHI instrument file."""
    metadata: CHIMetadata
    columns: List[CHIDataColumn]
    source_file: str = ""
    num_points: int = 0

    @property
    def column_names(self) -> List[str]:
        return [c.name for c in self.columns]

    def get_column(self, name: str) -> Optional[np.ndarray]:
        """Get column data by name (case-insensitive partial match)."""
        name_lower = name.lower()
        for col in self.columns:
            if name_lower in col.name.lower():
                return col.data
        return None

    def to_dict(self) -> dict:
        """Serialize for API response."""
        return {
            "metadata": {
                "date": self.metadata.date,
                "technique": self.metadata.technique,
                "instrument": self.metadata.instrument_model,
                "init_e_v": self.metadata.init_e_v,
                "high_freq_hz": self.metadata.high_freq_hz,
                "low_freq_hz": self.metadata.low_freq_hz,
                "amplitude_v": self.metadata.amplitude_v,
                "scan_rate_vs": self.metadata.scan_rate_vs,
            },
            "columns": [
                {"name": c.name, "unit": c.unit, "points": len(c.data)}
                for c in self.columns
            ],
            "num_points": self.num_points,
            "source_file": self.source_file,
        }


# ── Technique detection patterns ──────────────────────────────────

TECHNIQUE_MAP = {
    "a.c. impedance": "EIS",
    "ac impedance": "EIS",
    "impedance": "EIS",
    "differential pulse": "DPV",
    "diff pulse": "DPV",
    "cyclic voltammetry": "CV",
    "linear sweep": "LSV",
    "square wave": "SWV",
    "chronoamperometry": "CA",
    "chrono": "CA",
    "chronopotentiometry": "GCD",
    "galvanostatic": "GCD",
    "charge discharge": "GCD",
    "charge-discharge": "GCD",
    "gcd": "GCD",
    "open circuit": "OCP",
    "bulk electrolysis": "BE",
}

# Column header normalization
COLUMN_UNITS = {
    "Freq/Hz": ("frequency", "Hz"),
    "Z'/ohm": ("Z_real", "ohm"),
    'Z"/ohm': ("Z_imag", "ohm"),
    "Z/ohm": ("Z_mag", "ohm"),
    "Phase/deg": ("phase", "deg"),
    "Potential/V": ("potential", "V"),
    "Current/A": ("current", "A"),
    "Time/s": ("time", "s"),
    "Charge/C": ("charge", "C"),
}


class CHIParser:
    """
    Universal parser for CH Instruments electrochemical data files.
    """

    def parse(self, file_path: str) -> CHIDataset:
        """
        Parse a CHI instrument data file.

        Args:
            file_path: Path to .xlsx, .csv, or .txt file

        Returns:
            CHIDataset with metadata and data columns
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        if ext == ".xlsx" or ext == ".xls":
            return self._parse_xlsx(path)
        elif ext == ".csv":
            return self._parse_csv(path)
        elif ext == ".txt":
            return self._parse_txt(path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _parse_xlsx(self, path: Path) -> CHIDataset:
        """Parse CHI .xlsx export."""
        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl required: pip install openpyxl")

        wb = openpyxl.load_workbook(str(path), data_only=True)
        ws = wb.active

        # Read all rows
        all_rows = []
        for row in ws.iter_rows(values_only=True):
            all_rows.append(list(row))

        return self._parse_chi_rows(all_rows, str(path))

    def _parse_csv(self, path: Path) -> CHIDataset:
        """Parse CHI .csv export."""
        all_rows = []
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                all_rows.append(row)

        return self._parse_chi_rows(all_rows, str(path))

    def _parse_txt(self, path: Path) -> CHIDataset:
        """Parse tab-separated .txt (Raman, generic spectral data)."""
        metadata = CHIMetadata(technique="Raman")
        columns_data: Dict[str, list] = {}
        header_names = []

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # Check for header line
                if line.startswith("#"):
                    parts = line.lstrip("#").strip().split("\t")
                    header_names = [p.strip() for p in parts if p.strip()]
                    for h in header_names:
                        columns_data[h] = []
                    continue

                # Data line
                parts = line.split("\t")
                try:
                    values = [float(p.strip()) for p in parts if p.strip()]
                    if not header_names:
                        header_names = ["Wavenumber", "Intensity"]
                        for h in header_names:
                            columns_data[h] = []

                    for i, v in enumerate(values):
                        if i < len(header_names):
                            columns_data[header_names[i]].append(v)
                except ValueError:
                    continue

        # Build columns
        columns = []
        for name, data in columns_data.items():
            unit = "cm-1" if "wave" in name.lower() else "a.u."
            columns.append(CHIDataColumn(
                name=name, unit=unit, data=np.array(data)
            ))

        n_pts = len(columns[0].data) if columns else 0

        return CHIDataset(
            metadata=metadata,
            columns=columns,
            source_file=str(path),
            num_points=n_pts,
        )

    def _parse_chi_rows(self, rows: List[List], source: str) -> CHIDataset:
        """Parse CHI header + data from row list (shared by xlsx/csv)."""
        metadata = CHIMetadata()
        metadata.file_path = source

        data_start_row = -1
        header_row = -1
        column_headers = []

        # Scan for metadata and data start
        for i, row in enumerate(rows):
            if not row or all(v is None for v in row):
                continue

            first = str(row[0]).strip() if row[0] is not None else ""
            row_text = " ".join(str(v) for v in row if v is not None).lower()

            # Date (first row)
            if i < 3 and (
                "jan" in row_text or "feb" in row_text or "mar" in row_text
                or "apr" in row_text or "may" in row_text or "jun" in row_text
                or "jul" in row_text or "aug" in row_text or "sep" in row_text
                or "oct" in row_text or "nov" in row_text or "dec" in row_text
            ):
                metadata.date = " ".join(str(v) for v in row if v is not None).strip()

            # Technique
            for pattern, technique in TECHNIQUE_MAP.items():
                if pattern in row_text:
                    metadata.technique = technique
                    break

            # Instrument model
            if "instrument model" in row_text:
                match = re.search(r"CHI\w+", row_text, re.IGNORECASE)
                if match:
                    metadata.instrument_model = match.group().upper()

            # Experimental parameters
            if "init e" in row_text:
                m = re.search(r"[-+]?\d+\.?\d*", first.split("=")[-1] if "=" in first else first)
                if m:
                    metadata.init_e_v = float(m.group())
            if "final e" in row_text:
                m = re.search(r"[-+]?\d+\.?\d*", first.split("=")[-1] if "=" in first else first)
                if m:
                    metadata.final_e_v = float(m.group())
            if "high freq" in row_text:
                m = re.search(r"[\d.]+(?:e[+-]?\d+)?", first.split("=")[-1] if "=" in first else first)
                if m:
                    metadata.high_freq_hz = float(m.group())
            if "low freq" in row_text:
                m = re.search(r"[\d.]+(?:e[+-]?\d+)?", first.split("=")[-1] if "=" in first else first)
                if m:
                    metadata.low_freq_hz = float(m.group())
            if "amplitude" in row_text:
                m = re.search(r"[\d.]+", first.split("=")[-1] if "=" in first else first)
                if m:
                    metadata.amplitude_v = float(m.group())
            if "scan rate" in row_text:
                m = re.search(r"[\d.]+", first.split("=")[-1] if "=" in first else first)
                if m:
                    metadata.scan_rate_vs = float(m.group())
            if "quiet time" in row_text:
                m = re.search(r"[\d.]+", first.split("=")[-1] if "=" in first else first)
                if m:
                    metadata.quiet_time_s = float(m.group())

            # Column headers (Freq/Hz, Z'/ohm, etc.)
            if "freq" in row_text and ("hz" in row_text or "ohm" in row_text):
                header_row = i
                column_headers = [str(v).strip() for v in row if v is not None]
                continue
            if "potential" in row_text and ("current" in row_text or "v" in row_text.split()):
                header_row = i
                column_headers = [str(v).strip() for v in row if v is not None]
                continue

            # Auto-detect data start (row of all numbers after header)
            if header_row >= 0 and i > header_row:
                try:
                    numeric_vals = [float(v) for v in row if v is not None]
                    if len(numeric_vals) >= 2:
                        data_start_row = i
                        break
                except (ValueError, TypeError):
                    continue

        # If no header found, try to detect DPV multi-column format
        if header_row < 0:
            for i, row in enumerate(rows):
                if not row:
                    continue
                try:
                    numeric_vals = [float(v) for v in row if v is not None]
                    if len(numeric_vals) >= 4:
                        data_start_row = i
                        # Generate generic column names
                        n_cols = len([v for v in row if v is not None])
                        column_headers = [f"Col_{j}" for j in range(n_cols)]
                        break
                except (ValueError, TypeError):
                    # Check if this row has concentration labels
                    first_val = row[0]
                    if first_val is not None and isinstance(first_val, (int, float)):
                        continue
                    # This might be a label row
                    labels = [str(v) for v in row if v is not None]
                    if any(("potential" in l.lower() or "current" in l.lower()) for l in labels):
                        header_row = i
                        column_headers = labels
                    continue

        if data_start_row < 0:
            # Last resort: find first row with >=2 floats
            for i, row in enumerate(rows):
                try:
                    vals = [float(v) for v in row if v is not None]
                    if len(vals) >= 2:
                        data_start_row = i
                        if not column_headers:
                            column_headers = [f"Col_{j}" for j in range(len(vals))]
                        break
                except (ValueError, TypeError):
                    continue

        # Extract data columns
        columns = []
        if data_start_row >= 0:
            # Collect data
            col_data: Dict[int, list] = {j: [] for j in range(len(column_headers))}

            for i in range(data_start_row, len(rows)):
                row = rows[i]
                if not row or all(v is None for v in row):
                    continue
                for j in range(min(len(column_headers), len(row))):
                    val = row[j]
                    if val is not None:
                        try:
                            col_data[j].append(float(val))
                        except (ValueError, TypeError):
                            col_data[j].append(np.nan)

            for j, header in enumerate(column_headers):
                # Determine unit
                header_clean = header.strip().strip("'\"")
                name, unit = self._parse_column_header(header_clean)
                data = np.array(col_data.get(j, []))
                if len(data) > 0:
                    columns.append(CHIDataColumn(name=name, unit=unit, data=data))

        # Auto-detect technique from columns if not found in headers
        if not metadata.technique:
            col_names = [c.name.lower() for c in columns]
            if any("freq" in n for n in col_names):
                metadata.technique = "EIS"
            elif any("potential" in n for n in col_names):
                metadata.technique = "DPV"

        n_pts = len(columns[0].data) if columns else 0

        return CHIDataset(
            metadata=metadata,
            columns=columns,
            source_file=source,
            num_points=n_pts,
        )

    def _parse_column_header(self, header: str) -> Tuple[str, str]:
        """Extract name and unit from a CHI column header like Freq/Hz or Z'/ohm."""
        # Check known patterns
        for pattern, (name, unit) in COLUMN_UNITS.items():
            if pattern.lower() in header.lower() or header.lower() in pattern.lower():
                return name, unit

        # Try to split on /
        if "/" in header:
            parts = header.split("/", 1)
            return parts[0].strip(), parts[1].strip()

        # Detect from common keywords
        h = header.lower()
        if "freq" in h:
            return "frequency", "Hz"
        if "z'" in h or "zre" in h:
            return "Z_real", "ohm"
        if 'z"' in h or "zim" in h:
            return "Z_imag", "ohm"
        if "phase" in h:
            return "phase", "deg"
        if "potential" in h or h == "e":
            return "potential", "V"
        if "current" in h or h == "i":
            return "current", "A"
        if "time" in h:
            return "time", "s"

        return header, ""


class LabDataAnalyzer:
    """
    Analyzes parsed CHI instrument data — extracts EIS parameters,
    identifies materials, builds calibration curves.
    """

    def __init__(self):
        self.parser = CHIParser()

    def analyze_eis(self, dataset: CHIDataset) -> Dict[str, Any]:
        """Extract Randles circuit parameters from EIS data."""
        z_real = dataset.get_column("Z_real")
        z_imag = dataset.get_column("Z_imag")
        freq = dataset.get_column("freq")

        if z_real is None or z_imag is None:
            return {"error": "No Z' and Z'' columns found"}

        # Make Z_imag positive for Nyquist plot (convention: -Z" vs Z')
        z_imag_pos = np.abs(z_imag)

        # Rs = Z' at highest frequency (first point if sorted desc)
        if freq is not None and len(freq) > 0:
            high_freq_idx = np.argmax(freq)
            rs = z_real[high_freq_idx]
        else:
            rs = z_real[0]

        # Rct = semicircle diameter
        # Find the point where -Z" is maximum (top of semicircle)
        semicircle_top = np.argmax(z_imag_pos)

        # Rct estimation: Z' at the right edge of semicircle minus Rs
        # Right edge = after the maximum, where Z_imag crosses back near zero
        if semicircle_top < len(z_real) - 1:
            # Look for Z_imag minimum after the semicircle top
            post_top = z_imag_pos[semicircle_top:]
            min_after_top = np.argmin(post_top) + semicircle_top
            rct = z_real[min_after_top] - rs
        else:
            # Estimate from 2x(Z' at max -Z" point) - Rs
            rct = 2 * (z_real[semicircle_top] - rs)

        # Cdl estimation from peak frequency
        if freq is not None:
            f_peak = freq[semicircle_top]
            if f_peak > 0 and rct > 0:
                cdl = 1 / (2 * np.pi * f_peak * rct)
            else:
                cdl = None
        else:
            cdl = None

        # Z total at low frequency
        z_low_freq = np.sqrt(z_real[-1]**2 + z_imag[-1]**2)

        return {
            "Rs_ohm": round(float(rs), 2),
            "Rct_ohm": round(float(rct), 2),
            "Cdl_F": float(f"{cdl:.4e}") if cdl else None,
            "Z_low_freq_ohm": round(float(z_low_freq), 2),
            "semicircle_top_freq_Hz": float(freq[semicircle_top]) if freq is not None else None,
            "num_points": len(z_real),
            "nyquist_data": {
                "z_real": z_real.tolist(),
                "z_imag_neg": (-z_imag).tolist() if z_imag is not None else [],
            },
        }

    def analyze_dpv(self, dataset: CHIDataset) -> Dict[str, Any]:
        """Extract peak current and potential from DPV data."""
        potential = dataset.get_column("potential")
        current = dataset.get_column("current")

        if potential is None or current is None:
            return {"error": "No potential/current columns found"}

        # Find peak current (max absolute current)
        peak_idx = np.argmax(np.abs(current))
        peak_potential = potential[peak_idx]
        peak_current = current[peak_idx]

        return {
            "peak_potential_V": round(float(peak_potential), 4),
            "peak_current_A": float(f"{peak_current:.4e}"),
            "num_points": len(potential),
            "potential_range_V": [round(float(potential.min()), 4),
                                  round(float(potential.max()), 4)],
        }

    def analyze_raman(self, dataset: CHIDataset) -> Dict[str, Any]:
        """Extract peaks and identify material from Raman spectrum."""
        from scipy.signal import find_peaks

        wavenumber = dataset.get_column("Wave")
        intensity = dataset.get_column("Intensity")

        if wavenumber is None:
            wavenumber = dataset.get_column("wavenumber")
        if intensity is None:
            intensity = dataset.get_column("intensity")

        if wavenumber is None or intensity is None:
            return {"error": "No wavenumber/intensity columns found"}

        # Find significant peaks
        threshold = intensity.mean() + 1.5 * intensity.std()
        peaks, props = find_peaks(intensity, height=threshold, distance=10)

        peak_list = []
        band_assignments = []
        for p in peaks:
            wn = wavenumber[p]
            inten = intensity[p]
            peak_list.append({"wavenumber": round(float(wn), 1),
                              "intensity": round(float(inten), 1)})

            # Assign known bands
            if 200 < wn < 250:
                band_assignments.append({"wavenumber": round(float(wn)), "assignment": "Fe2O3 A1g"})
            elif 280 < wn < 310:
                band_assignments.append({"wavenumber": round(float(wn)), "assignment": "Fe2O3 Eg"})
            elif 380 < wn < 420:
                band_assignments.append({"wavenumber": round(float(wn)), "assignment": "Fe2O3 Eg"})
            elif 480 < wn < 520:
                band_assignments.append({"wavenumber": round(float(wn)), "assignment": "Fe2O3 A1g"})
            elif 590 < wn < 620:
                band_assignments.append({"wavenumber": round(float(wn)), "assignment": "Fe2O3 Eu/LO"})
            elif 650 < wn < 690:
                band_assignments.append({"wavenumber": round(float(wn)), "assignment": "Fe3O4 A1g (magnetite)"})
            elif 1300 < wn < 1400:
                band_assignments.append({"wavenumber": round(float(wn)), "assignment": "D-band (rGO/carbon)"})
            elif 1550 < wn < 1620:
                band_assignments.append({"wavenumber": round(float(wn)), "assignment": "G-band (rGO/carbon)"})
            elif 2650 < wn < 2750:
                band_assignments.append({"wavenumber": round(float(wn)), "assignment": "2D-band (graphene)"})

        # Material identification
        materials_detected = set()
        for ba in band_assignments:
            if "Fe2O3" in ba["assignment"]:
                materials_detected.add("Fe2O3 (hematite)")
            elif "Fe3O4" in ba["assignment"]:
                materials_detected.add("Fe3O4 (magnetite)")
            elif "D-band" in ba["assignment"] or "G-band" in ba["assignment"]:
                materials_detected.add("rGO (reduced graphene oxide)")
            elif "2D" in ba["assignment"]:
                materials_detected.add("graphene")

        return {
            "peaks": peak_list,
            "band_assignments": band_assignments,
            "materials_detected": list(materials_detected),
            "wavenumber_range": [round(float(wavenumber.min()), 1),
                                 round(float(wavenumber.max()), 1)],
            "num_points": len(wavenumber),
        }

    def auto_analyze(self, file_path: str) -> Dict[str, Any]:
        """
        Auto-detect file type and run appropriate analysis.

        Args:
            file_path: Path to any CHI instrument file

        Returns:
            Complete analysis result with metadata, data, and derived parameters
        """
        dataset = self.parser.parse(file_path)
        result = {
            "file": Path(file_path).name,
            "metadata": dataset.to_dict()["metadata"],
            "technique": dataset.metadata.technique,
        }

        if dataset.metadata.technique == "EIS":
            result["eis_analysis"] = self.analyze_eis(dataset)
        elif dataset.metadata.technique == "GCD":
            result["gcd_analysis"] = self._analyze_gcd(dataset)
        elif dataset.metadata.technique in ("DPV", "CV", "LSV", "SWV"):
            result["dpv_analysis"] = self.analyze_dpv(dataset)
        elif dataset.metadata.technique == "Raman":
            result["raman_analysis"] = self.analyze_raman(dataset)
        else:
            # Try EIS first, then GCD, then DPV, then Raman
            if dataset.get_column("Z_real") is not None:
                result["technique"] = "EIS"
                result["eis_analysis"] = self.analyze_eis(dataset)
            elif dataset.get_column("time") is not None and dataset.get_column("potential") is not None:
                # Could be GCD (time vs potential at constant current)
                result["technique"] = "GCD"
                result["gcd_analysis"] = self._analyze_gcd(dataset)
            elif dataset.get_column("potential") is not None:
                result["technique"] = "DPV"
                result["dpv_analysis"] = self.analyze_dpv(dataset)
            elif dataset.get_column("Wave") is not None:
                result["technique"] = "Raman"
                result["raman_analysis"] = self.analyze_raman(dataset)

        # Add plot data for any technique
        result["plot_data"] = self._extract_plot_data(dataset)
        result["num_points"] = dataset.num_points
        return result

    def _analyze_gcd(self, dataset) -> Dict[str, Any]:
        """Run GCD analysis on the dataset."""
        from src.backend.core.gcd_analyzer import get_gcd_analyzer
        analyzer = get_gcd_analyzer()
        return analyzer.analyze_from_dataset(dataset)

    def _extract_plot_data(self, dataset) -> Dict[str, list]:
        """Extract raw x,y plot data for frontend charting."""
        data = {}
        for col in dataset.columns:
            data[col.name] = col.data.tolist()
        return data


# Module API
_analyzer: Optional[LabDataAnalyzer] = None


def get_analyzer() -> LabDataAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = LabDataAnalyzer()
    return _analyzer
