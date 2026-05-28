"""
Google Drive Integration Routes
=================================
Endpoints:
  GET  /api/v2/drive/status           — connection & sync state
  POST /api/v2/drive/sync             — trigger Drive scan + ingest
  GET  /api/v2/drive/files            — list Drive files
  GET  /api/v2/drive/papers           — papers ingested from Drive
  POST /api/v2/drive/extract          — run EC extraction on all papers
  GET  /api/v2/drive/ec-table         — master EC comparison table
  GET  /api/v2/drive/review           — full literature review JSON
  GET  /api/v2/drive/review/export    — download review as JSON
  GET  /api/v2/drive/review/markdown  — download review as Markdown
"""

import json
import logging
import sqlite3
import time
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2/drive", tags=["Google Drive"])

# ── Shared state ──────────────────────────────────────────────────────────────

_sync_state = {
    "running": False, "last_run": None, "last_stats": None,
    "last_error": None, "progress": "", "files_found": 0,
}
_extract_state = {
    "running": False, "last_run": None, "last_stats": None,
    "last_error": None, "progress": "",
}


# ── Background: Drive sync ────────────────────────────────────────────────────

def _do_sync(force: bool = False):
    from src.backend.research.fetchers.gdrive_fetcher import GDriveFetcher
    from src.backend.research.pipeline import ResearchPipeline, PipelineStats
    from src.backend.research.config import DB_PATH
    from src.backend.research.ec_extractor import ensure_ec_table, run_batch_extraction

    _sync_state.update(running=True, last_error=None, progress="Connecting to Google Drive…")
    try:
        fetcher = GDriveFetcher(force_reprocess=force)
        _sync_state["progress"] = "Listing files in Drive folder…"

        records = fetcher.search(max_results=500)
        _sync_state["files_found"] = len(records)
        _sync_state["progress"] = f"Storing {len(records)} papers in database…"

        pipeline = ResearchPipeline(db_path=DB_PATH)
        stats = PipelineStats()
        pipeline._store_papers(records, stats)

        # Persist full_text, sections, tables
        conn = sqlite3.connect(DB_PATH)
        for r in records:
            ft = getattr(r, "_full_text", None)
            fid = getattr(r, "_drive_file_id", None)
            tables = getattr(r, "_tables", [])
            sections = getattr(r, "_sections", {})
            parser = getattr(r, "_parser_used", "")
            if ft and fid:
                # Store sections and tables as extended full_text
                extended = ft
                if tables:
                    extended += "\n\n--- EXTRACTED TABLES ---\n" + "\n\n".join(tables[:10])
                conn.execute(
                    "UPDATE papers SET full_text=? WHERE arxiv_id=?",
                    (extended[:80000], f"gdrive:{fid}"),
                )
        conn.commit()

        # Scientific extraction on new papers
        _sync_state["progress"] = "Extracting scientific data…"
        new_ids = [
            r[0] for r in conn.execute(
                "SELECT id FROM papers WHERE source_api='google_drive' AND processed=0"
            ).fetchall()
        ]
        conn.close()

        if new_ids:
            pipeline.conn = sqlite3.connect(DB_PATH)
            pipeline.conn.row_factory = sqlite3.Row
            pipeline._process_papers(new_ids, stats)
            pipeline.conn.close()

        # EC extraction
        _sync_state["progress"] = "Running EC sensor data extraction…"
        ec_conn = sqlite3.connect(DB_PATH)
        ensure_ec_table(ec_conn)
        ec_conn.close()
        ec_stats = run_batch_extraction(DB_PATH, source_filter="google_drive", force=force)

        _sync_state.update(
            last_run=time.time(), progress="Sync complete",
            last_stats={
                "files_found": len(records),
                "papers_new": stats.papers_new,
                "papers_processed": stats.papers_processed,
                "materials_extracted": stats.materials_extracted,
                "ec_extracted": ec_stats.get("extracted", 0),
                "nim_validated": ec_stats.get("nim_used", 0),
            },
        )
    except Exception as e:
        logger.error("Drive sync failed: %s", e)
        _sync_state.update(last_error=str(e), progress=f"Error: {e}")
    finally:
        _sync_state["running"] = False


