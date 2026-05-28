use crate::types::*;
use ndarray::{Array1, Array2};

fn build_drt_matrix(
    frequencies: &Array1<f64>,
    tau: &Array1<f64>,
) -> (Array2<f64>, Array2<f64>, f64) {
    let m = frequencies.len();
    let n = tau.len();
    let d_ln_tau = if n > 1 {
        (tau[n - 1].ln() - tau[0].ln()) / (n as f64 - 1.0)
    } else {
        1.0
    };

    let mut a_re = Array2::zeros((m, n));
    let mut a_im = Array2::zeros((m, n));

    for (i, mut row_re) in a_re.axis_iter_mut(ndarray::Axis(0)).enumerate() {
        let omega = 2.0 * PI * frequencies[i];
        for j in 0..n {
            let wt = omega * tau[j];
            let denom = 1.0 + wt * wt;
            row_re[j] = d_ln_tau / denom;
        }
    }

    for (i, mut row_im) in a_im.axis_iter_mut(ndarray::Axis(0)).enumerate() {
        let omega = 2.0 * PI * frequencies[i];
        for j in 0..n {
            let wt = omega * tau[j];
            let denom = 1.0 + wt * wt;
            row_im[j] = -d_ln_tau * wt / denom;
        }
    }

    (a_re, a_im, d_ln_tau)
}

fn build_l_matrix(n: usize) -> Array2<f64> {
    let mut l = Array2::zeros((n - 2, n));
    for i in 0..(n - 2) {
        l[[i, i]] = 1.0;
        l[[i, i + 1]] = -2.0;
        l[[i, i + 2]] = 1.0;
    }
    l
}

fn project_nonneg(x: &mut Array1<f64>) {
    for val in x.iter_mut() {
        if *val < 0.0 {
            *val = 0.0;
        }
    }
}

fn solve_ldlt_system(a: &Array2<f64>, b: &Array1<f64>) -> Array1<f64> {
    let n = a.nrows();
    let mut x = b.clone();

    let mut l = Array2::<f64>::eye(n);
    let mut d = Array1::<f64>::zeros(n);

    for j in 0..n {
        let mut sum = a[[j, j]];
        for k in 0..j {
            sum -= l[[j, k]] * l[[j, k]] * d[k];
        }
        d[j] = sum;

        for i in (j + 1)..n {
            let mut sum2 = a[[i, j]];
            for k in 0..j {
                sum2 -= l[[i, k]] * l[[j, k]] * d[k];
            }
            l[[i, j]] = sum2 / d[j];
        }
    }

    let mut y = b.clone();
    for i in 0..n {
        for j in 0..i {
            y[i] -= l[[i, j]] * y[j];
        }
    }

    let mut z = y.clone();
    for i in 0..n {
        z[i] /= d[i];
    }

    for i in (0..n).rev() {
        for j in (i + 1)..n {
            z[i] -= l[[j, i]] * z[j];
        }
        x[i] = z[i];
    }

    x
}

pub fn compute_drt(
    frequencies: &Array1<f64>,
    z_real: &Array1<f64>,
    z_imag: &Array1<f64>,
    params: &DRTParams,
) -> DRTResult {
    let m = frequencies.len();
    let n = params.n_tau;

    let mut tau = Array1::zeros(n);
    let log_tmin = params.tau_min.log10();
    let log_tmax = params.tau_max.log10();
    let log_step = (log_tmax - log_tmin) / (n as f64 - 1.0);
    for i in 0..n {
        tau[i] = 10f64.powf(log_tmin + i as f64 * log_step);
    }

    let mut idx_max_f = 0;
    for i in 1..m {
        if frequencies[i] > frequencies[idx_max_f] {
            idx_max_f = i;
        }
    }
    let r_inf = z_real[idx_max_f];

    let z_re_shifted: Array1<f64> = z_real - r_inf;

    let (a_re, a_im, d_ln_tau) = build_drt_matrix(frequencies, &tau);

    let mut a = Array2::zeros((2 * m, n));
    for i in 0..m {
        for j in 0..n {
            a[[i, j]] = a_re[[i, j]];
            a[[m + i, j]] = a_im[[i, j]];
        }
    }

    let mut b_vec = Array1::zeros(2 * m);
    for i in 0..m {
        b_vec[i] = z_re_shifted[i];
        b_vec[m + i] = z_imag[i];
    }

    let l = build_l_matrix(n);
    let at = a.t();
    let ata = at.dot(&a);
    let lt = l.t();
    let ltl = lt.dot(&l);
    let atb = at.dot(&b_vec);

    let mut h = ata.clone();
    for i in 0..n {
        for j in 0..n {
            h[[i, j]] += params.lambda * params.lambda * ltl[[i, j]];
        }
    }

    let mut gamma = solve_ldlt_system(&h, &atb);

    if params.non_negative {
        project_nonneg(&mut gamma);

        let step_size = 1.0 / h.diag().iter().cloned().fold(0.0, f64::max);
        for _ in 0..params.max_iter {
            let grad = h.dot(&gamma) - &atb;
            let mut gamma_new = &gamma - step_size * &grad;
            project_nonneg(&mut gamma_new);
            let delta = (&gamma_new - &gamma).iter().map(|&x| x * x).sum::<f64>().sqrt();
            gamma = gamma_new;
            if delta < 1e-10 * n as f64 {
                break;
            }
        }
    }

    let mut z_fit_real = Array1::zeros(m);
    let mut z_fit_imag = Array1::zeros(m);
    let z_re_fit = a_re.dot(&gamma);
    let z_im_fit = a_im.dot(&gamma);
    for i in 0..m {
        z_fit_real[i] = z_re_fit[i] + r_inf;
        z_fit_imag[i] = z_im_fit[i];
    }

    let r_pol = gamma.sum() * d_ln_tau;

    let resid = &b_vec - a.dot(&gamma);
    let residual = resid.iter().map(|&x| x * x).sum::<f64>() / (2.0 * m as f64);

    DRTResult {
        tau,
        gamma,
        Z_fit_real: z_fit_real,
        Z_fit_imag: z_fit_imag,
        R_inf: r_inf,
        R_pol: r_pol,
        residual,
        lambda_used: params.lambda,
    }
}

