"""
SupercapAnalyzer — extracts specific capacitance from CV / GCD / EIS.

The math we test here is well-known:

* CV — for an ideal capacitor doing a triangular sweep V(t),
  i(t) = C · dV/dt = C·v. The charge moved over a complete cycle is
  Q = 2·C·ΔV; integrating |i| over one cycle therefore yields
  ∮|i| dV / v = 2·C·ΔV, so Cs = ∮|i| dV / (2·ΔV·v).

* GCD — at constant discharge current i, V(t) drops linearly with slope
  dV/dt = i / C, hence C = i·Δt / ΔV (ignoring IR drop).

* EIS — at low frequency, an ideal supercapacitor's |Z″| ≈ 1/(2πf·C),
  so C = -1/(2π·f·Z″).
"""
import math


from src.backend.supercap.analyzer import SupercapAnalyzer


def _triangular_cv(C: float, scan_rate_V_s: float, v_min: float = 0.0,
                   v_max: float = 1.0, n_per_half: int = 200):
    """Generate an ideal-capacitor CV cycle."""
    pots = []
    curs = []
    # Forward sweep
    for k in range(n_per_half + 1):
        v = v_min + (v_max - v_min) * k / n_per_half
        pots.append(v); curs.append(+C * scan_rate_V_s)
    # Reverse sweep
    for k in range(1, n_per_half + 1):
        v = v_max - (v_max - v_min) * k / n_per_half
        pots.append(v); curs.append(-C * scan_rate_V_s)
    return pots, curs


def test_cv_recovers_known_capacitance():
    C_true = 1.0  # F
    pots, curs = _triangular_cv(C_true, scan_rate_V_s=0.1, v_min=0.0, v_max=1.0)
    a = SupercapAnalyzer()
    r = a.analyze_cv(scan_rate_V_s=0.1, potential_V=pots, current_A=curs)
    # Allow 5% tolerance for trapezoid quadrature
    assert math.isclose(r.cs_F, C_true, rel_tol=0.05), \
        f"CV-extracted Cs={r.cs_F:.4f} vs expected {C_true}"


def test_cv_per_gram_with_mass():
    C_true = 0.5
    pots, curs = _triangular_cv(C_true, scan_rate_V_s=0.05)
    a = SupercapAnalyzer(mass_g=2e-3)  # 2 mg active mass
    r = a.analyze_cv(scan_rate_V_s=0.05, potential_V=pots, current_A=curs)
    expected_F_per_g = C_true / 2e-3  # 250 F/g
    assert math.isclose(r.cs_F_per_g, expected_F_per_g, rel_tol=0.05)


def test_cv_zero_voltage_window_flagged():
    a = SupercapAnalyzer()
    pots = [0.5] * 10
    curs = [1e-3] * 10
    r = a.analyze_cv(scan_rate_V_s=0.1, potential_V=pots, current_A=curs)
    assert r.cs_F == 0.0
    assert any("voltage window" in f for f in r.quality_flags)


def test_cv_handles_nan_gracefully():
    a = SupercapAnalyzer()
    r = a.analyze_cv(
        scan_rate_V_s=0.1,
        potential_V=[float("nan"), float("nan")],
        current_A=[float("nan"), float("nan")],
    )
    assert r.cs_F == 0.0


def test_gcd_recovers_known_capacitance():
    """V drops from 1V to 0V at constant current 1mA over 1s → C = 1mA·1s/1V = 1mF."""
    n = 100
    time_s = [k / (n - 1) for k in range(n)]   # 0..1 s
    voltage_V = [1.0 - t for t in time_s]      # 1..0 V
    a = SupercapAnalyzer(gcd_current_A=1e-3)
    r = a.analyze_gcd(cycle=0, time_s=time_s, voltage_V=voltage_V)
    assert r.cs_F is not None
    # Cs = i·Δt / ΔV = 1e-3 · 1.0 / 1.0 = 1e-3 F
    assert math.isclose(r.cs_F, 1e-3, rel_tol=0.05), \
        f"GCD-extracted Cs={r.cs_F:.6f} vs expected 1e-3"


