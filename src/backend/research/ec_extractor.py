"""
EC Sensor NIM Extractor
========================
Uses NVIDIA NIM (LLaMA-3.3-70B) + regex fallback to extract the master
EC-sensor comparison table fields from every paper:

    Ref | Material | Electrode | Technique | LOD | Sensitivity
      | Sample Type | Interference Study | Commercial Potential

Works in two passes:
  1. Regex fast-pass  → fills numeric fields (LOD, sensitivity, linear range, …)
  2. NIM validation   → fills qualitative fields + confirms/corrects numerics

Results stored in ``ec_sensor_records`` SQLite table.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Regex patterns (same as literature_review.py, kept independent) ─────────

_LOD_RE = re.compile(
    r"(?:LOD|limit\s+of\s+detection|detection\s+limit)[^\d\n]{0,40}"
    r"([\d.]+(?:\s*[×x]\s*10\s*[⁻\-]?\s*\d+)?)\s*"
    r"(nM|µM|μM|mM|ng\s*/\s*mL|µg\s*/\s*mL|μg\s*/\s*mL|pg\s*/\s*mL|"
    r"ppb|ppm|mol\s*/\s*L|fM|pM|M\b)",
    re.IGNORECASE,
)
_SENSITIVITY_RE = re.compile(
    r"sensitivity[^\d\n]{0,30}"
    r"([\d.]+)\s*"
    r"(µA\s*/\s*(?:µM|mM|nM)(?:\s*[·\.]?\s*cm[\-⁻]?2)?|"
    r"mA\s*/\s*(?:µM|mM|nM)(?:\s*[·\.]?\s*cm[\-⁻]?2)?|"
    r"nA\s*/\s*(?:µM|nM|mM)(?:\s*[·\.]?\s*cm[\-⁻]?2)?|"
    r"µA\s+µM[\-⁻]1|mA\s+mM[\-⁻]1)",
    re.IGNORECASE,
)
_LINEAR_RE = re.compile(
    r"linear(?:\s+dynamic)?\s+range[^\d\n]{0,30}"
    r"([\d.]+(?:[\s×x]\s*10[\-⁻]\d+)?)\s*"
    r"(?:to|–|-|—)\s*"
    r"([\d.]+(?:[\s×x]\s*10[\-⁻]\d+)?)\s*"
    r"(nM|µM|μM|mM|µg\s*/\s*mL|ng\s*/\s*mL|M\b|fM|pM)",
    re.IGNORECASE,
)
_ELECTRODE_RE = re.compile(
    r"\b(glassy\s+carbon\s+electrode|GCE|carbon\s+paste\s+electrode|CPE|"
    r"screen[- ]printed\s+(?:carbon\s+)?electrode|SPE|SPCE|"
    r"gold\s+electrode|platinum\s+electrode|ITO|"
    r"pencil\s+graphite\s+electrode|PGE|"
    r"boron[- ]doped\s+diamond|BDD|flexible\s+electrode|"
    r"paper[- ]based\s+electrode|carbon\s+fiber\s+electrode)\b",
    re.IGNORECASE,
)
_TECH_RE = re.compile(
    r"\b(cyclic\s+voltammetry|CV|differential\s+pulse\s+voltammetry|DPV|"
    r"square\s+wave\s+voltammetry|SWV|"
    r"electrochemical\s+impedance\s+spectroscopy|EIS|"
    r"linear\s+sweep\s+voltammetry|LSV|amperometry|chronoamperometry|"
    r"stripping\s+voltammetry|DPASV|SWASV|DPSV|photoelectrochemical|PEC)\b",
    re.IGNORECASE,
)
_FOOD_SAMPLE_RE = re.compile(
    r"\b(apple\s*juice|orange\s*juice|grape\s*juice|milk|honey|wine|beer|"
    r"tap\s*water|river\s*water|lake\s*water|drinking\s*water|seawater|groundwater|"
    r"blood\s*serum|urine|saliva|sweat|plasma|whole\s*blood|"
    r"vegetables?|fruits?|fish|meat|eggs?|cheese|yoghurt?|yogurt|"
    r"soy\s*sauce|vinegar|tea|coffee|spinach|lettuce|tomato|potato|"
    r"onion|garlic|pepper|soil|sediment)\b",
    re.IGNORECASE,
)
_INTERFERENCE_RE = re.compile(
    r"(?:interferent[s]?|interfering\s+(?:species|substance[s]?)|"
    r"selectivity\s+(?:test|study|experiment)|coexisting\s+(?:species|ions?)|"
    r"common\s+interferent[s]?)[^.;]{0,200}",
    re.IGNORECASE,
)
_COMMERCIAL_RE = re.compile(
    r"\b(point[- ]of[- ]care|POC|portable|wearable|disposable|"
    r"screen[- ]printed|low[- ]cost|mass\s+produc|scalable|"
    r"smartphone|IoT|miniatur|field\s+deploy|commercial[- ]?\s*(?:sensor|application)|"
    r"real[- ]time\s+monitoring|on[- ]site|handheld)\b",
    re.IGNORECASE,
)
_RECOVERY_RE = re.compile(
    r"recover(?:y|ies)[^\d\n]{0,30}([\d.]+)\s*(?:%|percent)",
    re.IGNORECASE,
)

# NIM prompt template
_EC_EXTRACTION_PROMPT = """\
You are an expert electrochemical sensor scientist. Extract structured data from the scientific paper text below.

