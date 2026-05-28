# 🚨 CRITICAL: Production-Grade Fixes Needed

**Date:** May 5, 2026  
**Priority:** HIGH  
**Status:** URGENT

---

## ⚠️ Critical Issues Found

### 1. Plot Not Showing Processed Data
**Problem:** Plot displays raw intensity instead of baseline-corrected data  
**Impact:** Users cannot see the effect of analysis  
**Root Cause:** Frontend not properly using `corrected_intensity` from backend

**Fix Required:**
```javascript
// In renderSpectrumPlot function
const displayIntensity = corrected_intensity?.length ? corrected_intensity : intensity;

// Add visual indicator
if (corrected_intensity?.length) {
  ctx.fillText('✓ PROCESSED DATA', pad.l, 35);
} else {
  ctx.fillText('⚠ RAW DATA', pad.l, 35);
}
```

---

### 2. Data Persistence Lost
**Problem:** User profile pictures and settings are lost on refresh  
**Impact:** Poor user experience, data loss  
**Root Cause:** No localStorage implementation

**Fix Required:**
```javascript
// Add localStorage keys
const STORAGE_KEYS = {
  ANALYSES: 'raman-saved-analyses',
  LAST_ANALYSIS: 'raman-last-analysis',
  USER_PROFILE: 'raman-profile',
  SETTINGS: 'raman-settings',
};

// Save on every analysis
localStorage.setItem(STORAGE_KEYS.LAST_ANALYSIS, JSON.stringify({
  result: data,
  options: { cosmicRay, fourier, voigt },
  timestamp: Date.now(),
}));

// Restore on mount
useEffect(() => {
  const lastAnalysis = localStorage.getItem(STORAGE_KEYS.LAST_ANALYSIS);
  if (lastAnalysis) {
    const data = JSON.parse(lastAnalysis);
    setResult(data.result);
  }
}, []);
```

---

### 3. No Save Analysis Feature
**Problem:** Users cannot save their analyses  
**Impact:** Work is lost, no way to compare analyses  
**Root Cause:** Feature not implemented

**Fix Required:**
```javascript
// Add save function
const saveAnalysis = () => {
  const analysis = {
    id: Date.now(),
    name: analysisName || `Analysis_${new Date().toLocaleString()}`,
    result,
    options: { cosmicRay, fourier, voigt },
    timestamp: Date.now(),
    fileName: file?.name,
  };
  
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEYS.ANALYSES) || '[]');
  saved.push(analysis);
  localStorage.setItem(STORAGE_KEYS.ANALYSES, JSON.stringify(saved));
};

// Add load function
const loadAnalysis = (analysis) => {
  setResult(analysis.result);
  setCosmicRay(analysis.options.cosmicRay);
  setFourier(analysis.options.fourier);
  setVoigt(analysis.options.voigt);
};
```

---

### 4. No Visual Comparison
**Problem:** Users cannot see difference between raw and processed data  
**Impact:** Cannot verify that processing is working  
**Root Cause:** No comparison view

**Fix Required:**
```javascript
// Add toggle for raw data overlay
const [showRawData, setShowRawData] = useState(false);

// In plot rendering
if (showRawData && intensity) {
  // Draw raw data in orange
  ctx.strokeStyle = '#ff9500';
  ctx.lineWidth = 1;
  ctx.setLineDash([5, 5]);
  wavenumber.forEach((wn, i) => {
    if (i === 0) ctx.moveTo(toX(wn), toY(intensity[i]));
    else ctx.lineTo(toX(wn), toY(intensity[i]));
  });
  ctx.stroke();
  ctx.setLineDash([]);
}
```

---

### 5. Backend Not Processing Requests
**Problem:** No analysis requests in backend logs  
**Impact:** Analysis not happening  
**Root Cause:** Possible CORS issue or frontend not sending requests

**Fix Required:**
```python
# In server.py, add CORS middleware
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    return response
```

---

## 🔧 Implementation Steps

### Step 1: Fix Plot Rendering (HIGH PRIORITY)
1. Open `UnifiedSpectroscopyPanel.jsx`
2. Find `renderSpectrumPlot` function
3. Change line that sets `displayIntensity`:
   ```javascript
   const displayIntensity = corrected_intensity?.length ? corrected_intensity : intensity;
   ```
4. Add visual indicator showing which data is displayed
5. Test with FO.txt file

### Step 2: Add Data Persistence (HIGH PRIORITY)
1. Add localStorage keys at top of file
2. Add `useEffect` to restore last analysis on mount
3. Save analysis result to localStorage after every analysis
4. Test by refreshing page - data should persist

### Step 3: Add Save/Load Feature (MEDIUM PRIORITY)
1. Add state for saved analyses
2. Add save dialog with name input
3. Add load dialog showing saved analyses
4. Add delete function
5. Test saving and loading multiple analyses

### Step 4: Add Visual Comparison (MEDIUM PRIORITY)
1. Add checkbox "Show raw data (compare)"
2. Modify plot rendering to overlay raw data in orange
3. Add legend showing which line is which
4. Test toggling on/off

