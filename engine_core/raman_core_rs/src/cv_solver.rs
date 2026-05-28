use crate::types::*;
use ndarray::Array1;

fn build_waveform(p: &CVParams, n_per_seg: usize) -> (Vec<f64>, Vec<f64>) {
    let mut e_vec = Vec::with_capacity(n_per_seg * 3 * p.n_cycles as usize);

    for _cyc in 0..p.n_cycles {
        for i in 0..n_per_seg {
            let frac = i as f64 / n_per_seg as f64;
            e_vec.push(p.E_start_V + frac * (p.E_vertex_V - p.E_start_V));
        }
        for i in 0..n_per_seg {
            let frac = i as f64 / n_per_seg as f64;
            e_vec.push(p.E_vertex_V + frac * (p.E_end_V - p.E_vertex_V));
        }
        if (p.E_end_V - p.E_start_V).abs() > 1e-6 {
            let n_ret = n_per_seg / 2;
            for i in 0..=n_ret {
                let frac = i as f64 / n_ret as f64;
                e_vec.push(p.E_end_V + frac * (p.E_start_V - p.E_end_V));
            }
        }
    }

    let n = e_vec.len();
    let d_e = if n > 1 { (e_vec[1] - e_vec[0]).abs() } else { 1e-4 };
    let dt = d_e / p.scan_rate_V_s;
    let t_vec: Vec<f64> = (0..n).map(|i| i as f64 * dt).collect();

    (e_vec, t_vec)
}

fn clamp(x: f64, lo: f64, hi: f64) -> f64 {
    x.max(lo).min(hi)
}