Return ONLY valid JSON with exactly these keys (use null for missing/unclear):
{{
  "material": "primary electrode material(s), e.g. 'rGO/ZnO nanocomposite'",
  "material_formula": "chemical formula if clear, e.g. 'rGO/ZnO'",
  "electrode_type": "electrode substrate, e.g. 'GCE', 'SPE', 'CPE'",
  "techniques": ["CV", "DPV", "EIS"],
  "analyte": "target analyte being detected",
  "lod": "limit of detection with units, e.g. '0.05 nM'",
  "lod_numeric": 0.05,
  "lod_unit": "nM",
  "sensitivity": "sensitivity with units, e.g. '12.5 µA/µM·cm²'",
  "linear_range": "linear range, e.g. '0.1–100 µM'",
  "sample_types": ["apple juice", "tap water"],
  "recovery_pct": "recovery percentage range, e.g. '97–103%'",
  "interference_study": "brief description of interference/selectivity study or null",
  "interferents_tested": ["ascorbic acid", "dopamine", "glucose"],
  "commercial_potential": "high/medium/low based on POC/portable/wearable mentions",
  "commercial_keywords": ["portable", "disposable", "low-cost"],
  "challenges": ["biofouling", "stability"],
  "fabrication_method": "e.g. 'drop casting', 'electrodeposition'",
  "characterization": ["XRD", "FESEM", "EIS"],
  "is_ec_sensor_paper": true
}}

Paper text (truncated):
{text}

Return ONLY the JSON object. No explanation, no markdown.
"""


# ── DB helpers ────────────────────────────────────────────────────────────────

def ensure_ec_table(conn: sqlite3.Connection):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS ec_sensor_records (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        paper_id        INTEGER UNIQUE,
        title           TEXT,
        authors         TEXT,
        year            INTEGER,
        journal         TEXT,
        url             TEXT,
        source_api      TEXT,
        -- core comparison table fields
        material        TEXT,
        material_formula TEXT,
        electrode_type  TEXT,
        techniques      TEXT,        -- JSON array
        analyte         TEXT,
        lod             TEXT,
        lod_numeric     REAL,
        lod_unit        TEXT,
        sensitivity     TEXT,
        linear_range    TEXT,
        sample_types    TEXT,        -- JSON array
        recovery_pct    TEXT,
        interference_study TEXT,
        interferents_tested TEXT,    -- JSON array
        commercial_potential TEXT,
        commercial_keywords TEXT,    -- JSON array
        challenges      TEXT,        -- JSON array
        fabrication_method TEXT,
        characterization TEXT,       -- JSON array
        -- extraction metadata
        extraction_method TEXT,      -- 'nim' | 'regex' | 'nim+regex'
        nim_validated   INTEGER DEFAULT 0,
        is_ec_sensor    INTEGER DEFAULT 1,
        confidence      REAL DEFAULT 0.0,
        extracted_at    REAL,
        FOREIGN KEY (paper_id) REFERENCES papers(id)
    );
    CREATE INDEX IF NOT EXISTS idx_ec_paper_id ON ec_sensor_records(paper_id);
    CREATE INDEX IF NOT EXISTS idx_ec_analyte   ON ec_sensor_records(analyte);
    CREATE INDEX IF NOT EXISTS idx_ec_material  ON ec_sensor_records(material);
    """)
    conn.commit()


