"""
ZeroMQ IPC Bridge
==================
Provides typed, bidirectional messaging between RĀMAN Studio components:
  - Backend (Py3.14) ↔ AI Engine (Py3.13)
  - Backend (Py3.14) ↔ Electron renderer (via Node zmq)

Protocol:
  - REQ/REP for synchronous RPC calls
  - PUB/SUB for streaming results (simulation progress, live plots)
  - Messages are MessagePack-encoded for performance

Falls back to REST if zmq is unavailable.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Try ZeroMQ import
try:
    import zmq
    import zmq.asyncio
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    logger.warning("pyzmq not available — IPC will use REST fallback")

# Try msgpack for fast serialization
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False


class MessageType(str, Enum):
    """IPC message types."""
    REQUEST = "req"
    RESPONSE = "res"
    ERROR = "err"
    STREAM_START = "stream_start"
    STREAM_DATA = "stream_data"
    STREAM_END = "stream_end"
    HEARTBEAT = "heartbeat"


@dataclass
class IPCMessage:
    """Typed IPC message envelope."""
    msg_type: MessageType
    method: str
    payload: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    source: str = "backend"

    def serialize(self) -> bytes:
        """Serialize to bytes (msgpack if available, else JSON)."""
        data = {
            "t": self.msg_type.value,
            "m": self.method,
            "p": self.payload,
            "id": self.request_id,
            "ts": self.timestamp,
            "src": self.source,
        }
        if MSGPACK_AVAILABLE:
            return msgpack.packb(data, use_bin_type=True)
        return json.dumps(data).encode("utf-8")

    @classmethod
    def deserialize(cls, raw: bytes) -> "IPCMessage":
        """Deserialize from bytes."""
        if MSGPACK_AVAILABLE:
            try:
                data = msgpack.unpackb(raw, raw=False)
            except Exception:
                data = json.loads(raw.decode("utf-8"))
        else:
            data = json.loads(raw.decode("utf-8"))

        return cls(
            msg_type=MessageType(data["t"]),
            method=data["m"],
            payload=data.get("p", {}),
            request_id=data.get("id", ""),
            timestamp=data.get("ts", 0.0),
            source=data.get("src", "unknown"),
        )


class ZMQBridge:
    """
    ZeroMQ IPC bridge for RĀMAN Studio.

    Supports:
      - RPC (REQ/REP): call remote methods and get results
      - Streaming (PUB/SUB): real-time simulation data

    Usage (server side - Python backend):
        bridge = ZMQBridge(role="server")
        bridge.register("simulate_eis", handler_fn)
        bridge.serve()  # blocking event loop

    Usage (client side - AI engine or Electron):
        bridge = ZMQBridge(role="client")
        result = bridge.call("simulate_eis", {"Rs": 10, "Rct": 100})
    """

    DEFAULT_RPC_PORT = 5555
    DEFAULT_PUB_PORT = 5556

    def __init__(
        self,
        role: str = "server",
        rpc_port: int = DEFAULT_RPC_PORT,
        pub_port: int = DEFAULT_PUB_PORT,
        bind_address: str = "127.0.0.1",
    ):
        if not ZMQ_AVAILABLE:
            raise RuntimeError(
                "pyzmq is required for ZMQ IPC. "
                "Install: pip install pyzmq msgpack"
            )

        self.role = role
        self.rpc_port = rpc_port
        self.pub_port = pub_port
        self.bind_address = bind_address
        self._handlers: Dict[str, Callable] = {}
        self._context = zmq.Context()

        if role == "server":
            # REP socket for RPC (server binds)
            self._rpc_socket = self._context.socket(zmq.REP)
            self._rpc_socket.bind(f"tcp://{bind_address}:{rpc_port}")

            # PUB socket for streaming (server binds)
            self._pub_socket = self._context.socket(zmq.PUB)
            self._pub_socket.bind(f"tcp://{bind_address}:{pub_port}")

            logger.info(
                "ZMQ server bound: RPC=%s:%d, PUB=%s:%d",
                bind_address, rpc_port, bind_address, pub_port,
            )
        else:
            # REQ socket for RPC (client connects)
            self._rpc_socket = self._context.socket(zmq.REQ)
            self._rpc_socket.connect(f"tcp://{bind_address}:{rpc_port}")
            self._rpc_socket.setsockopt(zmq.RCVTIMEO, 30000)  # 30s timeout

            # SUB socket for streaming (client connects)
            self._pub_socket = self._context.socket(zmq.SUB)
            self._pub_socket.connect(f"tcp://{bind_address}:{pub_port}")
            self._pub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

            logger.info(
                "ZMQ client connected: RPC=%s:%d, SUB=%s:%d",
                bind_address, rpc_port, bind_address, pub_port,
            )

    def register(self, method: str, handler: Callable):
        """Register an RPC method handler (server only)."""
        self._handlers[method] = handler
        logger.info("Registered RPC handler: %s", method)

    def call(self, method: str, payload: Optional[Dict] = None, timeout_ms: int = 30000) -> Dict:
        """Call a remote RPC method (client only)."""
        if self.role != "client":
            raise RuntimeError("call() is for client role only")

        msg = IPCMessage(
            msg_type=MessageType.REQUEST,
            method=method,
            payload=payload or {},
            source="client",
        )

        self._rpc_socket.send(msg.serialize())
        raw = self._rpc_socket.recv()
        response = IPCMessage.deserialize(raw)

        if response.msg_type == MessageType.ERROR:
            raise RuntimeError(f"RPC error: {response.payload.get('error', 'unknown')}")

        return response.payload

    def publish(self, topic: str, data: Dict):
        """Publish streaming data (server only)."""
        if self.role != "server":
            raise RuntimeError("publish() is for server role only")

        msg = IPCMessage(
            msg_type=MessageType.STREAM_DATA,
            method=topic,
            payload=data,
            source="server",
        )
        self._pub_socket.send(msg.serialize())

    def serve_once(self):
        """Handle one RPC request (non-blocking for integration)."""
        if self.role != "server":
            raise RuntimeError("serve_once() is for server role only")

        if self._rpc_socket.poll(100):  # 100ms poll
            raw = self._rpc_socket.recv()
            request = IPCMessage.deserialize(raw)

            handler = self._handlers.get(request.method)
            if handler is None:
                response = IPCMessage(
                    msg_type=MessageType.ERROR,
                    method=request.method,
                    payload={"error": f"Unknown method: {request.method}"},
                    request_id=request.request_id,
                    source="server",
                )
            else:
                try:
                    result = handler(request.payload)
                    response = IPCMessage(
                        msg_type=MessageType.RESPONSE,
                        method=request.method,
                        payload=result if isinstance(result, dict) else {"result": result},
                        request_id=request.request_id,
                        source="server",
                    )
                except Exception as e:
                    logger.error("RPC handler error [%s]: %s", request.method, e)
                    response = IPCMessage(
                        msg_type=MessageType.ERROR,
                        method=request.method,
                        payload={"error": str(e)},
                        request_id=request.request_id,
                        source="server",
                    )

            self._rpc_socket.send(response.serialize())

    def serve(self):
        """Blocking RPC event loop."""
        logger.info("ZMQ server entering event loop...")
        while True:
            self.serve_once()

    def close(self):
        """Clean shutdown."""
        self._rpc_socket.close()
        self._pub_socket.close()
        self._context.term()
        logger.info("ZMQ bridge closed")
