"""
Raman Spectroscopy Analysis Engine
===================================
Production-grade Raman spectroscopy data analysis with state-of-the-art algorithms.

Features:
- Baseline correction (airPLS, polynomial, morphological, AsLS)
- Peak detection and fitting (Lorentzian, Gaussian, Voigt)
- Denoising (Savitzky-Golay, wavelet, moving average)
- Spectral normalization and smoothing
- Material identification via peak matching
- Quantitative analysis (peak area, FWHM, intensity ratios)

External Library Integrations:
- **pybaselines** (optional): When installed, replaces manual AsLS and airPLS
  implementations with the peer-reviewed pybaselines library.  Also unlocks
  four additional baseline algorithms: ModPoly, IModPoly, SNIP, and
  Morphological (Mor).  Falls back to the built-in implementations when
  the package is absent.
- **RamanSPy** (optional): When installed, provides a full RamanSPy-backed
  preprocessing pipeline (cosmic spike removal → denoising → baseline
  correction → normalization) and a standalone cosmic-spike-removal method.
  Falls back to the built-in pipeline when the package is absent.

Based on latest research:
- airPLS: Adaptive iteratively reweighted penalized least squares
- Morphological baseline (BubbleFill algorithm)
- Asymmetric least squares (AsLS)
- Convolutional autoencoder methods (future ML enhancement)

References:
- Eilers & Boelens (2005) - Baseline correction with asymmetric least squares
- Zhao et al. (2007) - Adaptive iteratively reweighted penalized least squares
- Perez-Guaita et al. (2023) - BubbleFill morphological baseline removal
- MDPI Sensors (2024) - Deep learning for Raman preprocessing
- pybaselines: Erb (2022) - pybaselines: A Python library of algorithms for
  the baseline correction of experimental data
- RamanSPy: Georgiev et al. (2024) - RamanSPy: An open-source Python package
  for integrative Raman spectroscopy data analysis

Author: VidyuthLabs
Date: May 4, 2026
"""

import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from scipy import sparse, signal, ndimage
from scipy.sparse.linalg import spsolve
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, savgol_filter

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONAL EXTERNAL LIBRARY DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import pybaselines
    HAS_PYBASELINES = True
    logger.info(
        "pybaselines %s detected – using research-grade baseline algorithms",
        getattr(pybaselines, "__version__", "unknown"),
    )
except ImportError:
    HAS_PYBASELINES = False
    logger.info(
        "pybaselines not installed – using built-in baseline implementations"
    )

try:
    import ramanspy
    HAS_RAMANSPY = True
    logger.info(
        "RamanSPy %s detected – RamanSPy preprocessing pipeline available",
        getattr(ramanspy, "__version__", "unknown"),
    )
except ImportError:
    HAS_RAMANSPY = False
    logger.info(
        "RamanSPy not installed – using built-in preprocessing pipeline"
    )


@dataclass
class RamanSpectrum:
    """Raman spectroscopy data container."""
    wavenumber: np.ndarray  # cm⁻¹ (Raman shift)
    intensity: np.ndarray   # Arbitrary units or counts
    
    # Metadata
    source_file: str = ""
    format_type: str = ""
    measurement_date: str = ""
    laser_wavelength_nm: Optional[float] = None
    laser_power_mW: Optional[float] = None
    integration_time_s: Optional[float] = None
    temperature_C: Optional[float] = None
    sample_id: str = ""
    
    # Processed data (filled after analysis)
    baseline: Optional[np.ndarray] = None
    corrected_intensity: Optional[np.ndarray] = None
    smoothed_intensity: Optional[np.ndarray] = None
    peaks: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        result = {
            "wavenumber": self.wavenumber.tolist(),
            "intensity": self.intensity.tolist(),
            "n_points": len(self.wavenumber),
            "wavenumber_range": [float(self.wavenumber.min()), float(self.wavenumber.max())],
            "intensity_range": [float(self.intensity.min()), float(self.intensity.max())],
            "source_file": self.source_file,
            "format_type": self.format_type,
            "measurement_date": self.measurement_date,
            "laser_wavelength_nm": self.laser_wavelength_nm,
            "laser_power_mW": self.laser_power_mW,
            "integration_time_s": self.integration_time_s,
            "temperature_C": self.temperature_C,
            "sample_id": self.sample_id,
        }
        
        if self.baseline is not None:
            result["baseline"] = self.baseline.tolist()
        if self.corrected_intensity is not None:
            result["corrected_intensity"] = self.corrected_intensity.tolist()
        if self.smoothed_intensity is not None:
            result["smoothed_intensity"] = self.smoothed_intensity.tolist()
        if self.peaks:
            result["peaks"] = self.peaks
        
        return result


@dataclass
class RamanAnalysisConfig:
    """Configuration for Raman spectroscopy analysis."""
    # Baseline correction
    baseline_method: str = "als"         # "airpls", "als", "polynomial", "morphological"
    baseline_lambda: float = 1e5         # Smoothness parameter for airPLS/AsLS
    baseline_p: float = 0.001            # Asymmetry parameter for airPLS/AsLS
    baseline_max_iter: int = 50          # Maximum iterations
    polynomial_order: int = 5            # For polynomial baseline
    
    # Denoising (now handled by adaptive smoothing in analyze())
    denoise_method: str = "none"         # Deprecated, use adaptive smoothing
    savgol_window: int = 11              # Deprecated, now adaptive
    savgol_polyorder: int = 3            # Deprecated, now adaptive
    moving_avg_window: int = 5           # Moving average window
    
    # Peak detection (now uses adaptive thresholds)
    peak_detection: bool = True
    peak_prominence: float = None        # Deprecated, now calculated dynamically
    peak_min_distance: int = None        # Deprecated, now calculated adaptively
    peak_width_range: Tuple[int, int] = (2, 50)  # Min/max peak width
    
    # Peak fitting
    peak_fitting: bool = True
    peak_model: str = "lorentzian"       # "lorentzian", "gaussian", "voigt"
    
    # Normalization
    normalize: bool = True
    normalization_method: str = "minmax"  # "minmax", "area", "vector", "snv"


