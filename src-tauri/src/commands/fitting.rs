use crate::engine::circuit_fitter;
use crate::engine::types::{CircuitType, FitParams};
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct FitCircuitRequest {
    pub frequencies: Vec<f64>,
    pub z_real: Vec<f64>,
    pub z_imag: Vec<f64>,
    pub initial_params: Vec<f64>,
    #[serde(default)]
    pub fit_params: FitParams,
}

#[derive(Debug, Serialize)]
pub struct FitCircuitResponse {
    pub params: Vec<f64>,
    pub param_names: Vec<String>,
    pub chi_squared: f64,
    pub iterations: usize,
    pub converged: bool,
    pub z_fit_real: Vec<f64>,
    pub z_fit_imag: Vec<f64>,
    pub residual_re: Vec<f64>,
    pub residual_im: Vec<f64>,
}

#[tauri::command]
pub fn fit_circuit(request: FitCircuitRequest) -> Result<FitCircuitResponse, String> {
    if request.frequencies.len() != request.z_real.len()
        || request.frequencies.len() != request.z_imag.len()
    {
        return Err("Frequency, Z_real, and Z_imag arrays must have the same length".into());
    }

    let result = circuit_fitter::fit_circuit(
        &request.frequencies,
        &request.z_real,
        &request.z_imag,
        &request.initial_params,
        &request.fit_params,
    );

    Ok(FitCircuitResponse {
        params: result.params,
        param_names: result.param_names,
        chi_squared: result.chi_squared,
        iterations: result.iterations,
        converged: result.converged,
        z_fit_real: result.z_fit_real,
        z_fit_imag: result.z_fit_imag,
        residual_re: result.residual_re,
        residual_im: result.residual_im,
    })
}
