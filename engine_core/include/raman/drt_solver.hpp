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
 * Kramers-Kronig consistency test using Lin-KK method.
 *
 * Tests whether impedance data satisfies K-K relations,
 * which is a prerequisite for valid equivalent circuit fitting.
 *
 * @param frequencies  Frequency array (Hz)
 * @param Z_real       Real impedance (Ω)
 * @param Z_imag       Imaginary impedance (Ω)
 * @param n_rc         Number of RC elements for Lin-KK (0 = auto)
 * @return             Map with: residual_real, residual_imag, is_valid, mu
 */
DRTResult kramers_kronig_test(
    const VecD& frequencies,
    const VecD& Z_real,
    const VecD& Z_imag,
    int n_rc = 0
);

}  // namespace raman
