---
name: Vite WebSocket proxy
description: Vite proxy config required for WebSocket passthrough; potentiostat WS behavior in Replit
---

Vite's `/api` proxy entry needs `ws: true` to upgrade WebSocket connections through to the FastAPI backend:

```js
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    ws: true,          // <-- required for WebSocket upgrade
  },
}
```

**Why:** Without `ws: true`, `wss?://host/api/v2/ws/telemetry` hits the Vite server and returns 404.

**Potentiostat WS in Replit:** The hardware WebSocket (`/api/v2/ws/telemetry`) will always fail in Replit because there is no physical serial device. DashboardPanel already handles this gracefully — it shows "Potentiostat: Disconnected" and retries every 5 s. This is correct behaviour, not a bug.

**WebSocket URL pattern:** Use `${proto}://${window.location.host}/api/v2/ws/...` where `proto = location.protocol === 'https:' ? 'wss' : 'ws'`. Do NOT hardcode `ws://127.0.0.1:8000`.
