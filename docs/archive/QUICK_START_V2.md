# CV Transformer V2: Quick Start Guide

**Date:** May 6, 2026  
**Goal:** Upgrade to world-class ML system in 8 weeks  
**Current Status:** V1 baseline (85% accuracy, 34.76ms, no uncertainty)  
**Target Status:** V2 world-class (95-98% accuracy, physics-informed, interpretable)

---

## 🔥 Week 1: Start Here (3-4 Days)

### **Day 1-2: Uncertainty Quantification**

**File:** `src/backend/ml/models/cv_transformer_ensemble.py`

```python
#!/usr/bin/env python3
"""
CV Transformer Ensemble for Uncertainty Quantification
======================================================
Train 5 models, return mean ± std for all predictions
"""

import torch
import torch.nn as nn
from typing import Dict, List
from .cv_transformer import CVTransformer

class CVTransformerEnsemble(nn.Module):
    """Ensemble of CV Transformers for uncertainty quantification"""
    
    def __init__(self, num_models: int = 5, model_size: str = 'base'):
        super().__init__()
        self.num_models = num_models
        self.models = nn.ModuleList([
            CVTransformer(model_size=model_size) 
            for _ in range(num_models)
        ])
    
    def forward(self, current: torch.Tensor, task: str = 'all') -> Dict[str, torch.Tensor]:
        """
        Forward pass through ensemble
        
        Returns:
            Dictionary with predictions and uncertainties:
            - mechanism: (batch, num_classes) - mean prediction
            - mechanism_uncertainty: (batch, num_classes) - std
            - reversibility: (batch, 1) - mean
            - reversibility_uncertainty: (batch, 1) - std
            ... (same for all outputs)
        """
        # Get predictions from all models
        predictions = [model(current, task=task) for model in self.models]
        
        # Compute mean and std for each output
        results = {}
        for key in predictions[0].keys():
            stacked = torch.stack([p[key] for p in predictions], dim=0)
            results[key] = stacked.mean(dim=0)
            results[f"{key}_uncertainty"] = stacked.std(dim=0)
        
        return results
    
    def load_ensemble(self, checkpoint_dir: str):
        """Load pre-trained ensemble from directory"""
        for i, model in enumerate(self.models):
            checkpoint = torch.load(f"{checkpoint_dir}/model_{i}.pt")
            model.load_state_dict(checkpoint['model_state_dict'])
    
    def save_ensemble(self, checkpoint_dir: str):
        """Save ensemble to directory"""
        import os
        os.makedirs(checkpoint_dir, exist_ok=True)
        for i, model in enumerate(self.models):
            torch.save({
                'model_state_dict': model.state_dict()
            }, f"{checkpoint_dir}/model_{i}.pt")


if __name__ == "__main__":
    # Test ensemble
    ensemble = CVTransformerEnsemble(num_models=5, model_size='base')
    
    # Dummy input
    batch_size = 4
    data_points = 2000
    current = torch.randn(batch_size, 1, data_points)
    
    # Forward pass
    outputs = ensemble(current, task='all')
    
    print("Ensemble outputs:")
    for key, value in outputs.items():
        print(f"  {key}: {value.shape}")
    
    # Check uncertainty
    print(f"\nReversibility predictions:")
    print(f"  Mean: {outputs['reversibility'].squeeze()}")
    print(f"  Uncertainty: {outputs['reversibility_uncertainty'].squeeze()}")
```

**Training Script:** `src/backend/ml/training/train_ensemble.py`

```python
#!/usr/bin/env python3
"""Train CV Transformer Ensemble"""

import torch
from pathlib import Path
from ..models.cv_transformer_ensemble import CVTransformerEnsemble
from .train_cv import CVDataLoader, CVDataset, CONFIG

def train_ensemble():
    """Train ensemble of 5 models with different seeds"""
    
    # Load data
    data_loader = CVDataLoader()
    data_loader.load_ebio_data()
    samples = data_loader.get_samples()
    dataset = CVDataset(samples, data_points=CONFIG['data_points'])
    
    # Create ensemble
    ensemble = CVTransformerEnsemble(num_models=5, model_size='base')
    
    # Train each model with different seed
    for i, model in enumerate(ensemble.models):
        print(f"\n{'='*80}")
        print(f"Training Model {i+1}/5")
        print(f"{'='*80}")
        
        # Set seed for reproducibility
        torch.manual_seed(42 + i)
        
        # Train model (use existing training loop)
        # ... (copy from train_cv.py)
        
        # Save checkpoint
        torch.save({
            'model_state_dict': model.state_dict()
        }, f"models/cv_transformer/ensemble/model_{i}.pt")
    
    # Save full ensemble
    ensemble.save_ensemble("models/cv_transformer/ensemble")
    print("\n✅ Ensemble training complete!")

if __name__ == "__main__":
    train_ensemble()
```

