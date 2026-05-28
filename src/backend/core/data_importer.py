"""
RĀMAN Studio — Multi-Format Data Importer
===========================================
Addresses the #1 pain point: proprietary potentiostat data formats.

Supports:
  - CSV (generic, Gamry, CH Instruments)
  - .dta (Gamry DTA text-based format)
  - .mpt (BioLogic EC-Lab format)
  - .z   (ZView/Scribner impedance format)
  - .txt (tab/space delimited)
  - .json (RĀMAN Studio native)

Each parser returns a standardized dict:
  {
    "format": "gamry_dta",
    "data_type": "EIS" | "CV" | "GCD" | "Battery" | "Unknown",
    "headers": ["col1", "col2", ...],
    "columns": {"col1": [...], "col2": [...]},
    "metadata": {...},
    "n_rows": int,
    "n_cols": int,
  }
"""

import re
import json
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_file(file_content: str, filename: str = "") -> Dict[str, Any]:
    """
    Auto-detect file format and parse accordingly.
    """
    ext = Path(filename).suffix.lower() if filename else ""

    if ext == ".json":
        return _parse_json(file_content)
    elif ext == ".dta":
        return _parse_gamry_dta(file_content)
    elif ext == ".mpt":
        return _parse_biologic_mpt(file_content)
    elif ext == ".z":
        return _parse_zview_z(file_content)
    else:
        # Try auto-detect
        if file_content.strip().startswith("{") or file_content.strip().startswith("["):
            return _parse_json(file_content)
        if "EXPLAIN" in file_content[:500] or "CURVE" in file_content[:500]:
            return _parse_gamry_dta(file_content)
        if "EC-Lab" in file_content[:200] or "BioLogic" in file_content[:200]:
            return _parse_biologic_mpt(file_content)
        if "ZView" in file_content[:200] or "Z'" in file_content[:200]:
            return _parse_zview_z(file_content)
        return _parse_csv(file_content)


def _parse_csv(text: str) -> Dict[str, Any]:
    """Parse generic CSV/TSV data."""
    lines = text.strip().split("\n")
    # Skip comment lines
    data_lines = [l for l in lines if l.strip() and not l.startswith("#") and not l.startswith("%")]
    if len(data_lines) < 2:
        return {"error": "File contains less than 2 data lines"}

    # Detect separator
    first_line = data_lines[0]
    if "\t" in first_line:
        sep = "\t"
    elif ";" in first_line:
        sep = ";"
    else:
        sep = ","

    headers = [h.strip().strip('"').strip("'") for h in data_lines[0].split(sep)]
    columns = {h: [] for h in headers}
    valid_rows = 0

    for line in data_lines[1:]:
        parts = line.split(sep)
        if len(parts) != len(headers):
            continue
        try:
            values = [float(v.strip().strip('"')) for v in parts]
            for h, v in zip(headers, values):
                columns[h].append(v)
            valid_rows += 1
        except ValueError:
            continue

    return {
        "format": "csv",
        "data_type": _guess_data_type(headers),
        "headers": headers,
        "columns": columns,
        "metadata": {},
        "n_rows": valid_rows,
        "n_cols": len(headers),
    }


def _parse_gamry_dta(text: str) -> Dict[str, Any]:
    """
    Parse Gamry .dta text format.
    Gamry DTA files have header sections starting with EXPLAIN, NOTES, CURVE, etc.
    Data starts after the TABLExx header.
    """
    lines = text.strip().split("\n")
    metadata = {}
    headers = []
    columns = {}
    in_data = False
    header_line_idx = -1

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Extract metadata from EXPLAIN section
        if stripped.startswith("LABEL"):
            parts = stripped.split("\t")
            if len(parts) >= 2:
                metadata["label"] = parts[1].strip()
        elif stripped.startswith("DATE"):
            parts = stripped.split("\t")
            if len(parts) >= 2:
                metadata["date"] = parts[1].strip()
        elif stripped.startswith("NOTES"):
            parts = stripped.split("\t")
            if len(parts) >= 2:
                metadata["notes"] = parts[1].strip()

        # Detect data table start (Pt, T, Vf, Im, ... or similar headers)
        if stripped.startswith("Pt\t") or stripped.startswith("#\tPt\t"):
            headers = [h.strip() for h in stripped.replace("#\t", "").split("\t")]
            columns = {h: [] for h in headers}
            in_data = True
            # Skip units line if present
            header_line_idx = i
            continue

        if in_data and i > header_line_idx + 1:  # Skip the units row
            parts = stripped.split("\t")
            if len(parts) == len(headers):
                try:
                    values = [float(v) for v in parts]
                    for h, v in zip(headers, values):
                        columns[h].append(v)
                except ValueError:
                    continue

    n_rows = len(columns[headers[0]]) if headers else 0

    # Auto-detect data type from headers
    data_type = "Unknown"
    h_lower = [h.lower() for h in headers]
    if any("zreal" in h or "zre" in h or "z'" in h for h in h_lower):
        data_type = "EIS"
    elif any("im" in h for h in h_lower) and any("vf" in h for h in h_lower):
        data_type = "CV"

    return {
        "format": "gamry_dta",
        "data_type": data_type,
        "headers": headers,
        "columns": columns,
        "metadata": metadata,
        "n_rows": n_rows,
        "n_cols": len(headers),
    }


