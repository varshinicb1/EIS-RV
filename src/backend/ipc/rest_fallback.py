"""
REST Fallback for IPC
======================
When ZeroMQ is unavailable, the backend communicates with the
AI engine (Python 3.13) via local HTTP REST calls.

This module provides a client that mirrors the ZMQ bridge API.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import requests as http_requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class RESTBridge:
    """
    REST-based IPC fallback.

    Usage:
        bridge = RESTBridge(base_url="http://127.0.0.1:8013")
        result = bridge.call("optimize_geometry", {"positions": [...]})
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8013",
                 timeout_s: int = 120):
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library required for REST fallback")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_s
        logger.info("REST bridge initialized: %s", self.base_url)

    def call(self, method: str, payload: Optional[Dict] = None) -> Dict:
        """Call a remote method via REST POST."""
        url = f"{self.base_url}/api/v1/{method}"
        try:
            response = http_requests.post(
                url,
                json=payload or {},
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except http_requests.ConnectionError:
            raise RuntimeError(f"AI engine not reachable at {self.base_url}")
        except http_requests.Timeout:
            raise RuntimeError(f"AI engine timeout after {self.timeout}s")
        except Exception as e:
            raise RuntimeError(f"REST call failed: {e}")

    def health_check(self) -> bool:
        """Check if AI engine is responding."""
        try:
            resp = http_requests.get(
                f"{self.base_url}/health", timeout=5
            )
            return resp.status_code == 200
        except Exception:
            return False
