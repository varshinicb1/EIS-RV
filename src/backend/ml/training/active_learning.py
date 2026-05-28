"""
Active Learning for CV Transformer (Week 7)
=============================================
Selects the most informative unlabelled samples for annotation,
maximising model improvement per labelling effort.

Strategies:
  1. Uncertainty sampling — label samples where ensemble disagrees most
  2. Core-set selection — label samples that best cover feature space
  3. Query-by-committee — label samples where models disagree

Author: VidyuthLabs
Date: May 6, 2026
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent


class ActiveLearningSelector:
    """
    Selects the most informative samples for labelling.

    Uses the trained ensemble to estimate uncertainty and
    selects samples that would most improve the model.
    """

    def __init__(
        self,
        ensemble,
        device: Optional[torch.device] = None,
        strategy: str = "uncertainty",  # "uncertainty" | "coreset" | "committee"
    ):
        self.ensemble = ensemble
        self.device   = device or torch.device("cpu")
        self.strategy = strategy
        self.ensemble.to(self.device)
        self.ensemble.eval()

    # ── Uncertainty Sampling ──────────────────────────────────────────────

    def uncertainty_scores(self, data_loader) -> np.ndarray:
        """
        Compute uncertainty scores for all samples.

        Uses ensemble disagreement (std of reversibility predictions)
        as the uncertainty measure.

        Returns:
            (N,) uncertainty scores — higher = more uncertain
        """
        scores = []
        with torch.no_grad():
            for batch in data_loader:
                current = batch["current"].to(self.device)
                out     = self.ensemble(current)

                # Reversibility uncertainty (std across ensemble)
                rev_std = out.get("reversibility_uncertainty")
                if rev_std is not None:
                    scores.extend(rev_std.cpu().numpy().tolist())
                else:
                    # Fallback: use entropy of mechanism predictions
                    mech_probs = F.softmax(out["mechanism"], dim=-1)
                    entropy    = -(mech_probs * torch.log(mech_probs + 1e-10)).sum(dim=-1)
                    scores.extend(entropy.cpu().numpy().tolist())

        return np.array(scores)

    # ── Core-Set Selection ────────────────────────────────────────────────

    def coreset_scores(
        self,
        unlabelled_loader,
        labelled_embeddings: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Core-set selection: find samples that maximise coverage of feature space.

        Selects samples that are farthest from already-labelled samples.

        Returns:
            (N,) distance scores — higher = more informative
        """
        # Extract embeddings for unlabelled samples
        embeddings = []
        with torch.no_grad():
            for batch in unlabelled_loader:
                current = batch["current"].to(self.device)
                out     = self.ensemble(current)
                # Use species embedding as feature representation
                emb = out.get("species", out.get("mechanism"))
                if emb is not None:
                    embeddings.append(emb.cpu().numpy())

        if not embeddings:
            return np.zeros(0)

        unlabelled_emb = np.concatenate(embeddings, axis=0)

        if labelled_embeddings is None or len(labelled_embeddings) == 0:
            # No labelled data: use distance from centroid
            centroid = unlabelled_emb.mean(axis=0, keepdims=True)
            distances = np.linalg.norm(unlabelled_emb - centroid, axis=1)
        else:
            # Distance to nearest labelled sample
            distances = np.array([
                np.min(np.linalg.norm(labelled_embeddings - emb, axis=1))
                for emb in unlabelled_emb
            ])

        return distances

    # ── Query-by-Committee ────────────────────────────────────────────────

    def committee_scores(self, data_loader) -> np.ndarray:
        """
        Query-by-committee: measure disagreement between ensemble members.

        Uses vote entropy: how much do individual models disagree on
        the mechanism classification?

        Returns:
            (N,) disagreement scores
        """
        all_votes = []
        with torch.no_grad():
            for batch in data_loader:
                current = batch["current"].to(self.device)

                # Get predictions from each model individually
                model_votes = []
                for model in self.ensemble.models:
                    model.eval()
                    out  = model(current, task="all")
                    vote = out["mechanism"].argmax(dim=-1)  # (B,)
                    model_votes.append(vote.cpu().numpy())

                # Vote entropy
                model_votes = np.stack(model_votes, axis=1)  # (B, n_models)
                B, n_models = model_votes.shape
                n_classes   = 5

                for i in range(B):
                    counts  = np.bincount(model_votes[i], minlength=n_classes)
                    probs   = counts / n_models
                    entropy = -(probs * np.log(probs + 1e-10)).sum()
                    all_votes.append(entropy)

        return np.array(all_votes)

    # ── Main Selection ────────────────────────────────────────────────────

    def select(
        self,
        unlabelled_loader,
        n_select: int = 50,
        labelled_embeddings: Optional[np.ndarray] = None,
    ) -> Tuple[List[int], np.ndarray]:
        """
        Select the most informative samples for labelling.

        Args:
            unlabelled_loader: DataLoader for unlabelled samples
            n_select: number of samples to select
            labelled_embeddings: embeddings of already-labelled samples (for coreset)

        Returns:
            selected_indices: list of indices to label
            scores: uncertainty/informativeness scores for all samples
        """
        logger.info("Active learning selection: strategy=%s, n_select=%d",
                    self.strategy, n_select)

        if self.strategy == "uncertainty":
            scores = self.uncertainty_scores(unlabelled_loader)
        elif self.strategy == "coreset":
            scores = self.coreset_scores(unlabelled_loader, labelled_embeddings)
        elif self.strategy == "committee":
            scores = self.committee_scores(unlabelled_loader)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

        # Select top-n by score
        n_select = min(n_select, len(scores))
        selected = np.argsort(scores)[::-1][:n_select].tolist()

        logger.info("Selected %d samples (mean score=%.4f, max=%.4f)",
                    len(selected), scores[selected].mean(), scores[selected].max())

        return selected, scores

    def save_selection(
        self,
        selected_indices: List[int],
        scores: np.ndarray,
        output_path: str,
    ):
        """Save selection results to JSON."""
        result = {
            "strategy":         self.strategy,
            "n_selected":       len(selected_indices),
            "selected_indices": selected_indices,
            "scores":           scores.tolist(),
            "mean_score":       float(scores[selected_indices].mean()),
            "max_score":        float(scores[selected_indices].max()),
        }
        Path(output_path).write_text(json.dumps(result, indent=2))
        logger.info("Selection saved to %s", output_path)


