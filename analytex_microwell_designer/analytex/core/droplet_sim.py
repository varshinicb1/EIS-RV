"""
Droplet Simulation Module
===========================
Approximate droplet shape and filling behavior using the
Young-Laplace spherical cap model.

Provides:
    - Droplet profile computation (spherical cap)
    - Volume / fill-ratio estimation
    - Contact angle sensitivity analysis
    - Evaporation time estimation
    - Mesh generation for 3D preview rendering
"""

import math
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional, List


@dataclass
class DropletProfile:
    """Computed droplet shape parameters."""
    contact_angle_deg: float        # Input contact angle (°)
    well_radius: float              # Well radius (mm)
    sphere_radius: float            # Spherical cap radius R (mm)
    cap_height: float               # Cap height h (mm)
    droplet_volume_uL: float        # Droplet volume (µL = mm³)
    well_volume_uL: float           # Well volume (µL)
    fill_ratio: float               # Volume fill ratio (0–1)
    contact_line_length: float      # Perimeter at contact line (mm)
    surface_area: float             # Droplet surface area (mm²)
    laplace_pressure_Pa: float      # ΔP across interface (Pa)
    is_confined: bool               # Whether droplet fits in well
    overflow_volume_uL: float       # Volume above well rim (µL)


@dataclass
class EvaporationEstimate:
    """Approximate evaporation time estimate."""
    initial_volume_uL: float
    evaporation_rate_uL_per_min: float
    time_to_50pct: float            # minutes
    time_to_dry: float              # minutes


# ---------------------------------------------------------------------------
#   Physical Constants
# ---------------------------------------------------------------------------

WATER_SURFACE_TENSION = 72.8e-3     # N/m
WATER_DENSITY = 998.0               # kg/m³
WATER_VISCOSITY = 1.002e-3          # Pa·s
GRAVITY = 9.81                      # m/s²

# Diffusion coefficient of water vapor in air at 25°C
D_WATER_VAPOR = 2.5e-5              # m²/s
# Saturated vapor concentration at 25°C
C_SAT = 0.023                       # kg/m³
RELATIVE_HUMIDITY = 0.5             # 50% RH


def compute_droplet_profile(
    well_radius: float,
    well_depth: float,
    taper_angle_deg: float,
    contact_angle_deg: float,
    well_volume_uL: float
) -> DropletProfile:
    """
    Compute droplet shape parameters using the spherical cap model.

    The Young-Laplace equation for a sessile drop in a cylindrical well
    is approximated by a spherical cap with the contact line pinned at
    the well rim.

    Args:
        well_radius: Radius of the well at the top (mm)
        well_depth: Depth of the well (mm)
        taper_angle_deg: Wall taper angle (degrees)
        contact_angle_deg: Liquid-surface contact angle (degrees)
        well_volume_uL: Total well volume (µL = mm³)

    Returns:
        DropletProfile with all computed parameters
    """
    theta = math.radians(contact_angle_deg)
    r = well_radius

    # Spherical cap geometry
    if math.sin(theta) > 1e-6:
        R = r / math.sin(theta)     # Sphere radius
    else:
        R = 1e6 * r                 # Near-flat droplet

    h = R * (1.0 - math.cos(theta))  # Cap height

    # Droplet volume (spherical cap formula)
    V = (math.pi * h * h * (3.0 * R - h)) / 3.0

    # Contact line length
    contact_line = 2.0 * math.pi * r

    # Surface area of spherical cap
    A_cap = 2.0 * math.pi * R * h

    # Laplace pressure ΔP = 2γ/R
    laplace_pressure = 2.0 * WATER_SURFACE_TENSION / (R * 1e-3)  # Pa

    # Check confinement
    is_confined = h <= well_depth
    overflow_volume = 0.0
    if not is_confined:
        # Estimate overflow volume (cap above well rim)
        h_in_well = well_depth
        V_in_well = (math.pi * h_in_well * h_in_well * (3.0 * R - h_in_well)) / 3.0
        overflow_volume = V - V_in_well

    # Fill ratio
    fill_ratio = min(V / well_volume_uL, 1.0) if well_volume_uL > 0 else 0

    return DropletProfile(
        contact_angle_deg=contact_angle_deg,
        well_radius=r,
        sphere_radius=R,
        cap_height=h,
        droplet_volume_uL=V,
        well_volume_uL=well_volume_uL,
        fill_ratio=fill_ratio,
        contact_line_length=contact_line,
        surface_area=A_cap,
        laplace_pressure_Pa=laplace_pressure,
        is_confined=is_confined,
        overflow_volume_uL=overflow_volume
    )


