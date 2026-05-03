/**
 * RĀMAN Studio — KK Solver Tests (C++ standalone)
 *
 * Pure-C++ test of kramers_kronig_test (Lin-KK / Schönleber μ).
 * Pybind11 dispatch of Eigen-typed functions currently segfaults on
 * this host (separate issue), so we verify the algorithm directly
 * here. The C++ tests are the source of truth for KK correctness.
 */
#include "raman/drt_solver.hpp"
#include <cassert>
#include <cmath>
#include <complex>
#include <iostream>
#include <Eigen/Dense>

using namespace raman;
using std::complex;

static int passed = 0, failed = 0;
#define CHECK(cond, msg) do { if (cond) ++passed; else { std::cerr << "FAIL: " << msg << std::endl; ++failed; } } while(0)


// Synthesize a clean Randles spectrum (Rs + (Cdl ∥ (Rct + Wsemi))).
static void make_randles(const Eigen::VectorXd& freqs,
                         double Rs, double Rct, double Cdl, double sigma,
                         Eigen::VectorXd& Zr, Eigen::VectorXd& Zi) {
    int M = freqs.size();
    Zr.resize(M); Zi.resize(M);
    for (int i = 0; i < M; ++i) {
        double w = 2.0 * M_PI * freqs(i);
        complex<double> Zw(sigma / std::sqrt(w), -sigma / std::sqrt(w));
        complex<double> Zc(0.0, -1.0 / (w * Cdl));
        complex<double> Zfar = Rct + Zw;
        complex<double> Zp = (Zc * Zfar) / (Zc + Zfar);
        complex<double> Z = Rs + Zp;
        Zr(i) = Z.real();
        Zi(i) = Z.imag();
    }
}


void test_kk_compliant_fits_well() {
    // A perfect Randles spectrum is K-K compliant by construction. With
    // n_rc = M (the default) the bank is over-parameterised — Lin-KK
    // can fit the data to numerical precision but uses negative R_k to
    // approximate the Warburg's √(jω) branch. So residuals will be
    // tiny but μ may be low. The two metrics carry different
    // information; we test both regimes.
    Eigen::VectorXd freqs(40);
    for (int i = 0; i < 40; ++i) freqs(i) = std::pow(10.0, -2.0 + 7.0 * i / 39.0);
    Eigen::VectorXd Zr, Zi;
    make_randles(freqs, 10.0, 100.0, 1e-5, 50.0, Zr, Zi);

    // Default n_rc = M. Expect tight residuals.
    auto kk = kramers_kronig_test(freqs, Zr, Zi, 0);
    std::cout << "    [n_rc=M=40] mu=" << kk.mu
              << "  max_res_real=" << kk.max_residual_real
              << "  max_res_imag=" << kk.max_residual_imag << "\n";
    CHECK(kk.max_residual_real < 0.01, "n_rc=M: max real residual < 1%");
    CHECK(kk.max_residual_imag < 0.05, "n_rc=M: max imag residual < 5%");
    CHECK(kk.n_rc_used == 40, "n_rc_used defaults to M");
}


void test_kk_compliant_small_bank_high_mu() {
    // Same compliant data, but with a SMALL RC bank. Now the fit cannot
    // overfit and μ should be close to 1 — the Warburg residual goes
    // into the (small but real) imag-part residual instead of into
    // negative R_k pairs.
    Eigen::VectorXd freqs(40);
    for (int i = 0; i < 40; ++i) freqs(i) = std::pow(10.0, -2.0 + 7.0 * i / 39.0);
    Eigen::VectorXd Zr, Zi;
    make_randles(freqs, 10.0, 100.0, 1e-5, 50.0, Zr, Zi);

    auto kk = kramers_kronig_test(freqs, Zr, Zi, 8);   // small bank
    std::cout << "    [n_rc=8] mu=" << kk.mu
              << "  max_res_real=" << kk.max_residual_real
              << "  max_res_imag=" << kk.max_residual_imag
              << "  is_valid=" << (kk.is_valid ? "true" : "false") << "\n";

    // With only 8 RC elements, the Warburg branch can't be fully
    // captured (residuals ~10 %), but the μ verdict — that the data is
    // K-K compliant — should be near 1.
    CHECK(kk.mu > 0.85,
          "K-K-compliant data → μ ≥ 0.85 (regardless of bank size)");
    CHECK(kk.n_rc_used == 8, "n_rc_used reflects the requested bank size");
}


void test_kk_violating_drift() {
    // Add a slow drift to Z' that mimics non-stationarity (a textbook K-K
    // violation: real part deviates from what its own imaginary part implies).
    Eigen::VectorXd freqs(30);
    for (int i = 0; i < 30; ++i) freqs(i) = std::pow(10.0, -2.0 + 7.0 * i / 29.0);
    Eigen::VectorXd Zr, Zi;
    make_randles(freqs, 10.0, 100.0, 1e-5, 50.0, Zr, Zi);

    // Drift that scales with frequency index — this is K-K-violating.
    for (int i = 0; i < 30; ++i) Zr(i) += i * 1.0;   // up to 29 Ω of drift

    auto kk = kramers_kronig_test(freqs, Zr, Zi, 0);

    // The drift forces the fit to use either negative R_k OR large residuals.
    // Either way, the verdict should not be "valid".
    bool flagged = !kk.is_valid;
    CHECK(flagged, "drifting data should not pass the K-K test");
}


void test_kk_invalid_input() {
    Eigen::VectorXd empty;
    auto kk = kramers_kronig_test(empty, empty, empty, 0);
    CHECK(!kk.is_valid, "empty input → is_valid=false");
    CHECK(kk.mu == 0.0, "empty input → mu=0");
}


int main() {
    std::cout << "╔══════════════════════════════════════════╗\n";
    std::cout << "║  RĀMAN Studio — KK Solver C++ Tests      ║\n";
    std::cout << "╚══════════════════════════════════════════╝\n";

    test_kk_compliant_fits_well();
    test_kk_compliant_small_bank_high_mu();
    test_kk_violating_drift();
    test_kk_invalid_input();

    std::cout << "Results: " << passed << " passed, " << failed << " failed\n";
    return failed > 0 ? 1 : 0;
}
