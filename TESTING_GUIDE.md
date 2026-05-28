# RĀMAN Studio - Testing Guide

## 🚀 Quick Start

Your localhost web app is **fully configured** with data persistence. Everything is saved locally in your browser.

---

## 📦 What's Already Persisted (LocalStorage)

### ✅ User Preferences
**Storage Key**: `raman-profile`
- Full name
- Email
- Organization
- Role
- Department
- ORCID
- Profile avatar (base64, up to 256KB)

**Location**: UserProfilePanel.jsx (Profile & Settings)

### ✅ Theme Preference
**Storage Key**: `raman-theme`
- Light / Dark / High-Contrast theme
- Persists across sessions

**Location**: useTheme.jsx hook

### ✅ Projects & Workspaces
**Storage Key**: `raman-projects`
- Project name
- Template type
- Creation/modification dates
- Simulations list
- Research notes
- Tags

**Location**: WorkspacePanel.jsx

### ✅ Spectroscopy Analyses
**Storage Keys**: 
- `raman-spectroscopy-last-analysis` - Last analysis
- `raman-spectroscopy-analyses` - Saved analyses library

**Location**: UnifiedSpectroscopyPanel.jsx

### ✅ Materials Selection
**Storage Key**: `raman-alchemist-selected`
- Selected materials in Alchemist Canvas

**Location**: AlchemistCanvas.jsx

### ✅ Generated Reports
**Storage Key**: `raman_reports`
- Report history (up to 50 reports)
- Report metadata
- Generation timestamps

**Location**: ReportsPanel.jsx

### ✅ Notification Preferences
**Storage Key**: `raman-profile` (nested)
- Email digest
- Simulation complete
- System alerts
- Weekly report

**Location**: UserProfilePanel.jsx

---

## 🔑 API Key Storage (Backend)

### NVIDIA NIM API Key
**Storage**: Backend `.env` file (NOT localStorage for security)
**Endpoint**: `/api/v2/settings/nvidia-key`
**Location**: UserProfilePanel.jsx

**How it works**:
1. User enters key in Profile panel
2. Key is validated against NVIDIA API
3. Key is saved to backend `.env` file
4. Backend uses key for AI features

---

## 🧪 Testing Checklist

### 1. Start the Application

```bash
# Terminal 1: Start Backend
cd c:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV
python -m uvicorn src.backend.api.server:app --reload --port 8000

# Terminal 2: Start Frontend
cd src/frontend
npm install  # First time only
npm run dev
```

**Expected**: 
- Backend: http://localhost:8000
- Frontend: http://localhost:5173 (or similar)

---

### 2. Test User Profile Persistence

**Steps**:
1. Navigate to Profile panel (⚙️ icon in top-right)
2. Fill in your details:
   - Name: "Dr. Varshini C.B."
   - Email: your email
   - Organization: "VidyuthLabs"
   - Role: "Research Scientist"
3. Click "Save profile"
4. **Refresh the page** (F5)
5. Navigate back to Profile panel

**Expected**: ✅ All your data should still be there

---

### 3. Test Theme Persistence

**Steps**:
1. Click theme toggle in top-right (☀️/🌙/👁️ icon)
2. Switch to Dark theme
3. **Refresh the page** (F5)

**Expected**: ✅ Dark theme should persist

---

### 4. Test Project Persistence

**Steps**:
1. Navigate to Workspace panel
2. Click "+ New" project
3. Create a project:
   - Name: "Test EIS Study"
   - Template: "EIS Study"
4. Click "Create Project"
5. Add some notes in the "Research Notes" section
6. **Refresh the page** (F5)
7. Navigate back to Workspace panel

**Expected**: ✅ Your project should still be there with notes

---

### 5. Test NVIDIA API Key (Optional)

**Steps**:
1. Navigate to Profile panel
2. Scroll to "AI provider · NVIDIA NIM" section
3. Enter your NVIDIA API key (starts with `nvapi-`)
4. Click "Validate"
5. If valid, click "Save key"
6. **Restart the backend** (Ctrl+C, then restart)

**Expected**: ✅ Key should be saved in `.env` file

**Verify**:
```bash
# Check .env file
type .env
# Should see: NVIDIA_API_KEY=nvapi-...
```

---

### 6. Test Simulation Data Persistence

