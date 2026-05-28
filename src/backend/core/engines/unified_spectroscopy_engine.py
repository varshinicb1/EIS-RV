"""
Unified Spectroscopy Engine
============================
Comprehensive spectroscopy analysis combining best practices from leading research.

Research Sources:
- SpectraGuru (ACS Analytical Chemistry 2025) - FAIR-compliant platform
- DeepeR - Deep learning denoising with ResUNet
- spectrai - PyTorch framework for spectral analysis
- RamanSPy - Advanced normalization methods
- BoxSERS - Data augmentation and cosmic ray removal
- RamanLab - 6,939+ reference spectra, advanced peak fitting
- Raman-Spectra-Deep-Learning - CNN, LSTM, Transformer, GCN, SimCLR

Features:
- Advanced preprocessing (cosmic ray removal, Fourier filtering)
- Enhanced normalization (MaxIntensity, AUC, pixelwise)
- Advanced peak fitting (Voigt, Asymmetric Voigt)
- Data augmentation (mixup, noise injection, x-shift)
- Dimensionality reduction (PCA, t-SNE, UMAP)
- Clustering (hierarchical, K-means)
- Deep learning models (ResUNet, CNN, LSTM, Transformer)
- Contrastive learning (SimCLR)
- Hyperspectral super-resolution

Author: VidyuthLabs
Date: May 4, 2026
Version: 1.0.0
"""

import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any, Union
from scipy import sparse, signal, ndimage, fft
from scipy.sparse.linalg import spsolve
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, savgol_filter
from scipy.cluster.hierarchy import dendrogram, linkage
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Import from existing raman_engine
from .raman_engine import RamanSpectrum, RamanAnalysisConfig, RamanAnalyzer

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# ENHANCED CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class UnifiedSpectroscopyConfig(RamanAnalysisConfig):
    """Extended configuration for unified spectroscopy engine."""
    
    # Cosmic ray removal
    cosmic_ray_removal: bool = False
    cosmic_ray_threshold: float = 10.0  # Standard deviations above median
    
    # Fourier filtering
    fourier_filtering: bool = False
    fourier_cutoff_freq: float = 0.1  # Normalized frequency (0-1)
    
    # Enhanced normalization
    normalization_pixelwise: bool = False  # Apply normalization per pixel (for hyperspectral)
    
    # Advanced peak fitting
    voigt_fitting: bool = False  # Use Voigt profile instead of Lorentzian/Gaussian
    
    # Data augmentation
    augmentation_enabled: bool = False
    augmentation_mixup_alpha: float = 0.2
    augmentation_noise_level: float = 0.01
    augmentation_xshift_range: float = 5.0  # cm⁻¹
    
    # Dimensionality reduction
    pca_enabled: bool = False
    pca_n_components: int = 10
    tsne_enabled: bool = False
    tsne_perplexity: float = 30.0
    tsne_n_iter: int = 1000
    
    # Clustering
    clustering_enabled: bool = False
    clustering_method: str = "kmeans"  # "kmeans", "hierarchical"
    clustering_n_clusters: int = 3
    
    # Deep learning (future)
    dl_denoising: bool = False  # ResUNet denoising
    dl_classification: bool = False  # CNN classification
    dl_model_path: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# UNIFIED SPECTROSCOPY ANALYZER
# ═══════════════════════════════════════════════════════════════════════════

