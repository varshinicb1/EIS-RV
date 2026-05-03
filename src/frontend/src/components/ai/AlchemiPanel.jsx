import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere, Cylinder, Environment, ContactShadows } from '@react-three/drei';

// Backend endpoint set in Phase 2/3:
//   GET  /api/v2/alchemi/status      — model + curated count + online/offline
//   POST /api/v2/alchemi/properties  — curated DB → LLM estimate → unavailable
//   POST /api/v2/alchemi/chat        — materials Q&A against the configured NIM
//   GET  /api/v2/alchemi/search/:q   — PubChem fetch + parsed 3D structure
const API = 'http://127.0.0.1:8000';

const ELEMENT_COLORS = {
  H:'#ffffff', C:'#333333', N:'#3050f8', O:'#ff0d0d', F:'#90e050',
  S:'#ffff30', P:'#ff8000', Li:'#cc80ff', Fe:'#e06633', Ti:'#bfc2c7',
  Mn:'#9c7ac7', Co:'#f090a0', Ni:'#50d050', Cu:'#c88033', Zn:'#7d80b0',
  Pt:'#d0d0e0', Au:'#ffd123', Ag:'#c0c0c0', Ru:'#248f8f', Cl:'#1ff01f',
  Na:'#ab5cf2', K:'#8f40d4', Ca:'#3dff00', Mg:'#8aff00', Al:'#bfa6a6',
  Si:'#f0c8a0', Br:'#a62929', I:'#940094',
};
const ELEMENT_RADII = {
  H:0.25, C:0.4, N:0.38, O:0.36, F:0.32, S:0.5, P:0.48, Li:0.45,
  Fe:0.55, Ti:0.55, Mn:0.55, Co:0.55, Ni:0.55, Cu:0.5, Zn:0.5,
  Pt:0.6, Au:0.6, Ag:0.6, Ru:0.55, Cl:0.42, Na:0.5, K:0.55,
  Ca:0.5, Mg:0.45, Al:0.5, Si:0.48, Br:0.45, I:0.5,
};


// ──────────── 3D molecule viewer (kept from previous panel) ────────────

function AnimatedMolecule({ species, positions, bondList, vibAmplitude }) {
  const groupRef = useRef();
  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    const t = clock.elapsedTime * 20;
    const N = positions.length;
    const children = groupRef.current.children;
    for (let i = 0; i < N; i++) {
      const atom = children[i];
      if (!atom) continue;
      const p = positions[i];
      atom.position.x = p[0] + Math.sin(t + i * 1.1) * vibAmplitude;
      atom.position.y = p[1] + Math.cos(t + i * 2.3) * vibAmplitude;
      atom.position.z = p[2] + Math.sin(t + i * 3.7) * vibAmplitude;
    }
    for (let j = 0; j < bondList.length; j++) {
      const b = bondList[j];
      const bond = children[N + j];
      if (!bond) continue;
      const p1 = children[b.from]?.position;
      const p2 = children[b.to]?.position;
      if (!p1 || !p2) continue;
      const dx = p2.x - p1.x, dy = p2.y - p1.y, dz = p2.z - p1.z;
      const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
      bond.position.set(p1.x + dx/2, p1.y + dy/2, p1.z + dz/2);
      bond.rotation.set(Math.atan2(Math.sqrt(dx*dx + dz*dz), dy), Math.atan2(dx, dz), 0);
      bond.scale.set(1, dist, 1);
    }
  });

  return (
    <group ref={groupRef}>
      {positions.map((p, i) => {
        const el = species[i] || 'C';
        const r = (ELEMENT_RADII[el] || 0.4) * 0.85;
        const color = ELEMENT_COLORS[el] || '#888888';
        return (
          <Sphere key={`atom-${i}`} position={[p[0], p[1], p[2]]} args={[r, 32, 32]} castShadow receiveShadow>
            <meshPhysicalMaterial color={color} metalness={0.4} roughness={0.2} clearcoat={1.0} clearcoatRoughness={0.1} emissive={color} emissiveIntensity={0.2} envMapIntensity={2.0} />
          </Sphere>
        );
      })}
      {bondList.map((b, i) => (
        <group key={`bond-${i}`}>
          <Cylinder args={[0.06 * b.order, 0.06 * b.order, 1, 16]} castShadow receiveShadow>
            <meshPhysicalMaterial color="#e0e0e0" metalness={0.8} roughness={0.2} clearcoat={1.0} transmission={0.5} transparent opacity={0.8} />
          </Cylinder>
        </group>
      ))}
    </group>
  );
}

