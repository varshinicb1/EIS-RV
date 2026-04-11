"""
Preset Library
===============
Built-in design presets for common electrochemical micro-well configurations.

Presets encode validated parameter sets based on published
electrochemistry best practices and standard manufacturing capabilities.
"""

import json
import os
from typing import Dict, List, Optional
from pathlib import Path

from .geometry_engine import (
    DesignProfile, WellParameters, SubstrateParameters,
    ArrayParameters, ElectrodeLayout, ChannelParameters,
    SurfaceConfig, WellArrayType, SurfaceType
)


# ---------------------------------------------------------------------------
#   Built-in Presets
# ---------------------------------------------------------------------------

def get_builtin_presets() -> Dict[str, DesignProfile]:
    """Return all built-in design presets."""
    return {
        "Standard Electrochemical Well": _preset_standard(),
        "High-Sensitivity Well": _preset_high_sensitivity(),
        "Low-Volume Micro-Well": _preset_low_volume(),
        "Array-Based Sensing Layout": _preset_array_sensing(),
        "Three-Electrode Cell": _preset_three_electrode(),
        "Screen-Printed Electrode Well": _preset_spe_well(),
    }


def _preset_standard() -> DesignProfile:
    """
    Standard electrochemical well.
    - 3 mm diameter, 1 mm depth
    - Suitable for 5-10 µL drop-casting
    - Compatible with standard potentiostat clips
    """
    return DesignProfile(
        name="Standard Electrochemical Well",
        well=WellParameters(
            diameter=3.0, depth=1.0,
            taper_angle=3.0, fillet_radius=0.1,
            bottom_fillet=0.08
        ),
        substrate=SubstrateParameters(
            thickness=2.5, margin=4.0, corner_radius=1.5
        ),
        array=ArrayParameters(
            array_type=WellArrayType.SINGLE,
            rows=1, cols=1
        ),
        electrode=ElectrodeLayout(enabled=False),
        channel=ChannelParameters(
            enabled=True,
            groove_width=1.5, groove_depth=0.3,
            pad_width=4.0, pad_length=6.0, pad_depth=0.2
        ),
        surface=SurfaceConfig(
            well_surface=SurfaceType.HYDROPHILIC,
            outer_surface=SurfaceType.HYDROPHOBIC,
            contact_angle_well=30.0,
            contact_angle_outer=110.0
        )
    )


def _preset_high_sensitivity() -> DesignProfile:
    """
    High-sensitivity well for trace analyte detection.
    - Smaller diameter (2 mm) for concentrated analyte
    - Deeper well (1.5 mm) for larger volume
    - Sharp edges for strong contact-line pinning
    """
    return DesignProfile(
        name="High-Sensitivity Well",
        well=WellParameters(
            diameter=2.0, depth=1.5,
            taper_angle=2.0, fillet_radius=0.05,
            bottom_fillet=0.05
        ),
        substrate=SubstrateParameters(
            thickness=3.0, margin=3.5, corner_radius=1.0
        ),
        array=ArrayParameters(
            array_type=WellArrayType.SINGLE,
            rows=1, cols=1
        ),
        electrode=ElectrodeLayout(enabled=False),
        channel=ChannelParameters(
            enabled=True,
            groove_width=1.0, groove_depth=0.25,
            pad_width=3.0, pad_length=5.0, pad_depth=0.15
        ),
        surface=SurfaceConfig(
            well_surface=SurfaceType.HYDROPHILIC,
            outer_surface=SurfaceType.HYDROPHOBIC,
            contact_angle_well=20.0,
            contact_angle_outer=120.0
        )
    )


def _preset_low_volume() -> DesignProfile:
    """
    Low-volume micro-well for minimal sample usage.
    - 1 mm diameter, 0.5 mm depth
    - Sub-microliter volumes
    - Optimized for expensive reagents
    """
    return DesignProfile(
        name="Low-Volume Micro-Well",
        well=WellParameters(
            diameter=1.0, depth=0.5,
            taper_angle=1.0, fillet_radius=0.03,
            bottom_fillet=0.03
        ),
        substrate=SubstrateParameters(
            thickness=1.5, margin=2.5, corner_radius=0.5
        ),
        array=ArrayParameters(
            array_type=WellArrayType.SINGLE,
            rows=1, cols=1
        ),
        electrode=ElectrodeLayout(enabled=False),
        channel=ChannelParameters(
            enabled=False
        ),
        surface=SurfaceConfig(
            well_surface=SurfaceType.HYDROPHILIC,
            outer_surface=SurfaceType.HYDROPHOBIC,
            contact_angle_well=25.0,
            contact_angle_outer=115.0
        )
    )


