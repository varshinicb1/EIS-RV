#!/usr/bin/env python3
"""
Attention Visualization for CV Transformer
===========================================
Extract and visualize attention weights to understand model decisions

Features:
- Extract attention weights from transformer layers
- Create heatmaps showing what model focuses on
- Overlay attention on CV curves
- Export visualizations for reports

Author: VidyuthLabs
Date: May 6, 2026
"""

import torch
import torch.nn as nn
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from typing import List, Tuple, Optional
from pathlib import Path


class AttentionExtractor:
    """Extract attention weights from CV Transformer"""
    
    def __init__(self, model: nn.Module):
        self.model = model
        self.attention_weights = []
        self.hooks = []
    
    def register_hooks(self):
        """Register forward hooks to capture attention weights.
        
        PyTorch MultiheadAttention only returns weights when need_weights=True.
        We patch each layer's self_attn forward to force need_weights=True.
        """
        def make_hook(mha_module):
            original_forward = mha_module.forward

            def patched_forward(*args, **kwargs):
                kwargs['need_weights'] = True
                kwargs['average_attn_weights'] = False
                return original_forward(*args, **kwargs)

            return patched_forward

        def hook_fn(module, input, output):
            if isinstance(output, tuple) and len(output) > 1 and output[1] is not None:
                self.attention_weights.append(output[1].detach().cpu())

        for layer in self.model.transformer.layers:
            # Patch forward to force need_weights=True
            layer.self_attn.forward = make_hook(layer.self_attn)
            hook = layer.self_attn.register_forward_hook(hook_fn)
            self.hooks.append(hook)
    
    def remove_hooks(self):
        """Remove all registered hooks"""
        for hook in self.hooks:
            hook.remove()
        self.hooks = []
        # Restore original forward methods
        for layer in self.model.transformer.layers:
            if hasattr(layer.self_attn, 'forward'):
                # Reset to default by deleting the instance-level override
                try:
                    del layer.self_attn.forward
                except AttributeError:
                    pass
    
    def extract(self, current: torch.Tensor) -> List[torch.Tensor]:
        """
        Extract attention weights for a CV curve.
        
        Args:
            current: (batch, 1, data_points) or (batch, data_points) - CV current
        
        Returns:
            List of attention weight tensors, one per layer.
            Each tensor: (batch, num_heads, seq_len, seq_len)
        """
        self.attention_weights = []
        self.register_hooks()
        
        with torch.no_grad():
            _ = self.model(current)
        
        self.remove_hooks()
        
        return self.attention_weights


def visualize_attention_heatmap(
    attention_weights: List[torch.Tensor],
    layer_idx: int = -1,
    head_idx: Optional[int] = None,
    sample_idx: int = 0,
    figsize: Tuple[int, int] = (12, 8),
    save_path: Optional[str] = None
):
    """
    Visualize attention weights as heatmap
    
    Args:
        attention_weights: List of attention tensors from each layer
        layer_idx: Which layer to visualize (default: -1 = last layer)
        head_idx: Which attention head to visualize (None = average all heads)
        sample_idx: Which sample in batch to visualize
        figsize: Figure size
        save_path: Path to save figure (None = show)
    """
    # Get attention from specified layer
    attn = attention_weights[layer_idx][sample_idx]  # (num_heads, seq_len, seq_len)
    
    # Average across heads or select specific head
    if head_idx is None:
        attn = attn.mean(dim=0)  # (seq_len, seq_len)
        title = f"Attention Heatmap (Layer {layer_idx}, All Heads Averaged)"
    else:
        attn = attn[head_idx]  # (seq_len, seq_len)
        title = f"Attention Heatmap (Layer {layer_idx}, Head {head_idx})"
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot heatmap
    sns.heatmap(
        attn.numpy(),
        cmap='viridis',
        cbar_kws={'label': 'Attention Weight'},
        ax=ax
    )
    
    ax.set_xlabel('Key Position')
    ax.set_ylabel('Query Position')
    ax.set_title(title)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"✅ Saved attention heatmap to {save_path}")
    else:
        plt.show()
    
    plt.close()


