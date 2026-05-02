/**
 * RĀMAN Studio — CV Solver Header
 * =================================
 * Butler-Volmer + semi-infinite diffusion cyclic voltammetry solver.
 *
 * Uses the convolution integral method (Nicholson-Shain):
 *   C_O(0,t) = C_O* - (1/√(πD)) ∫₀ᵗ j(τ)/√(t-τ) dτ
 *
 * This is the same approach used by commercial potentiostat software.
 */

#pragma once

#include "raman/types.hpp"

namespace raman {

/**
 * Simulate a full cyclic voltammogram.
 *
 * @param params    CV parameters (electrode, kinetics, scan settings)
 * @param n_points  Points per sweep segment
 * @return          CVResult with E, i, peak analysis
 */
CVResult simulate_cv(const CVParams& params, int n_points = 2000);

/**
 * Randles-Sevcik theoretical peak current.
 *
 * i_p = 0.4463 × n^(3/2) × F^(3/2) × A × C × √(Dv/RT)
 *
 * @param n       Number of electrons
 * @param A_cm2   Electrode area (cm²)
 * @param C_M     Bulk concentration (mol/L)
 * @param D_cm2s  Diffusion coefficient (cm²/s)
 * @param v_Vs    Scan rate (V/s)
 * @param T_K     Temperature (K)
 * @return        Peak current (A)
 */
double randles_sevcik_ip(int n, double A_cm2, double C_M,
                         double D_cm2s, double v_Vs,
                         double T_K = T_STD);

}  // namespace raman
