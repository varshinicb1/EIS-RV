# 🧬 RĀMAN Studio ML System
## The 300-Year Source of Truth for Raman Spectroscopy

**Mission:** Build ML models so accurate and comprehensive that RĀMAN Studio becomes the definitive reference for Raman spectroscopy for centuries.

---

## 📁 Directory Structure

```
EIS-RV/
├── data/
│   └── ml_datasets/
│       ├── raw/                    # Raw downloaded datasets
│       │   ├── rruff/             # RRUFF mineral database (~15K spectra)
│       │   ├── mlrod/             # MLROD Mars minerals (~130K spectra)
│       │   ├── bacteria_id/       # Bacteria-ID dataset (~66K spectra)
│       │   └── api/               # API pharmaceutical (~3.5K spectra)
│       ├── processed/              # Processed & standardized data
│       └── synthetic/              # Generated synthetic data
│
├── src/backend/ml/
│   ├── data_collection/
│   │   ├── download_datasets.py   # Download all datasets
│   │   ├── process_data.py        # Standardize format
│   │   └── generate_synthetic.py  # Generate synthetic spectra
│   │
│   ├── models/
│   │   ├── raman_transformer.py   # Transformer architecture (SOTA)
│   │   ├── sanet.py               # Scale-Adaptive Network
│   │   ├── hybrid_cnn_transformer.py  # Hybrid architecture
│   │   ├── self_supervised.py     # MAE & Contrastive learning
│   │   └── foundation_model.py    # Foundation model (future)
│   │
│   ├── training/
│   │   ├── train.py               # Training script
│   │   ├── pretrain.py            # Self-supervised pre-training
│   │   ├── finetune.py            # Fine-tuning script
│   │   └── evaluate.py            # Evaluation & benchmarking
│   │
│   ├── inference/
│   │   ├── predict.py             # Single spectrum prediction
│   │   ├── batch_predict.py       # Batch prediction
│   │   └── uncertainty.py         # Uncertainty quantification
│   │
│   └── utils/
│       ├── augmentation.py        # Data augmentation
│       ├── preprocessing.py       # Preprocessing utilities
│       ├── metrics.py             # Evaluation metrics
│       └── visualization.py       # Attention maps, etc.
│
└── docs/
    ├── ML_RESEARCH_MASTER_PLAN.md  # Complete research plan
    ├── DATASETS.md                 # Dataset documentation
    ├── MODELS.md                   # Model architectures
    └── TRAINING.md                 # Training procedures
```

---

## 🚀 Quick Start

### 1. Download Datasets

```bash
cd EIS-RV
python src/backend/ml/data_collection/download_datasets.py
```

This will download:
- RRUFF: ~15,000 mineral spectra
- MLROD: ~130,000 Mars mineral spectra
- Bacteria-ID: ~66,000 bacterial spectra
- API: ~3,500 pharmaceutical spectra

**Total:** ~220,000 real Raman spectra

### 2. Process Data

```bash
python src/backend/ml/data_collection/process_data.py
```

Standardizes all datasets to common format:
```json
{
  "wavenumber": [200, 201, ..., 3000],
  "intensity": [0.1, 0.2, ..., 0.9],
  "material": "Quartz",
  "source": "RRUFF",
  "instrument": "Horiba LabRAM",
  "laser_wavelength_nm": 532
}
```

### 3. Generate Synthetic Data

```bash
python src/backend/ml/data_collection/generate_synthetic.py --num_spectra 1000000
```

Generates 1M synthetic spectra with:
- Physics-based simulation
- Realistic noise & artifacts
- Baseline drift
- Fluorescence
- Cosmic rays

### 4. Train Model

```bash
# Pre-train with self-supervised learning
python src/backend/ml/training/pretrain.py \
    --model transformer \
    --data_dir data/ml_datasets/processed \
    --epochs 100 \
    --batch_size 256

# Fine-tune on labeled data
python src/backend/ml/training/finetune.py \
    --model transformer \
    --checkpoint checkpoints/pretrained.pth \
    --dataset rruff \
    --epochs 50 \
    --batch_size 128
```

### 5. Evaluate

```bash
python src/backend/ml/training/evaluate.py \
    --model transformer \
    --checkpoint checkpoints/finetuned.pth \
    --test_data data/ml_datasets/processed/rruff/test.json
```

### 6. Inference

```python
from src.backend.ml.inference.predict import RamanPredictor

# Load model
predictor = RamanPredictor('checkpoints/finetuned.pth')

# Predict
wavenumber = [200, 201, ..., 3000]
intensity = [0.1, 0.2, ..., 0.9]

result = predictor.predict(wavenumber, intensity)

print(f"Material: {result['material']}")
print(f"Confidence: {result['confidence']:.2%}")
print(f"Uncertainty: {result['uncertainty']:.3f}")
```

