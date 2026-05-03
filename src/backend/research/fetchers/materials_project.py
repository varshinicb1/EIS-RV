"""
Materials Project & NIST Data Fetcher
======================================
Retrieves accurate theoretical property data (density, band gap, formation energy)
from the Materials Project API (mp-api) and NIST Chemistry WebBook.

Usage:
Requires an API key (MP_API_KEY) exported to the environment to query 
real Materials Project data. If unavailable, falls back to the local
physics-informed `materials_db.py`.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import mp-api
try:
    from mp_api.client import MPRester
    MP_AVAILABLE = True
except ImportError:
    MP_AVAILABLE = False


class MaterialsProjectFetcher:
    """
    Connects to the Materials Project Database to pull theoretical
    thermodynamic, structural, and electronic properties for electrodes.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MP_API_KEY")
        self.client = None
        
        if MP_AVAILABLE and self.api_key:
            try:
                self.client = MPRester(self.api_key)
                logger.info("Materials Project client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to intialize MPRester: {e}")
        else:
            logger.warning("MP_API_KEY not found or mp-api not installed. Using local DB mode.")

    def fetch_properties(self, formula: str) -> Dict[str, Any]:
        """
        Pull best theoretical properties for a chemical formula.
        """
        if not self.client:
            logger.debug(f"Returning mocked/local properties for {formula} (No MP API Key)")
            return self._fallback_properties(formula)

        try:
            # Query materials project for the lowest energy stable phase (e_above_hull <= 0)
            docs = self.client.summary.search(
                formula=formula,
                is_stable=True,
                fields=["material_id", "density", "band_gap", "formation_energy_per_atom", "theoretical", "structure"]
            )
            
            if not docs:
                logger.warning(f"No stable phase found for {formula} in MP.")
                return {}

            # Sort by lowest formation energy (most stable phase)
            best_doc = sorted(docs, key=lambda x: x.formation_energy_per_atom)[0]
            
            return {
                "mp_id": best_doc.material_id,
                "density_g_cm3": best_doc.density,
                "bandgap_eV": best_doc.band_gap,
                "formation_energy_eV": best_doc.formation_energy_per_atom,
                "is_theoretical": best_doc.theoretical
            }
            
        except Exception as e:
            logger.error(f"Error fetching {formula} from Materials Project: {e}")
            return self._fallback_properties(formula)

    def _fallback_properties(self, formula: str) -> Dict[str, Any]:
        """
        If we don't have an API key, we return a warning message and empty dict,
        letting the system know it must rely on `materials_db.py`.
        """
        return {
            "error": "auth_required",
            "message": "MP_API_KEY required for live queries. Consult materials_db.py."
        }


class NISTFetcher:
    """
    Connects to NIST WebBook for retrieving exact thermochemical properties,
    viscosity specs, or phase change data.
    """
    def __init__(self):
        self.base_url = "https://webbook.nist.gov/cgi/cbook.cgi"

    def fetch_cas_properties(self, cas_number: str) -> Dict[str, Any]:
        """
        A placeholder for NIST HTML parsing or API wrapper.
        """
        logger.info(f"NIST lookup requested for CAS {cas_number}")
        return {
            "source": "NIST",
            "cas": cas_number,
            "status": "not_implemented_without_html_parser"
        }
