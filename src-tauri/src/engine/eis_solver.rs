//! EIS Solver — High-performance impedance computation for equivalent circuits.
//!
//! Core model: Modified Randles circuit
//!   Z(w) = Rs + 1 / (Y_CPE(jw) + 1/(Rct + Z_W(w)))
//!
//! Supports:
//!   - Semi-infinite Warburg: Z_W = sigma*(1-j)/sqrt(w)
//!   - Bounded Warburg:       Z_W = sigma*tanh(sqrt(jw*tau_d)) / sqrt(jw*tau_d)
//!   - CPE (constant phase element): Y = Q0*(jw)^n
//!
//! All frequency sweeps are parallelized via rayon.

use super::types::{Complex, EISParams, EISResult};
use rayon::prelude::*;
use std::f64::consts::PI;

/// Semi-infinite Warburg impedance: Z_W = sigma*(1-j)/sqrt(w)
pub fn warburg_semi_infinite(omega: f64, sigma_w: f64) -> Complex {
    if sigma_w < 1e-6 || omega < 1e-12 {
        return Complex::new(0.0, 0.0);
    }
    let sqrt_omega = omega.sqrt();
    Complex::new(sigma_w / sqrt_omega, -sigma_w / sqrt_omega)
}

/// Bounded (finite-length) Warburg impedance.
/// Z_W = sigma*tanh(sqrt(jw*tau_d)) / sqrt(jw*tau_d)
/// where tau_d = L^2/D
pub fn warburg_bounded(omega: f64, sigma_w: f64, l_um: f64, d_cm2s: f64) -> Complex {
    if sigma_w < 1e-6 || omega < 1e-12 {
        return Complex::new(0.0, 0.0);
    }

    let l_cm = l_um * 1e-4;
    let tau_d = (l_cm * l_cm) / d_cm2s.max(1e-12);

    // x = sqrt(jw*tau_d)
    // sqrt(j) = (1+j)/sqrt(2)
    let wt = omega * tau_d;
    let sqrt_wt = wt.sqrt();
    let x = Complex::new(sqrt_wt / 2.0_f64.sqrt(), sqrt_wt / 2.0_f64.sqrt());

    // tanh(x) — numerically stable for large |x|
    let tanh_x = if x.norm() > 20.0 {
        Complex::new(1.0, 0.0)
    } else {
        x.tanh()
    };

    // Z_W = sigma * tanh(x) / (x + eps)
    let denom = x + Complex::new(1e-30, 0.0);
    sigma_w * tanh_x / denom
}

/// Compute impedance of modified Randles circuit at given frequencies.
/// Parallelized over frequency points via rayon.
pub fn randles_impedance(frequencies: &[f64], params: &EISParams) -> Vec<Complex> {
    frequencies
        .par_iter()
        .map(|&f| {
            let omega = 2.0 * PI * f;

            // CPE admittance: Y_CPE = Q0*(jw)^n
            // (jw)^n = |w|^n * exp(j*n*pi/2)
            let omega_n = omega.powf(params.n_cpe);
            let phase = params.n_cpe * PI / 2.0;
            let y_cpe = params.cdl
                * Complex::new(omega_n * phase.cos(), omega_n * phase.sin());

            // Warburg impedance
            let z_w = if params.bounded_w {
                warburg_bounded(omega, params.sigma_w, params.diff_len_um, params.diff_coeff)
            } else {
                warburg_semi_infinite(omega, params.sigma_w)
            };

            // Faradaic impedance
            let z_faradaic = Complex::new(params.rct, 0.0) + z_w;

            // Parallel: Z_p = 1 / (Y_CPE + 1/Z_faradaic)
            let z_parallel =
                Complex::new(1.0, 0.0) / (y_cpe + Complex::new(1.0, 0.0) / z_faradaic);

            // Total: Z = Rs + Z_parallel
            Complex::new(params.rs, 0.0) + z_parallel
        })
        .collect()
}

/// Full EIS simulation: generates log-spaced frequencies + computes impedance.
pub fn simulate_eis(
    params: &EISParams,
    f_min: f64,
    f_max: f64,
    n_points: usize,
) -> EISResult {
    // Log-spaced frequency array
    let log_fmin = f_min.log10();
    let log_fmax = f_max.log10();
    let step = (log_fmax - log_fmin) / (n_points as f64 - 1.0);

    let frequencies: Vec<f64> = (0..n_points)
        .map(|i| 10.0_f64.powf(log_fmin + i as f64 * step))
        .collect();

    // Compute complex impedance
    let z = randles_impedance(&frequencies, params);

    // Extract components
    let z_real: Vec<f64> = z.iter().map(|c| c.re).collect();
    let z_imag: Vec<f64> = z.iter().map(|c| c.im).collect();
    let z_magnitude: Vec<f64> = z.iter().map(|c| c.norm()).collect();
    let z_phase: Vec<f64> = z
        .iter()
        .map(|c| c.im.atan2(c.re) * 180.0 / PI)
        .collect();

    EISResult {
        frequencies,
        z_real,
        z_imag,
        z_magnitude,
        z_phase,
        params: params.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_warburg_semi_infinite_zero_sigma() {
        let z = warburg_semi_infinite(100.0, 0.0);
        assert_eq!(z.re, 0.0);
        assert_eq!(z.im, 0.0);
    }

    #[test]
    fn test_warburg_semi_infinite_values() {
        let z = warburg_semi_infinite(100.0, 50.0);
        let expected_re = 50.0 / 100.0_f64.sqrt();
        assert!((z.re - expected_re).abs() < 1e-10);
        assert!((z.im + expected_re).abs() < 1e-10);
    }

    #[test]
    fn test_pure_resistor() {
        // n_cpe=1, sigma_w=0 => just Rs + Rct at low freq
        let params = EISParams {
            rs: 10.0,
            rct: 100.0,
            cdl: 1e-5,
            sigma_w: 0.0,
            n_cpe: 1.0,
            ..Default::default()
        };
        let result = simulate_eis(&params, 0.01, 1e6, 50);
        // At very low frequency, Z should approach Rs + Rct = 110
        let z_low = result.z_real.last().unwrap();
        // At very high frequency, Z should approach Rs = 10
        let z_high = result.z_real.first().unwrap();
        // Low freq end (last = highest freq for log-spaced)
        // Actually frequencies go from f_min to f_max
        // So first = lowest freq => Z ~= Rs + Rct
        assert!((result.z_real[0] - 110.0).abs() < 5.0);
    }

    #[test]
    fn test_simulation_returns_correct_length() {
        let params = EISParams::default();
        let result = simulate_eis(&params, 0.01, 1e6, 100);
        assert_eq!(result.frequencies.len(), 100);
        assert_eq!(result.z_real.len(), 100);
        assert_eq!(result.z_imag.len(), 100);
        assert_eq!(result.z_magnitude.len(), 100);
        assert_eq!(result.z_phase.len(), 100);
    }

    #[test]
    fn test_nyquist_semicircle_shape() {
        let params = EISParams {
            rs: 10.0,
            rct: 100.0,
            cdl: 1e-5,
            sigma_w: 0.0,
            n_cpe: 1.0,
            ..Default::default()
        };
        let result = simulate_eis(&params, 0.01, 1e6, 200);
        // All imaginary parts should be <= 0 for a standard Randles
        for &z_im in &result.z_imag {
            assert!(z_im <= 0.01, "Z_imag should be negative (capacitive)");
        }
    }
}
