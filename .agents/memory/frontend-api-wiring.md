---
name: Frontend API wiring
description: How simulation panels should call the backend; common pitfalls with hardcoded URLs in Replit
---

All simulation panels must use **relative URLs** (`/api/v2/...`) so the Vite dev-server proxy routes them to the FastAPI backend on `localhost:8000`. Hardcoded `http://127.0.0.1:8000` or conditional `API_BASE` logic based on `window.location.hostname === 'localhost'` breaks in Replit because the preview runs through a proxy and `window.location.host` is the Replit dev domain.

**Why:** Replit's preview iframe proxies traffic; absolute localhost URLs do not resolve from the browser context.

**How to apply:** Any new panel that calls the backend should use `fetch('/api/v2/endpoint', ...)`. Local JS fallbacks are acceptable for offline/demo use but must be labelled (e.g., engine: 'V_EMULATOR_LITE') and only triggered after a failed backend attempt.

**Panels fixed (May 2026):**
- EISPanel — was calling `computeEIS()` directly, now calls `/api/v2/eis` first
- CVPanel — was using `http://127.0.0.1:8000/api/v2/cv`
- BatteryPanel — was only trying `window.raman?.api` Electron bridge, skipping HTTP entirely
- GCDPanel — was trying Electron bridge then hardcoded URL
- ScanRateStudy — was 100% local; now calls `/api/v2/cv` for each rate
- CircuitFittingPanel, DashboardPanel — `const API = 'http://127.0.0.1:8000'` → `''`
- MaterialDiscoveryPanel — conditional API_BASE + double `.json()` bug fixed
