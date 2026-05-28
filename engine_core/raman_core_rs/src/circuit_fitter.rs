use crate::types::*;
use ndarray::{Array1, Array2, s};

pub fn randles_model(frequencies: &Array1<f64>, p: &Array1<f64>) -> (Array1<f64>, Array1<f64>) {
    let m = frequencies.len();
    let mut z_re = Array1::zeros(m);
    let mut z_im = Array1::zeros(m);

    let rs = p[0];
    let rct = p[1];
    let q0 = p[2];
    let n = p[3];
    let sigma = p[4];

    for (i, (zr, zi)) in z_re.iter_mut().zip(z_im.iter_mut()).enumerate() {
            let w = 2.0 * PI * frequencies[i];
            let sw = sigma / w.sqrt();
            let zw_re = sw;
            let zw_im = -sw;

            let zf_re = rct + zw_re;
            let zf_im = zw_im;

            let wn = w.powf(n);
            let yc_re = q0 * wn * (n * PI / 2.0).cos();
            let yc_im = q0 * wn * (n * PI / 2.0).sin();

            let d = zf_re * zf_re + zf_im * zf_im;
            let yf_re = zf_re / d;
            let yf_im = -zf_im / d;

            let yt_re = yc_re + yf_re;
            let yt_im = yc_im + yf_im;

            let d2 = yt_re * yt_re + yt_im * yt_im;
            *zr = rs + yt_re / d2;
            *zi = -yt_im / d2;
        }

    (z_re, z_im)
}

fn r_rc_model(frequencies: &Array1<f64>, p: &Array1<f64>) -> (Array1<f64>, Array1<f64>) {
    let m = frequencies.len();
    let mut z_re = Array1::zeros(m);
    let mut z_im = Array1::zeros(m);
    let rs = p[0];
    let r1 = p[1];
    let c1 = p[2];

    for i in 0..m {
        let w = 2.0 * PI * frequencies[i];
        let wrc = w * r1 * c1;
        let d = 1.0 + wrc * wrc;
        z_re[i] = rs + r1 / d;
        z_im[i] = -r1 * wrc / d;
    }
    (z_re, z_im)
}

fn r_rc_rc_model(frequencies: &Array1<f64>, p: &Array1<f64>) -> (Array1<f64>, Array1<f64>) {
    let m = frequencies.len();
    let mut z_re = Array1::zeros(m);
    let mut z_im = Array1::zeros(m);
    let rs = p[0];
    let r1 = p[1];
    let c1 = p[2];
    let r2 = p[3];
    let c2 = p[4];

    for i in 0..m {
        let w = 2.0 * PI * frequencies[i];
        let wrc1 = w * r1 * c1;
        let wrc2 = w * r2 * c2;
        let d1 = 1.0 + wrc1 * wrc1;
        let d2 = 1.0 + wrc2 * wrc2;
        z_re[i] = rs + r1 / d1 + r2 / d2;
        z_im[i] = -r1 * wrc1 / d1 - r2 * wrc2 / d2;
    }
    (z_re, z_im)
}

fn compute_model(
    ct: CircuitType,
    freq: &Array1<f64>,
    p: &Array1<f64>,
) -> (Array1<f64>, Array1<f64>) {
    match ct {
        CircuitType::RANDLES => randles_model(freq, p),
        CircuitType::R_RC => r_rc_model(freq, p),
        CircuitType::R_RC_RC => r_rc_rc_model(freq, p),
    }
}

fn compute_jacobian(
    ct: CircuitType,
    freq: &Array1<f64>,
    p: &Array1<f64>,
    m: usize,
) -> Array2<f64> {
    let n = p.len();
    let mut j = Array2::zeros((2 * m, n));

    for jj in 0..n {
        let mut pp = p.clone();
        let mut pm = p.clone();
        let h = (1e-8f64).max(p[jj].abs() * 1e-6);
        pp[jj] += h;
        pm[jj] -= h;

        let (zr_p, zi_p) = compute_model(ct, freq, &pp);
        let (zr_m, zi_m) = compute_model(ct, freq, &pm);

        for mm in 0..m {
            j[[mm, jj]] = (zr_p[mm] - zr_m[mm]) / (2.0 * h);
            j[[m + mm, jj]] = (zi_p[mm] - zi_m[mm]) / (2.0 * h);
        }
    }
    j
}

