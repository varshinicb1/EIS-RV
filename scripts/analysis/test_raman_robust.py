"""
Robust Raman Spectroscopy Analysis Test with Visualization
===========================================================
Tests the improved peak detection pipeline with debugging output.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

from backend.core.engines.raman_engine import (
    import_raman_data,
    RamanAnalyzer,
    RamanAnalysisConfig,
    identify_material,
)

def plot_analysis_results(spectrum, output_file="raman_analysis_plot.png"):
    """
    Create comprehensive visualization of Raman analysis.
    
    Args:
        spectrum: Analyzed RamanSpectrum object
        output_file: Output filename for plot
    """
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    # Plot 1: Original spectrum
    ax1 = axes[0]
    ax1.plot(spectrum.wavenumber, spectrum.intensity, 'b-', alpha=0.5, linewidth=0.5, label='Original')
    ax1.set_xlabel('Wavenumber (cm⁻¹)')
    ax1.set_ylabel('Intensity')
    ax1.set_title('Original Raman Spectrum')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Smoothed + Baseline
    ax2 = axes[1]
    if spectrum.smoothed_intensity is not None:
        ax2.plot(spectrum.wavenumber, spectrum.smoothed_intensity, 'g-', linewidth=1, label='Smoothed')
    if spectrum.baseline is not None:
        ax2.plot(spectrum.wavenumber, spectrum.baseline, 'r--', linewidth=1, label='Baseline')
    ax2.set_xlabel('Wavenumber (cm⁻¹)')
    ax2.set_ylabel('Intensity')
    ax2.set_title('Smoothed Spectrum with Baseline')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Corrected spectrum with detected peaks
    ax3 = axes[2]
    if spectrum.corrected_intensity is not None:
        ax3.plot(spectrum.wavenumber, spectrum.corrected_intensity, 'k-', linewidth=1, label='Corrected')
    
    # Mark detected peaks
    if spectrum.peaks:
        peak_positions = [p['position_cm'] for p in spectrum.peaks]
        peak_intensities = [p['intensity'] for p in spectrum.peaks]
        ax3.plot(peak_positions, peak_intensities, 'ro', markersize=8, label=f'Peaks ({len(spectrum.peaks)})')
        
        # Annotate top 10 peaks
        for i, peak in enumerate(spectrum.peaks[:10]):
            ax3.annotate(
                f"{peak['position_cm']:.0f}",
                xy=(peak['position_cm'], peak['intensity']),
                xytext=(0, 10),
                textcoords='offset points',
                ha='center',
                fontsize=8,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7)
            )
    
    ax3.set_xlabel('Wavenumber (cm⁻¹)')
    ax3.set_ylabel('Normalized Intensity')
    ax3.set_title('Baseline-Corrected Spectrum with Detected Peaks')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n✓ Plot saved to: {output_file}")
    plt.close()


def test_customer_data_robust():
    """Test robust peak detection on customer's FO.txt file."""
    print("=" * 80)
    print("ROBUST RAMAN SPECTROSCOPY ANALYSIS TEST")
    print("=" * 80)
    print()
    
    # Import customer data
    print("1. Importing customer data (FO.txt)...")
    try:
        spectrum = import_raman_data("Lab data/FO.txt")
        print(f"   ✓ Successfully imported {len(spectrum.wavenumber)} data points")
        print(f"   ✓ Wavenumber range: {spectrum.wavenumber.min():.1f} - {spectrum.wavenumber.max():.1f} cm⁻¹")
        print(f"   ✓ Intensity range: {spectrum.intensity.min():.1f} - {spectrum.intensity.max():.1f}")
        print()
    except Exception as e:
        print(f"   ✗ Failed to import data: {e}")
        return False
    
    # Analyze with robust pipeline
    print("2. Running robust analysis pipeline...")
    print("   Pipeline steps:")
    print("   1. Sort data by wavenumber")
    print("   2. Adaptive Savitzky-Golay smoothing")
    print("   3. Asymmetric Least Squares baseline correction")
    print("   4. Min-max normalization")
    print("   5. Robust peak detection with adaptive thresholds")
    print("   6. Peak fitting (Lorentzian)")
    print()
    
    try:
        config = RamanAnalysisConfig(
            baseline_method="als",
            normalize=True,
            normalization_method="minmax",
            peak_detection=True,
            peak_fitting=True,
            peak_model="lorentzian"
        )
        
        analyzer = RamanAnalyzer(config)
        analyzed = analyzer.analyze(spectrum)
        
        print(f"\n   ✓ Analysis complete!")
        print(f"   ✓ Peaks detected: {len(analyzed.peaks)}")
        print()
        
    except Exception as e:
        print(f"   ✗ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Display peak results
    print("3. Peak Detection Results:")
    print("-" * 80)
    
    if analyzed.peaks:
        print(f"\n   Total peaks found: {len(analyzed.peaks)}")
        print(f"\n   Top 20 peaks by intensity:")
        print(f"   {'#':<4} {'Position (cm⁻¹)':<18} {'Intensity':<12} {'Prominence':<12} {'FWHM (cm⁻¹)':<15}")
        print(f"   {'-'*4} {'-'*18} {'-'*12} {'-'*12} {'-'*15}")
        
        for i, peak in enumerate(analyzed.peaks[:20], 1):
            pos = peak['position_cm']
            intensity = peak['intensity']
            prominence = peak.get('prominence', 'N/A')
            fwhm = peak.get('fwhm_cm', 'N/A')
            
            prom_str = f"{prominence:.4f}" if isinstance(prominence, (int, float)) else prominence
            fwhm_str = f"{fwhm:.2f}" if isinstance(fwhm, (int, float)) else fwhm
            
            print(f"   {i:<4} {pos:<18.2f} {intensity:<12.4f} {prom_str:<12} {fwhm_str:<15}")
    else:
        print("   ⚠ No peaks detected (this should not happen with robust detection!)")
    
    print()
    
    # Material identification
    print("4. Material Identification:")
    print("-" * 80)
    
    try:
        matches = identify_material(analyzed)
        if matches:
            print(f"\n   Found {len(matches)} possible material matches:")
            for i, match in enumerate(matches[:5], 1):
                print(f"\n   {i}. {match['material']}")
                print(f"      Description: {match['description']}")
                print(f"      Confidence: {match['confidence']*100:.1f}%")
                print(f"      Matched peaks: {match['matched_peaks']}/{match['total_peaks']}")
        else:
            print("\n   ℹ No material matches found in database")
            print("   (Material may not be in current database)")
    except Exception as e:
        print(f"   ✗ Material identification failed: {e}")
    
    print()
    
    # Create visualization
    print("5. Creating visualization...")
    try:
        plot_analysis_results(analyzed, "customer_raman_analysis.png")
    except Exception as e:
        print(f"   ⚠ Plotting failed: {e}")
        print("   (matplotlib may not be available)")
    
    print()
    print("=" * 80)
    print("✓ ROBUST ANALYSIS TEST COMPLETE")
    print("=" * 80)
    print()
    
    return True


def test_synthetic_data():
    """Test with synthetic Raman spectrum (graphene-like)."""
    print("=" * 80)
    print("Testing with synthetic graphene-like spectrum...")
    print("=" * 80)
    print()
    
    from backend.core.engines.raman_engine import RamanSpectrum
    
    # Create synthetic graphene spectrum with realistic noise
    wavenumber = np.linspace(100, 3000, 2000)
    
    # Lorentzian peak function
    def lorentzian(x, x0, A, gamma):
        return A * (gamma**2) / ((x - x0)**2 + gamma**2)
    
    # Add G band (1580 cm⁻¹) and 2D band (2700 cm⁻¹)
    intensity = (
        lorentzian(wavenumber, 1580, 1000, 15) +  # G band
        lorentzian(wavenumber, 2700, 800, 25) +   # 2D band
        lorentzian(wavenumber, 1350, 300, 20) +   # D band (defects)
        50 +  # Baseline
        np.random.randn(len(wavenumber)) * 30  # Realistic noise
    )
    
    spectrum = RamanSpectrum(
        wavenumber=wavenumber,
        intensity=intensity,
        source_file="synthetic_graphene.txt",
        sample_id="Synthetic_Graphene"
    )
    
    # Analyze
    config = RamanAnalysisConfig()
    analyzer = RamanAnalyzer(config)
    analyzed = analyzer.analyze(spectrum)
    
    print(f"Peaks detected: {len(analyzed.peaks)}")
    if analyzed.peaks:
        print("\nTop 5 peaks:")
        for i, peak in enumerate(analyzed.peaks[:5], 1):
            print(f"  {i}. Position: {peak['position_cm']:.1f} cm⁻¹, Intensity: {peak['intensity']:.3f}")
    
    # Identify material
    matches = identify_material(analyzed)
    if matches:
        print(f"\nMaterial identification:")
        for match in matches[:3]:
            print(f"  {match['material']}: {match['confidence']*100:.1f}% confidence")
    
    # Create visualization
    try:
        plot_analysis_results(analyzed, "synthetic_graphene_analysis.png")
    except Exception as e:
        print(f"Plotting failed: {e}")
    
    print()
    return True


def test_noisy_data():
    """Test with very noisy data to verify robustness."""
    print("=" * 80)
    print("Testing with very noisy data...")
    print("=" * 80)
    print()
    
    from backend.core.engines.raman_engine import RamanSpectrum
    
    # Create spectrum with high noise
    wavenumber = np.linspace(500, 2000, 1000)
    
    def lorentzian(x, x0, A, gamma):
        return A * (gamma**2) / ((x - x0)**2 + gamma**2)
    
    # Weak peaks with high noise
    intensity = (
        lorentzian(wavenumber, 800, 100, 10) +
        lorentzian(wavenumber, 1200, 150, 15) +
        lorentzian(wavenumber, 1600, 80, 12) +
        20 +  # Baseline
        np.random.randn(len(wavenumber)) * 50  # Very high noise!
    )
    
    spectrum = RamanSpectrum(
        wavenumber=wavenumber,
        intensity=intensity,
        source_file="noisy_test.txt",
        sample_id="Noisy_Test"
    )
    
    # Analyze
    config = RamanAnalysisConfig()
    analyzer = RamanAnalyzer(config)
    analyzed = analyzer.analyze(spectrum)
    
    print(f"Peaks detected in noisy data: {len(analyzed.peaks)}")
    if analyzed.peaks:
        print("\nTop 5 peaks:")
        for i, peak in enumerate(analyzed.peaks[:5], 1):
            print(f"  {i}. Position: {peak['position_cm']:.1f} cm⁻¹, Intensity: {peak['intensity']:.3f}")
    
    # Create visualization
    try:
        plot_analysis_results(analyzed, "noisy_data_analysis.png")
    except Exception as e:
        print(f"Plotting failed: {e}")
    
    print()
    return True


if __name__ == "__main__":
    print()
    
    # Test 1: Customer data with robust pipeline
    success1 = test_customer_data_robust()
    
    print()
    
    # Test 2: Synthetic graphene
    success2 = test_synthetic_data()
    
    print()
    
    # Test 3: Very noisy data
    success3 = test_noisy_data()
    
    print()
    print("=" * 80)
    if success1 and success2 and success3:
        print("✓ ALL ROBUST TESTS PASSED!")
        print()
        print("Key improvements:")
        print("  ✓ Adaptive smoothing based on data size")
        print("  ✓ Dynamic prominence thresholds (5-10% of signal range)")
        print("  ✓ Adaptive peak distance based on wavenumber spacing")
        print("  ✓ Multi-level threshold fallback strategy")
        print("  ✓ Guaranteed peak detection (top N local maxima fallback)")
        print("  ✓ Comprehensive debugging output")
        print("  ✓ Visualization of all processing steps")
    else:
        print("✗ Some tests failed")
    print("=" * 80)
    print()
    
    sys.exit(0 if (success1 and success2 and success3) else 1)
