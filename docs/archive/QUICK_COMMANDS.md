# Quick Commands Reference - CV Transformer V2

**Date:** May 6, 2026  
**Status:** Training in progress

---

## 🔍 Check Training Status

```bash
# Training is running in background (Terminal 7)
# Check process list
# Process will complete automatically
```

---

## 📊 After Training Completes

### **1. Verify All Models Saved**
```bash
# Check if all 5 models exist
ls models/cv_transformer_ensemble/model_*.pt

# Expected output:
# model_0.pt  model_1.pt  model_2.pt  model_3.pt  model_4.pt
```

### **2. Evaluate Ensemble**
```bash
# Run comprehensive evaluation
py -3.12 src/backend/ml/evaluation/evaluate_ensemble.py

# Output:
# - ECE scores
# - Reliability diagrams
# - Uncertainty calibration
# - Coverage statistics
```

### **3. View TensorBoard Logs**
```bash
# Start TensorBoard
tensorboard --logdir=models/cv_transformer_ensemble/runs

# Open browser to: http://localhost:6006
```

---

## 🔧 Next Steps (Tomorrow)

### **4. Train Anomaly Detector**
```bash
# Train autoencoder for anomaly detection (~30 min)
py -3.12 src/backend/ml/training/train_anomaly_detector.py
```

### **5. Generate Attention Visualizations**
```bash
# Create attention heatmaps and overlays
py -3.12 src/backend/ml/visualization/generate_attention_viz.py
```

### **6. Test Uncertainty Quantification**
```bash
# Test on specific samples
py -3.12 src/backend/ml/evaluation/test_uncertainty.py
```

---

## 🔌 API Integration (Day 3)

### **7. Update API Routes**
```python
# Edit: src/backend/api/v1_routes/ml_routes.py

# Add ensemble endpoint
@router.post("/predict/ensemble")
async def predict_ensemble(data: CVData):
    # Load ensemble
    ensemble = load_ensemble()
    
    # Predict with uncertainty
    results = ensemble.predict_with_uncertainty(data.current)
    
    return {
        "reversibility": {
            "mean": results["reversibility"]["mean"],
            "std": results["reversibility"]["std"],
            "lower": results["reversibility"]["lower"],
            "upper": results["reversibility"]["upper"]
        },
        "mechanism": {
            "prediction": results["mechanism"]["mean"],
            "confidence": results["mechanism"]["confidence"]
        }
    }
```

### **8. Test API**
```bash
# Start backend
py -3.12 src/backend/main.py

# Test endpoint
curl -X POST http://localhost:8000/api/v1/ml/predict/ensemble \
  -H "Content-Type: application/json" \
  -d '{"current": [...]}'
```

---

## 📈 Performance Benchmarking

### **9. Benchmark Inference Speed**
```bash
# Test inference time
py -3.12 src/backend/ml/evaluation/benchmark_ensemble.py

# Expected: 45-50ms (5x single model)
```

### **10. Memory Profiling**
```bash
# Check memory usage
py -3.12 src/backend/ml/evaluation/profile_memory.py

# Expected: ~310 MB (5 models)
```

---

## 🐛 Troubleshooting

### **Training Failed?**
```bash
# Check logs
cat models/cv_transformer_ensemble/training.log

# Restart training
py -3.12 src/backend/ml/training/train_ensemble.py
```

### **CUDA Out of Memory?**
```python
# Reduce batch size in config
CONFIG['batch_size'] = 8  # Instead of 16
```

### **Models Not Loading?**
```bash
# Check model files exist
ls -lh models/cv_transformer_ensemble/

# Verify checksums
md5sum models/cv_transformer_ensemble/model_*.pt
```

---

## 📚 Documentation

### **Read Research**
```bash
# Comprehensive research findings
cat SOTA_RESEARCH_2026.md

# Implementation roadmap
cat RESEARCH_SUMMARY_AND_NEXT_STEPS.md

# Week 1 guide
cat QUICK_START_V2.md
```

### **View Progress**
```bash
# Current status
cat WEEK_1_PROGRESS_UPDATE.md

# Training status
cat TRAINING_IN_PROGRESS.md
```

---

## 🎯 Week 2 Preview

### **Physics-Informed Loss**
```bash
# Implement electrochemical constraints
# File: src/backend/ml/training/physics_loss.py

# Train with physics constraints
py -3.12 src/backend/ml/training/train_cv_v2.py --physics-loss
```

### **Contrastive Pre-Training**
```bash
# Pre-train on unlabeled data
py -3.12 src/backend/ml/training/contrastive_pretrain.py

# Fine-tune on labeled data
py -3.12 src/backend/ml/training/finetune_cv.py
```

---

## 🚀 Quick Start (New User)

```bash
# 1. Check training status
# (Training is running in background)

# 2. After training completes, evaluate
py -3.12 src/backend/ml/evaluation/evaluate_ensemble.py

# 3. View results
cat models/cv_transformer_ensemble/evaluation/evaluation_results.json

# 4. View visualizations
open models/cv_transformer_ensemble/evaluation/*.png

# 5. Integrate into API
# Edit: src/backend/api/v1_routes/ml_routes.py

# 6. Test end-to-end
py -3.12 src/backend/main.py
```

---

## 📞 Support

**Questions?** Check documentation:
- `SOTA_RESEARCH_2026.md` - Research findings
- `RESEARCH_SUMMARY_AND_NEXT_STEPS.md` - Implementation plan
- `WEEK_1_PROGRESS_UPDATE.md` - Current status

**Issues?** Check logs:
- `models/cv_transformer_ensemble/training.log`
- `models/cv_transformer_ensemble/runs/` (TensorBoard)

---

**Author:** VidyuthLabs  
**Date:** May 6, 2026  
**Status:** Training in progress
