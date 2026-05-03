/**
 * RĀMAN Studio — DRT Solver Header
 * ==================================
 * Distribution of Relaxation Times analysis using Tikhonov regularization.
 *
 * The DRT γ(τ) decomposes impedance data into a distribution of
 * relaxation time constants, revealing individual processes that
 * overlap in Nyquist/Bode plots.
 *
 * Algorithm:
 *   Z(ω) = R_∞ + R_pol ∫ γ(τ) / (1 + jωτ) d(ln τ)
 *
 *   Discretized as: Z = A · γ   (ill-posed → Tikhonov)
 *   Solve: min ||A·γ - Z||² + λ||L·γ||²
 *
 * Reference:
 *   Wan et al., Electrochimica Acta 184 (2015) 483-499
 *   Ciucci & Chen, Electrochimica Acta 167 (2015) 439-454
 */

#pragma once

#include "raman/types.hpp"

namespace raman {

// ── DRT Parameters ────────────────────────────────────────
struct DRTParams {
    double lambda       = 1e-3;   // Tikhonov regularization parameter
    int    n_tau        = 200;    // Number of τ grid points
    double tau_min      = 1e-7;   // Minimum relaxation time (s)
    double tau_max      = 1e3;    // Maximum relaxation time (s)
    bool   non_negative = true;   // Enforce γ(τ) ≥ 0
    int    max_iter     = 100;    // Max iterations for NNLS
};

// ── DRT Result ────────────────────────────────────────────
struct DRTResult {
    VecD tau;              // Relaxation time grid (s)
    VecD gamma;            // γ(τ) distribution
    VecD Z_fit_real;       // Fitted Z' from DRT
    VecD Z_fit_imag;       // Fitted Z'' from DRT
    double R_inf;          // High-frequency resistance
    double R_pol;          // Total polarization resistance
    double residual;       // ||Z_data - Z_fit||² / N
    double lambda_used;    // Regularization parameter used
};


// ── Kramers-Kronig Result ─────────────────────────────────
//
// Returned by kramers_kronig_test. The fields below match the
// header's documented contract (residual_real, residual_imag,
// is_valid, mu — see Schönleber et al. 2014).
struct KKResult {
    // Compliance verdict.
    bool   is_valid           = false;

    // The Schönleber μ statistic — fraction of the fitted residue mass
    // that lies on POSITIVE coefficients. μ → 1 ⇒ minimal negative
    // contribution ⇒ data is K-K compliant. μ < ~0.85 indicates
    // significant K-K violation.
    double mu                 = 0.0;

    // Per-frequency relative residual: |Z_meas - Z_fit| / |Z_meas|.
    VecD   residual_real;          // (Z_real_meas - Z_real_fit) / |Z_meas|
    VecD   residual_imag;          // (Z_imag_meas - Z_imag_fit) / |Z_meas|

    // Global residuals (max and L2-mean of the relative residuals).
    double max_residual_real  = 0.0;
    double max_residual_imag  = 0.0;
    double mean_residual      = 0.0;   // root-mean-square of the combined real+imag relative residuals

    // The fitted impedance for visual inspection.
    VecD   Z_fit_real;
    VecD   Z_fit_imag;

    // The RC bank used. R_k can be negative (Lin-KK trick).
    VecD   tau;
    VecD   R;
    double R_inf              = 0.0;

    // Diagnostics.
    int    n_rc_used          = 0;
};

/**
 * Compute DRT from impedance data using Tikhonov regularization.
 *
 * @param frequencies  Measured frequency array (Hz), size M
 * @param Z_real       Measured real impedance (Ω), size M
 * @param Z_imag       Measured imaginary impedance (Ω), size M
 * @param params       DRT solver parameters
 * @return             DRTResult with γ(τ) distribution
 */
DRTResult compute_drt(
    const VecD& frequencies,
    const VecD& Z_real,
    const VecD& Z_imag,
    const DRTParams& params = DRTParams()
);

/**
 * Kramers-Kronig consistency test using the Lin-KK method.
 *
 * Tests whether impedance data satisfies the Kramers-Kronig relations,
 * a prerequisite for valid equivalent-circuit fitting. Implementation
 * follows Schönleber, Klotz, Ivers-Tiffée (Electrochim. Acta 131, 2014):
 * fit the data with a bank of RC elements at logarithmically-spaced τ_k
 * (allowing negative R_k), then compute
 *
 *     μ  =  1 − |Σ R_k where R_k < 0| / Σ |R_k where R_k ≥ 0|
 *
 * μ ≈ 1 ⇒ K-K compliant (no negative-R_k mass needed). μ < 0.85
 * indicates a significant K-K violation, usually meaning experimental
 * artefacts (drift, noise, non-stationarity).
 *
 * @param frequencies  Frequency array (Hz)
 * @param Z_real       Real impedance (Ω)
 * @param Z_imag       Imaginary impedance (Ω)
 * @param n_rc         Number of RC elements (0 = use as many as data points)
 * @return             ``KKResult`` with is_valid, mu, residuals and fit
 */
KKResult kramers_kronig_test(
    const VecD& frequencies,
    const VecD& Z_real,
    const VecD& Z_imag,
    int n_rc = 0
);

}  // namespace raman
