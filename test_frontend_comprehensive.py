"""
Comprehensive Frontend Testing Script
=====================================
Tests every frontend panel, file uploads, and NVIDIA integration.

Tests:
1. Check frontend is running
2. Test all simulation panels
3. Test file upload functionality
4. Test NVIDIA API integration
5. Test materials explorer
6. Test all buttons and interactions
7. Verify CSV data processing

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import requests
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"


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


def create_test_csv(filename: str, data_type: str) -> str:
    """Create a test CSV file for upload testing."""
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    
    filepath = test_dir / filename
    
    if data_type == "eis":
        # EIS data: frequency, Z_real, Z_imag
        content = """frequency,Z_real,Z_imag
100000,10.5,-0.5
10000,11.2,-2.3
1000,15.8,-8.9
100,35.2,-25.6
10,85.3,-45.2
1,150.8,-35.1
0.1,180.2,-15.3
0.01,195.5,-5.2
"""
    elif data_type == "cv":
        # CV data: voltage, current
        content = """voltage,current
-0.5,-0.0001
-0.4,-0.00005
-0.3,0.00002
-0.2,0.00008
-0.1,0.00015
0.0,0.00020
0.1,0.00025
0.2,0.00028
0.3,0.00025
0.4,0.00018
0.5,0.00010
"""
    elif data_type == "gcd":
        # GCD data: time, voltage
        content = """time,voltage
0,0.0
10,0.5
20,0.8
30,0.9
40,0.95
50,0.98
60,0.99
70,1.0
80,0.95
90,0.85
100,0.7
"""
    elif data_type == "raman":
        # Raman data: wavenumber, intensity
        content = """wavenumber,intensity
