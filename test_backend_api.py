#!/usr/bin/env python3
"""Comprehensive backend API test for RAMAN Studio."""
import requests, json, math, sys

base = 'http://127.0.0.1:8000'
results = []

def test(name, method, path, payload=None):
    try:
        if method == 'GET':
            r = requests.get(f'{base}{path}', timeout=30)
        else:
            r = requests.post(f'{base}{path}', json=payload, timeout=30)
        ok = r.status_code == 200
        results.append((name, ok, r.status_code))
        return r.json() if ok else None
    except Exception as e:
        results.append((name, False, str(e)))
        return None

# 1. Health
test('health', 'GET', '/health')

# 2. Engine info
test('engine_info', 'GET', '/api/v2/engine-info')

# 3. EIS with Randles
eis = test('eis_randles', 'POST', '/api/v2/eis',
    {'model': 'randles', 'freq_min': 0.01, 'freq_max': 1e5, 'n_points': 100, 'bounded_warburg': False})

# 4. EIS with bounded Warburg
eis_b = test('eis_bounded', 'POST', '/api/v2/eis',
    {'model': 'randles', 'freq_min': 0.01, 'freq_max': 1e5, 'n_points': 100, 'bounded_warburg': True})

# 5. CV
cv = test('cv', 'POST', '/api/v2/cv',
    {'E0_V': 0.0, 'E1_V': 0.8, 'scan_rate_V_s': 0.05, 'n_points': 1000})

# 6. DRT
drt = test('drt', 'POST', '/api/v2/drt/analyze', {
    'frequencies': [0.1, 1, 10, 100, 1000],
    'Z_real': [100, 90, 80, 70, 60],
    'Z_imag': [-50, -40, -30, -20, -10],
    'lambda': 1e-3, 'n_tau': 50, 'method': 'tikhonov'
})

# 7. Circuit fit
fit = test('circuit_fit', 'POST', '/api/v2/circuit/fit', {
    'frequencies': [0.1, 1, 10, 100, 1000],
    'Z_real': [100, 90, 80, 70, 60],
    'Z_imag': [-50, -40, -30, -20, -10],
    'circuit_model': 'randles', 'method': 'lm'
})

# 8. Battery
bat = test('battery', 'POST', '/api/v2/battery', {
    'material': 'LiCoO2', 'SOC_start': 0.2, 'SOC_end': 0.8,
    'current_C': 0.5, 'n_cycles': 2, 'temperature': 25
})

# 9. GCD
gcd = test('gcd', 'POST', '/api/v2/gcd', {
    'material': 'MnO2', 'voltage_max_V': 0.8, 'voltage_min_V': 0.1,
    'current_A': 0.001, 'n_cycles': 2, 'active_mass_mg': 1.0
})

# 10. Biosensor
bio = test('biosensor', 'POST', '/api/v2/biosensor/simulate', {
    'electrode_pattern': 'interdigitated', 'ink_formulation': 'AuNPs-PEDOT',
    'coating_method': 'spin', 'n_cycles': 3, 'target_analyte': 'glucose',
    'pH': 7.4, 'temperature': 298.15
})

# 11. Cache stats
test('cache_stats', 'GET', '/api/v2/cache/stats')

# 12. License info
test('license', 'GET', '/api/v2/auth/license')

# 13. Biosensor library
test('biosensor_library', 'GET', '/api/v2/biosensor/library')

# 14. Digital twin
bio_opt = test('biosensor_optimize', 'POST', '/api/v2/biosensor/optimize', {
    'target_analyte': 'glucose', 'optimization_goal': 'sensitivity',
    'constraints': {'max_cost_usd': 100}
})

# Print endpoint results
print('=' * 60)
print('API ENDPOINT TESTS')
print('=' * 60)
for name, ok, detail in results:
    status = 'PASS' if ok else 'FAIL'
    print(f'  [{status}] {name:30s} ({detail})')

# Math/science checks
print()
print('=' * 60)
print('MATHEMATICAL & SCIENTIFIC CORRECTNESS CHECKS')
print('=' * 60)
math_pass = 0
math_total = 0

def check(desc, condition, expected):
    global math_pass, math_total
    math_total += 1
    if condition == expected:
        math_pass += 1
        print(f'  [PASS] {desc}')
    else:
        print(f'  [FAIL] {desc} (got {condition}, expected {expected})')

# EIS checks
if eis:
    z0 = math.sqrt(eis['Z_real'][0]**2 + eis['Z_imag'][0]**2)
    z_last = math.sqrt(eis['Z_real'][-1]**2 + eis['Z_imag'][-1]**2)
    check('EIS: |Z| decreases with frequency (low > high)', z0 > z_last, True)
    check('EIS: all Z_imag negative (capacitive)', all(z < 0 for z in eis['Z_imag']), True)
    check('EIS: uses Rust engine', eis.get('engine') == 'rust', True)
    # Bounded Warburg should have different low-freq behavior
    if eis_b:
        z0_b = math.sqrt(eis_b['Z_real'][0]**2 + eis_b['Z_imag'][0]**2)
        check('EIS: bounded Warburg differs from semi-infinite', abs(z0 - z0_b) > 1, True)

# CV checks
if cv:
    peaks = cv['peaks']
    check('CV: anodic peak > 0', peaks['i_pa'] > 0, True)
    check('CV: cathodic peak < 0', peaks['i_pc'] < 0, True)
    dEp = peaks['dEp']
    check('CV: peak separation in range 0.02-0.15V', 0.02 < dEp < 0.15, True)
    check('CV: uses Rust engine', cv.get('engine') == 'rust', True)

# DRT checks
if drt:
    check('DRT: all gamma >= 0', all(g >= 0 for g in drt['gamma']), True)
    check('DRT: success flag', drt.get('success'), True)
    check('DRT: positive chi_squared', drt.get('chi_squared', 0) > 0, True)

# Circuit fit checks
if fit:
    params = fit['parameters']
    check('Fit: all parameters positive', all(v > 0 for v in params.values()), True)
    check('Fit: success flag', fit.get('success'), True)
    check('Fit: positive chi_squared', fit.get('chi_squared', 0) > 0, True)

# Battery checks
if bat:
    util = bat['metrics']['utilization']
    check('Battery: utilization <= 100%', util <= 100, True)
    check('Battery: utilization > 0%', util > 0, True)
    check('Battery: delivered <= theoretical',
          bat['metrics']['delivered_mAh'] <= bat['metrics']['theoretical_mAh'], True)

# GCD checks
if gcd:
    cs = gcd['summary']['Cs_F_g']
    check('GCD: Cs > 0', cs > 0, True)
    check('GCD: ESR > 0', gcd['summary']['ESR'] > 0, True)

# Biosensor checks
if bio:
    perf = bio['performance']
    check('Biosensor: sensitivity > 0', perf['sensitivity_uA_mM_cm2'] > 0, True)
    check('Biosensor: LOD > 0', perf['lod_M'] > 0, True)
    check('Biosensor: response_time > 0', perf['response_time_s'] > 0, True)

print()
print('=' * 60)
print('SUMMARY')
print('=' * 60)
ep_pass = sum(1 for _, ok, _ in results if ok)
print(f'API Endpoints: {ep_pass}/{len(results)} passed')
print(f'Math/Science:  {math_pass}/{math_total} passed')
all_ok = ep_pass == len(results) and math_pass == math_total
print(f'Overall:       {"ALL PASS" if all_ok else "SOME FAILURES"}')
sys.exit(0 if all_ok else 1)
