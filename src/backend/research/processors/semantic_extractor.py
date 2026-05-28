"""
Semantic NLP Material Extractor
=================================
Replaces regex-based extraction with LLM-powered semantic parsing.
Reads full paper abstracts and extracts structured data using:

1. Local pattern matching (fast, no API needed)
2. NVIDIA NIM API (deep, contextual understanding)
3. Cross-validation between both methods for high confidence

Extracted entities:
  - Material names, formulas, and categories
  - Synthesis methods and conditions
  - Electrochemical parameters (Rct, Cdl, LOD, etc.)
  - Application classification
  - Performance metrics

Author: VidyuthLabs
Date: May 8, 2026
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """A single extracted scientific entity."""
    entity_type: str          # "material", "method", "parameter", "application"
    value: str                # The extracted value
    normalized: str           # Normalized/standardized form
    confidence: float         # 0-1 confidence score
    context: str = ""         # Surrounding text context
    source: str = "regex"     # "regex", "nlp", "cross_validated"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SemanticExtractionResult:
    """Full extraction result from a paper."""
    materials: List[ExtractedEntity] = field(default_factory=list)
    methods: List[ExtractedEntity] = field(default_factory=list)
    parameters: List[ExtractedEntity] = field(default_factory=list)
    applications: List[ExtractedEntity] = field(default_factory=list)
    raw_text: str = ""
    extraction_method: str = "hybrid"
    total_entities: int = 0

    def to_dict(self) -> dict:
        return {
            "materials": [m.to_dict() for m in self.materials],
            "methods": [m.to_dict() for m in self.methods],
            "parameters": [p.to_dict() for p in self.parameters],
            "applications": [a.to_dict() for a in self.applications],
            "extraction_method": self.extraction_method,
            "total_entities": self.total_entities,
        }


# NLP extraction prompt template
NLP_SYSTEM_PROMPT = """You are an expert electrochemist parsing scientific papers.
Extract ALL structured scientific information from the text.
Return ONLY valid JSON with no markdown fences.

Output format:
{
  "materials": [{"name": "...", "formula": "...", "category": "..."}],
  "synthesis_methods": [{"method": "...", "temperature_C": null, "duration_h": null, "precursors": []}],
  "electrochemical_parameters": [{"name": "...", "value": "...", "unit": "..."}],
  "applications": ["..."],
  "performance": {"LOD": "...", "sensitivity": "...", "linear_range": "...", "Rct": "...", "Cdl": "..."}
}

