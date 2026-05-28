"""
Comprehensive Test Suite for Unified Spectroscopy Engine
=========================================================

Tests all features:
- Baseline correction methods
- Peak detection with adaptive thresholds
- Cosmic ray removal
- Fourier filtering
- Voigt peak fitting
- Material identification
- Data augmentation
- PCA and clustering
- Theme-aware plotting

Author: VidyuthLabs
Date: May 5, 2026
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path

# Import engines
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend"))

from src.backend.core.engines.raman_engine import (
    RamanSpectrum,
    RamanAnalyzer,
    RamanAnalysisConfig,
    import_raman_data,
    identify_material,
    RAMAN_MATERIAL_DATABASE,
)
from src.backend.core.engines.unified_spectroscopy_engine import (
    UnifiedSpectroscopyAnalyzer,
    UnifiedSpectroscopyConfig,
    BatchSpectroscopyAnalyzer,
)


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def synthetic_spectrum():
    """Generate synthetic Raman spectrum with known peaks."""
    wavenumber = np.linspace(100, 3000, 1000)
    
    # Add Gaussian peaks at known positions
    peak_positions = [520, 1350, 1580, 2700]  # Silicon + graphene-like
    peak_intensities = [0.8, 0.5, 1.0, 0.6]
    peak_widths = [10, 30, 20, 40]
    
    intensity = np.zeros_like(wavenumber)
    
    for pos, amp, width in zip(peak_positions, peak_intensities, peak_widths):
        intensity += amp * np.exp(-((wavenumber - pos) ** 2) / (2 * width ** 2))
    
    # Add baseline (polynomial)
    baseline = 0.1 + 0.0001 * wavenumber + 1e-8 * wavenumber ** 2
    intensity += baseline
    
    # Add noise
    noise = np.random.normal(0, 0.02, len(wavenumber))
    intensity += noise
    
    return RamanSpectrum(
        wavenumber=wavenumber,
        intensity=intensity,
        source_file="synthetic_test.txt",
        sample_id="test_001"
    )


@pytest.fixture
def ferric_oxide_spectrum():
    """Generate synthetic ferric oxide (hematite) spectrum."""
    wavenumber = np.linspace(100, 1500, 800)
    
    # Ferric oxide peaks from database
    peak_positions = [225, 245, 292, 299, 412, 497, 613, 660, 1320]
    peak_intensities = [0.3, 0.4, 0.6, 0.5, 0.7, 0.5, 0.4, 0.3, 0.2]
    peak_widths = [15, 15, 15, 15, 20, 20, 20, 20, 30]
    
    intensity = np.zeros_like(wavenumber)
    
    for pos, amp, width in zip(peak_positions, peak_intensities, peak_widths):
        if pos <= wavenumber.max():
            intensity += amp * np.exp(-((wavenumber - pos) ** 2) / (2 * width ** 2))
    
    # Add baseline
    baseline = 0.05 + 0.0001 * wavenumber
    intensity += baseline
    
    # Add noise
    noise = np.random.normal(0, 0.01, len(wavenumber))
    intensity += noise
    
    return RamanSpectrum(
        wavenumber=wavenumber,
        intensity=intensity,
        source_file="ferric_oxide_test.txt",
        sample_id="Fe2O3_001"
    )


@pytest.fixture
def noisy_spectrum_with_cosmic_rays():
    """Generate spectrum with cosmic ray spikes."""
    wavenumber = np.linspace(200, 2000, 500)
    
    # Base spectrum
    intensity = 0.5 + 0.3 * np.sin(wavenumber / 200)
    
    # Add cosmic ray spikes (random high-intensity points)
    cosmic_ray_indices = np.random.choice(len(wavenumber), size=5, replace=False)
    for idx in cosmic_ray_indices:
        intensity[idx] += np.random.uniform(2.0, 5.0)
    
    # Add noise
    noise = np.random.normal(0, 0.05, len(wavenumber))
    intensity += noise
    
    return RamanSpectrum(
        wavenumber=wavenumber,
        intensity=intensity,
        source_file="cosmic_ray_test.txt",
        sample_id="CR_001"
    )


# ═══════════════════════════════════════════════════════════════════════════
# BASIC RAMAN ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_raman_spectrum_creation(synthetic_spectrum):
    """Test RamanSpectrum object creation."""
    assert len(synthetic_spectrum.wavenumber) == 1000
    assert len(synthetic_spectrum.intensity) == 1000
    assert synthetic_spectrum.source_file == "synthetic_test.txt"
    assert synthetic_spectrum.sample_id == "test_001"


def test_baseline_correction_als(synthetic_spectrum):
    """Test AsLS baseline correction."""
    config = RamanAnalysisConfig(baseline_method="als")
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    assert result.baseline is not None
    assert len(result.baseline) == len(result.wavenumber)
    assert result.corrected_intensity is not None
    assert len(result.corrected_intensity) == len(result.wavenumber)


def test_baseline_correction_airpls(synthetic_spectrum):
    """Test airPLS baseline correction."""
    config = RamanAnalysisConfig(baseline_method="airpls")
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    assert result.baseline is not None
    assert result.corrected_intensity is not None


def test_baseline_correction_polynomial(synthetic_spectrum):
    """Test polynomial baseline correction."""
    config = RamanAnalysisConfig(baseline_method="polynomial", polynomial_order=3)
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    assert result.baseline is not None
    assert result.corrected_intensity is not None


def test_baseline_correction_morphological(synthetic_spectrum):
    """Test morphological baseline correction."""
    config = RamanAnalysisConfig(baseline_method="morphological")
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    assert result.baseline is not None
    assert result.corrected_intensity is not None


def test_peak_detection(synthetic_spectrum):
    """Test robust peak detection."""
    config = RamanAnalysisConfig(peak_detection=True)
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    assert len(result.peaks) > 0
    print(f"Detected {len(result.peaks)} peaks")
    
    # Check peak structure
    for peak in result.peaks:
        assert "position_cm" in peak
        assert "intensity" in peak
        assert "prominence" in peak


def test_peak_fitting_lorentzian(synthetic_spectrum):
    """Test Lorentzian peak fitting."""
    config = RamanAnalysisConfig(
        peak_detection=True,
        peak_fitting=True,
        peak_model="lorentzian"
    )
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    assert len(result.peaks) > 0
    
    # Check if fitting was attempted
    fitted_peaks = [p for p in result.peaks if "fit_amplitude" in p]
    assert len(fitted_peaks) > 0


def test_peak_fitting_gaussian(synthetic_spectrum):
    """Test Gaussian peak fitting."""
    config = RamanAnalysisConfig(
        peak_detection=True,
        peak_fitting=True,
        peak_model="gaussian"
    )
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    assert len(result.peaks) > 0
    fitted_peaks = [p for p in result.peaks if "fit_amplitude" in p]
    assert len(fitted_peaks) > 0


def test_normalization_methods(synthetic_spectrum):
    """Test all normalization methods."""
    methods = ["minmax", "area", "vector", "snv"]
    
    for method in methods:
        config = RamanAnalysisConfig(normalize=True, normalization_method=method)
        analyzer = RamanAnalyzer(config)
        
        result = analyzer.analyze(synthetic_spectrum)
        
        assert result.corrected_intensity is not None
        print(f"Normalization {method}: range {result.corrected_intensity.min():.3f} to {result.corrected_intensity.max():.3f}")


# ═══════════════════════════════════════════════════════════════════════════
# UNIFIED SPECTROSCOPY ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_cosmic_ray_removal(noisy_spectrum_with_cosmic_rays):
    """Test cosmic ray removal."""
    # Create a copy for comparison
    original_intensity = noisy_spectrum_with_cosmic_rays.intensity.copy()
    
    config = UnifiedSpectroscopyConfig(cosmic_ray_removal=True, cosmic_ray_threshold=2.0)
    analyzer = UnifiedSpectroscopyAnalyzer(config)
    
    # Analyze with cosmic ray removal
    result_with_cr = analyzer.analyze(noisy_spectrum_with_cosmic_rays)
    
    # Check that cosmic rays were removed (max intensity should be lower)
    max_original = original_intensity.max()
    max_with_cr = result_with_cr.intensity.max()
    
    print(f"Max intensity original: {max_original:.3f}")
    print(f"Max intensity with CR removal: {max_with_cr:.3f}")
    
    # Cosmic ray removal should reduce max intensity or keep it same
    assert max_with_cr <= max_original


def test_fourier_filtering(synthetic_spectrum):
    """Test Fourier filtering."""
    config = UnifiedSpectroscopyConfig(fourier_filtering=True, fourier_cutoff_freq=0.1)
    analyzer = UnifiedSpectroscopyAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    assert result.corrected_intensity is not None
    # Fourier filtering should smooth the signal
    assert np.std(result.corrected_intensity) < np.std(synthetic_spectrum.intensity)


def test_voigt_peak_fitting(synthetic_spectrum):
    """Test Voigt profile peak fitting."""
    config = UnifiedSpectroscopyConfig(
        peak_detection=True,
        peak_fitting=True,
        voigt_fitting=True
    )
    analyzer = UnifiedSpectroscopyAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    assert len(result.peaks) > 0
    
    # Check for Voigt fit parameters
    voigt_fitted = [p for p in result.peaks if "voigt_amplitude" in p]
    print(f"Voigt fitted peaks: {len(voigt_fitted)}/{len(result.peaks)}")


def test_data_augmentation(synthetic_spectrum):
    """Test data augmentation."""
    config = UnifiedSpectroscopyConfig(
        augmentation_enabled=True,
        augmentation_noise_level=0.01,
        augmentation_xshift_range=5.0
    )
    analyzer = UnifiedSpectroscopyAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    # Check if augmented spectra were generated
    assert hasattr(result, 'augmented_spectra')
    assert len(result.augmented_spectra) > 0
    
    print(f"Generated {len(result.augmented_spectra)} augmented spectra")


def test_mixup_augmentation(synthetic_spectrum, ferric_oxide_spectrum):
    """Test mixup augmentation."""
    config = UnifiedSpectroscopyConfig()
    analyzer = UnifiedSpectroscopyAnalyzer(config)
    
    # Analyze both spectra first
    spec1 = analyzer.analyze(synthetic_spectrum)
    
    # Create a second spectrum with same wavenumber grid as spec1
    spec2_aligned = RamanSpectrum(
        wavenumber=spec1.wavenumber.copy(),
        intensity=np.interp(spec1.wavenumber, ferric_oxide_spectrum.wavenumber, ferric_oxide_spectrum.intensity),
        source_file="aligned_ferric_oxide.txt",
        sample_id="Fe2O3_aligned"
    )
    spec2 = analyzer.analyze(spec2_aligned)
    
    # Perform mixup
    mixed = analyzer.mixup_augmentation(spec1, spec2, alpha=0.5)
    
    assert mixed is not None
    assert len(mixed.wavenumber) == len(spec1.wavenumber)
    assert len(mixed.intensity) == len(spec1.intensity)


# ═══════════════════════════════════════════════════════════════════════════
# MATERIAL IDENTIFICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_material_database_completeness():
    """Test that material database has required fields."""
    for material_id, material_data in RAMAN_MATERIAL_DATABASE.items():
        assert "peaks" in material_data
        assert "description" in material_data
        assert "tolerance" in material_data
        assert "category" in material_data
        assert isinstance(material_data["peaks"], list)
        assert len(material_data["peaks"]) > 0


def test_material_identification_ferric_oxide(ferric_oxide_spectrum):
    """Test material identification for ferric oxide."""
    config = RamanAnalysisConfig(peak_detection=True)
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(ferric_oxide_spectrum)
    
    # Identify material
    matches = identify_material(result)
    
    assert len(matches) > 0
    print(f"Material matches: {len(matches)}")
    
    # Check if ferric oxide is in top matches
    top_match = matches[0]
    print(f"Top match: {top_match['description']} ({top_match['confidence']:.2%})")
    
    # Ferric oxide should be identified
    ferric_matches = [m for m in matches if "Fe2O3" in m["material"] or "hematite" in m["description"].lower()]
    assert len(ferric_matches) > 0


def test_material_categories():
    """Test that all material categories are represented."""
    categories = set()
    for material_data in RAMAN_MATERIAL_DATABASE.values():
        categories.add(material_data["category"])
    
    expected_categories = {
        "carbon", "semiconductor", "metal_oxide", "iron_oxide",
        "electrode", "sulfide", "nitride", "polymer", "mineral"
    }
    
    assert categories == expected_categories
    print(f"Material categories: {sorted(categories)}")


def test_expanded_database_size():
    """Test that database has been expanded."""
    # Original database had 10 materials
    # Expanded database should have significantly more
    assert len(RAMAN_MATERIAL_DATABASE) >= 45
    print(f"Total materials in database: {len(RAMAN_MATERIAL_DATABASE)}")


# ═══════════════════════════════════════════════════════════════════════════
# BATCH ANALYSIS TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_batch_analysis(synthetic_spectrum, ferric_oxide_spectrum):
    """Test batch analysis of multiple spectra."""
    config = UnifiedSpectroscopyConfig()
    batch_analyzer = BatchSpectroscopyAnalyzer(config)
    
    # Add spectra
    batch_analyzer.add_spectrum(synthetic_spectrum)
    batch_analyzer.add_spectrum(ferric_oxide_spectrum)
    
    # Analyze all
    results = batch_analyzer.analyze_all()
    
    assert len(results) == 2
    assert all(r.peaks for r in results)


def test_batch_statistics(synthetic_spectrum, ferric_oxide_spectrum):
    """Test batch statistics computation."""
    config = UnifiedSpectroscopyConfig()
    batch_analyzer = BatchSpectroscopyAnalyzer(config)
    
    # Create aligned spectra with same wavenumber grid
    wavenumber_common = np.linspace(200, 1400, 600)
    
    spec1_aligned = RamanSpectrum(
        wavenumber=wavenumber_common,
        intensity=np.interp(wavenumber_common, synthetic_spectrum.wavenumber, synthetic_spectrum.intensity),
        source_file="synthetic_aligned.txt",
        sample_id="test_001"
    )
    
    spec2_aligned = RamanSpectrum(
        wavenumber=wavenumber_common,
        intensity=np.interp(wavenumber_common, ferric_oxide_spectrum.wavenumber, ferric_oxide_spectrum.intensity),
        source_file="ferric_aligned.txt",
        sample_id="Fe2O3_001"
    )
    
    batch_analyzer.add_spectrum(spec1_aligned)
    batch_analyzer.add_spectrum(spec2_aligned)
    
    # Analyze all first
    batch_analyzer.analyze_all()
    
    # Compute statistics
    stats = batch_analyzer.compute_statistics()
    
    assert "mean_spectrum" in stats
    assert "std_spectrum" in stats
    assert "median_spectrum" in stats
    assert stats["n_spectra"] == 2


def test_pca_analysis(synthetic_spectrum, ferric_oxide_spectrum):
    """Test PCA dimensionality reduction."""
    config = UnifiedSpectroscopyConfig(pca_enabled=True, pca_n_components=2)
    batch_analyzer = BatchSpectroscopyAnalyzer(config)
    
    # Create aligned spectra with same wavenumber grid
    wavenumber_common = np.linspace(200, 1400, 600)
    
    spec1_aligned = RamanSpectrum(
        wavenumber=wavenumber_common,
        intensity=np.interp(wavenumber_common, synthetic_spectrum.wavenumber, synthetic_spectrum.intensity),
        source_file="synthetic_aligned.txt",
        sample_id="test_001"
    )
    
    spec2_aligned = RamanSpectrum(
        wavenumber=wavenumber_common,
        intensity=np.interp(wavenumber_common, ferric_oxide_spectrum.wavenumber, ferric_oxide_spectrum.intensity),
        source_file="ferric_aligned.txt",
        sample_id="Fe2O3_001"
    )
    
    # Need at least 2 spectra for PCA
    batch_analyzer.add_spectrum(spec1_aligned)
    batch_analyzer.add_spectrum(spec2_aligned)
    
    # Analyze all
    batch_analyzer.analyze_all()
    
    # Perform PCA
    X_pca, pca_model, explained_var = batch_analyzer.perform_pca_analysis()
    
    assert X_pca.shape[0] == 2  # 2 spectra
    assert X_pca.shape[1] <= 2  # At most 2 components
    assert len(explained_var) <= 2
    assert explained_var.sum() <= 1.0


def test_clustering_kmeans(synthetic_spectrum, ferric_oxide_spectrum):
    """Test K-means clustering."""
    config = UnifiedSpectroscopyConfig(
        clustering_enabled=True,
        clustering_method="kmeans",
        clustering_n_clusters=2
    )
    batch_analyzer = BatchSpectroscopyAnalyzer(config)
    
    # Create aligned spectra with same wavenumber grid
    wavenumber_common = np.linspace(200, 1400, 600)
    
    spec1_aligned = RamanSpectrum(
        wavenumber=wavenumber_common,
        intensity=np.interp(wavenumber_common, synthetic_spectrum.wavenumber, synthetic_spectrum.intensity),
        source_file="synthetic_aligned.txt",
        sample_id="test_001"
    )
    
    spec2_aligned = RamanSpectrum(
        wavenumber=wavenumber_common,
        intensity=np.interp(wavenumber_common, ferric_oxide_spectrum.wavenumber, ferric_oxide_spectrum.intensity),
        source_file="ferric_aligned.txt",
        sample_id="Fe2O3_001"
    )
    
    batch_analyzer.add_spectrum(spec1_aligned)
    batch_analyzer.add_spectrum(spec2_aligned)
    
    # Analyze all
    batch_analyzer.analyze_all()
    
    # Perform clustering
    labels, model = batch_analyzer.perform_clustering()
    
    assert len(labels) == 2
    assert len(set(labels)) <= 2  # At most 2 clusters


# ═══════════════════════════════════════════════════════════════════════════
# FILE I/O TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_import_raman_data_txt(synthetic_spectrum):
    """Test importing Raman data from text file."""
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for wn, intensity in zip(synthetic_spectrum.wavenumber, synthetic_spectrum.intensity):
            f.write(f"{wn}\t{intensity}\n")
        temp_path = f.name
    
    try:
        # Import
        imported = import_raman_data(temp_path)
        
        assert len(imported.wavenumber) == len(synthetic_spectrum.wavenumber)
        assert len(imported.intensity) == len(synthetic_spectrum.intensity)
        assert np.allclose(imported.wavenumber, synthetic_spectrum.wavenumber)
    finally:
        os.unlink(temp_path)


def test_spectrum_to_dict(synthetic_spectrum):
    """Test spectrum serialization to dictionary."""
    config = RamanAnalysisConfig()
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(synthetic_spectrum)
    
    # Convert to dict
    data = result.to_dict()
    
    assert "wavenumber" in data
    assert "intensity" in data
    assert "baseline" in data
    assert "corrected_intensity" in data
    assert "peaks" in data
    assert "n_points" in data
    assert "wavenumber_range" in data


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASE TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_empty_spectrum():
    """Test handling of empty spectrum."""
    spectrum = RamanSpectrum(
        wavenumber=np.array([]),
        intensity=np.array([]),
        source_file="empty.txt"
    )
    
    config = RamanAnalysisConfig()
    analyzer = RamanAnalyzer(config)
    
    # Should handle gracefully
    with pytest.raises(Exception):
        analyzer.analyze(spectrum)


def test_flat_spectrum():
    """Test handling of completely flat spectrum."""
    wavenumber = np.linspace(100, 1000, 100)
    intensity = np.ones_like(wavenumber) * 0.5
    
    spectrum = RamanSpectrum(
        wavenumber=wavenumber,
        intensity=intensity,
        source_file="flat.txt"
    )
    
    config = RamanAnalysisConfig()
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(spectrum)
    
    # Should complete without errors
    assert result is not None
    # Flat spectrum should have no peaks
    assert len(result.peaks) == 0


def test_single_peak_spectrum():
    """Test spectrum with single sharp peak."""
    wavenumber = np.linspace(100, 1000, 200)
    intensity = np.exp(-((wavenumber - 500) ** 2) / (2 * 10 ** 2))
    
    spectrum = RamanSpectrum(
        wavenumber=wavenumber,
        intensity=intensity,
        source_file="single_peak.txt"
    )
    
    config = RamanAnalysisConfig()
    analyzer = RamanAnalyzer(config)
    
    result = analyzer.analyze(spectrum)
    
    assert len(result.peaks) >= 1
    # Peak should be near 500 cm⁻¹
    main_peak = result.peaks[0]
    assert abs(main_peak["position_cm"] - 500) < 20


# ═══════════════════════════════════════════════════════════════════════════
# PERFORMANCE TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_large_spectrum_performance():
    """Test performance with large spectrum (10,000 points)."""
    import time
    
    wavenumber = np.linspace(100, 4000, 10000)
    intensity = np.random.normal(0.5, 0.1, 10000)
    
    # Add some peaks
    for pos in [500, 1000, 1500, 2000, 2500]:
        intensity += 0.5 * np.exp(-((wavenumber - pos) ** 2) / (2 * 20 ** 2))
    
    spectrum = RamanSpectrum(
        wavenumber=wavenumber,
        intensity=intensity,
        source_file="large.txt"
    )
    
    config = UnifiedSpectroscopyConfig(
        cosmic_ray_removal=True,
        fourier_filtering=True,
        peak_detection=True,
        peak_fitting=True
    )
    analyzer = UnifiedSpectroscopyAnalyzer(config)
    
    start = time.time()
    result = analyzer.analyze(spectrum)
    elapsed = time.time() - start
    
    print(f"Analysis of 10,000 points took {elapsed:.2f} seconds")
    assert elapsed < 5.0  # Should complete in under 5 seconds
    assert len(result.peaks) > 0


# ═══════════════════════════════════════════════════════════════════════════
# RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
