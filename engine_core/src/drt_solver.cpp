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

DRTResult kramers_kronig_test(
    const VecD& frequencies,
    const VecD& Z_real,
    const VecD& Z_imag,
    int n_rc)
{
    const int M = static_cast<int>(frequencies.size());

    // Use fixed τ_k = 1/(2π·f_k) for Lin-KK
    if (n_rc <= 0) n_rc = M;  // Use as many RC elements as data points

    DRTParams params;
    params.n_tau = n_rc;
    params.non_negative = false;  // Lin-KK allows negative coefficients
    params.lambda = 0.0;          // No regularization for K-K test

    // Set τ grid from frequency data
    params.tau_min = 1.0 / (2.0 * PI * frequencies.maxCoeff());
    params.tau_max = 1.0 / (2.0 * PI * frequencies.minCoeff());

    // Compute DRT (which gives us the fit)
    DRTResult result = compute_drt(frequencies, Z_real, Z_imag, params);

    // For K-K test, the residual indicates compliance:
    // Small residual → K-K compliant → data is valid for fitting
    // Large residual → K-K violation → experimental artifacts present

    return result;
}

}  // namespace raman
