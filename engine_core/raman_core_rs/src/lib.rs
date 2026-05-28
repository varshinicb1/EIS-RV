mod types;
mod eis_solver;
mod cv_solver;
mod circuit_fitter;
mod drt_solver;
mod diffusion_solver;

use pyo3::prelude::*;
use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1};
use ndarray::Array1;

use types::*;
use eis_solver::*;
use cv_solver::*;
use circuit_fitter::*;
use drt_solver::*;
use diffusion_solver::*;

// ── EIS ───────────────────────────────────────────────────

#[pyclass]
struct PyEISParams {
    #[pyo3(get, set)] Rs: f64,
    #[pyo3(get, set)] Rct: f64,
    #[pyo3(get, set)] Cdl: f64,
    #[pyo3(get, set)] sigma_w: f64,
    #[pyo3(get, set)] n_cpe: f64,
    #[pyo3(get, set)] bounded_w: bool,
    #[pyo3(get, set)] diff_len_um: f64,
    #[pyo3(get, set)] diff_coeff: f64,
}

#[pymethods]
impl PyEISParams {
    #[new]
    fn new() -> Self {
        PyEISParams {
            Rs: 10.0, Rct: 100.0, Cdl: 1.5e-5,
            sigma_w: 50.0, n_cpe: 0.9, bounded_w: false,
            diff_len_um: 100.0, diff_coeff: 1e-6,
        }
    }
}

#[pyclass]
struct PyEISResult {
    #[pyo3(get)] frequencies: Py<PyArray1<f64>>,
    #[pyo3(get)] Z_real: Py<PyArray1<f64>>,
    #[pyo3(get)] Z_imag: Py<PyArray1<f64>>,
    #[pyo3(get)] Z_magnitude: Py<PyArray1<f64>>,
    #[pyo3(get)] Z_phase: Py<PyArray1<f64>>,
}

#[pyfunction]
fn simulate_eis_py(
    py: Python,
    params: &PyEISParams,
    f_min: f64,
    f_max: f64,
    n_points: usize,
) -> PyResult<PyEISResult> {
    let p = EISParams {
        Rs: params.Rs, Rct: params.Rct, Cdl: params.Cdl,
        sigma_w: params.sigma_w, n_cpe: params.n_cpe,
        bounded_w: params.bounded_w, diff_len_um: params.diff_len_um,
        diff_coeff: params.diff_coeff,
    };
    let res = simulate_eis(&p, f_min, f_max, n_points);
    Ok(PyEISResult {
        frequencies: res.frequencies.into_pyarray(py).into(),
        Z_real: res.Z_real.into_pyarray(py).into(),
        Z_imag: res.Z_imag.into_pyarray(py).into(),
        Z_magnitude: res.Z_magnitude.into_pyarray(py).into(),
        Z_phase: res.Z_phase.into_pyarray(py).into(),
    })
}

#[pyfunction]
fn randles_impedance_py(
    py: Python,
    frequencies: PyReadonlyArray1<f64>,
    params: &PyEISParams,
) -> PyResult<(Py<PyArray1<f64>>, Py<PyArray1<f64>>)> {
    let p = EISParams {
        Rs: params.Rs, Rct: params.Rct, Cdl: params.Cdl,
        sigma_w: params.sigma_w, n_cpe: params.n_cpe,
        bounded_w: params.bounded_w, diff_len_um: params.diff_len_um,
        diff_coeff: params.diff_coeff,
    };
    let z = randles_impedance(&frequencies.as_array().to_owned(), &p);
    let z_re = z.iter().map(|c| c.re).collect::<Vec<f64>>();
    let z_im = z.iter().map(|c| c.im).collect::<Vec<f64>>();
    Ok((
        Array1::from(z_re).into_pyarray(py).into(),
        Array1::from(z_im).into_pyarray(py).into(),
    ))
}

