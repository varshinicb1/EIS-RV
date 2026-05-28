"""
Sprint 3 Tests: Real Lab Data Integration
============================================
Tests the CHI608E parser, auto-material detection, Nyquist fitting,
Raman auto-ID, and DPV calibration on REAL lab data files.

Author: VidyuthLabs
Date: May 8, 2026
"""
import sys
import os
import pytest
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend"))

LAB_DIR = Path(__file__).parent.parent / "Lab data"
FOG_DIR = LAB_DIR / "fog differet data" / "fog differet data"


class TestCHIParser:
    """Test CHI608E file parsing on real lab data."""

    def setup_method(self):
        from src.backend.core.chi_parser import CHIParser
        self.parser = CHIParser()

    @pytest.mark.skipif(not (LAB_DIR / "FO.txt").exists(), reason="FO.txt not found")
    def test_parse_raman_txt(self):
        """Parse FO.txt Raman spectroscopy data."""
        ds = self.parser.parse(str(LAB_DIR / "FO.txt"))
        assert ds.metadata.technique == "Raman"
        assert ds.num_points > 2000
        assert len(ds.columns) == 2
        assert ds.get_column("Wave") is not None

    @pytest.mark.skipif(not (FOG_DIR / "EIS FOG.xlsx").exists(), reason="EIS FOG.xlsx not found")
    def test_parse_eis_xlsx(self):
        """Parse CHI608E EIS .xlsx export."""
        ds = self.parser.parse(str(FOG_DIR / "EIS FOG.xlsx"))
        assert ds.metadata.technique == "EIS"
        assert ds.metadata.instrument_model == "CHI608E"
        assert ds.num_points > 50
        assert ds.get_column("Z_real") is not None
        assert ds.get_column("Z_imag") is not None
        assert ds.get_column("freq") is not None

    @pytest.mark.skipif(not (FOG_DIR / "EIS BARE GCE.xlsx").exists(), reason="missing")
    def test_parse_eis_metadata(self):
        """Metadata extraction from EIS file."""
        ds = self.parser.parse(str(FOG_DIR / "EIS BARE GCE.xlsx"))
        assert ds.metadata.high_freq_hz == 1e5
        assert ds.metadata.low_freq_hz == 1
        assert ds.metadata.amplitude_v == 0.005
        assert "Apr" in ds.metadata.date or "Feb" in ds.metadata.date

    def test_dataset_to_dict(self):
        """Serialization should work."""
        if not (FOG_DIR / "EIS FOG.xlsx").exists():
            pytest.skip("EIS FOG.xlsx not found")
        ds = self.parser.parse(str(FOG_DIR / "EIS FOG.xlsx"))
        d = ds.to_dict()
        assert "metadata" in d
        assert d["metadata"]["technique"] == "EIS"
        assert d["num_points"] > 0


class TestRealEISAnalysis:
    """Test EIS analysis on actual Nyquist data."""

    def setup_method(self):
        from src.backend.core.chi_parser import get_analyzer
        self.analyzer = get_analyzer()

    @pytest.mark.skipif(not (FOG_DIR / "EIS FOG.xlsx").exists(), reason="missing")
    def test_fog_has_lowest_rct(self):
        """FOG nanocomposite should have the lowest Rct of all electrodes."""
        results = {}
        for name, fname in [
            ("bare", "EIS BARE GCE.xlsx"),
            ("Fe2O3", "EIS FERRIC OXIDE.xlsx"),
            ("rGO", "EIS rGO.xlsx"),
            ("FOG", "EIS FOG.xlsx"),
        ]:
            fpath = FOG_DIR / fname
            if fpath.exists():
                r = self.analyzer.auto_analyze(str(fpath))
                results[name] = r["eis_analysis"]["Rct_ohm"]

        assert "FOG" in results
        assert "bare" in results
        # FOG should have lowest Rct
        assert results["FOG"] < results["bare"], \
            f"FOG Rct ({results['FOG']}) should be < bare ({results['bare']})"
        # FOG should be < all others
        for name, rct in results.items():
            if name != "FOG":
                assert results["FOG"] <= rct, \
                    f"FOG Rct ({results['FOG']}) should be <= {name} ({rct})"

    @pytest.mark.skipif(not (FOG_DIR / "EIS FOG.xlsx").exists(), reason="missing")
    def test_fog_rs_extraction(self):
        """FOG should have Rs around 3-5 ohm."""
        r = self.analyzer.auto_analyze(str(FOG_DIR / "EIS FOG.xlsx"))
        rs = r["eis_analysis"]["Rs_ohm"]
        assert 1 < rs < 10, f"FOG Rs should be 1-10 ohm, got {rs}"

    @pytest.mark.skipif(not (FOG_DIR / "EIS BARE GCE.xlsx").exists(), reason="missing")
    def test_bare_gce_high_rct(self):
        """Bare GCE should have very high Rct (unmodified electrode)."""
        r = self.analyzer.auto_analyze(str(FOG_DIR / "EIS BARE GCE.xlsx"))
        rct = r["eis_analysis"]["Rct_ohm"]
        assert rct > 1000, f"Bare GCE Rct should be > 1000, got {rct}"

    @pytest.mark.skipif(not (FOG_DIR / "EIS FOG.xlsx").exists(), reason="missing")
    def test_nyquist_data_returned(self):
        """Analysis should return raw Nyquist coordinates for plotting."""
        r = self.analyzer.auto_analyze(str(FOG_DIR / "EIS FOG.xlsx"))
        nyq = r["eis_analysis"]["nyquist_data"]
        assert len(nyq["z_real"]) > 50
        assert len(nyq["z_imag_neg"]) == len(nyq["z_real"])


