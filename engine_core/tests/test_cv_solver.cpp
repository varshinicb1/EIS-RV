/**
 * RĀMAN Studio — CV Solver Tests
 * ================================
 * Validates cyclic voltammetry solver physics.
 */

#include "raman/cv_solver.hpp"
#include <cassert>
#include <cmath>
#include <iostream>

using namespace raman;

static int tests_passed = 0;
static int tests_failed = 0;

#define ASSERT_NEAR(val, expected, tol, msg) do { \
    double _v = (val), _e = (expected), _t = (tol); \
    if (std::abs(_v - _e) > _t) { \
        std::cerr << "FAIL: " << msg << " — got " << _v \
                  << ", expected " << _e << " ±" << _t << std::endl; \
        tests_failed++; \
    } else { \
        tests_passed++; \
    } \
} while(0)

#define ASSERT_TRUE(cond, msg) do { \
    if (!(cond)) { \
        std::cerr << "FAIL: " << msg << std::endl; \
        tests_failed++; \
    } else { \
        tests_passed++; \
    } \
} while(0)


void test_cv_peak_separation() {
    std::cout << "Test: CV peak separation for reversible system..." << std::endl;
    CVParams p;
    p.k0_cm_s = 10.0;     // Fast kinetics → reversible
    p.scan_rate_V_s = 0.05;
    p.n_electrons = 1;

    auto result = simulate_cv(p, 1000);

    // For a reversible system, ΔEp ≈ 59/n mV at 25°C
    ASSERT_NEAR(result.dEp * 1000, 59.0, 30.0,
                "Reversible CV: ΔEp ≈ 59 mV for n=1");
}


void test_cv_peak_current_ratio() {
    std::cout << "Test: |ipa/ipc| ≈ 1 for reversible system..." << std::endl;
    CVParams p;
    p.k0_cm_s = 10.0;
    p.scan_rate_V_s = 0.05;

    auto result = simulate_cv(p, 1000);

    double ratio = std::abs(result.i_pa / result.i_pc);
    ASSERT_NEAR(ratio, 1.0, 0.3,
                "Reversible CV: |ipa/ipc| ≈ 1");
}


void test_cv_scan_rate_dependence() {
    std::cout << "Test: ip ∝ √v (diffusion-controlled)..." << std::endl;
    CVParams p;
    p.k0_cm_s = 10.0;

    p.scan_rate_V_s = 0.02;
    auto r1 = simulate_cv(p, 500);

    p.scan_rate_V_s = 0.08;
    auto r2 = simulate_cv(p, 500);

    // ip should scale as √v: ip2/ip1 ≈ √(v2/v1) = √4 = 2
    double ratio = std::abs(r2.i_pa / r1.i_pa);
    ASSERT_NEAR(ratio, 2.0, 0.8,
                "ip ∝ √v: 4x scan rate → 2x peak current");
}


void test_cv_irreversible() {
    std::cout << "Test: Irreversible CV has large ΔEp..." << std::endl;
    CVParams p;
    p.k0_cm_s = 1e-5;     // Very slow kinetics
    p.scan_rate_V_s = 0.1;

    auto result = simulate_cv(p, 1000);

    // Irreversible: ΔEp should be > 200 mV
    ASSERT_TRUE(result.dEp > 0.15,
                "Irreversible CV: ΔEp > 150 mV");
}


void test_randles_sevcik_consistency() {
    std::cout << "Test: Simulated ip vs Randles-Sevcik theory..." << std::endl;
    CVParams p;
    p.k0_cm_s = 10.0;  // Reversible
    p.scan_rate_V_s = 0.05;

    auto result = simulate_cv(p, 2000);

    double ip_theory = randles_sevcik_ip(
        p.n_electrons, p.area_cm2 * p.roughness,
        p.C_ox_M, p.D_ox_cm2s, p.scan_rate_V_s, p.temperature_K);

    double ip_sim = std::abs(result.i_pa);

    // Should agree within ~50% (convolution vs analytical)
    double ratio = ip_sim / ip_theory;
    ASSERT_NEAR(ratio, 1.0, 0.5,
                "Simulated ip vs R-S theory within 50%");
}


int main() {
    std::cout << "╔══════════════════════════════════════════╗" << std::endl;
    std::cout << "║  RĀMAN Studio — CV Solver C++ Tests      ║" << std::endl;
    std::cout << "╚══════════════════════════════════════════╝" << std::endl;

    test_cv_peak_separation();
    test_cv_peak_current_ratio();
    test_cv_scan_rate_dependence();
    test_cv_irreversible();
    test_randles_sevcik_consistency();

    std::cout << std::endl;
    std::cout << "Results: " << tests_passed << " passed, "
              << tests_failed << " failed" << std::endl;

    return tests_failed > 0 ? 1 : 0;
}
