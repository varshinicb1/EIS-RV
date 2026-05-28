"""
Tests for Cross-Modal Identifier, Biosensor Suggestor, and NVIDIA Integration
==============================================================================
Validates all Phase 2-4 implementations.

Author: VidyuthLabs
Date: May 8, 2026
"""
import sys
import os
import pytest
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend"))


class TestCrossModalIdentifier:
    """Test the cross-modal material identification engine."""

    def setup_method(self):
        from ml.models.cross_modal_identifier import CrossModalIdentifier
        self.identifier = CrossModalIdentifier()

    def test_cv_graphene_identification(self):
        """CV with ΔEp=65mV, ipa/ipc≈1 → should match graphene."""
        results = self.identifier.identify_from_cv(
            peak_separation_mV=65, ipa_ipc_ratio=0.99
        )
        assert len(results) > 0
        names = [r.material_name for r in results]
        assert "graphene" in names or "Ti3C2Tx" in names or "PEDOT:PSS" in names

    def test_cv_mno2_identification(self):
        """CV with high ΔEp → should match metal oxides."""
        results = self.identifier.identify_from_cv(peak_separation_mV=200)
        assert len(results) > 0

    def test_eis_low_rct(self):
        """EIS with low Rct → should match conductive materials."""
        results = self.identifier.identify_from_eis(rct_ohm=15, cdl_uF=400)
        assert len(results) > 0
        # Low Rct should match graphene, MXene, or PEDOT:PSS
        categories = [r.category for r in results]
        assert any(c in categories for c in ["carbon", "MXene", "conducting_polymer", "spinel_oxide"])

    def test_eis_high_rct(self):
        """EIS with high Rct → should match resistive materials."""
        results = self.identifier.identify_from_eis(rct_ohm=1000)
        assert len(results) > 0

    def test_gcd_high_capacitance(self):
        """GCD with very high capacitance → should match NiCo2O4 or similar."""
        results = self.identifier.identify_from_gcd(
            specific_capacitance_Fg=1500, coulombic_efficiency_pct=95
        )
        assert len(results) > 0

    def test_raman_graphene_peaks(self):
        """Raman peaks at 1350, 1580, 2700 → graphene family."""
        results = self.identifier.identify_from_raman([1350, 1580, 2700])
        assert len(results) > 0
        names = [r.material_name for r in results]
        assert "graphene" in names or "rGO" in names

    def test_raman_mos2_peaks(self):
        """Raman peaks at 383, 408 → MoS2."""
        results = self.identifier.identify_from_raman([383, 408])
        assert len(results) > 0
        names = [r.material_name for r in results]
        assert "MoS2" in names

    def test_raman_prussian_blue(self):
        """Raman peaks at 2102, 2154 → Prussian blue."""
        results = self.identifier.identify_from_raman([275, 2102, 2154])
        assert len(results) > 0
        names = [r.material_name for r in results]
        assert "Prussian_blue" in names

    def test_multimodal_fusion(self):
        """Cross-modal fusion should boost confidence."""
        from ml.models.cross_modal_identifier import ElectrochemicalFingerprint

        fp_cv = ElectrochemicalFingerprint(
            modality="CV", peak_separation_mV=65, ipa_ipc_ratio=0.99
        )
        fp_raman = ElectrochemicalFingerprint(
            modality="Raman", raman_peaks_cm=[1350, 1580, 2700]
        )

        results = self.identifier.identify_multimodal([fp_cv, fp_raman])
        assert len(results) > 0
        # Multimodal should have higher confidence
        assert results[0].confidence > 0.5

    def test_empty_input(self):
        """Should handle empty/missing inputs gracefully."""
        results = self.identifier.identify_from_cv()
        # No features → no strong matches, but shouldn't crash
        assert isinstance(results, list)


class TestBiosensorSuggestor:
    """Test the biosensor material suggestor."""

    def setup_method(self):
        from ml.models.biosensor_suggestor import BiosensorSuggestor
        self.suggestor = BiosensorSuggestor()

    def test_pb2_detection(self):
        """Should return Bi/rGO for lead detection."""
        results = self.suggestor.suggest("Pb2+", use_nvidia=False)
        assert len(results) > 0
        assert results[0].confidence >= 0.85
        assert "Bi" in results[0].material_name or "Au" in results[0].material_name

    def test_glucose_detection(self):
        """Should return GOx or NiCo2O4 for glucose."""
        results = self.suggestor.suggest("glucose", use_nvidia=False)
        assert len(results) > 0
        categories = [r.category for r in results]
        assert any("enzymatic" in c or "non_enzymatic" in c for c in categories)

    def test_dopamine_detection(self):
        """Should return MoS2/rGO for dopamine."""
        results = self.suggestor.suggest("dopamine", use_nvidia=False)
        assert len(results) > 0

    def test_cortisol_detection(self):
        """Should return immunosensor for cortisol."""
        results = self.suggestor.suggest("cortisol", use_nvidia=False)
        assert len(results) > 0
        assert results[0].category == "immunosensor"

    def test_alias_normalization(self):
        """'lead' should resolve to Pb2+."""
        results_alias = self.suggestor.suggest("lead", use_nvidia=False)
        results_direct = self.suggestor.suggest("Pb2+", use_nvidia=False)
        assert len(results_alias) == len(results_direct)

    def test_supported_analytes(self):
        """Should list all supported analytes."""
        analytes = self.suggestor.get_supported_analytes()
        assert len(analytes) >= 8
        assert "Pb2+" in analytes
        assert "glucose" in analytes

    def test_analyte_info(self):
        """Should return detailed info for known analytes."""
        info = self.suggestor.get_analyte_info("Pb2+")
        assert info is not None
        assert "num_coatings" in info
        assert info["num_coatings"] >= 1

    def test_unknown_analyte_no_nvidia(self):
        """Unknown analyte without NVIDIA should return empty."""
        results = self.suggestor.suggest("unobtanium", use_nvidia=False)
        assert len(results) == 0

    def test_preparation_steps_included(self):
        """Recommendations should include preparation steps."""
        results = self.suggestor.suggest("Pb2+", use_nvidia=False)
        assert len(results) > 0
        assert len(results[0].preparation_steps) > 0