function MoleculeViewer3D({ species, positions, bonds, temperature }) {
  if (!positions?.length) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
                    height: '100%', color: 'var(--text-disabled)', fontSize: 12, padding: 20,
                    textAlign: 'center', lineHeight: 1.6 }}>
        No 3D structure to display. Try the <strong>PubChem search</strong> button — it returns 3D coordinates for small molecules from PubChem when available.
      </div>
    );
  }
  const com = [0, 0, 0];
  positions.forEach(p => { com[0]+=p[0]; com[1]+=p[1]; com[2]+=p[2]; });
  com[0] /= positions.length; com[1] /= positions.length; com[2] /= positions.length;

  let bondList = bonds;
  if (!bondList?.length) {
    bondList = [];
    for (let i = 0; i < positions.length; i++) {
      for (let j = i+1; j < positions.length; j++) {
        const dx = positions[j][0]-positions[i][0];
        const dy = positions[j][1]-positions[i][1];
        const dz = positions[j][2]-positions[i][2];
        if (Math.sqrt(dx*dx+dy*dy+dz*dz) < 2.0 && !(species[i]==='H' && species[j]==='H')) {
          bondList.push({ from: i, to: j, order: 1 });
        }
      }
    }
  }
  const vibAmplitude = temperature ? Math.min(temperature / 3000, 0.08) : 0;

  return (
    <div style={{ width: '100%', height: '100%', background: 'radial-gradient(circle at center, #080810 0%, #000000 100%)', cursor: 'grab' }}>
      <Canvas camera={{ position: [0, 0, 8], fov: 45 }} gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }} dpr={[1, 2]}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[10, 15, 10]} intensity={1.5} castShadow />
        <pointLight position={[-10, -10, -10]} intensity={1} color="#4a9eff" />
        <pointLight position={[10, -10, 10]} intensity={1} color="#76b900" />
        <Environment preset="studio" />
        <group position={[-com[0], -com[1], -com[2]]}>
          <AnimatedMolecule species={species} positions={positions} bondList={bondList} vibAmplitude={vibAmplitude} />
        </group>
        <ContactShadows position={[0, -4, 0]} opacity={0.5} scale={15} blur={2} far={6} resolution={1024} color="#000000" />
        <OrbitControls autoRotate autoRotateSpeed={temperature ? Math.min(temperature/200, 3.0) : 1.5} enablePan enableZoom minDistance={3} maxDistance={20} />
      </Canvas>
    </div>
  );
}


// ──────────── Property formatting helpers ────────────

function formatValue(v) {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') {
    if (Math.abs(v) < 0.01 && v !== 0) return v.toExponential(2);
    if (Math.abs(v) > 1e5) return v.toExponential(2);
    return Number.isInteger(v) ? v.toString() : v.toFixed(3);
  }
  if (Array.isArray(v)) return v.join(', ');
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

const SOURCE_BADGE = {
  curated_db:   { label: 'Curated DB',  color: '#76b900',
                  desc: 'Value from the bundled 48-material reference database. Trust as ground truth.' },
  llm_estimate: { label: 'LLM estimate', color: '#f59e0b',
                  desc: 'Generated by the chat model. Use only as a first-pass guess; not computational chemistry.' },
  unavailable:  { label: 'Unavailable',  color: '#f87171',
                  desc: 'Neither the curated DB nor the cloud LLM could supply this. Set NVIDIA_API_KEY in .env to enable LLM estimation, or extend the curated DB.' },
  error:        { label: 'Error',        color: '#f87171', desc: 'Backend error.' },
};


