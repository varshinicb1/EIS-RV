"""
EC Sensor Literature Review Engine
=====================================
Generates a consolidated, structured literature review from the papers
database, focused on electrochemical (EC) sensors. Covers:

  • Methods & electrochemical techniques
  • Nanomaterials (name + formula)
  • Cyclic Voltammetry (CV) data
  • Differential Pulse Voltammetry (DPV) data
  • EIS data
  • Limit of Detection (LOD) & LOQ
  • Selectivity, sensitivity, interference studies
  • Food sample types analysed
  • Commercial feasibility
  • Challenges, scope & opportunities
"""

import logging
import re
import sqlite3
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────

_LOD_RE = re.compile(
    r"(?:LOD|limit\s+of\s+detection|detection\s+limit)[^\d]*"
    r"([\d.]+(?:\s*[×x]\s*10[⁻\-]?\d+)?)\s*"
    r"(nM|µM|μM|mM|ng\s*/\s*mL|µg\s*/\s*mL|μg\s*/\s*mL|pg\s*/\s*mL|ppb|ppm|mol\s*/\s*L|M)",
    re.IGNORECASE,
)
_LOQ_RE = re.compile(
    r"(?:LOQ|limit\s+of\s+quantification)[^\d]*([\d.]+)\s*(nM|µM|μM|mM|ng\s*/\s*mL|µg\s*/\s*mL)",
    re.IGNORECASE,
)
_SENSITIVITY_RE = re.compile(
    r"sensitivity[^\d]*([\d.]+)\s*(µA\s*/\s*(?:µM|mM|nM)|mA\s*/\s*(?:µM|mM)|nA\s*/\s*(?:µM|nM)"
    r"|µA\s*/\s*(?:µM|mM)[\s·]*cm[⁻\-]?2|mA\s*/\s*mM[\s·]*cm[⁻\-]?2)",
    re.IGNORECASE,
)
_LINEAR_RE = re.compile(
    r"linear\s+range[^\d]*([\d.]+)\s*(?:to|–|-)\s*([\d.]+)\s*(nM|µM|μM|mM|µg\s*/\s*mL|ng\s*/\s*mL|M)",
    re.IGNORECASE,
)
_CV_PEAK_RE = re.compile(
    r"(?:anodic|oxidation|cathodic|reduction)\s+peak[^\d]*([\d.]+)\s*(mA|µA|μA)",
    re.IGNORECASE,
)
_DPV_PEAK_RE = re.compile(
    r"(?:DPV|differential\s+pulse)[^.]*peak[^.]*?([\d.]+)\s*(V|mV)",
    re.IGNORECASE,
)
_SCAN_RATE_RE = re.compile(
    r"scan\s+rate[^\d]*([\d.]+)\s*(?:to\s+([\d.]+)\s*)?(mV\s*/\s*s|V\s*/\s*s)",
    re.IGNORECASE,
)
_FOOD_RE = re.compile(
    r"\b(apple\s*juice|orange\s*juice|grape\s*juice|milk|honey|wine|beer|"
    r"tap\s*water|river\s*water|lake\s*water|drinking\s*water|seawater|"
    r"blood\s*serum|urine|saliva|sweat|plasma|"
    r"vegetable[s]?|fruit[s]?|fish|meat|egg[s]?|cheese|yogurt|"
    r"soy\s*sauce|vinegar|tea|coffee|"
    r"spinach|lettuce|tomato|potato|onion|garlic|pepper)\b",
    re.IGNORECASE,
)
_INTERFERENCE_RE = re.compile(
    r"(?:interferent[s]?|interfering\s+species|selectivity\s+study|coexisting\s+species)"
    r"[^.]*?([A-Z][a-zA-Z]+(?:,\s*[A-Z][a-zA-Z]+){1,10})",
    re.IGNORECASE,
)
_ANALYTE_RE = re.compile(
    r"(?:detection\s+of|sensor\s+for|determination\s+of)\s+"
    r"([a-z][a-z\s\-]+?)(?:\s+in\s+|\s+using\s+|\.|\,)",
    re.IGNORECASE,
)
_TECH_RE = re.compile(
    r"\b(cyclic\s+voltammetry|CV|differential\s+pulse\s+voltammetry|DPV|"
    r"square\s+wave\s+voltammetry|SWV|chronoamperometry|"
    r"electrochemical\s+impedance\s+spectroscopy|EIS|"
    r"linear\s+sweep\s+voltammetry|LSV|amperometry|"
    r"stripping\s+voltammetry|DPASV|SWASV)\b",
    re.IGNORECASE,
)
_CHALLENGE_RE = re.compile(
    r"\b(biofouling|matrix\s+effect|interference|stability|reproducibility|"
    r"scalability|cost|miniaturization|selectivity\s+challenge|"
    r"long[- ]term\s+stability|batch[- ]to[- ]batch|electrode\s+fouling|"
    r"clinical\s+validation|regulatory|shelf[- ]?life)\b",
    re.IGNORECASE,
)
_COMMERCIAL_RE = re.compile(
    r"\b(commercial|point[- ]of[- ]care|POC|on[- ]site|portable|wearable|"
    r"disposable|mass\s+production|screen[- ]printed|low[- ]cost|scalable|"
    r"field\s+deployment|smartphone|IoT|miniaturized)\b",
    re.IGNORECASE,
)

