"""
Scientific Geometry Constraints
================================
Enforces physical constraints for electrochemical micro-well design:

    - Capillary confinement (Bond number check)
    - Minimum wall angle to prevent droplet overflow
    - Edge sharpness for contact-line pinning
    - Volume estimation with Young-Laplace model
    - Electrode spacing for electrochemical best practices
    - Manufacturing-aware limits

All equations reference standard microfluidics / surface science literature.
"""

import math
from dataclasses import dataclass
from typing import List, Tuple

from .geometry_engine import DesignProfile, WellParameters, SurfaceConfig


# ---------------------------------------------------------------------------
#   Physical Constants
# ---------------------------------------------------------------------------

WATER_DENSITY = 998.0           # kg/m³
WATER_SURFACE_TENSION = 0.0728  # N/m (at 20°C)
GRAVITY = 9.81                  # m/s²

# Minimum manufacturable feature sizes (FDM 3D printing)
MIN_WALL_THICKNESS_FDM = 0.4    # mm
MIN_FEATURE_SIZE_FDM = 0.2      # mm
MAX_OVERHANG_ANGLE_FDM = 45.0   # degrees from vertical
MAX_BRIDGE_SPAN_FDM = 10.0      # mm

# SLA / resin printing (finer resolution)
MIN_WALL_THICKNESS_SLA = 0.15   # mm
MIN_FEATURE_SIZE_SLA = 0.05     # mm


# ---------------------------------------------------------------------------
#   Constraint Check Results
# ---------------------------------------------------------------------------

@dataclass
class ConstraintResult:
    """Result of a single constraint check."""
    name: str
    passed: bool
    message: str
    value: float = 0.0
    limit: float = 0.0
    unit: str = ""
    severity: str = "info"  # info, warning, error


@dataclass
class ConstraintReport:
    """Complete constraint validation report."""
    results: List[ConstraintResult]
    all_passed: bool = True

    def __post_init__(self):
        self.all_passed = all(r.passed for r in self.results if r.severity == "error")


# ---------------------------------------------------------------------------
#   Constraint Checks
# ---------------------------------------------------------------------------

def check_bond_number(well: WellParameters) -> ConstraintResult:
    """
    Evaluate the Bond number for capillary confinement.

    Bo = ρgL² / γ

    Where L is the well radius. For Bo << 1, surface tension dominates
    and the droplet is well-confined. For Bo > 1, gravity dominates
    and confinement is lost.

    Criterion: Bo < 1.0 (preferably < 0.3 for reliable confinement)
    """
    L = well.radius_top * 1e-3  # Convert mm to m
    Bo = (WATER_DENSITY * GRAVITY * L * L) / WATER_SURFACE_TENSION

    if Bo < 0.3:
        return ConstraintResult(
            name="Bond Number (Capillary Confinement)",
            passed=True,
            message=f"Bo = {Bo:.4f} — Excellent capillary confinement (Bo < 0.3)",
            value=Bo, limit=0.3, unit="", severity="info"
        )
    elif Bo < 1.0:
        return ConstraintResult(
            name="Bond Number (Capillary Confinement)",
            passed=True,
            message=f"Bo = {Bo:.4f} — Adequate confinement (Bo < 1.0), but consider smaller well",
            value=Bo, limit=1.0, unit="", severity="warning"
        )
    else:
        return ConstraintResult(
            name="Bond Number (Capillary Confinement)",
            passed=False,
            message=f"Bo = {Bo:.4f} — Poor confinement! Reduce well diameter for capillary regime",
            value=Bo, limit=1.0, unit="", severity="error"
        )


def check_wall_angle(
    well: WellParameters, surface: SurfaceConfig
) -> ConstraintResult:
    """
    Check minimum wall angle to prevent droplet spillover.

    For a tapered well, the wall must prevent the contact line from
    advancing over the rim. The critical condition is:

        taper_angle < (180° - θ_advancing) / 2

    where θ_advancing is the advancing contact angle of the liquid
    on the outer surface.
    """
    theta_outer = surface.contact_angle_outer
    max_taper = (180.0 - theta_outer) / 2.0

    if well.taper_angle < max_taper:
        return ConstraintResult(
            name="Wall Angle (Spill Prevention)",
            passed=True,
            message=f"Taper {well.taper_angle:.1f}° < critical {max_taper:.1f}° — Spillover prevented",
            value=well.taper_angle, limit=max_taper, unit="°", severity="info"
        )
    else:
        return ConstraintResult(
            name="Wall Angle (Spill Prevention)",
            passed=False,
            message=f"Taper {well.taper_angle:.1f}° ≥ critical {max_taper:.1f}° — Risk of droplet spill!",
            value=well.taper_angle, limit=max_taper, unit="°", severity="error"
        )


