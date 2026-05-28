//! Circuit Fitter — CNLS via Levenberg-Marquardt.
//!
//! Reference: Boukamp, Solid State Ionics 20 (1986) 31-44

use super::types::{CircuitType, FitParams, FitResult, MatD, VecD};
use nalgebra::DVector;
use std::f64::consts::PI;

/// Randles circuit model: Z = Rs + 1/(Y_CPE + 1/(Rct + Z_W))
/// params: [Rs, Rct, Q0, n_cpe, sigma_w]
fn randles_model(frequencies: &[f64], p: &[f64]) -> (Vec<f64>, Vec<f64>) {
    let m = frequencies.len();
    let mut z_re = vec![0.0; m];
    let mut z_im = vec![0.0; m];

    let (rs, rct, q0, n, sigma) = (p[0], p[1], p[2], p[3], p[4]);

    for mi in 0..m {
        let w = 2.0 * PI * frequencies[mi];

        // Warburg: Zw = sigma*(1-j)/sqrt(w)
        let sw = sigma / w.sqrt();
        let (zw_re, zw_im) = (sw, -sw);

        // Faradaic: Zf = Rct + Zw
        let (zf_re, zf_im) = (rct + zw_re, zw_im);

        // CPE admittance: Y_cpe = Q0*(jw)^n
        let wn = w.powf(n);
        let yc_re = q0 * wn * (n * PI / 2.0).cos();
        let yc_im = q0 * wn * (n * PI / 2.0).sin();

        // Faradaic admittance: Y_f = 1/Zf
        let d = zf_re * zf_re + zf_im * zf_im;
        let (yf_re, yf_im) = (zf_re / d, -zf_im / d);

        // Total parallel admittance
        let (yt_re, yt_im) = (yc_re + yf_re, yc_im + yf_im);

        // Z_parallel = 1/Y_total
        let d2 = yt_re * yt_re + yt_im * yt_im;
        z_re[mi] = rs + yt_re / d2;
        z_im[mi] = -yt_im / d2;
    }

    (z_re, z_im)
}

/// Simple R-RC model: params = [Rs, R1, C1]
fn r_rc_model(frequencies: &[f64], p: &[f64]) -> (Vec<f64>, Vec<f64>) {
    let m = frequencies.len();
    let mut z_re = vec![0.0; m];
    let mut z_im = vec![0.0; m];

    let (rs, r1, c1) = (p[0], p[1], p[2]);

    for mi in 0..m {
        let w = 2.0 * PI * frequencies[mi];
        let wrc = w * r1 * c1;
        let d = 1.0 + wrc * wrc;
        z_re[mi] = rs + r1 / d;
        z_im[mi] = -r1 * wrc / d;
    }

    (z_re, z_im)
}

/// R-RC-RC model: params = [Rs, R1, C1, R2, C2]
fn r_rc_rc_model(frequencies: &[f64], p: &[f64]) -> (Vec<f64>, Vec<f64>) {
    let m = frequencies.len();
    let mut z_re = vec![0.0; m];
    let mut z_im = vec![0.0; m];

    let (rs, r1, c1, r2, c2) = (p[0], p[1], p[2], p[3], p[4]);

    for mi in 0..m {
        let w = 2.0 * PI * frequencies[mi];
        let wrc1 = w * r1 * c1;
        let d1 = 1.0 + wrc1 * wrc1;
        let wrc2 = w * r2 * c2;
        let d2 = 1.0 + wrc2 * wrc2;
        z_re[mi] = rs + r1 / d1 + r2 / d2;
        z_im[mi] = -r1 * wrc1 / d1 - r2 * wrc2 / d2;
    }

    (z_re, z_im)
}

/// Forward model dispatcher
fn compute_model(ct: CircuitType, freq: &[f64], p: &[f64]) -> (Vec<f64>, Vec<f64>) {
    match ct {
        CircuitType::Randles => randles_model(freq, p),
        CircuitType::RRc => r_rc_model(freq, p),
        CircuitType::RRcRc => r_rc_rc_model(freq, p),
    }
}

/// Get parameter names for a circuit type
fn param_names(ct: CircuitType) -> Vec<String> {
    match ct {
        CircuitType::Randles => vec![
            "Rs".into(), "Rct".into(), "Q0".into(), "n_CPE".into(), "sigma_W".into(),
        ],
        CircuitType::RRc => vec!["Rs".into(), "R1".into(), "C1".into()],
        CircuitType::RRcRc => vec![
            "Rs".into(), "R1".into(), "C1".into(), "R2".into(), "C2".into(),
        ],
    }
}

