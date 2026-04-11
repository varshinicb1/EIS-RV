"""
Semantic Scholar API Fetcher
===============================
Fetches papers from the Semantic Scholar public API.
No API key required for basic access (100 req/5min).

API docs: https://api.semanticscholar.org/api-docs/
"""

import json
import logging
from typing import List, Optional
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError

from .base import BaseFetcher, PaperRecord

logger = logging.getLogger(__name__)


class SemanticScholarFetcher(BaseFetcher):
    """Fetch papers from the Semantic Scholar API."""

    API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, delay_seconds: float = 3.5):
        super().__init__(delay_seconds=delay_seconds)

    def source_name(self) -> str:
        return "semantic_scholar"

    def search(self, query: str, max_results: int = 20) -> List[PaperRecord]:
        """
        Search Semantic Scholar for papers matching query.

        Args:
            query: Free-text search query
            max_results: Maximum papers to return (API max 100)

        Returns:
            List of PaperRecord objects
        """
        max_results = min(max_results, 100)

        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,authors,abstract,externalIds,year,venue,"
                      "openAccessPdf,url",
        }

        url = f"{self.API_URL}?{urlencode(params)}"
        logger.info("Semantic Scholar query: %s (max=%d)", query[:60], max_results)

        self._rate_limit()

        try:
            req = Request(url, headers={
                "User-Agent": "VANL-Research-Pipeline/0.1",
            })
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read())
        except (URLError, HTTPError) as e:
            logger.error("Semantic Scholar API error for query '%s': %s", query[:40], e)
            return []
        except json.JSONDecodeError as e:
            logger.error("Semantic Scholar JSON parse error: %s", e)
            return []

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> List[PaperRecord]:
        """Parse Semantic Scholar JSON response."""
        papers = []

        items = data.get("data", [])
        if not items:
            logger.warning("Semantic Scholar returned no data")
            return []

        for item in items:
            try:
                paper = self._parse_item(item)
                if paper:
                    papers.append(paper)
            except Exception as e:
                logger.warning("Failed to parse S2 item: %s", e)
                continue

        logger.info("Semantic Scholar returned %d papers", len(papers))
        return papers

    def _parse_item(self, item: dict) -> Optional[PaperRecord]:
        """Parse a single Semantic Scholar paper item."""
        title = item.get("title", "").strip()
        if not title:
            return None

        # Authors
        authors = []
        for author in item.get("authors", []):
            name = author.get("name", "").strip()
            if name:
                authors.append(name)

        # Abstract
        abstract = item.get("abstract", "") or ""

        # External IDs
        ext_ids = item.get("externalIds", {}) or {}
        doi = ext_ids.get("DOI")
        arxiv_id = ext_ids.get("ArXiv")

        # Semantic Scholar ID
        s2_id = item.get("paperId")

        # Year
        year = item.get("year")

        # Venue / journal
        journal = item.get("venue", "") or None
        if journal == "":
            journal = None

        # URL
        url = item.get("url", "")

        # PDF (open access)
        pdf_url = None
        oa_pdf = item.get("openAccessPdf")
        if oa_pdf and isinstance(oa_pdf, dict):
            pdf_url = oa_pdf.get("url")

        return PaperRecord(
            title=title,
            authors=authors,
            abstract=abstract,
            doi=doi,
            arxiv_id=arxiv_id,
            semantic_scholar_id=s2_id,
            year=year,
            journal=journal,
            url=url,
            pdf_url=pdf_url,
            source_api="semantic_scholar",
        )
