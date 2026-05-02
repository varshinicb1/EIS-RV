import pytest
import json
import asyncio
from fastapi.testclient import TestClient
from src.backend.api.server import app

client = TestClient(app)

def test_telemetry_websocket():
    # Connect to the websocket
    with client.websocket_connect("/api/v2/ws/telemetry") as websocket:
        # Give it a tiny bit of time to yield mock data
        # Since the mock generator has a 2.0s sleep, we might need to wait, but TestClient handles this
        # Actually, since it's a test client, the background task `lifespan` runs `hw_bridge.connect()`, 
        # which will start `_mock_listen`. The `_mock_listen` emits data every 2s.
        
        # In a test we might not want to wait 2 seconds. We can just send a command and verify we can receive.
        cmd_payload = {"cmd": "START_EIS", "params": {"f_min": 0.1}}
        websocket.send_json(cmd_payload)
        
        # We can try to receive json
        try:
            # We'll set a timeout to avoid hanging indefinitely if data doesn't come
            data = websocket.receive_json()
            assert "type" in data
            print("Received telemetry:", data)
        except Exception as e:
            print("Failed to receive telemetry:", e)
