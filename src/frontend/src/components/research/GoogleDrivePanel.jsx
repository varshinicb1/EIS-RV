import React, { useState, useEffect, useCallback } from 'react';

const API = 'http://127.0.0.1:8000';

const S = {
  root: { display: 'grid', gridTemplateColumns: '300px 1fr', gap: 12, height: '100%', overflow: 'hidden' },
  card: { background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius)', padding: 16 },
  h2: { fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 },
  h3: { fontSize: 11.5, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' },
  btn: (v) => ({ padding: '7px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid', cursor: 'pointer', fontSize: 12, fontWeight: 500, transition: 'all 0.15s', ...(v === 'primary' ? { background: 'var(--accent)', borderColor: 'var(--accent)', color: '#fff' } : v === 'danger' ? { background: 'transparent', borderColor: 'var(--color-error)', color: 'var(--color-error)' } : { background: 'transparent', borderColor: 'var(--border-secondary)', color: 'var(--text-secondary)' }) }),
  badge: (c) => ({ display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 99, fontSize: 10.5, fontWeight: 500, background: c === 'green' ? 'rgba(34,197,94,0.12)' : c === 'blue' ? 'rgba(59,130,246,0.12)' : c === 'amber' ? 'rgba(245,158,11,0.12)' : 'var(--bg-tertiary)', color: c === 'green' ? 'var(--color-success)' : c === 'blue' ? '#60a5fa' : c === 'amber' ? '#fbbf24' : 'var(--text-tertiary)' }),
  dot: (ok) => ({ width: 8, height: 8, borderRadius: '50%', background: ok ? 'var(--color-success)' : 'var(--color-error)', flexShrink: 0 }),
  row: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' },
  label: { fontSize: 11, color: 'var(--text-tertiary)', minWidth: 110 },
  value: { fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', flex: 1, wordBreak: 'break-all' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 11.5 },
  th: { textAlign: 'left', padding: '6px 8px', color: 'var(--text-tertiary)', fontSize: 10.5, fontWeight: 500, borderBottom: '1px solid var(--border-primary)', whiteSpace: 'nowrap' },
  td: { padding: '5px 8px', borderBottom: '1px solid var(--border-primary)', color: 'var(--text-secondary)', verticalAlign: 'top' },
  tab: (a) => ({ padding: '6px 14px', borderRadius: 'var(--radius-sm)', border: 'none', background: a ? 'var(--accent-muted)' : 'transparent', color: a ? 'var(--accent)' : 'var(--text-tertiary)', cursor: 'pointer', fontSize: 12, fontWeight: a ? 500 : 400, borderBottom: a ? '2px solid var(--accent)' : '2px solid transparent' }),
  scrollable: { overflowY: 'auto', flex: 1 },
  warn: { background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 'var(--radius-sm)', padding: '10px 14px', fontSize: 11.5, color: '#fbbf24', marginBottom: 12 },
  info: { background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 'var(--radius-sm)', padding: '10px 14px', fontSize: 11.5, color: '#93c5fd', marginBottom: 10 },
  stat: { textAlign: 'center', padding: '10px 6px', flex: 1 },
  statNum: { fontSize: 22, fontWeight: 700, color: 'var(--accent)', lineHeight: 1 },
  statLabel: { fontSize: 10, color: 'var(--text-tertiary)', marginTop: 3 },
};

const TABS = ['Overview', 'Files', 'Papers', 'Literature Review'];

export default function GoogleDrivePanel() {
  const [tab, setTab] = useState('Overview');
  const [status, setStatus] = useState(null);
  const [files, setFiles] = useState([]);
  const [papers, setPapers] = useState([]);
  const [paperTotal, setPaperTotal] = useState(0);
  const [review, setReview] = useState(null);
  const [reviewTab, setReviewTab] = useState('summary');
  const [loading, setLoading] = useState({});
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState(null);

  const setLoad = (k, v) => setLoading(prev => ({ ...prev, [k]: v }));

  const loadStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/v2/drive/status`);
      const d = await r.json();
      setStatus(d);
      setSyncing(d?.sync?.running || false);
    } catch (e) { setError('Cannot reach backend'); }
  }, []);

  const loadFiles = useCallback(async () => {
    setLoad('files', true);
    try {
      const r = await fetch(`${API}/api/v2/drive/files`);
      const d = await r.json();
      setFiles(d.files || []);
    } catch { setFiles([]); }
    setLoad('files', false);
  }, []);

  const loadPapers = useCallback(async () => {
    setLoad('papers', true);
    try {
      const r = await fetch(`${API}/api/v2/drive/papers?limit=200`);
      const d = await r.json();
      setPapers(d.papers || []);
      setPaperTotal(d.total || 0);
    } catch { setPapers([]); }
    setLoad('papers', false);
  }, []);

  const loadReview = useCallback(async () => {
    setLoad('review', true);
    try {
      const r = await fetch(`${API}/api/v2/drive/review`);
      const d = await r.json();
      setReview(d);
    } catch (e) { setError('Review generation failed: ' + e.message); }
    setLoad('review', false);
  }, []);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(() => {
      if (syncing) loadStatus();
    }, 3000);
    return () => clearInterval(interval);
  }, [syncing]);

  useEffect(() => {
    if (tab === 'Files' && !files.length) loadFiles();
    if (tab === 'Papers' && !papers.length) loadPapers();
    if (tab === 'Literature Review' && !review) loadReview();
  }, [tab]);

  const triggerSync = async (force = false) => {
    setSyncing(true);
    setError(null);
    try {
      await fetch(`${API}/api/v2/drive/sync?force=${force}`, { method: 'POST' });
      setTimeout(loadStatus, 1000);
    } catch (e) { setError(e.message); setSyncing(false); }
  };

  const exportReview = async () => {
    const r = await fetch(`${API}/api/v2/drive/review/export`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url;
    a.download = 'ec_sensor_literature_review.json'; a.click();
  };

  const connected = status?.connected;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 0 }}>
      {/* Header */}
      <div style={{ padding: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0, borderBottom: '1px solid var(--border-primary)', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
          <DriveIcon />
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>Google Drive Integration</div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Bidirectional sync · EC Sensor Literature Review</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={S.btn()} onClick={() => { loadStatus(); if (tab === 'Files') loadFiles(); if (tab === 'Papers') loadPapers(); }}>↻ Refresh</button>
          <button style={{ ...S.btn('primary'), opacity: syncing ? 0.6 : 1 }} disabled={syncing} onClick={() => triggerSync(false)}>
            {syncing ? '⟳ Syncing…' : '⬆ Sync Drive'}
          </button>
        </div>
      </div>

      {error && <div style={{ ...S.warn, marginBottom: 10 }}>⚠ {error}</div>}

      {/* Share reminder */}
      {status?.share_reminder && !connected && (
        <div style={S.warn}>
          ⚠ Drive folder not accessible. Make sure you shared the folder with:<br />
          <strong style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{status.service_account_email}</strong>
        </div>
      )}
      {status?.service_account_email && connected && (
        <div style={{ ...S.info, marginBottom: 10 }}>
          ✓ Connected as <strong style={{ fontFamily: 'var(--font-mono)' }}>{status.service_account_email}</strong>
          {status?.folder_info?.name && <> · Folder: <strong>{status.folder_info.name}</strong></>}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 12, flexShrink: 0, borderBottom: '1px solid var(--border-primary)' }}>
        {TABS.map(t => <button key={t} style={S.tab(tab === t)} onClick={() => setTab(t)}>{t}</button>)}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {tab === 'Overview' && <OverviewTab status={status} syncing={syncing} onSync={triggerSync} onForceSync={() => triggerSync(true)} />}
        {tab === 'Files' && <FilesTab files={files} loading={loading.files} onRefresh={loadFiles} />}
        {tab === 'Papers' && <PapersTab papers={papers} total={paperTotal} loading={loading.papers} onRefresh={loadPapers} />}
        {tab === 'Literature Review' && <ReviewTab review={review} loading={loading.review} reviewTab={reviewTab} setReviewTab={setReviewTab} onRefresh={loadReview} onExport={exportReview} />}
      </div>
    </div>
  );
}

// ── Overview Tab ──────────────────────────────────────────────────────────
function OverviewTab({ status, syncing, onSync, onForceSync }) {
  if (!status) return <div style={{ color: 'var(--text-tertiary)', fontSize: 12, padding: 16 }}>Loading status…</div>;
  const s = status.sync;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      {/* Connection status */}
      <div style={S.card}>
        <div style={S.h2}><span style={S.dot(status.connected)} /> Connection</div>
        <div style={S.row}><span style={S.label}>Status</span><span style={{ ...S.badge(status.connected ? 'green' : 'danger') }}>{status.connected ? 'Connected' : 'Disconnected'}</span></div>
        <div style={S.row}><span style={S.label}>Service account</span><span style={{ ...S.value, fontSize: 10.5 }}>{status.service_account_email || '—'}</span></div>
        <div style={S.row}><span style={S.label}>Folder name</span><span style={S.value}>{status.folder_info?.name || '—'}</span></div>
        <div style={S.row}><span style={S.label}>Files processed</span><span style={S.value}>{status.ledger_count}</span></div>
        {!status.connected && (
          <div style={{ ...S.warn, marginTop: 8, fontSize: 11 }}>
            Share your Drive folder with:<br />
            <code style={{ display: 'block', marginTop: 4 }}>{status.service_account_email}</code>
          </div>
        )}
      </div>

      {/* Sync status */}
      <div style={S.card}>
        <div style={S.h2}>⟳ Sync Status</div>
        <div style={S.row}><span style={S.label}>State</span><span style={S.badge(syncing ? 'amber' : 'green')}>{syncing ? 'Running' : 'Idle'}</span></div>
        {s?.progress && <div style={S.row}><span style={S.label}>Progress</span><span style={S.value}>{s.progress}</span></div>}
        {s?.last_run && <div style={S.row}><span style={S.label}>Last run</span><span style={S.value}>{new Date(s.last_run * 1000).toLocaleString()}</span></div>}
        {s?.last_error && <div style={{ ...S.warn, marginTop: 6, fontSize: 11 }}>Error: {s.last_error}</div>}
        {s?.last_stats && (
          <div style={{ display: 'flex', gap: 4, marginTop: 10 }}>
            {[['New files', s.last_stats.new_files], ['Processed', s.last_stats.processed], ['Materials', s.last_stats.materials_extracted]].map(([l, v]) => (
              <div key={l} style={{ ...S.stat, background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)' }}>
                <div style={S.statNum}>{v ?? 0}</div>
                <div style={S.statLabel}>{l}</div>
              </div>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <button style={{ ...S.btn('primary'), opacity: syncing ? 0.6 : 1 }} disabled={syncing} onClick={onSync}>
            {syncing ? '⟳ Syncing…' : 'Sync New Files'}
          </button>
          <button style={{ ...S.btn(), opacity: syncing ? 0.6 : 1 }} disabled={syncing} onClick={onForceSync} title="Re-process all Drive files">
            Force Re-sync
          </button>
        </div>
      </div>

      {/* How it works */}
      <div style={{ ...S.card, gridColumn: '1 / -1' }}>
        <div style={S.h2}>How it works</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {[
            ['1. Scan', 'Drive folder scanned recursively. All PDFs, Docs, and text files found.'],
            ['2. Extract', 'Full text extracted via pdfminer. Title, authors, DOI, year auto-inferred.'],
            ['3. Parse', 'EC sensor data extracted: LOD, sensitivity, CV/DPV/EIS params, analytes, food samples.'],
            ['4. Review', 'Consolidated literature review generated. LOD tables, material formulas, trends.'],
          ].map(([title, desc]) => (
            <div key={title} style={{ background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)', padding: '10px 12px' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', marginBottom: 4 }}>{title}</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Files Tab ─────────────────────────────────────────────────────────────
function FilesTab({ files, loading, onRefresh }) {
  const [search, setSearch] = useState('');
  const filtered = files.filter(f => !search || f.name.toLowerCase().includes(search.toLowerCase()));
  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, alignItems: 'center' }}>
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Filter files…"
          style={{ flex: 1, padding: '6px 10px', background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontSize: 12 }} />
        <button style={S.btn()} onClick={onRefresh}>Refresh</button>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{filtered.length} files</span>
      </div>
      {loading ? <div style={{ color: 'var(--text-tertiary)', fontSize: 12, padding: 16 }}>Loading…</div> : (
        <table style={S.table}>
          <thead><tr>
            {['Name', 'Type', 'Modified', 'Status'].map(h => <th key={h} style={S.th}>{h}</th>)}
          </tr></thead>
          <tbody>
            {filtered.map(f => (
              <tr key={f.id}>
                <td style={S.td}>
                  <a href={f.webViewLink} target="_blank" rel="noreferrer"
                    style={{ color: 'var(--accent)', textDecoration: 'none', fontSize: 11.5 }}>
                    {f.name}
                  </a>
                </td>
                <td style={S.td}><span style={S.badge('blue')}>{mimeShort(f.mimeType)}</span></td>
                <td style={S.td}>{f.modifiedTime ? new Date(f.modifiedTime).toLocaleDateString() : '—'}</td>
                <td style={S.td}><span style={S.badge(f.processed ? 'green' : 'amber')}>{f.processed ? '✓ Processed' : 'Pending'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Papers Tab ────────────────────────────────────────────────────────────
function PapersTab({ papers, total, loading, onRefresh }) {
  const [search, setSearch] = useState('');
  const filtered = papers.filter(p => !search ||
    (p.title || '').toLowerCase().includes(search.toLowerCase()) ||
    (p.journal || '').toLowerCase().includes(search.toLowerCase()));
  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, alignItems: 'center' }}>
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search papers…"
          style={{ flex: 1, padding: '6px 10px', background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontSize: 12 }} />
        <button style={S.btn()} onClick={onRefresh}>Refresh</button>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{total} total</span>
      </div>
      {loading ? <div style={{ color: 'var(--text-tertiary)', fontSize: 12, padding: 16 }}>Loading…</div> : (
        <table style={S.table}>
          <thead><tr>
            {['Title', 'Year', 'Status', 'Added'].map(h => <th key={h} style={S.th}>{h}</th>)}
          </tr></thead>
          <tbody>
            {filtered.map(p => (
              <tr key={p.id}>
                <td style={{ ...S.td, maxWidth: 400 }}>
                  {p.url
                    ? <a href={p.url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none' }}>{p.title}</a>
                    : <span style={{ color: 'var(--text-primary)' }}>{p.title}</span>}
                  {p.authors?.length > 0 && <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>{p.authors.slice(0, 3).join(', ')}</div>}
                </td>
                <td style={S.td}>{p.year || '—'}</td>
                <td style={S.td}><span style={S.badge(p.processed === 1 ? 'green' : p.processed === -1 ? 'danger' : 'amber')}>{p.processed === 1 ? '✓' : p.processed === -1 ? '✗ Error' : 'Pending'}</span></td>
                <td style={S.td}>{p.fetched_at ? new Date(p.fetched_at).toLocaleDateString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Literature Review Tab ─────────────────────────────────────────────────
const REVIEW_TABS = ['summary', 'materials', 'lod', 'techniques', 'food', 'interference', 'commercial', 'challenges'];

function ReviewTab({ review, loading, reviewTab, setReviewTab, onRefresh, onExport }) {
  if (loading) return <div style={{ color: 'var(--text-tertiary)', fontSize: 12, padding: 24, textAlign: 'center' }}>Generating literature review…</div>;
  if (!review) return (
    <div style={{ textAlign: 'center', padding: 40 }}>
      <div style={{ color: 'var(--text-tertiary)', fontSize: 13, marginBottom: 16 }}>No review generated yet. Sync Drive papers first.</div>
      <button style={S.btn('primary')} onClick={onRefresh}>Generate Review</button>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Stats row */}
      <div style={{ display: 'flex', gap: 8 }}>
        {[
          ['Total papers', review.total_papers],
          ['From Drive', review.drive_papers],
          ['From APIs', review.api_papers],
          ['With LOD data', review.lod_table?.length],
          ['With sensitivity', review.sensitivity_table?.length],
        ].map(([l, v]) => (
          <div key={l} style={{ ...S.stat, background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)' }}>
            <div style={S.statNum}>{v ?? 0}</div>
            <div style={S.statLabel}>{l}</div>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginLeft: 'auto' }}>
          <button style={S.btn()} onClick={onRefresh}>↻</button>
          <button style={S.btn('primary')} onClick={onExport}>⬇ Export JSON</button>
        </div>
      </div>

      {/* Sub-tabs */}
      <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap', borderBottom: '1px solid var(--border-primary)', paddingBottom: 2 }}>
        {REVIEW_TABS.map(t => (
          <button key={t} style={S.tab(reviewTab === t)} onClick={() => setReviewTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Sub-tab content */}
      <div style={{ overflowY: 'auto' }}>
        {reviewTab === 'summary' && <SummarySection review={review} />}
        {reviewTab === 'materials' && <MaterialsSection review={review} />}
        {reviewTab === 'lod' && <LodSection review={review} />}
        {reviewTab === 'techniques' && <TechniquesSection review={review} />}
        {reviewTab === 'food' && <FoodSection review={review} />}
        {reviewTab === 'interference' && <InterferenceSection review={review} />}
        {reviewTab === 'commercial' && <CommercialSection review={review} />}
        {reviewTab === 'challenges' && <ChallengesSection review={review} />}
      </div>
    </div>
  );
}

function SummarySection({ review }) {
  const top5analytes = Object.entries(review.analyte_counts || {}).slice(0, 5);
  const top5materials = Object.entries(review.material_counts || {}).slice(0, 5);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      <div style={S.card}>
        <div style={S.h3}>Top Analytes Detected</div>
        {top5analytes.map(([a, c]) => <BarRow key={a} label={a} value={c} max={top5analytes[0]?.[1] || 1} />)}
        {!top5analytes.length && <Empty />}
      </div>
      <div style={S.card}>
        <div style={S.h3}>Top Techniques</div>
        {Object.entries(review.technique_counts || {}).slice(0, 6).map(([t, c]) => (
          <BarRow key={t} label={t} value={c} max={Object.values(review.technique_counts)[0] || 1} />
        ))}
      </div>
      <div style={{ ...S.card, gridColumn: '1 / -1' }}>
        <div style={S.h3}>Scope Keywords</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {(review.scope_keywords || []).map(k => (
            <span key={k} style={{ ...S.badge('blue'), padding: '3px 10px', fontSize: 11 }}>{k}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function MaterialsSection({ review }) {
  const rows = review.material_formula_table || [];
  return (
    <div style={S.card}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={S.h3}>Nanomaterials — Name, Formula &amp; Occurrence</div>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{rows.length} materials</span>
      </div>
      <table style={S.table}>
        <thead><tr>
          {['Material', 'Formula', 'Papers'].map(h => <th key={h} style={S.th}>{h}</th>)}
        </tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td style={S.td}>{r.material}</td>
              <td style={{ ...S.td, fontFamily: 'var(--font-mono)', fontSize: 11 }}>{r.formula}</td>
              <td style={S.td}><span style={S.badge('blue')}>{r.count}</span></td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan={3} style={{ ...S.td, textAlign: 'center', color: 'var(--text-tertiary)' }}>Sync Drive papers to populate</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function LodSection({ review }) {
  const rows = review.lod_table || [];
  const sensitivity = review.sensitivity_table || [];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={S.card}>
        <div style={S.h3}>LOD / Sensitivity Summary ({rows.length} papers)</div>
        <table style={S.table}>
          <thead><tr>
            {['Title', 'Year', 'Analyte', 'LOD', 'Sensitivity', 'Linear Range', 'Materials'].map(h => <th key={h} style={S.th}>{h}</th>)}
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td style={{ ...S.td, maxWidth: 200, fontSize: 10.5 }}>{r.title}</td>
                <td style={S.td}>{r.year || '—'}</td>
                <td style={S.td}><span style={S.badge('blue')}>{r.analyte}</span></td>
                <td style={{ ...S.td, fontFamily: 'var(--font-mono)', color: 'var(--color-success)', fontSize: 11 }}>{r.lod || '—'}</td>
                <td style={{ ...S.td, fontFamily: 'var(--font-mono)', fontSize: 11 }}>{r.sensitivity || '—'}</td>
                <td style={{ ...S.td, fontFamily: 'var(--font-mono)', fontSize: 11 }}>{r.linear_range || '—'}</td>
                <td style={{ ...S.td, fontSize: 10.5 }}>{(r.materials || []).join(', ')}</td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={7} style={{ ...S.td, textAlign: 'center', color: 'var(--text-tertiary)' }}>No LOD data extracted yet</td></tr>}
          </tbody>
        </table>
      </div>
      {sensitivity.length > 0 && (
        <div style={S.card}>
          <div style={S.h3}>CV &amp; DPV Data</div>
          <table style={S.table}>
            <thead><tr>
              {['Title', 'Year', 'Analyte', 'Technique', 'Sensitivity', 'LOD'].map(h => <th key={h} style={S.th}>{h}</th>)}
            </tr></thead>
            <tbody>
              {sensitivity.map((r, i) => (
                <tr key={i}>
                  <td style={{ ...S.td, maxWidth: 200, fontSize: 10.5 }}>{r.title}</td>
                  <td style={S.td}>{r.year || '—'}</td>
                  <td style={S.td}>{r.analyte}</td>
                  <td style={S.td}><span style={S.badge('amber')}>{r.technique}</span></td>
                  <td style={{ ...S.td, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent)' }}>{r.sensitivity}</td>
                  <td style={{ ...S.td, fontFamily: 'var(--font-mono)', fontSize: 11 }}>{r.lod || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TechniquesSection({ review }) {
  const entries = Object.entries(review.technique_counts || {});
  const total = entries.reduce((s, [, v]) => s + v, 0);
  return (
    <div style={S.card}>
      <div style={S.h3}>Electrochemical Techniques Used</div>
      {entries.map(([t, c]) => (
        <div key={t} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{t}</span>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{c} papers ({Math.round(c / total * 100)}%)</span>
          </div>
          <div style={{ height: 6, background: 'var(--bg-tertiary)', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${c / total * 100}%`, background: 'var(--accent)', borderRadius: 3 }} />
          </div>
        </div>
      ))}
      {!entries.length && <Empty />}
    </div>
  );
}

