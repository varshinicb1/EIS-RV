"""
Test Suite for Research Pipeline
===================================
Tests the scientific parser, deduplication, schema, and search components.

Run: python -m pytest vanl/research_pipeline/tests/test_pipeline.py -v
"""

import json
import os
import sqlite3
import tempfile
import pytest

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from vanl.research_pipeline.processors.scientific_parser import (
    ScientificExtractor, ExtractionResult,
)
from vanl.research_pipeline.dedup import (
    Deduplicator, normalize_title, title_tokens, jaccard_similarity,
)
from vanl.research_pipeline.schema import init_database
from vanl.research_pipeline.search import DatasetSearch
from vanl.research_pipeline.fetchers.base import PaperRecord


# ================================================================
#   Scientific Parser Tests
# ================================================================

class TestMaterialExtraction:
    """Test material component extraction from text."""

    def setup_method(self):
        self.extractor = ScientificExtractor()

    def test_graphene_detection(self):
        text = "We synthesized graphene nanosheets via chemical exfoliation."
        result = self.extractor.extract(text)
        names = [m["component"] for m in result.materials]
        assert "graphene" in names

    def test_mno2_detection(self):
        text = "MnO2 nanoparticles were deposited on the electrode surface."
        result = self.extractor.extract(text)
        names = [m["component"] for m in result.materials]
        assert "MnO2" in names

    def test_pedot_pss_detection(self):
        text = "A PEDOT:PSS coating was applied by spin-coating method."
        result = self.extractor.extract(text)
        names = [m["component"] for m in result.materials]
        assert "PEDOT:PSS" in names

    def test_multiple_materials(self):
        text = ("The composite electrode contained graphene nanosheets, "
                "MnO2 nanoparticles, and PEDOT:PSS as binder. "
                "Additional carbon black was used for conductivity.")
        result = self.extractor.extract(text)
        names = [m["component"] for m in result.materials]
        assert len(names) >= 3
        assert "graphene" in names
        assert "MnO2" in names

    def test_ratio_extraction(self):
        text = ("The electrode was prepared with 15 wt% polyaniline "
                "mixed with graphene oxide to form nanocomposite.")
        result = self.extractor.extract(text)
        pani = [m for m in result.materials if m["component"] == "polyaniline"]
        assert len(pani) == 1
        assert pani[0]["ratio_value"] == 15.0
        assert pani[0]["ratio_unit"] == "wt%"

    def test_cnt_variants(self):
        text = ("Single-walled carbon nanotubes (SWCNTs) and MWCNTs "
                "were dispersed in the solution.")
        result = self.extractor.extract(text)
        names = [m["component"] for m in result.materials]
        assert "SWCNT" in names
        assert "MWCNT" in names

    def test_no_false_positive_on_go(self):
        """'GO' should not match inside words like 'GOOD' or 'GOAL'."""
        text = "The good results of this goal-oriented approach were remarkable."
        result = self.extractor.extract(text)
        names = [m["component"] for m in result.materials]
        assert "graphene_oxide" not in names

    def test_confidence_increases_with_mentions(self):
        text = ("Graphene was used. Graphene exhibited excellent properties. "
                "The graphene-based electrode showed high conductivity. "
                "Graphene nanosheets provided large surface area.")
        result = self.extractor.extract(text)
        gr = [m for m in result.materials if m["component"] == "graphene"]
        assert len(gr) == 1
        assert gr[0]["confidence"] >= 0.7  # multiple mentions boost confidence


