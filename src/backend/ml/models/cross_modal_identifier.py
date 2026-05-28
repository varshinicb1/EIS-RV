"""
Cross-Modal Material Identification Engine
============================================
Automatic material detection from ANY electrochemical file:
  - EIS  (Nyquist/Bode plots → Rct, Cdl, Warburg → material inference)
  - CV   (peak positions, ΔEp, ipa/ipc → redox fingerprint → material)
  - GCD  (plateau voltage, IR drop, coulombic eff → material class)
  - Raman (peak positions → spectral database matching)

The engine normalizes raw data from each modality into a unified
"Electrochemical Fingerprint" and cross-references the material
database for identification.

Cleanup (2026-05-20):
  - Added NiMn₂O₄ (Nickel Manganate) to static fingerprints.
  - Added dynamic loading from ``data/materials_database.json``
    and ``data/material_database/raman_materials.json`` so that new
    materials are picked up automatically without code changes.

Author: VidyuthLabs
Date: May 8, 2026
"""

import numpy as np
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# ELECTROCHEMICAL FINGERPRINT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ElectrochemicalFingerprint:
    """
    Unified representation of a material's electrochemical signature
    across all modalities.
    """
    modality: str  # "EIS", "CV", "GCD", "Raman"

    # CV features
    anodic_peak_V: Optional[float] = None
    cathodic_peak_V: Optional[float] = None
    peak_separation_mV: Optional[float] = None
    ipa_ipc_ratio: Optional[float] = None
    onset_potential_V: Optional[float] = None
    redox_couple: Optional[str] = None

    # EIS features
    rct_ohm: Optional[float] = None
    rs_ohm: Optional[float] = None
    cdl_uF: Optional[float] = None
    warburg_coefficient: Optional[float] = None
    time_constant_s: Optional[float] = None
    impedance_phase_deg: Optional[float] = None

    # GCD features
    plateau_voltage_V: Optional[float] = None
    ir_drop_mV: Optional[float] = None
    specific_capacitance_Fg: Optional[float] = None
    coulombic_efficiency_pct: Optional[float] = None
    discharge_slope: Optional[float] = None
    charge_time_s: Optional[float] = None

    # Raman features
    raman_peaks_cm: List[float] = field(default_factory=list)
    raman_d_g_ratio: Optional[float] = None

    # Metadata
    scan_rate_mVs: Optional[float] = None
    electrolyte: Optional[str] = None
    temperature_C: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MaterialIdentification:
    """Result of cross-modal material identification."""
    material_name: str
    formula: str
    category: str
    confidence: float
    modality_used: str
    matching_features: Dict[str, Any]
    suggested_applications: List[str]
    rationale: str

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# MATERIAL FINGERPRINT DATABASE
# ═══════════════════════════════════════════════════════════════════

# Each material has known electrochemical signatures across modalities.
# This is curated from >1,000 published papers.

