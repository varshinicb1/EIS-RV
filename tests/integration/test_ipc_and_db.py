"""
Integration Test — IPC Layer (ZMQ + REST)
===========================================
Tests ZeroMQ and REST communication between backend components.
"""

import json
import threading
import time

import pytest


class TestZMQBridge:
    """Test ZeroMQ IPC communication."""

    def test_message_serialization(self):
        """IPCMessage should round-trip serialize correctly."""
        from src.backend.ipc.zmq_bridge import IPCMessage, MessageType

        msg = IPCMessage(
            msg_type=MessageType.REQUEST,
            method="simulate_eis",
            payload={"Rs": 10, "Rct": 100},
            source="test",
        )

        raw = msg.serialize()
        restored = IPCMessage.deserialize(raw)

        assert restored.method == "simulate_eis"
        assert restored.payload["Rs"] == 10
        assert restored.msg_type == MessageType.REQUEST

    def test_message_types(self):
        """All message types should be valid."""
        from src.backend.ipc.zmq_bridge import MessageType

        assert MessageType.REQUEST.value == "req"
        assert MessageType.RESPONSE.value == "res"
        assert MessageType.ERROR.value == "err"
        assert MessageType.STREAM_DATA.value == "stream_data"


class TestRESTBridge:
    """Test REST fallback bridge."""

    def test_health_check_offline(self):
        """Health check should return False when no server running."""
        try:
            from src.backend.ipc.rest_fallback import RESTBridge
            bridge = RESTBridge(base_url="http://127.0.0.1:9999")
            assert bridge.health_check() is False
        except RuntimeError:
            pytest.skip("requests library not available")


class TestDatabaseEngines:
    """Test database initialization."""

    def test_sqlite_init(self):
        """SQLite state DB should initialize without error."""
        import tempfile
        import os
        from src.backend.database.sqlite_engine import StateDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db = StateDB(os.path.join(tmpdir, "test_state.sqlite"))
            db.initialize()

            db.set_setting("theme", "dark")
            assert db.get_setting("theme") == "dark"
            assert db.get_setting("missing", "default") == "default"

            db.close()

    def test_duckdb_init(self):
        """DuckDB analytics should initialize schema."""
        try:
            import tempfile
            import os
            from src.backend.database.duckdb_engine import AnalyticsDB

            with tempfile.TemporaryDirectory() as tmpdir:
                db = AnalyticsDB(os.path.join(tmpdir, "test.duckdb"))
                db.initialize()

                # Insert a test material
                mid = db.insert_material("Graphene", "C", "carbon")
                assert mid > 0

                # Query it back
                results = db.search_materials(category="carbon")
                assert len(results) >= 1

                db.close()
        except RuntimeError:
            pytest.skip("duckdb not installed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
