use ndarray::Array1;
use num_complex::Complex64;
use raman_core_rs::types::*;
use raman_core_rs::eis_solver::*;
use raman_core_rs::cv_solver::*;
use raman_core_rs::circuit_fitter::*;
use raman_core_rs::drt_solver::*;
use raman_core_rs::diffusion_solver::*;

#[test]
fn test_warburg_semi_infinite() {
    let z = warburg_semi_infinite(1.0, 10.0);
    assert!(z.re > 0.0);
    assert!(z.im < 0.0);
}

#[test]
fn test_eis_simulate_basic() {
    let p = EISParams {
        Rs: 10.0,
        Rct: 100.0,
        Cdl: 1e-5,
        sigma_w: 50.0,
        n_cpe: 0.9,
        bounded_w: false,
        diff_len_um: 100.0,
        diff_coeff: 1e-6,
    };
    let res = simulate_eis(&p, 0.01, 1e6, 100);
    assert_eq!(res.frequencies.len(), 100);
    assert_eq!(res.Z_real.len(), 100);
    assert_eq!(res.Z_imag.len(), 100);
    assert_eq!(res.Z_magnitude.len(), 100);
    assert_eq!(res.Z_phase.len(), 100);
    // At high frequency, Z approaches Rs
    assert!((res.Z_real[99] - p.Rs).abs() < 5.0);
}

#[test]
fn test_cv_simulate_basic() {
    let p = CVParams {
        area_cm2: 0.0707,
        roughness: 1.0,
        E_formal_V: 0.23,
        n_electrons: 1,
        C_ox_M: 5e-3,
        C_red_M: 5e-3,
        D_ox_cm2s: 7.6e-6,
        D_red_cm2s: 7.6e-6,
        k0_cm_s: 0.01,
        alpha: 0.5,
        Cdl_F_cm2: 20e-6,
        Rs_ohm: 10.0,
        E_start_V: -0.3,
        E_vertex_V: 0.8,
        E_end_V: -0.3,
        scan_rate_V_s: 0.05,
        n_cycles: 1,
        temperature_K: 298.15,
    };
    let res = simulate_cv(&p, 500);
    assert_eq!(res.E.len(), 1000);
    assert_eq!(res.i_total.len(), 1000);
    assert!(res.i_pa > 0.0);
    assert!(res.i_pc < 0.0);
}

#[test]
fn test_randles_sevcik() {
    let ip = randles_sevcik_ip(1, 0.0707, 5e-3, 7.6e-6, 0.05, 298.15);
    assert!(ip > 0.0);
}

#[test]
fn test_randles_model() {
    let freqs = Array1::from(vec![1.0, 10.0, 100.0, 1000.0]);
    let p = Array1::from(vec![10.0, 100.0, 1e-5, 0.9, 50.0]);
    let (z_re, z_im) = randles_model(&freqs, &p);
    assert_eq!(z_re.len(), 4);
    assert_eq!(z_im.len(), 4);
    assert!(z_re[0] > z_re[3]); // decreases with frequency
    assert!(z_im[0] > z_im[3]); // more negative at low frequency
}

#[test]
fn test_fit_circuit_randles() {
    let freqs = Array1::from(vec![1.0, 10.0, 100.0]);
    let zr = Array1::from(vec![110.0, 60.0, 20.0]);
    let zi = Array1::from(vec![-50.0, -30.0, -10.0]);
    let init = Array1::from(vec![5.0, 80.0, 1e-6, 0.8, 40.0]);
    let params = FitParams {
        circuit: CircuitType::RANDLES,
        max_iter: 50,
        tol: 1e-6,
        lambda_init: 1e-3,
        lambda_up: 10.0,
        lambda_down: 0.1,
    };
    let res = fit_circuit(&freqs, &zr, &zi, &init, &params);
    assert_eq!(res.params.len(), 5);
    assert_eq!(res.Z_fit_real.len(), 3);
    assert_eq!(res.Z_fit_imag.len(), 3);
}

#[test]
fn test_diffusion_1d() {
    let flux = Array1::from(vec![0.0; 10]);
    let c = solve_diffusion_1d(1e-6, 1e-3, 0.01, 50, 10, 0.1, &flux);
    assert_eq!(c.len(), 50);
    assert!(c.iter().all(|&v| v >= 0.0));
}

#[test]
fn test_spherical_diffusion() {
    let flux = Array1::from(vec![0.0; 10]);
    let c = solve_spherical_diffusion(1e-6, 1e-3, 0.1, 10.0, 30, 10, 0.1, &flux);
    assert_eq!(c.len(), 10);
    assert!(c.iter().all(|&v| v >= 0.0));
}

#[test]
fn test_compute_drt() {
    let freqs = Array1::from(vec![0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]);
    let zr = Array1::from(vec![110.0, 105.0, 100.0, 80.0, 50.0, 20.0]);
    let zi = Array1::from(vec![-5.0, -10.0, -20.0, -30.0, -20.0, -5.0]);
    let params = DRTParams {
        lambda: 1e-3,
        n_tau: 50,
        tau_min: 1e-7,
        tau_max: 1e3,
        non_negative: true,
        max_iter: 100,
    };
    let res = compute_drt(&freqs, &zr, &zi, &params);
    assert_eq!(res.tau.len(), 50);
    assert_eq!(res.gamma.len(), 50);
    assert_eq!(res.Z_fit_real.len(), 6);
    assert_eq!(res.Z_fit_imag.len(), 6);
}

#[test]
fn test_kramers_kronig() {
    let freqs = Array1::from(vec![0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]);
    let zr = Array1::from(vec![110.0, 105.0, 100.0, 80.0, 50.0, 20.0]);
    let zi = Array1::from(vec![-5.0, -10.0, -20.0, -30.0, -20.0, -5.0]);
    let res = kramers_kronig_test(&freqs, &zr, &zi, 0);
    assert!(res.mu >= 0.0);
    assert_eq!(res.residual_real.len(), 6);
    assert_eq!(res.residual_imag.len(), 6);
}
