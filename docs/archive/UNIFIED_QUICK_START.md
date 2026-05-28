# Unified Spectroscopy Engine - Quick Start

## 🚀 Get Started in 5 Minutes

### 1. Start the Server

```bash
cd EIS-RV
python -m uvicorn src.backend.api.server:app --port 8000 --reload
```

**Expected Output:**
```
INFO: Unified spectroscopy engine loaded (7 research sources integrated)
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000
```

### 2. Test Basic Analysis

```bash
curl -X POST "http://localhost:8000/api/v1/unified-spectroscopy/analyze" \
  -F "file=@Lab data/FO.txt"
```

### 3. Test with Advanced Features

```bash
curl -X POST "http://localhost:8000/api/v1/unified-spectroscopy/analyze" \
  -F "file=@Lab data/FO.txt" \
  -F "cosmic_ray_removal=true" \
  -F "fourier_filtering=true" \
  -F "voigt_fitting=true"
```

### 4. Batch Analysis

```bash
curl -X POST "http://localhost:8000/api/v1/unified-spectroscopy/batch-analyze" \
  -F "files=@sample1.txt" \
  -F "files=@sample2.txt" \
  -F "files=@sample3.txt" \
  -F "perform_pca=true" \
  -F "perform_clustering=true"
```

### 5. Check Available Methods

```bash
curl -X GET "http://localhost:8000/api/v1/unified-spectroscopy/methods"
```

### 6. Health Check

```bash
curl -X GET "http://localhost:8000/api/v1/unified-spectroscopy/health"
```

---

## 📊 Python Usage

### Basic Analysis

```python
from src.backend.core.engines.unified_spectroscopy_engine import (
    UnifiedSpectroscopyAnalyzer,
    UnifiedSpectroscopyConfig
)
from src.backend.core.engines.raman_engine import import_raman_data

# Import spectrum
spectrum = import_raman_data("Lab data/FO.txt")

# Analyze with default settings
config = UnifiedSpectroscopyConfig()
analyzer = UnifiedSpectroscopyAnalyzer(config)
analyzed = analyzer.analyze(spectrum)

print(f"Peaks detected: {len(analyzed.peaks)}")
```

### Advanced Analysis

```python
# Enable all advanced features
config = UnifiedSpectroscopyConfig(
    cosmic_ray_removal=True,
    fourier_filtering=True,
    voigt_fitting=True,
    augmentation_enabled=True
)

analyzer = UnifiedSpectroscopyAnalyzer(config)
analyzed = analyzer.analyze(spectrum)

# Access results
print(f"Peaks: {len(analyzed.peaks)}")
print(f"Augmented spectra: {len(analyzed.augmented_spectra)}")
```

### Batch Analysis

```python
from src.backend.core.engines.unified_spectroscopy_engine import BatchSpectroscopyAnalyzer

# Create batch analyzer
batch = BatchSpectroscopyAnalyzer()

# Add spectra
for file in ["sample1.txt", "sample2.txt", "sample3.txt"]:
    spectrum = import_raman_data(file)
    batch.add_spectrum(spectrum)

# Analyze all
analyzed = batch.analyze_all()

# PCA
X_pca, pca, var = batch.perform_pca_analysis()
print(f"Variance explained: {var.sum():.2%}")

# Clustering
labels, model = batch.perform_clustering()
print(f"Clusters: {labels}")
```

---

## 🎯 Key Features

### ✅ Implemented (Phase 1)
- **Cosmic Ray Removal** - Remove spikes from SERS data
- **Fourier Filtering** - Advanced noise reduction
- **Voigt Peak Fitting** - More accurate than Lorentzian/Gaussian
- **Data Augmentation** - Generate training data for ML
- **PCA** - Dimensionality reduction
- **t-SNE** - Nonlinear visualization
- **K-means Clustering** - Automatic grouping
- **Hierarchical Clustering** - Dendrogram visualization
- **Batch Analysis** - Process multiple spectra
- **Enhanced Normalization** - 6 methods including MaxIntensity, AUC

### 🔄 Planned (Phase 2)
- **ResUNet Denoising** - Deep learning denoising (10x improvement)
- **CNN Classification** - Material classification
- **SimCLR** - Few-shot learning
- **Reference Database** - 6,939+ spectra
- **2D Mapping** - Hyperspectral imaging

---

## 📚 Documentation

- **Complete Guide:** `UNIFIED_SPECTROSCOPY_GUIDE.md`
- **Implementation Details:** `UNIFIED_ENGINE_COMPLETE.md`
- **Research Summary:** `UNIFIED_ENGINE_SUMMARY.md`

---

## 🔬 Research Sources

1. **SpectraGuru** (ACS 2025) - PCA, t-SNE, clustering
2. **DeepeR** - Deep learning denoising
3. **spectrai** - PyTorch framework
4. **RamanSPy** - Enhanced normalization
5. **BoxSERS** - Cosmic ray removal, augmentation
6. **RamanLab** - Voigt fitting, 6,939+ spectra
7. **Raman-Spectra-Deep-Learning** - CNN, LSTM, Transformer, GCN, SimCLR

---

## 🆘 Troubleshooting

### Server won't start
```bash
# Check if port 8000 is available
netstat -an | grep 8000

# Try different port
python -m uvicorn src.backend.api.server:app --port 8001
```

### Import errors
```bash
# Install dependencies
pip install numpy scipy scikit-learn matplotlib seaborn
pip install fastapi uvicorn pydantic
```

### No peaks detected
- Ensure baseline correction is enabled
- Check normalization method
- System uses adaptive thresholds (should always find peaks)

---

## 📞 Support

- **GitHub:** https://github.com/varshinicb1/EIS-RV
- **Email:** support@vidyuthlabs.com

---

**Version:** 1.0.0  
**Status:** ✅ Production Ready  
**Date:** May 4, 2026
