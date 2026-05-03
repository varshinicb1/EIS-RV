"""
Main Pipeline Orchestrator
============================
Coordinates the full paper ingestion workflow:

    1. Fetch papers from all API sources
    2. Deduplicate against existing database
    3. Store new papers
    4. Extract scientific data from abstracts
    5. Store extracted data with provenance
    6. Export datasets to CSV/JSON

Usage:
    from src.backend.research.pipeline import ResearchPipeline

    pipeline = ResearchPipeline()
    stats = pipeline.run()
    print(stats)
"""

import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from .config import (
    DB_PATH, EXPORT_DIR, SEARCH_QUERIES,
    MAX_PAPERS_PER_QUERY, LOG_DIR, LOG_FORMAT, LOG_LEVEL,
)
from .schema import init_database, get_connection
from .fetchers.base import PaperRecord
from .fetchers.arxiv_fetcher import ArxivFetcher
from .fetchers.crossref_fetcher import CrossrefFetcher
from .fetchers.semantic_scholar import SemanticScholarFetcher
from .processors.scientific_parser import ScientificExtractor
from .dedup import Deduplicator
from .export import (
    export_papers_csv, export_materials_csv,
    export_eis_csv, export_full_json,
)

logger = logging.getLogger(__name__)


class PipelineStats:
    """Tracks pipeline run statistics."""

    def __init__(self):
        self.queries_run = 0
        self.papers_fetched = 0
        self.papers_new = 0
        self.papers_duplicate = 0
        self.papers_processed = 0
        self.papers_failed = 0
        self.materials_extracted = 0
        self.eis_records_extracted = 0
        self.synthesis_records = 0
        self.errors: List[str] = []
        self.start_time = time.time()
        self.end_time: Optional[float] = None

    def to_dict(self) -> dict:
        elapsed = (self.end_time or time.time()) - self.start_time
        return {
            "queries_run": self.queries_run,
            "papers_fetched": self.papers_fetched,
            "papers_new": self.papers_new,
            "papers_duplicate": self.papers_duplicate,
            "papers_processed": self.papers_processed,
            "papers_failed": self.papers_failed,
            "materials_extracted": self.materials_extracted,
            "eis_records_extracted": self.eis_records_extracted,
            "synthesis_records": self.synthesis_records,
            "errors_count": len(self.errors),
            "elapsed_seconds": round(elapsed, 1),
        }

    def __repr__(self):
        d = self.to_dict()
        lines = ["Pipeline Run Statistics:"]
        for k, v in d.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)