class TestRealRamanAnalysis:
    """Test Raman analysis on real FO.txt spectrum."""

    def setup_method(self):
        from src.backend.core.chi_parser import get_analyzer
        self.analyzer = get_analyzer()

    @pytest.mark.skipif(not (LAB_DIR / "FO.txt").exists(), reason="FO.txt not found")
    def test_detects_fe2o3(self):
        """Should detect Fe2O3 (hematite) from Eg modes."""
        r = self.analyzer.auto_analyze(str(LAB_DIR / "FO.txt"))
        materials = r["raman_analysis"]["materials_detected"]
        assert "Fe2O3 (hematite)" in materials

    @pytest.mark.skipif(not (LAB_DIR / "FO.txt").exists(), reason="FO.txt not found")
    def test_detects_rgo(self):
        """Should detect rGO from D-band."""
        r = self.analyzer.auto_analyze(str(LAB_DIR / "FO.txt"))
        materials = r["raman_analysis"]["materials_detected"]
        assert "rGO (reduced graphene oxide)" in materials

    @pytest.mark.skipif(not (LAB_DIR / "FO.txt").exists(), reason="FO.txt not found")
    def test_band_assignments(self):
        """Should assign D-band and Fe2O3 Eg correctly."""
        r = self.analyzer.auto_analyze(str(LAB_DIR / "FO.txt"))
        assignments = r["raman_analysis"]["band_assignments"]
        assignment_labels = [a["assignment"] for a in assignments]
        assert any("D-band" in a for a in assignment_labels)
        assert any("Fe2O3" in a for a in assignment_labels)

    @pytest.mark.skipif(not (LAB_DIR / "FO.txt").exists(), reason="FO.txt not found")
    def test_peak_positions(self):
        """Key peaks should be in expected ranges."""
        r = self.analyzer.auto_analyze(str(LAB_DIR / "FO.txt"))
        peaks_wn = [p["wavenumber"] for p in r["raman_analysis"]["peaks"]]
        # Should have peaks around 290, 408, 1325 cm-1
        has_fe2o3_low = any(280 < wn < 310 for wn in peaks_wn)
        has_d_band = any(1300 < wn < 1400 for wn in peaks_wn)
        assert has_fe2o3_low, f"Expected Fe2O3 peak near 290 cm-1, peaks: {peaks_wn}"
        assert has_d_band, f"Expected D-band near 1325 cm-1, peaks: {peaks_wn}"


class TestCrossModalFusion:
    """Test that multiple modalities identify the SAME material."""

    @pytest.mark.skipif(
        not ((LAB_DIR / "FO.txt").exists() and (FOG_DIR / "EIS FOG.xlsx").exists()),
        reason="missing files"
    )
    def test_raman_and_eis_agree_on_material(self):
        """Both Raman and EIS should point to Fe2O3/rGO composite."""
        from src.backend.core.chi_parser import get_analyzer
        analyzer = get_analyzer()

        # Raman identifies Fe2O3 + rGO
        raman = analyzer.auto_analyze(str(LAB_DIR / "FO.txt"))
        raman_materials = set(raman["raman_analysis"]["materials_detected"])

        # EIS shows low Rct (composite with good conductivity)
        eis = analyzer.auto_analyze(str(FOG_DIR / "EIS FOG.xlsx"))
        rct = eis["eis_analysis"]["Rct_ohm"]

        # Both should confirm: it's a carbon-metal oxide composite
        assert "Fe2O3 (hematite)" in raman_materials
        assert "rGO (reduced graphene oxide)" in raman_materials
        # Low Rct confirms rGO contribution (good conductivity)
        assert rct < 500, f"FOG Rct ({rct}) should be < 500 for rGO-enhanced composite"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