#[pyfunction]
fn quick_eis_py(
    py: Python,
    rs: f64,
    rct: f64,
    cdl: f64,
    sigma_w: f64,
    n_cpe: f64,
    n_points: usize,
) -> PyResult<PyEISResult> {
    let p = EISParams { Rs: rs, Rct: rct, Cdl: cdl, sigma_w, n_cpe, ..Default::default() };
    let res = simulate_eis(&p, 0.01, 1e6, n_points);
    Ok(PyEISResult {
        frequencies: res.frequencies.into_pyarray(py).into(),
        Z_real: res.Z_real.into_pyarray(py).into(),
        Z_imag: res.Z_imag.into_pyarray(py).into(),
        Z_magnitude: res.Z_magnitude.into_pyarray(py).into(),
        Z_phase: res.Z_phase.into_pyarray(py).into(),
    })
}

// ── CV ────────────────────────────────────────────────────

#[pyclass]
struct PyCVParams {
    #[pyo3(get, set)] area_cm2: f64,
    #[pyo3(get, set)] roughness: f64,
    #[pyo3(get, set)] E_formal_V: f64,
    #[pyo3(get, set)] n_electrons: i32,
    #[pyo3(get, set)] C_ox_M: f64,
    #[pyo3(get, set)] C_red_M: f64,
    #[pyo3(get, set)] D_ox_cm2s: f64,
    #[pyo3(get, set)] D_red_cm2s: f64,
    #[pyo3(get, set)] k0_cm_s: f64,
    #[pyo3(get, set)] alpha: f64,
    #[pyo3(get, set)] Cdl_F_cm2: f64,
    #[pyo3(get, set)] Rs_ohm: f64,
    #[pyo3(get, set)] E_start_V: f64,
    #[pyo3(get, set)] E_vertex_V: f64,
    #[pyo3(get, set)] E_end_V: f64,
    #[pyo3(get, set)] scan_rate_V_s: f64,
    #[pyo3(get, set)] n_cycles: i32,
    #[pyo3(get, set)] temperature_K: f64,
}

#[pymethods]
impl PyCVParams {
    #[new]
    fn new() -> Self {
        PyCVParams {
            area_cm2: 0.0707, roughness: 1.0, E_formal_V: 0.23,
            n_electrons: 1, C_ox_M: 5e-3, C_red_M: 5e-3,
            D_ox_cm2s: 7.6e-6, D_red_cm2s: 7.6e-6,
            k0_cm_s: 0.01, alpha: 0.5, Cdl_F_cm2: 20e-6,
            Rs_ohm: 10.0, E_start_V: -0.3, E_vertex_V: 0.8,
            E_end_V: -0.3, scan_rate_V_s: 0.05, n_cycles: 1,
            temperature_K: 298.15,
        }
    }
}

#[pyclass]
struct PyCVResult {
    #[pyo3(get)] E: Py<PyArray1<f64>>,
    #[pyo3(get)] i_total: Py<PyArray1<f64>>,
    #[pyo3(get)] i_faradaic: Py<PyArray1<f64>>,
    #[pyo3(get)] i_capacitive: Py<PyArray1<f64>>,
    #[pyo3(get)] time: Py<PyArray1<f64>>,
    #[pyo3(get)] i_pa: f64,
    #[pyo3(get)] i_pc: f64,
    #[pyo3(get)] E_pa: f64,
    #[pyo3(get)] E_pc: f64,
    #[pyo3(get)] dEp: f64,
}

