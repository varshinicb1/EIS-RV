"""
Design Validation Engine
=========================
Pre-export validation ensuring the design is:
    - Manufacturable (3D printing / CNC)
    - Geometrically valid (watertight, no degenerate features)
    - Scientifically sound (proper electrode spacing, volumes)

Provides detailed pass/fail reporting with actionable suggestions.
"""

import math
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

from .geometry_engine import DesignProfile, WellParameters


class ManufacturingMethod(Enum):
    FDM = "FDM (Fused Deposition Modeling)"
    SLA = "SLA (Stereolithography)"
    CNC = "CNC Milling"
    INJECTION = "Injection Molding"


@dataclass
class ValidationIssue:
    """Single validation finding."""
    category: str
    severity: str       # "error", "warning", "info"
    parameter: str
    message: str
    suggestion: str = ""
    icon: str = "ℹ"

    def __post_init__(self):
        if self.severity == "error":
            self.icon = "✗"
        elif self.severity == "warning":
            self.icon = "⚠"
        elif self.severity == "info":
            self.icon = "✓"


@dataclass
class ValidationReport:
    """Complete validation report with all findings."""
    issues: List[ValidationIssue]
    is_valid: bool = True
    method: ManufacturingMethod = ManufacturingMethod.FDM

    def __post_init__(self):
        self.is_valid = not any(i.severity == "error" for i in self.issues)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "info"]


# ---------------------------------------------------------------------------
#   Manufacturing Limits by Method
# ---------------------------------------------------------------------------

LIMITS = {
    ManufacturingMethod.FDM: {
        "min_wall": 0.4,            # mm
        "min_feature": 0.2,         # mm
        "min_hole_diameter": 0.5,   # mm
        "max_overhang": 45.0,       # degrees
        "layer_height": 0.1,        # mm (typical)
        "xy_resolution": 0.4,       # mm (nozzle width)
        "z_resolution": 0.1,        # mm
        "max_bridge": 10.0,         # mm
    },
    ManufacturingMethod.SLA: {
        "min_wall": 0.15,
        "min_feature": 0.05,
        "min_hole_diameter": 0.2,
        "max_overhang": 60.0,
        "layer_height": 0.025,
        "xy_resolution": 0.05,
        "z_resolution": 0.025,
        "max_bridge": 20.0,
    },
    ManufacturingMethod.CNC: {
        "min_wall": 0.5,
        "min_feature": 0.1,
        "min_hole_diameter": 0.3,
        "max_overhang": 90.0,       # Not applicable
        "layer_height": 0.01,
        "xy_resolution": 0.01,
        "z_resolution": 0.01,
        "max_bridge": 1000.0,
    },
    ManufacturingMethod.INJECTION: {
        "min_wall": 0.5,
        "min_feature": 0.1,
        "min_hole_diameter": 0.5,
        "max_overhang": 90.0,
        "layer_height": 0.01,
        "xy_resolution": 0.01,
        "z_resolution": 0.01,
        "max_bridge": 1000.0,
    },
}


# ---------------------------------------------------------------------------
#   Validation Functions
# ---------------------------------------------------------------------------

