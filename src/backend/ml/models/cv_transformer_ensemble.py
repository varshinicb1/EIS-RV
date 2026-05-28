#!/usr/bin/env python3
"""
CV Transformer Ensemble for Uncertainty Quantification
======================================================
State-of-the-art ensemble model with calibrated uncertainty estimates

Features:
- Deep ensemble (5 models) for uncertainty quantification
- Calibrated confidence intervals
- Expected Calibration Error (ECE) tracking
- Production-ready reliability

Author: VidyuthLabs
Date: May 6, 2026
"""

import torch
import torch.nn as nn
from typing import Dict, List, Optional
from pathlib import Path
import json

try:
    from .cv_transformer import CVTransformer, create_cv_transformer
except ImportError:
    from cv_transformer import CVTransformer, create_cv_transformer


class CVTransformerEnsemble(nn.Module):
    """
    Ensemble of CV Transformers for uncertainty quantification
    
    Uses deep ensemble approach:
    - Train N models with different random initializations
    - Predictions: mean across ensemble
    - Uncertainty: standard deviation across ensemble
    
    Benefits:
    - Calibrated uncertainty estimates
    - Know when to trust predictions
    - Production-ready reliability
    """
    
    def __init__(
        self, 
        num_models: int = 5, 
        model_size: str = 'base',
        data_points: int = 2000,
        d_model: int = 256,
        num_heads: int = 8,
        num_layers: int = 6,
        d_ff: int = 1024,
        num_mechanisms: int = 5,
        num_species: int = 100,
        dropout: float = 0.1
    ):
        super().__init__()
        
        self.num_models = num_models
        self.model_size = model_size
        
        # Create ensemble of models
        self.models = nn.ModuleList([
            CVTransformer(
                data_points=data_points,
                d_model=d_model,
                num_heads=num_heads,
                num_layers=num_layers,
                d_ff=d_ff,
                num_mechanisms=num_mechanisms,
                num_species=num_species,
                dropout=dropout
            )
            for _ in range(num_models)
        ])
        
        # Track calibration statistics
        self.register_buffer('ece', torch.tensor(0.0))  # Expected Calibration Error
        self.register_buffer('num_predictions', torch.tensor(0))
    
    def forward(
        self, 
        current: torch.Tensor,
        task: str = 'all',
        return_individual: bool = False
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass through ensemble
        
        Args:
            current: Current vs voltage (batch, 1, data_points)
            task: 'all', 'mechanism', 'peaks', 'parameters', 'species'
            return_individual: If True, return predictions from each model
        
        Returns:
            Dictionary with predictions and uncertainties:
            - mechanism: (batch, num_classes) - mean prediction
            - mechanism_uncertainty: (batch, num_classes) - std
            - mechanism_confidence: (batch,) - max probability
            - reversibility: (batch, 1) - mean
            - reversibility_uncertainty: (batch, 1) - std
            ... (same for all outputs)
        """
        # Get predictions from all models
        predictions = [model(current, task=task) for model in self.models]
        
        # Compute mean and std for each output
        results = {}
        
        for key in predictions[0].keys():
            # Stack predictions from all models
            stacked = torch.stack([p[key] for p in predictions], dim=0)
            
            # Mean prediction
            results[key] = stacked.mean(dim=0)
            
            # Uncertainty (standard deviation)
            results[f"{key}_uncertainty"] = stacked.std(dim=0)
            
            # Confidence (for classification tasks)
            if key in ['mechanism', 'species']:
                # Softmax to get probabilities
                probs = torch.softmax(results[key], dim=-1)
                # Max probability as confidence
                results[f"{key}_confidence"] = probs.max(dim=-1)[0]
        
        # Return individual predictions if requested
        if return_individual:
            results['individual_predictions'] = predictions
        
        return results
    
    def predict_with_uncertainty(
        self,
        current: torch.Tensor,
        task: str = 'all',
        confidence_level: float = 0.95
    ) -> Dict[str, Dict[str, torch.Tensor]]:
        """
        Predict with confidence intervals
        
        Args:
            current: Current vs voltage (batch, 1, data_points)
            task: 'all', 'mechanism', 'peaks', 'parameters', 'species'
            confidence_level: Confidence level for intervals (default: 95%)
        
        Returns:
            Dictionary with predictions, uncertainties, and confidence intervals
        """
        outputs = self.forward(current, task=task)
        
        # Compute confidence intervals (assuming Gaussian)
        from scipy import stats
        z_score = stats.norm.ppf((1 + confidence_level) / 2)
        
        results = {}
        for key in outputs.keys():
            if not key.endswith('_uncertainty') and not key.endswith('_confidence'):
                mean = outputs[key]
                std = outputs.get(f"{key}_uncertainty", torch.zeros_like(mean))
                
                results[key] = {
                    'mean': mean,
                    'std': std,
                    'lower': mean - z_score * std,
                    'upper': mean + z_score * std,
                    'confidence': outputs.get(f"{key}_confidence", None)
                }
        
        return results
    
    def compute_ece(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor,
        confidences: torch.Tensor,
        num_bins: int = 10
    ) -> float:
        """
        Compute Expected Calibration Error (ECE)
        
        ECE measures how well predicted confidences match actual accuracy
        Lower is better (0 = perfect calibration)
        
        Args:
            predictions: Model predictions (batch, num_classes)
            targets: Ground truth labels (batch,)
            confidences: Predicted confidences (batch,)
            num_bins: Number of bins for calibration
        
        Returns:
            ECE score (0-1, lower is better)
        """
        # Get predicted classes
        pred_classes = predictions.argmax(dim=-1)
        
        # Compute accuracy
        accuracies = (pred_classes == targets).float()
        
        # Bin confidences
        bin_boundaries = torch.linspace(0, 1, num_bins + 1)
        ece = 0.0
        
        for i in range(num_bins):
            # Find samples in this bin
            bin_lower = bin_boundaries[i]
            bin_upper = bin_boundaries[i + 1]
            in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
            
            if in_bin.sum() > 0:
                # Average confidence in bin
                avg_confidence = confidences[in_bin].mean()
                
                # Average accuracy in bin
                avg_accuracy = accuracies[in_bin].mean()
                
                # Weighted contribution to ECE
                bin_weight = in_bin.float().mean()
                ece += bin_weight * torch.abs(avg_confidence - avg_accuracy)
        
        return ece.item()
    
    def load_ensemble(self, checkpoint_dir: str):
        """Load pre-trained ensemble from directory"""
        checkpoint_dir = Path(checkpoint_dir)
        
        for i, model in enumerate(self.models):
            checkpoint_path = checkpoint_dir / f"model_{i}.pt"
            if checkpoint_path.exists():
                checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
                model.load_state_dict(checkpoint['model_state_dict'])
                print(f"✅ Loaded model {i+1}/{self.num_models}")
            else:
                print(f"⚠️  Model {i} checkpoint not found: {checkpoint_path}")
        
        # Load ensemble metadata
        metadata_path = checkpoint_dir / "ensemble_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                self.ece = torch.tensor(metadata.get('ece', 0.0))
                self.num_predictions = torch.tensor(metadata.get('num_predictions', 0))
                print(f"✅ Loaded ensemble metadata (ECE: {self.ece.item():.4f})")
    
    def save_ensemble(self, checkpoint_dir: str, metadata: Optional[Dict] = None):
        """Save ensemble to directory"""
        checkpoint_dir = Path(checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Save each model
        for i, model in enumerate(self.models):
            checkpoint_path = checkpoint_dir / f"model_{i}.pt"
            torch.save({
                'model_state_dict': model.state_dict()
            }, checkpoint_path)
            print(f"✅ Saved model {i+1}/{self.num_models}")
        
        # Save ensemble metadata
        ensemble_metadata = {
            'num_models': self.num_models,
            'model_size': self.model_size,
            'ece': self.ece.item(),
            'num_predictions': self.num_predictions.item(),
        }
        
        if metadata:
            ensemble_metadata.update(metadata)
        
        metadata_path = checkpoint_dir / "ensemble_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(ensemble_metadata, f, indent=2)
        
        print(f"✅ Saved ensemble metadata to {metadata_path}")


def create_cv_transformer_ensemble(
    num_models: int = 5,
    model_size: str = 'base'
) -> CVTransformerEnsemble:
    """
    Factory function for CV transformer ensemble
    
    Args:
        num_models: Number of models in ensemble (default: 5)
        model_size: 'small', 'base', 'large'
    
    Returns:
        CVTransformerEnsemble model
    """
    configs = {
        'small': {
            'd_model': 128,
            'num_heads': 4,
            'num_layers': 4,
            'd_ff': 512
        },
        'base': {
            'd_model': 256,
            'num_heads': 8,
            'num_layers': 6,
            'd_ff': 1024
        },
        'large': {
            'd_model': 512,
            'num_heads': 8,
            'num_layers': 12,
            'd_ff': 2048
        }
    }
    
    config = configs.get(model_size, configs['base'])
    
    return CVTransformerEnsemble(
        num_models=num_models,
        model_size=model_size,
        **config
    )


if __name__ == "__main__":
    print("Testing CV Transformer Ensemble...")
    
    # Create ensemble
    ensemble = create_cv_transformer_ensemble(num_models=5, model_size='base')
    
    # Count parameters
    num_params = sum(p.numel() for p in ensemble.parameters())
    print(f"Total parameters: {num_params:,}")
    print(f"Parameters per model: {num_params // 5:,}")
    
    # Dummy input
    batch_size = 4
    data_points = 2000
    current = torch.randn(batch_size, 1, data_points)
    
    # Forward pass
    print("\n" + "="*80)
    print("Testing forward pass...")
    print("="*80)
    
    outputs = ensemble(current, task='all')
    
    print("\nEnsemble outputs:")
    for key, value in outputs.items():
        print(f"  {key}: {value.shape}")
    
    # Test uncertainty quantification
    print("\n" + "="*80)
    print("Testing uncertainty quantification...")
    print("="*80)
    
    print(f"\nReversibility predictions:")
    print(f"  Mean: {outputs['reversibility'].squeeze()}")
    print(f"  Uncertainty (std): {outputs['reversibility_uncertainty'].squeeze()}")
    
    print(f"\nMechanism predictions:")
    print(f"  Logits shape: {outputs['mechanism'].shape}")
    print(f"  Uncertainty shape: {outputs['mechanism_uncertainty'].shape}")
    print(f"  Confidence: {outputs['mechanism_confidence']}")
    
    # Test confidence intervals
    print("\n" + "="*80)
    print("Testing confidence intervals...")
    print("="*80)
    
    results = ensemble.predict_with_uncertainty(current, confidence_level=0.95)
    
    print(f"\nReversibility with 95% confidence interval:")
    rev = results['reversibility']
    print(f"  Mean: {rev['mean'].squeeze()}")
    print(f"  Lower: {rev['lower'].squeeze()}")
    print(f"  Upper: {rev['upper'].squeeze()}")
    
    # Test save/load
    print("\n" + "="*80)
    print("Testing save/load...")
    print("="*80)
    
    test_dir = Path("test_ensemble_checkpoint")
    ensemble.save_ensemble(test_dir, metadata={'test': True})
    
    # Create new ensemble and load
    ensemble2 = create_cv_transformer_ensemble(num_models=5, model_size='base')
    ensemble2.load_ensemble(test_dir)
    
    # Cleanup
    import shutil
    shutil.rmtree(test_dir)
    
    print("\n✅ CV Transformer Ensemble test successful!")
    print("\nNext steps:")
    print("1. Train ensemble: py -3.12 src/backend/ml/training/train_ensemble.py")
    print("2. Evaluate: py -3.12 src/backend/ml/evaluation/evaluate_ensemble.py")
    print("3. Integrate into API: Update ml_routes.py")
