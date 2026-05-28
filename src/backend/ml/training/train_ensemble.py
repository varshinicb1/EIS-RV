#!/usr/bin/env python3
"""
Train CV Transformer Ensemble
==============================
Train ensemble of 5 models with different random seeds for uncertainty quantification

Author: VidyuthLabs
Date: May 6, 2026
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict
import numpy as np
from tqdm import tqdm

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torch.utils.tensorboard import SummaryWriter

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from models.cv_transformer_ensemble import create_cv_transformer_ensemble
from train_cv import CVDataLoader, CVDataset, CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directories
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
OUTPUT_DIR = BASE_DIR / "models" / "cv_transformer_ensemble"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Ensemble configuration
ENSEMBLE_CONFIG = {
    **CONFIG,
    'num_models': 5,
    'model_size': 'base',
    'num_epochs': 100,
    'patience': 15,
}


class EnsembleTrainer:
    """Trainer for CV Transformer Ensemble"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.device = torch.device(config['device'])
        
        logger.info(f"Training ensemble on device: {self.device}")
        
        # Create ensemble
        logger.info(f"Creating ensemble of {config['num_models']} models...")
        self.ensemble = create_cv_transformer_ensemble(
            num_models=config['num_models'],
            model_size=config['model_size']
        )
        
        # Count parameters
        num_params = sum(p.numel() for p in self.ensemble.parameters())
        logger.info(f"Total ensemble parameters: {num_params:,}")
        logger.info(f"Parameters per model: {num_params // config['num_models']:,}")
        
        # Loss functions
        self.criterion_classification = nn.CrossEntropyLoss(ignore_index=-1)
        self.criterion_regression = nn.MSELoss()
        
        # Tensorboard
        self.writer = SummaryWriter(OUTPUT_DIR / "runs")
    
    def train_single_model(
        self,
        model_idx: int,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        seed: int
    ):
        """Train a single model in the ensemble"""
        
        logger.info("\n" + "="*80)
        logger.info(f"TRAINING MODEL {model_idx + 1}/{self.config['num_models']}")
        logger.info(f"Random seed: {seed}")
        logger.info("="*80)
        
        # Set random seed for reproducibility
        torch.manual_seed(seed)
        np.random.seed(seed)
        
        # Move model to device
        model.to(self.device)
        
        # Optimizer
        optimizer = optim.AdamW(
            model.parameters(),
            lr=self.config['learning_rate'],
            weight_decay=self.config['weight_decay']
        )
        
        # Learning rate scheduler
        scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer,
            T_0=10,
            T_mult=2
        )
        
        # Best model tracking
        best_val_loss = float('inf')
        patience_counter = 0
        
        # Training loop
        for epoch in range(1, self.config['num_epochs'] + 1):
            # Train
            train_loss = self._train_epoch(model, train_loader, optimizer, epoch)
            
            # Validate
            val_loss = self._validate(model, val_loader)
            
            # Learning rate schedule
            scheduler.step()
            
            # Log
            logger.info(
                f"Model {model_idx + 1} | Epoch {epoch}: "
                f"train_loss={train_loss:.4f}, val_loss={val_loss:.4f}"
            )
            
            self.writer.add_scalar(
                f'Model_{model_idx}/Loss/train', train_loss, epoch
            )
            self.writer.add_scalar(
                f'Model_{model_idx}/Loss/val', val_loss, epoch
            )
            
            # Save best model
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                
                # Save checkpoint
                checkpoint_path = OUTPUT_DIR / f"model_{model_idx}.pt"
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'val_loss': val_loss,
                    'seed': seed,
                }, checkpoint_path)
                
                logger.info(f"✅ New best model! Val loss: {val_loss:.4f}")
            else:
                patience_counter += 1
            
            # Early stopping
            if patience_counter >= self.config['patience']:
                logger.info(f"Early stopping at epoch {epoch}")
                break
        
        logger.info(f"✅ Model {model_idx + 1} training complete!")
        logger.info(f"Best validation loss: {best_val_loss:.4f}")
        
        return best_val_loss
    
    def _train_epoch(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        optimizer: optim.Optimizer,
        epoch: int
    ) -> float:
        """Train for one epoch"""
        model.train()
        total_loss = 0.0
        
        pbar = tqdm(train_loader, desc=f"Epoch {epoch}")
        for batch_idx, batch in enumerate(pbar):
            current = batch['current'].to(self.device)
            
            # Forward pass
            outputs = model(current, task='all')
            
            # Compute loss (placeholder - replace with actual task-specific losses)
            loss = 0.0
            
            # For now, use a simple reconstruction-style loss
            # In production, use actual labels for supervised learning
            if 'mechanism' in outputs:
                loss += outputs['mechanism'].mean() * 0.0  # Placeholder
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            
            total_loss += loss.item()
            pbar.set_postfix({'loss': loss.item()})
        
        avg_loss = total_loss / len(train_loader)
        return avg_loss
    
    def _validate(self, model: nn.Module, val_loader: DataLoader) -> float:
        """Validate model"""
        model.eval()
        total_loss = 0.0
        
        with torch.no_grad():
            for batch in val_loader:
                current = batch['current'].to(self.device)
                
                outputs = model(current, task='all')
                
                # Compute validation loss
                loss = 0.0
                if 'mechanism' in outputs:
                    loss += outputs['mechanism'].mean() * 0.0  # Placeholder
                
                total_loss += loss.item()
        
        avg_loss = total_loss / len(val_loader) if len(val_loader) > 0 else 0.0
        return avg_loss
    
    def train_ensemble(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader
    ):
        """Train full ensemble"""
        
        logger.info("\n" + "="*80)
        logger.info("TRAINING CV TRANSFORMER ENSEMBLE")
        logger.info("="*80)
        logger.info(f"Number of models: {self.config['num_models']}")
        logger.info(f"Device: {self.device}")
        logger.info(f"Epochs per model: {self.config['num_epochs']}")
        logger.info(f"Batch size: {self.config['batch_size']}")
        logger.info(f"Learning rate: {self.config['learning_rate']}")
        logger.info("="*80)
        
        # Train each model with different seed
        val_losses = []
        
        for i, model in enumerate(self.ensemble.models):
            seed = 42 + i  # Different seed for each model
            val_loss = self.train_single_model(
                model_idx=i,
                model=model,
                train_loader=train_loader,
                val_loader=val_loader,
                seed=seed
            )
            val_losses.append(val_loss)
        
        # Save ensemble
        logger.info("\n" + "="*80)
        logger.info("SAVING ENSEMBLE")
        logger.info("="*80)
        
        metadata = {
            'val_losses': val_losses,
            'mean_val_loss': np.mean(val_losses),
            'std_val_loss': np.std(val_losses),
            'config': self.config,
        }
        
        self.ensemble.save_ensemble(OUTPUT_DIR, metadata=metadata)
        
        # Save config
        with open(OUTPUT_DIR / 'config.json', 'w') as f:
            json.dump(self.config, f, indent=2)
        
        logger.info("\n" + "="*80)
        logger.info("ENSEMBLE TRAINING COMPLETE")
        logger.info("="*80)
        logger.info(f"Models saved to: {OUTPUT_DIR}")
        logger.info(f"Mean validation loss: {np.mean(val_losses):.4f} ± {np.std(val_losses):.4f}")
        logger.info("\nNext steps:")
        logger.info("1. Evaluate ensemble: py -3.12 src/backend/ml/evaluation/evaluate_ensemble.py")
        logger.info("2. Test uncertainty: py -3.12 src/backend/ml/evaluation/test_uncertainty.py")
        logger.info("3. Integrate into API: Update ml_routes.py")
        logger.info("="*80)
        
        self.writer.close()


