"""
Test Specific Capacitance Calculator
=====================================
Comprehensive tests for the capacitance calculation system.

Tests standard equations from literature:
- Gravimetric specific capacitance (F/g)
- Areal specific capacitance (F/cm²)
- Volumetric specific capacitance (F/cm³)
- Multi-scan-rate analysis
- Ragone plot (energy/power density)

Author: VidyuthLabs
Date: May 13, 2026
"""

import requests
import numpy as np
import json

API_BASE = "http://localhost:8000"


def print_header(title):
    print("\n" + "="*70)
    print(title)
    print("="*70)


def generate_ideal_cv_data(scan_rate_mV_s=50, capacitance_F_g=200, mass_g=0.001):
    """Generate ideal rectangular CV for testing."""
    # Potential window: -0.2 to 0.8 V
    E_min, E_max = -0.2, 0.8
    potential_window = E_max - E_min
    scan_rate_V_s = scan_rate_mV_s / 1000.0
    
    # Time for one full cycle
    t_cycle = 2 * potential_window / scan_rate_V_s
    
    # Generate potential array (forward and reverse)
    n_points = 200
    t = np.linspace(0, t_cycle, n_points)
    
    # Forward scan
    E_forward = np.linspace(E_min, E_max, n_points // 2)
    # Reverse scan
    E_reverse = np.linspace(E_max, E_min, n_points // 2)
    E = np.concatenate([E_forward, E_reverse])
    
    # Ideal capacitive current: i = C × dE/dt = C × scan_rate
    # Total capacitance = specific_capacitance × mass
    C_total = capacitance_F_g * mass_g
    i_ideal = C_total * scan_rate_V_s
    
    # Current is positive for forward scan, negative for reverse
    i = np.ones(n_points) * i_ideal
    i[n_points//2:] = -i_ideal
    
    return E.tolist(), i.tolist()


def test_basic_calculation():
    """Test 1: Basic capacitance calculation from CV data."""
    print_header("Test 1: Basic Capacitance Calculation")
    
    # Generate ideal CV data
    mass_g = 0.001  # 1 mg
    scan_rate = 50  # mV/s
    expected_capacitance = 200  # F/g
    
    E, i = generate_ideal_cv_data(
        scan_rate_mV_s=scan_rate,
        capacitance_F_g=expected_capacitance,
        mass_g=mass_g
    )
    
    # Calculate capacitance
    response = requests.post(
        f"{API_BASE}/api/v2/capacitance/from-cv",
        json={
            "potential": E,
            "current": i,
            "scan_rate_mV_s": scan_rate,
            "mass_g": mass_g,
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        calc_capacitance = result['result']['specific_capacitance_F_g']
        
        print(f"✅ Calculation successful")
        print(f"   Expected: {expected_capacitance:.2f} F/g")
        print(f"   Calculated: {calc_capacitance:.2f} F/g")
        print(f"   Error: {abs(calc_capacitance - expected_capacitance):.2f} F/g")
        print(f"   Charge: {result['result']['charge_coulombs']:.6f} C")
        print(f"   Equation: {result['equation']}")
        print(f"   Reference: {result['reference']}")
        return True
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return False


def test_real_material_cv():
    """Test 2: Calculate capacitance for real material (graphene)."""
    print_header("Test 2: Real Material CV (Graphene)")
    
    # Simulate graphene CV (250 F/g typical)
    mass_g = 0.002  # 2 mg
    area_cm2 = 1.0  # 1 cm²
    scan_rate = 100  # mV/s
    
    E, i = generate_ideal_cv_data(
        scan_rate_mV_s=scan_rate,
        capacitance_F_g=250,
        mass_g=mass_g
    )
    
    response = requests.post(
        f"{API_BASE}/api/v2/capacitance/from-cv",
        json={
            "potential": E,
            "current": i,
            "scan_rate_mV_s": scan_rate,
            "mass_g": mass_g,
            "area_cm2": area_cm2,
        }
    )
    
    if response.status_code == 200:
        result = response.json()['result']
        print(f"✅ Graphene capacitance calculated")
        print(f"   Specific capacitance: {result['specific_capacitance_F_g']:.2f} F/g")
        print(f"   Areal capacitance: {result['areal_capacitance_F_cm2']:.6f} F/cm²")
        print(f"   Total capacitance: {result['total_capacitance_F']:.6f} F")
        print(f"   Reversibility: {result['reversibility']:.3f}")
        print(f"   Coulombic efficiency: {result['coulombic_efficiency']:.3f}")
        return True
    else:
        print(f"❌ Failed: {response.status_code}")
        return False


def test_multi_scan_rate():
    """Test 3: Multi-scan-rate analysis."""
    print_header("Test 3: Multi-Scan-Rate Analysis")
    
    mass_g = 0.001
    scan_rates = [10, 20, 50, 100, 200]  # mV/s
    
    cv_data = []
    for scan_rate in scan_rates:
        E, i = generate_ideal_cv_data(
            scan_rate_mV_s=scan_rate,
            capacitance_F_g=200,
            mass_g=mass_g
        )
        cv_data.append({
            "potential": E,
            "current": i,
            "scan_rate_mV_s": scan_rate
        })
    
    response = requests.post(
        f"{API_BASE}/api/v2/capacitance/multi-scan-rate",
        json={
            "cv_data": cv_data,
            "mass_g": mass_g,
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        analysis = result['analysis']
        
        print(f"✅ Multi-scan-rate analysis complete")
        print(f"   Scan rates: {analysis['scan_rates']} mV/s")
        print(f"   Capacitances: {[f'{c:.1f}' for c in analysis['capacitances']]} F/g")
        print(f"   Rate capability: {analysis['rate_capability']:.1f}%")
        print(f"   Best capacitance: {analysis['best_capacitance']:.2f} F/g")
        print(f"   Performance: {result['interpretation']['performance']}")
        return True
    else:
        print(f"❌ Failed: {response.status_code}")
        return False


def test_ragone_analysis():
    """Test 4: Ragone plot (energy/power density)."""
    print_header("Test 4: Ragone Analysis (Energy/Power Density)")
    
    response = requests.post(
        f"{API_BASE}/api/v2/capacitance/ragone-analysis",
        json={
            "capacitance_F_g": 250,  # Graphene
            "potential_window_V": 1.0,
            "mass_g": 0.001,
            "esr_ohm": 5.0,
        }
    )
    
    if response.status_code == 200:
        result = response.json()['result']
        print(f"✅ Ragone analysis complete")
        print(f"   Energy density: {result['energy_density_Wh_kg']:.2f} Wh/kg")
        print(f"   Power density: {result['power_density_W_kg']:.2f} W/kg")
        print(f"   Capacitance: {result['capacitance_F_g']:.2f} F/g")
        print(f"   Potential window: {result['potential_window_V']:.2f} V")
        return True
    else:
        print(f"❌ Failed: {response.status_code}")
        return False


def test_equations_endpoint():
    """Test 5: Get standard equations."""
    print_header("Test 5: Standard Equations Reference")
    
    response = requests.get(f"{API_BASE}/api/v2/capacitance/equations")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Equations retrieved")
        
        for name, eq in data['equations'].items():
            print(f"\n   {name}:")
            print(f"   Formula: {eq['formula']}")
            print(f"   Units: {eq['units']}")
        
        print(f"\n   References:")
        for ref in data['references']:
            print(f"   - {ref['authors']} ({ref['year']})")
            print(f"     {ref['title']}")
        
        return True
    else:
        print(f"❌ Failed: {response.status_code}")
        return False


def test_best_practices():
    """Test 6: Get best practices."""
    print_header("Test 6: Best Practices for CV Measurements")
    
    response = requests.get(f"{API_BASE}/api/v2/capacitance/best-practices")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Best practices retrieved")
        
        bp = data['best_practices']
        print(f"\n   Scan rate: {bp['scan_rate']['recommendation']}")
        print(f"   Typical values: {bp['scan_rate']['typical_values']} mV/s")
        
        print(f"\n   Potential window:")
        print(f"   - Aqueous: {bp['potential_window']['aqueous']}")
        print(f"   - Organic: {bp['potential_window']['organic']}")
        print(f"   - Ionic liquid: {bp['potential_window']['ionic_liquid']}")
        
        print(f"\n   Common mistakes:")
        for mistake in data['common_mistakes'][:3]:
            print(f"   - {mistake}")
        
        return True
    else:
        print(f"❌ Failed: {response.status_code}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("SPECIFIC CAPACITANCE CALCULATOR TEST SUITE")
    print("="*70)
    print("\nTesting standard equations from electrochemistry literature:")
    print("- Stoller & Ruoff (2010), Energy Environ. Sci.")
    print("- Conway (1999), Electrochemical Supercapacitors")
    
    tests = [
        ("Basic Calculation", test_basic_calculation),
        ("Real Material CV", test_real_material_cv),
        ("Multi-Scan-Rate", test_multi_scan_rate),
        ("Ragone Analysis", test_ragone_analysis),
        ("Equations Reference", test_equations_endpoint),
        ("Best Practices", test_best_practices),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print_header("SUMMARY")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")
    
    print(f"\nTests passed: {passed}/{total} ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n❌ {total - passed} test(s) failed")


if __name__ == "__main__":
    main()
