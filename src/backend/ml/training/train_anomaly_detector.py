#!/usr/bin/env python3
"""
Train Anomaly Detector for CV Quality Control
==============================================
Trains a CVAnomalyDetector (autoencoder) on normal CV curves.
Anomaly threshold is set at the 95th percentile of reconstruction errors.

Author: VidyuthLabs
Date: May 6, 2026
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List

import numpy as np
from tqdm import tqdm

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

# ── Path setup ────────────────────────────────────────────────────────────
sys.path.append(str(Path(__file__).parent.parent))

from models.anomaly_detector import CVAnomalyDetector
from train_cv import CVDataLoader, CVDataset, CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).parent.parent.parent.parent.parent
OUTPUT_DIR = BASE_DIR / "models" / "anomaly_detector"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ANOMALY_CONFIG = {
    **CONFIG,
    "num_epochs": 50,
    "patience": 10,
    "threshold_percentile": 95,
}


# ── Trainer ───────────────────────────────────────────────────────────────

class AnomalyTrainer:
    def __init__(self, config: Dict):
        self.config = config
        self.device = torch.device(config["device"])
        logger.info("Training anomaly detector on: %s", self.device)

        self.model = CVAnomalyDetector(
            data_points=config["data_points"],
            latent_dim=64,
        )
        n_params = sum(p.numel() for p in self.model.parameters())
        logger.info("CVAnomalyDetector parameters: %s", f"{n_params:,}")
        self.model.to(self.device)

        self.criterion = nn.MSELoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=config["learning_rate"])
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5
        )

    # ── single epoch ──────────────────────────────────────────────────────
    def _train_epoch(self, loader: DataLoader, epoch: int) -> float:
        self.model.train()
        total = 0.0
        pbar = tqdm(loader, desc=f"Epoch {epoch}")
        for batch in pbar:
            # batch["current"] shape: (B, 2000) → need (B, 1, 2000)
            current = batch["current"].to(self.device)
            if current.dim() == 2:
                current = current.unsqueeze(1)

            out = self.model(current)
            recon = out["reconstruction"]
            loss = self.criterion(recon, current)

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()

            total += loss.item()
            pbar.set_postfix(loss=f"{loss.item():.6f}")
        return total / len(loader)

    def _validate(self, loader: DataLoader) -> float:
        self.model.eval()
        total = 0.0
        with torch.no_grad():
            for batch in loader:
                current = batch["current"].to(self.device)
                if current.dim() == 2:
                    current = current.unsqueeze(1)
                out = self.model(current)
                total += self.criterion(out["reconstruction"], current).item()
        return total / len(loader) if loader else 0.0

    # ── threshold ─────────────────────────────────────────────────────────
    def _compute_threshold(self, loader: DataLoader) -> float:
        self.model.eval()
        errors: List[float] = []
        with torch.no_grad():
            for batch in tqdm(loader, desc="Computing threshold"):
                current = batch["current"].to(self.device)
                if current.dim() == 2:
                    current = current.unsqueeze(1)
                out = self.model(current)
                errors.extend(out["reconstruction_error"].cpu().numpy().tolist())
        errors_arr = np.array(errors)
        threshold = float(np.percentile(errors_arr, self.config["threshold_percentile"]))
        logger.info("Threshold (95th %%ile): %.6f  mean=%.6f  std=%.6f",
                    threshold, errors_arr.mean(), errors_arr.std())
        return threshold

    # ── full training pipeline ────────────────────────────────────────────
    def train(self, train_loader: DataLoader, val_loader: DataLoader):
        logger.info("=" * 70)
        logger.info("TRAINING ANOMALY DETECTOR")
        logger.info("=" * 70)

        best_val = float("inf")
        patience_ctr = 0
        ckpt_path = OUTPUT_DIR / "anomaly_detector.pt"

        for epoch in range(1, self.config["num_epochs"] + 1):
            train_loss = self._train_epoch(train_loader, epoch)
            val_loss   = self._validate(val_loader)
            self.scheduler.step(val_loss)

            logger.info("Epoch %d: train=%.6f  val=%.6f", epoch, train_loss, val_loss)

            if val_loss < best_val:
                best_val = val_loss
                patience_ctr = 0
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": self.model.state_dict(),
                    "optimizer_state_dict": self.optimizer.state_dict(),
                    "val_loss": val_loss,
                }, ckpt_path)
                logger.info("✅ New best model saved (val=%.6f)", val_loss)
            else:
                patience_ctr += 1
                if patience_ctr >= self.config["patience"]:
                    logger.info("Early stopping at epoch %d", epoch)
                    break

        # Load best weights
        ckpt = torch.load(ckpt_path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(ckpt["model_state_dict"])
        logger.info("Loaded best model (epoch %d, val=%.6f)", ckpt["epoch"], ckpt["val_loss"])

        # Compute and save threshold
        threshold = self._compute_threshold(train_loader)

        # Update threshold buffer in model and re-save
        self.model.threshold.fill_(threshold)
        torch.save({
            "epoch": ckpt["epoch"],
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "val_loss": ckpt["val_loss"],
            "threshold": threshold,
        }, ckpt_path)

        # Save metadata
        meta = {
            "best_val_loss": float(best_val),
            "threshold": threshold,
            "config": {k: str(v) for k, v in self.config.items()},
        }
        with open(OUTPUT_DIR / "training_results.json", "w") as f:
            json.dump(meta, f, indent=2)

        logger.info("=" * 70)
        logger.info("TRAINING COMPLETE")
        logger.info("  Best val loss : %.6f", best_val)
        logger.info("  Threshold     : %.6f", threshold)
        logger.info("  Saved to      : %s", OUTPUT_DIR)
        logger.info("=" * 70)
        return threshold


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 70)
    logger.info("ANOMALY DETECTOR TRAINING")
    logger.info("=" * 70)

    # Load data
    data_loader = CVDataLoader()
    ebio_count  = data_loader.load_ebio_data()
    logger.info("Loaded %d EBIO samples", ebio_count)

    if ebio_count == 0:
        logger.error("No data found. Run download_ebio_data.py first.")
        return

    # Build dataset
    dataset = CVDataset(data_loader.samples)
    n_total = len(dataset)
    n_train = int(0.8 * n_total)
    n_val   = n_total - n_train
    train_ds, val_ds = torch.utils.data.random_split(
        dataset, [n_train, n_val],
        generator=torch.Generator().manual_seed(42)
    )

    train_loader = DataLoader(train_ds, batch_size=ANOMALY_CONFIG["batch_size"],
                              shuffle=True,  num_workers=0, pin_memory=False)
    val_loader   = DataLoader(val_ds,   batch_size=ANOMALY_CONFIG["batch_size"],
                              shuffle=False, num_workers=0, pin_memory=False)

    logger.info("Train: %d  Val: %d", len(train_ds), len(val_ds))

    # Train
    trainer = AnomalyTrainer(ANOMALY_CONFIG)
    trainer.train(train_loader, val_loader)


if __name__ == "__main__":
    main()