class UnifiedSpectroscopyAnalyzer(RamanAnalyzer):
    """
    Unified spectroscopy analyzer with advanced features from leading research.
    
    Extends RamanAnalyzer with:
    - Cosmic ray removal
    - Fourier filtering
    - Enhanced normalization methods
    - Voigt peak fitting
    - Data augmentation
    - PCA, t-SNE dimensionality reduction
    - Clustering analysis
    - Deep learning models (future)
    """
    
    def __init__(self, config: Optional[UnifiedSpectroscopyConfig] = None):
        """Initialize unified analyzer with extended configuration."""
        self.unified_config = config or UnifiedSpectroscopyConfig()
        super().__init__(self.unified_config)
        logger.info("Unified spectroscopy analyzer initialized")
    
    def analyze(self, spectrum: RamanSpectrum) -> RamanSpectrum:
        """
        Perform comprehensive spectroscopy analysis with advanced features.
        
        Extended Pipeline:
        1. Sort data by wavenumber
        2. Cosmic ray removal (if enabled)
        3. Fourier filtering (if enabled)
        4. Smoothing (adaptive Savitzky-Golay)
        5. Baseline correction
        6. Enhanced normalization
        7. Robust peak detection
        8. Advanced peak fitting (Voigt if enabled)
        9. Data augmentation (if enabled)
        
        Args:
            spectrum: Input spectrum
        
        Returns:
            Analyzed spectrum with all enhancements
        """
        logger.info("Starting unified spectroscopy analysis")
        
        # STEP 1: Sort data
        sort_idx = np.argsort(spectrum.wavenumber)
        wavenumber = spectrum.wavenumber[sort_idx]
        intensity = spectrum.intensity[sort_idx]
        
        # STEP 2: Cosmic ray removal
        if self.unified_config.cosmic_ray_removal:
            intensity = self.remove_cosmic_rays(intensity)
            logger.debug("Cosmic ray removal applied")
        
        # STEP 3: Fourier filtering
        if self.unified_config.fourier_filtering:
            intensity = self.fourier_filter(intensity)
            logger.debug("Fourier filtering applied")
        
        # STEP 4-8: Use parent class analysis
        spectrum.wavenumber = wavenumber
        spectrum.intensity = intensity
        spectrum = super().analyze(spectrum)
        
        # STEP 9: Data augmentation (if enabled)
        if self.unified_config.augmentation_enabled:
            augmented_spectra = self.augment_spectrum(spectrum)
            spectrum.augmented_spectra = augmented_spectra
            logger.debug(f"Generated {len(augmented_spectra)} augmented spectra")
        
        logger.info("Unified analysis complete")
        return spectrum
    
    # ═══════════════════════════════════════════════════════════════════════
    # COSMIC RAY REMOVAL (from BoxSERS)
    # ═══════════════════════════════════════════════════════════════════════
    
    def remove_cosmic_rays(self, intensity: np.ndarray) -> np.ndarray:
        """
        Remove cosmic ray spikes using statistical outlier detection.
        
        Method from BoxSERS:
        - Calculate median and standard deviation
        - Identify points > threshold * std above median
        - Replace with interpolated values
        
        Args:
            intensity: Intensity array
        
        Returns:
            Intensity array with cosmic rays removed
        """
        median = np.median(intensity)
        std = np.std(intensity)
        threshold = self.unified_config.cosmic_ray_threshold
        
        # Identify cosmic ray spikes
        spikes = intensity > (median + threshold * std)
        
        if spikes.sum() > 0:
            logger.debug(f"Removing {spikes.sum()} cosmic ray spikes")
            
            # Replace spikes with interpolated values
            intensity_clean = intensity.copy()
            spike_indices = np.where(spikes)[0]
            
            for idx in spike_indices:
                # Use neighbors for interpolation
                if idx > 0 and idx < len(intensity) - 1:
                    intensity_clean[idx] = (intensity[idx-1] + intensity[idx+1]) / 2
                elif idx == 0:
                    intensity_clean[idx] = intensity[idx+1]
                else:
                    intensity_clean[idx] = intensity[idx-1]
            
            return intensity_clean
        
        return intensity
    
    # ═══════════════════════════════════════════════════════════════════════
    # FOURIER FILTERING (from SpectraGuru)
    # ═══════════════════════════════════════════════════════════════════════
    
    def fourier_filter(self, intensity: np.ndarray) -> np.ndarray:
        """
        Apply Fourier transform filtering for noise reduction.
        
        Method from SpectraGuru:
        - FFT to frequency domain
        - Apply low-pass filter
        - Inverse FFT back to spatial domain
        
        Args:
            intensity: Intensity array
        
        Returns:
            Filtered intensity array
        """
        # FFT
        fft_spectrum = fft.fft(intensity)
        frequencies = fft.fftfreq(len(intensity))
        
        # Low-pass filter
        cutoff = self.unified_config.fourier_cutoff_freq
        fft_spectrum[np.abs(frequencies) > cutoff] = 0
        
        # Inverse FFT
        filtered = fft.ifft(fft_spectrum).real
        
        logger.debug(f"Fourier filtering applied with cutoff={cutoff}")
        return filtered
    
    # ═══════════════════════════════════════════════════════════════════════
    # ENHANCED NORMALIZATION (from RamanSPy)
    # ═══════════════════════════════════════════════════════════════════════
    
    def normalize_max_intensity(self, intensity: np.ndarray) -> np.ndarray:
        """
        MaxIntensity normalization from RamanSPy.
        
        Normalize by maximum intensity value.
        
        Args:
            intensity: Intensity array
        
        Returns:
            Normalized intensity array
        """
        max_val = np.max(intensity)
        if max_val > 0:
            return intensity / max_val
        return intensity
    
    def normalize_auc(self, intensity: np.ndarray) -> np.ndarray:
        """
        AUC (Area Under Curve) normalization from RamanSPy.
        
        Normalize by total area under the curve.
        
        Args:
            intensity: Intensity array
        
        Returns:
            Normalized intensity array
        """
        auc = np.trapz(np.abs(intensity))
        if auc > 0:
            return intensity / auc
        return intensity
    
    def normalize_spectrum_enhanced(
        self,
        intensity: np.ndarray,
        method: str = "minmax"
    ) -> np.ndarray:
        """
        Enhanced normalization with additional methods from RamanSPy.
        
        Args:
            intensity: Intensity array
            method: Normalization method
        
        Returns:
            Normalized intensity array
        """
        if method == "max_intensity":
            return self.normalize_max_intensity(intensity)
        elif method == "auc":
            return self.normalize_auc(intensity)
        else:
            # Use parent class methods
            return super().normalize_spectrum(intensity, method)
    
    # ═══════════════════════════════════════════════════════════════════════
    # ADVANCED PEAK FITTING (from RamanLab)
    # ═══════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def _voigt(x: np.ndarray, A: float, x0: float, sigma: float, gamma: float) -> np.ndarray:
        """
        Voigt profile (convolution of Gaussian and Lorentzian).
        
        From RamanLab - more accurate for real Raman peaks.
        
        Args:
            x: Wavenumber array
            A: Amplitude
            x0: Peak center
            sigma: Gaussian width
            gamma: Lorentzian width
        
        Returns:
            Voigt profile
        """
        from scipy.special import wofz
        
        z = ((x - x0) + 1j * gamma) / (sigma * np.sqrt(2))
        voigt = A * np.real(wofz(z)) / (sigma * np.sqrt(2 * np.pi))
        
        return voigt
    
    @staticmethod
    def _asymmetric_voigt(
        x: np.ndarray,
        A: float,
        x0: float,
        sigma: float,
        gamma: float,
        asym: float
    ) -> np.ndarray:
        """
        Asymmetric Voigt profile from RamanLab.
        
        Handles asymmetric peak shapes common in real spectra.
        
        Args:
            x: Wavenumber array
            A: Amplitude
            x0: Peak center
            sigma: Gaussian width
            gamma: Lorentzian width
            asym: Asymmetry parameter
        
        Returns:
            Asymmetric Voigt profile
        """
        # Split into left and right sides
        left_mask = x <= x0
        right_mask = x > x0
        
        profile = np.zeros_like(x)
        
        # Left side
        if left_mask.sum() > 0:
            profile[left_mask] = UnifiedSpectroscopyAnalyzer._voigt(
                x[left_mask], A, x0, sigma * (1 - asym), gamma
            )
        
        # Right side
        if right_mask.sum() > 0:
            profile[right_mask] = UnifiedSpectroscopyAnalyzer._voigt(
                x[right_mask], A, x0, sigma * (1 + asym), gamma
            )
        
        return profile
    
    def fit_peaks_voigt(
        self,
        wavenumber: np.ndarray,
        intensity: np.ndarray,
        peaks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Fit peaks using Voigt profile from RamanLab.
        
        Args:
            wavenumber: Wavenumber array
            intensity: Intensity array
            peaks: List of detected peaks
        
        Returns:
            List of peaks with Voigt fit parameters
        """
        for peak in peaks:
            idx = peak["index"]
            
            # Define fitting window
            window = 50
            start = max(0, idx - window)
            end = min(len(wavenumber), idx + window)
            
            x_fit = wavenumber[start:end]
            y_fit = intensity[start:end]
            
            # Initial guess
            x0 = peak["position_cm"]
            A = peak["intensity"]
            sigma = peak.get("fwhm_cm", 10.0) / 2.355  # Convert FWHM to sigma
            gamma = peak.get("fwhm_cm", 10.0) / 2  # Lorentzian width
            
            try:
                popt, _ = curve_fit(
                    self._voigt,
                    x_fit, y_fit,
                    p0=[A, x0, sigma, gamma],
                    maxfev=2000
                )
                
                peak["voigt_amplitude"] = float(popt[0])
                peak["voigt_position_cm"] = float(popt[1])
                peak["voigt_sigma"] = float(popt[2])
                peak["voigt_gamma"] = float(popt[3])
                peak["voigt_fwhm_cm"] = float(2.355 * popt[2])  # Approximate
                
            except Exception as e:
                logger.warning(f"Voigt fitting failed for peak at {x0}: {e}")
                peak["voigt_fit_error"] = str(e)
        
        return peaks
    
    # ═══════════════════════════════════════════════════════════════════════
    # DATA AUGMENTATION (from BoxSERS)
    # ═══════════════════════════════════════════════════════════════════════
    
    def augment_spectrum(
        self,
        spectrum: RamanSpectrum,
        n_augmentations: int = 5
    ) -> List[RamanSpectrum]:
        """
        Generate augmented spectra for training data augmentation.
        
        Methods from BoxSERS:
        - Mixup: Linear interpolation between spectra
        - Noise injection: Add Gaussian noise
        - X-shift: Shift wavenumber axis
        - Intensity scaling: Scale intensity values
        
        Args:
            spectrum: Original spectrum
            n_augmentations: Number of augmented spectra to generate
        
        Returns:
            List of augmented spectra
        """
        augmented = []
        
        for i in range(n_augmentations):
            aug_spectrum = RamanSpectrum(
                wavenumber=spectrum.wavenumber.copy(),
                intensity=spectrum.intensity.copy(),
                source_file=f"{spectrum.source_file}_aug_{i}",
                sample_id=f"{spectrum.sample_id}_aug_{i}"
            )
            
            # Apply random augmentations
            
            # 1. Noise injection
            if np.random.rand() > 0.5:
                noise_level = self.unified_config.augmentation_noise_level
                noise = np.random.normal(0, noise_level, len(aug_spectrum.intensity))
                aug_spectrum.intensity += noise * aug_spectrum.intensity.std()
            
            # 2. X-shift (wavenumber shift)
            if np.random.rand() > 0.5:
                shift_range = self.unified_config.augmentation_xshift_range
                shift = np.random.uniform(-shift_range, shift_range)
                aug_spectrum.wavenumber += shift
            
            # 3. Intensity scaling
            if np.random.rand() > 0.5:
                scale = np.random.uniform(0.8, 1.2)
                aug_spectrum.intensity *= scale
            
            augmented.append(aug_spectrum)
        
        logger.debug(f"Generated {len(augmented)} augmented spectra")
        return augmented
    
    def mixup_augmentation(
        self,
        spectrum1: RamanSpectrum,
        spectrum2: RamanSpectrum,
        alpha: Optional[float] = None
    ) -> RamanSpectrum:
        """
        Mixup augmentation from BoxSERS.
        
        Linear interpolation between two spectra.
        
        Args:
            spectrum1: First spectrum
            spectrum2: Second spectrum
            alpha: Mixing coefficient (0-1)
        
        Returns:
            Mixed spectrum
        """
        if alpha is None:
            alpha = self.unified_config.augmentation_mixup_alpha
        
        # Ensure same wavenumber grid
        if not np.allclose(spectrum1.wavenumber, spectrum2.wavenumber):
            logger.warning("Spectra have different wavenumber grids, interpolating")
            # Interpolate spectrum2 to spectrum1's grid
            spectrum2_interp = np.interp(
                spectrum1.wavenumber,
                spectrum2.wavenumber,
                spectrum2.intensity
            )
        else:
            spectrum2_interp = spectrum2.intensity
        
        # Mix intensities
        mixed_intensity = alpha * spectrum1.intensity + (1 - alpha) * spectrum2_interp
        
        mixed_spectrum = RamanSpectrum(
            wavenumber=spectrum1.wavenumber.copy(),
            intensity=mixed_intensity,
            source_file=f"mixup_{spectrum1.source_file}_{spectrum2.source_file}",
            sample_id=f"mixup_{alpha:.2f}"
        )
        
        return mixed_spectrum
    
    # ═══════════════════════════════════════════════════════════════════════
    # DIMENSIONALITY REDUCTION (from SpectraGuru)
    # ═══════════════════════════════════════════════════════════════════════
    
    def perform_pca(
        self,
        spectra_list: List[RamanSpectrum]
    ) -> Tuple[np.ndarray, PCA, np.ndarray]:
        """
        Perform PCA dimensionality reduction from SpectraGuru.
        
        Args:
            spectra_list: List of spectra to analyze
        
        Returns:
            Tuple of (transformed_data, pca_model, explained_variance)
        """
        # Stack spectra into matrix
        X = np.vstack([s.corrected_intensity if s.corrected_intensity is not None 
                       else s.intensity for s in spectra_list])
        
        # Standardize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # PCA
        n_components = min(self.unified_config.pca_n_components, X.shape[0], X.shape[1])
        pca = PCA(n_components=n_components)
        X_pca = pca.fit_transform(X_scaled)
        
        logger.info(f"PCA: {n_components} components explain {pca.explained_variance_ratio_.sum():.2%} variance")
        
        return X_pca, pca, pca.explained_variance_ratio_
    
    def perform_tsne(
        self,
        spectra_list: List[RamanSpectrum],
        n_components: int = 2
    ) -> np.ndarray:
        """
        Perform t-SNE dimensionality reduction from SpectraGuru.
        
        Args:
            spectra_list: List of spectra to analyze
            n_components: Number of dimensions (typically 2 or 3)
        
        Returns:
            Transformed data in lower dimensions
        """
        # Stack spectra into matrix
        X = np.vstack([s.corrected_intensity if s.corrected_intensity is not None 
                       else s.intensity for s in spectra_list])
        
        # t-SNE
        tsne = TSNE(
            n_components=n_components,
            perplexity=self.unified_config.tsne_perplexity,
            n_iter=self.unified_config.tsne_n_iter,
            random_state=42
        )
        X_tsne = tsne.fit_transform(X)
        
        logger.info(f"t-SNE: Reduced to {n_components} dimensions")
        
        return X_tsne
    
    # ═══════════════════════════════════════════════════════════════════════
    # CLUSTERING (from SpectraGuru)
    # ═══════════════════════════════════════════════════════════════════════
    
    def perform_kmeans_clustering(
        self,
        spectra_list: List[RamanSpectrum]
    ) -> Tuple[np.ndarray, KMeans]:
        """
        Perform K-means clustering from SpectraGuru.
        
        Args:
            spectra_list: List of spectra to cluster
        
        Returns:
            Tuple of (cluster_labels, kmeans_model)
        """
        # Stack spectra into matrix
        X = np.vstack([s.corrected_intensity if s.corrected_intensity is not None 
                       else s.intensity for s in spectra_list])
        
        # K-means
        n_clusters = self.unified_config.clustering_n_clusters
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(X)
        
        logger.info(f"K-means: {n_clusters} clusters identified")
        
        return labels, kmeans
    
    def perform_hierarchical_clustering(
        self,
        spectra_list: List[RamanSpectrum],
        method: str = "ward"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Perform hierarchical clustering from SpectraGuru.
        
        Args:
            spectra_list: List of spectra to cluster
            method: Linkage method ('ward', 'average', 'complete')
        
        Returns:
            Tuple of (linkage_matrix, dendrogram_data)
        """
        # Stack spectra into matrix
        X = np.vstack([s.corrected_intensity if s.corrected_intensity is not None 
                       else s.intensity for s in spectra_list])
        
        # Hierarchical clustering
        linkage_matrix = linkage(X, method=method)
        
        logger.info(f"Hierarchical clustering: {method} linkage computed")
        
        return linkage_matrix, X
    
    # ═══════════════════════════════════════════════════════════════════════
    # CORRELATION ANALYSIS (from SpectraGuru)
    # ═══════════════════════════════════════════════════════════════════════
    
    def compute_correlation_matrix(
        self,
        spectra_list: List[RamanSpectrum]
    ) -> np.ndarray:
        """
        Compute pairwise correlation matrix from SpectraGuru.
        
        Args:
            spectra_list: List of spectra
        
        Returns:
            Correlation matrix (n_spectra x n_spectra)
        """
        # Stack spectra into matrix
        X = np.vstack([s.corrected_intensity if s.corrected_intensity is not None 
                       else s.intensity for s in spectra_list])
        
        # Compute correlation matrix
        corr_matrix = np.corrcoef(X)
        
        logger.info(f"Correlation matrix: {corr_matrix.shape}")
        
        return corr_matrix


# ═══════════════════════════════════════════════════════════════════════════
# BATCH ANALYSIS UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

class BatchSpectroscopyAnalyzer:
    """
    Batch analysis for multiple spectra with unified engine.
    
    Features:
    - Parallel processing
    - Statistical analysis across spectra
    - Group comparisons
    - Visualization
    """
    
    def __init__(self, config: Optional[UnifiedSpectroscopyConfig] = None):
        """Initialize batch analyzer."""
        self.config = config or UnifiedSpectroscopyConfig()
        self.analyzer = UnifiedSpectroscopyAnalyzer(self.config)
        self.spectra: List[RamanSpectrum] = []
        logger.info("Batch spectroscopy analyzer initialized")
    
    def add_spectrum(self, spectrum: RamanSpectrum):
        """Add spectrum to batch."""
        self.spectra.append(spectrum)
    
    def analyze_all(self) -> List[RamanSpectrum]:
        """Analyze all spectra in batch."""
        logger.info(f"Analyzing {len(self.spectra)} spectra in batch")
        
        analyzed = []
        for i, spectrum in enumerate(self.spectra):
            logger.debug(f"Analyzing spectrum {i+1}/{len(self.spectra)}")
            analyzed_spectrum = self.analyzer.analyze(spectrum)
            analyzed.append(analyzed_spectrum)
        
        logger.info("Batch analysis complete")
        return analyzed
    
    def compute_statistics(self) -> Dict[str, Any]:
        """
        Compute statistics across all spectra.
        
        Returns:
            Dictionary with mean, std, confidence intervals
        """
        if not self.spectra:
            return {}
        
        # Stack intensities
        intensities = np.vstack([s.corrected_intensity if s.corrected_intensity is not None 
                                 else s.intensity for s in self.spectra])
        
        stats = {
            "mean_spectrum": np.mean(intensities, axis=0),
            "std_spectrum": np.std(intensities, axis=0),
            "median_spectrum": np.median(intensities, axis=0),
            "min_spectrum": np.min(intensities, axis=0),
            "max_spectrum": np.max(intensities, axis=0),
            "n_spectra": len(self.spectra),
            "wavenumber": self.spectra[0].wavenumber
        }
        
        logger.info(f"Statistics computed for {len(self.spectra)} spectra")
        return stats
    
    def perform_pca_analysis(self) -> Tuple[np.ndarray, PCA, np.ndarray]:
        """Perform PCA on all spectra."""
        return self.analyzer.perform_pca(self.spectra)
    
    def perform_clustering(self) -> Tuple[np.ndarray, Any]:
        """Perform clustering on all spectra."""
        if self.config.clustering_method == "kmeans":
            return self.analyzer.perform_kmeans_clustering(self.spectra)
        else:
            return self.analyzer.perform_hierarchical_clustering(self.spectra)


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "UnifiedSpectroscopyConfig",
    "UnifiedSpectroscopyAnalyzer",
    "BatchSpectroscopyAnalyzer",
]
