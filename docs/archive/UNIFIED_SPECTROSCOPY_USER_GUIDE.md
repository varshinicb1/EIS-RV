# Unified Spectroscopy Panel - User Guide

**Quick Start**: Upload your Raman spectrum file and see instant results!

---

## How to Access

1. Open RĀMAN Studio: http://localhost:5173
2. Look at the **left sidebar**
3. Find the **"Analysis"** section
4. Click **"Unified Spectroscopy"**

---

## What You'll See

### Left Sidebar (Controls)

#### 1. Upload Section
```
┌─────────────────────────────┐
│ ◆ Unified Spectroscopy      │
│ 7 research sources · Pub... │
├─────────────────────────────┤
│ Raman spectrum file         │
│ [Choose File]               │
│ FO.txt                      │
└─────────────────────────────┘
```
- Click "Choose File"
- Select your `.txt` or `.csv` Raman data
- **Plot appears immediately!** No "Analyze" button needed

#### 2. Analysis Options
```
┌─────────────────────────────┐
│ Analysis Options            │
├─────────────────────────────┤
│ ☑ Cosmic ray removal        │
│   (BoxSERS)                 │
│ ☑ Fourier filtering         │
│   (SpectraGuru)             │
│ ☑ Voigt peak fitting        │
│   (RamanLab)                │
│ [▶ Reanalyze]               │
└─────────────────────────────┘
```
- Check boxes to enable advanced preprocessing
- Click "Reanalyze" to update plot with new options

#### 3. Display Options
```
┌─────────────────────────────┐
│ Display Options             │
├─────────────────────────────┤
│ ☑ Show peak markers         │
│ ☐ Show baseline correction  │
│ ☐ Show fitted peaks         │
└─────────────────────────────┘
```
- Toggle what appears on the plot
- Changes apply instantly

#### 4. Export
```
┌─────────────────────────────┐
│ Export                      │
├─────────────────────────────┤
│ [⬇ Download PNG (300 DPI)]  │
└─────────────────────────────┘
```
- One-click export for publications
- High-resolution PNG file

#### 5. AI Analysis
```
┌─────────────────────────────┐
│ ◆ AI Analysis               │
├─────────────────────────────┤
│ [▶ Run AI Analysis]         │
│                             │
│ Analysis results appear     │
│ here with material ID,      │
│ features, and publication   │
│ recommendations             │
└─────────────────────────────┘
```
- Requires NVIDIA API key (configure in Profile → Settings)
- Provides contextual insights for your spectrum

---

### Main Content Area

#### 1. Research-Grade Plot
```
┌─────────────────────────────────────────────────────────┐
│ RAMAN_SPECTRUM_TELEMETRY    ENGINE: UNIFIED_V1 · ...    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Raman Spectrum Analysis          2672 points · 14 peaks│
│                                                         │
│  Intensity                                              │
│  (a.u.)     ╱╲                                          │
│       │    ╱  ╲    ╱╲                                   │
│       │   ╱    ╲  ╱  ╲                                  │
│       │  ╱      ╲╱    ╲                                 │
│       │ ╱              ╲___                             │
│       └─────────────────────────────────────            │
│         Raman Shift (cm⁻¹)                              │
│                                                         │
│  [Red dots mark detected peaks with position labels]    │
└─────────────────────────────────────────────────────────┘
```
- **Gradient fill** under spectrum (blue)
- **Peak markers** (red dots) with position labels
- **Grid lines** for easy reading
- **Professional axes** with units
- **HUD brackets** in corners (cyan)

#### 2. Statistics Cards
```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ PEAKS_       │ DATA_        │ WAVENUMBER_  │ WAVENUMBER_  │
│ DETECTED     │ POINTS       │ MIN          │ MAX          │
│ 14 peaks     │ 2672 pts     │ 103.0 cm⁻¹   │ 3004.0 cm⁻¹  │
└──────────────┴──────────────┴──────────────┴──────────────┘
```
- Quick overview of spectrum properties
- Updates automatically

#### 3. Peaks Table
```
┌─────────────────────────────────────────────────────────┐
│ Detected Peaks (14)                                     │
├───┬──────────────┬───────────┬────────────┬────────────┤
│ # │ Position     │ Intensity │ Prominence │ FWHM       │
│   │ (cm⁻¹)       │           │            │ (cm⁻¹)     │
├───┼──────────────┼───────────┼────────────┼────────────┤
│ 1 │ 156.23       │ 0.847     │ 0.234      │ 12.45      │
│ 2 │ 289.67       │ 0.623     │ 0.189      │ 15.32      │
│ 3 │ 412.89       │ 0.912     │ 0.456      │ 18.76      │
│...│ ...          │ ...       │ ...        │ ...        │
└───┴──────────────┴───────────┴────────────┴────────────┘
```
- Scrollable table with all detected peaks
- Monospace font for precise numbers

#### 4. Material Identification
```
┌─────────────────────────────────────────────────────────┐
│ Material Identification                                 │
├─────────────────────────────────────────────────────────┤
│ Graphene                                          87%   │
│ 12 of 14 peaks matched                        confidence│
├─────────────────────────────────────────────────────────┤
│ Carbon nanotubes                                  65%   │
│ 9 of 14 peaks matched                         confidence│
└─────────────────────────────────────────────────────────┘
```
- Ranked by confidence
- Shows matched peaks count

---

## Workflow Examples

### Basic Analysis
1. **Upload file** → Plot appears instantly
2. **Review peaks** → Check table and markers
3. **Export PNG** → Download for paper