// ──────────── Main panel ────────────

export default function AlchemiPanel() {
  const [searchQuery, setSearchQuery] = useState('');
  const [temperature, setTemperature] = useState(298);

  const [status, setStatus] = useState({ configured: false, model: '', mode: '' });
  const [statusError, setStatusError] = useState('');

  const [props, setProps] = useState(null);          // /api/v2/alchemi/properties response
  const [propsError, setPropsError] = useState('');
  const [propsLoading, setPropsLoading] = useState(false);

  const [structure, setStructure] = useState(null);  // /api/v2/alchemi/search response (PubChem)
  const [structureError, setStructureError] = useState('');
  const [structureLoading, setStructureLoading] = useState(false);

  const [chatInput, setChatInput] = useState('');
  const [chatLog, setChatLog] = useState([]);        // [{role, text, tokens?}, ...]
  const [chatLoading, setChatLoading] = useState(false);

  const [activeTab, setActiveTab] = useState('properties');
  const [recentSearches, setRecentSearches] = useState([
    'graphene', 'MnO2', 'LiFePO4', 'TiO2', 'Bi2WO6', 'Aspirin', 'Caffeine'
  ]);

  // ---- Status check on mount ----
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/v2/alchemi/status`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setStatus(await r.json());
        setStatusError('');
      } catch (e) {
        setStatusError(`Cannot reach the local backend at ${API}`);
      }
    })();
  }, []);

  const lookupProperties = useCallback(async (formulaOverride) => {
    const formula = (formulaOverride || searchQuery || '').trim();
    if (!formula) return;
    setPropsLoading(true);
    setPropsError('');
    setProps(null);
    try {
      const r = await fetch(`${API}/api/v2/alchemi/properties`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ formula }),
      });
      const data = await r.json();
      if (!r.ok) {
        const detail = data?.detail;
        const msg = typeof detail === 'string' ? detail : detail?.message || `HTTP ${r.status}`;
        setPropsError(msg);
      } else {
        setProps(data);
        if (!recentSearches.includes(formula)) {
          setRecentSearches(prev => [formula, ...prev.slice(0, 9)]);
        }
      }
    } catch (e) {
      setPropsError(`Network error: ${e.message}`);
    } finally {
      setPropsLoading(false);
    }
  }, [searchQuery, recentSearches]);

  const fetchStructure = useCallback(async () => {
    const query = (searchQuery || '').trim();
    if (!query) return;
    setStructureLoading(true);
    setStructureError('');
    setStructure(null);
    try {
      const r = await fetch(`${API}/api/v2/alchemi/search/${encodeURIComponent(query)}`);
      const data = await r.json();
      if (!r.ok) {
        const detail = data?.detail;
        const msg = typeof detail === 'string' ? detail : detail?.message || `HTTP ${r.status}`;
        setStructureError(msg);
      } else if (data?.error) {
        setStructureError(data.error);
      } else {
        setStructure(data);
      }
    } catch (e) {
      setStructureError(`Network error: ${e.message}`);
    } finally {
      setStructureLoading(false);
    }
  }, [searchQuery]);

  const sendChat = useCallback(async () => {
    const prompt = chatInput.trim();
    if (!prompt) return;
    setChatInput('');
    setChatLog(log => [...log, { role: 'user', text: prompt }]);
    setChatLoading(true);
    try {
      const r = await fetch(`${API}/api/v2/alchemi/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, temperature: 0.4 }),
      });
      const data = await r.json();
      if (data?.ok) {
        setChatLog(log => [...log, { role: 'assistant', text: data.answer, tokens: data.tokens }]);
      } else {
        const msg = data?.error || data?.detail?.message || `HTTP ${r.status}`;
        setChatLog(log => [...log, { role: 'system', text: `❌ ${msg}` }]);
      }
    } catch (e) {
      setChatLog(log => [...log, { role: 'system', text: `❌ Network error: ${e.message}` }]);
    } finally {
      setChatLoading(false);
    }
  }, [chatInput]);

  const s3d = structure?.structure_3d || {};
  const sourceBadge = props?.source ? SOURCE_BADGE[props.source] : null;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gridTemplateRows: '1fr 1fr', gap: 12, height: '100%' }} className="animate-in">
      {/* ─── Left — Controls + status ─── */}
      <div className="card" style={{ gridRow: '1/3', overflow: 'auto' }}>
        <div className="card-header">
          <div>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: '#76b900', fontSize: 14 }}>{'◆'}</span> Alchemi
            </div>
            <div className="card-subtitle">Materials AI · NVIDIA NIM + curated DB</div>
          </div>
        </div>

        {/* Backend status */}
        <div style={{
          padding: 10, borderRadius: 6, marginBottom: 12,
          background: status.configured ? 'rgba(118,185,0,0.08)' : 'rgba(245,158,11,0.08)',
          border: `1px solid ${status.configured ? '#76b90033' : '#f59e0b33'}`,
          fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5,
        }}>
          {statusError ? (
            <span style={{ color: '#f87171' }}>{statusError}</span>
          ) : status.configured ? (
            <>
              <div><strong style={{ color: '#76b900' }}>Online:</strong> {status.model}</div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>
                {status.curated_materials} curated materials available offline
              </div>
            </>
          ) : (
            <>
              <strong style={{ color: '#f59e0b' }}>Offline mode.</strong> NVIDIA_API_KEY not set
              — only the {status.curated_materials || 48}-material curated DB is available. Set the key in <code>.env</code> for chat + LLM estimation.
            </>
          )}
        </div>

        <div className="input-group">
          <span className="input-label">Material formula or name</span>
          <input
            className="input-field"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="e.g. graphene, LiFePO4, Aspirin"
            onKeyDown={e => e.key === 'Enter' && lookupProperties()}
          />
        </div>

        <div className="input-group">
          <span className="input-label">Animation temperature <span className="input-unit">K</span></span>
          <input className="input-field" type="number" value={temperature} onChange={e => setTemperature(+e.target.value || 0)} />
          <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 4 }}>
            Cosmetic only — drives the 3D viewer's vibration amplitude.
          </div>
        </div>

        <button className="btn btn-primary"
                onClick={() => lookupProperties()}
                disabled={propsLoading || !searchQuery.trim()}
                style={{ width: '100%', marginTop: 12 }}>
          {propsLoading ? 'Looking up…' : 'Look up properties'}
        </button>
        <button className="btn"
                onClick={fetchStructure}
                disabled={structureLoading || !searchQuery.trim()}
                style={{ width: '100%', marginTop: 6, fontSize: 11 }}>
          {structureLoading ? 'Searching PubChem…' : 'PubChem 3D structure'}
        </button>

        {(propsError || structureError) && (
          <div style={{ color: '#f87171', fontSize: 10, marginTop: 8 }}>
            {propsError || structureError}
          </div>
        )}

        {/* Recent */}
        <div style={{ marginTop: 16 }}>
          <div className="input-label" style={{ marginBottom: 6 }}>Quick lookup</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {recentSearches.map(name => (
              <button key={name} className="btn btn-sm btn-ghost"
                onClick={() => { setSearchQuery(name); lookupProperties(name); }}
                style={{ fontSize: 9, padding: '3px 8px' }}>{name}</button>
            ))}
          </div>
        </div>
      </div>

      {/* ─── Top-right — 3D viewer ─── */}
      <div className="plot-container" style={{ overflow: 'hidden' }}>
        <div className="plot-header">
          <span className="plot-title">
            {structure ? `${structure.name || searchQuery} — ${structure.molecular_formula || ''}` : '3D structure'}
          </span>
          <span className="input-unit">
            {s3d.species?.length ? `${s3d.species.length} atoms · ${s3d.bonds?.length ?? 0} bonds · ${temperature} K` : 'no structure loaded'}
          </span>
        </div>
        <div className="plot-canvas">
          <MoleculeViewer3D
            species={s3d.species}
            positions={s3d.positions}
            bonds={s3d.bonds || []}
            temperature={temperature}
          />
        </div>
      </div>

      {/* ─── Bottom-right — tabbed results ─── */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}>
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-primary)', background: 'var(--bg-elevated)', padding: '0 16px' }}>
          {[['properties', 'Properties'], ['chat', 'Materials chat'], ['status', 'Status']].map(([k, l]) => (
            <button key={k} onClick={() => setActiveTab(k)}
              style={{
                background: 'none', border: 'none', padding: '10px 14px',
                color: activeTab === k ? '#76b900' : 'var(--text-secondary)',
                borderBottom: activeTab === k ? '2px solid #76b900' : '2px solid transparent',
                cursor: 'pointer', fontWeight: 600, fontSize: 11, transition: 'color 0.2s',
              }}>{l}</button>
          ))}
        </div>

        <div style={{ padding: 14, overflow: 'auto', flex: 1 }}>
          {activeTab === 'properties' && (
            !props ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
                            height: '100%', color: 'var(--text-disabled)', fontSize: 11, textAlign: 'center', padding: 20 }}>
                Look up a material on the left to see its properties.
              </div>
            ) : (
              <div className="animate-in">
                {sourceBadge && (
                  <div style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '4px 10px', borderRadius: 4, marginBottom: 10,
                    background: `${sourceBadge.color}1F`, color: sourceBadge.color,
                    border: `1px solid ${sourceBadge.color}55`, fontSize: 10, fontWeight: 600,
                  }}>
                    {sourceBadge.label}
                  </div>
                )}
                {sourceBadge && (
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 10, lineHeight: 1.5 }}>
                    {sourceBadge.desc}
                  </div>
                )}
                {props.error && (
                  <div style={{ color: '#f87171', fontSize: 11, marginBottom: 8 }}>
                    {props.error}
                  </div>
                )}
                {props.warning && (
                  <div style={{ fontSize: 10, color: '#f59e0b', marginBottom: 10, lineHeight: 1.5,
                                padding: 8, borderRadius: 4, background: 'rgba(245,158,11,0.08)' }}>
                    {props.warning}
                  </div>
                )}
                {props.properties && (
                  <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
                    <tbody>
                      {Object.entries(props.properties).map(([k, v]) => (
                        <tr key={k} style={{ borderBottom: '1px solid var(--border-primary)' }}>
                          <td style={{ padding: '6px 8px', color: 'var(--text-tertiary)', width: 200 }}>{k}</td>
                          <td style={{ padding: '6px 8px', color: 'var(--text-primary)', fontFamily: 'var(--font-data)' }}>
                            {formatValue(v)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )
          )}

          {activeTab === 'chat' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={{ flex: 1, overflowY: 'auto', marginBottom: 8, paddingRight: 4 }}>
                {chatLog.length === 0 ? (
                  <div style={{ color: 'var(--text-disabled)', fontSize: 11, textAlign: 'center', padding: 20, lineHeight: 1.6 }}>
                    Ask the configured NVIDIA NIM about materials.
                    <div style={{ marginTop: 8, fontSize: 10 }}>
                      Try: "What's the typical electrochemical window of an aqueous electrolyte?"
                    </div>
                  </div>
                ) : chatLog.map((m, i) => (
                  <div key={i} style={{
                    marginBottom: 10, padding: 8, borderRadius: 6,
                    background: m.role === 'user' ? 'rgba(118,185,0,0.06)'
                              : m.role === 'system' ? 'rgba(248,113,113,0.06)'
                              : 'var(--bg-elevated)',
                    border: '1px solid var(--border-primary)',
                  }}>
                    <div style={{ fontSize: 9, fontWeight: 600,
                                  color: m.role === 'user' ? '#76b900'
                                       : m.role === 'system' ? '#f87171'
                                       : 'var(--text-secondary)',
                                  marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                      {m.role}{m.tokens ? ` · ${m.tokens} tokens` : ''}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-primary)', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                      {m.text}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <input className="input-field" style={{ flex: 1, fontSize: 11 }}
                       placeholder="Ask about materials, mechanisms, parameters…"
                       value={chatInput}
                       onChange={e => setChatInput(e.target.value)}
                       onKeyDown={e => e.key === 'Enter' && !chatLoading && sendChat()}
                       disabled={chatLoading || !status.configured} />
                <button className="btn btn-sm btn-primary"
                        onClick={sendChat}
                        disabled={chatLoading || !chatInput.trim() || !status.configured}
                        style={{ fontSize: 11 }}>
                  {chatLoading ? '…' : 'Send'}
                </button>
              </div>
              {!status.configured && (
                <div style={{ fontSize: 10, color: '#f59e0b', marginTop: 6 }}>
                  Chat requires NVIDIA_API_KEY in <code>.env</code>.
                </div>
              )}
            </div>
          )}

          {activeTab === 'status' && (
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
              <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
                <tbody>
                  <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                    <td style={{ padding: '6px 8px', color: 'var(--text-tertiary)', width: 200 }}>configured</td>
                    <td style={{ padding: '6px 8px', color: status.configured ? '#76b900' : '#f59e0b' }}>
                      {String(status.configured)}
                    </td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                    <td style={{ padding: '6px 8px', color: 'var(--text-tertiary)' }}>model</td>
                    <td style={{ padding: '6px 8px', fontFamily: 'var(--font-data)' }}>{status.model || '—'}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                    <td style={{ padding: '6px 8px', color: 'var(--text-tertiary)' }}>endpoint</td>
                    <td style={{ padding: '6px 8px', fontFamily: 'var(--font-data)' }}>{status.base_url || '—'}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                    <td style={{ padding: '6px 8px', color: 'var(--text-tertiary)' }}>curated materials</td>
                    <td style={{ padding: '6px 8px' }}>{status.curated_materials ?? '—'}</td>
                  </tr>
                  <tr>
                    <td style={{ padding: '6px 8px', color: 'var(--text-tertiary)' }}>mode</td>
                    <td style={{ padding: '6px 8px' }}>{status.mode || '—'}</td>
                  </tr>
                </tbody>
              </table>

              <div style={{ marginTop: 12, fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>
                <strong style={{ color: 'var(--text-secondary)' }}>What this panel does today:</strong>
                <ul style={{ margin: 0, paddingLeft: 16, marginTop: 4 }}>
                  <li>Looks materials up in a curated 48-entry database (offline, instant).</li>
                  <li>Falls back to the configured chat NIM for unknown formulas, with a clear "estimate" badge.</li>
                  <li>Fetches PubChem records for small molecules, including 3D coordinates when available.</li>
                  <li>Provides a free-form chat against the configured NIM.</li>
                </ul>
                <strong style={{ color: 'var(--text-secondary)', display: 'block', marginTop: 8 }}>What it deliberately doesn't do:</strong>
                <ul style={{ margin: 0, paddingLeft: 16, marginTop: 4 }}>
                  <li>Run MLIPs (MACE, ORB, SevenNet, MatterSim). Those NIMs use separate request shapes that aren't wired up yet — placeholder fakery has been removed.</li>
                  <li>Predict synthesis routes or feasibility scores. Earlier numbers were generated from a polynomial of molecular descriptors and have been removed.</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
