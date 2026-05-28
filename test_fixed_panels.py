#!/usr/bin/env python3
"""
Test Script for Fixed Frontend Panels
======================================
Verifies that all API endpoints used by MaterialIdentificationPanel
and MaterialDiscoveryPanel are working correctly.

Run this after starting the backend server:
    python -m uvicorn src.backend.api.server:app --reload --port 8000
    python test_fixed_panels.py
"""

import requests
import json
from typing import Dict, Any

API_BASE = "http://localhost:8000"

def test_endpoint(method: str, endpoint: str, data: Dict[str, Any] = None, expected_status: int = 200):
    """Test a single API endpoint."""
    url = f"{API_BASE}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        status = "✅" if response.status_code == expected_status else "❌"
        print(f"{status} {method} {endpoint} - Status: {response.status_code}")
        
        if response.status_code != expected_status:
            print(f"   Error: {response.text[:200]}")
        
        return response.status_code == expected_status
    
    except requests.exceptions.ConnectionError:
        print(f"❌ {method} {endpoint} - Connection failed (is server running?)")
        return False
    except Exception as e:
        print(f"❌ {method} {endpoint} - Error: {e}")
        return False


def main():
    print("=" * 70)
    print("Testing Fixed Frontend Panels - API Endpoints")
    print("=" * 70)
    
    results = []
    
    # ── Material Identification Panel Endpoints ──────────────────────
    print("\n📊 Material Identification Panel Endpoints:")
    print("-" * 70)
    
    results.append(test_endpoint("GET", "/api/v2/material-id/status"))
    results.append(test_endpoint("GET", "/api/v2/material-id/materials"))
    
    # Test EIS identification (may fail if model not trained)
    eis_data = {
        "frequencies": [0.01, 0.1, 1, 10, 100, 1000],
        "Z_real": [10, 15, 25, 35, 40, 42],
        "Z_imag": [0, -5, -15, -25, -10, -2],
        "top_k": 3
    }
    results.append(test_endpoint("POST", "/api/v2/material-id/identify/eis", eis_data, expected_status=200))
    
    # Test CV identification
    cv_data = {
        "potential": [-0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.4, 0.5],
        "current": [0, 0.1, 0.3, 0.5, 0.7, 0.6, 0.4, 0.2, 0],
        "top_k": 3
    }
    results.append(test_endpoint("POST", "/api/v2/material-id/identify/cv", cv_data, expected_status=200))
    
    # Test Raman identification
    raman_data = {
        "wavenumber": [1000, 1200, 1350, 1580, 2000, 2700],
        "intensity": [100, 200, 500, 800, 300, 400],
        "top_k": 3
    }
    results.append(test_endpoint("POST", "/api/v2/material-id/identify/raman", raman_data, expected_status=200))
    
    # ── Material Discovery Panel Endpoints ───────────────────────────
    print("\n🔬 Material Discovery Panel Endpoints:")
    print("-" * 70)
    
    # Test material discovery
    discovery_data = {
        "application": "Pb2+ detection biosensor",
        "max_candidates": 5
    }
    results.append(test_endpoint("POST", "/api/v2/materials/discover", discovery_data))
    
    # Test synthesis routes
    synthesis_data = {
        "material_name": "MoS2",
        "material_formula": "MoS2",
        "target_form": "nanosheets"
    }
    results.append(test_endpoint("POST", "/api/v2/materials/synthesis", synthesis_data))
    
    # Test biosensor suggestions
    biosensor_data = {
        "analyte": "Pb2+",
        "technique": "DPV",
        "electrode_substrate": "screen-printed carbon",
        "max_suggestions": 3
    }
    results.append(test_endpoint("POST", "/api/v2/biosensor/suggest", biosensor_data))
    
    # Test supported analytes
    results.append(test_endpoint("GET", "/api/v2/biosensor/supported-analytes"))
    
    # ── Cross-Modal Identification Endpoints ──────────────────────────
    print("\n🎯 Cross-Modal Identification Endpoints:")
    print("-" * 70)
    
    # Test CV identification
    cv_identify_data = {
        "peak_separation_mV": 65,
        "ipa_ipc_ratio": 0.99,
        "onset_potential_V": 0.1
    }
    results.append(test_endpoint("POST", "/api/v2/identify/cv", cv_identify_data))
    
    # Test EIS identification
    eis_identify_data = {
        "rct_ohm": 30,
        "rs_ohm": 5,
        "cdl_uF": 300
    }
    results.append(test_endpoint("POST", "/api/v2/identify/eis", eis_identify_data))
    
    # Test GCD identification
    gcd_identify_data = {
        "specific_capacitance_Fg": 250,
        "coulombic_efficiency_pct": 97,
        "plateau_voltage_V": 0.8
    }
    results.append(test_endpoint("POST", "/api/v2/identify/gcd", gcd_identify_data))
    
    # Test Raman identification
    raman_identify_data = {
        "peaks_cm": [1350, 1580, 2700]
    }
    results.append(test_endpoint("POST", "/api/v2/identify/raman", raman_identify_data))
    
    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"Results: {passed}/{total} endpoints working ({percentage:.1f}%)")
    
    if passed == total:
        print("✅ All endpoints working! Panels should load without crashing.")
    elif passed >= total * 0.8:
        print("⚠️  Most endpoints working. Some features may not work.")
    else:
        print("❌ Many endpoints failing. Check server logs.")
    
    print("=" * 70)
    
    # ── Recommendations ───────────────────────────────────────────────
    if passed < total:
        print("\n💡 Troubleshooting:")
        print("   1. Ensure backend server is running:")
        print("      python -m uvicorn src.backend.api.server:app --reload --port 8000")
        print("   2. Load materials database:")
        print("      curl -X POST http://localhost:8000/api/v2/material-id/database/load")
        print("   3. Train ML model:")
        print("      curl -X POST http://localhost:8000/api/v2/material-id/train")
        print("   4. Check server logs for errors")


if __name__ == "__main__":
    main()