### Step 5: Fix Backend Logging (LOW PRIORITY)
1. Add CORS middleware
2. Add request logging middleware
3. Verify requests are being received
4. Check analysis is actually running

---

## 📊 Testing Checklist

### Plot Rendering
- [ ] Upload FO.txt
- [ ] Verify plot shows baseline-corrected data
- [ ] Enable cosmic ray removal
- [ ] Verify "CR" appears in metadata
- [ ] Enable Fourier filtering
- [ ] Verify "FFT" appears in metadata
- [ ] Enable Voigt fitting
- [ ] Verify "Voigt" appears in metadata
- [ ] Toggle "Show raw data"
- [ ] Verify orange overlay appears

### Data Persistence
- [ ] Upload file and analyze
- [ ] Refresh page
- [ ] Verify analysis is still visible
- [ ] Change theme
- [ ] Refresh page
- [ ] Verify theme persists

### Save/Load
- [ ] Analyze spectrum
- [ ] Click "Save Analysis"
- [ ] Enter name
- [ ] Click Save
- [ ] Upload different file
- [ ] Click "Load Analysis"
- [ ] Select saved analysis
- [ ] Verify original analysis loads

### Backend
- [ ] Check backend logs for POST requests
- [ ] Verify analysis is running
- [ ] Check response contains corrected_intensity
- [ ] Verify peaks are detected

---

## 🎯 Expected Results After Fixes

### Plot Display
```
Before: Raw noisy data with baseline
After: Clean baseline-corrected data
Metadata: "1000 pts · 14 peaks · Corrected · CR · FFT · Voigt"
```

### Data Persistence
```
Before: All data lost on refresh
After: Last analysis restored automatically
```

### Save/Load
```
Before: No way to save analyses
After: Save with custom names, load anytime
```

### Visual Comparison
```
Before: Cannot see difference
After: Raw data (orange) vs Processed data (blue)
```

---

## 🚀 Quick Fix Script

Create this file as `fix-production.js` in `src/frontend/src/components/simulation/`:

```javascript
// Quick fixes for production issues

// 1. Fix plot rendering
export const fixPlotRendering = (result) => {
  // Always use corrected_intensity if available
  const displayIntensity = result.corrected_intensity?.length 
    ? result.corrected_intensity 
    : result.intensity;
  
  const isProcessed = result.corrected_intensity?.length > 0;
  
  return { displayIntensity, isProcessed };
};

// 2. Fix data persistence
export const saveToLocalStorage = (key, data) => {
  try {
    localStorage.setItem(key, JSON.stringify(data));
    return true;
  } catch (e) {
    console.error('Failed to save:', e);
    return false;
  }
};

export const loadFromLocalStorage = (key) => {
  try {
    const data = localStorage.getItem(key);
    return data ? JSON.parse(data) : null;
  } catch (e) {
    console.error('Failed to load:', e);
    return null;
  }
};

// 3. Fix save analysis
export const saveAnalysis = (result, options, fileName) => {
  const analysis = {
    id: Date.now(),
    name: `Analysis_${new Date().toLocaleString()}`,
    result,
    options,
    fileName,
    timestamp: Date.now(),
  };
  
  const saved = loadFromLocalStorage('raman-saved-analyses') || [];
  saved.push(analysis);
  saveToLocalStorage('raman-saved-analyses', saved);
  
  return analysis;
};
```

---

## 📝 Code Changes Summary

### Files to Modify

1. **UnifiedSpectroscopyPanel.jsx** (CRITICAL)
   - Line ~15: Add localStorage keys
   - Line ~50: Add saved analyses state
   - Line ~70: Add useEffect for data restoration
   - Line ~150: Fix displayIntensity logic
   - Line ~200: Add save/load functions
   - Line ~400: Add save/load UI

2. **server.py** (IMPORTANT)
   - Line ~20: Add CORS middleware
   - Line ~30: Add request logging
   - Line ~40: Verify unified spectroscopy routes

3. **unified_spectroscopy_routes.py** (VERIFY)
   - Line ~100: Verify corrected_intensity is returned
   - Line ~150: Add logging for analysis requests

---

## ⚠️ Disk Space Warning

**CRITICAL:** C: drive has only 10MB free space!

**Immediate Actions:**
1. Clean temp files: `cleanmgr /d C:`
2. Delete old logs
3. Move large files to D: drive
4. Free up at least 1GB before continuing

---

## 🎉 Success Criteria

After implementing all fixes:

✅ Plot shows baseline-corrected data  
✅ "Corrected" appears in plot metadata  
✅ Analysis options (CR, FFT, Voigt) are visible  
✅ Data persists across page refreshes  
✅ Can save and load analyses  
✅ Can compare raw vs processed data  
✅ Backend logs show analysis requests  
✅ User profile persists  

---

**Priority:** URGENT  
**Estimated Time:** 2-3 hours  
**Impact:** HIGH - Critical for production use

**Next Steps:**
1. Free up disk space (IMMEDIATE)
2. Implement fixes in order of priority
3. Test each fix thoroughly
4. Deploy to production

---

**Report Generated:** May 5, 2026  
**Status:** AWAITING IMPLEMENTATION  
**Severity:** CRITICAL