# ── Background: EC extraction ─────────────────────────────────────────────────

def _do_extraction(force: bool = False, source: Optional[str] = None, use_nim: bool = True):
    from src.backend.research.ec_extractor import run_batch_extraction, ensure_ec_table
    from src.backend.research.config import DB_PATH

    _extract_state.update(running=True, last_error=None, progress="Initialising EC extractor…")
    try:
        conn = sqlite3.connect(DB_PATH)
        ensure_ec_table(conn)
        conn.close()

        total = sqlite3.connect(DB_PATH).execute(
            "SELECT COUNT(*) FROM papers" + (" WHERE source_api=?" if source else ""),
            [source] if source else [],
        ).fetchone()[0]

        _extract_state["progress"] = f"Extracting EC data from {total} papers (NIM={'on' if use_nim else 'off'})…"
        stats = run_batch_extraction(
            DB_PATH, source_filter=source, force=force, use_nim=use_nim, max_papers=500,
        )
        _extract_state.update(
            running=False, last_run=time.time(), progress="Extraction complete",
            last_stats=stats,
        )
    except Exception as e:
        logger.error("EC extraction failed: %s", e)
        _extract_state.update(last_error=str(e), progress=f"Error: {e}", running=False)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def drive_status():
    from src.backend.integrations.gdrive_client import get_folder_info, get_service_account_email
    from src.backend.research.fetchers.gdrive_fetcher import GDriveFetcher
    from src.backend.research.config import DB_PATH

    sa_email = get_service_account_email()
    try:
        folder_info = get_folder_info()
        connected = "error" not in folder_info
    except Exception as e:
        folder_info = {"error": str(e)}
        connected = False

    fetcher = GDriveFetcher()
    sync_stats = fetcher.sync_stats()

    # Count EC records
    try:
        conn = sqlite3.connect(DB_PATH)
        ec_count = conn.execute(
            "SELECT COUNT(*) FROM ec_sensor_records"
        ).fetchone()[0]
        paper_count = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE source_api='google_drive'"
        ).fetchone()[0]
        conn.close()
    except Exception:
        ec_count = 0
        paper_count = 0

    return {
        "connected": connected,
        "service_account_email": sa_email,
        "folder_info": folder_info,
        "sync": _sync_state,
        "extract": _extract_state,
        "ledger_count": sync_stats["ledger_count"],
        "drive_papers": paper_count,
        "ec_records": ec_count,
        "share_reminder": f"Share your Drive folder with: {sa_email}" if sa_email and not connected else "",
    }


@router.post("/sync")
async def trigger_sync(background_tasks: BackgroundTasks, force: bool = False):
    if _sync_state["running"]:
        raise HTTPException(409, "Sync already in progress")
    background_tasks.add_task(_do_sync, force=force)
    return {"status": "started", "message": "Drive sync started in background"}


@router.post("/extract")
async def trigger_extraction(
    background_tasks: BackgroundTasks,
    force: bool = False,
    source: Optional[str] = None,
    use_nim: bool = True,
):
    """Run EC sensor data extraction on all papers (or a source subset)."""
    if _extract_state["running"]:
        raise HTTPException(409, "Extraction already in progress")
    background_tasks.add_task(_do_extraction, force=force, source=source, use_nim=use_nim)
    return {"status": "started", "message": f"EC extraction started (NIM={'on' if use_nim else 'off'})"}


@router.get("/files")
async def list_drive_files():
    from src.backend.research.fetchers.gdrive_fetcher import GDriveFetcher
    fetcher = GDriveFetcher()
    ledger_entries = fetcher.sync_stats()["entries"]
    try:
        files = fetcher.list_all_files()
        for f in files:
            f["processed"] = f["id"] in ledger_entries
        return {"files": files, "total": len(files), "connected": True}
    except Exception as e:
        logger.warning("Drive files listing failed (likely bad credentials): %s", e)
        # Return ledger-cached entries instead of a 500
        cached = [
            {"id": fid, "name": meta.get("filename","unknown"), "processed": True,
             "modifiedTime": meta.get("modified_time",""), "from_cache": True}
            for fid, meta in ledger_entries.items()
        ]
        return {
            "files": cached, "total": len(cached), "connected": False,
            "error": str(e),
            "fix": "Paste the full service_account.json from GCP → IAM & Admin → Service Accounts → Keys into the GOOGLE_SERVICE_ACCOUNT_JSON secret.",
        }


