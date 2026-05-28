"""
Integration Tests for RĀMAN Studio External Integrations
=========================================================
Tests for RDKit, CAMD, and WEI integrations.

Tests are designed to pass whether or not optional packages are installed.
"""

import pytest
from typing import Optional


# ── RDKit Tests ─────────────────────────────────────────────────

def test_rdkit_availability():
    """Test RDKit integration availability check."""
    from src.backend.integrations.rdkit_integration import get_rdkit_integration
    
    rdkit = get_rdkit_integration()
    # Should return True or False, never crash
    assert isinstance(rdkit.is_available(), bool)


@pytest.mark.skipif(
    not _rdkit_available(),
    reason="RDKit not installed"
)
def test_rdkit_descriptors():
    """Test molecular descriptor calculation."""
    from src.backend.integrations.rdkit_integration import get_rdkit_integration
    
    rdkit = get_rdkit_integration()
    
    # Test benzene
    descriptors = rdkit.calculate_descriptors("C1=CC=CC=C1")
    assert descriptors is not None
    assert descriptors.smiles == "C1=CC=CC=C1"
    assert 78.0 < descriptors.molecular_weight < 79.0
    assert descriptors.num_aromatic_rings == 1
    assert descriptors.num_h_donors == 0


@pytest.mark.skipif(
    not _rdkit_available(),
    reason="RDKit not installed"
)
def test_rdkit_similarity():
    """Test molecular similarity calculation."""
    from src.backend.integrations.rdkit_integration import get_rdkit_integration
    
    rdkit = get_rdkit_integration()
    
    # Benzene vs phenol (should be similar)
    similarity = rdkit.calculate_similarity("C1=CC=CC=C1", "C1=CC=C(C=C1)O")
    assert similarity is not None
    assert 0.8 < similarity < 1.0
    
    # Benzene vs hexane (should be dissimilar)
    similarity = rdkit.calculate_similarity("C1=CC=CC=C1", "CCCCCC")
    assert similarity is not None
    assert 0.0 < similarity < 0.3


@pytest.mark.skipif(
    not _rdkit_available(),
    reason="RDKit not installed"
)
def test_rdkit_similarity_search():
    """Test finding most similar molecules."""
    from src.backend.integrations.rdkit_integration import get_rdkit_integration
    
    rdkit = get_rdkit_integration()
    
    query = "C1=CC=CC=C1"  # Benzene
    candidates = [
        "C1=CC=C(C=C1)O",   # Phenol (similar)
        "C1=CC=C(C=C1)N",   # Aniline (similar)
        "CCCCCC",            # Hexane (dissimilar)
    ]
    
    results = rdkit.find_most_similar(query, candidates)
    assert results is not None
    assert len(results) == 3
    
    # First result should be most similar
    assert results[0][1] > results[1][1] > results[2][1]


@pytest.mark.skipif(
    not _rdkit_available(),
    reason="RDKit not installed"
)
def test_rdkit_validate_smiles():
    """Test SMILES validation."""
    from src.backend.integrations.rdkit_integration import get_rdkit_integration
    
    rdkit = get_rdkit_integration()
    
    # Valid SMILES
    assert rdkit.validate_smiles("C1=CC=CC=C1") is True
    assert rdkit.validate_smiles("CCO") is True
    
    # Invalid SMILES
    assert rdkit.validate_smiles("INVALID") is False
    assert rdkit.validate_smiles("C1=CC=CC=C") is False  # Unclosed ring


def test_rdkit_graceful_fallback():
    """Test that RDKit functions return None when unavailable."""
    from src.backend.integrations.rdkit_integration import RDKitIntegration
    
    # Create instance that thinks RDKit is unavailable
    rdkit = RDKitIntegration()
    rdkit.available = False
    
    # All methods should return None or False, not crash
    assert rdkit.calculate_descriptors("C1=CC=CC=C1") is None
    assert rdkit.calculate_similarity("C1=CC=CC=C1", "CCO") is None
    assert rdkit.find_most_similar("C1=CC=CC=C1", ["CCO"]) is None
    assert rdkit.validate_smiles("C1=CC=CC=C1") is False


# ── CAMD Tests ──────────────────────────────────────────────────

def test_camd_availability():
    """Test CAMD integration availability check."""
    from src.backend.integrations.camd_integration import get_camd_integration
    
    camd = get_camd_integration()
    assert isinstance(camd.is_available(), bool)


