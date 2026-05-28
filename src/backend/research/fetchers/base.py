"""
Base fetcher interface.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PaperRecord:
    """Standardized paper record from any API source."""
    title: str
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    source_api: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "semantic_scholar_id": self.semantic_scholar_id,
            "year": self.year,
            "journal": self.journal,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "source_api": self.source_api,
        }


class BaseFetcher(ABC):
    """Base class for all paper fetchers."""

    def __init__(self, delay_seconds: float = 1.0):
        self.delay_seconds = delay_seconds
        self._last_request_time = 0.0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_seconds:
            wait = self.delay_seconds - elapsed
            logger.debug("Rate limiting: waiting %.1fs", wait)
            time.sleep(wait)
        self._last_request_time = time.time()

    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> List[PaperRecord]:
        """Search for papers matching query. Returns list of PaperRecord."""
        pass

    @abstractmethod
    def source_name(self) -> str:
        """Return the name of this data source."""
        pass
