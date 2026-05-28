#!/usr/bin/env python3
"""
Anomaly Detection for CV Measurements
======================================
Autoencoder-based anomaly detection for quality control

Detects:
- Disconnected electrodes
- Contaminated samples
- Instrument failures
- Abnormal CV curves

Author: VidyuthLabs
Date: May 6, 2026
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple
import numpy as np


class CVAnomalyDetector(nn.Module):
    """
    Autoencoder-based anomaly detection for CV curves
    
    Architecture:
    - Encoder: Conv1D layers to compress CV curve to latent space
    - Decoder: Reconstruct CV curve from latent representation
    - Anomaly score: Reconstruction error
    
    Training:
    - Train on normal CV curves only
    - Set threshold at 95th percentile of reconstruction errors
    - At inference, flag curves with error > threshold
    """
    
    def __init__(self, data_points: int = 2000, latent_dim: int = 64):
        super().__init__()
        
        self.data_points = data_points
        self.latent_dim = latent_dim
        
        # Encoder
        self.encoder = nn.Sequential(
            # Conv block 1
            nn.Conv1d(1, 32, kernel_size=21, padding=10),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(2),  # 2000 -> 1000
            
            # Conv block 2
            nn.Conv1d(32, 64, kernel_size=11, padding=5),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(2),  # 1000 -> 500
            
            # Conv block 3
            nn.Conv1d(64, 128, kernel_size=5, padding=2),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.MaxPool1d(2),  # 500 -> 250
            
            # Global pooling
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            
            # Latent space
            nn.Linear(128, latent_dim),
            nn.ReLU()
        )
        
        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, 512),
            nn.ReLU(),
            nn.Linear(512, data_points),
            nn.Unflatten(1, (1, data_points))
        )
        
        # Anomaly threshold (learned during training)
        self.register_buffer('threshold', torch.tensor(0.1))
        self.register_buffer('mean_error', torch.tensor(0.0))
        self.register_buffer('std_error', torch.tensor(1.0))
    
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass
        
        Args:
            x: (batch, 1, data_points) - CV current
        
        Returns:
            Dictionary with:
            - reconstruction: (batch, 1, data_points)
            - reconstruction_error: (batch,)
            - is_anomaly: (batch,) - boolean
            - anomaly_score: (batch,) - normalized score
            - latent: (batch, latent_dim)
        """
        # Encode
        z = self.encoder(x)
        
        # Decode
        x_recon = self.decoder(z)
        
        # Reconstruction error (MSE per sample)
        recon_error = F.mse_loss(x, x_recon, reduction='none').mean(dim=[1, 2])
        
        # Normalized anomaly score (z-score)
        anomaly_score = (recon_error - self.mean_error) / (self.std_error + 1e-8)
        
        # Anomaly detection
        is_anomaly = recon_error > self.threshold
        
        return {
            'reconstruction': x_recon,
            'reconstruction_error': recon_error,
            'is_anomaly': is_anomaly,
            'anomaly_score': anomaly_score,
            'latent': z
        }
    
    def set_threshold(
        self,
        normal_data: torch.Tensor,
        percentile: float = 95.0
    ):
        """
        Set anomaly threshold based on normal data
        
        Args:
            normal_data: (N, 1, data_points) - Normal CV curves
            percentile: Percentile for threshold (default: 95)
        """
        self.eval()
        
        with torch.no_grad():
            # Compute reconstruction errors on normal data
            errors = []
            
            # Process in batches to avoid memory issues
            batch_size = 32
            for i in range(0, len(normal_data), batch_size):
                batch = normal_data[i:i+batch_size]
                outputs = self(batch)
                errors.append(outputs['reconstruction_error'])
            
            errors = torch.cat(errors)
            
            # Set threshold at percentile
            self.threshold = torch.quantile(errors, percentile / 100.0)
            
            # Set mean and std for normalization
            self.mean_error = errors.mean()
            self.std_error = errors.std()
        
        print(f"✅ Anomaly threshold set:")
        print(f"   Threshold: {self.threshold.item():.6f}")
        print(f"   Mean error: {self.mean_error.item():.6f}")
        print(f"   Std error: {self.std_error.item():.6f}")
        print(f"   Percentile: {percentile}%")
    
    def detect_anomalies(
        self,
        data: torch.Tensor,
        return_details: bool = False
    ) -> Tuple[torch.Tensor, Dict]:
        """
        Detect anomalies in CV curves
        
        Args:
            data: (N, 1, data_points) - CV curves to check
            return_details: If True, return detailed results
        
        Returns:
            is_anomaly: (N,) - Boolean tensor
            details: Dictionary with reconstruction errors, scores, etc.
        """
        self.eval()
        
        with torch.no_grad():
            outputs = self(data)
            
            is_anomaly = outputs['is_anomaly']
            
            if return_details:
                details = {
                    'reconstruction_error': outputs['reconstruction_error'],
                    'anomaly_score': outputs['anomaly_score'],
                    'threshold': self.threshold.item(),
                    'num_anomalies': is_anomaly.sum().item(),
                    'anomaly_rate': is_anomaly.float().mean().item()
                }
                return is_anomaly, details
            else:
                return is_anomaly, {}
    
    def visualize_reconstruction(
        self,
        x: torch.Tensor,
        idx: int = 0
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Visualize reconstruction for a single sample
        
        Args:
            x: (batch, 1, data_points) - CV curves
            idx: Index of sample to visualize
        
        Returns:
            original: (data_points,) - Original curve
            reconstruction: (data_points,) - Reconstructed curve
            error: Reconstruction error
        """
        self.eval()
        
        with torch.no_grad():
            outputs = self(x)
            
            original = x[idx, 0].cpu().numpy()
            reconstruction = outputs['reconstruction'][idx, 0].cpu().numpy()
            error = outputs['reconstruction_error'][idx].item()
        
        return original, reconstruction, error


def train_anomaly_detector(
    model: CVAnomalyDetector,
    train_loader: torch.utils.data.DataLoader,
    num_epochs: int = 50,
    learning_rate: float = 1e-4,
    device: str = 'cuda'
):
    """
    Train anomaly detector on normal CV curves
    
    Args:
        model: CVAnomalyDetector model
        train_loader: DataLoader with normal CV curves
        num_epochs: Number of training epochs
        learning_rate: Learning rate
        device: 'cuda' or 'cpu'
    """
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    
    print("="*80)
    print("TRAINING ANOMALY DETECTOR")
    print("="*80)
    print(f"Device: {device}")
    print(f"Epochs: {num_epochs}")
    print(f"Learning rate: {learning_rate}")
    print("="*80)
    
    for epoch in range(1, num_epochs + 1):
        model.train()
        total_loss = 0.0
        
        for batch in train_loader:
            current = batch['current'].to(device)
            
            # Forward
            outputs = model(current)
            loss = outputs['reconstruction_error'].mean()
            
            # Backward
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / len(train_loader)
        
        if epoch % 10 == 0 or epoch == 1:
            print(f"Epoch {epoch}/{num_epochs}: Loss = {avg_loss:.6f}")
    
    print("\n✅ Training complete!")
    
    # Set threshold on training data
    print("\nSetting anomaly threshold...")
    all_data = []
    for batch in train_loader:
        all_data.append(batch['current'])
    all_data = torch.cat(all_data).to(device)
    
    model.set_threshold(all_data, percentile=95)
    
    return model


if __name__ == "__main__":
    print("Testing CV Anomaly Detector...")
    
    # Create model
    model = CVAnomalyDetector(data_points=2000, latent_dim=64)
    
    # Count parameters
    num_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {num_params:,}")
    
    # Test forward pass
    print("\n" + "="*80)
    print("Testing forward pass...")
    print("="*80)
    
    batch_size = 4
    data_points = 2000
    x = torch.randn(batch_size, 1, data_points)
    
    outputs = model(x)
    
    print("\nOutputs:")
    for key, value in outputs.items():
        if isinstance(value, torch.Tensor):
            print(f"  {key}: {value.shape}")
    
    print(f"\nReconstruction errors: {outputs['reconstruction_error']}")
    print(f"Is anomaly: {outputs['is_anomaly']}")
    print(f"Anomaly scores: {outputs['anomaly_score']}")
    
    # Test threshold setting
    print("\n" + "="*80)
    print("Testing threshold setting...")
    print("="*80)
    
    normal_data = torch.randn(100, 1, data_points)
    model.set_threshold(normal_data, percentile=95)
    
    # Test anomaly detection
    print("\n" + "="*80)
    print("Testing anomaly detection...")
    print("="*80)
    
    # Normal data
    normal = torch.randn(10, 1, data_points)
    # Anomalous data (very different)
    anomalous = torch.randn(10, 1, data_points) * 10
    
    test_data = torch.cat([normal, anomalous])
    
    is_anomaly, details = model.detect_anomalies(test_data, return_details=True)
    
    print(f"\nDetected {details['num_anomalies']} anomalies out of {len(test_data)}")
    print(f"Anomaly rate: {details['anomaly_rate']*100:.1f}%")
    print(f"Threshold: {details['threshold']:.6f}")
    
    print("\n✅ CV Anomaly Detector test successful!")
    print("\nNext steps:")
    print("1. Train on real data: py -3.12 src/backend/ml/training/train_anomaly_detector.py")
    print("2. Integrate into API: Add anomaly check before predictions")
    print("3. Create visualization: Plot reconstruction errors")
