"""
Tests for Sprint 2: Training Runner, Semantic Extractor, API Endpoints
=======================================================================
Validates all new implementations from the "implement everything" sprint.

Author: VidyuthLabs
Date: May 8, 2026
"""
import sys
import os
import json
import pytest
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend"))


class TestSemanticExtractor:
    """Test the hybrid regex+NLP semantic extractor."""

    def setup_method(self):
        from research.processors.semantic_extractor import SemanticExtractor
        self.extractor = SemanticExtractor(use_nlp=False)

    def test_extract_materials_from_abstract(self):
        """Should extract materials from a real abstract."""
        text = """
        We report a novel MoS2/rGO/AuNP nanocomposite electrode for the
        electrochemical detection of dopamine.
        """
        result = self.extractor.extract(text)
        material_names = [m.normalized for m in result.materials]
        assert any("MoS2" in m or "rGO" in m or "graphene" in m for m in material_names), \
            f"Expected MoS2/rGO in materials, got: {material_names}"

    def test_extract_synthesis_methods(self):
        """Should extract synthesis methods."""
        text = """
        The composite was synthesized via hydrothermal method at 200°C
        for 24h, followed by electrodeposition of AuNPs.
        """
        result = self.extractor.extract(text)
        method_names = [m.normalized for m in result.methods]
        assert "hydrothermal" in method_names
        assert "electrodeposition" in method_names

    def test_extract_electrochemical_parameters(self):
        """Should extract Rct, LOD, sensitivity, etc."""
        text = """
        Electrochemical impedance spectroscopy revealed a charge transfer
        resistance (Rct) of 45 Ω. The biosensor exhibited a limit of
        detection (LOD) of 0.05 μM and sensitivity of 420 μA/mM/cm².
        """
        result = self.extractor.extract(text)
        param_names = [p.normalized for p in result.parameters]
        assert "Rct" in param_names
        assert "LOD" in param_names
        assert "sensitivity" in param_names

    def test_extract_applications(self):
        """Should classify applications."""
        text = """
        This biosensor showed excellent selectivity for dopamine detection
        in the presence of ascorbic acid and uric acid interferents.
        """
        result = self.extractor.extract(text)
        app_names = [a.normalized for a in result.applications]
        assert len(app_names) > 0

    def test_extract_from_capacitance_paper(self):
        """Should extract supercapacitor parameters."""
        text = """
        The NiCo2O4 nanowires on carbon cloth exhibited a specific
        capacitance of 1850 F/g at 1 A/g current density. The electrode
        was synthesized by hydrothermal method at 120°C for 6h.
        """
        result = self.extractor.extract(text)
        param_names = [p.normalized for p in result.parameters]
        assert "specific_capacitance" in param_names

    def test_empty_text(self):
        """Should handle empty text gracefully."""
        result = self.extractor.extract("")
        assert result.total_entities == 0

    def test_deduplication(self):
        """Should not return duplicate materials."""
        text = "We used rGO and rGO modified with AuNP, the rGO was prepared by Hummers method."
        result = self.extractor.extract(text)
        normalized = [m.normalized for m in result.materials]
        # rGO should appear only once
        rgo_count = normalized.count("reduced_graphene_oxide")
        assert rgo_count <= 1, f"rGO should be deduplicated, got {rgo_count}"

    def test_confidence_scores(self):
        """All extracted entities should have valid confidence scores."""
        text = "MnO2 electrode with Rct of 150 ohm prepared by sol-gel method for supercapacitor."
        result = self.extractor.extract(text)
        for entity_list in [result.materials, result.methods, result.parameters]:
            for entity in entity_list:
                assert 0 <= entity.confidence <= 1.0, \
                    f"Invalid confidence {entity.confidence} for {entity.value}"

    def test_result_serialization(self):
        """SemanticExtractionResult should serialize to dict."""
        text = "PEDOT:PSS electrode with Rct = 25 Ω via spin coating."
        result = self.extractor.extract(text)
        d = result.to_dict()
        assert "materials" in d
        assert "methods" in d
        assert "parameters" in d
        assert isinstance(d["materials"], list)

    def test_complex_multi_material_abstract(self):
        """Should extract multiple materials from a complex abstract."""
        text = """
        A ternary nanocomposite of Ti3C2Tx MXene, ZIF-67 derived carbon,
        and PEDOT:PSS was prepared via electrodeposition on a glassy
        carbon electrode. The electrode was tested for dopamine detection
        using differential pulse voltammetry. The charge transfer
        resistance Rct was 12 Ω, with LOD of 0.02 μM.
        """
        result = self.extractor.extract(text)
        assert len(result.materials) >= 2
        assert len(result.parameters) >= 1
        assert result.total_entities >= 4


