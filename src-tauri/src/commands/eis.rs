use crate::engine::eis_solver;
use crate::engine::types::EISParams;
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct SimulateEISRequest {
    pub params: EISParams,
    #[serde(default = "default_f_min")]
    pub f_min: f64,
    #[serde(default = "default_f_max")]
    pub f_max: f64,
    #[serde(default = "default_n_points")]
    pub n_points: usize,
}

fn default_f_min() -> f64 { 0.01 }
fn default_f_max() -> f64 { 1e6 }
fn default_n_points() -> usize { 100 }

#[derive(Debug, Serialize)]
pub struct SimulateEISResponse {
    pub frequencies: Vec<f64>,
    pub z_real: Vec<f64>,
    pub z_imag: Vec<f64>,
    pub z_magnitude: Vec<f64>,
    pub z_phase: Vec<f64>,
}

#[tauri::command]
pub fn simulate_eis(request: SimulateEISRequest) -> Result<SimulateEISResponse, String> {
    let result = eis_solver::simulate_eis(
        &request.params,
        request.f_min,
        request.f_max,
        request.n_points,
    );

    Ok(SimulateEISResponse {
        frequencies: result.frequencies,
        z_real: result.z_real,
        z_imag: result.z_imag,
        z_magnitude: result.z_magnitude,
        z_phase: result.z_phase,
    })
}