Rules:
- Extract EVERY material mentioned, including substrates, modifiers, and electrolytes
- Include numerical values with units for all parameters
- Classify materials: carbon, metal_oxide, polymer, MOF, MXene, TMD, composite, etc.
- Never fabricate data. If uncertain, omit the field."""


class SemanticExtractor:
    """
    Hybrid regex + NLP extractor for scientific papers.
    """

    def __init__(self, use_nlp: bool = True):
        """
        Args:
            use_nlp: Enable NVIDIA NIM extraction (requires API key)
        """
        self.use_nlp = use_nlp

        # Import the regex patterns from the existing parser
        try:
            from src.backend.research.processors.scientific_parser import (
                KNOWN_MATERIALS,
                SYNTHESIS_METHODS,
                APPLICATION_KEYWORDS,
            )
            self.known_materials = KNOWN_MATERIALS
            self.synthesis_methods = SYNTHESIS_METHODS
            self.application_keywords = APPLICATION_KEYWORDS
        except ImportError:
            # Fallback — load from relative path
            try:
                from research.processors.scientific_parser import (
                    KNOWN_MATERIALS,
                    SYNTHESIS_METHODS,
                    APPLICATION_KEYWORDS,
                )
                self.known_materials = KNOWN_MATERIALS
                self.synthesis_methods = SYNTHESIS_METHODS
                self.application_keywords = APPLICATION_KEYWORDS
            except ImportError:
                logger.warning("Could not import scientific_parser patterns; using minimal set")
                self.known_materials = {}
                self.synthesis_methods = {}
                self.application_keywords = {}

        # Electrochemical parameter patterns
        self._param_patterns = {
            "Rct": re.compile(
                r"(?:R\s*(?:ct|CT)|charge\s+transfer\s+resistance)\s*\)?\s*"
                r"(?:=|of|is|was|:)?\s*"
                r"(\d+(?:\.\d+)?)\s*(?:(?:k|m)?(?:ohm|Ohm|Ω))?",
                re.IGNORECASE,
            ),
            "Rs": re.compile(
                r"(?:R\s*(?:s|S|sol)|solution\s+resistance)\s*"
                r"(?:=|of|is|was|:)?\s*"
                r"(\d+(?:\.\d+)?)\s*(?:(?:k|m)?(?:ohm|Ohm|Ω))?",
                re.IGNORECASE,
            ),
            "Cdl": re.compile(
                r"(?:C\s*(?:dl|DL)|double[- ]layer\s+capacitance)\s*"
                r"(?:=|of|is|was|:)?\s*"
                r"(\d+(?:\.\d+)?)\s*(?:(?:m|μ|n)?F)?",
                re.IGNORECASE,
            ),
            "LOD": re.compile(
                r"(?:LOD|limit\s+of\s+detection|detection\s+limit)\s*\)?\s*"
                r"(?:=|of|is|was|:)?\s*"
                r"(\d+(?:\.\d+)?(?:\s*[xX×]\s*10\s*[⁻−-]?\s*\d+)?)\s*"
                r"(?:(?:p|n|μ|m)?(?:M|mol/L|g/L|ppm|ppb))?",
                re.IGNORECASE,
            ),
            "sensitivity": re.compile(
                r"sensitivity\s*(?:=|of|is|was|:)?\s*"
                r"(\d+(?:\.\d+)?)\s*"
                r"(?:μA|mA|nA)\s*/\s*(?:mM|μM|nM)\s*(?:/\s*cm[²2])?",
                re.IGNORECASE,
            ),
            "specific_capacitance": re.compile(
                r"(?:specific\s+)?capacitance\s*(?:=|of|is|was|:)?\s*"
                r"(\d+(?:\.\d+)?)\s*F\s*/\s*g",
                re.IGNORECASE,
            ),
            "linear_range": re.compile(
                r"(?:linear\s+range|linearity)\s*(?:=|of|is|was|:)?\s*"
                r"(\d+(?:\.\d+)?)\s*(?:to|–|-|—)\s*"
                r"(\d+(?:\.\d+)?)\s*(?:(?:p|n|μ|m)?M)",
                re.IGNORECASE,
            ),
        }

        logger.info(
            "SemanticExtractor initialized: %d material patterns, NLP=%s",
            len(self.known_materials),
            use_nlp,
        )

    def extract(self, text: str) -> SemanticExtractionResult:
        """
        Extract all scientific entities from text using hybrid approach.

        Args:
            text: Paper abstract or full text

        Returns:
            SemanticExtractionResult with all extracted entities
        """
        if not text or not text.strip():
            return SemanticExtractionResult()

        # Step 1: Regex extraction (fast, deterministic)
        regex_result = self._extract_regex(text)

        # Step 2: NLP extraction (deep, contextual) — if enabled
        nlp_result = None
        if self.use_nlp:
            nlp_result = self._extract_nlp(text)

        # Step 3: Cross-validate and merge
        if nlp_result:
            merged = self._merge_results(regex_result, nlp_result)
        else:
            merged = regex_result

        merged.raw_text = text[:500]
        merged.total_entities = (
            len(merged.materials) + len(merged.methods)
            + len(merged.parameters) + len(merged.applications)
        )

        return merged

    def _extract_regex(self, text: str) -> SemanticExtractionResult:
        """Extract entities using regex patterns."""
        result = SemanticExtractionResult(extraction_method="regex")

        # Materials
        for pattern, normalized_name in self.known_materials.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for m in matches:
                ctx_start = max(0, m.start() - 50)
                ctx_end = min(len(text), m.end() + 50)
                result.materials.append(ExtractedEntity(
                    entity_type="material",
                    value=m.group(),
                    normalized=normalized_name,
                    confidence=0.85,
                    context=text[ctx_start:ctx_end].strip(),
                    source="regex",
                ))

        # Deduplicate materials by normalized name
        seen = set()
        unique_materials = []
        for m in result.materials:
            if m.normalized not in seen:
                seen.add(m.normalized)
                unique_materials.append(m)
        result.materials = unique_materials

        # Synthesis methods
        for pattern, method_name in self.synthesis_methods.items():
            if re.search(pattern, text, re.IGNORECASE):
                result.methods.append(ExtractedEntity(
                    entity_type="method",
                    value=method_name,
                    normalized=method_name,
                    confidence=0.80,
                    source="regex",
                ))

        # Electrochemical parameters
        for param_name, pattern in self._param_patterns.items():
            match = pattern.search(text)
            if match:
                result.parameters.append(ExtractedEntity(
                    entity_type="parameter",
                    value=match.group(),
                    normalized=param_name,
                    confidence=0.90,
                    context=text[max(0, match.start()-30):min(len(text), match.end()+30)].strip(),
                    source="regex",
                ))

        # Applications
        for domain, keywords in self.application_keywords.items():
            for kw in keywords:
                if kw.lower() in text.lower():
                    result.applications.append(ExtractedEntity(
                        entity_type="application",
                        value=domain,
                        normalized=domain,
                        confidence=0.75,
                        source="regex",
                    ))
                    break

        return result

    def _extract_nlp(self, text: str) -> Optional[SemanticExtractionResult]:
        """Extract entities using NVIDIA NIM LLM."""
        try:
            from src.backend.research.nvidia_integration import _call_nvidia_chat
        except ImportError:
            try:
                from research.nvidia_integration import _call_nvidia_chat
            except ImportError:
                logger.debug("NVIDIA integration not available for NLP extraction")
                return None

        prompt = f"""Extract all scientific entities from this electrochemistry paper text:

