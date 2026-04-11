"""
Profile I/O
=============
Save, load, and manage design profiles (JSON format).
"""

import json
import os
import glob
from typing import List, Optional

from ..core.presets import profile_to_dict, dict_to_profile, save_preset, load_preset
from ..core.geometry_engine import DesignProfile


DEFAULT_PROFILES_DIR = os.path.join(
    os.path.expanduser("~"), ".analytex", "profiles"
)

DEFAULT_OUTPUT_DIR = os.path.join(
    os.path.expanduser("~"), ".analytex", "output"
)


def ensure_dirs():
    """Create default directories if they don't exist."""
    os.makedirs(DEFAULT_PROFILES_DIR, exist_ok=True)
    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)


def save_profile(profile: DesignProfile, filepath: Optional[str] = None) -> str:
    """
    Save a design profile.

    Args:
        profile: Profile to save
        filepath: Optional path; defaults to ~/.analytex/profiles/<name>.json

    Returns:
        Path where the file was saved
    """
    ensure_dirs()
    if filepath is None:
        safe_name = profile.name.lower().replace(" ", "_").replace("/", "_")
        filepath = os.path.join(DEFAULT_PROFILES_DIR, f"{safe_name}.json")

    save_preset(profile, filepath)
    return filepath


def load_profile(filepath: str) -> DesignProfile:
    """Load a design profile from a JSON file."""
    return load_preset(filepath)


def list_saved_profiles() -> List[str]:
    """List all saved profile files."""
    ensure_dirs()
    pattern = os.path.join(DEFAULT_PROFILES_DIR, "*.json")
    return sorted(glob.glob(pattern))


def get_profile_names() -> List[str]:
    """Get names of all saved profiles."""
    names = []
    for filepath in list_saved_profiles():
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            names.append(data.get("name", os.path.basename(filepath)))
        except Exception:
            names.append(os.path.basename(filepath))
    return names


def delete_profile(filepath: str) -> bool:
    """Delete a saved profile file."""
    try:
        os.remove(filepath)
        return True
    except Exception:
        return False
