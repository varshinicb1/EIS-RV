//! Core types for the RAMAN Studio physics engine.
//!
//! All impedance computations use `num::Complex<f64>`.
//! nalgebra `DVector`/`DMatrix` handle vectorized operations.

use nalgebra::{DMatrix, DVector};
use serde::{Deserialize, Serialize};
use std::f64::consts::PI;

// Physical constants
pub const FARADAY: f64 = 96485.33212; // C/mol
pub const R_GAS: f64 = 8.314462618; // J/(mol*K)
pub const T_STD: f64 = 298.15; // K (25 deg C)
pub const RT_F: f64 = R_GAS * T_STD / FARADAY; // ~0.02569 V

/// Complex number type alias
pub type Complex = num_complex::Complex64;

// Re-export nalgebra types
pub type VecD = DVector<f64>;
pub type MatD = DMatrix<f64>;

/// EIS circuit parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EISParams {
    /// Solution resistance (ohm)
    pub rs: f64,
    /// Charge transfer resistance (ohm)
    pub rct: f64,
    /// Double-layer capacitance (F) or CPE Q0
    pub cdl: f64,
    /// Warburg coefficient (ohm*s^(-1/2))
    pub sigma_w: f64,
    /// CPE exponent (1.0 = ideal capacitor)
    pub n_cpe: f64,
    /// Use finite-length Warburg
    pub bounded_w: bool,
    /// Diffusion layer thickness (um)
    pub diff_len_um: f64,
    /// Diffusion coefficient (cm^2/s)
    pub diff_coeff: f64,
}

impl Default for EISParams {
    fn default() -> Self {
        Self {
            rs: 10.0,
            rct: 100.0,
            cdl: 1.5e-5,
            sigma_w: 50.0,
            n_cpe: 0.9,
            bounded_w: false,
            diff_len_um: 100.0,
            diff_coeff: 1e-6,
        }
    }
}

/// EIS simulation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EISResult {
    pub frequencies: Vec<f64>,
    pub z_real: Vec<f64>,
    pub z_imag: Vec<f64>,
    pub z_magnitude: Vec<f64>,
    pub z_phase: Vec<f64>,
    pub params: EISParams,
}

/// CV parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CVParams {
    // Electrode
    pub area_cm2: f64,
    pub roughness: f64,

    // Redox couple
    pub e_formal_v: f64,
    pub n_electrons: i32,
    pub c_ox_m: f64,
    pub c_red_m: f64,
    pub d_ox_cm2s: f64,
    pub d_red_cm2s: f64,

    // Kinetics (Butler-Volmer)
    pub k0_cm_s: f64,
    pub alpha: f64,

    // Double layer
    pub cdl_f_cm2: f64,
    pub rs_ohm: f64,

    // Scan
    pub e_start_v: f64,
    pub e_vertex_v: f64,
    pub e_end_v: f64,
    pub scan_rate_v_s: f64,
    pub n_cycles: i32,
    pub temperature_k: f64,
}

impl Default for CVParams {
    fn default() -> Self {
        Self {
            area_cm2: 0.0707,
            roughness: 1.0,
            e_formal_v: 0.23,
            n_electrons: 1,
            c_ox_m: 5e-3,
            c_red_m: 5e-3,
            d_ox_cm2s: 7.6e-6,
            d_red_cm2s: 7.6e-6,
            k0_cm_s: 0.01,
            alpha: 0.5,
            cdl_f_cm2: 20e-6,
            rs_ohm: 10.0,
            e_start_v: -0.3,
            e_vertex_v: 0.8,
            e_end_v: -0.3,
            scan_rate_v_s: 0.05,
            n_cycles: 1,
            temperature_k: 298.15,
        }
    }
}

/// CV simulation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CVResult {
    pub e: Vec<f64>,
    pub e_actual: Vec<f64>,
    pub i_total: Vec<f64>,
    pub i_faradaic: Vec<f64>,
    pub i_capacitive: Vec<f64>,
    pub time: Vec<f64>,

    // Peak analysis
    pub i_pa: f64,
    pub i_pc: f64,
    pub e_pa: f64,
    pub e_pc: f64,
    pub d_ep: f64,

    pub params: CVParams,
}

/// DRT parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DRTParams {
    pub lambda: f64,
    pub n_tau: usize,
    pub tau_min: f64,
    pub tau_max: f64,
    pub non_negative: bool,
    pub max_iter: usize,
}

impl Default for DRTParams {
    fn default() -> Self {
        Self {
            lambda: 1e-3,
            n_tau: 100,
            tau_min: 1e-7,
            tau_max: 1e3,
            non_negative: true,
            max_iter: 200,
        }
    }
}

/// DRT result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DRTResult {
    pub tau: Vec<f64>,
    pub gamma: Vec<f64>,
    pub z_fit_real: Vec<f64>,
    pub z_fit_imag: Vec<f64>,
    pub r_inf: f64,
    pub r_pol: f64,
    pub residual_re: Vec<f64>,
    pub residual_im: Vec<f64>,
}

/// Circuit types for fitting
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum CircuitType {
    Randles,
    RRc,
    RRcRc,
}

/// Circuit fitting parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FitParams {
    pub circuit: CircuitType,
    pub max_iter: usize,
    pub tol: f64,
    pub lambda_init: f64,
}

impl Default for FitParams {
    fn default() -> Self {
        Self {
            circuit: CircuitType::Randles,
            max_iter: 200,
            tol: 1e-10,
            lambda_init: 1e-3,
        }
    }
}

/// Circuit fitting result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FitResult {
    pub params: Vec<f64>,
    pub chi_squared: f64,
    pub iterations: usize,
    pub converged: bool,
    pub z_fit_real: Vec<f64>,
    pub z_fit_imag: Vec<f64>,
    pub residual_re: Vec<f64>,
    pub residual_im: Vec<f64>,
    pub param_names: Vec<String>,
}

/// Kramers-Kronig validation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KKResult {
    pub z_kk_real: Vec<f64>,
    pub z_kk_imag: Vec<f64>,
    pub residual_re: Vec<f64>,
    pub residual_im: Vec<f64>,
    pub mean_residual: f64,
    pub valid: bool,
}