---
{text[:3000]}
---

Return ONLY valid JSON as specified."""

        response = _call_nvidia_chat(prompt, system_prompt=NLP_SYSTEM_PROMPT)
        if not response:
            return None

        try:
            # Parse response
            resp_text = response.strip()
            if resp_text.startswith("```"):
                resp_text = resp_text.split("\n", 1)[-1].rsplit("```", 1)[0]

            data = json.loads(resp_text)
            result = SemanticExtractionResult(extraction_method="nlp")

            # Materials
            for mat in data.get("materials", []):
                result.materials.append(ExtractedEntity(
                    entity_type="material",
                    value=mat.get("name", ""),
                    normalized=mat.get("formula", mat.get("name", "")),
                    confidence=0.80,
                    source="nlp",
                ))

            # Methods
            for method in data.get("synthesis_methods", []):
                result.methods.append(ExtractedEntity(
                    entity_type="method",
                    value=method.get("method", ""),
                    normalized=method.get("method", ""),
                    confidence=0.75,
                    source="nlp",
                ))

            # Parameters
            perf = data.get("performance", {})
            for key, val in perf.items():
                if val and val != "N/A":
                    result.parameters.append(ExtractedEntity(
                        entity_type="parameter",
                        value=str(val),
                        normalized=key,
                        confidence=0.75,
                        source="nlp",
                    ))

            params = data.get("electrochemical_parameters", [])
            for p in params:
                result.parameters.append(ExtractedEntity(
                    entity_type="parameter",
                    value=f"{p.get('value', '')} {p.get('unit', '')}".strip(),
                    normalized=p.get("name", ""),
                    confidence=0.75,
                    source="nlp",
                ))

            # Applications
            for app in data.get("applications", []):
                result.applications.append(ExtractedEntity(
                    entity_type="application",
                    value=app,
                    normalized=app.lower().replace(" ", "_"),
                    confidence=0.70,
                    source="nlp",
                ))

            return result

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse NLP extraction: %s", e)
            return None

    def _merge_results(
        self,
        regex_result: SemanticExtractionResult,
        nlp_result: SemanticExtractionResult,
    ) -> SemanticExtractionResult:
        """
        Merge regex and NLP results with cross-validation boosting.

        Entities found by BOTH methods get boosted confidence.
        """
        merged = SemanticExtractionResult(extraction_method="hybrid")

        # Merge materials
        regex_mat_names = {m.normalized.lower() for m in regex_result.materials}
        nlp_mat_names = {m.normalized.lower() for m in nlp_result.materials}

        for m in regex_result.materials:
            if m.normalized.lower() in nlp_mat_names:
                m.confidence = min(1.0, m.confidence + 0.10)
                m.source = "cross_validated"
            merged.materials.append(m)

        # Add NLP-only materials
        for m in nlp_result.materials:
            if m.normalized.lower() not in regex_mat_names:
                merged.materials.append(m)

        # Merge methods (union)
        method_names = set()
        for m in regex_result.methods + nlp_result.methods:
            if m.normalized not in method_names:
                method_names.add(m.normalized)
                merged.methods.append(m)

        # Merge parameters (prefer regex for numerical accuracy)
        param_names = set()
        for p in regex_result.parameters:
            param_names.add(p.normalized)
            merged.parameters.append(p)
        for p in nlp_result.parameters:
            if p.normalized not in param_names:
                merged.parameters.append(p)

        # Merge applications (union)
        app_names = set()
        for a in regex_result.applications + nlp_result.applications:
            if a.normalized not in app_names:
                app_names.add(a.normalized)
                merged.applications.append(a)

        return merged


# ── Module API ───────────────────────────────────────────────────

_extractor_instance: Optional[SemanticExtractor] = None


def get_extractor(use_nlp: bool = True) -> SemanticExtractor:
    """Get or create the singleton extractor instance."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = SemanticExtractor(use_nlp=use_nlp)
    return _extractor_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    sample_abstract = """
    We report a novel MoS2/rGO/AuNP nanocomposite electrode for the
    electrochemical detection of dopamine. The composite was synthesized
    via hydrothermal method at 200°C for 24h using Na2MoO4 and L-cysteine
    as precursors. Electrochemical impedance spectroscopy (EIS) revealed
    a charge transfer resistance (Rct) of 45 Ω, significantly lower than
    bare GCE (1200 Ω). Cyclic voltammetry showed well-defined redox peaks
    with a peak separation of 85 mV. The biosensor exhibited a linear
    range of 0.1 to 200 μM with a limit of detection (LOD) of 0.05 μM
    and sensitivity of 420 μA/mM/cm². The sensor showed excellent
    selectivity over ascorbic acid, uric acid, and glucose.
    """

    extractor = SemanticExtractor(use_nlp=False)
    result = extractor.extract(sample_abstract)

    print(f"\n{'='*70}")
    print("  Semantic NLP Extraction Results")
    print(f"{'='*70}")
    print(f"\nMaterials ({len(result.materials)}):")
    for m in result.materials:
        print(f"  [{m.confidence:.2f}] {m.value} → {m.normalized} ({m.source})")

    print(f"\nMethods ({len(result.methods)}):")
    for m in result.methods:
        print(f"  [{m.confidence:.2f}] {m.normalized} ({m.source})")

    print(f"\nParameters ({len(result.parameters)}):")
    for p in result.parameters:
        print(f"  [{p.confidence:.2f}] {p.normalized}: {p.value} ({p.source})")

    print(f"\nApplications ({len(result.applications)}):")
    for a in result.applications:
        print(f"  [{a.confidence:.2f}] {a.normalized} ({a.source})")

    print(f"\nTotal entities: {result.total_entities}")