#[pyfunction]
fn simulate_cv_py(
    py: Python,
    params: &PyCVParams,
    n_points: usize,
) -> PyResult<PyCVResult> {
    let p = CVParams {
        area_cm2: params.area_cm2, roughness: params.roughness,
        E_formal_V: params.E_formal_V, n_electrons: params.n_electrons,
        C_ox_M: params.C_ox_M, C_red_M: params.C_red_M,
        D_ox_cm2s: params.D_ox_cm2s, D_red_cm2s: params.D_red_cm2s,
        k0_cm_s: params.k0_cm_s, alpha: params.alpha,
        Cdl_F_cm2: params.Cdl_F_cm2, Rs_ohm: params.Rs_ohm,
        E_start_V: params.E_start_V, E_vertex_V: params.E_vertex_V,
        E_end_V: params.E_end_V, scan_rate_V_s: params.scan_rate_V_s,
        n_cycles: params.n_cycles, temperature_K: params.temperature_K,
    };
    let res = simulate_cv(&p, n_points);
    Ok(PyCVResult {
        E: res.E.into_pyarray(py).into(),
        i_total: res.i_total.into_pyarray(py).into(),
        i_faradaic: res.i_faradaic.into_pyarray(py).into(),
        i_capacitive: res.i_capacitive.into_pyarray(py).into(),
        time: res.time.into_pyarray(py).into(),
        i_pa: res.i_pa, i_pc: res.i_pc,
        E_pa: res.E_pa, E_pc: res.E_pc, dEp: res.dEp,
    })
}

#[pyfunction]
fn randles_sevcik_ip_py(
    n: i32, a_cm2: f64, c_m: f64, d_cm2s: f64, v_vs: f64, t_k: f64,
) -> f64 {
    randles_sevcik_ip(n, a_cm2, c_m, d_cm2s, v_vs, t_k)
}

// ── Diffusion ─────────────────────────────────────────────

#[pyfunction]
fn solve_diffusion_1d_py(
    py: Python,
    d_cm2s: f64, c_bulk_m: f64, l_cm: f64,
    n_spatial: usize, n_time: usize, dt_s: f64,
    surface_flux: PyReadonlyArray1<f64>,
) -> PyResult<Py<PyArray1<f64>>> {
    let flux = surface_flux.as_array().to_owned();
    let res = solve_diffusion_1d(d_cm2s, c_bulk_m, l_cm, n_spatial, n_time, dt_s, &flux);
    Ok(res.into_pyarray(py).into())
}

#[pyfunction]
fn solve_spherical_diffusion_py(
    py: Python,
    d_cm2s: f64, c_max_m: f64, c_init_frac: f64,
    radius_um: f64, n_radial: usize, n_time: usize,
    dt_s: f64, surface_flux: PyReadonlyArray1<f64>,
) -> PyResult<Py<PyArray1<f64>>> {
    let flux = surface_flux.as_array().to_owned();
    let res = solve_spherical_diffusion(
        d_cm2s, c_max_m, c_init_frac, radius_um,
        n_radial, n_time, dt_s, &flux,
    );
    Ok(res.into_pyarray(py).into())
}

// ── DRT ───────────────────────────────────────────────────

#[pyclass]
struct PyDRTParams {
    #[pyo3(get, set)] lambda_: f64,
    #[pyo3(get, set)] n_tau: usize,
    #[pyo3(get, set)] tau_min: f64,
    #[pyo3(get, set)] tau_max: f64,
    #[pyo3(get, set)] non_negative: bool,
    #[pyo3(get, set)] max_iter: usize,
}

#[pymethods]
impl PyDRTParams {
    #[new]
    fn new() -> Self {
        PyDRTParams {
            lambda_: 1e-3, n_tau: 200, tau_min: 1e-7,
            tau_max: 1e3, non_negative: true, max_iter: 100,
        }
    }
}

#[pyclass]
struct PyDRTResult {
    #[pyo3(get)] tau: Py<PyArray1<f64>>,
    #[pyo3(get)] gamma: Py<PyArray1<f64>>,
    #[pyo3(get)] Z_fit_real: Py<PyArray1<f64>>,
    #[pyo3(get)] Z_fit_imag: Py<PyArray1<f64>>,
    #[pyo3(get)] R_inf: f64,
    #[pyo3(get)] R_pol: f64,
    #[pyo3(get)] residual: f64,
    #[pyo3(get)] lambda_used: f64,
}

