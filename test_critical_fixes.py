"""
Test Critical Fixes
===================
Verify all 4 critical fixes are working.

Run after restarting the backend server.

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

import requests
import os
from pathlib import Path

BASE_URL = "http://localhost:8000"


def print_test(name, passed, details=""):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {name}")
    if details:
        print(f"    {details}")


def create_test_csv():
    """Create test CSV files."""
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    
    # EIS data
    eis_path = test_dir / "test_eis.csv"
    with open(eis_path, "w") as f:
        f.write("frequency,Z_real,Z_imag\n")
        f.write("100000,10.5,-0.5\n")
        f.write("10000,11.2,-2.3\n")
        f.write("1000,15.8,-8.9\n")
        f.write("100,35.2,-25.6\n")
    
    # CV data
    cv_path = test_dir / "test_cv.csv"
    with open(cv_path, "w") as f:
        f.write("voltage,current\n")
        f.write("-0.5,-0.0001\n")
        f.write("-0.3,0.00002\n")
        f.write("0.0,0.00020\n")
        f.write("0.5,0.00010\n")
    
    # GCD data
    gcd_path = test_dir / "test_gcd.csv"
    with open(gcd_path, "w") as f:
        f.write("time,voltage\n")
        f.write("0,0.0\n")
        f.write("10,0.5\n")
        f.write("20,0.8\n")
        f.write("30,0.9\n")
    
    return eis_path, cv_path, gcd_path


def test_file_upload_eis():
    """Test 1: EIS file upload."""
    print("\n" + "="*70)
    print("Test 1: EIS File Upload")
    print("="*70)
    
    try:
        eis_path, _, _ = create_test_csv()
        
        with open(eis_path, "rb") as f:
            files = {"file": ("test_eis.csv", f, "text/csv")}
            response = requests.post(f"{BASE_URL}/api/v2/upload/eis", files=files)
        
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "frequencies" in data
        assert len(data["frequencies"]) == 4
        
        print_test("EIS Upload", True, f"Uploaded {data['n_points']} points")
        return True
    except Exception as e:
        print_test("EIS Upload", False, str(e))
        return False


def test_file_upload_cv():
    """Test 2: CV file upload."""
    print("\n" + "="*70)
    print("Test 2: CV File Upload")
    print("="*70)
    
    try:
        _, cv_path, _ = create_test_csv()
        
        with open(cv_path, "rb") as f:
            files = {"file": ("test_cv.csv", f, "text/csv")}
            response = requests.post(f"{BASE_URL}/api/v2/upload/cv", files=files)
        
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "potential" in data
        assert len(data["potential"]) == 4
        
        print_test("CV Upload", True, f"Uploaded {data['n_points']} points")
        return True
    except Exception as e:
        print_test("CV Upload", False, str(e))
        return False


def test_file_upload_gcd():
    """Test 3: GCD file upload."""
    print("\n" + "="*70)
    print("Test 3: GCD File Upload")
    print("="*70)
    
    try:
        _, _, gcd_path = create_test_csv()
        
        with open(gcd_path, "rb") as f:
            files = {"file": ("test_gcd.csv", f, "text/csv")}
            response = requests.post(f"{BASE_URL}/api/v2/upload/gcd", files=files)
        
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "success"
        assert "time" in data
        assert len(data["time"]) == 4
        
        print_test("GCD Upload", True, f"Uploaded {data['n_points']} points")
        return True
    except Exception as e:
        print_test("GCD Upload", False, str(e))
        return False


def test_materials_database():
    """Test 4: Materials database loaded."""
    print("\n" + "="*70)
    print("Test 4: Materials Database")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/v2/material-id/materials")
        data = response.json()
        
        assert response.status_code == 200
        assert "materials" in data
        
        n_materials = len(data["materials"])
        
        if n_materials > 0:
            print(f"Materials loaded: {n_materials}")
            for mat in data["materials"][:3]:
                print(f"  - {mat.get('name', 'unknown')}")
            print_test("Materials Database", True, f"{n_materials} materials loaded")
            return True
        else:
            print_test("Materials Database", False, "No materials loaded")
            return False
    except Exception as e:
        print_test("Materials Database", False, str(e))
        return False


def test_workflow_templates():
    """Test 5: Workflow templates initialized."""
    print("\n" + "="*70)
    print("Test 5: Workflow Templates")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/v2/workflows/templates")
        data = response.json()
        
        assert response.status_code == 200
        assert "templates" in data
        
        n_templates = len(data["templates"])
        
        if n_templates > 0:
            print(f"Templates loaded: {n_templates}")
            for template in data["templates"][:3]:
                print(f"  - {template.get('name', 'unknown')}")
            print_test("Workflow Templates", True, f"{n_templates} templates loaded")
            return True
        else:
            print_test("Workflow Templates", False, "No templates loaded")
            return False
    except Exception as e:
        print_test("Workflow Templates", False, str(e))
        return False


def test_nvidia_api_key():
    """Test 6: NVIDIA API key configured."""
    print("\n" + "="*70)
    print("Test 6: NVIDIA API Key")
    print("="*70)
    
    try:
        # Check environment variable
        nvidia_key = os.environ.get("NVIDIA_API_KEY")
        
        # Also check .env file
        env_path = Path(".env")
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if line.startswith("NVIDIA_API_KEY="):
                        nvidia_key = line.split("=", 1)[1].strip()
                        break
        
        if nvidia_key and nvidia_key != "":
            print(f"NVIDIA API key found: {nvidia_key[:15]}...")
            print_test("NVIDIA API Key", True, "Key is configured")
            return True
        else:
            print_test("NVIDIA API Key", False, "Key not found")
            return False
    except Exception as e:
        print_test("NVIDIA API Key", False, str(e))
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("CRITICAL FIXES VERIFICATION")
    print("="*70)
    print(f"Backend URL: {BASE_URL}")
    print("\n⚠️  Make sure backend has been restarted!")
    
    # Run tests
    results = [
        test_file_upload_eis(),
        test_file_upload_cv(),
        test_file_upload_gcd(),
        test_materials_database(),
        test_workflow_templates(),
        test_nvidia_api_key(),
    ]
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTests passed: {passed}/{total} ({100*passed//total}%)")
    
    if passed == total:
        print("\n✅ ALL CRITICAL FIXES VERIFIED!")
        print("✅ System is now fully functional")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("⚠️  Make sure backend has been restarted")
        return 1


if __name__ == "__main__":
    exit(main())