**Steps**:
1. Navigate to EIS panel
2. Run a simulation with default parameters
3. Navigate to Spectroscopy panel
4. Run an analysis
5. Click "Save Analysis" and give it a name
6. **Refresh the page** (F5)
7. Navigate back to Spectroscopy panel
8. Check "Saved Analyses" section

**Expected**: ✅ Your saved analysis should be there

---

### 7. Test Report Generation

**Steps**:
1. Navigate to Reports panel
2. Fill in report details:
   - Template: "EIS analysis report"
   - Title: "Test Report"
   - Authors: Your name
3. Click "EXECUTE_COMPILATION"
4. Wait for report generation
5. **Refresh the page** (F5)
6. Navigate back to Reports panel
7. Click "ARCHIVE" tab

**Expected**: ✅ Your generated report should be in the archive

---

### 8. Test Cross-Session Persistence

**Steps**:
1. Complete steps 2-7 above
2. **Close the browser completely**
3. **Reopen the browser**
4. Navigate to http://localhost:5173
5. Check all panels (Profile, Workspace, Spectroscopy, Reports)

**Expected**: ✅ ALL data should persist across browser sessions

---

## 🔍 Debugging Data Persistence

### View Stored Data (Browser DevTools)

1. Open DevTools (F12)
2. Go to "Application" tab (Chrome) or "Storage" tab (Firefox)
3. Expand "Local Storage"
4. Click on your localhost URL
5. You should see all keys:

```
raman-profile
raman-theme
raman-projects
raman-spectroscopy-last-analysis
raman-spectroscopy-analyses
raman-alchemist-selected
raman_reports
```

### Clear All Data (Reset)

**Option 1: Browser DevTools**
1. F12 → Application → Local Storage
2. Right-click → Clear

**Option 2: Console**
```javascript
localStorage.clear()
location.reload()
```

---

## 🐛 Common Issues & Solutions

### Issue: Data Not Persisting
**Cause**: Browser in private/incognito mode
**Solution**: Use normal browser window

### Issue: API Key Not Working
**Cause**: Backend not restarted after saving key
**Solution**: Restart backend (Ctrl+C, then restart)

### Issue: "Backend offline" message
**Cause**: Backend not running
**Solution**: Start backend with `python -m uvicorn src.backend.api.server:app --reload --port 8000`

### Issue: Plots not showing
**Cause**: Frontend not built or not running
**Solution**: 
```bash
cd src/frontend
npm install
npm run dev
```

### Issue: Profile avatar not saving
**Cause**: Image too large (>256KB after compression)
**Solution**: Use smaller image or crop to smaller size

---

## 📊 Data Storage Limits

### LocalStorage Limits
- **Total**: ~5-10 MB per domain (browser-dependent)
- **Profile avatar**: Max 256 KB (enforced by app)
- **Reports**: Max 50 reports (older ones auto-deleted)
- **Projects**: Unlimited (until storage limit)

### Backend Storage
- **NVIDIA API Key**: Stored in `.env` file
- **Simulation results**: Temporary (not persisted)
- **Uploaded data**: Stored in `data/` folder

---

## ✅ Expected Behavior Summary

| Feature | Persists? | Storage | Notes |
|---------|-----------|---------|-------|
| User Profile | ✅ Yes | LocalStorage | Including avatar |
| Theme | ✅ Yes | LocalStorage | Light/Dark/HC |
| Projects | ✅ Yes | LocalStorage | With notes |
| Spectroscopy Analyses | ✅ Yes | LocalStorage | Named saves |
| Materials Selection | ✅ Yes | LocalStorage | Alchemist |
| Reports | ✅ Yes | LocalStorage | Last 50 |
| NVIDIA API Key | ✅ Yes | Backend .env | Secure |
| Simulation Results | ❌ No | Memory | Run again |
| Uploaded Files | ✅ Yes | Backend disk | In data/ |

---

## 🚀 Ready to Test!

Your app is **fully configured** for data persistence. Everything should work out of the box.

**Start Testing**:
1. Start backend: `python -m uvicorn src.backend.api.server:app --reload --port 8000`
2. Start frontend: `cd src/frontend && npm run dev`
3. Open browser: http://localhost:5173
4. Follow the testing checklist above

**Report any issues** and I'll help fix them immediately!

---

## 📝 Notes

- All data is stored **locally** in your browser
- No data is sent to external servers (except NVIDIA API for validation)
- Data persists across browser sessions
- Data is tied to the localhost domain
- Clearing browser data will clear all saved information

---

**Happy Testing! 🎉**

