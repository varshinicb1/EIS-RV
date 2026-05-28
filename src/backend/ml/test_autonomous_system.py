"""
Autonomous System Integration Tests
====================================
Comprehensive tests for the autonomous materials discovery system.

Tests:
- Material identification
- Bayesian optimization
- Campaign management
- WebSocket updates
"""

import pytest
import numpy as np
from typing import Dict, Any


# ── Material Identification Tests ──────────────────────────────

def test_material_identifier_initialization():
    """Test material identifier initialization."""
    from src.backend.ml.material_identifier import get_material_identifier
    
    identifier = get_material_identifier()
    assert identifier is not None
    assert identifier.rdkit is not None


def test_load_materials_database():
    """Test loading materials database."""
    from src.backend.ml.material_identifier import get_material_identifier
    
    identifier = get_material_identifier()
    n_loaded = identifier.load_materials_database("data/materials_database.json")
    
    assert n_loaded > 0
    assert len(identifier.materials_db) == n_loaded


def test_extract_eis_features():
    """Test EIS feature extraction."""
    from src.backend.ml.material_identifier import get_material_identifier
    
    identifier = get_material_identifier()
    
    # Generate synthetic EIS data
    freq = np.logspace(-2, 6, 50)
    Rs = 10.0
    Rct = 100.0
    Cdl = 1e-5
    
    omega = 2 * np.pi * freq
    Z_c = 1 / (1j * omega * Cdl)
    Z = Rs + 1 / (1/Rct + 1/Z_c)
    
    features = identifier.extract_eis_features(
        frequencies=freq.tolist(),
        Z_real=np.real(Z).tolist(),
        Z_imag=np.imag(Z).tolist()
    )
    
    assert features is not None
    assert features.Rs is not None
    assert features.Rct is not None
    assert features.Cdl is not None


def test_identify_from_eis():
    """Test material identification from EIS data."""
    from src.backend.ml.material_identifier import get_material_identifier
    
    identifier = get_material_identifier()
    identifier.load_materials_database("data/materials_database.json")
    
    # Generate synthetic EIS data
    freq = np.logspace(-2, 6, 50)
    Rs = 10.0
    Rct = 100.0
    Cdl = 1e-5
    
    omega = 2 * np.pi * freq
    Z_c = 1 / (1j * omega * Cdl)
    Z = Rs + 1 / (1/Rct + 1/Z_c)
    
    prediction = identifier.identify_from_eis(
        frequencies=freq.tolist(),
        Z_real=np.real(Z).tolist(),
        Z_imag=np.imag(Z).tolist(),
        top_k=3
    )
    
    assert prediction is not None
    assert prediction.material_name is not None
    assert 0 <= prediction.confidence <= 1
    assert len(prediction.alternatives) <= 3


# ── Autonomous Optimizer Tests ─────────────────────────────────

def test_autonomous_optimizer_initialization():
    """Test autonomous optimizer initialization."""
    from src.backend.ml.autonomous_optimizer import get_autonomous_optimizer
    
    optimizer = get_autonomous_optimizer()
    assert optimizer is not None
    assert optimizer.camd is not None


def test_start_campaign():
    """Test starting an optimization campaign."""
    from src.backend.ml.autonomous_optimizer import get_autonomous_optimizer
    from src.backend.ml.material_identifier import get_material_identifier
    
    optimizer = get_autonomous_optimizer()
    identifier = get_material_identifier()
    identifier.load_materials_database("data/materials_database.json")
    
    # Define simple objective function
    def objective(material: Dict[str, Any]) -> float:
        # Return stored capacitance
        return material.get("properties", {}).get("capacitance_F_g", 100.0)
    
    # Start campaign
    campaign_id = optimizer.start_campaign(
        objective_fn=objective,
        candidate_space=identifier.materials_db,
        target_metric="capacitance",
        objective="maximize",
        max_iterations=10,
        convergence_threshold=0.01,
    )
    
    assert campaign_id is not None
    assert len(campaign_id) > 0