# Nanomaterial → formula lookup
MATERIAL_FORMULAS = {
    "graphene": "C (2D)",
    "graphene_oxide": "C + O functional groups",
    "reduced_graphene_oxide": "rGO",
    "MWCNT": "(C)ₙ multi-walled",
    "SWCNT": "(C)ₙ single-walled",
    "CNT": "(C)ₙ",
    "carbon_quantum_dots": "CQDs",
    "g-C3N4": "g-C₃N₄",
    "Ti3C2Tx": "Ti₃C₂Tₓ",
    "MXene": "Mₙ₊₁XₙTₓ",
    "MoS2": "MoS₂",
    "WS2": "WS₂",
    "MnO2": "MnO₂",
    "NiO": "NiO",
    "Fe2O3": "Fe₂O₃",
    "Fe3O4": "Fe₃O₄",
    "ZnO": "ZnO",
    "TiO2": "TiO₂",
    "CuO": "CuO",
    "Co3O4": "Co₃O₄",
    "NiCo2O4": "NiCo₂O₄",
    "gold_nanoparticles": "Au NPs",
    "silver_nanoparticles": "Ag NPs",
    "platinum_nanoparticles": "Pt NPs",
    "palladium_nanoparticles": "Pd NPs",
    "polyaniline": "PANI",
    "polypyrrole": "PPy",
    "PEDOT": "PEDOT",
    "MOF": "Metal-Organic Framework",
    "ZIF-8": "Zn(mIM)₂",
    "ZIF-67": "Co(mIM)₂",
}


@dataclass
class ECPaperData:
    paper_id: int
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    journal: Optional[str] = None
    source: str = ""
    url: Optional[str] = None
    analytes: List[str] = field(default_factory=list)
    techniques: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)
    lod: Optional[str] = None
    lod_value: Optional[float] = None
    lod_unit: Optional[str] = None
    loq: Optional[str] = None
    sensitivity: Optional[str] = None
    linear_range: Optional[str] = None
    cv_peak: Optional[str] = None
    dpv_peak: Optional[str] = None
    scan_rates: Optional[str] = None
    food_samples: List[str] = field(default_factory=list)
    interferents: List[str] = field(default_factory=list)
    commercial_keywords: List[str] = field(default_factory=list)
    challenges: List[str] = field(default_factory=list)
    abstract: str = ""


@dataclass
class LiteratureReview:
    total_papers: int = 0
    drive_papers: int = 0
    api_papers: int = 0
    papers: List[ECPaperData] = field(default_factory=list)
    # Aggregated
    technique_counts: Dict[str, int] = field(default_factory=dict)
    material_counts: Dict[str, int] = field(default_factory=dict)
    analyte_counts: Dict[str, int] = field(default_factory=dict)
    food_sample_counts: Dict[str, int] = field(default_factory=dict)
    lod_table: List[Dict] = field(default_factory=list)
    sensitivity_table: List[Dict] = field(default_factory=list)
    interference_mentions: Dict[str, int] = field(default_factory=dict)
    commercial_score_avg: float = 0.0
    challenge_counts: Dict[str, int] = field(default_factory=dict)
    scope_keywords: List[str] = field(default_factory=list)


