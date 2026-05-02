import React, { useState, useRef, useEffect, useCallback } from 'react';

const MODELS = [
  { id: 'orb-v3', label: 'ORB-v3', desc: 'Universal MLIP' },
  { id: 'mace-mp', label: 'MACE-MP-0', desc: 'Multi-ACE potential' },
  { id: 'sevennet', label: 'SevenNet-0', desc: 'Graph neural network' },
  { id: 'mattersim', label: 'MatterSim', desc: 'Microsoft foundation' },
];

const ELEMENT_COLORS = {
  H:'#ffffff',C:'#333333',N:'#3050f8',O:'#ff0d0d',F:'#90e050',
  S:'#ffff30',P:'#ff8000',Li:'#cc80ff',Fe:'#e06633',Ti:'#bfc2c7',
  Mn:'#9c7ac7',Co:'#f090a0',Ni:'#50d050',Cu:'#c88033',Zn:'#7d80b0',
  Pt:'#d0d0e0',Au:'#ffd123',Ag:'#c0c0c0',Ru:'#248f8f',Cl:'#1ff01f',
  Na:'#ab5cf2',K:'#8f40d4',Ca:'#3dff00',Mg:'#8aff00',Al:'#bfa6a6',
  Si:'#f0c8a0',Br:'#a62929',I:'#940094',
};
const ELEMENT_RADII = {
  H:0.25,C:0.4,N:0.38,O:0.36,F:0.32,S:0.5,P:0.48,Li:0.45,
  Fe:0.55,Ti:0.55,Mn:0.55,Co:0.55,Ni:0.55,Cu:0.5,Zn:0.5,
  Pt:0.6,Au:0.6,Ag:0.6,Ru:0.55,Cl:0.42,Na:0.5,K:0.55,
  Ca:0.5,Mg:0.45,Al:0.5,Si:0.48,Br:0.45,I:0.5,
};

import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere, Cylinder, Environment, ContactShadows } from '@react-three/drei';

function AnimatedMolecule({ species, positions, bondList, vibAmplitude }) {
  const groupRef = useRef();

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    const t = clock.elapsedTime * 20;
    const children = groupRef.current.children;
    const N = positions.length;
    
    // Animate atoms
    for (let i = 0; i < N; i++) {
      const atom = children[i];
      if (!atom) continue;
      const p = positions[i];
      atom.position.x = p[0] + Math.sin(t + i * 1.1) * vibAmplitude;
      atom.position.y = p[1] + Math.cos(t + i * 2.3) * vibAmplitude;
      atom.position.z = p[2] + Math.sin(t + i * 3.7) * vibAmplitude;
    }
    
    // Update bonds to stay attached to vibrating atoms
    for (let j = 0; j < bondList.length; j++) {
      const b = bondList[j];
      const bond = children[N + j];
      if (!bond) continue;
      const p1 = children[b.from]?.position;
      const p2 = children[b.to]?.position;
      
      if (!p1 || !p2) continue;

      const dx = p2.x - p1.x;
      const dy = p2.y - p1.y;
      const dz = p2.z - p1.z;
      const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
      
      bond.position.set(p1.x + dx/2, p1.y + dy/2, p1.z + dz/2);
      
      const yaw = Math.atan2(dx, dz);
      const pitch = Math.atan2(Math.sqrt(dx*dx + dz*dz), dy);
      bond.rotation.set(pitch, yaw, 0);
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
            <meshPhysicalMaterial 
              color={color} 
              metalness={0.4}
              roughness={0.2}
              clearcoat={1.0}
              clearcoatRoughness={0.1}
              emissive={color}
              emissiveIntensity={0.2}
              envMapIntensity={2.0}
            />
          </Sphere>
        );
      })}
      {bondList.map((b, i) => {
        return (
          <group key={`bond-${i}`}>
            <Cylinder args={[0.06 * b.order, 0.06 * b.order, 1, 16]} castShadow receiveShadow>
              <meshPhysicalMaterial 
                color="#e0e0e0" 
                metalness={0.8} 
                roughness={0.2} 
                clearcoat={1.0}
                transmission={0.5}
                transparent={true}
                opacity={0.8}
              />
            </Cylinder>
          </group>
        );
      })}
    </group>
  );
}

