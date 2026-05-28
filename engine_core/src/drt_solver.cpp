/**
 * RĀMAN Studio — DRT Solver Implementation
 * ==========================================
 * Distribution of Relaxation Times via Tikhonov regularization.
 *
 * Algorithm:
 *   1. Build discretization matrix A where:
 *      A[m, n] = (Δ ln τ) / (1 + j·2π·f_m·τ_n)
 *
 *   2. Solve regularized least-squares:
 *      min ||A·γ - Z_data||² + λ²||L·γ||²
 *
 *      Using the normal equations:
 *      (Aᵀ A + λ² LᵀL) γ = Aᵀ Z_data
 *
 *   3. If non_negative, apply NNLS (projected gradient).
 *
 * For Kramers-Kronig test (Lin-KK):
 *   Use fixed τ_k = 1/(2π·f_k) and fit R_k coefficients.
 *   Residuals indicate K-K compliance.
 *
 * Reference:
 *   Wan et al., Electrochimica Acta 184 (2015) 483-499
 */

#include "raman/drt_solver.hpp"
#include <cmath>
#include <algorithm>
#include <numeric>

namespace raman {

// ── Build DRT discretization matrix ───────────────────────

static void build_drt_matrix(
    const VecD& frequencies, const VecD& tau,
    MatD& A_re, MatD& A_im, double& d_ln_tau)
{
    const int M = static_cast<int>(frequencies.size());
    const int N = static_cast<int>(tau.size());

    d_ln_tau = (N > 1) ? (std::log(tau(N-1)) - std::log(tau(0))) / (N - 1) : 1.0;

    A_re.resize(M, N);
    A_im.resize(M, N);

    #ifdef RAMAN_HAS_OPENMP
    #pragma omp parallel for schedule(static)
    #endif
    for (int m = 0; m < M; ++m) {
        double omega = 2.0 * PI * frequencies(m);
        for (int n = 0; n < N; ++n) {
            double wt = omega * tau(n);
            double denom = 1.0 + wt * wt;
            // Real part: 1/(1 + (ωτ)²)
            A_re(m, n) = d_ln_tau / denom;
            // Imaginary part: -ωτ/(1 + (ωτ)²)
            A_im(m, n) = -d_ln_tau * wt / denom;
        }
    }
}

// ── Second-order difference matrix (smoothness prior) ─────

static MatD build_L_matrix(int N) {
    MatD L = MatD::Zero(N - 2, N);
    for (int i = 0; i < N - 2; ++i) {
        L(i, i)     =  1.0;
        L(i, i + 1) = -2.0;
        L(i, i + 2) =  1.0;
    }
    return L;
}

// ── Non-negative projection ──────────────────────────────

static void project_nonneg(VecD& x) {
    for (int i = 0; i < x.size(); ++i) {
        if (x(i) < 0.0) x(i) = 0.0;
    }
}

// ── Main DRT computation ─────────────────────────────────

DRTResult compute_drt(
    const VecD& frequencies,
    const VecD& Z_real,
    const VecD& Z_imag,
    const DRTParams& params)
{
    DRTResult result;
    const int M = static_cast<int>(frequencies.size());
    const int N = params.n_tau;

    // Build log-spaced τ grid
    result.tau.resize(N);
    double log_tmin = std::log10(params.tau_min);
    double log_tmax = std::log10(params.tau_max);
    double log_step = (log_tmax - log_tmin) / (N - 1);
    for (int i = 0; i < N; ++i) {
        result.tau(i) = std::pow(10.0, log_tmin + i * log_step);
    }

    // Estimate R_inf from highest frequency Z'
    // Find index of maximum frequency
    int idx_max_f = 0;
    for (int i = 1; i < M; ++i) {
        if (frequencies(i) > frequencies(idx_max_f)) idx_max_f = i;
    }
    result.R_inf = Z_real(idx_max_f);

    // Subtract R_inf from Z_real for fitting
    VecD Z_re_shifted = Z_real.array() - result.R_inf;

    // Build discretization matrices
    MatD A_re, A_im;
    double d_ln_tau;
    build_drt_matrix(frequencies, result.tau, A_re, A_im, d_ln_tau);

    // Stack real and imaginary parts: [A_re; A_im] γ ≈ [Z_re - R∞; Z_im]
    MatD A(2 * M, N);
    A.topRows(M) = A_re;
    A.bottomRows(M) = A_im;

    VecD b(2 * M);
    b.head(M) = Z_re_shifted;
    b.tail(M) = Z_imag;

    // Build regularization matrix L (2nd-order smoothness)
    MatD L = build_L_matrix(N);
    double lambda = params.lambda;

    // Normal equations: (AᵀA + λ²LᵀL) γ = Aᵀb
    MatD AtA = A.transpose() * A;
    MatD LtL = L.transpose() * L;
    VecD Atb = A.transpose() * b;

    MatD H = AtA + lambda * lambda * LtL;

    // Solve
    result.gamma = H.ldlt().solve(Atb);

    // Apply non-negativity constraint via projected gradient
    if (params.non_negative) {
        project_nonneg(result.gamma);

        // Refine with a few projected gradient steps
        for (int iter = 0; iter < params.max_iter; ++iter) {
            VecD grad = H * result.gamma - Atb;
            double step = 1.0 / H.diagonal().maxCoeff();
            VecD gamma_new = result.gamma - step * grad;
            project_nonneg(gamma_new);

            // Check convergence
            double delta = (gamma_new - result.gamma).norm();
            result.gamma = gamma_new;
            if (delta < 1e-10 * N) break;
        }
    }

    // Compute fitted impedance
    result.Z_fit_real.resize(M);
    result.Z_fit_imag.resize(M);

    VecD Z_re_fit = A_re * result.gamma;
    VecD Z_im_fit = A_im * result.gamma;

    for (int m = 0; m < M; ++m) {
        result.Z_fit_real(m) = Z_re_fit(m) + result.R_inf;
        result.Z_fit_imag(m) = Z_im_fit(m);
    }

    // Compute R_pol (integral of γ)
    result.R_pol = result.gamma.sum() * d_ln_tau;

    // Compute residual
    VecD resid = b - A * result.gamma;
    result.residual = resid.squaredNorm() / (2 * M);
    result.lambda_used = lambda;

    return result;
}


// ── Kramers-Kronig Test (Lin-KK method) ──────────────────
//
// Schönleber, Klotz, Ivers-Tiffée — A method for improving the
// robustness of linear Kramers-Kronig validity tests. Electrochim.
// Acta 131 (2014) 20-27.
//
// We fit the measured impedance with a bank of RC elements at
// log-spaced τ_k via UNREGULARIZED linear least squares (the Lin-KK
// trick: allowing negative R_k stays K-K-compliant, so a fit that
// requires lots of negative mass implies the data violates K-K).
//
// The Schönleber μ statistic is:
//     μ = 1 - |Σ R_k where R_k < 0| / Σ R_k where R_k ≥ 0
// μ → 1: data is K-K compliant; μ < 0.85: significant violation.

KKResult kramers_kronig_test(
    const VecD& frequencies,
    const VecD& Z_real,
    const VecD& Z_imag,
    int n_rc)
{
    KKResult kk;
    const int M = static_cast<int>(frequencies.size());
    if (M < 2 || Z_real.size() != M || Z_imag.size() != M) {
        return kk;  // empty / mismatched input → is_valid=false, mu=0
    }

    // Default n_rc = number of frequency points.
    if (n_rc <= 0) n_rc = M;
    n_rc = std::max(2, std::min(n_rc, M));
    kk.n_rc_used = n_rc;

    // Log-spaced τ grid spanning a decade beyond the measured frequency
    // range so the fit can absorb relaxations near the edges without
    // forcing artefacts.
    const double tau_min = 1.0 / (2.0 * PI * frequencies.maxCoeff() * 10.0);
    const double tau_max = 10.0 / (2.0 * PI * frequencies.minCoeff());
    VecD tau(n_rc);
    const double log_tau_min = std::log(tau_min);
    const double log_tau_max = std::log(tau_max);
    for (int k = 0; k < n_rc; ++k) {
        const double frac = static_cast<double>(k) / (n_rc - 1);
        tau(k) = std::exp(log_tau_min + frac * (log_tau_max - log_tau_min));
    }

    // Build the design matrix: 2M rows (real, imag stacked), n_rc + 1
    // columns. The last column is the R_inf series term, which only
    // contributes to the real part. For an RC element R_k / (1 + jωτ_k):
    //     real contribution at row i, col k = 1 / (1 + (ω_i τ_k)²)
    //     imag contribution at row i, col k = -ω_i τ_k / (1 + (ω_i τ_k)²)
    MatD A(2 * M, n_rc + 1);
    VecD b(2 * M);
    for (int i = 0; i < M; ++i) {
        const double omega = 2.0 * PI * frequencies(i);
        for (int k = 0; k < n_rc; ++k) {
            const double wt    = omega * tau(k);
            const double denom = 1.0 + wt * wt;
            A(i,     k)     = 1.0 / denom;
            A(M + i, k)     = -wt / denom;
        }
        A(i,     n_rc) = 1.0;   // R_inf → real part only
        A(M + i, n_rc) = 0.0;
        b(i)     = Z_real(i);
        b(M + i) = Z_imag(i);
    }

    // Unregularized least-squares via QR. Returns a minimum-norm
    // solution if A is rank-deficient.
    VecD x = A.colPivHouseholderQr().solve(b);
    VecD R = x.head(n_rc);
    kk.R_inf = x(n_rc);
    kk.tau   = tau;
    kk.R     = R;

    // Fitted impedance + relative residuals.
    VecD fit = A * x;
    kk.Z_fit_real.resize(M);
    kk.Z_fit_imag.resize(M);
    kk.residual_real.resize(M);
    kk.residual_imag.resize(M);
    double mean_sq = 0.0;
    for (int i = 0; i < M; ++i) {
        kk.Z_fit_real(i) = fit(i);
        kk.Z_fit_imag(i) = fit(M + i);
        const double mag = std::sqrt(Z_real(i) * Z_real(i) +
                                      Z_imag(i) * Z_imag(i));
        const double mag_safe = std::max(mag, 1e-30);
        kk.residual_real(i) = (Z_real(i) - kk.Z_fit_real(i)) / mag_safe;
        kk.residual_imag(i) = (Z_imag(i) - kk.Z_fit_imag(i)) / mag_safe;
        mean_sq += kk.residual_real(i) * kk.residual_real(i)
                 + kk.residual_imag(i) * kk.residual_imag(i);
    }
    kk.max_residual_real = kk.residual_real.array().abs().maxCoeff();
    kk.max_residual_imag = kk.residual_imag.array().abs().maxCoeff();
    kk.mean_residual = std::sqrt(mean_sq / (2.0 * M));

    // Schönleber μ statistic.
    double sum_neg = 0.0;
    double sum_pos = 0.0;
    for (int k = 0; k < n_rc; ++k) {
        if (R(k) < 0.0) sum_neg += -R(k);
        else            sum_pos += R(k);
    }
    if (sum_pos > 0.0) {
        kk.mu = 1.0 - sum_neg / sum_pos;
    } else {
        // No positive residues → all mass is negative → severe K-K violation.
        kk.mu = 0.0;
    }
    // Clamp to [0,1] so callers can treat μ as a confidence-like value.
    kk.mu = std::max(0.0, std::min(1.0, kk.mu));

    // Compliance verdict: μ ≥ 0.85 AND per-point residuals ≤ 5 % of |Z|.
    // Schönleber's strict residual cap is 1 %; we are slightly more
    // permissive to accommodate noisier real-world datasets.
    const bool mu_ok       = (kk.mu >= 0.85);
    const bool residual_ok = (kk.max_residual_real < 0.05) &&
                             (kk.max_residual_imag < 0.05);
    kk.is_valid = mu_ok && residual_ok;

    return kk;
}

}  // namespace raman