MATERIAL_FINGERPRINTS: Dict[str, Dict[str, Any]] = {
    "graphene": {
        "formula": "C (graphene)",
        "category": "carbon",
        "cv": {
            "peak_separation_mV": (59, 80),  # Nearly reversible
            "ipa_ipc_ratio": (0.95, 1.05),
            "onset_potential_V": (-0.2, 0.1),
        },
        "eis": {
            "rct_ohm": (5, 100),        # Very low Rct
            "cdl_uF": (50, 500),         # High double-layer capacitance
            "warburg_coefficient": (10, 200),
        },
        "gcd": {
            "specific_capacitance_Fg": (100, 300),
            "coulombic_efficiency_pct": (95, 100),
        },
        "raman_peaks": [1350, 1580, 2700],  # D, G, 2D bands
        "raman_d_g_ratio": (0.0, 0.3),  # Low D/G = high quality
        "applications": ["supercapacitor", "biosensor", "fuel_cell"],
    },
    "rGO": {
        "formula": "rGO",
        "category": "carbon",
        "cv": {
            "peak_separation_mV": (65, 120),
            "ipa_ipc_ratio": (0.8, 1.1),
        },
        "eis": {
            "rct_ohm": (20, 300),
            "cdl_uF": (100, 800),
        },
        "gcd": {
            "specific_capacitance_Fg": (150, 400),
        },
        "raman_peaks": [1350, 1590, 2700],
        "raman_d_g_ratio": (0.8, 1.5),  # Higher D/G due to defects
        "applications": ["supercapacitor", "biosensor", "battery"],
    },
    "MnO2": {
        "formula": "MnO2",
        "category": "metal_oxide",
        "cv": {
            "peak_separation_mV": (100, 300),
            "onset_potential_V": (-0.1, 0.4),
        },
        "eis": {
            "rct_ohm": (50, 500),
            "cdl_uF": (200, 2000),
        },
        "gcd": {
            "plateau_voltage_V": (0.0, 0.9),
            "specific_capacitance_Fg": (200, 1400),
            "coulombic_efficiency_pct": (85, 98),
        },
        "raman_peaks": [510, 580, 635, 730],
        "applications": ["supercapacitor", "battery"],
    },
    "NiCo2O4": {
        "formula": "NiCo2O4",
        "category": "spinel_oxide",
        "cv": {
            "peak_separation_mV": (80, 200),
            "redox_couple": "Ni2+/Ni3+ and Co2+/Co3+",
        },
        "eis": {
            "rct_ohm": (1, 50),
            "cdl_uF": (500, 5000),
        },
        "gcd": {
            "specific_capacitance_Fg": (800, 2600),
            "coulombic_efficiency_pct": (90, 99),
        },
        "raman_peaks": [192, 475, 520, 620, 680],
        "applications": ["supercapacitor", "glucose_sensor", "OER_catalyst"],
    },
    "Ti3C2Tx": {
        "formula": "Ti3C2Tx",
        "category": "MXene",
        "cv": {
            "peak_separation_mV": (50, 100),
            "ipa_ipc_ratio": (0.9, 1.1),
        },
        "eis": {
            "rct_ohm": (1, 20),
            "cdl_uF": (200, 3000),
        },
        "gcd": {
            "specific_capacitance_Fg": (200, 500),
            "coulombic_efficiency_pct": (95, 100),
        },
        "raman_peaks": [200, 385, 621],
        "applications": ["supercapacitor", "EMI_shielding", "biosensor"],
    },
    "PEDOT:PSS": {
        "formula": "PEDOT:PSS",
        "category": "conducting_polymer",
        "cv": {
            "peak_separation_mV": (30, 80),
            "ipa_ipc_ratio": (0.85, 1.0),
        },
        "eis": {
            "rct_ohm": (5, 100),
            "cdl_uF": (100, 1000),
        },
        "gcd": {
            "specific_capacitance_Fg": (50, 200),
        },
        "raman_peaks": [440, 700, 990, 1260, 1370, 1440, 1500],
        "applications": ["biosensor", "wearable", "solar_cell"],
    },
    "MoS2": {
        "formula": "MoS2",
        "category": "TMD",
        "cv": {
            "peak_separation_mV": (100, 250),
        },
        "eis": {
            "rct_ohm": (50, 500),
            "cdl_uF": (20, 200),
        },
        "gcd": {
            "specific_capacitance_Fg": (100, 400),
        },
        "raman_peaks": [383, 408],  # E2g and A1g modes
        "applications": ["HER_catalyst", "biosensor", "battery"],
    },
    "Fe2O3": {
        "formula": "α-Fe2O3",
        "category": "metal_oxide",
        "cv": {
            "peak_separation_mV": (150, 400),
            "onset_potential_V": (-0.8, -0.3),
            "redox_couple": "Fe2+/Fe3+",
        },
        "eis": {
            "rct_ohm": (100, 2000),
        },
        "gcd": {
            "plateau_voltage_V": (0.5, 1.0),
        },
        "raman_peaks": [225, 245, 293, 299, 412, 498, 613],
        "applications": ["battery", "photocatalysis", "gas_sensor"],
    },
    "ZIF-67": {
        "formula": "Co(2-mIm)2",
        "category": "MOF",
        "cv": {
            "peak_separation_mV": (100, 250),
            "redox_couple": "Co2+/Co3+",
        },
        "eis": {
            "rct_ohm": (200, 2000),
        },
        "raman_peaks": [178, 429, 686, 1146, 1179, 1460],
        "applications": ["supercapacitor", "OER_catalyst", "gas_sensor"],
    },
    "polyaniline": {
        "formula": "PANI",
        "category": "conducting_polymer",
        "cv": {
            "peak_separation_mV": (50, 150),
            "redox_couple": "leucoemeraldine/emeraldine/pernigraniline",
        },
        "eis": {
            "rct_ohm": (10, 200),
            "cdl_uF": (100, 2000),
        },
        "gcd": {
            "specific_capacitance_Fg": (200, 800),
        },
        "raman_peaks": [574, 812, 1170, 1220, 1340, 1480, 1595],
        "applications": ["supercapacitor", "anticorrosion", "biosensor"],
    },
    "Prussian_blue": {
        "formula": "Fe4[Fe(CN)6]3",
        "category": "coordination_compound",
        "cv": {
            "peak_separation_mV": (20, 60),
            "ipa_ipc_ratio": (0.95, 1.05),
            "redox_couple": "Fe2+/Fe3+ hexacyanoferrate",
        },
        "eis": {
            "rct_ohm": (5, 50),
        },
        "raman_peaks": [275, 2102, 2154],
        "applications": ["biosensor", "H2O2_sensor", "battery"],
    },
    "NiMn2O4": {
        "formula": "NiMn2O4",
        "category": "spinel_oxide",
        "cv": {
            "peak_separation_mV": (80, 250),
            "ipa_ipc_ratio": (0.80, 0.90),
            "redox_couple": "Ni2+/Ni3+ and Mn3+/Mn4+",
        },
        "eis": {
            "rct_ohm": (15, 40),       # ~24.5 Ω from experimental data
            "cdl_uF": (10, 25),          # ~15 µF (Cdl_F = 1.5e-5)
            "warburg_coefficient": (20, 100),
        },
        "gcd": {
            "specific_capacitance_Fg": (250, 320),
            "coulombic_efficiency_pct": (85, 95),
        },
        "raman_peaks": [490, 590, 630],  # Spinel Mn–O / Ni–O modes
        "applications": ["supercapacitor", "biosensor", "battery", "electrocatalysis"],
    },
}