/// Numerical Jacobian (central finite differences)
fn compute_jacobian(ct: CircuitType, freq: &[f64], p: &[f64], m: usize) -> MatD {
    let n = p.len();
    let mut j = MatD::zeros(2 * m, n);

    for ji in 0..n {
        let mut pp = p.to_vec();
        let mut pm = p.to_vec();
        let h = 1e-8_f64.max(p[ji].abs() * 1e-6);
        pp[ji] += h;
        pm[ji] -= h;

        let (zr_p, zi_p) = compute_model(ct, freq, &pp);
        let (zr_m, zi_m) = compute_model(ct, freq, &pm);

        for mi in 0..m {
            j[(mi, ji)] = (zr_p[mi] - zr_m[mi]) / (2.0 * h);
            j[(m + mi, ji)] = (zi_p[mi] - zi_m[mi]) / (2.0 * h);
        }
    }
    j
}

/// Main Levenberg-Marquardt circuit fitter
pub fn fit_circuit(
    frequencies: &[f64],
    z_real: &[f64],
    z_imag: &[f64],
    initial: &[f64],
    params: &FitParams,
) -> FitResult {
    let m = frequencies.len();
    let n = initial.len();

    let mut p = initial.to_vec();
    let mut lambda = params.lambda_init;

    // Compute initial residual
    let (mut zr_calc, mut zi_calc) = compute_model(params.circuit, frequencies, &p);

    let mut r = DVector::zeros(2 * m);
    for mi in 0..m {
        r[mi] = z_real[mi] - zr_calc[mi];
        r[m + mi] = z_imag[mi] - zi_calc[mi];
    }
    let mut chi2 = r.norm_squared();

    let mut converged = false;
    let mut iter = 0;

    for it in 0..params.max_iter {
        iter = it + 1;

        let j = compute_jacobian(params.circuit, frequencies, &p, m);

        // Normal equations: (J^T*J + lambda*diag(J^T*J)) dp = J^T*r
        let jt_j = j.transpose() * &j;
        let jt_r = j.transpose() * &r;

        // Damping: add lambda * diag(J^T*J)
        let mut h = jt_j.clone();
        for i in 0..n {
            h[(i, i)] += lambda * jt_j[(i, i)].max(1e-10);
        }

        // Solve for step
        let dp = h
            .clone()
            .cholesky()
            .map(|chol| chol.solve(&jt_r))
            .unwrap_or_else(|| h.lu().solve(&jt_r).unwrap_or_else(|| DVector::zeros(n)));

        // Trial parameters (enforce positivity for physical params)
        let mut p_trial = p.clone();
        for i in 0..n {
            p_trial[i] += dp[i];
            if p_trial[i] < 1e-15 {
                p_trial[i] = p[i] * 0.1; // don't let it go negative
            }
        }

        // Evaluate trial
        let (zr_trial, zi_trial) = compute_model(params.circuit, frequencies, &p_trial);
        let mut r_trial = DVector::zeros(2 * m);
        for mi in 0..m {
            r_trial[mi] = z_real[mi] - zr_trial[mi];
            r_trial[m + mi] = z_imag[mi] - zi_trial[mi];
        }
        let chi2_trial = r_trial.norm_squared();

        if chi2_trial < chi2 {
            // Accept step
            p = p_trial;
            zr_calc = zr_trial;
            zi_calc = zi_trial;
            r = r_trial;
            chi2 = chi2_trial;
            lambda *= 0.1;

            // Check convergence
            if dp.norm() < params.tol * (1.0 + DVector::from_column_slice(&p).norm()) {
                converged = true;
                break;
            }
        } else {
            // Reject step, increase damping
            lambda *= 10.0;
            if lambda > 1e16 {
                break;
            }
        }
    }

    // Compute final residuals
    let residual_re: Vec<f64> = (0..m).map(|i| z_real[i] - zr_calc[i]).collect();
    let residual_im: Vec<f64> = (0..m).map(|i| z_imag[i] - zi_calc[i]).collect();

    FitResult {
        params: p,
        chi_squared: chi2,
        iterations: iter,
        converged,
        z_fit_real: zr_calc,
        z_fit_imag: zi_calc,
        residual_re,
        residual_im,
        param_names: param_names(params.circuit),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::eis_solver::simulate_eis;
    use crate::engine::types::EISParams;

    #[test]
    fn test_randles_fit_recovers_params() {
        // Generate data from known parameters
        let true_params = EISParams {
            rs: 15.0,
            rct: 80.0,
            cdl: 2e-5,
            sigma_w: 30.0,
            n_cpe: 0.85,
            ..Default::default()
        };
        let eis = simulate_eis(&true_params, 0.01, 1e6, 50);

        // Fit with slightly off initial guesses
        let initial = [10.0, 100.0, 1e-5, 0.9, 50.0];
        let fit_params = FitParams {
            circuit: CircuitType::Randles,
            ..Default::default()
        };

        let result = fit_circuit(
            &eis.frequencies,
            &eis.z_real,
            &eis.z_imag,
            &initial,
            &fit_params,
        );

        assert!(result.converged, "Fit should converge");
        // Rs should be close to 15
        assert!(
            (result.params[0] - 15.0).abs() < 2.0,
            "Rs = {} should be close to 15",
            result.params[0]
        );
    }
}
