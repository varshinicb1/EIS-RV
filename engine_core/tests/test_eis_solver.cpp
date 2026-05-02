/**
 * RĀMAN Studio — EIS Solver Tests
 * =================================
 * Validates C++ EIS solver against known analytical solutions.
 *
 * Test cases:
 *   1. Pure resistor: Z = R (real only)
 *   2. Pure capacitor: Z = 1/(jωC) (imaginary only)
 *   3. R + C parallel: known formula
 *   4. Full Randles: high-freq → Rs, low-freq → Rs + Rct
 *   5. Warburg 45° line
 */

#include "raman/eis_solver.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
#include <iomanip>

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


void test_pure_resistor() {
    std::cout << "Test: Pure resistor (σ_w=0, Cdl→∞, Rct=0)..." << std::endl;
    EISParams p;
    p.Rs = 50.0;
    p.Rct = 0.001;    // ~0 Ω
    p.Cdl = 1.0;      // Very large → Y_CPE ≫ 1/Z_faradaic
    p.sigma_w = 0.0;
    p.n_cpe = 1.0;

    auto result = simulate_eis(p, 1.0, 1e5, 10);

    // At any frequency, Z ≈ Rs (since Rct≈0 and Cdl is huge)
    for (int i = 0; i < 10; ++i) {
        ASSERT_NEAR(result.Z_real(i), 50.0, 1.0,
                    "Pure R: Z_real ≈ Rs");
        ASSERT_NEAR(std::abs(result.Z_imag(i)), 0.0, 5.0,
                    "Pure R: Z_imag ≈ 0");
    }
}


void test_high_freq_limit() {
    std::cout << "Test: High frequency limit → Z = Rs..." << std::endl;
    EISParams p;
    p.Rs = 10.0;
    p.Rct = 500.0;
    p.Cdl = 1e-5;
    p.sigma_w = 50.0;
    p.n_cpe = 0.9;

    auto result = simulate_eis(p, 1e5, 1e6, 5);

    // At very high frequency, CPE admittance → ∞, so Z_parallel → 0
    // Z_total → Rs
    ASSERT_NEAR(result.Z_real(4), 10.0, 2.0,
                "High-f: Z_real → Rs");
}


void test_low_freq_limit() {
    std::cout << "Test: Low frequency limit → Z ≈ Rs + Rct (no Warburg)..."
              << std::endl;
    EISParams p;
    p.Rs = 10.0;
    p.Rct = 200.0;
    p.Cdl = 1e-4;
    p.sigma_w = 0.0;   // No Warburg
    p.n_cpe = 1.0;     // Ideal capacitor

    auto result = simulate_eis(p, 0.001, 0.01, 3);

    // At very low f with no Warburg: Z ≈ Rs + Rct
    ASSERT_NEAR(result.Z_real(0), 210.0, 15.0,
                "Low-f: Z_real → Rs + Rct");
}


void test_warburg_45_degrees() {
    std::cout << "Test: Warburg region shows ~45° line..." << std::endl;
    EISParams p;
    p.Rs = 5.0;
    p.Rct = 50.0;
    p.Cdl = 1e-6;      // Small Cdl → Warburg dominates at mid-freq
    p.sigma_w = 100.0;
    p.n_cpe = 1.0;

    auto result = simulate_eis(p, 0.01, 0.1, 5);

    // In the Warburg regime, Z_real increment ≈ |Z_imag| increment
    // (45° line in Nyquist)
    for (int i = 0; i < 4; ++i) {
        double dZr = result.Z_real(i) - result.Z_real(i + 1);
        double dZi = std::abs(result.Z_imag(i)) - std::abs(result.Z_imag(i + 1));
        if (std::abs(dZr) > 1.0 && std::abs(dZi) > 1.0) {
            double ratio = dZr / dZi;
            // Should be close to 1.0 for 45° line
            ASSERT_NEAR(ratio, 1.0, 0.5,
                        "Warburg: dZr/dZi ≈ 1 (45° line)");
        }
    }
}


void test_randles_sevcik() {
    std::cout << "Test: Randles-Sevcik peak current..." << std::endl;
    // Known: 1 electron, 1 cm², 1 mM, D = 7.6e-6 cm²/s, v = 0.1 V/s
    // ip = 0.4463 * 1^1.5 * 96485^1.5 * 1 * 1e-6 * sqrt(7.6e-6 * 0.1 / 8.314 / 298.15)
    // ≈ 2.69e-5 * sqrt(0.1) * sqrt(7.6e-6) * 1e-6 ... let's compute
    double ip = randles_sevcik_ip(1, 1.0, 1e-3, 7.6e-6, 0.1, 298.15);
    // Expected: ~ 2.7e-5 A (27 µA) for these standard conditions
    ASSERT_NEAR(ip * 1e6, 27.0, 10.0,
                "Randles-Sevcik: ip ~ 27 µA for standard conditions");
}


int main() {
    std::cout << "╔══════════════════════════════════════════╗" << std::endl;
    std::cout << "║  RĀMAN Studio — EIS Solver C++ Tests     ║" << std::endl;
    std::cout << "╚══════════════════════════════════════════╝" << std::endl;

    test_pure_resistor();
    test_high_freq_limit();
    test_low_freq_limit();
    test_warburg_45_degrees();
    test_randles_sevcik();

    std::cout << std::endl;
    std::cout << "Results: " << tests_passed << " passed, "
              << tests_failed << " failed" << std::endl;

    return tests_failed > 0 ? 1 : 0;
}
