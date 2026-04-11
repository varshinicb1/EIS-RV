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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.routes import router
from .api.pe_routes import router as pe_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="VANL — Virtual Autonomous Nanomaterials Lab",
    description=(
        "Physics-informed digital twin platform for printed electronics: "
        "supercapacitors, batteries, sensors, biosensors. "
        "Ink formulation → printing → device simulation → characterization."
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

# API routes — core electrochemistry
app.include_router(router)
# API routes — printed electronics digital twin
app.include_router(pe_router)

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