class TestSynthesisExtraction:
    """Test synthesis method and condition extraction."""

    def setup_method(self):
        self.extractor = ScientificExtractor()

    def test_hydrothermal_method(self):
        text = ("The synthesis was carried out via hydrothermal method "
                "at 180 C for 12 hours in Teflon-lined autoclave.")
        result = self.extractor.extract(text)
        methods = [s["method"] for s in result.synthesis]
        assert "hydrothermal" in methods

    def test_temperature_extraction(self):
        text = "The mixture was heated at 180 degrees Celsius for 6 hours."
        result = self.extractor.extract(text)
        assert len(result.synthesis) > 0
        temps = [s["temperature_C"] for s in result.synthesis if s.get("temperature_C")]
        assert 180.0 in temps

    def test_duration_hours(self):
        text = "The hydrothermal reaction was maintained for 12 hours."
        result = self.extractor.extract(text)
        durations = [s["duration_hours"] for s in result.synthesis if s.get("duration_hours")]
        assert 12.0 in durations

    def test_duration_minutes(self):
        text = "The electrodeposition was performed for 30 min at room temperature."
        result = self.extractor.extract(text)
        durations = [s["duration_hours"] for s in result.synthesis if s.get("duration_hours")]
        assert any(abs(d - 0.5) < 0.01 for d in durations)

    def test_ph_extraction(self):
        text = ("The solution pH was adjusted to pH = 10.5 using NaOH "
                "and maintained at that pH throughout the hydrothermal synthesis.")
        result = self.extractor.extract(text)
        phs = [s["pH"] for s in result.synthesis if s.get("pH")]
        assert 10.5 in phs

    def test_multiple_methods(self):
        text = ("The material was first prepared by sol-gel method, "
                "followed by calcination at 500 C for 2 h.")
        result = self.extractor.extract(text)
        methods = [s["method"] for s in result.synthesis]
        assert "sol_gel" in methods
        assert "calcination" in methods

    def test_screen_printing(self):
        text = "Screen-printed electrodes were fabricated on PET substrate."
        result = self.extractor.extract(text)
        methods = [s["method"] for s in result.synthesis]
        assert "screen_printing" in methods


class TestEISExtraction:
    """Test EIS parameter extraction."""

    def setup_method(self):
        self.extractor = ScientificExtractor()

    def test_rct_extraction(self):
        text = ("The Nyquist plot analysis revealed that the charge transfer "
                "resistance Rct = 150 ohm for the graphene/MnO2 composite electrode.")
        result = self.extractor.extract(text)
        assert result.eis_data.get("Rct_ohm") == 150.0

    def test_capacitance_extraction(self):
        text = "The specific capacitance of 450 F/g was achieved at 1 A/g."
        result = self.extractor.extract(text)
        assert result.eis_data.get("capacitance_F_g") == 450.0

    def test_electrolyte_extraction(self):
        text = "All measurements were performed in 1M KOH electrolyte."
        result = self.extractor.extract(text)
        assert result.eis_data.get("electrolyte") == "1M KOH"

    def test_frequency_range(self):
        text = "EIS was measured from 0.01 Hz to 100 kHz with 10 mV amplitude."
        result = self.extractor.extract(text)
        assert result.eis_data.get("freq_min_Hz") == pytest.approx(0.01, abs=0.001)
        assert result.eis_data.get("freq_max_Hz") == pytest.approx(100000.0, rel=0.01)

    def test_no_fabrication(self):
        """Ensure no EIS data is fabricated from irrelevant text."""
        text = "This paper discusses machine learning for image classification."
        result = self.extractor.extract(text)
        assert not result.eis_data


class TestApplicationClassification:
    """Test application domain classification."""

    def setup_method(self):
        self.extractor = ScientificExtractor()

    def test_supercapacitor(self):
        text = ("High-performance supercapacitor electrode with "
                "pseudocapacitive behavior and energy storage capability.")
        result = self.extractor.extract(text)
        assert result.application == "supercapacitor"

    def test_biosensor(self):
        text = ("An electrochemical biosensor for glucose detection "
                "with low detection limit of 0.1 uM.")
        result = self.extractor.extract(text)
        assert result.application == "biosensor"

    def test_battery(self):
        text = ("Lithium-ion battery anode material with improved "
                "charge-discharge cycling stability.")
        result = self.extractor.extract(text)
        assert result.application == "battery"

    def test_no_application(self):
        text = "We studied the crystal structure of this material using XRD."
        result = self.extractor.extract(text)
        # Should not confidently classify unrelated text
        # application can be None or have low confidence


