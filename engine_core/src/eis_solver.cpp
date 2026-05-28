/**
 * RĀMAN Studio — EIS Solver Implementation
 * ==========================================
 * Physics-exact impedance computation for modified Randles circuit.
 *
 * Performance: OpenMP-parallelized frequency sweep.
 * Each frequency point is independent → embarrassingly parallel.
 *
 * Validated against:
 *   - Analytical solutions for pure R, pure C, R||C
 *   - Bard & Faulkner eq 11.4.18 (Warburg coefficient)
 *   - Python reference implementation (vanl/backend/core/eis_engine.py)
 */

#include "raman/eis_solver.hpp"
#include <cmath>
#include <algorithm>

namespace raman {

// ── Warburg impedance models ──────────────────────────────

Complex warburg_semi_infinite(double omega, double sigma_w) {
    if (sigma_w < 1e-6 || omega < 1e-12) {
        return Complex(0.0, 0.0);
    }
    double sqrt_omega = std::sqrt(omega);
    // Z_W = σ(1-j)/√ω
    return Complex(sigma_w / sqrt_omega, -sigma_w / sqrt_omega);
}

Complex warburg_bounded(double omega, double sigma_w,
                        double L_um, double D_cm2s) {
    if (sigma_w < 1e-6 || omega < 1e-12) {
        return Complex(0.0, 0.0);
    }

    double L_cm = L_um * 1e-4;
    double tau_d = (L_cm * L_cm) / std::max(D_cm2s, 1e-12);

    // x = √(jωτ_d)
    // √(j) = (1+j)/√2
    double wt = omega * tau_d;
    double sqrt_wt = std::sqrt(wt);
    Complex x(sqrt_wt / std::sqrt(2.0), sqrt_wt / std::sqrt(2.0));

    // tanh(x) — numerically stable for large |x|
    Complex tanh_x;
    if (std::abs(x) > 20.0) {
        tanh_x = Complex(1.0, 0.0);
    } else {
        tanh_x = std::tanh(x);
    }

    // Z_W = σ · tanh(x) / (x + ε)
    Complex denom = x + Complex(1e-30, 0.0);
    return sigma_w * tanh_x / denom;
}


// ── Randles impedance ─────────────────────────────────────

VecC randles_impedance(const VecD& frequencies, const EISParams& p) {
    const int N = static_cast<int>(frequencies.size());
    VecC Z(N);

    #ifdef RAMAN_HAS_OPENMP
    #pragma omp parallel for schedule(static)
    #endif
    for (int i = 0; i < N; ++i) {
        double f = frequencies(i);
        double omega = 2.0 * PI * f;

        // CPE admittance: Y_CPE = Q₀(jω)^n
        // (jω)^n = |ω|^n · exp(j·n·π/2)
        double omega_n = std::pow(omega, p.n_cpe);
        double phase = p.n_cpe * PI / 2.0;
        Complex Y_cpe = p.Cdl * Complex(
            omega_n * std::cos(phase),
            omega_n * std::sin(phase)
        );

        // Warburg impedance
        Complex Z_w;
        if (p.bounded_w) {
            Z_w = warburg_bounded(omega, p.sigma_w,
                                  p.diff_len_um, p.diff_coeff);
        } else {
            Z_w = warburg_semi_infinite(omega, p.sigma_w);
        }

        // Faradaic impedance
        Complex Z_faradaic = Complex(p.Rct, 0.0) + Z_w;

        // Parallel: Z_p = 1 / (Y_CPE + 1/Z_faradaic)
        Complex Z_parallel = Complex(1.0, 0.0) /
            (Y_cpe + Complex(1.0, 0.0) / Z_faradaic);

        // Total: Z = Rs + Z_parallel
        Z(i) = Complex(p.Rs, 0.0) + Z_parallel;
    }

    return Z;
}


// ── Full EIS simulation ───────────────────────────────────

EISResult simulate_eis(const EISParams& params,
                       double f_min, double f_max, int n_points) {
    EISResult result;
    result.params = params;

    // Log-spaced frequency array
    result.frequencies.resize(n_points);
    double log_fmin = std::log10(f_min);
    double log_fmax = std::log10(f_max);
    double step = (log_fmax - log_fmin) / (n_points - 1);

    for (int i = 0; i < n_points; ++i) {
        result.frequencies(i) = std::pow(10.0, log_fmin + i * step);
    }

    // Compute complex impedance
    VecC Z = randles_impedance(result.frequencies, params);

    // Extract real, imaginary, magnitude, phase
    result.Z_real.resize(n_points);
    result.Z_imag.resize(n_points);
    result.Z_magnitude.resize(n_points);
    result.Z_phase.resize(n_points);

    for (int i = 0; i < n_points; ++i) {
        result.Z_real(i)      = Z(i).real();
        result.Z_imag(i)      = Z(i).imag();
        result.Z_magnitude(i) = std::abs(Z(i));
        result.Z_phase(i)     = std::atan2(Z(i).imag(), Z(i).real())
                                 * 180.0 / PI;
    }

    return result;
}

}  // namespace raman
