# 🚀 RĀMAN Studio v2.1.0 — Quick Start

**For**: End Users  
**Time**: 5 minutes to get started

---

## 📥 Installation

### Step 1: Download
- **File**: `RĀMAN Studio-2.1.0-Setup.exe`
- **Size**: 265.6 MB
- **Location**: `dist-electron/` folder

### Step 2: Install
1. Double-click the installer
2. **Windows SmartScreen warning?**
   - Click "More info"
   - Click "Run anyway"
3. Choose install location (or use default)
4. Click "Install"
5. Wait 30 seconds
6. Done!

### Step 3: Launch
- Double-click "RĀMAN Studio" desktop icon
- Wait 5 seconds for startup
- Dashboard appears — you're ready!

---

## 🎯 First Steps

### 1. Create Your First Project
1. Click **File → New Project** (or press `Ctrl+N`)
2. Enter project name: "My First Analysis"
3. Click "Create"

### 2. Run an EIS Simulation
1. Click **Tools → EIS** (or press `Ctrl+2`)
2. Click "New Simulation"
3. Select circuit: "Randles"
4. Set parameters:
   - R_s = 10 Ω
   - R_ct = 100 Ω
   - C_dl = 1e-5 F
5. Click "Run Simulation"
6. **Result**: Nyquist and Bode plots appear!

### 3. Save Your Work
1. Click **File → Save Project** (or press `Ctrl+S`)
2. Choose location
3. Enter filename: "my-first-project.raman"
4. Click "Save"

---

## 🔧 Key Features

### Electrochemical Analysis
- **EIS**: Impedance spectroscopy (Nyquist, Bode plots)
- **CV**: Cyclic voltammetry analysis
- **GCD**: Galvanostatic charge-discharge
- **DRT**: Distribution of relaxation times

### Advanced Tools
- **Circuit Fitting**: Automatic parameter optimization
- **Materials AI**: NVIDIA-powered materials insights
- **Biosensor**: Specialized biosensor analysis
- **Lab Data**: Import Excel/CSV data

### Data Management
- **Projects**: Save/load complete analysis sessions
- **Export**: PDF reports, PNG plots
- **Import**: CSV, Excel, JSON data formats
- **Encryption**: Hardware-bound project encryption

---

## ⌨️ Keyboard Shortcuts

### File Operations
- `Ctrl+N` — New project
- `Ctrl+O` — Open project
- `Ctrl+S` — Save project
- `Ctrl+Shift+S` — Save as
- `Ctrl+E` — Export report

### Navigation
- `Ctrl+1` — Dashboard
- `Ctrl+2` — EIS
- `Ctrl+3` — Cyclic Voltammetry
- `Ctrl+4` — GCD
- `Ctrl+5` — DRT
- `Ctrl+6` — Circuit Fitting
- `Ctrl+7` — Biosensor

### View
- `Ctrl+Shift+L` — Light theme
- `Ctrl+Shift+D` — Dark theme
- `Ctrl+Shift+H` — High-contrast theme

---

## 🎨 Interface Overview

```
┌─────────────────────────────────────────────────────┐
│ File  Edit  View  Tools  Window  Help              │ ← Menu Bar
├──────┬──────────────────────────────────────────────┤
│      │                                              │
│ 📊   │                                              │
│ ⚡   │         Main Content Area                    │
│ 🔬   │         (Plots, Data, Controls)              │
│ 📈   │                                              │
│ 🧪   │                                              │
│ 🤖   │                                              │
│      │                                              │
└──────┴──────────────────────────────────────────────┘
  ↑
Sidebar (Tools)
```

---

## 💡 Tips & Tricks

### Performance
- **GPU Acceleration**: Automatically enabled if available
- **Large Datasets**: Use "Downsample" option for faster plotting
- **Memory**: Close unused projects to free RAM

### Workflow
- **Templates**: Save common circuit models as templates
- **Batch Processing**: Import multiple files at once
- **Keyboard Navigation**: Use shortcuts for faster work

### Troubleshooting
- **Backend Not Starting?** Wait 10 seconds, then restart
- **Plots Not Showing?** Check data format (frequency, Z_real, Z_imag)
- **License Issues?** Check internet connection for validation

---

## 📚 Learn More

### Documentation
- **User Manual**: `README.md`
- **Testing Guide**: `TESTING_GUIDE.md`
- **Deployment Guide**: `DEPLOYMENT_GUIDE.md`

### Online Resources
- **GitHub**: https://github.com/varshinicb1/EIS-RV
- **Documentation**: https://github.com/varshinicb1/EIS-RV/blob/master/README.md
- **Support**: support@vidyuthlabs.co.in

---

## 🆘 Common Issues

### Issue: SmartScreen Warning
**Solution**: Click "More info" → "Run anyway"  
**Why**: App is not code-signed (safe to run)

### Issue: Slow Startup
**Solution**: Wait 10 seconds on first launch  
**Why**: Backend initialization takes time

### Issue: "Backend Unreachable"
**Solution**: Restart the application  
**Why**: Backend may have crashed

### Issue: Plots Not Rendering
**Solution**: Check browser console (F12) for errors  
**Why**: Data format may be incorrect

---

## 🎓 Example Workflow

### Analyzing Battery EIS Data

1. **Import Data**
   - File → Open Lab Data
   - Select your `.csv` file
   - Columns: frequency, Z_real, Z_imag

2. **Visualize**
   - Tools → EIS
   - Data appears in Nyquist plot

3. **Fit Circuit**
   - Tools → Circuit Fitting
   - Select "Randles" model
   - Click "Fit"
   - View fitted parameters

4. **Analyze DRT**
   - Tools → DRT
   - Click "Calculate DRT"
   - Identify relaxation processes

5. **Export Report**
   - File → Export Report (PDF)
   - Share with colleagues!

---

## 🌟 Pro Tips

### For Researchers
- Use **Materials AI** to get insights on electrode materials
- Export plots as **high-res PNG** for publications
- Save **circuit models** as templates for reuse

### For Students
- Start with **simulated data** to learn concepts
- Use **built-in tutorials** (Help menu)
- Experiment with **different circuit models**

### For Industry
- Batch process **QC data** from production
- Set up **automated reports** for daily testing
- Use **license system** for team deployment

---

## 📞 Need Help?

**Email**: support@vidyuthlabs.co.in  
**GitHub Issues**: https://github.com/varshinicb1/EIS-RV/issues  
**Documentation**: https://github.com/varshinicb1/EIS-RV

---

**Welcome to RĀMAN Studio!** 🎉  
**The Digital Twin for Your Potentiostat** ⚡

---

**Version**: 2.1.0  
**Company**: VidyuthLabs  
**License**: Commercial (Trial available)