@router.get("/papers")
async def list_drive_papers(limit: int = 200, offset: int = 0):
    from src.backend.research.config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT p.id, p.title, p.authors, p.year, p.journal, p.url,
                  p.processed, p.fetched_at, p.source_api,
                  e.lod, e.sensitivity, e.analyte, e.electrode_type,
                  e.extraction_method, e.nim_validated
           FROM papers p
           LEFT JOIN ec_sensor_records e ON e.paper_id = p.id
           WHERE p.source_api='google_drive'
           ORDER BY p.fetched_at DESC LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM papers WHERE source_api='google_drive'"
    ).fetchone()[0]
    conn.close()
    papers = []
    for r in rows:
        papers.append({
            "id": r["id"], "title": r["title"],
            "authors": json.loads(r["authors"] or "[]"),
            "year": r["year"], "journal": r["journal"], "url": r["url"],
            "processed": r["processed"], "fetched_at": r["fetched_at"],
            "lod": r["lod"], "sensitivity": r["sensitivity"],
            "analyte": r["analyte"], "electrode_type": r["electrode_type"],
            "ec_extracted": r["extraction_method"] is not None,
            "nim_validated": bool(r["nim_validated"]),
        })
    return {"papers": papers, "total": total}


@router.get("/ec-table")
async def get_ec_table(
    limit: int = 500,
    offset: int = 0,
    analyte: Optional[str] = None,
    material: Optional[str] = None,
    technique: Optional[str] = None,
    has_lod: bool = False,
    source: Optional[str] = None,
):
    """
    Master EC sensor comparison table:
    Ref | Material | Electrode | Technique | LOD | Sensitivity |
    Sample Type | Interference Study | Commercial Potential
    """
    from src.backend.research.config import DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        where_clauses = []
        params = []

        if analyte:
            where_clauses.append("LOWER(e.analyte) LIKE ?")
            params.append(f"%{analyte.lower()}%")
        if material:
            where_clauses.append("LOWER(e.material) LIKE ?")
            params.append(f"%{material.lower()}%")
        if technique:
            where_clauses.append("LOWER(e.techniques) LIKE ?")
            params.append(f"%{technique.lower()}%")
        if has_lod:
            where_clauses.append("e.lod IS NOT NULL")
        if source:
            where_clauses.append("e.source_api = ?")
            params.append(source)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        rows = conn.execute(f"""
            SELECT
                e.id, e.paper_id, e.title, e.authors, e.year, e.journal, e.url,
                e.material, e.material_formula, e.electrode_type, e.techniques,
                e.analyte, e.lod, e.lod_numeric, e.lod_unit,
                e.sensitivity, e.linear_range,
                e.sample_types, e.recovery_pct,
                e.interference_study, e.interferents_tested,
                e.commercial_potential, e.commercial_keywords,
                e.challenges, e.fabrication_method, e.characterization,
                e.extraction_method, e.nim_validated, e.confidence,
                e.source_api
            FROM ec_sensor_records e
            {where_sql}
            ORDER BY e.lod_numeric ASC NULLS LAST, e.year DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        total = conn.execute(
            f"SELECT COUNT(*) FROM ec_sensor_records e {where_sql}", params
        ).fetchone()[0]
        conn.close()

        records = []
        for r in rows:
            records.append({
                "ref": r["paper_id"],
                "title": r["title"] or "—",
                "authors": json.loads(r["authors"] or "[]"),
                "year": r["year"],
                "journal": r["journal"],
                "url": r["url"],
                "material": r["material"] or "—",
                "material_formula": r["material_formula"],
                "electrode": r["electrode_type"] or "—",
                "techniques": json.loads(r["techniques"] or "[]"),
                "analyte": r["analyte"] or "—",
                "lod": r["lod"] or "—",
                "lod_numeric": r["lod_numeric"],
                "lod_unit": r["lod_unit"],
                "sensitivity": r["sensitivity"] or "—",
                "linear_range": r["linear_range"] or "—",
                "sample_types": json.loads(r["sample_types"] or "[]"),
                "recovery_pct": r["recovery_pct"],
                "interference_study": r["interference_study"],
                "interferents": json.loads(r["interferents_tested"] or "[]"),
                "commercial_potential": r["commercial_potential"] or "—",
                "commercial_keywords": json.loads(r["commercial_keywords"] or "[]"),
                "challenges": json.loads(r["challenges"] or "[]"),
                "fabrication": r["fabrication_method"],
                "characterization": json.loads(r["characterization"] or "[]"),
                "nim_validated": bool(r["nim_validated"]),
                "confidence": r["confidence"],
                "source": r["source_api"],
            })

        return {"records": records, "total": total, "limit": limit, "offset": offset}

    except Exception as e:
        logger.error("EC table error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/review")
async def get_literature_review(source: Optional[str] = None):
    from src.backend.research.literature_review import generate_review, review_to_dict, material_formula_table
    from src.backend.research.config import DB_PATH
    try:
        src_filter = source if source else None
        review = generate_review(DB_PATH, source_filter=src_filter)
        d = review_to_dict(review)
        d["material_formula_table"] = material_formula_table(review.material_counts)
        return d
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/review/export")
async def export_review_json():
    from src.backend.research.literature_review import generate_review, review_to_dict, material_formula_table
    from src.backend.research.config import DB_PATH
    review = generate_review(DB_PATH)
    d = review_to_dict(review)
    d["material_formula_table"] = material_formula_table(review.material_counts)
    d["generated_at"] = time.time()
    d["report_title"] = "EC Sensor Literature Review — RĀMAN Studio"
    return JSONResponse(content=d, headers={
        "Content-Disposition": "attachment; filename=ec_sensor_literature_review.json"
    })


@router.get("/review/markdown")
async def export_review_markdown():
    from src.backend.research.config import DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT e.*, p.journal
            FROM ec_sensor_records e
            LEFT JOIN papers p ON p.id = e.paper_id
            ORDER BY e.lod_numeric ASC NULLS LAST
        """).fetchall()
        total = len(rows)
        conn.close()

        md = _generate_markdown_report(rows, total)
        return PlainTextResponse(md, headers={
            "Content-Disposition": "attachment; filename=ec_sensor_review.md",
            "Content-Type": "text/markdown; charset=utf-8",
        })
    except Exception as e:
        raise HTTPException(500, str(e))