def visualize_attention_on_cv(
    voltage: np.ndarray,
    current: np.ndarray,
    attention_weights: List[torch.Tensor],
    layer_idx: int = -1,
    sample_idx: int = 0,
    figsize: Tuple[int, int] = (14, 10),
    save_path: Optional[str] = None
):
    """
    Overlay attention weights on CV curve
    
    Args:
        voltage: (data_points,) - Voltage values
        current: (data_points,) - Current values
        attention_weights: List of attention tensors
        layer_idx: Which layer to visualize
        sample_idx: Which sample in batch
        figsize: Figure size
        save_path: Path to save figure
    """
    # Get attention from specified layer
    attn = attention_weights[layer_idx][sample_idx]  # (num_heads, seq_len, seq_len)
    
    # Average across heads and queries (focus on keys)
    attn_avg = attn.mean(dim=[0, 1])  # (seq_len,)
    
    # Normalize attention to [0, 1]
    attn_norm = (attn_avg - attn_avg.min()) / (attn_avg.max() - attn_avg.min() + 1e-8)
    
    # Resample attention to match CV data points
    if len(attn_norm) != len(current):
        attn_resampled = np.interp(
            np.linspace(0, 1, len(current)),
            np.linspace(0, 1, len(attn_norm)),
            attn_norm.numpy()
        )
    else:
        attn_resampled = attn_norm.numpy()
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(3, 1, figsize=figsize)
    
    # Plot 1: CV curve
    axes[0].plot(voltage, current, 'b-', linewidth=2, label='CV Curve')
    axes[0].set_xlabel('Voltage (V)')
    axes[0].set_ylabel('Current (A)')
    axes[0].set_title('Cyclic Voltammogram')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    
    # Plot 2: Attention weights
    axes[1].plot(voltage, attn_resampled, 'r-', linewidth=2, label='Attention')
    axes[1].fill_between(voltage, 0, attn_resampled, alpha=0.3, color='red')
    axes[1].set_xlabel('Voltage (V)')
    axes[1].set_ylabel('Attention Weight')
    axes[1].set_title(f'Attention Weights (Layer {layer_idx})')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    
    # Plot 3: CV curve with attention overlay
    axes[2].plot(voltage, current, 'b-', linewidth=2, alpha=0.5, label='CV Curve')
    
    # Color CV curve by attention
    scatter = axes[2].scatter(
        voltage, current,
        c=attn_resampled,
        cmap='hot',
        s=20,
        alpha=0.6,
        label='Attention Intensity'
    )
    
    cbar = plt.colorbar(scatter, ax=axes[2])
    cbar.set_label('Attention Weight')
    
    axes[2].set_xlabel('Voltage (V)')
    axes[2].set_ylabel('Current (A)')
    axes[2].set_title('CV Curve with Attention Overlay')
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"✅ Saved attention overlay to {save_path}")
    else:
        plt.show()
    
    plt.close()


def visualize_multi_head_attention(
    attention_weights: List[torch.Tensor],
    layer_idx: int = -1,
    sample_idx: int = 0,
    figsize: Tuple[int, int] = (16, 12),
    save_path: Optional[str] = None
):
    """
    Visualize all attention heads in a layer
    
    Args:
        attention_weights: List of attention tensors
        layer_idx: Which layer to visualize
        sample_idx: Which sample in batch
        figsize: Figure size
        save_path: Path to save figure
    """
    # Get attention from specified layer
    attn = attention_weights[layer_idx][sample_idx]  # (num_heads, seq_len, seq_len)
    num_heads = attn.shape[0]
    
    # Create grid of subplots
    cols = 4
    rows = (num_heads + cols - 1) // cols
    
    fig, axes = plt.subplots(rows, cols, figsize=figsize)
    axes = axes.flatten()
    
    for head_idx in range(num_heads):
        ax = axes[head_idx]
        
        # Plot heatmap for this head
        sns.heatmap(
            attn[head_idx].numpy(),
            cmap='viridis',
            cbar=True,
            ax=ax,
            cbar_kws={'label': 'Weight'}
        )
        
        ax.set_title(f'Head {head_idx}')
        ax.set_xlabel('Key')
        ax.set_ylabel('Query')
    
    # Hide unused subplots
    for idx in range(num_heads, len(axes)):
        axes[idx].axis('off')
    
    plt.suptitle(f'Multi-Head Attention (Layer {layer_idx})', fontsize=16, y=1.02)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"✅ Saved multi-head attention to {save_path}")
    else:
        plt.show()
    
    plt.close()