def _parse_biologic_mpt(text: str) -> Dict[str, Any]:
    """
    Parse BioLogic EC-Lab .mpt format.
    MPT files have a header section with "Nb header lines" indicating
    how many lines to skip before data.
    """
    lines = text.strip().split("\n")
    metadata = {}
    skip_lines = 0

    for line in lines[:50]:  # Only check first 50 lines for header
        if "Nb header lines" in line:
            try:
                skip_lines = int(line.split(":")[-1].strip())
            except ValueError:
                pass
        if "Acquisition started on" in line:
            metadata["acquisition_date"] = line.split(":")[-1].strip()
        if "Technique" in line:
            metadata["technique"] = line.split(":")[-1].strip()

    if skip_lines == 0:
        # Fallback: find the header line by looking for tab-separated column names
        for i, line in enumerate(lines):
            if "\t" in line and not line.startswith("EC-Lab"):
                skip_lines = i
                break

    if skip_lines >= len(lines):
        return {"error": "Could not find data section in .mpt file"}

    # Parse headers
    header_line = lines[skip_lines] if skip_lines < len(lines) else ""
    headers = [h.strip() for h in header_line.split("\t") if h.strip()]

    columns = {h: [] for h in headers}
    valid_rows = 0

    for line in lines[skip_lines + 1:]:
        parts = line.split("\t")
        if len(parts) != len(headers):
            continue
        try:
            values = [float(v.strip()) for v in parts]
            for h, v in zip(headers, values):
                columns[h].append(v)
            valid_rows += 1
        except ValueError:
            continue

    return {
        "format": "biologic_mpt",
        "data_type": _guess_data_type(headers),
        "headers": headers,
        "columns": columns,
        "metadata": metadata,
        "n_rows": valid_rows,
        "n_cols": len(headers),
    }


def _parse_zview_z(text: str) -> Dict[str, Any]:
    """
    Parse ZView .z impedance data format.
    These files typically have:
    - Header lines starting with 'ZView' or comment markers
    - Column headers: freq, Z', Z'', etc.
    - Tab or space-separated data
    """
    lines = text.strip().split("\n")
    data_start = 0
    headers = []

    # Find column header line
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith("z'") or "freq" in stripped.lower():
            # This looks like the column headers
            headers = re.split(r"[\t,]+", stripped)
            headers = [h.strip().strip('"') for h in headers if h.strip()]
            data_start = i + 1
            break
        elif i > 20:
            break

    if not headers:
        # Try treating as simple 3-column data (freq, Z', Z'')
        headers = ["Frequency_Hz", "Z_real", "Z_imag"]
        data_start = 0
        for i, line in enumerate(lines):
            parts = line.strip().split()
            if len(parts) >= 3:
                try:
                    [float(v) for v in parts[:3]]
                    data_start = i
                    break
                except ValueError:
                    continue

    columns = {h: [] for h in headers}
    valid_rows = 0

    for line in lines[data_start:]:
        parts = re.split(r"[\t,\s]+", line.strip())
        if len(parts) < len(headers):
            continue
        try:
            values = [float(v) for v in parts[:len(headers)]]
            for h, v in zip(headers, values):
                columns[h].append(v)
            valid_rows += 1
        except ValueError:
            continue

    return {
        "format": "zview_z",
        "data_type": "EIS",
        "headers": headers,
        "columns": columns,
        "metadata": {"source": "ZView/Scribner"},
        "n_rows": valid_rows,
        "n_cols": len(headers),
    }


def _parse_json(text: str) -> Dict[str, Any]:
    """Parse JSON data (RĀMAN Studio native format)."""
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "headers" in data and "columns" in data:
            return {
                "format": "raman_json",
                "data_type": data.get("data_type", "Unknown"),
                "headers": data["headers"],
                "columns": data["columns"],
                "metadata": data.get("metadata", {}),
                "n_rows": len(next(iter(data["columns"].values()), [])),
                "n_cols": len(data["headers"]),
            }
        return {"error": "JSON does not match expected format", "raw": data}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}


def _guess_data_type(headers: List[str]) -> str:
    """Guess the electrochemical technique from column headers."""
    h = [s.lower().replace("'", "").replace('"', '') for s in headers]

    if any("zreal" in s or "zre" in s or "z'" in s or "z_real" in s for s in h):
        return "EIS"
    if any("freq" in s for s in h) and any("z" in s for s in h):
        return "EIS"
    if any("potential" in s or "e_v" in s or "ewe" in s for s in h):
        if any("current" in s or "i_" in s or "<i>" in s for s in h):
            return "CV"
    if any("capacity" in s or "soc" in s or "q_" in s for s in h):
        return "Battery"
    if any("time" in s for s in h) and any("voltage" in s or "ecell" in s for s in h):
        return "GCD"
    return "Unknown"


def get_supported_formats() -> List[Dict[str, str]]:
    """Return list of all supported file formats."""
    return [
        {"ext": ".csv", "desc": "Comma/tab/semicolon-separated values (generic)"},
        {"ext": ".dta", "desc": "Gamry DTA format (text section)"},
        {"ext": ".mpt", "desc": "BioLogic EC-Lab MPT format"},
        {"ext": ".z", "desc": "ZView / Scribner impedance format"},
        {"ext": ".txt", "desc": "Tab/space delimited text data"},
        {"ext": ".json", "desc": "RĀMAN Studio JSON export"},
    ]
