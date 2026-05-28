import React, { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical, Search, Sparkles, CheckCircle2, AlertTriangle,
  ChevronDown, ChevronRight, Loader2, Info, Send, RefreshCcw,
  BookOpen, Activity, Layers, Target, Beaker, ThumbsUp, ThumbsDown,
  Database, Zap, Network,
} from 'lucide-react';

const API = '';

async function api(endpoint, options = {}) {
  const res = await fetch(`${API}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

const APPLICATIONS = [
  'Supercapacitor electrode (alkaline)',
  'Supercapacitor electrode (neutral)',
  'Li-ion battery anode',
  'Li-ion battery cathode',
  'Photocatalysis (H2 evolution)',
  'Electrochemical glucose sensing',
  'Heavy metal ion detection',
  'Oxygen evolution reaction (OER)',
  'Hydrogen evolution reaction (HER)',
  'Dye degradation (photocatalysis)',
  'Nitrogen reduction (NRR)',
  'CO2 reduction electrocatalysis',
];

const ROLE_COLORS = {
  metal_source: '#3b82f6',
  base: '#8b5cf6',
  acid: '#ef4444',
  surfactant: '#f59e0b',
  reducing_agent: '#10b981',
  oxidizing_agent: '#f97316',
  carbon_source: '#6b7280',
  sulfur_source: '#eab308',
  chelating_agent: '#06b6d4',
  template: '#ec4899',
  nitrogen_source: '#14b8a6',
  structure_directing_agent: '#a855f7',
};

function ConfidenceBar({ value, label }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct >= 70 ? 'var(--color-success)' : pct >= 40 ? '#f59e0b' : 'var(--color-error)';
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2, color: 'var(--text-secondary)' }}>
        <span>{label}</span>
        <span style={{ color, fontWeight: 600 }}>{pct}%</span>
      </div>
      <div style={{ height: 4, background: 'var(--border-primary)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 2, transition: 'width 0.5s ease' }} />
      </div>
    </div>
  );
}

function Tag({ label, color }) {
  return (
    <span style={{
      display: 'inline-block', padding: '1px 8px', borderRadius: 10,
      fontSize: 10, fontWeight: 600, letterSpacing: 0.5,
      background: `${color || '#6b7280'}22`,
      color: color || 'var(--text-secondary)',
      border: `1px solid ${color || '#6b7280'}44`,
      marginRight: 4, marginBottom: 3,
    }}>
      {label.replace(/_/g, ' ').toUpperCase()}
    </span>
  );
}

function ChemicalCard({ chem, compact = false }) {
  const roleColor = ROLE_COLORS[chem.hydrothermal_role?.[0]] || '#6b7280';
  return (
    <div style={{
      padding: compact ? '6px 10px' : '10px 12px',
      background: 'var(--bg-primary)',
      border: '1px solid var(--border-primary)',
      borderRadius: 6,
      borderLeft: `3px solid ${roleColor}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: compact ? 11 : 12, fontWeight: 600, color: 'var(--text-primary)' }}>
            {chem.name}
          </div>
          {!compact && (
            <div style={{ fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'monospace', marginTop: 2 }}>
              {chem.formula}
            </div>
          )}
        </div>
        <CheckCircle2 size={compact ? 10 : 12} color="var(--color-success)" />
      </div>
      {!compact && (
        <div style={{ marginTop: 6 }}>
          {(chem.hydrothermal_role || []).slice(0, 3).map(r => (
            <Tag key={r} label={r} color={ROLE_COLORS[r]} />
          ))}
        </div>
      )}
    </div>
  );
}

