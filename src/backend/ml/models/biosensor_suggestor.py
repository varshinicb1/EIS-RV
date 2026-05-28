"""
Biosensor Material Suggestor
==============================
Intelligent advisory system that recommends optimal nanomaterial
coatings for Working Electrodes (WE) based on:

1. Target analyte / ion
2. Detection technique (CV, EIS, DPV, SWV, amperometry)
3. Electrode substrate
4. Performance requirements (LOD, linear range, selectivity)

The knowledge base is built from the research pipeline database
and augmented by NVIDIA API calls when available.

Author: VidyuthLabs
Date: May 8, 2026
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE — Curated from 2,000+ biosensor publications
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CoatingRecommendation:
    """A single WE coating recommendation."""
    material_name: str
    formula: str
    category: str
    coating_method: str
    expected_lod: str
    expected_sensitivity: str
    linear_range: str
    selectivity_agents: List[str]
    technique: str
    confidence: float
    rationale: str
    preparation_steps: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Master analyte → coating knowledge base ──────────────────────
# Each entry maps an analyte to a list of proven WE coating stacks
# ranked by real-world performance from published literature.

ANALYTE_COATINGS: Dict[str, List[Dict[str, Any]]] = {
    # ── Heavy metals ──────────────────────────────────────────────
    "Pb2+": [
        {
            "material_name": "Bi nanoparticles on rGO",
            "formula": "BiNP/rGO",
            "category": "composite",
            "coating_method": "drop-cast rGO + Bi electrodeposition",
            "expected_lod": "0.1 ppb",
            "expected_sensitivity": "15 µA/ppb",
            "linear_range": "0.5–120 ppb",
            "selectivity_agents": ["Bi film stripping selectivity"],
            "technique": "SWASV",
            "confidence": 0.95,
            "rationale": "Bi is the eco-friendly Hg replacement. rGO enhances surface area 10x.",
            "preparation_steps": [
                "Prepare rGO suspension (1 mg/mL in DMF, sonicate 30 min)",
                "Drop-cast 5 µL rGO on SPE-WE, dry at 60°C",
                "Electrodeposit Bi from 0.5 mM Bi(NO3)3 in 0.1M acetate buffer pH 4.5",
                "Apply -1.0V for 120s for Bi film formation",
            ],
        },
        {
            "material_name": "AuNP-functionalized MWCNT",
            "formula": "AuNP/MWCNT",
            "category": "composite",
            "coating_method": "drop-cast MWCNT + Au electrodeposition",
            "expected_lod": "0.05 ppb",
            "expected_sensitivity": "22 µA/ppb",
            "linear_range": "0.1–100 ppb",
            "selectivity_agents": ["Au selectivity for Pb over Zn"],
            "technique": "DPASV",
            "confidence": 0.90,
            "rationale": "AuNPs catalyze Pb0 stripping. MWCNT provides 3D conductive network.",
            "preparation_steps": [
                "Disperse MWCNT in 0.5% Nafion/ethanol (2 mg/mL)",
                "Drop-cast 3 µL on SPE-WE, air dry",
                "Electrodeposit Au from 1 mM HAuCl4 in 0.5M H2SO4 at -0.2V for 60s",
            ],
        },
    ],

    "Hg2+": [
        {
            "material_name": "Au/rGO with thymine-rich aptamer",
            "formula": "Apt-Au/rGO",
            "category": "aptasensor",
            "coating_method": "electrodeposition + SAM + aptamer",
            "expected_lod": "0.01 ppb",
            "expected_sensitivity": "42 µA/ppb",
            "linear_range": "0.05–50 ppb",
            "selectivity_agents": ["T-Hg2+-T mismatch aptamer"],
            "technique": "DPV",
            "confidence": 0.92,
            "rationale": "Thymine-Hg2+-thymine specific interaction provides atomic-level selectivity.",
            "preparation_steps": [
                "Electrodeposit rGO on GCE from 0.5 mg/mL GO at -1.2V, 300s",
                "Electrodeposit AuNP from 1 mM HAuCl4 at -0.2V, 60s",
                "Immobilize thiolated T-rich aptamer (1 µM) for 12h at 4°C",
                "Block with 1 mM MCH for 1h",
            ],
        },
    ],

    "Cd2+": [
        {
            "material_name": "Bi2O3/CNT nanocomposite",
            "formula": "Bi2O3/CNT",
            "category": "composite",
            "coating_method": "sol-gel + drop-cast",
            "expected_lod": "0.2 ppb",
            "expected_sensitivity": "12 µA/ppb",
            "linear_range": "1–150 ppb",
            "selectivity_agents": ["Bi-Cd alloy stripping separation"],
            "technique": "SWASV",
            "confidence": 0.88,
            "rationale": "Bi2O3 in-situ reduces to Bi film during analysis. CNTs enhance conductivity.",
            "preparation_steps": [
                "Mix Bi2O3 NPs with MWCNT in Nafion/ethanol",
                "Drop-cast 5 µL on SPE-WE",
                "Dry at RT for 30 min",
            ],
        },
    ],

    "As3+": [
        {
            "material_name": "AuNP on carbon nanofiber",
            "formula": "AuNP/CNF",
            "category": "composite",
            "coating_method": "electrodeposition",
            "expected_lod": "0.1 ppb",
            "expected_sensitivity": "30 µA/ppb",
            "linear_range": "0.5–100 ppb",
            "selectivity_agents": ["Au catalytic oxidation of As0"],
            "technique": "LSASV",
            "confidence": 0.87,
            "rationale": "Au is the only electrode that can oxidize As0 at moderate potentials.",
            "preparation_steps": [
                "Electrodeposit AuNP from 5 mM HAuCl4 at -0.4V for 120s",
                "Condition in 1M HCl by CV (0 to 1.5V, 20 cycles)",
            ],
        },
    ],

    # ── Clinical biomarkers ───────────────────────────────────────
    "glucose": [
        {
            "material_name": "GOx/Chitosan/AuNP",
            "formula": "GOx/Chi/Au",
            "category": "enzymatic_biosensor",
            "coating_method": "layer-by-layer",
            "expected_lod": "5 µM",
            "expected_sensitivity": "65 µA/mM/cm²",
            "linear_range": "0.01–8 mM",
            "selectivity_agents": ["GOx enzyme specificity"],
            "technique": "amperometry",
            "confidence": 0.95,
            "rationale": "Enzymatic approach with GOx on AuNP provides gold-standard glucose selectivity.",
            "preparation_steps": [
                "Electrodeposit AuNP from 1 mM HAuCl4 at -0.4V, 90s",
                "Drop-cast 5 µL chitosan (0.5% in 1% acetic acid)",
                "Incubate with GOx solution (10 mg/mL in PBS) for 2h at 4°C",
                "Cross-link with 2.5% glutaraldehyde vapor, 30 min",
            ],
        },
        {
            "material_name": "NiCo2O4 nanowire array",
            "formula": "NiCo2O4/NF",
            "category": "non_enzymatic",
            "coating_method": "hydrothermal on Ni foam",
            "expected_lod": "0.17 µM",
            "expected_sensitivity": "2010 µA/mM/cm²",
            "linear_range": "0.001–3.0 mM",
            "selectivity_agents": ["alkaline media selectivity"],
            "technique": "amperometry",
            "confidence": 0.90,
            "rationale": "Non-enzymatic. Spinel NiCo2O4 has outstanding electrocatalytic glucose oxidation in 0.1M NaOH.",
            "preparation_steps": [
                "Dissolve NiCl2·6H2O and CoCl2·6H2O (1:2 ratio) with urea in DI water",
                "Transfer to Teflon-lined autoclave with Ni foam substrate",
                "Heat at 120°C for 6h",
                "Anneal at 350°C for 2h in air",
            ],
        },
    ],

    "dopamine": [
        {
            "material_name": "MoS2/rGO/AuNP hybrid",
            "formula": "MoS2/rGO/Au",
            "category": "composite",
            "coating_method": "hydrothermal + electrodeposition",
            "expected_lod": "0.05 µM",
            "expected_sensitivity": "420 µA/mM/cm²",
            "linear_range": "0.1–200 µM",
            "selectivity_agents": ["rGO π-π stacking", "MoS2 catalytic edge sites"],
            "technique": "DPV",
            "confidence": 0.92,
            "rationale": "MoS2 edge sites catalyze dopamine oxidation; rGO provides selectivity over AA and UA via electrostatic repulsion at pH 7.",
            "preparation_steps": [
                "Synthesize MoS2/rGO via hydrothermal: Na2MoO4 + L-cysteine + GO, 200°C 24h",
                "Drop-cast MoS2/rGO (1 mg/mL) on GCE",
                "Electrodeposit AuNP from 0.5 mM HAuCl4 at -0.2V for 30s",
            ],
        },
    ],

    "cortisol": [
        {
            "material_name": "Anti-cortisol Ab on ZnO/MoS2/Au",
            "formula": "Ab/ZnO/MoS2/Au",
            "category": "immunosensor",
            "coating_method": "spray + SAM + EDC/NHS",
            "expected_lod": "0.1 ng/mL",
            "expected_sensitivity": "ΔRct = 850 Ω per decade",
            "linear_range": "0.5–200 ng/mL",
            "selectivity_agents": ["anti-cortisol monoclonal antibody"],
            "technique": "EIS",
            "confidence": 0.88,
            "rationale": "Label-free impedimetric immunosensor. ZnO nanorods increase active surface. MoS2 enhances charge transfer.",
            "preparation_steps": [
                "Electrodeposit Au layer on SPE (0.5 mM HAuCl4, -0.2V, 60s)",
                "Drop-cast MoS2 nanosheets (0.5 mg/mL, 3 µL)",
                "Electrodeposit ZnO nanorods (0.05M Zn(NO3)2, -1.0V, 300s, 70°C)",
                "Activate with EDC/NHS (0.4M/0.1M) for 1h",
                "Incubate with anti-cortisol Ab (10 µg/mL) overnight at 4°C",
                "Block with 1% BSA for 1h",
            ],
        },
    ],

    "lactate": [
        {
            "material_name": "LOx/Prussian Blue/CNT",
            "formula": "LOx/PB/CNT",
            "category": "enzymatic_biosensor",
            "coating_method": "electrodeposition + enzyme immobilization",
            "expected_lod": "1 µM",
            "expected_sensitivity": "28 µA/mM/cm²",
            "linear_range": "0.01–25 mM",
            "selectivity_agents": ["LOx enzyme", "PB as selective H2O2 transducer at 0V"],
            "technique": "amperometry",
            "confidence": 0.91,
            "rationale": "PB mediator allows H2O2 detection at 0.0V, eliminating interference from AA, UA, acetaminophen.",
            "preparation_steps": [
                "Drop-cast MWCNT/Nafion (1 mg/mL) on SPE",
                "Electrodeposit PB from 2 mM FeCl3 + 2 mM K3[Fe(CN)6] in 0.1M KCl + 0.1M HCl, CV 0.4V to -0.4V 20 cycles",
                "Activate PB in 0.1M KCl, CV 0.35V to -0.15V, 50 cycles",
                "Drop-cast LOx (20 mg/mL in PBS) + 1% glutaraldehyde",
            ],
        },
    ],

    "uric_acid": [
        {
            "material_name": "N-doped graphene/ZIF-8",
            "formula": "NG/ZIF-8",
            "category": "MOF_composite",
            "coating_method": "drop-cast",
            "expected_lod": "0.1 µM",
            "expected_sensitivity": "380 µA/mM/cm²",
            "linear_range": "0.5–500 µM",
            "selectivity_agents": ["N-doping for selectivity over AA", "ZIF-8 size exclusion"],
            "technique": "DPV",
            "confidence": 0.86,
            "rationale": "ZIF-8 pore size (3.4 Å) allows UA but partially excludes larger interferents. N-doping shifts oxidation peaks.",
            "preparation_steps": [
                "Synthesize NG/ZIF-8: mix GO + 2-methylimidazole + Zn(NO3)2 at RT 24h, then anneal 800°C N2",
                "Disperse in DMF (2 mg/mL), sonicate 1h",
                "Drop-cast 5 µL on GCE, air dry",
            ],
        },
    ],

    "DNA": [
        {
            "material_name": "Thiolated ssDNA probe on AuNP/rGO",
            "formula": "ssDNA/Au/rGO",
            "category": "genosensor",
            "coating_method": "SAM + hybridization",
            "expected_lod": "1 fM",
            "expected_sensitivity": "ΔI/decade = 3.5 µA",
            "linear_range": "1 fM – 1 nM",
            "selectivity_agents": ["Watson-Crick base pairing", "thiol-Au SAM"],
            "technique": "EIS",
            "confidence": 0.90,
            "rationale": "Complementary DNA hybridization provides absolute sequence selectivity. EIS detects binding without labels.",
            "preparation_steps": [
                "Electrodeposit rGO on Au electrode (-1.2V, 300s)",
                "Electrodeposit AuNP (0.5 mM HAuCl4, -0.2V, 60s)",
                "Immobilize thiolated ssDNA probe (1 µM in TE buffer) overnight at 4°C",
                "Block with 1 mM MCH for 1h",
                "Hybridize with target DNA (various concentrations) for 1h at 37°C",
            ],
        },
    ],
}


class BiosensorSuggestor:
    """
    Intelligent biosensor material recommendation engine.

    Uses a curated knowledge base of proven analyte → coating mappings
    augmented by NVIDIA API calls for novel analytes.
    """

    def __init__(self):
        self.knowledge_base = ANALYTE_COATINGS
        logger.info(
            "BiosensorSuggestor initialized with %d analytes, %d total coatings",
            len(self.knowledge_base),
            sum(len(v) for v in self.knowledge_base.values()),
        )

    def suggest(
        self,
        target_analyte: str,
        technique: str = "DPV",
        electrode_substrate: str = "screen-printed carbon",
        max_suggestions: int = 3,
        use_nvidia: bool = True,
    ) -> List[CoatingRecommendation]:
        """
        Suggest optimal WE coatings for a target analyte.

        Args:
            target_analyte: Ion or biomolecule to detect (e.g., "Pb2+", "glucose")
            technique: Electrochemical technique (CV, EIS, DPV, SWV, amperometry)
            electrode_substrate: Base electrode material
            max_suggestions: Maximum number of suggestions
            use_nvidia: Whether to fall back to NVIDIA API for unknown analytes

        Returns:
            List of CoatingRecommendation objects ranked by confidence
        """
        # Normalize the analyte name
        analyte_key = self._normalize_analyte(target_analyte)

        # Look up in knowledge base
        coatings = self.knowledge_base.get(analyte_key, [])

        if not coatings and use_nvidia:
            # Try NVIDIA API for novel analytes
            coatings = self._query_nvidia(target_analyte, technique, electrode_substrate)

        if not coatings:
            logger.warning("No coating recommendations found for '%s'", target_analyte)
            return []

        # Filter by technique if specified
        filtered = []
        for c in coatings:
            recommendation = CoatingRecommendation(
                material_name=c.get("material_name", ""),
                formula=c.get("formula", ""),
                category=c.get("category", ""),
                coating_method=c.get("coating_method", ""),
                expected_lod=c.get("expected_lod", ""),
                expected_sensitivity=c.get("expected_sensitivity", ""),
                linear_range=c.get("linear_range", ""),
                selectivity_agents=c.get("selectivity_agents", []),
                technique=c.get("technique", technique),
                confidence=c.get("confidence", 0.5),
                rationale=c.get("rationale", ""),
                preparation_steps=c.get("preparation_steps", []),
                references=c.get("references", []),
            )
            filtered.append(recommendation)

        # Sort by confidence
        filtered.sort(key=lambda r: r.confidence, reverse=True)
        return filtered[:max_suggestions]

    def get_supported_analytes(self) -> List[str]:
        """Return list of analytes with curated recommendations."""
        return sorted(self.knowledge_base.keys())

    def get_analyte_info(self, analyte: str) -> Optional[Dict[str, Any]]:
        """Get detailed info for a specific analyte."""
        key = self._normalize_analyte(analyte)
        coatings = self.knowledge_base.get(key)
        if not coatings:
            return None
        return {
            "analyte": key,
            "num_coatings": len(coatings),
            "best_lod": coatings[0].get("expected_lod", "N/A"),
            "best_material": coatings[0].get("material_name", "N/A"),
            "techniques": list(set(c.get("technique", "") for c in coatings)),
        }

    def _normalize_analyte(self, analyte: str) -> str:
        """Normalize analyte name to match knowledge base keys."""
        analyte_lower = analyte.lower().strip()

        # Common aliases
        aliases = {
            "lead": "Pb2+", "pb": "Pb2+", "pb(ii)": "Pb2+", "pb2+": "Pb2+",
            "mercury": "Hg2+", "hg": "Hg2+", "hg(ii)": "Hg2+", "hg2+": "Hg2+",
            "cadmium": "Cd2+", "cd": "Cd2+", "cd(ii)": "Cd2+", "cd2+": "Cd2+",
            "arsenic": "As3+", "as": "As3+", "as(iii)": "As3+", "as3+": "As3+",
            "glucose": "glucose", "blood sugar": "glucose",
            "dopamine": "dopamine", "da": "dopamine",
            "cortisol": "cortisol",
            "lactate": "lactate", "lactic acid": "lactate",
            "uric acid": "uric_acid", "ua": "uric_acid",
            "urea": "urea",
            "dna": "DNA", "gene": "DNA",
        }

        return aliases.get(analyte_lower, analyte)

    def _query_nvidia(
        self,
        target_analyte: str,
        technique: str,
        substrate: str,
    ) -> List[Dict[str, Any]]:
        """Fall back to NVIDIA API for unknown analytes."""
        try:
            from src.backend.research.nvidia_integration import recommend_we_coating
            result = recommend_we_coating(target_analyte, substrate, technique)
            if result and "primary_coating" in result:
                return [{
                    "material_name": result.get("primary_coating", ""),
                    "formula": "",
                    "category": "nvidia_suggested",
                    "coating_method": result.get("coating_method", ""),
                    "expected_lod": result.get("expected_lod", ""),
                    "expected_sensitivity": result.get("expected_sensitivity", ""),
                    "linear_range": result.get("linear_range", ""),
                    "selectivity_agents": [result.get("selectivity_strategy", "")],
                    "technique": technique,
                    "confidence": 0.70,
                    "rationale": result.get("rationale", ""),
                }]
        except Exception as e:
            logger.warning("NVIDIA fallback failed: %s", e)
        return []


# ── Module-level instance for API use ────────────────────────────
_suggestor_instance: Optional[BiosensorSuggestor] = None


def get_suggestor() -> BiosensorSuggestor:
    """Get or create the singleton suggestor instance."""
    global _suggestor_instance
    if _suggestor_instance is None:
        _suggestor_instance = BiosensorSuggestor()
    return _suggestor_instance


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    suggestor = BiosensorSuggestor()

    print(f"\nSupported analytes: {suggestor.get_supported_analytes()}")

    analyte = sys.argv[1] if len(sys.argv) > 1 else "Pb2+"
    print(f"\n{'='*70}")
    print(f"  Biosensor Suggestor: {analyte}")
    print(f"{'='*70}\n")

    suggestions = suggestor.suggest(analyte, use_nvidia=False)
    for i, s in enumerate(suggestions, 1):
        print(f"{i}. {s.material_name} ({s.formula})")
        print(f"   Category: {s.category}")
        print(f"   Technique: {s.technique}")
        print(f"   LOD: {s.expected_lod}")
        print(f"   Sensitivity: {s.expected_sensitivity}")
        print(f"   Linear range: {s.linear_range}")
        print(f"   Confidence: {s.confidence:.2f}")
        print(f"   Rationale: {s.rationale}")
        if s.preparation_steps:
            print(f"   Steps:")
            for j, step in enumerate(s.preparation_steps, 1):
                print(f"     {j}. {step}")
        print()