# ── Regex fast-pass ──────────────────────────────────────────────────────────

def regex_extract(text: str) -> Dict[str, Any]:
    """Fast regex extraction — fills numeric/structured fields."""
    result: Dict[str, Any] = {}

    # LOD
    m = _LOD_RE.search(text)
    if m:
        result["lod"] = f"{m.group(1)} {m.group(2)}"
        result["lod_unit"] = m.group(2)
        try:
            raw = m.group(1).replace("×10", "e").replace("x10", "e").replace(" ", "")
            result["lod_numeric"] = float(raw)
        except Exception:
            pass

    # Sensitivity
    m = _SENSITIVITY_RE.search(text)
    if m:
        result["sensitivity"] = f"{m.group(1)} {m.group(2)}"

    # Linear range
    m = _LINEAR_RE.search(text)
    if m:
        result["linear_range"] = f"{m.group(1)}–{m.group(2)} {m.group(3)}"

    # Electrode type
    found_electrodes = list({m.group(1) for m in _ELECTRODE_RE.finditer(text[:5000])})
    if found_electrodes:
        # Normalize
        norm = []
        for e in found_electrodes[:3]:
            e_lower = e.lower()
            if "glassy" in e_lower or "gce" in e_lower.replace(" ", ""):
                norm.append("GCE")
            elif "carbon paste" in e_lower or "cpe" in e_lower:
                norm.append("CPE")
            elif "screen" in e_lower or "spce" in e_lower or "spe" in e_lower:
                norm.append("SPE/SPCE")
            elif "boron" in e_lower or "bdd" in e_lower:
                norm.append("BDD")
            elif "gold" in e_lower:
                norm.append("Gold electrode")
            elif "pencil" in e_lower or "pge" in e_lower:
                norm.append("PGE")
            elif "ito" in e_lower:
                norm.append("ITO")
            elif "paper" in e_lower:
                norm.append("Paper-based")
            else:
                norm.append(e[:30])
        result["electrode_type"] = norm[0] if len(norm) == 1 else " / ".join(norm[:2])

    # Techniques
    techs = set()
    for m in _TECH_RE.finditer(text):
        t = m.group(1).strip().upper()
        norm_map = {
            "CYCLIC VOLTAMMETRY": "CV", "DIFFERENTIAL PULSE VOLTAMMETRY": "DPV",
            "SQUARE WAVE VOLTAMMETRY": "SWV", "ELECTROCHEMICAL IMPEDANCE SPECTROSCOPY": "EIS",
            "LINEAR SWEEP VOLTAMMETRY": "LSV", "CHRONOAMPEROMETRY": "CA",
            "STRIPPING VOLTAMMETRY": "Stripping", "PHOTOELECTROCHEMICAL": "PEC",
        }
        techs.add(norm_map.get(t, t))
    result["techniques"] = sorted(techs)

    # Sample types
    samples = list({m.group(1).lower() for m in _FOOD_SAMPLE_RE.finditer(text)})
    if samples:
        result["sample_types"] = samples[:8]

    # Recovery
    m = _RECOVERY_RE.search(text)
    if m:
        result["recovery_pct"] = f"{m.group(1)}%"

    # Interference mentions
    m = _INTERFERENCE_RE.search(text)
    if m:
        result["interference_study"] = m.group(0)[:200].strip()

    # Commercial keywords
    kws = list({m.group(1).lower() for m in _COMMERCIAL_RE.finditer(text)})
    if kws:
        result["commercial_keywords"] = kws
        score = len(kws)
        result["commercial_potential"] = "high" if score >= 3 else "medium" if score >= 1 else "low"

    return result