pub fn simulate_cv(p: &CVParams, n_points: usize) -> CVResult {
    let mut result = CVResult {
        params: p.clone(),
        ..CVResult::default()
    };

    let a_eff = p.area_cm2 * p.roughness;
    let f_val = FARADAY / (R_GAS * p.temperature_K);

    let (e_vec, t_vec) = build_waveform(p, n_points);
    let n = e_vec.len();
    let dt = if n > 1 { t_vec[1] - t_vec[0] } else { 1e-4 };

    result.E = Array1::from(e_vec.clone());
    result.time = Array1::from(t_vec);

    let c_bulk_ox = p.C_ox_M * 1e-3;
    let c_bulk_red = p.C_red_M * 1e-3;

    result.i_faradaic = Array1::zeros(n);
    result.i_capacitive = Array1::zeros(n);
    result.i_total = Array1::zeros(n);
    result.E_actual = Array1::zeros(n);

    let sqrt_vals: Vec<f64> = (0..=n).map(|i| (i as f64).sqrt()).collect();

    let coeff_ox = 2.0 * (dt / (PI * p.D_ox_cm2s)).sqrt();
    let coeff_red = 2.0 * (dt / (PI * p.D_red_cm2s)).sqrt();

    let s_diff: Vec<f64> = (0..n).map(|i| sqrt_vals[i + 1] - sqrt_vals[i]).collect();

    let mut flux = vec![0.0; n];
    let rs = p.Rs_ohm.max(0.0);
    let i_to_drop_v = p.n_electrons as f64 * FARADAY * a_eff * rs;
    let fp_tol = 1e-12;
    let fp_max_iters = if rs > 0.0 { 20 } else { 1 };
    const NERNSTIAN_LAMBDA_THRESHOLD: f64 = 1.0;

    for k in 0..n {
        let e_set = e_vec[k];

        let mut conv_ox = 0.0;
        let mut conv_red = 0.0;
        for m in 0..k {
            let s_val = s_diff[k - 1 - m];
            conv_ox += flux[m] * s_val;
            conv_red += flux[m] * s_val;
        }
        conv_ox *= coeff_ox;
        conv_red *= coeff_red;

        let s0_ox = coeff_ox * s_diff[0];
        let s0_red = coeff_red * s_diff[0];

        let mut j_net = if k > 0 { flux[k - 1] } else { 0.0 };
        let mut e_actual = e_set;

        for _iter in 0..fp_max_iters {
            let e_new_actual = e_set - i_to_drop_v * j_net;
            e_actual = 0.5 * (e_actual + e_new_actual);

            let eta = e_actual - p.E_formal_V;
            let dimless = p.n_electrons as f64 * f_val * eta;
            let j_new;

            let arg_fwd_test = clamp(-p.alpha * dimless, -30.0, 30.0);
            let arg_rev_test = clamp((1.0 - p.alpha) * dimless, -30.0, 30.0);
            let kf_test = p.k0_cm_s * arg_fwd_test.exp();
            let kb_test = p.k0_cm_s * arg_rev_test.exp();
            let lambda_step = (kf_test * s0_ox).max(kb_test * s0_red);

            if lambda_step > NERNSTIAN_LAMBDA_THRESHOLD {
                let dimless_clipped = clamp(-dimless, -700.0, 700.0);
                let xi = dimless_clipped.exp();
                let scale = (-dimless_clipped.max(0.0)).exp();
                let xi_s = xi * scale;
                let one_s = 1.0 * scale;
                let numerator =
                    (c_bulk_ox - conv_ox) * one_s - (c_bulk_red + conv_red) * xi_s;
                let denom_n = s0_ox * one_s + s0_red * xi_s;
                j_new = numerator / denom_n.max(1e-300);
            } else {
                let c_ox_surf = (c_bulk_ox - conv_ox).max(0.0);
                let c_red_surf = (c_bulk_red + conv_red).max(0.0);
                let denom = 1.0 + kf_test * s0_ox + kb_test * s0_red;
                j_new = (kf_test * c_ox_surf - kb_test * c_red_surf) / denom.max(1e-30);
            }

            if (j_new - j_net).abs() < fp_tol {
                j_net = j_new;
                break;
            }
            j_net = j_new;
        }

        e_actual = e_set - i_to_drop_v * j_net;
        flux[k] = j_net;
        result.E_actual[k] = e_actual;
        result.i_faradaic[k] = p.n_electrons as f64 * FARADAY * a_eff * j_net;

        let de_actual_dt = if k > 0 {
            (result.E_actual[k] - result.E_actual[k - 1]) / dt
        } else {
            p.scan_rate_V_s
        };
        result.i_capacitive[k] = p.Cdl_F_cm2 * a_eff * de_actual_dt;
    }

    result.i_total = &result.i_faradaic + &result.i_capacitive;

    // Peak analysis
    let half = n / 2;
    let fwd_anodic = p.E_start_V < p.E_vertex_V;

    if fwd_anodic {
        let mut idx_pa = 0;
        let mut max_i = result.i_total[0];
        for i in 1..half {
            if result.i_total[i] > max_i {
                max_i = result.i_total[i];
                idx_pa = i;
            }
        }
        result.i_pa = max_i;
        result.E_pa = result.E[idx_pa];

        let mut idx_pc = half;
        let mut min_i = result.i_total[half];
        for i in (half + 1)..n {
            if result.i_total[i] < min_i {
                min_i = result.i_total[i];
                idx_pc = i;
            }
        }
        result.i_pc = min_i;
        result.E_pc = result.E[idx_pc];
    } else {
        let mut idx_pc = 0;
        let mut min_i = result.i_total[0];
        for i in 1..half {
            if result.i_total[i] < min_i {
                min_i = result.i_total[i];
                idx_pc = i;
            }
        }
        result.i_pc = min_i;
        result.E_pc = result.E[idx_pc];

        let mut idx_pa = half;
        let mut max_i = result.i_total[half];
        for i in (half + 1)..n {
            if result.i_total[i] > max_i {
                max_i = result.i_total[i];
                idx_pa = i;
            }
        }
        result.i_pa = max_i;
        result.E_pa = result.E[idx_pa];
    }

    result.dEp = (result.E_pa - result.E_pc).abs();

    result
}

pub fn randles_sevcik_ip(n: i32, a_cm2: f64, c_m: f64, d_cm2s: f64, v_vs: f64, t_k: f64) -> f64 {
    let c_cm3 = c_m * 1e-3;
    let n15 = (n as f64).powf(1.5);
    let f15 = FARADAY.powf(1.5);
    0.4463 * n15 * f15 * a_cm2 * c_cm3 * (d_cm2s * v_vs / (R_GAS * t_k)).sqrt()
}