class TestNvidiaIntegration:
    """Test NVIDIA integration (fallback mode — no API key needed)."""

    def test_discover_materials_fallback(self):
        """Should return fallback candidates without API key."""
        from research.nvidia_integration import discover_materials
        # Unset API key to force fallback
        old_key = os.environ.pop("NVIDIA_API_KEY", None)
        try:
            candidates = discover_materials("Pb2+ detection biosensor")
            assert len(candidates) > 0
            assert candidates[0].confidence > 0
        finally:
            if old_key:
                os.environ["NVIDIA_API_KEY"] = old_key

    def test_suggest_synthesis_fallback(self):
        """Should return fallback synthesis routes."""
        from research.nvidia_integration import suggest_synthesis
        old_key = os.environ.pop("NVIDIA_API_KEY", None)
        try:
            routes = suggest_synthesis("MoS2", "MoS2", "nanosheets")
            assert len(routes) > 0
            assert len(routes[0].steps) > 0
        finally:
            if old_key:
                os.environ["NVIDIA_API_KEY"] = old_key

    def test_recommend_we_coating_fallback(self):
        """Should return fallback coating recommendation."""
        from research.nvidia_integration import recommend_we_coating
        old_key = os.environ.pop("NVIDIA_API_KEY", None)
        try:
            result = recommend_we_coating("Pb2+", "SPE carbon", "CV")
            assert "primary_coating" in result
            assert "rationale" in result
        finally:
            if old_key:
                os.environ["NVIDIA_API_KEY"] = old_key

    def test_material_candidate_serialization(self):
        """MaterialCandidate should serialize to dict."""
        from research.nvidia_integration import MaterialCandidate
        mc = MaterialCandidate(
            name="Test", formula="T", category="test",
            confidence=0.9, rationale="test"
        )
        d = mc.to_dict()
        assert d["name"] == "Test"
        assert d["confidence"] == 0.9


class TestScientificParserExpansion:
    """Test that the expanded material dictionary works correctly."""

    def test_mxene_detection(self):
        """Should detect MXene materials."""
        import re
        from research.processors.scientific_parser import KNOWN_MATERIALS
        test_text = "We synthesized Ti3C2Tx MXene nanosheets"
        found = []
        for pattern, name in KNOWN_MATERIALS.items():
            if re.search(pattern, test_text, re.IGNORECASE):
                found.append(name)
        assert "Ti3C2Tx" in found or "MXene" in found

    def test_mof_detection(self):
        """Should detect MOF materials."""
        import re
        from research.processors.scientific_parser import KNOWN_MATERIALS
        test_text = "ZIF-67 was used as a precursor for carbon electrode"
        found = []
        for pattern, name in KNOWN_MATERIALS.items():
            if re.search(pattern, test_text, re.IGNORECASE):
                found.append(name)
        assert "ZIF-67" in found

    def test_perovskite_detection(self):
        """Should detect perovskite materials."""
        import re
        from research.processors.scientific_parser import KNOWN_MATERIALS
        test_text = "BaTiO3 perovskite nanoparticles were prepared"
        found = []
        for pattern, name in KNOWN_MATERIALS.items():
            if re.search(pattern, test_text, re.IGNORECASE):
                found.append(name)
        assert "BaTiO3" in found or "perovskite" in found

    def test_biosensor_keywords(self):
        """Should detect biosensor application keywords."""
        from research.processors.scientific_parser import APPLICATION_KEYWORDS
        assert "biosensor" in APPLICATION_KEYWORDS
        assert "LOD" in APPLICATION_KEYWORDS["biosensor"]
        assert "aptasensor" in APPLICATION_KEYWORDS["biosensor"]

    def test_heavy_metal_keywords(self):
        """Should detect heavy metal detection keywords."""
        from research.processors.scientific_parser import APPLICATION_KEYWORDS
        assert "heavy_metal_detection" in APPLICATION_KEYWORDS
        assert "Pb(II)" in APPLICATION_KEYWORDS["heavy_metal_detection"]

    def test_expanded_material_count(self):
        """Should have significantly more materials than before."""
        from research.processors.scientific_parser import KNOWN_MATERIALS
        # We expanded from ~30 to 120+
        assert len(KNOWN_MATERIALS) >= 80

    def test_expanded_application_count(self):
        """Should have more application domains."""
        from research.processors.scientific_parser import APPLICATION_KEYWORDS
        assert len(APPLICATION_KEYWORDS) >= 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
