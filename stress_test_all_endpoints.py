#!/usr/bin/env python3
"""
Comprehensive Stress Test for All Frontend-Backend Pairs
=========================================================
Tests every API endpoint with:
- Valid inputs
- Edge cases
- Invalid inputs
- Load testing
- Concurrent requests
- Error handling

Run this after starting the backend server:
    python -m uvicorn src.backend.api.server:app --reload --port 8000
    python stress_test_all_endpoints.py
"""

import requests
import json
import time
import concurrent.futures
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import statistics

API_BASE = "http://localhost:8000"

@dataclass
class TestResult:
    endpoint: str
    test_name: str
    passed: bool
    response_time_ms: float
    status_code: int
    error_message: str = ""

class StressTestRunner:
    def __init__(self):
        self.results: List[TestResult] = []
        self.total_tests = 0
        self.passed_tests = 0
        
    def test_endpoint(
        self, 
        method: str, 
        endpoint: str, 
        data: Dict[str, Any] = None,
        test_name: str = "",
        expected_status: int = 200,
        should_fail: bool = False
    ) -> TestResult:
        """Test a single endpoint and record results."""
        url = f"{API_BASE}{endpoint}"
        
        start_time = time.time()
        try:
            if method == "GET":
                response = requests.get(url, timeout=30)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Check if test passed
            if should_fail:
                passed = response.status_code >= 400
            else:
                passed = response.status_code == expected_status
            
            result = TestResult(
                endpoint=endpoint,
                test_name=test_name,
                passed=passed,
                response_time_ms=response_time,
                status_code=response.status_code,
                error_message="" if passed else f"Expected {expected_status}, got {response.status_code}"
            )
            
        except requests.exceptions.Timeout:
            result = TestResult(
                endpoint=endpoint,
                test_name=test_name,
                passed=False,
                response_time_ms=30000,
                status_code=0,
                error_message="Request timeout (30s)"
            )
        except requests.exceptions.ConnectionError:
            result = TestResult(
                endpoint=endpoint,
                test_name=test_name,
                passed=False,
                response_time_ms=0,
                status_code=0,
                error_message="Connection failed (is server running?)"
            )
        except Exception as e:
            result = TestResult(
                endpoint=endpoint,
                test_name=test_name,
                passed=False,
                response_time_ms=0,
                status_code=0,
                error_message=str(e)
            )
        
        self.results.append(result)
        self.total_tests += 1
        if result.passed:
            self.passed_tests += 1
        
        return result
    
    def print_result(self, result: TestResult):
        """Print a single test result."""
        status = "✅" if result.passed else "❌"
        print(f"{status} {result.test_name}")
        print(f"   Endpoint: {result.endpoint}")
        print(f"   Status: {result.status_code} | Time: {result.response_time_ms:.0f}ms")
        if not result.passed:
            print(f"   Error: {result.error_message}")
        print()
    
    def load_test(self, method: str, endpoint: str, data: Dict[str, Any], n_requests: int = 10):
        """Load test an endpoint with concurrent requests."""
        print(f"🔥 Load Testing: {endpoint} ({n_requests} concurrent requests)")
        
        def make_request():
            start = time.time()
            try:
                if method == "GET":
                    response = requests.get(f"{API_BASE}{endpoint}", timeout=30)
                else:
                    response = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=30)
                return (time.time() - start) * 1000, response.status_code
            except Exception as e:
                return 0, 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(n_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        times = [r[0] for r in results if r[0] > 0]
        success_count = sum(1 for r in results if r[1] == 200)
        
        if times:
            print(f"   Success: {success_count}/{n_requests}")
            print(f"   Avg: {statistics.mean(times):.0f}ms | "
                  f"Min: {min(times):.0f}ms | "
                  f"Max: {max(times):.0f}ms | "
                  f"Median: {statistics.median(times):.0f}ms")
        else:
            print(f"   ❌ All requests failed")
        print()


def main():
    runner = StressTestRunner()
    
    print("=" * 80)
    print("COMPREHENSIVE STRESS TEST - ALL FRONTEND-BACKEND PAIRS")
    print("=" * 80)
    print()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 1: MATERIAL IDENTIFICATION ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("┌─ PHASE 1: MATERIAL IDENTIFICATION ─────────────────────────────────┐")
    print("│ Testing ML-based material identification from lab data             │")
    print("└─────────────────────────────────────────────────────────────────────┘")
    print()
    
    # Test 1.1: System Status
    result = runner.test_endpoint(
        "GET", "/api/v2/material-id/status",
        test_name="1.1 Get system status"
    )
    runner.print_result(result)
    
    # Test 1.2: List Materials
    result = runner.test_endpoint(
        "GET", "/api/v2/material-id/materials",
        test_name="1.2 List materials database"
    )
    runner.print_result(result)
    
    # Test 1.3: EIS Identification - Valid Data
    eis_valid = {
        "frequencies": [0.01, 0.1, 1, 10, 100, 1000, 10000, 100000],
        "Z_real": [10, 12, 18, 28, 35, 38, 40, 41],
        "Z_imag": [0, -2, -8, -18, -15, -8, -3, -1],
        "top_k": 3
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/material-id/identify/eis",
        data=eis_valid,
        test_name="1.3 EIS identification - valid data"
    )
    runner.print_result(result)
    
    # Test 1.4: EIS Identification - Edge Case (minimal data)
    eis_minimal = {
        "frequencies": [1, 10, 100],
        "Z_real": [10, 20, 30],
        "Z_imag": [0, -5, -2],
        "top_k": 1
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/material-id/identify/eis",
        data=eis_minimal,
        test_name="1.4 EIS identification - minimal data (3 points)"
    )
    runner.print_result(result)
    
    # Test 1.5: EIS Identification - Invalid (mismatched arrays)
    eis_invalid = {
        "frequencies": [1, 10, 100],
        "Z_real": [10, 20],  # Wrong length
        "Z_imag": [0, -5, -2],
        "top_k": 3
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/material-id/identify/eis",
        data=eis_invalid,
        test_name="1.5 EIS identification - invalid (mismatched arrays)",
        should_fail=True
    )
    runner.print_result(result)
    
    # Test 1.6: CV Identification - Valid Data
    cv_valid = {
        "potential": [-0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.4, 0.3, 0.2, 0.1, 0, -0.1, -0.2, -0.3],
        "current": [0, 0.05, 0.15, 0.3, 0.5, 0.7, 0.8, 0.75, 0.6, 0.5, 0.4, 0.3, 0.2, 0.15, 0.1, 0.05, 0],
        "top_k": 3
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/material-id/identify/cv",
        data=cv_valid,
        test_name="1.6 CV identification - valid data"
    )
    runner.print_result(result)
    
    # Test 1.7: CV Identification - Edge Case (large dataset)
    cv_large = {
        "potential": [i * 0.01 - 0.5 for i in range(1000)],
        "current": [abs((i * 0.01 - 0.5) ** 2) for i in range(1000)],
        "top_k": 5
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/material-id/identify/cv",
        data=cv_large,
        test_name="1.7 CV identification - large dataset (1000 points)"
    )
    runner.print_result(result)
    
    # Test 1.8: Raman Identification - Valid Data
    raman_valid = {
        "wavenumber": [500, 800, 1000, 1200, 1350, 1580, 2000, 2700, 3000],
        "intensity": [100, 150, 200, 300, 500, 800, 400, 600, 200],
        "top_k": 3
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/material-id/identify/raman",
        data=raman_valid,
        test_name="1.8 Raman identification - valid data"
    )
    runner.print_result(result)
    
    # Test 1.9: Raman Identification - Edge Case (noisy data)
    raman_noisy = {
        "wavenumber": [i * 10 for i in range(400)],
        "intensity": [100 + (i % 50) * 10 for i in range(400)],
        "top_k": 3
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/material-id/identify/raman",
        data=raman_noisy,
        test_name="1.9 Raman identification - noisy data (400 points)"
    )
    runner.print_result(result)
    
    # Load Test 1.10: EIS Identification
    runner.load_test(
        "POST", "/api/v2/material-id/identify/eis",
        data=eis_valid,
        n_requests=20
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 2: MATERIAL DISCOVERY ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("┌─ PHASE 2: MATERIAL DISCOVERY (NVIDIA NIM) ─────────────────────────┐")
    print("│ Testing AI-powered material discovery and synthesis                │")
    print("└─────────────────────────────────────────────────────────────────────┘")
    print()
    
    # Test 2.1: Material Discovery - Valid
    discovery_valid = {
        "application": "Pb2+ detection biosensor",
        "max_candidates": 5
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/materials/discover",
        data=discovery_valid,
        test_name="2.1 Material discovery - Pb2+ biosensor"
    )
    runner.print_result(result)
    
    # Test 2.2: Material Discovery - Different Application
    discovery_supercap = {
        "application": "high-performance supercapacitor electrode",
        "max_candidates": 3
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/materials/discover",
        data=discovery_supercap,
        test_name="2.2 Material discovery - supercapacitor"
    )
    runner.print_result(result)
    
    # Test 2.3: Material Discovery - Edge Case (max candidates)
    discovery_max = {
        "application": "battery anode material",
        "max_candidates": 10
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/materials/discover",
        data=discovery_max,
        test_name="2.3 Material discovery - max candidates (10)"
    )
    runner.print_result(result)
    
    # Test 2.4: Synthesis Routes - Valid
    synthesis_valid = {
        "material_name": "MoS2",
        "material_formula": "MoS2",
        "target_form": "nanosheets"
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/materials/synthesis",
        data=synthesis_valid,
        test_name="2.4 Synthesis routes - MoS2 nanosheets"
    )
    runner.print_result(result)
    
    # Test 2.5: Synthesis Routes - Different Forms
    for form in ["nanoparticles", "thin_film", "nanowires", "nanofibers"]:
        synthesis_form = {
            "material_name": "RuO2",
            "material_formula": "RuO2",
            "target_form": form
        }
        result = runner.test_endpoint(
            "POST", "/api/v2/materials/synthesis",
            data=synthesis_form,
            test_name=f"2.5 Synthesis routes - RuO2 {form}"
        )
        runner.print_result(result)
    
    # Test 2.6: Biosensor Suggestions - Valid
    biosensor_valid = {
        "analyte": "Pb2+",
        "technique": "DPV",
        "electrode_substrate": "screen-printed carbon",
        "max_suggestions": 3
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/biosensor/suggest",
        data=biosensor_valid,
        test_name="2.6 Biosensor suggestions - Pb2+ DPV"
    )
    runner.print_result(result)
    
    # Test 2.7: Biosensor Suggestions - Different Analytes
    for analyte in ["glucose", "dopamine", "H2O2", "uric acid"]:
        biosensor_analyte = {
            "analyte": analyte,
            "technique": "CV",
            "electrode_substrate": "GCE",
            "max_suggestions": 2
        }
        result = runner.test_endpoint(
            "POST", "/api/v2/biosensor/suggest",
            data=biosensor_analyte,
            test_name=f"2.7 Biosensor suggestions - {analyte}"
        )
        runner.print_result(result)
    
    # Test 2.8: Supported Analytes
    result = runner.test_endpoint(
        "GET", "/api/v2/biosensor/supported-analytes",
        test_name="2.8 Get supported analytes list"
    )
    runner.print_result(result)
    
    # Load Test 2.9: Material Discovery
    runner.load_test(
        "POST", "/api/v2/materials/discover",
        data=discovery_valid,
        n_requests=15
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3: CROSS-MODAL IDENTIFICATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("┌─ PHASE 3: CROSS-MODAL IDENTIFICATION ──────────────────────────────┐")
    print("│ Testing material identification from extracted features            │")
    print("└─────────────────────────────────────────────────────────────────────┘")
    print()
    
    # Test 3.1: CV Feature Identification
    cv_features = {
        "peak_separation_mV": 65,
        "ipa_ipc_ratio": 0.99,
        "onset_potential_V": 0.1
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/identify/cv",
        data=cv_features,
        test_name="3.1 CV feature identification - reversible"
    )
    runner.print_result(result)
    
    # Test 3.2: CV Feature Identification - Irreversible
    cv_irreversible = {
        "peak_separation_mV": 200,
        "ipa_ipc_ratio": 0.5,
        "onset_potential_V": 0.3
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/identify/cv",
        data=cv_irreversible,
        test_name="3.2 CV feature identification - irreversible"
    )
    runner.print_result(result)
    
    # Test 3.3: EIS Feature Identification
    eis_features = {
        "rct_ohm": 30,
        "rs_ohm": 5,
        "cdl_uF": 300
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/identify/eis",
        data=eis_features,
        test_name="3.3 EIS feature identification - low resistance"
    )
    runner.print_result(result)
    
    # Test 3.4: EIS Feature Identification - High Resistance
    eis_high_r = {
        "rct_ohm": 1000,
        "rs_ohm": 50,
        "cdl_uF": 50
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/identify/eis",
        data=eis_high_r,
        test_name="3.4 EIS feature identification - high resistance"
    )
    runner.print_result(result)
    
    # Test 3.5: GCD Feature Identification
    gcd_features = {
        "specific_capacitance_Fg": 250,
        "coulombic_efficiency_pct": 97,
        "plateau_voltage_V": 0.8
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/identify/gcd",
        data=gcd_features,
        test_name="3.5 GCD feature identification - high capacitance"
    )
    runner.print_result(result)
    
    # Test 3.6: GCD Feature Identification - Low Capacitance
    gcd_low = {
        "specific_capacitance_Fg": 50,
        "coulombic_efficiency_pct": 85,
        "plateau_voltage_V": 0.5
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/identify/gcd",
        data=gcd_low,
        test_name="3.6 GCD feature identification - low capacitance"
    )
    runner.print_result(result)
    
    # Test 3.7: Raman Peak Identification - Graphene
    raman_graphene = {
        "peaks_cm": [1350, 1580, 2700]
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/identify/raman",
        data=raman_graphene,
        test_name="3.7 Raman peak identification - graphene signature"
    )
    runner.print_result(result)
    
    # Test 3.8: Raman Peak Identification - MoS2
    raman_mos2 = {
        "peaks_cm": [383, 408]
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/identify/raman",
        data=raman_mos2,
        test_name="3.8 Raman peak identification - MoS2 signature"
    )
    runner.print_result(result)
    
    # Load Test 3.9: Cross-Modal Identification
    runner.load_test(
        "POST", "/api/v2/identify/cv",
        data=cv_features,
        n_requests=25
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 4: AUTONOMOUS OPTIMIZATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("┌─ PHASE 4: AUTONOMOUS OPTIMIZATION ─────────────────────────────────┐")
    print("│ Testing Bayesian optimization campaigns                            │")
    print("└─────────────────────────────────────────────────────────────────────┘")
    print()
    
    # Test 4.1: Optimizer Status
    result = runner.test_endpoint(
        "GET", "/api/v2/optimize/status",
        test_name="4.1 Get optimizer status"
    )
    runner.print_result(result)
    
    # Test 4.2: List Campaigns
    result = runner.test_endpoint(
        "GET", "/api/v2/optimize/campaigns",
        test_name="4.2 List optimization campaigns"
    )
    runner.print_result(result)
    
    # Test 4.3: Start Campaign - Capacitance Optimization
    campaign_capacitance = {
        "target_metric": "capacitance",
        "objective": "maximize",
        "max_iterations": 10,
        "convergence_threshold": 0.05,
        "simulation_type": "eis"
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/optimize/start",
        data=campaign_capacitance,
        test_name="4.3 Start campaign - maximize capacitance"
    )
    runner.print_result(result)
    
    # Test 4.4: Start Campaign - Conductivity Optimization
    campaign_conductivity = {
        "target_metric": "conductivity",
        "objective": "maximize",
        "max_iterations": 15,
        "convergence_threshold": 0.01,
        "simulation_type": "eis"
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/optimize/start",
        data=campaign_conductivity,
        test_name="4.4 Start campaign - maximize conductivity"
    )
    runner.print_result(result)
    
    # Test 4.5: Start Campaign - Invalid (missing database)
    # This should work now since we loaded the database
    campaign_invalid = {
        "target_metric": "energy_density",
        "objective": "maximize",
        "max_iterations": 20,
        "simulation_type": "gcd"
    }
    result = runner.test_endpoint(
        "POST", "/api/v2/optimize/start",
        data=campaign_invalid,
        test_name="4.5 Start campaign - energy density (GCD)"
    )
    runner.print_result(result)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("=" * 80)
    print("STRESS TEST SUMMARY")
    print("=" * 80)
    print()
    
    # Overall statistics
    pass_rate = (runner.passed_tests / runner.total_tests * 100) if runner.total_tests > 0 else 0
    print(f"Total Tests: {runner.total_tests}")
    print(f"Passed: {runner.passed_tests} ({pass_rate:.1f}%)")
    print(f"Failed: {runner.total_tests - runner.passed_tests}")
    print()
    
    # Response time statistics
    response_times = [r.response_time_ms for r in runner.results if r.passed and r.response_time_ms > 0]
    if response_times:
        print("Response Time Statistics:")
        print(f"  Average: {statistics.mean(response_times):.0f}ms")
        print(f"  Median:  {statistics.median(response_times):.0f}ms")
        print(f"  Min:     {min(response_times):.0f}ms")
        print(f"  Max:     {max(response_times):.0f}ms")
        print()
    
    # Failed tests
    failed_tests = [r for r in runner.results if not r.passed]
    if failed_tests:
        print("Failed Tests:")
        for r in failed_tests:
            print(f"  ❌ {r.test_name}")
            print(f"     {r.endpoint} - {r.error_message}")
        print()
    
    # Performance warnings
    slow_tests = [r for r in runner.results if r.passed and r.response_time_ms > 5000]
    if slow_tests:
        print("⚠️  Slow Tests (>5s):")
        for r in slow_tests:
            print(f"  {r.test_name}: {r.response_time_ms:.0f}ms")
        print()
    
    # Final verdict
    print("=" * 80)
    if pass_rate == 100:
        print("✅ ALL TESTS PASSED - System is production ready!")
    elif pass_rate >= 90:
        print("⚠️  MOSTLY PASSING - Some issues need attention")
    elif pass_rate >= 70:
        print("⚠️  PARTIAL SUCCESS - Multiple issues found")
    else:
        print("❌ MANY FAILURES - System needs debugging")
    print("=" * 80)


if __name__ == "__main__":
    main()