pub fn kramers_kronig_test(
    frequencies: &Array1<f64>,
    z_real: &Array1<f64>,
    z_imag: &Array1<f64>,
    n_rc: i32,
) -> KKResult {
    let m = frequencies.len();
    if m < 2 || z_real.len() != m || z_imag.len() != m {
        return KKResult::default();
    }

    let mut n_rc = n_rc as usize;
    if n_rc <= 0 {
        n_rc = m;
    }
    n_rc = n_rc.max(2).min(m);

    let tau_min = 1.0 / (2.0 * PI * frequencies.iter().cloned().fold(0.0, f64::max) * 10.0);
    let tau_max = 10.0 / (2.0 * PI * frequencies.iter().cloned().fold(f64::MAX, f64::min));

    let mut tau = Array1::zeros(n_rc);
    let log_tau_min = tau_min.ln();
    let log_tau_max = tau_max.ln();
    for k in 0..n_rc {
        let frac = k as f64 / (n_rc as f64 - 1.0);
        tau[k] = (log_tau_min + frac * (log_tau_max - log_tau_min)).exp();
    }

    let mut a = Array2::zeros((2 * m, n_rc + 1));
    let mut b_vec = Array1::zeros(2 * m);
    for i in 0..m {
        let omega = 2.0 * PI * frequencies[i];
        for k in 0..n_rc {
            let wt = omega * tau[k];
            let denom = 1.0 + wt * wt;
            a[[i, k]] = 1.0 / denom;
            a[[m + i, k]] = -wt / denom;
        }
        a[[i, n_rc]] = 1.0;
        a[[m + i, n_rc]] = 0.0;
        b_vec[i] = z_real[i];
        b_vec[m + i] = z_imag[i];
    }

    let x = solve_ldlt_system(&a.t().dot(&a), &a.t().dot(&b_vec));
    let r = x.slice(ndarray::s![0..n_rc]).to_owned();
    let r_inf = x[n_rc];

    let fit = a.dot(&x);
    let mut z_fit_real = Array1::zeros(m);
    let mut z_fit_imag = Array1::zeros(m);
    let mut residual_real = Array1::zeros(m);
    let mut residual_imag = Array1::zeros(m);
    let mut mean_sq = 0.0;

    for i in 0..m {
        z_fit_real[i] = fit[i];
        z_fit_imag[i] = fit[m + i];
        let mag = (z_real[i] * z_real[i] + z_imag[i] * z_imag[i]).sqrt();
        let mag_safe = mag.max(1e-30);
        residual_real[i] = (z_real[i] - z_fit_real[i]) / mag_safe;
        residual_imag[i] = (z_imag[i] - z_fit_imag[i]) / mag_safe;
        mean_sq += residual_real[i] * residual_real[i] + residual_imag[i] * residual_imag[i];
    }

    let max_rr = residual_real.iter().map(|&x| x.abs()).fold(0.0, f64::max);
    let max_ri = residual_imag.iter().map(|&x| x.abs()).fold(0.0, f64::max);
    let mean_residual = (mean_sq / (2.0 * m as f64)).sqrt();

    let mut sum_neg = 0.0;
    let mut sum_pos = 0.0;
    for k in 0..n_rc {
        if r[k] < 0.0 {
            sum_neg += -r[k];
        } else {
            sum_pos += r[k];
        }
    }

    let mu = if sum_pos > 0.0 {
        (1.0 - sum_neg / sum_pos).max(0.0).min(1.0)
    } else {
        0.0
    };

    let is_valid = mu >= 0.85 && max_rr < 0.05 && max_ri < 0.05;

    KKResult {
        is_valid,
        mu,
        residual_real,
        residual_imag,
        max_residual_real: max_rr,
        max_residual_imag: max_ri,
        mean_residual,
        Z_fit_real: z_fit_real,
        Z_fit_imag: z_fit_imag,
        tau,
        R: r,
        R_inf: r_inf,
        n_rc_used: n_rc as i32,
    }
}
