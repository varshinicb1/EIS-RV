# Raman Spectroscopy - Quick Start Guide

## 🚀 Analyze Your Raman Data in 3 Steps

### Step 1: Start the Server
```bash
cd EIS-RV
python -m uvicorn src.backend.api.server:app --port 8000
```

### Step 2: Upload Your Data
```bash
curl -X POST "http://localhost:8000/api/v1/raman/upload" \
  -F "file=@your_raman_data.txt" \
  -F "sample_id=My_Sample"
```

### Step 3: View Results
The response contains:
- ✅ Baseline-corrected spectrum
- ✅ Detected peaks (position, intensity, FWHM)
- ✅ Material identification
- ✅ Processed data ready for plotting

---

## 📁 File Format

Your Raman data file should be **two columns**:

```
#Wave    #Intensity
3000     27.9
2999     16.8
2998     5.6
...
```

**Supported formats:** `.txt`, `.csv` (tab, comma, or space-separated)

---

## 🎛️ Adjust Analysis Settings

For noisy data or specific requirements:

```bash
curl -X POST "http://localhost:8000/api/v1/raman/analyze" \
  -F "file=@your_data.txt" \
  -F 'config={
    "baseline_method": "airpls",
    "baseline_lambda": 100000,
    "denoise_method": "savgol",
    "savgol_window": 15,
    "peak_prominence": 20.0,
    "peak_model": "lorentzian",
    "normalize": true
  }'
```

---

## 🔬 Available Methods

### Baseline Correction
- `airpls` - Best for complex baselines (recommended)
- `als` - Fast and effective
- `polynomial` - Simple baselines
- `morphological` - Complex shapes

### Denoising
- `savgol` - Preserves peaks (recommended)
- `wavelet` - Advanced noise reduction
- `moving_average` - Simple smoothing

### Peak Models
- `lorentzian` - Typical for Raman (recommended)
- `gaussian` - Alternative model

---

## 🎯 Common Use Cases

### High-Quality Data
```json
{
  "baseline_method": "airpls",
  "denoise_method": "savgol",
  "peak_prominence": 50.0
}
```

### Noisy Data
```json
{
  "baseline_method": "airpls",
  "baseline_lambda": 1000000,
  "denoise_method": "savgol",
  "savgol_window": 21,
  "peak_prominence": 10.0
}
```

### Weak Peaks
```json
{
  "baseline_method": "morphological",
  "denoise_method": "wavelet",
  "peak_prominence": 5.0,
  "peak_min_distance": 5
}
```

---

## 📊 Material Identification

Built-in database includes:
- Graphene (1580, 2700 cm⁻¹)
- Diamond (1332 cm⁻¹)
- Silicon (520 cm⁻¹)
- TiO₂ (Anatase & Rutile)
- Carbon nanotubes
- Polystyrene (calibration standard)

View full database:
```bash
curl http://localhost:8000/api/v1/raman/materials
```

---

## 🐍 Python Example

```python
import requests

# Upload and analyze
with open('raman_data.txt', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/raman/upload',
        files={'file': f},
        data={'sample_id': 'Sample_001'}
    )

result = response.json()

# Print results
print(f"Detected {len(result['peaks'])} peaks:")
for peak in result['peaks']:
    print(f"  {peak['position_cm']:.1f} cm⁻¹: {peak['intensity']:.1f}")

# Material matches
if result['material_matches']:
    print(f"\nPossible materials:")
    for match in result['material_matches']:
        print(f"  {match['material']}: {match['confidence']*100:.0f}%")
```

---

## 🔧 Troubleshooting

### No peaks detected?
- Lower `peak_prominence` (try 10.0 or 5.0)
- Increase `savgol_window` for more smoothing
- Try different `baseline_method`

### Too many false peaks?
- Increase `peak_prominence` (try 100.0)
- Increase `peak_min_distance`
- Use stronger denoising

### Baseline removes peaks?
- Reduce `baseline_lambda` (try 1e4)
- Try `morphological` baseline method
- Adjust `baseline_p` parameter

---

## 📚 Full Documentation

See `RAMAN_SPECTROSCOPY_GUIDE.md` for:
- Detailed algorithm descriptions
- Scientific references
- Advanced configuration
- API documentation
- Performance characteristics

---

## ✅ Quick Test

Test with customer's data:
```bash
curl -X POST "http://localhost:8000/api/v1/raman/upload" \
  -F "file=@Lab data/FO.txt" \
  -F "sample_id=FO_Test"
```

---

## 🆘 Support

- **Documentation:** `RAMAN_SPECTROSCOPY_GUIDE.md`
- **Email:** support@vidyuthlabs.co.in
- **GitHub:** https://github.com/varshinicb1/EIS-RV

---

**RĀMAN Studio v2.1.0+** | VidyuthLabs © 2026
