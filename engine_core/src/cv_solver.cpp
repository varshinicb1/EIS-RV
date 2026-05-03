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

    // Resize result.E_actual and result.i_actual_E to record the iR-corrected
    // electrode potential per step (matches result.E when Rs_ohm == 0).
    result.E_actual.resize(N);

    // ── Per-step solve with optional iR-drop correction ──────────
    //
    // The user supplies the SET potential E (the waveform). With
    // uncompensated resistance Rs > 0, the working electrode actually
    // sees E_actual = E_set - i*Rs. Since i depends on E_actual via the
    // Butler-Volmer kinetics, this is a fixed-point problem: solve for
    // j_net such that
    //
    //     j_net  =  [kf(E_actual)·Cox_surf − kb(E_actual)·Cred_surf]
    //               / (1 + kf(E_actual)·S0_ox + kb(E_actual)·S0_red)
    //
    //     E_actual  =  E_set − (n·F·A·j_net)·Rs
    //
    // We use damped fixed-point iteration. With Rs == 0 the loop falls
    // through after one pass (trivially converges).
    const double Rs = std::max(p.Rs_ohm, 0.0);
    const double i_to_dropV = p.n_electrons * FARADAY * A_eff * Rs;
    const double FP_TOL = 1e-12;       // mol/cm²/s
    const int    FP_MAX_ITERS = (Rs > 0.0) ? 20 : 1;

    // ── Boundary-condition strategy (audit C2 fix) ──────────────
    //
    // The original BV-only solver oscillates whenever the kinetic
    // timescale 1/(kf+kb) is much smaller than the convolution
    // timescale (S0 = coeff·√(dt) where coeff ∝ √(dt/D)). When the
    // dimensionless ratio
    //
    //     Λ_step  ≡  max(kf, kb) · S0
    //
    // exceeds ~1, the surface is already in Nernstian equilibrium and
    // BV's implicit linear solve becomes ill-conditioned: the term
    // (1 + kf·S0) absorbs essentially all of the kinetic stiffness and
    // history-corrected concentrations skip about zero between
    // timesteps. The fix:
    //
    //   * NERNSTIAN regime (Λ_step > NERNSTIAN_LAMBDA_THRESHOLD):
    //     close the boundary using Nernst (C_ox_surf / C_red_surf =
    //     exp(-n·F·η/RT)) + the convolution mass balance. Closed-form,
    //     no iteration, numerically stable for arbitrarily fast
    //     kinetics.
    //
    //   * BV regime (slow / quasi-reversible / irreversible): standard
    //     implicit BV solve with the textbook clamp on history-corrected
    //     concentrations. Correct in this regime; was already producing
    //     the right answers for k0 ≪ 1.
    //
    // The two branches agree exactly in the reversible limit, so the
    // hand-off doesn't introduce a discontinuity.
    constexpr double NERNSTIAN_LAMBDA_THRESHOLD = 1.0;

    for (int k = 0; k < N; ++k) {
        const double E_set = result.E(k);

        // Convolution-based history terms (independent of E_actual).
        double conv_ox = 0.0, conv_red = 0.0;
        for (int m = 0; m < k; ++m) {
            const double S_val = S_diff[k - 1 - m];
            conv_ox  += flux[m] * S_val;
            conv_red += flux[m] * S_val;
        }
        conv_ox  *= coeff_ox;
        conv_red *= coeff_red;

        // History contributes to the surface concentration via:
        //     C_ox_surf  = C_bulk_ox  - history_ox  - S0_ox·flux[k]
        //     C_red_surf = C_bulk_red + history_red + S0_red·flux[k]
        // The implicit BV solve below treats S0·flux[k] as part of the
        // unknown; the Nernstian branch does the same, just from the
        // ratio constraint.
        const double S0_ox  = coeff_ox  * S_diff[0];
        const double S0_red = coeff_red * S_diff[0];

        // Initial guess for j: previous step's flux. For k=0 use 0.
        double j_net = (k > 0) ? flux[k - 1] : 0.0;
        double E_actual = E_set;

        for (int iter = 0; iter < FP_MAX_ITERS; ++iter) {
            // Update E_actual from current j_net guess (iR drop).
            const double E_new_actual = E_set - i_to_dropV * j_net;
            E_actual = 0.5 * (E_actual + E_new_actual);

            const double eta = E_actual - p.E_formal_V;
            const double dimless = p.n_electrons * f_val * eta;   // n·F·η/RT
            double j_new = 0.0;

            // Decide BV vs Nernstian for this step. We base the
            // decision on the kinetic-vs-mass-transport ratio
            //   Λ_step = max(kf, kb) · S0
            // computed with kf, kb evaluated at the same E_actual the
            // BV branch would use. If either rate is large enough that
            // Λ_step > threshold, we switch to the Nernstian closed form.
            // Compute kf, kb (with the standard clamp) for the test.
            const double arg_fwd_test = std::clamp(-p.alpha * dimless, -30.0, 30.0);
            const double arg_rev_test = std::clamp((1.0 - p.alpha) * dimless, -30.0, 30.0);
            const double kf_test = p.k0_cm_s * std::exp(arg_fwd_test);
            const double kb_test = p.k0_cm_s * std::exp(arg_rev_test);
            const double lambda_step = std::max(kf_test * S0_ox, kb_test * S0_red);

            if (lambda_step > NERNSTIAN_LAMBDA_THRESHOLD) {
                // ── Nernstian branch ───────────────────────
                //
                // Closure constraint, derived from kf·C_ox = kb·C_red at
                // equilibrium with this code's BV convention (kf grows at
                // η < 0, kb grows at η > 0):
                //
                //     C_ox_surf / C_red_surf  =  kb/kf  =  exp(-dimless)
                //
                // Mass balance:
                //     C_ox_surf  = C_bulk_ox  - conv_ox  - S0_ox·j
                //     C_red_surf = C_bulk_red + conv_red + S0_red·j
                //
                // Setting the ratio constraint:
                //
                //     j (S0_ox + ξ·S0_red)  =  (C_bulk_ox - conv_ox) - ξ·(C_bulk_red + conv_red)
                //         where ξ = exp(-dimless)
                //
                // For very negative η (large positive |dimless|), ξ → ∞
                // and we rescale by min(1, 1/ξ) to keep the linear
                // system well-conditioned.
                const double dimless_clipped = std::clamp(-dimless, -700.0, 700.0);
                const double xi = std::exp(dimless_clipped);

                // scale = min(1, 1/ξ) keeps both ξ_s and one_s in (0, 1].
                const double scale = std::exp(-std::max(dimless_clipped, 0.0));
                const double xi_s   = xi * scale;
                const double one_s  = 1.0 * scale;

                const double numerator =
                    (C_bulk_ox  - conv_ox)  * one_s
                  - (C_bulk_red + conv_red) * xi_s;
                const double denom_n =
                    S0_ox * one_s + S0_red * xi_s;
                j_new = numerator / std::max(denom_n, 1e-300);
            } else {
                // ── Butler-Volmer branch (slow / quasi-reversible) ──
                const double C_ox_surf  = std::max(C_bulk_ox  - conv_ox,  0.0);
                const double C_red_surf = std::max(C_bulk_red + conv_red, 0.0);
                const double denom = 1.0 + kf_test * S0_ox + kb_test * S0_red;
                j_new = (kf_test * C_ox_surf - kb_test * C_red_surf)
                        / std::max(denom, 1e-30);
            }

            if (std::abs(j_new - j_net) < FP_TOL) {
                j_net = j_new;
                break;
            }
            j_net = j_new;
        }

        // Pin E_actual to its self-consistent value (in-loop damping
        // would otherwise leave a tiny offset).
        E_actual = E_set - i_to_dropV * j_net;

        flux[k] = j_net;
        result.E_actual(k)   = E_actual;
        result.i_faradaic(k) = p.n_electrons * FARADAY * A_eff * j_net;

        // Capacitive current driven by the electrode potential we
        // actually see.
        const double dE_actual_dt = (k > 0)
            ? (result.E_actual(k) - result.E_actual(k - 1)) / dt
            : p.scan_rate_V_s;
        result.i_capacitive(k) = p.Cdl_F_cm2 * A_eff * dE_actual_dt;
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