def _preset_array_sensing() -> DesignProfile:
    """
    Array-based sensing layout.
    - 4×2 rectangular array
    - 3 mm wells, 6 mm spacing
    - Individual contact channels
    """
    return DesignProfile(
        name="Array-Based Sensing Layout",
        well=WellParameters(
            diameter=3.0, depth=1.0,
            taper_angle=3.0, fillet_radius=0.1,
            bottom_fillet=0.08
        ),
        substrate=SubstrateParameters(
            thickness=2.5, margin=5.0, corner_radius=2.0
        ),
        array=ArrayParameters(
            array_type=WellArrayType.RECTANGULAR,
            rows=2, cols=4,
            spacing_x=6.0, spacing_y=6.0
        ),
        electrode=ElectrodeLayout(enabled=False),
        channel=ChannelParameters(
            enabled=True,
            groove_width=1.0, groove_depth=0.25,
            pad_width=3.0, pad_length=4.0, pad_depth=0.15
        ),
        surface=SurfaceConfig(
            well_surface=SurfaceType.HYDROPHILIC,
            outer_surface=SurfaceType.HYDROPHOBIC,
            contact_angle_well=30.0,
            contact_angle_outer=110.0
        )
    )


def _preset_three_electrode() -> DesignProfile:
    """
    Three-electrode electrochemical cell.
    - WE, RE, CE regions with proper spacing
    - Contact channels for each electrode
    - Optimized for cyclic voltammetry
    """
    return DesignProfile(
        name="Three-Electrode Cell",
        well=WellParameters(
            diameter=4.0, depth=1.2,
            taper_angle=3.0, fillet_radius=0.12,
            bottom_fillet=0.1
        ),
        substrate=SubstrateParameters(
            thickness=3.0, margin=6.0, corner_radius=2.0
        ),
        array=ArrayParameters(
            array_type=WellArrayType.SINGLE,
            rows=1, cols=1
        ),
        electrode=ElectrodeLayout(
            enabled=True,
            we_diameter=4.0,
            re_width=1.5, re_length=3.0,
            ce_width=2.0, ce_length=4.0,
            we_re_spacing=4.0, we_ce_spacing=5.0,
            re_offset_angle=135.0, ce_offset_angle=225.0
        ),
        channel=ChannelParameters(
            enabled=True,
            groove_width=1.5, groove_depth=0.3,
            pad_width=4.0, pad_length=6.0, pad_depth=0.2
        ),
        surface=SurfaceConfig(
            well_surface=SurfaceType.HYDROPHILIC,
            outer_surface=SurfaceType.HYDROPHOBIC,
            contact_angle_well=30.0,
            contact_angle_outer=110.0
        )
    )


def _preset_spe_well() -> DesignProfile:
    """
    Screen-Printed Electrode (SPE) compatible well.
    - Dimensions match standard SPE footprints
    - Single well over WE area
    - Contact pads for SPE connector
    """
    return DesignProfile(
        name="Screen-Printed Electrode Well",
        well=WellParameters(
            diameter=5.0, depth=1.0,
            taper_angle=5.0, fillet_radius=0.15,
            bottom_fillet=0.1
        ),
        substrate=SubstrateParameters(
            thickness=2.0, margin=5.0, corner_radius=1.5
        ),
        array=ArrayParameters(
            array_type=WellArrayType.SINGLE,
            rows=1, cols=1
        ),
        electrode=ElectrodeLayout(enabled=False),
        channel=ChannelParameters(
            enabled=True,
            groove_width=2.0, groove_depth=0.3,
            pad_width=5.0, pad_length=8.0, pad_depth=0.2,
            snap_fit=True
        ),
        surface=SurfaceConfig(
            well_surface=SurfaceType.HYDROPHILIC,
            outer_surface=SurfaceType.HYDROPHOBIC,
            contact_angle_well=35.0,
            contact_angle_outer=105.0
        )
    )


# ---------------------------------------------------------------------------
#   Preset Serialization
# ---------------------------------------------------------------------------

