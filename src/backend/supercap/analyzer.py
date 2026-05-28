"""
Supercapacitor analysis — converts raw CV / GCD / EIS arrays into
the figures of merit a researcher actually iterates on.

Why this module exists
----------------------
The earlier ``import_agv_xlsx.py`` used naive shortcuts:
  * GCD capacitance from the *steepest* discharge segment (overestimates
    pseudocapacitive contribution and gets fooled by short transients).
  * EIS Rct via "2 × (semicircle apex − Rs)", which is wrong for
    supercap-shaped Nyquist plots that don't have a real semicircle.

This module replaces those with the proper physics:

* **CV → Cs(v)**:  for each scan rate v,
      Cs(v) = (1/(2 · ΔV · v)) · ∮ |i(V)| dV
   averaged over a full triangular cycle. This integrates the real
   charge passed and is meaningful for both EDLC and pseudocapacitive
   electrodes.

* **GCD → Cs(cycle)**: identify the linear discharge segment with the
  longest near-constant-slope run, fit i·dt / dV after subtracting the
  IR drop at current reversal, and compute Coulombic efficiency from
  charge/discharge time ratio.

* **EIS → Cs(f), Rs, knee freq**:
      C(f) = -1 / (2π·f·Z''(f))
   evaluated at the lowest frequency. ESR from the high-frequency
   real intercept. The knee frequency where the trace transitions from
   semicircle/arc to vertical line is computed from |dZ''/dZ'|.

* **Trasatti b-value**: from log(i_pa) vs log(v) slope.
  b ≈ 0.5 ⇒ diffusion-limited.
  b ≈ 1.0 ⇒ surface-confined (capacitive / pseudocap).
  0.5 < b < 1.0 ⇒ mixed; 1−b is the diffusion fraction.

Energy density E = 0.5·C·ΔV² and power density P = ΔV²/(4·ESR·m) are
returned when the user provides electrode mass.

What the caller has to provide
------------------------------
The xlsx files lack metadata that the analyzer needs:

* ``mass_g``        — active-material mass for gravimetric Cs (F/g, Wh/kg, W/kg).
                      If omitted, only absolute (F) and areal (F/cm²) values are reported.
* ``area_cm2``      — geometric electrode area for areal Cs.
* ``eis_freq_Hz``   — the actual frequency vector. If omitted we assume
                      log-spaced ``f_max → f_min``.
* ``gcd_current_A`` — applied current for the GCD run (cannot be
                      inferred from voltage data alone).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


# ---- helpers --------------------------------------------------------


def _is_finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def _trapezoid(xs: list[float], ys: list[float]) -> float:
    """Pure-Python trapezoidal integration — no numpy dependency."""
    if len(xs) < 2:
        return 0.0
    s = 0.0
    for i in range(len(xs) - 1):
        dx = xs[i + 1] - xs[i]
        if not _is_finite(dx):
            continue
        s += 0.5 * dx * (ys[i] + ys[i + 1])
    return s


def _abs_trapezoid(xs: list[float], ys: list[float]) -> float:
    """Integral of |y| dx along a possibly-non-monotonic x.

    Splits the trace at every direction reversal of x so each segment is
    integrated with a consistent sign, then sums the absolute values."""
    if len(xs) < 2:
        return 0.0
    total = 0.0
    seg_x: list[float] = [xs[0]]
    seg_y: list[float] = [ys[0]]
    prev_dir = 0
    for i in range(1, len(xs)):
        dx = xs[i] - xs[i - 1]
        cur = 1 if dx > 0 else -1 if dx < 0 else 0
        if cur != 0 and prev_dir != 0 and cur != prev_dir:
            total += abs(_trapezoid(seg_x, [abs(y) for y in seg_y]))
            seg_x = [xs[i - 1]]
            seg_y = [ys[i - 1]]
        seg_x.append(xs[i])
        seg_y.append(ys[i])
        if cur != 0:
            prev_dir = cur
    total += abs(_trapezoid(seg_x, [abs(y) for y in seg_y]))
    return total


def _log_lin_fit(xs: list[float], ys: list[float]) -> dict[str, Optional[float]]:
    """Return slope/intercept/r² of log10(y) = m·log10(x) + b. Skips
    non-positive entries."""
    pairs = [(math.log10(x), math.log10(y))
             for x, y in zip(xs, ys)
             if x > 0 and y > 0 and _is_finite(x) and _is_finite(y)]
    if len(pairs) < 2:
        return {"slope": None, "intercept": None, "r_squared": None,
                "n": len(pairs)}
    n = len(pairs)
    sx = sum(x for x, _ in pairs); sy = sum(y for _, y in pairs)
    sxx = sum(x * x for x, _ in pairs)
    sxy = sum(x * y for x, y in pairs)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-30:
        return {"slope": None, "intercept": None, "r_squared": None, "n": n}
    m = (n * sxy - sx * sy) / denom
    b = (sy - m * sx) / n
    y_mean = sy / n
    ss_res = sum((y - (m * x + b)) ** 2 for x, y in pairs)
    ss_tot = sum((y - y_mean) ** 2 for _, y in pairs)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else None
    return {"slope": m, "intercept": b, "r_squared": r2, "n": n}


# ---- single-experiment results ------------------------------------


@dataclass
class CVCycleResult:
    scan_rate_V_s:   float
    cs_F:            float    # absolute (no mass)
    cs_F_per_g:      Optional[float] = None
    cs_F_per_cm2:    Optional[float] = None
    ipa_A:           Optional[float] = None
    ipc_A:           Optional[float] = None
    e_pa_V:          Optional[float] = None
    e_pc_V:          Optional[float] = None
    delta_v_V:       Optional[float] = None
    cycle_time_s:    Optional[float] = None
    quality_flags:   list[str] = field(default_factory=list)


@dataclass
class GCDCycleResult:
    cycle:                        int
    discharge_slope_V_per_s:      Optional[float]
    cs_F:                         Optional[float]
    cs_F_per_g:                   Optional[float] = None
    cs_F_per_cm2:                 Optional[float] = None
    ir_drop_V:                    Optional[float] = None
    energy_J:                     Optional[float] = None
    energy_Wh_per_kg:             Optional[float] = None
    coulombic_efficiency:         Optional[float] = None
    discharge_time_s:             Optional[float] = None
    charge_time_s:                Optional[float] = None
    v_max_V:                      Optional[float] = None
    v_min_V:                      Optional[float] = None
    quality_flags:                list[str] = field(default_factory=list)


@dataclass
class EISResult:
    rs_ohm:                Optional[float]
    cs_low_freq_F:         Optional[float] = None
    cs_low_freq_F_per_g:   Optional[float] = None
    knee_frequency_Hz:     Optional[float] = None
    f_at_phase_45deg_Hz:   Optional[float] = None
    n_points:              int = 0
    nyquist_shape:         str = "unknown"   # supercapacitive | semicircle | mixed
    quality_flags:         list[str] = field(default_factory=list)


@dataclass
class SupercapReport:
    """Top-level structured analysis result."""
    cv_per_scan_rate:    list[CVCycleResult] = field(default_factory=list)
    gcd_per_cycle:       list[GCDCycleResult] = field(default_factory=list)
    eis:                 Optional[EISResult] = None

    # Cross-experiment summary numbers.
    cs_summary_F:        dict[str, Optional[float]] = field(default_factory=dict)
    cs_summary_F_per_g:  dict[str, Optional[float]] = field(default_factory=dict)
    b_value:             Optional[float] = None
    b_value_r_squared:   Optional[float] = None
    diffusion_fraction:  Optional[float] = None
    surface_fraction:    Optional[float] = None
    capacitance_retention_pct: Optional[float] = None
    average_coulombic_efficiency_pct: Optional[float] = None

    # Power / energy density (require mass).
    energy_density_Wh_per_kg: Optional[float] = None
    power_density_W_per_kg:   Optional[float] = None

    # Qualitative diagnosis the recommender can use.
    diagnostics: list[str] = field(default_factory=list)


# ---- the analyzer --------------------------------------------------


class SupercapAnalyzer:
    """
    Stateless analyzer. Pass arrays in, get a ``SupercapReport`` out.

    Construction parameters carry the metadata the xlsx doesn't have:
    electrode mass, area, applied GCD current, EIS frequency vector.
    """

    def __init__(
        self,
        *,
        mass_g:        Optional[float] = None,
        area_cm2:      Optional[float] = None,
        gcd_current_A: Optional[float] = None,
        eis_freq_Hz:   Optional[list[float]] = None,
        eis_fmax_Hz:   float = 1.0e5,
        eis_fmin_Hz:   float = 1.0e-2,
    ) -> None:
        self.mass_g = mass_g
        self.area_cm2 = area_cm2
        self.gcd_current_A = gcd_current_A
        self.eis_freq_Hz = list(eis_freq_Hz) if eis_freq_Hz else None
        self.eis_fmax_Hz = eis_fmax_Hz
        self.eis_fmin_Hz = eis_fmin_Hz

    # ------------------------------------------------------------------
    # CV — Cs by integration of i(V) over a full triangular cycle.
    # Cs(v) = (1 / (2·ΔV·v)) · ∮ |i(V)| dV
    # ------------------------------------------------------------------

    def analyze_cv(
        self,
        scan_rate_V_s: float,
        potential_V:   list[float],
        current_A:     list[float],
    ) -> CVCycleResult:
        if len(potential_V) < 4 or len(current_A) != len(potential_V):
            return CVCycleResult(
                scan_rate_V_s=scan_rate_V_s, cs_F=0.0,
                quality_flags=["insufficient data"],
            )

        clean = [(p, i) for p, i in zip(potential_V, current_A)
                 if _is_finite(p) and _is_finite(i)]
        if len(clean) < 4:
            return CVCycleResult(
                scan_rate_V_s=scan_rate_V_s, cs_F=0.0,
                quality_flags=["all NaN"],
            )

        pots = [p for p, _ in clean]
        curs = [i for _, i in clean]
        v_max = max(pots); v_min = min(pots)
        delta_v = v_max - v_min
        if delta_v < 1e-6:
            return CVCycleResult(
                scan_rate_V_s=scan_rate_V_s, cs_F=0.0,
                quality_flags=["zero voltage window"],
            )

        # Total charge passed over the cycle ≈ ∮ |i| dt = (1/v) · ∮ |i| dV.
        # Splitting at direction reversals keeps the segment-wise sign
        # consistent.
        q_total_C = _abs_trapezoid(pots, curs) / scan_rate_V_s
        # A full charge–discharge cycle moves ≈ 2·Cs·ΔV of charge.
        cs_F = q_total_C / (2.0 * delta_v) if delta_v > 0 else 0.0

        # Forward-half peak detection (re-uses the importer's logic).
        i_max_pot_idx = max(range(len(pots)), key=lambda i: pots[i])
        fwd_p = pots[: i_max_pot_idx + 1]; fwd_i = curs[: i_max_pot_idx + 1]
        rev_p = pots[i_max_pot_idx:];     rev_i = curs[i_max_pot_idx:]
        ipa_idx = max(range(len(fwd_i)), key=lambda i: fwd_i[i])
        ipc_idx = min(range(len(rev_i)), key=lambda i: rev_i[i])
        ipa = fwd_i[ipa_idx]; e_pa = fwd_p[ipa_idx]
        ipc = rev_i[ipc_idx]; e_pc = rev_p[ipc_idx]

        flags: list[str] = []
        if cs_F <= 0:
            flags.append("non-positive Cs (data quality?)")
        if scan_rate_V_s <= 0:
            flags.append("non-positive scan rate")
        if abs(ipa) > 0 and abs(ipc) > 0:
            ratio = abs(ipa / ipc)
            if ratio < 0.5 or ratio > 2.0:
                flags.append(f"asymmetric ipa/ipc = {ratio:.2f} (non-Nernstian)")

        return CVCycleResult(
            scan_rate_V_s=scan_rate_V_s,
            cs_F=cs_F,
            cs_F_per_g=cs_F / self.mass_g if self.mass_g else None,
            cs_F_per_cm2=cs_F / self.area_cm2 if self.area_cm2 else None,
            ipa_A=ipa, ipc_A=ipc, e_pa_V=e_pa, e_pc_V=e_pc,
            delta_v_V=delta_v,
            cycle_time_s=2.0 * delta_v / scan_rate_V_s,
            quality_flags=flags,
        )

    # ------------------------------------------------------------------
    # GCD — find the linear discharge segment, account for IR drop,
    # compute Cs = i·Δt / (ΔV − ΔV_IR).
    # ------------------------------------------------------------------

    def analyze_gcd(
        self,
        cycle:      int,
        time_s:     list[float],
        voltage_V:  list[float],
    ) -> GCDCycleResult:
        if len(time_s) < 4 or len(voltage_V) != len(time_s):
            return GCDCycleResult(cycle=cycle, discharge_slope_V_per_s=None,
                                  cs_F=None,
                                  quality_flags=["insufficient data"])
        clean = [(t, v) for t, v in zip(time_s, voltage_V)
                 if _is_finite(t) and _is_finite(v)]
        if len(clean) < 4:
            return GCDCycleResult(cycle=cycle, discharge_slope_V_per_s=None,
                                  cs_F=None, quality_flags=["all NaN"])

        ts = [t for t, _ in clean]
        vs = [v for _, v in clean]
        v_max_idx = max(range(len(vs)), key=lambda i: vs[i])
        v_max = vs[v_max_idx]
        v_min = min(vs)

        # The discharge segment is the part where dV/dt < 0.
        # Find the longest run of consecutively decreasing voltage that
        # starts at or after the global maximum (charge → discharge transition).
        best_run = (None, None)  # (start_idx, end_idx) in `clean`
        i = v_max_idx
        while i < len(clean) - 1:
            if vs[i + 1] < vs[i]:
                start = i
                while i < len(clean) - 1 and vs[i + 1] <= vs[i]:
                    i += 1
                end = i
                if best_run == (None, None) or (end - start) > (best_run[1] - best_run[0]):
                    best_run = (start, end)
            else:
                i += 1

        if best_run == (None, None) or best_run[1] - best_run[0] < 3:
            return GCDCycleResult(cycle=cycle, discharge_slope_V_per_s=None,
                                  cs_F=None, v_max_V=v_max, v_min_V=v_min,
                                  quality_flags=["no discharge segment"])

        s, e = best_run
        # IR drop: voltage step right at the charge → discharge transition.
        # Approximate as |V[s] − V[s−1]| if s > 0 (the dip when current
        # reverses direction).
        ir_drop = None
        if s >= 1:
            ir_drop = max(0.0, vs[s - 1] - vs[s])

        # Linear regression on the discharge segment.
        ts_seg = ts[s:e + 1]; vs_seg = vs[s:e + 1]
        n = len(ts_seg)
        sx = sum(ts_seg); sy = sum(vs_seg)
        sxx = sum(t * t for t in ts_seg)
        sxy = sum(t * v for t, v in zip(ts_seg, vs_seg))
        denom = n * sxx - sx * sx
        slope = (n * sxy - sx * sy) / denom if abs(denom) > 1e-30 else None

        # Charge / discharge time ratio for Coulombic efficiency.
        # We approximate the charge segment as the run preceding s.
        charge_time = ts[v_max_idx] - ts[0] if v_max_idx > 0 else None
        discharge_time = ts[e] - ts[s]
        eta = None
        if charge_time and charge_time > 0:
            eta = max(0.0, min(1.0, discharge_time / charge_time))

        # Cs from i·Δt / ΔV.
        cs_F = None
        cs_F_per_g = cs_F_per_cm2 = None
        energy_J = energy_Wh_per_kg = None
        if (self.gcd_current_A is not None and slope is not None
                and slope < 0):
            # ΔV_effective subtracts IR drop so we measure the truly
            # capacitive portion of the swing.
            dv_eff = max(1e-12, (v_max - v_min) - (ir_drop or 0.0))
            cs_F = abs(self.gcd_current_A) * discharge_time / dv_eff
            if self.mass_g:
                cs_F_per_g = cs_F / self.mass_g
                energy_J = 0.5 * cs_F * (dv_eff ** 2)
                # E = 0.5 C V² → Wh/kg = J / (3600·m·1e-3·1000) = J / (3600·m_kg)
                energy_Wh_per_kg = energy_J / (3600.0 * self.mass_g * 1e-3)
            if self.area_cm2:
                cs_F_per_cm2 = cs_F / self.area_cm2

        flags: list[str] = []
        if discharge_time < 0.1:
            flags.append("very short discharge segment")
        if ir_drop is not None and ir_drop > 0.1 * (v_max - v_min):
            flags.append(f"large IR drop ({1000 * ir_drop:.0f} mV)")
        if eta is not None and eta < 0.85:
            flags.append(f"low Coulombic efficiency ({100 * eta:.1f}%)")

        return GCDCycleResult(
            cycle=cycle,
            discharge_slope_V_per_s=slope,
            cs_F=cs_F,
            cs_F_per_g=cs_F_per_g,
            cs_F_per_cm2=cs_F_per_cm2,
            ir_drop_V=ir_drop,
            energy_J=energy_J,
            energy_Wh_per_kg=energy_Wh_per_kg,
            coulombic_efficiency=eta,
            discharge_time_s=discharge_time,
            charge_time_s=charge_time,
            v_max_V=v_max, v_min_V=v_min,
            quality_flags=flags,
        )

    # ------------------------------------------------------------------
    # EIS — Rs from ω→∞ extrapolation, Cs from ω→0 (-1/(ω·Z'')).
    # ------------------------------------------------------------------

    def analyze_eis(
        self,
        z_real_ohm: list[float],
        z_imag_ohm: list[float],
    ) -> EISResult:
        if len(z_real_ohm) < 4 or len(z_imag_ohm) != len(z_real_ohm):
            return EISResult(rs_ohm=None, n_points=len(z_real_ohm),
                              quality_flags=["insufficient data"])

        n = len(z_real_ohm)
        if self.eis_freq_Hz and len(self.eis_freq_Hz) == n:
            freqs = list(self.eis_freq_Hz)
        else:
            log_fmax = math.log10(self.eis_fmax_Hz)
            log_fmin = math.log10(self.eis_fmin_Hz)
            freqs = [10.0 ** (log_fmax - i * (log_fmax - log_fmin) / (n - 1))
                     for i in range(n)]

        # Rs: high-frequency intercept. The first row in our data is the
        # highest frequency; if Z'' is roughly zero there, Rs = Z' there.
        # If Z'' has changed sign in the high-freq region, interpolate.
        rs_ohm = None
        for i in range(min(8, n - 1)):  # search the top-8 highest-freq points
            if z_imag_ohm[i] * z_imag_ohm[i + 1] <= 0 and z_imag_ohm[i] != z_imag_ohm[i + 1]:
                t = z_imag_ohm[i] / (z_imag_ohm[i] - z_imag_ohm[i + 1])
                rs_ohm = z_real_ohm[i] + t * (z_real_ohm[i + 1] - z_real_ohm[i])
                break
        if rs_ohm is None:
            rs_ohm = z_real_ohm[0]

        # C(f) at the lowest frequency, where the trace should be vertical
        # for a clean supercap. Use the median of the bottom-3 points to
        # reject single-point noise.
        cs_low_freq_F = None
        bottom = sorted(range(n), key=lambda i: freqs[i])[:3]
        c_estimates: list[float] = []
        for i in bottom:
            if freqs[i] > 0 and z_imag_ohm[i] < 0:
                c_estimates.append(-1.0 / (2.0 * math.pi * freqs[i] * z_imag_ohm[i]))
        if c_estimates:
            c_estimates.sort()
            cs_low_freq_F = c_estimates[len(c_estimates) // 2]

        # Knee frequency: find the frequency where the local slope of the
        # Nyquist trace transitions from semicircle-like (|dZ''/dZ'| of
        # order 1) to capacitive line (|dZ''/dZ'| ≫ 1, often > 5).
        knee = None
        for i in range(2, n - 2):
            if z_imag_ohm[i] >= 0:
                continue
            dr = z_real_ohm[i + 1] - z_real_ohm[i]
            di = z_imag_ohm[i + 1] - z_imag_ohm[i]
            if abs(dr) < 1e-12:
                continue
            slope = abs(di / dr)
            if slope > 5.0:
                knee = freqs[i]
                break

        # Phase 45° point — useful for diffusion / Warburg detection.
        phase_45 = None
        for i in range(n - 1):
            if z_real_ohm[i] <= 0 or z_imag_ohm[i] >= 0:
                continue
            phase = math.degrees(math.atan2(-z_imag_ohm[i], z_real_ohm[i]))
            if 40.0 <= phase <= 50.0:
                phase_45 = freqs[i]
                break

        # Diagnose Nyquist shape.
        z_min = min(z_imag_ohm); z_real_max = max(z_real_ohm)
        if z_min < -0.5 * z_real_max:
            shape = "supercapacitive (vertical low-f line dominates)"
        elif z_min < -0.05 * z_real_max:
            shape = "mixed (visible arc + capacitive tail)"
        else:
            shape = "near-pure-resistor or noise"

        flags: list[str] = []
        if rs_ohm is not None and rs_ohm < 0:
            flags.append("Rs estimate is negative — frequency vector may be reversed")
        if cs_low_freq_F is None:
            flags.append("could not extract Cs(f) — Z'' never went below zero")

        return EISResult(
            rs_ohm=rs_ohm,
            cs_low_freq_F=cs_low_freq_F,
            cs_low_freq_F_per_g=(cs_low_freq_F / self.mass_g
                                  if (cs_low_freq_F and self.mass_g) else None),
            knee_frequency_Hz=knee,
            f_at_phase_45deg_Hz=phase_45,
            n_points=n,
            nyquist_shape=shape,
            quality_flags=flags,
        )

    # ------------------------------------------------------------------
    # Cross-experiment summary
    # ------------------------------------------------------------------

    def aggregate(
        self,
        cv_results: list[CVCycleResult],
        gcd_results: list[GCDCycleResult],
        eis_result: Optional[EISResult] = None,
    ) -> SupercapReport:
        report = SupercapReport(
            cv_per_scan_rate=cv_results,
            gcd_per_cycle=gcd_results,
            eis=eis_result,
        )

        # ── Cs summaries (the headline numbers).
        # CV: report Cs at the lowest scan rate (closest to thermodynamic limit)
        # and the median across all scans.
        cs_F_summary: dict[str, Optional[float]] = {}
        cs_g_summary: dict[str, Optional[float]] = {}
        if cv_results:
            cv_sorted = sorted(cv_results, key=lambda r: r.scan_rate_V_s)
            cs_F_summary["cv_lowest_scan"]   = cv_sorted[0].cs_F
            cs_F_summary["cv_median_scan"]   = sorted(r.cs_F for r in cv_results)[len(cv_results) // 2]
            cs_F_summary["cv_highest_scan"]  = cv_sorted[-1].cs_F
            if any(r.cs_F_per_g is not None for r in cv_results):
                gs = [r.cs_F_per_g for r in cv_results if r.cs_F_per_g is not None]
                cs_g_summary["cv_lowest_scan"]  = sorted([r.cs_F_per_g for r in cv_sorted if r.cs_F_per_g is not None])[0] if gs else None
                cs_g_summary["cv_median_scan"]  = sorted(gs)[len(gs) // 2]
        if gcd_results:
            gcd_clean = [r for r in gcd_results if r.cs_F is not None]
            if gcd_clean:
                cs_F_summary["gcd_first_cycle"]  = gcd_clean[0].cs_F
                cs_F_summary["gcd_last_cycle"]   = gcd_clean[-1].cs_F
                cs_F_summary["gcd_median"]       = sorted(r.cs_F for r in gcd_clean)[len(gcd_clean) // 2]
                if all(r.cs_F_per_g is not None for r in gcd_clean):
                    gs = [r.cs_F_per_g for r in gcd_clean]
                    cs_g_summary["gcd_first_cycle"] = gs[0]
                    cs_g_summary["gcd_last_cycle"]  = gs[-1]
                    cs_g_summary["gcd_median"]      = sorted(gs)[len(gs) // 2]
        if eis_result and eis_result.cs_low_freq_F is not None:
            cs_F_summary["eis_low_freq"] = eis_result.cs_low_freq_F
            if eis_result.cs_low_freq_F_per_g is not None:
                cs_g_summary["eis_low_freq"] = eis_result.cs_low_freq_F_per_g

        report.cs_summary_F = cs_F_summary
        report.cs_summary_F_per_g = cs_g_summary

        # ── Trasatti b-value: log(ipa) vs log(v).
        if len(cv_results) >= 3:
            xs = [r.scan_rate_V_s for r in cv_results
                  if r.ipa_A is not None and r.scan_rate_V_s > 0]
            ys = [abs(r.ipa_A) for r in cv_results
                  if r.ipa_A is not None and r.ipa_A != 0]
            if len(xs) >= 3 and len(ys) == len(xs):
                fit = _log_lin_fit(xs, ys)
                report.b_value = fit["slope"]
                report.b_value_r_squared = fit["r_squared"]
                if fit["slope"] is not None:
                    b = max(0.0, min(1.0, fit["slope"]))
                    report.surface_fraction = b - 0.5 if b >= 0.5 else 0.0
                    report.diffusion_fraction = 1.0 - b if b <= 1.0 else 0.0

        # ── Capacitance retention from GCD.
        gcd_with_c = [r for r in gcd_results if r.cs_F]
        if len(gcd_with_c) >= 2:
            first = gcd_with_c[0].cs_F
            last  = gcd_with_c[-1].cs_F
            if first and first > 0:
                report.capacitance_retention_pct = 100.0 * last / first

        etas = [r.coulombic_efficiency for r in gcd_results
                if r.coulombic_efficiency is not None]
        if etas:
            report.average_coulombic_efficiency_pct = 100.0 * sum(etas) / len(etas)

        # ── Energy / power densities (require mass).
        if (self.mass_g and gcd_with_c
                and any(r.energy_Wh_per_kg is not None for r in gcd_with_c)):
            es = [r.energy_Wh_per_kg for r in gcd_with_c
                  if r.energy_Wh_per_kg is not None]
            report.energy_density_Wh_per_kg = max(es) if es else None
        if (self.mass_g and eis_result and eis_result.rs_ohm
                and gcd_with_c):
            v_swings = [(r.v_max_V or 0) - (r.v_min_V or 0) for r in gcd_with_c]
            v = max(v_swings) if v_swings else 0
            if v > 0 and eis_result.rs_ohm > 0:
                # P_max = V² / (4·ESR·m_kg) → W/kg
                report.power_density_W_per_kg = (v ** 2) / (
                    4.0 * eis_result.rs_ohm * self.mass_g * 1e-3)

        # ── Diagnostics (consumed by the recommender).
        diag: list[str] = []
        if report.b_value is not None:
            if report.b_value > 0.9:
                diag.append(
                    f"b ≈ {report.b_value:.2f}: surface-confined "
                    "(capacitive / pseudocap) charge storage")
            elif report.b_value > 0.7:
                diag.append(
                    f"b ≈ {report.b_value:.2f}: mixed "
                    f"(~{100*(report.surface_fraction or 0):.0f}% surface, "
                    f"~{100*(report.diffusion_fraction or 0):.0f}% diffusion)")
            elif report.b_value > 0.5:
                diag.append(
                    f"b ≈ {report.b_value:.2f}: predominantly diffusion-limited")
        if eis_result and "supercapacitive" in eis_result.nyquist_shape:
            diag.append(
                "EIS Nyquist is supercapacitor-shaped (vertical low-f line); "
                "real Cs comes from ω→0, not from a 'semicircle' that isn't there")
        if report.capacitance_retention_pct is not None and report.capacitance_retention_pct < 80:
            diag.append(
                f"only {report.capacitance_retention_pct:.0f}% capacitance retention "
                f"over {len(gcd_with_c)} cycles — investigate degradation mechanism")
        if cs_F_summary:
            cv_med = cs_F_summary.get("cv_median_scan")
            gcd_med = cs_F_summary.get("gcd_median")
            eis_lf  = cs_F_summary.get("eis_low_freq")
            non_null = [v for v in (cv_med, gcd_med, eis_lf) if v]
            if len(non_null) >= 2:
                hi, lo = max(non_null), min(non_null)
                if lo > 0 and (hi / lo) > 3.0:
                    diag.append(
                        "Cs estimates from CV/GCD/EIS disagree by >3×; "
                        "double-check applied current, mass, and EIS frequency vector")
        report.diagnostics = diag

        return report


# ---- serialisation -----------------------------------------------


def report_to_dict(r: SupercapReport) -> dict[str, Any]:
    """Plain-dict view of the report for JSON serialisation."""
    return {
        "cv": [
            {
                "scan_rate_V_s":  cv.scan_rate_V_s,
                "scan_rate_mV_s": cv.scan_rate_V_s * 1000.0,
                "cs_F":           cv.cs_F,
                "cs_F_per_g":     cv.cs_F_per_g,
                "cs_F_per_cm2":   cv.cs_F_per_cm2,
                "ipa_uA":         (cv.ipa_A or 0.0) * 1e6,
                "ipc_uA":         (cv.ipc_A or 0.0) * 1e6,
                "e_pa_V":         cv.e_pa_V,
                "e_pc_V":         cv.e_pc_V,
                "delta_v_V":      cv.delta_v_V,
                "quality_flags":  list(cv.quality_flags),
            }
            for cv in r.cv_per_scan_rate
        ],
        "gcd": [
            {
                "cycle":              g.cycle,
                "discharge_slope_V_per_s": g.discharge_slope_V_per_s,
                "ir_drop_V":          g.ir_drop_V,
                "cs_F":               g.cs_F,
                "cs_mF":              (g.cs_F * 1000.0) if g.cs_F else None,
                "cs_F_per_g":         g.cs_F_per_g,
                "cs_F_per_cm2":       g.cs_F_per_cm2,
                "energy_J":           g.energy_J,
                "energy_Wh_per_kg":   g.energy_Wh_per_kg,
                "coulombic_efficiency": g.coulombic_efficiency,
                "discharge_time_s":   g.discharge_time_s,
                "charge_time_s":      g.charge_time_s,
                "v_max_V":            g.v_max_V,
                "v_min_V":            g.v_min_V,
                "quality_flags":      list(g.quality_flags),
            }
            for g in r.gcd_per_cycle
        ],
        "eis": (
            {
                "rs_ohm":              r.eis.rs_ohm,
                "cs_low_freq_F":       r.eis.cs_low_freq_F,
                "cs_low_freq_mF":      (r.eis.cs_low_freq_F * 1000.0)
                                       if r.eis.cs_low_freq_F else None,
                "cs_low_freq_F_per_g": r.eis.cs_low_freq_F_per_g,
                "knee_frequency_Hz":   r.eis.knee_frequency_Hz,
                "f_at_phase_45deg_Hz": r.eis.f_at_phase_45deg_Hz,
                "n_points":            r.eis.n_points,
                "nyquist_shape":       r.eis.nyquist_shape,
                "quality_flags":       list(r.eis.quality_flags),
            }
            if r.eis else None
        ),
        "summary": {
            "cs_F":               r.cs_summary_F,
            "cs_F_per_g":         r.cs_summary_F_per_g,
            "b_value":            r.b_value,
            "b_value_r_squared":  r.b_value_r_squared,
            "diffusion_fraction": r.diffusion_fraction,
            "surface_fraction":   r.surface_fraction,
            "capacitance_retention_pct":      r.capacitance_retention_pct,
            "average_coulombic_efficiency_pct": r.average_coulombic_efficiency_pct,
            "energy_density_Wh_per_kg":       r.energy_density_Wh_per_kg,
            "power_density_W_per_kg":         r.power_density_W_per_kg,
            "diagnostics":        list(r.diagnostics),
        },
    }
