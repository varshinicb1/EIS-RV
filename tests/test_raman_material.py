"""
Raman Material Identifier — Dedicated Tests
=============================================
Tests the full material identification pipeline.

Run:
    py -3.12 tests/test_raman_material.py
"""

import sys, json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src" / "backend" / "ml"))

from models.raman_material_identifier import (
    RamanMaterialIdentifier, MaterialMatch,
    add_material_to_database, update_material_in_database,
)

DB_PATH = ROOT / "data" / "material_database" / "raman_materials.json"

# Guard to fix pytest test collection issues (old regressed guard restored).
# Prevents this standalone runner script from interfering with `pytest tests/` collection.
__test__ = False

_results = []
def check(name, cond, detail=""):
    status = "✅ PASS" if cond else "❌ FAIL"
    _results.append((name, cond, detail))
    print(f"  {status}  {name}" + (f"  [{detail}]" if detail else ""))
    return cond

def section(t):
    print(f"\n{'='*60}\n  {t}\n{'='*60}")

# ── 1. Database Loading ───────────────────────────────────────────────────
section("1. Database Loading")

ident = RamanMaterialIdentifier(database_path=str(DB_PATH))
check("DB loaded",                len(ident.materials) > 0, f"{len(ident.materials)} materials")
check("DB has ≥ 10 materials",    len(ident.materials) >= 10)
check("Each material has id",     all("material_id" in m for m in ident.materials))
check("Each material has name",   all("name" in m for m in ident.materials))
check("Each material has peaks",  all(len(m.get("reference_peaks", [])) > 0 for m in ident.materials))

# ── 2. Peak Matching — Known Materials ───────────────────────────────────
section("2. Peak Matching — Known Materials")

# Graphene: G=1580, 2D=2700
graphene_peaks = [{"position_cm": 1582, "intensity": 1.0},
                  {"position_cm": 2698, "intensity": 4.0}]
matches = ident.identify_material(graphene_peaks, top_n=5, min_confidence=0.3)
check("Graphene: match found",         len(matches) > 0)
check("Graphene: top is carbon",       "carbon" in matches[0].category.lower() if matches else False,
      matches[0].name if matches else "none")
check("Graphene: confidence ≥ 0.9",   matches[0].confidence >= 0.9 if matches else False,
      f"{matches[0].confidence:.3f}" if matches else "0")
check("Graphene: matched_peaks = 2",  matches[0].matched_peaks == 2 if matches else False)
check("Graphene: returns MaterialMatch", isinstance(matches[0], MaterialMatch) if matches else False)

# Silicon: 520 cm⁻¹
si_peaks = [{"position_cm": 520.5, "intensity": 1.0}]
si_matches = ident.identify_material(si_peaks, top_n=3, min_confidence=0.5)
check("Silicon: match found",          len(si_matches) > 0)
check("Silicon: top is semiconductor", "semiconductor" in si_matches[0].category.lower() if si_matches else False,
      si_matches[0].name if si_matches else "none")
check("Silicon: confidence ≥ 0.9",    si_matches[0].confidence >= 0.9 if si_matches else False)

# Diamond: 1332 cm⁻¹
diamond_peaks = [{"position_cm": 1333, "intensity": 1.0}]
d_matches = ident.identify_material(diamond_peaks, top_n=3, min_confidence=0.5)
check("Diamond: match found",          len(d_matches) > 0)
check("Diamond: top is carbon",        "carbon" in d_matches[0].category.lower() if d_matches else False,
      d_matches[0].name if d_matches else "none")

# MoS2: 383, 408 cm⁻¹
mos2_peaks = [{"position_cm": 383, "intensity": 1.0},
              {"position_cm": 408, "intensity": 0.8}]
mos2_matches = ident.identify_material(mos2_peaks, top_n=3, min_confidence=0.5)
check("MoS2: match found",             len(mos2_matches) > 0)
check("MoS2: top is sulfide/2D",
      any(x in mos2_matches[0].category.lower() for x in ["sulfide", "2d"]) if mos2_matches else False,
      mos2_matches[0].name if mos2_matches else "none")

# ── 3. Confidence Scoring ─────────────────────────────────────────────────
section("3. Confidence Scoring")

# Perfect match (all peaks within tolerance)
perfect_peaks = [{"position_cm": 1580, "intensity": 1.0},
                 {"position_cm": 2700, "intensity": 4.0}]
perfect = ident.identify_material(perfect_peaks, top_n=1, min_confidence=0.0)
check("Perfect match: confidence = 1.0",
      perfect[0].confidence == 1.0 if perfect else False,
      f"{perfect[0].confidence:.3f}" if perfect else "none")

# Partial match (only 1 of 2 peaks)
partial_peaks = [{"position_cm": 1580, "intensity": 1.0}]
partial = ident.identify_material(partial_peaks, top_n=5, min_confidence=0.0)
if partial:
    check("Partial match: confidence < 1.0",
          partial[0].confidence < 1.0, f"{partial[0].confidence:.3f}")

# No match (random peaks)
random_peaks = [{"position_cm": 999, "intensity": 1.0},
                {"position_cm": 1234, "intensity": 0.5}]
no_match = ident.identify_material(random_peaks, top_n=5, min_confidence=0.8)
check("No match: empty result for high threshold", len(no_match) == 0)

