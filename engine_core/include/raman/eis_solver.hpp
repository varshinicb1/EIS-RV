/**
 * RĀMAN Studio — EIS Solver Header
 * ==================================
 * High-performance impedance computation for equivalent circuits.
 *
 * Core model: Modified Randles circuit
 *   Z(ω) = Rs + 1 / (Y_CPE(jω) + 1/(Rct + Z_W(ω)))
 *
 * Supports:
 *   - Semi-infinite Warburg: Z_W = σ(1-j)/√ω
 *   - Bounded Warburg: Z_W = σ·tanh(√(jωτ_d)) / √(jωτ_d)
 *   - CPE (constant phase element): Y = Q₀(jω)^n
 *
 * All frequency sweeps are OpenMP-parallelized.
 */

#pragma once

#include "raman/types.hpp"

namespace raman {

/**
 * Compute impedance of modified Randles circuit at given frequencies.
 *
 * @param frequencies  Log-spaced frequency array (Hz), size N
 * @param params       Circuit parameters (Rs, Rct, Cdl, σ_w, n_cpe, ...)
 * @return             Complex impedance vector, size N
 */
VecC randles_impedance(const VecD& frequencies, const EISParams& params);

/**
 * Full EIS simulation: generates frequencies + computes impedance.
 *
 * @param params     Circuit parameters
 * @param f_min      Minimum frequency (Hz), default 0.01
 * @param f_max      Maximum frequency (Hz), default 1e6
 * @param n_points   Number of log-spaced points, default 100
 * @return           EISResult with all arrays populated
 */
EISResult simulate_eis(
    const EISParams& params,
    double f_min = 0.01,
    double f_max = 1e6,
    int n_points = 100
);

/**
 * Semi-infinite Warburg impedance.
 * Z_W = σ(1-j)/√ω
 */
Complex warburg_semi_infinite(double omega, double sigma_w);

/**
 * Bounded (finite-length) Warburg impedance.
 * Z_W = σ·tanh(√(jωτ_d)) / √(jωτ_d)
 * where τ_d = L²/D
 */
Complex warburg_bounded(double omega, double sigma_w,
                        double L_um, double D_cm2s);

}  // namespace raman
