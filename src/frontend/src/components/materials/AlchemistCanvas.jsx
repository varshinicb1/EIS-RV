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


export default function AlchemistCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [isGenerating, setIsGenerating] = useState(false);
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

  const runSynthesis = () => {
    setIsGenerating(true);
    addLog('QUERYING_ALCHEMIST_7B...');
    setNodes(nds => nds.map(n => n.id === 'llm' ? { ...n, data: { ...n.data, status: 'generating' } } : n));

    setTimeout(() => {
      addLog('ANALYZING_REAGENT_STABILITY...');
      setTimeout(() => {
        addLog('OPTIMIZING_PATHWAY_TRAJECTORY...');
        setTimeout(() => {
          const materialName = 'MW-Expanded Graphene Oxide';
          const materialData = DB.find(m => m.name === materialName);

          const newNode1 = {
            id: 'protocol',
            type: 'protocol',
            position: { x: 880, y: 50 },
            data: {
              material: materialName,
              atoms: materialData?.atoms || [],
              steps: [
                'Add 2g Graphite to 50ml H2SO4 under ice bath.',
                'Slowly add 6g KMnO4 (CRITICAL: EXOTHERMIC).',
                'Neutralize distilled water until pH 7.0.',
                'Microwave @ 800W / 60s for exfoliation.'
              ]
            }
          };
          
          const newNode2 = {
            id: 'sim',
            type: 'simulation',
            position: { x: 880, y: 450 },
            data: { bandgap: '0.042', capacitance: '210.58' }
          };

          setNodes(nds => [...nds.map(n => n.id === 'llm' ? { ...n, data: { ...n.data, status: 'idle' } } : n), newNode1, newNode2]);
          
          setEdges(eds => [
            ...eds,
            { id: 'e3', source: 'llm', target: 'protocol', animated: true, style: { stroke: THEME.llm, strokeWidth: 2 } },
            { id: 'e4', source: 'llm', target: 'sim', animated: true, style: { stroke: THEME.llm, strokeWidth: 2 } },
          ]);
          
          addLog('GENERATION_SEQUENCE_COMPLETE.');
          setIsGenerating(false);
        }, 1000);
      }, 800);
    }, 1200);
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
