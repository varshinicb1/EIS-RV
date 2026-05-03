import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  FlaskConical, Upload, Database, BarChart3, Lightbulb, Plus, Trash2,
  RefreshCcw, AlertTriangle, CheckCircle2, Beaker, FileSpreadsheet, X,
} from 'lucide-react';

const API = 'http://127.0.0.1:8000';

// ───────────────────────────────────────────────────────────────────
// Tiny helpers
// ───────────────────────────────────────────────────────────────────

function fmt(v, digits = 3) {
  if (v == null || Number.isNaN(v)) return '—';
  if (typeof v !== 'number') return String(v);
  if (v === 0) return '0';
  const a = Math.abs(v);
  if (a >= 1e5 || a < 1e-3) return v.toExponential(2);
  return v.toFixed(digits);
}
function fmtPct(v) {
  if (v == null || Number.isNaN(v)) return '—';
  return `${v.toFixed(1)}%`;
}
function fmtCs(F) {
  if (F == null) return '—';
  if (F >= 1) return `${F.toFixed(2)} F`;
  if (F >= 1e-3) return `${(F * 1e3).toFixed(2)} mF`;
  if (F >= 1e-6) return `${(F * 1e6).toFixed(2)} µF`;
  return `${F.toExponential(2)} F`;
}

