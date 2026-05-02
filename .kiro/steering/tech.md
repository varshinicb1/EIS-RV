# Technology Stack

## VANL Backend

### Core Technologies
- **Python**: 3.10+ (3.11 recommended)
- **Web Framework**: FastAPI 0.100+
- **Server**: Uvicorn (ASGI server)
- **Production Server**: Gunicorn with Uvicorn workers

### Key Dependencies
- **NumPy**: 1.24+ (numerical computing)
- **SciPy**: Scientific computing and optimization
- **Plotly**: Interactive visualization
- **Pydantic**: Data validation and settings management

### Testing
- **pytest**: Unit testing framework
- Test suite location: `vanl/backend/tests/`
- 30+ unit tests covering core engines

### API Structure
- RESTful API with automatic OpenAPI/Swagger documentation
- Core endpoints: `/api/routes.py`
- Printed electronics endpoints: `/api/pe_routes.py`
- Interactive docs available at `/docs` and `/redoc`

## AnalyteX MicroWell Designer

### Core Technologies
- **Python**: 3.10+ (3.11 recommended)
- **CAD Kernel**: CadQuery 2.4+ (OpenCascade wrapper)
- **GUI Framework**: PyQt6 6.5+
- **3D Visualization**: pyqtgraph 0.13+ with PyOpenGL 3.1+
- **Numerical**: NumPy 1.24+

### Installation Methods
1. **Conda (Recommended)**: `conda env create -f environment.yml`
2. **pip**: `pip install -r requirements.txt`

## Common Commands

### VANL Development
```bash
# Start development server (auto-reload)
python -m uvicorn vanl.backend.main:app --reload --port 8000

# Alternative entry point
python vanl/backend/main.py

# Run tests
python -m pytest vanl/backend/tests/test_core.py -v
python -m pytest vanl/backend/tests/ -v

# Generate datasets
python -c "from vanl.backend.core.dataset_gen import generate_and_save_datasets; generate_and_save_datasets()"
```

### AnalyteX MicroWell Designer
```bash
# Launch GUI application
cd analytex_microwell_designer
python main.py

# Headless STEP generation (no GUI)
python generate_example.py
```

### Docker Deployment
```bash
# Build image
docker build -t vanl:latest .

# Run container
docker run -p 8000:8000 vanl:latest

# Docker Compose
docker-compose up
```

### Cloud Deployment
```bash
# Google Cloud Run (uses app.yaml)
gcloud run deploy vanl --source .

# Health check endpoint
curl http://localhost:8000/api/health
```

## Development Environment

### Platform Support
- **Primary**: Windows (bash shell)
- **Supported**: Linux, macOS
- **High-DPI**: Automatic scaling enabled for Qt applications

### Environment Variables
- `PYTHONUNBUFFERED=1`: Unbuffered output for logging
- `LOG_LEVEL=INFO`: Logging verbosity
- `QT_ENABLE_HIGHDPI_SCALING=1`: High-DPI support for Qt

### Code Quality
- UTF-8 encoding enforced on Windows
- Type hints used throughout (Pydantic models)
- Comprehensive error handling with validation
- Physics model references documented in docstrings
