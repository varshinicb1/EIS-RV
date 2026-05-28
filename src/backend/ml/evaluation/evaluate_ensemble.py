#!/usr/bin/env python3
"""
Evaluate CV Transformer Ensemble
=================================
Comprehensive evaluation of ensemble uncertainty quantification

Features:
- Expected Calibration Error (ECE)
- Reliability diagrams
- Uncertainty vs accuracy analysis
- Confidence interval coverage
- Performance metrics

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
import torch.nn as nn
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
OUTPUT_DIR = BASE_DIR / "models" / "cv_transformer_ensemble" / "evaluation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)


class EnsembleEvaluator:
    """Evaluator for CV Transformer Ensemble"""
    
    def __init__(self, model_dir: Path, device: str = 'cuda'):
        self.model_dir = model_dir
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        
        logger.info(f"Evaluation device: {self.device}")
        
        # Load ensemble
        logger.info("Loading ensemble...")
        self.ensemble = create_cv_transformer_ensemble(num_models=5, model_size='base')
        self.ensemble.load_ensemble(model_dir)
        self.ensemble.to(self.device)
        self.ensemble.eval()
        
        logger.info("✅ Ensemble loaded successfully")
    
    def compute_ece(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        confidences: np.ndarray,
        num_bins: int = 10
    ) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute Expected Calibration Error (ECE)
        
        Args:
            predictions: Predicted classes (N,)
            targets: Ground truth classes (N,)
            confidences: Predicted confidences (N,)
            num_bins: Number of bins
        
        Returns:
            ece: Expected Calibration Error
            bin_accuracies: Accuracy per bin
            bin_confidences: Average confidence per bin
            bin_counts: Number of samples per bin
        """
        # Create bins
        bin_boundaries = np.linspace(0, 1, num_bins + 1)
        bin_lowers = bin_boundaries[:-1]
        bin_uppers = bin_boundaries[1:]
        
        # Initialize
        bin_accuracies = np.zeros(num_bins)
        bin_confidences = np.zeros(num_bins)
        bin_counts = np.zeros(num_bins)
        
        # Compute accuracy
        accuracies = (predictions == targets).astype(float)
        
        # Bin samples
        ece = 0.0
        for i, (bin_lower, bin_upper) in enumerate(zip(bin_lowers, bin_uppers)):
            # Find samples in bin
            in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
            bin_count = in_bin.sum()
            
            if bin_count > 0:
                # Average confidence in bin
                bin_confidence = confidences[in_bin].mean()
                bin_confidences[i] = bin_confidence
                
                # Average accuracy in bin
                bin_accuracy = accuracies[in_bin].mean()
                bin_accuracies[i] = bin_accuracy
                
                # Count
                bin_counts[i] = bin_count
                
                # Weighted contribution to ECE
                ece += (bin_count / len(predictions)) * np.abs(bin_confidence - bin_accuracy)
        
        return ece, bin_accuracies, bin_confidences, bin_counts
    
    def plot_reliability_diagram(
        self,
        bin_accuracies: np.ndarray,
        bin_confidences: np.ndarray,
        bin_counts: np.ndarray,
        ece: float,
        save_path: Path
    ):
        """Plot reliability diagram"""
        fig, ax = plt.subplots(figsize=(10, 10))
        
        # Plot perfect calibration line
        ax.plot([0, 1], [0, 1], 'k--', label='Perfect Calibration', linewidth=2)
        
        # Plot actual calibration
        # Filter out empty bins
        mask = bin_counts > 0
        ax.plot(
            bin_confidences[mask],
            bin_accuracies[mask],
            'o-',
            label='Model Calibration',
            linewidth=2,
            markersize=10,
            color='#2E86AB'
        )
        
        # Add bar chart for bin counts
        ax2 = ax.twinx()
        ax2.bar(
            bin_confidences[mask],
            bin_counts[mask],
            width=0.08,
            alpha=0.3,
            color='#A23B72',
            label='Sample Count'
        )
        
        # Labels and title
        ax.set_xlabel('Confidence', fontsize=14, fontweight='bold')
        ax.set_ylabel('Accuracy', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Sample Count', fontsize=14, fontweight='bold')
        ax.set_title(
            f'Reliability Diagram\nECE = {ece:.4f}',
            fontsize=16,
            fontweight='bold'
        )
        
        # Grid and legend
        ax.grid(True, alpha=0.3)
        ax.set_xlim([0, 1])
        ax.set_ylim([0, 1])
        
        # Combine legends
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=12)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"✅ Reliability diagram saved to {save_path}")
    
    def plot_uncertainty_vs_error(
        self,
        uncertainties: np.ndarray,
        errors: np.ndarray,
        save_path: Path
    ):
        """Plot uncertainty vs prediction error"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # Scatter plot
        ax1.scatter(uncertainties, errors, alpha=0.5, s=20, color='#2E86AB')
        ax1.set_xlabel('Predicted Uncertainty (Std)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Prediction Error (Absolute)', fontsize=12, fontweight='bold')
        ax1.set_title('Uncertainty vs Error', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Correlation
        correlation = np.corrcoef(uncertainties, errors)[0, 1]
        ax1.text(
            0.05, 0.95,
            f'Correlation: {correlation:.3f}',
            transform=ax1.transAxes,
            fontsize=12,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        )
        
        # Binned analysis
        num_bins = 10
        bin_edges = np.percentile(uncertainties, np.linspace(0, 100, num_bins + 1))
        bin_indices = np.digitize(uncertainties, bin_edges[:-1])
        
        bin_mean_uncertainty = []
        bin_mean_error = []
        bin_std_error = []
        
        for i in range(1, num_bins + 1):
            mask = bin_indices == i
            if mask.sum() > 0:
                bin_mean_uncertainty.append(uncertainties[mask].mean())
                bin_mean_error.append(errors[mask].mean())
                bin_std_error.append(errors[mask].std())
        
        bin_mean_uncertainty = np.array(bin_mean_uncertainty)
        bin_mean_error = np.array(bin_mean_error)
        bin_std_error = np.array(bin_std_error)
        
        # Plot binned results
        ax2.errorbar(
            bin_mean_uncertainty,
            bin_mean_error,
            yerr=bin_std_error,
            fmt='o-',
            linewidth=2,
            markersize=8,
            capsize=5,
            color='#A23B72',
            label='Mean ± Std'
        )
        ax2.set_xlabel('Predicted Uncertainty (Std)', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Prediction Error (Mean ± Std)', fontsize=12, fontweight='bold')
        ax2.set_title('Binned Uncertainty vs Error', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=12)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"✅ Uncertainty vs error plot saved to {save_path}")
    
    def evaluate_regression_task(
        self,
        test_loader: DataLoader,
        task_name: str = 'reversibility'
    ) -> Dict:
        """Evaluate regression task with uncertainty"""
        logger.info(f"\nEvaluating {task_name}...")
        
        predictions = []
        uncertainties = []
        targets = []
        
        with torch.no_grad():
            for batch in tqdm(test_loader, desc=f"Evaluating {task_name}"):
                current = batch['current'].to(self.device)
                
                # Get predictions with uncertainty
                outputs = self.ensemble(current, task='all')
                
                if task_name in outputs:
                    pred = outputs[task_name].cpu().numpy()
                    unc = outputs[f'{task_name}_uncertainty'].cpu().numpy()
                    
                    predictions.append(pred)
                    uncertainties.append(unc)
                    
                    # Use actual targets from labels if available, else default to 0
                    if 'labels' in batch and task_name in batch['labels']:
                        targets.append(batch['labels'][task_name].cpu().numpy())
                    else:
                        targets.append(np.zeros_like(pred))
        
        # Concatenate
        predictions = np.concatenate(predictions, axis=0).flatten()
        uncertainties = np.concatenate(uncertainties, axis=0).flatten()
        targets = np.concatenate(targets, axis=0).flatten()
        
        # Compute metrics
        errors = np.abs(predictions - targets)
        mae = errors.mean()
        rmse = np.sqrt((errors ** 2).mean())
        
        # Uncertainty correlation
        correlation = np.corrcoef(uncertainties, errors)[0, 1]
        
        # Coverage (percentage of targets within 1-sigma)
        within_1sigma = np.abs(predictions - targets) <= uncertainties
        coverage_1sigma = within_1sigma.mean()
        
        within_2sigma = np.abs(predictions - targets) <= 2 * uncertainties
        coverage_2sigma = within_2sigma.mean()
        
        results = {
            'task': task_name,
            'mae': float(mae),
            'rmse': float(rmse),
            'mean_uncertainty': float(uncertainties.mean()),
            'std_uncertainty': float(uncertainties.std()),
            'uncertainty_error_correlation': float(correlation),
            'coverage_1sigma': float(coverage_1sigma),
            'coverage_2sigma': float(coverage_2sigma),
            'expected_coverage_1sigma': 0.68,
            'expected_coverage_2sigma': 0.95,
        }
        
        logger.info(f"\n{task_name} Results:")
        logger.info(f"  MAE: {mae:.4f}")
        logger.info(f"  RMSE: {rmse:.4f}")
        logger.info(f"  Mean Uncertainty: {uncertainties.mean():.4f}")
        logger.info(f"  Uncertainty-Error Correlation: {correlation:.4f}")
        logger.info(f"  Coverage (1σ): {coverage_1sigma:.2%} (expected: 68%)")
        logger.info(f"  Coverage (2σ): {coverage_2sigma:.2%} (expected: 95%)")
        
        # Plot
        self.plot_uncertainty_vs_error(
            uncertainties,
            errors,
            OUTPUT_DIR / f'{task_name}_uncertainty_vs_error.png'
        )
        
        return results
    
    def evaluate_classification_task(
        self,
        test_loader: DataLoader,
        task_name: str = 'mechanism',
        num_classes: int = 5
    ) -> Dict:
        """Evaluate classification task with uncertainty"""
        logger.info(f"\nEvaluating {task_name}...")
        
        all_predictions = []
        all_confidences = []
        all_targets = []
        
        with torch.no_grad():
            for batch in tqdm(test_loader, desc=f"Evaluating {task_name}"):
                current = batch['current'].to(self.device)
                
                # Get predictions with uncertainty
                outputs = self.ensemble(current, task='all')
                
                if task_name in outputs:
                    logits = outputs[task_name]
                    probs = torch.softmax(logits, dim=-1)
                    
                    pred_classes = logits.argmax(dim=-1).cpu().numpy()
                    confidences = probs.max(dim=-1)[0].cpu().numpy()
                    
                    all_predictions.append(pred_classes)
                    all_confidences.append(confidences)
                    
                    # Use actual targets from labels if available, else default to 0
                    if 'labels' in batch and task_name in batch['labels']:
                        batch_targets = batch['labels'][task_name].cpu().numpy()
                        # Handle cases where label is missing (-1)
                        batch_targets = np.where(batch_targets == -1, 0, batch_targets)
                        all_targets.append(batch_targets)
                    else:
                        all_targets.append(np.zeros_like(pred_classes))
        
        # Concatenate
        predictions = np.concatenate(all_predictions, axis=0)
        confidences = np.concatenate(all_confidences, axis=0)
        targets = np.concatenate(all_targets, axis=0)
        
        # Compute accuracy
        accuracy = (predictions == targets).mean()
        
        # Compute ECE
        ece, bin_accuracies, bin_confidences, bin_counts = self.compute_ece(
            predictions, targets, confidences, num_bins=10
        )
        
        results = {
            'task': task_name,
            'accuracy': float(accuracy),
            'ece': float(ece),
            'mean_confidence': float(confidences.mean()),
            'std_confidence': float(confidences.std()),
        }
        
        logger.info(f"\n{task_name} Results:")
        logger.info(f"  Accuracy: {accuracy:.2%}")
        logger.info(f"  ECE: {ece:.4f}")
        logger.info(f"  Mean Confidence: {confidences.mean():.4f}")
        
        # Plot reliability diagram
        self.plot_reliability_diagram(
            bin_accuracies,
            bin_confidences,
            bin_counts,
            ece,
            OUTPUT_DIR / f'{task_name}_reliability_diagram.png'
        )
        
        return results
    
    def evaluate(self, test_loader: DataLoader) -> Dict:
        """Full evaluation"""
        logger.info("\n" + "="*80)
        logger.info("ENSEMBLE EVALUATION")
        logger.info("="*80)
        
        results = {}
        
        # Evaluate regression tasks
        regression_tasks = ['reversibility', 'peak_separation', 'diffusion_coefficient']
        for task in regression_tasks:
            try:
                results[task] = self.evaluate_regression_task(test_loader, task)
            except Exception as e:
                logger.warning(f"Could not evaluate {task}: {e}")
        
        # Evaluate classification tasks
        classification_tasks = [
            ('mechanism', 5),
            ('species', 100)
        ]
        for task, num_classes in classification_tasks:
            try:
                results[task] = self.evaluate_classification_task(
                    test_loader, task, num_classes
                )
            except Exception as e:
                logger.warning(f"Could not evaluate {task}: {e}")
        
        # Save results
        results_path = OUTPUT_DIR / 'evaluation_results.json'
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"\n✅ Results saved to {results_path}")
        
        # Summary
        logger.info("\n" + "="*80)
        logger.info("EVALUATION SUMMARY")
        logger.info("="*80)
        
        for task, metrics in results.items():
            logger.info(f"\n{task.upper()}:")
            for key, value in metrics.items():
                if isinstance(value, float):
                    logger.info(f"  {key}: {value:.4f}")
                else:
                    logger.info(f"  {key}: {value}")
        
        logger.info("\n" + "="*80)
        logger.info("EVALUATION COMPLETE")
        logger.info("="*80)
        logger.info(f"Results saved to: {OUTPUT_DIR}")
        logger.info("\nNext steps:")
        logger.info("1. Review reliability diagrams")
        logger.info("2. Check uncertainty calibration")
        logger.info("3. Integrate ensemble into API")
        logger.info("="*80)
        
        return results


def main():
    """Main evaluation function"""
    logger.info("="*80)
    logger.info("CV TRANSFORMER ENSEMBLE EVALUATION")
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
    
    # Create evaluator
    evaluator = EnsembleEvaluator(MODEL_DIR)
    
    # Evaluate
    results = evaluator.evaluate(test_loader)


if __name__ == "__main__":
    main()
