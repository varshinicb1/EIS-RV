"""
Google Drive Fetcher (Docling-powered)
========================================
Implements BaseFetcher for Google Drive.

• Recursively scans the configured Drive folder
• Uses docling_parser (Docling → PyMuPDF → pdfminer) for best-in-class
  scientific PDF extraction (tables, sections, headings, captions)
• Tracks processed file IDs in a local JSON ledger
• Returns PaperRecord objects compatible with ResearchPipeline
"""

import hashlib
import json
import logging
import os
import re
from typing import List, Optional

from .base import BaseFetcher, PaperRecord
from src.backend.research.config import DATA_DIR

logger = logging.getLogger(__name__)

LEDGER_PATH = os.path.join(DATA_DIR, "gdrive_ledger.json")


# ── Ledger ────────────────────────────────────────────────────────────────────

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


# ── GDriveFetcher ─────────────────────────────────────────────────────────────

class GDriveFetcher(BaseFetcher):
    """Fetches papers from a Google Drive folder using Docling-powered parsing."""

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
        from src.backend.integrations.gdrive_client import list_files_in_folder, download_file_bytes
        from src.backend.research.docling_parser import parse_document

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
                parsed = parse_document(data, mime, filename=filename)

                if len(parsed.full_text.strip()) < 50:
                    logger.debug("Skipping %s — too little text extracted", filename)
                    continue

                # Use parser-extracted fields or fall back to heuristics
                title = parsed.title or _infer_title_fallback(parsed.full_text, filename)
                abstract = parsed.abstract or parsed.full_text[:800]
                authors = parsed.authors or []
                doi = _infer_doi(parsed.full_text)
                year = _infer_year(parsed.full_text, filename)

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
                record.arxiv_id = f"gdrive:{file_id}"
                record._full_text = parsed.full_text
                record._sections = parsed.sections
                record._tables = parsed.tables
                record._parser_used = parsed.parser_used
                record._drive_file_id = file_id
                record._drive_filename = filename
                record._page_count = parsed.page_count

                self.ledger.mark(file_id, mod_time, filename)
                records.append(record)
                processed += 1
                logger.info(
                    "Drive [%s]: '%s' — %d chars, %d tables, %d pages",
                    parsed.parser_used, filename[:60],
                    len(parsed.full_text), len(parsed.tables), parsed.page_count,
                )

            except Exception as e:
                logger.warning("Drive: failed to process %s (%s): %s", filename, file_id, e)

        logger.info("Drive sync: %d new, %d already seen", processed, skipped)
        return records

    def list_all_files(self) -> List[dict]:
        from src.backend.integrations.gdrive_client import list_files_in_folder
        return list_files_in_folder(self.folder_id, recursive=True)

    def sync_stats(self) -> dict:
        return {
            "ledger_count": self.ledger.count(),
            "folder_id": self.folder_id,
            "entries": self.ledger.all_entries(),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_DOI_RE  = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", re.IGNORECASE)


def _infer_year(text: str, filename: str) -> Optional[int]:
    for src in (filename, text[:2000]):
        m = _YEAR_RE.search(src)
        if m:
            yr = int(m.group())
            if 1990 <= yr <= 2030:
                return yr
    return None


def _infer_doi(text: str) -> Optional[str]:
    m = _DOI_RE.search(text[:5000])
    return m.group() if m else None


def _infer_title_fallback(text: str, filename: str) -> str:
    lines = [l.strip() for l in text[:2000].split("\n") if l.strip()]
    for line in lines[:10]:
        if len(line) > 20 and not line.startswith("http") and not re.match(r"^\d", line):
            return line[:250]
    return os.path.splitext(filename)[0]