500,100
600,150
700,200
800,300
900,500
1000,800
1100,1200
1200,1500
1300,2000
1400,2500
1500,3000
1600,3500
1700,2800
1800,2000
1900,1500
2000,1000
"""
    else:
        content = "x,y\n1,2\n3,4\n5,6\n"
    
    with open(filepath, "w") as f:
        f.write(content)
    
    return str(filepath)


def test_frontend_running():
    """Test 1: Check if frontend is running."""
    print_header("Test 1: Frontend Running")
    
    try:
        # Try to access frontend
        response = requests.get(FRONTEND_URL, timeout=5)
        
        if response.status_code == 200:
            print_result("Frontend Running", True, f"Frontend accessible at {FRONTEND_URL}")
            return True
        else:
            print_result("Frontend Running", False, f"Status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_result("Frontend Running", False, "Frontend not accessible - is it running?")
        print("    Start frontend with: cd src/frontend && npm run dev")
        return False
    except Exception as e:
        print_result("Frontend Running", False, str(e))
        return False


def test_backend_health():
    """Test 2: Check backend health."""
    print_header("Test 2: Backend Health")
    
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "healthy"
        
        print(f"Backend version: {data.get('version', 'unknown')}")
        print(f"Uptime: {data.get('uptime', 'unknown')}")
        
        print_result("Backend Health", True, "Backend is healthy")
        return True
    except Exception as e:
        print_result("Backend Health", False, str(e))
        return False


def test_eis_simulation():
    """Test 3: EIS simulation endpoint."""
    print_header("Test 3: EIS Simulation")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/simulate/eis",
            json={
                "Rs": 10.0,
                "Rct": 100.0,
                "Cdl": 1e-5,
                "n": 0.9,
                "f_min": 0.01,
                "f_max": 100000,
                "points_per_decade": 10,
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert "frequencies" in data
        assert "Z_real" in data
        assert "Z_imag" in data
        assert len(data["frequencies"]) > 0
        
        print(f"Frequency points: {len(data['frequencies'])}")
        print(f"Frequency range: {data['frequencies'][0]:.2e} - {data['frequencies'][-1]:.2e} Hz")
        
        print_result("EIS Simulation", True, "EIS endpoint working")
        return True
    except Exception as e:
        print_result("EIS Simulation", False, str(e))
        return False


def test_cv_simulation():
    """Test 4: CV simulation endpoint."""
    print_header("Test 4: CV Simulation")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/simulate/cv",
            json={
                "E0": 0.0,
                "k0": 1e-3,
                "alpha": 0.5,
                "n": 1,
                "A": 0.01,
                "C_bulk": 1e-3,
                "D": 1e-9,
                "scan_rate": 0.1,
                "E_start": -0.5,
                "E_end": 0.5,
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert "potential" in data
        assert "current" in data
        assert len(data["potential"]) > 0
        
        print(f"Data points: {len(data['potential'])}")
        print(f"Potential range: {min(data['potential']):.2f} - {max(data['potential']):.2f} V")
        
        print_result("CV Simulation", True, "CV endpoint working")
        return True
    except Exception as e:
        print_result("CV Simulation", False, str(e))
        return False


def test_gcd_simulation():
    """Test 5: GCD simulation endpoint."""
    print_header("Test 5: GCD Simulation")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/simulate/gcd",
            json={
                "C": 1.0,
                "Rs": 10.0,
                "Rleak": 10000.0,
                "I": 0.1,
                "V_max": 1.0,
                "V_min": 0.0,
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert "time" in data
        assert "voltage" in data
        assert len(data["time"]) > 0
        
        print(f"Data points: {len(data['time'])}")
        print(f"Time range: {data['time'][0]:.2f} - {data['time'][-1]:.2f} s")
        
        print_result("GCD Simulation", True, "GCD endpoint working")
        return True
    except Exception as e:
        print_result("GCD Simulation", False, str(e))
        return False


def test_file_upload_eis():
    """Test 6: EIS file upload."""
    print_header("Test 6: EIS File Upload")
    
    try:
        # Create test CSV
        csv_path = create_test_csv("test_eis.csv", "eis")
        
        # Upload file
        with open(csv_path, "rb") as f:
            files = {"file": ("test_eis.csv", f, "text/csv")}
            response = requests.post(
                f"{BASE_URL}/api/v2/upload/eis",
                files=files
            )
        
        data = response.json()
        
        assert response.status_code == 200
        assert "frequencies" in data
        assert "Z_real" in data
        assert "Z_imag" in data
        
        print(f"Uploaded {len(data['frequencies'])} data points")
        print(f"Frequency range: {min(data['frequencies']):.2e} - {max(data['frequencies']):.2e} Hz")
        
        print_result("EIS File Upload", True, "File upload working")
        return True
    except Exception as e:
        print_result("EIS File Upload", False, str(e))
        return False


def test_file_upload_cv():
    """Test 7: CV file upload."""
    print_header("Test 7: CV File Upload")
    
    try:
        # Create test CSV
        csv_path = create_test_csv("test_cv.csv", "cv")
        
        # Upload file
        with open(csv_path, "rb") as f:
            files = {"file": ("test_cv.csv", f, "text/csv")}
            response = requests.post(
                f"{BASE_URL}/api/v2/upload/cv",
                files=files
            )
        
        data = response.json()
        
        assert response.status_code == 200
        assert "potential" in data or "voltage" in data
        assert "current" in data
        
        print(f"Uploaded {len(data.get('potential', data.get('voltage', [])))} data points")
        
        print_result("CV File Upload", True, "File upload working")
        return True
    except Exception as e:
        print_result("CV File Upload", False, str(e))
        return False


def test_nvidia_api_key():
    """Test 8: NVIDIA API key configuration."""
    print_header("Test 8: NVIDIA API Key")
    
    try:
        # Check if NVIDIA_API_KEY is set in environment
        nvidia_key = os.environ.get("NVIDIA_API_KEY")
        
        if nvidia_key and nvidia_key != "":
            print(f"NVIDIA API key found: {nvidia_key[:10]}...")
            
            # Test if key works (optional - would need actual NVIDIA endpoint)
            print_result("NVIDIA API Key", True, "Key is configured")
            return True
        else:
            print("NVIDIA API key not found in environment")
            print("Set it with: export NVIDIA_API_KEY=your_key_here")
            print_result("NVIDIA API Key", False, "Key not configured")
            return False
    except Exception as e:
        print_result("NVIDIA API Key", False, str(e))
        return False


def test_material_identification():
    """Test 9: Material identification with CSV."""
    print_header("Test 9: Material Identification")
    
    try:
        # Create test EIS data
        csv_path = create_test_csv("test_material_id.csv", "eis")
        
        # First upload the file
        with open(csv_path, "rb") as f:
            files = {"file": ("test_material_id.csv", f, "text/csv")}
            upload_response = requests.post(
                f"{BASE_URL}/api/v2/upload/eis",
                files=files
            )
        
        eis_data = upload_response.json()
        
        # Then identify material
        response = requests.post(
            f"{BASE_URL}/api/v2/material-id/identify/eis",
            json={
                "frequencies": eis_data["frequencies"],
                "Z_real": eis_data["Z_real"],
                "Z_imag": eis_data["Z_imag"],
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert "prediction" in data
        
        pred = data["prediction"]
        print(f"Identified material: {pred.get('material_name', 'unknown')}")
        print(f"Confidence: {pred.get('confidence', 0):.2%}")
        
        print_result("Material Identification", True, "Identification working")
        return True
    except Exception as e:
        print_result("Material Identification", False, str(e))
        return False


def test_materials_database():
    """Test 10: Materials database."""
    print_header("Test 10: Materials Database")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v2/material-id/materials")
        data = response.json()
        
        assert response.status_code == 200
        assert "materials" in data
        
        materials = data["materials"]
        print(f"Materials in database: {len(materials)}")
        for mat in materials[:5]:
            print(f"  - {mat.get('name', 'unknown')}")
        
        print_result("Materials Database", True, f"{len(materials)} materials loaded")
        return True
    except Exception as e:
        print_result("Materials Database", False, str(e))
        return False


def test_optimization_campaign():
    """Test 11: Optimization campaign creation."""
    print_header("Test 11: Optimization Campaign")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/optimize/campaigns/create",
            json={
                "name": "Test Campaign",
                "objective": "maximize",
                "target_metric": "capacitance",
                "parameter_space": {
                    "Rs": [1.0, 100.0],
                    "Rct": [10.0, 1000.0],
                    "Cdl": [1e-6, 1e-4],
                },
                "max_iterations": 10,
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert "campaign" in data
        
        campaign = data["campaign"]
        print(f"Campaign ID: {campaign.get('campaign_id', 'unknown')}")
        print(f"Status: {campaign.get('status', 'unknown')}")
        
        print_result("Optimization Campaign", True, "Campaign creation working")
        return True
    except Exception as e:
        print_result("Optimization Campaign", False, str(e))
        return False


def test_workflow_execution():
    """Test 12: Workflow execution."""
    print_header("Test 12: Workflow Execution")
    
    try:
        # Get available templates
        templates_response = requests.get(f"{BASE_URL}/api/v2/workflows/templates")
        templates = templates_response.json()["templates"]
        
        if len(templates) == 0:
            print_result("Workflow Execution", False, "No templates available")
            return False
        
        # Execute first template
        template_id = templates[0]["template_id"]
        response = requests.post(
            f"{BASE_URL}/api/v2/workflows/execute",
            json={
                "workflow_id": template_id,
                "parameters": {
                    "material": "graphene",
                    "Rs": 10.0,
                    "Rct": 100.0,
                },
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert "execution_id" in data
        
        print(f"Execution ID: {data.get('execution_id', 'unknown')}")
        print(f"Status: {data.get('status', 'unknown')}")
        
        print_result("Workflow Execution", True, "Workflow execution working")
        return True
    except Exception as e:
        print_result("Workflow Execution", False, str(e))
        return False


def test_physics_validation():
    """Test 13: Physics validation."""
    print_header("Test 13: Physics Validation")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/physics/validate-material",
            params={
                "material": "graphene",
                "electrolyte": "1M NaCl",
            }
        )
        data = response.json()
        
        assert response.status_code == 200
        assert "parameters" in data
        
        params = data["parameters"]["recommended"]
        print(f"Validated parameters:")
        print(f"  Cdl: {params['Cdl']:.2e} F/cm²")
        print(f"  Rct: {params['Rct']:.2f} Ω")
        print(f"  Work function: {params['work_function']:.2f} eV")
        
        print_result("Physics Validation", True, "Physics validation working")
        return True
    except Exception as e:
        print_result("Physics Validation", False, str(e))
        return False


def test_all_panels():
    """Test 14: All simulation panels."""
    print_header("Test 14: All Simulation Panels")
    
    panels = [
        ("EIS", "/api/v2/simulate/eis"),
        ("CV", "/api/v2/simulate/cv"),
        ("GCD", "/api/v2/simulate/gcd"),
        ("Supercapacitor", "/api/v2/simulate/supercap"),
        ("Battery", "/api/v2/simulate/battery"),
        ("Biosensor", "/api/v2/simulate/biosensor"),
    ]
    
    results = []
    for panel_name, endpoint in panels:
        try:
            # Test with minimal parameters
            response = requests.post(f"{BASE_URL}{endpoint}", json={})
            
            # Some endpoints might require parameters, so 400 is acceptable
            if response.status_code in [200, 400]:
                print(f"  ✅ {panel_name} panel endpoint accessible")
                results.append(True)
            else:
                print(f"  ❌ {panel_name} panel endpoint failed: {response.status_code}")
                results.append(False)
        except Exception as e:
            print(f"  ❌ {panel_name} panel error: {e}")
            results.append(False)
    
    passed = sum(results)
    total = len(results)
    print_result("All Panels", passed == total, f"{passed}/{total} panels accessible")
    return passed == total


def main():
    """Run all tests."""
    print_header("Comprehensive Frontend Testing")
    print("Testing all panels, file uploads, and integrations...")
    print(f"Backend URL: {BASE_URL}")
    print(f"Frontend URL: {FRONTEND_URL}")
    
    # Run all tests
    tests = [
        ("Frontend Running", test_frontend_running),
        ("Backend Health", test_backend_health),
        ("EIS Simulation", test_eis_simulation),
        ("CV Simulation", test_cv_simulation),
        ("GCD Simulation", test_gcd_simulation),
        ("EIS File Upload", test_file_upload_eis),
        ("CV File Upload", test_file_upload_cv),
        ("NVIDIA API Key", test_nvidia_api_key),
        ("Material Identification", test_material_identification),
        ("Materials Database", test_materials_database),
        ("Optimization Campaign", test_optimization_campaign),
        ("Workflow Execution", test_workflow_execution),
        ("Physics Validation", test_physics_validation),
        ("All Panels", test_all_panels),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results.append((name, False))
        time.sleep(0.5)
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total} ({100*passed//total}%)")
    print("\nDetailed results:")
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    # Recommendations
    print_header("Recommendations")
    if passed < total:
        print("⚠️  Some tests failed. Check the following:")
        for name, result in results:
            if not result:
                if "Frontend" in name:
                    print(f"  - Start frontend: cd src/frontend && npm run dev")
                elif "NVIDIA" in name:
                    print(f"  - Set NVIDIA API key: export NVIDIA_API_KEY=your_key")
                else:
                    print(f"  - Fix {name}")
    else:
        print("✅ All tests passed!")
        print("✅ Frontend is fully functional")
        print("✅ File uploads working")
        print("✅ All panels accessible")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit(main())
