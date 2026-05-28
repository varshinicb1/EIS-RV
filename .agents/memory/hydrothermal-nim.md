---
name: Hydrothermal engine + NIM setup
description: Key facts about the Hydrothermal Discovery Engine wiring and NIM AI configuration in RĀMAN Studio
---

## Rule
NVIDIA_API_KEY must be stored as a Replit secret (not a plain env var). The NIM client checks both `bool(self.api_key)` and `self._requests_available` (requires `requests` library installed — confirmed present at 2.34.2).

**Why:** The error_handlers.py global handler originally sanitized all 5xx HTTPExceptions into a generic internal_error response. This masked the intentional 503 "NIM not configured" raised by the hydrothermal routes. Fixed by changing the condition from `>= 500` to `== 500`, so 503/502/504 pass through with their actionable detail intact.

**How to apply:** Any new route that intentionally raises HTTPException with a non-500 5xx status (e.g. 503 for missing external service, 502 for bad gateway) will work correctly. Only genuine unhandled 500s get sanitized. Always raise HTTPException directly (not via `internal_error()` helper) for intentional service-unavailable responses.

## Verified endpoints (all returning real NIM output)
- GET  /api/v2/hydrothermal/status         — nim_configured, inventory_total, capabilities
- GET  /api/v2/hydrothermal/inventory      — 121 chemicals, filterable by category/role/search
- POST /api/v2/hydrothermal/discover       — ranked candidates with precursor availability + DOI provenance
- POST /api/v2/hydrothermal/synthesize     — step-by-step protocol with mass calculations
- POST /api/v2/hydrothermal/interpret      — CV/EIS correlation + synthesis optimisation suggestions
- POST /api/v2/hydrothermal/feedback       — HITL ingestion, writes to knowledge graph
- POST /api/v2/hydrothermal/failures/record — failure tracking for candidate penalisation
- GET  /api/v2/hydrothermal/failures       — retrieve recorded failures
- GET  /api/v2/hydrothermal/knowledge-graph — live graph nodes + edges
