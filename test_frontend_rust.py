"""
FRONTEND VERIFICATION WITH RUST ENGINE
=========================================
Tests that backend endpoints return correct data when using the Rust engine.

Usage:
    python test_frontend_rust.py
"""

import sys
import time
sys.path.insert(0, r'C:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV')

from src.backend.core.native_bridge import eis_simulate, cv_simulate, get_engine_info

def test_engine_info():
    print("--- Test 1: Engine Info ---")
    info = get_engine_info()
    assert info['rust_available'] == True, "Rust engine should be available"
    assert info['rust_version'] is not None, "Rust version should be present"
    print(f"  Rust engine v{info['rust_version']} available: OK")
    return True

def test_eis_endpoint_format():
    print("\n--- Test 2: EIS Response Format ---")
    res = eis_simulate(Rs=10, Rct=100, Cdl=1e-5, sigma_w=50, n_points=100)
    assert res['engine'] == 'rust', f"Expected engine='rust', got {res['engine']}"
    assert 'frequencies' in res
    assert 'Z_real' in res
    assert 'Z_imag' in res
    assert 'Z_magnitude' in res
    assert 'Z_phase' in res
    assert len(res['frequencies']) == 100
    assert len(res['Z_real']) == 100
    # Sanity check: at high frequency, real part approaches Rs
    assert res['Z_real'][-1] < 20.0, "High-freq Z_real should approach Rs"
    print(f"  Engine: {res['engine']}")
    print(f"  Points: {len(res['frequencies'])}")
    print(f"  Compute time: {res['compute_time_s']*1000:.2f} ms")
    print("  EIS response format: OK")
    return True

def test_cv_endpoint_format():
    print("\n--- Test 3: CV Response Format ---")
    res = cv_simulate(area_cm2=0.0707, E_formal_V=0.23, scan_rate_V_s=0.05, n_points=500)
    assert res['engine'] == 'rust', f"Expected engine='rust', got {res['engine']}"
    assert 'E' in res
    assert 'i_total' in res
    assert 'i_faradaic' in res
    assert 'i_capacitive' in res
    assert 'peaks' in res
    assert len(res['E']) == 1000
    assert res['peaks']['i_pa'] > 0.0
    assert res['peaks']['i_pc'] < 0.0
    print(f"  Engine: {res['engine']}")
    print(f"  Points: {len(res['E'])}")
    print(f"  i_pa: {res['peaks']['i_pa']:.6f}")
    print(f"  i_pc: {res['peaks']['i_pc']:.6f}")
    print("  CV response format: OK")
    return True

def test_drt_via_native_bridge():
    print("\n--- Test 4: DRT via Rust Direct ---")
    import raman_core_rs
    import numpy as np
    freqs = np.logspace(-2, 6, 80)
    zr = np.ones(80) * 110
    zi = -np.ones(80) * 50
    p = raman_core_rs.PyDRTParams()
    res = raman_core_rs.compute_drt_py(freqs, zr, zi, p)
    assert len(res.tau) == 200
    assert len(res.gamma) == 200
    assert res.R_inf > 0.0
    print(f"  tau points: {len(res.tau)}")
    print(f"  gamma max: {np.max(res.gamma):.2f}")
    print(f"  R_inf: {res.R_inf:.2f}")
    print("  DRT computation: OK")
    return True

def test_circuit_fit_via_rust():
    print("\n--- Test 5: Circuit Fit via Rust ---")
    import raman_core_rs
    import numpy as np
    freqs = np.logspace(-2, 6, 80)
    zr = np.ones(80) * 110
    zi = -np.ones(80) * 50
    fp = raman_core_rs.PyFitParams()
    init = np.array([10.0, 100.0, 1e-5, 0.9, 50.0])
    res = raman_core_rs.fit_circuit_py(freqs, zr, zi, init, fp)
    assert res.converged == True or res.iterations > 0
    assert len(res.params) == 5
    assert len(res.Z_fit_real) == 80
    print(f"  Converged: {res.converged}")
    print(f"  Iterations: {res.iterations}")
    print(f"  Chi2: {res.chi_squared:.2f}")
    print("  Circuit fit: OK")
    return True

def test_kramers_kronig():
    print("\n--- Test 6: Kramers-Kronig Test ---")
    import raman_core_rs
    import numpy as np
    freqs = np.logspace(-2, 6, 80)
    zr = np.ones(80) * 110
    zi = -np.ones(80) * 50
    res = raman_core_rs.kramers_kronig_test_py(freqs, zr, zi, 0)
    assert res.mu >= 0.0
    print(f"  mu statistic: {res.mu:.6f}")
    print(f"  is_valid: {res.is_valid}")
    print("  KK test: OK")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("FRONTEND VERIFICATION WITH RUST ENGINE")
    print("=" * 60)

    tests = [
        ("Engine Info", test_engine_info),
        ("EIS Endpoint", test_eis_endpoint_format),
        ("CV Endpoint", test_cv_endpoint_format),
        ("DRT Computation", test_drt_via_native_bridge),
        ("Circuit Fit", test_circuit_fit_via_rust),
        ("Kramers-Kronig", test_kramers_kronig),
    ]

    results = []
    for name, test_fn in tests:
        try:
            test_fn()
            results.append((name, "PASS"))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append((name, "FAIL"))

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for name, status in results:
        print(f"  {name:.<40} {status}")

    passed = sum(1 for _, s in results if s == "PASS")
    total = len(results)
    print(f"\n  Total: {passed}/{total} passed")
    print("=" * 60)

    if passed == total:
        print("ALL FRONTEND VERIFICATION TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)