function MoleculeViewer3D({ species, positions, bonds, temperature }) {
  if (!positions?.length) return null;

  const com = [0, 0, 0];
  positions.forEach(p => { com[0]+=p[0]; com[1]+=p[1]; com[2]+=p[2]; });
  com[0]/=positions.length; com[1]/=positions.length; com[2]/=positions.length;

  const getBondList = () => {
    if (bonds?.length) return bonds;
    const autoBonds = [];
    for (let i=0; i<positions.length; i++) {
      for (let j=i+1; j<positions.length; j++) {
        const dx=positions[j][0]-positions[i][0];
        const dy=positions[j][1]-positions[i][1];
        const dz=positions[j][2]-positions[i][2];
        if (Math.sqrt(dx*dx+dy*dy+dz*dz) < 2.0 && !(species[i]==='H' && species[j]==='H')) {
          autoBonds.push({ from: i, to: j, order: 1 });
        }
      }
    }
    return autoBonds;
  };

  const bondList = getBondList();
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
        <OrbitControls autoRotate autoRotateSpeed={temperature ? Math.min(temperature/200, 3.0) : 1.5} enablePan={true} enableZoom={true} minDistance={3} maxDistance={20} />
      </Canvas>
    </div>
  );
}

function StatCard({label, value, unit, color}) {
  return (
    <div style={{background:'var(--bg-elevated)',borderRadius:6,padding:'8px 10px',border:'1px solid var(--border-primary)'}}>
      <div style={{fontSize:16,fontWeight:700,color:color||'var(--text-primary)',fontFamily:'var(--font-data)'}}>{value}{unit&&<span style={{fontSize:10,fontWeight:400,marginLeft:2}}>{unit}</span>}</div>
      <div style={{fontSize:9,color:'var(--text-tertiary)',marginTop:2}}>{label}</div>
    </div>
  );
}