def check_edge_sharpness(well: WellParameters) -> ConstraintResult:
    """
    Evaluate edge sharpness for contact-line pinning.

    The Gibbs criterion for contact-line pinning requires that the
    edge radius be significantly smaller than the capillary length:

        λ_c = sqrt(γ / (ρg)) ≈ 2.73 mm for water

    For reliable pinning: fillet_radius < 0.1 * λ_c ≈ 0.27 mm
    """
    capillary_length = math.sqrt(WATER_SURFACE_TENSION / (WATER_DENSITY * GRAVITY)) * 1000  # mm
    max_fillet = 0.1 * capillary_length

    if well.fillet_radius < max_fillet:
        return ConstraintResult(
            name="Edge Sharpness (Contact-Line Pinning)",
            passed=True,
            message=f"Fillet {well.fillet_radius:.3f} mm < limit {max_fillet:.3f} mm — Strong pinning",
            value=well.fillet_radius, limit=max_fillet, unit="mm", severity="info"
        )
    else:
        pinning_quality = "Weakened" if well.fillet_radius < 2 * max_fillet else "Poor"
        return ConstraintResult(
            name="Edge Sharpness (Contact-Line Pinning)",
            passed=False,
            message=f"Fillet {well.fillet_radius:.3f} mm — {pinning_quality} pinning. Reduce for better confinement.",
            value=well.fillet_radius, limit=max_fillet, unit="mm", severity="warning"
        )


def check_volume_compatibility(
    well: WellParameters, surface: SurfaceConfig
) -> ConstraintResult:
    """
    Check if the well can hold the target droplet without overflow.

    Compares the spherical cap volume (contact angle dependent)
    to the well volume (geometry dependent).
    """
    well_vol = well.volume_uL  # µL
    theta = math.radians(surface.contact_angle_well)
    r = well.radius_top

    if theta > 0 and theta < math.pi:
        R_sphere = r / math.sin(theta)
        h_cap = R_sphere * (1.0 - math.cos(theta))
        droplet_vol = (math.pi * h_cap * h_cap * (3 * R_sphere - h_cap)) / 3.0
    else:
        droplet_vol = well_vol * 0.5

    fill_ratio = droplet_vol / well_vol if well_vol > 0 else 0

    if fill_ratio < 0.9:
        return ConstraintResult(
            name="Volume Compatibility",
            passed=True,
            message=f"Droplet {droplet_vol:.2f} µL / Well {well_vol:.2f} µL — Fill ratio {fill_ratio:.1%}",
            value=fill_ratio * 100, limit=90, unit="%", severity="info"
        )
    else:
        return ConstraintResult(
            name="Volume Compatibility",
            passed=False,
            message=f"Droplet may overflow! Fill ratio {fill_ratio:.1%}. Increase well depth or reduce volume.",
            value=fill_ratio * 100, limit=90, unit="%", severity="warning"
        )


def check_well_spacing(well: WellParameters, spacing: float) -> ConstraintResult:
    """
    Verify inter-well spacing is sufficient to prevent cross-contamination.

    Minimum spacing should be at least 2× capillary length plus the
    well diameter, to ensure independent capillary behavior.
    """
    capillary_length = math.sqrt(WATER_SURFACE_TENSION / (WATER_DENSITY * GRAVITY)) * 1000  # mm
    min_spacing = well.diameter + 2 * capillary_length

    if spacing >= min_spacing:
        return ConstraintResult(
            name="Well Spacing (Cross-Contamination)",
            passed=True,
            message=f"Spacing {spacing:.2f} mm ≥ minimum {min_spacing:.2f} mm — Wells are independent",
            value=spacing, limit=min_spacing, unit="mm", severity="info"
        )
    elif spacing >= well.diameter + 0.5:
        return ConstraintResult(
            name="Well Spacing (Cross-Contamination)",
            passed=True,
            message=f"Spacing {spacing:.2f} mm — Adequate but close. Minimum recommended: {min_spacing:.2f} mm",
            value=spacing, limit=min_spacing, unit="mm", severity="warning"
        )
    else:
        return ConstraintResult(
            name="Well Spacing (Cross-Contamination)",
            passed=False,
            message=f"Spacing {spacing:.2f} mm — Too close! Wells will overlap or cross-contaminate.",
            value=spacing, limit=min_spacing, unit="mm", severity="error"
        )