def _extract_ec_data(text: str, title: str, paper_id: int, authors: list,
                     year: int, journal: str, source: str, url: str) -> ECPaperData:
    d = ECPaperData(paper_id=paper_id, title=title, authors=authors,
                    year=year, journal=journal, source=source, url=url)
    if not text:
        return d

    d.abstract = text[:600]

    # Analytes
    d.analytes = list({m.group(1).strip().lower()
                       for m in _ANALYTE_RE.finditer(text)
                       if len(m.group(1).strip()) > 3})[:8]

    # Techniques
    found_tech = set()
    for m in _TECH_RE.finditer(text):
        t = m.group(1).strip()
        normalized = {
            "cyclic voltammetry": "CV", "cv": "CV",
            "differential pulse voltammetry": "DPV", "dpv": "DPV",
            "square wave voltammetry": "SWV", "swv": "SWV",
            "electrochemical impedance spectroscopy": "EIS", "eis": "EIS",
            "amperometry": "Amperometry",
            "chronoamperometry": "Chronoamperometry",
            "linear sweep voltammetry": "LSV", "lsv": "LSV",
            "stripping voltammetry": "Stripping Voltammetry",
            "dpasv": "DPASV", "swasv": "SWASV",
        }.get(t.lower(), t.upper())
        found_tech.add(normalized)
    d.techniques = list(found_tech)

    # LOD
    m = _LOD_RE.search(text)
    if m:
        d.lod = f"{m.group(1)} {m.group(2)}"
        try:
            d.lod_value = float(m.group(1).replace("×10", "e").replace("x10", "e"))
        except Exception:
            pass
        d.lod_unit = m.group(2)

    # LOQ
    m = _LOQ_RE.search(text)
    if m:
        d.loq = f"{m.group(1)} {m.group(2)}"

    # Sensitivity
    m = _SENSITIVITY_RE.search(text)
    if m:
        d.sensitivity = f"{m.group(1)} {m.group(2)}"

    # Linear range
    m = _LINEAR_RE.search(text)
    if m:
        d.linear_range = f"{m.group(1)}–{m.group(2)} {m.group(3)}"

    # CV peak current
    m = _CV_PEAK_RE.search(text)
    if m:
        d.cv_peak = f"{m.group(1)} {m.group(2)}"

    # DPV peak potential
    m = _DPV_PEAK_RE.search(text)
    if m:
        d.dpv_peak = f"{m.group(1)} {m.group(2)}"

    # Scan rates
    m = _SCAN_RATE_RE.search(text)
    if m:
        if m.group(2):
            d.scan_rates = f"{m.group(1)}–{m.group(2)} {m.group(3)}"
        else:
            d.scan_rates = f"{m.group(1)} {m.group(3)}"

    # Food samples
    d.food_samples = list({m.group(1).lower() for m in _FOOD_RE.finditer(text)})

    # Interferents
    m = _INTERFERENCE_RE.search(text)
    if m:
        raw = m.group(1)
        d.interferents = [x.strip() for x in raw.split(",") if x.strip()][:10]

    # Commercial keywords
    d.commercial_keywords = list({m.group(1).lower()
                                   for m in _COMMERCIAL_RE.finditer(text)})

    # Challenges
    d.challenges = list({m.group(1).lower()
                          for m in _CHALLENGE_RE.finditer(text)})

    return d