async function apiGet(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { detail = JSON.stringify(await res.json()); } catch {}
    throw new Error(detail);
  }
  return res.json();
}
async function apiPostJSON(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail?.message || data?.detail || `HTTP ${res.status}`);
  return data;
}
async function apiDelete(path) {
  const res = await fetch(`${API}${path}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ───────────────────────────────────────────────────────────────────
// Sub-component: Nyquist mini-plot (pure-SVG, no chart lib)
// ───────────────────────────────────────────────────────────────────

function NyquistPlot({ zReal, zImag, fitReal, fitImag, height = 220, accent = '#76b900' }) {
  if (!zReal?.length || !zImag?.length) return null;
  const negZi = zImag.map(v => -v);
  const xs = [...zReal, ...(fitReal || [])];
  const ys = [...negZi,  ...(fitImag || []).map(v => -v)];
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys, 0), yMax = Math.max(...ys);
  const W = 460, H = height, pad = { l: 56, r: 12, t: 14, b: 36 };
  const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
  const x = v => pad.l + (v - xMin) / (xMax - xMin || 1) * pw;
  const y = v => pad.t + ph - (v - yMin) / (yMax - yMin || 1) * ph;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: 520, height }}>
      <rect width={W} height={H} fill="#0d1117" />
      {/* gridlines */}
      {[0, 0.25, 0.5, 0.75, 1].map((t, i) => (
        <g key={i} stroke="#1e2733" strokeWidth={0.5}>
          <line x1={pad.l + pw * t} y1={pad.t} x2={pad.l + pw * t} y2={pad.t + ph} />
          <line x1={pad.l} y1={pad.t + ph * t} x2={pad.l + pw} y2={pad.t + ph * t} />
        </g>
      ))}
      {/* axes */}
      <line x1={pad.l} y1={pad.t} x2={pad.l} y2={pad.t + ph} stroke="#666" />
      <line x1={pad.l} y1={pad.t + ph} x2={pad.l + pw} y2={pad.t + ph} stroke="#666" />
      <text x={pad.l + pw / 2} y={H - 8} fontSize={10} fill="#aaa" textAnchor="middle">Z′ (Ω)</text>
      <text x={12} y={pad.t + ph / 2} fontSize={10} fill="#aaa" textAnchor="middle"
            transform={`rotate(-90 12 ${pad.t + ph / 2})`}>−Z″ (Ω)</text>
      <text x={pad.l - 6} y={pad.t + 4} fontSize={9} fill="#aaa" textAnchor="end">{fmt(yMax, 1)}</text>
      <text x={pad.l - 6} y={pad.t + ph} fontSize={9} fill="#aaa" textAnchor="end">{fmt(yMin, 1)}</text>
      <text x={pad.l} y={H - 22} fontSize={9} fill="#aaa" textAnchor="start">{fmt(xMin, 1)}</text>
      <text x={pad.l + pw} y={H - 22} fontSize={9} fill="#aaa" textAnchor="end">{fmt(xMax, 1)}</text>
      {/* data */}
      {zReal.map((r, i) => (
        <circle key={i} cx={x(r)} cy={y(negZi[i])} r={2.5} fill={accent} />
      ))}
      {fitReal?.length && (
        <polyline
          points={fitReal.map((r, i) => `${x(r)},${y(-fitImag[i])}`).join(' ')}
          fill="none" stroke="#ef5350" strokeWidth={1.4}
        />
      )}
    </svg>
  );
}

// ───────────────────────────────────────────────────────────────────
// Sub-component: Cs-vs-scan-rate mini-bar
// ───────────────────────────────────────────────────────────────────

function CsByMethodChart({ summary, height = 180 }) {
  if (!summary) return null;
  const entries = Object.entries(summary)
    .filter(([, v]) => typeof v === 'number')
    .map(([k, v]) => ({ k, v }));
  if (!entries.length) return null;
  const max = Math.max(...entries.map(e => e.v));
  const W = 460, H = height, pad = { l: 200, r: 60, t: 8, b: 8 };
  const pw = W - pad.l - pad.r;
  const rowH = (H - pad.t - pad.b) / entries.length;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: 520, height }}>
      <rect width={W} height={H} fill="transparent" />
      {entries.map((e, i) => {
        const w = max > 0 ? (e.v / max) * pw : 0;
        const yy = pad.t + i * rowH + rowH * 0.15;
        return (
          <g key={e.k}>
            <text x={pad.l - 8} y={yy + rowH * 0.55} fontSize={10}
                  fill="#cbd5e1" textAnchor="end" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
              {e.k}
            </text>
            <rect x={pad.l} y={yy} width={w} height={rowH * 0.7} fill="#76b900" opacity="0.85" rx={2} />
            <text x={pad.l + w + 4} y={yy + rowH * 0.55} fontSize={10}
                  fill="#9aa4b1" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
              {fmtCs(e.v)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ───────────────────────────────────────────────────────────────────
// Sub-panel: Datasets list + create-new
// ───────────────────────────────────────────────────────────────────

function DatasetsList({ datasets, selectedId, onSelect, onRefresh, onCreate, onDelete }) {
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [busy, setBusy] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await onCreate(name.trim(), desc.trim());
      setShowCreate(false); setName(''); setDesc('');
    } finally { setBusy(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 14px', borderBottom: '1px solid var(--border-primary)' }}>
        <Database size={14} color="#76b900" />
        <div style={{ fontSize: 12, fontWeight: 600 }}>Lab Datasets ({datasets.length})</div>
        <div style={{ flex: 1 }} />
        <button className="btn btn-sm btn-ghost" onClick={onRefresh} title="Refresh">
          <RefreshCcw size={11} />
        </button>
        <button className="btn btn-sm btn-primary" onClick={() => setShowCreate(s => !s)}>
          <Plus size={11} style={{ marginRight: 4 }} /> New
        </button>
      </div>

      {showCreate && (
        <div style={{ padding: 12, background: 'var(--bg-elevated)', borderBottom: '1px solid var(--border-primary)' }}>
          <input className="input-field" placeholder="Dataset name (e.g. AGV batch 03)"
                 value={name} onChange={e => setName(e.target.value)}
                 style={{ width: '100%', fontSize: 12, marginBottom: 6 }} autoFocus />
          <input className="input-field" placeholder="Description (optional)"
                 value={desc} onChange={e => setDesc(e.target.value)}
                 style={{ width: '100%', fontSize: 11, marginBottom: 8 }} />
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-sm btn-primary" onClick={handleCreate}
                    disabled={busy || !name.trim()} style={{ flex: 1 }}>
              {busy ? 'Creating…' : 'Create'}
            </button>
            <button className="btn btn-sm" onClick={() => setShowCreate(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {datasets.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-disabled)', fontSize: 11, lineHeight: 1.6 }}>
            No datasets yet.<br />Create one and upload a CV/GCD/EIS xlsx.
          </div>
        ) : datasets.map(d => (
          <div key={d.id}
               onClick={() => onSelect(d.id)}
               style={{
                 padding: '10px 14px',
                 borderBottom: '1px solid var(--border-primary)',
                 cursor: 'pointer',
                 background: selectedId === d.id ? 'rgba(118,185,0,0.08)' : 'transparent',
                 borderLeft: selectedId === d.id ? '2px solid #76b900' : '2px solid transparent',
               }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {d.name}
              </div>
              <button className="btn btn-sm btn-ghost"
                      onClick={(e) => { e.stopPropagation(); if (window.confirm(`Delete '${d.name}'?`)) onDelete(d.id); }}
                      title="Delete">
                <Trash2 size={11} color="#ef5350" />
              </button>
            </div>
            {d.description && (
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2, lineHeight: 1.4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {d.description}
              </div>
            )}
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 4 }}>
              {d.row_count} row{d.row_count === 1 ? '' : 's'} · {new Date(d.modified_at * 1000).toLocaleDateString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// Sub-panel: Upload xlsx
// ───────────────────────────────────────────────────────────────────

function UploadCard({ datasetId, onUploaded, defaults }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [meta, setMeta] = useState(defaults);
  const fileInputRef = useRef(null);

  const upload = useCallback(async () => {
    if (!file) return;
    setBusy(true); setError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('material', meta.material);
      fd.append('electrolyte', meta.electrolyte);
      fd.append('gcd_current_mA', String(meta.gcd_current_mA));
      fd.append('eis_fmax_Hz', String(meta.eis_fmax_Hz));
      fd.append('eis_fmin_Hz', String(meta.eis_fmin_Hz));
      if (meta.electrode_area_cm2) fd.append('electrode_area_cm2', String(meta.electrode_area_cm2));

      const res = await fetch(`${API}/api/v2/lab/datasets/${datasetId}/import/xlsx`, {
        method: 'POST', body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data?.detail || `HTTP ${res.status}`);
      } else {
        onUploaded(data);
        setFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    } catch (e) {
      setError(`Network error: ${e.message}`);
    } finally { setBusy(false); }
  }, [file, meta, datasetId, onUploaded]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  }, []);

  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="card-header">
        <div>
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <FileSpreadsheet size={14} color="#76b900" /> Upload AnalyteX xlsx
          </div>
          <div className="card-subtitle">CV + GCD + EIS sheets, multipart upload</div>
        </div>
      </div>

      <div onDrop={handleDrop} onDragOver={e => e.preventDefault()}
           onClick={() => fileInputRef.current?.click()}
           style={{
             padding: 16, border: '1px dashed var(--border-secondary)', borderRadius: 8,
             background: file ? 'rgba(118,185,0,0.06)' : 'var(--bg-primary)',
             textAlign: 'center', cursor: 'pointer', marginBottom: 12,
             color: 'var(--text-secondary)', fontSize: 11, lineHeight: 1.6,
           }}>
        <Upload size={20} style={{ display: 'block', margin: '0 auto 6px', opacity: 0.7 }} />
        {file
          ? <><strong style={{ color: '#76b900' }}>{file.name}</strong><br/>{(file.size / 1024).toFixed(1)} kB — click to change</>
          : <>Drop a <code>.xlsx</code> here or click to browse.<br/>Sheets must be named <code>CV</code>, <code>GCD</code>, <code>EIS</code>.</>
        }
        <input type="file" accept=".xlsx" ref={fileInputRef} style={{ display: 'none' }}
               onChange={e => setFile(e.target.files?.[0] || null)} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
        {[
          ['material', 'Material tag', 'text'],
          ['electrolyte', 'Electrolyte', 'text'],
          ['gcd_current_mA', 'GCD current (mA)', 'number'],
          ['electrode_area_cm2', 'Electrode area (cm²)', 'number'],
          ['eis_fmax_Hz', 'EIS f_max (Hz)', 'number'],
          ['eis_fmin_Hz', 'EIS f_min (Hz)', 'number'],
        ].map(([k, label, type]) => (
          <div key={k}>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginBottom: 2, textTransform: 'uppercase' }}>{label}</div>
            <input className="input-field" type={type} step="any"
                   value={meta[k] ?? ''} placeholder={type === 'number' ? '—' : ''}
                   onChange={e => setMeta(m => ({ ...m, [k]: type === 'number' ? (e.target.value === '' ? null : Number(e.target.value)) : e.target.value }))}
                   style={{ width: '100%', fontSize: 11 }} />
          </div>
        ))}
      </div>

      {error && (
        <div style={{ fontSize: 11, color: '#ef5350', padding: 8, background: 'rgba(239,83,80,0.06)', borderRadius: 4, marginBottom: 8 }}>
          {error}
        </div>
      )}

      <button className="btn btn-primary" onClick={upload} disabled={!file || busy}
              style={{ width: '100%', fontSize: 12 }}>
        {busy ? 'Uploading…' : 'Import xlsx'}
      </button>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// Sub-panel: Analysis report
// ───────────────────────────────────────────────────────────────────

function AnalysisCard({ datasetId, defaults }) {
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [opts, setOpts] = useState({
    mass_g: '', area_cm2: '',
    gcd_current_mA: defaults.gcd_current_mA,
    eis_fmax_Hz: defaults.eis_fmax_Hz, eis_fmin_Hz: defaults.eis_fmin_Hz,
  });

  const run = useCallback(async () => {
    setBusy(true); setError(''); setReport(null);
    try {
      const params = new URLSearchParams({
        gcd_current_mA: String(opts.gcd_current_mA),
        eis_fmax_Hz: String(opts.eis_fmax_Hz),
        eis_fmin_Hz: String(opts.eis_fmin_Hz),
      });
      if (opts.mass_g)  params.set('mass_g', String(opts.mass_g));
      if (opts.area_cm2) params.set('area_cm2', String(opts.area_cm2));
      const data = await apiGet(`/api/v2/supercap/analyze/${datasetId}?${params}`);
      setReport(data);
    } catch (e) {
      setError(String(e.message || e));
    } finally { setBusy(false); }
  }, [datasetId, opts]);

  const summary = report?.report?.summary;
  const eis = report?.report?.eis;

  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="card-header">
        <div>
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <BarChart3 size={14} color="#42a5f5" /> Supercap analysis
          </div>
          <div className="card-subtitle">Cs from CV+GCD+EIS, b-value, retention</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginBottom: 8 }}>
        {[
          ['mass_g', 'Mass (g)'],
          ['area_cm2', 'Area (cm²)'],
          ['gcd_current_mA', 'GCD I (mA)'],
          ['eis_fmax_Hz', 'EIS f_max'],
          ['eis_fmin_Hz', 'EIS f_min'],
        ].map(([k, label]) => (
          <div key={k}>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginBottom: 2, textTransform: 'uppercase' }}>{label}</div>
            <input className="input-field" type="number" step="any"
                   value={opts[k] ?? ''} placeholder="—"
                   onChange={e => setOpts(o => ({ ...o, [k]: e.target.value === '' ? '' : Number(e.target.value) }))}
                   style={{ width: '100%', fontSize: 11 }} />
          </div>
        ))}
        <button className="btn btn-primary" onClick={run} disabled={busy}
                style={{ alignSelf: 'flex-end', fontSize: 11 }}>
          {busy ? 'Running…' : 'Analyse'}
        </button>
      </div>

      {error && <div style={{ fontSize: 11, color: '#ef5350' }}>{error}</div>}

      {summary && (
        <>
          {/* Headline numbers */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 12, marginBottom: 12 }}>
            <Stat label="b-value (Trasatti)" value={fmt(summary.b_value, 3)} sub={`R²=${fmt(summary.b_value_r_squared, 2)}`} />
            <Stat label="Capacitance retention" value={fmtPct(summary.capacitance_retention_pct)} accent={summary.capacitance_retention_pct < 80 ? '#ef5350' : '#76b900'} />
            <Stat label="Avg Coulombic η" value={fmtPct(summary.average_coulombic_efficiency_pct)} accent={summary.average_coulombic_efficiency_pct < 90 ? '#f59e0b' : '#76b900'} />
            <Stat label="Energy density" value={summary.energy_density_Wh_per_kg ? `${fmt(summary.energy_density_Wh_per_kg, 2)} Wh/kg` : '—'} />
          </div>

          {/* Cs by method */}
          <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 6, color: 'var(--text-secondary)' }}>Cs by method (absolute)</div>
          <CsByMethodChart summary={summary.cs_F} />

          {/* Diagnostics */}
          {summary.diagnostics?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 6, color: 'var(--text-secondary)' }}>Diagnostics</div>
              {summary.diagnostics.map((d, i) => (
                <div key={i} style={{ fontSize: 10, padding: '6px 10px', background: 'rgba(245,158,11,0.06)', border: '1px solid #f59e0b33', borderRadius: 4, marginBottom: 4, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  <AlertTriangle size={11} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6, color: '#f59e0b' }} />
                  {d}
                </div>
              ))}
            </div>
          )}

          {/* EIS Nyquist + Rs */}
          {eis && eis.nyquist_shape && (
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 6, color: 'var(--text-secondary)' }}>EIS fingerprint</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginBottom: 8 }}>
                <Stat label="Rs" value={`${fmt(eis.rs_ohm, 3)} Ω`} />
                <Stat label="Cs(low f)" value={fmtCs(eis.cs_low_freq_F)} />
                <Stat label="Knee f" value={eis.knee_frequency_Hz ? `${fmt(eis.knee_frequency_Hz, 2)} Hz` : '—'} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{eis.nyquist_shape}</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value, sub, accent = 'var(--text-primary)' }) {
  return (
    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-primary)', borderRadius: 6, padding: 8 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: accent, fontFamily: 'JetBrains Mono, monospace' }}>{value}</div>
      <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>{label}</div>
      {sub && <div style={{ fontSize: 8, color: 'var(--text-tertiary)', marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// Sub-panel: NIM-grounded suggestions
// ───────────────────────────────────────────────────────────────────

function SuggestionsCard({ datasetId, defaults }) {
  const [target, setTarget] = useState(
    'Stable EDLC supercap, Cs > 200 F/g, retention > 90% over 1000 cycles');
  const [n, setN] = useState(4);
  const [out, setOut] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const run = async () => {
    setBusy(true); setError(''); setOut(null);
    try {
      const data = await apiPostJSON('/api/v2/supercap/suggest-next', {
        dataset_id: datasetId, target, n_suggestions: n,
        options: {
          gcd_current_mA: defaults.gcd_current_mA,
          eis_fmax_Hz: defaults.eis_fmax_Hz, eis_fmin_Hz: defaults.eis_fmin_Hz,
        },
      });
      setOut(data);
    } catch (e) {
      setError(String(e.message || e));
    } finally { setBusy(false); }
  };

  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="card-header">
        <div>
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Lightbulb size={14} color="#f59e0b" /> Iteration suggestions (NVIDIA NIM)
          </div>
          <div className="card-subtitle">Grounded in your numbers, never fabricated</div>
        </div>
      </div>

      <textarea className="input-field" rows={2}
                value={target} onChange={e => setTarget(e.target.value)}
                style={{ width: '100%', fontSize: 11, marginBottom: 8, resize: 'vertical' }} />
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Suggestions:</span>
        <input className="input-field" type="number" min={1} max={8} value={n}
               onChange={e => setN(Number(e.target.value || 4))}
               style={{ width: 56, fontSize: 11 }} />
        <button className="btn btn-primary" onClick={run} disabled={busy}
                style={{ marginLeft: 'auto', fontSize: 11 }}>
          {busy ? 'Asking NIM…' : 'Get suggestions'}
        </button>
      </div>

      {error && <div style={{ fontSize: 11, color: '#ef5350' }}>{error}</div>}

      {out && !out.available && (
        <div style={{ padding: 10, background: 'rgba(245,158,11,0.06)', borderRadius: 4, fontSize: 11, color: 'var(--text-secondary)' }}>
          <strong>Recommender unavailable.</strong> {out.reason}
        </div>
      )}

      {out?.available && (
        <>
          {out.diagnosis && (
            <div style={{ padding: 10, background: 'rgba(118,185,0,0.05)', border: '1px solid #76b90033', borderRadius: 4, marginBottom: 10, fontSize: 11, lineHeight: 1.5, color: 'var(--text-secondary)' }}>
              <strong style={{ color: '#76b900' }}>Diagnosis:</strong> {out.diagnosis}
            </div>
          )}
          {(out.suggestions || []).map((s, i) => (
            <div key={i} style={{
              padding: 10, border: '1px solid var(--border-primary)', borderRadius: 6,
              marginBottom: 8, background: 'var(--bg-elevated)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: '#76b900' }}>#{i + 1}</span>
                <span style={{ fontSize: 12, fontWeight: 600 }}>{s.title}</span>
                <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3,
                                background: s.risk === 'low' ? 'rgba(118,185,0,0.15)' : s.risk === 'medium' ? 'rgba(245,158,11,0.15)' : 'rgba(239,83,80,0.15)',
                                color: s.risk === 'low' ? '#76b900' : s.risk === 'medium' ? '#f59e0b' : '#ef5350' }}>
                  risk: {s.risk}
                </span>
                {s.expected_effect_on_Cs && (
                  <span style={{ fontSize: 9, color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
                    Cs effect: {s.expected_effect_on_Cs}
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-primary)', marginBottom: 4 }}>
                <strong style={{ color: '#42a5f5' }}>Change:</strong> {s.what_to_change}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 4, lineHeight: 1.5 }}>
                <strong>Why:</strong> {s.why}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
                <strong>Verify with:</strong> {s.data_needed_to_evaluate}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// Sub-panel: Rows table (drill-down view)
// ───────────────────────────────────────────────────────────────────

function RowsCard({ dataset }) {
  if (!dataset?.rows?.length) return (
    <div className="card" style={{ marginBottom: 14, fontSize: 11, color: 'var(--text-tertiary)' }}>
      No rows yet. Upload an xlsx or POST rows via the API.
    </div>
  );
  const summary = (() => {
    const counts = {};
    for (const r of dataset.rows) {
      const exp = r.conditions?.experiment || 'other';
      counts[exp] = (counts[exp] || 0) + 1;
    }
    return counts;
  })();
  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="card-header">
        <div>
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Beaker size={14} /> Rows ({dataset.rows.length})
          </div>
          <div className="card-subtitle">
            {Object.entries(summary).map(([k, v]) => `${v} × ${k}`).join('  ·  ')}
          </div>
        </div>
      </div>
      <div style={{ maxHeight: 280, overflowY: 'auto', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ background: 'var(--bg-elevated)' }}>
            <th style={{ padding: '6px 8px', textAlign: 'left' }}>Name</th>
            <th style={{ padding: '6px 8px', textAlign: 'left' }}>Experiment</th>
            <th style={{ padding: '6px 8px', textAlign: 'left' }}>Properties</th>
          </tr></thead>
          <tbody>
            {dataset.rows.map((r, i) => (
              <tr key={i} style={{ borderTop: '1px solid var(--border-primary)' }}>
                <td style={{ padding: '6px 8px' }}>{r.name || '—'}</td>
                <td style={{ padding: '6px 8px', color: 'var(--text-tertiary)' }}>{r.conditions?.experiment || '—'}</td>
                <td style={{ padding: '6px 8px', color: 'var(--text-secondary)' }}>
                  {Object.entries(r.properties || {}).slice(0, 3).map(([k, v]) => `${k}=${typeof v === 'number' ? v.toExponential(2) : v}`).join(' · ')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// Main panel
// ───────────────────────────────────────────────────────────────────

const DEFAULT_META = {
  material: 'AGV',
  electrolyte: '1 M H2SO4',
  gcd_current_mA: 1.0,
  eis_fmax_Hz: 1e5,
  eis_fmin_Hz: 1e-2,
  electrode_area_cm2: null,
};

export default function LabDataPanel() {
  const [datasets, setDatasets] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedData, setSelectedData] = useState(null);
  const [tab, setTab] = useState('upload');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const refreshList = useCallback(async () => {
    setBusy(true); setError('');
    try {
      const list = await apiGet('/api/v2/lab/datasets');
      setDatasets(Array.isArray(list) ? list : []);
    } catch (e) {
      setError(`Could not reach the local backend at ${API}: ${e.message}`);
    } finally { setBusy(false); }
  }, []);

  const refreshSelected = useCallback(async () => {
    if (!selectedId) { setSelectedData(null); return; }
    try {
      const ds = await apiGet(`/api/v2/lab/datasets/${selectedId}`);
      setSelectedData(ds);
    } catch (e) {
      setError(String(e.message || e));
    }
  }, [selectedId]);

  useEffect(() => { refreshList(); }, [refreshList]);
  useEffect(() => { refreshSelected(); }, [refreshSelected]);

  const create = useCallback(async (name, description) => {
    const ds = await apiPostJSON('/api/v2/lab/datasets', { name, description });
    setSelectedId(ds.id);
    await refreshList();
  }, [refreshList]);

  const remove = useCallback(async (id) => {
    await apiDelete(`/api/v2/lab/datasets/${id}`);
    if (selectedId === id) setSelectedId(null);
    await refreshList();
  }, [selectedId, refreshList]);

  const onUploaded = useCallback(async (info) => {
    await refreshSelected();
    await refreshList();
    setTab('analysis');
  }, [refreshSelected, refreshList]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', height: '100%', gap: 0 }}>
      {/* Left rail */}
      <div style={{ borderRight: '1px solid var(--border-primary)', overflow: 'hidden' }}>
        <DatasetsList
          datasets={datasets}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onRefresh={refreshList}
          onCreate={create}
          onDelete={remove}
        />
      </div>

      {/* Right side */}
      <div style={{ overflowY: 'auto', padding: 16 }}>
        {error && (
          <div style={{ padding: 10, marginBottom: 12, background: 'rgba(239,83,80,0.08)', border: '1px solid #ef535055', borderRadius: 4, fontSize: 11, color: '#ef5350' }}>
            {error}
          </div>
        )}

        {!selectedId ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', textAlign: 'center', color: 'var(--text-disabled)' }}>
            <FlaskConical size={36} style={{ opacity: 0.4, marginBottom: 12 }} />
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Select a dataset</div>
            <div style={{ fontSize: 11, marginTop: 6, lineHeight: 1.6 }}>
              or create a new one to upload your CV / GCD / EIS data.<br/>
              Everything is encrypted under <code>~/.local/share/raman-studio/lab_datasets/</code>.
            </div>
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <FlaskConical size={20} color="#76b900" />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16, fontWeight: 700 }}>
                  {datasets.find(d => d.id === selectedId)?.name || 'Dataset'}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'JetBrains Mono, monospace' }}>
                  id: {selectedId}
                </div>
              </div>
              <button className="btn btn-sm btn-ghost" onClick={refreshSelected} title="Refresh">
                <RefreshCcw size={11} />
              </button>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border-primary)', marginBottom: 12 }}>
              {[
                ['upload', 'Upload', Upload],
                ['rows', 'Rows', Database],
                ['analysis', 'Analysis', BarChart3],
                ['suggest', 'Suggestions', Lightbulb],
              ].map(([key, label, Icon]) => (
                <button key={key} onClick={() => setTab(key)}
                        style={{
                          background: 'none', border: 'none', padding: '8px 12px',
                          fontSize: 11, fontWeight: 600, cursor: 'pointer',
                          color: tab === key ? '#76b900' : 'var(--text-secondary)',
                          borderBottom: tab === key ? '2px solid #76b900' : '2px solid transparent',
                          display: 'flex', alignItems: 'center', gap: 6,
                        }}>
                  <Icon size={11} /> {label}
                </button>
              ))}
            </div>

            {tab === 'upload' && (
              <UploadCard datasetId={selectedId} onUploaded={onUploaded} defaults={DEFAULT_META} />
            )}
            {tab === 'rows' && <RowsCard dataset={selectedData} />}
            {tab === 'analysis' && <AnalysisCard datasetId={selectedId} defaults={DEFAULT_META} />}
            {tab === 'suggest' && <SuggestionsCard datasetId={selectedId} defaults={DEFAULT_META} />}
          </>
        )}
      </div>
    </div>
  );
}