class TestPhysicsTrainingRunner:
    """Test the physics-informed training runner components."""

    def test_synthetic_sample_generation(self):
        """Should generate valid synthetic CV samples."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend" / "ml"))
        from training.run_physics_training import _create_synthetic_samples

        samples = _create_synthetic_samples(50)
        assert len(samples) == 50

        for s in samples[:5]:
            assert len(s.voltage) > 0
            assert len(s.current) > 0
            assert len(s.voltage) == len(s.current)
            assert s.mechanism in [0, 1, 2]
            assert s.scan_rate > 0

    def test_physics_loss_validation(self):
        """PhysicsInformedLoss should produce non-zero, differentiable loss."""
        import torch
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend" / "ml"))
        from models.physics_informed_loss import PhysicsInformedLoss

        loss_fn = PhysicsInformedLoss(
            lambda_bv=0.1, lambda_rs=0.1, lambda_nernst=0.1, lambda_charge=0.05
        )

        batch_size = 4
        seq_len = 100
        voltage = torch.linspace(-0.5, 0.5, seq_len).unsqueeze(0).expand(batch_size, -1)
        current = torch.randn(batch_size, 1, seq_len, requires_grad=True)

        predictions = {
            "embedding": current.squeeze(1),
            "reconstructed": current.squeeze(1),
        }

        loss, breakdown = loss_fn(
            predictions=predictions, voltage=voltage, current=current,
        )

        assert loss.item() > 0
        assert loss.requires_grad
        assert isinstance(breakdown, dict)
        assert len(breakdown) > 0

    def test_synthetic_dataset_creation(self):
        """Dataset should accept synthetic samples and return valid tensors."""
        import torch
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend" / "ml"))
        from training.run_physics_training import _create_synthetic_samples
        from training.train_cv import CVDataset, CONFIG

        samples = _create_synthetic_samples(20)
        dataset = CVDataset(samples, data_points=CONFIG["data_points"])
        assert len(dataset) == 20

        item = dataset[0]
        assert item["current"].shape == (1, CONFIG["data_points"])
        assert item["voltage"].shape == (CONFIG["data_points"],)
        assert isinstance(item["labels"], dict)


class TestNewAPIEndpoints:
    """Test the new API endpoints are importable and functional."""

    def test_semantic_extract_endpoint_exists(self):
        """Semantic extract endpoint should be registered."""
        from research.processors.semantic_extractor import get_extractor
        extractor = get_extractor(use_nlp=False)
        assert extractor is not None
        result = extractor.extract("MnO2 electrode for supercapacitor")
        assert result.total_entities > 0

    def test_cross_modal_cv_endpoint(self):
        """CV identification should return results."""
        from ml.models.cross_modal_identifier import get_identifier
        identifier = get_identifier()
        results = identifier.identify_from_cv(peak_separation_mV=65, ipa_ipc_ratio=0.99)
        assert len(results) > 0

    def test_cross_modal_eis_endpoint(self):
        """EIS identification should return results."""
        from ml.models.cross_modal_identifier import get_identifier
        identifier = get_identifier()
        results = identifier.identify_from_eis(rct_ohm=30, cdl_uF=300)
        assert len(results) > 0

    def test_cross_modal_raman_endpoint(self):
        """Raman identification should return results."""
        from ml.models.cross_modal_identifier import get_identifier
        identifier = get_identifier()
        results = identifier.identify_from_raman([383, 408])
        assert len(results) > 0
        names = [r.material_name for r in results]
        assert "MoS2" in names

    def test_biosensor_suggest_endpoint(self):
        """Biosensor suggest should return coating recommendations."""
        from ml.models.biosensor_suggestor import get_suggestor
        suggestor = get_suggestor()
        results = suggestor.suggest("glucose", use_nvidia=False)
        assert len(results) > 0
        assert results[0].expected_lod != ""

    def test_nvidia_discover_fallback(self):
        """NVIDIA discovery should return fallback candidates."""
        old_key = os.environ.pop("NVIDIA_API_KEY", None)
        try:
            from research.nvidia_integration import discover_materials
            candidates = discover_materials("supercapacitor electrode")
            assert len(candidates) > 0
        finally:
            if old_key:
                os.environ["NVIDIA_API_KEY"] = old_key


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
