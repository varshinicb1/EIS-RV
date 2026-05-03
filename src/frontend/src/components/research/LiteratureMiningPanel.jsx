import React, { useState, useEffect } from 'react';

const API = 'http://127.0.0.1:8000';

export default function LiteratureMiningPanel() {
  const [stats, setStats] = useState(null);
  const [papers, setPapers] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [methods, setMethods] = useState([]);
  const [apps, setApps] = useState([]);
  const [config, setConfig] = useState(null);
  const [selectedPaper, setSelectedPaper] = useState(null);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [filterMat, setFilterMat] = useState('');
  const [filterApp, setFilterApp] = useState('');
  const [filterMethod, setFilterMethod] = useState('');
  const [tab, setTab] = useState('papers');

  const load = () => {
    fetch(`${API}/api/v2/pipeline/stats`).then(r => r.json()).then(setStats).catch(() => {});
    fetch(`${API}/api/v2/pipeline/config`).then(r => r.json()).then(setConfig).catch(() => {});
    fetch(`${API}/api/v2/pipeline/materials`).then(r => r.json()).then(setMaterials).catch(() => setMaterials([]));
    fetch(`${API}/api/v2/pipeline/methods`).then(r => r.json()).then(setMethods).catch(() => setMethods([]));
    fetch(`${API}/api/v2/pipeline/applications`).then(r => r.json()).then(setApps).catch(() => setApps([]));
  };

  const searchPapers = () => {
    const params = new URLSearchParams({ limit: '50' });
    if (filterMat) params.set('material', filterMat);
    if (filterApp) params.set('application', filterApp);
    if (filterMethod) params.set('method', filterMethod);
    fetch(`${API}/api/v2/pipeline/papers?${params}`).then(r => r.json()).then(d => setPapers(d.papers || [])).catch(() => setPapers([]));
  };

  useEffect(() => { load(); searchPapers(); }, []);
  useEffect(() => { searchPapers(); }, [filterMat, filterApp, filterMethod]);

  const runPipeline = async () => {
    setRunning(true); setRunResult(null);
    try {
      const r = await fetch(`${API}/api/v2/pipeline/run`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_per_query: 5 }),
      });
      const d = await r.json(); setRunResult(d); load(); searchPapers();
    } catch (e) { setRunResult({ status: 'error', error: e.message }); }
    setRunning(false);
  };

  const loadPaperDetail = async (id) => {
    try {
      const r = await fetch(`${API}/api/v2/pipeline/papers/${id}`);
      const d = await r.json(); setSelectedPaper(d);
    } catch { }
  };

  return (
    <div className="animate-in" style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 12, height: '100%' }}>
      {/* Left — Controls & Stats */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, overflow: 'auto' }}>
        {/* Pipeline Control */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 14 }}></span> Literature Mining
              </div>
              <div className="card-subtitle">arXiv · CrossRef · Semantic Scholar</div>
            </div>
          </div>
          <button className="btn btn-primary" onClick={runPipeline} disabled={running}
            style={{ width: '100%', marginTop: 8, background: running ? '#555' : 'linear-gradient(135deg, #4a9eff 0%, #7c3aed 100%)' }}>
            {running ? 'Mining Papers...' : 'Run Pipeline'}
          </button>
          {runResult && (
            <div className="animate-in" style={{ marginTop: 8, fontSize: 10, padding: 8, borderRadius: 6, background: runResult.status === 'completed' ? 'rgba(102,187,106,0.1)' : 'rgba(239,83,80,0.1)', border: `1px solid ${runResult.status === 'completed' ? '#66bb6a33' : '#ef535033'}` }}>
              <div style={{ fontWeight: 600, color: runResult.status === 'completed' ? '#66bb6a' : '#ef5350' }}>
                {runResult.status === 'completed' ? 'Pipeline Complete' : 'Error'}
              </div>
              {runResult.papers_fetched != null && (
                <div style={{ color: 'var(--text-secondary)', marginTop: 4 }}>
                  Fetched: {runResult.papers_fetched} · New: {runResult.papers_new} · Processed: {runResult.papers_processed}
                  <br />Materials: {runResult.materials_extracted} · EIS: {runResult.eis_records_extracted} · {runResult.elapsed_seconds}s
                </div>
              )}
              {runResult.error && <div style={{ color: '#ef5350' }}>{runResult.error}</div>}
            </div>
          )}
        </div>

        {/* Database Stats */}
        <div className="card">
          <div className="card-title" style={{ fontSize: 11, marginBottom: 8 }}>Database</div>
          {stats ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              <div className="stat-card"><div className="stat-value" style={{ fontSize: 16 }}>{stats.total_papers || 0}</div><div className="stat-label">Papers</div></div>
              <div className="stat-card"><div className="stat-value" style={{ fontSize: 16 }}>{stats.unique_materials || 0}</div><div className="stat-label">Materials</div></div>
              <div className="stat-card"><div className="stat-value" style={{ fontSize: 16 }}>{stats.total_eis_records || 0}</div><div className="stat-label">EIS Records</div></div>
              <div className="stat-card"><div className="stat-value" style={{ fontSize: 16 }}>{stats.total_synthesis || 0}</div><div className="stat-label">Synthesis</div></div>
            </div>
          ) : <div style={{ fontSize: 10, color: 'var(--text-disabled)' }}>Loading…</div>}
        </div>

        {/* Filters */}
        <div className="card">
          <div className="card-title" style={{ fontSize: 11, marginBottom: 8 }}>Filters</div>
          <div className="input-group">
            <span className="input-label">Material</span>
            <select className="input-field" value={filterMat} onChange={e => setFilterMat(e.target.value)}>
              <option value="">All materials</option>
              {materials.map(m => <option key={m.component} value={m.component}>{m.component} ({m.paper_count})</option>)}
            </select>
          </div>
          <div className="input-group">
            <span className="input-label">Application</span>
            <select className="input-field" value={filterApp} onChange={e => setFilterApp(e.target.value)}>
              <option value="">All applications</option>
              {apps.map(a => <option key={a.application} value={a.application}>{a.application} ({a.count})</option>)}
            </select>
          </div>
          <div className="input-group">
            <span className="input-label">Synthesis Method</span>
            <select className="input-field" value={filterMethod} onChange={e => setFilterMethod(e.target.value)}>
              <option value="">All methods</option>
              {methods.map(m => <option key={m.method} value={m.method}>{m.method} ({m.paper_count})</option>)}
            </select>
          </div>
        </div>

        {/* Search Queries */}
        {config && (
          <div className="card" style={{ flex: 1, overflow: 'auto' }}>
            <div className="card-title" style={{ fontSize: 11, marginBottom: 6 }}>Search Queries ({config.queries?.length || 0})</div>
            {(config.queries || []).map((q, i) => (
              <div key={i} style={{ fontSize: 9, color: 'var(--text-tertiary)', padding: '2px 0', fontFamily: 'var(--font-data)' }}>{q}</div>
            ))}
          </div>
        )}
      </div>

      {/* Right — Papers list / detail */}
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Tabs */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 10, flexShrink: 0 }}>
          {[['papers','Papers'],['materials','Extracted Materials'],['eis','EIS Data']].map(([k,l]) => (
            <button key={k} className={`btn btn-sm ${tab === k ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setTab(k)}>{l}</button>
          ))}
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)', alignSelf: 'center' }}>{papers.length} results</span>
        </div>

        <div style={{ display: 'flex', gap: 12, flex: 1, overflow: 'hidden' }}>
          {/* Papers table */}
          <div className="card" style={{ flex: 1, padding: 0, overflow: 'auto' }}>
            {tab === 'papers' && (
              <table className="data-table">
                <thead><tr><th style={{ width: '45%' }}>Title</th><th>Year</th><th>Source</th><th>Application</th><th>Materials</th></tr></thead>
                <tbody>
                  {papers.length === 0 ? (
                    <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-disabled)', padding: 40 }}>
                      {stats?.total_papers > 0 ? 'No papers match filters' : 'Run the pipeline to fetch papers from arXiv, CrossRef & Semantic Scholar'}
                    </td></tr>
                  ) : papers.map(p => (
                    <tr key={p.id} onClick={() => loadPaperDetail(p.id)} style={{ cursor: 'pointer',
                      background: selectedPaper?.id === p.id ? 'rgba(74,158,255,0.08)' : undefined }}>
                      <td style={{ fontSize: 11, maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.title}</td>
                      <td className="mono">{p.year || '—'}</td>
                      <td><span className={`tag tag-${p.source_api === 'arxiv' ? 'cyan' : p.source_api === 'crossref' ? 'amber' : 'violet'}`} style={{ fontSize: 9 }}>{p.source_api}</span></td>
                      <td>{p.application ? <span className="tag tag-emerald" style={{ fontSize: 9 }}>{p.application}</span> : '—'}</td>
                      <td style={{ fontSize: 10 }}>{(p.materials || []).map(m => m.component).join(', ') || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {tab === 'materials' && (
              <table className="data-table">
                <thead><tr><th>Material</th><th>Papers</th><th>Avg Confidence</th></tr></thead>
                <tbody>
                  {materials.map(m => (
                    <tr key={m.component}><td style={{ fontWeight: 500 }}>{m.component}</td>
                      <td className="mono">{m.paper_count}</td>
                      <td className="mono">{(m.avg_confidence || 0).toFixed(2)}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
            {tab === 'eis' && (
              <div style={{ padding: 20 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                  {papers.filter(p => p.eis_data?.length > 0).map(p => (
                    <div key={p.id} className="card" style={{ background: 'var(--bg-elevated)', cursor: 'pointer' }} onClick={() => loadPaperDetail(p.id)}>
                      <div style={{ fontSize: 11, fontWeight: 500, marginBottom: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.title}</div>
                      {p.eis_data.map((e, i) => (
                        <div key={i} style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                          {e.Rct_ohm != null && <span>Rct: {e.Rct_ohm}Ω </span>}
                          {e.capacitance_F_g != null && <span>Cap: {e.capacitance_F_g}F/g </span>}
                          {e.electrolyte && <span>· {e.electrolyte}</span>}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
                {papers.filter(p => p.eis_data?.length > 0).length === 0 && (
                  <div style={{ textAlign: 'center', color: 'var(--text-disabled)', padding: 40, fontSize: 12 }}>No EIS data extracted yet</div>
                )}
              </div>
            )}
          </div>

          {/* Paper detail */}
          {selectedPaper && (
            <div className="card animate-slide" style={{ width: 380, overflow: 'auto', flexShrink: 0 }}>
              <div className="card-header">
                <div className="card-title" style={{ fontSize: 12 }}>Paper Detail</div>
                <button className="btn btn-ghost btn-sm" onClick={() => setSelectedPaper(null)}>Close</button>
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: 8 }}>{selectedPaper.title}</div>
              {selectedPaper.doi && <div style={{ fontSize: 10, marginBottom: 4 }}><a href={`https://doi.org/${selectedPaper.doi}`} target="_blank" rel="noreferrer" style={{ color: '#4a9eff' }}>DOI: {selectedPaper.doi}</a></div>}
              {selectedPaper.url && <div style={{ fontSize: 10, marginBottom: 8 }}><a href={selectedPaper.url} target="_blank" rel="noreferrer" style={{ color: '#4a9eff' }}>Open ↗</a></div>}

              {selectedPaper.abstract && (
                <div style={{ marginBottom: 12 }}>
                  <div className="input-label" style={{ marginBottom: 4 }}>Abstract</div>
                  <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.7, maxHeight: 120, overflow: 'auto' }}>{selectedPaper.abstract}</div>
                </div>
              )}

              {/* Extracted Materials */}
              {selectedPaper.materials?.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div className="input-label" style={{ marginBottom: 4 }}>Extracted Materials</div>
                  {selectedPaper.materials.map((m, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, padding: '3px 0', borderBottom: '1px solid var(--border-default)' }}>
                      <span style={{ fontWeight: 500 }}>{m.component}</span>
                      <span style={{ color: 'var(--text-tertiary)' }}>
                        {m.ratio_value != null && `${m.ratio_value} ${m.ratio_unit || ''} · `}
                        conf: {(m.confidence || 0).toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Extracted Synthesis */}
              {selectedPaper.synthesis?.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div className="input-label" style={{ marginBottom: 4 }}>Synthesis Conditions</div>
                  {selectedPaper.synthesis.map((s, i) => (
                    <div key={i} style={{ fontSize: 10, color: 'var(--text-secondary)', padding: '3px 0' }}>
                      {s.method && <span className="tag tag-amber" style={{ fontSize: 9, marginRight: 4 }}>{s.method}</span>}
                      {s.temperature_C != null && <span>{s.temperature_C}°C · </span>}
                      {s.duration_hours != null && <span>{s.duration_hours}h · </span>}
                      {s.pH != null && <span>pH {s.pH}</span>}
                    </div>
                  ))}
                </div>
              )}

              {/* Extracted EIS */}
              {selectedPaper.eis_data?.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div className="input-label" style={{ marginBottom: 4 }}>EIS Parameters</div>
                  {selectedPaper.eis_data.map((e, i) => (
                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 10 }}>
                      {e.Rs_ohm != null && <div className="stat-card"><div className="stat-value" style={{ fontSize: 13 }}>{e.Rs_ohm}</div><div className="stat-label">Rs (Ω)</div></div>}
                      {e.Rct_ohm != null && <div className="stat-card"><div className="stat-value" style={{ fontSize: 13 }}>{e.Rct_ohm}</div><div className="stat-label">Rct (Ω)</div></div>}
                      {e.capacitance_F_g != null && <div className="stat-card"><div className="stat-value" style={{ fontSize: 13 }}>{e.capacitance_F_g}</div><div className="stat-label">Cap (F/g)</div></div>}
                      {e.electrolyte && <div className="stat-card"><div className="stat-value" style={{ fontSize: 11 }}>{e.electrolyte}</div><div className="stat-label">Electrolyte</div></div>}
                    </div>
                  ))}
                </div>
              )}

              <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                <button className="btn btn-primary btn-sm" style={{ flex: 1 }}
                  onClick={() => {
                    const eis = selectedPaper.eis_data?.[0];
                    if (eis) {
                      sessionStorage.setItem('RAMAN_EIS_IMPORT', JSON.stringify({
                        Rs: eis.Rs_ohm || 10,
                        Rct: eis.Rct_ohm || 100,
                        Cdl: eis.capacitance_F_g ? eis.capacitance_F_g * 1e-3 : 1e-5
                      }));
                      window.dispatchEvent(new CustomEvent('NAVIGATE_PANEL', { detail: 'eis' }));
                    } else {
                      window.dispatchEvent(new CustomEvent('NAVIGATE_PANEL', { detail: 'eis' }));
                    }
                  }}>
                  Use in EIS →
                </button>
                <button className="btn btn-secondary btn-sm" style={{ flex: 1 }}
                  onClick={() => {
                    try {
                      const raw = localStorage.getItem('raman-projects');
                      const projects = raw ? JSON.parse(raw) : [];
                      if (projects.length === 0) {
                        window.dispatchEvent(new CustomEvent('NAVIGATE_PANEL', { detail: 'workspace' }));
                        window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
                          detail: { kind: 'info', text: 'No project yet — create one in the Workspace panel, then come back to save papers.' }
                        }));
                        return;
                      }
                      const target = projects[0]; // active = first in list, matches WorkspacePanel ordering
                      target.saved_papers = target.saved_papers || [];
                      const already = target.saved_papers.some(p => p.id === selectedPaper.id);
                      if (!already) {
                        target.saved_papers.push({
                          id: selectedPaper.id,
                          title: selectedPaper.title,
                          doi: selectedPaper.doi,
                          year: selectedPaper.year,
                          saved_at: new Date().toISOString(),
                        });
                        target.modified = new Date().toISOString();
                        localStorage.setItem('raman-projects', JSON.stringify(projects));
                      }
                      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
                        detail: { kind: 'ok', text: already ? 'Already saved.' : `Saved to "${target.name}".` }
                      }));
                    } catch (err) {
                      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
                        detail: { kind: 'err', text: 'Could not save (storage error).' }
                      }));
                    }
                  }}>
                  Save to Project
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
