#!/usr/bin/env python3
"""
RĀMAN Studio - Transformer Model for Raman Spectroscopy
State-of-the-art transformer architecture for material identification

Based on latest research (2024-2025):
- RamanFormer architecture
- Self-attention mechanism
- Positional encoding for spectral data
- Multi-head attention for peak relationships

This model will be the foundation for the 300-year source of truth.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from typing import Optional, Tuple


class PositionalEncoding(nn.Module):
    """
    Positional encoding for spectral data
    Encodes the position (wavenumber) information
    """
    
    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        # Create positional encoding matrix
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        
        pe = torch.zeros(max_len, d_model)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        
        self.register_buffer('pe', pe)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor of shape (batch_size, seq_len, d_model)
        Returns:
            Tensor with positional encoding added
        """
        x = x + self.pe[:x.size(1)]
        return self.dropout(x)


class MultiHeadAttention(nn.Module):
    """
    Multi-head self-attention mechanism
    Captures relationships between different parts of the spectrum
    """
    
    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0, "d_model must be divisible by num_heads"
        
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        
        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)
        
        self.dropout = nn.Dropout(dropout)
    
    def scaled_dot_product_attention(
        self, 
        Q: torch.Tensor, 
        K: torch.Tensor, 
        V: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute scaled dot-product attention
        """
        # Q, K, V: (batch_size, num_heads, seq_len, d_k)
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        
        attention_weights = F.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)
        
        output = torch.matmul(attention_weights, V)
        
        return output, attention_weights
    
    def forward(
        self, 
        x: torch.Tensor, 
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Input tensor of shape (batch_size, seq_len, d_model)
            mask: Optional mask tensor
        Returns:
            Output tensor and attention weights
        """
        batch_size = x.size(0)
        
        # Linear projections
        Q = self.W_q(x)  # (batch_size, seq_len, d_model)
        K = self.W_k(x)
        V = self.W_v(x)
        
        # Reshape for multi-head attention
        Q = Q.view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        K = K.view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        V = V.view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        
        # Attention
        x, attention_weights = self.scaled_dot_product_attention(Q, K, V, mask)
        
        # Concatenate heads
        x = x.transpose(1, 2).contiguous().view(batch_size, -1, self.d_model)
        
        # Final linear projection
        x = self.W_o(x)
        
        return x, attention_weights


class FeedForward(nn.Module):
    """
    Position-wise feed-forward network
    """
    
    def __init__(self, d_model: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.linear1 = nn.Linear(d_model, d_ff)
        self.linear2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input tensor of shape (batch_size, seq_len, d_model)
        Returns:
            Output tensor of same shape
        """
        x = self.linear1(x)
        x = F.gelu(x)  # GELU activation (better than ReLU for transformers)
        x = self.dropout(x)
        x = self.linear2(x)
        return x


class TransformerBlock(nn.Module):
    """
    Single transformer encoder block
    """
    
    def __init__(
        self, 
        d_model: int, 
        num_heads: int, 
        d_ff: int, 
        dropout: float = 0.1
    ):
        super().__init__()
        
        self.attention = MultiHeadAttention(d_model, num_heads, dropout)
        self.feed_forward = FeedForward(d_model, d_ff, dropout)
        
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)
    
    def forward(
        self, 
        x: torch.Tensor, 
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Input tensor of shape (batch_size, seq_len, d_model)
            mask: Optional mask tensor
        Returns:
            Output tensor and attention weights
        """
        # Multi-head attention with residual connection
        attn_output, attention_weights = self.attention(x, mask)
        x = x + self.dropout1(attn_output)
        x = self.norm1(x)
        
        # Feed-forward with residual connection
        ff_output = self.feed_forward(x)
        x = x + self.dropout2(ff_output)
        x = self.norm2(x)
        
        return x, attention_weights


class RamanTransformer(nn.Module):
    """
    Transformer model for Raman spectroscopy
    
    Architecture:
    1. Patch embedding: Convert spectrum to patches
    2. Positional encoding: Add position information
    3. Transformer blocks: Self-attention + feed-forward
    4. Classification head: Predict material class
    
    This is the foundation model for RĀMAN Studio's 300-year vision.
    """
    
    def __init__(
        self,
        spectrum_length: int = 2048,
        patch_size: int = 16,
        d_model: int = 256,
        num_heads: int = 8,
        num_layers: int = 6,
        d_ff: int = 1024,
        num_classes: int = 1000,
        dropout: float = 0.1,
        use_cls_token: bool = True
    ):
        """
        Args:
            spectrum_length: Length of input spectrum
            patch_size: Size of each patch
            d_model: Dimension of model embeddings
            num_heads: Number of attention heads
            num_layers: Number of transformer blocks
            d_ff: Dimension of feed-forward network
            num_classes: Number of output classes
            dropout: Dropout rate
            use_cls_token: Whether to use a learnable CLS token
        """
        super().__init__()
        
        self.spectrum_length = spectrum_length
        self.patch_size = patch_size
        self.d_model = d_model
        self.num_patches = spectrum_length // patch_size
        self.use_cls_token = use_cls_token
        
        # Patch embedding
        self.patch_embed = nn.Linear(patch_size, d_model)
        
        # CLS token (learnable)
        if use_cls_token:
            self.cls_token = nn.Parameter(torch.randn(1, 1, d_model))
        
        # Positional encoding
        max_len = self.num_patches + (1 if use_cls_token else 0)
        self.pos_encoder = PositionalEncoding(d_model, max_len, dropout)
        
        # Transformer blocks
        self.transformer_blocks = nn.ModuleList([
            TransformerBlock(d_model, num_heads, d_ff, dropout)
            for _ in range(num_layers)
        ])
        
        # Classification head
        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_classes)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights using Xavier initialization"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.LayerNorm):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)
    
    def forward(
        self, 
        x: torch.Tensor, 
        return_attention: bool = False
    ) -> torch.Tensor:
        """
        Forward pass
        
        Args:
            x: Input spectrum of shape (batch_size, spectrum_length)
            return_attention: Whether to return attention weights
        Returns:
            Class logits of shape (batch_size, num_classes)
            If return_attention=True, also returns attention weights
        """
        batch_size = x.size(0)
        
        # Reshape to patches
        # (batch_size, spectrum_length) -> (batch_size, num_patches, patch_size)
        x = x.view(batch_size, self.num_patches, self.patch_size)
        
        # Patch embedding
        x = self.patch_embed(x)  # (batch_size, num_patches, d_model)
        
        # Add CLS token
        if self.use_cls_token:
            cls_tokens = self.cls_token.expand(batch_size, -1, -1)
            x = torch.cat([cls_tokens, x], dim=1)
        
        # Positional encoding
        x = self.pos_encoder(x)
        
        # Transformer blocks
        attention_weights = []
        for block in self.transformer_blocks:
            x, attn = block(x)
            if return_attention:
                attention_weights.append(attn)
        
        # Extract CLS token or use global average pooling
        if self.use_cls_token:
            x = x[:, 0]  # Take CLS token
        else:
            x = x.mean(dim=1)  # Global average pooling
        
        # Normalize
        x = self.norm(x)
        
        # Classification
        logits = self.classifier(x)
        
        if return_attention:
            return logits, attention_weights
        return logits
    
    def get_attention_maps(self, x: torch.Tensor) -> list:
        """
        Get attention maps for visualization
        
        Args:
            x: Input spectrum of shape (batch_size, spectrum_length)
        Returns:
            List of attention weight tensors from each layer
        """
        _, attention_weights = self.forward(x, return_attention=True)
        return attention_weights


class RamanTransformerWithUncertainty(RamanTransformer):
    """
    Raman Transformer with uncertainty quantification
    Uses Monte Carlo Dropout for Bayesian inference
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dropout_rate = kwargs.get('dropout', 0.1)
    
    def forward_with_uncertainty(
        self, 
        x: torch.Tensor, 
        num_samples: int = 100
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with uncertainty estimation
        
        Args:
            x: Input spectrum of shape (batch_size, spectrum_length)
            num_samples: Number of Monte Carlo samples
        Returns:
            Mean predictions and standard deviations
        """
        self.train()  # Enable dropout
        
        predictions = []
        for _ in range(num_samples):
            with torch.no_grad():
                pred = self.forward(x)
                predictions.append(pred)
        
        predictions = torch.stack(predictions)  # (num_samples, batch_size, num_classes)
        
        mean = predictions.mean(dim=0)
        std = predictions.std(dim=0)
        
        return mean, std


def create_raman_transformer(
    num_classes: int,
    model_size: str = 'base'
) -> RamanTransformer:
    """
    Factory function to create RamanTransformer with predefined configurations
    
    Args:
        num_classes: Number of output classes
        model_size: 'tiny', 'small', 'base', 'large', or 'huge'
    Returns:
        RamanTransformer model
    """
    configs = {
        'tiny': {
            'd_model': 128,
            'num_heads': 4,
            'num_layers': 3,
            'd_ff': 512
        },
        'small': {
            'd_model': 256,
            'num_heads': 8,
            'num_layers': 6,
            'd_ff': 1024
        },
        'base': {
            'd_model': 512,
            'num_heads': 8,
            'num_layers': 12,
            'd_ff': 2048
        },
        'large': {
            'd_model': 768,
            'num_heads': 12,
            'num_layers': 12,
            'd_ff': 3072
        },
        'huge': {
            'd_model': 1024,
            'num_heads': 16,
            'num_layers': 24,
            'd_ff': 4096
        }
    }
    
    config = configs.get(model_size, configs['base'])
    
    return RamanTransformer(
        num_classes=num_classes,
        **config
    )


if __name__ == "__main__":
    # Test the model
    print("Testing RamanTransformer...")
    
    # Create model
    model = create_raman_transformer(num_classes=100, model_size='small')
    
    # Create dummy input
    batch_size = 4
    spectrum_length = 2048
    x = torch.randn(batch_size, spectrum_length)
    
    # Forward pass
    logits = model(x)
    print(f"Input shape: {x.shape}")
    print(f"Output shape: {logits.shape}")
    
    # Get attention maps
    attention_maps = model.get_attention_maps(x)
    print(f"Number of attention layers: {len(attention_maps)}")
    print(f"Attention map shape: {attention_maps[0].shape}")
    
    # Test uncertainty
    model_uncertain = RamanTransformerWithUncertainty(num_classes=100)
    mean, std = model_uncertain.forward_with_uncertainty(x, num_samples=10)
    print(f"Mean predictions shape: {mean.shape}")
    print(f"Std predictions shape: {std.shape}")
    
    # Count parameters
    num_params = sum(p.numel() for p in model.parameters())
    print(f"Total parameters: {num_params:,}")
    
    print("\nModel test successful!")
