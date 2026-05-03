#!/usr/bin/env python3
"""
RĀMAN Studio — Comprehensive API Endpoint Test Suite
=====================================================
Tests every registered backend route for reachability,
correct status codes, and valid JSON responses.

Run:  python tests/test_api_endpoints.py
"""

import json
import sys
import time
import requests
from dataclasses import dataclass, field
from typing import Optional

BASE = "http://127.0.0.1:8000"

# ── colour helpers ──────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

@dataclass
class TestResult:
    name: str
    method: str
    url: str
    expected_status: int
    actual_status: Optional[int] = None
    passed: bool = False
    error: str = ""
    response_time_ms: float = 0
    response_body: str = ""


def run_test(name: str, method: str, path: str, expected: int = 200,
             json_body: dict = None, timeout: int = 10) -> TestResult:
    """Execute a single API test."""
    url = f"{BASE}{path}"
    result = TestResult(name=name, method=method.upper(), url=url, expected_status=expected)

    try:
        start = time.time()
        if method.upper() == "GET":
            resp = requests.get(url, timeout=timeout)
        elif method.upper() == "POST":
            resp = requests.post(url, json=json_body or {}, timeout=timeout)
        elif method.upper() == "DELETE":
            resp = requests.delete(url, timeout=timeout)
        else:
            resp = requests.request(method.upper(), url, json=json_body, timeout=timeout)
        
        elapsed = (time.time() - start) * 1000
        result.actual_status = resp.status_code
        result.response_time_ms = round(elapsed, 1)

        # Truncate body for display
        try:
            result.response_body = json.dumps(resp.json(), indent=2)[:300]
        except Exception:
            result.response_body = resp.text[:300]

        result.passed = resp.status_code == expected

    except requests.ConnectionError:
        result.error = "CONNECTION_REFUSED"
    except requests.Timeout:
        result.error = "TIMEOUT"
    except Exception as e:
        result.error = str(e)[:120]

    return result


# ═══════════════════════════════════════════════════════════════
# Test definitions — every registered route
# ═══════════════════════════════════════════════════════════════

TESTS = [
    # ── Core API (/api) ────────────────────────────────────────
    ("Health Check",            "GET",  "/api/health",              200),
    ("System Metrics",          "GET",  "/api/system/metrics",      200),
    ("List Materials",          "GET",  "/api/materials",           200),
    ("Full Materials DB",       "GET",  "/api/materials/full",      200),
    ("Synthesis Methods",       "GET",  "/api/synthesis-methods",   200),
    ("Datasets Index",          "GET",  "/api/datasets",            200),
    ("Perovskite Dataset",      "GET",  "/api/datasets/perovskite", 200),
    ("Pipeline Stats",          "GET",  "/api/pipeline/stats",      200),
    ("Perovskite Validation",   "GET",  "/api/validate/perovskite", 200),
    ("External Material Lookup","GET",  "/api/materials/external/TiO2", 200),

    # ── Core API — POST endpoints ──────────────────────────────
    ("EIS Predict",             "POST", "/api/predict", 200, {
        "material_id": "TiO2",
        "thickness_um": 100,
        "porosity": 0.3,
        "temperature_c": 25,
        "frequency_range": [0.01, 1000000],
        "num_points": 50
    }),
    ("EIS Simulate",            "POST", "/api/simulate", 200, {
        "R_el": 10, "R_ct": 100, "C_dl": 0.00001,
        "sigma": 50, "n": 0.9, "num_points": 50
    }),
    ("CV Simulate",             "POST", "/api/cv/simulate", 200, {
        "E_start": -0.5, "E_reverse": 0.5, "scan_rate": 0.05,
        "E0": 0.0, "k0": 0.01, "D": 1e-5, "C": 1e-3, "alpha": 0.5, "n_electrons": 1
    }),
    ("GCD Simulate",            "POST", "/api/gcd/simulate", 200, {
        "current_density": 1.0, "capacitance": 100.0,
        "esr": 0.5, "voltage_window": [0, 1]
    }),
    ("KK Validation",           "POST", "/api/validate/kk", 200, {
        "frequencies": [1, 10, 100, 1000, 10000],
        "z_real": [100, 80, 60, 40, 20],
        "z_imag": [-50, -40, -30, -20, -10]
    }),
    ("Pipeline Search",         "POST", "/api/pipeline/search", 200, {
        "query": "graphene supercapacitor",
        "limit": 5
    }),
    ("Cost Estimate",           "POST", "/api/cost/estimate", 200, {
        "materials": [{"name": "Graphene", "quantity_g": 1.0}],
        "technique": "screen_printing"
    }),
    ("Optimize",                "POST", "/api/optimize", 200, {
        "material_id": "TiO2",
        "target": "capacitance",
        "thickness_range": [10, 200],
        "porosity_range": [0.1, 0.8],
        "n_iterations": 5
    }),

    # ── Compliance (/api/compliance) ───────────────────────────
    ("Compliance Health",       "GET",  "/api/compliance/health",       200),
    ("Audit Logs",              "GET",  "/api/compliance/audit-logs",   200),
    ("Certification Status",    "GET",  "/api/compliance/certification", 200),
    ("Generate Report (custom)","POST", "/api/compliance/reports/generate", 200, {
        "resource_type": "custom",
        "resource_id": "test-001",
        "format": "pdf",
        "include_signatures": False,
        "custom_data": {
            "title": "Test Report",
            "type": "EIS",
            "authors": "Test User",
            "affiliation": "TestLab"
        }
    }),

    # ── Automation (/api/automation) ───────────────────────────
    ("Automation Health",       "GET",  "/api/automation/health",  200),
    ("List Jobs",               "GET",  "/api/automation/jobs",    200),
    ("List Webhooks",           "GET",  "/api/automation/webhooks", 200),

    # ── Auth (/api/auth) ──────────────────────────────────────
    # Auth routes typically need credentials; test what we can
    ("Auth — Register (no body)", "POST", "/api/auth/register", 422, {}),

    # ── Data (/api/data) ──────────────────────────────────────
    # Data routes may need file uploads; test listing
    
    # ── Quantum (/api/quantum) ────────────────────────────────
    ("Quantum Health",          "GET",  "/api/quantum/health",     200),

    # ── PE (Printed Electronics) ──────────────────────────────
    ("PE Health / Materials",   "GET",  "/api/pe/materials",       200),
]


