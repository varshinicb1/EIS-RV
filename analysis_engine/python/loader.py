"""
loader.py - CV data ingestion and cleaning.

The input files used by the app store cyclic voltammetry loops in acquisition
order. A full CV loop contains repeated potentials on the forward/reverse
sweeps, so sorting the whole file by potential corrupts the waveform. This
module keeps the raw loop intact, splits it into monotonic branches, and only
interpolates within a selected branch for potential-resolved kinetics.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class CVBranch:
    name: str
    direction: str
    start_idx: int
    end_idx: int
    potential: np.ndarray
    currents: np.ndarray


@dataclass(frozen=True)
class CVDataset:
    potential_raw: np.ndarray
    currents_raw: np.ndarray
    scan_rates: list[float]
    branches: list[CVBranch]


def _read_numeric_cv(filepath: str) -> tuple[np.ndarray, np.ndarray, list[float]]:
    """
    Load a CV CSV/Excel file and return (potential, currents_matrix, scan_rates).

    Accepted CSV layouts:
        Row 1: "POTENTIAL", "CURRENT", ...   (header labels, mostly ignored)
        Row 2: "", 10, 20, 30, ...           (scan rates in mV/s)
        Row 3: empty / blank
        Row 4+: -0.499, I1, I2, I3, ...     (data rows)

    and common instrument exports such as:
        Row 1: "Potential", 10, 20, 30, ...
        Row 2: empty / blank
        Row 3+: -0.499, I1, I2, I3, ...

        Trailing rows may be '--' placeholders

    Returns
    -------
    potential : np.ndarray, shape (N,)
        Voltage values in V (sorted ascending for clean interpolation)
    currents  : np.ndarray, shape (N, M)
        Current matrix; currents[:, j] corresponds to scan_rates[j]
    scan_rates : list of float
        Scan rates in mV/s, corresponding to columns of currents
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    # ── Read raw, no header parsing ──────────────────────────────────────
    if ext in (".xlsx", ".xls"):
        raw = pd.read_excel(filepath, header=None, dtype=str)
    else:
        raw = pd.read_csv(filepath, header=None, dtype=str)

    def parse_float(value) -> float | None:
        text = str(value).strip()
        if text == "" or text.lower() == "nan" or text in {"--", "-"}:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    # ── Locate the scan-rate row robustly ────────────────────────────────
    # Different potentiostat/export templates place scan rates either on the
    # second row (after a text header) or directly beside the Potential label.
    # A scan-rate row has a non-numeric/empty first cell and at least two
    # contiguous numeric cells from column 2 onward.
    scan_idx = None
    scan_rates: list[float] = []
    for idx in range(min(10, len(raw))):
        first = parse_float(raw.iloc[idx, 0]) if raw.shape[1] else None
        if first is not None:
            continue
        row_rates = []
        for val in raw.iloc[idx, 1:]:
            parsed = parse_float(val)
            if parsed is None:
                break
            row_rates.append(parsed)
        if len(row_rates) >= 2:
            scan_idx = idx
            scan_rates = row_rates
            break

    if scan_idx is None or not scan_rates:
        raise ValueError("Could not parse scan rates from the file header.")

    # ── Extract scan rates from the located header row ───────────────────
    scan_rate_row = raw.iloc[scan_idx, 1:]  # skip first column (label)
    scan_rates = []
    for val in scan_rate_row:
        v = parse_float(val)
        if v is None:
            break  # stop at first non-numeric
        scan_rates.append(v)

    n_rates = len(scan_rates)

    # ── Extract data rows after the scan-rate row ─────────────────────────
    data_rows = raw.iloc[scan_idx + 1 :]

    potentials = []
    currents_list = []

    for _, row in data_rows.iterrows():
        # Skip rows that are empty or contain '--' placeholders
        pot = parse_float(row.iloc[0])
        if pot is None:
            continue

        # Collect leading valid current values; stop at first None/missing
        # (handles trailing commas in files that have fewer data columns
        # than scan rates listed in the header, e.g. Windows CSV exports)
        curr_row = []
        for j in range(n_rates):
            col_idx = j + 1
            if col_idx >= len(row):
                break
            current = parse_float(row.iloc[col_idx])
            if current is None:
                break
            curr_row.append(current)

        if len(curr_row) >= 2:
            potentials.append(pot)
            currents_list.append(curr_row)

    if len(potentials) < 10:
        raise ValueError(
            f"Too few valid data rows found ({len(potentials)}). "
            "Check file format."
        )

    # ── Reconcile rows that may have different column counts ──────────────
    # (e.g. trailing-comma files where the last scan-rate column is blank)
    # Use the most common column count that covers ≥90% of rows; trim others.
    from collections import Counter
    col_counts = Counter(len(r) for r in currents_list)
    effective_cols = col_counts.most_common(1)[0][0]
    # Filter rows to only those with the effective column count
    paired = [(p, c) for p, c in zip(potentials, currents_list) if len(c) == effective_cols]
    if len(paired) < 10:
        # Fall back: use all rows trimmed to the minimum column count
        min_cols = min(len(c) for c in currents_list)
        paired = [(p, c[:min_cols]) for p, c in zip(potentials, currents_list)]
    potentials = [p for p, _ in paired]
    currents_list = [c for _, c in paired]
    # Trim scan_rates to match actual column count
    effective_n = len(currents_list[0])
    scan_rates = scan_rates[:effective_n]

    potential = np.array(potentials, dtype=float)
    currents = np.array(currents_list, dtype=float)

    return potential, currents, scan_rates


