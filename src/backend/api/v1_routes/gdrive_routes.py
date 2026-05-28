"""
Google Drive Integration Routes
=================================
Endpoints for Drive sync, paper listing, and literature review generation.
"""

import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2/drive", tags=["Google Drive"])


# ── Background sync state ────────────────────────────────────────────────
_sync_state = {
    "running": False,
    "last_run": None,
    "last_stats": None,
    "last_error": None,
    "progress": "",
}


def _do_sync(force: bool = False):
    """Run the Drive sync in the background."""
    from src.backend.research.fetchers.gdrive_fetcher import GDriveFetcher
    from src.backend.research.pipeline import ResearchPipeline
    from src.backend.research.config import DB_PATH

    _sync_state["running"] = True
    _sync_state["last_error"] = None
    _sync_state["progress"] = "Connecting to Google Drive…"

    try:
        fetcher = GDriveFetcher(force_reprocess=force)
        _sync_state["progress"] = "Listing files in Drive folder…"
        records = fetcher.search(max_results=500)

        _sync_state["progress"] = f"Processing {len(records)} new papers…"

        pipeline = ResearchPipeline(db_path=DB_PATH)
        new_ids = pipeline._store_papers(records, type("S", (), {
            "papers_new": 0, "papers_duplicate": 0, "errors": []
        })())

        # Also store full text for papers that have it
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        for record in records:
            ft = getattr(record, "_full_text", None)
            fid = getattr(record, "_drive_file_id", None)
            fname = getattr(record, "_drive_filename", None)
            if ft:
                conn.execute(
                    "UPDATE papers SET full_text=? WHERE arxiv_id=?",
                    (ft[:50000], f"gdrive:{fid}"),
                )
        conn.commit()
        conn.close()

        _sync_state["progress"] = "Extracting scientific data…"
        import sqlite3 as _sq
        _conn = _sq.connect(DB_PATH)
        _conn.row_factory = _sq.Row
        new_paper_ids = [r[0] for r in _conn.execute(
            "SELECT id FROM papers WHERE source_api='google_drive' AND processed=0"
        ).fetchall()]
        _conn.close()

        from src.backend.research.pipeline import PipelineStats
        stats = PipelineStats()
        pipeline.conn = sqlite3.connect(DB_PATH)
        pipeline.conn.row_factory = sqlite3.Row
        pipeline._process_papers(new_paper_ids, stats)
        pipeline.conn.close()

        import time
        _sync_state["last_run"] = time.time()
        _sync_state["last_stats"] = {
            "new_files": len(records),
            "processed": stats.papers_processed,
            "materials_extracted": stats.materials_extracted,
            "errors": len(stats.errors),
        }
        _sync_state["progress"] = "Sync complete"
        logger.info("Drive sync complete: %d new files", len(records))

    except Exception as e:
        logger.error("Drive sync failed: %s", e)
        _sync_state["last_error"] = str(e)
        _sync_state["progress"] = f"Error: {e}"
    finally:
        _sync_state["running"] = False


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/status")
async def drive_status():
    """Check Drive connection status and sync state."""
    from src.backend.integrations.gdrive_client import (
        get_folder_info, get_service_account_email,
    )
    from src.backend.research.fetchers.gdrive_fetcher import GDriveFetcher

    sa_email = get_service_account_email()

    try:
        folder_info = get_folder_info()
        connected = "error" not in folder_info
    except Exception as e:
        folder_info = {"error": str(e)}
        connected = False

    fetcher = GDriveFetcher()
    sync_stats = fetcher.sync_stats()

    return {
        "connected": connected,
        "service_account_email": sa_email,
        "folder_info": folder_info,
        "sync": _sync_state,
        "ledger_count": sync_stats["ledger_count"],
        "share_reminder": f"Share your Drive folder with: {sa_email}" if sa_email else "",
    }


@router.post("/sync")
async def trigger_sync(background_tasks: BackgroundTasks, force: bool = False):
    """Trigger an async Drive sync. Returns immediately; poll /status for progress."""
    if _sync_state["running"]:
        raise HTTPException(status_code=409, detail="Sync already in progress")
    background_tasks.add_task(_do_sync, force=force)
    return {"status": "started", "message": "Drive sync started in background"}


@router.get("/files")
async def list_drive_files():
    """List all PDF/Doc files in the configured Drive folder."""
    from src.backend.research.fetchers.gdrive_fetcher import GDriveFetcher
    try:
        fetcher = GDriveFetcher()
        files = fetcher.list_all_files()
        ledger = fetcher.sync_stats()["entries"]
        for f in files:
            f["processed"] = f["id"] in ledger
        return {"files": files, "total": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/papers")
async def list_drive_papers(limit: int = 100, offset: int = 0):
    """List papers that were ingested from Google Drive."""
    import sqlite3
    from src.backend.research.config import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, title, authors, year, journal, url, processed, fetched_at
           FROM papers WHERE source_api='google_drive'
           ORDER BY fetched_at DESC LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM papers WHERE source_api='google_drive'"
    ).fetchone()[0]
    conn.close()

    import json
    papers = []
    for r in rows:
        papers.append({
            "id": r["id"], "title": r["title"],
            "authors": json.loads(r["authors"] or "[]"),
            "year": r["year"], "journal": r["journal"],
            "url": r["url"], "processed": r["processed"],
            "fetched_at": r["fetched_at"],
        })
    return {"papers": papers, "total": total, "limit": limit, "offset": offset}


@router.get("/review")
async def get_literature_review(source: Optional[str] = None):
    """
    Generate and return a consolidated EC sensor literature review.
    source: 'google_drive' | 'all' (default: all)
    """
    from src.backend.research.literature_review import generate_review, review_to_dict, material_formula_table
    from src.backend.research.config import DB_PATH

    try:
        src_filter = "google_drive" if source == "google_drive" else None
        review = generate_review(DB_PATH, source_filter=src_filter)
        d = review_to_dict(review)
        d["material_formula_table"] = material_formula_table(review.material_counts)
        return d
    except Exception as e:
        logger.error("Literature review failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review/export")
async def export_literature_review():
    """Export full literature review as a downloadable JSON report."""
    from src.backend.research.literature_review import generate_review, review_to_dict, material_formula_table
    from src.backend.research.config import DB_PATH
    from fastapi.responses import JSONResponse
    import time

    try:
        review = generate_review(DB_PATH)
        d = review_to_dict(review)
        d["material_formula_table"] = material_formula_table(review.material_counts)
        d["generated_at"] = time.time()
        d["report_title"] = "EC Sensor Literature Review — RĀMAN Studio"
        return JSONResponse(content=d, headers={
            "Content-Disposition": "attachment; filename=ec_sensor_literature_review.json"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