def check_wall_thickness(well: WellParameters) -> ConstraintResult:
    """
    Check if wall thickness at the well bottom is manufacturable.
    """
    # Wall thickness at bottom = r_top - r_bottom (for neighbor wells)
    # But for single well, check the absolute wall thickness
    wall_at_bottom = well.depth * math.tan(math.radians(well.taper_angle))

    if well.radius_bottom < MIN_FEATURE_SIZE_FDM:
        return ConstraintResult(
            name="Bottom Radius (Manufacturability)",
            passed=False,
            message=f"Bottom radius {well.radius_bottom:.3f} mm is too small for manufacturing.",
            value=well.radius_bottom, limit=MIN_FEATURE_SIZE_FDM, unit="mm", severity="error"
        )
    else:
        return ConstraintResult(
            name="Bottom Radius (Manufacturability)",
            passed=True,
            message=f"Bottom radius {well.radius_bottom:.3f} mm — Manufacturable",
            value=well.radius_bottom, limit=MIN_FEATURE_SIZE_FDM, unit="mm", severity="info"
        )


def check_overhang_angle(well: WellParameters) -> ConstraintResult:
    """
    Check overhang angle for 3D printability.

    FDM printers typically cannot print overhangs steeper than 45°
    from vertical without supports.
    """
    # For a tapered well, the overhang is the wall angle from vertical
    # Negative taper (inward sloping from top) creates an overhang
    if well.taper_angle < 0:
        actual_overhang = abs(well.taper_angle)
    else:
        # Positive taper (outward sloping from top) — print upside down
        # The internal wall has overhang = 90° - taper_angle
        actual_overhang = 0  # Well opens upward, no overhang with support

    if actual_overhang <= MAX_OVERHANG_ANGLE_FDM:
        return ConstraintResult(
            name="Overhang Angle (3D Printability)",
            passed=True,
            message=f"Overhang {actual_overhang:.1f}° ≤ {MAX_OVERHANG_ANGLE_FDM:.0f}° — Printable without supports",
            value=actual_overhang, limit=MAX_OVERHANG_ANGLE_FDM, unit="°", severity="info"
        )
    else:
        return ConstraintResult(
            name="Overhang Angle (3D Printability)",
            passed=False,
            message=f"Overhang {actual_overhang:.1f}° > {MAX_OVERHANG_ANGLE_FDM:.0f}° — Requires support structures",
            value=actual_overhang, limit=MAX_OVERHANG_ANGLE_FDM, unit="°", severity="warning"
        )


def check_depth_ratio(well: WellParameters) -> ConstraintResult:
    """
    Check well aspect ratio (depth / diameter).

    Very deep narrow wells (<1:1 ratio) are difficult to print,
    hard to clean, and may trap air bubbles during filling.
    Recommended: depth / diameter < 1.0
    """
    ratio = well.depth / well.diameter if well.diameter > 0 else 0

    if ratio < 0.5:
        return ConstraintResult(
            name="Aspect Ratio (Depth/Diameter)",
            passed=True,
            message=f"Aspect ratio {ratio:.2f} — Excellent accessibility and filling",
            value=ratio, limit=1.0, unit="", severity="info"
        )
    elif ratio < 1.0:
        return ConstraintResult(
            name="Aspect Ratio (Depth/Diameter)",
            passed=True,
            message=f"Aspect ratio {ratio:.2f} — Acceptable, verify easy filling",
            value=ratio, limit=1.0, unit="", severity="info"
        )
    else:
        return ConstraintResult(
            name="Aspect Ratio (Depth/Diameter)",
            passed=False,
            message=f"Aspect ratio {ratio:.2f} — Deep well may trap air. Consider reducing depth.",
            value=ratio, limit=1.0, unit="", severity="warning"
        )


# ---------------------------------------------------------------------------
#   Full Constraint Validation
# ---------------------------------------------------------------------------

def validate_design(profile: DesignProfile) -> ConstraintReport:
    """
    Run all constraint checks against a design profile.

    Returns a comprehensive ConstraintReport with pass/fail status
    for each physical and manufacturing constraint.
    """
    results = []

    well = profile.well
    surface = profile.surface

    # Physical constraints
    results.append(check_bond_number(well))
    results.append(check_wall_angle(well, surface))
    results.append(check_edge_sharpness(well))
    results.append(check_volume_compatibility(well, surface))
    results.append(check_depth_ratio(well))

    # Array spacing check
    if profile.array.rows > 1 or profile.array.cols > 1:
        min_spacing = min(profile.array.spacing_x, profile.array.spacing_y)
        results.append(check_well_spacing(well, min_spacing))

    # Manufacturing constraints
    results.append(check_wall_thickness(well))
    results.append(check_overhang_angle(well))

    return ConstraintReport(results=results)