def _unique_average(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Collapse duplicate potentials by averaging their current rows."""
    order = np.argsort(x)
    xs = x[order]
    ys = y[order]
    unique, inverse = np.unique(xs, return_inverse=True)
    if len(unique) == len(xs):
        return xs, ys

    out = np.zeros((len(unique), ys.shape[1]), dtype=float)
    counts = np.bincount(inverse).astype(float)
    for col in range(ys.shape[1]):
        out[:, col] = np.bincount(inverse, weights=ys[:, col]) / counts
    return unique, out


def _resample_branch(
    potential: np.ndarray,
    currents: np.ndarray,
    n_points: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return an ascending, uniformly spaced potential grid for one branch."""
    x, y = _unique_average(potential, currents)
    if len(x) < 2:
        raise ValueError("A CV branch must contain at least two unique potentials.")

    n_points = n_points or len(x)
    grid = np.linspace(float(x[0]), float(x[-1]), int(n_points))
    resampled = np.zeros((len(grid), y.shape[1]), dtype=float)
    for j in range(y.shape[1]):
        resampled[:, j] = np.interp(grid, x, y[:, j])
    return grid, resampled


def split_cv_branches(
    potential: np.ndarray,
    currents: np.ndarray,
    min_points: int = 25,
) -> list[CVBranch]:
    """
    Split a CV loop into monotonic branches.

    Short startup nudges are merged/ignored, which handles files that start one
    row away from the switching potential.
    """
    if len(potential) != len(currents):
        raise ValueError("Potential and current arrays have different lengths.")
    if len(potential) < min_points:
        raise ValueError("Too few points to split CV branches.")

    diffs = np.diff(potential)
    eps = max(float(np.nanmax(np.abs(diffs))) * 1e-6, 1e-12)
    signs = np.sign(np.where(np.abs(diffs) <= eps, 0.0, diffs))

    nonzero_idx = np.flatnonzero(signs)
    if len(nonzero_idx) == 0:
        raise ValueError("Potential is constant; cannot identify CV branches.")

    turns = [0]
    prev_sign = signs[nonzero_idx[0]]
    for idx in nonzero_idx[1:]:
        sign = signs[idx]
        if sign != prev_sign:
            turns.append(idx)
            prev_sign = sign
    turns.append(len(potential) - 1)

    branches: list[CVBranch] = []
    for start, end in zip(turns[:-1], turns[1:]):
        if end - start + 1 < min_points:
            continue
        p = potential[start : end + 1]
        c = currents[start : end + 1, :]
        direction = "forward" if p[-1] >= p[0] else "reverse"
        branch_name = f"{direction}_{len([b for b in branches if b.direction == direction]) + 1}"
        branches.append(CVBranch(branch_name, direction, start, end, p, c))

    if not branches:
        p = potential
        direction = "forward" if p[-1] >= p[0] else "reverse"
        branches.append(CVBranch(f"{direction}_1", direction, 0, len(p) - 1, p, currents))

    return branches


def load_cv_dataset(filepath: str) -> CVDataset:
    """Load raw CV data and detected loop branches without flattening the loop."""
    potential, currents, scan_rates = _read_numeric_cv(filepath)
    branches = split_cv_branches(potential, currents)
    return CVDataset(potential, currents, scan_rates, branches)


def select_branch(dataset: CVDataset, branch: str = "forward") -> CVBranch:
    """Select a branch by name or direction, falling back to the longest branch."""
    branch = branch.lower()
    for item in dataset.branches:
        if item.name.lower() == branch or item.direction.lower() == branch:
            return item
    return max(dataset.branches, key=lambda b: len(b.potential))


def load_cv_file(
    filepath: str,
    branch: str = "forward",
    n_points: int | None = None,
) -> tuple[np.ndarray, np.ndarray, list[float]]:
    """
    Load a CV CSV/Excel file and return one clean monotonic branch.

    The raw loop is preserved by ``load_cv_dataset``. This compatibility helper
    returns the selected branch on an ascending uniform potential grid for
    b-value, Dunn, PCA, and other potential-resolved analyses.
    """
    dataset = load_cv_dataset(filepath)
    selected = select_branch(dataset, branch=branch)
    potential, currents = _resample_branch(
        selected.potential,
        selected.currents,
        n_points=n_points,
    )

    return potential, currents, dataset.scan_rates
