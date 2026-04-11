"""
CrossRef API Fetcher
======================
Fetches papers from the CrossRef public API.
No API key required (polite pool). Rate limit: 1s between requests.

API docs: https://api.crossref.org/swagger-ui/index.html
"""

import json
import logging
from typing import List, Optional
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote
from urllib.error import URLError, HTTPError

from .base import BaseFetcher, PaperRecord

logger = logging.getLogger(__name__)


class CrossrefFetcher(BaseFetcher):
    """Fetch papers from the CrossRef API."""

    API_URL = "https://api.crossref.org/works"

    def __init__(self, delay_seconds: float = 1.0, email: str = "vanl@research.local"):
        super().__init__(delay_seconds=delay_seconds)
        # CrossRef polite pool: include email in User-Agent
        self.user_agent = f"VANL-Research-Pipeline/0.1 (mailto:{email})"

    def source_name(self) -> str:
        return "crossref"

    def search(self, query: str, max_results: int = 20) -> List[PaperRecord]:
        """
        Search CrossRef for papers matching query.

        Args:
            query: Free-text search query
            max_results: Maximum papers to return

        Returns:
            List of PaperRecord objects
        """
        max_results = min(max_results, 100)

        params = {
            "query": query,
            "rows": max_results,
            "sort": "relevance",
            "order": "desc",
            "select": "DOI,title,author,abstract,published-print,"
                      "published-online,container-title,URL,link",
        }

        url = f"{self.API_URL}?{urlencode(params)}"
        logger.info("CrossRef query: %s (max=%d)", query[:60], max_results)

        self._rate_limit()

        try:
            req = Request(url, headers={"User-Agent": self.user_agent})
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read())
        except (URLError, HTTPError) as e:
            logger.error("CrossRef API error for query '%s': %s", query[:40], e)
            return []
        except json.JSONDecodeError as e:
            logger.error("CrossRef JSON parse error: %s", e)
            return []

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> List[PaperRecord]:
        """Parse CrossRef JSON response."""
        papers = []

        items = data.get("message", {}).get("items", [])
        for item in items:
            try:
                paper = self._parse_item(item)
                if paper:
                    papers.append(paper)
            except Exception as e:
                logger.warning("Failed to parse CrossRef item: %s", e)
                continue

        logger.info("CrossRef returned %d papers", len(papers))
        return papers

    def _parse_item(self, item: dict) -> Optional[PaperRecord]:
        """Parse a single CrossRef work item."""
        # Title
        titles = item.get("title", [])
        if not titles:
            return None
        title = titles[0].strip()

        # Authors
        authors = []
        for author in item.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                authors.append(name)

        # Abstract (CrossRef sometimes includes JATS XML tags)
        abstract = item.get("abstract", "")
        if abstract:
            # Strip basic JATS XML tags
            import re
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        # DOI
        doi = item.get("DOI")

        # Year
        year = None
        for date_field in ["published-print", "published-online"]:
            date_parts = item.get(date_field, {}).get("date-parts", [[]])
            if date_parts and date_parts[0]:
                try:
                    year = int(date_parts[0][0])
                    break
                except (ValueError, IndexError):
                    continue

        # Journal
        containers = item.get("container-title", [])
        journal = containers[0] if containers else None

        # URL
        url = item.get("URL", "")

        # PDF link (look for application/pdf in links)
        pdf_url = None
        for link in item.get("link", []):
            content_type = link.get("content-type", "")
            if "pdf" in content_type.lower():
                pdf_url = link.get("URL")
                break

        return PaperRecord(
            title=title,
            authors=authors,
            abstract=abstract,
            doi=doi,
            year=year,
            journal=journal,
            url=url,
            pdf_url=pdf_url,
            source_api="crossref",
        )