def analyze_attention_patterns(
    attention_weights: List[torch.Tensor],
    sample_idx: int = 0
) -> dict:
    """
    Analyze attention patterns across layers
    
    Args:
        attention_weights: List of attention tensors
        sample_idx: Which sample in batch
    
    Returns:
        Dictionary with attention statistics
    """
    stats = {
        'num_layers': len(attention_weights),
        'num_heads': attention_weights[0].shape[1],
        'seq_len': attention_weights[0].shape[2],
        'layer_stats': []
    }
    
    for layer_idx, attn in enumerate(attention_weights):
        attn_layer = attn[sample_idx]  # (num_heads, seq_len, seq_len)
        
        # Average across heads
        attn_avg = attn_layer.mean(dim=0)  # (seq_len, seq_len)
        
        layer_stat = {
            'layer': layer_idx,
            'mean': attn_avg.mean().item(),
            'std': attn_avg.std().item(),
            'max': attn_avg.max().item(),
            'min': attn_avg.min().item(),
            'entropy': -(attn_avg * torch.log(attn_avg + 1e-8)).sum(dim=-1).mean().item()
        }
        
        stats['layer_stats'].append(layer_stat)
    
    return stats


if __name__ == "__main__":
    print("Testing Attention Visualization...")
    
    # Create dummy model and data
    from ..models.cv_transformer import create_cv_transformer
    
    model = create_cv_transformer('base')
    model.eval()
    
    # Dummy CV data
    batch_size = 2
    data_points = 2000
    current = torch.randn(batch_size, 1, data_points)
    voltage = np.linspace(-0.5, 0.5, data_points)
    current_data = current[0, 0].numpy()
    
    # Extract attention
    print("\n" + "="*80)
    print("Extracting attention weights...")
    print("="*80)
    
    extractor = AttentionExtractor(model)
    attention_weights = extractor.extract(current)
    
    print(f"Extracted attention from {len(attention_weights)} layers")
    for i, attn in enumerate(attention_weights):
        print(f"  Layer {i}: {attn.shape}")
    
    # Analyze patterns
    print("\n" + "="*80)
    print("Analyzing attention patterns...")
    print("="*80)
    
    stats = analyze_attention_patterns(attention_weights, sample_idx=0)
    
    print(f"Number of layers: {stats['num_layers']}")
    print(f"Number of heads: {stats['num_heads']}")
    print(f"Sequence length: {stats['seq_len']}")
    
    print("\nLayer statistics:")
    for layer_stat in stats['layer_stats']:
        print(f"  Layer {layer_stat['layer']}: "
              f"mean={layer_stat['mean']:.4f}, "
              f"std={layer_stat['std']:.4f}, "
              f"entropy={layer_stat['entropy']:.4f}")
    
    # Create visualizations
    print("\n" + "="*80)
    print("Creating visualizations...")
    print("="*80)
    
    output_dir = Path("attention_visualizations")
    output_dir.mkdir(exist_ok=True)
    
    # Heatmap
    visualize_attention_heatmap(
        attention_weights,
        layer_idx=-1,
        save_path=output_dir / "attention_heatmap.png"
    )
    
    # Overlay on CV
    visualize_attention_on_cv(
        voltage,
        current_data,
        attention_weights,
        layer_idx=-1,
        save_path=output_dir / "attention_overlay.png"
    )
    
    # Multi-head
    visualize_multi_head_attention(
        attention_weights,
        layer_idx=-1,
        save_path=output_dir / "multi_head_attention.png"
    )
    
    print("\n✅ Attention visualization test successful!")
    print(f"\nVisualizations saved to: {output_dir}")
    print("\nNext steps:")
    print("1. Integrate into API: Add /api/v1/ml/attention endpoint")
    print("2. Create frontend component: AttentionVisualization.jsx")
    print("3. Add to evaluation reports")