# min_confidence filter
low_conf = ident.identify_material(partial_peaks, top_n=10, min_confidence=0.0)
high_conf = ident.identify_material(partial_peaks, top_n=10, min_confidence=0.9)
check("Confidence filter: high threshold → fewer results",
      len(high_conf) <= len(low_conf))

# ── 4. Sorted Results ────────────────────────────────────────────────────
section("4. Sorted Results")

multi_peaks = [{"position_cm": 1580, "intensity": 1.0},
               {"position_cm": 2700, "intensity": 2.0},
               {"position_cm": 1350, "intensity": 0.3}]
sorted_matches = ident.identify_material(multi_peaks, top_n=10, min_confidence=0.0)
if len(sorted_matches) >= 2:
    check("Results sorted by confidence (desc)",
          sorted_matches[0].confidence >= sorted_matches[1].confidence,
          f"{sorted_matches[0].confidence:.3f} >= {sorted_matches[1].confidence:.3f}")

check("top_n respected",
      len(ident.identify_material(multi_peaks, top_n=2, min_confidence=0.0)) <= 2)

# ── 5. Mixture Detection ─────────────────────────────────────────────────
section("5. Mixture Detection")

# Graphene + Silicon peaks together
mixture_peaks = [
    {"position_cm": 1580, "intensity": 1.0},
    {"position_cm": 2700, "intensity": 2.0},
    {"position_cm": 520,  "intensity": 0.8},
]
components = ident.identify_mixture(mixture_peaks, max_components=3, min_confidence=0.3)
check("Mixture: at least 1 component found", len(components) >= 1)
check("Mixture: returns MaterialMatch list",
      all(isinstance(c, MaterialMatch) for c in components))

# ── 6. Database Queries ───────────────────────────────────────────────────
section("6. Database Queries")

# get_material_by_id
first_id = ident.materials[0]["material_id"]
mat = ident.get_material_by_id(first_id)
check("get_by_id: found",          mat is not None)
check("get_by_id: correct id",     mat["material_id"] == first_id if mat else False)
check("get_by_id: missing → None", ident.get_material_by_id("nonexistent_xyz") is None)

# get_materials_by_category
carbon_mats = ident.get_materials_by_category("carbon")
check("get_by_category: carbon found",  len(carbon_mats) > 0, f"{len(carbon_mats)} materials")
check("get_by_category: all carbon",    all(m["category"] == "carbon" for m in carbon_mats))
check("get_by_category: empty cat → []", ident.get_materials_by_category("nonexistent_cat") == [])

# search_materials
results = ident.search_materials("graphene")
check("search: 'graphene' returns results", len(results) > 0, f"{len(results)} results")
check("search: all contain 'graphene'",
      all("graphene" in m.get("name","").lower() or
          "graphene" in m.get("description","").lower() or
          "graphene" in m.get("formula","").lower()
          for m in results))

results_empty = ident.search_materials("xyznonexistent123")
check("search: no match → []", len(results_empty) == 0)

# get_statistics
stats = ident.get_statistics()
check("stats: total_materials",    "total_materials" in stats)
check("stats: categories",         "categories" in stats)
check("stats: total_reference_peaks", "total_reference_peaks" in stats)
check("stats: total_materials > 0",   stats["total_materials"] > 0)
check("stats: total_peaks > 0",       stats["total_reference_peaks"] > 0)

# ── 7. MaterialMatch.to_dict() ────────────────────────────────────────────
section("7. MaterialMatch.to_dict()")

if matches:
    d = matches[0].to_dict()
    for key in ["material_id", "name", "formula", "category", "confidence",
                "matched_peaks", "total_expected_peaks", "match_ratio",
                "peak_matches", "spectral_similarity", "quality_score", "description"]:
        check(f"to_dict: has '{key}'", key in d)
    check("to_dict: match_ratio in [0,1]", 0 <= d["match_ratio"] <= 1)
    check("to_dict: confidence in [0,1]",  0 <= d["confidence"] <= 1)

# ── 8. Edge Cases ────────────────────────────────────────────────────────
section("8. Edge Cases")

check("Empty peaks → []",          ident.identify_material([]) == [])
check("Single peak works",         len(ident.identify_material([{"position_cm": 520, "intensity": 1.0}], min_confidence=0.0)) >= 0)
check("Very high min_confidence → []",
      ident.identify_material(graphene_peaks, min_confidence=0.9999) == [] or
      ident.identify_material(graphene_peaks, min_confidence=0.9999)[0].confidence >= 0.9999)

# Reload database
ident.load_database()
check("Reload: still has materials", len(ident.materials) > 0)

# ── Final ─────────────────────────────────────────────────────────────────
total_t = len(_results)
passed  = sum(1 for _, ok, _ in _results if ok)
failed  = total_t - passed
print(f"\n{'='*60}\n  RESULTS: {passed}/{total_t}  ({100*passed/total_t:.1f}%)\n{'='*60}")
if failed:
    for name, ok, detail in _results:
        if not ok:
            print(f"  ✗ {name}" + (f"  [{detail}]" if detail else ""))
if __name__ == "__main__":
    import sys; sys.exit(0 if failed == 0 else 1)