function FoodSection({ review }) {
  const entries = Object.entries(review.food_sample_counts || {});
  return (
    <div style={S.card}>
      <div style={S.h3}>Food Sample Types Analysed ({entries.length} types)</div>
      {entries.length ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
          {entries.sort((a, b) => b[1] - a[1]).map(([f, c]) => (
            <div key={f} style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)', padding: '6px 12px', fontSize: 12 }}>
              <span style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{f}</span>
              <span style={{ color: 'var(--text-tertiary)', marginLeft: 6, fontSize: 11 }}>×{c}</span>
            </div>
          ))}
        </div>
      ) : <Empty msg="No food sample mentions found yet" />}
    </div>
  );
}

function InterferenceSection({ review }) {
  const entries = Object.entries(review.interference_mentions || {}).sort((a, b) => b[1] - a[1]);
  return (
    <div style={S.card}>
      <div style={S.h3}>Interferents &amp; Selectivity Studies</div>
      {entries.length ? (
        <table style={S.table}>
          <thead><tr>
            <th style={S.th}>Interferent</th><th style={S.th}>Mentioned in (papers)</th>
          </tr></thead>
          <tbody>
            {entries.map(([k, v]) => (
              <tr key={k}>
                <td style={S.td}>{k}</td>
                <td style={S.td}><span style={S.badge('blue')}>{v}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <Empty msg="No interference data extracted yet" />}
    </div>
  );
}

function CommercialSection({ review }) {
  const score = Math.round((review.commercial_score_avg || 0) * 100);
  const papers = (review.papers || []).filter(p => p.commercial_keywords?.length > 0);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={S.card}>
        <div style={S.h3}>Commercial Feasibility Score</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
          <div style={{ fontSize: 42, fontWeight: 700, color: score > 50 ? 'var(--color-success)' : score > 25 ? '#fbbf24' : 'var(--color-error)' }}>{score}%</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {score}% of papers mention commercial/POC keywords.<br />
            Higher scores → stronger commercial translation signal.
          </div>
        </div>
        <div style={{ height: 8, background: 'var(--bg-tertiary)', borderRadius: 4, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${score}%`, background: score > 50 ? 'var(--color-success)' : '#fbbf24', borderRadius: 4 }} />
        </div>
      </div>
      <div style={S.card}>
        <div style={S.h3}>Papers with POC / Commercial Mentions</div>
        {papers.slice(0, 30).map(p => (
          <div key={p.paper_id} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: '1px solid var(--border-primary)' }}>
            <div style={{ fontSize: 12, color: 'var(--text-primary)', marginBottom: 4 }}>{p.title}</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {p.commercial_keywords.map(k => <span key={k} style={S.badge('green')}>{k}</span>)}
            </div>
          </div>
        ))}
        {!papers.length && <Empty msg="No commercial mentions extracted yet" />}
      </div>
    </div>
  );
}

function ChallengesSection({ review }) {
  const challenges = Object.entries(review.challenge_counts || {}).sort((a, b) => b[1] - a[1]);
  const opportunities = [
    'Wearable & flexible sensors for continuous monitoring',
    'Multi-analyte detection arrays (multiplexing)',
    'Integration with IoT and smartphone readout',
    'AI-guided material discovery for ultra-low LOD',
    'Paper/textile-based sensors for field deployment',
    'Green synthesis of electrode nanomaterials',
    'Standardization of sensor fabrication protocols',
    'Clinical validation for regulatory approval',
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      <div style={S.card}>
        <div style={S.h3}>Challenges (from literature)</div>
        {challenges.map(([ch, c]) => (
          <div key={ch} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'var(--text-primary)', textTransform: 'capitalize' }}>{ch.replace(/-/g, ' ')}</span>
            <span style={S.badge('amber')}>{c} papers</span>
          </div>
        ))}
        {!challenges.length && <Empty />}
      </div>
      <div style={S.card}>
        <div style={S.h3}>Scope &amp; Opportunities</div>
        {opportunities.map((o, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'flex-start' }}>
            <span style={{ color: 'var(--accent)', fontWeight: 700, fontSize: 13, lineHeight: 1.4, flexShrink: 0 }}>→</span>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{o}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────
function BarRow({ label, value, max }) {
  return (
    <div style={{ marginBottom: 7 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
        <span style={{ fontSize: 11.5, color: 'var(--text-primary)', textTransform: 'capitalize' }}>{label}</span>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{value}</span>
      </div>
      <div style={{ height: 4, background: 'var(--bg-tertiary)', borderRadius: 2 }}>
        <div style={{ height: '100%', width: `${value / max * 100}%`, background: 'var(--accent)', borderRadius: 2 }} />
      </div>
    </div>
  );
}

function Empty({ msg = 'No data yet — sync Drive papers first' }) {
  return <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', textAlign: 'center', padding: '20px 0' }}>{msg}</div>;
}

function mimeShort(mime) {
  if (mime?.includes('pdf')) return 'PDF';
  if (mime?.includes('word')) return 'DOCX';
  if (mime?.includes('google-apps.document')) return 'GDoc';
  if (mime?.includes('text')) return 'TXT';
  return 'File';
}

function DriveIcon() {
  return (
    <svg width="22" height="18" viewBox="0 0 87.3 78" xmlns="http://www.w3.org/2000/svg">
      <path d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8h-27.5c0 1.55.4 3.1 1.2 4.5z" fill="#0066da"/>
      <path d="m43.65 25-13.75-23.8c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44a9.06 9.06 0 0 0 -1.2 4.5h27.5z" fill="#00ac47"/>
      <path d="m73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5h-27.502l5.852 11.5z" fill="#ea4335"/>
      <path d="m43.65 25 13.75-23.8c-1.35-.8-2.9-1.2-4.5-1.2h-18.5c-1.6 0-3.15.45-4.5 1.2z" fill="#00832d"/>
      <path d="m59.8 53h-32.3l-13.75 23.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684fc"/>
      <path d="m73.4 26.5-12.7-22c-.8-1.4-1.95-2.5-3.3-3.3l-13.75 23.8 16.15 27h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#ffba00"/>
    </svg>
  );
}
