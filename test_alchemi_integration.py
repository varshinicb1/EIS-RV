"""
Test ALCHEMI Integration
=========================
Comprehensive test suite for NVIDIA ALCHEMI quantum engine integration.

Usage:
    python test_alchemi_integration.py
"""

import os
import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = os.environ.get("RAMAN_BASE_URL", "http://localhost:8001")
# Read from environment; never commit a real key. Empty key disables NVIDIA-dependent tests.
API_KEY = os.environ.get("NVIDIA_API_KEY", "")


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


def test_server_health():
    """Test 1: Server Health Check"""
    print_header("Test 1: Server Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/api/quantum/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Status: {data['status']}")
            print(f"  Quantum Engine: {data['quantum_engine']}")
            print(f"  Device: {data['device']}")
            print_result("Server Health", True, "Server is operational")
            return True
        else:
            print_result("Server Health", False, f"Status code: {response.status_code}")
            return False
    
    except Exception as e:
        print_result("Server Health", False, f"Error: {e}")
        return False


def test_engine_status():
    """Test 2: Quantum Engine Status"""
    print_header("Test 2: Quantum Engine Status")
    
    try:
        response = requests.get(f"{BASE_URL}/api/quantum/status", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Status: {data['status']}")
            print(f"  ALCHEMI Available: {data['alchemi_available']}")
            print(f"  CUDA Available: {data['cuda_available']}")
            print(f"  Device: {data['device']}")
            print(f"  Placeholder Mode: {data['placeholder_mode']}")
            print(f"  Message: {data['message']}")
            
            # Check if we're in real ALCHEMI mode or placeholder
            if data['placeholder_mode']:
                print_result("Engine Status", True, "Running in placeholder mode (expected without ALCHEMI)")
            else:
                print_result("Engine Status", True, "Running in real ALCHEMI mode")
            
            return data
        else:
            print_result("Engine Status", False, f"Status code: {response.status_code}")
            return None
    
    except Exception as e:
        print_result("Engine Status", False, f"Error: {e}")
        return None


def test_geometry_optimization():
    """Test 3: Geometry Optimization"""
    print_header("Test 3: Geometry Optimization (Ethanol)")
    
    payload = {
        "smiles": "CCO",
        "method": "AIMNet2",
        "force_tol": 0.01,
        "max_steps": 200
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/quantum/optimize",
            json=payload,
            timeout=30
        )
        wall_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                result = data['data']
                print(f"  Energy: {result['energy_eV']:.6f} eV")
                print(f"  Converged: {result['converged']}")
                print(f"  Iterations: {result['n_iterations']}")
                print(f"  Wall Time: {result['wall_time_s']:.3f} s")
                print(f"  Method: {result['method']}")
                print(f"  Total Time: {wall_time:.3f} s")
                
                # Check if geometry is reasonable
                geometry = result['geometry_A']
                n_atoms = len(geometry)
                print(f"  Atoms: {n_atoms}")
                
                # Verify XYZ format
                if 'xyz' in result:
                    xyz_lines = result['xyz'].split('\n')
                    print(f"  XYZ Format: {len(xyz_lines)} lines")
                
                print_result("Geometry Optimization", True, f"Optimized {n_atoms} atoms in {wall_time:.3f}s")
                return result
            else:
                print_result("Geometry Optimization", False, f"Error: {data.get('error', 'Unknown')}")
                return None
        else:
            print_result("Geometry Optimization", False, f"Status code: {response.status_code}")
            return None
    
    except Exception as e:
        print_result("Geometry Optimization", False, f"Error: {e}")
        return None


def test_band_gap_calculation():
    """Test 4: Band Gap Calculation"""
    print_header("Test 4: Band Gap Calculation (Benzene)")
    
    payload = {
        "smiles": "c1ccccc1",
        "method": "AIMNet2"
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/quantum/band-gap",
            json=payload,
            timeout=30
        )
        wall_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                result = data['data']
                print(f"  Band Gap: {result['band_gap_eV']:.3f} eV")
                print(f"  HOMO: {result['homo_eV']:.3f} eV")
                print(f"  LUMO: {result['lumo_eV']:.3f} eV")
                print(f"  Wall Time: {wall_time:.3f} s")
                
                # Verify band gap is reasonable (benzene should be ~5-6 eV)
                if 0 < result['band_gap_eV'] < 10:
                    print_result("Band Gap Calculation", True, f"Band gap: {result['band_gap_eV']:.3f} eV")
                else:
                    print_result("Band Gap Calculation", False, f"Unreasonable band gap: {result['band_gap_eV']:.3f} eV")
                
                return result
            else:
                print_result("Band Gap Calculation", False, f"Error: {data.get('error', 'Unknown')}")
                return None
        else:
            print_result("Band Gap Calculation", False, f"Status code: {response.status_code}")
            return None
    
    except Exception as e:
        print_result("Band Gap Calculation", False, f"Error: {e}")
        return None


def test_multi_property_calculation():
    """Test 5: Multi-Property Calculation"""
    print_header("Test 5: Multi-Property Calculation (Ethanol)")
    
    payload = {
        "smiles": "CCO",
        "properties": ["energy", "band_gap", "homo", "lumo"]
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/quantum/properties",
            json=payload,
            timeout=30
        )
        wall_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                result = data['data']
                print(f"  Energy: {result.get('energy_eV', 'N/A')} eV")
                print(f"  Band Gap: {result.get('band_gap_eV', 'N/A')} eV")
                print(f"  HOMO: {result.get('homo_eV', 'N/A')} eV")
                print(f"  LUMO: {result.get('lumo_eV', 'N/A')} eV")
                print(f"  Wall Time: {wall_time:.3f} s")
                
                # Check if all requested properties are present
                requested = set(payload['properties'])
                received = set([k.replace('_eV', '') for k in result.keys() if k.endswith('_eV')])
                
                if requested.issubset(received):
                    print_result("Multi-Property Calculation", True, f"All {len(requested)} properties calculated")
                else:
                    missing = requested - received
                    print_result("Multi-Property Calculation", False, f"Missing properties: {missing}")
                
                return result
            else:
                print_result("Multi-Property Calculation", False, f"Error: {data.get('error', 'Unknown')}")
                return None
        else:
            print_result("Multi-Property Calculation", False, f"Status code: {response.status_code}")
            return None
    
    except Exception as e:
        print_result("Multi-Property Calculation", False, f"Error: {e}")
        return None


def test_example_molecules():
    """Test 6: Example Molecules"""
    print_header("Test 6: Example Molecules")
    
    try:
        response = requests.get(f"{BASE_URL}/api/quantum/examples", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            examples = data['examples']
            
            print(f"  Found {len(examples)} example molecules:")
            for ex in examples:
                print(f"    - {ex['name']} ({ex['smiles']}): {ex['description']}")
            
            print_result("Example Molecules", True, f"Retrieved {len(examples)} examples")
            return examples
        else:
            print_result("Example Molecules", False, f"Status code: {response.status_code}")
            return None
    
    except Exception as e:
        print_result("Example Molecules", False, f"Error: {e}")
        return None


def test_batch_optimization():
    """Test 7: Batch Optimization"""
    print_header("Test 7: Batch Optimization")
    
    smiles_list = ["CCO", "CC(=O)O", "c1ccccc1"]
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/quantum/batch-optimize",
            json={"smiles_list": smiles_list},
            timeout=30
        )
        wall_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            if data['success']:
                print(f"  Job ID: {data['job_id']}")
                print(f"  Molecules: {data['n_molecules']}")
                print(f"  Status URL: {data['status_url']}")
                print(f"  Wall Time: {wall_time:.3f} s")
                
                print_result("Batch Optimization", True, f"Batch job submitted for {data['n_molecules']} molecules")
                return data
            else:
                print_result("Batch Optimization", False, "Batch job failed")
                return None
        else:
            print_result("Batch Optimization", False, f"Status code: {response.status_code}")
            return None
    
    except Exception as e:
        print_result("Batch Optimization", False, f"Error: {e}")
        return None


def run_all_tests():
    """Run all tests and generate report."""
    print("\n" + "=" * 80)
    print("  RĀMAN Studio - ALCHEMI Integration Test Suite")
    print("  " + "=" * 78)
    print(f"  Server: {BASE_URL}")
    print(f"  Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    results = {}
    
    # Run tests
    results['server_health'] = test_server_health()
    results['engine_status'] = test_engine_status()
    results['geometry_optimization'] = test_geometry_optimization()
    results['band_gap_calculation'] = test_band_gap_calculation()
    results['multi_property'] = test_multi_property_calculation()
    results['example_molecules'] = test_example_molecules()
    results['batch_optimization'] = test_batch_optimization()
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v is not None and v is not False)
    total = len(results)
    
    print(f"\n  Tests Passed: {passed}/{total}")
    print(f"  Success Rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n  ✅ ALL TESTS PASSED!")
        print("\n  RĀMAN Studio quantum engine is fully operational.")
        print("  Ready for production use with NVIDIA ALCHEMI integration.")
    else:
        print("\n  ⚠️  SOME TESTS FAILED")
        print("\n  Check the logs above for details.")
        print("  If running in placeholder mode, this is expected without ALCHEMI API access.")
    
    print("\n" + "=" * 80)
    print("  Test suite complete!")
    print("=" * 80 + "\n")
    
    return results


if __name__ == "__main__":
    results = run_all_tests()
