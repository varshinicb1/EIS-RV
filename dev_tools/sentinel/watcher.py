#!/usr/bin/env python3
"""
RĀMAN Sentinel — Research Intelligence Scanner
================================================
Scans arXiv and GitHub for SOTA research in electrochemistry,
PINNs, and differentiable physics. Stores results in SQLite
and generates a self-contained HTML dashboard.

Usage:
    python3 watcher.py              # Run once (scan + generate dashboard)
    python3 watcher.py --serve      # Start local dashboard server on port 8099
"""

import os
import sys
import json
import sqlite3
import signal
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "sota_intel.db"
DASHBOARD_PATH = BASE_DIR / "DASHBOARD.html"
LOG_PATH = BASE_DIR / "autonomous.log"

# Search topics relevant to RĀMAN Studio
ARXIV_QUERIES = [
    'all:"physics-informed neural network" AND all:"electrochemistry"',
    'all:"differentiable" AND all:"PDE solver"',
    'all:"foundation model" AND all:"partial differential equation"',
    'all:"neural operator" AND all:"battery"',
]

GITHUB_QUERIES = [
    "pinn electrochemistry",
    "differentiable physics simulation",
    "neural pde solver",
    "battery digital twin",
]


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS intel (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT,
        url TEXT,
        category TEXT,
        published TEXT,
        found_at TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()


def fetch_arxiv(query, max_results=5):
    """Fetch papers from arXiv Atom API."""
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    url = f"http://export.arxiv.org/api/query?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RAMAN-Sentinel/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = []
        for entry in root.findall("atom:entry", ns):
            pub = entry.find("atom:published", ns)
            pub_date = pub.text if pub is not None else ""
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            link_el = entry.find("atom:link", ns)
            id_el = entry.find("atom:id", ns)
            entries.append({
                "id": id_el.text.strip() if id_el is not None else "",
                "source": "arXiv",
                "title": title_el.text.strip().replace("\n", " ") if title_el is not None else "",
                "summary": (summary_el.text.strip().replace("\n", " ")[:500] if summary_el is not None else ""),
                "url": link_el.attrib.get("href", "") if link_el is not None else "",
                "category": "Research",
                "published": pub_date[:10],
                "found_at": datetime.now().isoformat(),
            })
        return entries
    except Exception as e:
        log(f"  arXiv fetch failed for '{query[:40]}...': {e}")
        return []


def fetch_github(query, max_results=5):
    """Fetch repos from GitHub Search API (no auth needed for basic searches)."""
    q = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page={max_results}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "RAMAN-Sentinel/1.0",
            "Accept": "application/vnd.github.v3+json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        entries = []
        for repo in data.get("items", []):
            entries.append({
                "id": f"gh-{repo['id']}",
                "source": "GitHub",
                "title": repo["full_name"],
                "summary": (repo.get("description") or "No description")[:500],
                "url": repo["html_url"],
                "category": "Repository",
                "published": (repo.get("updated_at") or "")[:10],
                "found_at": datetime.now().isoformat(),
            })
        return entries
    except Exception as e:
        log(f"  GitHub fetch failed for '{query}': {e}")
        return []


def save_entries(entries):
    """Save new entries to SQLite; skip duplicates."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    new = 0
    for e in entries:
        try:
            c.execute(
                "INSERT INTO intel (id, source, title, summary, url, category, published, found_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (e["id"], e["source"], e["title"], e["summary"], e["url"], e["category"], e["published"], e["found_at"]),
            )
            new += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return new


def get_all_intel():
    """Read all intel from DB, newest first."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM intel ORDER BY found_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    """Get basic stats from DB."""
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM intel").fetchone()[0]
    arxiv = conn.execute("SELECT COUNT(*) FROM intel WHERE source='arXiv'").fetchone()[0]
    github = conn.execute("SELECT COUNT(*) FROM intel WHERE source='GitHub'").fetchone()[0]
    conn.close()
    return {"total": total, "arxiv": arxiv, "github": github}


def run_scan():
    """Execute one full scan cycle."""
    log("Scan started")
    all_entries = []
    for q in ARXIV_QUERIES:
        entries = fetch_arxiv(q)
        all_entries.extend(entries)
        log(f"  arXiv '{q[:40]}...': {len(entries)} results")

    for q in GITHUB_QUERIES:
        entries = fetch_github(q)
        all_entries.extend(entries)
        log(f"  GitHub '{q}': {len(entries)} results")

    new = save_entries(all_entries)
    stats = get_stats()
    log(f"Scan complete: {new} new, {stats['total']} total ({stats['arxiv']} papers, {stats['github']} repos)")
    return stats


def generate_dashboard():
    """Generate a self-contained HTML dashboard from the database."""
    intel = get_all_intel()
    stats = get_stats()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build intel cards HTML
    cards_html = ""
    for item in intel[:30]:
        src_color = "#3b82f6" if item["source"] == "arXiv" else "#a855f7"
        src_bg = "rgba(59,130,246,0.1)" if item["source"] == "arXiv" else "rgba(168,85,247,0.1)"
        cards_html += f"""
        <div class="card">
            <div class="card-header">
                <span class="badge" style="background:{src_bg};color:{src_color}">{item['source']}</span>
                <span class="date">{item['published']}</span>
            </div>
            <a href="{item['url']}" target="_blank" class="card-title">{item['title']}</a>
            <p class="card-summary">{item['summary'][:200]}{'...' if len(item['summary']) > 200 else ''}</p>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RĀMAN Sentinel</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #09090b; color: #a1a1aa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid #27272a; }}
h1 {{ color: #fafafa; font-size: 20px; font-weight: 700; }}
h1 span {{ color: #52525b; font-weight: 400; font-size: 12px; margin-left: 8px; }}
.meta {{ font-size: 11px; color: #52525b; font-family: 'SF Mono', 'Fira Code', monospace; }}
.stats {{ display: flex; gap: 24px; margin-bottom: 32px; }}
.stat {{ background: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 16px 20px; flex: 1; }}
.stat-value {{ color: #fafafa; font-size: 24px; font-weight: 700; margin-bottom: 4px; }}
.stat-label {{ font-size: 11px; color: #71717a; text-transform: uppercase; letter-spacing: 0.05em; }}
.controls {{ display: flex; gap: 8px; margin-bottom: 32px; }}
.btn {{ padding: 8px 16px; border-radius: 6px; border: 1px solid #27272a; background: #18181b; color: #fafafa; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s; }}
.btn:hover {{ background: #27272a; }}
.btn-primary {{ background: #fafafa; color: #09090b; border-color: #fafafa; }}
.btn-primary:hover {{ background: #e4e4e7; }}
.btn-danger {{ color: #ef4444; border-color: #7f1d1d; }}
.btn-danger:hover {{ background: #7f1d1d; }}
h2 {{ color: #fafafa; font-size: 14px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
h2::before {{ content: ''; width: 6px; height: 6px; background: #3b82f6; border-radius: 50%; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.card {{ background: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 16px; transition: border-color 0.15s; }}
.card:hover {{ border-color: #3f3f46; }}
.card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
.badge {{ font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.05em; }}
.date {{ font-size: 10px; color: #52525b; font-family: monospace; }}
.card-title {{ color: #fafafa; font-size: 13px; font-weight: 600; text-decoration: none; display: block; margin-bottom: 6px; line-height: 1.4; }}
.card-title:hover {{ color: #60a5fa; }}
.card-summary {{ font-size: 12px; color: #71717a; line-height: 1.5; }}
.log {{ background: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 16px; margin-top: 32px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #52525b; white-space: pre-wrap; }}
@media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} .stats {{ flex-direction: column; }} }}
</style>
</head>
<body>
<div class="container">
    <header>
        <h1>RĀMAN Sentinel<span>v2.0</span></h1>
        <div class="meta">Last sync: {now}</div>
    </header>

    <div class="stats">
        <div class="stat"><div class="stat-value">{stats['total']}</div><div class="stat-label">Total Intel</div></div>
        <div class="stat"><div class="stat-value">{stats['arxiv']}</div><div class="stat-label">Papers</div></div>
        <div class="stat"><div class="stat-value">{stats['github']}</div><div class="stat-label">Repositories</div></div>
    </div>

    <div class="controls">
        <button class="btn btn-primary" onclick="location.reload()">Refresh</button>
    </div>

    <h2>Intelligence Feed</h2>
    <div class="grid">{cards_html}
    </div>

    <div class="log" id="log">Loading log...</div>
</div>
<script>
fetch('autonomous.log').then(r=>r.text()).then(t=>{{
    document.getElementById('log').textContent = t.split('\\n').slice(-20).join('\\n');
}}).catch(()=>{{document.getElementById('log').textContent='Log file not accessible (open via local server).';}});
</script>
</body>
</html>"""

    DASHBOARD_PATH.write_text(html)
    log(f"Dashboard generated: {DASHBOARD_PATH}")


def serve_dashboard(port=8099):
    """Start a local HTTP server to serve the dashboard."""
    os.chdir(BASE_DIR)
    handler = SimpleHTTPRequestHandler
    httpd = HTTPServer(("0.0.0.0", port), handler)
    log(f"Dashboard server running at http://localhost:{port}/DASHBOARD.html")
    httpd.serve_forever()


if __name__ == "__main__":
    init_db()

    if "--serve" in sys.argv:
        # Run scan, generate dashboard, then serve
        run_scan()
        generate_dashboard()
        serve_dashboard()
    else:
        # Just scan and generate
        run_scan()
        generate_dashboard()
