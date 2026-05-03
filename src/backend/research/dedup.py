"""
Deduplication Engine
======================
Prevent duplicate papers from being stored in the database.

Dedup strategies:
    1. Exact DOI match
    2. Title similarity (Jaccard on word tokens, threshold 0.85)
    3. arXiv ID match
"""

import re
import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)


def normalize_title(title: str) -> str:
    """Normalize a title for comparison: lowercase, remove punctuation."""
    title = title.lower().strip()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title


def title_tokens(title: str) -> Set[str]:
    """Get word tokens from a normalized title."""
    normalized = normalize_title(title)
    # Remove very short words (articles, prepositions)
    return set(w for w in normalized.split() if len(w) > 2)


def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


class Deduplicator:
    """
    Check if a paper already exists in the database before inserting.

    Uses DOI exact match, title Jaccard similarity, and arXiv ID match.
    """

    def __init__(self, conn, similarity_threshold: float = 0.80):
        self.conn = conn
        self.threshold = similarity_threshold
        self._doi_cache: Set[str] = set()
        self._arxiv_cache: Set[str] = set()
        self._title_cache: dict = {}  # normalized_title -> paper_id
        self._load_cache()

    def _load_cache(self):
        """Load existing DOIs and titles from database."""
        cursor = self.conn.execute("SELECT id, doi, arxiv_id, title FROM papers")
        for row in cursor:
            if row["doi"]:
                self._doi_cache.add(row["doi"].lower().strip())
            if row["arxiv_id"]:
                self._arxiv_cache.add(row["arxiv_id"].strip())
            if row["title"]:
                self._title_cache[normalize_title(row["title"])] = row["id"]

        logger.info(
            "Dedup cache loaded: %d DOIs, %d arXiv IDs, %d titles",
            len(self._doi_cache), len(self._arxiv_cache), len(self._title_cache),
        )

    def is_duplicate(
        self,
        title: str,
        doi: Optional[str] = None,
        arxiv_id: Optional[str] = None,
    ) -> bool:
        """
        Check if a paper is a duplicate.

        Returns True if the paper already exists in the database.
        """
        # 1. DOI match
        if doi and doi.lower().strip() in self._doi_cache:
            logger.debug("Duplicate by DOI: %s", doi)
            return True

        # 2. arXiv ID match
        if arxiv_id and arxiv_id.strip() in self._arxiv_cache:
            logger.debug("Duplicate by arXiv ID: %s", arxiv_id)
            return True

        # 3. Title similarity
        if title:
            new_tokens = title_tokens(title)
            if not new_tokens:
                return False

            for existing_title in self._title_cache:
                existing_tokens = title_tokens(existing_title)
                sim = jaccard_similarity(new_tokens, existing_tokens)
                if sim >= self.threshold:
                    logger.debug(
                        "Duplicate by title (sim=%.2f): '%s'",
                        sim, title[:60],
                    )
                    return True

        return False

    def register(
        self,
        title: str,
        paper_id: int,
        doi: Optional[str] = None,
        arxiv_id: Optional[str] = None,
    ):
        """Register a newly inserted paper in the dedup cache."""
        if doi:
            self._doi_cache.add(doi.lower().strip())
        if arxiv_id:
            self._arxiv_cache.add(arxiv_id.strip())
        if title:
            self._title_cache[normalize_title(title)] = paper_id