**Run:** `py -3.12 src/backend/ml/training/train_ensemble.py`

---

### **Day 2-3: Attention Visualization**

**File:** `src/backend/ml/visualization/attention_viz.py`

```python
#!/usr/bin/env python3
"""Attention Visualization for CV Transformer"""

import torch
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

def extract_attention_weights(model, current):
    """Extract attention weights from transformer layers"""
    
    # Hook to capture attention weights
    attention_weights = []
    
    def hook_fn(module, input, output):
        # output[1] contains attention weights
        attention_weights.append(output[1].detach().cpu())
    
    # Register hooks on transformer layers
    hooks = []
    for layer in model.transformer.layers:
        hook = layer.self_attn.register_forward_hook(hook_fn)
        hooks.append(hook)
    
    # Forward pass
    with torch.no_grad():
        _ = model(current)
    
    # Remove hooks
    for hook in hooks:
        hook.remove()
    
    return attention_weights

def visualize_attention(attention_weights, voltage, current, save_path=None):
    """Visualize attention heatmap"""
    
    # Average attention across heads and layers
    avg_attention = torch.stack(attention_weights).mean(dim=[0, 1, 2])
    
    # Create figure
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    
    # Plot CV curve
    axes[0].plot(voltage, current, 'b-', linewidth=2)
    axes[0].set_xlabel('Voltage (V)')
    axes[0].set_ylabel('Current (A)')
    axes[0].set_title('Cyclic Voltammogram')
    axes[0].grid(True, alpha=0.3)
    
    # Plot attention heatmap
    sns.heatmap(avg_attention.numpy(), ax=axes[1], cmap='viridis')
    axes[1].set_xlabel('Sequence Position')
    axes[1].set_ylabel('Sequence Position')
    axes[1].set_title('Attention Weights (Averaged)')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    else:
        plt.show()

# Example usage
if __name__ == "__main__":
    from ..models.cv_transformer import create_cv_transformer
    
    # Load model
    model = create_cv_transformer('base')
    checkpoint = torch.load('models/cv_transformer/cv_transformer_best.pt')
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    # Load sample CV data
    current = torch.randn(1, 1, 2000)
    
    # Extract attention
    attention_weights = extract_attention_weights(model, current)
    
    # Visualize
    voltage = np.linspace(-0.5, 0.5, 2000)
    current_data = current.squeeze().numpy()
    visualize_attention(attention_weights, voltage, current_data, 
                       save_path='attention_viz.png')
```

---

### **Day 3-4: Anomaly Detection**

**File:** `src/backend/ml/models/anomaly_detector.py`

