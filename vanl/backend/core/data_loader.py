"""
External EIS Data Loader
==========================
Utilities for loading and processing real-world EIS datasets
for model validation and calibration.

Supported datasets:
    - Perovskite EIS (from literature)
    - Custom CSV files with (frequency, Z_real, Z_imag) columns
"""

import os
import csv
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

DATASETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "datasets", "external")


@dataclass
class ExternalEISData:
    """Parsed external EIS measurement."""
    name: str
    frequencies: np.ndarray
    Z_real: np.ndarray
    Z_imag: np.ndarray
    temperature: Optional[float] = None
    metadata: Optional[dict] = None

    @property
    def Z_magnitude(self) -> np.ndarray:
        return np.sqrt(self.Z_real**2 + self.Z_imag**2)

    @property
    def Z_phase(self) -> np.ndarray:
        return np.degrees(np.arctan2(self.Z_imag, self.Z_real))


def load_perovskite_eis(
    filepath: Optional[str] = None,
    temperature_filter: Optional[float] = None,
) -> List[ExternalEISData]:
    """
    Load perovskite EIS dataset.

    Columns: Ionic_radius, Temperature, Frequency, Re(Z), Img(Z)

    Args:
        filepath: Path to CSV. Defaults to bundled dataset.
        temperature_filter: If set, only return data for this temperature.

    Returns:
        List of ExternalEISData grouped by (ionic_radius, temperature).
    """
    if filepath is None:
        filepath = os.path.join(DATASETS_DIR, "eis_perovskites.csv")

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset not found: {filepath}")

    # Parse CSV
    data_groups = {}
    with open(filepath, "r") as f:
        reader = csv.reader(f)
        header = next(reader)

        for row in reader:
            try:
                ionic_radius = float(row[0])
                temp = float(row[1])
                freq = float(row[2])
                z_real = float(row[3])
                z_imag = float(row[4])
            except (ValueError, IndexError):
                continue

            if temperature_filter is not None and temp != temperature_filter:
                continue

            key = (ionic_radius, temp)
            if key not in data_groups:
                data_groups[key] = {"freqs": [], "z_real": [], "z_imag": []}
            data_groups[key]["freqs"].append(freq)
            data_groups[key]["z_real"].append(z_real)
            data_groups[key]["z_imag"].append(z_imag)

    results = []
    for (radius, temp), group in sorted(data_groups.items()):
        # Sort by frequency
        idx = np.argsort(group["freqs"])
        results.append(ExternalEISData(
            name=f"Perovskite r={radius:.2e} T={temp}°C",
            frequencies=np.array(group["freqs"])[idx],
            Z_real=np.array(group["z_real"])[idx],
            Z_imag=np.array(group["z_imag"])[idx],
            temperature=temp,
            metadata={"ionic_radius": radius, "source": "perovskite_dataset"},
        ))

    logger.info("Loaded %d EIS spectra from %s", len(results), filepath)
    return results


def load_custom_csv(
    filepath: str,
    freq_col: int = 0,
    z_real_col: int = 1,
    z_imag_col: int = 2,
    skip_header: bool = True,
    name: Optional[str] = None,
) -> ExternalEISData:
    """
    Load a single EIS spectrum from a CSV file.

    Args:
        filepath: Path to CSV
        freq_col, z_real_col, z_imag_col: Column indices
        skip_header: Whether to skip the first row
        name: Optional name for the dataset

    Returns:
        ExternalEISData object
    """
    freqs, z_real, z_imag = [], [], []

    with open(filepath, "r") as f:
        reader = csv.reader(f)
        if skip_header:
            next(reader)

        for row in reader:
            try:
                freqs.append(float(row[freq_col]))
                z_real.append(float(row[z_real_col]))
                z_imag.append(float(row[z_imag_col]))
            except (ValueError, IndexError):
                continue

    idx = np.argsort(freqs)
    return ExternalEISData(
        name=name or os.path.basename(filepath),
        frequencies=np.array(freqs)[idx],
        Z_real=np.array(z_real)[idx],
        Z_imag=np.array(z_imag)[idx],
    )


def list_available_datasets() -> List[str]:
    """List available external datasets."""
    if not os.path.isdir(DATASETS_DIR):
        return []
    return [f for f in os.listdir(DATASETS_DIR) if f.endswith('.csv')]