# ═══════════════════════════════════════════════════════════════════
# CROSS-MODAL IDENTIFICATION ENGINE
# ═══════════════════════════════════════════════════════════════════

class CrossModalIdentifier:
    """
    Identifies materials from electrochemical data across all modalities.

    On initialisation the engine:
    1. Loads the built-in ``MATERIAL_FINGERPRINTS`` dictionary.
    2. Attempts to load ``data/materials_database.json`` — if it exists,
       EIS / property data for each material is merged into the
       fingerprint dictionary.
    3. Attempts to load ``data/material_database/raman_materials.json`` —
       if it exists, Raman peak positions for each material are merged.

    This means new materials added to either JSON file are automatically
    available for identification without code changes.
    """

    # Paths are relative to the project root (3 levels up from this file)
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    _MATERIALS_DB_PATH = _PROJECT_ROOT / "data" / "materials_database.json"
    _RAMAN_DB_PATH = _PROJECT_ROOT / "data" / "material_database" / "raman_materials.json"

    def __init__(self):
        # Start with the curated static fingerprints
        self.fingerprints: Dict[str, Dict[str, Any]] = dict(MATERIAL_FINGERPRINTS)

        # ── Dynamic enrichment from JSON databases ───────────────
        self._load_materials_database()
        self._load_raman_database()

        logger.info(
            "CrossModalIdentifier initialized with %d material fingerprints"
            " (after dynamic enrichment)",
            len(self.fingerprints),
        )

    # ── Private loaders ──────────────────────────────────────────

    def _load_materials_database(self) -> None:
        """
        Load ``data/materials_database.json`` and merge EIS / property
        data into ``self.fingerprints``.

        For each material entry that contains ``features`` or
        ``eis_params`` keys the corresponding EIS signature ranges are
        derived (±20 % of the nominal value) and merged.
        """
        if not self._MATERIALS_DB_PATH.exists():
            logger.debug(
                "materials_database.json not found at %s — skipping",
                self._MATERIALS_DB_PATH,
            )
            return

        try:
            with open(self._MATERIALS_DB_PATH, 'r', encoding='utf-8') as fh:
                data = json.load(fh)

            materials = data.get('materials', data) if isinstance(data, dict) else data

            for mat in materials:
                name = mat.get('name', '')
                # Build a lookup key that matches the static dict style
                key = (
                    mat.get('formula')
                    or mat.get('id')
                    or name.replace(' ', '_')
                )

                # Initialise entry if not already present
                if key not in self.fingerprints:
                    self.fingerprints[key] = {
                        "formula": mat.get('formula', name),
                        "category": mat.get('category', 'unknown'),
                        "applications": mat.get('applications', []),
                    }
                fp = self.fingerprints[key]

                # Merge EIS ranges from 'features' or 'eis_params'
                feats = mat.get('features', {})
                eis = mat.get('eis_params', {})
                Rs  = feats.get('Rs', eis.get('Rs_ohm'))
                Rct = feats.get('Rct', eis.get('Rct_ohm'))
                Cdl = feats.get('Cdl', eis.get('Cdl_F'))

                if Rs is not None or Rct is not None or Cdl is not None:
                    eis_sig = fp.setdefault('eis', {})
                    if Rct is not None and 'rct_ohm' not in eis_sig:
                        eis_sig['rct_ohm'] = (
                            round(Rct * 0.8, 2), round(Rct * 1.2, 2)
                        )
                    if Cdl is not None and 'cdl_uF' not in eis_sig:
                        # Cdl stored in Farads; convert to µF for the
                        # fingerprint convention.
                        cdl_uF = Cdl * 1e6
                        eis_sig['cdl_uF'] = (
                            round(cdl_uF * 0.8, 2), round(cdl_uF * 1.2, 2)
                        )

            logger.info(
                "Merged %d entries from materials_database.json",
                len(materials),
            )
        except Exception as exc:
            logger.warning(
                "Failed to load materials_database.json: %s", exc
            )

    def _load_raman_database(self) -> None:
        """
        Load ``data/material_database/raman_materials.json`` and merge
        Raman peak positions into ``self.fingerprints``.
        """
        if not self._RAMAN_DB_PATH.exists():
            logger.debug(
                "raman_materials.json not found at %s — skipping",
                self._RAMAN_DB_PATH,
            )
            return

        try:
            with open(self._RAMAN_DB_PATH, 'r', encoding='utf-8') as fh:
                data = json.load(fh)

            materials = data.get('materials', data) if isinstance(data, dict) else data

            for mat in materials:
                name = mat.get('name', '')
                formula = mat.get('formula', '')
                key = formula or name.replace(' ', '_')

                if key not in self.fingerprints:
                    self.fingerprints[key] = {
                        "formula": formula or name,
                        "category": mat.get('category', 'unknown'),
                        "applications": [],
                    }
                fp = self.fingerprints[key]

                # Extract peak positions from reference_peaks
                ref_peaks = mat.get('reference_peaks', [])
                if ref_peaks and 'raman_peaks' not in fp:
                    fp['raman_peaks'] = [
                        p['position_cm'] for p in ref_peaks
                        if 'position_cm' in p
                    ]

                # Extract D/G ratio from quality_indicators
                qi = mat.get('quality_indicators', {})
                dg = qi.get('I_D_I_G_ratio')
                if dg and 'raman_d_g_ratio' not in fp:
                    fp['raman_d_g_ratio'] = tuple(dg)

            logger.info(
                "Merged %d entries from raman_materials.json",
                len(materials),
            )
        except Exception as exc:
            logger.warning(
                "Failed to load raman_materials.json: %s", exc
            )

    def identify_from_cv(
        self,
        peak_separation_mV: Optional[float] = None,
        ipa_ipc_ratio: Optional[float] = None,
        onset_potential_V: Optional[float] = None,
        anodic_peak_V: Optional[float] = None,
        cathodic_peak_V: Optional[float] = None,
    ) -> List[MaterialIdentification]:
        """Identify material from CV features."""
        fingerprint = ElectrochemicalFingerprint(
            modality="CV",
            peak_separation_mV=peak_separation_mV,
            ipa_ipc_ratio=ipa_ipc_ratio,
            onset_potential_V=onset_potential_V,
            anodic_peak_V=anodic_peak_V,
            cathodic_peak_V=cathodic_peak_V,
        )
        return self._match_fingerprint(fingerprint)

    def identify_from_eis(
        self,
        rct_ohm: Optional[float] = None,
        rs_ohm: Optional[float] = None,
        cdl_uF: Optional[float] = None,
        warburg_coefficient: Optional[float] = None,
    ) -> List[MaterialIdentification]:
        """Identify material from EIS features."""
        fingerprint = ElectrochemicalFingerprint(
            modality="EIS",
            rct_ohm=rct_ohm,
            rs_ohm=rs_ohm,
            cdl_uF=cdl_uF,
            warburg_coefficient=warburg_coefficient,
        )
        return self._match_fingerprint(fingerprint)

    def identify_from_gcd(
        self,
        specific_capacitance_Fg: Optional[float] = None,
        coulombic_efficiency_pct: Optional[float] = None,
        plateau_voltage_V: Optional[float] = None,
        ir_drop_mV: Optional[float] = None,
    ) -> List[MaterialIdentification]:
        """Identify material from GCD features."""
        fingerprint = ElectrochemicalFingerprint(
            modality="GCD",
            specific_capacitance_Fg=specific_capacitance_Fg,
            coulombic_efficiency_pct=coulombic_efficiency_pct,
            plateau_voltage_V=plateau_voltage_V,
            ir_drop_mV=ir_drop_mV,
        )
        return self._match_fingerprint(fingerprint)

    def identify_from_raman(
        self,
        peaks_cm: List[float],
        d_g_ratio: Optional[float] = None,
    ) -> List[MaterialIdentification]:
        """Identify material from Raman spectral peaks."""
        fingerprint = ElectrochemicalFingerprint(
            modality="Raman",
            raman_peaks_cm=peaks_cm,
            raman_d_g_ratio=d_g_ratio,
        )
        return self._match_fingerprint(fingerprint)

    def identify_multimodal(
        self,
        fingerprints: List[ElectrochemicalFingerprint],
    ) -> List[MaterialIdentification]:
        """
        Fuse results from multiple modalities for higher confidence.
        """
        all_results: Dict[str, List[MaterialIdentification]] = {}

        for fp in fingerprints:
            results = self._match_fingerprint(fp)
            for r in results:
                key = r.formula
                if key not in all_results:
                    all_results[key] = []
                all_results[key].append(r)

        # Fuse: materials appearing in multiple modalities get boosted
        fused = []
        for formula, matches in all_results.items():
            modalities = [m.modality_used for m in matches]
            avg_confidence = sum(m.confidence for m in matches) / len(matches)
            # Multi-modal bonus: +10% per additional modality
            boost = min(0.3, 0.1 * (len(modalities) - 1))
            final_confidence = min(1.0, avg_confidence + boost)

            merged_features = {}
            for m in matches:
                merged_features.update(m.matching_features)

            fused.append(MaterialIdentification(
                material_name=matches[0].material_name,
                formula=formula,
                category=matches[0].category,
                confidence=final_confidence,
                modality_used="+".join(modalities),
                matching_features=merged_features,
                suggested_applications=matches[0].suggested_applications,
                rationale=f"Cross-modal identification from {', '.join(modalities)}. "
                          f"Average confidence {avg_confidence:.2f} boosted to {final_confidence:.2f}.",
            ))

        fused.sort(key=lambda x: x.confidence, reverse=True)
        return fused

    def _match_fingerprint(
        self, fingerprint: ElectrochemicalFingerprint
    ) -> List[MaterialIdentification]:
        """Match a fingerprint against the database."""
        results = []

        for mat_name, mat_data in self.fingerprints.items():
            score, matched_features = self._compute_match_score(fingerprint, mat_data)

            if score > 0.2:  # Minimum threshold
                results.append(MaterialIdentification(
                    material_name=mat_name,
                    formula=mat_data.get("formula", ""),
                    category=mat_data.get("category", ""),
                    confidence=score,
                    modality_used=fingerprint.modality,
                    matching_features=matched_features,
                    suggested_applications=mat_data.get("applications", []),
                    rationale=self._generate_rationale(mat_name, matched_features, score),
                ))

        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:5]

    def _compute_match_score(
        self,
        fp: ElectrochemicalFingerprint,
        mat: Dict[str, Any],
    ) -> Tuple[float, Dict[str, Any]]:
        """Compute a match score between a fingerprint and a material."""
        scores = []
        matched = {}

        modality = fp.modality.lower()

        # CV matching
        if modality == "cv" and "cv" in mat:
            cv_ref = mat["cv"]
            if fp.peak_separation_mV is not None and "peak_separation_mV" in cv_ref:
                lo, hi = cv_ref["peak_separation_mV"]
                if lo <= fp.peak_separation_mV <= hi:
                    scores.append(1.0)
                    matched["peak_separation_mV"] = f"{fp.peak_separation_mV} in [{lo}, {hi}]"
                else:
                    dist = min(abs(fp.peak_separation_mV - lo), abs(fp.peak_separation_mV - hi))
                    scores.append(max(0, 1.0 - dist / 200))

            if fp.ipa_ipc_ratio is not None and "ipa_ipc_ratio" in cv_ref:
                lo, hi = cv_ref["ipa_ipc_ratio"]
                if lo <= fp.ipa_ipc_ratio <= hi:
                    scores.append(1.0)
                    matched["ipa_ipc_ratio"] = f"{fp.ipa_ipc_ratio:.3f} in [{lo}, {hi}]"
                else:
                    dist = min(abs(fp.ipa_ipc_ratio - lo), abs(fp.ipa_ipc_ratio - hi))
                    scores.append(max(0, 1.0 - dist / 0.5))

            if fp.onset_potential_V is not None and "onset_potential_V" in cv_ref:
                lo, hi = cv_ref["onset_potential_V"]
                if lo <= fp.onset_potential_V <= hi:
                    scores.append(1.0)
                    matched["onset_potential_V"] = f"{fp.onset_potential_V} in [{lo}, {hi}]"

        # EIS matching
        if modality == "eis" and "eis" in mat:
            eis_ref = mat["eis"]
            if fp.rct_ohm is not None and "rct_ohm" in eis_ref:
                lo, hi = eis_ref["rct_ohm"]
                if lo <= fp.rct_ohm <= hi:
                    scores.append(1.0)
                    matched["rct_ohm"] = f"{fp.rct_ohm} Ω in [{lo}, {hi}]"
                else:
                    dist = min(abs(fp.rct_ohm - lo), abs(fp.rct_ohm - hi))
                    scores.append(max(0, 1.0 - dist / (hi * 2)))

            if fp.cdl_uF is not None and "cdl_uF" in eis_ref:
                lo, hi = eis_ref["cdl_uF"]
                if lo <= fp.cdl_uF <= hi:
                    scores.append(1.0)
                    matched["cdl_uF"] = f"{fp.cdl_uF} µF in [{lo}, {hi}]"

        # GCD matching
        if modality == "gcd" and "gcd" in mat:
            gcd_ref = mat["gcd"]
            if fp.specific_capacitance_Fg is not None and "specific_capacitance_Fg" in gcd_ref:
                lo, hi = gcd_ref["specific_capacitance_Fg"]
                if lo <= fp.specific_capacitance_Fg <= hi:
                    scores.append(1.0)
                    matched["specific_capacitance_Fg"] = f"{fp.specific_capacitance_Fg} F/g in [{lo}, {hi}]"
                else:
                    dist = min(abs(fp.specific_capacitance_Fg - lo), abs(fp.specific_capacitance_Fg - hi))
                    scores.append(max(0, 1.0 - dist / (hi * 2)))

            if fp.coulombic_efficiency_pct is not None and "coulombic_efficiency_pct" in gcd_ref:
                lo, hi = gcd_ref["coulombic_efficiency_pct"]
                if lo <= fp.coulombic_efficiency_pct <= hi:
                    scores.append(1.0)
                    matched["coulombic_efficiency_pct"] = f"{fp.coulombic_efficiency_pct}% in [{lo}, {hi}]"

        # Raman matching
        if modality == "raman" and "raman_peaks" in mat:
            ref_peaks = mat["raman_peaks"]
            tolerance = 20  # cm⁻¹
            matched_peaks = 0
            for ref_p in ref_peaks:
                for det_p in fp.raman_peaks_cm:
                    if abs(det_p - ref_p) <= tolerance:
                        matched_peaks += 1
                        break
            if ref_peaks:
                peak_score = matched_peaks / len(ref_peaks)
                scores.append(peak_score)
                if matched_peaks > 0:
                    matched["raman_peaks_matched"] = f"{matched_peaks}/{len(ref_peaks)}"

            if fp.raman_d_g_ratio is not None and "raman_d_g_ratio" in mat:
                lo, hi = mat["raman_d_g_ratio"]
                if lo <= fp.raman_d_g_ratio <= hi:
                    scores.append(1.0)
                    matched["raman_d_g_ratio"] = f"{fp.raman_d_g_ratio:.2f} in [{lo}, {hi}]"

        if not scores:
            return 0.0, matched

        return sum(scores) / len(scores), matched

    def _generate_rationale(
        self, material: str, features: Dict[str, Any], score: float
    ) -> str:
        """Generate a human-readable rationale."""
        feature_strs = [f"{k}: {v}" for k, v in features.items()]
        return (
            f"Material '{material}' matched with confidence {score:.2f}. "
            f"Matching features: {'; '.join(feature_strs) if feature_strs else 'partial signature match'}."
        )


