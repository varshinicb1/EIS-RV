#!/usr/bin/env python3
"""Edge case and error handling tests for RAMAN Studio backend."""
import requests, json, math, sys

base = 'http://127.0.0.1:8000'
results = []

def test(name, method, path, payload=None, expected_status=200):
    try:
        if method == 'GET':
            r = requests.get(f'{base}{path}', timeout=30)
        else:
            r = requests.post(f'{base}{path}', json=payload, timeout=30)
        ok = r.status_code == expected_status
        results.append((name, ok, r.status_code, expected_status))
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        results.append((name, False, str(e), expected_status))
        return None

print('=' * 60)
print('EDGE CASE & ERROR HANDLING TESTS')
print('=' * 60)

# 1. EIS: very few points
test('eis_min_points', 'POST', '/api/v2/eis',
    {'model': 'randles', 'freq_min': 0.1, 'freq_max': 100, 'n_points': 10, 'bounded_warburg': False})

# 2. EIS: very high frequency range
test('eis_high_freq', 'POST', '/api/v2/eis',
    {'model': 'randles', 'freq_min': 1, 'freq_max': 1e7, 'n_points': 200, 'bounded_warburg': False})

# 3. CV: very fast scan rate
test('cv_fast_scan', 'POST', '/api/v2/cv',
    {'E0_V': -0.5, 'E1_V': 0.5, 'scan_rate_V_s': 10.0, 'n_points': 500})

# 4. CV: very slow scan rate
test('cv_slow_scan', 'POST', '/api/v2/cv',
    {'E0_V': -0.2, 'E1_V': 0.2, 'scan_rate_V_s': 0.001, 'n_points': 500})

# 5. DRT: single data point (should fail gracefully)
test('drt_single_point', 'POST', '/api/v2/drt/analyze',
    {'frequencies': [1], 'Z_real': [100], 'Z_imag': [-50],
     'lambda': 1e-3, 'n_tau': 50, 'method': 'tikhonov'}, expected_status=500)

# 6. Circuit fit: with CPE model
test('fit_cpe', 'POST', '/api/v2/circuit/fit', {
    'frequencies': [0.1, 1, 10, 100, 1000],
    'Z_real': [100, 90, 80, 70, 60],
    'Z_imag': [-50, -40, -30, -20, -10],
    'circuit_model': 'randles_cpe', 'method': 'lm'
})

# 7. Battery: invalid material (should fallback gracefully)
test('battery_invalid_material', 'POST', '/api/v2/battery',
    {'material': 'UnknownMaterial', 'SOC_start': 0.2, 'SOC_end': 0.8,
     'current_C': 0.5, 'n_cycles': 1, 'temperature': 25})

# 8. GCD: very high current
test('gcd_high_current', 'POST', '/api/v2/gcd',
    {'material': 'MnO2', 'voltage_max_V': 0.8, 'voltage_min_V': 0.1,
     'current_A': 10.0, 'n_cycles': 1, 'active_mass_mg': 1.0})

# 9. Biosensor: invalid pattern (should fail gracefully)
test('biosensor_invalid_pattern', 'POST', '/api/v2/biosensor/simulate',
    {'electrode_pattern': 'nonexistent', 'ink_formulation': 'AuNPs-PEDOT',
     'coating_method': 'spin', 'n_cycles': 3, 'target_analyte': 'glucose'},
    expected_status=500)

# 10. Cache invalidate
test('cache_invalidate', 'POST', '/api/v2/cache/invalidate')

# 11. EIS: RC model
test('eis_rc', 'POST', '/api/v2/eis',
    {'model': 'rc', 'freq_min': 0.1, 'freq_max': 1e5, 'n_points': 100, 'bounded_warburg': False})

# 12. EIS: Warburg only
test('eis_warburg', 'POST', '/api/v2/eis',
    {'model': 'warburg', 'freq_min': 0.1, 'freq_max': 1e5, 'n_points': 100, 'bounded_warburg': False})

# 13. CV: symmetric around zero
cv_sym = test('cv_symmetric', 'POST', '/api/v2/cv',
    {'E0_V': -0.3, 'E1_V': 0.3, 'scan_rate_V_s': 0.05, 'n_points': 1000})

# 14. DRT: ridge method
test('drt_ridge', 'POST', '/api/v2/drt/analyze', {
    'frequencies': [0.1, 1, 10, 100, 1000, 10000],
    'Z_real': [100, 95, 85, 75, 65, 55],
    'Z_imag': [-50, -45, -35, -25, -15, -5],
    'lambda': 1e-2, 'n_tau': 60, 'method': 'ridge'
})

# 15. Circuit fit: differential evolution method
test('fit_de', 'POST', '/api/v2/circuit/fit', {
    'frequencies': [0.1, 1, 10, 100, 1000],
    'Z_real': [100, 90, 80, 70, 60],
    'Z_imag': [-50, -40, -30, -20, -10],
    'circuit_model': 'rc', 'method': 'de'
})

# Print results
for name, ok, got, expected in results:
    status = 'PASS' if ok else 'FAIL'
    print(f'  [{status}] {name:30s} (got {got}, expected {expected})')

# Math checks on edge cases
print()
print('=== EDGE CASE MATH CHECKS ===')
if cv_sym:
    peaks = cv_sym['peaks']
    # For symmetric scan, peaks should be roughly symmetric around 0
    i_pa = peaks['i_pa']
    i_pc = peaks['i_pc']
    print(f'CV symmetric: i_pa={i_pa:.6f}, i_pc={i_pc:.6f}')
    print(f'  -> Peak currents roughly equal magnitude: {abs(abs(i_pa) - abs(i_pc)) < abs(i_pa)*0.5}')

passed = sum(1 for _, ok, _, _ in results if ok)
print()
print(f'Edge cases: {passed}/{len(results)} passed')
sys.exit(0 if passed == len(results) else 1)
