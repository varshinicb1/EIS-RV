#!/usr/bin/env python3
"""
Generate Attention Visualizations
==================================
Create attention heatmaps and overlays for CV Transformer

Features:
- Attention heatmaps (all layers)
- CV overlay (attention on signal)
- Multi-head attention grids
- High-quality exports (300 DPI)

Author: VidyuthLabs
Date: May 6, 2026
"""

import os
import sys
import logging
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

import torch
from torch.utils.data import DataLoader, random_split

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from models.cv_transformer import CVTransformer, create_cv_transformer
from training.train_cv import CVDataLoader, CVDataset, CONFIG
from visualization.attention_viz import (
    AttentionExtractor,
    visualize_attention_heatmap,
    visualize_attention_on_cv,
    visualize_multi_head_attention,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directories
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
MODEL_DIR = BASE_DIR / "models" / "cv_transformer"
OUTPUT_DIR = BASE_DIR / "models" / "cv_transformer" / "attention_visualizations"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Set style
sns.set_style("whitegrid")


def load_model(model_path: Path, device: str = 'cuda') -> CVTransformer:
    """Load trained CV Transformer model"""
    logger.info(f"Loading model from {model_path}...")
    
    device = torch.device(device if torch.cuda.is_available() else 'cpu')
    
    # Create model
    model = create_cv_transformer(model_size='base')
    
    # Load checkpoint
    checkpoint = torch.load(model_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    
    model.to(device)
    model.eval()
    
    logger.info("✅ Model loaded successfully")
    return model, device


def generate_visualizations(
    model: CVTransformer,
    test_loader: DataLoader,
    device: torch.device,
    num_samples: int = 5
):
    """Generate attention visualizations for multiple samples"""
    
    logger.info("\n" + "="*80)
    logger.info("GENERATING ATTENTION VISUALIZATIONS")
    logger.info("="*80)
    logger.info(f"Number of samples: {num_samples}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info("="*80)
    
    # Create extractor
    extractor = AttentionExtractor(model)
    
    # Get samples
    sample_count = 0
    for batch_idx, batch in enumerate(test_loader):
        if sample_count >= num_samples:
            break
        
        current = batch['current'].to(device)
        voltage = batch.get('voltage', None)
        
        # Process each sample in batch
        for i in range(current.shape[0]):
            if sample_count >= num_samples:
                break
            
            sample_current = current[i:i+1]
            sample_voltage = voltage[i].cpu().numpy() if voltage is not None else None
            
            logger.info(f"\nProcessing sample {sample_count + 1}/{num_samples}...")
            
            # Extract attention weights
            attention_weights = extractor.extract(sample_current)
            current_np = sample_current[0, 0].cpu().numpy() if sample_current.dim() == 3 else sample_current[0].cpu().numpy()
            
            # 1. Attention heatmap
            logger.info("  Generating attention heatmap...")
            heatmap_path = OUTPUT_DIR / f"sample_{sample_count + 1}_heatmap.png"
            if attention_weights:
                visualize_attention_heatmap(
                    attention_weights,
                    layer_idx=-1,
                    save_path=str(heatmap_path),
                )
            
            # 2. CV overlay
            if sample_voltage is not None and attention_weights:
                logger.info("  Generating CV overlay...")
                overlay_path = OUTPUT_DIR / f"sample_{sample_count + 1}_overlay.png"
                visualize_attention_on_cv(
                    sample_voltage,
                    current_np,
                    attention_weights,
                    save_path=str(overlay_path),
                )
            
            # 3. Multi-head attention
            if attention_weights:
                logger.info("  Generating multi-head attention grid...")
                multihead_path = OUTPUT_DIR / f"sample_{sample_count + 1}_multihead.png"
                visualize_multi_head_attention(
                    attention_weights,
                    layer_idx=0,
                    save_path=str(multihead_path),
                )
            
            sample_count += 1
    
    logger.info("\n" + "="*80)
    logger.info("VISUALIZATION COMPLETE")
    logger.info("="*80)
    logger.info(f"Generated {sample_count * 3} visualizations")
    logger.info(f"Saved to: {OUTPUT_DIR}")
    logger.info("\nVisualization types:")
    logger.info("  - Attention heatmaps (layer-by-layer)")
    logger.info("  - CV overlays (attention on signal)")
    logger.info("  - Multi-head attention grids")
    logger.info("="*80)


def generate_summary_visualization(
    model: CVTransformer,
    test_loader: DataLoader,
    device: torch.device
):
    """Generate summary visualization with multiple samples"""
    logger.info("\nGenerating summary visualization...")

    extractor = AttentionExtractor(model)

    samples = []
    for batch in test_loader:
        current = batch['current'].to(device)
        for i in range(min(4, current.shape[0])):
            samples.append(current[i:i+1])
        if len(samples) >= 4:
            break

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()

    for idx, (sample, ax) in enumerate(zip(samples, axes)):
        attention_weights = extractor.extract(sample)
        if not attention_weights:
            continue
        # Average across layers and heads
        avg_attention = torch.stack([
            attn.mean(dim=1) for attn in attention_weights
        ]).mean(dim=0)

        im = ax.imshow(
            avg_attention[0].cpu().numpy(),
            cmap='viridis', aspect='auto', interpolation='nearest'
        )
        ax.set_title(f'Sample {idx + 1}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Key Position', fontsize=12)
        ax.set_ylabel('Query Position', fontsize=12)
        plt.colorbar(im, ax=ax)

    plt.suptitle('Attention Patterns Across Multiple Samples', fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()

    summary_path = OUTPUT_DIR / "attention_summary.png"
    plt.savefig(summary_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"✅ Summary visualization saved to {summary_path}")


def analyze_attention_patterns(
    model: CVTransformer,
    test_loader: DataLoader,
    device: torch.device
):
    """Analyze attention patterns across dataset"""
    logger.info("\nAnalyzing attention patterns...")

    extractor = AttentionExtractor(model)
    all_attention_stats = []

    for batch in test_loader:
        current = batch['current'].to(device)
        for i in range(current.shape[0]):
            sample = current[i:i+1]
            attention_weights = extractor.extract(sample)
            if not attention_weights:
                continue
            # Compute simple stats from last layer
            last = attention_weights[-1][0].mean(dim=0).cpu().numpy()  # (seq, seq)
            mean_attn = float(last.mean())
            max_attn  = float(last.max())
            # Entropy
            flat = last.flatten()
            flat = flat / (flat.sum() + 1e-10)
            entropy = float(-np.sum(flat * np.log(flat + 1e-10)))
            all_attention_stats.append({
                'mean_attention': mean_attn,
                'max_attention': max_attn,
                'attention_entropy': entropy,
            })
    
    # Aggregate statistics
    if not all_attention_stats:
        logger.warning("No attention stats collected")
        return

    avg_stats = {
        'mean_attention': np.mean([s['mean_attention'] for s in all_attention_stats]),
        'max_attention': np.mean([s['max_attention'] for s in all_attention_stats]),
        'attention_entropy': np.mean([s['attention_entropy'] for s in all_attention_stats]),
    }
    
    logger.info("\nAttention Pattern Statistics:")
    logger.info(f"  Mean attention: {avg_stats['mean_attention']:.6f}")
    logger.info(f"  Max attention: {avg_stats['max_attention']:.6f}")
    logger.info(f"  Attention entropy: {avg_stats['attention_entropy']:.6f}")
    
    # Plot attention statistics
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    # Mean attention distribution
    axes[0].hist(
        [s['mean_attention'] for s in all_attention_stats],
        bins=30,
        alpha=0.7,
        color='#2E86AB',
        edgecolor='black'
    )
    axes[0].set_xlabel('Mean Attention', fontsize=12, fontweight='bold')
    axes[0].set_ylabel('Frequency', fontsize=12, fontweight='bold')
    axes[0].set_title('Mean Attention Distribution', fontsize=14, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    
    # Max attention distribution
    axes[1].hist(
        [s['max_attention'] for s in all_attention_stats],
        bins=30,
        alpha=0.7,
        color='#A23B72',
        edgecolor='black'
    )
    axes[1].set_xlabel('Max Attention', fontsize=12, fontweight='bold')
    axes[1].set_ylabel('Frequency', fontsize=12, fontweight='bold')
    axes[1].set_title('Max Attention Distribution', fontsize=14, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    
    # Attention entropy distribution
    axes[2].hist(
        [s['attention_entropy'] for s in all_attention_stats],
        bins=30,
        alpha=0.7,
        color='#F18F01',
        edgecolor='black'
    )
    axes[2].set_xlabel('Attention Entropy', fontsize=12, fontweight='bold')
    axes[2].set_ylabel('Frequency', fontsize=12, fontweight='bold')
    axes[2].set_title('Attention Entropy Distribution', fontsize=14, fontweight='bold')
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    stats_path = OUTPUT_DIR / "attention_statistics.png"
    plt.savefig(stats_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    logger.info(f"✅ Statistics plot saved to {stats_path}")


def main():
    """Main function"""
    logger.info("="*80)
    logger.info("ATTENTION VISUALIZATION GENERATOR")
    logger.info("="*80)
    
    # Check if model exists
    model_path = MODEL_DIR / "cv_transformer_best.pt"
    if not model_path.exists():
        logger.error(f"Model not found: {model_path}")
        logger.error("Please train the model first:")
        logger.error("  py -3.12 src/backend/ml/training/train_cv.py")
        return
    
    # Load model
    model, device = load_model(model_path)
    
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
    
    # Generate visualizations
    generate_visualizations(model, test_loader, device, num_samples=5)
    
    # Generate summary
    generate_summary_visualization(model, test_loader, device)
    
    # Analyze patterns
    analyze_attention_patterns(model, test_loader, device)
    
    logger.info("\n✅ All visualizations generated successfully!")


if __name__ == "__main__":
    main()