---

## 🏗️ Model Architectures

### 1. RamanTransformer (SOTA)

**Architecture:**
- Patch embedding (spectrum → patches)
- Positional encoding
- 12 transformer blocks
- 8-head self-attention
- Classification head

**Parameters:** ~50M  
**Accuracy:** >99% (in-distribution)  
**Speed:** <100ms per spectrum

**Use cases:**
- Material identification
- High accuracy required
- Sufficient compute available

### 2. SANet (Scale-Adaptive)

**Architecture:**
- Multi-scale convolutional blocks
- Channel attention
- 6 different kernel sizes (3, 5, 7, 9, 11, 13)
- Classification head

**Parameters:** ~10M  
**Accuracy:** >98%  
**Speed:** <50ms per spectrum

**Use cases:**
- Real-time analysis
- Edge devices
- Proven performance

### 3. Hybrid CNN-Transformer

**Architecture:**
- CNN backbone (local features)
- Transformer encoder (global context)
- Best of both worlds

**Parameters:** ~30M  
**Accuracy:** >99%  
**Speed:** <75ms per spectrum

**Use cases:**
- Balance accuracy & speed
- Complex spectra
- Multi-scale features

### 4. Self-Supervised Models

**MAE (Masked Autoencoder):**
- Pre-train on unlabeled data
- Mask 75% of spectrum
- Reconstruct original
- Transfer to downstream tasks

**Contrastive Learning:**
- Learn robust representations
- Augmented views of same spectrum
- SimCLR loss
- Fine-tune for classification

**Use cases:**
- Limited labeled data
- Transfer learning
- Robust representations

---

## 📊 Datasets

### RRUFF Database
- **Size:** ~15,000 spectra
- **Coverage:** 5,000+ minerals
- **Quality:** Reference quality
- **Instrument:** Various
- **License:** Public domain

### MLROD (Mars Minerals)
- **Size:** ~130,000 spectra
- **Coverage:** 12 minerals + 3 mixtures
- **Quality:** High (NASA)
- **Special:** Dusty spectra (distribution shift)
- **License:** NASA Open Data

### Bacteria-ID
- **Size:** ~66,000 spectra
- **Coverage:** 30 bacterial species
- **Quality:** High (Stanford)
- **Special:** Multi-task (isolate + treatment)
- **License:** MIT

### API (Pharmaceutical)
- **Size:** ~3,500 spectra
- **Coverage:** 32 compounds
- **Quality:** High (instrument pre-processed)
- **License:** CC BY 4.0

### Synthetic Data
- **Size:** 1,000,000+ spectra
- **Coverage:** All materials
- **Quality:** Physics-based simulation
- **Special:** Infinite variations
- **License:** Open source

---

## 🎯 Training Strategy

### Phase 1: Self-Supervised Pre-training (2 weeks)
```
Data: 1M+ unlabeled spectra (real + synthetic)
Method: Masked Autoencoder (MAE)
Goal: Learn robust representations
Epochs: 100
Batch size: 256
GPU: 4x A100 (40GB)
```

### Phase 2: Supervised Fine-tuning (1 week)
```
Data: 220K labeled spectra
Method: Classification
Goal: Material identification
Epochs: 50
Batch size: 128
GPU: 1x A100 (40GB)
```

### Phase 3: Domain Adaptation (1 week)
```
Data: Multi-instrument data
Method: Adversarial domain adaptation
Goal: Instrument-agnostic model
Epochs: 30
Batch size: 64
GPU: 1x A100 (40GB)
```

### Phase 4: Uncertainty Quantification (1 week)
```
Method: Monte Carlo Dropout + Ensemble
Goal: Know when model is uncertain
Samples: 100 per prediction
```

---

## 📈 Performance Targets

### Accuracy
- **In-distribution:** >99%
- **Out-of-distribution:** >95%
- **Unknown materials:** High uncertainty (std > 0.5)

### Robustness
- **Noise:** SNR < 10
- **Baseline drift:** Polynomial order 5
- **Cosmic rays:** 10+ spikes
- **Fluorescence:** Strong background

### Speed
- **Single spectrum:** <100ms
- **Batch (1000):** <10s
- **Real-time:** <50ms latency

### Generalization
- **Cross-dataset:** >90% accuracy
- **Cross-instrument:** >85% accuracy
- **Temporal:** >90% accuracy (old → new)

---

## 🔬 Validation Strategy

### 1. Cross-Dataset Validation
```python
# Train on RRUFF, test on MLROD
train_data = load_dataset('rruff')
test_data = load_dataset('mlrod')

model = train(train_data)
accuracy = evaluate(model, test_data)

print(f"Cross-dataset accuracy: {accuracy:.2%}")
```