### Advanced Analysis
1. **Upload file** → Plot appears
2. **Enable options** → Check "Cosmic ray removal" + "Fourier filtering"
3. **Click Reanalyze** → Updated plot with cleaner data
4. **Toggle display** → Show/hide peak markers as needed
5. **Export PNG** → Publication-ready figure

### AI-Assisted Analysis
1. **Upload file** → Plot appears
2. **Run AI Analysis** → Click button (requires API key)
3. **Review insights** → Material ID, features, recommendations
4. **Export PNG** → Include in manuscript
5. **Use AI suggestions** → Follow recommended next steps

---

## File Format Requirements

### Supported Formats
- `.txt` - Plain text with two columns
- `.csv` - Comma-separated values

### Expected Structure
```
# Optional header lines (ignored)
wavenumber1  intensity1
wavenumber2  intensity2
wavenumber3  intensity3
...
```

### Example (FO.txt)
```
103.0  0.234
105.5  0.245
108.0  0.256
...
3004.0  0.189
```

### Requirements
- **Two columns**: wavenumber (cm⁻¹) and intensity
- **Numeric values**: No text in data rows
- **Consistent spacing**: Tab or space separated
- **No missing values**: All rows must have both columns

---

## NVIDIA API Key Setup

### Why You Need It
- Enables AI analysis of your spectra
- Provides contextual insights for publications
- Suggests material identification
- Recommends next steps

### How to Configure

#### Option 1: Via Profile Panel
1. Click **"Profile"** in sidebar (bottom)
2. Find **"NVIDIA NIM API Key"** section
3. Enter your key (starts with `nvapi-`)
4. Click **"Save"**
5. Key persists automatically - no repeated prompts!

#### Option 2: Via .env File
1. Open `src/.env` in text editor
2. Add line: `NVIDIA_API_KEY=nvapi-your-key-here`
3. Save file
4. Restart backend (or it auto-reloads)

### Getting an API Key
1. Visit: https://build.nvidia.com/
2. Sign up for free account
3. Navigate to API Keys section
4. Generate new key
5. Copy key (starts with `nvapi-`)

### Key Storage
- Stored in `src/.env` file (gitignored)
- Permissions set to 0600 (user-only)
- Never exposed in UI or logs
- Persists across sessions

---

## Troubleshooting

### Plot Not Showing
- **Check file format**: Must be .txt or .csv with two columns
- **Check data**: Ensure numeric values only
- **Refresh browser**: Press F5 or Ctrl+R
- **Check console**: Press F12, look for errors

### No Peaks Detected
- **Try Fourier filtering**: Helps with noisy data
- **Check intensity range**: Very flat spectra may have no peaks
- **Verify data**: Ensure wavenumber and intensity columns are correct

### AI Analysis Not Working
- **Check API key**: Must be configured in Profile → Settings
- **Verify key format**: Should start with `nvapi-`
- **Check backend**: Ensure http://localhost:8000 is running
- **Check console**: Press F12, look for network errors

### Export PNG Not Working
- **Check browser**: Some browsers block downloads
- **Allow popups**: Enable for localhost:5173
- **Try different browser**: Chrome/Firefox recommended

### Reanalyze Button Disabled
- **Upload file first**: Button only works after file upload
- **Wait for analysis**: Button disabled during processing

---

## Keyboard Shortcuts

- **Ctrl+O**: Open file dialog (when panel focused)
- **Ctrl+S**: Export PNG (when plot visible)
- **Ctrl+R**: Reanalyze with current options
- **Ctrl+1**: Toggle peak markers
- **Ctrl+2**: Toggle baseline
- **Ctrl+3**: Toggle fitted peaks

---

## Tips for Best Results

### Data Quality
1. **Clean data**: Remove header lines and comments
2. **Consistent format**: Use same delimiter throughout
3. **Sufficient points**: At least 100 points recommended
4. **Reasonable range**: Typical Raman 100-4000 cm⁻¹

### Analysis Options
1. **Cosmic ray removal**: Use for CCD detector data
2. **Fourier filtering**: Use for noisy spectra
3. **Voigt fitting**: Use for overlapping peaks

### Publication Plots
1. **Enable peak markers**: Shows key features
2. **Export as PNG**: 300 DPI for papers
3. **Use AI analysis**: Get insights for discussion section
4. **Check material ID**: Verify against known references

---

## Research Sources

The Unified Spectroscopy Engine integrates methods from 7 peer-reviewed sources:

1. **SpectraGuru** (ACS 2025) - Fourier filtering
2. **DeepeR** - Deep learning peak detection
3. **RamanSPy** - Normalization methods
4. **BoxSERS** - Cosmic ray removal, augmentation
5. **RamanLab** - Voigt peak fitting, 6,939+ spectra database
6. **spectrai** - PyTorch-based analysis
7. **Deep Learning** - CNN, LSTM, GCN architectures

All methods are research-grade and suitable for publication.

---

## Support

### Documentation
- **Quick Start**: `UNIFIED_QUICK_START.md`
- **Full Guide**: `UNIFIED_SPECTROSCOPY_GUIDE.md`
- **API Docs**: http://localhost:8000/docs
- **Test Results**: `UNIFIED_ENGINE_TEST_RESULTS.md`

### Common Issues
- See "Troubleshooting" section above
- Check browser console (F12) for errors
- Verify backend is running (http://localhost:8000)

### Contact
- GitHub: https://github.com/varshinicb1/EIS-RV
- Company: VidyuthLabs Pvt. Ltd.

---

## Summary

✨ **The Unified Spectroscopy Panel makes Raman analysis effortless:**

1. **Upload** → Instant plot
2. **Analyze** → 14 peaks detected
3. **Export** → Publication-ready PNG
4. **AI insights** → Contextual recommendations

**No complicated workflows. No repeated prompts. Just results.** 🎉