def test_gcd_with_ir_drop():
    """Add a tiny IR drop at t=0 and confirm we still get sensible Cs."""
    n = 100
    time_s = [k / (n - 1) for k in range(n)]
    # IR drop: 1.0 → 0.9 instantly, then linear 0.9 → 0
    voltage_V = [0.9 - 0.9 * t for t in time_s]
    voltage_V[0] = 1.0  # the pre-discharge open-circuit point
    a = SupercapAnalyzer(gcd_current_A=1e-3)
    r = a.analyze_gcd(cycle=0, time_s=time_s, voltage_V=voltage_V)
    assert r.cs_F is not None and r.cs_F > 0


def test_gcd_insufficient_data():
    a = SupercapAnalyzer(gcd_current_A=1e-3)
    r = a.analyze_gcd(cycle=0, time_s=[0.0, 0.1], voltage_V=[1.0, 0.9])
    assert r.cs_F is None
    assert "insufficient data" in r.quality_flags


def test_eis_recovers_low_freq_capacitance():
    """At f=0.01 Hz, an ideal 1F cap has |Z″|=1/(2π·0.01·1)≈15.92 Ω."""
    C_true = 1.0
    freqs = [0.01, 0.05, 0.1, 1.0, 10.0, 100.0]
    z_imag = [-1.0 / (2 * math.pi * f * C_true) for f in freqs]
    z_real = [0.5] * len(freqs)  # tiny constant Rs

    a = SupercapAnalyzer(eis_freq_Hz=freqs, eis_fmax_Hz=100.0, eis_fmin_Hz=0.01)
    r = a.analyze_eis(z_real_ohm=z_real, z_imag_ohm=z_imag)
    assert r.cs_low_freq_F is not None
    assert math.isclose(r.cs_low_freq_F, C_true, rel_tol=0.10), \
        f"EIS-extracted Cs={r.cs_low_freq_F:.4f} vs expected {C_true}"


def test_aggregate_runs_with_mixed_cycles():
    """End-to-end: a few CV scan rates + a couple of GCDs → aggregate report."""
    a = SupercapAnalyzer(mass_g=1e-3, gcd_current_A=1e-3)
    cv_results = []
    for v in (0.005, 0.01, 0.05, 0.1):
        pots, curs = _triangular_cv(1.0, scan_rate_V_s=v)
        cv_results.append(a.analyze_cv(scan_rate_V_s=v, potential_V=pots, current_A=curs))
    gcd_results = []
    for cyc in range(3):
        n = 50
        t = [k / (n - 1) for k in range(n)]
        v = [1.0 - tt for tt in t]
        gcd_results.append(a.analyze_gcd(cycle=cyc, time_s=t, voltage_V=v))
    eis = a.analyze_eis(
        z_real_ohm=[0.5, 0.5, 0.5],
        z_imag_ohm=[-15.92, -3.18, -1.59],  # |Z″|=1/(2πfC) for f=0.01,0.05,0.1
    )
    rep = a.aggregate(cv_results=cv_results, gcd_results=gcd_results, eis_result=eis)
    # cs_summary_F is keyed by method/cycle (cv_lowest_scan, gcd_median,
    # eis_low_freq, ...). Verify at least the three big buckets emitted.
    assert rep.cs_summary_F is not None
    s = rep.cs_summary_F
    cv_any = any(s.get(k) for k in ("cv_lowest_scan", "cv_median_scan", "cv_highest_scan"))
    gcd_any = any(s.get(k) for k in ("gcd_first_cycle", "gcd_median", "gcd_last_cycle"))
    eis_any = bool(s.get("eis_low_freq"))
    assert sum([cv_any, gcd_any, eis_any]) >= 2, \
        f"aggregate should produce ≥2 method estimates, got {s}"