def _generate_markdown_report(rows, total: int) -> str:
    lines = [
        "# Comprehensive Consolidated Literature Review on Advanced Electrochemical Sensors",
        "",
        f"*Generated by RĀMAN Studio · {time.strftime('%Y-%m-%d')} · {total} papers analysed*",
        "",
        "---",
        "",
        "## Master Comparison Table",
        "",
        "| Ref | Material | Electrode | Technique | LOD | Sensitivity | Sample Type | Interference Study | Commercial Potential |",
        "|-----|----------|-----------|-----------|-----|-------------|-------------|-------------------|---------------------|",
    ]

    for i, r in enumerate(rows, 1):
        techs = ", ".join(json.loads(r["techniques"] or "[]"))
        samples = ", ".join(json.loads(r["sample_types"] or "[]")[:2])
        interferents = (r["interference_study"] or "—")[:60]
        lines.append(
            f"| {i} | {r['material'] or '—'} | {r['electrode_type'] or '—'} | "
            f"{techs or '—'} | {r['lod'] or '—'} | {r['sensitivity'] or '—'} | "
            f"{samples or '—'} | {interferents} | {r['commercial_potential'] or '—'} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Scope & Opportunities",
        "",
        "- Wearable & flexible sensors for continuous monitoring",
        "- Multi-analyte detection arrays (multiplexing)",
        "- Integration with IoT and smartphone readout",
        "- AI-guided material discovery for ultra-low LOD",
        "- Paper/textile-based sensors for field deployment",
        "- Green synthesis of electrode nanomaterials",
        "- Standardization of sensor fabrication protocols",
        "- Clinical validation for regulatory approval",
        "",
    ]
    return "\n".join(lines)
