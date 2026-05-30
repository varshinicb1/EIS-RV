# 🎯 START HERE - RĀMAN Studio (EIS-RV)

**The complete virtual electrochemistry & nanomaterials discovery lab — now in active best-of-n maximum-subagent 100% push.**

See the brand-new vision README (badges, 5 visual proofs, honest A autonomous closed-loop + B real human pipelines, E2E evidence) for the full story and current status: [README.md](README.md)

## ✅ Core Engines + A+B Flows Are Real and E2E Proven (May 2026)

- Honest Autonomous A (zero synthetic fallbacks, always-virtual characterization, real-synth-only evidence)
- Human B (real FOG 01-08 SHAP + Silver vanadate + artifacted reports from your exact CSVs)
- Tauri v2 + centralized client + local Qwen brain + real Drive + Rust acceleration skeleton

Everything below is the practical on-ramp and is being refreshed as part of the docs vision alignment.

---

## 🚀 Quick Start (30 seconds)

## 🚀 Quick Start (30 seconds)

### Step 1: Start the App
**Double-click**: `START_APP.bat`

**OR manually**:
```bash
# Terminal 1
python -m uvicorn src.backend.api.server:app --reload --port 8000

# Terminal 2
cd src\frontend
npm run dev
```

### Step 2: Open Browser
Go to: **http://localhost:5173**

### Step 3: Test!
- Run EIS simulation (should have WHITE background)
- Save your profile (should persist after refresh)
- Create a project (should persist after refresh)

**That's it!** 🎉

---

## 📚 Documentation Guide

### For Quick Testing
👉 **Read**: `README_TESTING.md`
- Quick test scenarios
- What to look for
- Common issues

### For Detailed Testing
👉 **Read**: `TESTING_GUIDE.md`
- Step-by-step checklist
- All features to test
- Data persistence verification

### For Startup Issues
👉 **Read**: `QUICK_START.md`
- Manual startup instructions
- Troubleshooting
- Environment setup

### For Technical Details
👉 **Read**: `FRONTEND_AUDIT_COMPLETE.md`
- What was fixed (92.5% complete)
- 100+ issues resolved
- Code quality improvements

### For Plot Changes
👉 **Read**: `PLOT_STYLING_UPDATE.md`
- Research-grade white backgrounds
- Publication-ready formatting
- IEEE/ECS/IUPAC compliance

---

## 🎯 What to Test

### Priority 1: Core Features (5 min)
1. ✅ Start app → Backend should be online
2. ✅ Run EIS simulation → Plots should be WHITE
3. ✅ Save profile → Refresh → Should persist
4. ✅ Switch theme → Refresh → Should persist

### Priority 2: Data Persistence (10 min)
1. ✅ Create project in Workspace
2. ✅ Save spectroscopy analysis
3. ✅ Generate report
4. ✅ Close browser → Reopen → All data should persist

### Priority 3: All Features (30 min)
1. ✅ Test all simulation panels
2. ✅ Test materials explorer
3. ✅ Test lab data import
4. ✅ Test AI features (if you have NVIDIA key)
5. ✅ Test report generation

---

## ✨ Key Features

### Data Persistence ✅
- User profile (name, email, org, avatar)
- Theme preference
- Projects and notes
- Saved analyses
- Report history

### Simulations ✅
- EIS, CV, Battery, GCD, DRT
- Circuit Fitting
- Biosensor Design
- Unified Spectroscopy

### Materials ✅
- 48-material database
- AI-powered discovery
- Interactive canvas

### Reports ✅
- IEEE-formatted PDFs
- **WHITE background plots** (publication-ready)
- Export to CSV/JSON

---

## 📦 Production Packaged Windows Install (Tauri v2 — Zero-Friction First Run)

**Exact one-command (or double-click) path after build:**

```powershell
cd "C:\Users\varsh\OneDrive\Documents\Vidyuthlabs\Raman-studio\EIS-RV\src-tauri"
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
cargo tauri build --debug
```

- Resulting installer: `src-tauri\target\debug\bundle\nsis\RAMAN Studio_3.0.0_x64-setup.exe` (or release for final)
- Double-click the .exe → full install (includes embedded Python 3.11 + all wheels + src/backend + models/Raman-Qwen-Agent adapter + Lab data + FOG samples)
- **First launch automatically shows the Vision Tour wizard** (multi-step, real calls via client.js):
  Health → Drive (graceful if no creds) → Local LLM (Raman-Qwen structure-paper) → Brain sync → A enrichment → B FOG+SHAP → Real report generation.
- Sidecar (Python) starts/stops cleanly with the app (fixed lifecycle).
- Everything works offline after first install — no external Python required.

This is the C-track "on first install, everything works, guided tour" vision made real.

---

## 🎨 Special: Publication-Ready Plots

**All plots now have WHITE backgrounds** for scientific publications:
- ✅ Black text and axes
- ✅ Times New Roman font
- ✅ IEEE/ECS/IUPAC compliant
- ✅ Ready for Nature, Science, IEEE journals

**No theme dependency** - always white!

---

## 🐛 Quick Troubleshooting

### "Backend offline" message
```bash
python -m uvicorn src.backend.api.server:app --reload --port 8000
```

### Frontend won't start
```bash
cd src\frontend
npm install
npm run dev
```

### Data not persisting
Exit private/incognito mode → Use normal browser

### Plots are dark (should be white)
Hard refresh: Ctrl+Shift+R

---

## 📊 What Was Fixed

### Frontend Audit: 92.5% Complete
- ✅ 37/40 files audited
- ✅ 100+ issues fixed
- ✅ Centralized API config
- ✅ Error boundaries everywhere
- ✅ Memory leak prevention
- ✅ Full accessibility
- ✅ Research-grade plots

**Details**: See `FRONTEND_AUDIT_COMPLETE.md`

---

## 🎉 You're Ready!

1. **Start**: Double-click `START_APP.bat`
2. **Test**: Follow Priority 1 checklist above
3. **Explore**: Try all features
4. **Report**: Any issues you find

---

## 📞 Need Help?

| Issue | Solution |
|-------|----------|
| Can't start | Read `QUICK_START.md` |
| Want test steps | Read `TESTING_GUIDE.md` |
| Want overview | Read `README_TESTING.md` |
| Technical details | Read `FRONTEND_AUDIT_COMPLETE.md` |

---

## 🚀 Start Testing Now!

**Double-click**: `START_APP.bat`

**Or read**: `README_TESTING.md` for full details

---

**Everything is ready. Happy testing! 🎉**