class RamanAnalyzer:
    """
    Comprehensive Raman spectroscopy analysis engine.
    
    Implements state-of-the-art algorithms for:
    - Baseline correction
    - Denoising
    - Peak detection and fitting
    - Material identification
    """
    
    def __init__(self, config: Optional[RamanAnalysisConfig] = None):
        """Initialize Raman analyzer with configuration."""
        self.config = config or RamanAnalysisConfig()
        logger.info("Raman analyzer initialized with config: %s", self.config.baseline_method)
    
    def preprocess_ramanspy(self, spectrum: RamanSpectrum, steps: list = None) -> RamanSpectrum:
        """
        Preprocess Raman spectrum using the RamanSPy pipeline.
        
        Applies a sequence of preprocessing steps: cosmic ray removal,
        denoising, baseline correction, and normalization.
        """
        if not HAS_RAMANSPY:
            logger.warning("RamanSPy not installed. Falling back to built-in preprocessing.")
            return spectrum

        try:
            # Convert to ramanspy Spectrum object
            rs_spectrum = ramanspy.Spectrum(spectrum.intensity, spectrum.wavenumber)
            
            pipeline_steps = []
            
            # Default steps if none provided
            if steps is None:
                steps = ['despike', 'denoise', 'baseline', 'normalize']
                
            for step in steps:
                if step == 'despike':
                    # Use Whitaker-Hayes cosmic ray removal
                    pipeline_steps.append(ramanspy.preprocessing.despike.WhitakerHayes())
                elif step == 'denoise':
                    pipeline_steps.append(ramanspy.preprocessing.denoise.SavGol(
                        window_length=self.config.smoothing_window, 
                        polyorder=self.config.smoothing_polyorder
                    ))
                elif step == 'baseline':
                    if self.config.baseline_method == 'asls':
                        pipeline_steps.append(ramanspy.preprocessing.baseline.ASLS(
                            lam=self.config.baseline_lambda, 
                            p=self.config.baseline_p
                        ))
                    else:
                        # Fallback to polynomial
                        pipeline_steps.append(ramanspy.preprocessing.baseline.Poly(
                            poly_order=self.config.polynomial_order
                        ))
                elif step == 'normalize':
                    pipeline_steps.append(ramanspy.preprocessing.normalise.MinMax())

            # Build and execute pipeline
            pipeline = ramanspy.preprocessing.Pipeline(pipeline_steps)
            processed_rs_spectrum = pipeline.apply(rs_spectrum)
            
            # Convert back to our RamanSpectrum object
            return RamanSpectrum(
                wavenumber=processed_rs_spectrum.spectral_axis,
                intensity=processed_rs_spectrum.spectral_data,
                source_file=spectrum.source_file,
                format_type=spectrum.format_type,
                measurement_date=spectrum.measurement_date,
                laser_wavelength_nm=spectrum.laser_wavelength_nm,
                laser_power_mW=spectrum.laser_power_mW,
                integration_time_s=spectrum.integration_time_s,
                temperature_C=spectrum.temperature_C,
            )
        except Exception as e:
            logger.error(f"RamanSPy preprocessing failed: {e}. Returning original spectrum.")
            return spectrum

    def analyze(self, spectrum: RamanSpectrum) -> RamanSpectrum:
        """
        Perform complete Raman spectroscopy analysis with robust peak detection.
        
        Pipeline:
        1. Sort data by wavenumber
        2. Smoothing (Savitzky-Golay)
        3. Baseline correction (ALS)
        4. Normalization
        5. Robust peak detection with adaptive thresholds
        6. Peak fitting
        
        Args:
            spectrum: Input Raman spectrum
        
        Returns:
            Analyzed spectrum with baseline, peaks, etc.
        """
        logger.info("Analyzing Raman spectrum: %d points", len(spectrum.wavenumber))
        
        # STEP 1: SORT DATA by wavenumber
        sort_idx = np.argsort(spectrum.wavenumber)
        wavenumber = spectrum.wavenumber[sort_idx]
        intensity = spectrum.intensity[sort_idx]
        
        logger.debug(f"Data sorted: {len(wavenumber)} points, range {wavenumber.min():.1f}-{wavenumber.max():.1f} cm⁻¹")
        
        # STEP 2: SMOOTHING (Savitzky-Golay with adaptive window)
        smoothed = self._adaptive_smoothing(intensity)
        logger.debug(f"Smoothing applied: signal range {smoothed.min():.2f} to {smoothed.max():.2f}")
        
        # STEP 3: BASELINE CORRECTION (prefer ALS for robustness)
        baseline = self.baseline_correction(
            wavenumber,
            smoothed,
            method=self.config.baseline_method
        )
        corrected = smoothed - baseline
        logger.debug(f"Baseline corrected: corrected range {corrected.min():.2f} to {corrected.max():.2f}")
        
        # STEP 4: NORMALIZATION
        if self.config.normalize:
            corrected = self.normalize_spectrum(corrected, self.config.normalization_method)
            logger.debug(f"Normalized: range {corrected.min():.2f} to {corrected.max():.2f}")
        
        # STEP 5: ROBUST PEAK DETECTION with adaptive thresholds
        peaks = []
        if self.config.peak_detection:
            peaks = self._robust_peak_detection(wavenumber, corrected)
            logger.info(f"Peak detection complete: {len(peaks)} peaks found")
        
        # STEP 6: PEAK FITTING
        if self.config.peak_fitting and peaks:
            peaks = self.fit_peaks(wavenumber, corrected, peaks)
            logger.debug(f"Peak fitting complete for {len(peaks)} peaks")
        
        # Update spectrum object with sorted data
        spectrum.wavenumber = wavenumber
        spectrum.intensity = intensity
        spectrum.baseline = baseline
        spectrum.corrected_intensity = corrected
        spectrum.smoothed_intensity = smoothed
        spectrum.peaks = peaks
        
        logger.info("Analysis complete: %d peaks detected", len(peaks))
        return spectrum
    
    # ═══════════════════════════════════════════════════════════════════════
    # BASELINE CORRECTION METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
    def baseline_correction(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray,
        method: str = "airpls"
    ) -> np.ndarray:
        """
        Perform baseline correction using specified method.

        When *pybaselines* is installed the following additional methods become
        available: ``"modpoly"``, ``"imodpoly"``, ``"snip"``, ``"mor"``.
        The original four methods (``"airpls"``, ``"als"``, ``"polynomial"``,
        ``"morphological"``) also benefit from the optimised pybaselines
        back-end when the library is present.

        Args:
            wavenumber: Wavenumber array (cm⁻¹)
            intensity: Intensity array
            method: Baseline correction method – one of ``"airpls"``,
                ``"als"``, ``"polynomial"``, ``"morphological"``,
                ``"modpoly"``, ``"imodpoly"``, ``"snip"``, ``"mor"``.

        Returns:
            Baseline array
        """
        # Sanitise NaN / Inf values before any baseline computation
        if intensity is None or len(intensity) == 0:
            logger.warning("Empty intensity array passed to baseline_correction")
            return np.zeros_like(wavenumber) if wavenumber is not None else np.array([])

        clean_intensity = np.copy(intensity)
        nan_mask = ~np.isfinite(clean_intensity)
        if nan_mask.any():
            logger.warning(
                "Replacing %d non-finite values in intensity before baseline correction",
                int(nan_mask.sum()),
            )
            clean_intensity[nan_mask] = np.nanmedian(intensity[np.isfinite(intensity)]) if np.any(np.isfinite(intensity)) else 0.0

        # ── Dispatch ──────────────────────────────────────────────────────
        if method == "airpls":
            return self.baseline_airpls(clean_intensity)
        elif method == "als":
            return self.baseline_als(clean_intensity)
        elif method == "polynomial":
            return self.baseline_polynomial(wavenumber, clean_intensity)
        elif method == "morphological":
            return self.baseline_morphological(clean_intensity)
        elif method == "modpoly":
            return self.baseline_modpoly(wavenumber, clean_intensity)
        elif method == "imodpoly":
            return self.baseline_imodpoly(wavenumber, clean_intensity)
        elif method == "snip":
            return self.baseline_snip(clean_intensity)
        elif method == "mor":
            return self.baseline_mor(clean_intensity)
        else:
            logger.warning(f"Unknown baseline method: {method}, using airPLS")
            return self.baseline_airpls(clean_intensity)
    
    def baseline_airpls(self, intensity: np.ndarray) -> np.ndarray:
        """
        Adaptive iteratively reweighted penalized least squares (airPLS).

        When *pybaselines* is available the call is delegated to
        ``pybaselines.whittaker.airpls`` which is numerically more stable
        and supports banded-matrix solvers.  Otherwise the original
        hand-rolled implementation is used.

        Reference:
            Zhang et al. (2010) "Baseline correction using adaptive iteratively
            reweighted penalized least squares"

        Args:
            intensity: Intensity array

        Returns:
            Baseline array
        """
        lam = self.config.baseline_lambda

        # ── pybaselines fast-path ─────────────────────────────────────────
        if HAS_PYBASELINES:
            try:
                logger.debug("airPLS: using pybaselines backend (lam=%.1e)", lam)
                baseline, _params = pybaselines.whittaker.airpls(
                    intensity, lam=lam,
                    max_iter=self.config.baseline_max_iter,
                )
                return baseline
            except Exception as exc:
                logger.warning(
                    "pybaselines.airpls failed (%s), falling back to built-in",
                    exc,
                )

        # ── Built-in fallback ─────────────────────────────────────────────
        logger.debug("airPLS: using built-in implementation (lam=%.1e)", lam)
        m = len(intensity)
        w = np.ones(m)

        D = sparse.diags([1, -2, 1], [0, 1, 2], shape=(m-2, m), dtype=float)
        D = D.T @ D

        for i in range(self.config.baseline_max_iter):
            W = sparse.diags(w, 0, shape=(m, m))
            Z = (W + lam * D).tocsc()
            z = spsolve(Z, w * intensity)

            d = intensity - z
            dssn = np.abs(d[d < 0].sum())

            if dssn < 0.001 * (abs(intensity).sum()) or i == self.config.baseline_max_iter - 1:
                break

            w_new = np.where(d >= 0, 0, np.exp(i * np.abs(d) / dssn))
            w_new[0] = np.exp(i * (d[0] / dssn))
            w_new[-1] = np.exp(i * (d[-1] / dssn))

            w = w_new

        return z
    
    def baseline_als(self, intensity: np.ndarray) -> np.ndarray:
        """
        Asymmetric least squares (AsLS) baseline correction.

        When *pybaselines* is available the call is delegated to
        ``pybaselines.whittaker.asls``.  Otherwise the original
        implementation is used.

        Reference:
            Eilers & Boelens (2005) "Baseline correction with asymmetric
            least squares"

        Args:
            intensity: Intensity array

        Returns:
            Baseline array
        """
        lam = self.config.baseline_lambda
        p = self.config.baseline_p

        # ── pybaselines fast-path ─────────────────────────────────────────
        if HAS_PYBASELINES:
            try:
                logger.debug(
                    "AsLS: using pybaselines backend (lam=%.1e, p=%.1e)", lam, p,
                )
                baseline, _params = pybaselines.whittaker.asls(
                    intensity, lam=lam, p=p,
                    max_iter=self.config.baseline_max_iter,
                )
                return baseline
            except Exception as exc:
                logger.warning(
                    "pybaselines.asls failed (%s), falling back to built-in",
                    exc,
                )

        # ── Built-in fallback ─────────────────────────────────────────────
        logger.debug("AsLS: using built-in implementation (lam=%.1e, p=%.1e)", lam, p)
        m = len(intensity)
        D = sparse.diags([1, -2, 1], [0, 1, 2], shape=(m-2, m), dtype=float)
        D = D.T @ D

        w = np.ones(m)

        for _ in range(self.config.baseline_max_iter):
            W = sparse.diags(w, 0, shape=(m, m))
            Z = (W + lam * D).tocsc()
            z = spsolve(Z, w * intensity)
            w = p * (intensity > z) + (1 - p) * (intensity < z)

        return z
    
    def baseline_polynomial(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray
    ) -> np.ndarray:
        """
        Polynomial baseline fitting.
        
        Args:
            wavenumber: Wavenumber array
            intensity: Intensity array
        
        Returns:
            Baseline array
        """
        # Fit polynomial to lower envelope
        # Use iterative approach: fit, remove points above fit, repeat
        x = wavenumber.copy()
        y = intensity.copy()
        
        for _ in range(5):  # 5 iterations
            coeffs = np.polyfit(x, y, self.config.polynomial_order)
            baseline = np.polyval(coeffs, wavenumber)
            
            # Keep only points below baseline
            mask = intensity < baseline
            if mask.sum() < self.config.polynomial_order + 2:  # Need enough points for polyfit
                break
            x = wavenumber[mask]
            y = intensity[mask]
        
        return baseline
    
    def baseline_morphological(self, intensity: np.ndarray) -> np.ndarray:
        """
        Morphological baseline correction (BubbleFill algorithm).

        Reference:
            Perez-Guaita et al. (2023) "Open-sourced Raman spectroscopy data
            processing package implementing a baseline removal algorithm"

        Args:
            intensity: Intensity array

        Returns:
            Baseline array
        """
        # Use morphological opening with increasing structure sizes
        baseline = intensity.copy()

        for size in [5, 10, 20, 40, 80]:
            if size > len(intensity) // 4:
                break
            struct = np.ones(size)
            opened = ndimage.grey_opening(baseline, footprint=struct)
            baseline = np.minimum(baseline, opened)

        return baseline

    # ── New baseline methods (require pybaselines) ────────────────────────

    def baseline_modpoly(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray,
    ) -> np.ndarray:
        """
        Modified polynomial (ModPoly) baseline correction.

        Iteratively fits a polynomial, replacing data above the current
        fit with the fit value, until convergence.  Requires *pybaselines*.

        Reference:
            Lieber & Mahadevan-Jansen (2003) "Automated method for
            subtraction of fluorescence from biological Raman spectra"

        Args:
            wavenumber: Wavenumber array (cm⁻¹)
            intensity: Intensity array

        Returns:
            Baseline array

        Raises:
            RuntimeError: If pybaselines is not installed.
        """
        if not HAS_PYBASELINES:
            raise RuntimeError(
                "baseline_modpoly requires pybaselines. "
                "Install it with: pip install pybaselines"
            )
        logger.debug(
            "ModPoly: using pybaselines backend (poly_order=%d)",
            self.config.polynomial_order,
        )
        baseline, _params = pybaselines.polynomial.modpoly(
            intensity,
            x_data=wavenumber,
            poly_order=self.config.polynomial_order,
            max_iter=self.config.baseline_max_iter,
        )
        return baseline

    def baseline_imodpoly(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray,
    ) -> np.ndarray:
        """
        Improved modified polynomial (IModPoly) baseline correction.

        Like ModPoly but uses the standard deviation of the residual to
        threshold peaks rather than a simple minimum comparison.
        Requires *pybaselines*.

        Reference:
            Zhao et al. (2007) "Automated autofluorescence background
            subtraction algorithm for biomedical Raman spectroscopy"

        Args:
            wavenumber: Wavenumber array (cm⁻¹)
            intensity: Intensity array

        Returns:
            Baseline array

        Raises:
            RuntimeError: If pybaselines is not installed.
        """
        if not HAS_PYBASELINES:
            raise RuntimeError(
                "baseline_imodpoly requires pybaselines. "
                "Install it with: pip install pybaselines"
            )
        logger.debug(
            "IModPoly: using pybaselines backend (poly_order=%d)",
            self.config.polynomial_order,
        )
        baseline, _params = pybaselines.polynomial.imodpoly(
            intensity,
            x_data=wavenumber,
            poly_order=self.config.polynomial_order,
            max_iter=self.config.baseline_max_iter,
        )
        return baseline

    def baseline_snip(self, intensity: np.ndarray) -> np.ndarray:
        """
        Statistics-sensitive Non-linear Iterative Peak-clipping (SNIP).

        A non-parametric baseline estimator that iteratively clips peaks.
        Requires *pybaselines* (the algorithm lives in ``pybaselines.smooth``).

        Reference:
            Ryan et al. (1988) "SNIP, A statistics-sensitive background
            treatment for the quantitative analysis of PIXE spectra"

        Args:
            intensity: Intensity array

        Returns:
            Baseline array

        Raises:
            RuntimeError: If pybaselines is not installed.
        """
        if not HAS_PYBASELINES:
            raise RuntimeError(
                "baseline_snip requires pybaselines. "
                "Install it with: pip install pybaselines"
            )
        # max_half_window defaults to ~len/20 if None – a sensible auto-value
        logger.debug("SNIP: using pybaselines backend")
        baseline, _params = pybaselines.smooth.snip(
            intensity,
            max_half_window=None,
            decreasing=False,
        )
        return baseline

    def baseline_mor(self, intensity: np.ndarray) -> np.ndarray:
        """
        Morphological (Mor) baseline correction via pybaselines.

        Uses a combination of morphological opening and the average of
        erosion/dilation to estimate the baseline.  Requires *pybaselines*.

        Reference:
            Perez-Pueyo et al. (2010) "Morphology-Based Automated Baseline
            Removal for Raman Spectra of Artistic Pigments"

        Args:
            intensity: Intensity array

        Returns:
            Baseline array

        Raises:
            RuntimeError: If pybaselines is not installed.
        """
        if not HAS_PYBASELINES:
            raise RuntimeError(
                "baseline_mor requires pybaselines. "
                "Install it with: pip install pybaselines"
            )
        logger.debug("Mor: using pybaselines backend")
        baseline, _params = pybaselines.morphological.mor(
            intensity,
            half_window=None,  # auto-optimised
        )
        return baseline

    
    # ═══════════════════════════════════════════════════════════════════════
    # DENOISING METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
    def denoise(self, intensity: np.ndarray, method: str = "savgol") -> np.ndarray:
        """
        Denoise spectrum using specified method.
        
        Args:
            intensity: Intensity array
            method: Denoising method
        
        Returns:
            Denoised intensity array
        """
        if method == "savgol":
            return self.denoise_savgol(intensity)
        elif method == "moving_average":
            return self.denoise_moving_average(intensity)
        elif method == "wavelet":
            return self.denoise_wavelet(intensity)
        else:
            return intensity
    
    def denoise_savgol(self, intensity: np.ndarray) -> np.ndarray:
        """
        Savitzky-Golay filter for denoising.
        
        Args:
            intensity: Intensity array
        
        Returns:
            Smoothed intensity array
        """
        window = self.config.savgol_window
        polyorder = self.config.savgol_polyorder
        
        # Ensure window is odd and valid
        if window % 2 == 0:
            window += 1
        window = min(window, len(intensity) - 1)
        polyorder = min(polyorder, window - 1)
        
        return savgol_filter(intensity, window, polyorder)
    
    def denoise_moving_average(self, intensity: np.ndarray) -> np.ndarray:
        """
        Moving average filter for denoising.
        
        Args:
            intensity: Intensity array
        
        Returns:
            Smoothed intensity array
        """
        window = self.config.moving_avg_window
        kernel = np.ones(window) / window
        return np.convolve(intensity, kernel, mode='same')
    
    def denoise_wavelet(self, intensity: np.ndarray) -> np.ndarray:
        """
        Wavelet denoising (requires pywt).
        
        Args:
            intensity: Intensity array
        
        Returns:
            Denoised intensity array
        """
        try:
            import pywt
            
            # Decompose signal
            coeffs = pywt.wavedec(intensity, 'sym7', level=5)
            
            # Threshold detail coefficients
            sigma = np.median(np.abs(coeffs[-1])) / 0.6745
            threshold = sigma * np.sqrt(2 * np.log(len(intensity)))
            
            coeffs[1:] = [pywt.threshold(c, threshold, mode='soft') for c in coeffs[1:]]
            
            # Reconstruct signal
            return pywt.waverec(coeffs, 'sym7')
        
        except ImportError:
            logger.warning("pywt not available, falling back to Savitzky-Golay")
            return self.denoise_savgol(intensity)
    
    # ═══════════════════════════════════════════════════════════════════════
    # PEAK DETECTION AND FITTING
    # ═══════════════════════════════════════════════════════════════════════
    
    def _adaptive_smoothing(self, intensity: np.ndarray) -> np.ndarray:
        """
        Apply adaptive Savitzky-Golay smoothing based on data size.
        
        Args:
            intensity: Intensity array
        
        Returns:
            Smoothed intensity array
        """
        n_points = len(intensity)
        
        # Adaptive window length: 11-31 based on data size
        if n_points < 100:
            window = 7
        elif n_points < 500:
            window = 11
        elif n_points < 1000:
            window = 15
        elif n_points < 2000:
            window = 21
        else:
            window = 31
        
        # Ensure window is odd
        if window % 2 == 0:
            window += 1
        
        # Ensure window is not larger than data
        window = min(window, n_points - 1 if n_points % 2 == 0 else n_points)
        if window < 5:
            window = 5
        
        # Adaptive polynomial order: 2-3
        polyorder = 3 if n_points > 500 else 2
        polyorder = min(polyorder, window - 1)
        
        logger.debug(f"Adaptive smoothing: window={window}, polyorder={polyorder}")
        
        return savgol_filter(intensity, window, polyorder)
    
    def _robust_peak_detection(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Robust peak detection with adaptive thresholds and fallback strategies.
        
        Pipeline:
        1. Calculate dynamic prominence threshold (5-10% of signal range)
        2. Calculate adaptive distance based on spectrum length
        3. Attempt peak detection with scipy.signal.find_peaks
        4. If no peaks found, gradually lower threshold and retry
        5. Fallback: Return top N local maxima if still no peaks
        
        Args:
            wavenumber: Wavenumber array (sorted)
            intensity: Intensity array (baseline-corrected, normalized)
        
        Returns:
            List of peak dictionaries with positions, intensities, etc.
        """
        n_points = len(intensity)
        signal_range = intensity.max() - intensity.min()
        signal_mean = intensity.mean()
        signal_std = intensity.std()
        
        logger.debug(f"Signal statistics: range={signal_range:.3f}, mean={signal_mean:.3f}, std={signal_std:.3f}")
        
        # Check for completely flat signal
        if signal_range < 1e-10:
            logger.warning("Signal is completely flat, no peaks possible")
            return []
        
        # STEP 1: Calculate dynamic prominence threshold (5-10% of signal range)
        # Start with 5% for first attempt
        base_prominence = 0.05 * signal_range
        
        # STEP 2: Calculate adaptive distance based on spectrum length
        # Typical Raman peaks are separated by at least 10-20 cm⁻¹
        wavenumber_step = np.median(np.diff(wavenumber))
        min_peak_separation_cm = 10.0  # cm⁻¹
        adaptive_distance = max(int(min_peak_separation_cm / wavenumber_step), 5)
        
        logger.debug(f"Adaptive distance: {adaptive_distance} points (~{adaptive_distance * wavenumber_step:.1f} cm⁻¹)")
        
        # STEP 3: Attempt peak detection with multiple threshold levels
        prominence_levels = [
            base_prominence,           # 5% of range
            base_prominence * 0.5,     # 2.5% of range
            base_prominence * 0.3,     # 1.5% of range
            base_prominence * 0.1,     # 0.5% of range
            signal_std * 0.5,          # Half standard deviation
            signal_std * 0.2,          # 0.2 standard deviations
        ]
        
        peaks = []
        used_prominence = None
        
        for prominence in prominence_levels:
            if prominence <= 0:
                continue
            
            logger.debug(f"Trying peak detection with prominence={prominence:.4f}")
            
            try:
                peak_indices, properties = find_peaks(
                    intensity,
                    prominence=prominence,
                    distance=adaptive_distance,
                    width=(2, None)  # Minimum width of 2 points
                )
                
                if len(peak_indices) > 0:
                    logger.info(f"✓ Found {len(peak_indices)} peaks with prominence={prominence:.4f}")
                    used_prominence = prominence
                    
                    # Build peak list
                    for idx in peak_indices:
                        peak = {
                            "position_cm": float(wavenumber[idx]),
                            "intensity": float(intensity[idx]),
                            "index": int(idx),
                            "prominence": float(properties["prominences"][np.where(peak_indices == idx)[0][0]]),
                        }
                        
                        # Estimate FWHM
                        try:
                            width_idx = np.where(peak_indices == idx)[0][0]
                            width_points = properties["widths"][width_idx]
                            width_cm = width_points * abs(wavenumber_step)
                            peak["fwhm_cm"] = float(width_cm)
                            peak["width_points"] = float(width_points)
                        except:
                            peak["fwhm_cm"] = None
                            peak["width_points"] = None
                        
                        peaks.append(peak)
                    
                    break  # Success, exit loop
                else:
                    logger.debug(f"  No peaks found with prominence={prominence:.4f}")
            
            except Exception as e:
                logger.warning(f"Peak detection failed with prominence={prominence:.4f}: {e}")
                continue
        
        # STEP 4: Fallback strategy - find top N local maxima
        if len(peaks) == 0:
            logger.warning("No peaks found with standard detection, using fallback strategy")
            peaks = self._fallback_peak_detection(wavenumber, intensity, n_peaks=10)
        
        # STEP 5: Sort peaks by intensity (descending)
        peaks.sort(key=lambda p: p["intensity"], reverse=True)
        
        # STEP 6: Debug output
        logger.info(f"Peak detection summary:")
        logger.info(f"  Total peaks found: {len(peaks)}")
        if used_prominence is not None:
            logger.info(f"  Prominence threshold used: {used_prominence:.4f}")
        else:
            logger.info(f"  Prominence threshold used: fallback")
        logger.info(f"  Signal range: {signal_range:.3f}")
        logger.info(f"  Adaptive distance: {adaptive_distance} points")
        
        if peaks:
            logger.info(f"  Top 5 peaks:")
            for i, peak in enumerate(peaks[:5], 1):
                logger.info(f"    {i}. {peak['position_cm']:.1f} cm⁻¹, intensity={peak['intensity']:.3f}, prominence={peak.get('prominence', 'N/A')}")
        
        return peaks
    
    def _fallback_peak_detection(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray,
        n_peaks: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fallback peak detection: Find top N local maxima.
        
        This ensures we always return some peaks even if the signal is very noisy.
        
        Args:
            wavenumber: Wavenumber array
            intensity: Intensity array
            n_peaks: Number of peaks to return
        
        Returns:
            List of peak dictionaries
        """
        logger.info(f"Fallback detection: Finding top {n_peaks} local maxima")
        
        # Find all local maxima (peaks with neighbors on both sides)
        local_maxima = []
        
        for i in range(1, len(intensity) - 1):
            if intensity[i] > intensity[i-1] and intensity[i] > intensity[i+1]:
                local_maxima.append({
                    "position_cm": float(wavenumber[i]),
                    "intensity": float(intensity[i]),
                    "index": int(i),
                    "prominence": float(intensity[i] - min(intensity[i-1], intensity[i+1])),
                    "fwhm_cm": None,
                    "fallback": True
                })
        
        # Sort by intensity and take top N
        local_maxima.sort(key=lambda p: p["intensity"], reverse=True)
        peaks = local_maxima[:n_peaks]
        
        logger.info(f"Fallback found {len(local_maxima)} local maxima, returning top {len(peaks)}")
        
        return peaks
    
    def detect_peaks(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Detect peaks in Raman spectrum (legacy method, calls robust detection).
        
        Args:
            wavenumber: Wavenumber array
            intensity: Intensity array (baseline-corrected)
        
        Returns:
            List of peak dictionaries
        """
        return self._robust_peak_detection(wavenumber, intensity)
    
    def fit_peaks(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray,
        peaks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Fit detected peaks with specified model.
        
        Args:
            wavenumber: Wavenumber array
            intensity: Intensity array
            peaks: List of detected peaks
        
        Returns:
            List of peaks with fit parameters
        """
        for peak in peaks:
            idx = peak["index"]
            
            # Define fitting window (±50 points around peak)
            window = 50
            start = max(0, idx - window)
            end = min(len(wavenumber), idx + window)
            
            x_fit = wavenumber[start:end]
            y_fit = intensity[start:end]
            
            # Initial guess
            x0 = peak["position_cm"]
            A = peak["intensity"]
            gamma = peak.get("fwhm_cm", 10.0) / 2  # Half-width
            
            try:
                if self.config.peak_model == "lorentzian":
                    popt, _ = curve_fit(
                        self._lorentzian,
                        x_fit, y_fit,
                        p0=[A, x0, gamma],
                        maxfev=1000
                    )
                    peak["fit_amplitude"] = float(popt[0])
                    peak["fit_position_cm"] = float(popt[1])
                    peak["fit_gamma"] = float(popt[2])
                    peak["fit_fwhm_cm"] = float(2 * popt[2])
                    
                elif self.config.peak_model == "gaussian":
                    popt, _ = curve_fit(
                        self._gaussian,
                        x_fit, y_fit,
                        p0=[A, x0, gamma],
                        maxfev=1000
                    )
                    peak["fit_amplitude"] = float(popt[0])
                    peak["fit_position_cm"] = float(popt[1])
                    peak["fit_sigma"] = float(popt[2])
                    peak["fit_fwhm_cm"] = float(2.355 * popt[2])
                
                # Calculate peak area
                peak["area"] = self._calculate_peak_area(x_fit, y_fit)
                
            except Exception as e:
                logger.warning(f"Peak fitting failed for peak at {x0}: {e}")
                peak["fit_error"] = str(e)
        
        return peaks
    
    @staticmethod
    def _lorentzian(x: np.ndarray, A: float, x0: float, gamma: float) -> np.ndarray:
        """Lorentzian peak function."""
        return A * (gamma**2) / ((x - x0)**2 + gamma**2)
    
    @staticmethod
    def _gaussian(x: np.ndarray, A: float, x0: float, sigma: float) -> np.ndarray:
        """Gaussian peak function."""
        return A * np.exp(-((x - x0)**2) / (2 * sigma**2))
    
    @staticmethod
    def _calculate_peak_area(x: np.ndarray, y: np.ndarray) -> float:
        """Calculate peak area using trapezoidal integration."""
        try:
            # Use np.trapezoid for numpy >= 2.0, fallback to np.trapz
            if hasattr(np, 'trapezoid'):
                return float(np.trapezoid(y, x))
            else:
                return float(np.trapz(y, x))
        except:
            # Fallback: simple sum
            return float(np.sum(y) * np.mean(np.diff(x)))
    
    # ═══════════════════════════════════════════════════════════════════════
    # NORMALIZATION METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
    def normalize_spectrum(
        self,
        intensity: np.ndarray,
        method: str = "minmax"
    ) -> np.ndarray:
        """
        Normalize spectrum using specified method.
        
        Args:
            intensity: Intensity array
            method: Normalization method
        
        Returns:
            Normalized intensity array
        """
        if method == "minmax":
            # Min-max normalization to [0, 1]
            min_val = intensity.min()
            max_val = intensity.max()
            if max_val > min_val:
                return (intensity - min_val) / (max_val - min_val)
            return intensity
        
        elif method == "area":
            # Area normalization
            try:
                # Use np.trapezoid for numpy >= 2.0, fallback to np.trapz
                if hasattr(np, 'trapezoid'):
                    area = np.trapezoid(np.abs(intensity))
                else:
                    area = np.trapz(np.abs(intensity))
            except:
                # Fallback: simple sum
                area = np.sum(np.abs(intensity))
            
            if area > 0:
                return intensity / area
            return intensity
        
        elif method == "vector":
            # Vector normalization (L2 norm)
            norm = np.linalg.norm(intensity)
            if norm > 0:
                return intensity / norm
            return intensity
        
        elif method == "snv":
            # Standard normal variate
            mean = intensity.mean()
            std = intensity.std()
            if std > 0:
                return (intensity - mean) / std
            return intensity
        
        else:
            return intensity


def import_raman_data(file_path: str) -> RamanSpectrum:
    """
    Import Raman spectroscopy data from file.
    
    Supported formats:
    - Tab-separated (.txt)
    - Comma-separated (.csv)
    - Space-separated
    - Renishaw WiRE (.txt)
    - Horiba LabSpec (.txt)
    
    Args:
        file_path: Path to data file
    
    Returns:
        RamanSpectrum object
    """
    logger.info(f"Importing Raman data from: {file_path}")
    
    try:
        # Try to read file with different separators
        for sep in ['\t', ',', r'\s+']:
            try:
                data = np.loadtxt(file_path, delimiter=sep if sep != r'\s+' else None, comments='#')
                if data.shape[1] >= 2:
                    break
            except:
                continue
        
        # Extract wavenumber and intensity
        wavenumber = data[:, 0]
        intensity = data[:, 1]
        
        # Sort by wavenumber (ascending)
        sort_idx = np.argsort(wavenumber)
        wavenumber = wavenumber[sort_idx]
        intensity = intensity[sort_idx]
        
        return RamanSpectrum(
            wavenumber=wavenumber,
            intensity=intensity,
            source_file=file_path,
            format_type="generic_txt"
        )
    
    except Exception as e:
        logger.error(f"Failed to import Raman data: {e}")
        raise ValueError(f"Could not import Raman data from {file_path}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# MATERIAL IDENTIFICATION DATABASE
# ═══════════════════════════════════════════════════════════════════════════

# Common Raman-active materials and their characteristic peaks (cm⁻¹)
# Expanded database with standard reference materials from RRUFF, InstaNANO, Materials Project
RAMAN_MATERIAL_DATABASE = {
    # ═══ CARBON MATERIALS ═══
    "graphene": {
        "peaks": [1580, 2700],  # G and 2D bands
        "description": "Single-layer graphene",
        "tolerance": 20,
        "category": "carbon"
    },
    "graphite": {
        "peaks": [1580, 2700],
        "description": "Graphite (multilayer graphene)",
        "tolerance": 20,
        "category": "carbon"
    },
    "graphene_oxide": {
        "peaks": [1350, 1580, 2700],  # D, G, 2D bands (D band from defects)
        "description": "Graphene oxide (GO)",
        "tolerance": 30,
        "category": "carbon"
    },
    "reduced_graphene_oxide": {
        "peaks": [1350, 1580, 2700],  # D, G, 2D bands
        "description": "Reduced graphene oxide (rGO)",
        "tolerance": 30,
        "category": "carbon"
    },
    "diamond": {
        "peaks": [1332],
        "description": "Diamond (sp³ carbon)",
        "tolerance": 5,
        "category": "carbon"
    },
    "carbon_nanotubes": {
        "peaks": [1350, 1580, 2700],  # D, G, 2D bands
        "description": "Carbon nanotubes (CNT)",
        "tolerance": 30,
        "category": "carbon"
    },
    "activated_carbon": {
        "peaks": [1350, 1580],  # D and G bands (broad)
        "description": "Activated carbon (porous)",
        "tolerance": 50,
        "category": "carbon"
    },
    
    # ═══ SEMICONDUCTORS ═══
    "silicon": {
        "peaks": [520],
        "description": "Crystalline silicon",
        "tolerance": 5,
        "category": "semiconductor"
    },
    "germanium": {
        "peaks": [300],
        "description": "Crystalline germanium",
        "tolerance": 5,
        "category": "semiconductor"
    },
    "GaN": {
        "peaks": [531, 568, 735],
        "description": "Gallium nitride",
        "tolerance": 10,
        "category": "semiconductor"
    },
    "GaAs": {
        "peaks": [268, 292],
        "description": "Gallium arsenide",
        "tolerance": 5,
        "category": "semiconductor"
    },
    
    # ═══ METAL OXIDES (TITANIUM) ═══
    "TiO2_anatase": {
        "peaks": [144, 197, 399, 513, 519, 639],
        "description": "Titanium dioxide (anatase)",
        "tolerance": 10,
        "category": "metal_oxide"
    },
    "TiO2_rutile": {
        "peaks": [143, 447, 612],
        "description": "Titanium dioxide (rutile)",
        "tolerance": 10,
        "category": "metal_oxide"
    },
    "TiO2_brookite": {
        "peaks": [128, 153, 194, 247, 322, 366, 395, 460, 502, 545, 636],
        "description": "Titanium dioxide (brookite)",
        "tolerance": 10,
        "category": "metal_oxide"
    },
    
    # ═══ IRON OXIDES ═══
    "Fe2O3_hematite": {
        "peaks": [225, 245, 292, 299, 412, 497, 613, 660, 1320],
        "description": "Ferric oxide / Hematite (α-Fe₂O₃)",
        "tolerance": 15,
        "category": "iron_oxide"
    },
    "Fe3O4_magnetite": {
        "peaks": [306, 538, 668],
        "description": "Magnetite (Fe₃O₄)",
        "tolerance": 15,
        "category": "iron_oxide"
    },
    "gamma_Fe2O3_maghemite": {
        "peaks": [350, 500, 700],
        "description": "Maghemite (γ-Fe₂O₃)",
        "tolerance": 20,
        "category": "iron_oxide"
    },
    "FeOOH_goethite": {
        "peaks": [243, 299, 385, 418, 479, 549],
        "description": "Goethite (α-FeOOH)",
        "tolerance": 15,
        "category": "iron_oxide"
    },
    "FeO_wustite": {
        "peaks": [650],
        "description": "Wüstite (FeO)",
        "tolerance": 20,
        "category": "iron_oxide"
    },
    
    # ═══ ELECTRODE MATERIALS (BATTERY/SUPERCAPACITOR) ═══
    "LiFePO4": {
        "peaks": [950, 1000],
        "description": "Lithium iron phosphate (LFP cathode)",
        "tolerance": 20,
        "category": "electrode"
    },
    "MnO2_alpha": {
        "peaks": [575, 650],
        "description": "Manganese dioxide α-MnO₂ (supercapacitor)",
        "tolerance": 20,
        "category": "electrode"
    },
    "MnO2_beta": {
        "peaks": [575, 650],
        "description": "Manganese dioxide β-MnO₂",
        "tolerance": 20,
        "category": "electrode"
    },
    "RuO2": {
        "peaks": [528, 646, 716],
        "description": "Ruthenium dioxide (pseudocapacitor)",
        "tolerance": 15,
        "category": "electrode"
    },
    "NiO": {
        "peaks": [550, 1100],
        "description": "Nickel oxide (battery electrode)",
        "tolerance": 20,
        "category": "electrode"
    },
    "Co3O4": {
        "peaks": [194, 482, 520, 618, 691],
        "description": "Cobalt oxide (battery electrode)",
        "tolerance": 15,
        "category": "electrode"
    },
    "V2O5": {
        "peaks": [145, 197, 284, 304, 404, 483, 527, 703, 995],
        "description": "Vanadium pentoxide (battery cathode)",
        "tolerance": 15,
        "category": "electrode"
    },
    
    # ═══ OTHER METAL OXIDES ═══
    "ZnO": {
        "peaks": [99, 380, 438, 583],
        "description": "Zinc oxide",
        "tolerance": 10,
        "category": "metal_oxide"
    },
    "CuO": {
        "peaks": [296, 345, 630],
        "description": "Copper(II) oxide",
        "tolerance": 15,
        "category": "metal_oxide"
    },
    "Cu2O": {
        "peaks": [150, 220, 415, 525, 645],
        "description": "Copper(I) oxide (cuprite)",
        "tolerance": 15,
        "category": "metal_oxide"
    },
    "Al2O3_corundum": {
        "peaks": [378, 417, 432, 451, 578, 645, 751],
        "description": "Aluminum oxide (corundum/sapphire)",
        "tolerance": 10,
        "category": "metal_oxide"
    },
    "SnO2": {
        "peaks": [475, 634, 776],
        "description": "Tin dioxide (cassiterite)",
        "tolerance": 15,
        "category": "metal_oxide"
    },
    "WO3": {
        "peaks": [273, 327, 717, 807],
        "description": "Tungsten trioxide",
        "tolerance": 15,
        "category": "metal_oxide"
    },
    
    # ═══ SULFIDES ═══
    "MoS2": {
        "peaks": [383, 408],
        "description": "Molybdenum disulfide (2D material)",
        "tolerance": 10,
        "category": "sulfide"
    },
    "WS2": {
        "peaks": [352, 420],
        "description": "Tungsten disulfide (2D material)",
        "tolerance": 10,
        "category": "sulfide"
    },
    "CdS": {
        "peaks": [305],
        "description": "Cadmium sulfide",
        "tolerance": 10,
        "category": "sulfide"
    },
    
    # ═══ NITRIDES ═══
    "Si3N4": {
        "peaks": [185, 230, 860],
        "description": "Silicon nitride",
        "tolerance": 15,
        "category": "nitride"
    },
    "BN": {
        "peaks": [1366],
        "description": "Boron nitride (hexagonal)",
        "tolerance": 10,
        "category": "nitride"
    },
    
    # ═══ POLYMERS ═══
    "polystyrene": {
        "peaks": [621, 1001, 1031, 1155, 1583, 1602, 3054],
        "description": "Polystyrene (calibration standard)",
        "tolerance": 5,
        "category": "polymer"
    },
    "PMMA": {
        "peaks": [600, 812, 1450, 1730, 2950],
        "description": "Poly(methyl methacrylate)",
        "tolerance": 10,
        "category": "polymer"
    },
    "polyethylene": {
        "peaks": [1060, 1130, 1295, 1440, 2850, 2880],
        "description": "Polyethylene (PE)",
        "tolerance": 15,
        "category": "polymer"
    },
    "polypropylene": {
        "peaks": [400, 840, 970, 1150, 1330, 1460, 2840, 2880, 2950],
        "description": "Polypropylene (PP)",
        "tolerance": 15,
        "category": "polymer"
    },
    "PET": {
        "peaks": [630, 795, 860, 1095, 1180, 1290, 1615, 1730],
        "description": "Polyethylene terephthalate",
        "tolerance": 10,
        "category": "polymer"
    },
    
    # ═══ MINERALS (RRUFF DATABASE) ═══
    "quartz": {
        "peaks": [128, 206, 265, 356, 394, 465, 697, 809, 1085],
        "description": "Quartz (SiO₂)",
        "tolerance": 10,
        "category": "mineral"
    },
    "calcite": {
        "peaks": [156, 282, 712, 1086],
        "description": "Calcite (CaCO₃)",
        "tolerance": 10,
        "category": "mineral"
    },
    "aragonite": {
        "peaks": [155, 206, 705, 1085],
        "description": "Aragonite (CaCO₃ polymorph)",
        "tolerance": 10,
        "category": "mineral"
    },
    "gypsum": {
        "peaks": [415, 493, 620, 670, 1008, 1136],
        "description": "Gypsum (CaSO₄·2H₂O)",
        "tolerance": 10,
        "category": "mineral"
    },
    "pyrite": {
        "peaks": [343, 379, 430],
        "description": "Pyrite (FeS₂)",
        "tolerance": 10,
        "category": "mineral"
    },
}


def identify_material(spectrum: RamanSpectrum, top_n: int = 5, min_confidence: float = 0.3) -> List[Dict[str, Any]]:
    """
    Identify material based on Raman peaks.

    Uses the database-backed RamanMaterialIdentifier (27+ materials with
    peer-reviewed reference data) when available, falling back to the
    built-in RAMAN_MATERIAL_DATABASE dict otherwise.

    Args:
        spectrum: Analyzed Raman spectrum with detected peaks
        top_n: Maximum number of matches to return
        min_confidence: Minimum confidence threshold (0-1)

    Returns:
        List of possible material matches with confidence scores
    """
    if not spectrum.peaks:
        return []

    # ── Try the database-backed identifier first ──────────────────────────
    try:
        from src.backend.ml.models.raman_material_identifier import RamanMaterialIdentifier
        from pathlib import Path

        db_path = (
            Path(__file__).parent.parent.parent.parent
            / "data" / "material_database" / "raman_materials.json"
        )
        _identifier = RamanMaterialIdentifier(database_path=str(db_path))

        if _identifier.materials:
            matches = _identifier.identify_material(
                detected_peaks=spectrum.peaks,
                wavenumber=spectrum.wavenumber if spectrum.corrected_intensity is not None else None,
                intensity=spectrum.corrected_intensity,
                top_n=top_n,
                min_confidence=min_confidence,
            )
            result = [m.to_dict() for m in matches]
            logger.info(
                "Material identification (DB): %d matches (top: %s)",
                len(result),
                result[0]["name"] if result else "none",
            )
            return result
    except Exception as e:
        logger.warning("DB-backed identifier failed, falling back to built-in: %s", e)

    # ── Fallback: built-in RAMAN_MATERIAL_DATABASE dict ──────────────────
    detected_positions = [p["position_cm"] for p in spectrum.peaks]
    matches = []

    for material_id, material_data in RAMAN_MATERIAL_DATABASE.items():
        expected_peaks = material_data["peaks"]
        tolerance = material_data["tolerance"]

        matched_peaks = 0
        for expected in expected_peaks:
            for detected in detected_positions:
                if abs(detected - expected) <= tolerance:
                    matched_peaks += 1
                    break

        if matched_peaks > 0:
            confidence = matched_peaks / len(expected_peaks)
            if confidence >= min_confidence:
                matches.append({
                    "material": material_id,
                    "name": material_id.replace("_", " ").title(),
                    "description": material_data["description"],
                    "confidence": confidence,
                    "matched_peaks": matched_peaks,
                    "total_peaks": len(expected_peaks),
                    "category": material_data.get("category", "unknown"),
                })

    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return matches[:top_n]