class ResearchPipeline:
    """
    Main orchestrator for the research paper ingestion pipeline.

    This class:
    - Fetches papers from arXiv, CrossRef, and Semantic Scholar
    - Deduplicates against the existing database
    - Extracts structured scientific data from abstracts
    - Stores everything in SQLite with full provenance
    - Exports to CSV and JSON
    """

    def __init__(
        self,
        db_path: str = DB_PATH,
        queries: Optional[List[str]] = None,
        max_per_query: int = MAX_PAPERS_PER_QUERY,
    ):
        self.db_path = db_path
        self.queries = queries or SEARCH_QUERIES
        self.max_per_query = max_per_query

        # Initialize database
        self.conn = init_database(db_path)

        # Initialize components
        self.fetchers = [
            ArxivFetcher(delay_seconds=3.0),
            SemanticScholarFetcher(delay_seconds=1.5),
            CrossrefFetcher(delay_seconds=1.0),
        ]
        self.dedup = Deduplicator(self.conn)
        self.extractor = ScientificExtractor()

    def run(
        self,
        queries: Optional[List[str]] = None,
        max_per_query: Optional[int] = None,
        skip_export: bool = False,
    ) -> PipelineStats:
        """
        Execute the full pipeline.

        Args:
            queries: Override search queries (uses config default if None)
            max_per_query: Override max papers per query
            skip_export: Skip CSV/JSON export step

        Returns:
            PipelineStats with detailed run metrics
        """
        queries = queries or self.queries
        max_per_query = max_per_query or self.max_per_query
        stats = PipelineStats()

        # Log pipeline run
        run_id = self._log_run_start()

        logger.info(
            "Starting pipeline: %d queries, %d fetchers, max %d/query",
            len(queries), len(self.fetchers), max_per_query,
        )

        # Phase 1: Fetch papers
        all_papers = self._fetch_all(queries, max_per_query, stats)

        # Phase 2: Deduplicate and store
        new_paper_ids = self._store_papers(all_papers, stats)

        # Phase 3: Extract scientific data from abstracts
        self._process_papers(new_paper_ids, stats)

        # Phase 4: Export
        if not skip_export:
            self._export_datasets()

        stats.end_time = time.time()
        self._log_run_end(run_id, stats)

        logger.info(str(stats))
        return stats

    def _fetch_all(
        self,
        queries: List[str],
        max_per_query: int,
        stats: PipelineStats,
    ) -> List[PaperRecord]:
        """Fetch papers from all sources for all queries."""
        all_papers = []

        for query in queries:
            for fetcher in self.fetchers:
                try:
                    papers = fetcher.search(query, max_results=max_per_query)
                    all_papers.extend(papers)
                    stats.papers_fetched += len(papers)
                    stats.queries_run += 1
                    logger.info(
                        "  [%s] '%s' -> %d papers",
                        fetcher.source_name(), query[:40], len(papers),
                    )
                except Exception as e:
                    error_msg = f"{fetcher.source_name()} failed for '{query[:30]}': {e}"
                    logger.error(error_msg)
                    stats.errors.append(error_msg)

        logger.info("Total papers fetched (raw): %d", len(all_papers))
        return all_papers

    def _store_papers(
        self,
        papers: List[PaperRecord],
        stats: PipelineStats,
    ) -> List[int]:
        """Deduplicate and store papers. Returns list of new paper IDs."""
        new_ids = []

        for paper in papers:
            # Dedup check
            if self.dedup.is_duplicate(
                title=paper.title,
                doi=paper.doi,
                arxiv_id=paper.arxiv_id,
            ):
                stats.papers_duplicate += 1
                continue

            # Insert into database
            try:
                authors_json = json.dumps(paper.authors)
                cursor = self.conn.execute(
                    """
                    INSERT INTO papers
                        (title, authors, abstract, doi, arxiv_id,
                         semantic_scholar_id, year, journal, url, pdf_url,
                         source_api, processed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        paper.title, authors_json, paper.abstract,
                        paper.doi, paper.arxiv_id, paper.semantic_scholar_id,
                        paper.year, paper.journal, paper.url, paper.pdf_url,
                        paper.source_api,
                    ),
                )
                paper_id = cursor.lastrowid
                self.conn.commit()

                # Register in dedup cache
                self.dedup.register(
                    title=paper.title,
                    paper_id=paper_id,
                    doi=paper.doi,
                    arxiv_id=paper.arxiv_id,
                )

                new_ids.append(paper_id)
                stats.papers_new += 1

            except Exception as e:
                logger.warning("Failed to insert paper '%s': %s", paper.title[:40], e)
                stats.errors.append(f"Insert failed: {paper.title[:40]}: {e}")

        logger.info(
            "Stored %d new papers (%d duplicates skipped)",
            stats.papers_new, stats.papers_duplicate,
        )
        return new_ids

    def _process_papers(self, paper_ids: List[int], stats: PipelineStats):
        """Extract scientific data from paper abstracts."""
        for paper_id in paper_ids:
            try:
                row = self.conn.execute(
                    "SELECT abstract, title FROM papers WHERE id=?", (paper_id,)
                ).fetchone()

                if not row:
                    continue

                # Use abstract (or title as fallback) for extraction
                text = row["abstract"] or row["title"] or ""

                result = self.extractor.extract(text, paper_id=paper_id)

                # Store extracted materials
                for mat in result.materials:
                    self.conn.execute(
                        """
                        INSERT INTO materials
                            (paper_id, component, ratio_value, ratio_unit,
                             confidence)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (paper_id, mat["component"], mat.get("ratio_value"),
                         mat.get("ratio_unit"), mat["confidence"]),
                    )
                    stats.materials_extracted += 1

                # Store synthesis data
                for syn in result.synthesis:
                    self.conn.execute(
                        """
                        INSERT INTO synthesis
                            (paper_id, method, temperature_C, duration_hours,
                             pH, confidence)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (paper_id, syn.get("method"), syn.get("temperature_C"),
                         syn.get("duration_hours"), syn.get("pH"),
                         syn["confidence"]),
                    )
                    stats.synthesis_records += 1

                # Store EIS data
                eis = result.eis_data
                if eis:
                    # Compute overall confidence
                    conf_keys = [k for k in eis if k.endswith("_confidence")]
                    avg_conf = sum(eis[k] for k in conf_keys) / len(conf_keys) \
                        if conf_keys else 0.5

                    self.conn.execute(
                        """
                        INSERT INTO eis_data
                            (paper_id, Rs_ohm, Rct_ohm, Cdl_F,
                             sigma_warburg, capacitance_F_g,
                             capacitance_mF_cm2, electrolyte,
                             freq_min_Hz, freq_max_Hz, confidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            paper_id,
                            eis.get("Rs_ohm"), eis.get("Rct_ohm"),
                            eis.get("Cdl_F"), eis.get("sigma_warburg"),
                            eis.get("capacitance_F_g"),
                            eis.get("capacitance_mF_cm2"),
                            eis.get("electrolyte"),
                            eis.get("freq_min_Hz"), eis.get("freq_max_Hz"),
                            round(avg_conf, 2),
                        ),
                    )
                    stats.eis_records_extracted += 1

                # Store extraction provenance log
                for log_entry in result.extractions_log:
                    self.conn.execute(
                        """
                        INSERT INTO extractions
                            (paper_id, target_table, field_name,
                             extracted_value, confidence, extraction_method)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            log_entry["paper_id"],
                            log_entry["target_table"],
                            log_entry["field_name"],
                            log_entry["extracted_value"],
                            log_entry["confidence"],
                            log_entry["extraction_method"],
                        ),
                    )

                # Update application if detected
                if result.application:
                    self.conn.execute(
                        "UPDATE papers SET application=? WHERE id=?",
                        (result.application, paper_id),
                    )

                # Mark as processed
                self.conn.execute(
                    "UPDATE papers SET processed=1 WHERE id=?", (paper_id,)
                )
                self.conn.commit()
                stats.papers_processed += 1

            except Exception as e:
                logger.error("Processing failed for paper %d: %s", paper_id, e)
                stats.papers_failed += 1
                stats.errors.append(f"Processing paper {paper_id}: {e}")
                try:
                    self.conn.execute(
                        "UPDATE papers SET processed=-1, processing_error=? WHERE id=?",
                        (str(e), paper_id),
                    )
                    self.conn.commit()
                except Exception:
                    pass

        logger.info(
            "Processed %d papers: %d materials, %d synthesis, %d EIS records",
            stats.papers_processed, stats.materials_extracted,
            stats.synthesis_records, stats.eis_records_extracted,
        )

    def _export_datasets(self):
        """Export all data to CSV and JSON."""
        import os

        try:
            export_papers_csv(
                self.conn, os.path.join(EXPORT_DIR, "papers.csv")
            )
            export_materials_csv(
                self.conn, os.path.join(EXPORT_DIR, "materials.csv")
            )
            export_eis_csv(
                self.conn, os.path.join(EXPORT_DIR, "eis_data.csv")
            )
            export_full_json(
                self.conn, os.path.join(EXPORT_DIR, "full_dataset.json")
            )
            logger.info("All exports complete -> %s", EXPORT_DIR)
        except Exception as e:
            logger.error("Export failed: %s", e)

    def _log_run_start(self) -> int:
        """Log pipeline run start in database."""
        cursor = self.conn.execute(
            "INSERT INTO pipeline_runs (status) VALUES ('running')"
        )
        self.conn.commit()
        return cursor.lastrowid

    def _log_run_end(self, run_id: int, stats: PipelineStats):
        """Log pipeline run completion in database."""
        self.conn.execute(
            """
            UPDATE pipeline_runs SET
                finished_at=CURRENT_TIMESTAMP,
                papers_fetched=?,
                papers_processed=?,
                papers_failed=?,
                queries_run=?,
                status=?
            WHERE id=?
            """,
            (
                stats.papers_fetched, stats.papers_processed,
                stats.papers_failed, stats.queries_run,
                "completed" if not stats.errors else "completed_with_errors",
                run_id,
            ),
        )
        self.conn.commit()

    def get_database_stats(self) -> dict:
        """Get current database statistics."""
        stats = {}

        stats["total_papers"] = self.conn.execute(
            "SELECT COUNT(*) FROM papers"
        ).fetchone()[0]

        stats["processed_papers"] = self.conn.execute(
            "SELECT COUNT(*) FROM papers WHERE processed=1"
        ).fetchone()[0]

        stats["total_materials"] = self.conn.execute(
            "SELECT COUNT(*) FROM materials"
        ).fetchone()[0]

        stats["unique_materials"] = self.conn.execute(
            "SELECT COUNT(DISTINCT component) FROM materials"
        ).fetchone()[0]

        stats["total_eis_records"] = self.conn.execute(
            "SELECT COUNT(*) FROM eis_data"
        ).fetchone()[0]

        stats["total_synthesis"] = self.conn.execute(
            "SELECT COUNT(*) FROM synthesis"
        ).fetchone()[0]

        stats["total_extractions"] = self.conn.execute(
            "SELECT COUNT(*) FROM extractions"
        ).fetchone()[0]

        # Application distribution
        app_rows = self.conn.execute(
            "SELECT application, COUNT(*) as cnt FROM papers "
            "WHERE application IS NOT NULL GROUP BY application "
            "ORDER BY cnt DESC"
        ).fetchall()
        stats["applications"] = {r["application"]: r["cnt"] for r in app_rows}

        # Source distribution
        src_rows = self.conn.execute(
            "SELECT source_api, COUNT(*) as cnt FROM papers "
            "GROUP BY source_api ORDER BY cnt DESC"
        ).fetchall()
        stats["sources"] = {r["source_api"]: r["cnt"] for r in src_rows}

        return stats

    def close(self):
        """Close database connection."""
        self.conn.close()
