"""
NVIDIA Alchemi Bridge (Python 3.13 Isolated)
=============================================
Wraps NVIDIA NIM/Alchemi API calls for quantum-accurate calculations.

Extracted from vanl/backend/core/quantum_engine.py for runtime isolation.
This runs ONLY in the Python 3.13 environment.

Capabilities:
  - Geometry optimization (MLIP-based)
  - Band gap calculation
  - Formation energy prediction
  - Molecular dynamics simulation
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NIM_BASE_URL = os.environ.get("NIM_BASE_URL",
    "https://integrate.api.nvidia.com/v1")

# Try importing NVIDIA toolkit
try:
    import requests
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False


class AlchemiBridge:
    """
    Bridge to NVIDIA Alchemi/NIM APIs.

    All methods accept dicts and return dicts for easy JSON serialization
    over the ZMQ/REST IPC layer.
    """

    # Supported NVIDIA NIM models
    MODELS = {
        "orb-v3": "nvidia/orb-v3",
        "mace-mp": "nvidia/mace-mp-0",
        "sevennet": "nvidia/sevennet-0",
        "mattersim": "microsoft/mattersim-v1-0-0-rc",
    }

    def __init__(self, api_key: Optional[str] = None,
                 model: str = "orb-v3"):
        self.api_key = api_key or NVIDIA_API_KEY
        self.model_id = self.MODELS.get(model, model)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if not self.api_key:
            logger.warning("NVIDIA_API_KEY not set — Alchemi calls will fail")
        else:
            logger.info("AlchemiBridge initialized (model=%s)", self.model_id)

    def optimize_geometry(self, params: Dict) -> Dict:
        """
        Optimize molecular/crystal geometry using NVIDIA MLIP.

        Params:
            positions: list of [x, y, z] coordinates (Å)
            species: list of element symbols
            cell: 3x3 lattice matrix (optional, for periodic)
            fmax: force convergence threshold (eV/Å)
            max_steps: maximum optimization steps

        Returns:
            optimized_positions, final_energy, forces, converged
        """
        t0 = time.perf_counter()

        positions = params.get("positions", [])
        species = params.get("species", [])
        cell = params.get("cell", None)
        fmax = params.get("fmax", 0.05)
        max_steps = params.get("max_steps", 100)

        payload = {
            "model": self.model_id,
            "input": {
                "positions": positions,
                "species": species,
                "fmax": fmax,
                "max_steps": max_steps,
            }
        }
        if cell:
            payload["input"]["cell"] = cell
            payload["input"]["pbc"] = [True, True, True]

        result = self._api_call("/optimize", payload)
        result["compute_time_s"] = time.perf_counter() - t0

        return result

    def calculate_band_gap(self, params: Dict) -> float:
        """
        Predict band gap using NVIDIA MLIP.

        Params:
            positions, species, cell (same as optimize)

        Returns:
            band_gap in eV
        """
        payload = {
            "model": self.model_id,
            "input": {
                "positions": params.get("positions", []),
                "species": params.get("species", []),
                "cell": params.get("cell", []),
                "pbc": params.get("pbc", [True, True, True]),
                "task": "band_gap",
            }
        }

        result = self._api_call("/predict", payload)
        return result.get("band_gap_eV", 0.0)

    def calculate_properties(self, params: Dict) -> Dict:
        """
        Predict multiple properties: energy, forces, stress.

        Returns dict with: energy_eV, forces, stress_GPa
        """
        payload = {
            "model": self.model_id,
            "input": {
                "positions": params.get("positions", []),
                "species": params.get("species", []),
                "cell": params.get("cell", []),
                "pbc": params.get("pbc", [True, True, True]),
            }
        }

        return self._api_call("/properties", payload)

    def run_molecular_dynamics(self, params: Dict) -> Dict:
        """
        Run NVT molecular dynamics simulation.

        Params:
            positions, species, cell, temperature_K, n_steps, timestep_fs
        """
        payload = {
            "model": self.model_id,
            "input": {
                "positions": params.get("positions", []),
                "species": params.get("species", []),
                "cell": params.get("cell", []),
                "pbc": [True, True, True],
                "temperature_K": params.get("temperature_K", 300),
                "n_steps": params.get("n_steps", 1000),
                "timestep_fs": params.get("timestep_fs", 1.0),
                "ensemble": "nvt",
            }
        }

        return self._api_call("/md", payload)

    def _api_call(self, endpoint: str, payload: Dict) -> Dict:
        """Make authenticated API call to NVIDIA NIM."""
        if not HTTP_AVAILABLE:
            return self._offline_fallback(endpoint, payload)

        if not self.api_key:
            return self._offline_fallback(endpoint, payload)

        url = f"{NIM_BASE_URL}{endpoint}"

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=120,
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                return {"error": "Invalid NVIDIA API key", "fallback": self._offline_fallback(endpoint, payload)}
            elif response.status_code == 429:
                return {"error": "Rate limited — try again later", "fallback": self._offline_fallback(endpoint, payload)}
            else:
                return {
                    "error": f"API error: {response.status_code}",
                    "detail": response.text[:500],
                    "fallback": self._offline_fallback(endpoint, payload),
                }
        except requests.ConnectionError:
            return self._offline_fallback(endpoint, payload)
        except requests.Timeout:
            return self._offline_fallback(endpoint, payload)
        except Exception as e:
            return {"error": f"API call failed: {str(e)}",
                    "fallback": self._offline_fallback(endpoint, payload)}

    # ── Offline MLIP Fallback Database ─────────────────────────

    OFFLINE_PROPERTIES = {
        "Au": {"band_gap_eV": 0.0, "formation_energy_eV": 0.0, "lattice_a": 4.078,
               "density_g_cm3": 19.32, "bulk_modulus_GPa": 220, "type": "metal"},
        "Pt": {"band_gap_eV": 0.0, "formation_energy_eV": 0.0, "lattice_a": 3.924,
               "density_g_cm3": 21.45, "bulk_modulus_GPa": 230, "type": "metal"},
        "C":  {"band_gap_eV": 5.47, "formation_energy_eV": 0.0, "lattice_a": 3.567,
               "density_g_cm3": 3.51, "bulk_modulus_GPa": 443, "type": "diamond"},
        "Si": {"band_gap_eV": 1.12, "formation_energy_eV": 0.0, "lattice_a": 5.431,
               "density_g_cm3": 2.33, "bulk_modulus_GPa": 97.6, "type": "semiconductor"},
        "MnO2": {"band_gap_eV": 1.3, "formation_energy_eV": -5.22, "lattice_a": 4.396,
                 "density_g_cm3": 5.03, "bulk_modulus_GPa": 270, "type": "oxide"},
        "TiO2": {"band_gap_eV": 3.2, "formation_energy_eV": -9.73, "lattice_a": 4.594,
                 "density_g_cm3": 4.23, "bulk_modulus_GPa": 210, "type": "oxide"},
        "ZnO":  {"band_gap_eV": 3.37, "formation_energy_eV": -3.63, "lattice_a": 3.250,
                 "density_g_cm3": 5.61, "bulk_modulus_GPa": 183, "type": "semiconductor"},
        "Fe2O3": {"band_gap_eV": 2.2, "formation_energy_eV": -8.29, "lattice_a": 5.035,
                  "density_g_cm3": 5.24, "bulk_modulus_GPa": 220, "type": "oxide"},
        "Cu":   {"band_gap_eV": 0.0, "formation_energy_eV": 0.0, "lattice_a": 3.615,
                 "density_g_cm3": 8.96, "bulk_modulus_GPa": 140, "type": "metal"},
        "Ag":   {"band_gap_eV": 0.0, "formation_energy_eV": 0.0, "lattice_a": 4.086,
                 "density_g_cm3": 10.49, "bulk_modulus_GPa": 104, "type": "metal"},
        "LiFePO4": {"band_gap_eV": 3.8, "formation_energy_eV": -15.4, "lattice_a": 10.332,
                    "density_g_cm3": 3.6, "bulk_modulus_GPa": 96, "type": "cathode"},
        "LiCoO2":  {"band_gap_eV": 2.7, "formation_energy_eV": -7.1, "lattice_a": 2.816,
                    "density_g_cm3": 5.1, "bulk_modulus_GPa": 160, "type": "cathode"},
        "Graphite": {"band_gap_eV": 0.04, "formation_energy_eV": 0.0, "lattice_a": 2.461,
                     "density_g_cm3": 2.26, "bulk_modulus_GPa": 33, "type": "anode"},
    }

    def _offline_fallback(self, endpoint: str, payload: Dict) -> Dict:
        """Return cached material properties when NVIDIA API is unavailable."""
        species = payload.get("input", {}).get("species", [])
        formula = "".join(sorted(set(species))) if species else "unknown"

        # Try to match against offline database
        props = self.OFFLINE_PROPERTIES.get(formula, None)
        if not props:
            # Try first element
            if species:
                props = self.OFFLINE_PROPERTIES.get(species[0], None)

        if props:
            logger.info("Using offline MLIP cache for %s", formula)
            return {
                "source": "offline_cache",
                "formula": formula,
                "properties": props,
                "warning": "Results from local database — connect NVIDIA API for MLIP-grade accuracy",
            }

        return {
            "source": "offline_cache",
            "formula": formula,
            "error": f"No offline data for {formula}",
            "warning": "Set NVIDIA_API_KEY for full MLIP calculations",
        }

    def get_status(self) -> Dict:
        """Check connectivity to NVIDIA services."""
        return {
            "api_key_set": bool(self.api_key),
            "model": self.model_id,
            "nim_url": NIM_BASE_URL,
            "offline_materials": len(self.OFFLINE_PROPERTIES),
            "mode": "online" if self.api_key else "offline_cache",
        }

