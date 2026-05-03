import React, { useState, useCallback, useMemo } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { 
  BrainCircuit, FlaskConical, Microscope, Calculator, Settings, 
  Play, Database, Flame, Terminal, Cpu, Info, Zap, 
  Layers, Binary, Activity, ChevronRight 
} from 'lucide-react';
import SynthesisAnimator from './SynthesisAnimator';
import { DB } from './MaterialsExplorer';

// ── Design Tokens ───────────────────────────────────────────────────────────
const THEME = {
  fontMono: '"JetBrains Mono", monospace',
  border: 'rgba(255, 255, 255, 0.05)',
  bgNode: 'rgba(10, 10, 14, 0.85)',
  accent: '#00f2ff', // Cyber Cyan
  inventory: '#ffb800', // Warning Yellow
  target: '#00ff9d', // Success Green
  llm: '#00b2ff', // Info Blue
  protocol: '#00f2ff',
};

// ── Custom Nodes ─────────────────────────────────────────────────────────────

const NodeHeader = ({ icon: Icon, color, title, subtitle }) => (
  <div style={{ 
    display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, 
    borderBottom: `1px solid rgba(255,255,255,0.05)`, paddingBottom: 12,
    position: 'relative'
  }}>
    <div style={{ 
      padding: 8, background: `${color}10`, borderRadius: 4, display: 'flex',
      border: `1px solid ${color}22`, boxShadow: `0 0 10px ${color}11`
    }}>
      <Icon style={{ width: 16, height: 16, color }} />
    </div>
    <div style={{ flex: 1 }}>
      <div style={{ fontWeight: 800, color: '#fff', fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{title}</div>
      {subtitle && <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.3)', fontFamily: THEME.fontMono, marginTop: 2 }}>{subtitle}</div>}
    </div>
    {/* Tech Detail */}
    <div style={{ width: 4, height: 14, background: color, borderRadius: 1 }} />
  </div>
);

const CustomHandle = ({ type, position, color, id }) => (
  <Handle
    type={type}
    position={position}
    id={id}
    style={{ 
      width: 8, height: 8, 
      background: '#000', 
      border: `2px solid ${color}`,
      boxShadow: `0 0 8px ${color}66`,
      borderRadius: '1px'
    }}
  />
);

const ModuleWrapper = ({ children, color, style = {} }) => (
  <div className="glass-panel" style={{ 
    background: THEME.bgNode, border: `1px solid rgba(255,255,255,0.08)`, 
    borderRadius: 4, padding: 16, boxShadow: '0 10px 40px rgba(0,0,0,0.6)',
    position: 'relative', overflow: 'hidden', ...style
  }}>
    {/* Side Accent Line */}
    <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 2, background: color }} />
    {children}
  </div>
);

const ConstraintNode = ({ data }) => (
  <ModuleWrapper color={THEME.inventory} style={{ width: 280 }}>
    <NodeHeader icon={Database} color={THEME.inventory} title="Resource Matrix" subtitle="ID: BGR_L4_INV" />
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: 11, color: '#94a3b8' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 9, opacity: 0.5 }}>QUOTA_REMAIN:</span> 
        <span style={{ color: THEME.inventory, fontWeight: 700, fontFamily: THEME.fontMono }}>₹{data.budget}</span>
      </div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2 }}>
         <div style={{ width: '65%', height: '100%', background: THEME.inventory, borderRadius: 2 }} />
      </div>
      <div>
        <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.2)', marginBottom: 6, fontWeight: 700 }}>AVAILABLE_REAGENTS:</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {data.inventory.map(item => (
            <span key={item} style={{ 
              background: 'rgba(255,255,255,0.03)', padding: '2px 8px', borderRadius: 2, 
              fontSize: 8, border: '1px solid rgba(255,255,255,0.05)', color: '#cbd5e1'
            }}>{item}</span>
          ))}
        </div>
      </div>
    </div>
    <CustomHandle type="source" position={Position.Right} color={THEME.inventory} />
  </ModuleWrapper>
);

const TargetNode = ({ data }) => (
  <ModuleWrapper color={THEME.target} style={{ width: 280 }}>
    <NodeHeader icon={Zap} color={THEME.target} title="Target Objective" subtitle="HASH: OBJ_88X_2" />
    <div style={{ 
      fontSize: 11, color: '#fff', lineHeight: 1.5, background: 'rgba(0,0,0,0.4)', 
      padding: 12, borderRadius: 2, border: '1px solid rgba(0,255,157,0.1)',
      fontFamily: THEME.fontMono, opacity: 0.9
    }}>
      <ChevronRight size={10} style={{ marginRight: 6, display: 'inline' }} />
      {data.objective}
    </div>
    <CustomHandle type="source" position={Position.Right} color={THEME.target} />
  </ModuleWrapper>
);

