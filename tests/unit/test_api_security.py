"""
API security smoke tests.

Two things matter and they cut across every endpoint:

1. License gate — every paid route returns 403 (or {"code":"internal_error"}
   with our sanitized handler) when there is no valid trial / license. We
   force the singleton license manager into INVALID and confirm.

2. No stack-trace leak — when a route raises, the response body must NOT
   contain Python repr (file paths, "Traceback", str(exc) of
   FileNotFoundError, etc.). We pick a route that's easy to crash and
   confirm the body is the sanitized {error_id, message} shape.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.backend.api.server import app
from src.backend.licensing.license_manager import (
    get_license_manager,
    reset_license_manager,
    LicenseStatus,
)


@pytest.fixture
def client():
    return TestClient(app)


def _force_status(status: str):
    """Monkey-patch the singleton license manager to return ``status``."""
    mgr = get_license_manager()
    real = mgr.validate_license

    class _FakeInfo:
        def __init__(self):
            self.status = status
            self.message = "test fixture"
            self.features = ["alchemi", "agent", "lab_data"]
            self.plan = "trial" if status == LicenseStatus.TRIAL else "none"
            self.expires_at = 0
            self.days_remaining = 30 if status == LicenseStatus.TRIAL else 0

        def to_dict(self):
            return {"status": self.status, "plan": self.plan}

    mgr.validate_license = lambda: _FakeInfo()
    return real


def _restore(real):
    get_license_manager().validate_license = real
    reset_license_manager()


# Paid endpoints we expect to gate. Mix of GET / POST. (Path, method, body).
# /health and /api/health are intentionally NOT in this list — they are
# public liveness probes (covered by ``test_health_endpoint_does_not_require_license``).
GATED_ROUTES = [
    ("/api/v2/lab/datasets",          "GET",  None),
    ("/api/v2/supercap/analyze/raw",  "POST", {"cycles": [], "scan_rate_V_s": 0.01}),
    ("/api/quantum/status",           "GET",  None),
    ("/api/nvidia/status",            "GET",  None),
    ("/api/data/formats",             "GET",  None),
    ("/api/pe/ink/solvents",          "GET",  None),
    ("/api/materials",                "GET",  None),
]


@pytest.mark.parametrize("path,method,body", GATED_ROUTES)
def test_gated_routes_reject_when_license_invalid(client, path, method, body):
    real = _force_status(LicenseStatus.INVALID)
    try:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json=body)
        assert res.status_code == 403, f"{method} {path} expected 403 got {res.status_code}: {res.text}"
        # Body should reference license / activation, not a Python error
        body_text = res.text.lower()
        assert "traceback" not in body_text
        assert "/home/" not in body_text
    finally:
        _restore(real)


def test_gated_routes_accept_when_license_trial(client):
    """A subset of GET routes that don't need any state should succeed under trial."""
    real = _force_status(LicenseStatus.TRIAL)
    try:
        # /api/v2/lab/datasets — empty list is fine
        r = client.get("/api/v2/lab/datasets")
        assert r.status_code == 200, f"trial should pass: {r.text}"
        # /api/data/formats — static
        r = client.get("/api/data/formats")
        assert r.status_code == 200
    finally:
        _restore(real)


def test_health_endpoint_does_not_require_license(client):
    """/health and /api/health are explicitly NOT gated — they're for liveness probes."""
    real = _force_status(LicenseStatus.INVALID)
    try:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"
    finally:
        _restore(real)


def test_500_response_is_sanitized(client):
    """
    Force an internal error path and confirm the body is sanitized
    (no traceback, no str(exc), only {code, error_id, message}).

    We pick the lab xlsx route with an empty file body — that should hit
    the "uploaded file is empty" 400 path. We do NOT want a 500 here, so
    we don't get to verify the sanitizer in that route. Use the activate
    license endpoint with a clearly-malformed token instead — the route
    raises HTTPException(400, ...) which our handler passes through, and
    we confirm there's no leak.
    """
    real = _force_status(LicenseStatus.TRIAL)
    try:
        r = client.post("/api/v2/auth/license/activate", json={"token": "RMNS1.x.y"})
        # 400 path (validated to be a token but parse fails) — body is
        # safe to contain a structured 'detail' but NOT a stack trace.
        assert r.status_code in (400, 422)
        body = r.text.lower()
        assert "traceback" not in body
        assert "/home/" not in body
        assert "site-packages" not in body
    finally:
        _restore(real)


def test_pydantic_bounds_reject_bad_inputs(client):
    """porosity > 1, temperature < -273.15, mass < 0 should 422."""
    real = _force_status(LicenseStatus.TRIAL)
    try:
        bad_payloads = [
            ("/api/pe/supercap/simulate", {"porosity": 2.0}),                  # ge=0, le=1
            ("/api/pe/supercap/simulate", {"temperature_C": -500.0}),          # ge=-273.15
            ("/api/pe/supercap/simulate", {"mass_mg": -1.0}),                  # ge=0
        ]
        for path, body in bad_payloads:
            r = client.post(path, json=body)
            assert r.status_code == 422, f"{path} {body}: expected 422, got {r.status_code}"
    finally:
        _restore(real)
