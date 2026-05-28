use crate::types::*;
use num_complex::Complex64;
use ndarray::Array1;

fn warburg_semi_infinite(omega: f64, sigma_w: f64) -> Complex64 {
    if sigma_w < 1e-6 || omega < 1e-12 {
        return Complex64::new(0.0, 0.0);
    }
    let sqrt_omega = omega.sqrt();
    Complex64::new(sigma_w / sqrt_omega, -sigma_w / sqrt_omega)
}

fn warburg_bounded(omega: f64, sigma_w: f64, L_um: f64, D_cm2s: f64) -> Complex64 {
    if sigma_w < 1e-6 || omega < 1e-12 {
        return Complex64::new(0.0, 0.0);
    }
    let L_cm = L_um * 1e-4;
    let tau_d = (L_cm * L_cm) / D_cm2s.max(1e-12);
    let wt = omega * tau_d;
    let sqrt_wt = wt.sqrt();
    let x = Complex64::new(sqrt_wt / 2f64.sqrt(), sqrt_wt / 2f64.sqrt());
    let tanh_x = if x.norm() > 20.0 {
        Complex64::new(1.0, 0.0)
    } else {
        x.tanh()
    };
    let denom = x + Complex64::new(1e-30, 0.0);
    sigma_w * tanh_x / denom
}

pub fn randles_impedance(frequencies: &Array1<f64>, p: &EISParams) -> Array1<Complex64> {
    let n = frequencies.len();
    let mut z = Array1::zeros(n);

    for (i, z_i) in z.iter_mut().enumerate() {
        let f = frequencies[i];
        let omega = 2.0 * PI * f;
        let omega_n = omega.powf(p.n_cpe);
        let phase = p.n_cpe * PI / 2.0;
        let y_cpe = Complex64::new(
            p.Cdl * omega_n * phase.cos(),
            p.Cdl * omega_n * phase.sin(),
        );
        let z_w = if p.bounded_w {
            warburg_bounded(omega, p.sigma_w, p.diff_len_um, p.diff_coeff)
        } else {
            warburg_semi_infinite(omega, p.sigma_w)
        };
        let z_faradaic = Complex64::new(p.Rct, 0.0) + z_w;
        let z_parallel = Complex64::new(1.0, 0.0)
            / (y_cpe + Complex64::new(1.0, 0.0) / z_faradaic);
        *z_i = Complex64::new(p.Rs, 0.0) + z_parallel;
    }

    z
}

pub fn simulate_eis(
    params: &EISParams,
    f_min: f64,
    f_max: f64,
    n_points: usize,
) -> EISResult {
    let mut frequencies = Array1::zeros(n_points);
    let log_fmin = f_min.log10();
    let log_fmax = f_max.log10();
    let step = (log_fmax - log_fmin) / (n_points as f64 - 1.0);

    for i in 0..n_points {
        frequencies[i] = 10f64.powf(log_fmin + i as f64 * step);
    }

    let z = randles_impedance(&frequencies, params);

    let mut z_real = Array1::zeros(n_points);
    let mut z_imag = Array1::zeros(n_points);
    let mut z_mag = Array1::zeros(n_points);
    let mut z_phase = Array1::zeros(n_points);

    for i in 0..n_points {
        z_real[i] = z[i].re;
        z_imag[i] = z[i].im;
        z_mag[i] = z[i].norm();
        z_phase[i] = z[i].arg().to_degrees();
    }

    EISResult {
        frequencies,
        Z_real: z_real,
        Z_imag: z_imag,
        Z_magnitude: z_mag,
        Z_phase: z_phase,
        params: params.clone(),
    }
}
