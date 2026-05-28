//! CV Solver — Convolution-based cyclic voltammetry with Butler-Volmer kinetics.
//!
//! Algorithm (Nicholson-Shain):
//!   At each time step k, solve for surface flux j(k):
//!     j(k) = [kf*C_ox_surf - kb*C_red_surf] / (1 + kf*S0_ox + kb*S0_red)
//!   where surface concentrations come from the convolution integral.
//!
//! Includes iR-drop correction via damped fixed-point iteration and
//! Nernstian fallback for fast kinetics.

use super::types::{CVParams, CVResult, FARADAY, R_GAS};
use std::f64::consts::PI;

/// Build triangular waveform for CV scan
fn build_waveform(p: &CVParams, n_per_seg: usize) -> (Vec<f64>, Vec<f64>) {
    let mut e_vec = Vec::with_capacity(n_per_seg * 3 * p.n_cycles as usize);

    for _cyc in 0..p.n_cycles {
        // Forward: E_start -> E_vertex
        for i in 0..n_per_seg {
            let frac = i as f64 / n_per_seg as f64;
            e_vec.push(p.e_start_v + frac * (p.e_vertex_v - p.e_start_v));
        }
        // Reverse: E_vertex -> E_end
        for i in 0..n_per_seg {
            let frac = i as f64 / n_per_seg as f64;
            e_vec.push(p.e_vertex_v + frac * (p.e_end_v - p.e_vertex_v));
        }
        // Return to start if needed
        if (p.e_end_v - p.e_start_v).abs() > 1e-6 {
            let n_ret = n_per_seg / 2;
            for i in 0..=n_ret {
                let frac = i as f64 / n_ret as f64;
                e_vec.push(p.e_end_v + frac * (p.e_start_v - p.e_end_v));
            }
        }
    }

    let n = e_vec.len();
    let de = if n > 1 {
        (e_vec[1] - e_vec[0]).abs()
    } else {
        1e-4
    };
    let dt = de / p.scan_rate_v_s;
    let t_vec: Vec<f64> = (0..n).map(|i| i as f64 * dt).collect();

    (e_vec, t_vec)
}

