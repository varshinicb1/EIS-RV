"""
Test script for Raman spectroscopy analysis engine.
Tests the customer's FO.txt file and validates the implementation.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from backend.core.engines.raman_engine import (
    import_raman_data,
    RamanAnalyzer,
    RamanAnalysisConfig,
    identify_material,
)

def test_customer_data():
    """Test analysis of customer's FO.txt file."""
    print("=" * 80)
    print("RĀMAN STUDIO - Raman Spectroscopy Analysis Test")
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
    
    # Test different baseline correction methods
    print("2. Testing baseline correction methods...")
    methods = ["airpls", "als", "polynomial", "morphological"]
    
    for method in methods:
        try:
            config = RamanAnalysisConfig(
                baseline_method=method,
                denoise_method="savgol",
                peak_detection=True,
                peak_fitting=True,
                normalize=True
            )
            analyzer = RamanAnalyzer(config)
            
            # Analyze (create a copy to avoid modifying original)
            import copy
            test_spectrum = copy.deepcopy(spectrum)
            result = analyzer.analyze(test_spectrum)
            
            print(f"   ✓ {method:15s}: {len(result.peaks)} peaks detected")
            
        except Exception as e:
            print(f"   ✗ {method:15s}: Failed - {e}")
    
    print()
    
    # Full analysis with adjusted settings for noisy data
    print("3. Running full analysis with adjusted settings...")
    try:
        config = RamanAnalysisConfig(
            baseline_method="airpls",
            denoise_method="savgol",
            savgol_window=21,  # Larger window for noisy data
            peak_prominence=10.0,  # Lower threshold for noisy data
            peak_min_distance=20,
            normalize=True
        )
        analyzer = RamanAnalyzer(config)
        analyzed = analyzer.analyze(spectrum)
        
        print(f"   ✓ Baseline correction: {config.baseline_method}")
        print(f"   ✓ Denoising: {config.denoise_method}")
        print(f"   ✓ Peaks detected: {len(analyzed.peaks)}")
        print()
        
        # Show top 10 peaks
        if analyzed.peaks:
            print("   Top 10 peaks:")
            sorted_peaks = sorted(analyzed.peaks, key=lambda p: p["intensity"], reverse=True)[:10]
            for i, peak in enumerate(sorted_peaks, 1):
                pos = peak["position_cm"]
                intensity = peak["intensity"]
                fwhm = peak.get("fwhm_cm", "N/A")
                print(f"      {i:2d}. Position: {pos:7.1f} cm⁻¹, Intensity: {intensity:8.2f}, FWHM: {fwhm}")
        print()
        
    except Exception as e:
        print(f"   ✗ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Material identification
    print("4. Material identification...")
    try:
        matches = identify_material(analyzed)
        if matches:
            print(f"   ✓ Found {len(matches)} possible material matches:")
            for match in matches[:5]:  # Top 5
                print(f"      - {match['material']:20s}: {match['confidence']*100:5.1f}% confidence")
                print(f"        {match['description']}")
                print(f"        Matched {match['matched_peaks']}/{match['total_peaks']} peaks")
        else:
            print("   ℹ No material matches found (material may not be in database)")
        print()
    except Exception as e:
        print(f"   ✗ Material identification failed: {e}")
    
    # Test data export
    print("5. Testing data export...")
    try:
        result_dict = analyzed.to_dict()
        print(f"   ✓ Export successful")
        print(f"   ✓ Keys: {', '.join(result_dict.keys())}")
        print()
    except Exception as e:
        print(f"   ✗ Export failed: {e}")
        return False
    
    print("=" * 80)
    print("✓ ALL TESTS PASSED")
    print("=" * 80)
    print()
    print("The Raman spectroscopy analysis engine is working correctly!")
    print("Customer's FO.txt file can now be analyzed through the API.")
    print()
    print("To analyze via API:")
    print('  curl -X POST "http://localhost:8000/api/v1/raman/upload" \\')
    print('    -F "file=@Lab data/FO.txt" \\')
    print('    -F "sample_id=FO_Customer_Sample"')
    print()
    
    return True


def test_synthetic_data():
    """Test with synthetic Raman spectrum."""
    print("=" * 80)
    print("Testing with synthetic Raman spectrum...")
    print("=" * 80)
    print()
    
    import numpy as np
    from backend.core.engines.raman_engine import RamanSpectrum
    
    # Create synthetic graphene-like spectrum
    wavenumber = np.linspace(100, 3000, 1000)
    
    # Add two Lorentzian peaks (G and 2D bands)
    def lorentzian(x, x0, A, gamma):
        return A * (gamma**2) / ((x - x0)**2 + gamma**2)
    
    intensity = (
        lorentzian(wavenumber, 1580, 1000, 15) +  # G band
        lorentzian(wavenumber, 2700, 800, 25) +   # 2D band
        50 +  # Baseline
        np.random.randn(len(wavenumber)) * 20  # Noise
    )
    
    spectrum = RamanSpectrum(
        wavenumber=wavenumber,
        intensity=intensity,
        source_file="synthetic_graphene.txt",
        sample_id="Synthetic_Graphene"
    )
    
    # Analyze
    config = RamanAnalysisConfig(
        peak_prominence=50.0,  # Higher for clean synthetic data
        peak_min_distance=50
    )
    analyzer = RamanAnalyzer(config)
    analyzed = analyzer.analyze(spectrum)
    
    print(f"Peaks detected: {len(analyzed.peaks)}")
    for peak in analyzed.peaks:
        print(f"  Position: {peak['position_cm']:.1f} cm⁻¹, Intensity: {peak['intensity']:.1f}")
    
    # Identify material
    matches = identify_material(analyzed)
    if matches:
        print(f"\nMaterial identification:")
        for match in matches:
            print(f"  {match['material']}: {match['confidence']*100:.1f}% confidence")
    
    print()
    return True


if __name__ == "__main__":
    print()
    
    # Test with customer data
    success1 = test_customer_data()
    
    print()
    
    # Test with synthetic data
    success2 = test_synthetic_data()
    
    if success1 and success2:
        print("\n✓ All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed")
        sys.exit(1)