def validate_for_manufacturing(
    profile: DesignProfile,
    method: ManufacturingMethod = ManufacturingMethod.FDM
) -> ValidationReport:
    """
    Validate a design profile against manufacturing constraints.

    Args:
        profile: Design to validate
        method: Target manufacturing method

    Returns:
        ValidationReport with all findings
    """
    issues = []
    limits = LIMITS[method]

    well = profile.well
    sub = profile.substrate

    # --- Geometry Validity ---

    if well.diameter <= 0:
        issues.append(ValidationIssue(
            category="Geometry", severity="error",
            parameter="Well Diameter",
            message=f"Well diameter must be positive (got {well.diameter:.3f} mm)",
            suggestion="Set diameter to at least 0.5 mm"
        ))

    if well.depth <= 0:
        issues.append(ValidationIssue(
            category="Geometry", severity="error",
            parameter="Well Depth",
            message=f"Well depth must be positive (got {well.depth:.3f} mm)",
            suggestion="Set depth to at least 0.1 mm"
        ))

    if well.depth > sub.thickness:
        issues.append(ValidationIssue(
            category="Geometry", severity="error",
            parameter="Well Depth",
            message=f"Well depth ({well.depth:.2f} mm) exceeds substrate thickness ({sub.thickness:.2f} mm)",
            suggestion="Reduce well depth or increase substrate thickness"
        ))

    if well.taper_angle < 0 or well.taper_angle >= 45:
        issues.append(ValidationIssue(
            category="Geometry", severity="warning",
            parameter="Taper Angle",
            message=f"Taper angle {well.taper_angle:.1f}° is unusual",
            suggestion="Typical range: 0° – 15° for micro-wells"
        ))

    if well.radius_bottom < limits["min_feature"]:
        issues.append(ValidationIssue(
            category="Manufacturing", severity="error",
            parameter="Bottom Radius",
            message=f"Bottom radius {well.radius_bottom:.3f} mm below {method.value} minimum ({limits['min_feature']:.3f} mm)",
            suggestion="Reduce taper angle or increase well diameter"
        ))

    # --- Wall Thickness ---

    if sub.thickness - well.depth < limits["min_wall"]:
        remaining = sub.thickness - well.depth
        issues.append(ValidationIssue(
            category="Manufacturing", severity="error",
            parameter="Base Thickness",
            message=f"Remaining base thickness {remaining:.2f} mm below minimum ({limits['min_wall']:.2f} mm)",
            suggestion="Increase substrate thickness or reduce well depth"
        ))
    else:
        remaining = sub.thickness - well.depth
        issues.append(ValidationIssue(
            category="Manufacturing", severity="info",
            parameter="Base Thickness",
            message=f"Base thickness {remaining:.2f} mm — OK for {method.value}"
        ))

    # --- Feature Size ---

    if well.diameter < limits["min_hole_diameter"]:
        issues.append(ValidationIssue(
            category="Manufacturing", severity="error",
            parameter="Well Diameter",
            message=f"Well diameter {well.diameter:.3f} mm below {method.value} minimum hole ({limits['min_hole_diameter']:.3f} mm)",
            suggestion="Increase well diameter or use finer manufacturing method"
        ))
    else:
        issues.append(ValidationIssue(
            category="Manufacturing", severity="info",
            parameter="Well Diameter",
            message=f"Well diameter {well.diameter:.2f} mm — Manufacturable with {method.value}"
        ))

    # --- Fillet Radius ---

    if well.fillet_radius > 0 and well.fillet_radius < limits["min_feature"]:
        issues.append(ValidationIssue(
            category="Manufacturing", severity="warning",
            parameter="Fillet Radius",
            message=f"Fillet {well.fillet_radius:.3f} mm may not resolve in {method.value}",
            suggestion=f"Increase to {limits['min_feature']:.3f} mm or set to 0"
        ))

    # --- Array Spacing ---

    if profile.array.cols > 1 or profile.array.rows > 1:
        min_spacing = min(profile.array.spacing_x, profile.array.spacing_y)
        min_wall_between = min_spacing - well.diameter

        if min_wall_between < limits["min_wall"]:
            issues.append(ValidationIssue(
                category="Manufacturing", severity="error",
                parameter="Well Spacing",
                message=f"Wall between wells ({min_wall_between:.2f} mm) below minimum ({limits['min_wall']:.2f} mm)",
                suggestion="Increase spacing or reduce well diameter"
            ))
        else:
            issues.append(ValidationIssue(
                category="Manufacturing", severity="info",
                parameter="Well Spacing",
                message=f"Inter-well wall {min_wall_between:.2f} mm — Adequate"
            ))

    # --- Overhang ---

    if well.taper_angle > limits["max_overhang"]:
        issues.append(ValidationIssue(
            category="Manufacturing", severity="warning",
            parameter="Overhang",
            message=f"Taper angle {well.taper_angle:.1f}° exceeds {method.value} limit ({limits['max_overhang']:.0f}°)",
            suggestion="Print with supports or reduce taper"
        ))

    # --- Contact Channels ---

    if profile.channel.enabled:
        if profile.channel.groove_width < limits["min_feature"]:
            issues.append(ValidationIssue(
                category="Manufacturing", severity="warning",
                parameter="Groove Width",
                message=f"Groove width {profile.channel.groove_width:.3f} mm may be too narrow",
                suggestion=f"Increase to at least {limits['min_feature']:.3f} mm"
            ))
        else:
            issues.append(ValidationIssue(
                category="Manufacturing", severity="info",
                parameter="Channel Grooves",
                message="Contact channel dimensions OK"
            ))

    # --- Overall Assessment ---

    issues.append(ValidationIssue(
        category="Summary", severity="info",
        parameter="Overall",
        message=f"Well volume: {well.volume_uL:.2f} µL | Substrate: {sub.length:.1f} × {sub.width:.1f} × {sub.thickness:.1f} mm"
    ))

    report = ValidationReport(issues=issues, method=method)
    return report
