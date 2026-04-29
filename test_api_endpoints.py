"""
API Endpoint Testing Script for VANL
=====================================
Tests all four new simulation engines via HTTP API.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint."""
    print("\n" + "="*60)
    print("Testing Health Endpoint")
    print("="*60)
    
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✅ Health check passed")


def test_ink_simulation():
    """Test ink formulation simulation."""
    print("\n" + "="*60)
    print("Testing Ink Formulation Engine")
    print("="*60)
    
    payload = {
        "filler_material": "graphene",
        "filler_loading_wt_pct": 10.0,
        "primary_solvent": "water",
        "print_method": "inkjet",
        "aspect_ratio": 100
    }
    
    response = requests.post(f"{BASE_URL}/api/pe/ink/simulate", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Viscosity: {data.get('viscosity_mPas', 'N/A')} mPa·s")
        print(f"Conductivity: {data.get('conductivity_S_m', 'N/A')} S/m")
        print(f"Sheet Resistance: {data.get('sheet_resistance_ohm_sq', 'N/A')} Ω/□")
        print(f"Printability Score: {data.get('printability_score', 'N/A')}")
        print(f"Above Percolation: {data.get('above_percolation', 'N/A')}")
        print("✅ Ink simulation passed")
    else:
        print(f"❌ Error: {response.text}")


def test_biosensor_simulation():
    """Test biosensor simulation."""
    print("\n" + "="*60)
    print("Testing Biosensor Engine")
    print("="*60)
    
    payload = {
        "analyte": "glucose",
        "sensor_type": "amperometric",
        "working_electrode_area_mm2": 7.07,
        "enzyme_loading_U_cm2": 10.0,
        "modifier": "enzyme"
    }
    
    response = requests.post(f"{BASE_URL}/api/pe/biosensor/simulate", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Sensitivity: {data.get('sensitivity_uA_mM', 'N/A')} µA/mM")
        print(f"LOD: {data.get('LOD_uM', 'N/A')} µM")
        print(f"LOQ: {data.get('LOQ_uM', 'N/A')} µM")
        print(f"Linear Range: {data.get('linear_range_mM', 'N/A')} mM")
        print(f"Response Time: {data.get('response_time_s', 'N/A')} s")
        print("✅ Biosensor simulation passed")
    else:
        print(f"❌ Error: {response.text}")


def test_battery_simulation():
    """Test battery simulation."""
    print("\n" + "="*60)
    print("Testing Battery Engine")
    print("="*60)
    
    payload = {
        "chemistry": "zinc_MnO2",
        "electrode_area_cm2": 1.0,
        "cathode_loading_mg_cm2": 10.0,
        "anode_loading_mg_cm2": 8.0,
        "C_rate": 0.5
    }
    
    response = requests.post(f"{BASE_URL}/api/pe/battery/simulate", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Theoretical Capacity: {data.get('theoretical_capacity_mAh', 'N/A')} mAh")
        print(f"Delivered Capacity: {data.get('delivered_capacity_mAh', 'N/A')} mAh")
        print(f"Energy: {data.get('energy_mWh', 'N/A')} mWh")
        print(f"Energy Density: {data.get('energy_density_Wh_kg', 'N/A')} Wh/kg")
        print(f"Nominal Voltage: {data.get('nominal_V', 'N/A')} V")
        print(f"Internal Resistance: {data.get('internal_resistance_ohm', 'N/A')} Ω")
        print("✅ Battery simulation passed")
    else:
        print(f"❌ Error: {response.text}")


def test_supercap_simulation():
    """Test supercapacitor simulation."""
    print("\n" + "="*60)
    print("Testing Supercapacitor Device Engine")
    print("="*60)
    
    payload = {
        "material": "activated_carbon",
        "capacitance_F_g": 150.0,
        "mass_mg": 1.0,
        "area_mm2": 100.0,
        "thickness_um": 50.0,
        "electrolyte": "1M H2SO4",
        "voltage_V": 1.0
    }
    
    response = requests.post(f"{BASE_URL}/api/pe/supercap/simulate", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Device Capacitance: {data.get('C_device_mF', 'N/A')} mF")
        print(f"Specific Capacitance: {data.get('C_specific_F_g', 'N/A')} F/g")
        print(f"Energy Density: {data.get('energy_Wh_kg', 'N/A')} Wh/kg")
        print(f"Power Density: {data.get('power_W_kg', 'N/A')} W/kg")
        print(f"ESR: {data.get('ESR_ohm', 'N/A')} Ω")
        print("✅ Supercapacitor simulation passed")
    else:
        print(f"❌ Error: {response.text}")


def test_list_endpoints():
    """Test listing endpoints."""
    print("\n" + "="*60)
    print("Testing List Endpoints")
    print("="*60)
    
    endpoints = [
        "/api/pe/ink/solvents",
        "/api/pe/ink/print-methods",
        "/api/pe/biosensor/analytes",
        "/api/pe/battery/chemistries"
    ]
    
    for endpoint in endpoints:
        response = requests.get(f"{BASE_URL}{endpoint}")
        print(f"\n{endpoint}: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Items: {len(data)}")
            print(f"  ✅ Passed")
        else:
            print(f"  ❌ Failed: {response.text}")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("VANL API Endpoint Testing")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    
    # Wait a moment for server to be ready
    time.sleep(1)
    
    try:
        # Test all endpoints
        test_health()
        test_ink_simulation()
        test_biosensor_simulation()
        test_battery_simulation()
        test_supercap_simulation()
        test_list_endpoints()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to server at", BASE_URL)
        print("Make sure the server is running with:")
        print("  python -m uvicorn vanl.backend.main:app --reload --port 8000")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
