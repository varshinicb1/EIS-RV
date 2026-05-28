# 🚀 RĀMAN Studio - Quick Start Guide

## Running the Full Stack

### Option 1: PowerShell Script (Recommended)

**From anywhere in PowerShell:**

```powershell
# Navigate to project directory
cd C:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV

# Run the launcher
.\start-raman.ps1
```

**Or create an alias to run from anywhere:**

```powershell
# Add to your PowerShell profile
function Start-Raman {
    & "C:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV\start-raman.ps1" @args
}

# Then run from anywhere:
Start-Raman
```

**Options:**
```powershell
# Custom ports
.\start-raman.ps1 -Port 8080 -FrontendPort 3000

# Don't open browser
.\start-raman.ps1 -NoBrowser

# Get help
Get-Help .\start-raman.ps1 -Full
```

---

### Option 2: Batch File (Windows CMD)

**Double-click or run from CMD:**

```cmd
cd C:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV
start-raman.bat
```

This will:
- ✅ Check Python and Node.js
- ✅ Start backend in a new window
- ✅ Start frontend in a new window
- ✅ Open browser automatically

---

### Option 3: Manual Start (Two Terminals)

**Terminal 1 - Backend:**
```powershell
cd C:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV
python -m uvicorn src.backend.api.server:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```powershell
cd C:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV\src\frontend
npm run dev
```

---

## 🌐 Access Points

Once started, access the application at:

- **Frontend (UI)**: http://localhost:5173
- **Backend API**: http://127.0.0.1:8000
- **API Documentation**: http://127.0.0.1:8000/docs
- **API Redoc**: http://127.0.0.1:8000/redoc

---

## 🛑 Stopping the Servers

### PowerShell Script
- Press `Ctrl+C` in the terminal running the script

### Batch File
- Close the "RĀMAN Backend" and "RĀMAN Frontend" windows

### Manual
- Press `Ctrl+C` in each terminal

---

## 🔧 Troubleshooting

### Backend won't start
```powershell
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Kill the process using port 8000
taskkill /PID <PID> /F

# Or use a different port
.\start-raman.ps1 -Port 8080
```

### Frontend won't start
```powershell
# Check if port 5173 is in use
netstat -ano | findstr :5173

# Kill the process
taskkill /PID <PID> /F

# Or use a different port
.\start-raman.ps1 -FrontendPort 3000
```

### Python not found
```powershell
# Check Python installation
python --version

# If not installed, download from python.org
# Make sure to check "Add Python to PATH" during installation
```

### Node.js not found
```powershell
# Check Node.js installation
node --version

# If not installed, download from nodejs.org
```

### Dependencies missing
```powershell
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd src/frontend
npm install
```

---

## 📝 Development Tips

### Hot Reload
Both backend and frontend support hot reload:
- **Backend**: Changes to `.py` files auto-reload
- **Frontend**: Changes to `.tsx/.ts/.css` files auto-reload

### Environment Variables
Create a `.env` file in the project root:
```env
NVIDIA_API_KEY=nvapi-your-key-here
JWT_SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///./raman.db
```

### Running Tests
```powershell
# Backend tests
pytest

# Frontend tests
cd src/frontend
npm test
```

### Building for Production
```powershell
# Build frontend
cd src/frontend
npm run build

# Build Electron app
npm run build:win
```

---

## 🎯 Quick Commands Reference

```powershell
# Start full stack
.\start-raman.ps1

# Start with custom ports
.\start-raman.ps1 -Port 8080 -FrontendPort 3000

# Start without browser
.\start-raman.ps1 -NoBrowser

# Backend only
python -m uvicorn src.backend.api.server:app --reload

# Frontend only
cd src/frontend && npm run dev

# Run tests
pytest                    # Backend
cd src/frontend && npm test  # Frontend

# Build production
npm run build:win         # Windows installer
npm run build:linux       # Linux packages
npm run build:mac         # macOS packages
```

---

## 📞 Support

**Company**: VidyuthLabs  
**Email**: support@vidyuthlabs.co.in  
**GitHub**: https://github.com/varshinicb1/EIS-RV

---

**Happy Coding!** 🎉
