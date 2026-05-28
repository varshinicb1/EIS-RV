//! Diffusion Solver — Crank-Nicolson finite difference for Fick's 2nd law.
//!
//! 1D Planar:    dC/dt = D * d^2C/dx^2
//! Spherical:    dC/dt = D/r^2 * d/dr(r^2 * dC/dr)
//!
//! Both use the tridiagonal Thomas algorithm (O(n)) per time step.

use std::f64::consts::PI;

/// Thomas algorithm (tridiagonal solver) — O(n) per call
fn thomas_solve(a: &[f64], b: &[f64], c: &[f64], d: &[f64]) -> Vec<f64> {
    let n = d.len();
    let mut cp = vec![0.0; n];
    let mut dp = vec![0.0; n];
    let mut x = vec![0.0; n];

    // Forward sweep
    cp[0] = c[0] / b[0];
    dp[0] = d[0] / b[0];
    for i in 1..n {
        let m = b[i] - a[i] * cp[i - 1];
        let m = if m.abs() < 1e-30 { 1e-30 } else { m };
        cp[i] = if i < n - 1 { c[i] / m } else { 0.0 };
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m;
    }

    // Back substitution
    x[n - 1] = dp[n - 1];
    for i in (0..n - 1).rev() {
        x[i] = dp[i] - cp[i] * x[i + 1];
    }
    x
}

/// 1D planar diffusion (Crank-Nicolson)
pub fn solve_diffusion_1d(
    d_cm2s: f64,
    c_bulk_m: f64,
    l_cm: f64,
    n_spatial: usize,
    n_time: usize,
    dt_s: f64,
    surface_flux: &[f64],
) -> Vec<f64> {
    let dx = l_cm / (n_spatial as f64 - 1.0);
    let r = d_cm2s * dt_s / (2.0 * dx * dx); // Crank-Nicolson parameter

    // Initialize concentration profile
    let c_init = c_bulk_m * 1e-3; // mol/cm^3
    let mut c = vec![c_init; n_spatial];

    // Tridiagonal coefficients (constant for uniform grid)
    let mut a_coeff = vec![-r; n_spatial];
    let mut b_coeff = vec![1.0 + 2.0 * r; n_spatial];
    let c_coeff = vec![-r; n_spatial];

    // Boundary adjustments
    a_coeff[0] = 0.0;

    let mut rhs = vec![0.0; n_spatial];

    for t in 0..n_time {
        // Build RHS from explicit part
        for i in 1..(n_spatial - 1) {
            rhs[i] = r * c[i - 1] + (1.0 - 2.0 * r) * c[i] + r * c[i + 1];
        }

        // x = 0: flux boundary (electrode surface)
        let flux_t = if t < surface_flux.len() {
            surface_flux[t]
        } else {
            0.0
        };
        rhs[0] = c[0] - flux_t * dx / d_cm2s; // Neumann BC
        b_coeff[0] = 1.0;

        // x = L: bulk concentration (Dirichlet)
        rhs[n_spatial - 1] = c_bulk_m * 1e-3;
        b_coeff[n_spatial - 1] = 1.0;

        // Solve tridiagonal system
        c = thomas_solve(&a_coeff, &b_coeff, &c_coeff, &rhs);

        // Clamp to physical range
        for ci in c.iter_mut() {
            *ci = ci.max(0.0);
        }
    }

    c
}

/// Spherical diffusion (Single Particle Model)
pub fn solve_spherical_diffusion(
    d_cm2s: f64,
    c_max_m: f64,
    c_init_frac: f64,
    radius_um: f64,
    n_radial: usize,
    n_time: usize,
    dt_s: f64,
    surface_flux: &[f64],
) -> Vec<f64> {
    let r_cm = radius_um * 1e-4; // um -> cm
    let dr = r_cm / (n_radial as f64 - 1.0);

    // Radial grid
    let r_grid: Vec<f64> = (0..n_radial)
        .map(|i| if i == 0 { dr * 0.01 } else { i as f64 * dr })
        .collect();

    // Initialize: uniform concentration
    let c_init = c_max_m * c_init_frac * 1e-3; // mol/cm^3
    let mut c = vec![c_init; n_radial];

    // Output: surface concentration at each time step
    let mut c_surface = vec![0.0; n_time];

    let mut a_coeff = vec![0.0; n_radial];
    let mut b_coeff = vec![0.0; n_radial];
    let mut c_coeff_arr = vec![0.0; n_radial];
    let mut rhs = vec![0.0; n_radial];

    for t in 0..n_time {
        // Build tridiagonal system for spherical Crank-Nicolson
        for i in 1..(n_radial - 1) {
            let ri = r_grid[i];
            let alpha_m = d_cm2s * dt_s / (2.0 * dr * dr);
            let beta = d_cm2s * dt_s / (2.0 * ri * dr);

            a_coeff[i] = -(alpha_m - beta);
            b_coeff[i] = 1.0 + 2.0 * alpha_m;
            c_coeff_arr[i] = -(alpha_m + beta);

            // RHS: explicit part
            rhs[i] = (alpha_m - beta) * c[i - 1]
                + (1.0 - 2.0 * alpha_m) * c[i]
                + (alpha_m + beta) * c[i + 1];
        }

        // BC at r = 0: symmetry (dC/dr = 0)
        a_coeff[0] = 0.0;
        b_coeff[0] = 1.0;
        c_coeff_arr[0] = -1.0;
        rhs[0] = 0.0;

        // BC at r = R: flux boundary
        let flux_t = if t < surface_flux.len() {
            surface_flux[t]
        } else {
            0.0
        };
        a_coeff[n_radial - 1] = -1.0;
        b_coeff[n_radial - 1] = 1.0;
        c_coeff_arr[n_radial - 1] = 0.0;
        rhs[n_radial - 1] = flux_t * dr / d_cm2s;

        // Solve
        c = thomas_solve(&a_coeff, &b_coeff, &c_coeff_arr, &rhs);

        // Clamp
        for ci in c.iter_mut() {
            *ci = ci.max(0.0);
        }

        // Record surface concentration
        c_surface[t] = c[n_radial - 1];
    }

    c_surface
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_thomas_solve_identity() {
        // Solve I*x = [1,2,3]
        let a = vec![0.0, 0.0, 0.0];
        let b = vec![1.0, 1.0, 1.0];
        let c = vec![0.0, 0.0, 0.0];
        let d = vec![1.0, 2.0, 3.0];
        let x = thomas_solve(&a, &b, &c, &d);
        assert!((x[0] - 1.0).abs() < 1e-10);
        assert!((x[1] - 2.0).abs() < 1e-10);
        assert!((x[2] - 3.0).abs() < 1e-10);
    }

    #[test]
    fn test_1d_diffusion_bulk_preserved() {
        // With no flux, concentration should stay at bulk
        let flux = vec![0.0; 100];
        let c = solve_diffusion_1d(1e-5, 1.0, 0.1, 50, 100, 1e-3, &flux);
        // Bulk end should be close to 1e-3 mol/cm^3
        assert!((c[49] - 1e-3).abs() < 1e-4);
    }
}
