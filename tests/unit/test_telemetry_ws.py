"""
Telemetry WebSocket — license gate behavior.

The endpoint at ``/api/v2/ws/telemetry`` is now license-gated; the server
closes the upgrade with policy-violation (1008) when no valid trial /
license is present, instead of accepting unauthenticated commands.

We don't need to actually drive the hardware bridge to verify the gate —
just that the close path works and unauthenticated callers cannot
exchange any message after upgrade.
"""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.backend.api.server import app
from src.backend.licensing.license_manager import (
    get_license_manager,
    reset_license_manager,
    LicenseStatus,
)


@pytest.fixture
def client():
    return TestClient(app)


def _force_license_status(status: str):
    """
    Helper: monkey-patch the singleton license manager so the gate sees
    the requested status without us needing to write to disk.
    """
    mgr = get_license_manager()
    real = mgr.validate_license

    class _FakeInfo:
        def __init__(self, status):
            self.status = status
            self.message = ""
            self.features = ["lab_data", "agent", "alchemi"]
            self.plan = "trial"
            self.expires_at = 0
            self.days_remaining = 30

        def to_dict(self):
            return {"status": self.status, "plan": self.plan}

    mgr.validate_license = lambda: _FakeInfo(status)
    return real


def _restore_license(mgr_validate):
    get_license_manager().validate_license = mgr_validate


def test_ws_telemetry_rejects_when_license_invalid(client):
    """No license → server closes with policy-violation (1008) before any message."""
    real = _force_license_status(LicenseStatus.INVALID)
    try:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v2/ws/telemetry") as ws:
                # Trigger receive — server has already closed.
                ws.receive_text()
        assert exc_info.value.code == 1008
    finally:
        _restore_license(real)


def test_ws_telemetry_accepts_with_trial(client):
    """Active trial → connection accepted; bad payloads ignored, not crashing."""
    real = _force_license_status(LicenseStatus.TRIAL)
    try:
        with client.websocket_connect("/api/v2/ws/telemetry") as ws:
            # Non-JSON frame — server logs warning and continues.
            ws.send_text("not json {{{")
            # Missing 'cmd' field — server logs warning and continues.
            ws.send_json({"foo": "bar"})
            # Valid frame; the hw_bridge in tests is the mock instance,
            # so this just exercises the dispatch path.
            ws.send_json({"cmd": "PING", "params": {}})
            # Close cleanly — TestClient handles the close handshake.
    finally:
        _restore_license(real)
        # Reset singleton so subsequent tests start clean
        reset_license_manager()