pub fn fit_circuit(
    frequencies: &Array1<f64>,
    z_real: &Array1<f64>,
    z_imag: &Array1<f64>,
    initial: &Array1<f64>,
    params: &FitParams,
) -> FitResult {
    let m = frequencies.len();
    let n = initial.len();

    let mut p = initial.clone();
    let mut lambda = params.lambda_init;

    let (zr_calc, zi_calc) = compute_model(params.circuit, frequencies, &p);

    let mut r = Array1::zeros(2 * m);
    for i in 0..m {
        r[i] = z_real[i] - zr_calc[i];
        r[m + i] = z_imag[i] - zi_calc[i];
    }
    let mut chi2 = r.iter().map(|&x| x * x).sum::<f64>();

    let mut result = FitResult {
        converged: false,
        ..FitResult::default()
    };
    let mut iter = 0;

    for _ in 0..params.max_iter {
        let j = compute_jacobian(params.circuit, frequencies, &p, m);
        let jt = j.t();
        let jtj = &jt.dot(&j);
        let jtr = &jt.dot(&r);

        let mut h = jtj.clone();
        for i in 0..n {
            h[[i, i]] += lambda * jtj[[i, i]];
        }

        let delta = solve_ldlt(&h, jtr);
        let mut p_new = &p + &delta;

        for i in 0..n {
            if p_new[i] < 1e-15 {
                p_new[i] = 1e-15;
            }
        }

        let (zr_new, zi_new) = compute_model(params.circuit, frequencies, &p_new);
        let mut r_new = Array1::zeros(2 * m);
        for i in 0..m {
            r_new[i] = z_real[i] - zr_new[i];
            r_new[m + i] = z_imag[i] - zi_new[i];
        }
        let chi2_new = r_new.iter().map(|&x| x * x).sum::<f64>();

        if chi2_new < chi2 {
            p = p_new;
            r = r_new;
            chi2 = chi2_new;
            lambda *= params.lambda_down;

            if delta.norm_l2() < params.tol * p.norm_l2() {
                result.converged = true;
                break;
            }
        } else {
            lambda *= params.lambda_up;
        }
        iter += 1;
    }

    result.params = p.clone();
    let (zr_final, zi_final) = compute_model(params.circuit, frequencies, &p);
    result.Z_fit_real = zr_final;
    result.Z_fit_imag = zi_final;
    result.chi_squared = chi2;
    result.reduced_chi_sq = chi2 / (2.0 * m as f64 - n as f64).max(1.0);
    result.iterations = iter;

    let j = compute_jacobian(params.circuit, frequencies, &p, m);
    let jt = j.t();
    let jtj = jt.dot(&j);
    match jtj.inv() {
        Ok(cov_base) => {
            let cov = cov_base * result.reduced_chi_sq;
            let mut errors = Array1::zeros(n);
            for i in 0..n {
                errors[i] = cov[[i, i]].max(0.0).sqrt();
            }
            result.errors = errors;
        }
        Err(_) => {
            result.errors = Array1::from_elem(n, 1e6);
        }
    }

    result
}

fn solve_ldlt(a: &Array2<f64>, b: &Array1<f64>) -> Array1<f64> {
    let n = a.nrows();
    let mut x = b.clone();

    // LDL^T decomposition
    let mut l = Array2::<f64>::eye(n);
    let mut d = Array1::<f64>::zeros(n);

    for j in 0..n {
        let mut sum = a[[j, j]];
        for k in 0..j {
            sum -= l[[j, k]] * l[[j, k]] * d[k];
        }
        d[j] = sum;

        for i in (j + 1)..n {
            let mut sum2 = a[[i, j]];
            for k in 0..j {
                sum2 -= l[[i, k]] * l[[j, k]] * d[k];
            }
            l[[i, j]] = sum2 / d[j];
        }
    }

    // Forward substitution: Ly = b
    let mut y = b.clone();
    for i in 0..n {
        for j in 0..i {
            y[i] -= l[[i, j]] * y[j];
        }
    }

    // Diagonal solve: Dz = y
    let mut z = y.clone();
    for i in 0..n {
        z[i] /= d[i];
    }

    // Backward substitution: L^T x = z
    for i in (0..n).rev() {
        for j in (i + 1)..n {
            z[i] -= l[[j, i]] * z[j];
        }
        x[i] = z[i];
    }

    x
}

// Manual LDL^T doesn't have inv(), so we compute inverse via solve for identity columns
// Actually, let's use a simpler approach - we can use a basic Gauss-Jordan for small matrices
pub trait MatrixInv {
    fn inv(&self) -> Result<Array2<f64>, String>;
}

impl MatrixInv for Array2<f64> {
    fn inv(&self) -> Result<Array2<f64>, String> {
        let n = self.nrows();
        if n != self.ncols() {
            return Err("Not square".to_string());
        }

        // Augmented matrix [A | I]
        let mut aug = Array2::<f64>::zeros((n, 2 * n));
        for i in 0..n {
            for j in 0..n {
                aug[[i, j]] = self[[i, j]];
            }
            aug[[i, n + i]] = 1.0;
        }

        // Gauss-Jordan elimination
        for i in 0..n {
            let mut pivot = aug[[i, i]];
            if pivot.abs() < 1e-30 {
                // Find swap row
                let mut swap = None;
                for k in (i + 1)..n {
                    if aug[[k, i]].abs() > 1e-30 {
                        swap = Some(k);
                        break;
                    }
                }
                match swap {
                    Some(k) => {
                        for col in 0..(2 * n) {
                            let tmp = aug[[i, col]];
                            aug[[i, col]] = aug[[k, col]];
                            aug[[k, col]] = tmp;
                        }
                        pivot = aug[[i, i]];
                    }
                    None => return Err("Singular matrix".to_string()),
                }
            }

            for col in 0..(2 * n) {
                aug[[i, col]] /= pivot;
            }

            for row in 0..n {
                if row != i {
                    let factor = aug[[row, i]];
                    for col in 0..(2 * n) {
                        aug[[row, col]] -= factor * aug[[i, col]];
                    }
                }
            }
        }

        let mut inv = Array2::<f64>::zeros((n, n));
        for i in 0..n {
            for j in 0..n {
                inv[[i, j]] = aug[[i, n + j]];
            }
        }
        Ok(inv)
    }
}

pub trait NormL2 {
    fn norm_l2(&self) -> f64;
}

impl NormL2 for Array1<f64> {
    fn norm_l2(&self) -> f64 {
        self.iter().map(|&x| x * x).sum::<f64>().sqrt()
    }
}