/// Main CV simulation
pub fn simulate_cv(params: &CVParams, n_points: usize) -> CVResult {
    let a_eff = params.area_cm2 * params.roughness;
    let f_val = FARADAY / (R_GAS * params.temperature_k); // F/RT

    let (e_vec, t_vec) = build_waveform(params, n_points);
    let n = e_vec.len();
    let dt = if n > 1 { t_vec[1] - t_vec[0] } else { 1e-4 };

    let c_bulk_ox = params.c_ox_m * 1e-3; // mol/cm^3
    let c_bulk_red = params.c_red_m * 1e-3;

    let mut i_faradaic = vec![0.0_f64; n];
    let mut i_capacitive = vec![0.0_f64; n];
    let mut i_total = vec![0.0_f64; n];
    let mut e_actual = vec![0.0_f64; n];

    // Precompute convolution kernel: S[m] = 2*sqrt(dt/(pi*D))*(sqrt(m+1) - sqrt(m))
    let sqrt_vals: Vec<f64> = (0..=n).map(|i| (i as f64).sqrt()).collect();
    let coeff_ox = 2.0 * (dt / (PI * params.d_ox_cm2s)).sqrt();
    let coeff_red = 2.0 * (dt / (PI * params.d_red_cm2s)).sqrt();

    let s_diff: Vec<f64> = (0..n).map(|i| sqrt_vals[i + 1] - sqrt_vals[i]).collect();

    let mut flux = vec![0.0_f64; n];

    // iR-drop iteration parameters
    let rs = params.rs_ohm.max(0.0);
    let i_to_drop_v = params.n_electrons as f64 * FARADAY * a_eff * rs;
    let fp_tol = 1e-12;
    let fp_max_iters = if rs > 0.0 { 20 } else { 1 };

    for k in 0..n {
        // Convolution: surface concentration corrections
        let mut conv_ox = 0.0;
        let mut conv_red = 0.0;
        for m in 0..k {
            conv_ox += flux[m] * s_diff[k - m - 1];
            conv_red -= flux[m] * s_diff[k - m - 1];
        }

        let s0_ox = coeff_ox * s_diff[0];
        let s0_red = coeff_red * s_diff[0];

        let c_ox_hist = c_bulk_ox - coeff_ox * conv_ox;
        let c_red_hist = c_bulk_red + coeff_red * conv_red;

        // Fixed-point iteration for iR-drop
        let mut j_net = if k > 0 { flux[k - 1] } else { 0.0 };

        for _fp_iter in 0..fp_max_iters {
            // Compute E_actual with iR drop
            let i_curr = params.n_electrons as f64 * FARADAY * a_eff * j_net;
            let e_act = e_vec[k] - i_curr * rs;

            // Butler-Volmer rate constants
            let eta = e_act - params.e_formal_v;
            let kf = params.k0_cm_s * (-params.alpha * params.n_electrons as f64 * f_val * eta).exp();
            let kb = params.k0_cm_s * ((1.0 - params.alpha) * params.n_electrons as f64 * f_val * eta).exp();

            // Check for Nernstian regime
            let lambda_step = kf.max(kb) * s0_ox.max(s0_red);

            let j_new = if lambda_step > 50.0 {
                // Nernstian: surface concentrations at equilibrium
                let theta = (params.n_electrons as f64 * f_val * eta).exp();
                let c_ox_surf = (c_ox_hist + c_red_hist * theta) / (1.0 + theta) / (1.0 + s0_ox / s0_red);
                (c_bulk_ox - c_ox_surf) / (coeff_ox * s_diff[0]).max(1e-30)
            } else {
                // Butler-Volmer
                let c_ox_surf = (c_ox_hist + kf * s0_ox * c_ox_hist).max(0.0);
                let c_red_surf = (c_red_hist + kb * s0_red * c_red_hist).max(0.0);
                (kf * c_ox_hist - kb * c_red_hist) / (1.0 + kf * s0_ox + kb * s0_red)
            };

            let delta = (j_new - j_net).abs();
            // Damped update
            j_net = if rs > 0.0 {
                0.5 * j_net + 0.5 * j_new
            } else {
                j_new
            };

            if delta < fp_tol {
                break;
            }
        }

        flux[k] = j_net;

        // Faradaic current
        let i_far = params.n_electrons as f64 * FARADAY * a_eff * j_net;
        i_faradaic[k] = i_far;

        // Capacitive current
        let i_cap = if k > 0 {
            params.cdl_f_cm2 * a_eff * (e_vec[k] - e_vec[k - 1]) / dt
        } else {
            0.0
        };
        i_capacitive[k] = i_cap;

        // Total current
        i_total[k] = i_far + i_cap;

        // Actual electrode potential
        e_actual[k] = e_vec[k] - i_total[k] * rs;
    }

    // Peak analysis
    let (mut i_pa, mut i_pc) = (0.0_f64, 0.0_f64);
    let (mut e_pa, mut e_pc) = (0.0_f64, 0.0_f64);

    for k in 0..n {
        if i_total[k] > i_pa {
            i_pa = i_total[k];
            e_pa = e_actual[k];
        }
        if i_total[k] < i_pc {
            i_pc = i_total[k];
            e_pc = e_actual[k];
        }
    }
    let d_ep = (e_pa - e_pc).abs();

    CVResult {
        e: e_vec,
        e_actual,
        i_total,
        i_faradaic,
        i_capacitive,
        time: t_vec,
        i_pa,
        i_pc,
        e_pa,
        e_pc,
        d_ep,
        params: params.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_waveform_generation() {
        let params = CVParams::default();
        let (e, t) = build_waveform(&params, 100);
        assert!(e.len() > 100);
        assert_eq!(e.len(), t.len());
        // First point should be E_start
        assert!((e[0] - params.e_start_v).abs() < 1e-10);
    }

    #[test]
    fn test_cv_simulation_runs() {
        let params = CVParams::default();
        let result = simulate_cv(&params, 200);
        assert!(!result.e.is_empty());
        assert_eq!(result.e.len(), result.i_total.len());
        assert_eq!(result.e.len(), result.i_faradaic.len());
        assert_eq!(result.e.len(), result.i_capacitive.len());
    }

    #[test]
    fn test_cv_peak_detection() {
        let params = CVParams::default();
        let result = simulate_cv(&params, 500);
        // Should detect anodic and cathodic peaks
        assert!(result.i_pa > 0.0, "Anodic peak should be positive");
        assert!(result.i_pc < 0.0, "Cathodic peak should be negative");
        // Peak separation should be reasonable
        assert!(result.d_ep > 0.0);
    }
}
