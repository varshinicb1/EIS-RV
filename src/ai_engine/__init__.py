"""
RĀMAN Studio — AI Engine (Python 3.13 Isolated)
=================================================
This module runs in a SEPARATE Python 3.13 runtime.
It communicates with the main backend (Python 3.14) via ZeroMQ or REST.

DO NOT import this from the main backend directly.

Contains:
  - NVIDIA Alchemi bridge (quantum-accurate calculations)
  - ML inference models
  - AI-powered material property prediction
"""

__version__ = "2.0.0"
__python_required__ = "3.13"