```python
#!/usr/bin/env python3
"""Anomaly Detection for CV Measurements"""

import torch
import torch.nn as nn
import torch.nn.functional as F

class CVAnomalyDetector(nn.Module):
    """Autoencoder-based anomaly detection for CV curves"""
    
    def __init__(self, data_points: int = 2000, latent_dim: int = 64):
        super().__init__()
        
        # Encoder
        self.encoder = nn.Sequential(
            nn.Conv1d(1, 32, kernel_size=21, padding=10),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(32, 64, kernel_size=11, padding=5),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(64, 128, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(128, latent_dim)
        )
        
        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, data_points),
            nn.Unflatten(1, (1, data_points))
        )
        
        # Anomaly threshold (learned during training)
        self.register_buffer('threshold', torch.tensor(0.1))
    
    def forward(self, x):
        """
        Args:
            x: (batch, 1, data_points) - CV current
        Returns:
            reconstruction: (batch, 1, data_points)
            reconstruction_error: (batch,)
            is_anomaly: (batch,) - boolean
        """
        # Encode
        z = self.encoder(x)
        
        # Decode
        x_recon = self.decoder(z)
        
        # Reconstruction error
        recon_error = F.mse_loss(x, x_recon, reduction='none').mean(dim=[1, 2])
        
        # Anomaly detection
        is_anomaly = recon_error > self.threshold
        
        return {
            'reconstruction': x_recon,
            'reconstruction_error': recon_error,
            'is_anomaly': is_anomaly,
            'latent': z
        }
    
    def set_threshold(self, normal_data, percentile=95):
        """Set anomaly threshold based on normal data"""
        with torch.no_grad():
            outputs = self(normal_data)
            errors = outputs['reconstruction_error']
            self.threshold = torch.quantile(errors, percentile / 100.0)
        print(f"Anomaly threshold set to: {self.threshold.item():.6f}")


# Training script
def train_anomaly_detector():
    """Train anomaly detector on normal CV curves"""
    
    from ..training.train_cv import CVDataLoader, CVDataset, CONFIG
    
    # Load data
    data_loader = CVDataLoader()
    data_loader.load_ebio_data()
    samples = data_loader.get_samples()
    dataset = CVDataset(samples, data_points=CONFIG['data_points'])
    
    # Create model
    model = CVAnomalyDetector(data_points=CONFIG['data_points'])
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    
    # Train
    model.train()
    for epoch in range(50):
        total_loss = 0
        for batch in dataloader:
            current = batch['current']
            
            # Forward
            outputs = model(current)
            loss = outputs['reconstruction_error'].mean()
            
            # Backward
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        print(f"Epoch {epoch+1}: Loss = {total_loss/len(dataloader):.6f}")
    
    # Set threshold on training data
    all_data = torch.cat([batch['current'] for batch in dataloader])
    model.set_threshold(all_data, percentile=95)
    
    # Save
    torch.save({
        'model_state_dict': model.state_dict(),
        'threshold': model.threshold
    }, 'models/cv_transformer/anomaly_detector.pt')
    
    print("✅ Anomaly detector trained!")

if __name__ == "__main__":
    train_anomaly_detector()
```

---

## 📊 Week 1 Deliverables

After 3-4 days, you should have:

1. ✅ **Ensemble Model** - 5 models returning mean ± std
2. ✅ **Attention Visualization** - Heatmaps showing what model focuses on
3. ✅ **Anomaly Detection** - Flags bad measurements in real-time

**Test:**
```bash
# Train ensemble
py -3.12 src/backend/ml/training/train_ensemble.py

# Evaluate with uncertainty
py -3.12 src/backend/ml/evaluation/evaluate_ensemble.py

# Visualize attention
py -3.12 src/backend/ml/visualization/attention_viz.py

# Test anomaly detection
py -3.12 src/backend/ml/models/anomaly_detector.py
```

---

## 🎯 Success Metrics (Week 1)

- ✅ Ensemble inference time <50ms
- ✅ Uncertainty calibration ECE <0.15
- ✅ Attention visualization working
- ✅ Anomaly detector catches >90% of bad curves

---

## 📅 Next Steps

**Week 2:** Physics-informed loss (Butler-Volmer, Nernst, Randles-Sevcik)  
**Week 3:** Contrastive pre-training on 1,710 samples  
**Week 4-5:** Peak localization (EchemNet-style)  
**Week 6-7:** Multi-modal (CV + EIS + metadata)  
**Week 8:** Testing & deployment

---

## 📚 Resources

- **Full Research:** `SOTA_RESEARCH_2026.md` (50+ papers analyzed)
- **Implementation Plan:** `RESEARCH_SUMMARY_AND_NEXT_STEPS.md` (8-week roadmap)
- **Current Model:** `src/backend/ml/models/cv_transformer.py`
- **Training Script:** `src/backend/ml/training/train_cv.py`

---

**Author:** VidyuthLabs  
**Date:** May 6, 2026  
**Status:** Ready to Code  
**Next Action:** Create `cv_transformer_ensemble.py` and start training!

🚀 **Let's make this the best electrochemical ML system in the world!**

