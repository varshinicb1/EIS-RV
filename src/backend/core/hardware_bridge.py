import asyncio
import logging
import json
import random
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class PotentiostatBridge:
    """
    Asynchronous Serial Bridge for Potentiostat Hardware.
    Handles streaming of raw EIS/CV data from physical hardware via PySerial.
    """
    def __init__(self, port: str = "COM3", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.connected = False
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._callbacks = []

    async def connect(self):
        """Connect to the serial port via asyncio (using serial_asyncio if available)"""
        logger.info(f"Connecting to Potentiostat on {self.port} at {self.baudrate} baud...")
        try:
            import serial_asyncio
            self._reader, self._writer = await serial_asyncio.open_serial_connection(url=self.port, baudrate=self.baudrate)
            self.connected = True
            logger.info("Successfully connected to hardware.")
            self._listener_task = asyncio.create_task(self._listen())
        except ImportError:
            logger.warning("serial_asyncio not installed. Falling back to mocked hardware interface for development.")
            self.connected = True
            self._listener_task = asyncio.create_task(self._mock_listen())
        except Exception as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            self.connected = False
            
    def add_callback(self, cb: Callable[[dict], None]):
        self._callbacks.append(cb)

    async def _listen(self):
        """Listen to real hardware serial stream"""
        while self.connected and self._reader:
            try:
                line = await self._reader.readline()
                if line:
                    data = json.loads(line.decode('utf-8').strip())
                    for cb in self._callbacks:
                        cb(data)
            except Exception as e:
                logger.error(f"Serial read error: {e}")
                await asyncio.sleep(1)

    async def _mock_listen(self):
        """Generate mock EIS/CV telemetry data for UI development without physical hardware"""
        while self.connected:
            await asyncio.sleep(2.0)
            mock_data = {
                "type": "telemetry",
                "voltage_V": round(random.uniform(-0.5, 0.5), 4),
                "current_uA": round(random.uniform(-100, 100), 2),
                "status": "IDLE" if random.random() > 0.1 else "MEASURING"
            }
            for cb in self._callbacks:
                cb(mock_data)

    async def send_command(self, cmd: str, params: dict = None):
        """Send JSON command to the potentiostat microcontroller"""
        if not self.connected:
            raise ConnectionError("Not connected to potentiostat hardware")
            
        payload = json.dumps({"cmd": cmd, "params": params or {}}) + "\n"
        if self._writer:
            self._writer.write(payload.encode('utf-8'))
            await self._writer.drain()
        else:
            logger.debug(f"[MOCK HARDWARE] Sent command: {payload.strip()}")

    async def disconnect(self):
        self.connected = False
        if self._listener_task:
            self._listener_task.cancel()
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        logger.info("Disconnected from potentiostat hardware.")

# Singleton instance
bridge = PotentiostatBridge()
