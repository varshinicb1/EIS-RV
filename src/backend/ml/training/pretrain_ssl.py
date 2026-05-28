"""
Self-Supervised Pre-training (Week 6)
=======================================
Pre-trains the CV Transformer on unlabelled data using:
  1. Masked Autoencoding (MAE) — reconstruct masked segments
  2. Contrastive Learning (SimCLR) — augmentation-based

Uses the 1,016 unlabelled EBIO samples that were previously wasted.

Author: VidyuthLabs
Date: May 6, 2026
"""

import sys
import json
import logging
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset

sys.path.append(str(Path(__file__).parent.parent))

from models.cv_transformer import create_cv_transformer
from models.contrastive_learning import ContrastiveCVTransformer, CVAugmentation
from training.train_cv import CVDataLoader, CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).parent.parent.parent.parent.parent
OUTPUT_DIR = BASE_DIR / "models" / "cv_transformer_ssl"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SSL_CONFIG = {
    **CONFIG,
    "num_epochs":       30,
    "patience":         10,
    "ssl_method":       "contrastive",   # "contrastive" | "mae" | "both"
    "temperature":      0.07,
    "projection_dim":   128,
    "mask_ratio":       0.15,            # For MAE
}


# ── Masked Autoencoding Dataset ───────────────────────────────────────────

class MaskedCVDataset(Dataset):
    """Dataset that returns masked CV curves for MAE pre-training."""

    def __init__(self, samples, data_points: int = 2000, mask_ratio: float = 0.15):
        self.samples     = samples
        self.data_points = data_points
        self.mask_ratio  = mask_ratio
        self.augment     = CVAugmentation()

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        import numpy as np

        # Resample to fixed length
        current = np.interp(
            np.linspace(0, 1, self.data_points),
            np.linspace(0, 1, len(sample.current)),
            sample.current,
        ).astype(np.float32)

        # Normalise
        std = current.std()
        if std > 0:
            current = (current - current.mean()) / std

        current_tensor = torch.tensor(current).unsqueeze(0)  # (1, N)

        # Create mask
        N = self.data_points
        n_mask = int(N * self.mask_ratio)
        mask_indices = torch.randperm(N)[:n_mask]
        mask = torch.zeros(N, dtype=torch.bool)
        mask[mask_indices] = True

        # Masked input (replace with zeros)
        masked = current_tensor.clone()
        masked[0, mask] = 0.0

        return {
            "current":        current_tensor,
            "masked_current": masked,
            "mask":           mask,
        }


# ── MAE Decoder ───────────────────────────────────────────────────────────

class MAEDecoder(nn.Module):
    """Simple decoder for masked autoencoding."""

    def __init__(self, d_model: int = 256, data_points: int = 2000):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, 512),
            nn.GELU(),
            nn.Linear(512, data_points),
        )

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        return self.net(h)


# ── SSL Trainer ───────────────────────────────────────────────────────────

class SSLTrainer:
    def __init__(self, config):
        self.config = config
        self.device = torch.device(config["device"])
        logger.info("SSL pre-training on: %s", self.device)

        # Encoder
        self.encoder = create_cv_transformer("base")
        self.encoder.to(self.device)

        method = config["ssl_method"]

        if method in ("contrastive", "both"):
            self.contrastive_model = ContrastiveCVTransformer(
                self.encoder,
                projection_dim=config["projection_dim"],
                temperature=config["temperature"],
            )
            self.contrastive_model.to(self.device)

        if method in ("mae", "both"):
            self.mae_decoder = MAEDecoder(d_model=256, data_points=config["data_points"])
            self.mae_decoder.to(self.device)

        # Optimizer
        params = list(self.encoder.parameters())
        if method in ("contrastive", "both"):
            params += list(self.contrastive_model.projector.parameters())
        if method in ("mae", "both"):
            params += list(self.mae_decoder.parameters())

        self.optimizer = optim.AdamW(params, lr=config["learning_rate"], weight_decay=1e-4)
        self.scheduler = optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=config["num_epochs"]
        )

    def train_epoch_contrastive(self, loader) -> float:
        self.contrastive_model.train()
        total = 0.0
        for batch in loader:
            current = batch["current"].to(self.device)
            out = self.contrastive_model(current, return_loss=True)
            loss = out["loss"]
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.encoder.parameters(), 1.0)
            self.optimizer.step()
            total += loss.item()
        return total / len(loader)

    def train_epoch_mae(self, loader) -> float:
        self.encoder.train()
        self.mae_decoder.train()
        total = 0.0
        for batch in loader:
            current = batch["current"].to(self.device)
            masked  = batch["masked_current"].to(self.device)
            mask    = batch["mask"].to(self.device)

            # Encode masked input
            enc_out = self.encoder(masked, task="species")
            h = enc_out["species"]

            # Decode
            recon = self.mae_decoder(h)  # (B, N)

            # Loss only on masked positions
            target = current.squeeze(1)  # (B, N)
            loss = ((recon - target) ** 2 * mask.float()).sum() / (mask.float().sum() + 1e-8)

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.encoder.parameters(), 1.0)
            self.optimizer.step()
            total += loss.item()
        return total / len(loader)

    def train(self, loader):
        logger.info("=" * 65)
        logger.info("SELF-SUPERVISED PRE-TRAINING")
        logger.info("Method: %s", self.config["ssl_method"])
        logger.info("=" * 65)

        best_loss = float("inf")
        patience  = 0
        ckpt_path = OUTPUT_DIR / "cv_transformer_ssl.pt"
        history   = []

        for epoch in range(1, self.config["num_epochs"] + 1):
            method = self.config["ssl_method"]

            if method == "contrastive":
                loss = self.train_epoch_contrastive(loader)
            elif method == "mae":
                loss = self.train_epoch_mae(loader)
            else:  # both
                loss_c = self.train_epoch_contrastive(loader)
                loss_m = self.train_epoch_mae(loader)
                loss   = 0.5 * loss_c + 0.5 * loss_m

            self.scheduler.step()
            logger.info("Epoch %3d | loss=%.4f", epoch, loss)
            history.append({"epoch": epoch, "loss": loss})

            if loss < best_loss:
                best_loss = loss
                patience  = 0
                torch.save({
                    "epoch": epoch,
                    "encoder_state_dict": self.encoder.state_dict(),
                    "loss": loss,
                    "config": self.config,
                }, ckpt_path)
                logger.info("✅ New best SSL model (loss=%.4f)", loss)
            else:
                patience += 1
                if patience >= self.config["patience"]:
                    logger.info("Early stopping at epoch %d", epoch)
                    break

        with open(OUTPUT_DIR / "ssl_history.json", "w") as f:
            json.dump(history, f, indent=2)

        logger.info("SSL pre-training complete. Best loss: %.4f", best_loss)
        logger.info("Saved to: %s", OUTPUT_DIR)
        return best_loss


def main():
    data_loader = CVDataLoader()
    n = data_loader.load_ebio_data()
    logger.info("Loaded %d samples for SSL pre-training", n)

    if n == 0:
        logger.error("No data found.")
        return

    dataset = MaskedCVDataset(
        data_loader.samples,
        data_points=SSL_CONFIG["data_points"],
        mask_ratio=SSL_CONFIG["mask_ratio"],
    )
    loader = DataLoader(dataset, batch_size=SSL_CONFIG["batch_size"],
                        shuffle=True, num_workers=0)

    trainer = SSLTrainer(SSL_CONFIG)
    trainer.train(loader)


if __name__ == "__main__":
    main()
