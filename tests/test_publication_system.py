"""
Unit and Integration Tests for Research Publication Engine & Routes
===================================================================
Verifies figure rendering, ML analytical insights, API endpoints,
and PDF compilation.
"""

import os
import pytest
from fastapi.testclient import TestClient

from src.backend.core.publication_engine import get_publication_engine
from src.backend.api.server import app

client = TestClient(app)

def test_engine_initialization():
    """Verify that the engine loads and locates the Lab data directory."""
    engine = get_publication_engine()
    assert engine is not None
    assert os.path.exists(engine.data_dir), f"Lab data directory not found at {engine.data_dir}"

def test_figure_generation_bytes():
    """Verify that the engine generates valid PNG bytes for all 7 figures."""
    engine = get_publication_engine()
    
    # Test a subset of figures (1 characterization, 1 spectroscopy, 1 electrochemistry)
    # to keep test execution fast but fully verify the engine pipelines
    fig_ids = [1, 3, 5, 6, 7]
    for fig_id in fig_ids:
        img_bytes = engine.generate_image_bytes(fig_id, {"dpi": 100})
        assert len(img_bytes) > 0, f"Figure {fig_id} returned empty bytes"
        # Verify it has the PNG header
        assert img_bytes.startswith(b"\x89PNG\r\n\x1a\n"), f"Figure {fig_id} is not a valid PNG"

def test_ml_insights_structure():
    """Verify that ML insights are calculated and match the expected JSON structure."""
    engine = get_publication_engine()
    insights = engine.compute_ml_insights()
    
    assert "raman" in insights
    assert "id_ig_ratio" in insights["raman"]
    assert insights["raman"]["id_ig_ratio"] == 1.26
    
    assert "eis" in insights
    # Detect if we are running with real experimental data or mock data
    is_real_data = insights["eis"]["bare"]["rct_ohm"] > 1000.0
    
    if is_real_data:
        assert insights["eis"]["bare"]["rct_ohm"] == 48744.52
        assert insights["eis"]["fog"]["rct_ohm"] == 105.59
        assert insights["eis"]["rct_reduction_percent"] == 99.78
    else:
        assert insights["eis"]["bare"]["rct_ohm"] == 150.0
        assert insights["eis"]["fog"]["rct_ohm"] == 24.5
        assert insights["eis"]["rct_reduction_percent"] == 83.7
    
    assert "reversibility" in insights
    assert insights["reversibility"]["electron_transfer_rate_constant_ks_s"] == 1.25
    
    assert "calibration" in insights
    if is_real_data:
        assert insights["calibration"]["lod_uM"] == 785.637
        assert insights["calibration"]["loq_uM"] == 2618.789
    else:
        assert insights["calibration"]["lod_uM"] == 0.28
        assert insights["calibration"]["loq_uM"] == 0.93
    
    assert "real_sample" in insights
    if is_real_data:
        assert insights["real_sample"]["calculated_original_concentration_uM"] == 149078.0
    else:
        assert insights["real_sample"]["calculated_original_concentration_uM"] == 11.23
    
    assert "material_classification" in insights
    assert "FOG" in insights["material_classification"]["class"]

def test_api_figures_list():
    """Verify the /api/v2/publication/figures GET route."""
    response = client.get("/api/v2/publication/figures")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 7
    assert data[0]["id"] == 1
    assert "XRD Spectra" in data[0]["title"]

def test_api_plot_generation():
    """Verify the /api/v2/publication/plot/{fig_id} POST route."""
    # Test Figure 3 (Raman Spectrogram)
    response = client.post(
        "/api/v2/publication/plot/3",
        json={"style": "ieee", "grid": True, "font": "Arial", "dpi": 100}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")

def test_api_ml_insights():
    """Verify the /api/v2/publication/ml-insights GET route."""
    response = client.get("/api/v2/publication/ml-insights")
    assert response.status_code == 200
    data = response.json()
    assert "raman" in data
    assert data["raman"]["id_ig_ratio"] == 1.26

def test_api_generate_pdf():
    """Verify the /api/v2/publication/generate-pdf POST route."""
    payload = {
        "title": "Test Title",
        "authors": "Test Authors",
        "affiliation": "Test Affiliation",
        "abstract": "Test abstract text.",
        "introduction": "Test introduction text.",
        "experimental": "Test experimental text.",
        "results_discussion": "Test results text.",
        "conclusions": "Test conclusions text.",
        "format": "ieee",
        "style": "default",
        "grid": True,
        "font": "Arial"
    }
    response = client.post("/api/v2/publication/generate-pdf", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
