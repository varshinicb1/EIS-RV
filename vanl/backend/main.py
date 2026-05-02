"""
VANL FastAPI Application
==========================
Main entry point for the Virtual Autonomous Nanomaterials Lab API server.

Usage:
    python -m uvicorn vanl.backend.main:app --reload --port 8000

Or:
    python vanl/backend/main.py
"""

import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.routes import router
from .api.pe_routes import router as pe_router
from .api.nvidia_routes import router as nvidia_router
from .api.quantum_routes import router as quantum_router
from .api.data_routes import router as data_router
from .api.auth_routes import router as auth_router
from .api.workspace_routes import router as workspace_router
from .api.project_routes import router as project_router
from .api.experiment_routes import router as experiment_router
from .api.batch_routes import router as batch_router
from .api.automation_routes import router as automation_router
from .api.compliance_routes import router as compliance_router
from .core.rate_limiter import RateLimitMiddleware, RateLimitConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="RĀMAN Studio — The Digital Twin for Your Potentiostat",
    description=(
        "Quantum-accurate electrochemical analysis platform powered by NVIDIA ALCHEMI. "
        "Physics-informed digital twin for printed electronics: "
        "supercapacitors, batteries, sensors, biosensors. "
        "Ink formulation → printing → device simulation → characterization. "
        "Near-quantum accuracy at 100x-1000x speed of traditional DFT."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS for frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    config=RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        requests_per_day=10000
    )
)

# API routes — core electrochemistry
app.include_router(router)
# API routes — printed electronics digital twin
app.include_router(pe_router)
# API routes — NVIDIA intelligence & validation
app.include_router(nvidia_router)
# API routes — quantum chemistry (ALCHEMI)
app.include_router(quantum_router)
# API routes — real data analysis (import, fitting, DRT)
app.include_router(data_router)
# API routes — authentication & user management
app.include_router(auth_router)
# API routes — workspace & team collaboration
app.include_router(workspace_router)
# API routes — project organization
app.include_router(project_router)
# API routes — experiment management
app.include_router(experiment_router)
# API routes — batch processing & automation
app.include_router(batch_router)
# API routes — scheduled jobs & webhooks
app.include_router(automation_router)
# API routes — compliance & reporting (21 CFR Part 11)
app.include_router(compliance_router)

# Serve frontend static files if they exist
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="frontend")

    @app.get("/")
    async def serve_frontend():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/static/index.html")
else:
    @app.get("/")
    async def root():
        return {
            "service": "VANL — Virtual Autonomous Nanomaterials Lab",
            "version": "0.1.0",
            "docs": "/docs",
            "endpoints": [
                "GET  /api/health",
                "GET  /api/materials",
                "POST /api/predict",
                "POST /api/simulate",
                "POST /api/optimize",
            ],
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("vanl.backend.main:app", host="0.0.0.0", port=8000, reload=True)
