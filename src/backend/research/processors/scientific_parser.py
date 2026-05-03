"""
Scientific Information Extractor
===================================
Regex-based extraction of structured scientific data from paper
abstracts and full text.

Extracts:
    - Material components and ratios
    - Synthesis methods and conditions
    - EIS / electrochemical parameters
    - Application classification

Each extraction carries a confidence score. Confidence is determined by:
    - 0.9+: Value extracted from a clear, unambiguous numeric statement
    - 0.7-0.9: Value found in context but with some ambiguity
    - 0.5-0.7: Value inferred from indirect mention
    - <0.5: Low confidence, weak match

Fields not found are returned as None -- never fabricated.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ================================================================
#   Material Extraction Patterns
# ================================================================

# Known material names and their normalized forms
KNOWN_MATERIALS = {
    # Carbon materials
    r"(?:r[- ]?GO|reduced\s+graphene\s+oxide)": "reduced_graphene_oxide",
    r"(?:(?<!\w)GO(?!\w)|graphene\s+oxide)(?!\s+reduced)": "graphene_oxide",
    r"graphene(?:\s+nano(?:sheets?|platelets?|ribbons?))?": "graphene",
    r"(?:MWCNTs?|multi[- ]?wall(?:ed)?\s+carbon\s+nano(?:tubes?))": "MWCNT",
    r"(?:SWCNTs?|single[- ]?wall(?:ed)?\s+carbon\s+nano(?:tubes?))": "SWCNT",
    r"(?:CNTs?|carbon\s+nano(?:tubes?))": "CNT",
    r"carbon\s+black": "carbon_black",
    r"activated\s+carbon": "activated_carbon",
    r"carbon\s+(?:nano)?fibers?": "carbon_fiber",

    # Metal oxides
    r"MnO[_]?2|manganese\s+(?:di)?oxide": "MnO2",
    r"NiO|nickel\s+oxide": "NiO",
    r"Fe[_]?2O[_]?3|iron\s+oxide|hematite": "Fe2O3",
    r"Fe[_]?3O[_]?4|magnetite": "Fe3O4",
    r"Co[_]?3O[_]?4|cobalt\s+oxide": "Co3O4",
    r"RuO[_]?2|ruthenium\s+oxide": "RuO2",
    r"TiO[_]?2|titanium\s+dioxide|titania": "TiO2",
    r"ZnO|zinc\s+oxide": "ZnO",
    r"V[_]?2O[_]?5|vanadium\s+(?:pent)?oxide": "V2O5",
    r"CuO|copper\s+oxide": "CuO",
    r"WO[_]?3|tungsten\s+oxide": "WO3",
    r"SnO[_]?2|tin\s+oxide": "SnO2",

    # Conducting polymers
    r"PEDOT[\s:]*PSS": "PEDOT:PSS",
    r"PEDOT(?![\s:]*PSS)": "PEDOT",
    r"(?:PANI|polyaniline)": "polyaniline",
    r"(?:PPy|polypyrrole)": "polypyrrole",
    r"(?:PTh|polythiophene)": "polythiophene",

    # Metals
    r"(?:Au|gold)\s+nano(?:particles?|wires?|rods?)": "gold_nanoparticles",
    r"(?:Ag|silver)\s+nano(?:particles?|wires?)": "silver_nanoparticles",
    r"(?:Pt|platinum)\s+nano(?:particles?)": "platinum_nanoparticles",

    # Other
    r"Nafion": "Nafion",
    r"chitosan": "chitosan",
    r"PVDF": "PVDF",
}

# Ratio patterns: "X wt%", "X:Y ratio", "X mg/mL"
RATIO_PATTERNS = [
    (r"(\d+(?:\.\d+)?)\s*(?:wt|weight)\s*%", "wt%"),
    (r"(\d+(?:\.\d+)?)\s*(?:mol|molar)\s*%", "mol%"),
    (r"(\d+(?:\.\d+)?)\s*(?:at|atomic)\s*%", "at%"),
    (r"(\d+(?:\.\d+)?)\s*mg\s*/\s*(?:mL|ml)", "mg/mL"),
    (r"(\d+(?:\.\d+)?)\s*(?:mg\s*/\s*cm\s*[23²³])", "mg/cm2"),
    (r"(\d+(?:\.\d+)?)\s*(?:vol|volume)\s*%", "vol%"),
]


# ================================================================
#   Synthesis Extraction Patterns
# ================================================================

SYNTHESIS_METHODS = {
    r"hydrothermal": "hydrothermal",
    r"solvothermal": "solvothermal",
    r"sol[- ]?gel": "sol_gel",
    r"electrodeposit(?:ion|ed)": "electrodeposition",
    r"drop[- ]?cast(?:ing|ed)?": "drop_casting",
    r"spin[- ]?coat(?:ing|ed)?": "spin_coating",
    r"spray[- ]?coat(?:ing|ed)?": "spray_coating",
    r"screen[- ]?print(?:ing|ed)?": "screen_printing",
    r"inkjet[- ]?print(?:ing|ed)?": "inkjet_printing",
    r"(?:CVD|chemical\s+vapor\s+deposition)": "CVD",
    r"co[- ]?precipitation": "coprecipitation",
    r"(?:ALD|atomic\s+layer\s+deposition)": "ALD",
    r"(?:PVD|physical\s+vapor\s+deposition)": "PVD",
    r"(?:ball[- ]?mill(?:ing|ed)?)": "ball_milling",
    r"(?:sonication|ultrasonication)": "sonication",
    r"calcin(?:ation|ed|ing)": "calcination",
    r"anneal(?:ing|ed)": "annealing",
}

# Temperature: "180 C", "180 deg C", "180 degrees Celsius"
TEMP_PATTERN = re.compile(
    r"(\d{2,4})\s*(?:°|deg(?:rees?)?|o)?\s*(?:C|celsius)",
    re.IGNORECASE
)

# Duration: "6 h", "12 hours", "30 min"
DURATION_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>h(?:ours?|rs?)?|min(?:utes?)?)",
    re.IGNORECASE
)

# pH
PH_PATTERN = re.compile(
    r"pH\s*(?:=|of|~|:|was|is|adjusted\s+to)?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE
)


# ================================================================
#   EIS / Electrochemical Extraction Patterns
# ================================================================

# Rct: "Rct = 150 ohm", "charge transfer resistance of 150 Omega"
RCT_PATTERN = re.compile(
    r"(?:R\s*(?:ct|CT)|charge\s+transfer\s+resistance)\s*"
    r"(?:=|of|is|was|:|found\s+to\s+be)?\s*"
    r"(\d+(?:\.\d+)?(?:\s*[xX×]\s*10\s*[\u207b\u2212-]?\s*\d+)?)\s*"
    r"(?:ohm|Ohm|[\u03a9\u2126]|k[\u03a9\u2126])?",
    re.IGNORECASE
)

# Rs: "Rs = 5 ohm", "solution resistance"
RS_PATTERN = re.compile(
    r"(?:R\s*(?:s|S|sol|soln)|solution\s+resistance|ohmic\s+resistance)\s*"
    r"(?:=|of|is|was|:)?\s*"
    r"(\d+(?:\.\d+)?(?:\s*[xX×]\s*10\s*[⁻−-]?\s*\d+)?)\s*"
    r"(?:ohm|Ohm|[ΩΩ]|k[ΩΩ])?",
    re.IGNORECASE
)

# Capacitance: "specific capacitance of 450 F/g", "Cs = 450 F g-1"
CAPACITANCE_PATTERN = re.compile(
    r"(?:specific\s+)?capacitance\s*"
    r"(?:=|of|is|was|:)?\s*"
    r"(\d+(?:\.\d+)?(?:\s*[xX×]\s*10\s*[⁻−-]?\s*\d+)?)\s*"
    r"(?:F\s*/?\s*g|F\s*g\s*[⁻−-]\s*1|mF\s*/?\s*cm\s*[²2])",
    re.IGNORECASE
)

# Electrolyte: "1M KOH", "0.5 M H2SO4", "3M KCl"
ELECTROLYTE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*[Mm]\s+(KOH|H[_]?2SO[_]?4|Na[_]?2SO[_]?4|KCl|NaCl|"
    r"HCl|NaOH|PBS|LiClO[_]?4|KNO[_]?3|Na[_]?2HPO[_]?4)",
    re.IGNORECASE
)

# Frequency range: "0.01 Hz to 100 kHz", "10 mHz - 1 MHz"
FREQ_RANGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(m?Hz|kHz|MHz)\s*(?:to|[-–])\s*"
    r"(\d+(?:\.\d+)?)\s*(m?Hz|kHz|MHz)",
    re.IGNORECASE
)

# Application keywords
APPLICATION_KEYWORDS = {
    "supercapacitor": ["supercapacitor", "electrochemical capacitor", "EDLC",
                       "pseudocapacitor", "hybrid capacitor", "energy storage"],
    "biosensor": ["biosensor", "glucose sensor", "immunosensor",
                  "aptasensor", "electrochemical sensor", "detection limit"],
    "battery": ["battery", "lithium-ion", "Li-ion", "anode", "cathode",
                "charge-discharge", "sodium-ion", "zinc-air"],
    "fuel_cell": ["fuel cell", "PEM", "SOFC", "oxygen reduction", "ORR", "HER", "OER"],
    "corrosion": ["corrosion", "coating", "anticorrosion", "protective"],
    "photocatalysis": ["photocatalysis", "photocatalytic", "photodegradation",
                       "dye degradation", "water splitting"],
}


# ================================================================
#   Extractor Class
# ================================================================

@dataclass
class ExtractionResult:
    """Container for all extracted data from a single paper."""
    materials: List[Dict[str, Any]] = field(default_factory=list)
    synthesis: List[Dict[str, Any]] = field(default_factory=list)
    eis_data: Dict[str, Any] = field(default_factory=dict)
    application: Optional[str] = None
    application_confidence: float = 0.0
    extractions_log: List[Dict[str, Any]] = field(default_factory=list)


class ScientificExtractor:
    """
    Extract structured scientific data from paper text using regex patterns.

    This is a deterministic, rule-based extractor. It does NOT hallucinate --
    if a pattern is not matched, the field is left as None.
    """

    def extract(self, text: str, paper_id: int = 0) -> ExtractionResult:
        """
        Run all extractors on the given text.

        Args:
            text: Full text or abstract of the paper
            paper_id: Database ID for provenance tracking

        Returns:
            ExtractionResult with all extracted fields
        """
        if not text or len(text.strip()) < 50:
            logger.warning("Text too short for extraction (paper_id=%d)", paper_id)
            return ExtractionResult()

        result = ExtractionResult()

        # Extract materials
        result.materials = self._extract_materials(text)

        # Extract synthesis conditions
        result.synthesis = self._extract_synthesis(text)

        # Extract EIS / electrochemical data
        result.eis_data = self._extract_eis(text)

        # Classify application
        result.application, result.application_confidence = \
            self._classify_application(text)

        # Build extraction log
        result.extractions_log = self._build_log(result, paper_id)

        return result

    def _extract_materials(self, text: str) -> List[Dict[str, Any]]:
        """Extract material components and their ratios."""
        found = []
        seen_materials = set()

        for pattern, normalized_name in KNOWN_MATERIALS.items():
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches and normalized_name not in seen_materials:
                seen_materials.add(normalized_name)

                # Confidence: higher if material appears multiple times
                confidence = min(0.5 + 0.1 * len(matches), 0.95)

                # Look for ratio near the material mention
                ratio_value = None
                ratio_unit = None
                for match in matches:
                    # Search within 100 chars of the match for a ratio
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 100)
                    context = text[start:end]

                    for rpat, runit in RATIO_PATTERNS:
                        ratio_match = re.search(rpat, context, re.IGNORECASE)
                        if ratio_match:
                            try:
                                ratio_value = float(ratio_match.group(1))
                                ratio_unit = runit
                                confidence = min(confidence + 0.1, 0.95)
                            except ValueError:
                                pass
                            break

                found.append({
                    "component": normalized_name,
                    "ratio_value": ratio_value,
                    "ratio_unit": ratio_unit,
                    "confidence": round(confidence, 2),
                })

        return found

    def _extract_synthesis(self, text: str) -> List[Dict[str, Any]]:
        """Extract synthesis method and conditions."""
        synth_records = []

        # Find synthesis methods
        methods_found = []
        for pattern, method_name in SYNTHESIS_METHODS.items():
            if re.search(pattern, text, re.IGNORECASE):
                methods_found.append(method_name)

        # Extract temperature
        temp_value = None
        temp_conf = 0.0
        temp_matches = TEMP_PATTERN.findall(text)
        if temp_matches:
            # Pick the most common temperature, or the first
            temps = []
            for t in temp_matches:
                try:
                    temps.append(float(t))
                except ValueError:
                    pass
            if temps:
                # Filter out room temp mentions (20-30 C)
                process_temps = [t for t in temps if t > 50]
                if process_temps:
                    temp_value = process_temps[0]
                    temp_conf = 0.8 if len(process_temps) > 1 else 0.7
                elif temps:
                    temp_value = temps[0]
                    temp_conf = 0.6

        # Extract duration
        duration_hours = None
        dur_conf = 0.0
        for dur_match in DURATION_PATTERN.finditer(text):
            try:
                d = float(dur_match.group("value"))
                unit_str = dur_match.group("unit").lower()
                if "min" in unit_str:
                    d /= 60.0
                duration_hours = d
                dur_conf = 0.75
                break
            except (ValueError, IndexError):
                pass

        # Extract pH
        ph_value = None
        ph_conf = 0.0
        ph_matches = PH_PATTERN.findall(text)
        if ph_matches:
            try:
                ph_value = float(ph_matches[0])
                if 0 <= ph_value <= 14:
                    ph_conf = 0.8
                else:
                    ph_value = None
            except ValueError:
                pass

        # Create a record for each method found, or one generic if no method
        if methods_found:
            for method in methods_found:
                synth_records.append({
                    "method": method,
                    "temperature_C": temp_value,
                    "duration_hours": duration_hours,
                    "pH": ph_value,
                    "confidence": round(max(temp_conf, dur_conf, 0.6), 2),
                })
        elif temp_value or duration_hours:
            synth_records.append({
                "method": None,
                "temperature_C": temp_value,
                "duration_hours": duration_hours,
                "pH": ph_value,
                "confidence": round(max(temp_conf, dur_conf, 0.5), 2),
            })

        return synth_records

    def _extract_eis(self, text: str) -> Dict[str, Any]:
        """Extract EIS and electrochemical parameters."""
        data = {}

        # Rct
        rct_match = RCT_PATTERN.search(text)
        if rct_match:
            val = self._parse_sci_number(rct_match.group(1))
            if val is not None and 0 < val < 1e8:
                data["Rct_ohm"] = val
                data["Rct_confidence"] = 0.85

        # Rs
        rs_match = RS_PATTERN.search(text)
        if rs_match:
            val = self._parse_sci_number(rs_match.group(1))
            if val is not None and 0 < val < 1e6:
                data["Rs_ohm"] = val
                data["Rs_confidence"] = 0.85

        # Capacitance
        cap_match = CAPACITANCE_PATTERN.search(text)
        if cap_match:
            val = self._parse_sci_number(cap_match.group(1))
            if val is not None and 0 < val < 1e5:
                # Determine unit from context
                context = cap_match.group(0)
                if "mF" in context or "cm" in context:
                    data["capacitance_mF_cm2"] = val
                else:
                    data["capacitance_F_g"] = val
                data["capacitance_confidence"] = 0.80

        # Electrolyte
        electrolyte_match = ELECTROLYTE_PATTERN.search(text)
        if electrolyte_match:
            conc = electrolyte_match.group(1)
            species = electrolyte_match.group(2)
            data["electrolyte"] = f"{conc}M {species}"
            data["electrolyte_confidence"] = 0.90

        # Frequency range
        freq_match = FREQ_RANGE_PATTERN.search(text)
        if freq_match:
            f_min = self._convert_freq(
                float(freq_match.group(1)), freq_match.group(2)
            )
            f_max = self._convert_freq(
                float(freq_match.group(3)), freq_match.group(4)
            )
            if f_min is not None and f_max is not None:
                data["freq_min_Hz"] = min(f_min, f_max)
                data["freq_max_Hz"] = max(f_min, f_max)
                data["freq_confidence"] = 0.85

        return data

    def _classify_application(self, text: str) -> Tuple[Optional[str], float]:
        """Classify the paper's primary application domain."""
        text_lower = text.lower()
        scores = {}

        for app, keywords in APPLICATION_KEYWORDS.items():
            count = sum(text_lower.count(kw.lower()) for kw in keywords)
            if count > 0:
                scores[app] = count

        if not scores:
            return None, 0.0

        best_app = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = scores[best_app] / total if total > 0 else 0.0
        confidence = min(confidence, 0.95)

        return best_app, round(confidence, 2)

    def _parse_sci_number(self, text: str) -> Optional[float]:
        """Parse a number that may be in scientific notation."""
        text = text.strip()

        # Handle "X x 10^Y" format
        sci_match = re.match(
            r"(\d+(?:\.\d+)?)\s*[xX×]\s*10\s*[⁻−-]?\s*(\d+)", text
        )
        if sci_match:
            base = float(sci_match.group(1))
            exp_str = sci_match.group(2)
            # Check for negative exponent
            if any(c in text for c in "⁻−-"):
                exp = -int(exp_str)
            else:
                exp = int(exp_str)
            return base * (10 ** exp)

        # Plain number
        try:
            return float(text)
        except ValueError:
            return None

    def _convert_freq(self, value: float, unit: str) -> Optional[float]:
        """Convert frequency to Hz."""
        unit_lower = unit.lower()
        # Distinguish millihertz (mHz) from megahertz (MHz)
        if unit == "MHz":
            return value * 1e6
        elif unit_lower == "mhz" and unit[0] == "m":
            # lowercase 'm' -> millihertz
            return value * 1e-3
        elif unit_lower == "khz":
            return value * 1e3
        elif unit_lower == "hz":
            return value
        return value

    def _build_log(self, result: ExtractionResult, paper_id: int) -> List[Dict]:
        """Build extraction provenance log entries."""
        log = []

        for mat in result.materials:
            log.append({
                "paper_id": paper_id,
                "target_table": "materials",
                "field_name": "component",
                "extracted_value": mat["component"],
                "confidence": mat["confidence"],
                "extraction_method": "regex",
            })

        for syn in result.synthesis:
            for field_name in ["method", "temperature_C", "duration_hours", "pH"]:
                val = syn.get(field_name)
                if val is not None:
                    log.append({
                        "paper_id": paper_id,
                        "target_table": "synthesis",
                        "field_name": field_name,
                        "extracted_value": str(val),
                        "confidence": syn["confidence"],
                        "extraction_method": "regex",
                    })

        for field_name, val in result.eis_data.items():
            if not field_name.endswith("_confidence"):
                conf_key = f"{field_name}_confidence"
                conf = result.eis_data.get(conf_key, 0.5)
                log.append({
                    "paper_id": paper_id,
                    "target_table": "eis_data",
                    "field_name": field_name,
                    "extracted_value": str(val),
                    "confidence": conf,
                    "extraction_method": "regex",
                })

        if result.application:
            log.append({
                "paper_id": paper_id,
                "target_table": "papers",
                "field_name": "application",
                "extracted_value": result.application,
                "confidence": result.application_confidence,
                "extraction_method": "keyword_count",
            })

        return log
