use crate::engine::cv_solver;
use crate::engine::types::CVParams;
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct SimulateCVRequest {
    pub params: CVParams,
    #[serde(default = "default_n_points")]
    pub n_points: usize,
}

fn default_n_points() -> usize { 500 }

#[derive(Debug, Serialize)]
pub struct SimulateCVResponse {
    pub e: Vec<f64>,
    pub e_actual: Vec<f64>,
    pub i_total: Vec<f64>,
    pub i_faradaic: Vec<f64>,
    pub i_capacitive: Vec<f64>,
    pub time: Vec<f64>,
    pub i_pa: f64,
    pub i_pc: f64,
    pub e_pa: f64,
    pub e_pc: f64,
    pub d_ep: f64,
}

#[tauri::command]
pub fn simulate_cv(request: SimulateCVRequest) -> Result<SimulateCVResponse, String> {
    let result = cv_solver::simulate_cv(&request.params, request.n_points);

    Ok(SimulateCVResponse {
        e: result.e,
        e_actual: result.e_actual,
        i_total: result.i_total,
        i_faradaic: result.i_faradaic,
        i_capacitive: result.i_capacitive,
        time: result.time,
        i_pa: result.i_pa,
        i_pc: result.i_pc,
        e_pa: result.e_pa,
        e_pc: result.e_pc,
        d_ep: result.d_ep,
    })
}