def test_get_campaign_status():
    """Test getting campaign status."""
    from src.backend.ml.autonomous_optimizer import get_autonomous_optimizer
    from src.backend.ml.material_identifier import get_material_identifier
    
    optimizer = get_autonomous_optimizer()
    identifier = get_material_identifier()
    identifier.load_materials_database("data/materials_database.json")
    
    # Start campaign
    def objective(material: Dict[str, Any]) -> float:
        return material.get("properties", {}).get("capacitance_F_g", 100.0)
    
    campaign_id = optimizer.start_campaign(
        objective_fn=objective,
        candidate_space=identifier.materials_db,
        target_metric="capacitance",
        objective="maximize",
        max_iterations=5,
    )
    
    # Get status
    status = optimizer.get_campaign_status(campaign_id)
    
    assert status is not None
    assert status["campaign_id"] == campaign_id
    assert "status" in status
    assert "n_iterations" in status


def test_campaign_convergence():
    """Test that campaign converges."""
    from src.backend.ml.autonomous_optimizer import get_autonomous_optimizer
    from src.backend.ml.material_identifier import get_material_identifier
    
    optimizer = get_autonomous_optimizer()
    identifier = get_material_identifier()
    identifier.load_materials_database("data/materials_database.json")
    
    # Define objective with clear optimum
    def objective(material: Dict[str, Any]) -> float:
        # Graphene has highest capacitance in database
        if material["name"] == "Graphene":
            return 250.0
        return material.get("properties", {}).get("capacitance_F_g", 100.0)
    
    campaign_id = optimizer.start_campaign(
        objective_fn=objective,
        candidate_space=identifier.materials_db,
        target_metric="capacitance",
        objective="maximize",
        max_iterations=20,
        convergence_threshold=0.01,
    )
    
    # Get results
    results = optimizer.get_campaign_results(campaign_id)
    
    assert results is not None
    assert results["best_candidate"] is not None
    assert results["best_score"] >= 200.0  # Should find high-capacitance material


def test_list_campaigns():
    """Test listing all campaigns."""
    from src.backend.ml.autonomous_optimizer import get_autonomous_optimizer
    
    optimizer = get_autonomous_optimizer()
    campaigns = optimizer.list_campaigns()
    
    assert isinstance(campaigns, list)
    # Should have campaigns from previous tests
    assert len(campaigns) > 0


# ── API Integration Tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_material_id_status_endpoint():
    """Test material identification status endpoint."""
    from fastapi.testclient import TestClient
    from src.backend.api.server import app
    
    client = TestClient(app)
    response = client.get("/api/v2/material-id/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "ml_model_trained" in data
    assert "n_materials" in data


@pytest.mark.asyncio
async def test_optimization_status_endpoint():
    """Test optimization status endpoint."""
    from fastapi.testclient import TestClient
    from src.backend.api.server import app
    
    client = TestClient(app)
    response = client.get("/api/v2/optimize/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "active_campaigns" in data
    assert "camd_available" in data


@pytest.mark.asyncio
async def test_list_campaigns_endpoint():
    """Test list campaigns endpoint."""
    from fastapi.testclient import TestClient
    from src.backend.api.server import app
    
    client = TestClient(app)
    response = client.get("/api/v2/optimize/campaigns")
    
    assert response.status_code == 200
    data = response.json()
    assert "campaigns" in data
    assert "total" in data


# ── Performance Tests ──────────────────────────────────────────

def test_optimization_performance():
    """Test optimization performance (should complete in reasonable time)."""
    import time
    from src.backend.ml.autonomous_optimizer import get_autonomous_optimizer
    from src.backend.ml.material_identifier import get_material_identifier
    
    optimizer = get_autonomous_optimizer()
    identifier = get_material_identifier()
    identifier.load_materials_database("data/materials_database.json")
    
    def objective(material: Dict[str, Any]) -> float:
        return material.get("properties", {}).get("capacitance_F_g", 100.0)
    
    start_time = time.time()
    
    campaign_id = optimizer.start_campaign(
        objective_fn=objective,
        candidate_space=identifier.materials_db,
        target_metric="capacitance",
        objective="maximize",
        max_iterations=10,
    )
    
    elapsed = time.time() - start_time
    
    # Should complete 10 iterations in < 5 seconds
    assert elapsed < 5.0
    
    results = optimizer.get_campaign_results(campaign_id)
    assert results["n_iterations"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
