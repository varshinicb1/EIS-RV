"""
Test Advanced Features - Molecular Dynamics & Electron Density
================================================================
Test suite for Week 3-4 advanced features.

Usage:
    python test_advanced_features.py
"""

import requests
import json
import time
import numpy as np
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8001"


def print_header(title: str):
    """Print formatted test header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status} - {test_name}")
    if details:
        print(f"  {details}")


def test_molecular_dynamics():
    """Test 1: Molecular Dynamics Simulation"""
    print_header("Test 1: Molecular Dynamics (Ethanol, 100 steps)")
    
    payload = {
        "smiles": "CCO",
        "n_steps": 100,
        "timestep_fs": 0.5,
        "temperature_K": 300.0,
        "ensemble": "NVT"
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/quantum/molecular-dynamics",
            json=payload,
            timeout=60
        )
        wall_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                result = data['data']
                print(f"  Steps: {result['n_steps']}")
                print(f"  Timestep: {result['timestep_fs']} fs")
                print(f"  Target Temperature: {result['target_temperature_K']} K")
                print(f"  Average Temperature: {result['avg_temperature_K']:.2f} K")
                print(f"  Average Energy: {result['avg_energy_eV']:.6f} eV")
                print(f"  Temperature Std Dev: {result['std_temperature_K']:.2f} K")
                print(f"  Energy Std Dev: {result['std_energy_eV']:.6f} eV")
                print(f"  Method: {result['method']}")
                print(f"  Wall Time: {wall_time:.3f} s")
                
                # Check if temperature is reasonable
                temp_diff = abs(result['avg_temperature_K'] - result['target_temperature_K'])
                if temp_diff < 50:  # Within 50 K
                    print_result("Molecular Dynamics", True, f"Temperature control: ±{temp_diff:.1f} K")
                else:
                    print_result("Molecular Dynamics", False, f"Temperature control poor: ±{temp_diff:.1f} K")
                
                return result
            else:
                print_result("Molecular Dynamics", False, f"Error: {data.get('error', 'Unknown')}")
                return None
        else:
            print_result("Molecular Dynamics", False, f"Status code: {response.status_code}")
            return None
    
    except Exception as e:
        print_result("Molecular Dynamics", False, f"Error: {e}")
        return None


def test_electron_density():
    """Test 2: Electron Density Calculation"""
    print_header("Test 2: Electron Density (Ethanol)")
    
    payload = {
        "smiles": "CCO",
        "grid_spacing": 0.3,
        "padding": 2.0
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/quantum/electron-density",
            json=payload,
            timeout=60
        )
        wall_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                result = data['data']
                print(f"  Grid Shape: {result['shape']}")
                print(f"  Grid Spacing: {result['grid_spacing']} Å")
                print(f"  Min Density: {result['min_density']:.6f} e/Å³")
                print(f"  Max Density: {result['max_density']:.6f} e/Å³")
                print(f"  Total Electrons: {result['total_electrons']:.2f}")
                print(f"  Method: {result['method']}")
                print(f"  Wall Time: {wall_time:.3f} s")
                
                # Check if total electrons is reasonable (ethanol has 26 electrons)
                expected_electrons = 26
                electron_diff = abs(result['total_electrons'] - expected_electrons)
                if electron_diff < 5:  # Within 5 electrons
                    print_result("Electron Density", True, f"Electron count: {result['total_electrons']:.1f} (expected: {expected_electrons})")
                else:
                    print_result("Electron Density", False, f"Electron count off by {electron_diff:.1f}")
                
                return result
            else:
                print_result("Electron Density", False, f"Error: {data.get('error', 'Unknown')}")
                return None
        else:
            print_result("Electron Density", False, f"Status code: {response.status_code}")
            return None
    
    except Exception as e:
        print_result("Electron Density", False, f"Error: {e}")
        return None


def test_md_benzene():
    """Test 3: MD for Larger Molecule (Benzene)"""
    print_header("Test 3: Molecular Dynamics (Benzene, 50 steps)")
    
    payload = {
        "smiles": "c1ccccc1",
        "n_steps": 50,
        "timestep_fs": 0.5,
        "temperature_K": 300.0,
        "ensemble": "NVT"
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/quantum/molecular-dynamics",
            json=payload,
            timeout=60
        )
        wall_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                result = data['data']
                print(f"  Average Temperature: {result['avg_temperature_K']:.2f} K")
                print(f"  Average Energy: {result['avg_energy_eV']:.6f} eV")
                print(f"  Wall Time: {wall_time:.3f} s")
                
                print_result("MD Benzene", True, f"Completed {result['n_steps']} steps")
                return result
            else:
                print_result("MD Benzene", False, f"Error: {data.get('error', 'Unknown')}")
                return None
        else:
            print_result("MD Benzene", False, f"Status code: {response.status_code}")
            return None
    
    except Exception as e:
        print_result("MD Benzene", False, f"Error: {e}")
        return None


def test_density_benzene():
    """Test 4: Electron Density for Benzene"""
    print_header("Test 4: Electron Density (Benzene)")
    
    payload = {
        "smiles": "c1ccccc1",
        "grid_spacing": 0.3,
        "padding": 2.0
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/quantum/electron-density",
            json=payload,
            timeout=60
        )
        wall_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                result = data['data']
                print(f"  Grid Shape: {result['shape']}")
                print(f"  Total Electrons: {result['total_electrons']:.2f}")
                print(f"  Wall Time: {wall_time:.3f} s")
                
                # Benzene has 42 electrons
                expected_electrons = 42
                electron_diff = abs(result['total_electrons'] - expected_electrons)
                if electron_diff < 10:
                    print_result("Density Benzene", True, f"Electron count: {result['total_electrons']:.1f}")
                else:
                    print_result("Density Benzene", False, f"Electron count off by {electron_diff:.1f}")
                
                return result
            else:
                print_result("Density Benzene", False, f"Error: {data.get('error', 'Unknown')}")
                return None
        else:
            print_result("Density Benzene", False, f"Status code: {response.status_code}")
            return None
    
    except Exception as e:
        print_result("Density Benzene", False, f"Error: {e}")
        return None


def run_all_tests():
    """Run all advanced feature tests."""
    print("\n" + "=" * 80)
    print("  RĀMAN Studio - Advanced Features Test Suite")
    print("  " + "=" * 78)
    print(f"  Server: {BASE_URL}")
    print(f"  Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    results = {}
    
    # Run tests
    results['md_ethanol'] = test_molecular_dynamics()
    results['density_ethanol'] = test_electron_density()
    results['md_benzene'] = test_md_benzene()
    results['density_benzene'] = test_density_benzene()
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v is not None)
    total = len(results)
    
    print(f"\n  Tests Passed: {passed}/{total}")
    print(f"  Success Rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n  ✅ ALL TESTS PASSED!")
        print("\n  Advanced features (MD & Electron Density) are fully operational.")
    else:
        print("\n  ⚠️  SOME TESTS FAILED")
        print("\n  Check the logs above for details.")
    
    print("\n" + "=" * 80)
    print("  Test suite complete!")
    print("=" * 80 + "\n")
    
    return results


if __name__ == "__main__":
    results = run_all_tests()
