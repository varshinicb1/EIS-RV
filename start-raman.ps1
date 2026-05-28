#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start RĀMAN Studio full stack (backend + frontend)

.DESCRIPTION
    Starts the FastAPI backend server and Vite frontend dev server.
    Both run in the background and logs are displayed.

.PARAMETER Port
    Backend port (default: 8000)

.PARAMETER FrontendPort
    Frontend port (default: 5173)

.PARAMETER NoBrowser
    Don't open browser automatically

.EXAMPLE
    .\start-raman.ps1
    Start with default ports (backend: 8000, frontend: 5173)

.EXAMPLE
    .\start-raman.ps1 -Port 8080 -FrontendPort 3000
    Start with custom ports

.EXAMPLE
    .\start-raman.ps1 -NoBrowser
    Start without opening browser
#>

param(
    [int]$Port = 8000,
    [int]$FrontendPort = 5173,
    [switch]$NoBrowser
)

# Get script directory (project root)
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                              ║" -ForegroundColor Cyan
Write-Host "║              RĀMAN Studio - Full Stack Launcher              ║" -ForegroundColor Cyan
Write-Host "║                                                              ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found! Please install Python 3.8+" -ForegroundColor Red
    exit 1
}

# Check if Node.js is installed
Write-Host "[2/4] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "  ✓ Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Node.js not found! Please install Node.js 18+" -ForegroundColor Red
    exit 1
}

# Start backend server
Write-Host "[3/4] Starting backend server..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($root, $port)
    Set-Location $root
    python -m uvicorn src.backend.api.server:app --host 127.0.0.1 --port $port --reload
} -ArgumentList $ProjectRoot, $Port

Write-Host "  ✓ Backend starting on http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "  ✓ Job ID: $($backendJob.Id)" -ForegroundColor Gray

# Wait for backend to start
Write-Host "  ⏳ Waiting for backend to be ready..." -ForegroundColor Gray
Start-Sleep -Seconds 3

# Check if backend is running
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "  ✓ Backend is ready!" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Backend may still be starting..." -ForegroundColor Yellow
}

# Start frontend dev server
Write-Host "[4/4] Starting frontend dev server..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    param($root, $port)
    Set-Location "$root/src/frontend"
    npm run dev -- --port $port
} -ArgumentList $ProjectRoot, $FrontendPort

Write-Host "  ✓ Frontend starting on http://localhost:$FrontendPort" -ForegroundColor Green
Write-Host "  ✓ Job ID: $($frontendJob.Id)" -ForegroundColor Gray

# Wait for frontend to start
Write-Host "  ⏳ Waiting for frontend to be ready..." -ForegroundColor Gray
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                                                              ║" -ForegroundColor Green
Write-Host "║                    🚀 RĀMAN Studio Ready!                    ║" -ForegroundColor Green
Write-Host "║                                                              ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend:  http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:$FrontendPort" -ForegroundColor Cyan
Write-Host "  API Docs: http://127.0.0.1:$Port/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend Job ID:  $($backendJob.Id)" -ForegroundColor Gray
Write-Host "  Frontend Job ID: $($frontendJob.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers" -ForegroundColor Yellow
Write-Host ""

# Open browser
if (-not $NoBrowser) {
    Write-Host "Opening browser..." -ForegroundColor Gray
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:$FrontendPort"
}

# Monitor jobs and display logs
Write-Host "═══════════════════════ LOGS ═══════════════════════════" -ForegroundColor Cyan
Write-Host ""

try {
    while ($true) {
        # Check if jobs are still running
        $backendState = (Get-Job -Id $backendJob.Id).State
        $frontendState = (Get-Job -Id $frontendJob.Id).State

        if ($backendState -eq "Failed" -or $frontendState -eq "Failed") {
            Write-Host ""
            Write-Host "⚠ One or more servers failed!" -ForegroundColor Red
            
            if ($backendState -eq "Failed") {
                Write-Host ""
                Write-Host "Backend Error:" -ForegroundColor Red
                Receive-Job -Id $backendJob.Id
            }
            
            if ($frontendState -eq "Failed") {
                Write-Host ""
                Write-Host "Frontend Error:" -ForegroundColor Red
                Receive-Job -Id $frontendJob.Id
            }
            
            break
        }

        # Display new output
        $backendOutput = Receive-Job -Id $backendJob.Id
        $frontendOutput = Receive-Job -Id $frontendJob.Id

        if ($backendOutput) {
            $backendOutput | ForEach-Object {
                Write-Host "[Backend]  $_" -ForegroundColor Blue
            }
        }

        if ($frontendOutput) {
            $frontendOutput | ForEach-Object {
                Write-Host "[Frontend] $_" -ForegroundColor Magenta
            }
        }

        Start-Sleep -Milliseconds 500
    }
} finally {
    # Cleanup on exit
    Write-Host ""
    Write-Host "Stopping servers..." -ForegroundColor Yellow
    
    Stop-Job -Id $backendJob.Id -ErrorAction SilentlyContinue
    Stop-Job -Id $frontendJob.Id -ErrorAction SilentlyContinue
    
    Remove-Job -Id $backendJob.Id -Force -ErrorAction SilentlyContinue
    Remove-Job -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue
    
    Write-Host "✓ All servers stopped" -ForegroundColor Green
}