#[pyfunction]
fn compute_drt_py(
    py: Python,
    frequencies: PyReadonlyArray1<f64>,
    z_real: PyReadonlyArray1<f64>,
    z_imag: PyReadonlyArray1<f64>,
    params: &PyDRTParams,
) -> PyResult<PyDRTResult> {
    let p = DRTParams {
        lambda: params.lambda_, n_tau: params.n_tau,
        tau_min: params.tau_min, tau_max: params.tau_max,
        non_negative: params.non_negative, max_iter: params.max_iter,
    };
    let res = compute_drt(
        &frequencies.as_array().to_owned(),
        &z_real.as_array().to_owned(),
        &z_imag.as_array().to_owned(),
        &p,
    );
    Ok(PyDRTResult {
        tau: res.tau.into_pyarray(py).into(),
        gamma: res.gamma.into_pyarray(py).into(),
        Z_fit_real: res.Z_fit_real.into_pyarray(py).into(),
        Z_fit_imag: res.Z_fit_imag.into_pyarray(py).into(),
        R_inf: res.R_inf, R_pol: res.R_pol,
        residual: res.residual, lambda_used: res.lambda_used,
    })
}

#[pyclass]
struct PyKKResult {
    #[pyo3(get)] is_valid: bool,
    #[pyo3(get)] mu: f64,
    #[pyo3(get)] residual_real: Py<PyArray1<f64>>,
    #[pyo3(get)] residual_imag: Py<PyArray1<f64>>,
    #[pyo3(get)] max_residual_real: f64,
    #[pyo3(get)] max_residual_imag: f64,
    #[pyo3(get)] mean_residual: f64,
    #[pyo3(get)] Z_fit_real: Py<PyArray1<f64>>,
    #[pyo3(get)] Z_fit_imag: Py<PyArray1<f64>>,
    #[pyo3(get)] tau: Py<PyArray1<f64>>,
    #[pyo3(get)] R: Py<PyArray1<f64>>,
    #[pyo3(get)] R_inf: f64,
    #[pyo3(get)] n_rc_used: i32,
}

#[pyfunction]
fn kramers_kronig_test_py(
    py: Python,
    frequencies: PyReadonlyArray1<f64>,
    z_real: PyReadonlyArray1<f64>,
    z_imag: PyReadonlyArray1<f64>,
    n_rc: i32,
) -> PyResult<PyKKResult> {
    let res = kramers_kronig_test(
        &frequencies.as_array().to_owned(),
        &z_real.as_array().to_owned(),
        &z_imag.as_array().to_owned(),
        n_rc,
    );
    Ok(PyKKResult {
        is_valid: res.is_valid, mu: res.mu,
        residual_real: res.residual_real.into_pyarray(py).into(),
        residual_imag: res.residual_imag.into_pyarray(py).into(),
        max_residual_real: res.max_residual_real,
        max_residual_imag: res.max_residual_imag,
        mean_residual: res.mean_residual,
        Z_fit_real: res.Z_fit_real.into_pyarray(py).into(),
        Z_fit_imag: res.Z_fit_imag.into_pyarray(py).into(),
        tau: res.tau.into_pyarray(py).into(),
        R: res.R.into_pyarray(py).into(),
        R_inf: res.R_inf, n_rc_used: res.n_rc_used,
    })
}

// ── Circuit Fitter ────────────────────────────────────────

#[pyclass]
#[derive(Clone, Debug, Copy)]
enum PyCircuitType {
    RANDLES = 0,
    R_RC = 1,
    R_RC_RC = 2,
}

#[pyclass]
struct PyFitParams {
    #[pyo3(get, set)] circuit: PyCircuitType,
    #[pyo3(get, set)] max_iter: i32,
    #[pyo3(get, set)] tol: f64,
    #[pyo3(get, set)] lambda_init: f64,
    #[pyo3(get, set)] lambda_up: f64,
    #[pyo3(get, set)] lambda_down: f64,
}

#[pymethods]
impl PyFitParams {
    #[new]
    fn new() -> Self {
        PyFitParams {
            circuit: PyCircuitType::RANDLES,
            max_iter: 200, tol: 1e-8,
            lambda_init: 1e-3, lambda_up: 10.0, lambda_down: 0.1,
        }
    }
}

