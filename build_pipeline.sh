#!/bin/bash
# RĀMAN Studio — Enterprise CI/CD Build Pipeline
# Builds the Python Backend using PyInstaller, then bundles the Electron App.

set -e

echo "================================================"
echo " RĀMAN STUDIO v2.0 - CI/CD BUILD PIPELINE"
echo "================================================"

echo "[1/4] Preparing Python Environment & Dependencies..."
python3 -m pip install -r vanl/requirements.txt
python3 -m pip install pyinstaller

echo "[2/4] Building Backend Executable (PyInstaller)..."
# Build the standalone binary from the spec file
pyinstaller raman-backend.spec --clean --noconfirm

# Create the resources/backend directory if it doesn't exist
mkdir -p resources/backend

echo "[3/4] Staging Backend for Electron Builder..."
# Move the compiled backend to the resources folder where Electron expects it
if [ -d "dist/raman_backend" ]; then
    # Directory build (if PyInstaller made a folder instead of onefile)
    cp -r dist/raman_backend/* resources/backend/
elif [ -f "dist/raman_backend" ]; then
    # Onefile build (Linux/Mac)
    cp dist/raman_backend resources/backend/
elif [ -f "dist/raman_backend.exe" ]; then
    # Onefile build (Windows)
    cp dist/raman_backend.exe resources/backend/
else
    echo "❌ Error: Backend binary not found in dist/"
    exit 1
fi

echo "[4/4] Bundling Electron Application (Electron-Builder)..."
# Build frontend if needed (assuming Vite)
if [ -d "src/frontend" ]; then
    echo "  -> Building Vite Frontend..."
    cd src/frontend
    npm install
    npm run build
    cd ../..
fi

# Package via electron-builder
npm install
npm run build:all

echo "================================================"
echo "✅ BUILD COMPLETE! Output binaries in build/"
echo "================================================"