class ActiveLearningLoop:
    """
    Full active learning loop:
    1. Train on labelled data
    2. Select most informative unlabelled samples
    3. Label selected samples (human-in-the-loop)
    4. Add to labelled set and retrain
    5. Repeat until budget exhausted
    """

    def __init__(
        self,
        ensemble,
        labelled_samples,
        unlabelled_samples,
        n_per_round: int = 50,
        n_rounds:    int = 5,
        strategy:    str = "uncertainty",
    ):
        self.ensemble            = ensemble
        self.labelled_samples    = list(labelled_samples)
        self.unlabelled_samples  = list(unlabelled_samples)
        self.n_per_round         = n_per_round
        self.n_rounds            = n_rounds
        self.strategy            = strategy
        self.history             = []

    def run(self, train_fn, eval_fn):
        """
        Run the active learning loop.

        Args:
            train_fn: function(labelled_samples) → trained_model
            eval_fn:  function(model, test_samples) → metrics_dict
        """
        logger.info("=" * 65)
        logger.info("ACTIVE LEARNING LOOP")
        logger.info("Strategy: %s | Rounds: %d | Per round: %d",
                    self.strategy, self.n_rounds, self.n_per_round)
        logger.info("Initial labelled: %d | Unlabelled: %d",
                    len(self.labelled_samples), len(self.unlabelled_samples))
        logger.info("=" * 65)

        for round_idx in range(self.n_rounds):
            logger.info("\n--- Round %d/%d ---", round_idx + 1, self.n_rounds)
            logger.info("Labelled: %d | Unlabelled: %d",
                        len(self.labelled_samples), len(self.unlabelled_samples))

            # Train on current labelled set
            model = train_fn(self.labelled_samples)

            # Evaluate
            metrics = eval_fn(model, self.labelled_samples[-100:])
            logger.info("Metrics: %s", metrics)

            # Select new samples
            if not self.unlabelled_samples:
                logger.info("No more unlabelled samples. Stopping.")
                break

            selector = ActiveLearningSelector(
                self.ensemble, strategy=self.strategy
            )

            # Create simple loader for unlabelled samples
            from torch.utils.data import DataLoader
            from training.train_cv import CVDataset
            unlab_dataset = CVDataset(self.unlabelled_samples)
            unlab_loader  = DataLoader(unlab_dataset, batch_size=32, shuffle=False)

            selected_idx, scores = selector.select(unlab_loader, n_select=self.n_per_round)

            # Move selected to labelled (simulating human annotation)
            new_labelled = [self.unlabelled_samples[i] for i in selected_idx]
            self.labelled_samples.extend(new_labelled)
            self.unlabelled_samples = [
                s for i, s in enumerate(self.unlabelled_samples)
                if i not in set(selected_idx)
            ]

            self.history.append({
                "round":          round_idx + 1,
                "n_labelled":     len(self.labelled_samples),
                "n_unlabelled":   len(self.unlabelled_samples),
                "metrics":        metrics,
                "mean_score":     float(scores[selected_idx].mean()),
            })

            logger.info("Added %d samples. Total labelled: %d",
                        len(new_labelled), len(self.labelled_samples))

        return self.history


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Active learning module loaded successfully.")
    print("Use ActiveLearningSelector to select informative samples.")
    print("Use ActiveLearningLoop for the full active learning pipeline.")
