"""
AI Engine — Standalone ZeroMQ/REST Server
============================================
Runs NVIDIA Alchemi (quantum chemistry) in an isolated Python 3.13 environment.

Communication protocol:
  - ZeroMQ REP socket on port 5557 (primary)
  - REST fallback on http://127.0.0.1:8013 (secondary)

Startup:
  python3.13 -m src.ai_engine.server

The main backend (Python 3.14) calls this service via ZMQ or REST.
"""

import json
import logging
import os
import sys
import signal
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AI-Engine] %(levelname)s: %(message)s",
)

# ── ZeroMQ Server ──────────────────────────────────────────

ZMQ_PORT = int(os.environ.get("RAMAN_AI_ZMQ_PORT", "5557"))
REST_PORT = int(os.environ.get("RAMAN_AI_REST_PORT", "8013"))


def _load_alchemi():
    """Attempt to load NVIDIA Alchemi toolkit."""
    try:
        from .alchemi_bridge import AlchemiBridge
        bridge = AlchemiBridge()
        logger.info("✅ NVIDIA Alchemi bridge loaded")
        return bridge
    except ImportError:
        logger.warning("⚠️  Alchemi bridge not available — placeholder mode")
        return None
    except Exception as e:
        logger.error("❌ Alchemi bridge failed: %s", e)
        return None


def _handle_request(method: str, payload: Dict, alchemi) -> Dict:
    """Route incoming request to appropriate handler."""
    handlers = {
        "health": lambda p: {"status": "ok", "engine": "ai_engine_py313"},
        "optimize_geometry": lambda p: _handle_optimize(p, alchemi),
        "calculate_band_gap": lambda p: _handle_band_gap(p, alchemi),
        "calculate_properties": lambda p: _handle_properties(p, alchemi),
        "run_md": lambda p: _handle_md(p, alchemi),
    }

    handler = handlers.get(method)
    if handler is None:
        return {"error": f"Unknown method: {method}"}

    try:
        return handler(payload)
    except Exception as e:
        logger.error("Handler error [%s]: %s", method, e)
        return {"error": str(e)}


def _handle_optimize(payload: Dict, alchemi) -> Dict:
    if alchemi is None:
        return {"error": "Alchemi not available"}
    result = alchemi.optimize_geometry(payload)
    return result.to_dict() if hasattr(result, 'to_dict') else result


def _handle_band_gap(payload: Dict, alchemi) -> Dict:
    if alchemi is None:
        return {"error": "Alchemi not available"}
    gap = alchemi.calculate_band_gap(payload)
    return {"band_gap_eV": gap}


def _handle_properties(payload: Dict, alchemi) -> Dict:
    if alchemi is None:
        return {"error": "Alchemi not available"}
    return alchemi.calculate_properties(payload)


def _handle_md(payload: Dict, alchemi) -> Dict:
    if alchemi is None:
        return {"error": "Alchemi not available"}
    return alchemi.run_molecular_dynamics(payload)


# ── ZMQ Event Loop ─────────────────────────────────────────

def run_zmq_server():
    """Run ZeroMQ REP server."""
    try:
        import zmq
    except ImportError:
        logger.error("pyzmq not installed. Install: pip install pyzmq")
        return

    alchemi = _load_alchemi()

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://127.0.0.1:{ZMQ_PORT}")
    logger.info("🚀 AI Engine ZMQ server listening on port %d", ZMQ_PORT)

    running = True

    def shutdown(sig, frame):
        nonlocal running
        logger.info("Shutting down AI Engine...")
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    while running:
        if socket.poll(500):  # 500ms poll
            raw = socket.recv()
            try:
                request = json.loads(raw.decode("utf-8"))
                method = request.get("m", request.get("method", ""))
                payload = request.get("p", request.get("payload", {}))

                result = _handle_request(method, payload, alchemi)

                response = json.dumps({
                    "t": "res",
                    "m": method,
                    "p": result,
                }).encode("utf-8")
            except Exception as e:
                response = json.dumps({
                    "t": "err",
                    "m": "",
                    "p": {"error": str(e)},
                }).encode("utf-8")

            socket.send(response)

    socket.close()
    context.term()
    logger.info("AI Engine stopped")


# ── REST Fallback ──────────────────────────────────────────

def run_rest_server():
    """Run REST fallback server using FastAPI."""
    try:
        from fastapi import FastAPI
        import uvicorn
    except ImportError:
        logger.error("FastAPI not installed for REST fallback")
        return

    app = FastAPI(title="RĀMAN AI Engine", version="2.0.0")
    alchemi = _load_alchemi()

    @app.get("/health")
    async def health():
        return {"status": "ok", "engine": "ai_engine_py313"}

    @app.post("/api/v1/{method}")
    async def handle(method: str, payload: Dict[str, Any] = {}):
        return _handle_request(method, payload, alchemi)

    uvicorn.run(app, host="127.0.0.1", port=REST_PORT, log_level="info")


# ── Main ───────────────────────────────────────────────────

def main():
    mode = os.environ.get("RAMAN_AI_MODE", "zmq")
    logger.info("AI Engine starting (mode=%s, Python %s)", mode, sys.version)

    if mode == "rest":
        run_rest_server()
    else:
        run_zmq_server()


if __name__ == "__main__":
    main()
