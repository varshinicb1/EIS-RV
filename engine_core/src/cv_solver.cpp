/**
 * RĀMAN Studio — CV Solver Implementation
 * =========================================
 * Convolution-based cyclic voltammetry solver with Butler-Volmer kinetics.
 *
 * Algorithm (Nicholson-Shain):
 *   At each time step k, solve for surface flux j(k):
 *     j(k) = [kf·C_ox_surf - kb·C_red_surf] / (1 + kf·S0_ox + kb·S0_red)
 *   where surface concentrations come from the convolution integral.
 *
 * This matches Gamry Echem Analyst and the Python reference.
 */

#include "raman/cv_solver.hpp"
#include <cmath>
#include <algorithm>
#include <numeric>

namespace raman {

// ── Helper: build triangular waveform ─────────────────────

static void build_waveform(const CVParams& p, int n_per_seg,
                           VecD& E_out, VecD& t_out) {
    std::vector<double> E_vec;
    E_vec.reserve(n_per_seg * 3 * p.n_cycles);

    for (int cyc = 0; cyc < p.n_cycles; ++cyc) {
        // Forward: E_start → E_vertex
        for (int i = 0; i < n_per_seg; ++i) {
            double frac = static_cast<double>(i) / n_per_seg;
            E_vec.push_back(p.E_start_V + frac * (p.E_vertex_V - p.E_start_V));
        }
        // Reverse: E_vertex → E_end
        for (int i = 0; i < n_per_seg; ++i) {
            double frac = static_cast<double>(i) / n_per_seg;
            E_vec.push_back(p.E_vertex_V + frac * (p.E_end_V - p.E_vertex_V));
        }
        // Return to start if needed
        if (std::abs(p.E_end_V - p.E_start_V) > 1e-6) {
            int n_ret = n_per_seg / 2;
            for (int i = 0; i <= n_ret; ++i) {
                double frac = static_cast<double>(i) / n_ret;
                E_vec.push_back(p.E_end_V + frac * (p.E_start_V - p.E_end_V));
            }
        }
    }

    int N = static_cast<int>(E_vec.size());
    E_out.resize(N);
    t_out.resize(N);

    for (int i = 0; i < N; ++i) E_out(i) = E_vec[i];

    double dE = (N > 1) ? std::abs(E_vec[1] - E_vec[0]) : 1e-4;
    double dt = dE / p.scan_rate_V_s;
    for (int i = 0; i < N; ++i) t_out(i) = i * dt;
}


// ── Main CV solver ────────────────────────────────────────

CVResult simulate_cv(const CVParams& p, int n_points) {
    CVResult result;
    result.params = p;

    double A_eff = p.area_cm2 * p.roughness;
    double f_val = FARADAY / (R_GAS * p.temperature_K);  // F/RT

    // Build waveform
    build_waveform(p, n_points, result.E, result.time);
    int N = static_cast<int>(result.E.size());
    double dt = (N > 1) ? (result.time(1) - result.time(0)) : 1e-4;

    double C_bulk_ox  = p.C_ox_M * 1e-3;   // mol/cm³
    double C_bulk_red = p.C_red_M * 1e-3;

    result.i_faradaic.resize(N);
    result.i_capacitive.resize(N);
    result.i_total.resize(N);

    // Precompute convolution kernel: S[m] = 2√(dt/πD)(√(m+1) - √m)
    std::vector<double> sqrt_vals(N + 1);
    for (int i = 0; i <= N; ++i) sqrt_vals[i] = std::sqrt(static_cast<double>(i));

    double coeff_ox  = 2.0 * std::sqrt(dt / (PI * p.D_ox_cm2s));
    double coeff_red = 2.0 * std::sqrt(dt / (PI * p.D_red_cm2s));

    std::vector<double> S_diff(N);
    for (int i = 0; i < N; ++i) S_diff[i] = sqrt_vals[i + 1] - sqrt_vals[i];

    std::vector<double> flux(N, 0.0);

    for (int k = 0; k < N; ++k) {
        double E = result.E(k);
        double eta = E - p.E_formal_V;

        // Butler-Volmer rate constants
        double arg_fwd = std::clamp(-p.alpha * p.n_electrons * f_val * eta, -30.0, 30.0);
        double arg_rev = std::clamp((1.0 - p.alpha) * p.n_electrons * f_val * eta, -30.0, 30.0);
        double kf = p.k0_cm_s * std::exp(arg_fwd);
        double kb = p.k0_cm_s * std::exp(arg_rev);

        // Convolution for surface concentrations
        double conv_ox = 0.0, conv_red = 0.0;
        for (int m = 0; m < k; ++m) {
            double S_val = S_diff[k - 1 - m];
            conv_ox  += flux[m] * S_val;
            conv_red += flux[m] * S_val;
        }
        conv_ox  *= coeff_ox;
        conv_red *= coeff_red;

        double C_ox_surf  = std::max(C_bulk_ox  - conv_ox,  0.0);
        double C_red_surf = std::max(C_bulk_red + conv_red, 0.0);

        // Implicit flux solve
        double S0_ox  = coeff_ox  * S_diff[0];
        double S0_red = coeff_red * S_diff[0];
        double denom  = 1.0 + kf * S0_ox + kb * S0_red;
        double j_net  = (kf * C_ox_surf - kb * C_red_surf) / std::max(denom, 1e-30);

        flux[k] = j_net;
        result.i_faradaic(k) = p.n_electrons * FARADAY * A_eff * j_net;

        // Capacitive current: i_cap = Cdl · A · dE/dt
        double dEdt = (k > 0) ? (result.E(k) - result.E(k - 1)) / dt : p.scan_rate_V_s;
        result.i_capacitive(k) = p.Cdl_F_cm2 * A_eff * dEdt;
    }

    result.i_total = result.i_faradaic + result.i_capacitive;

    // ── Peak analysis ─────────────────────────────────────
    int half = N / 2;
    bool fwd_anodic = p.E_start_V < p.E_vertex_V;

    if (fwd_anodic) {
        // Forward sweep → anodic peak (max of i_total in first half)
        int idx_pa = 0;
        double max_i = result.i_total(0);
        for (int i = 1; i < half; ++i) {
            if (result.i_total(i) > max_i) {
                max_i = result.i_total(i);
                idx_pa = i;
            }
        }
        result.i_pa = max_i;
        result.E_pa = result.E(idx_pa);

        // Reverse → cathodic peak (min of i_total in second half)
        int idx_pc = half;
        double min_i = result.i_total(half);
        for (int i = half + 1; i < N; ++i) {
            if (result.i_total(i) < min_i) {
                min_i = result.i_total(i);
                idx_pc = i;
            }
        }
        result.i_pc = min_i;
        result.E_pc = result.E(idx_pc);
    } else {
        // Forward cathodic
        int idx_pc = 0;
        double min_i = result.i_total(0);
        for (int i = 1; i < half; ++i) {
            if (result.i_total(i) < min_i) {
                min_i = result.i_total(i);
                idx_pc = i;
            }
        }
        result.i_pc = min_i;
        result.E_pc = result.E(idx_pc);

        int idx_pa = half;
        double max_i = result.i_total(half);
        for (int i = half + 1; i < N; ++i) {
            if (result.i_total(i) > max_i) {
                max_i = result.i_total(i);
                idx_pa = i;
            }
        }
        result.i_pa = max_i;
        result.E_pa = result.E(idx_pa);
    }

    result.dEp = std::abs(result.E_pa - result.E_pc);

    return result;
}


// ── Randles-Sevcik ────────────────────────────────────────

double randles_sevcik_ip(int n, double A_cm2, double C_M,
                         double D_cm2s, double v_Vs, double T_K) {
    double C_cm3 = C_M * 1e-3;  // mol/L → mol/cm³
    double n15 = std::pow(static_cast<double>(n), 1.5);
    double F15 = std::pow(FARADAY, 1.5);
    return 0.4463 * n15 * F15 * A_cm2 * C_cm3 *
           std::sqrt(D_cm2s * v_Vs / (R_GAS * T_K));
}

}  // namespace raman
