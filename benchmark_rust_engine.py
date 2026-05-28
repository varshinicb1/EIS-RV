"""
RUST ENGINE PERFORMANCE BENCHMARK
====================================
Compares Rust engine performance against Python fallback implementations.

Usage:
    python benchmark_rust_engine.py
"""

import time
import sys
import numpy as np

sys.path.insert(0, r'C:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV')

from src.backend.core.native_bridge import eis_simulate, cv_simulate, get_engine_info

info = get_engine_info()
print("=" * 60)
print("RUST ENGINE PERFORMANCE BENCHMARK")
print("=" * 60)
print(f"Engine: raman_core_rs v{info.get('rust_version', 'N/A')}")
print(f"Python fallback available: {info.get('python_fallback', False)}")
print()

N_RUNS = 5

def benchmark_eis():
    print("--- EIS Simulation Benchmark ---")
    times_rust = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        res = eis_simulate(Rs=10, Rct=100, Cdl=1e-5, sigma_w=50, n_points=1000)
        t1 = time.perf_counter()
        times_rust.append(t1 - t0)
    avg_rust = sum(times_rust) / len(times_rust)
    print(f"  Rust (avg {N_RUNS} runs): {avg_rust*1000:.2f} ms")
    print(f"  Output: {len(res['frequencies'])} frequency points")
    print(f"  Z_real[0] = {res['Z_real'][0]:.2f}")
    return avg_rust

def benchmark_cv():
    print("\n--- CV Simulation Benchmark ---")
    times_rust = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        res = cv_simulate(area_cm2=0.0707, E_formal_V=0.23, scan_rate_V_s=0.05, n_points=2000)
        t1 = time.perf_counter()
        times_rust.append(t1 - t0)
    avg_rust = sum(times_rust) / len(times_rust)
    print(f"  Rust (avg {N_RUNS} runs): {avg_rust*1000:.2f} ms")
    print(f"  Output: {len(res['E'])} potential points")
    print(f"  i_pa = {res['peaks']['i_pa']:.6f}, i_pc = {res['peaks']['i_pc']:.6f}")
    return avg_rust

def benchmark_rust_direct():
    print("\n--- Direct Rust Module Benchmark ---")
    import raman_core_rs

    p = raman_core_rs.PyEISParams()
    p.Rs = 10.0
    p.Rct = 100.0
    p.Cdl = 1e-5
    p.sigma_w = 50.0
    p.n_cpe = 0.9

    times = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        res = raman_core_rs.simulate_eis_py(p, 0.01, 1e6, 1000)
        t1 = time.perf_counter()
        times.append(t1 - t0)
    avg = sum(times) / len(times)
    print(f"  Direct PyO3 call (avg {N_RUNS} runs): {avg*1000:.2f} ms")
    print(f"  Result fields: frequencies={len(res.frequencies)}, Z_real={len(res.Z_real)}")
    return avg

if __name__ == "__main__":
    t_eis = benchmark_eis()
    t_cv = benchmark_cv()
    t_direct = benchmark_rust_direct()

    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"  EIS simulation:     {t_eis*1000:.2f} ms")
    print(f"  CV simulation:      {t_cv*1000:.2f} ms")
    print(f"  Direct Rust call:   {t_direct*1000:.2f} ms")
    print("=" * 60)
    print("All benchmarks completed successfully.")