function CandidateCard({ candidate, index, onSynthesise, onFeedback }) {
  const [expanded, setExpanded] = useState(index === 0);
  const [synthesising, setSynthesising] = useState(false);
  const [synthRoute, setSynthRoute] = useState(null);
  const [synthError, setSynthError] = useState(null);

  const handleSynthesise = async () => {
    setSynthesising(true);
    setSynthRoute(null);
    setSynthError(null);
    try {
      const result = await api('/api/v2/hydrothermal/synthesize', {
        method: 'POST',
        body: JSON.stringify({
          material: candidate.material,
          application: candidate.application_fit || 'electrochemical',
          scale_mL: 50,
        }),
      });
      setSynthRoute(result);
      if (onSynthesise) onSynthesise(result);
    } catch (e) {
      setSynthError(e.message);
    }
    setSynthesising(false);
  };

  const conf = candidate.confidence || {};
  const feasibilityPct = Math.round((conf.synthesis_feasibility || candidate.synthesis_feasibility || 0) * 100);
  const feasColor = feasibilityPct >= 70 ? 'var(--color-success)' : feasibilityPct >= 40 ? '#f59e0b' : 'var(--color-error)';

  return (
    <div style={{
      border: '1px solid var(--border-primary)',
      borderRadius: 8,
      overflow: 'hidden',
      background: 'var(--bg-secondary)',
      marginBottom: 12,
    }}>
      <div
        onClick={() => setExpanded(e => !e)}
        style={{
          padding: '12px 16px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          background: expanded ? 'var(--bg-primary)' : 'transparent',
        }}
      >
        <div style={{
          width: 28, height: 28, borderRadius: 14,
          background: 'var(--accent)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 700, flexShrink: 0,
        }}>
          {candidate.rank || index + 1}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>
            {candidate.material}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 1 }}>
            {candidate.family} · {candidate.application_fit?.slice(0, 60)}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <div style={{
            padding: '2px 10px', borderRadius: 10, fontSize: 11, fontWeight: 700,
            background: `${feasColor}22`, color: feasColor, border: `1px solid ${feasColor}44`,
          }}>
            {feasibilityPct}% feasible
          </div>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--border-primary)' }}>

          {/* Precursors */}
          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Precursors from Lab Inventory
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
              {(candidate.available_precursors || []).map(p => (
                <div key={p} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
                  <CheckCircle2 size={10} color="var(--color-success)" />
                  <span style={{ color: 'var(--text-primary)' }}>{p}</span>
                </div>
              ))}
              {(candidate.missing_precursors || []).map(p => (
                <div key={p} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
                  <AlertTriangle size={10} color="var(--color-error)" />
                  <span style={{ color: 'var(--color-error)' }}>{p} (procure)</span>
                </div>
              ))}
            </div>
          </div>

          {/* Property estimates */}
          {candidate.property_estimates && (
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Estimated Properties
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
                {candidate.property_estimates.capacitance_F_g != null && (
                  <div style={{ padding: '8px 10px', background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Capacitance</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent)', fontFamily: 'monospace' }}>
                      {candidate.property_estimates.capacitance_F_g} <span style={{ fontSize: 10, fontWeight: 400 }}>F/g</span>
                    </div>
                  </div>
                )}
                {candidate.property_estimates.conductivity_S_cm != null && (
                  <div style={{ padding: '8px 10px', background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Conductivity</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent)', fontFamily: 'monospace' }}>
                      {candidate.property_estimates.conductivity_S_cm} <span style={{ fontSize: 10, fontWeight: 400 }}>S/cm</span>
                    </div>
                  </div>
                )}
                {candidate.property_estimates.band_gap_eV != null && (
                  <div style={{ padding: '8px 10px', background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Band gap</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent)', fontFamily: 'monospace' }}>
                      {candidate.property_estimates.band_gap_eV} <span style={{ fontSize: 10, fontWeight: 400 }}>eV</span>
                    </div>
                  </div>
                )}
              </div>
              {candidate.property_estimates.notes && (
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 6, fontStyle: 'italic' }}>
                  {candidate.property_estimates.notes}
                </div>
              )}
            </div>
          )}

          {/* Confidence */}
          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Confidence Scores
            </div>
            <ConfidenceBar value={conf.synthesis_feasibility} label="Synthesis feasibility" />
            <ConfidenceBar value={conf.phase_purity} label="Phase purity" />
            <ConfidenceBar value={conf.electrochemical_prediction} label="Electrochemical prediction" />
            <ConfidenceBar value={conf.reproducibility} label="Reproducibility" />
          </div>

          {/* Provenance & Warnings */}
          {candidate.provenance && (
            <div style={{ marginTop: 12, padding: '8px 10px', background: '#3b82f611', borderRadius: 6, border: '1px solid #3b82f622' }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: '#3b82f6', marginBottom: 2 }}>PROVENANCE</div>
              <div style={{ fontSize: 11, color: 'var(--text-primary)' }}>{candidate.provenance}</div>
            </div>
          )}
          {(candidate.warnings || []).length > 0 && (
            <div style={{ marginTop: 8, padding: '8px 10px', background: '#f59e0b11', borderRadius: 6, border: '1px solid #f59e0b22' }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: '#f59e0b', marginBottom: 4 }}>WARNINGS</div>
              {candidate.warnings.map((w, i) => (
                <div key={i} style={{ fontSize: 11, color: 'var(--text-primary)', display: 'flex', gap: 6, marginBottom: 2 }}>
                  <AlertTriangle size={10} color="#f59e0b" style={{ flexShrink: 0, marginTop: 1 }} />
                  {w}
                </div>
              ))}
            </div>
          )}

          {/* Assumptions */}
          {(candidate.assumptions || []).length > 0 && (
            <div style={{ marginTop: 8, padding: '8px 10px', background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 4 }}>ASSUMPTIONS</div>
              {candidate.assumptions.map((a, i) => (
                <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 1 }}>· {a}</div>
              ))}
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
            <button
              onClick={handleSynthesise}
              disabled={synthesising}
              style={{
                flex: 1, padding: '8px 12px', borderRadius: 6, border: 'none',
                background: 'var(--accent)', color: '#fff', fontSize: 12,
                fontWeight: 600, cursor: synthesising ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                opacity: synthesising ? 0.7 : 1,
              }}
            >
              {synthesising ? <Loader2 size={12} className="spin" /> : <Beaker size={12} />}
              {synthesising ? 'Planning…' : 'Plan Synthesis Route'}
            </button>
            <button
              onClick={() => onFeedback && onFeedback(candidate, true)}
              style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid var(--color-success)', background: 'transparent', cursor: 'pointer' }}
              title="Mark as successfully synthesised"
            >
              <ThumbsUp size={12} color="var(--color-success)" />
            </button>
            <button
              onClick={() => onFeedback && onFeedback(candidate, false)}
              style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid var(--color-error)', background: 'transparent', cursor: 'pointer' }}
              title="Report synthesis failure"
            >
              <ThumbsDown size={12} color="var(--color-error)" />
            </button>
          </div>

          {/* Synthesis route */}
          {synthError && (
            <div style={{ marginTop: 10, padding: '8px 10px', background: '#ef444411', borderRadius: 6, border: '1px solid #ef444422', fontSize: 11, color: 'var(--color-error)' }}>
              {synthError.includes('503') ? 'Set NVIDIA_API_KEY to generate synthesis routes.' : synthError}
            </div>
          )}
          {synthRoute && !synthRoute.error && (
            <SynthesisRouteView route={synthRoute} />
          )}
        </div>
      )}
    </div>
  );
}