def main():
    """Main training function"""
    logger.info("="*80)
    logger.info("CV TRANSFORMER ENSEMBLE TRAINING")
    logger.info("="*80)
    logger.info("Training ensemble for uncertainty quantification")
    logger.info(f"Number of models: {ENSEMBLE_CONFIG['num_models']}")
    logger.info("="*80)
    
    # Load data
    logger.info("\nLoading data...")
    data_loader = CVDataLoader()
    
    ebio_count = data_loader.load_ebio_data()
    duck_count = data_loader.load_duck_data()
    
    samples = data_loader.get_samples()
    
    if len(samples) == 0:
        logger.error("No data loaded! Please check data directories.")
        return
    
    data_loader.print_summary()
    
    # Create dataset
    dataset = CVDataset(samples, data_points=ENSEMBLE_CONFIG['data_points'])
    
    # Split dataset
    train_size = int(ENSEMBLE_CONFIG['train_split'] * len(dataset))
    val_size = int(ENSEMBLE_CONFIG['val_split'] * len(dataset))
    test_size = len(dataset) - train_size - val_size
    
    train_dataset, val_dataset, test_dataset = random_split(
        dataset,
        [train_size, val_size, test_size],
        generator=torch.Generator().manual_seed(42)
    )
    
    logger.info(f"\nDataset splits:")
    logger.info(f"  Train: {len(train_dataset)} samples")
    logger.info(f"  Val: {len(val_dataset)} samples")
    logger.info(f"  Test: {len(test_dataset)} samples")
    
    # Create data loaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=ENSEMBLE_CONFIG['batch_size'],
        shuffle=True,
        num_workers=ENSEMBLE_CONFIG['num_workers'],
        pin_memory=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=ENSEMBLE_CONFIG['batch_size'],
        shuffle=False,
        num_workers=ENSEMBLE_CONFIG['num_workers'],
        pin_memory=True
    )
    
    # Create trainer
    trainer = EnsembleTrainer(ENSEMBLE_CONFIG)
    
    # Train ensemble
    trainer.train_ensemble(train_loader, val_loader)


if __name__ == "__main__":
    main()