# ── NIM extraction ────────────────────────────────────────────────────────────

def nim_extract(text: str, paper_title: str = "") -> Optional[Dict[str, Any]]:
    """
    Call NVIDIA NIM to extract EC sensor fields from paper text.
    Returns None if NIM is unavailable or extraction fails.
    """
    try:
        from src.ai_engine.nim_client import get_default_client, NIMError
        client = get_default_client()
        if not client.is_available():
            return None

        # Truncate text to avoid token limits
        truncated = (paper_title + "\n\n" + text)[:6000]
        prompt = _EC_EXTRACTION_PROMPT.format(text=truncated)

        response_text = client.chat_text(
            prompt,
            system=(
                "You are a precise scientific data extractor. Return only valid JSON. "
                "Never fabricate values not explicitly stated in the text."
            ),
            model="fast",   # llama-3.1-8b for speed
            temperature=0.05,
            max_tokens=1200,
        )

        # Parse JSON from response
        cleaned = response_text.strip()
        # Strip markdown code fences if present
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

        data = json.loads(cleaned)
        if not isinstance(data, dict):
            return None

        # Validate it's actually an EC sensor paper
        if data.get("is_ec_sensor_paper") is False:
            return {"is_ec_sensor": False}

        return data

    except Exception as e:
        logger.debug("NIM extraction failed for paper: %s", e)
        return None


# ── Master extractor ─────────────────────────────────────────────────────────

