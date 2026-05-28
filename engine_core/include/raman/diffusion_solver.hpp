/**
 * RĀMAN Studio — Diffusion Solver Header
 * ========================================
 * PDE-based diffusion models for electrochemistry:
 *   - 1D Fick's 2nd law (finite difference, Crank-Nicolson)
 *   - Spherical diffusion (battery particle model)
 *   - Planar diffusion with boundary conditions
 */

#pragma once

#include "raman/types.hpp"

namespace raman {

/**
 * 1D planar diffusion solver (Crank-Nicolson).
 *
 * ∂C/∂t = D · ∂²C/∂x²
 *
 * @param D_cm2s       Diffusion coefficient (cm²/s)
 * @param C_bulk_M     Bulk concentration (mol/L)
 * @param L_cm         Domain length (cm)
 * @param n_spatial    Spatial grid points
 * @param n_time       Time steps
 * @param dt_s         Time step (s)
 * @param flux_func    Surface flux as function of time index
 * @return             Concentration profile at final time (size n_spatial)
 */
VecD solve_diffusion_1d(
    double D_cm2s,
    double C_bulk_M,
    double L_cm,
    int n_spatial,
    int n_time,
    double dt_s,
    const VecD& surface_flux
);

/**
 * Spherical diffusion solver (Single Particle Model).
 *
 * ∂C/∂t = D/r² · ∂/∂r(r² · ∂C/∂r)
 *
 * Used for battery electrode particles.
 *
 * @param D_cm2s       Solid-state diffusion coefficient
 * @param C_max_M      Maximum concentration in solid
 * @param C_init_frac  Initial SOC (0-1)
 * @param radius_um    Particle radius (µm)
 * @param n_radial     Radial grid points
 * @param n_time       Time steps
 * @param dt_s         Time step
 * @param surface_flux Surface flux array (mol/cm²/s)
 * @return             Surface concentration at each time step
 */
VecD solve_spherical_diffusion(
    double D_cm2s,
    double C_max_M,
    double C_init_frac,
    double radius_um,
    int n_radial,
    int n_time,
    double dt_s,
    const VecD& surface_flux
);

}  // namespace raman
