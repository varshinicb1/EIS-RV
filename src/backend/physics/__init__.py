"""
Advanced Physics Validation Module for RĀMAN Studio
===================================================
Provides integration with LAMMPS and Quantum ESPRESSO for
advanced physics-based validation and parameter extraction.

Author: RĀMAN Studio Team
Date: May 12, 2026
"""

from .lammps_integration import LAMMPSIntegration, get_lammps_integration
from .quantum_espresso_integration import QuantumEspressoIntegration, get_qe_integration

__all__ = [
    "LAMMPSIntegration",
    "get_lammps_integration",
    "QuantumEspressoIntegration",
    "get_qe_integration",
]
