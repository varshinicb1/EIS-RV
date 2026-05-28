# RĀMAN Studio - Quick Start Guide

## 🚀 Fastest Way to Start

### Option 1: Double-Click Startup (Recommended)
1. Double-click `START_APP.bat`
2. Wait for both servers to start
3. Browser will open automatically at http://localhost:5173

**That's it!** The app is now running.

---

## 🔧 Manual Startup (Alternative)

### Step 1: Start Backend
```bash
# Open Terminal 1
cd c:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV
python -m uvicorn src.backend.api.server:app --reload --port 8000
```

**Expected Output**:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 2: Start Frontend
```bash
# Open Terminal 2
cd c:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV\src\frontend
npm run dev
```

**Expected Output**:
```
  VITE v6.0.6  ready in 1234 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

### Step 3: Open Browser
Navigate to: **http://localhost:5173**

---

## ✅ Verify Everything Works

### 1. Check Backend is Running
Open: http://localhost:8000/docs

**Expected**: Swagger API documentation page

### 2. Check Frontend is Running
Open: http://localhost:5173

**Expected**: RĀMAN Studio interface loads

### 3. Check API Connection
1. Open RĀMAN Studio (http://localhost:5173)
2. Look at bottom status bar
3. Should show: "Backend online · X routes"

**If you see "Backend offline"**: Backend is not running or wrong port

---

## 🎯 First-Time Setup

### 1. Install Frontend Dependencies (First Time Only)
```bash
cd src\frontend
npm install
```

**This installs**:
- React 19
- Vite (dev server)
- Three.js (3D graphics)
- Lucide icons
- jsPDF (report generation)
- And more...

### 2. Install Backend Dependencies (First Time Only)
```bash
pip install -r requirements.txt
```

**This installs**:
- FastAPI
- Uvicorn
- NumPy, SciPy
- Plotly
- And more...

---

## 📊 What You Should See

### Backend Terminal
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### Frontend Terminal
```
  VITE v6.0.6  ready in 1234 ms
  ➜  Local:   http://localhost:5173/
```

### Browser
- RĀMAN Studio interface
- Dark theme by default
- Sidebar with panels
- Status bar at bottom showing "Backend online"

---

## 🧪 Quick Test

### Test 1: Run EIS Simulation
1. Click "EIS" in sidebar
2. Use default parameters
3. Click "Run Simulation"
4. **Expected**: Nyquist and Bode plots appear with **white backgrounds**

### Test 2: Save Your Profile
1. Click ⚙️ icon (top-right)
2. Enter your name and organization
3. Click "Save profile"
4. Refresh page (F5)
5. **Expected**: Your data is still there

### Test 3: Create a Project
1. Click "Workspace" in sidebar
2. Click "+ New"
3. Create "Test Project"
4. Refresh page (F5)
5. **Expected**: Project is still there

---

## 🐛 Troubleshooting

### Problem: "Backend offline" message

**Solution 1**: Check if backend is running
```bash
# Should show Python process
tasklist | findstr python
```

**Solution 2**: Restart backend
```bash
# Terminal 1
python -m uvicorn src.backend.api.server:app --reload --port 8000
```

**Solution 3**: Check port 8000 is not in use
```bash
netstat -ano | findstr :8000
```

---

### Problem: Frontend won't start

**Solution 1**: Install dependencies
```bash
cd src\frontend
npm install
```

**Solution 2**: Clear cache and restart
```bash
npm run dev -- --force
```

**Solution 3**: Check port 5173 is not in use
```bash
netstat -ano | findstr :5173
```

---

### Problem: "Module not found" errors

**Solution**: Install missing dependencies
```bash
# Backend
pip install -r requirements.txt

# Frontend
cd src\frontend
npm install
```

---

### Problem: Plots not showing

**Cause**: Canvas rendering issue

**Solution**: 
1. Hard refresh: Ctrl+Shift+R
2. Clear browser cache
3. Check browser console (F12) for errors

---

### Problem: Data not persisting

**Cause**: Browser in private/incognito mode

**Solution**: Use normal browser window

---

## 📁 Important URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend** | http://localhost:5173 | Main application |
| **Backend** | http://localhost:8000 | API server |
| **API Docs** | http://localhost:8000/docs | Swagger documentation |
| **ReDoc** | http://localhost:8000/redoc | Alternative API docs |
| **Health Check** | http://localhost:8000/api/health | Backend status |

---

## 🔑 Environment Variables

### Backend (.env file)
Create `.env` in project root:

```env
# Optional: NVIDIA NIM API Key for AI features
NVIDIA_API_KEY=nvapi-your-key-here

# Optional: Custom port
PORT=8000

# Optional: Log level
LOG_LEVEL=INFO
```

### Frontend (No .env needed)
Frontend automatically connects to `http://localhost:8000`

---

## 💾 Data Storage

### LocalStorage (Browser)
- User profile
- Theme preference
- Projects
- Saved analyses
- Reports history

**Location**: Browser → DevTools (F12) → Application → Local Storage

### Backend Files
- NVIDIA API key: `.env` file
- Uploaded data: `data/` folder
- Simulation cache: Memory (temporary)

---

## 🎨 Features to Test

### ✅ Simulations
- EIS (Electrochemical Impedance Spectroscopy)
- CV (Cyclic Voltammetry)
- Battery (Charge-Discharge)
- GCD (Galvanostatic Charge-Discharge)
- DRT (Distribution of Relaxation Times)
- Biosensor Design

### ✅ Materials
- Materials Explorer (48 materials database)
- Material Discovery (AI-powered)
- Alchemist Canvas (Interactive)
- Synthesis Animator

### ✅ Lab Tools
- Lab Data Import
- Data Cleaner
- Real Lab Data Analysis

### ✅ AI Features
- Alchemi AI (Material recommendations)
- Literature Mining
- Paper Validation

### ✅ Reports
- IEEE-formatted PDF generation
- Publication-ready plots
- Export to CSV/JSON

---

## 🚀 You're Ready!

1. **Start**: Double-click `START_APP.bat` OR run manually
2. **Test**: Follow the Quick Test section above
3. **Explore**: Try all the panels and features
4. **Save**: Everything persists automatically

**Need Help?** Check `TESTING_GUIDE.md` for detailed testing instructions.

---

## 📞 Support

If you encounter issues:
1. Check the Troubleshooting section above
2. Review `TESTING_GUIDE.md`
3. Check browser console (F12) for errors
4. Check backend terminal for error messages

---

**Happy Testing! 🎉**

