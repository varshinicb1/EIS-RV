import React, { useState, useCallback } from 'react';
import { Search, Beaker, Zap, ChevronRight, Sparkles, Layers, FlaskConical, Target, Upload, Plus, X } from 'lucide-react';

// API helper — always use relative URLs so the Vite proxy routes them correctly
const apiCall = async (endpoint, options = {}) => {
  const response = await fetch(endpoint, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
};

/* ────────────────────────────────────────────────────────────────
   Helper: API call with loading state management
   ──────────────────────────────────────────────────────────────── */
async function apiPost(endpoint, body) {
  return apiCall(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
async function apiGet(endpoint) {
  return apiCall(endpoint);
}

/* ────────────────────────────────────────────────────────────────
   Sub-panel: NVIDIA Material Discovery
   ──────────────────────────────────────────────────────────────── */
function DiscoveryTab() {
  const [application, setApplication] = useState('Pb2+ detection biosensor');
  const [candidates, setCandidates] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const discover = async () => {
    setLoading(true); setError(null);
    try {
      const data = await apiPost('/api/v2/materials/discover', {
        application, max_candidates: 5,
      });
      setCandidates(data.candidates || []);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  return (
    <div className="animate-in">
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input className="input-field" value={application}
          onChange={e => setApplication(e.target.value)}
          placeholder="e.g., Pb2+ detection biosensor, supercapacitor electrode"
          style={{ flex: 1 }} />
        <button className="btn btn-primary" onClick={discover} disabled={loading}
          style={{ minWidth: 120 }}>
          {loading ? <span className="spinner-sm" /> : <><Search size={14} /> Discover</>}
        </button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 12, padding: 10, background: 'rgba(239,68,68,0.1)', borderRadius: 6, fontSize: 11, color: '#ef4444' }}>{error}</div>}

      {candidates && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {candidates.map((c, i) => (
            <div key={i} style={{
              background: 'var(--bg-elevated)', borderRadius: 8, padding: 14,
              border: '1px solid var(--border-default)',
              borderLeft: `3px solid hsl(${120 * c.confidence}, 70%, 50%)`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <div>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{c.name}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 8, fontFamily: 'var(--font-data)' }}>{c.formula}</span>
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
                  background: `hsla(${120 * c.confidence}, 70%, 50%, 0.15)`,
                  color: `hsl(${120 * c.confidence}, 70%, 50%)`,
                }}>{Math.round(c.confidence * 100)}%</span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 4 }}>
                <span style={{ background: 'var(--bg-surface)', padding: '1px 6px', borderRadius: 4, marginRight: 6, fontSize: 9, fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-tertiary)' }}>{c.category}</span>
                {c.synthesis_route}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>{c.rationale}</div>
              {c.predicted_properties && Object.keys(c.predicted_properties).length > 0 && (
                <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                  {Object.entries(c.predicted_properties).map(([k, v]) => (
                    <span key={k} style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: 'rgba(66,165,245,0.1)', color: '#42a5f5', fontFamily: 'var(--font-data)' }}>
                      {k}: {v}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────
   Sub-panel: Synthesis Route Generator
   ──────────────────────────────────────────────────────────────── */
function SynthesisTab() {
  const [material, setMaterial] = useState('MoS2');
  const [formula, setFormula] = useState('MoS2');
  const [form, setForm] = useState('nanosheets');
  const [routes, setRoutes] = useState(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    try {
      const data = await apiPost('/api/v2/materials/synthesis', {
        material_name: material, material_formula: formula, target_form: form,
      });
      setRoutes(data.routes || []);
    } catch { }
    setLoading(false);
  };

  return (
    <div className="animate-in">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 8, marginBottom: 16 }}>
        <input className="input-field" value={material} onChange={e => setMaterial(e.target.value)} placeholder="Material name" />
        <input className="input-field" value={formula} onChange={e => setFormula(e.target.value)} placeholder="Formula" />
        <select className="input-field" value={form} onChange={e => setForm(e.target.value)}>
          <option value="nanoparticles">Nanoparticles</option>
          <option value="nanosheets">Nanosheets</option>
          <option value="thin_film">Thin Film</option>
          <option value="nanowires">Nanowires</option>
          <option value="nanofibers">Nanofibers</option>
        </select>
        <button className="btn btn-primary" onClick={generate} disabled={loading}>
          {loading ? '...' : <><FlaskConical size={14} /> Generate</>}
        </button>
      </div>

      {routes && routes.map((route, i) => (
        <div key={i} style={{
          background: 'var(--bg-elevated)', borderRadius: 8, padding: 14,
          border: '1px solid var(--border-default)', marginBottom: 10,
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, textTransform: 'capitalize' }}>
            <FlaskConical size={14} style={{ display: 'inline', marginRight: 6, color: '#f59e0b' }} />
            {route.method}
            {route.temperature_C && <span style={{ fontSize: 10, color: 'var(--text-tertiary)', marginLeft: 8 }}>{route.temperature_C}°C</span>}
            {route.duration_hours && <span style={{ fontSize: 10, color: 'var(--text-tertiary)', marginLeft: 6 }}>{route.duration_hours}h</span>}
          </div>
          <ol style={{ margin: 0, paddingLeft: 20, fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
            {route.steps?.map((step, j) => <li key={j}>{step}</li>)}
          </ol>
          {route.precursors?.length > 0 && (
            <div style={{ marginTop: 8, fontSize: 9, color: 'var(--text-tertiary)' }}>
              <strong>Precursors:</strong> {route.precursors.join(', ')}
            </div>
          )}
          {route.safety_notes && (
            <div style={{ marginTop: 4, fontSize: 9, color: '#ef4444', fontStyle: 'italic' }}>
              ⚠ {route.safety_notes}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────
   Sub-panel: Biosensor Coating Suggestor
   ──────────────────────────────────────────────────────────────── */
function BiosensorSuggestorTab() {
  const [analyte, setAnalyte] = useState('Pb2+');
  const [technique, setTechnique] = useState('DPV');
  const [substrate, setSubstrate] = useState('screen-printed carbon');
  const [suggestions, setSuggestions] = useState(null);
  const [supportedAnalytes, setSupportedAnalytes] = useState(null);
  const [loading, setLoading] = useState(false);

  const suggest = async () => {
    setLoading(true);
    try {
      const data = await apiPost('/api/v2/biosensor/suggest', {
        analyte, technique, electrode_substrate: substrate, max_suggestions: 3,
      });
      setSuggestions(data.suggestions || []);
    } catch { }
    setLoading(false);
  };

  const loadAnalytes = async () => {
    try {
      const data = await apiGet('/api/v2/biosensor/supported-analytes');
      setSupportedAnalytes(data.supported_analytes || []);
    } catch { }
  };

  return (
    <div className="animate-in">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 8, marginBottom: 16 }}>
        <div>
          <span className="input-label">Target Analyte</span>
          <input className="input-field" value={analyte} onChange={e => setAnalyte(e.target.value)}
            placeholder="Pb2+, glucose, dopamine..." onFocus={loadAnalytes} />
          {supportedAnalytes && (
            <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
              {supportedAnalytes.map(a => (
                <button key={a} onClick={() => setAnalyte(a)}
                  style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, border: '1px solid var(--border-default)',
                    background: analyte === a ? 'var(--accent)' : 'var(--bg-elevated)',
                    color: analyte === a ? '#fff' : 'var(--text-tertiary)', cursor: 'pointer' }}>
                  {a}
                </button>
              ))}
            </div>
          )}
        </div>
        <div>
          <span className="input-label">Technique</span>
          <select className="input-field" value={technique} onChange={e => setTechnique(e.target.value)}>
            {['CV', 'DPV', 'SWV', 'EIS', 'amperometry', 'SWASV', 'DPASV'].map(t =>
              <option key={t} value={t}>{t}</option>
            )}
          </select>
        </div>
        <div>
          <span className="input-label">Electrode</span>
          <select className="input-field" value={substrate} onChange={e => setSubstrate(e.target.value)}>
            <option value="screen-printed carbon">SPE Carbon</option>
            <option value="screen-printed gold">SPE Gold</option>
            <option value="GCE">GCE</option>
            <option value="Pt disk">Pt Disk</option>
            <option value="ITO">ITO</option>
            <option value="Ni foam">Ni Foam</option>
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button className="btn btn-primary" onClick={suggest} disabled={loading}
            style={{ height: 36 }}>
            {loading ? '...' : <><Target size={14} /> Suggest</>}
          </button>
        </div>
      </div>

      {suggestions && suggestions.map((s, i) => (
        <div key={i} style={{
          background: 'var(--bg-elevated)', borderRadius: 8, padding: 14,
          border: '1px solid var(--border-default)', marginBottom: 10,
          borderLeft: `3px solid hsl(${120 * s.confidence}, 70%, 50%)`,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <div>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{s.material_name}</span>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 8, fontFamily: 'var(--font-data)' }}>{s.formula}</span>
            </div>
            <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
              background: `hsla(${120 * s.confidence}, 70%, 50%, 0.15)`,
              color: `hsl(${120 * s.confidence}, 70%, 50%)` }}>
              {Math.round(s.confidence * 100)}%
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 10 }}>
            {[
              { label: 'LOD', value: s.expected_lod, color: '#10b981' },
              { label: 'Sensitivity', value: s.expected_sensitivity, color: '#3b82f6' },
              { label: 'Linear Range', value: s.linear_range, color: '#f59e0b' },
              { label: 'Technique', value: s.technique, color: '#8b5cf6' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ textAlign: 'center', padding: 6, background: `${color}11`, borderRadius: 6, border: `1px solid ${color}33` }}>
                <div style={{ fontSize: 10, fontWeight: 600, color, fontFamily: 'var(--font-data)' }}>{value || '—'}</div>
                <div style={{ fontSize: 8, color: 'var(--text-tertiary)', marginTop: 2 }}>{label}</div>
              </div>
            ))}
          </div>

          <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 8 }}>{s.rationale}</div>

          {s.preparation_steps?.length > 0 && (
            <details style={{ fontSize: 10 }}>
              <summary style={{ cursor: 'pointer', color: '#42a5f5', fontWeight: 600, marginBottom: 4 }}>
                Preparation Protocol ({s.preparation_steps.length} steps)
              </summary>
              <ol style={{ paddingLeft: 20, margin: 0, lineHeight: 1.8, color: 'var(--text-secondary)' }}>
                {s.preparation_steps.map((step, j) => <li key={j}>{step}</li>)}
              </ol>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────
   Sub-panel: Cross-Modal Material Identification
   ──────────────────────────────────────────────────────────────── */
function IdentifyTab() {
  const [modality, setModality] = useState('cv');
  const [params, setParams] = useState({});
  const [ramanPeaks, setRamanPeaks] = useState('1350, 1580, 2700');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const identify = async () => {
    setLoading(true);
    try {
      let body = { ...params };
      if (modality === 'raman') {
        body.peaks_cm = ramanPeaks.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
        if (params.d_g_ratio) body.d_g_ratio = parseFloat(params.d_g_ratio);
      }
      // Convert numeric strings to numbers
      for (const [k, v] of Object.entries(body)) {
        if (typeof v === 'string' && v && !isNaN(v)) body[k] = parseFloat(v);
      }

      const data = await apiPost(`/api/v2/identify/${modality}`, body);
      setResults(data.matches || []);
    } catch { }
    setLoading(false);
  };

  const fields = {
    cv: [
      { key: 'peak_separation_mV', label: 'ΔEp (mV)', placeholder: '65' },
      { key: 'ipa_ipc_ratio', label: 'ipa/ipc', placeholder: '0.99' },
      { key: 'onset_potential_V', label: 'Onset (V)', placeholder: '0.1' },
    ],
    eis: [
      { key: 'rct_ohm', label: 'Rct (Ω)', placeholder: '30' },
      { key: 'rs_ohm', label: 'Rs (Ω)', placeholder: '5' },
      { key: 'cdl_uF', label: 'Cdl (µF)', placeholder: '300' },
    ],
    gcd: [
      { key: 'specific_capacitance_Fg', label: 'Cs (F/g)', placeholder: '250' },
      { key: 'coulombic_efficiency_pct', label: 'CE (%)', placeholder: '97' },
      { key: 'plateau_voltage_V', label: 'Vplateau (V)', placeholder: '0.8' },
    ],
  };

  return (
    <div className="animate-in">
      <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
        {[
          { key: 'cv', label: 'CV', icon: <Zap size={12} /> },
          { key: 'eis', label: 'EIS', icon: <Layers size={12} /> },
          { key: 'gcd', label: 'GCD', icon: <Beaker size={12} /> },
          { key: 'raman', label: 'Raman', icon: <Sparkles size={12} /> },
        ].map(({ key, label, icon }) => (
          <button key={key} onClick={() => { setModality(key); setParams({}); setResults(null); }}
            className={`btn btn-sm ${modality === key ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: 11 }}>
            {icon} {label}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: modality === 'raman' ? '1fr auto' : 'repeat(3, 1fr) auto', gap: 8, marginBottom: 16 }}>
        {modality === 'raman' ? (
          <>
            <div>
              <span className="input-label">Peak positions (cm⁻¹, comma-separated)</span>
              <input className="input-field" value={ramanPeaks}
                onChange={e => setRamanPeaks(e.target.value)}
                placeholder="1350, 1580, 2700" />
            </div>
          </>
        ) : (
          fields[modality]?.map(f => (
            <div key={f.key}>
              <span className="input-label">{f.label}</span>
              <input className="input-field" value={params[f.key] || ''}
                onChange={e => setParams({ ...params, [f.key]: e.target.value })}
                placeholder={f.placeholder} />
            </div>
          ))
        )}
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button className="btn btn-primary" onClick={identify} disabled={loading}
            style={{ height: 36 }}>
            {loading ? '...' : <><Search size={14} /> Identify</>}
          </button>
        </div>
      </div>

      {results && results.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {results.map((r, i) => (
            <div key={i} style={{
              background: 'var(--bg-elevated)', borderRadius: 8, padding: 12,
              border: '1px solid var(--border-default)',
              borderLeft: `3px solid hsl(${120 * r.confidence}, 70%, 50%)`,
              opacity: r.confidence > 0.5 ? 1 : 0.7,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{r.material_name}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 8 }}>{r.formula}</span>
                  <span style={{ fontSize: 9, marginLeft: 8, padding: '1px 6px', borderRadius: 4, background: 'var(--bg-surface)', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>{r.category}</span>
                </div>
                <span style={{ fontSize: 11, fontWeight: 700, color: `hsl(${120 * r.confidence}, 70%, 50%)` }}>
                  {Math.round(r.confidence * 100)}%
                </span>
              </div>
              {r.suggested_applications?.length > 0 && (
                <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {r.suggested_applications.map(app => (
                    <span key={app} style={{ fontSize: 8, padding: '1px 5px', borderRadius: 3, background: 'rgba(139,92,246,0.12)', color: '#8b5cf6' }}>
                      {app.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
              <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 4 }}>{r.rationale}</div>
            </div>
          ))}
        </div>
      )}

      {results && results.length === 0 && (
        <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-disabled)', fontSize: 11 }}>
          No material matches found. Try adjusting your parameters.
        </div>
      )}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────
   Main Panel — Material Discovery & Biosensor AI
   ──────────────────────────────────────────────────────────────── */
export default function MaterialDiscoveryPanel() {
  const [tab, setTab] = useState('discover');

  const tabs = [
    { key: 'discover', label: 'Material Discovery', icon: <Sparkles size={13} /> },
    { key: 'synthesis', label: 'Synthesis Routes', icon: <FlaskConical size={13} /> },
    { key: 'biosensor', label: 'WE Coating AI', icon: <Target size={13} /> },
    { key: 'identify', label: 'Cross-Modal ID', icon: <Layers size={13} /> },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }} className="animate-in" role="main" aria-label="Material Discovery and Biosensor AI">
      {/* Header */}
      <div className="card" style={{ marginBottom: 12, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'linear-gradient(135deg, #76b900 0%, #42a5f5 100%)',
          }}>
            <Beaker size={18} color="#fff" />
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>Material Discovery & Biosensor AI</div>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>NVIDIA NIM-powered nanomaterial discovery • Cross-modal identification • Electrode coating advisor</div>
          </div>
        </div>

        {/* Tab bar */}
        <div style={{ display: 'flex', gap: 4, borderTop: '1px solid var(--border-default)', paddingTop: 10 }}>
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              style={{
                display: 'flex', alignItems: 'center', gap: 5, padding: '6px 14px', fontSize: 11, fontWeight: 600,
                borderRadius: 6, border: 'none', cursor: 'pointer',
                background: tab === t.key ? 'var(--accent)' : 'var(--bg-elevated)',
                color: tab === t.key ? '#fff' : 'var(--text-secondary)',
                transition: 'all 0.15s',
              }}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="card" style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        {tab === 'discover' && <DiscoveryTab />}
        {tab === 'synthesis' && <SynthesisTab />}
        {tab === 'biosensor' && <BiosensorSuggestorTab />}
        {tab === 'identify' && <IdentifyTab />}
      </div>
    </div>
  );
}