def extract_and_store(
    paper_id: int,
    title: str,
    authors: List[str],
    year: Optional[int],
    journal: Optional[str],
    url: Optional[str],
    source_api: str,
    abstract: str,
    full_text: str,
    db_conn: sqlite3.Connection,
    use_nim: bool = True,
    force: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Extract EC sensor data from a paper and upsert into ec_sensor_records.
    Returns the extracted dict or None on failure.
    """
    # Skip if already done
    if not force:
        existing = db_conn.execute(
            "SELECT id FROM ec_sensor_records WHERE paper_id=?", (paper_id,)
        ).fetchone()
        if existing:
            return None

    text = (abstract or "") + "\n\n" + (full_text or "")
    text = text[:12000]

    extraction_method = "regex"
    nim_validated = 0
    confidence = 0.3

    # Pass 1: Regex
    record = regex_extract(text)

    # Pass 2: NIM (if available)
    if use_nim:
        nim_data = nim_extract(text, paper_title=title)
        if nim_data:
            nim_validated = 1
            extraction_method = "nim+regex"
            confidence = 0.85

            if nim_data.get("is_ec_sensor") is False:
                # Not an EC sensor paper — still store a minimal record
                nim_validated = 0

            # NIM wins on qualitative fields
            for key in ("material", "material_formula", "analyte",
                        "electrode_type", "interference_study",
                        "fabrication_method", "commercial_potential",
                        "characterization"):
                val = nim_data.get(key)
                if val and val != "null":
                    record[key] = val

            # NIM arrays
            for key in ("techniques", "sample_types", "interferents_tested",
                        "commercial_keywords", "challenges"):
                val = nim_data.get(key)
                if isinstance(val, list) and val:
                    record[key] = val

            # NIM numerics — only update if regex didn't find them
            for key in ("lod", "lod_numeric", "lod_unit", "sensitivity",
                        "linear_range", "recovery_pct"):
                if key not in record or not record[key]:
                    val = nim_data.get(key)
                    if val and val != "null":
                        record[key] = val

    # Serialize arrays to JSON strings
    for arr_key in ("techniques", "sample_types", "interferents_tested",
                    "commercial_keywords", "challenges", "characterization"):
        v = record.get(arr_key)
        if isinstance(v, list):
            record[arr_key] = json.dumps(v)
        elif v is None:
            record[arr_key] = json.dumps([])

    # Set commercial potential based on keywords if not set
    if not record.get("commercial_potential"):
        kws = json.loads(record.get("commercial_keywords", "[]"))
        record["commercial_potential"] = "high" if len(kws) >= 3 else "medium" if kws else "low"

    row = {
        "paper_id": paper_id,
        "title": title,
        "authors": json.dumps(authors) if isinstance(authors, list) else (authors or "[]"),
        "year": year,
        "journal": journal,
        "url": url,
        "source_api": source_api,
        "material": record.get("material"),
        "material_formula": record.get("material_formula"),
        "electrode_type": record.get("electrode_type"),
        "techniques": record.get("techniques", "[]"),
        "analyte": record.get("analyte"),
        "lod": record.get("lod"),
        "lod_numeric": record.get("lod_numeric"),
        "lod_unit": record.get("lod_unit"),
        "sensitivity": record.get("sensitivity"),
        "linear_range": record.get("linear_range"),
        "sample_types": record.get("sample_types", "[]"),
        "recovery_pct": record.get("recovery_pct"),
        "interference_study": record.get("interference_study"),
        "interferents_tested": record.get("interferents_tested", "[]"),
        "commercial_potential": record.get("commercial_potential", "low"),
        "commercial_keywords": record.get("commercial_keywords", "[]"),
        "challenges": record.get("challenges", "[]"),
        "fabrication_method": record.get("fabrication_method"),
        "characterization": record.get("characterization", "[]"),
        "extraction_method": extraction_method,
        "nim_validated": nim_validated,
        "is_ec_sensor": 1,
        "confidence": confidence,
        "extracted_at": time.time(),
    }

    try:
        db_conn.execute("""
            INSERT OR REPLACE INTO ec_sensor_records
            (paper_id, title, authors, year, journal, url, source_api,
             material, material_formula, electrode_type, techniques, analyte,
             lod, lod_numeric, lod_unit, sensitivity, linear_range,
             sample_types, recovery_pct, interference_study, interferents_tested,
             commercial_potential, commercial_keywords, challenges,
             fabrication_method, characterization,
             extraction_method, nim_validated, is_ec_sensor, confidence, extracted_at)
            VALUES
            (:paper_id, :title, :authors, :year, :journal, :url, :source_api,
             :material, :material_formula, :electrode_type, :techniques, :analyte,
             :lod, :lod_numeric, :lod_unit, :sensitivity, :linear_range,
             :sample_types, :recovery_pct, :interference_study, :interferents_tested,
             :commercial_potential, :commercial_keywords, :challenges,
             :fabrication_method, :characterization,
             :extraction_method, :nim_validated, :is_ec_sensor, :confidence, :extracted_at)
        """, row)
        db_conn.commit()
        return row
    except Exception as e:
        logger.error("Failed to store EC record for paper %d: %s", paper_id, e)
        return None


def run_batch_extraction(
    db_path: str,
    source_filter: Optional[str] = None,
    force: bool = False,
    use_nim: bool = True,
    max_papers: int = 500,
) -> Dict[str, int]:
    """
    Run EC extraction over all papers in the DB (or filtered by source).
    Returns stats dict.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_ec_table(conn)

    where = ""
    params: List[Any] = []
    if source_filter:
        where = "WHERE source_api=?"
        params = [source_filter]

    rows = conn.execute(
        f"""SELECT id, title, authors, year, journal, url, source_api,
                   abstract, full_text
            FROM papers {where}
            ORDER BY id DESC LIMIT ?""",
        params + [max_papers],
    ).fetchall()

    stats = {"total": len(rows), "extracted": 0, "skipped": 0, "errors": 0, "nim_used": 0}

    for row in rows:
        try:
            authors = json.loads(row["authors"] or "[]")
            if isinstance(authors, str):
                authors = [authors]
            result = extract_and_store(
                paper_id=row["id"],
                title=row["title"] or "",
                authors=authors,
                year=row["year"],
                journal=row["journal"],
                url=row["url"],
                source_api=row["source_api"] or "",
                abstract=row["abstract"] or "",
                full_text=row["full_text"] or "",
                db_conn=conn,
                use_nim=use_nim,
                force=force,
            )
            if result is None:
                stats["skipped"] += 1
            else:
                stats["extracted"] += 1
                if result.get("nim_validated"):
                    stats["nim_used"] += 1
        except Exception as e:
            logger.error("EC extraction error for paper %d: %s", row["id"], e)
            stats["errors"] += 1

    conn.close()
    return stats
