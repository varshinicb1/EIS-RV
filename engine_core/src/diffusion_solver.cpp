/**
 * RĀMAN Studio — Diffusion Solver Implementation
 * ================================================
 * Crank-Nicolson finite difference solvers for Fick's 2nd law.
 *
 * 1D Planar:    ∂C/∂t = D · ∂²C/∂x²
 * Spherical:    ∂C/∂t = D/r² · ∂/∂r(r² · ∂C/∂r)
 *
 * Both use the tridiagonal Thomas algorithm (O(n)) per time step.
 * OpenMP parallelism is used for multi-particle batch simulations.
 */

#include "raman/diffusion_solver.hpp"
#include <cmath>
#include <algorithm>
#include <vector>

namespace raman {

// ── Thomas algorithm (tridiagonal solver) ─────────────────

static VecD thomas_solve(const VecD& a, const VecD& b,
                         const VecD& c, const VecD& d) {
    int n = static_cast<int>(d.size());
    VecD cp(n), dp(n), x(n);

    // Forward sweep
    cp(0) = c(0) / b(0);
    dp(0) = d(0) / b(0);
    for (int i = 1; i < n; ++i) {
        double m = b(i) - a(i) * cp(i - 1);
        if (std::abs(m) < 1e-30) m = 1e-30;
        cp(i) = (i < n - 1) ? c(i) / m : 0.0;
        dp(i) = (d(i) - a(i) * dp(i - 1)) / m;
    }

    // Back substitution
    x(n - 1) = dp(n - 1);
    for (int i = n - 2; i >= 0; --i) {
        x(i) = dp(i) - cp(i) * x(i + 1);
    }
    return x;
}


// ── 1D Planar diffusion (Crank-Nicolson) ──────────────────

VecD solve_diffusion_1d(double D_cm2s, double C_bulk_M,
                        double L_cm, int n_spatial,
                        int n_time, double dt_s,
                        const VecD& surface_flux) {
    double dx = L_cm / (n_spatial - 1);
    double r = D_cm2s * dt_s / (2.0 * dx * dx);  // Crank-Nicolson parameter

    // Initialize concentration profile
    VecD C = VecD::Constant(n_spatial, C_bulk_M * 1e-3);  // mol/cm³

    // Tridiagonal coefficients (constant for uniform grid)
    VecD a_coeff = VecD::Constant(n_spatial, -r);
    VecD b_coeff = VecD::Constant(n_spatial, 1.0 + 2.0 * r);
    VecD c_coeff = VecD::Constant(n_spatial, -r);

    // Boundary: fixed bulk concentration at x = L
    a_coeff(0) = 0.0;
    c_coeff(n_spatial - 1) = 0.0;

    VecD rhs(n_spatial);

    for (int t = 0; t < n_time; ++t) {
        // Build RHS from explicit part
        for (int i = 1; i < n_spatial - 1; ++i) {
            rhs(i) = r * C(i - 1) + (1.0 - 2.0 * r) * C(i) + r * C(i + 1);
        }

        // Boundary conditions
        // x = 0: flux boundary (electrode surface)
        double flux_t = (t < surface_flux.size()) ? surface_flux(t) : 0.0;
        rhs(0) = C(0) - flux_t * dx / D_cm2s;  // Neumann BC
        b_coeff(0) = 1.0;

        // x = L: bulk concentration (Dirichlet)
        rhs(n_spatial - 1) = C_bulk_M * 1e-3;
        b_coeff(n_spatial - 1) = 1.0;

        // Solve tridiagonal system
        C = thomas_solve(a_coeff, b_coeff, c_coeff, rhs);

        // Clamp to physical range
        for (int i = 0; i < n_spatial; ++i) {
            C(i) = std::max(C(i), 0.0);
        }
    }

    return C;
}


// ── Spherical diffusion (Single Particle Model) ───────────

VecD solve_spherical_diffusion(double D_cm2s, double C_max_M,
                               double C_init_frac, double radius_um,
                               int n_radial, int n_time, double dt_s,
                               const VecD& surface_flux) {
    double R_cm = radius_um * 1e-4;  // µm → cm
    double dr = R_cm / (n_radial - 1);

    // Radial grid
    VecD r(n_radial);
    for (int i = 0; i < n_radial; ++i) {
        r(i) = (i == 0) ? dr * 0.01 : i * dr;  // Avoid r=0 singularity
    }

    // Initialize: uniform concentration
    double C_init = C_max_M * C_init_frac * 1e-3;  // mol/cm³
    VecD C = VecD::Constant(n_radial, C_init);

    // Output: surface concentration at each time step
    VecD C_surface(n_time);

    // Tridiagonal coefficients (vary with r)
    VecD a_coeff(n_radial);
    VecD b_coeff(n_radial);
    VecD c_coeff(n_radial);
    VecD rhs(n_radial);

    for (int t = 0; t < n_time; ++t) {
        // Build tridiagonal system for spherical Crank-Nicolson
        for (int i = 1; i < n_radial - 1; ++i) {
            double ri = r(i);
            double alpha_m = D_cm2s * dt_s / (2.0 * dr * dr);
            double beta = D_cm2s * dt_s / (2.0 * ri * dr);

            a_coeff(i) = -(alpha_m - beta);
            b_coeff(i) = 1.0 + 2.0 * alpha_m;
            c_coeff(i) = -(alpha_m + beta);

            // RHS: explicit part
            rhs(i) = (alpha_m - beta) * C(i - 1)
                    + (1.0 - 2.0 * alpha_m) * C(i)
                    + (alpha_m + beta) * C(i + 1);
        }

        // BC at r = 0: symmetry (dC/dr = 0)
        a_coeff(0) = 0.0;
        b_coeff(0) = 1.0;
        c_coeff(0) = -1.0;
        rhs(0) = 0.0;

        // BC at r = R: flux boundary
        double flux_t = (t < surface_flux.size()) ? surface_flux(t) : 0.0;
        a_coeff(n_radial - 1) = -1.0;
        b_coeff(n_radial - 1) = 1.0;
        c_coeff(n_radial - 1) = 0.0;
        rhs(n_radial - 1) = flux_t * dr / D_cm2s;

        // Solve
        C = thomas_solve(a_coeff, b_coeff, c_coeff, rhs);

        // Clamp
        double C_max_cm3 = C_max_M * 1e-3;
        for (int i = 0; i < n_radial; ++i) {
            C(i) = std::clamp(C(i), 0.0, C_max_cm3);
        }

        C_surface(t) = C(n_radial - 1);
    }

    return C_surface;
}

}  // namespace raman
