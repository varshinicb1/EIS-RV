import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Cpu, BookOpen, Activity, Database, FileText, Play, Square,
  RefreshCcw, Loader2, CheckCircle2, AlertTriangle, ChevronDown,
  ChevronRight, Zap, Target, BarChart2, FlaskConical, Network,
  Download, ExternalLink, Filter, Search, ArrowUpDown, Beaker,
  Layers, Info, Clock, TrendingUp, Award, Microscope,
} from 'lucide-react';

const API = '';

async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Shared micro-components ────────────────────────────────────────────────

function Pill({ label, color = '#6b7280', small = false }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: small ? '1px 7px' : '2px 10px',
      borderRadius: 12,
      fontSize: small ? 9 : 10,
      fontWeight: 700,
      letterSpacing: 0.4,
      background: `${color}22`,
      color,
      border: `1px solid ${color}44`,
      marginRight: 4,
      whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  );
}

function StatCard({ icon: Icon, label, value, sub, color = 'var(--color-accent)' }) {
  return (
    <div style={{
      flex: 1, minWidth: 120,
      padding: '14px 16px',
      background: 'var(--bg-primary)',
      border: '1px solid var(--border-primary)',
      borderRadius: 8,
      borderTop: `3px solid ${color}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <Icon size={14} color={color} />
        <span style={{ fontSize: 10, color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</span>
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1 }}>{value ?? '—'}</div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function ScoreBar({ value, max = 1 }) {
  const pct = Math.round(((value || 0) / max) * 100);
  const color = pct >= 70 ? '#22c55e' : pct >= 45 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 5, background: 'var(--border-primary)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 3, transition: 'width 0.4s' }} />
      </div>
      <span style={{ fontSize: 10, color, fontWeight: 700, minWidth: 28, textAlign: 'right' }}>{pct}%</span>
    </div>
  );
}

function Tab({ label, icon: Icon, active, onClick, badge }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '8px 16px',
      fontSize: 12, fontWeight: active ? 700 : 500,
      color: active ? 'var(--color-accent)' : 'var(--text-secondary)',
      background: active ? 'var(--color-accent)15' : 'transparent',
      border: 'none', borderBottom: active ? '2px solid var(--color-accent)' : '2px solid transparent',
      cursor: 'pointer', whiteSpace: 'nowrap',
    }}>
      <Icon size={13} />
      {label}
      {badge != null && (
        <span style={{
          background: 'var(--color-accent)', color: '#fff',
          borderRadius: 8, fontSize: 9, fontWeight: 700,
          padding: '1px 5px', lineHeight: 1.4,
        }}>{badge}</span>
      )}
    </button>
  );
}

function EmptyState({ icon: Icon, title, sub }) {
  return (
    <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-secondary)' }}>
      <Icon size={40} strokeWidth={1.2} style={{ opacity: 0.35, marginBottom: 12 }} />
      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 12 }}>{sub}</div>
    </div>
  );
}

// ── Analyte tag colours ────────────────────────────────────────────────────

const ANALYTE_COLORS = {
  formaldehyde: '#f97316', formalin: '#f97316', hcho: '#f97316',
  'pb2+': '#8b5cf6', 'cd2+': '#3b82f6', 'hg2+': '#ef4444',
  'cu2+': '#f59e0b', 'as3+': '#10b981', 'cr6+': '#ec4899',
  'zn2+': '#06b6d4', 'ni2+': '#a855f7',
};

function analyteColor(analyte) {
  const k = (analyte || '').toLowerCase();
  for (const [key, col] of Object.entries(ANALYTE_COLORS)) {
    if (k.includes(key)) return col;
  }
  return '#6b7280';
}

// ══════════════════════════════════════════════════════════════════════════
//  PAPER CARD
// ══════════════════════════════════════════════════════════════════════════

function PaperCard({ paper, onRecipe }) {
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const acol = analyteColor(paper.analyte);
  const q1   = paper.quartile === 'Q1';

  return (
    <div style={{
      background: 'var(--bg-primary)',
      border: '1px solid var(--border-primary)',
      borderRadius: 8,
      borderLeft: `3px solid ${acol}`,
      padding: '12px 14px',
      marginBottom: 8,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 4 }}>
            <span style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--text-secondary)', background: 'var(--bg-secondary)', padding: '1px 6px', borderRadius: 4 }}>{paper.id}</span>
            {q1 && <Pill label="Q1" color="#22c55e" small />}
            <Pill label={paper.analyte} color={acol} small />
            <Pill label={paper.technique} color="#6366f1" small />
          </div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.35, marginBottom: 4 }}>
            {paper.title}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
            {paper.journal} · {paper.year}
            {paper.impact_factor && <span style={{ color: '#f59e0b', marginLeft: 6 }}>IF {paper.impact_factor}</span>}
          </div>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          {paper.detection_limit_nM != null && (
            <div style={{ fontSize: 11 }}>
              <span style={{ color: 'var(--text-secondary)' }}>LoD </span>
              <span style={{ fontWeight: 700, color: acol }}>{paper.detection_limit_nM} nM</span>
            </div>
          )}
          {paper.sensitivity_uA_uM_cm2 != null && (
            <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>
              {paper.sensitivity_uA_uM_cm2} µA/µM/cm²
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
          <Beaker size={10} style={{ verticalAlign: 'middle', marginRight: 3 }} />
          {paper.electrode_material}
        </span>
        {paper.real_sample && (
          <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
            <Target size={10} style={{ verticalAlign: 'middle', marginRight: 3 }} />
            {paper.real_sample}
          </span>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button onClick={() => setExpanded(e => !e)} style={{
            fontSize: 10, padding: '2px 8px', borderRadius: 4,
            border: '1px solid var(--border-primary)',
            background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer',
          }}>
            {expanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />} Details
          </button>
          <button
            onClick={async () => { setLoading(true); await onRecipe(paper.id); setLoading(false); }}
            disabled={loading}
            style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 4,
              border: '1px solid var(--color-accent)44',
              background: 'var(--color-accent)15', color: 'var(--color-accent)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 4,
            }}
          >
            {loading ? <Loader2 size={9} className="spin" /> : <Zap size={9} />}
            Recipe
          </button>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border-primary)', fontSize: 11 }}>
          <div style={{ marginBottom: 4 }}>
            <span style={{ color: 'var(--text-secondary)' }}>Synthesis: </span>
            <span style={{ color: 'var(--text-primary)' }}>{paper.synthesis_method} @ {paper.synthesis_temperature_C}°C / {paper.synthesis_time_h}h</span>
          </div>
          {paper.precursors_inventory?.length > 0 && (
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: 'var(--text-secondary)' }}>Precursors: </span>
              <span style={{ color: 'var(--text-primary)' }}>{paper.precursors_inventory.join(', ')}</span>
            </div>
          )}
          {paper.key_finding && (
            <div style={{ background: 'var(--bg-secondary)', padding: '6px 10px', borderRadius: 4, marginTop: 6, color: 'var(--text-secondary)', fontStyle: 'italic' }}>
              ❝ {paper.key_finding} ❞
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
//  RECIPE MODAL
// ══════════════════════════════════════════════════════════════════════════

function RecipeModal({ paperId, recipe, onClose }) {
  if (!recipe) return null;
  const steps = Array.isArray(recipe.steps) ? recipe.steps : [];
  const chems = Array.isArray(recipe.chemicals_needed) ? recipe.chemicals_needed : [];
  const equip = Array.isArray(recipe.equipment_needed) ? recipe.equipment_needed : [];
  const warns = Array.isArray(recipe.safety_warnings) ? recipe.safety_warnings : [];

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
      zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 20,
    }} onClick={onClose}>
      <div style={{
        background: 'var(--bg-primary)', borderRadius: 12, maxWidth: 720, width: '100%',
        maxHeight: '85vh', overflowY: 'auto',
        border: '1px solid var(--border-primary)', padding: 24,
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              Replication Recipe — {paperId}
            </div>
            {recipe.estimated_time_hours && (
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                <Clock size={10} style={{ verticalAlign: 'middle', marginRight: 3 }} />
                Estimated time: {recipe.estimated_time_hours} hours
              </div>
            )}
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 18 }}>✕</button>
        </div>

        {warns.length > 0 && (
          <div style={{ background: '#fef3c740', border: '1px solid #f59e0b44', borderRadius: 6, padding: '8px 12px', marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b', marginBottom: 4 }}>
              <AlertTriangle size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Safety Warnings
            </div>
            {warns.map((w, i) => <div key={i} style={{ fontSize: 11, color: '#b45309', marginBottom: 2 }}>• {w}</div>)}
          </div>
        )}

        {chems.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Chemicals Required</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 6 }}>
              {chems.map((c, i) => (
                <div key={i} style={{ background: 'var(--bg-secondary)', borderRadius: 5, padding: '5px 10px', fontSize: 11 }}>
                  <span style={{ fontWeight: 600 }}>{c.name || c}</span>
                  {c.amount && <span style={{ color: 'var(--text-secondary)', marginLeft: 6 }}>{c.amount}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {steps.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>Protocol Steps</div>
            {steps.map((step, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 8 }}>
                <span style={{
                  flexShrink: 0, width: 22, height: 22, borderRadius: '50%',
                  background: 'var(--color-accent)', color: '#fff',
                  fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>{i + 1}</span>
                <span style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.45, paddingTop: 2 }}>{step}</span>
              </div>
            ))}
          </div>
        )}

        {recipe.expected_outcome && (
          <div style={{ background: '#dcfce740', border: '1px solid #22c55e44', borderRadius: 6, padding: '8px 12px', fontSize: 11, color: '#16a34a' }}>
            <CheckCircle2 size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            <strong>Expected outcome:</strong> {recipe.expected_outcome}
          </div>
        )}

        {recipe.raw && (
          <pre style={{ fontSize: 10, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', background: 'var(--bg-secondary)', padding: 12, borderRadius: 6, marginTop: 10 }}>
            {recipe.raw}
          </pre>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
//  DISCOVERY CARD
// ══════════════════════════════════════════════════════════════════════════

function DiscoveryCard({ disc, onReport }) {
  const acol = analyteColor(disc.analyte);
  return (
    <div style={{
      background: 'var(--bg-primary)',
      border: '1px solid var(--border-primary)',
      borderRadius: 8,
      borderLeft: `3px solid ${acol}`,
      padding: '12px 14px',
      marginBottom: 8,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>{disc.material}</div>
          <Pill label={disc.analyte} color={acol} small />
          {disc.nim_validated && <Pill label="NIM ✓" color="#22c55e" small />}
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Score</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: disc.overall_score >= 0.7 ? '#22c55e' : disc.overall_score >= 0.45 ? '#f59e0b' : '#ef4444' }}>
            {(disc.overall_score * 100).toFixed(0)}
          </div>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 8 }}>
        <div style={{ fontSize: 10 }}>
          <span style={{ color: 'var(--text-secondary)' }}>LoD </span>
          <span style={{ fontWeight: 700, color: acol }}>{disc.predicted_lod_nM?.toFixed(3)} nM</span>
        </div>
        <div style={{ fontSize: 10 }}>
          <span style={{ color: 'var(--text-secondary)' }}>Sensitivity </span>
          <span style={{ fontWeight: 600 }}>{disc.predicted_sensitivity?.toFixed(2)} µA/µM/cm²</span>
        </div>
        <div style={{ fontSize: 10 }}>
          <span style={{ color: 'var(--text-secondary)' }}>Rct </span>
          <span>{disc.rct_ohm?.toFixed(1)} Ω</span>
        </div>
        <div style={{ fontSize: 10 }}>
          <span style={{ color: 'var(--text-secondary)' }}>Feasibility </span>
          <span>{((disc.synthesis_feasibility || 0) * 100).toFixed(0)}%</span>
        </div>
      </div>
      <ScoreBar value={disc.overall_score} />
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
        <button onClick={() => onReport(disc.material, disc.analyte)} style={{
          fontSize: 10, padding: '3px 10px', borderRadius: 4,
          border: '1px solid var(--color-accent)44',
          background: 'var(--color-accent)15', color: 'var(--color-accent)',
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
        }}>
          <FileText size={9} /> Generate Q1 Report
        </button>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
//  MAIN PANEL
// ══════════════════════════════════════════════════════════════════════════

export default function AutonomousLabPanel() {
  const [activeTab,    setActiveTab]    = useState('papers');
  const [status,       setStatus]       = useState(null);
  const [papers,       setPapers]       = useState([]);
  const [discoveries,  setDiscoveries]  = useState([]);
  const [loopStatus,   setLoopStatus]   = useState(null);
  const [ingestStatus, setIngestStatus] = useState(null);
  const [loading,      setLoading]      = useState({});
  const [error,        setError]        = useState(null);
  const [recipe,       setRecipe]       = useState(null);
  const [recipeId,     setRecipeId]     = useState(null);
  const [reportFrame,  setReportFrame]  = useState(null);
  const [reportMeta,   setReportMeta]   = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [paperFilter,  setPaperFilter]  = useState('');
  const [analyteFilter, setAnalyteFilter] = useState('all');
  const [validateForm, setValidateForm] = useState({ material: '', analyte: 'formaldehyde' });
  const [validateResult, setValidateResult] = useState(null);
  const [reportForm,   setReportForm]   = useState({ material: '', analyte: 'formaldehyde', title: '' });
  const pollRef = useRef(null);

  const setLoad = (k, v) => setLoading(prev => ({ ...prev, [k]: v }));

  // ── Initial load ────────────────────────────────────────────────────────

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api('/api/v2/brain/status');
      setStatus(s);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  const fetchPapers = useCallback(async () => {
    try {
      setLoad('papers', true);
      const r = await api('/api/v2/brain/papers?limit=105');
      setPapers(r.papers || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoad('papers', false);
    }
  }, []);

  const fetchDiscoveries = useCallback(async () => {
    try {
      setLoad('discoveries', true);
      const q = analyteFilter !== 'all' ? `&analyte=${encodeURIComponent(analyteFilter)}` : '';
      const r = await api(`/api/v2/brain/discoveries?n=100${q}`);
      setDiscoveries(r.candidates || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoad('discoveries', false);
    }
  }, [analyteFilter]);

  const fetchLoopStatus = useCallback(async () => {
    try {
      const r = await api('/api/v2/brain/loop/status');
      setLoopStatus(r);
    } catch (e) { /* silent */ }
  }, []);

  const fetchIngestStatus = useCallback(async () => {
    try {
      const r = await api('/api/v2/brain/ingest/status');
      setIngestStatus(r);
    } catch (e) { /* silent */ }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchPapers();
    fetchLoopStatus();
    fetchIngestStatus();
  }, []);

  useEffect(() => {
    if (activeTab === 'discoveries') fetchDiscoveries();
  }, [activeTab, analyteFilter]);

  // ── Polling while loop or ingest is running ──────────────────────────────

  useEffect(() => {
    const isActive = loopStatus?.running || ingestStatus?.running;
    if (isActive) {
      pollRef.current = setInterval(() => {
        fetchLoopStatus();
        fetchIngestStatus();
        fetchStatus();
        if (activeTab === 'discoveries') fetchDiscoveries();
      }, 2500);
    } else {
      clearInterval(pollRef.current);
    }
    return () => clearInterval(pollRef.current);
  }, [loopStatus?.running, ingestStatus?.running, activeTab]);

  // ── Actions ──────────────────────────────────────────────────────────────

  const handleIngestStart = async (withRecipes) => {
    setLoad('ingest', true); setError(null);
    try {
      await api('/api/v2/brain/ingest/start', {
        method: 'POST',
        body: JSON.stringify({ generate_recipes: withRecipes }),
      });
      setTimeout(() => { fetchIngestStatus(); setLoad('ingest', false); }, 500);
    } catch (e) { setError(e.message); setLoad('ingest', false); }
  };

  const handleLoopStart = async () => {
    setLoad('loop', true); setError(null);
    try {
      await api('/api/v2/brain/loop/start', { method: 'POST', body: JSON.stringify({ max_iterations: 0 }) });
      setTimeout(() => { fetchLoopStatus(); setLoad('loop', false); }, 400);
    } catch (e) { setError(e.message); setLoad('loop', false); }
  };

  const handleLoopStop = async () => {
    setLoad('loopStop', true);
    try {
      await api('/api/v2/brain/loop/stop', { method: 'POST' });
      setTimeout(() => { fetchLoopStatus(); setLoad('loopStop', false); }, 400);
    } catch (e) { setLoad('loopStop', false); }
  };

  const handleGetRecipe = async (paperId) => {
    setError(null);
    try {
      // Try to get existing recipe first
      const r = await api(`/api/v2/brain/papers/${paperId}/recipe`).catch(async () => {
        // If not found, ingest it first
        await api(`/api/v2/brain/ingest/${paperId}`, { method: 'POST' });
        return api(`/api/v2/brain/papers/${paperId}/recipe`);
      });
      setRecipe(r.recipe);
      setRecipeId(paperId);
    } catch (e) {
      setError(`Recipe not available for ${paperId}: ${e.message}`);
    }
  };

  const handleValidate = async () => {
    if (!validateForm.material || !validateForm.analyte) return;
    setLoad('validate', true); setValidateResult(null);
    try {
      const r = await api('/api/v2/brain/validate', {
        method: 'POST',
        body: JSON.stringify({
          material: validateForm.material,
          analyte:  validateForm.analyte,
          ecsa_multiplier: 1.5,
          synthesis_feasibility: 0.75,
        }),
      });
      setValidateResult(r);
    } catch (e) { setError(e.message); } finally { setLoad('validate', false); }
  };

  const handleGenerateReport = async (mat, ana, title) => {
    const material = mat || reportForm.material;
    const analyte  = ana || reportForm.analyte;
    if (!material || !analyte) return;
    setReportLoading(true); setReportFrame(null); setReportMeta(null); setError(null);
    setActiveTab('reports');
    try {
      const r = await api('/api/v2/brain/report/generate', {
        method: 'POST',
        body: JSON.stringify({ material, analyte, title: title || reportForm.title || null }),
      });
      setReportMeta(r);
      setReportFrame(r.html_url);
    } catch (e) { setError(e.message); } finally { setReportLoading(false); }
  };

  // ── Derived state ─────────────────────────────────────────────────────

  const filteredPapers = papers.filter(p => {
    const q = paperFilter.toLowerCase();
    if (!q) return true;
    return (
      p.title?.toLowerCase().includes(q) ||
      p.analyte?.toLowerCase().includes(q) ||
      p.electrode_material?.toLowerCase().includes(q) ||
      p.journal?.toLowerCase().includes(q)
    );
  });

  const loopRunning   = loopStatus?.running;
  const ingestRunning = ingestStatus?.running;

  // ════════════════════════════════════════════════════════════════════════
  //  RENDER
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-secondary)', overflow: 'hidden' }}>

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div style={{
        padding: '14px 20px 0',
        background: 'var(--bg-primary)',
        borderBottom: '1px solid var(--border-primary)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <Cpu size={20} color="var(--color-accent)" />
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1 }}>
              Autonomous Digital Twin Lab Brain
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>
              24/7 self-improving discovery · formalin + heavy metals · physics-validated · Q1 reports
            </div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
            {loopRunning && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#22c55e', fontWeight: 700 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e', animation: 'pulse 1.5s infinite' }} />
                LOOP ACTIVE
              </span>
            )}
            <button onClick={() => { fetchStatus(); fetchPapers(); fetchLoopStatus(); fetchDiscoveries(); }} style={{
              background: 'none', border: '1px solid var(--border-primary)',
              borderRadius: 6, padding: '4px 8px', cursor: 'pointer', color: 'var(--text-secondary)',
              display: 'flex', alignItems: 'center', gap: 4, fontSize: 11,
            }}>
              <RefreshCcw size={11} /> Refresh
            </button>
          </div>
        </div>

        {/* Stats row */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
          <StatCard icon={BookOpen} label="Papers" value={status?.papers_available ?? papers.length}
            sub={`${status?.papers_ingested ?? 0} ingested`} color="#6366f1" />
          <StatCard icon={Network} label="Discoveries" value={status?.discoveries_total ?? discoveries.length}
            sub="candidates scored" color="#22c55e" />
          <StatCard icon={Activity} label="Loop" value={loopStatus?.iteration ?? 0}
            sub={loopRunning ? '● running' : '○ idle'} color={loopRunning ? '#22c55e' : '#6b7280'} />
          <StatCard icon={TrendingUp} label="Best LoD" value={loopStatus?.best_lod_nM ? `${loopStatus.best_lod_nM.toFixed(2)} nM` : '—'}
            sub={loopStatus?.best_material || 'no result yet'} color="#f59e0b" />
        </div>

        {/* Error banner */}
        {error && (
          <div style={{ fontSize: 11, color: '#ef4444', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6, padding: '6px 12px', marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
            <span><AlertTriangle size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />{error}</span>
            <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444' }}>✕</button>
          </div>
        )}

        {/* Tab bar */}
        <div style={{ display: 'flex', gap: 0, overflowX: 'auto' }}>
          <Tab label="Literature" icon={BookOpen} active={activeTab === 'papers'} onClick={() => setActiveTab('papers')} badge={papers.length || null} />
          <Tab label="Discovery Loop" icon={Activity} active={activeTab === 'loop'} onClick={() => setActiveTab('loop')}
            badge={loopRunning ? '●' : null} />
          <Tab label="Discoveries" icon={Database} active={activeTab === 'discoveries'} onClick={() => { setActiveTab('discoveries'); fetchDiscoveries(); }}
            badge={discoveries.length || null} />
          <Tab label="Validate" icon={Microscope} active={activeTab === 'validate'} onClick={() => setActiveTab('validate')} />
          <Tab label="Q1 Reports" icon={FileText} active={activeTab === 'reports'} onClick={() => setActiveTab('reports')} />
        </div>
      </div>

      {/* ── Content ──────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>

        {/* ── PAPERS TAB ─────────────────────────────────────────── */}
        {activeTab === 'papers' && (
          <div>
            {/* Controls */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Ingest All 105 Papers</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button
                    onClick={() => handleIngestStart(true)}
                    disabled={ingestRunning || loading.ingest}
                    style={{
                      padding: '8px 16px', borderRadius: 6, border: 'none', cursor: 'pointer',
                      background: 'var(--color-accent)', color: '#fff', fontWeight: 700, fontSize: 12,
                      display: 'flex', alignItems: 'center', gap: 6, opacity: (ingestRunning || loading.ingest) ? 0.6 : 1,
                    }}
                  >
                    {(ingestRunning || loading.ingest) ? <Loader2 size={13} className="spin" /> : <Zap size={13} />}
                    Ingest + Generate Recipes (NIM)
                  </button>
                  <button
                    onClick={() => handleIngestStart(false)}
                    disabled={ingestRunning || loading.ingest}
                    style={{
                      padding: '8px 14px', borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 12,
                      border: '1px solid var(--border-primary)', background: 'var(--bg-primary)',
                      color: 'var(--text-secondary)',
                      display: 'flex', alignItems: 'center', gap: 6, opacity: (ingestRunning || loading.ingest) ? 0.6 : 1,
                    }}
                  >
                    <BookOpen size={13} /> Ingest Metadata Only
                  </button>
                </div>
              </div>

              {/* Progress */}
              {ingestRunning && ingestStatus && (
                <div style={{ flex: 1, minWidth: 200 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 4 }}>
                    Ingesting {ingestStatus.current || '…'} ({ingestStatus.progress}/{ingestStatus.total})
                  </div>
                  <div style={{ height: 6, background: 'var(--border-primary)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', borderRadius: 3, background: 'var(--color-accent)',
                      width: `${ingestStatus.total > 0 ? (ingestStatus.progress / ingestStatus.total) * 100 : 0}%`,
                      transition: 'width 0.3s',
                    }} />
                  </div>
                </div>
              )}

              {ingestStatus?.result && !ingestRunning && (
                <div style={{ fontSize: 11, color: '#22c55e', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <CheckCircle2 size={13} />
                  {ingestStatus.result.ingested} papers ingested · {ingestStatus.result.recipes_generated} recipes generated
                </div>
              )}
            </div>

            {/* Search + filter */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center' }}>
              <div style={{ flex: 1, position: 'relative' }}>
                <Search size={12} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                <input
                  value={paperFilter} onChange={e => setPaperFilter(e.target.value)}
                  placeholder="Search papers by title, analyte, material, journal…"
                  style={{
                    width: '100%', padding: '7px 12px 7px 30px', borderRadius: 6, fontSize: 12,
                    border: '1px solid var(--border-primary)', background: 'var(--bg-primary)', color: 'var(--text-primary)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                {filteredPapers.length} / {papers.length} papers
              </div>
            </div>

            {loading.papers && <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}><Loader2 size={22} className="spin" /></div>}

            {!loading.papers && filteredPapers.length === 0 && (
              <EmptyState icon={BookOpen} title="No papers loaded" sub="Click 'Ingest + Generate Recipes' to populate the literature database" />
            )}

            {filteredPapers.map(p => (
              <PaperCard key={p.id} paper={p} onRecipe={handleGetRecipe} />
            ))}
          </div>
        )}

        {/* ── LOOP TAB ─────────────────────────────────────────────── */}
        {activeTab === 'loop' && (
          <div>
            {/* Loop controls */}
            <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', borderRadius: 10, padding: 18, marginBottom: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>24/7 Autonomous Discovery Loop</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 14 }}>
                Continuously tests all combinations from the 121-chemical inventory against 8 analytes.
                Each candidate is scored with Randles-Ševčík + Butler-Volmer physics.
                Runs in the background — safe to navigate away.
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <button
                  onClick={handleLoopStart}
                  disabled={loopRunning || loading.loop}
                  style={{
                    padding: '9px 20px', borderRadius: 7, border: 'none', cursor: 'pointer',
                    background: '#22c55e', color: '#fff', fontWeight: 700, fontSize: 13,
                    display: 'flex', alignItems: 'center', gap: 7,
                    opacity: (loopRunning || loading.loop) ? 0.6 : 1,
                  }}
                >
                  {loading.loop ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
                  Start Discovery Loop
                </button>
                <button
                  onClick={handleLoopStop}
                  disabled={!loopRunning || loading.loopStop}
                  style={{
                    padding: '9px 18px', borderRadius: 7, cursor: 'pointer', fontWeight: 600, fontSize: 13,
                    border: '1px solid #ef444444', background: '#ef444415', color: '#ef4444',
                    display: 'flex', alignItems: 'center', gap: 7,
                    opacity: !loopRunning ? 0.4 : 1,
                  }}
                >
                  {loading.loopStop ? <Loader2 size={14} className="spin" /> : <Square size={14} />}
                  Stop
                </button>
                <button onClick={fetchLoopStatus} style={{ background: 'none', border: '1px solid var(--border-primary)', borderRadius: 6, padding: '7px 12px', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <RefreshCcw size={11} /> Refresh
                </button>
              </div>
            </div>

            {/* Live stats */}
            {loopStatus && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: 10, marginBottom: 16 }}>
                  <StatCard icon={Activity} label="Iteration" value={loopStatus.iteration} color="#6366f1" />
                  <StatCard icon={Layers} label="Tested" value={loopStatus.candidates_tested} sub="combinations" color="#3b82f6" />
                  <StatCard icon={CheckCircle2} label="Validated" value={loopStatus.validated} sub="scored ≥ 0.25" color="#22c55e" />
                  <StatCard icon={AlertTriangle} label="Discarded" value={loopStatus.discarded} sub="score < 0.25" color="#6b7280" />
                </div>

                {loopStatus.best_lod_nM != null && (
                  <div style={{ background: 'linear-gradient(135deg, #fef3c720, #dcfce720)', border: '1px solid #22c55e44', borderRadius: 10, padding: 14, marginBottom: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <Award size={16} color="#22c55e" />
                      <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>Best Discovery So Far</span>
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>{loopStatus.best_material}</div>
                    <div style={{ display: 'flex', gap: 16 }}>
                      <div style={{ fontSize: 11 }}>
                        <span style={{ color: 'var(--text-secondary)' }}>LoD: </span>
                        <span style={{ fontWeight: 700, color: '#22c55e' }}>{loopStatus.best_lod_nM?.toFixed(3)} nM</span>
                      </div>
                      {loopStatus.top_discovery && (
                        <>
                          <div style={{ fontSize: 11 }}>
                            <span style={{ color: 'var(--text-secondary)' }}>Analyte: </span>
                            <span>{loopStatus.top_discovery.analyte}</span>
                          </div>
                          <div style={{ fontSize: 11 }}>
                            <span style={{ color: 'var(--text-secondary)' }}>Score: </span>
                            <span style={{ fontWeight: 700 }}>{((loopStatus.top_discovery.score || 0) * 100).toFixed(0)}%</span>
                          </div>
                        </>
                      )}
                    </div>
                    {loopStatus.top_discovery && (
                      <button
                        onClick={() => handleGenerateReport(loopStatus.best_material, loopStatus.top_discovery.analyte)}
                        style={{ marginTop: 10, padding: '5px 14px', borderRadius: 5, fontSize: 11, fontWeight: 600, border: '1px solid #22c55e44', background: '#22c55e15', color: '#22c55e', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
                        <FileText size={11} /> Generate Q1 Report for this candidate
                      </button>
                    )}
                  </div>
                )}

                {loopRunning && loopStatus.current_material && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', borderRadius: 8, fontSize: 11 }}>
                    <Loader2 size={13} className="spin" color="var(--color-accent)" />
                    <span style={{ color: 'var(--text-secondary)' }}>Currently testing:</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{loopStatus.current_material}</span>
                    <span style={{ color: 'var(--text-secondary)' }}>→</span>
                    <Pill label={loopStatus.current_analyte} color={analyteColor(loopStatus.current_analyte)} small />
                  </div>
                )}

                <div style={{ marginTop: 14, fontSize: 11, color: 'var(--text-secondary)' }}>
                  <Info size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                  Target analytes: {['formaldehyde', 'Pb²⁺', 'Cd²⁺', 'Hg²⁺', 'Cu²⁺', 'As³⁺', 'Cr⁶⁺', 'Zn²⁺'].join(' · ')}
                </div>
              </>
            )}

            {!loopStatus && (
              <EmptyState icon={Activity} title="Loop not started" sub="Click 'Start Discovery Loop' to begin 24/7 combinatorial synthesis" />
            )}
          </div>
        )}

        {/* ── DISCOVERIES TAB ──────────────────────────────────────── */}
        {activeTab === 'discoveries' && (
          <div>
            <div style={{ display: 'flex', gap: 10, marginBottom: 14, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', flex: 1 }}>Top Validated Candidates</div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <Filter size={12} color="var(--text-secondary)" />
                <select
                  value={analyteFilter} onChange={e => setAnalyteFilter(e.target.value)}
                  style={{ padding: '5px 8px', borderRadius: 5, border: '1px solid var(--border-primary)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 11, cursor: 'pointer' }}
                >
                  <option value="all">All analytes</option>
                  {['formaldehyde', 'Pb2+', 'Cd2+', 'Hg2+', 'Cu2+', 'As3+', 'Cr6+', 'Zn2+'].map(a => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
                <button onClick={fetchDiscoveries} style={{ background: 'none', border: '1px solid var(--border-primary)', borderRadius: 5, padding: '5px 10px', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <RefreshCcw size={10} /> Refresh
                </button>
              </div>
            </div>

            {loading.discoveries && <div style={{ textAlign: 'center', padding: 40 }}><Loader2 size={22} className="spin" color="var(--text-secondary)" /></div>}

            {!loading.discoveries && discoveries.length === 0 && (
              <EmptyState icon={Database} title="No discoveries yet"
                sub="Start the Discovery Loop to generate candidates, or run physics validation on a specific material" />
            )}

            {!loading.discoveries && discoveries.map((d, i) => (
              <DiscoveryCard key={d.id || i} disc={d} onReport={handleGenerateReport} />
            ))}
          </div>
        )}

        {/* ── VALIDATE TAB ─────────────────────────────────────────── */}
        {activeTab === 'validate' && (
          <div>
            <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', borderRadius: 10, padding: 18, marginBottom: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                Physics Validation — Custom Material
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 14 }}>
                Input any electrode material. The engine applies Randles-Ševčík, Butler-Volmer, Cottrell, and LoD = 3σ/S equations to predict electrochemical performance.
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 10, alignItems: 'flex-end', marginBottom: 14 }}>
                <div>
                  <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Electrode Material</label>
                  <input
                    value={validateForm.material} onChange={e => setValidateForm(f => ({ ...f, material: e.target.value }))}
                    placeholder="e.g. NiCo2O4/rGO, MnO2/CNT…"
                    style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Target Analyte</label>
                  <select
                    value={validateForm.analyte} onChange={e => setValidateForm(f => ({ ...f, analyte: e.target.value }))}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: 12, cursor: 'pointer', boxSizing: 'border-box' }}
                  >
                    {['formaldehyde', 'Pb2+', 'Cd2+', 'Hg2+', 'Cu2+', 'As3+', 'Cr6+', 'Zn2+', 'Ni2+'].map(a => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleValidate}
                  disabled={!validateForm.material || loading.validate}
                  style={{
                    padding: '8px 18px', borderRadius: 6, border: 'none', cursor: 'pointer',
                    background: 'var(--color-accent)', color: '#fff', fontWeight: 700, fontSize: 12,
                    display: 'flex', alignItems: 'center', gap: 6, height: 36,
                    opacity: !validateForm.material ? 0.5 : 1,
                  }}
                >
                  {loading.validate ? <Loader2 size={13} className="spin" /> : <Zap size={13} />}
                  Validate
                </button>
              </div>

              {/* Physics equations used */}
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', background: 'var(--bg-secondary)', padding: '8px 12px', borderRadius: 6 }}>
                <span style={{ fontWeight: 600 }}>Equations applied: </span>
                Randles-Ševčík · Butler-Volmer · Cottrell · Nernst · LoD=3σ/S (IUPAC 1995) · Randles EIS circuit
              </div>
            </div>

            {validateResult && (
              <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', borderRadius: 10, padding: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{validateResult.material}</div>
                    <Pill label={validateResult.analyte} color={analyteColor(validateResult.analyte)} />
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Overall Score</div>
                    <div style={{ fontSize: 28, fontWeight: 800, color: validateResult.overall_score >= 0.7 ? '#22c55e' : validateResult.overall_score >= 0.45 ? '#f59e0b' : '#ef4444', lineHeight: 1 }}>
                      {(validateResult.overall_score * 100).toFixed(1)}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 10, marginBottom: 14 }}>
                  {[
                    ['Sensitivity', `${validateResult.sensitivity_uA_uM_cm2} µA/µM/cm²`],
                    ['Limit of Detection', `${validateResult.lod_nM} nM`],
                    ['Peak Current (1 µM)', `${validateResult.peak_current_uA} µA`],
                    ['Rs (electrolyte)', `${validateResult.rs_ohm} Ω`],
                    ['Rct (charge transfer)', `${validateResult.rct_ohm} Ω`],
                    ['Double-layer Cdl', `${validateResult.cdl_uF_cm2} µF/cm²`],
                    ['ECSA', `${validateResult.ecsa_cm2} cm²`],
                    ['Selectivity Score', `${(validateResult.selectivity_score * 100).toFixed(0)}%`],
                  ].map(([label, val]) => (
                    <div key={label} style={{ background: 'var(--bg-secondary)', borderRadius: 6, padding: '8px 12px' }}>
                      <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 3 }}>{label}</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{val}</div>
                    </div>
                  ))}
                </div>

                {validateResult.equations_used?.length > 0 && (
                  <div style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Equations Used</div>
                    {validateResult.equations_used.map((eq, i) => (
                      <div key={i} style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 2 }}>• {eq}</div>
                    ))}
                  </div>
                )}

                <button
                  onClick={() => handleGenerateReport(validateResult.material, validateResult.analyte)}
                  style={{ padding: '7px 16px', borderRadius: 6, fontSize: 12, fontWeight: 700, border: 'none', cursor: 'pointer', background: 'var(--color-accent)', color: '#fff', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <FileText size={12} /> Generate Q1 Report for This Material
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── REPORTS TAB ──────────────────────────────────────────── */}
        {activeTab === 'reports' && (
          <div>
            <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', borderRadius: 10, padding: 18, marginBottom: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                Q1 Report Generator
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 14 }}>
                Generates a publication-quality HTML report with 4 matplotlib figures: CV simulation, EIS Nyquist, calibration curve, and LoD comparison chart.
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
                <div>
                  <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Electrode Material</label>
                  <input
                    value={reportForm.material} onChange={e => setReportForm(f => ({ ...f, material: e.target.value }))}
                    placeholder="e.g. NiCo2O4/rGO"
                    style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Target Analyte</label>
                  <select
                    value={reportForm.analyte} onChange={e => setReportForm(f => ({ ...f, analyte: e.target.value }))}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: 12, cursor: 'pointer', boxSizing: 'border-box' }}
                  >
                    {['formaldehyde', 'Pb2+', 'Cd2+', 'Hg2+', 'Cu2+', 'As3+', 'Cr6+', 'Zn2+'].map(a => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Custom Title (optional)</label>
                <input
                  value={reportForm.title} onChange={e => setReportForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="Leave blank for auto-generated title"
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box' }}
                />
              </div>
              <button
                onClick={() => handleGenerateReport()}
                disabled={!reportForm.material || reportLoading}
                style={{
                  padding: '9px 20px', borderRadius: 7, border: 'none', cursor: 'pointer',
                  background: 'var(--color-accent)', color: '#fff', fontWeight: 700, fontSize: 13,
                  display: 'flex', alignItems: 'center', gap: 7,
                  opacity: !reportForm.material ? 0.5 : 1,
                }}
              >
                {reportLoading ? <Loader2 size={14} className="spin" /> : <BarChart2 size={14} />}
                Generate Q1 Report with 4 Figures
              </button>
            </div>

            {reportLoading && (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-secondary)' }}>
                <Loader2 size={28} className="spin" style={{ marginBottom: 10 }} />
                <div style={{ fontSize: 12 }}>Generating matplotlib figures and building report…</div>
              </div>
            )}

            {reportMeta && !reportLoading && (
              <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', borderRadius: 10, overflow: 'hidden' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid var(--border-primary)' }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
                      {reportMeta.material} → {reportMeta.analyte}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>
                      Report ID: {reportMeta.report_id} · {reportMeta.timestamp?.substring(0, 10)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <a
                      href={reportMeta.html_url} target="_blank" rel="noreferrer"
                      style={{ padding: '5px 12px', borderRadius: 5, fontSize: 11, fontWeight: 600, border: '1px solid var(--color-accent)44', background: 'var(--color-accent)15', color: 'var(--color-accent)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 5 }}
                    >
                      <ExternalLink size={11} /> Open Full Report
                    </a>
                  </div>
                </div>

                {/* Predictions summary */}
                {reportMeta.predictions && (
                  <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border-primary)', display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                    {[
                      ['LoD', `${reportMeta.predictions.lod_nM} nM`],
                      ['Sensitivity', `${reportMeta.predictions.sensitivity_uA_uM_cm2} µA/µM/cm²`],
                      ['Score', `${((reportMeta.predictions.overall_score || 0) * 100).toFixed(1)}%`],
                      ['Rct', `${reportMeta.predictions.rct_ohm} Ω`],
                    ].map(([k, v]) => (
                      <div key={k} style={{ fontSize: 11 }}>
                        <span style={{ color: 'var(--text-secondary)' }}>{k}: </span>
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{v}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Embedded iframe */}
                <iframe
                  src={reportFrame}
                  title="Q1 Report"
                  style={{ width: '100%', height: 700, border: 'none', display: 'block' }}
                />
              </div>
            )}

            {!reportMeta && !reportLoading && (
              <EmptyState icon={FileText} title="No report generated yet"
                sub="Fill in a material and analyte above, then click 'Generate Q1 Report'" />
            )}
          </div>
        )}
      </div>

      {/* Recipe modal */}
      {recipe && (
        <RecipeModal paperId={recipeId} recipe={recipe} onClose={() => { setRecipe(null); setRecipeId(null); }} />
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        .spin { animation: spin 0.8s linear infinite; }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
      `}</style>
    </div>
  );
}
