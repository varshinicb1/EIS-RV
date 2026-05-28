use ndarray::{Array1, Array2};

// Constants
pub const PI: f64 = std::f64::consts::PI;
pub const FARADAY: f64 = 96485.33212;
pub const R_GAS: f64 = 8.314462618;
pub const T_STD: f64 = 298.15;
pub const RT_F: f64 = R_GAS * T_STD / FARADAY;

// EIS Parameters
#[derive(Clone, Debug, Default)]
pub struct EISParams {
    pub Rs: f64,
    pub Rct: f64,
    pub Cdl: f64,
    pub sigma_w: f64,
    pub n_cpe: f64,
    pub bounded_w: bool,
    pub diff_len_um: f64,
    pub diff_coeff: f64,
}

#[derive(Clone, Debug)]
pub struct EISResult {
    pub frequencies: Array1<f64>,
    pub Z_real: Array1<f64>,
    pub Z_imag: Array1<f64>,
    pub Z_magnitude: Array1<f64>,
    pub Z_phase: Array1<f64>,
    pub params: EISParams,
}

// CV Parameters
#[derive(Clone, Debug, Default)]
pub struct CVParams {
    pub area_cm2: f64,
    pub roughness: f64,
    pub E_formal_V: f64,
    pub n_electrons: i32,
    pub C_ox_M: f64,
    pub C_red_M: f64,
    pub D_ox_cm2s: f64,
    pub D_red_cm2s: f64,
    pub k0_cm_s: f64,
    pub alpha: f64,
    pub Cdl_F_cm2: f64,
    pub Rs_ohm: f64,
    pub E_start_V: f64,
    pub E_vertex_V: f64,
    pub E_end_V: f64,
    pub scan_rate_V_s: f64,
    pub n_cycles: i32,
    pub temperature_K: f64,
}

// CV Result
#[derive(Clone, Debug, Default)]
pub struct CVResult {
    pub E: Array1<f64>,
    pub E_actual: Array1<f64>,
    pub i_total: Array1<f64>,
    pub i_faradaic: Array1<f64>,
    pub i_capacitive: Array1<f64>,
    pub time: Array1<f64>,
    pub i_pa: f64,
    pub i_pc: f64,
    pub E_pa: f64,
    pub E_pc: f64,
    pub dEp: f64,
    pub params: CVParams,
}

// DRT Parameters
#[derive(Clone, Debug, Default)]
pub struct DRTParams {
    pub lambda: f64,
    pub n_tau: usize,
    pub tau_min: f64,
    pub tau_max: f64,
    pub non_negative: bool,
    pub max_iter: usize,
}

// DRT Result
#[derive(Clone, Debug, Default)]
pub struct DRTResult {
    pub tau: Array1<f64>,
    pub gamma: Array1<f64>,
    pub Z_fit_real: Array1<f64>,
    pub Z_fit_imag: Array1<f64>,
    pub R_inf: f64,
    pub R_pol: f64,
    pub residual: f64,
    pub lambda_used: f64,
}

// Kramers-Kronig Result
#[derive(Clone, Debug, Default)]
pub struct KKResult {
    pub is_valid: bool,
    pub mu: f64,
    pub residual_real: Array1<f64>,
    pub residual_imag: Array1<f64>,
    pub max_residual_real: f64,
    pub max_residual_imag: f64,
    pub mean_residual: f64,
    pub Z_fit_real: Array1<f64>,
    pub Z_fit_imag: Array1<f64>,
    pub tau: Array1<f64>,
    pub R: Array1<f64>,
    pub R_inf: f64,
    pub n_rc_used: i32,
}

// Circuit Fitter
#[derive(Clone, Debug, Copy, Default)]
pub enum CircuitType {
    #[default]
    RANDLES = 0,
    R_RC = 1,
    R_RC_RC = 2,
}

#[derive(Clone, Debug, Default)]
pub struct FitParams {
    pub circuit: CircuitType,
    pub max_iter: i32,
    pub tol: f64,
    pub lambda_init: f64,
    pub lambda_up: f64,
    pub lambda_down: f64,
}

#[derive(Clone, Debug, Default)]
pub struct FitResult {
    pub params: Array1<f64>,
    pub errors: Array1<f64>,
    pub Z_fit_real: Array1<f64>,
    pub Z_fit_imag: Array1<f64>,
    pub chi_squared: f64,
    pub reduced_chi_sq: f64,
    pub iterations: i32,
    pub converged: bool,
}
