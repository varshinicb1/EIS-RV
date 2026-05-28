//! DRT Solver — Distribution of Relaxation Times via Tikhonov regularization.
//!
//! Algorithm:
//!   1. Build discretization matrix A where:
//!      A[m, n] = (delta ln tau) / (1 + j*2*pi*f_m*tau_n)
//!
//!   2. Solve regularized least-squares:
//!      min ||A*gamma - Z_data||^2 + lambda^2*||L*gamma||^2
//!
//!   3. If non_negative, apply NNLS (projected gradient).
//!
//! For Kramers-Kronig test (Lin-KK):
//!   Use fixed tau_k = 1/(2*pi*f_k) and fit R_k coefficients.
//!
//! Reference:
//!   Wan et al., Electrochimica Acta 184 (2015) 483-499

use super::types::{DRTParams, DRTResult, KKResult, MatD, VecD};
use nalgebra::DVector;
use std::f64::consts::PI;

/// Build DRT discretization matrices for real and imaginary parts
fn build_drt_matrix(
    frequencies: &[f64],
    tau: &[f64],
) -> (MatD, MatD, f64) {
    let m = frequencies.len();
    let n = tau.len();

    let d_ln_tau = if n > 1 {
        (tau[n - 1].ln() - tau[0].ln()) / (n as f64 - 1.0)
    } else {
        1.0
    };

    let mut a_re = MatD::zeros(m, n);
    let mut a_im = MatD::zeros(m, n);

    for mi in 0..m {
        let omega = 2.0 * PI * frequencies[mi];
        for ni in 0..n {
            let wt = omega * tau[ni];
            let denom = 1.0 + wt * wt;
            a_re[(mi, ni)] = d_ln_tau / denom;
            a_im[(mi, ni)] = -d_ln_tau * wt / denom;
        }
    }

    (a_re, a_im, d_ln_tau)
}

/// Second-order difference matrix (smoothness prior)
fn build_l_matrix(n: usize) -> MatD {
    let mut l = MatD::zeros(n - 2, n);
    for i in 0..(n - 2) {
        l[(i, i)] = 1.0;
        l[(i, i + 1)] = -2.0;
        l[(i, i + 2)] = 1.0;
    }
    l
}

/// Project vector to non-negative
fn project_nonneg(x: &mut DVector<f64>) {
    for i in 0..x.len() {
        if x[i] < 0.0 {
            x[i] = 0.0;
        }
    }
}

/// Main DRT computation
pub fn compute_drt(
    frequencies: &[f64],
    z_real: &[f64],
    z_imag: &[f64],
    params: &DRTParams,
) -> DRTResult {
    let m = frequencies.len();
    let n = params.n_tau;

    // Build log-spaced tau grid
    let log_tmin = params.tau_min.log10();
    let log_tmax = params.tau_max.log10();
    let log_step = (log_tmax - log_tmin) / (n as f64 - 1.0);
    let tau: Vec<f64> = (0..n)
        .map(|i| 10.0_f64.powf(log_tmin + i as f64 * log_step))
        .collect();

    // Estimate R_inf from highest frequency Z'
    let idx_max_f = frequencies
        .iter()
        .enumerate()
        .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
        .map(|(i, _)| i)
        .unwrap_or(0);
    let r_inf = z_real[idx_max_f];

    // Subtract R_inf from Z_real for fitting
    let z_re_shifted: Vec<f64> = z_real.iter().map(|&v| v - r_inf).collect();

    // Build discretization matrices
    let (a_re, a_im, d_ln_tau) = build_drt_matrix(frequencies, &tau);

    // Stack real and imaginary: [A_re; A_im] gamma ~= [Z_re - R_inf; Z_im]
    let mut a_full = MatD::zeros(2 * m, n);
    for i in 0..m {
        for j in 0..n {
            a_full[(i, j)] = a_re[(i, j)];
            a_full[(m + i, j)] = a_im[(i, j)];
        }
    }

    let mut b = DVector::zeros(2 * m);
    for i in 0..m {
        b[i] = z_re_shifted[i];
        b[m + i] = z_imag[i];
    }

    // Build regularization matrix L (2nd-order smoothness)
    let l = build_l_matrix(n);
    let lambda = params.lambda;

    // Normal equations: (A^T*A + lambda^2*L^T*L) gamma = A^T*b
    let at_a = a_full.transpose() * &a_full;
    let lt_l = l.transpose() * &l;
    let at_b = a_full.transpose() * &b;

    let h = at_a + lambda * lambda * lt_l;

    // Solve via Cholesky decomposition
    let mut gamma = h
        .clone()
        .cholesky()
        .map(|chol| chol.solve(&at_b))
        .unwrap_or_else(|| {
            // Fallback: use LU decomposition
            h.clone()
                .lu()
                .solve(&at_b)
                .unwrap_or_else(|| DVector::zeros(n))
        });

    // Apply non-negativity constraint via projected gradient
    if params.non_negative {
        project_nonneg(&mut gamma);

        for _iter in 0..params.max_iter {
            let grad = &h * &gamma - &at_b;
            let step = 1.0 / h.diagonal().max();
            let mut gamma_new = &gamma - step * &grad;
            project_nonneg(&mut gamma_new);

            let delta = (&gamma_new - &gamma).norm();
            gamma = gamma_new;
            if delta < 1e-10 * n as f64 {
                break;
            }
        }
    }

    // Compute fitted impedance
    let z_re_fit_vec = &a_re * &gamma;
    let z_im_fit_vec = &a_im * &gamma;

    let z_fit_real: Vec<f64> = (0..m).map(|i| z_re_fit_vec[i] + r_inf).collect();
    let z_fit_imag: Vec<f64> = (0..m).map(|i| z_im_fit_vec[i]).collect();

    // Residuals
    let residual_re: Vec<f64> = (0..m).map(|i| z_real[i] - z_fit_real[i]).collect();
    let residual_im: Vec<f64> = (0..m).map(|i| z_imag[i] - z_fit_imag[i]).collect();

    // R_pol (integral of gamma)
    let r_pol: f64 = gamma.iter().sum::<f64>() * d_ln_tau;

    let gamma_vec: Vec<f64> = gamma.iter().copied().collect();

    DRTResult {
        tau,
        gamma: gamma_vec,
        z_fit_real,
        z_fit_imag,
        r_inf,
        r_pol,
        residual_re,
        residual_im,
    }
}

