"""
arXiv API Fetcher
===================
Fetches papers from the arXiv public API.
No API key required. Rate limit: >= 3 seconds between requests.

API docs: https://info.arxiv.org/help/api/index.html
"""

import logging
import xml.etree.ElementTree as ET
from typing import List, Optional
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError

from .base import BaseFetcher, PaperRecord

logger = logging.getLogger(__name__)

# arXiv Atom namespace
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class ArxivFetcher(BaseFetcher):
    """Fetch papers from the arXiv API."""

    API_URL = "http://export.arxiv.org/api/query"

    def __init__(self, delay_seconds: float = 3.0):
        super().__init__(delay_seconds=delay_seconds)

    def source_name(self) -> str:
        return "arxiv"

    def search(self, query: str, max_results: int = 20) -> List[PaperRecord]:
        """
        Search arXiv for papers matching query.

        Args:
            query: Search string (arXiv query syntax)
            max_results: Maximum papers to return (capped at 100)

        Returns:
            List of PaperRecord objects
        """
        max_results = min(max_results, 100)

        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        url = f"{self.API_URL}?{urlencode(params)}"
        logger.info("arXiv query: %s (max=%d)", query[:60], max_results)

        self._rate_limit()

        try:
            req = Request(url, headers={"User-Agent": "VANL-Research-Pipeline/0.1"})
            with urlopen(req, timeout=30) as response:
                xml_data = response.read()
        except (URLError, HTTPError) as e:
            logger.error("arXiv API error for query '%s': %s", query[:40], e)
            return []

        return self._parse_response(xml_data)

    def _parse_response(self, xml_data: bytes) -> List[PaperRecord]:
        """Parse arXiv Atom XML response into PaperRecord list."""
        papers = []

        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            logger.error("Failed to parse arXiv XML: %s", e)
            return []

        for entry in root.findall(f"{ATOM_NS}entry"):
            try:
                paper = self._parse_entry(entry)
                if paper:
                    papers.append(paper)
            except Exception as e:
                title_el = entry.find(f"{ATOM_NS}title")
                title_text = title_el.text[:40] if title_el is not None and title_el.text else "unknown"
                logger.warning("Failed to parse arXiv entry '%s': %s", title_text, e)
                continue

        logger.info("arXiv returned %d papers", len(papers))
        return papers

    def _parse_entry(self, entry: ET.Element) -> Optional[PaperRecord]:
        """Parse a single Atom entry into a PaperRecord."""
        # Title
        title_el = entry.find(f"{ATOM_NS}title")
        if title_el is None or not title_el.text:
            return None
        title = " ".join(title_el.text.strip().split())  # normalize whitespace

        # Authors
        authors = []
        for author_el in entry.findall(f"{ATOM_NS}author"):
            name_el = author_el.find(f"{ATOM_NS}name")
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        # Abstract
        abstract = ""
        summary_el = entry.find(f"{ATOM_NS}summary")
        if summary_el is not None and summary_el.text:
            abstract = " ".join(summary_el.text.strip().split())

        # arXiv ID
        id_el = entry.find(f"{ATOM_NS}id")
        arxiv_id = None
        url = None
        if id_el is not None and id_el.text:
            url = id_el.text.strip()
            # Extract ID from URL: http://arxiv.org/abs/2301.12345v1
            arxiv_id = url.split("/abs/")[-1] if "/abs/" in url else None

        # DOI (if available)
        doi = None
        doi_el = entry.find(f"{ARXIV_NS}doi")
        if doi_el is not None and doi_el.text:
            doi = doi_el.text.strip()

        # Published date -> year
        year = None
        published_el = entry.find(f"{ATOM_NS}published")
        if published_el is not None and published_el.text:
            try:
                year = int(published_el.text[:4])
            except (ValueError, IndexError):
                pass

        # Journal reference
        journal = None
        journal_el = entry.find(f"{ARXIV_NS}journal_ref")
        if journal_el is not None and journal_el.text:
            journal = journal_el.text.strip()

        # PDF link
        pdf_url = None
        for link_el in entry.findall(f"{ATOM_NS}link"):
            if link_el.get("title") == "pdf":
                pdf_url = link_el.get("href")
                break

        return PaperRecord(
            title=title,
            authors=authors,
            abstract=abstract,
            doi=doi,
            arxiv_id=arxiv_id,
            year=year,
            journal=journal,
            url=url,
            pdf_url=pdf_url,
            source_api="arxiv",
        )
