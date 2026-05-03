# ---- Build Frontend ----
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY src/frontend/package*.json ./src/frontend/
RUN cd src/frontend && npm install
COPY src/frontend/ ./src/frontend/
RUN cd src/frontend && npm run build

# ---- Python backend (FastAPI + C++ engine) ----
FROM python:3.12-slim
WORKDIR /app

# System deps for C++ engine compilation at image-build time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libssl-dev \
    libeigen3-dev \
    pybind11-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn uvicorn

# Application source
COPY engine_core/ ./engine_core/
COPY src/ ./src/
COPY data/ ./data/
COPY scripts/ ./scripts/

# Build the C++ engine and put the bindings on PYTHONPATH
RUN mkdir -p engine_core/build \
    && cd engine_core/build \
    && cmake .. -DCMAKE_BUILD_TYPE=Release -DRAMAN_BUILD_TESTS=OFF \
    && cmake --build . -j"$(nproc)"

# Compiled frontend assets
COPY --from=frontend-builder /app/src/frontend/dist ./static

ENV PYTHONPATH=/app:/app/engine_core/build \
    PORT=8000 \
    ENVIRONMENT=production \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Production entrypoint — single canonical FastAPI app under src/.
CMD ["gunicorn", "src.backend.api.server:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-"]