def generate_review(db_path: str, source_filter: Optional[str] = None) -> LiteratureReview:
    """
    Run the full literature review against the papers database.

    Args:
        db_path: Path to the SQLite papers database.
        source_filter: Optional source_api filter (e.g. 'google_drive').
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    where = ""
    params = []
    if source_filter:
        where = "WHERE p.source_api = ?"
        params = [source_filter]

    rows = conn.execute(f"""
        SELECT p.id, p.title, p.authors, p.abstract, p.full_text,
               p.year, p.journal, p.source_api, p.url, p.processed,
               GROUP_CONCAT(m.component, '|') AS mat_components
        FROM papers p
        LEFT JOIN materials m ON m.paper_id = p.id
        {where}
        GROUP BY p.id
        ORDER BY p.year DESC NULLS LAST
    """, params).fetchall()

    review = LiteratureReview()
    review.total_papers = len(rows)

    for row in rows:
        text = row["full_text"] or row["abstract"] or ""
        title = row["title"] or ""
        authors = json.loads(row["authors"] or "[]")
        if isinstance(authors, str):
            authors = [authors]
        year = row["year"]
        journal = row["journal"]
        source = row["source_api"] or ""
        url = row["url"]

        if "google_drive" in source:
            review.drive_papers += 1
        else:
            review.api_papers += 1

        mat_raw = row["mat_components"] or ""
        materials = [m for m in mat_raw.split("|") if m]

        ec = _extract_ec_data(text, title, row["id"], authors,
                               year, journal, source, url)
        ec.materials = materials
        review.papers.append(ec)

        # Aggregate techniques
        for t in ec.techniques:
            review.technique_counts[t] = review.technique_counts.get(t, 0) + 1

        # Aggregate materials
        for mat in materials:
            review.material_counts[mat] = review.material_counts.get(mat, 0) + 1

        # Aggregate analytes
        for a in ec.analytes:
            review.analyte_counts[a] = review.analyte_counts.get(a, 0) + 1

        # Food samples
        for fs in ec.food_samples:
            review.food_sample_counts[fs] = review.food_sample_counts.get(fs, 0) + 1

        # LOD table
        if ec.lod:
            review.lod_table.append({
                "paper_id": ec.paper_id,
                "title": title[:80],
                "year": year,
                "analyte": ec.analytes[0] if ec.analytes else "—",
                "lod": ec.lod,
                "linear_range": ec.linear_range,
                "sensitivity": ec.sensitivity,
                "materials": materials[:3],
                "source": source,
            })

        # Sensitivity table
        if ec.sensitivity:
            review.sensitivity_table.append({
                "paper_id": ec.paper_id,
                "title": title[:80],
                "year": year,
                "analyte": ec.analytes[0] if ec.analytes else "—",
                "sensitivity": ec.sensitivity,
                "lod": ec.lod,
                "technique": ec.techniques[0] if ec.techniques else "—",
                "materials": materials[:3],
            })

        # Interferents
        for interferent in ec.interferents:
            review.interference_mentions[interferent] = \
                review.interference_mentions.get(interferent, 0) + 1

        # Challenges
        for ch in ec.challenges:
            review.challenge_counts[ch] = review.challenge_counts.get(ch, 0) + 1

    # Scope keywords (top analytes + materials)
    top_analytes = sorted(review.analyte_counts, key=review.analyte_counts.get, reverse=True)[:10]
    top_materials = sorted(review.material_counts, key=review.material_counts.get, reverse=True)[:10]
    review.scope_keywords = top_analytes + top_materials

    # Commercial score: fraction of papers mentioning commercial keywords
    commercial_count = sum(1 for p in review.papers if p.commercial_keywords)
    review.commercial_score_avg = round(commercial_count / max(len(review.papers), 1), 2)

    conn.close()
    return review


def review_to_dict(review: LiteratureReview) -> dict:
    """Serialize a LiteratureReview to a JSON-compatible dict."""
    d = asdict(review)
    # Sort aggregated dicts by value descending
    for key in ("technique_counts", "material_counts", "analyte_counts",
                 "food_sample_counts", "interference_mentions", "challenge_counts"):
        d[key] = dict(sorted(d[key].items(), key=lambda x: x[1], reverse=True))
    return d


def material_formula_table(material_counts: Dict[str, int]) -> List[Dict]:
    """Return a table of materials with formulas and occurrence counts."""
    rows = []
    for mat, count in sorted(material_counts.items(), key=lambda x: x[1], reverse=True):
        rows.append({
            "material": mat.replace("_", " ").title(),
            "formula": MATERIAL_FORMULAS.get(mat, "—"),
            "count": count,
        })
    return rows
