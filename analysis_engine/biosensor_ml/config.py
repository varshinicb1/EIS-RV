"""Central configuration — all paths and physical constants."""
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[1]
DATA_RAW    = Path("/Users/bahumanyarg/Downloads/fog differet data for aiml")
DATA_PROC   = ROOT / "data" / "processed"
DATA_FEAT   = ROOT / "data" / "features"
MODELS_DIR  = ROOT / "models"
FIG_DIR     = ROOT / "reports" / "figures"
CSV_DIR     = ROOT / "reports" / "plot_csvs"
MLRUNS_DIR  = ROOT / "mlruns"

for d in [DATA_PROC, DATA_FEAT, MODELS_DIR, FIG_DIR, CSV_DIR, MLRUNS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Raw file paths ─────────────────────────────────────────────────────────────
DPV_FILE        = DATA_RAW / "DPV UA FOG EDITTED FINAL.xlsx"
CALIB_FILE      = DATA_RAW / "FOG UA CALIBRATION CURVE.xlsx"
EIS_FILES       = {
    "Bare GCE":   DATA_RAW / "EIS BARE GCE.xlsx",
    "Fe2O3/GCE":  DATA_RAW / "EIS FERRIC OXIDE.xlsx",
    "rGO/GCE":    DATA_RAW / "EIS rGO.xlsx",
    "FOG/GCE":    DATA_RAW / "EIS FOG.xlsx",
}
GOMUTRA_FILE    = DATA_RAW / "GOMUTRA CONCN STUDY FINAL.xlsx"
PH_FILE         = DATA_RAW / "pH study.xlsx"

# ── Electrochemical constants ──────────────────────────────────────────────────
UA_PEAK_V       = 0.475   # V vs Ag/AgCl — UA oxidation peak (from manuscript)
SCAN_RATE_CV    = 0.050   # V/s (50 mV/s, main CV scan rate)
GCE_DIAMETER_MM = 3.0     # mm — standard GCE (resolves manuscript ambiguity)
GCE_AREA_CM2    = 3.14159 * (GCE_DIAMETER_MM / 20.0) ** 2  # cm²

# EIS Randles parameters (initial guesses)
EIS_P0 = {
    "Rs":    10.0,   # Ω
    "Rct":   1000.0, # Ω
    "Q":     1e-6,   # CPE admittance Y0
    "n":     0.85,   # CPE exponent (0=R, 1=C)
    "sigma": 100.0,  # Warburg coefficient
}

# ── Figure style ──────────────────────────────────────────────────────────────
import matplotlib
matplotlib.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         11,
    "axes.labelsize":    12,
    "axes.titlesize":    12,
    "xtick.labelsize":   10,
    "ytick.labelsize":   10,
    "legend.fontsize":   9,
    "figure.dpi":        150,
    "savefig.dpi":       800,
    "savefig.bbox":      "tight",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "lines.linewidth":   1.8,
    "axes.linewidth":    1.0,
})

COLORS = {
    "Bare GCE":  "#555555",
    "Fe2O3/GCE": "#E05C3A",
    "rGO/GCE":   "#3A7EC0",
    "FOG/GCE":   "#2BA84A",
    "buffer":    "#888888",
}
CONC_CMAP = "plasma"
