"""
Google Drive Fetcher
======================
Implements BaseFetcher interface for Google Drive.

- Recursively scans the configured Drive folder for PDFs / Docs / text files
- Extracts full text using pdfminer.six (PDF) or plain-text fallback
- Tracks already-processed file IDs in a local JSON ledger so re-syncs only
  pick up new/modified files
- Returns PaperRecord objects compatible with the existing ResearchPipeline
"""

import hashlib
import io
import json
import logging
import os
import re
from typing import List, Optional

from .base import BaseFetcher, PaperRecord
from src.backend.research.config import PDF_CACHE_DIR, DATA_DIR

logger = logging.getLogger(__name__)

LEDGER_PATH = os.path.join(DATA_DIR, "gdrive_ledger.json")


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def _extract_pdf_text(data: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams

        buf_in = io.BytesIO(data)
        buf_out = io.StringIO()
        extract_text_to_fp(buf_in, buf_out, laparams=LAParams(), output_type="text", codec=None)
        return buf_out.getvalue()
    except Exception as e:
        logger.warning("pdfminer extraction failed: %s", e)
        return ""


def _extract_docx_text(data: bytes) -> str:
    try:
        import docx
        from io import BytesIO
        doc = docx.Document(BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        logger.warning("docx extraction failed: %s", e)
        return ""


def _extract_text(data: bytes, mime_type: str) -> str:
    if "pdf" in mime_type:
        return _extract_pdf_text(data)
    elif "wordprocessing" in mime_type:
        return _extract_docx_text(data)
    else:
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Metadata parsing from filename / full text
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_DOI_RE  = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", re.IGNORECASE)
_AUTHOR_SECTION_RE = re.compile(
    r"(?:authors?|by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)*)",
    re.IGNORECASE,
)


def _infer_year(text: str, filename: str) -> Optional[int]:
    for src in (filename, text[:2000]):
        m = _YEAR_RE.search(src)
        if m:
            return int(m.group())
    return None


def _infer_doi(text: str) -> Optional[str]:
    m = _DOI_RE.search(text[:5000])
    return m.group() if m else None


def _infer_authors(text: str) -> List[str]:
    m = _AUTHOR_SECTION_RE.search(text[:3000])
    if m:
        raw = m.group(1)
        return [a.strip() for a in raw.split(",") if a.strip()]
    return []


def _infer_title(text: str, filename: str) -> str:
    lines = [l.strip() for l in text[:2000].split("\n") if l.strip()]
    # Use first substantial line that isn't just numbers/metadata
    for line in lines[:10]:
        if len(line) > 20 and not line.startswith("http") and not re.match(r"^\d", line):
            return line[:250]
    # Fall back to filename without extension
    return os.path.splitext(filename)[0]


def _abstract_from_text(text: str) -> str:
    """Try to extract the abstract section from full text."""
    m = re.search(
        r"(?:abstract|summary)[:\s]*\n?(.*?)(?:\n{2,}|\bintroduction\b|\bkeywords?\b)",
        text[:8000], re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).strip()[:3000]
    # Fall back to first 800 chars of body
    return text[:800].strip()


# ---------------------------------------------------------------------------
# Ledger — tracks which Drive file IDs have been ingested
# ---------------------------------------------------------------------------

class _Ledger:
    def __init__(self, path: str = LEDGER_PATH):
        self.path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        try:
            if os.path.exists(self.path):
                with open(self.path) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def seen(self, file_id: str, modified_time: str) -> bool:
        entry = self._data.get(file_id)
        return entry is not None and entry.get("modified_time") == modified_time

    def mark(self, file_id: str, modified_time: str, filename: str):
        self._data[file_id] = {"modified_time": modified_time, "filename": filename}
        self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self.path)

    def all_entries(self) -> dict:
        return dict(self._data)

    def count(self) -> int:
        return len(self._data)


# ---------------------------------------------------------------------------
# GDriveFetcher
# ---------------------------------------------------------------------------

class GDriveFetcher(BaseFetcher):
    """
    Fetches papers from a Google Drive folder (and its sub-folders).

    Unlike the query-based fetchers, this one ignores the `query` argument
    and instead scans the entire folder tree for new/modified files.
    """

    SOURCE = "google_drive"

    def __init__(self, folder_id: str = None, force_reprocess: bool = False):
        super().__init__(delay_seconds=0.5)
        from src.backend.integrations.gdrive_client import DRIVE_FOLDER_ID
        self.folder_id = folder_id or DRIVE_FOLDER_ID
        self.force_reprocess = force_reprocess
        self.ledger = _Ledger()

    def source_name(self) -> str:
        return self.SOURCE

    def search(self, query: str = "", max_results: int = 500) -> List[PaperRecord]:
        """
        Scan the Drive folder and return PaperRecord for each new/modified file.
        The `query` parameter is ignored (Drive folder is the data source).
        """
        from src.backend.integrations.gdrive_client import list_files_in_folder, download_file_bytes

        try:
            files = list_files_in_folder(self.folder_id, recursive=True)
        except Exception as e:
            logger.error("Drive listing failed: %s", e)
            return []

        records = []
        processed = 0
        skipped = 0

        for f in files[:max_results]:
            file_id = f["id"]
            filename = f["name"]
            mime = f["mimeType"]
            mod_time = f.get("modifiedTime", "")

            if not self.force_reprocess and self.ledger.seen(file_id, mod_time):
                skipped += 1
                continue

            self._rate_limit()
            try:
                data = download_file_bytes(file_id, mime)
                text = _extract_text(data, mime)

                if len(text.strip()) < 50:
                    logger.debug("Skipping %s — too little text extracted", filename)
                    continue

                title = _infer_title(text, filename)
                abstract = _abstract_from_text(text)
                doi = _infer_doi(text)
                year = _infer_year(text, filename)
                authors = _infer_authors(text)

                record = PaperRecord(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    doi=doi,
                    year=year,
                    journal=None,
                    url=f.get("webViewLink"),
                    pdf_url=f.get("webViewLink"),
                    source_api=self.SOURCE,
                )
                # Stash Drive metadata in arxiv_id field (prefixed) so dedup works
                record.arxiv_id = f"gdrive:{file_id}"
                # Also attach full text for deep extraction
                record._full_text = text
                record._drive_file_id = file_id
                record._drive_filename = filename

                self.ledger.mark(file_id, mod_time, filename)
                records.append(record)
                processed += 1
                logger.info("Drive: processed '%s' (%d chars)", filename[:60], len(text))

            except Exception as e:
                logger.warning("Drive: failed to process file %s (%s): %s", filename, file_id, e)

        logger.info(
            "Drive sync: %d new files processed, %d already seen",
            processed, skipped,
        )
        return records

    def list_all_files(self) -> List[dict]:
        """List all files in Drive folder (for UI display)."""
        from src.backend.integrations.gdrive_client import list_files_in_folder
        return list_files_in_folder(self.folder_id, recursive=True)

    def sync_stats(self) -> dict:
        return {
            "ledger_count": self.ledger.count(),
            "folder_id": self.folder_id,
            "entries": self.ledger.all_entries(),
        }
