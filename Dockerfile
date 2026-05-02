# ---- Build Frontend ----
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY src/frontend/package*.json ./src/frontend/
RUN cd src/frontend && npm install
COPY src/frontend/ ./src/frontend/
RUN cd src/frontend && npm run build

# ---- Python Environment (Backend + Sentinel) ----
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies (needed at runtime for on-the-fly C++ compilation)
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY vanl/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn uvicorn pytest

# Copy application source code
COPY engine_core/ ./engine_core/
COPY src/backend/ ./src/backend/
COPY vanl/ ./vanl/
COPY dev_tools/ ./dev_tools/
COPY data/ ./data/

# Compile the C++ engine initially
RUN mkdir -p engine_core/build && cd engine_core/build && cmake .. && cmake --build .

# Copy frontend static build 
COPY --from=frontend-builder /app/src/frontend/dist ./static

# Configure environment
ENV PYTHONPATH=/app:/app/engine_core/build
ENV PORT=8000
ENV ENVIRONMENT=production

# The default command will be the FastAPI backend. 
CMD ["gunicorn", "src.backend.api.server:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