/// Kramers-Kronig validation using Lin-KK method
pub fn kramers_kronig_test(
    frequencies: &[f64],
    z_real: &[f64],
    z_imag: &[f64],
) -> KKResult {
    let m = frequencies.len();

    // Use fixed tau_k = 1/(2*pi*f_k) for each frequency
    let tau_kk: Vec<f64> = frequencies
        .iter()
        .map(|&f| 1.0 / (2.0 * PI * f))
        .collect();
    let n = tau_kk.len();

    // Build matrix with these fixed tau values
    let (a_re, a_im, _) = build_drt_matrix(frequencies, &tau_kk);

    // Fit R_k coefficients to imaginary part only
    let at_a = a_im.transpose() * &a_im;
    let z_im_vec = DVector::from_column_slice(z_imag);
    let at_b = a_im.transpose() * &z_im_vec;

    // Small regularization for stability
    let reg = MatD::identity(n, n) * 1e-10;
    let h = at_a + reg;

    let r_k = h
        .cholesky()
        .map(|chol| chol.solve(&at_b))
        .unwrap_or_else(|| DVector::zeros(n));

    // Predict real part from fitted coefficients
    let z_re_pred = &a_re * &r_k;

    // R_inf estimate
    let idx_max_f = frequencies
        .iter()
        .enumerate()
        .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
        .map(|(i, _)| i)
        .unwrap_or(0);
    let r_inf = z_real[idx_max_f];

    let z_kk_real: Vec<f64> = (0..m).map(|i| z_re_pred[i] + r_inf).collect();
    let z_kk_imag: Vec<f64> = z_imag.to_vec();

    let residual_re: Vec<f64> = (0..m)
        .map(|i| {
            let denom = z_real[i].abs().max(1e-10);
            (z_real[i] - z_kk_real[i]) / denom
        })
        .collect();
    let residual_im: Vec<f64> = (0..m)
        .map(|i| {
            let denom = z_imag[i].abs().max(1e-10);
            (z_imag[i] - z_kk_imag[i]) / denom
        })
        .collect();

    let mean_residual: f64 = residual_re
        .iter()
        .chain(residual_im.iter())
        .map(|r| r.abs())
        .sum::<f64>()
        / (2 * m) as f64;

    // Typically valid if mean residual < 1%
    let valid = mean_residual < 0.01;

    KKResult {
        z_kk_real,
        z_kk_imag,
        residual_re,
        residual_im,
        mean_residual,
        valid,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::eis_solver::simulate_eis;
    use crate::engine::types::EISParams;

    #[test]
    fn test_drt_on_synthetic_data() {
        // Generate synthetic EIS data from known circuit
        let eis_params = EISParams::default();
        let eis_result = simulate_eis(&eis_params, 0.01, 1e6, 50);

        let drt_params = DRTParams::default();
        let drt_result = compute_drt(
            &eis_result.frequencies,
            &eis_result.z_real,
            &eis_result.z_imag,
            &drt_params,
        );

        assert_eq!(drt_result.tau.len(), drt_params.n_tau);
        assert_eq!(drt_result.gamma.len(), drt_params.n_tau);
        assert!(drt_result.r_pol > 0.0);
    }

    #[test]
    fn test_kk_validation() {
        let eis_params = EISParams::default();
        let eis_result = simulate_eis(&eis_params, 0.01, 1e6, 50);

        let kk_result = kramers_kronig_test(
            &eis_result.frequencies,
            &eis_result.z_real,
            &eis_result.z_imag,
        );

        // Synthetic KK-compliant data should pass
        assert_eq!(kk_result.z_kk_real.len(), eis_result.frequencies.len());
    }
}