def profile_to_dict(profile: DesignProfile) -> dict:
    """Serialize a DesignProfile to a JSON-compatible dictionary."""
    return {
        "name": profile.name,
        "well": {
            "diameter": profile.well.diameter,
            "depth": profile.well.depth,
            "taper_angle": profile.well.taper_angle,
            "fillet_radius": profile.well.fillet_radius,
            "bottom_fillet": profile.well.bottom_fillet,
        },
        "substrate": {
            "thickness": profile.substrate.thickness,
            "margin": profile.substrate.margin,
            "corner_radius": profile.substrate.corner_radius,
        },
        "array": {
            "array_type": profile.array.array_type.value,
            "rows": profile.array.rows,
            "cols": profile.array.cols,
            "spacing_x": profile.array.spacing_x,
            "spacing_y": profile.array.spacing_y,
        },
        "electrode": {
            "enabled": profile.electrode.enabled,
            "we_diameter": profile.electrode.we_diameter,
            "re_width": profile.electrode.re_width,
            "re_length": profile.electrode.re_length,
            "ce_width": profile.electrode.ce_width,
            "ce_length": profile.electrode.ce_length,
            "we_re_spacing": profile.electrode.we_re_spacing,
            "we_ce_spacing": profile.electrode.we_ce_spacing,
            "re_offset_angle": profile.electrode.re_offset_angle,
            "ce_offset_angle": profile.electrode.ce_offset_angle,
        },
        "channel": {
            "enabled": profile.channel.enabled,
            "groove_width": profile.channel.groove_width,
            "groove_depth": profile.channel.groove_depth,
            "pad_width": profile.channel.pad_width,
            "pad_length": profile.channel.pad_length,
            "pad_depth": profile.channel.pad_depth,
            "snap_fit": profile.channel.snap_fit,
        },
        "surface": {
            "well_surface": profile.surface.well_surface.value,
            "outer_surface": profile.surface.outer_surface.value,
            "contact_angle_well": profile.surface.contact_angle_well,
            "contact_angle_outer": profile.surface.contact_angle_outer,
        },
    }


def dict_to_profile(data: dict) -> DesignProfile:
    """Deserialize a dictionary to a DesignProfile."""
    return DesignProfile(
        name=data.get("name", "Imported Design"),
        well=WellParameters(
            diameter=data["well"]["diameter"],
            depth=data["well"]["depth"],
            taper_angle=data["well"]["taper_angle"],
            fillet_radius=data["well"]["fillet_radius"],
            bottom_fillet=data["well"].get("bottom_fillet", 0.1),
        ),
        substrate=SubstrateParameters(
            thickness=data["substrate"]["thickness"],
            margin=data["substrate"]["margin"],
            corner_radius=data["substrate"].get("corner_radius", 1.0),
        ),
        array=ArrayParameters(
            array_type=WellArrayType(data["array"]["array_type"]),
            rows=data["array"]["rows"],
            cols=data["array"]["cols"],
            spacing_x=data["array"].get("spacing_x", 5.0),
            spacing_y=data["array"].get("spacing_y", 5.0),
        ),
        electrode=ElectrodeLayout(
            enabled=data["electrode"]["enabled"],
            we_diameter=data["electrode"].get("we_diameter", 3.0),
            re_width=data["electrode"].get("re_width", 1.5),
            re_length=data["electrode"].get("re_length", 3.0),
            ce_width=data["electrode"].get("ce_width", 2.0),
            ce_length=data["electrode"].get("ce_length", 4.0),
            we_re_spacing=data["electrode"].get("we_re_spacing", 2.0),
            we_ce_spacing=data["electrode"].get("we_ce_spacing", 3.0),
            re_offset_angle=data["electrode"].get("re_offset_angle", 120.0),
            ce_offset_angle=data["electrode"].get("ce_offset_angle", 240.0),
        ),
        channel=ChannelParameters(
            enabled=data["channel"]["enabled"],
            groove_width=data["channel"].get("groove_width", 1.5),
            groove_depth=data["channel"].get("groove_depth", 0.3),
            pad_width=data["channel"].get("pad_width", 4.0),
            pad_length=data["channel"].get("pad_length", 6.0),
            pad_depth=data["channel"].get("pad_depth", 0.2),
            snap_fit=data["channel"].get("snap_fit", False),
        ),
        surface=SurfaceConfig(
            well_surface=SurfaceType(data["surface"].get("well_surface", "hydrophilic")),
            outer_surface=SurfaceType(data["surface"].get("outer_surface", "hydrophobic")),
            contact_angle_well=data["surface"].get("contact_angle_well", 30.0),
            contact_angle_outer=data["surface"].get("contact_angle_outer", 110.0),
        ),
    )


def save_preset(profile: DesignProfile, filepath: str):
    """Save a design profile to a JSON file."""
    data = profile_to_dict(profile)
    parent = os.path.dirname(os.path.abspath(filepath))
    os.makedirs(parent, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_preset(filepath: str) -> DesignProfile:
    """Load a design profile from a JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return dict_to_profile(data)


def save_builtin_presets(directory: str):
    """Save all built-in presets as JSON files."""
    os.makedirs(directory, exist_ok=True)
    for name, profile in get_builtin_presets().items():
        filename = name.lower().replace(" ", "_").replace("-", "_") + ".json"
        filepath = os.path.join(directory, filename)
        save_preset(profile, filepath)
