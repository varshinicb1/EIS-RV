"""
Script 01 — Data Ingestion
Loads all raw Excel files from the updated 'fog differet data for aiml' folder.
New file structures vs previous run:
  DPV  : row 0 = col-type header, row 1 = concentration labels, data rows 2-53
         current now in µA (previously raw instrument units)
  CALIB: brand-new dedicated calibration curve ([UA] in M, current in A)
  Gomutra / pH: same row-offset structure as before, new final files
  EIS  : unchanged format
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from config import (DATA_PROC, DPV_FILE, CALIB_FILE, EIS_FILES,
                    GOMUTRA_FILE, PH_FILE)


# ── 1. DPV ────────────────────────────────────────────────────────────────────
def load_dpv() -> pd.DataFrame:
    """
    New layout (DPV UA FOG EDITTED FINAL.xlsx):
      Row 0: col-type headers ('potential (V)', 'current (µA)', ...)
      Row 1: concentration labels (None, '1 µM', None, '5 µM', ..., None, 'BUFFER')
      Rows 2-53: 52 data points per condition
    10 conditions: 1, 5, 10, 20, 30, 40, 50, 60, 70 µM + BUFFER
    Current unit: µA  (stored as µA in the CSV for consistency)
    """
    raw = pd.read_excel(DPV_FILE, sheet_name="Sheet1",
                        header=None, engine="openpyxl")

    label_row = raw.iloc[1]           # row 1 = concentration labels
    data      = raw.iloc[2:].reset_index(drop=True).astype(float)

    col_map = {}
    current_label = None
    for i, val in enumerate(label_row):
        if pd.notna(val):
            s = str(val).strip()
            s = s.replace("µm", "µM").replace("um", "µM")
            current_label = s
            col_map[i] = (current_label, "current")
        else:
            col_map[i] = (current_label, "potential")

    records = []
    for i in range(0, 20, 2):
        j     = i + 1
        label = col_map[j][0]
        if label is None:
            continue
        conc = 0.0 if label.upper() == "BUFFER" else \
               float(label.replace("µM", "").replace("µm", "").strip())
        pot = data.iloc[:, i].values
        cur = data.iloc[:, j].values          # already in µA
        for k in range(len(pot)):
            records.append({
                "concentration_uM": conc,
                "label":            label,
                "potential_V":      round(float(pot[k]), 6),
                "current_uA":       float(cur[k]),
            })

    df = pd.DataFrame(records)
    df = df.sort_values(["concentration_uM", "potential_V"]).reset_index(drop=True)
    df.to_csv(DATA_PROC / "dpv_clean.csv", index=False)
    print(f"  DPV  → {len(df)} rows, {df['concentration_uM'].nunique()} conditions "
          f"  [V: {df.potential_V.min():.3f}–{df.potential_V.max():.3f}]  "
          f"  [I: {df.current_uA.min():.4f}–{df.current_uA.max():.4f} µA]")
    return df


# ── 2. Calibration curve (NEW) ────────────────────────────────────────────────
def load_calibration_curve() -> pd.DataFrame:
    """
    FOG UA CALIBRATION CURVE.xlsx:
      Col A: [UA] M   (Molar concentrations)
      Col B: current A  (Amperes)
    9 points: 10, 50, 100, 200, 300, 400, 500, 600, 700 µM
    Converts to µM and µA for pipeline consistency.
    """
    raw = pd.read_excel(CALIB_FILE, header=0, engine="openpyxl")
    raw.columns = ["conc_M", "current_A"]
    raw = raw.dropna()
    raw["concentration_uM"] = raw["conc_M"] * 1e6
    raw["current_uA"]       = raw["current_A"] * 1e6
    df = raw[["concentration_uM", "current_uA"]].reset_index(drop=True)
    df.to_csv(DATA_PROC / "calib_curve.csv", index=False)
    print(f"  Calib→ {len(df)} points  "
          f"[{df.concentration_uM.min():.0f}–{df.concentration_uM.max():.0f} µM]  "
          f"[{df.current_uA.min()*1000:.3f}–{df.current_uA.max()*1000:.3f} nA]")
    return df


# ── 3. EIS ────────────────────────────────────────────────────────────────────
def load_eis() -> pd.DataFrame:
    """
    Each file: rows 1-17 metadata; data from row 18.
    5 columns: Freq/Hz, Z'/ohm, Z"/ohm, Z/ohm, Phase/deg  (unchanged format).
    """
    frames = []
    for electrode, path in EIS_FILES.items():
        df = pd.read_excel(path, header=None, skiprows=17,
                           names=["freq_Hz", "Zreal_ohm", "Zimag_ohm",
                                  "Zmag_ohm", "phase_deg"],
                           engine="openpyxl")
        df = df.dropna(subset=["freq_Hz"]).copy()
        df["electrode"] = electrode
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)
    for c in ["freq_Hz", "Zreal_ohm", "Zimag_ohm", "Zmag_ohm", "phase_deg"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna()
    out.to_csv(DATA_PROC / "eis_clean.csv", index=False)
    for name, grp in out.groupby("electrode"):
        print(f"  EIS  {name:12s} → {len(grp)} freq points  "
              f"Zreal: {grp.Zreal_ohm.min():.1f}–{grp.Zreal_ohm.max():.1f} Ω")
    return out


# ── 4. Gomutra ────────────────────────────────────────────────────────────────
def load_gomutra() -> pd.DataFrame:
    """
    GOMUTRA CONCN STUDY FINAL.xlsx:
      Row 0: POTENTIAL (V), Current (A) headers
      Row 1: volume labels (None, 'Buffer', None, '10 µl', ...)
      Rows 2-201: 200 data rows, current in A
    12 conditions: Buffer + 10, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500 µL
    """
    raw = pd.read_excel(GOMUTRA_FILE, sheet_name="Sheet1",
                        header=None, engine="openpyxl")
    vol_labels_row = raw.iloc[1]
    data = raw.iloc[2:].reset_index(drop=True).astype(float)

    vol_map = {}
    for i in range(0, 24, 2):
        label = str(vol_labels_row.iloc[i+1]).strip() \
                if pd.notna(vol_labels_row.iloc[i+1]) else \
                str(vol_labels_row.iloc[i]).strip()
        vol_map[i] = label

    records = []
    for i in range(0, 24, 2):
        label = vol_map[i]
        vol_uL = 0.0 if label.lower() == "buffer" else \
                 float(label.replace("µl", "").replace("ul", "")
                             .replace("µL", "").strip())
        pot = data.iloc[:, i].values
        cur = data.iloc[:, i+1].values
        for k in range(len(pot)):
            records.append({
                "volume_uL":   vol_uL,
                "label":       label,
                "potential_V": float(pot[k]),
                "current_A":   float(cur[k]),
                "row_idx":     k,
            })

    df = pd.DataFrame(records)
    df.to_csv(DATA_PROC / "gomutra_clean.csv", index=False)
    print(f"  Gomutra → {len(df)} rows, {df['volume_uL'].nunique()} conditions  "
          f"vols: {sorted(df.volume_uL.unique())}")
    return df


# ── 5. pH study ───────────────────────────────────────────────────────────────
def load_ph() -> pd.DataFrame:
    """
    pH study.xlsx:
      Row 0: Potential (V), Current (A) col headers
      Row 1: pH labels (None, 'pH 4', None, 'pH 5', ...)
      Rows 2-201: 200 data rows, current in A
    6 conditions: pH 4–9
    pH 8 stored in reversed sweep direction → sort by potential.
    """
    raw = pd.read_excel(PH_FILE, sheet_name="Sheet1",
                        header=None, engine="openpyxl")
    ph_labels_row = raw.iloc[1]
    data = raw.iloc[2:].reset_index(drop=True).astype(float)

    records = []
    for i in range(0, 12, 2):
        label = str(ph_labels_row.iloc[i+1]).strip() \
                if pd.notna(ph_labels_row.iloc[i+1]) else \
                str(ph_labels_row.iloc[i]).strip()
        ph_val = float(label.replace("pH", "").strip())
        pot = data.iloc[:, i].values
        cur = data.iloc[:, i+1].values
        for k in range(len(pot)):
            records.append({
                "pH":          ph_val,
                "potential_V": float(pot[k]),
                "current_A":   float(cur[k]),
                "row_idx":     k,
            })

    df = pd.DataFrame(records)
    df = df.sort_values(["pH", "potential_V"]).reset_index(drop=True)
    df.to_csv(DATA_PROC / "ph_clean.csv", index=False)
    print(f"  pH   → {len(df)} rows, pH values: {sorted(df.pH.unique())}")
    return df


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("STEP 01 — Ingesting raw data (fog differet data for aiml)")
    print("=" * 60)
    dpv   = load_dpv()
    calib = load_calibration_curve()
    eis   = load_eis()
    gom   = load_gomutra()
    ph    = load_ph()
    print("\nAll raw data ingested → data/processed/")

    assert dpv["concentration_uM"].nunique() == 10, "Expected 10 DPV conditions"
    assert len(dpv[dpv.concentration_uM > 0].concentration_uM.unique()) == 9, \
        "Expected 9 UA concentrations"
    assert len(calib) == 9, "Expected 9 calibration curve points"
    assert eis["electrode"].nunique() == 4, "Expected 4 EIS electrodes"
    assert gom["volume_uL"].nunique() == 12, "Expected 12 Gomutra conditions"
    assert ph["pH"].nunique() == 6, "Expected 6 pH values"
    print("\n✓ All sanity checks passed")
