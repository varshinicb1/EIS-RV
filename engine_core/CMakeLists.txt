cmake_minimum_required(VERSION 3.18)
project(raman_core VERSION 2.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# ── Options ────────────────────────────────────────────────
option(RAMAN_BUILD_TESTS   "Build C++ unit tests"       ON)
option(RAMAN_USE_OPENMP    "Enable OpenMP parallelism"   ON)
option(RAMAN_CUDA_HOOKS    "Compile CUDA hook stubs"     OFF)

# ── Dependencies ───────────────────────────────────────────
# Eigen (header-only linear algebra)
find_package(Eigen3 3.4 QUIET)
if(NOT Eigen3_FOUND)
    message(STATUS "Eigen3 not found — fetching via FetchContent")
    include(FetchContent)
    FetchContent_Declare(
        eigen
        GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
        GIT_TAG        3.4.0
        GIT_SHALLOW    TRUE
    )
    FetchContent_MakeAvailable(eigen)
endif()

# OpenMP
if(RAMAN_USE_OPENMP)
    find_package(OpenMP)
    if(OpenMP_CXX_FOUND)
        message(STATUS "OpenMP found: ${OpenMP_CXX_VERSION}")
    else()
        message(WARNING "OpenMP not found — parallelism disabled")
        set(RAMAN_USE_OPENMP OFF)
    endif()
endif()

# pybind11
find_package(pybind11 QUIET)
if(NOT pybind11_FOUND)
    message(STATUS "pybind11 not found — fetching via FetchContent")
    include(FetchContent)
    FetchContent_Declare(
        pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11.git
        GIT_TAG        v2.12.0
        GIT_SHALLOW    TRUE
    )
    FetchContent_MakeAvailable(pybind11)
endif()

# ── Core Library (static) ─────────────────────────────────
add_library(raman_core_static STATIC
    src/eis_solver.cpp
    src/cv_solver.cpp
    src/diffusion_solver.cpp
    src/drt_solver.cpp
    src/circuit_fitter.cpp
)

target_include_directories(raman_core_static PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(raman_core_static PUBLIC Eigen3::Eigen)

if(RAMAN_USE_OPENMP AND OpenMP_CXX_FOUND)
    target_link_libraries(raman_core_static PUBLIC OpenMP::OpenMP_CXX)
    target_compile_definitions(raman_core_static PUBLIC RAMAN_HAS_OPENMP)
endif()

# ── Python Bindings (shared .so/.pyd) ─────────────────────
pybind11_add_module(raman_core NO_EXTRAS
    bindings/pybind_module.cpp
)

target_link_libraries(raman_core PRIVATE raman_core_static)

# ── Tests ──────────────────────────────────────────────────
if(RAMAN_BUILD_TESTS)
    enable_testing()
    add_executable(test_eis_solver tests/test_eis_solver.cpp)
    target_link_libraries(test_eis_solver PRIVATE raman_core_static)
    add_test(NAME EISSolverTests COMMAND test_eis_solver)

    add_executable(test_cv_solver tests/test_cv_solver.cpp)
    target_link_libraries(test_cv_solver PRIVATE raman_core_static)
    add_test(NAME CVSolverTests COMMAND test_cv_solver)

    # DRT solver test (if test file exists)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_drt_solver.cpp)
        add_executable(test_drt_solver tests/test_drt_solver.cpp)
        target_link_libraries(test_drt_solver PRIVATE raman_core_static)
        add_test(NAME DRTSolverTests COMMAND test_drt_solver)
    endif()

    # KK solver test
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_kk_solver.cpp)
        add_executable(test_kk_solver tests/test_kk_solver.cpp)
        target_link_libraries(test_kk_solver PRIVATE raman_core_static)
        add_test(NAME KKSolverTests COMMAND test_kk_solver)
    endif()
endif()