function SyncCard({title, params, color}) {
  return (
    <div style={{background:'rgba(0,0,0,0.3)',borderRadius:8,padding:12,border:`1px solid ${color}33`}}>
      <div style={{fontSize:11,fontWeight:600,color,marginBottom:8}}>{title}</div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6}}>
        {Object.entries(params).map(([k,v])=>(
          <div key={k} style={{fontSize:10}}>
            <span style={{color:'var(--text-tertiary)'}}>{k}: </span>
            <span style={{color:'var(--text-primary)',fontFamily:'var(--font-data)'}}>{typeof v==='number'?v.toExponential?.(2)??v:v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AlchemiPanel() {
  const [searchQuery, setSearchQuery] = useState('');
  const [model, setModel] = useState('orb-v3');
  const [task, setTask] = useState('analyze');
  const [temperature, setTemperature] = useState(298);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [rotX, setRotX] = useState(0.3);
  const [rotY, setRotY] = useState(0.5);
  const [activeTab, setActiveTab] = useState('quantum');
  const [recentSearches, setRecentSearches] = useState([
    'Titanium Dioxide','Graphene','Penicillin','Lithium Cobalt Oxide','Aspirin',
    'Silicon Carbide','Caffeine','Polyethylene','Ferrocene','Dopamine'
  ]);
  const dragRef = useRef(null);

  const handleMouseDown = (e) => { dragRef.current = {x:e.clientX,y:e.clientY,rx:rotX,ry:rotY}; };
  const handleMouseMove = useCallback((e) => {
    if (!dragRef.current) return;
    setRotY(dragRef.current.ry + (e.clientX-dragRef.current.x)*0.01);
    setRotX(dragRef.current.rx + (e.clientY-dragRef.current.y)*0.01);
  }, []);
  const handleMouseUp = () => { dragRef.current = null; };
  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => { window.removeEventListener('mousemove', handleMouseMove); window.removeEventListener('mouseup', handleMouseUp); };
  }, [handleMouseMove]);

  const runUniversal = async (materialOverride) => {
    const mat = materialOverride || searchQuery;
    if (!mat.trim()) return;
    setRunning(true); setError(''); setResult(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v2/alchemi/universal', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ material: mat, task, temperature_K: temperature, n_steps: 200 }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
      if (!recentSearches.includes(mat)) setRecentSearches(prev => [mat, ...prev.slice(0,9)]);
    } catch (e) {
      setError(e.message);
    }
    setRunning(false);
  };

  const s3d = result?.structure_3d || {};
  const q = result?.quantum || {};
  const syn = result?.synthesis || {};
  const esync = result?.electrochem_sync || {};

  return (
    <div style={{display:'grid',gridTemplateColumns:'300px 1fr',gridTemplateRows:'1fr 1fr',gap:12,height:'100%'}} className="animate-in">
      {/* Left — Controls */}
      <div className="card" style={{gridRow:'1/3',overflow:'auto'}}>
        <div className="card-header">
          <div>
            <div className="card-title" style={{display:'flex',alignItems:'center',gap:6}}>
              <span style={{color:'#76b900',fontSize:14}}>{'\u25C6'}</span> NVIDIA Alchemi
            </div>
            <div className="card-subtitle">Universal Materials AI</div>
          </div>
        </div>

        {/* Universal Search */}
        <div className="input-group">
          <span className="input-label">Select Material</span>
          <div style={{display:'flex',gap:4}}>
            <select className="input-field" value={searchQuery} onChange={e=>setSearchQuery(e.target.value)} style={{flex:1}}>
              <option value="">-- Choose a material --</option>
              {recentSearches.map(name => (
                <option key={name} value={name}>{name}</option>
              ))}
              <option value="Glucose">Glucose</option>
              <option value="Cortisol">Cortisol</option>
              <option value="PSA">PSA</option>
              <option value="Gold Nanoparticles">Gold Nanoparticles</option>
              <option value="Silver Nanowires">Silver Nanowires</option>
              <option value="Platinum">Platinum</option>
              <option value="PEDOT:PSS">PEDOT:PSS</option>
              <option value="MoS2">MoS2 (Molybdenum Disulfide)</option>
              <option value="Carbon Nanotubes">Carbon Nanotubes</option>
            </select>
          </div>
        </div>

        <div className="input-group">
          <span className="input-label">Task</span>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:4}}>
            {[['analyze','Full Analysis'],['optimize','Geometry Opt.'],['md','Molec. Dynamics'],['bandgap','Band Gap']].map(([k,l])=>(
              <button key={k} className={`btn btn-sm ${task===k?'btn-primary':'btn-ghost'}`}
                onClick={()=>setTask(k)} style={{fontSize:10}}>{l}</button>
            ))}
          </div>
        </div>

        <div className="input-group">
          <span className="input-label">Simulate Lab Temperature <span className="input-unit">K</span></span>
          <input className="input-field" type="number" value={temperature} onChange={e=>setTemperature(+e.target.value)} />
        </div>

        <div className="input-group">
          <span className="input-label">MLIP Model</span>
          <select className="input-field" value={model} onChange={e=>setModel(e.target.value)}>
            {MODELS.map(m=><option key={m.id} value={m.id}>{m.label} — {m.desc}</option>)}
          </select>
        </div>

        <button className="btn btn-primary" onClick={()=>runUniversal()} disabled={running||!searchQuery.trim()}
          style={{width:'100%',marginTop:12,background:running?'#555':'linear-gradient(135deg,#76b900 0%,#00a67e 100%)', transition:'all 0.3s'}}>
          {running ? 'Simulating...' : 'Run Simulation'}
        </button>

        {error && <div style={{color:'#ef5350',fontSize:10,marginTop:6}}>{error}</div>}

        {/* Quick Access Materials */}
        <div style={{marginTop:16}}>
          <div className="input-label" style={{marginBottom:6}}>Quick Access</div>
          <div style={{display:'flex',flexWrap:'wrap',gap:4}}>
            {recentSearches.map(name=>(
              <button key={name} className="btn btn-sm btn-ghost"
                onClick={()=>{setSearchQuery(name);runUniversal(name);}}
                style={{fontSize:9,padding:'3px 8px'}}>{name}</button>
            ))}
          </div>
        </div>

        {result && (
          <div style={{marginTop:12,fontSize:10,color:'var(--text-tertiary)',fontFamily:'var(--font-data)',lineHeight:1.6}}>
            Source: {result.source} | CID: {result.cid||'N/A'}<br/>
            Formula: {result.material} | MW: {result.molecular_weight?.toFixed(1)} g/mol<br/>
            Atoms: {s3d.species?.length||0} | Bonds: {s3d.bonds?.length||0}<br/>
            Engine: {result.engine} | {result.compute_time_ms}ms
          </div>
        )}
      </div>

      {/* Top-right — 3D Viewer */}
      <div className="plot-container" style={{overflow:'hidden'}}>
        <div className="plot-header">
          <span className="plot-title">
            {result ? `${result.name} — ${result.material}` : '3D Material Viewer'}
          </span>
          <span className="input-unit">{s3d.species?.length||0} atoms | {s3d.bonds?.length||0} bonds | {temperature}K</span>
        </div>
        <div className="plot-canvas" onMouseDown={handleMouseDown}>
          <MoleculeViewer3D
            species={s3d.species||['O','H','H']}
            positions={s3d.positions||[[0,0,0],[0.96,0,0],[-0.24,0.93,0]]}
            bonds={s3d.bonds||[]}
            temperature={temperature}
            rotX={rotX} rotY={rotY} />
        </div>
      </div>

      {/* Bottom-right — Results */}
      <div className="card" style={{display:'flex',flexDirection:'column',overflow:'hidden',padding:0}}>
        <div style={{display:'flex',borderBottom:'1px solid var(--border-primary)',background:'var(--bg-elevated)',padding:'0 16px'}}>
          {[['quantum','Quantum Properties'],['sync','EIS/CV Sync'],['synthesis','Synthesis Protocol']].map(([k,l])=>(
            <button key={k} onClick={()=>setActiveTab(k)}
              style={{background:'none',border:'none',padding:'10px 14px',
                color:activeTab===k?'#76b900':'var(--text-secondary)',
                borderBottom:activeTab===k?'2px solid #76b900':'2px solid transparent',
                cursor:'pointer',fontWeight:600,fontSize:11, transition:'color 0.2s'}}>{l}</button>
          ))}
        </div>

        <div style={{padding:14,overflow:'auto',flex:1}}>
          {!result ? (
            <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:'var(--text-disabled)',fontSize:11}}>
              Select a material and run simulation to view results.
            </div>
          ) : activeTab === 'quantum' ? (
            <div className="animate-in">
              <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:8,marginBottom:12}}>
                <StatCard label="Bandgap" value={q.bandgap_eV?.toFixed(3)} unit="eV" color="#ffa726" />
                <StatCard label="HOMO" value={q.homo_eV?.toFixed(2)} unit="eV" color="#ef5350" />
                <StatCard label="LUMO" value={q.lumo_eV?.toFixed(2)} unit="eV" color="#66bb6a" />
                <StatCard label="Density" value={q.density_g_cm3?.toFixed(2)} unit="g/cm3" />
              </div>
              <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:8}}>
                <StatCard label="Conductivity" value={q.conductivity_S_m?.toExponential(2)} unit="S/m" color="#42a5f5" />
                <StatCard label="Dielectric" value={q.dielectric_constant?.toFixed(2)} />
                <StatCard label="Thermal Cond." value={q.thermal_conductivity_W_mK?.toFixed(4)} unit="W/mK" />
                <StatCard label="Debye Temp." value={q.debye_temperature_K?.toFixed(0)} unit="K" />
              </div>
              {result.synonyms?.length > 0 && (
                <div style={{marginTop:12,fontSize:10,color:'var(--text-tertiary)'}}>
                  Also known as: {result.synonyms.join(', ')}
                </div>
              )}
            </div>
          ) : activeTab === 'sync' ? (
            <div className="animate-in" style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
              <SyncCard title="EIS Parameters" params={esync.eis||{}} color="#42a5f5" />
              <SyncCard title="CV Parameters" params={esync.cv||{}} color="#ffa726" />
              <div style={{gridColumn:'1/-1',padding:12,background:'rgba(118,185,0,0.08)',borderRadius:8,border:'1px solid #76b90033',fontSize:11,color:'var(--text-secondary)',lineHeight:1.6}}>
                <strong style={{color:'#76b900'}}>Auto-Sync Active:</strong> These parameters are computed from {result.name}'s quantum properties. Conductivity maps to Rct via Butler-Volmer kinetics. HOMO/LUMO maps to E0 via vacuum-to-SHE conversion (4.5 eV offset).
              </div>
            </div>
          ) : (
            <div className="animate-in" style={{display:'flex', flexDirection:'column', gap: 12}}>
              <div style={{display:'flex',alignItems:'center',gap:12}}>
                <div style={{width:60,height:60,borderRadius:12,display:'flex',alignItems:'center',justifyContent:'center',fontSize:24,
                  background:syn.feasibility_label==='High'?'rgba(102,187,106,0.15)':syn.feasibility_label==='Medium'?'rgba(255,167,38,0.15)':'rgba(239,83,80,0.15)',
                  color:syn.feasibility_label==='High'?'#66bb6a':syn.feasibility_label==='Medium'?'#ffa726':'#ef5350'}}>
                  {syn.feasibility_score?.toFixed(0)}
                </div>
                <div>
                  <div style={{fontSize:14,fontWeight:700,color:'var(--text-primary)'}}>Synthesis Feasibility: {syn.feasibility_label}</div>
                  <div style={{fontSize:10,color:'var(--text-tertiary)',marginTop:2}}>Confidence {syn.feasibility_score}/100 | Optimal route for {result.name}</div>
                </div>
              </div>
              
              <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12}}>
                {/* Method Overview */}
                <div style={{background:'var(--bg-elevated)', borderRadius:8, padding:12, border:'1px solid var(--border-primary)'}}>
                  <div style={{fontSize:12, fontWeight:600, color:'#76b900', marginBottom:8}}>
                    Recommended Method
                  </div>
                  {syn.recommended_methods?.map((m,i)=>(
                    <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'6px 0', borderBottom: i === syn.recommended_methods.length-1 ? 'none' : '1px solid var(--border-primary)'}}>
                      <span style={{fontSize:11,fontWeight:500}}>{m.method}</span>
                      <div style={{display:'flex',gap:8,fontSize:10}}>
                        <span style={{color:'#66bb6a'}}>{(m.confidence*100).toFixed(0)}% conf.</span>
                        <span style={{color:'var(--text-tertiary)'}}>Cost: {m.cost}</span>
                      </div>
                    </div>
                  ))}
                  {syn.risk_factors?.length > 0 && (
                    <div style={{marginTop:8,fontSize:10,color:'var(--text-tertiary)'}}>
                      <strong style={{color:'#ef5350'}}>Risk Factors:</strong><br/>
                      <ul style={{margin:0, paddingLeft:16, marginTop:4}}>
                        {syn.risk_factors.map((rf, idx) => <li key={idx}>{rf}</li>)}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Lab Protocol */}
                <div style={{background:'var(--bg-elevated)', borderRadius:8, padding:12, border:'1px solid var(--border-primary)'}}>
                  <div style={{fontSize:12, fontWeight:600, color:'var(--text-primary)', marginBottom:8}}>
                    Lab Protocol
                  </div>
                  {syn.instructions && syn.instructions.length > 0 ? (
                    <div style={{display:'flex', flexDirection:'column', gap:6}}>
                      {syn.instructions.map((step, idx) => (
                        <div key={idx} style={{fontSize:10, color:'var(--text-secondary)', lineHeight:1.4, display:'flex', gap:6}}>
                          <div style={{minWidth:14, height:14, borderRadius:'50%', background:'#76b900', color:'#000', display:'flex', alignItems:'center', justifyContent:'center', fontSize:8, fontWeight:700, marginTop:1}}>
                            {idx + 1}
                          </div>
                          <div>{step.replace(/^Step \d+: /, '')}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{fontSize:10, color:'var(--text-tertiary)'}}>No specific protocol available.</div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
