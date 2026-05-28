/**
 * RĀMAN Studio — Circuit Fitter Implementation
 * ==============================================
 * CNLS (Complex Nonlinear Least Squares) via Levenberg-Marquardt.
 *
 * Reference: Boukamp, Solid State Ionics 20 (1986) 31-44
 */

#include "raman/circuit_fitter.hpp"
#include <cmath>
#include <algorithm>

namespace raman {

// ── Randles circuit model ─────────────────────────────────

void randles_model(
    const VecD& frequencies,
    const VecD& p,  // [Rs, Rct, Q0, n_cpe, sigma_w]
    VecD& Z_re,
    VecD& Z_im)
{
    const int M = static_cast<int>(frequencies.size());
    Z_re.resize(M);
    Z_im.resize(M);

    const double Rs = p(0), Rct = p(1), Q0 = p(2);
    const double n = p(3), sigma = p(4);

    #ifdef RAMAN_HAS_OPENMP
    #pragma omp parallel for schedule(static)
    #endif
    for (int m = 0; m < M; ++m) {
        double w = 2.0 * PI * frequencies(m);

        // Warburg: Zw = sigma*(1-j)/sqrt(w)
        double sw = sigma / std::sqrt(w);
        double Zw_re = sw, Zw_im = -sw;

        // Faradaic: Zf = Rct + Zw
        double Zf_re = Rct + Zw_re;
        double Zf_im = Zw_im;

        // CPE admittance: Y_cpe = Q0*(jw)^n
        double wn = std::pow(w, n);
        double Yc_re = Q0 * wn * std::cos(n * PI / 2.0);
        double Yc_im = Q0 * wn * std::sin(n * PI / 2.0);

        // Faradaic admittance: Y_f = 1/Zf
        double d = Zf_re * Zf_re + Zf_im * Zf_im;
        double Yf_re = Zf_re / d;
        double Yf_im = -Zf_im / d;

        // Total parallel admittance
        double Yt_re = Yc_re + Yf_re;
        double Yt_im = Yc_im + Yf_im;

        // Z_parallel = 1/Y_total
        double d2 = Yt_re * Yt_re + Yt_im * Yt_im;
        Z_re(m) = Rs + Yt_re / d2;
        Z_im(m) = -Yt_im / d2;
    }
}

// ── Simple R-RC model ─────────────────────────────────────

static void r_rc_model(
    const VecD& frequencies,
    const VecD& p,  // [Rs, R1, C1]
    VecD& Z_re, VecD& Z_im)
{
    const int M = static_cast<int>(frequencies.size());
    Z_re.resize(M); Z_im.resize(M);
    double Rs = p(0), R1 = p(1), C1 = p(2);

    for (int m = 0; m < M; ++m) {
        double w = 2.0 * PI * frequencies(m);
        double wRC = w * R1 * C1;
        double d = 1.0 + wRC * wRC;
        Z_re(m) = Rs + R1 / d;
        Z_im(m) = -R1 * wRC / d;
    }
}

// ── R-RC-RC model ─────────────────────────────────────────

static void r_rc_rc_model(
    const VecD& frequencies,
    const VecD& p,  // [Rs, R1, C1, R2, C2]
    VecD& Z_re, VecD& Z_im)
{
    const int M = static_cast<int>(frequencies.size());
    Z_re.resize(M); Z_im.resize(M);
    double Rs = p(0), R1 = p(1), C1 = p(2), R2 = p(3), C2 = p(4);

    for (int m = 0; m < M; ++m) {
        double w = 2.0 * PI * frequencies(m);
        double wRC1 = w * R1 * C1, d1 = 1.0 + wRC1 * wRC1;
        double wRC2 = w * R2 * C2, d2 = 1.0 + wRC2 * wRC2;
        Z_re(m) = Rs + R1 / d1 + R2 / d2;
        Z_im(m) = -R1 * wRC1 / d1 - R2 * wRC2 / d2;
    }
}

// ── Forward model dispatcher ─────────────────────────────

static void compute_model(
    CircuitType ct, const VecD& freq, const VecD& p,
    VecD& Zr, VecD& Zi)
{
    switch (ct) {
        case CircuitType::RANDLES: randles_model(freq, p, Zr, Zi); break;
        case CircuitType::R_RC:    r_rc_model(freq, p, Zr, Zi); break;
        case CircuitType::R_RC_RC: r_rc_rc_model(freq, p, Zr, Zi); break;
    }
}

// ── Numerical Jacobian (finite differences) ───────────────

static MatD compute_jacobian(
    CircuitType ct, const VecD& freq, const VecD& p, int M)
{
    const int N = static_cast<int>(p.size());
    MatD J(2 * M, N);
    VecD Zr_p, Zi_p, Zr_m, Zi_m;

    for (int j = 0; j < N; ++j) {
        VecD pp = p, pm = p;
        double h = std::max(1e-8, std::abs(p(j)) * 1e-6);
        pp(j) += h; pm(j) -= h;

        compute_model(ct, freq, pp, Zr_p, Zi_p);
        compute_model(ct, freq, pm, Zr_m, Zi_m);

        for (int m = 0; m < M; ++m) {
            J(m, j) = (Zr_p(m) - Zr_m(m)) / (2.0 * h);
            J(M + m, j) = (Zi_p(m) - Zi_m(m)) / (2.0 * h);
        }
    }
    return J;
}

// ── Main Levenberg-Marquardt fitter ───────────────────────

FitResult fit_circuit(
    const VecD& frequencies,
    const VecD& Z_real,
    const VecD& Z_imag,
    const VecD& initial,
    const FitParams& params)
{
    FitResult result;
    const int M = static_cast<int>(frequencies.size());
    const int N = static_cast<int>(initial.size());

    VecD p = initial;
    double lambda = params.lambda_init;

    // Residual vector [Z_re_data - Z_re_model; Z_im_data - Z_im_model]
    VecD Zr_calc, Zi_calc;
    compute_model(params.circuit, frequencies, p, Zr_calc, Zi_calc);

    VecD r(2 * M);
    for (int m = 0; m < M; ++m) {
        r(m) = Z_real(m) - Zr_calc(m);
        r(M + m) = Z_imag(m) - Zi_calc(m);
    }
    double chi2 = r.squaredNorm();

    result.converged = false;
    int iter = 0;

    for (; iter < params.max_iter; ++iter) {
        MatD J = compute_jacobian(params.circuit, frequencies, p, M);
        MatD JtJ = J.transpose() * J;
        VecD Jtr = J.transpose() * r;

        // LM step: (JᵀJ + λ·diag(JᵀJ)) δ = Jᵀr
        MatD H = JtJ;
        for (int i = 0; i < N; ++i)
            H(i, i) += lambda * JtJ(i, i);

        VecD delta = H.ldlt().solve(Jtr);
        VecD p_new = p + delta;

        // Enforce positivity for physical params
        for (int i = 0; i < N; ++i)
            if (p_new(i) < 1e-15) p_new(i) = 1e-15;

        // Evaluate new residual
        VecD Zr_new, Zi_new;
        compute_model(params.circuit, frequencies, p_new, Zr_new, Zi_new);

        VecD r_new(2 * M);
        for (int m = 0; m < M; ++m) {
            r_new(m) = Z_real(m) - Zr_new(m);
            r_new(M + m) = Z_imag(m) - Zi_new(m);
        }
        double chi2_new = r_new.squaredNorm();

        if (chi2_new < chi2) {
            p = p_new; r = r_new; chi2 = chi2_new;
            Zr_calc = Zr_new; Zi_calc = Zi_new;
            lambda *= params.lambda_down;

            if (delta.norm() < params.tol * p.norm()) {
                result.converged = true;
                break;
            }
        } else {
            lambda *= params.lambda_up;
        }
    }

    result.params = p;
    result.Z_fit_real = Zr_calc;
    result.Z_fit_imag = Zi_calc;
    result.chi_squared = chi2;
    result.reduced_chi_sq = chi2 / std::max(1, 2 * M - N);
    result.iterations = iter;

    // Parameter errors from covariance matrix
    MatD J = compute_jacobian(params.circuit, frequencies, p, M);
    MatD cov = (J.transpose() * J).inverse() * result.reduced_chi_sq;
    result.errors.resize(N);
    for (int i = 0; i < N; ++i)
        result.errors(i) = std::sqrt(std::max(0.0, cov(i, i)));

    return result;
}

}  // namespace raman