const LLMNode = ({ data }) => (
  <ModuleWrapper color={THEME.llm} style={{ width: 320, border: `1px solid ${THEME.llm}33` }}>
    <CustomHandle type="target" position={Position.Left} color={THEME.llm} />
    <NodeHeader icon={BrainCircuit} color={THEME.llm} title="Alchemist Intelligence" subtitle="KERNEL_V4.2.0" />
    
    <div style={{ 
      background: '#000', borderRadius: 4, padding: 12, fontSize: 10, 
      color: THEME.llm, fontFamily: THEME.fontMono, border: `1px solid ${THEME.llm}22` 
    }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <div className={data.status === 'generating' ? 'animate-pulse-glow' : ''} style={{ 
          width: 6, height: 6, borderRadius: '50%', background: THEME.llm,
          boxShadow: `0 0 10px ${THEME.llm}`
        }} />
        <span style={{ fontWeight: 700 }}>{data.status === 'idle' ? 'STANDBY_MODE' : 'COMPUTING_PATHWAY'}</span>
      </div>
      <div style={{ color: 'rgba(255,255,255,0.2)', fontSize: 9 }}>
        {data.status === 'idle' ? '> Awaiting instruction set...' : '> Processing thermodynamic tensors...'}
      </div>
    </div>
    <CustomHandle type="source" position={Position.Right} color={THEME.llm} />
  </ModuleWrapper>
);

const ProtocolNode = ({ data }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const formattedSteps = data.steps.map(s => ({ action: s, phase: "Synthesis Phase", duration_min: 5, critical: s.includes('Exothermic') }));

  return (
    <ModuleWrapper color={THEME.protocol} style={{ width: 440 }}>
      <CustomHandle type="target" position={Position.Left} color={THEME.protocol} />
      <NodeHeader icon={FlaskConical} color={THEME.protocol} title="Execution Protocol" subtitle={data.material.toUpperCase()} />
      
      {!isPlaying ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {data.steps.map((s, i) => (
            <div key={i} style={{ 
              background: 'rgba(255,255,255,0.02)', padding: '8px 12px', borderRadius: 2, 
              fontSize: 10, color: '#cbd5e1', display: 'flex', gap: 12, border: '1px solid rgba(255,255,255,0.05)' 
            }}>
              <span style={{ color: THEME.protocol, fontFamily: THEME.fontMono, fontWeight: 800 }}>{(i+1).toString().padStart(2, '0')}</span>
              <span style={{ lineHeight: 1.4 }}>{s}</span>
            </div>
          ))}
          <button 
            onClick={() => setIsPlaying(true)}
            className="btn btn-primary"
            style={{ marginTop: 12, padding: '12px', background: THEME.protocol, border: 'none', borderRadius: 2, gap: 10 }} 
          >
            <Play size={14} fill="black" /> START HI-FI SIMULATION
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <SynthesisAnimator protocolSteps={formattedSteps} materialAtoms={data.atoms} />
          <button 
            onClick={() => setIsPlaying(false)}
            className="btn btn-secondary"
            style={{ padding: '8px', fontSize: 9 }} 
          >
            ABORT_STREAM
          </button>
        </div>
      )}
      <CustomHandle type="source" position={Position.Right} color={THEME.protocol} />
    </ModuleWrapper>
  );
};

const SimulationNode = ({ data }) => (
  <ModuleWrapper color={THEME.accent} style={{ width: 280 }}>
    <CustomHandle type="target" position={Position.Left} color={THEME.accent} />
    <NodeHeader icon={Layers} color={THEME.accent} title="Auto-Validator" subtitle="ENGINE: RMN_SYS_1" />
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {[
        { label: 'BANDGAP_ML', val: data.bandgap, unit: 'eV' },
        { label: 'CAPACITANCE', val: data.capacitance, unit: 'F/g' }
      ].map(metric => (
        <div key={metric.label} style={{ 
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
          background: 'rgba(0,0,0,0.5)', padding: '10px 14px', borderRadius: 2, 
          border: '1px solid rgba(255,255,255,0.03)' 
        }}>
          <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.4)', fontFamily: THEME.fontMono }}>{metric.label}:</span>
          <span style={{ fontSize: 12, color: THEME.accent, fontWeight: 800, fontFamily: THEME.fontMono }}>
            {metric.val} <small style={{ fontSize: 8, opacity: 0.5 }}>{metric.unit}</small>
          </span>
        </div>
      ))}
    </div>
  </ModuleWrapper>
);