class TestExtractionConfidence:
    """Test that confidence scoring behaves correctly."""

    def setup_method(self):
        self.extractor = ScientificExtractor()

    def test_confidence_range(self):
        text = ("Graphene/MnO2 composite for supercapacitor with "
                "specific capacitance of 350 F/g in 1M KOH at 180 C "
                "synthesized via hydrothermal method for 6 h.")
        result = self.extractor.extract(text)

        for mat in result.materials:
            assert 0.0 <= mat["confidence"] <= 1.0

        for syn in result.synthesis:
            assert 0.0 <= syn["confidence"] <= 1.0

    def test_extraction_log_generated(self):
        text = "Graphene electrode via hydrothermal at 180 C for supercapacitor."
        result = self.extractor.extract(text)
        assert len(result.extractions_log) > 0
        for entry in result.extractions_log:
            assert "paper_id" in entry
            assert "target_table" in entry
            assert "confidence" in entry


# ================================================================
#   Deduplication Tests
# ================================================================

class TestDeduplication:
    """Test deduplication engine."""

    def test_normalize_title(self):
        t = "  A Novel Method for Graphene Synthesis!  "
        assert normalize_title(t) == "a novel method for graphene synthesis"

    def test_jaccard_identical(self):
        s = {"graphene", "electrode", "supercapacitor"}
        assert jaccard_similarity(s, s) == 1.0

    def test_jaccard_disjoint(self):
        s1 = {"graphene", "electrode"}
        s2 = {"battery", "lithium"}
        assert jaccard_similarity(s1, s2) == 0.0

    def test_jaccard_partial(self):
        s1 = {"graphene", "electrode", "impedance"}
        s2 = {"graphene", "electrode", "capacitance"}
        sim = jaccard_similarity(s1, s2)
        assert 0.4 < sim < 0.7

    def test_dedup_by_doi(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = init_database(db_path)
            conn.execute(
                "INSERT INTO papers (title, doi) VALUES (?, ?)",
                ("Test Paper", "10.1234/test")
            )
            conn.commit()
            dedup = Deduplicator(conn)
            assert dedup.is_duplicate("Different Title", doi="10.1234/test")
            assert not dedup.is_duplicate("Different Title", doi="10.9999/other")
        finally:
            conn.close()
            os.unlink(db_path)

    def test_dedup_by_title_similarity(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = init_database(db_path)
            conn.execute(
                "INSERT INTO papers (title) VALUES (?)",
                ("High performance graphene oxide nanocomposite supercapacitor electrode material",)
            )
            conn.commit()
            dedup = Deduplicator(conn)
            # Very similar title (same words, slightly different order)
            assert dedup.is_duplicate(
                "High Performance Graphene Oxide Nanocomposite for Supercapacitor Electrode Material"
            )
            # Different title
            assert not dedup.is_duplicate(
                "Lithium-ion battery anode materials review"
            )
        finally:
            conn.close()
            os.unlink(db_path)


# ================================================================
#   Schema Tests
# ================================================================

class TestSchema:
    """Test database schema initialization."""

    def test_init_creates_tables(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = init_database(db_path)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t["name"] for t in tables]
            assert "papers" in table_names
            assert "materials" in table_names
            assert "synthesis" in table_names
            assert "eis_data" in table_names
            assert "extractions" in table_names
            assert "pipeline_runs" in table_names
            conn.close()
        finally:
            os.unlink(db_path)

    def test_insert_and_query(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = init_database(db_path)
            conn.execute(
                "INSERT INTO papers (title, doi, year) VALUES (?, ?, ?)",
                ("Test Paper", "10.1234/test", 2024),
            )
            conn.execute(
                "INSERT INTO materials (paper_id, component, confidence) "
                "VALUES (1, 'graphene', 0.85)",
            )
            conn.commit()

            row = conn.execute("SELECT * FROM papers WHERE id=1").fetchone()
            assert row["title"] == "Test Paper"
            assert row["year"] == 2024

            mat = conn.execute("SELECT * FROM materials WHERE paper_id=1").fetchone()
            assert mat["component"] == "graphene"
            assert mat["confidence"] == 0.85
            conn.close()
        finally:
            os.unlink(db_path)


# ================================================================
#   Search Interface Tests
# ================================================================

class TestSearch:
    """Test the search/filter interface."""

    def setup_method(self):
        self.db_path = tempfile.mktemp(suffix=".db")
        self.conn = init_database(self.db_path)
        # Insert test data
        self.conn.execute(
            "INSERT INTO papers (title, doi, year, application) "
            "VALUES (?, ?, ?, ?)",
            ("Graphene MnO2 Supercapacitor", "10.1234/a", 2023, "supercapacitor"),
        )
        self.conn.execute(
            "INSERT INTO papers (title, doi, year, application) "
            "VALUES (?, ?, ?, ?)",
            ("NiO Biosensor Impedance", "10.1234/b", 2024, "biosensor"),
        )
        self.conn.execute(
            "INSERT INTO materials (paper_id, component, confidence) "
            "VALUES (1, 'graphene', 0.9)",
        )
        self.conn.execute(
            "INSERT INTO materials (paper_id, component, confidence) "
            "VALUES (1, 'MnO2', 0.8)",
        )
        self.conn.execute(
            "INSERT INTO materials (paper_id, component, confidence) "
            "VALUES (2, 'NiO', 0.85)",
        )
        self.conn.execute(
            "INSERT INTO eis_data (paper_id, Rct_ohm, capacitance_F_g, confidence) "
            "VALUES (1, 150.0, 450.0, 0.85)",
        )
        self.conn.execute(
            "INSERT INTO synthesis (paper_id, method, temperature_C, confidence) "
            "VALUES (1, 'hydrothermal', 180.0, 0.8)",
        )
        self.conn.commit()

    def teardown_method(self):
        self.conn.close()
        os.unlink(self.db_path)

    def test_search_by_material(self):
        search = DatasetSearch(self.conn)
        results = search.search(material="graphene")
        assert len(results) >= 1
        assert results[0]["title"] == "Graphene MnO2 Supercapacitor"

    def test_search_by_application(self):
        search = DatasetSearch(self.conn)
        results = search.search(application="biosensor")
        assert len(results) == 1
        assert "Biosensor" in results[0]["title"]

    def test_search_by_min_capacitance(self):
        search = DatasetSearch(self.conn)
        results = search.search(min_capacitance=400.0)
        assert len(results) >= 1

    def test_list_materials(self):
        search = DatasetSearch(self.conn)
        mats = search.list_materials()
        names = [m["component"] for m in mats]
        assert "graphene" in names
        assert "MnO2" in names
        assert "NiO" in names

    def test_list_methods(self):
        search = DatasetSearch(self.conn)
        methods = search.list_methods()
        assert any(m["method"] == "hydrothermal" for m in methods)

    def test_get_paper_detail(self):
        search = DatasetSearch(self.conn)
        paper = search.get_paper_detail(1)
        assert paper is not None
        assert len(paper["materials"]) == 2
        assert len(paper["eis_data"]) == 1


# ================================================================
#   PaperRecord Tests
# ================================================================

class TestPaperRecord:
    """Test PaperRecord dataclass."""

    def test_to_dict(self):
        p = PaperRecord(
            title="Test Paper",
            authors=["Author A", "Author B"],
            doi="10.1234/test",
            year=2024,
            source_api="arxiv",
        )
        d = p.to_dict()
        assert d["title"] == "Test Paper"
        assert len(d["authors"]) == 2
        assert d["doi"] == "10.1234/test"

    def test_defaults(self):
        p = PaperRecord(title="Minimal")
        assert p.authors == []
        assert p.doi is None
        assert p.source_api == ""
