"""
Quick test to verify backend is processing Raman data correctly
"""
import requests
import json

# Test data - simple Raman spectrum
test_data = """100\t0.1
200\t0.3
300\t0.5
400\t0.7
500\t0.9
600\t0.7
700\t0.5
800\t0.3
900\t0.1"""

# Save test file
with open('test_spectrum.txt', 'w') as f:
    f.write(test_data)

# Test backend
print("Testing Unified Spectroscopy Backend...")
print("=" * 60)

try:
    # Test health endpoint
    print("\n1. Testing health endpoint...")
    response = requests.get('http://127.0.0.1:8000/api/v1/unified-spectroscopy/health')
    print(f"   Status: {response.status_code}")
    if response.ok:
        health = response.json()
        print(f"   Engine: {health['engine']}")
        print(f"   Version: {health['version']}")
        print(f"   Features: {len(health['features'])} available")
    
    # Test analysis endpoint
    print("\n2. Testing analysis endpoint...")
    with open('test_spectrum.txt', 'rb') as f:
        files = {'file': ('test_spectrum.txt', f, 'text/plain')}
        data = {
            'cosmic_ray_removal': 'true',
            'fourier_filtering': 'true',
            'voigt_fitting': 'true'
        }
        response = requests.post(
            'http://127.0.0.1:8000/api/v1/unified-spectroscopy/analyze',
            files=files,
            data=data
        )
    
    print(f"   Status: {response.status_code}")
    
    if response.ok:
        result = response.json()
        print(f"\n   ✓ Analysis successful!")
        print(f"   - Data points: {result.get('n_points', 0)}")
        print(f"   - Peaks detected: {len(result.get('peaks', []))}")
        print(f"   - Has baseline: {result.get('baseline') is not None}")
        print(f"   - Has corrected_intensity: {result.get('corrected_intensity') is not None}")
        
        if result.get('corrected_intensity'):
            print(f"   - Corrected intensity length: {len(result['corrected_intensity'])}")
            print(f"   - Raw intensity length: {len(result['intensity'])}")
            
            # Check if they're different
            raw_sum = sum(result['intensity'][:5])
            corrected_sum = sum(result['corrected_intensity'][:5])
            print(f"   - Raw sum (first 5): {raw_sum:.4f}")
            print(f"   - Corrected sum (first 5): {corrected_sum:.4f}")
            
            if abs(raw_sum - corrected_sum) > 0.01:
                print(f"   ✓ Data is being processed (values are different)")
            else:
                print(f"   ⚠ Data might not be processed (values are similar)")
        
        # Check analysis config
        if 'analysis_config' in result:
            config = result['analysis_config']
            print(f"\n   Analysis options applied:")
            print(f"   - Cosmic ray removal: {config.get('cosmic_ray_removal', False)}")
            print(f"   - Fourier filtering: {config.get('fourier_filtering', False)}")
            print(f"   - Voigt fitting: {config.get('voigt_fitting', False)}")
        
        # Save result for inspection
        with open('test_result.json', 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n   Full result saved to: test_result.json")
        
    else:
        print(f"   ✗ Analysis failed: {response.text}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