def estimate_evaporation(profile: DropletProfile) -> EvaporationEstimate:
    """
    Estimate evaporation time using the diffusion-limited model.

    For a sessile droplet on a surface, the evaporation rate is:
        dm/dt ≈ -π * D * R * Δc * f(θ)

    where D is diffusion coefficient, R is contact radius,
    Δc is vapor concentration difference, and f(θ) is a geometric factor.
    """
    r_m = profile.well_radius * 1e-3   # Convert to meters
    theta = math.radians(profile.contact_angle_deg)

    # Geometric factor f(θ) ≈ (0.27θ² + 1.30) (Hu & Larson approximation)
    f_theta = 0.27 * theta * theta + 1.30

    # Concentration difference
    delta_c = C_SAT * (1.0 - RELATIVE_HUMIDITY)

    # Mass evaporation rate (kg/s)
    dm_dt = math.pi * D_WATER_VAPOR * r_m * delta_c * f_theta

    # Convert to volume rate (µL/min = mm³/min)
    dV_dt = (dm_dt / WATER_DENSITY) * 1e9 * 60.0  # µL/min

    if dV_dt > 0:
        time_50 = (profile.droplet_volume_uL * 0.5) / dV_dt
        time_dry = profile.droplet_volume_uL / dV_dt
    else:
        time_50 = float('inf')
        time_dry = float('inf')

    return EvaporationEstimate(
        initial_volume_uL=profile.droplet_volume_uL,
        evaporation_rate_uL_per_min=dV_dt,
        time_to_50pct=time_50,
        time_to_dry=time_dry
    )


def generate_droplet_mesh(
    well_radius: float,
    contact_angle_deg: float,
    center: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    n_radial: int = 32,
    n_angular: int = 48
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate a triangle mesh for the spherical cap droplet.

    Args:
        well_radius: Well radius (mm)
        contact_angle_deg: Contact angle (degrees)
        center: Center position (x, y, z) of the well top
        n_radial: Number of radial divisions
        n_angular: Number of angular divisions

    Returns:
        (vertices, faces) as numpy arrays
        vertices: (N, 3) float32
        faces: (M, 3) int32
    """
    theta = math.radians(contact_angle_deg)
    r = well_radius

    if math.sin(theta) < 1e-6:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.int32)

    R = r / math.sin(theta)
    h = R * (1.0 - math.cos(theta))

    cx, cy, cz = center
    sphere_cz = cz - (R - h)  # Z center of the full sphere

    # Generate vertices on the spherical cap
    # Parametric: phi from 0 to arcsin(r/R), theta from 0 to 2π
    phi_max = math.asin(min(r / R, 1.0))

    vertices = []
    faces = []

    # Top pole (apex of cap)
    vertices.append([cx, cy, sphere_cz + R])

    # Generate rings from top to contact line
    for i in range(1, n_radial + 1):
        phi = phi_max * (i / n_radial)
        ring_r = R * math.sin(phi)
        ring_z = sphere_cz + R * math.cos(phi)

        for j in range(n_angular):
            angle = 2.0 * math.pi * j / n_angular
            x = cx + ring_r * math.cos(angle)
            y = cy + ring_r * math.sin(angle)
            vertices.append([x, y, ring_z])

    vertices = np.array(vertices, dtype=np.float32)

    # Generate faces
    # Top cap (pole to first ring)
    for j in range(n_angular):
        j_next = (j + 1) % n_angular
        faces.append([0, 1 + j, 1 + j_next])

    # Middle rings
    for i in range(n_radial - 1):
        base1 = 1 + i * n_angular
        base2 = 1 + (i + 1) * n_angular

        for j in range(n_angular):
            j_next = (j + 1) % n_angular

            v1 = base1 + j
            v2 = base1 + j_next
            v3 = base2 + j
            v4 = base2 + j_next

            faces.append([v1, v3, v2])
            faces.append([v2, v3, v4])

    faces = np.array(faces, dtype=np.int32)

    return vertices, faces


def contact_angle_sweep(
    well_radius: float,
    well_depth: float,
    taper_angle_deg: float,
    well_volume_uL: float,
    angles: Optional[List[float]] = None
) -> List[DropletProfile]:
    """
    Compute droplet profiles across a range of contact angles.

    Useful for evaluating surface treatment sensitivity.

    Args:
        well_radius, well_depth, taper_angle_deg: Well geometry
        well_volume_uL: Well volume
        angles: List of contact angles to evaluate (degrees)

    Returns:
        List of DropletProfile for each angle
    """
    if angles is None:
        angles = list(range(10, 170, 10))

    profiles = []
    for angle in angles:
        p = compute_droplet_profile(
            well_radius, well_depth, taper_angle_deg, angle, well_volume_uL
        )
        profiles.append(p)

    return profiles
