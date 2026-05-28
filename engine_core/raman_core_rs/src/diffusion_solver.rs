use ndarray::Array1;

fn thomas_solve(a: &Array1<f64>, b: &Array1<f64>, c: &Array1<f64>, d: &Array1<f64>) -> Array1<f64> {
    let n = d.len();
    let mut cp = Array1::zeros(n);
    let mut dp = Array1::zeros(n);
    let mut x = Array1::zeros(n);

    cp[0] = c[0] / b[0];
    dp[0] = d[0] / b[0];

    for i in 1..n {
        let mut m = b[i] - a[i] * cp[i - 1];
        if m.abs() < 1e-30 {
            m = 1e-30;
        }
        cp[i] = if i < n - 1 { c[i] / m } else { 0.0 };
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m;
    }

    x[n - 1] = dp[n - 1];
    for i in (0..n - 1).rev() {
        x[i] = dp[i] - cp[i] * x[i + 1];
    }

    x
}

pub fn solve_diffusion_1d(
    d_cm2s: f64,
    c_bulk_m: f64,
    l_cm: f64,
    n_spatial: usize,
    n_time: usize,
    dt_s: f64,
    surface_flux: &Array1<f64>,
) -> Array1<f64> {
    let dx = l_cm / (n_spatial as f64 - 1.0);
    let r = d_cm2s * dt_s / (2.0 * dx * dx);

    let mut c = Array1::from_elem(n_spatial, c_bulk_m * 1e-3);

    let mut a_coeff = Array1::from_elem(n_spatial, -r);
    let mut b_coeff = Array1::from_elem(n_spatial, 1.0 + 2.0 * r);
    let mut c_coeff = Array1::from_elem(n_spatial, -r);

    a_coeff[0] = 0.0;
    c_coeff[n_spatial - 1] = 0.0;

    let mut rhs = Array1::zeros(n_spatial);

    for t in 0..n_time {
        for i in 1..(n_spatial - 1) {
            rhs[i] = r * c[i - 1] + (1.0 - 2.0 * r) * c[i] + r * c[i + 1];
        }

        let flux_t = if t < surface_flux.len() {
            surface_flux[t]
        } else {
            0.0
        };
        rhs[0] = c[0] - flux_t * dx / d_cm2s;
        b_coeff[0] = 1.0;

        rhs[n_spatial - 1] = c_bulk_m * 1e-3;
        b_coeff[n_spatial - 1] = 1.0;

        c = thomas_solve(&a_coeff, &b_coeff, &c_coeff, &rhs);

        for i in 0..n_spatial {
            if c[i] < 0.0 {
                c[i] = 0.0;
            }
        }
    }

    c
}

pub fn solve_spherical_diffusion(
    d_cm2s: f64,
    c_max_m: f64,
    c_init_frac: f64,
    radius_um: f64,
    n_radial: usize,
    n_time: usize,
    dt_s: f64,
    surface_flux: &Array1<f64>,
) -> Array1<f64> {
    let r_cm = radius_um * 1e-4;
    let dr = r_cm / (n_radial as f64 - 1.0);

    let mut r_grid = Array1::zeros(n_radial);
    for i in 0..n_radial {
        r_grid[i] = if i == 0 { dr * 0.01 } else { i as f64 * dr };
    }

    let c_init = c_max_m * c_init_frac * 1e-3;
    let mut c = Array1::from_elem(n_radial, c_init);
    let mut c_surface = Array1::zeros(n_time);

    let mut a_coeff = Array1::zeros(n_radial);
    let mut b_coeff = Array1::zeros(n_radial);
    let mut c_coeff = Array1::zeros(n_radial);
    let mut rhs = Array1::zeros(n_radial);

    for t in 0..n_time {
        for i in 1..(n_radial - 1) {
            let ri = r_grid[i];
            let alpha_m = d_cm2s * dt_s / (2.0 * dr * dr);
            let beta = d_cm2s * dt_s / (2.0 * ri * dr);

            a_coeff[i] = -(alpha_m - beta);
            b_coeff[i] = 1.0 + 2.0 * alpha_m;
            c_coeff[i] = -(alpha_m + beta);

            rhs[i] = (alpha_m - beta) * c[i - 1]
                + (1.0 - 2.0 * alpha_m) * c[i]
                + (alpha_m + beta) * c[i + 1];
        }

        a_coeff[0] = 0.0;
        b_coeff[0] = 1.0;
        c_coeff[0] = -1.0;
        rhs[0] = 0.0;

        let flux_t = if t < surface_flux.len() {
            surface_flux[t]
        } else {
            0.0
        };
        a_coeff[n_radial - 1] = -1.0;
        b_coeff[n_radial - 1] = 1.0;
        c_coeff[n_radial - 1] = 0.0;
        rhs[n_radial - 1] = flux_t * dr / d_cm2s;

        c = thomas_solve(&a_coeff, &b_coeff, &c_coeff, &rhs);

        let c_max_cm3 = c_max_m * 1e-3;
        for i in 0..n_radial {
            if c[i] < 0.0 {
                c[i] = 0.0;
            }
            if c[i] > c_max_cm3 {
                c[i] = c_max_cm3;
            }
        }

        c_surface[t] = c[n_radial - 1];
    }

    c_surface
}
