# 🚀 ML System Quick Start Guide

**Get started with the self-evolving ML system in 5 minutes**

---

## ⚡ Quick Test - Verify Models Work

### 1. Test All Models

```bash
cd EIS-RV

# Test Raman Transformer
python src/backend/ml/models/raman_transformer.py

# Test EIS Transformer
python src/backend/ml/models/eis_transformer.py

# Test CV Transformer
python src/backend/ml/models/cv_transformer.py

# Test GCD Transformer
python src/backend/ml/models/gcd_transformer.py

# Test Biosensor Transformer
python src/backend/ml/models/biosensor_transformer.py
```

**Expected output for each:**
```
Testing [Model] Transformer...
Input shape: torch.Size([4, ...])
Output shape: torch.Size([4, ...])
Total parameters: XX,XXX,XXX
[Model] Transformer test successful!
```

---

## 📥 Download Real Datasets

### Option 1: Automatic Download (Recommended)

```bash
python src/backend/ml/data_collection/download_datasets.py
```

This will download:
- RRUFF: ~15,000 mineral spectra
- MLROD: ~130,000 Mars mineral spectra  
- Bacteria-ID: ~66,000 bacterial spectra
- API: ~3,500 pharmaceutical spectra

**Total:** ~220,000 real Raman spectra

**Time:** ~2-4 hours depending on connection

### Option 2: Manual Download

If automatic download fails, download manually:

1. **RRUFF:** https://rruff.info/
2. **MLROD:** https://github.com/NASA-Planetary-Science/MLROD
3. **Bacteria-ID:** https://github.com/csho33/bacteria-ID
4. **API:** https://doi.org/10.6084/m9.figshare.27826699

Place in: `data/ml_datasets/raw/`

---

## 🧠 Train Your First Model

### Train Raman Model (Simplest)

```python
import torch
import torch.nn as nn
from src.backend.ml.models.raman_transformer import create_raman_transformer

# Create model
model = create_raman_transformer(num_classes=100, model_size='small')

# Dummy training data (replace with real data)
train_data = torch.randn(1000, 2048)  # 1000 spectra
train_labels = torch.randint(0, 100, (1000,))  # 100 classes

# Simple training loop
optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
criterion = nn.CrossEntropyLoss()

model.train()
for epoch in range(10):
    # Forward pass
    outputs = model(train_data)
    loss = criterion(outputs, train_labels)
    
    # Backward pass
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    
    print(f"Epoch {epoch+1}/10, Loss: {loss.item():.4f}")

# Save model
torch.save(model.state_dict(), 'raman_model.pth')
print("Model saved!")
```

---

## 🔄 Start Continuous Learning System

### Run the Self-Evolving System

```bash
python src/backend/ml/continuous_learning/self_evolving_system.py
```

This starts:
- ✅ Data lake monitoring
- ✅ Literature mining (24/7)
- ✅ Automatic retraining
- ✅ Model deployment

**Note:** This runs indefinitely. Use Ctrl+C to stop.

---

## 🧪 Use Models for Inference

### Example: Predict Material from Raman Spectrum

```python
import torch
from src.backend.ml.models.raman_transformer import create_raman_transformer
import numpy as np

# Load model
model = create_raman_transformer(num_classes=100, model_size='base')
model.load_state_dict(torch.load('raman_model.pth'))
model.eval()

# Your spectrum data
wavenumber = np.linspace(200, 3000, 2048)
intensity = np.random.randn(2048)  # Replace with real data

# Convert to tensor
spectrum = torch.tensor(intensity, dtype=torch.float32).unsqueeze(0)

# Predict
with torch.no_grad():
    prediction = model(spectrum)
    predicted_class = torch.argmax(prediction, dim=1)
    confidence = torch.softmax(prediction, dim=1).max()

print(f"Predicted material: Class {predicted_class.item()}")
print(f"Confidence: {confidence.item():.2%}")
```

### Example: Battery SOC/SOH from EIS

```python
import torch
from src.backend.ml.models.eis_transformer import create_eis_transformer

# Load model
model = create_eis_transformer('base')
model.eval()

# Your EIS data
z_real = torch.randn(1, 1, 1000)  # Replace with real impedance data
z_imag = torch.randn(1, 1, 1000)

# Predict
with torch.no_grad():
    outputs = model(z_real, z_imag, task='battery')
    soc = outputs['soc'].item()
    soh = outputs['soh'].item()

print(f"State of Charge (SOC): {soc:.1%}")
print(f"State of Health (SOH): {soh:.1%}")
```

### Example: CV Mechanism Classification

