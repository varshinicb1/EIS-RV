"""
Phase 6: Advanced Physics Validation - Test Script
==================================================
Comprehensive testing for LAMMPS and Quantum ESPRESSO integrations.

Tests:
1. System status
2. LAMMPS interface simulation
3. LAMMPS diffusion calculation
4. LAMMPS RDF computation
5. LAMMPS parameter extraction
6. Quantum ESPRESSO band structure
7. Quantum ESPRESSO DOS
8. Quantum ESPRESSO work function
9. Quantum ESPRESSO parameter extraction
10. Combined material validation
11. List validated materials

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}\n")


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {test_name}")
    if details:
        print(f"    {details}")


def test_status():
    """Test 1: Check system status."""
    print_header("Test 1: System Status")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v2/physics/status")
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "lammps" in data
        assert "quantum_espresso" in data
        
        print(f"LAMMPS available: {data['lammps']['lammps_available']}")
        print(f"Quantum ESPRESSO available: {data['quantum_espresso']['qe_available']}")
        
        print_result("System Status", True, "Both integrations initialized")
        return True
    except Exception as e:
        print_result("System Status", False, str(e))
        return False


def test_lammps_interface():
    """Test 2: LAMMPS interface simulation."""
    print_header("Test 2: LAMMPS Interface Simulation")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/physics/lammps/interface",
            json={
                "material": "graphene",
                "electrolyte": "1M NaCl",
                "voltage": 1.0,
                "temperature": 300.0,
                "n_steps": 10000,
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "results" in data
        
        results = data["results"]
        assert "capacitance" in results
        assert "charge_density" in results
        assert "ion_density_profile" in results
        assert "diffusion_coefficient" in results
        
        print(f"Capacitance: {results['capacitance']:.2f} F/m²")
        print(f"Charge density: {results['charge_density']:.4f} C/m²")
        print(f"Diffusion coefficient: {results['diffusion_coefficient']:.2e} m²/s")
        print(f"Ion density profile points: {len(results['ion_density_profile'])}")
        
        print_result("LAMMPS Interface", True, "Interface simulation successful")
        return True
    except Exception as e:
        print_result("LAMMPS Interface", False, str(e))
        return False


def test_lammps_diffusion():
    """Test 3: LAMMPS diffusion calculation."""
    print_header("Test 3: LAMMPS Diffusion Calculation")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/physics/lammps/diffusion",
            json={
                "material": "carbon",
                "electrolyte": "1M KOH",
                "temperature": 300.0,
                "n_steps": 5000,
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "results" in data
        
        results = data["results"]
        assert "cation" in results
        assert "anion" in results
        assert "temperature" in results
        
        print(f"Cation diffusion: {results['cation']:.2e} m²/s")
        print(f"Anion diffusion: {results['anion']:.2e} m²/s")
        print(f"Temperature: {results['temperature']} K")
        
        print_result("LAMMPS Diffusion", True, "Diffusion calculation successful")
        return True
    except Exception as e:
        print_result("LAMMPS Diffusion", False, str(e))
        return False


def test_lammps_rdf():
    """Test 4: LAMMPS RDF computation."""
    print_header("Test 4: LAMMPS RDF Computation")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/physics/lammps/rdf",
            json={
                "material": "graphene",
                "electrolyte": "1M NaCl",
                "r_max": 10.0,
                "n_bins": 100,
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "rdf" in data
        
        rdf = data["rdf"]
        assert len(rdf) == 100
        assert all(len(point) == 2 for point in rdf)
        
        print(f"RDF points: {len(rdf)}")
        print(f"First peak at r = {rdf[28][0]:.2f} Å, g(r) = {rdf[28][1]:.2f}")
        
        print_result("LAMMPS RDF", True, "RDF computation successful")
        return True
    except Exception as e:
        print_result("LAMMPS RDF", False, str(e))
        return False


def test_lammps_parameter_extraction():
    """Test 5: LAMMPS parameter extraction."""
    print_header("Test 5: LAMMPS Parameter Extraction")
    
    try:
        # First run interface simulation
        interface_response = requests.post(
            f"{BASE_URL}/api/v2/physics/lammps/interface",
            json={
                "material": "graphene",
                "electrolyte": "1M NaCl",
                "voltage": 1.0,
                "temperature": 300.0,
                "n_steps": 10000,
            }
        )
        interface_data = interface_response.json()
        
        # Extract parameters
        response = requests.post(
            f"{BASE_URL}/api/v2/physics/lammps/extract-parameters",
            json={
                "source": "lammps",
                "material": "graphene",
                "data": interface_data["results"],
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "parameters" in data
        
        params = data["parameters"]
        assert "Cdl" in params
        assert "Rct" in params
        assert "Rs" in params
        assert "n" in params
        
        print(f"Cdl: {params['Cdl']:.2e} F/cm²")
        print(f"Rct: {params['Rct']:.2f} Ω")
        print(f"Rs: {params['Rs']:.2f} Ω")
        print(f"n: {params['n']:.2f}")
        
        print_result("LAMMPS Parameters", True, "Parameter extraction successful")
        return True
    except Exception as e:
        print_result("LAMMPS Parameters", False, str(e))
        return False


def test_qe_band_structure():
    """Test 6: Quantum ESPRESSO band structure."""
    print_header("Test 6: Quantum ESPRESSO Band Structure")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/physics/qe/bands",
            json={
                "material": "graphene",
                "structure": None,
                "k_path": ["G", "M", "K", "G"],
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "band_structure" in data
        
        bands = data["band_structure"]
        assert "k_points" in bands
        assert "eigenvalues" in bands
        assert "fermi_energy" in bands
        assert "band_gap" in bands
        assert "is_metal" in bands
        
        print(f"K-points: {len(bands['k_points'])}")
        print(f"Bands: {len(bands['eigenvalues'][0])}")
        print(f"Fermi energy: {bands['fermi_energy']:.2f} eV")
        print(f"Band gap: {bands['band_gap']:.2f} eV")
        print(f"Is metal: {bands['is_metal']}")
        
        print_result("QE Band Structure", True, "Band structure calculation successful")
        return True
    except Exception as e:
        print_result("QE Band Structure", False, str(e))
        return False


def test_qe_dos():
    """Test 7: Quantum ESPRESSO DOS."""
    print_header("Test 7: Quantum ESPRESSO DOS")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/physics/qe/dos",
            json={
                "material": "graphene",
                "structure": None,
                "energy_range": [-10.0, 10.0],
                "n_points": 1000,
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "dos" in data
        
        dos = data["dos"]
        assert "energies" in dos
        assert "dos" in dos
        assert "fermi_energy" in dos
        
        print(f"Energy points: {len(dos['energies'])}")
        print(f"DOS points: {len(dos['dos'])}")
        print(f"Fermi energy: {dos['fermi_energy']:.2f} eV")
        print(f"DOS at E_F: {dos['dos'][len(dos['dos'])//2]:.2f}")
        
        print_result("QE DOS", True, "DOS calculation successful")
        return True
    except Exception as e:
        print_result("QE DOS", False, str(e))
        return False


def test_qe_work_function():
    """Test 8: Quantum ESPRESSO work function."""
    print_header("Test 8: Quantum ESPRESSO Work Function")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/physics/qe/work-function",
            json={
                "material": "graphene",
                "structure": None,
                "surface": "001",
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "work_function" in data
        
        wf = data["work_function"]
        assert "work_function" in wf
        assert "vacuum_level" in wf
        assert "fermi_level" in wf
        assert "surface_dipole" in wf
        
        print(f"Work function: {wf['work_function']:.2f} eV")
        print(f"Vacuum level: {wf['vacuum_level']:.2f} eV")
        print(f"Fermi level: {wf['fermi_level']:.2f} eV")
        print(f"Surface dipole: {wf['surface_dipole']:.2f} eV")
        
        print_result("QE Work Function", True, "Work function calculation successful")
        return True
    except Exception as e:
        print_result("QE Work Function", False, str(e))
        return False


def test_qe_parameter_extraction():
    """Test 9: Quantum ESPRESSO parameter extraction."""
    print_header("Test 9: Quantum ESPRESSO Parameter Extraction")
    
    try:
        # First run all QE calculations
        bands_response = requests.post(
            f"{BASE_URL}/api/v2/physics/qe/bands",
            json={"material": "graphene"}
        )
        dos_response = requests.post(
            f"{BASE_URL}/api/v2/physics/qe/dos",
            json={"material": "graphene"}
        )
        wf_response = requests.post(
            f"{BASE_URL}/api/v2/physics/qe/work-function",
            json={"material": "graphene"}
        )
        
        # Extract parameters
        response = requests.post(
            f"{BASE_URL}/api/v2/physics/qe/extract-parameters",
            json={
                "source": "qe",
                "material": "graphene",
                "data": {
                    "band_structure": bands_response.json()["band_structure"],
                    "dos": dos_response.json()["dos"],
                    "work_function": wf_response.json()["work_function"],
                },
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "parameters" in data
        
        params = data["parameters"]
        assert "conductivity" in params
        assert "Rct" in params
        assert "Cdl" in params
        assert "work_function" in params
        assert "band_gap" in params
        
        print(f"Conductivity: {params['conductivity']:.2e} S/m")
        print(f"Rct: {params['Rct']:.2f} Ω")
        print(f"Cdl: {params['Cdl']:.2e} F/cm²")
        print(f"Work function: {params['work_function']:.2f} eV")
        print(f"Band gap: {params['band_gap']:.2f} eV")
        
        print_result("QE Parameters", True, "Parameter extraction successful")
        return True
    except Exception as e:
        print_result("QE Parameters", False, str(e))
        return False


def test_combined_validation():
    """Test 10: Combined material validation."""
    print_header("Test 10: Combined Material Validation")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/physics/validate-material",
            params={
                "material": "graphene",
                "electrolyte": "1M NaCl",
                "voltage": 1.0,
                "temperature": 300.0,
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "interface_results" in data
        assert "band_structure" in data
        assert "dos" in data
        assert "work_function" in data
        assert "parameters" in data
        
        params = data["parameters"]
        assert "lammps" in params
        assert "quantum_espresso" in params
        assert "recommended" in params
        
        recommended = params["recommended"]
        print(f"Recommended parameters:")
        print(f"  Cdl: {recommended['Cdl']:.2e} F/cm²")
        print(f"  Rct: {recommended['Rct']:.2f} Ω")
        print(f"  Rs: {recommended['Rs']:.2f} Ω")
        print(f"  Conductivity: {recommended['conductivity']:.2e} S/m")
        print(f"  Work function: {recommended['work_function']:.2f} eV")
        print(f"  Band gap: {recommended['band_gap']:.2f} eV")
        
        print_result("Combined Validation", True, "Full validation successful")
        return True
    except Exception as e:
        print_result("Combined Validation", False, str(e))
        return False


def test_list_validated_materials():
    """Test 11: List validated materials."""
    print_header("Test 11: List Validated Materials")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v2/physics/materials/validated")
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "materials" in data
        
        materials = data["materials"]
        print(f"Validated materials: {len(materials)}")
        for mat in materials:
            print(f"  - {mat['material']}: {mat['lammps_runs']} LAMMPS, {mat['qe_runs']} QE runs")
        
        print_result("List Materials", True, "Material listing successful")
        return True
    except Exception as e:
        print_result("List Materials", False, str(e))
        return False


def main():
    """Run all tests."""
    print_header("Phase 6: Advanced Physics Validation - Test Suite")
    print("Testing LAMMPS and Quantum ESPRESSO integrations...")
    print(f"Backend URL: {BASE_URL}")
    
    # Run all tests
    tests = [
        ("System Status", test_status),
        ("LAMMPS Interface", test_lammps_interface),
        ("LAMMPS Diffusion", test_lammps_diffusion),
        ("LAMMPS RDF", test_lammps_rdf),
        ("LAMMPS Parameters", test_lammps_parameter_extraction),
        ("QE Band Structure", test_qe_band_structure),
        ("QE DOS", test_qe_dos),
        ("QE Work Function", test_qe_work_function),
        ("QE Parameters", test_qe_parameter_extraction),
        ("Combined Validation", test_combined_validation),
        ("List Materials", test_list_validated_materials),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results.append((name, False))
        time.sleep(0.5)  # Brief pause between tests
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total} ({100*passed//total}%)")
    print("\nDetailed results:")
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    if passed == total:
        print("\n🎉 All tests passed! Phase 6 is complete.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    exit(main())