# ── Module-level instance ────────────────────────────────────────
_identifier_instance: Optional[CrossModalIdentifier] = None


def get_identifier() -> CrossModalIdentifier:
    """Get or create the singleton identifier instance."""
    global _identifier_instance
    if _identifier_instance is None:
        _identifier_instance = CrossModalIdentifier()
    return _identifier_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    identifier = CrossModalIdentifier()

    # Test CV identification
    print("="*70)
    print("  Cross-Modal Material Identification Test")
    print("="*70)

    print("\n--- CV Test: ΔEp=65mV, ipa/ipc=0.99 ---")
    results = identifier.identify_from_cv(peak_separation_mV=65, ipa_ipc_ratio=0.99)
    for r in results[:3]:
        print(f"  {r.material_name} ({r.formula}) — confidence: {r.confidence:.2f}")
        print(f"    {r.rationale}")

    print("\n--- EIS Test: Rct=30Ω, Cdl=300µF ---")
    results = identifier.identify_from_eis(rct_ohm=30, cdl_uF=300)
    for r in results[:3]:
        print(f"  {r.material_name} ({r.formula}) — confidence: {r.confidence:.2f}")

    print("\n--- Raman Test: peaks at 1350, 1580, 2700 cm⁻¹ ---")
    results = identifier.identify_from_raman([1350, 1580, 2700])
    for r in results[:3]:
        print(f"  {r.material_name} ({r.formula}) — confidence: {r.confidence:.2f}")

    print("\n--- GCD Test: 250 F/g, 97% CE ---")
    results = identifier.identify_from_gcd(specific_capacitance_Fg=250, coulombic_efficiency_pct=97)
    for r in results[:3]:
        print(f"  {r.material_name} ({r.formula}) — confidence: {r.confidence:.2f}")

    print("\nAll tests completed.")
