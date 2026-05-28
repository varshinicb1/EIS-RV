"""
analysis.py — Electrochemical CV analysis routines
All methods follow standard literature implementations.

References:
  - b-value: Dunn et al., ACS Nano 2015; Wang et al., Nature Chem 2007
  - Dunn decomposition: i(V,v) = k1*v + k2*sqrt(v)
  - Peak detection: scipy.signal with electrochemical conventions
  - PCA: standard sklearn decomposition
"""

import warnings
import numpy as np
from scipy.signal import find_peaks, savgol_filter
from scipy.stats import linregress
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


# ══════════════════════════════════════════════════════════════════════════════
#  b-VALUE ANALYSIS
#  log(i) = log(a) + b*log(v)  at each potential point
#  b ≈ 1 → surface capacitive; b ≈ 0.5 → semi-infinite diffusion
# ══════════════════════════════════════════════════════════════════════════════

def compute_b_values(
    potential: np.ndarray,
    currents: np.ndarray,
    scan_rates: list[float],
    min_points: int = 3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute b-values at every potential point via log-log linear regression.

    Parameters
    ----------
    potential   : (N,) array of potential values
    currents    : (N, M) array; currents[:, j] for scan_rates[j]
    scan_rates  : list of M scan rates [mV/s]
    min_points  : minimum valid log-log points required for a fit

    Returns
    -------
    b_values    : (N,) slope from log(|i|) vs log(v)
    r_squared   : (N,) R² of each fit
    log_a       : (N,) intercept (log of pre-factor a)
    """
    scan_rates = np.array(scan_rates, dtype=float)
    log_v = np.log(scan_rates)

    n_pts = len(potential)
    b_values = np.full(n_pts, np.nan)
    r_squared = np.full(n_pts, np.nan)
    log_a = np.full(n_pts, np.nan)

    for i in range(n_pts):
        i_row = currents[i, :]
        # Use absolute current; filter out zeros to avoid log(0)
        valid = np.abs(i_row) > 1e-15
        if valid.sum() < min_points:
            continue

        log_i = np.log(np.abs(i_row[valid]))
        lv = log_v[valid]

        slope, intercept, r, _, _ = linregress(lv, log_i)
        b_values[i] = slope
        r_squared[i] = r ** 2
        log_a[i] = intercept

    return b_values, r_squared, log_a


# ══════════════════════════════════════════════════════════════════════════════
#  DUNN DECOMPOSITION
#  i(V,v) = k1(V)*v + k2(V)*sqrt(v)
#  capacitive contribution: k1*v
#  diffusion contribution:  k2*sqrt(v)
# ══════════════════════════════════════════════════════════════════════════════

def dunn_decomposition(
    potential: np.ndarray,
    currents: np.ndarray,
    scan_rates: list[float],
) -> dict:
    """
    Perform Dunn (capacitive/diffusion) decomposition at every potential point.

    Fits i/sqrt(v) = k1*sqrt(v) + k2  at each potential via linear regression.

    Returns a dict with keys:
        k1          : (N,) capacitive coefficient
        k2          : (N,) diffusion coefficient
        cap_current : (N, M) capacitive current at each scan rate
        dif_current : (N, M) diffusion current at each scan rate
        cap_frac    : (M,) fraction of charge from capacitive process (per scan rate)
        dif_frac    : (M,) fraction of charge from diffusion process
        total_cap_frac : scalar mean capacitive fraction across all scan rates
    """
    scan_rates = np.array(scan_rates, dtype=float)
    sqrt_v = np.sqrt(scan_rates)
    n_pts = len(potential)
    n_rates = len(scan_rates)

    k1 = np.zeros(n_pts)
    k2 = np.zeros(n_pts)

    for i in range(n_pts):
        # i / sqrt(v) = k1 * sqrt(v) + k2
        y = currents[i, :] / sqrt_v   # i/sqrt(v)
        x = sqrt_v                     # sqrt(v)
        # Linear regression: y = k1*x + k2
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            slope, intercept, _, _, _ = linregress(x, y)
        k1[i] = slope
        k2[i] = intercept

    # Reconstruct capacitive and diffusion current maps
    # cap_current[i, j] = k1[i] * v[j]
    # dif_current[i, j] = k2[i] * sqrt(v[j])
    cap_current = np.outer(k1, scan_rates)          # (N, M)
    dif_current = np.outer(k2, sqrt_v)              # (N, M)

    # Charge (area under curve) — use trapezoidal integration over potential
    dpot = np.abs(np.gradient(potential))
    _trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    cap_charge = np.array([
        _trapz(np.abs(cap_current[:, j]), potential) for j in range(n_rates)
    ])
    dif_charge = np.array([
        _trapz(np.abs(dif_current[:, j]), potential) for j in range(n_rates)
    ])
    total_charge = cap_charge + dif_charge
    # Avoid division by zero
    total_charge = np.where(total_charge == 0, 1e-30, total_charge)

    cap_frac = cap_charge / total_charge
    dif_frac = dif_charge / total_charge

    return {
        "k1": k1,
        "k2": k2,
        "cap_current": cap_current,
        "dif_current": dif_current,
        "cap_frac": cap_frac,
        "dif_frac": dif_frac,
        "total_cap_frac": float(np.nanmean(cap_frac)),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  PEAK DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def detect_peaks(
    potential: np.ndarray,
    current: np.ndarray,
    smoothing: bool = True,
) -> dict:
    """
    Detect anodic (positive) and cathodic (negative) peaks in a single CV.

    Uses scipy find_peaks on smoothed (Savitzky-Golay) current if requested.

    Returns dict with keys:
        anodic_idx, cathodic_idx  : indices of detected peaks
        anodic_potential          : potential at anodic peaks
        cathodic_potential        : potential at cathodic peaks
        anodic_current            : current at anodic peaks
        cathodic_current          : current at cathodic peaks
        peak_separation           : ΔE = E_anodic - E_cathodic (V), or None
    """
    if smoothing and len(current) >= 15:
        window = min(15, len(current) // 5 * 2 + 1)  # must be odd
        if window % 2 == 0:
            window += 1
        curr_smooth = savgol_filter(current, window_length=window, polyorder=3)
    else:
        curr_smooth = current.copy()

    # Anodic peaks (positive local maxima)
    anodic_idx, _ = find_peaks(
        curr_smooth,
        prominence=np.std(curr_smooth) * 0.3,
        distance=max(5, len(current) // 20),
    )

    # Cathodic peaks (negative local maxima = minima of current)
    cathodic_idx, _ = find_peaks(
        -curr_smooth,
        prominence=np.std(curr_smooth) * 0.3,
        distance=max(5, len(current) // 20),
    )

    # Peak separation (nearest anodic–cathodic pair)
    peak_sep = None
    if len(anodic_idx) > 0 and len(cathodic_idx) > 0:
        e_a = potential[anodic_idx[np.argmax(current[anodic_idx])]]
        e_c = potential[cathodic_idx[np.argmin(current[cathodic_idx])]]
        peak_sep = e_a - e_c

    return {
        "anodic_idx": anodic_idx,
        "cathodic_idx": cathodic_idx,
        "anodic_potential": potential[anodic_idx],
        "cathodic_potential": potential[cathodic_idx],
        "anodic_current": current[anodic_idx],
        "cathodic_current": current[cathodic_idx],
        "peak_separation": peak_sep,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  PEAK SCALING: Ip vs sqrt(v)  — Randles-Sevcik diagnostic
# ══════════════════════════════════════════════════════════════════════════════

def peak_scaling_analysis(
    potential: np.ndarray,
    currents: np.ndarray,
    scan_rates: list[float],
) -> dict:
    """
    For each scan rate extract the peak anodic and cathodic currents,
    then regress Ip vs sqrt(v).

    Diffusion-controlled: linear Ip vs sqrt(v) → Randles-Ševčík
    Capacitive:           linear Ip vs v

    Returns dict with:
        sqrt_v           : (M,) sqrt of scan rates
        anodic_peaks     : (M,) peak anodic current per scan rate
        cathodic_peaks   : (M,) peak cathodic current per scan rate (absolute)
        anodic_slope     : slope of Ip_a vs sqrt(v) regression
        anodic_intercept
        anodic_r2
        cathodic_slope
        cathodic_intercept
        cathodic_r2
    """
    scan_rates = np.array(scan_rates, dtype=float)
    sqrt_v = np.sqrt(scan_rates)
    n_rates = len(scan_rates)

    anodic_peaks = np.zeros(n_rates)
    cathodic_peaks = np.zeros(n_rates)

    for j in range(n_rates):
        curr = currents[:, j]
        peaks = detect_peaks(potential, curr, smoothing=True)
        if len(peaks["anodic_current"]) > 0:
            anodic_peaks[j] = np.max(peaks["anodic_current"])
        else:
            anodic_peaks[j] = np.max(curr)
        if len(peaks["cathodic_current"]) > 0:
            cathodic_peaks[j] = np.min(peaks["cathodic_current"])
        else:
            cathodic_peaks[j] = np.min(curr)

    # Regress anodic Ip vs sqrt(v)
    a_slope, a_int, a_r, _, _ = linregress(sqrt_v, anodic_peaks)
    # Regress |cathodic Ip| vs sqrt(v)
    c_slope, c_int, c_r, _, _ = linregress(sqrt_v, np.abs(cathodic_peaks))

    return {
        "sqrt_v": sqrt_v,
        "anodic_peaks": anodic_peaks,
        "cathodic_peaks": cathodic_peaks,
        "anodic_slope": a_slope,
        "anodic_intercept": a_int,
        "anodic_r2": a_r ** 2,
        "cathodic_slope": c_slope,
        "cathodic_intercept": c_int,
        "cathodic_r2": c_r ** 2,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  KINETIC REGIME MAP
#  Binary classification per (potential, scan_rate) cell
# ══════════════════════════════════════════════════════════════════════════════

def kinetic_regime_map(
    b_values: np.ndarray,
    dunn_result: dict,
    b_threshold: float = 0.7,
) -> np.ndarray:
    """
    Generate a (N,) regime array based on b-values.
        regime = 1  → capacitive-dominated  (b >= b_threshold)
        regime = 0  → diffusion-dominated   (b < b_threshold)

    Returns (N,) float array with values in {0, 1}.
    """
    regime = np.zeros(len(b_values))
    regime[b_values >= b_threshold] = 1.0
    return regime



# ══════════════════════════════════════════════════════════════════════════════
#  PCA / DIMENSIONALITY REDUCTION
# ══════════════════════════════════════════════════════════════════════════════

def pca_analysis(
    currents: np.ndarray,
    scan_rates: list[float],
    n_components: int = 2,
) -> dict:
    """
    Treat each scan rate as a feature vector (the CV curve) and project
    all voltage points into PCA space.  Also provides scan-rate PCA.

    Returns dict:
        pca_scores_voltage  : (N, 2) PCA scores for each voltage point
        pca_scores_rate     : (M, 2) PCA scores for each scan rate curve
        explained_variance  : (n_components,) explained variance ratio
        pca_model           : fitted PCA object
    """
    scan_rates = np.array(scan_rates, dtype=float)

    # Voltage-point PCA: each row = one potential, features = currents at different v
    scaler_v = StandardScaler()
    X_v = scaler_v.fit_transform(currents)          # (N, M)
    n_comp_v = min(n_components, X_v.shape[1])
    pca_v = PCA(n_components=n_comp_v)
    scores_v = pca_v.fit_transform(X_v)             # (N, 2)

    # Scan-rate PCA: each row = one CV curve (transposed)
    X_r = currents.T                                # (M, N)
    scaler_r = StandardScaler()
    X_r_scaled = scaler_r.fit_transform(X_r)
    n_comp_r = min(n_components, X_r_scaled.shape[1])
    pca_r = PCA(n_components=n_comp_r)
    scores_r = pca_r.fit_transform(X_r_scaled)      # (M, 2)

    return {
        "pca_scores_voltage": scores_v,
        "pca_scores_rate": scores_r,
        "explained_variance_voltage": pca_v.explained_variance_ratio_,
        "explained_variance_rate": pca_r.explained_variance_ratio_,
        "scan_rates": scan_rates,
    }
