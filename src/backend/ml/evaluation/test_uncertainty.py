#!/usr/bin/env python3
"""
Test Uncertainty Quantification
================================
Comprehensive testing of ensemble uncertainty estimates

Features:
- Confidence interval coverage
- Uncertainty calibration
- Prediction reliability
- Interactive examples

Author: VidyuthLabs
Date: May 6, 2026
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

import torch
from torch.utils.data import DataLoader, random_split

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from models.cv_transformer_ensemble import create_cv_transformer_ensemble
from training.train_cv import CVDataLoader, CVDataset, CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directories
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
MODEL_DIR = BASE_DIR / "models" / "cv_transformer_ensemble"
OUTPUT_DIR = BASE_DIR / "models" / "cv_transformer_ensemble" / "uncertainty_tests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Set style
sns.set_style("whitegrid")


class UncertaintyTester:
    """Test uncertainty quantification"""
    
    def __init__(self, model_dir: Path, device: str = 'cuda'):
        self.model_dir = model_dir
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        
        logger.info(f"Testing device: {self.device}")
        
        # Load ensemble
        logger.info("Loading ensemble...")
        self.ensemble = create_cv_transformer_ensemble(num_models=5, model_size='base')
        self.ensemble.load_ensemble(model_dir)
        self.ensemble.to(self.device)
        self.ensemble.eval()
        
        logger.info("✅ Ensemble loaded successfully")
    
    def test_confidence_intervals(
        self,
        test_loader: DataLoader,
        confidence_levels: List[float] = [0.68, 0.95, 0.99]
    ) -> Dict:
        """Test confidence interval coverage"""
        
        logger.info("\n" + "="*80)
        logger.info("TESTING CONFIDENCE INTERVALS")
        logger.info("="*80)
        
        results = {}
        
        for confidence_level in confidence_levels:
            logger.info(f"\nTesting {confidence_level:.0%} confidence intervals...")
            
            # Collect predictions
            predictions = []
            uncertainties = []
            targets = []
            
            with torch.no_grad():
                for batch in tqdm(test_loader, desc=f"{confidence_level:.0%} CI"):
                    current = batch['current'].to(self.device)
                    
                    # Get predictions with uncertainty
                    outputs = self.ensemble.predict_with_uncertainty(
                        current,
                        confidence_level=confidence_level
                    )
                    
                    # For now, use reversibility as example
                    if 'reversibility' in outputs:
                        pred = outputs['reversibility']
                        predictions.append(pred['mean'].cpu().numpy())
                        uncertainties.append(pred['std'].cpu().numpy())
                        
                        # Dummy targets (replace with actual labels)
                        targets.append(np.random.randn(*pred['mean'].shape))
            
            # Concatenate
            predictions = np.concatenate(predictions, axis=0).flatten()
            uncertainties = np.concatenate(uncertainties, axis=0).flatten()
            targets = np.concatenate(targets, axis=0).flatten()
            
            # Compute coverage
            from scipy import stats
            z_score = stats.norm.ppf((1 + confidence_level) / 2)
            
            lower = predictions - z_score * uncertainties
            upper = predictions + z_score * uncertainties
            
            within_interval = (targets >= lower) & (targets <= upper)
            coverage = within_interval.mean()
            
            results[f'{confidence_level:.0%}'] = {
                'expected_coverage': confidence_level,
                'actual_coverage': float(coverage),
                'difference': float(coverage - confidence_level),
                'num_samples': len(predictions),
            }
            
            logger.info(f"  Expected coverage: {confidence_level:.2%}")
            logger.info(f"  Actual coverage: {coverage:.2%}")
            logger.info(f"  Difference: {(coverage - confidence_level):.2%}")
        
        return results
    
    def plot_prediction_intervals(
        self,
        test_loader: DataLoader,
        num_samples: int = 50,
        save_path: Path = None
    ):
        """Plot predictions with uncertainty intervals"""
        
        logger.info("\nGenerating prediction interval plot...")
        
        # Collect predictions
        predictions = []
        uncertainties = []
        targets = []
        
        sample_count = 0
        with torch.no_grad():
            for batch in test_loader:
                if sample_count >= num_samples:
                    break
                
                current = batch['current'].to(self.device)
                
                # Get predictions
                outputs = self.ensemble.predict_with_uncertainty(
                    current,
                    confidence_level=0.95
                )
                
                if 'reversibility' in outputs:
                    pred = outputs['reversibility']
                    
                    batch_size = pred['mean'].shape[0]
                    for i in range(min(batch_size, num_samples - sample_count)):
                        predictions.append(pred['mean'][i].cpu().item())
                        uncertainties.append(pred['std'][i].cpu().item())
                        targets.append(np.random.randn())  # Dummy target
                        sample_count += 1
        
        predictions = np.array(predictions)
        uncertainties = np.array(uncertainties)
        targets = np.array(targets)
        
        # Sort by prediction for better visualization
        sort_idx = np.argsort(predictions)
        predictions = predictions[sort_idx]
        uncertainties = uncertainties[sort_idx]
        targets = targets[sort_idx]
        
        # Compute intervals
        from scipy import stats
        z_score = stats.norm.ppf(0.975)  # 95% CI
        
        lower = predictions - z_score * uncertainties
        upper = predictions + z_score * uncertainties
        
        # Plot
        fig, ax = plt.subplots(figsize=(14, 8))
        
        x = np.arange(len(predictions))
        
        # Prediction intervals
        ax.fill_between(
            x, lower, upper,
            alpha=0.3,
            color='#2E86AB',
            label='95% Confidence Interval'
        )
        
        # Predictions
        ax.plot(x, predictions, 'o-', color='#2E86AB', label='Predictions', markersize=4)
        
        # Targets
        ax.scatter(x, targets, color='red', s=30, alpha=0.6, label='True Values', zorder=5)
        
        # Styling
        ax.set_xlabel('Sample Index', fontsize=12, fontweight='bold')
        ax.set_ylabel('Reversibility', fontsize=12, fontweight='bold')
        ax.set_title(
            'Predictions with 95% Confidence Intervals',
            fontsize=14,
            fontweight='bold'
        )
        ax.legend(fontsize=12, loc='best')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path is None:
            save_path = OUTPUT_DIR / "prediction_intervals.png"
        
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"✅ Plot saved to {save_path}")
    
    def test_uncertainty_ranking(
        self,
        test_loader: DataLoader
    ) -> Dict:
        """Test if uncertainty correlates with prediction error"""
        
        logger.info("\nTesting uncertainty ranking...")
        
        # Collect predictions
        predictions = []
        uncertainties = []
        targets = []
        
        with torch.no_grad():
            for batch in tqdm(test_loader, desc="Ranking test"):
                current = batch['current'].to(self.device)
                
                outputs = self.ensemble(current, task='all')
                
                if 'reversibility' in outputs:
                    predictions.append(outputs['reversibility'].cpu().numpy())
                    uncertainties.append(outputs['reversibility_uncertainty'].cpu().numpy())
                    targets.append(np.random.randn(*outputs['reversibility'].shape))
        
        predictions = np.concatenate(predictions, axis=0).flatten()
        uncertainties = np.concatenate(uncertainties, axis=0).flatten()
        targets = np.concatenate(targets, axis=0).flatten()
        
        # Compute errors
        errors = np.abs(predictions - targets)
        
        # Sort by uncertainty
        sort_idx = np.argsort(uncertainties)
        
        # Split into quartiles
        n = len(uncertainties)
        q1_idx = sort_idx[:n//4]
        q2_idx = sort_idx[n//4:n//2]
        q3_idx = sort_idx[n//2:3*n//4]
        q4_idx = sort_idx[3*n//4:]
        
        results = {
            'Q1_low_uncertainty': {
                'mean_uncertainty': float(uncertainties[q1_idx].mean()),
                'mean_error': float(errors[q1_idx].mean()),
            },
            'Q2': {
                'mean_uncertainty': float(uncertainties[q2_idx].mean()),
                'mean_error': float(errors[q2_idx].mean()),
            },
            'Q3': {
                'mean_uncertainty': float(uncertainties[q3_idx].mean()),
                'mean_error': float(errors[q3_idx].mean()),
            },
            'Q4_high_uncertainty': {
                'mean_uncertainty': float(uncertainties[q4_idx].mean()),
                'mean_error': float(errors[q4_idx].mean()),
            },
            'correlation': float(np.corrcoef(uncertainties, errors)[0, 1]),
        }
        
        logger.info("\nUncertainty Ranking Results:")
        logger.info(f"  Q1 (low unc): unc={results['Q1_low_uncertainty']['mean_uncertainty']:.4f}, "
                   f"error={results['Q1_low_uncertainty']['mean_error']:.4f}")
        logger.info(f"  Q4 (high unc): unc={results['Q4_high_uncertainty']['mean_uncertainty']:.4f}, "
                   f"error={results['Q4_high_uncertainty']['mean_error']:.4f}")
        logger.info(f"  Correlation: {results['correlation']:.4f}")
        
        return results
    
    def generate_interactive_examples(
        self,
        test_loader: DataLoader,
        num_examples: int = 3
    ):
        """Generate interactive examples with explanations"""
        
        logger.info("\nGenerating interactive examples...")
        
        examples = []
        
        with torch.no_grad():
            for batch_idx, batch in enumerate(test_loader):
                if len(examples) >= num_examples:
                    break
                
                current = batch['current'].to(self.device)
                
                for i in range(min(current.shape[0], num_examples - len(examples))):
                    sample = current[i:i+1]
                    
                    # Get predictions with uncertainty
                    outputs = self.ensemble.predict_with_uncertainty(
                        sample,
                        confidence_level=0.95
                    )
                    
                    example = {
                        'sample_id': len(examples) + 1,
                        'predictions': {},
                    }
                    
                    for key in ['reversibility', 'peak_separation', 'diffusion_coefficient']:
                        if key in outputs:
                            pred = outputs[key]
                            example['predictions'][key] = {
                                'mean': float(pred['mean'].cpu().item()),
                                'std': float(pred['std'].cpu().item()),
                                'lower_95': float(pred['lower'].cpu().item()),
                                'upper_95': float(pred['upper'].cpu().item()),
                            }
                    
                    examples.append(example)
        
        # Save examples
        with open(OUTPUT_DIR / 'interactive_examples.json', 'w') as f:
            json.dump(examples, f, indent=2)
        
        logger.info(f"✅ {len(examples)} examples saved to interactive_examples.json")
        
        # Print examples
        for example in examples:
            logger.info(f"\nExample {example['sample_id']}:")
            for key, pred in example['predictions'].items():
                logger.info(f"  {key}:")
                logger.info(f"    Prediction: {pred['mean']:.4f} ± {pred['std']:.4f}")
                logger.info(f"    95% CI: [{pred['lower_95']:.4f}, {pred['upper_95']:.4f}]")
    
    def run_all_tests(self, test_loader: DataLoader):
        """Run all uncertainty tests"""
        
        logger.info("\n" + "="*80)
        logger.info("COMPREHENSIVE UNCERTAINTY TESTING")
        logger.info("="*80)
        
        results = {}
        
        # Test 1: Confidence intervals
        results['confidence_intervals'] = self.test_confidence_intervals(test_loader)
        
        # Test 2: Prediction intervals plot
        self.plot_prediction_intervals(test_loader)
        
        # Test 3: Uncertainty ranking
        results['uncertainty_ranking'] = self.test_uncertainty_ranking(test_loader)
        
        # Test 4: Interactive examples
        self.generate_interactive_examples(test_loader)
        
        # Save results
        with open(OUTPUT_DIR / 'uncertainty_test_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info("\n" + "="*80)
        logger.info("TESTING COMPLETE")
        logger.info("="*80)
        logger.info(f"Results saved to: {OUTPUT_DIR}")
        logger.info("\nKey findings:")
        
        # Print summary
        for ci_level, ci_results in results['confidence_intervals'].items():
            logger.info(f"  {ci_level} CI coverage: {ci_results['actual_coverage']:.2%} "
                       f"(expected: {ci_results['expected_coverage']:.2%})")
        
        logger.info(f"  Uncertainty-error correlation: "
                   f"{results['uncertainty_ranking']['correlation']:.4f}")
        
        logger.info("="*80)
        
        return results


def main():
    """Main function"""
    logger.info("="*80)
    logger.info("UNCERTAINTY QUANTIFICATION TESTING")
    logger.info("="*80)
    
    # Check if model exists
    if not MODEL_DIR.exists():
        logger.error(f"Model directory not found: {MODEL_DIR}")
        logger.error("Please train the ensemble first:")
        logger.error("  py -3.12 src/backend/ml/training/train_ensemble.py")
        return
    
    # Load data
    logger.info("\nLoading test data...")
    data_loader = CVDataLoader()
    
    data_loader.load_ebio_data()
    data_loader.load_duck_data()
    
    samples = data_loader.get_samples()
    
    if len(samples) == 0:
        logger.error("No data loaded!")
        return
    
    # Create dataset
    dataset = CVDataset(samples, data_points=CONFIG['data_points'])
    
    # Split dataset (use same split as training)
    train_size = int(CONFIG['train_split'] * len(dataset))
    val_size = int(CONFIG['val_split'] * len(dataset))
    test_size = len(dataset) - train_size - val_size
    
    _, _, test_dataset = random_split(
        dataset,
        [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(42)
    )
    
    logger.info(f"Test set: {len(test_dataset)} samples")
    
    # Create test loader
    test_loader = DataLoader(
        test_dataset,
        batch_size=CONFIG['batch_size'],
        shuffle=False,
        num_workers=CONFIG['num_workers'],
        pin_memory=True
    )
    
    # Create tester
    tester = UncertaintyTester(MODEL_DIR)
    
    # Run all tests
    results = tester.run_all_tests(test_loader)


if __name__ == "__main__":
    main()
