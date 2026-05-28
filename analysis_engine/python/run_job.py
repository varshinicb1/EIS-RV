"""
CLI entry-point for the RVCE electrochemistry analysis pipeline.

Usage:
    python run_job.py <config_json_path>

The config JSON must contain:
    {
      "job_id": "...",
      "upload_paths": ["..."],
      "output_root": "...",
      "technique": "auto",
      "dpi": 300,
      "style": "reference",
      "material_query": null,
      "mp_api_key": null,
      "nvidia_api_key": null,
      "enable_ai": false
    }

Writes job_summary.json to <output_root>/<job_id>/ and prints it to stdout.
Exits 0 on success, 1 on error (prints error JSON to stdout).
"""

from __future__ import annotations

# ── Environment guards (must be set before ANY heavy import) ──────────────────
# These prevent matplotlib font-scan hangs and OpenBLAS thread-pool deadlocks
# that occur on first run in production containers.
import os as _os
_os.environ.setdefault("MPLBACKEND", "Agg")
_os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl_cache")
_os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
_os.environ.setdefault("MKL_NUM_THREADS", "1")
_os.environ.setdefault("OMP_NUM_THREADS", "1")
_os.makedirs("/tmp/mpl_cache", exist_ok=True)
# ─────────────────────────────────────────────────────────────────────────────

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: run_job.py <config_json_path>"}))
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(json.dumps({"error": f"Config file not found: {config_path}"}))
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))

    job_id: str = config["job_id"]
    upload_paths = [Path(p) for p in config["upload_paths"]]
    output_root = Path(config["output_root"])

    import matplotlib
    matplotlib.use("Agg")

    from rvce_pipeline import run_job, APP_OUTPUT

    APP_OUTPUT.__class__.__truediv__ = Path.__truediv__
    import rvce_pipeline as _rp
    _rp.APP_OUTPUT = output_root

    try:
        summary = run_job(
            upload_paths=upload_paths,
            job_id=job_id,
            dpi=config.get("dpi", 300),
            style=config.get("style", "reference"),
            technique=config.get("technique", "auto"),
            material_query=config.get("material_query"),
            mp_api_key=config.get("mp_api_key"),
            nvidia_api_key=config.get("nvidia_api_key"),
            enable_ai=config.get("enable_ai", False),
            palette=config.get("palette", "turbo"),
            plot_titles=config.get("plot_titles"),
        )
        print(json.dumps({"ok": True, "summary": summary}))
        sys.exit(0)
    except Exception as exc:
        import traceback
        print(json.dumps({"ok": False, "error": str(exc), "traceback": traceback.format_exc()}))
        sys.exit(1)


if __name__ == "__main__":
    main()
