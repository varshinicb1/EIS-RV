/**
 * RĀMAN Studio — pybind11 Module
 * ================================
 * Exposes C++ physics engine to Python as `raman_core`.
 *
 * Usage from Python:
 *   import raman_core
 *   result = raman_core.simulate_eis(Rs=10, Rct=100, Cdl=1e-5, sigma_w=50)
 *   print(result.Z_real)  # numpy array
 *
 * All Eigen vectors are automatically converted to numpy arrays.
 */

#include <pybind11/pybind11.h>
#include <pybind11/eigen.h>
#include <pybind11/stl.h>
#include <pybind11/complex.h>

#include "raman/types.hpp"
#include "raman/eis_solver.hpp"
#include "raman/cv_solver.hpp"
#include "raman/diffusion_solver.hpp"

namespace py = pybind11;

PYBIND11_MODULE(raman_core, m) {
    m.doc() = R"doc(
        RĀMAN Studio C++ Physics Engine
        =================================
        High-performance solvers for electrochemical simulation.

        Modules:
          - EIS: Impedance spectroscopy (modified Randles circuit)
          - CV:  Cyclic voltammetry (Butler-Volmer + diffusion)
          - Diffusion: 1D planar and spherical PDE solvers
    )doc";

    m.attr("__version__") = "2.0.0";

    using namespace raman;

    // ── EIS Parameters ────────────────────────────────────
    py::class_<EISParams>(m, "EISParams",
        "Parameters for EIS (modified Randles circuit).")
        .def(py::init<>())
        .def_readwrite("Rs",          &EISParams::Rs,          "Solution resistance (Ω)")
        .def_readwrite("Rct",         &EISParams::Rct,         "Charge transfer resistance (Ω)")
        .def_readwrite("Cdl",         &EISParams::Cdl,         "Double-layer capacitance (F) or CPE Q₀")
        .def_readwrite("sigma_w",     &EISParams::sigma_w,     "Warburg coefficient (Ω·s⁻⁰·⁵)")
        .def_readwrite("n_cpe",       &EISParams::n_cpe,       "CPE exponent (1.0=ideal cap)")
        .def_readwrite("bounded_w",   &EISParams::bounded_w,   "Use bounded Warburg")
        .def_readwrite("diff_len_um", &EISParams::diff_len_um, "Diffusion length (µm)")
        .def_readwrite("diff_coeff",  &EISParams::diff_coeff,  "Diffusion coefficient (cm²/s)")
        .def("__repr__", [](const EISParams& p) {
            return "<EISParams Rs=" + std::to_string(p.Rs) +
                   " Rct=" + std::to_string(p.Rct) +
                   " Cdl=" + std::to_string(p.Cdl) + ">";
        });

    // ── EIS Result ────────────────────────────────────────
    py::class_<EISResult>(m, "EISResult",
        "Complete EIS simulation result with numpy arrays.")
        .def_readonly("frequencies",  &EISResult::frequencies)
        .def_readonly("Z_real",       &EISResult::Z_real)
        .def_readonly("Z_imag",       &EISResult::Z_imag)
        .def_readonly("Z_magnitude",  &EISResult::Z_magnitude)
        .def_readonly("Z_phase",      &EISResult::Z_phase)
        .def_readonly("params",       &EISResult::params);

    // ── EIS Functions ─────────────────────────────────────
    m.def("simulate_eis", &simulate_eis,
        py::arg("params"),
        py::arg("f_min") = 0.01,
        py::arg("f_max") = 1e6,
        py::arg("n_points") = 100,
        R"doc(
            Simulate EIS for a modified Randles circuit.

            Args:
                params: EISParams object
                f_min: Minimum frequency (Hz)
                f_max: Maximum frequency (Hz)
                n_points: Number of log-spaced frequency points

            Returns:
                EISResult with frequencies, Z_real, Z_imag, etc.
        )doc");

    m.def("randles_impedance", &randles_impedance,
        py::arg("frequencies"),
        py::arg("params"),
        "Compute complex impedance at given frequencies.");

    // ── Quick EIS helper ──────────────────────────────────
    m.def("quick_eis", [](double Rs, double Rct, double Cdl,
                          double sigma_w, double n_cpe,
                          int n_points) {
        EISParams p;
        p.Rs = Rs; p.Rct = Rct; p.Cdl = Cdl;
        p.sigma_w = sigma_w; p.n_cpe = n_cpe;
        return simulate_eis(p, 0.01, 1e6, n_points);
    },
    py::arg("Rs") = 10.0,
    py::arg("Rct") = 100.0,
    py::arg("Cdl") = 1e-5,
    py::arg("sigma_w") = 50.0,
    py::arg("n_cpe") = 0.9,
    py::arg("n_points") = 100,
    "Quick EIS simulation with scalar parameters.");

    // ── CV Parameters ─────────────────────────────────────
    py::class_<CVParams>(m, "CVParams",
        "Parameters for cyclic voltammetry simulation.")
        .def(py::init<>())
        .def_readwrite("area_cm2",      &CVParams::area_cm2)
        .def_readwrite("roughness",     &CVParams::roughness)
        .def_readwrite("E_formal_V",    &CVParams::E_formal_V)
        .def_readwrite("n_electrons",   &CVParams::n_electrons)
        .def_readwrite("C_ox_M",        &CVParams::C_ox_M)
        .def_readwrite("C_red_M",       &CVParams::C_red_M)
        .def_readwrite("D_ox_cm2s",     &CVParams::D_ox_cm2s)
        .def_readwrite("D_red_cm2s",    &CVParams::D_red_cm2s)
        .def_readwrite("k0_cm_s",       &CVParams::k0_cm_s)
        .def_readwrite("alpha",         &CVParams::alpha)
        .def_readwrite("Cdl_F_cm2",     &CVParams::Cdl_F_cm2)
        .def_readwrite("Rs_ohm",        &CVParams::Rs_ohm)
        .def_readwrite("E_start_V",     &CVParams::E_start_V)
        .def_readwrite("E_vertex_V",    &CVParams::E_vertex_V)
        .def_readwrite("E_end_V",       &CVParams::E_end_V)
        .def_readwrite("scan_rate_V_s", &CVParams::scan_rate_V_s)
        .def_readwrite("n_cycles",      &CVParams::n_cycles)
        .def_readwrite("temperature_K", &CVParams::temperature_K);

    // ── CV Result ─────────────────────────────────────────
    py::class_<CVResult>(m, "CVResult",
        "Complete CV simulation result.")
        .def_readonly("E",             &CVResult::E)
        .def_readonly("i_total",       &CVResult::i_total)
        .def_readonly("i_faradaic",    &CVResult::i_faradaic)
        .def_readonly("i_capacitive",  &CVResult::i_capacitive)
        .def_readonly("time",          &CVResult::time)
        .def_readonly("i_pa",          &CVResult::i_pa)
        .def_readonly("i_pc",          &CVResult::i_pc)
        .def_readonly("E_pa",          &CVResult::E_pa)
        .def_readonly("E_pc",          &CVResult::E_pc)
        .def_readonly("dEp",           &CVResult::dEp)
        .def_readonly("params",        &CVResult::params);

    // ── CV Functions ──────────────────────────────────────
    m.def("simulate_cv", &simulate_cv,
        py::arg("params"),
        py::arg("n_points") = 2000,
        "Simulate cyclic voltammogram with Butler-Volmer kinetics.");

    m.def("randles_sevcik_ip", &randles_sevcik_ip,
        py::arg("n"), py::arg("A_cm2"), py::arg("C_M"),
        py::arg("D_cm2s"), py::arg("v_Vs"),
        py::arg("T_K") = T_STD,
        "Randles-Sevcik theoretical peak current (A).");

    // ── Diffusion Solvers ─────────────────────────────────
    m.def("solve_diffusion_1d", &solve_diffusion_1d,
        py::arg("D_cm2s"), py::arg("C_bulk_M"),
        py::arg("L_cm"), py::arg("n_spatial"),
        py::arg("n_time"), py::arg("dt_s"),
        py::arg("surface_flux"),
        "1D planar diffusion solver (Crank-Nicolson).");

    m.def("solve_spherical_diffusion", &solve_spherical_diffusion,
        py::arg("D_cm2s"), py::arg("C_max_M"),
        py::arg("C_init_frac"), py::arg("radius_um"),
        py::arg("n_radial"), py::arg("n_time"),
        py::arg("dt_s"), py::arg("surface_flux"),
        "Spherical diffusion solver (battery SPM).");
}
