@echo off
REM RĀMAN Studio Startup Script
REM Uses Python 3.13 virtual environment with NVIDIA ALCHEMI support

echo ============================================================
echo RĀMAN Studio - The Digital Twin for Your Potentiostat
echo VidyuthLabs - https://vidyuthlabs.co.in
echo ============================================================
echo.

REM Activate Python 3.13 virtual environment
echo [1/3] Activating Python 3.13 environment...
call .venv313\Scripts\activate.bat

REM Check if NVIDIA ALCHEMI is installed
echo [2/3] Checking NVIDIA ALCHEMI installation...
python -c "import nvalchemi; print('✓ NVIDIA ALCHEMI:', nvalchemi.__version__)" 2>nul
if errorlevel 1 (
    echo ⚠ NVIDIA ALCHEMI not installed yet
    echo Installing NVIDIA ALCHEMI toolkit...
    pip install nvalchemi-toolkit ase
)

REM Start the server
echo [3/3] Starting RĀMAN Studio server...
echo.
echo Server will be available at: http://localhost:8001
echo API Documentation: http://localhost:8001/docs
echo.
echo Press Ctrl+C to stop the server
echo.

python -m uvicorn vanl.backend.main:app --reload --port 8001

pause
