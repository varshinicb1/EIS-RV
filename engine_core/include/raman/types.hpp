/**
 * RĀMAN Studio — Core Types
 * ==========================
 * Shared data structures for the C++ physics engine.
 *
 * All impedance computations use std::complex<double>.
 * Eigen is used for vectorized operations on frequency arrays.
 */

#pragma once

#include <Eigen/Dense>
#include <complex>
#include <vector>
#include <string>
#include <cmath>

namespace raman {

// ── Constants ─────────────────────────────────────────────
constexpr double PI       = 3.14159265358979323846;
constexpr double FARADAY  = 96485.33212;    // C/mol
constexpr double R_GAS    = 8.314462618;    // J/(mol·K)
constexpr double T_STD    = 298.15;         // K (25°C)
constexpr double RT_F     = R_GAS * T_STD / FARADAY;  // ~0.02569 V

// ── Type aliases ──────────────────────────────────────────
using Complex  = std::complex<double>;
using VecD     = Eigen::VectorXd;
using VecC     = Eigen::VectorXcd;   // Vector of complex doubles
using MatD     = Eigen::MatrixXd;

// ── EIS Parameters ────────────────────────────────────────
struct EISParams {
    double Rs          = 10.0;    // Solution resistance (Ω)
    double Rct         = 100.0;   // Charge transfer resistance (Ω)
    double Cdl         = 1.5e-05;    // Double-layer capacitance (F) or CPE Q₀
    double sigma_w     = 50.0;    // Warburg coefficient (Ω·s^(-1/2))
    double n_cpe       = 0.9;     // CPE exponent (1.0 = ideal capacitor)
    bool   bounded_w   = false;   // Use finite-length Warburg
    double diff_len_um = 100.0;   // Diffusion layer thickness (µm)
    double diff_coeff  = 1e-6;    // Diffusion coefficient (cm²/s)
};

// ── EIS Result ────────────────────────────────────────────
struct EISResult {
    VecD frequencies;   // Hz
    VecD Z_real;        // Ω
    VecD Z_imag;        // Ω
    VecD Z_magnitude;   // |Z| Ω
    VecD Z_phase;       // degrees
    EISParams params;
};

// ── CV Parameters ─────────────────────────────────────────
struct CVParams {
    // Electrode
    double area_cm2        = 0.0707;  // Electrode area
    double roughness       = 1.0;     // Roughness factor

    // Redox couple
    double E_formal_V      = 0.23;    // Formal potential vs ref (V)
    int    n_electrons     = 1;
    double C_ox_M          = 5e-3;    // Bulk oxidant conc (mol/L)
    double C_red_M         = 5e-3;    // Bulk reductant conc
    double D_ox_cm2s       = 7.6e-6;  // Diff coeff oxidant
    double D_red_cm2s      = 7.6e-6;  // Diff coeff reductant

    // Kinetics (Butler-Volmer)
    double k0_cm_s         = 0.01;    // Standard rate constant
    double alpha           = 0.5;     // Transfer coefficient

    // Double layer
    double Cdl_F_cm2       = 20e-6;   // F/cm²
    double Rs_ohm          = 10.0;    // Uncompensated resistance

    // Scan
    double E_start_V       = -0.3;
    double E_vertex_V      = 0.8;
    double E_end_V         = -0.3;
    double scan_rate_V_s   = 0.05;
    int    n_cycles        = 1;
    double temperature_K   = 298.15;
};

// ── CV Result ─────────────────────────────────────────────
struct CVResult {
    VecD E;              // Set potential (V) — the waveform the user requested
    VecD E_actual;       // Electrode potential (V) — equals E when Rs_ohm == 0;
                         // otherwise E_set − i·Rs after iR-drop correction
    VecD i_total;        // Total current (A)
    VecD i_faradaic;     // Faradaic current (A)
    VecD i_capacitive;   // Capacitive current (A)
    VecD time;           // Time (s)

    // Peak analysis (computed from i_total vs E_actual when Rs > 0)
    double i_pa   = 0;   // Anodic peak current (A)
    double i_pc   = 0;   // Cathodic peak current (A)
    double E_pa   = 0;   // Anodic peak potential (V)
    double E_pc   = 0;   // Cathodic peak potential (V)
    double dEp    = 0;   // Peak separation (V)

    CVParams params;
};

}  // namespace raman