@pytest.mark.skipif(
    not _camd_available(),
    reason="CAMD not installed"
)
def test_camd_optimization():
    """Test Bayesian optimization."""
    from src.backend.integrations.camd_integration import get_camd_integration
    
    camd = get_camd_integration()
    
    # Simple test function: maximize x^2
    def test_function(candidate):
        x = candidate.get("x", 0)
        return {"score": x ** 2}
    
    # Candidate space
    candidates = [{"x": i} for i in range(-10, 11)]
    
    # Run optimization
    result = camd.optimize_material(
        simulation_fn=test_function,
        candidate_space=candidates,
        n_iterations=10,
        objective="maximize",
    )
    
    assert result is not None
    assert result.best_candidate is not None
    assert result.best_score >= 0
    assert result.n_iterations <= 10


def test_camd_graceful_fallback():
    """Test that CAMD functions return None when unavailable."""
    from src.backend.integrations.camd_integration import CAMDIntegration
    
    # Create instance that thinks CAMD is unavailable
    camd = CAMDIntegration()
    camd.available = False
    
    # All methods should return None, not crash
    result = camd.optimize_material(
        simulation_fn=lambda x: {"score": 1.0},
        candidate_space=[{"x": 1}],
        n_iterations=10,
    )
    assert result is None
    
    suggestion = camd.suggest_next_experiment([], [])
    assert suggestion is None


# ── WEI Tests ───────────────────────────────────────────────────

def test_wei_node_info():
    """Test WEI node information."""
    from src.backend.integrations.wei_integration import get_wei_node
    
    node = get_wei_node()
    info = node.get_info()
    
    assert info.node_id == "raman_studio_node"
    assert info.node_type == "simulation"
    assert "simulate_eis" in info.capabilities
    assert "simulate_cv" in info.capabilities


def test_wei_execute_eis():
    """Test WEI EIS simulation action."""
    from src.backend.integrations.wei_integration import get_wei_node
    
    node = get_wei_node()
    
    result = node.execute_action("simulate_eis", {
        "Rs": 10.0,
        "Rct": 100.0,
        "Cdl": 1e-5,
    })
    
    assert result.status == "success"
    assert "frequencies" in result.result
    assert "Z_real" in result.result
    assert "Z_imag" in result.result


def test_wei_execute_cv():
    """Test WEI CV simulation action."""
    from src.backend.integrations.wei_integration import get_wei_node
    
    node = get_wei_node()
    
    result = node.execute_action("simulate_cv", {
        "area_cm2": 0.0707,
        "E_formal_V": 0.23,
        "scan_rate_V_s": 0.05,
    })
    
    assert result.status == "success"
    assert "E" in result.result
    assert "i_total" in result.result


def test_wei_invalid_action():
    """Test WEI error handling for invalid action."""
    from src.backend.integrations.wei_integration import get_wei_node
    
    node = get_wei_node()
    
    result = node.execute_action("invalid_action", {})
    
    assert result.status == "error"
    assert result.error is not None
    assert "Unknown action" in result.error


# ── Helper Functions ────────────────────────────────────────────

def _rdkit_available() -> bool:
    """Check if RDKit is available."""
    try:
        from rdkit import Chem
        return True
    except ImportError:
        return False


def _camd_available() -> bool:
    """Check if CAMD is available."""
    try:
        import camd
        return True
    except ImportError:
        return False


# ── API Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_integration_status_endpoint():
    """Test integration status API endpoint."""
    from fastapi.testclient import TestClient
    from src.backend.api.server import app
    
    client = TestClient(app)
    response = client.get("/api/v2/integrations/status")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "rdkit" in data
    assert "camd" in data
    assert "wei" in data
    
    # WEI should always be available
    assert data["wei"]["available"] is True


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _rdkit_available(),
    reason="RDKit not installed"
)
async def test_rdkit_descriptors_endpoint():
    """Test RDKit descriptors API endpoint."""
    from fastapi.testclient import TestClient
    from src.backend.api.server import app
    
    client = TestClient(app)
    response = client.post(
        "/api/v2/integrations/rdkit/descriptors",
        json={"smiles": "C1=CC=CC=C1"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["smiles"] == "C1=CC=CC=C1"
    assert 78.0 < data["molecular_weight"] < 79.0


@pytest.mark.asyncio
async def test_wei_node_info_endpoint():
    """Test WEI node info API endpoint."""
    from fastapi.testclient import TestClient
    from src.backend.api.server import app
    
    client = TestClient(app)
    response = client.get("/api/v2/integrations/wei/node/info")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["node_id"] == "raman_studio_node"
    assert "simulate_eis" in data["capabilities"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
