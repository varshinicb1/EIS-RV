import asyncio
import websockets
import json

async def test_telemetry():
    uri = "ws://localhost:8085/api/v2/ws/telemetry"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to telemetry websocket")
            
            # Send a command
            cmd = {"cmd": "START_EIS", "params": {}}
            await websocket.send(json.dumps(cmd))
            print("Sent command:", cmd)
            
            # Wait for data
            # The mock hardware bridge emits data every 2 seconds
            for _ in range(2):
                data = await websocket.recv()
                print("Received telemetry:", data)
    except Exception as e:
        print("WebSocket test failed:", e)

if __name__ == "__main__":
    asyncio.run(test_telemetry())
