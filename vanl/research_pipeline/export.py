"""
Data Export
=============
Export the research database to CSV and JSON formats.
"""

import csv
import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def export_papers_csv(conn, output_path: str) -> int:
    """Export papers table to CSV. Returns number of rows exported."""
    cursor = conn.execute("""
        SELECT p.id, p.title, p.authors, p.doi, p.arxiv_id, p.year,
               p.journal, p.application, p.source_api, p.url, p.pdf_url
        FROM papers p
        ORDER BY p.year DESC, p.id
    """)

    rows = cursor.fetchall()
    if not rows:
        logger.warning("No papers to export")
        return 0

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "title", "authors", "doi", "arxiv_id", "year",
            "journal", "application", "source_api", "url", "pdf_url",
        ])
        for row in rows:
            writer.writerow(list(row))

    logger.info("Exported %d papers to %s", len(rows), output_path)
    return len(rows)


def export_materials_csv(conn, output_path: str) -> int:
    """Export materials with paper titles to CSV."""
    cursor = conn.execute("""
        SELECT m.id, p.title, p.doi, m.component, m.ratio_value,
               m.ratio_unit, m.role, m.confidence
        FROM materials m
        JOIN papers p ON m.paper_id = p.id
        ORDER BY m.component, m.confidence DESC
    """)

    rows = cursor.fetchall()
    if not rows:
        return 0

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "paper_title", "doi", "component", "ratio_value",
            "ratio_unit", "role", "confidence",
        ])
        for row in rows:
            writer.writerow(list(row))

    logger.info("Exported %d material records to %s", len(rows), output_path)
    return len(rows)


def export_eis_csv(conn, output_path: str) -> int:
    """Export EIS data with paper titles to CSV."""
    cursor = conn.execute("""
        SELECT e.id, p.title, p.doi, e.Rs_ohm, e.Rct_ohm, e.Cdl_F,
               e.sigma_warburg, e.capacitance_F_g, e.capacitance_mF_cm2,
               e.electrolyte, e.freq_min_Hz, e.freq_max_Hz, e.confidence
        FROM eis_data e
        JOIN papers p ON e.paper_id = p.id
        ORDER BY e.confidence DESC
    """)

    rows = cursor.fetchall()
    if not rows:
        return 0

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "paper_title", "doi", "Rs_ohm", "Rct_ohm", "Cdl_F",
            "sigma_warburg", "capacitance_F_g", "capacitance_mF_cm2",
            "electrolyte", "freq_min_Hz", "freq_max_Hz", "confidence",
        ])
        for row in rows:
            writer.writerow(list(row))

    logger.info("Exported %d EIS records to %s", len(rows), output_path)
    return len(rows)


def export_full_json(conn, output_path: str) -> int:
    """Export complete dataset as structured JSON."""
    papers = []

    paper_rows = conn.execute("""
        SELECT id, title, authors, doi, arxiv_id, year, journal,
               application, source_api, url
        FROM papers ORDER BY id
    """).fetchall()

    for p in paper_rows:
        paper = dict(p)
        paper_id = p["id"]

        # Parse authors JSON
        try:
            paper["authors"] = json.loads(paper["authors"]) if paper["authors"] else []
        except (json.JSONDecodeError, TypeError):
            paper["authors"] = []

        # Materials
        mat_rows = conn.execute(
            "SELECT component, ratio_value, ratio_unit, confidence "
            "FROM materials WHERE paper_id=?", (paper_id,)
        ).fetchall()
        paper["materials"] = [dict(r) for r in mat_rows]

        # Synthesis
        syn_rows = conn.execute(
            "SELECT method, temperature_C, duration_hours, pH, confidence "
            "FROM synthesis WHERE paper_id=?", (paper_id,)
        ).fetchall()
        paper["synthesis"] = [dict(r) for r in syn_rows]

        # EIS data
        eis_rows = conn.execute(
            "SELECT Rs_ohm, Rct_ohm, Cdl_F, sigma_warburg, "
            "capacitance_F_g, capacitance_mF_cm2, electrolyte, "
            "freq_min_Hz, freq_max_Hz, confidence "
            "FROM eis_data WHERE paper_id=?", (paper_id,)
        ).fetchall()
        paper["eis_data"] = [dict(r) for r in eis_rows]

        papers.append(paper)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"papers": papers, "count": len(papers)}, f, indent=2,
                  default=str, ensure_ascii=False)

    logger.info("Exported %d papers to %s", len(papers), output_path)
    return len(papers)