// ── Main Component ───────────────────────────────────────────────────────────

const initialNodes = [
  { id: 'inventory', type: 'constraint', position: { x: 50, y: 100 }, data: { budget: 500, location: 'Bangalore, IN', inventory: ['Graphite Powder', 'H2SO4', 'KMnO4', 'Microwave'] } },
  { id: 'target', type: 'target', position: { x: 50, y: 350 }, data: { objective: 'High-capacitance supercapacitor electrode for wearables.' } },
  { id: 'llm', type: 'llm', position: { x: 450, y: 220 }, data: { status: 'idle' } },
];

const initialEdges = [
  { id: 'e1', source: 'inventory', target: 'llm', animated: true, style: { stroke: THEME.inventory, strokeWidth: 2, opacity: 0.4 } },
  { id: 'e2', source: 'target', target: 'llm', animated: true, style: { stroke: THEME.target, strokeWidth: 2, opacity: 0.4 } },
];


// Resolve backend URL — same convention as App.jsx (Electron preload bridge first).
const BACKEND_URL = (typeof window !== 'undefined' && window.raman) ? null : 'http://127.0.0.1:8000';

async function callBackend(path, opts = {}) {
  const api = (typeof window !== 'undefined' && window.raman) ? window.raman.api : null;
  if (api) {
    return opts.method === 'POST' ? api.post(path, opts.body) : api.get(path);
  }
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: opts.method || 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    const err = new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

// Strip Markdown code fences and find the first JSON object/array; useful when
// the LLM returns a fenced block with prose around it.
function extractJSON(text) {
  if (!text) return null;
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  const candidate = fenced ? fenced[1] : text;
  const start = candidate.search(/[\[{]/);
  if (start < 0) return null;
  const sliced = candidate.slice(start);
  try { return JSON.parse(sliced); } catch { /* fallthrough */ }
  // Try to find a balanced { ... } or [ ... ]
  for (let end = sliced.length; end > 0; end--) {
    try { return JSON.parse(sliced.slice(0, end)); } catch { /* keep shrinking */ }
  }
  return null;
}

export default function AlchemistCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [isGenerating, setIsGenerating] = useState(false);
  const [targetFormula, setTargetFormula] = useState('MnO2');
  const [error, setError] = useState(null);
  const [logs, setLogs] = useState(['[SYSTEM] KERNEL_INIT_OK', '[SYSTEM] Awaiting target specification...']);

  const nodeTypes = useMemo(() => ({
    constraint: ConstraintNode,
    target: TargetNode,
    llm: LLMNode,
    protocol: ProtocolNode,
    simulation: SimulationNode,
  }), []);

  const onConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  const addLog = (msg) => {
    const timestamp = new Date().toLocaleTimeString('en-GB', { hour12: false });
    setLogs(prev => [...prev.slice(-15), `[${timestamp}] ${msg}`]);
  };

  const runSynthesis = async () => {
    setIsGenerating(true);
    setError(null);
    setNodes(nds => nds.map(n => n.id === 'llm' ? { ...n, data: { ...n.data, status: 'generating' } } : n));

    const formula = (targetFormula || '').trim();
    if (!formula) {
      setError('Enter a target formula first (e.g. MnO2).');
      setIsGenerating(false);
      setNodes(nds => nds.map(n => n.id === 'llm' ? { ...n, data: { ...n.data, status: 'idle' } } : n));
      return;
    }

    try {
      // Step 1 — material properties via the AlchemiBridge (curated DB → NIM fallback).
      addLog(`QUERYING_PROPERTIES[${formula}]...`);
      const props = await callBackend('/api/v2/alchemi/properties', {
        method: 'POST',
        body: { formula },
      });

      // Step 2 — synthesis protocol via NIM chat. We ask for strict JSON
      // and parse what we get back; if parsing fails we surface the raw text.
      addLog('REQUESTING_SYNTHESIS_PROTOCOL...');
      const target = nodes.find(n => n.id === 'target')?.data?.objective || '';
      const inventory = nodes.find(n => n.id === 'inventory')?.data?.inventory || [];
      const promptObj = {
        target_formula: formula,
        target_application: target,
        available_inventory: inventory,
        ask: 'Return a JSON object with keys "steps" (array of strings, 4–8 entries, each one concrete experimental step including reagent quantities and conditions) and "rationale" (2–3 sentence justification grounded in literature). No prose outside the JSON.',
      };
      const chatResp = await callBackend('/api/v2/alchemi/chat', {
        method: 'POST',
        body: {
          question: JSON.stringify(promptObj),
          system: 'You are a synthesis chemist. Reply with ONE valid JSON object exactly matching the requested shape. No prose, no markdown fences.',
        },
      });

      const responseText = chatResp.answer || chatResp.response || chatResp.text || '';
      const parsed = extractJSON(responseText);
      const steps = parsed?.steps && Array.isArray(parsed.steps)
        ? parsed.steps.slice(0, 12)
        : [responseText.trim() || '(model returned an empty response)'];
      const rationale = parsed?.rationale || '';

      // Best-effort: if MaterialsExplorer.DB has atoms for a similar material, reuse them
      // for the SynthesisAnimator. Otherwise pass empty array — the protocol still renders.
      const dbHit = DB.find(m => m.name?.toLowerCase().includes(formula.toLowerCase())
                              || formula.toLowerCase().includes(m.name?.toLowerCase().split(' ')[0]?.toLowerCase()));

      const protocolNode = {
        id: 'protocol',
        type: 'protocol',
        position: { x: 880, y: 50 },
        data: {
          material: formula,
          atoms: dbHit?.atoms || [],
          steps,
        },
      };

      // Step 3 — pull simulated bandgap / capacitance from the properties response.
      const bandgap = props?.band_gap_ev ?? props?.band_gap ?? props?.properties?.band_gap_ev;
      const capacitance = props?.specific_capacitance_f_g ?? props?.properties?.specific_capacitance_f_g;
      const provenance = props?.source ? props.source : 'curated';

      const simNode = {
        id: 'sim',
        type: 'simulation',
        position: { x: 880, y: 450 },
        data: {
          bandgap: bandgap != null ? Number(bandgap).toFixed(3) : 'n/a',
          capacitance: capacitance != null ? Number(capacitance).toFixed(2) : 'n/a',
          provenance,
        },
      };

      setNodes(nds => [
        ...nds
          .filter(n => n.id !== 'protocol' && n.id !== 'sim')
          .map(n => n.id === 'llm' ? { ...n, data: { ...n.data, status: 'idle' } } : n),
        protocolNode,
        simNode,
      ]);
      setEdges(eds => [
        ...eds.filter(e => e.id !== 'e3' && e.id !== 'e4'),
        { id: 'e3', source: 'llm', target: 'protocol', animated: true, style: { stroke: THEME.llm, strokeWidth: 2 } },
        { id: 'e4', source: 'llm', target: 'sim', animated: true, style: { stroke: THEME.llm, strokeWidth: 2 } },
      ]);

      if (rationale) addLog(`RATIONALE: ${rationale.slice(0, 90)}${rationale.length > 90 ? '...' : ''}`);
      addLog(`PROVENANCE: ${provenance.toUpperCase()}`);
      addLog('GENERATION_SEQUENCE_COMPLETE.');
    } catch (err) {
      const msg = err?.status === 403
        ? 'License required — activate a trial or paid seat to use AlchemistCanvas.'
        : err?.status === 503 || err?.message?.includes('Cannot reach')
        ? 'Backend unreachable. Check that the RĀMAN Studio backend is running.'
        : `Synthesis failed: ${err?.message || 'unknown error'}`;
      setError(msg);
      addLog(`ERROR: ${msg}`);
      setNodes(nds => nds.map(n => n.id === 'llm' ? { ...n, data: { ...n.data, status: 'idle' } } : n));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="animate-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)' }}>
      {/* Header Bar */}
      <div className="glass-panel" style={{ 
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
        padding: '16px 24px', borderBottom: `1px solid var(--border-primary)`,
        background: 'rgba(255,255,255,0.02)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ 
            width: 32, height: 32, background: 'var(--bg-elevated)', 
            borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: '1px solid var(--border-secondary)'
          }}>
            <Flame size={20} color={THEME.accent} />
          </div>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '0.1em', margin: 0, textTransform: 'uppercase' }}>
              Alchemist's Canvas
            </h2>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: THEME.fontMono, display: 'flex', alignItems: 'center', gap: 8 }}>
               <span style={{ color: THEME.accent }}>● AUTONOMOUS_MODE</span>
               <span style={{ opacity: 0.3 }}>|</span>
               <span>VER: 4.2.0-STABLE</span>
            </div>
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <input
            type="text"
            value={targetFormula}
            onChange={e => setTargetFormula(e.target.value)}
            placeholder="Target formula (e.g. MnO2)"
            disabled={isGenerating}
            spellCheck={false}
            style={{
              fontFamily: THEME.fontMono, fontSize: 11, letterSpacing: '0.05em',
              background: 'rgba(0,0,0,0.4)', color: '#fff',
              border: `1px solid ${THEME.accent}33`, borderRadius: 2,
              padding: '10px 14px', width: 180, outline: 'none',
            }}
            onKeyDown={e => { if (e.key === 'Enter' && !isGenerating) runSynthesis(); }}
          />
          <button
            onClick={runSynthesis}
            disabled={isGenerating}
            className="btn btn-primary"
            style={{
              padding: '10px 28px', background: isGenerating ? 'transparent' : THEME.accent,
              color: '#000', border: isGenerating ? `1px solid ${THEME.accent}44` : 'none',
              boxShadow: isGenerating ? 'none' : `0 0 30px ${THEME.accent}33`,
            }}
          >
            {isGenerating ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Activity size={14} className="animate-pulse-glow" />
                <span>COMPUTING...</span>
              </div>
            ) : 'INITIALIZE GENERATION'}
          </button>
        </div>
      </div>
      {error && (
        <div style={{
          padding: '10px 24px', background: 'rgba(255, 100, 100, 0.08)',
          borderBottom: '1px solid rgba(255, 100, 100, 0.25)',
          color: '#ff6b6b', fontFamily: THEME.fontMono, fontSize: 11,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span>● {error}</span>
          <button onClick={() => setError(null)} style={{
            background: 'transparent', border: '1px solid rgba(255,107,107,0.4)',
            color: '#ff6b6b', borderRadius: 2, padding: '4px 10px', cursor: 'pointer',
            fontSize: 9, fontFamily: THEME.fontMono,
          }}>DISMISS</button>
        </div>
      )}

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          fitView
        >
          <Background color="rgba(0, 242, 255, 0.03)" gap={24} size={1} />
          <Controls style={{ 
            background: 'var(--bg-elevated)', border: `1px solid var(--border-primary)`, 
            fill: 'var(--text-primary)', borderRadius: 2 
          }} />
        </ReactFlow>

        {/* Reasoning Log Console (Terminal Style) */}
        <div className="glass-panel" style={{ 
          position: 'absolute', bottom: 24, right: 24, width: 340, 
          borderRadius: 4, overflow: 'hidden', zIndex: 4,
          boxShadow: '0 20px 50px rgba(0,0,0,0.8)'
        }}>
          <div style={{ 
            padding: '10px 16px', background: 'rgba(0,0,0,0.4)', 
            borderBottom: `1px solid var(--border-primary)`, 
            display: 'flex', justifyContent: 'space-between', alignItems: 'center' 
          }}>
            <div style={{ fontSize: 9, fontWeight: 800, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 10 }}>
              <Terminal size={12} color={THEME.accent} /> 
              <span style={{ letterSpacing: '0.1em' }}>REASONING_ENGINE_LOG</span>
            </div>
            <div className={isGenerating ? 'animate-pulse-glow' : ''} style={{ 
              width: 6, height: 6, borderRadius: '50%', background: isGenerating ? THEME.accent : THEME.target 
            }} />
          </div>
          <div style={{ 
            padding: '12px', height: 140, overflowY: 'auto', 
            fontFamily: THEME.fontMono, fontSize: 10, color: 'var(--text-secondary)', 
            display: 'flex', flexDirection: 'column', gap: 6, background: 'rgba(0,0,0,0.2)'
          }}>
            {logs.map((log, i) => (
              <div key={i} style={{ 
                color: log.includes('COMPLETE') ? THEME.target : log.includes('QUERYING') ? THEME.accent : 'inherit',
                opacity: i === logs.length - 1 ? 1 : 0.6
              }}>
                {log}
              </div>
            ))}
            {isGenerating && <div style={{ color: THEME.accent }}>_</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
