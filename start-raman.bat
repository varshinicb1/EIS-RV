@echo off
REM RĀMAN Studio - Full Stack Launcher (Windows CMD)
REM Starts backend (FastAPI) and frontend (Vite) servers

cd /d "%~dp0"

echo ================================================================
echo.
echo              RĀMAN Studio - Full Stack Launcher
echo.
echo ================================================================
echo.

echo [1/4] Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   X Python not found! Please install Python 3.8+
    pause
    exit /b 1
)
python --version
echo   √ Python found
echo.

echo [2/4] Checking Node.js...
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   X Node.js not found! Please install Node.js 18+
    pause
    exit /b 1
)
node --version
echo   √ Node.js found
echo.

echo [3/4] Starting backend server...
start "RĀMAN Backend" cmd /k "python -m uvicorn src.backend.api.server:app --host 127.0.0.1 --port 8000 --reload"
echo   √ Backend starting on http://127.0.0.1:8000
echo   √ Check the "RĀMAN Backend" window for logs
echo.

echo   Waiting for backend to start...
timeout /t 3 /nobreak >nul
echo.

echo [4/4] Starting frontend dev server...
start "RĀMAN Frontend" cmd /k "cd src\frontend && npm run dev"
echo   √ Frontend starting on http://localhost:5173
echo   √ Check the "RĀMAN Frontend" window for logs
echo.

echo   Waiting for frontend to start...
timeout /t 5 /nobreak >nul
echo.

echo ================================================================
echo.
echo                    RĀMAN Studio Ready!
echo.
echo ================================================================
echo.
echo   Backend:  http://127.0.0.1:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://127.0.0.1:8000/docs
echo.
echo   Two new windows opened:
echo     - RĀMAN Backend  (FastAPI server)
echo     - RĀMAN Frontend (Vite dev server)
echo.
echo   Close those windows to stop the servers.
echo.
echo ================================================================
echo.

echo Opening browser...
timeout /t 2 /nobreak >nul
start http://localhost:5173

echo.
echo Press any key to exit this launcher window...
echo (The servers will keep running in their own windows)
pause >nul
