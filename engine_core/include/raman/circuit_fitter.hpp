/**
 * RĀMAN Studio — Circuit Fitter Header
 * ======================================
 * Complex Nonlinear Least Squares (CNLS) fitting of equivalent circuits
 * to experimental impedance data.
 *
 * Algorithm: Levenberg-Marquardt with analytical Jacobian.
 *
 * Supported circuits:
 *   - Randles:  Rs + (CPE || (Rct + Zw))
 *   - R-RC:     Rs + (C || Rct)
 *   - R-RC-RC:  Rs + (C1 || R1) + (C2 || R2)
 *   - Custom:   User-defined CDC string (future)
 *
 * Reference:
 *   Boukamp, Solid State Ionics 20 (1986) 31-44
 *   Macdonald, Impedance Spectroscopy, Wiley (2005)
 */

#pragma once

#include "raman/types.hpp"

namespace raman {

// ── Circuit types ─────────────────────────────────────────
enum class CircuitType {
    RANDLES,      // Rs + (CPE || (Rct + Zw))
    R_RC,         // Rs + (C || Rct)
    R_RC_RC,      // Rs + (C1 || R1) + (C2 || R2)
};

// ── Fit parameters ────────────────────────────────────────
struct FitParams {
    CircuitType circuit = CircuitType::RANDLES;
    int    max_iter     = 200;
    double tol          = 1e-8;     // Convergence tolerance
    double lambda_init  = 1e-3;     // Initial LM damping
    double lambda_up    = 10.0;     // Damping increase factor
    double lambda_down  = 0.1;      // Damping decrease factor
};

// ── Fit result ────────────────────────────────────────────
struct FitResult {
    VecD params;              // Fitted parameter values
    VecD errors;              // Parameter standard errors
    VecD Z_fit_real;          // Fitted Z' at each frequency
    VecD Z_fit_imag;          // Fitted Z'' at each frequency
    double chi_squared;       // χ² goodness of fit
    double reduced_chi_sq;    // χ²/(M - N)
    int    iterations;        // Number of LM iterations
    bool   converged;         // Whether fit converged
};

/**
 * Fit equivalent circuit to impedance data.
 *
 * @param frequencies  Frequency array (Hz)
 * @param Z_real       Measured Z' (Ω)
 * @param Z_imag       Measured Z'' (Ω)
 * @param initial      Initial parameter guess
 * @param params       Fitting control parameters
 * @return             FitResult with optimized circuit values
 */
FitResult fit_circuit(
    const VecD& frequencies,
    const VecD& Z_real,
    const VecD& Z_imag,
    const VecD& initial,
    const FitParams& params = FitParams()
);

/**
 * Compute impedance of a Randles circuit at given frequencies.
 * Used internally by the fitter and for forward simulation.
 */
void randles_model(
    const VecD& frequencies,
    const VecD& p,  // [Rs, Rct, Q0, n_cpe, sigma_w]
    VecD& Z_re_out,
    VecD& Z_im_out
);

}  // namespace raman