function SynthesisRouteView({ route }) {
  if (!route) return null;
  const cond = route.conditions || {};
  const conf = route.confidence || {};

  return (
    <div style={{ marginTop: 14, padding: 12, background: 'var(--bg-primary)', borderRadius: 8, border: '1px solid var(--border-primary)' }}>
      <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
        <Beaker size={14} color="var(--accent)" />
        Synthesis Route — {route.material}
        <span style={{ marginLeft: 4, fontSize: 10, padding: '2px 8px', borderRadius: 10, background: 'var(--accent)22', color: 'var(--accent)', border: '1px solid var(--accent)44' }}>
          {route.method}
        </span>
      </div>

      {/* Conditions */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 6, marginBottom: 12 }}>
        {[
          { label: 'Temperature', value: `${cond.temperature_C}°C` },
          { label: 'Dwell time', value: `${cond.dwell_time_h}h` },
          { label: 'Volume', value: `${cond.total_volume_mL}mL` },
          { label: 'pH initial', value: cond.pH_initial },
          { label: 'Solvent', value: cond.solvent },
          { label: 'Atmosphere', value: cond.atmosphere },
          { label: 'Fill fraction', value: cond.autoclave_fill_fraction ? `${Math.round(cond.autoclave_fill_fraction*100)}%` : null },
          { label: 'Pressure est.', value: cond.pressure_atm_estimated ? `${cond.pressure_atm_estimated} atm` : null },
        ].filter(i => i.value != null).map(item => (
          <div key={item.label} style={{ padding: '6px 8px', background: 'var(--bg-secondary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
            <div style={{ fontSize: 9, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{item.label}</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'monospace' }}>{item.value}</div>
          </div>
        ))}
      </div>

      {/* Precursors table */}
      {(route.precursors || []).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Precursors</div>
          <div style={{ borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border-primary)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ background: 'var(--bg-secondary)' }}>
                  {['Chemical', 'Role', 'Conc. (mM)', 'Mass (mg/50mL)', '✓'].map(h => (
                    <th key={h} style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)', fontSize: 10 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {route.precursors.map((p, i) => (
                  <tr key={i} style={{ borderTop: '1px solid var(--border-primary)' }}>
                    <td style={{ padding: '5px 8px', color: 'var(--text-primary)', fontWeight: 500 }}>{p.chemical}</td>
                    <td style={{ padding: '5px 8px', color: 'var(--text-secondary)' }}>{p.role}</td>
                    <td style={{ padding: '5px 8px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>{p.concentration_mM}</td>
                    <td style={{ padding: '5px 8px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>{p.mass_mg_per_50mL}</td>
                    <td style={{ padding: '5px 8px' }}>
                      {p.available !== false
                        ? <CheckCircle2 size={11} color="var(--color-success)" />
                        : <AlertTriangle size={11} color="#f59e0b" />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Post-processing */}
      {(route.post_processing || []).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Post-Processing</div>
          {route.post_processing.map((step, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 4, fontSize: 11, alignItems: 'flex-start' }}>
              <div style={{ width: 20, height: 20, borderRadius: 10, background: 'var(--accent)22', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, flexShrink: 0 }}>
                {i + 1}
              </div>
              <div>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{step.step}</span>
                {step.temperature_C && <span style={{ color: 'var(--text-secondary)' }}> · {step.temperature_C}°C</span>}
                {step.duration_h && <span style={{ color: 'var(--text-secondary)' }}> · {step.duration_h}h</span>}
                {step.atmosphere && <span style={{ color: 'var(--text-secondary)' }}> · {step.atmosphere}</span>}
                {step.purpose && <div style={{ color: 'var(--text-secondary)', marginTop: 1 }}>{step.purpose}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Confidence */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Route Confidence</div>
        <ConfidenceBar value={conf.synthesis_feasibility} label="Synthesis feasibility" />
        <ConfidenceBar value={conf.phase_purity} label="Phase purity" />
        <ConfidenceBar value={conf.morphology} label="Morphology prediction" />
        <ConfidenceBar value={conf.reproducibility} label="Reproducibility" />
      </div>

      {/* Expected outputs */}
      {(route.expected_morphology || route.expected_phase) && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {route.expected_morphology && (
            <div style={{ flex: 1, padding: '8px 10px', background: 'var(--bg-secondary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
              <div style={{ fontSize: 9, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 2 }}>Expected morphology</div>
              <div style={{ fontSize: 11, color: 'var(--text-primary)' }}>{route.expected_morphology}</div>
            </div>
          )}
          {route.expected_phase && (
            <div style={{ flex: 1, padding: '8px 10px', background: 'var(--bg-secondary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
              <div style={{ fontSize: 9, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 2 }}>Expected phase</div>
              <div style={{ fontSize: 11, color: 'var(--text-primary)' }}>{route.expected_phase}</div>
            </div>
          )}
        </div>
      )}

      {/* Characterisation checklist */}
      {(route.characterisation_checklist || []).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Characterisation Checklist (HITL Validation)
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {route.characterisation_checklist.map(c => (
              <span key={c} style={{ padding: '3px 10px', borderRadius: 10, border: '1px solid var(--accent)44', color: 'var(--accent)', fontSize: 11, fontWeight: 600 }}>
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Safety */}
      {(route.safety_notes || []).length > 0 && (
        <div style={{ padding: '8px 10px', background: '#ef444411', borderRadius: 6, border: '1px solid #ef444422' }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#ef4444', marginBottom: 4 }}>SAFETY</div>
          {route.safety_notes.map((s, i) => (
            <div key={i} style={{ fontSize: 11, color: 'var(--text-primary)', marginBottom: 1 }}>· {s}</div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function HydrothermalDiscoveryPanel() {
  const [status, setStatus] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [invLoading, setInvLoading] = useState(false);
  const [inventorySearch, setInventorySearch] = useState('');
  const [inventoryCategory, setInventoryCategory] = useState('');
  const [invExpanded, setInvExpanded] = useState(false);

  const [goal, setGoal] = useState('');
  const [customGoal, setCustomGoal] = useState('');
  const [targetProps, setTargetProps] = useState('{\n  "capacitance_F_g": ">300",\n  "stability_cycles": ">5000",\n  "electrolyte": "1M KOH"\n}');
  const [constraints, setConstraints] = useState('{\n  "max_temperature_C": 200,\n  "available_only": true,\n  "avoid_toxic": false\n}');
  const [nCandidates, setNCandidates] = useState(5);

  const [discovering, setDiscovering] = useState(false);
  const [candidates, setCandidates] = useState(null);
  const [discoverError, setDiscoverError] = useState(null);
  const [reasoning, setReasoning] = useState('');

  const [failures, setFailures] = useState([]);
  const [feedbackQueue, setFeedbackQueue] = useState([]);

  const [activeTab, setActiveTab] = useState('discover');

  useEffect(() => {
    api('/api/v2/hydrothermal/status').then(setStatus).catch(() => {});
    api('/api/v2/hydrothermal/failures').then(d => setFailures(d.failures || [])).catch(() => {});
  }, []);

  const loadInventory = useCallback(async () => {
    setInvLoading(true);
    try {
      const params = new URLSearchParams();
      if (inventorySearch) params.set('search', inventorySearch);
      if (inventoryCategory) params.set('category', inventoryCategory);
      const result = await api(`/api/v2/hydrothermal/inventory?${params}`);
      setInventory(result);
    } catch (e) {
      console.error(e);
    }
    setInvLoading(false);
  }, [inventorySearch, inventoryCategory]);

  useEffect(() => {
    if (activeTab === 'inventory') loadInventory();
  }, [activeTab, loadInventory]);

  const handleDiscover = async () => {
    const finalGoal = goal === '__custom__' ? customGoal : goal;
    if (!finalGoal.trim()) return;

    let props = {}, constr = {};
    try { props = JSON.parse(targetProps); } catch {}
    try { constr = JSON.parse(constraints); } catch {}

    setDiscovering(true);
    setCandidates(null);
    setDiscoverError(null);
    setReasoning('');

    try {
      const result = await api('/api/v2/hydrothermal/discover', {
        method: 'POST',
        body: JSON.stringify({ goal: finalGoal, target_properties: props, constraints: constr, n_candidates: nCandidates }),
      });
      if (result.error) {
        setDiscoverError(result.message || result.error);
      } else {
        setCandidates(result.candidates || []);
        setReasoning(result.reasoning || '');
      }
    } catch (e) {
      setDiscoverError(e.message.includes('503') ? 'Set NVIDIA_API_KEY to enable AI discovery. The engine is ready — it just needs an API key.' : e.message);
    }
    setDiscovering(false);
  };

  const handleFeedback = async (candidate, success) => {
    try {
      await api('/api/v2/hydrothermal/feedback', {
        method: 'POST',
        body: JSON.stringify({
          candidate_material: candidate.material,
          experiment_result: success ? 'Synthesis successful' : 'Synthesis failed',
          characterisation: {},
          success,
        }),
      });
      setFeedbackQueue(q => [...q, { material: candidate.material, success, time: new Date().toLocaleTimeString() }]);
      if (!success) {
        api('/api/v2/hydrothermal/failures').then(d => setFailures(d.failures || [])).catch(() => {});
      }
    } catch (e) {
      console.error(e);
    }
  };

  const allCategories = inventory?.categories ? Object.keys(inventory.categories) : [];

  const tabs = [
    { id: 'discover', label: 'Inverse Design', icon: Target },
    { id: 'inventory', label: 'Lab Inventory', icon: Database },
    { id: 'failures', label: `Failures (${failures.length})`, icon: AlertTriangle },
    { id: 'graph', label: 'Knowledge Graph', icon: Network },
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)', overflow: 'hidden' }}>

      {/* Header */}
      <div style={{ padding: '20px 24px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 4 }}>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              <FlaskConical size={18} color="var(--accent)" />
              Autonomous Hydrothermal Discovery
            </h1>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0 0' }}>
              Goal-driven inverse design · Synthesis planning · Verification-first · Confidence-scored
            </p>
          </div>
          {status && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 10px', borderRadius: 6, background: status.nim_configured ? 'var(--color-success)22' : '#f59e0b22', border: `1px solid ${status.nim_configured ? 'var(--color-success)' : '#f59e0b'}44` }}>
                {status.nim_configured
                  ? <CheckCircle2 size={11} color="var(--color-success)" />
                  : <AlertTriangle size={11} color="#f59e0b" />}
                <span style={{ fontSize: 10, fontWeight: 700, color: status.nim_configured ? 'var(--color-success)' : '#f59e0b' }}>
                  {status.nim_configured ? 'NIM ready' : 'NIM: set API key'}
                </span>
              </div>
              <div style={{ padding: '4px 10px', borderRadius: 6, background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)' }}>
                {status.inventory_total} chemicals
              </div>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 2, marginTop: 16, borderBottom: '1px solid var(--border-primary)' }}>
          {tabs.map(t => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                style={{
                  padding: '8px 14px',
                  border: 'none',
                  background: activeTab === t.id ? 'var(--bg-primary)' : 'transparent',
                  color: activeTab === t.id ? 'var(--accent)' : 'var(--text-secondary)',
                  borderBottom: activeTab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
                  cursor: 'pointer',
                  fontSize: 12,
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  borderRadius: '4px 4px 0 0',
                }}
              >
                <Icon size={12} />
                {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>

        {/* ── INVERSE DESIGN TAB ── */}
        {activeTab === 'discover' && (
          <div style={{ maxWidth: 1000, margin: '0 auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: 20 }}>

              {/* Left: Goal input */}
              <div>
                <div style={{ padding: 16, background: 'var(--bg-secondary)', borderRadius: 8, border: '1px solid var(--border-primary)', marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Target size={13} color="var(--accent)" /> Scientific Goal
                  </div>
                  <select
                    value={goal}
                    onChange={e => setGoal(e.target.value)}
                    style={{
                      width: '100%', padding: '8px 10px', borderRadius: 6,
                      border: '1px solid var(--border-primary)',
                      background: 'var(--bg-primary)', color: 'var(--text-primary)',
                      fontSize: 12, marginBottom: 8,
                    }}
                  >
                    <option value="">Select a target application…</option>
                    {APPLICATIONS.map(a => <option key={a} value={a}>{a}</option>)}
                    <option value="__custom__">Custom goal…</option>
                  </select>
                  {goal === '__custom__' && (
                    <textarea
                      value={customGoal}
                      onChange={e => setCustomGoal(e.target.value)}
                      placeholder="Describe your scientific goal…"
                      rows={3}
                      style={{
                        width: '100%', padding: '8px 10px', borderRadius: 6,
                        border: '1px solid var(--border-primary)',
                        background: 'var(--bg-primary)', color: 'var(--text-primary)',
                        fontSize: 12, resize: 'vertical', boxSizing: 'border-box',
                      }}
                    />
                  )}
                </div>

                <div style={{ padding: 16, background: 'var(--bg-secondary)', borderRadius: 8, border: '1px solid var(--border-primary)', marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Activity size={13} color="var(--accent)" /> Target Properties (JSON)
                  </div>
                  <textarea
                    value={targetProps}
                    onChange={e => setTargetProps(e.target.value)}
                    rows={6}
                    style={{
                      width: '100%', padding: '8px 10px', borderRadius: 6,
                      border: '1px solid var(--border-primary)',
                      background: 'var(--bg-primary)', color: 'var(--text-primary)',
                      fontSize: 11, fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box',
                    }}
                  />
                </div>

                <div style={{ padding: 16, background: 'var(--bg-secondary)', borderRadius: 8, border: '1px solid var(--border-primary)', marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Layers size={13} color="var(--accent)" /> Constraints (JSON)
                  </div>
                  <textarea
                    value={constraints}
                    onChange={e => setConstraints(e.target.value)}
                    rows={5}
                    style={{
                      width: '100%', padding: '8px 10px', borderRadius: 6,
                      border: '1px solid var(--border-primary)',
                      background: 'var(--bg-primary)', color: 'var(--text-primary)',
                      fontSize: 11, fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box',
                    }}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Candidates:</span>
                  {[3, 5, 8].map(n => (
                    <button
                      key={n}
                      onClick={() => setNCandidates(n)}
                      style={{
                        padding: '4px 12px', borderRadius: 6, fontSize: 12,
                        border: `1px solid ${nCandidates === n ? 'var(--accent)' : 'var(--border-primary)'}`,
                        background: nCandidates === n ? 'var(--accent)22' : 'transparent',
                        color: nCandidates === n ? 'var(--accent)' : 'var(--text-secondary)',
                        cursor: 'pointer',
                      }}
                    >
                      {n}
                    </button>
                  ))}
                </div>

                <button
                  onClick={handleDiscover}
                  disabled={discovering || !goal || (goal === '__custom__' && !customGoal.trim())}
                  style={{
                    width: '100%', padding: '12px', borderRadius: 8, border: 'none',
                    background: 'var(--accent)', color: '#fff',
                    fontSize: 13, fontWeight: 700, cursor: discovering ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                    opacity: (discovering || !goal || (goal === '__custom__' && !customGoal.trim())) ? 0.6 : 1,
                  }}
                >
                  {discovering ? <Loader2 size={15} className="spin" /> : <Sparkles size={15} />}
                  {discovering ? 'Discovering candidates…' : 'Run Inverse Design'}
                </button>

                {feedbackQueue.length > 0 && (
                  <div style={{ marginTop: 14, padding: 10, background: 'var(--bg-secondary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>HITL FEEDBACK LOG</div>
                    {feedbackQueue.map((fb, i) => (
                      <div key={i} style={{ fontSize: 11, color: fb.success ? 'var(--color-success)' : 'var(--color-error)', marginBottom: 2 }}>
                        {fb.success ? '✓' : '✗'} {fb.material} — {fb.time}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Right: Results */}
              <div>
                {!candidates && !discovering && !discoverError && (
                  <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)', border: '2px dashed var(--border-primary)', borderRadius: 8 }}>
                    <FlaskConical size={32} style={{ opacity: 0.3, marginBottom: 12 }} />
                    <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>Ready for Inverse Design</div>
                    <div style={{ fontSize: 12 }}>Select a goal, set target properties, then run the engine to get ranked material candidates with synthesis routes.</div>
                    {status && !status.nim_configured && (
                      <div style={{ marginTop: 16, padding: '10px 14px', background: '#f59e0b11', borderRadius: 6, border: '1px solid #f59e0b22', fontSize: 11, color: '#f59e0b' }}>
                        Set NVIDIA_API_KEY in your environment to enable the NIM AI engine.
                      </div>
                    )}
                  </div>
                )}

                {discovering && (
                  <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>
                    <Loader2 size={32} style={{ opacity: 0.5, marginBottom: 12, animation: 'spin 1s linear infinite' }} />
                    <div style={{ fontSize: 13 }}>Running inverse design pipeline…</div>
                    <div style={{ fontSize: 11, marginTop: 6 }}>Checking inventory · Reasoning about candidates · Scoring confidence</div>
                  </div>
                )}

                {discoverError && (
                  <div style={{ padding: 20, background: '#ef444411', borderRadius: 8, border: '1px solid #ef444422', color: 'var(--color-error)', fontSize: 12 }}>
                    <AlertTriangle size={14} style={{ marginRight: 6, display: 'inline' }} />
                    {discoverError}
                  </div>
                )}

                {candidates && candidates.length > 0 && (
                  <>
                    {reasoning && (
                      <div style={{ padding: '10px 14px', background: '#3b82f611', borderRadius: 8, border: '1px solid #3b82f622', marginBottom: 16, fontSize: 12, color: 'var(--text-primary)' }}>
                        <div style={{ fontWeight: 700, color: '#3b82f6', fontSize: 11, marginBottom: 4 }}>SCIENTIFIC REASONING</div>
                        {reasoning}
                      </div>
                    )}
                    {candidates.map((c, i) => (
                      <CandidateCard key={i} candidate={c} index={i} onFeedback={handleFeedback} />
                    ))}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── INVENTORY TAB ── */}
        {activeTab === 'inventory' && (
          <div>
            <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center' }}>
              <div style={{ position: 'relative', flex: 1, maxWidth: 300 }}>
                <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                <input
                  value={inventorySearch}
                  onChange={e => setInventorySearch(e.target.value)}
                  placeholder="Search chemicals…"
                  style={{
                    width: '100%', padding: '8px 10px 8px 30px',
                    borderRadius: 6, border: '1px solid var(--border-primary)',
                    background: 'var(--bg-secondary)', color: 'var(--text-primary)',
                    fontSize: 12, boxSizing: 'border-box',
                  }}
                  onKeyDown={e => e.key === 'Enter' && loadInventory()}
                />
              </div>
              <select
                value={inventoryCategory}
                onChange={e => setInventoryCategory(e.target.value)}
                style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: 12 }}
              >
                <option value="">All categories</option>
                {allCategories.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
              </select>
              <button
                onClick={loadInventory}
                style={{ padding: '8px 14px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
              >
                {invLoading ? <Loader2 size={12} className="spin" /> : <RefreshCcw size={12} />}
                Filter
              </button>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {inventory ? `${inventory.total} / 121` : '121'} chemicals
              </span>
            </div>

            {inventory && (
              <div style={{ columns: '280px 3', columnGap: 12 }}>
                {inventory.chemicals.map(chem => (
                  <div key={chem.no} style={{ breakInside: 'avoid', marginBottom: 8 }}>
                    <ChemicalCard chem={chem} />
                  </div>
                ))}
              </div>
            )}

            {!inventory && (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)', fontSize: 13 }}>
                Click Filter to load the inventory
              </div>
            )}
          </div>
        )}

        {/* ── FAILURES TAB ── */}
        {activeTab === 'failures' && (
          <div>
            <div style={{ marginBottom: 16, fontSize: 13, color: 'var(--text-secondary)' }}>
              Synthesis failures are tracked and used to penalise candidates in future discovery runs. Submit failures via the feedback buttons on candidate cards.
            </div>
            {failures.length === 0 ? (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)', border: '2px dashed var(--border-primary)', borderRadius: 8 }}>
                <CheckCircle2 size={28} style={{ opacity: 0.3, marginBottom: 10 }} />
                <div style={{ fontSize: 13 }}>No failures recorded yet</div>
              </div>
            ) : (
              failures.map((f, i) => (
                <div key={i} style={{ padding: 14, background: 'var(--bg-secondary)', borderRadius: 8, border: '1px solid #ef444422', borderLeft: '3px solid #ef4444', marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{f.material}</div>
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{new Date(f.timestamp * 1000).toLocaleString()}</span>
                  </div>
                  <div style={{ fontSize: 11, color: '#ef4444', marginTop: 4 }}>{f.failure_mode}</div>
                  {f.notes && <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{f.notes}</div>}
                </div>
              ))
            )}
          </div>
        )}

        {/* ── KNOWLEDGE GRAPH TAB ── */}
        {activeTab === 'graph' && (
          <KnowledgeGraphView />
        )}
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}

function KnowledgeGraphView() {
  const [graph, setGraph] = useState(null);

  useEffect(() => {
    api('/api/v2/hydrothermal/knowledge-graph').then(setGraph).catch(() => {});
  }, []);

  if (!graph) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}><Loader2 size={20} className="spin" /></div>;

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Nodes', value: graph.node_count, color: 'var(--accent)' },
          { label: 'Edges', value: graph.edge_count, color: '#10b981' },
        ].map(s => (
          <div key={s.label} style={{ padding: '12px 20px', background: 'var(--bg-secondary)', borderRadius: 8, border: '1px solid var(--border-primary)' }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: s.color, fontFamily: 'monospace' }}>{s.value}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {graph.node_count === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)', border: '2px dashed var(--border-primary)', borderRadius: 8 }}>
          <Network size={28} style={{ opacity: 0.3, marginBottom: 10 }} />
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Graph is empty</div>
          <div style={{ fontSize: 12 }}>Run inverse design and submit experimental feedback to populate the scientific knowledge graph.</div>
        </div>
      ) : (
        <div>
          <div style={{ marginBottom: 12, fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Nodes</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
            {graph.nodes.map(n => (
              <div key={n.id} style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', marginBottom: 2 }}>{n.type}</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{n.label}</div>
              </div>
            ))}
          </div>
          {graph.edges.length > 0 && (
            <>
              <div style={{ margin: '16px 0 8px', fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Edges</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {graph.edges.map((e, i) => (
                  <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ color: 'var(--text-primary)' }}>{e.from.split(':')[1]}</span>
                    <span style={{ color: 'var(--accent)', fontWeight: 600 }}>→ {e.relation} →</span>
                    <span style={{ color: 'var(--text-primary)' }}>{e.to.split(':')[1]}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
