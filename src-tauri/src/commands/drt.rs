use crate::engine::drt_solver;
use crate::engine::types::DRTParams;
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct ComputeDRTRequest {
    pub frequencies: Vec<f64>,
    pub z_real: Vec<f64>,
    pub z_imag: Vec<f64>,
    #[serde(default)]
    pub params: DRTParams,
}

#[derive(Debug, Serialize)]
pub struct ComputeDRTResponse {
    pub tau: Vec<f64>,
    pub gamma: Vec<f64>,
    pub z_fit_real: Vec<f64>,
    pub z_fit_imag: Vec<f64>,
    pub r_inf: f64,
    pub r_pol: f64,
    pub residual_re: Vec<f64>,
    pub residual_im: Vec<f64>,
}

#[tauri::command]
pub fn compute_drt(request: ComputeDRTRequest) -> Result<ComputeDRTResponse, String> {
    if request.frequencies.len() != request.z_real.len()
        || request.frequencies.len() != request.z_imag.len()
    {
        return Err("Frequency, Z_real, and Z_imag arrays must have the same length".into());
    }

    let result = drt_solver::compute_drt(
        &request.frequencies,
        &request.z_real,
        &request.z_imag,
        &request.params,
    );

    Ok(ComputeDRTResponse {
        tau: result.tau,
        gamma: result.gamma,
        z_fit_real: result.z_fit_real,
        z_fit_imag: result.z_fit_imag,
        r_inf: result.r_inf,
        r_pol: result.r_pol,
        residual_re: result.residual_re,
        residual_im: result.residual_im,
    })
}

#[derive(Debug, Serialize)]
pub struct KKResponse {
    pub z_kk_real: Vec<f64>,
    pub z_kk_imag: Vec<f64>,
    pub residual_re: Vec<f64>,
    pub residual_im: Vec<f64>,
    pub mean_residual: f64,
    pub valid: bool,
}

#[derive(Debug, Deserialize)]
pub struct KKRequest {
    pub frequencies: Vec<f64>,
    pub z_real: Vec<f64>,
    pub z_imag: Vec<f64>,
}

#[tauri::command]
pub fn kramers_kronig_test(request: KKRequest) -> Result<KKResponse, String> {
    let result = drt_solver::kramers_kronig_test(
        &request.frequencies,
        &request.z_real,
        &request.z_imag,
    );

    Ok(KKResponse {
        z_kk_real: result.z_kk_real,
        z_kk_imag: result.z_kk_imag,
        residual_re: result.residual_re,
        residual_im: result.residual_im,
        mean_residual: result.mean_residual,
        valid: result.valid,
    })
}