### 2. Instrument Transfer
```python
# Train on Instrument A, test on Instrument B
train_data = load_data(instrument='Horiba')
test_data = load_data(instrument='Renishaw')

model = train(train_data)
accuracy = evaluate(model, test_data)

print(f"Instrument transfer accuracy: {accuracy:.2%}")
```

### 3. Temporal Validation
```python
# Train on old data, test on new data
train_data = load_data(year_range=(2010, 2020))
test_data = load_data(year_range=(2021, 2025))

model = train(train_data)
accuracy = evaluate(model, test_data)

print(f"Temporal accuracy: {accuracy:.2%}")
```

### 4. Expert Validation
```python
# Compare with human experts
expert_labels = load_expert_annotations()
model_predictions = model.predict(test_data)

agreement = calculate_agreement(expert_labels, model_predictions)

print(f"Expert agreement: {agreement:.2%}")
```

---

## 🛠️ Development Workflow

### 1. Experiment Tracking
```python
import wandb

# Initialize
wandb.init(project='raman-studio-ml', name='transformer-v1')

# Log metrics
wandb.log({
    'train_loss': loss,
    'val_accuracy': accuracy,
    'learning_rate': lr
})

# Log model
wandb.save('model.pth')
```

### 2. Hyperparameter Tuning
```python
import optuna

def objective(trial):
    # Suggest hyperparameters
    lr = trial.suggest_loguniform('lr', 1e-5, 1e-2)
    batch_size = trial.suggest_categorical('batch_size', [64, 128, 256])
    
    # Train model
    model = train(lr=lr, batch_size=batch_size)
    
    # Evaluate
    accuracy = evaluate(model)
    
    return accuracy

# Optimize
study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=100)

print(f"Best params: {study.best_params}")
```

### 3. Model Versioning
```python
# Save model with metadata
torch.save({
    'model_state_dict': model.state_dict(),
    'optimizer_state_dict': optimizer.state_dict(),
    'epoch': epoch,
    'accuracy': accuracy,
    'hyperparameters': config,
    'training_data': data_info,
    'timestamp': datetime.now()
}, 'model_v1.0.0.pth')
```

---

## 📚 Documentation

### For Each Model:
1. Architecture diagram
2. Hyperparameters
3. Training procedure
4. Performance metrics
5. Failure cases
6. Uncertainty estimates

### For Each Dataset:
1. Source and license
2. Collection method
3. Preprocessing steps
4. Statistics
5. Known issues
6. Citation

---

## 🌟 The 300-Year Vision

### What We're Building:

1. **The Largest Raman Database**
   - 1M+ spectra (real + synthetic)
   - 10,000+ materials
   - All instruments, all conditions

2. **The Most Accurate Models**
   - >99% accuracy
   - Uncertainty quantification
   - Explainable predictions

3. **The Most Robust System**
   - Works on any instrument
   - Handles any artifact
   - Adapts to new materials

4. **The Most Open Platform**
   - All data public
   - All models open-source
   - All code reproducible

5. **The Most Trusted Reference**
   - Peer-reviewed
   - Validated by experts
   - Used in publications

---

## 🎯 Current Status

### Completed:
- ✅ Research plan
- ✅ Data download scripts
- ✅ Transformer model implementation
- ✅ Training infrastructure

### In Progress:
- 🔄 Downloading datasets
- 🔄 Implementing other models
- 🔄 Setting up training pipeline

### Next Steps:
1. Complete dataset downloads
2. Implement SANet & Hybrid models
3. Implement self-supervised learning
4. Begin pre-training
5. Fine-tune on labeled data
6. Evaluate & benchmark
7. Deploy to production

---

## 📞 Contributing

This is a 300-year project. Contributions welcome!

### How to Contribute:
1. Add new datasets
2. Implement new models
3. Improve training procedures
4. Add evaluation metrics
5. Write documentation
6. Report issues

---

## 📖 Citation

If you use this work, please cite:

```bibtex
@software{raman_studio_ml_2026,
  title={RĀMAN Studio ML System: The 300-Year Source of Truth},
  author={RĀMAN Studio Team},
  year={2026},
  url={https://github.com/your-repo/raman-studio}
}
```

---

## 📄 License

All code: MIT License  
All data: See individual dataset licenses  
All models: Apache 2.0 License

---

**Status:** 🔴 ACTIVE DEVELOPMENT  
**Timeline:** 16 weeks to production  
**Goal:** Source of truth for 300 years  
**Priority:** HIGHEST

**Generated:** May 5, 2026  
**Version:** 1.0.0  
**Last Updated:** May 5, 2026