#[pyclass]
struct PyFitResult {
    #[pyo3(get)] params: Py<PyArray1<f64>>,
    #[pyo3(get)] errors: Py<PyArray1<f64>>,
    #[pyo3(get)] Z_fit_real: Py<PyArray1<f64>>,
    #[pyo3(get)] Z_fit_imag: Py<PyArray1<f64>>,
    #[pyo3(get)] chi_squared: f64,
    #[pyo3(get)] reduced_chi_sq: f64,
    #[pyo3(get)] iterations: i32,
    #[pyo3(get)] converged: bool,
}

#[pyfunction]
fn fit_circuit_py(
    py: Python,
    frequencies: PyReadonlyArray1<f64>,
    z_real: PyReadonlyArray1<f64>,
    z_imag: PyReadonlyArray1<f64>,
    initial: PyReadonlyArray1<f64>,
    params: &PyFitParams,
) -> PyResult<PyFitResult> {
    let ct = match params.circuit {
        PyCircuitType::RANDLES => CircuitType::RANDLES,
        PyCircuitType::R_RC => CircuitType::R_RC,
        PyCircuitType::R_RC_RC => CircuitType::R_RC_RC,
    };
    let p = FitParams {
        circuit: ct, max_iter: params.max_iter,
        tol: params.tol, lambda_init: params.lambda_init,
        lambda_up: params.lambda_up, lambda_down: params.lambda_down,
    };
    let res = fit_circuit(
        &frequencies.as_array().to_owned(),
        &z_real.as_array().to_owned(),
        &z_imag.as_array().to_owned(),
        &initial.as_array().to_owned(),
        &p,
    );
    Ok(PyFitResult {
        params: res.params.into_pyarray(py).into(),
        errors: res.errors.into_pyarray(py).into(),
        Z_fit_real: res.Z_fit_real.into_pyarray(py).into(),
        Z_fit_imag: res.Z_fit_imag.into_pyarray(py).into(),
        chi_squared: res.chi_squared,
        reduced_chi_sq: res.reduced_chi_sq,
        iterations: res.iterations,
        converged: res.converged,
    })
}

#[pyfunction]
fn randles_model_py(
    py: Python,
    frequencies: PyReadonlyArray1<f64>,
    p: PyReadonlyArray1<f64>,
) -> PyResult<(Py<PyArray1<f64>>, Py<PyArray1<f64>>)> {
    let (zr, zi) = randles_model(&frequencies.as_array().to_owned(), &p.as_array().to_owned());
    Ok((zr.into_pyarray(py).into(), zi.into_pyarray(py).into()))
}

// ── Module ────────────────────────────────────────────────

#[pymodule]
fn raman_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", "2.0.0")?;

    m.add_class::<PyEISParams>()?;
    m.add_class::<PyEISResult>()?;
    m.add_wrapped(wrap_pyfunction!(simulate_eis_py))?;
    m.add_wrapped(wrap_pyfunction!(randles_impedance_py))?;
    m.add_wrapped(wrap_pyfunction!(quick_eis_py))?;

    m.add_class::<PyCVParams>()?;
    m.add_class::<PyCVResult>()?;
    m.add_wrapped(wrap_pyfunction!(simulate_cv_py))?;
    m.add_wrapped(wrap_pyfunction!(randles_sevcik_ip_py))?;

    m.add_wrapped(wrap_pyfunction!(solve_diffusion_1d_py))?;
    m.add_wrapped(wrap_pyfunction!(solve_spherical_diffusion_py))?;

    m.add_class::<PyDRTParams>()?;
    m.add_class::<PyDRTResult>()?;
    m.add_wrapped(wrap_pyfunction!(compute_drt_py))?;
    m.add_class::<PyKKResult>()?;
    m.add_wrapped(wrap_pyfunction!(kramers_kronig_test_py))?;

    m.add_class::<PyCircuitType>()?;
    m.add_class::<PyFitParams>()?;
    m.add_class::<PyFitResult>()?;
    m.add_wrapped(wrap_pyfunction!(fit_circuit_py))?;
    m.add_wrapped(wrap_pyfunction!(randles_model_py))?;

    Ok(())
}