```python
import torch
from src.backend.ml.models.cv_transformer import create_cv_transformer

# Load model
model = create_cv_transformer('base')
model.eval()

# Your CV data
current = torch.randn(1, 1, 2000)  # Replace with real CV data

# Predict
with torch.no_grad():
    outputs = model(current, task='mechanism')
    mechanism = torch.argmax(outputs['mechanism'], dim=1)
    reversibility = outputs['reversibility'].item()

mechanisms = ['Reversible', 'Irreversible', 'Quasi-reversible', 'EC', 'ECE']
print(f"Mechanism: {mechanisms[mechanism.item()]}")
print(f"Reversibility score: {reversibility:.2f}")
```

---

## 📊 Monitor System Performance

### Check Data Lake Statistics

```python
from pathlib import Path
from src.backend.ml.continuous_learning.self_evolving_system import DataLake

# Create data lake
base_dir = Path("data/ml_system/data_lake")
data_lake = DataLake(base_dir)

# Get statistics
stats = data_lake.get_statistics()

print(f"Total measurements: {stats['total_measurements']}")
print(f"By technique:")
for technique, count in stats['by_technique'].items():
    print(f"  {technique}: {count}")
```

---

## 🎯 Integration with RĀMAN Studio

### Add ML Prediction to Analysis Pipeline

```python
# In your analysis code
from src.backend.ml.models.raman_transformer import create_raman_transformer
import torch

class RamanAnalyzerWithML:
    def __init__(self):
        # Load ML model
        self.ml_model = create_raman_transformer(num_classes=100)
        self.ml_model.load_state_dict(torch.load('raman_model.pth'))
        self.ml_model.eval()
    
    def analyze(self, wavenumber, intensity):
        # Traditional analysis
        peaks = self.detect_peaks(intensity)
        baseline = self.correct_baseline(intensity)
        
        # ML prediction
        spectrum = torch.tensor(intensity, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            prediction = self.ml_model(spectrum)
            material = torch.argmax(prediction, dim=1)
            confidence = torch.softmax(prediction, dim=1).max()
        
        return {
            'peaks': peaks,
            'baseline': baseline,
            'ml_material': material.item(),
            'ml_confidence': confidence.item()
        }
```

---

## 🔧 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'torch'"

**Solution:**
```bash
pip install torch torchvision torchaudio
```

### Issue: "CUDA out of memory"

**Solution:** Use smaller model size
```python
model = create_raman_transformer(num_classes=100, model_size='small')
```

### Issue: "Download failed"

**Solution:** Download datasets manually (see Option 2 above)

### Issue: "Model training is slow"

**Solution:** Use GPU if available
```python
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = model.to(device)
train_data = train_data.to(device)
```

---

## 📚 Next Steps

1. **Read full documentation:**
   - `SELF_EVOLVING_SYSTEM_IMPLEMENTATION.md` - Complete implementation
   - `ML_RESEARCH_MASTER_PLAN.md` - Research background
   - `ULTIMATE_SELF_EVOLVING_SYSTEM.md` - Vision document

2. **Train on real data:**
   - Download datasets
   - Preprocess data
   - Train models
   - Validate performance

3. **Integrate with RĀMAN Studio:**
   - Add ML endpoints to API
   - Update frontend to show ML predictions
   - Enable user contributions

4. **Deploy continuous learning:**
   - Start literature mining
   - Enable automatic retraining
   - Monitor performance

---

## 🎓 Learning Resources

### PyTorch Tutorials
- https://pytorch.org/tutorials/

### Transformer Architecture
- "Attention Is All You Need" paper
- https://arxiv.org/abs/1706.03762

### Raman Spectroscopy ML
- "Benchmarking Deep Learning Models for Raman Spectroscopy" (2025)
- "RamanFormer: Transformer-based quantification" (2024)

---

## 💡 Tips

1. **Start small:** Use 'small' model size for testing
2. **Use GPU:** Training is 10-100x faster on GPU
3. **Monitor memory:** Large models need 8-16GB RAM
4. **Save checkpoints:** Save model every epoch
5. **Validate often:** Check performance on test set
6. **Use real data:** Synthetic data doesn't generalize well

---

## 🏆 Success Criteria

You'll know it's working when:
- ✅ All model tests pass
- ✅ Training loss decreases
- ✅ Validation accuracy > 90%
- ✅ Inference time < 100ms
- ✅ Continuous learning system runs without errors

---

## 📞 Need Help?

1. Check documentation files
2. Review error messages carefully
3. Test with dummy data first
4. Verify PyTorch installation
5. Check GPU availability

---

**Status:** 🟢 READY TO USE  
**Difficulty:** Intermediate  
**Time:** 5 minutes to test, 4 hours to train  
**Requirements:** Python 3.8+, PyTorch 2.0+, 16GB RAM

**Let's build the future of science!** 🚀
