"""
Standalone STEP Generator Script
===================================
Generate example STEP and STL files without the GUI.
Works with both CadQuery (if available) and native mesh kernel.

Usage:
    python generate_example.py
"""

import os
import sys

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    print("=" * 60)
    print("  AnalyteX MicroWell Designer - STEP Generator")
    print("=" * 60)

    # Check core dependency
    try:
        import numpy as np
        print(f"  [OK] NumPy {np.__version__} loaded")
    except ImportError:
        print("  [FAIL] NumPy not installed!")
        sys.exit(1)

    # Check CadQuery (optional)
    try:
        import cadquery as cq
        print(f"  [OK] CadQuery loaded (OpenCascade kernel)")
        engine_mode = "CadQuery/OpenCascade"
    except ImportError:
        print("  [INFO] CadQuery not available - using native mesh kernel")
        engine_mode = "Native Mesh Kernel"

    from analytex.core.geometry_engine import (
        GeometryEngine, DesignProfile, WellParameters,
        SubstrateParameters, ArrayParameters, WellArrayType,
        SurfaceConfig, SurfaceType, ChannelParameters
    )
    from analytex.core.exporter import export_step, export_stl
    from analytex.core.constraints import validate_design
    from analytex.core.validation import validate_for_manufacturing, ManufacturingMethod
    from analytex.core.droplet_sim import compute_droplet_profile, estimate_evaporation

    print(f"  Engine: {engine_mode}")
    print()

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    # ---------------------------------------------------------------
    # Design 1: Standard Single Well
    # ---------------------------------------------------------------
    print("  [1/3] Generating: Standard Single Well")

    profile_single = DesignProfile(
        name="Standard Single Well",
        well=WellParameters(
            diameter=3.0, depth=1.0,
            taper_angle=3.0, fillet_radius=0.1
        ),
        substrate=SubstrateParameters(
            thickness=2.5, margin=4.0, corner_radius=1.5
        ),
        array=ArrayParameters(array_type=WellArrayType.SINGLE),
        channel=ChannelParameters(
            enabled=True,
            groove_width=1.5, groove_depth=0.3,
            pad_width=4.0, pad_length=6.0
        ),
        surface=SurfaceConfig(
            contact_angle_well=30.0,
            contact_angle_outer=110.0
        )
    )

    engine = GeometryEngine()
    model_single = engine.generate(profile_single)

    step_path = os.path.join(output_dir, "standard_single_well.step")
    result = export_step(model_single, step_path, design=profile_single)
    print(f"    -> STEP: {result.message}")

    stl_path = os.path.join(output_dir, "standard_single_well.stl")
    result_stl = export_stl(model_single, stl_path)
    print(f"    -> STL: {result_stl.message}")

    # ---------------------------------------------------------------
    # Design 2: 4x2 Array
    # ---------------------------------------------------------------
    print("  [2/3] Generating: 4x2 Well Array")

    profile_array = DesignProfile(
        name="4x2 Array",
        well=WellParameters(
            diameter=3.0, depth=1.0,
            taper_angle=3.0, fillet_radius=0.1
        ),
        substrate=SubstrateParameters(
            thickness=2.5, margin=5.0, corner_radius=2.0
        ),
        array=ArrayParameters(
            array_type=WellArrayType.RECTANGULAR,
            rows=2, cols=4,
            spacing_x=6.0, spacing_y=6.0
        ),
        surface=SurfaceConfig(
            contact_angle_well=30.0,
            contact_angle_outer=110.0
        )
    )

    engine2 = GeometryEngine()
    model_array = engine2.generate(profile_array)

    result = export_step(model_array, os.path.join(output_dir, "array_4x2_well.step"),
                         design=profile_array)
    print(f"    -> STEP: {result.message}")

    result_stl = export_stl(model_array, os.path.join(output_dir, "array_4x2_well.stl"))
    print(f"    -> STL: {result_stl.message}")

    # ---------------------------------------------------------------
    # Design 3: High-Sensitivity Well
    # ---------------------------------------------------------------
    print("  [3/3] Generating: High-Sensitivity Tapered Well")

    profile_hs = DesignProfile(
        name="High-Sensitivity Well",
        well=WellParameters(
            diameter=2.0, depth=1.5,
            taper_angle=5.0, fillet_radius=0.05
        ),
        substrate=SubstrateParameters(
            thickness=3.0, margin=3.5, corner_radius=1.0
        ),
        array=ArrayParameters(array_type=WellArrayType.SINGLE),
        surface=SurfaceConfig(
            contact_angle_well=20.0,
            contact_angle_outer=120.0
        )
    )

    engine3 = GeometryEngine()
    model_hs = engine3.generate(profile_hs)

    result = export_step(model_hs, os.path.join(output_dir, "high_sensitivity_well.step"),
                         design=profile_hs)
    print(f"    -> STEP: {result.message}")

    # ---------------------------------------------------------------
    # Validation Report
    # ---------------------------------------------------------------
    print()
    print("  --- Validation Report (Standard Well) ---")

    constraint_report = validate_design(profile_single)
    for r in constraint_report.results:
        icon = "[OK]" if r.passed else ("[WARN]" if r.severity == "warning" else "[FAIL]")
        print(f"    {icon} {r.name}")
        print(f"          {r.message}")

    mfg_report = validate_for_manufacturing(profile_single, ManufacturingMethod.FDM)
    status = "PASS" if mfg_report.is_valid else "FAIL"
    print(f"\n  Manufacturing (FDM): {status}")
    for issue in mfg_report.issues:
        icon = "[OK]" if issue.severity == "info" else ("[WARN]" if issue.severity == "warning" else "[FAIL]")
        print(f"    {icon} {issue.parameter}: {issue.message}")

    # ---------------------------------------------------------------
    # Droplet Simulation
    # ---------------------------------------------------------------
    print()
    print("  --- Droplet Simulation ---")
    well = profile_single.well
    dp = compute_droplet_profile(
        well.radius_top, well.depth, well.taper_angle,
        profile_single.surface.contact_angle_well, well.volume_uL
    )
    evap = estimate_evaporation(dp)

    print(f"    Droplet volume:    {dp.droplet_volume_uL:.3f} uL")
    print(f"    Well volume:       {dp.well_volume_uL:.3f} uL")
    print(f"    Fill ratio:        {dp.fill_ratio:.1%}")
    print(f"    Cap height:        {dp.cap_height:.3f} mm")
    print(f"    Laplace pressure:  {dp.laplace_pressure_Pa:.1f} Pa")
    print(f"    Confined:          {'Yes' if dp.is_confined else 'No'}")
    print(f"    Evaporation rate:  {evap.evaporation_rate_uL_per_min:.4f} uL/min")
    print(f"    Time to dry:       {evap.time_to_dry:.1f} min")

    print()
    print("=" * 60)
    print(f"  Output files saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
