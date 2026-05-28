"""
Physics-Informed CV Transformer Training (Week 2)
===================================================
Trains the CV Transformer with physics-informed loss constraints:
  - Butler-Volmer kinetics (|ipa/ipc| ≈ 1 for reversible)
  - Randles-Ševčík equation (ip ∝ √v)
  - Nernst equation (ΔEp ≈ 59/n mV)
  - Charge conservation (∫i dE ≈ 0)

Usage:
    py -3.12 src/backend/ml/training/train_physics_informed.py

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
from torch.utils.data import DataLoader

sys.path.append(str(Path(__file__).parent.parent))

from models.cv_transformer import create_cv_transformer
from models.physics_informed_loss import PhysicsInformedLoss
from training.train_cv import CVDataLoader, CVDataset, CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).parent.parent.parent.parent.parent
OUTPUT_DIR = BASE_DIR / "models" / "cv_transformer_physics"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PHYSICS_CONFIG = {
    **CONFIG,
    "num_epochs":      50,
    "patience":        15,
    "physics_weight":  0.1,   # λ for physics loss
    "lambda_bv":       0.10,
    "lambda_rs":       0.10,
    "lambda_nernst":   0.10,
    "lambda_charge":   0.05,
}


class MultiTaskLoss(nn.Module):
    """Standard multi-task loss for CV Transformer."""

    def forward(self, predictions, targets):
        loss = torch.tensor(0.0, device=next(iter(predictions.values())).device)
        n = 0

        if "reversibility" in predictions and "reversibility" in targets:
            pred = predictions["reversibility"]
            tgt  = targets["reversibility"].float()
            if pred.shape == tgt.shape:
                loss = loss + nn.functional.mse_loss(pred, tgt)
                n += 1

        if "mechanism" in predictions and "mechanism" in targets:
            pred = predictions["mechanism"]
            tgt  = targets["mechanism"].long()
            valid = tgt >= 0
            if valid.any():
                loss = loss + nn.functional.cross_entropy(pred[valid], tgt[valid])
                n += 1

        return loss / max(n, 1)


class PhysicsInformedTrainer:
    def __init__(self, config):
        self.config = config
        self.device = torch.device(config["device"])
        logger.info("Physics-informed training on: %s", self.device)

        self.model = create_cv_transformer("base")
        self.model.to(self.device)

        n_params = sum(p.numel() for p in self.model.parameters())
        logger.info("Model parameters: %s", f"{n_params:,}")

        self.task_loss_fn   = MultiTaskLoss()
        self.physics_loss_fn = PhysicsInformedLoss(
            lambda_bv=config["lambda_bv"],
            lambda_rs=config["lambda_rs"],
            lambda_nernst=config["lambda_nernst"],
            lambda_charge=config["lambda_charge"],
        )

        self.optimizer = optim.AdamW(
            self.model.parameters(),
            lr=config["learning_rate"],
            weight_decay=1e-4,
        )
        self.scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.optimizer, T_0=10, T_mult=2
        )

    def _step(self, batch, train=True):
        current = batch["current"].to(self.device)
        voltage = batch.get("voltage")
        if voltage is not None:
            voltage = voltage.to(self.device)

        targets = {
            k: batch["labels"][k].to(self.device)
            for k in ("reversibility", "mechanism", "peaks", "parameters")
            if k in batch.get("labels", {})
        }

        predictions = self.model(current, task="all")

        # Task loss
        task_loss = self.task_loss_fn(predictions, targets)

        # Physics loss
        phys_loss, phys_breakdown = self.physics_loss_fn(
            predictions,
            voltage=voltage,
            current=current.squeeze(1) if current.dim() == 3 else current,
        )

        total = task_loss + self.config["physics_weight"] * phys_loss

        return total, task_loss, phys_loss, phys_breakdown

    def train_epoch(self, loader, epoch):
        self.model.train()
        totals = {"total": 0, "task": 0, "physics": 0}
        phys_avg = {}

        for batch in loader:
            total, task, phys, breakdown = self._step(batch, train=True)

            self.optimizer.zero_grad()
            total.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()

            totals["total"]   += total.item()
            totals["task"]    += task.item()
            totals["physics"] += phys.item()
            for k, v in breakdown.items():
                phys_avg[k] = phys_avg.get(k, 0) + v

        n = len(loader)
        return {k: v / n for k, v in totals.items()}, {k: v / n for k, v in phys_avg.items()}

    def validate(self, loader):
        self.model.eval()
        total_loss = 0.0
        with torch.no_grad():
            for batch in loader:
                total, _, _, _ = self._step(batch, train=False)
                total_loss += total.item()
        return total_loss / len(loader) if loader else 0.0

    def train(self, train_loader, val_loader):
        logger.info("=" * 65)
        logger.info("PHYSICS-INFORMED CV TRANSFORMER TRAINING")
        logger.info("=" * 65)
        logger.info("Physics weight: %.2f", self.config["physics_weight"])
        logger.info("Constraints: BV=%.2f  RS=%.2f  Nernst=%.2f  Charge=%.2f",
                    self.config["lambda_bv"], self.config["lambda_rs"],
                    self.config["lambda_nernst"], self.config["lambda_charge"])

        best_val  = float("inf")
        patience  = 0
        ckpt_path = OUTPUT_DIR / "cv_transformer_physics_best.pt"
        history   = []

        for epoch in range(1, self.config["num_epochs"] + 1):
            train_losses, phys_breakdown = self.train_epoch(train_loader, epoch)
            val_loss = self.validate(val_loader)
            self.scheduler.step()

            logger.info(
                "Epoch %3d | total=%.4f  task=%.4f  phys=%.4f | val=%.4f",
                epoch,
                train_losses["total"], train_losses["task"], train_losses["physics"],
                val_loss,
            )
            logger.info(
                "           BV=%.4f  RS=%.4f  Nernst=%.4f  Charge=%.4f",
                phys_breakdown.get("bv_loss", 0),
                phys_breakdown.get("rs_loss", 0),
                phys_breakdown.get("nernst_loss", 0),
                phys_breakdown.get("charge_loss", 0),
            )

            history.append({
                "epoch": epoch,
                "train_total": train_losses["total"],
                "train_task":  train_losses["task"],
                "train_phys":  train_losses["physics"],
                "val_total":   val_loss,
                **{f"phys_{k}": v for k, v in phys_breakdown.items()},
            })

            if val_loss < best_val:
                best_val = val_loss
                patience = 0
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": self.model.state_dict(),
                    "optimizer_state_dict": self.optimizer.state_dict(),
                    "val_loss": val_loss,
                    "config": self.config,
                }, ckpt_path)
                logger.info("✅ New best model saved (val=%.4f)", val_loss)
            else:
                patience += 1
                if patience >= self.config["patience"]:
                    logger.info("Early stopping at epoch %d", epoch)
                    break

        # Save training history
        with open(OUTPUT_DIR / "training_history.json", "w") as f:
            json.dump(history, f, indent=2)

        logger.info("=" * 65)
        logger.info("TRAINING COMPLETE")
        logger.info("  Best val loss: %.4f", best_val)
        logger.info("  Saved to: %s", OUTPUT_DIR)
        logger.info("=" * 65)
        return best_val


def main():
    data_loader = CVDataLoader()
    n = data_loader.load_ebio_data()
    logger.info("Loaded %d samples", n)

    if n == 0:
        logger.error("No data found. Run download_ebio_data.py first.")
        return

    dataset = CVDataset(data_loader.samples)
    n_train = int(0.8 * len(dataset))
    n_val   = len(dataset) - n_train
    train_ds, val_ds = torch.utils.data.random_split(
        dataset, [n_train, n_val],
        generator=torch.Generator().manual_seed(42)
    )

    train_loader = DataLoader(train_ds, batch_size=PHYSICS_CONFIG["batch_size"],
                              shuffle=True,  num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=PHYSICS_CONFIG["batch_size"],
                              shuffle=False, num_workers=0)

    trainer = PhysicsInformedTrainer(PHYSICS_CONFIG)
    trainer.train(train_loader, val_loader)


if __name__ == "__main__":
    main()