def main():
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  RĀMAN Studio — API Endpoint Test Suite{RESET}")
    print(f"{BOLD}{CYAN}  Target: {BASE}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")

    # Pre-flight: check server is reachable
    try:
        requests.get(f"{BASE}/api/health", timeout=3)
    except requests.ConnectionError:
        print(f"{RED}✗ Server not reachable at {BASE}. Start the backend first.{RESET}")
        sys.exit(1)

    results: list[TestResult] = []

    for test_def in TESTS:
        name, method, path, expected = test_def[0], test_def[1], test_def[2], test_def[3]
        body = test_def[4] if len(test_def) > 4 else None

        result = run_test(name, method, path, expected, json_body=body)
        results.append(result)

        if result.passed:
            icon = f"{GREEN}✓{RESET}"
            status_str = f"{GREEN}{result.actual_status}{RESET}"
        elif result.error:
            icon = f"{RED}✗{RESET}"
            status_str = f"{RED}{result.error}{RESET}"
        else:
            icon = f"{RED}✗{RESET}"
            status_str = f"{RED}{result.actual_status} (expected {result.expected_status}){RESET}"

        time_str = f"{result.response_time_ms:>7.1f}ms" if result.response_time_ms else "    N/A"
        print(f"  {icon} {time_str}  {method:>4} {path:<45}  {status_str}  {name}")

    # ── Summary ────────────────────────────────────────────────
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)

    print(f"\n{BOLD}{'─' * 70}{RESET}")
    print(f"  {BOLD}Results: {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET}, {total} total")
    print(f"{BOLD}{'─' * 70}{RESET}\n")

    # Print failed test details
    if failed > 0:
        print(f"{BOLD}{RED}  FAILED TESTS:{RESET}\n")
        for r in results:
            if not r.passed:
                print(f"  {RED}✗ {r.name}{RESET}")
                print(f"    {r.method} {r.url}")
                if r.error:
                    print(f"    Error: {r.error}")
                else:
                    print(f"    Got: {r.actual_status}, Expected: {r.expected_status}")
                if r.response_body:
                    # Show first few lines of response
                    for line in r.response_body.split('\n')[:5]:
                        print(f"    {YELLOW}{line}{RESET}")
                print()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
