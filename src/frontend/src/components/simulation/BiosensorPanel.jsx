import React, { useState, useRef, useEffect } from 'react';
import jsPDF from 'jspdf';
import 'jspdf-autotable';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Box, Cylinder, Sphere, Environment, ContactShadows, Grid } from '@react-three/drei';
import { Layers, Download } from 'lucide-react';
import { generateIEEEReport } from '../../utils/ieeeReportGenerator';


function ElectrodeViewer3D({ geometry, coating }) {
  if (!geometry?.layers?.length) {
    return (
      <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:'var(--text-disabled)',fontSize:12}}>
        Run simulation to view 3D architecture
      </div>
    );
  }

  const { pattern, layers } = geometry;
  
  return (
    <div style={{ width: '100%', height: '100%', background: 'radial-gradient(circle at center, #0a0a10 0%, #000000 100%)', cursor: 'grab' }}>
      <Canvas camera={{ position: [0, 5, 9], fov: 40 }} gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }} dpr={[1, 2]}>
        {/* Research-grade lighting setup: 3-point lighting for publication renders */}
        <ambientLight intensity={0.3} />
        <directionalLight position={[8, 12, 6]} intensity={1.8} castShadow shadow-mapSize-width={2048} shadow-mapSize-height={2048} />
        <directionalLight position={[-5, 8, -4]} intensity={0.6} color="#b0c4de" />
        <pointLight position={[0, 6, 0]} intensity={0.4} color="#4a9eff" />
        <Environment preset="city" />
        {/* Scale grid for research reference */}
        <Grid position={[0, -0.21, 0]} args={[20, 20]} cellSize={1} cellThickness={0.3} cellColor="#1a1a2e" sectionSize={5} sectionThickness={0.8} sectionColor="#2a2a4e" fadeDistance={25} />


        {/* Substrate */}
        <Box args={[12, 0.2, 16]} position={[0, -0.1, 2]}>
          <meshPhysicalMaterial color="#2a2d35" metalness={0.1} roughness={0.8} />
        </Box>

        <group position={[0, 0, 0]}>
          {pattern === 'screen_printed' && layers.map((l, i) => {
            const x = l.cx || 0;
            const z = l.cy || 0;
            const r = l.radius || 1;
            const h = 0.05;

            let color = '#222';
            let metalness = 0.3;
            let roughness = 0.8;

            if (l.type === 'reference_electrode') { color = '#b0bec5'; metalness = 0.1; } // Ag/AgCl
            if (l.type === 'working_electrode') { color = '#f1c40f'; metalness = 0.8; roughness = 0.3; } // Assume Gold default
            if (l.type === 'counter_electrode') { color = '#222'; } // Carbon
            
            return (
              <group key={i} position={[x, 0.025, z]}>
                <Cylinder args={[r, r, h, 64]}>
                  <meshPhysicalMaterial color={color} metalness={metalness} roughness={roughness} />
                </Cylinder>
                {l.type === 'working_electrode' && coating && (
                  <Cylinder args={[r*0.98, r*0.98, 0.02, 64]} position={[0, h/2 + 0.01, 0]}>
                    <meshPhysicalMaterial color="#42a5f5" transparent opacity={0.6} roughness={0.2} clearcoat={1} />
                  </Cylinder>
                )}
              </group>
            );
          })}

          {pattern === 'interdigitated' && (
            <group position={[-1.5, 0.05, 0]}>
              {Array.from({length: 12}).map((_, i) => (
                <Box key={i} args={[0.1, 0.1, 2]} position={[i * 0.25, 0, 0]}>
                  <meshPhysicalMaterial color={i % 2 === 0 ? '#ffa726' : '#42a5f5'} metalness={0.8} roughness={0.2} />
                </Box>
              ))}

            </group>
          )}

          {pattern === 'microwell_array' && (
            <group position={[-2, 0.05, -1]}>
              {Array.from({length: 6}).map((_, r) => (
                Array.from({length: 8}).map((_, c) => (
                  <Cylinder key={`${r}-${c}`} args={[0.15, 0.15, 0.1, 16]} position={[c * 0.5, 0, r * 0.4]}>
                    <meshPhysicalMaterial color="#ce93d8" metalness={0.3} roughness={0.5} />
                  </Cylinder>
                ))
              ))}
            </group>
          )}

          {pattern === 'disk' && (
            <group position={[0, 0.05, 0]}>
              <Cylinder args={[1, 1, 0.1, 64]}>
                <meshPhysicalMaterial color="#ffa726" metalness={0.5} roughness={0.5} />
              </Cylinder>
              {coating && (
                <Cylinder args={[0.95, 0.95, 0.02, 64]} position={[0, 0.06, 0]}>
                  <meshPhysicalMaterial color="#ce93d8" transparent opacity={0.6} clearcoat={1} />
                </Cylinder>
              )}
            </group>
          )}
          {pattern === 'vidyutx_v1' && (
            <group position={[0, 0, 0]}>
              {/* VidyutX PCB Substrate (Longer dark grey rectangle) */}
              <Box args={[8, 0.15, 2.5]} position={[1, -0.05, 0]}>
                <meshPhysicalMaterial color="#222428" metalness={0.2} roughness={0.7} />
              </Box>

              {/* Working Electrode (WE) - Large Gold Circle */}
              <Cylinder args={[0.8, 0.8, 0.1, 64]} position={[-2, 0.05, 0]}>
                <meshPhysicalMaterial color="#f7cd65" metalness={0.9} roughness={0.2} clearcoat={1} />
              </Cylinder>

              {/* Counter Electrode (CE) - Outer Gold Ring */}
              <mesh position={[-2, 0.05, 0]} rotation={[Math.PI/2, 0, 0]}>
                <ringGeometry args={[0.9, 1.05, 64]} />
                <meshPhysicalMaterial color="#f7cd65" metalness={0.9} roughness={0.2} side={2} />
              </mesh>

              {/* Reference dots / Vias */}
              {[[-0.5, 0.3], [-0.5, -0.3], [-0.8, 0], [-0.2, 0], [-0.35, 0.2], [-0.35, -0.2]].map((pos, idx) => (
                <Cylinder key={idx} args={[0.04, 0.04, 0.12, 16]} position={[pos[0], 0.05, pos[1]]}>
                  <meshPhysicalMaterial color="#f7cd65" metalness={0.8} roughness={0.3} />
                </Cylinder>
              ))}



              {/* Connection Pads (RE, WE, CE) */}
              {['RE', 'WE', 'CE'].map((label, i) => {
                const zPos = -0.8 + i * 0.8;
                return (
                  <group key={label} position={[4.0, 0.05, zPos]}>
                    <Box args={[1.5, 0.12, 0.6]}>
                      <meshPhysicalMaterial color="#f7cd65" metalness={0.9} roughness={0.2} />
                    </Box>

                  </group>
                )
              })}

              {/* Coating Layer on WE if applicable */}
              {coating && (
                <Cylinder args={[0.78, 0.78, 0.02, 64]} position={[-2, 0.08, 0]}>
                  <meshPhysicalMaterial color="#ce93d8" transparent opacity={0.7} roughness={0.1} clearcoat={1} />
                </Cylinder>
              )}
            </group>
          )}
          {pattern === 'microfluidic' && (
            <group position={[0, 0, 0]}>
              {/* PDMS substrate */}
              <Box args={[6, 0.3, 3]} position={[0, -0.15, 0]}>
                <meshPhysicalMaterial color="#e8e8e8" transparent opacity={0.4} roughness={0.1} clearcoat={1} />
              </Box>
              {/* Flow channel (rectangular) */}
              <Box args={[5, 0.12, 0.4]} position={[0, 0.06, 0]}>
                <meshPhysicalMaterial color="#42a5f5" transparent opacity={0.35} roughness={0.05} clearcoat={1} />
              </Box>
              {/* Inlet port */}
              <Cylinder args={[0.2, 0.2, 0.4, 32]} position={[-2.2, 0.2, 0]}>
                <meshPhysicalMaterial color="#78909c" metalness={0.6} roughness={0.3} />
              </Cylinder>
              {/* Outlet port */}
              <Cylinder args={[0.2, 0.2, 0.4, 32]} position={[2.2, 0.2, 0]}>
                <meshPhysicalMaterial color="#78909c" metalness={0.6} roughness={0.3} />
              </Cylinder>
              {/* Embedded WE electrode */}
              <Cylinder args={[0.35, 0.35, 0.05, 64]} position={[0, 0.01, 0]} rotation={[0, 0, 0]}>
                <meshPhysicalMaterial color="#f7cd65" metalness={0.9} roughness={0.15} clearcoat={1} />
              </Cylinder>
              {/* CE electrode */}
              <Cylinder args={[0.25, 0.25, 0.05, 64]} position={[0.9, 0.01, 0]}>
                <meshPhysicalMaterial color="#424242" metalness={0.3} roughness={0.6} />
              </Cylinder>
              {/* RE electrode */}
              <Cylinder args={[0.15, 0.15, 0.05, 48]} position={[-0.9, 0.01, 0]}>
                <meshPhysicalMaterial color="#b0bec5" metalness={0.7} roughness={0.3} />
              </Cylinder>
              {/* Sample droplet on WE */}
              <Sphere args={[0.18, 32, 16]} position={[0, 0.12, 0]}>
                <meshPhysicalMaterial color="#e91e63" transparent opacity={0.5} roughness={0.05} clearcoat={1} />
              </Sphere>
              {coating && (
                <Cylinder args={[0.34, 0.34, 0.015, 64]} position={[0, 0.04, 0]}>
                  <meshPhysicalMaterial color="#ce93d8" transparent opacity={0.65} clearcoat={1} />
                </Cylinder>
              )}
            </group>
          )}
        </group>

        <ContactShadows position={[0, -0.19, 0]} opacity={0.6} scale={20} blur={1.5} far={6} resolution={1024} />
        <OrbitControls autoRotate autoRotateSpeed={0.3} maxPolarAngle={Math.PI/2.1} enableZoom={true} enablePan={true} minDistance={3} maxDistance={20} />
      </Canvas>
      {coating && (
        <div style={{ position: 'absolute', bottom: 10, right: 10, textAlign: 'right' }}>
          <div style={{ fontSize: 11, color: '#42a5f5', fontWeight: 600 }}><Layers size={12} style={{display:'inline', marginRight:4}}/> Film: {coating.thickness_nm}nm</div>
          <div style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{coating.uniformity_pct}% Uniformity</div>
        </div>
      )}
    </div>
  );
}

function FabStep({step, isActive}) {
  const colors = {true:'#76b900',false:'var(--text-tertiary)'};
  return (
    <div style={{display:'flex',gap:10,padding:'8px 0',borderBottom:'1px solid var(--border-default)',opacity:isActive?1:0.6}}>
      <div style={{width:24,height:24,borderRadius:12,background:step.critical?'rgba(118,185,0,0.15)':'var(--bg-elevated)',
        display:'flex',alignItems:'center',justifyContent:'center',fontSize:10,fontWeight:700,
        color:step.critical?'#76b900':'var(--text-tertiary)',border:`1px solid ${step.critical?'#76b90055':'var(--border-default)'}`}}>
        {step.step}
      </div>
      <div style={{flex:1}}>
        <div style={{fontSize:11,fontWeight:600,color:'var(--text-primary)'}}>{step.phase}</div>
        <div style={{fontSize:10,color:'var(--text-secondary)',lineHeight:1.5,marginTop:2}}>{step.action}</div>
        <div style={{fontSize:9,color:'var(--text-tertiary)',marginTop:2}}>{step.duration_min} min{step.critical?' | Critical':''}
        </div>
      </div>
    </div>
  );
}

export default function BiosensorPanel() {
  const [pattern, setPattern] = useState('screen_printed');
  const [ink, setInk] = useState('gold_nanoparticle');
  const [sam, setSam] = useState('thiol_gold');
  const [coating, setCoating] = useState('spin');
  const [analyte, setAnalyte] = useState('Glucose');
  const [spinRpm, setSpinRpm] = useState(3000);
  const [spinTime, setSpinTime] = useState(30);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [activeTab, setActiveTab] = useState('3d');
  const [library, setLibrary] = useState(null);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/v2/biosensor/library')
      .then(r=>r.json()).then(setLibrary).catch(()=>{});
  }, []);

  const runSimulation = async () => {
    setRunning(true); setResult(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v2/biosensor/simulate', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({pattern,ink,sam,coating_method:coating,analyte,spin_rpm:spinRpm,spin_time_s:spinTime}),
      });
      const data = await res.json();
      setResult(data);
    } catch(e) { console.error(e); }
    setRunning(false);
  };

  const optimizeMaterial = async () => {
    setOptimizing(true); setResult(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v2/biosensor/optimize', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ analyte, constraints: { we_size: "4mm", pattern: "vidyutx_v1" } }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setResult(data.simulation_result);
        setPattern(data.optimal_configuration.pattern);
        setInk(data.optimal_configuration.ink);
        setSam(data.optimal_configuration.sam);
        setCoating(data.optimal_configuration.coating);
        // Display results through the UI — no browser alerts in enterprise software
        console.log(`Optimization complete: ${data.iterations_simulated} iters, ${data.optimization_time_ms}ms, suggests ${data.suggested_nanomaterial}`);
      }
    } catch (e) { console.error(e); }
    setOptimizing(false);
  };

  const perf = result?.performance || {};
  const ec = result?.electrochem_sync || {};

  return (
    <div style={{display:'grid',gridTemplateColumns:'300px 1fr',gridTemplateRows:'1fr 1fr',gap:12,height:'100%'}} className="animate-in">
      {/* Left Controls */}
      <div className="card" style={{gridRow:'1/3',overflow:'auto'}}>
        <div className="card-header">
          <div>
            <div className="card-title" style={{display:'flex',alignItems:'center',gap:6}}>
              Biosensor Fabrication
            </div>
            <div className="card-subtitle">End-to-end electrochemical biosensor design</div>
          </div>
        </div>

        <div className="input-group">
          <span className="input-label">Target Analyte</span>
          <select className="input-field" value={analyte} onChange={e=>setAnalyte(e.target.value)}>
            <option value="Glucose">Glucose</option>
            <option value="Cortisol">Cortisol</option>
            <option value="PSA">PSA (Prostate-Specific Antigen)</option>
            <option value="SARS-CoV-2">SARS-CoV-2</option>
            <option value="L-Lactate">L-Lactate</option>
            <option value="Uric Acid">Uric Acid</option>
            <option value="Ascorbic Acid">Ascorbic Acid</option>
            <option value="Dopamine">Dopamine</option>
            <option value="Serotonin">Serotonin</option>
          </select>
        </div>

        <div className="input-group">
          <span className="input-label">Electrode Pattern</span>
          <select className="input-field" value={pattern} onChange={e=>setPattern(e.target.value)}>
            {library ? Object.entries(library.patterns).map(([k,v])=>
              <option key={k} value={k}>{v}</option>
            ) : <>
              <option value="vidyutx_v1">VidyutX V1.0 (VidyuthLabs)</option>
              <option value="screen_printed">Screen-Printed (SPE)</option>
              <option value="interdigitated">Interdigitated Array</option>
              <option value="disk">Disk Microelectrode</option>
              <option value="microwell_array">Microwell Array (96)</option>
            </>}
          </select>
        </div>

        <div className="input-group">
          <span className="input-label">Ink Formulation</span>
          <select className="input-field" value={ink} onChange={e=>setInk(e.target.value)}>
            {library ? Object.entries(library.inks).map(([k,v])=>
              <option key={k} value={k}>{v}</option>
            ) : <>
              <option value="gold_nanoparticle">Gold Nanoparticle</option>
              <option value="carbon_paste">Carbon Paste</option>
              <option value="silver_nanowire">Silver Nanowire</option>
              <option value="conductive_polymer">PEDOT:PSS</option>
            </>}
          </select>
        </div>

        <div className="input-group">
          <span className="input-label">Surface Chemistry (SAM)</span>
          <select className="input-field" value={sam} onChange={e=>setSam(e.target.value)}>
            {library ? Object.entries(library.sams).map(([k,v])=>
              <option key={k} value={k}>{v}</option>
            ) : <>
              <option value="thiol_gold">Thiol-Gold SAM</option>
              <option value="silane_oxide">Silane-Oxide</option>
              <option value="biotin_streptavidin">Biotin-Streptavidin</option>
              <option value="diazonium">Diazonium Grafting</option>
            </>}
          </select>
        </div>

        <div className="input-group">
          <span className="input-label">Coating Method</span>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:4}}>
            {['spin','dip','inkjet'].map(m=>(
              <button key={m} className={`btn btn-sm ${coating===m?'btn-primary':'btn-ghost'}`}
                onClick={()=>setCoating(m)} style={{fontSize:10,textTransform:'capitalize'}}>{m}</button>
            ))}
          </div>
        </div>

        {coating==='spin' && <>
          <div className="input-group">
            <span className="input-label">Spin Speed <span className="input-unit">RPM</span></span>
            <select className="input-field" value={spinRpm} onChange={e=>setSpinRpm(+e.target.value)}>
              <option value="1000">1000</option>
              <option value="2000">2000</option>
              <option value="3000">3000</option>
              <option value="4000">4000</option>
              <option value="5000">5000</option>
            </select>
          </div>
          <div className="input-group">
            <span className="input-label">Spin Time <span className="input-unit">s</span></span>
            <select className="input-field" value={spinTime} onChange={e=>setSpinTime(+e.target.value)}>
              <option value="15">15</option>
              <option value="30">30</option>
              <option value="45">45</option>
              <option value="60">60</option>
              <option value="120">120</option>
            </select>
          </div>
        </>}

        <div style={{display:'flex', gap:8, marginTop:12}}>
          <button className="btn btn-primary" onClick={runSimulation} disabled={running || optimizing}
            style={{flex:1, background:(running||optimizing)?'#555':'linear-gradient(135deg,#76b900 0%,#00a67e 100%)'}}>
            {running ? 'Simulating...' : 'Simulate'}
          </button>
          <button className="btn" onClick={optimizeMaterial} disabled={running || optimizing}
            style={{flex:1, background:(running||optimizing)?'#555':'#42a5f5', color:'#fff', border:'none'}}>
            {optimizing ? 'Optimizing...' : 'AI Optimize'}
          </button>
        </div>

        {result && (
          <div style={{marginTop:12,padding:10,background:'rgba(118,185,0,0.08)',borderRadius:6,border:'1px solid #76b90033'}}>
            <div style={{fontSize:11,fontWeight:600,color:'#76b900',marginBottom:6}}>Performance Summary</div>
            <div style={{fontSize:10,color:'var(--text-secondary)',lineHeight:1.8,fontFamily:'var(--font-data)'}}>
              Sensitivity: {perf.sensitivity_uA_mM_cm2} μA/mM/cm²<br/>
              LOD: {perf.lod_M} M<br/>
              Response: {perf.response_time_s}s<br/>
              Stability: {perf.stability_days} days<br/>
              Selectivity: {perf.selectivity_pct}%<br/>
              RSD: {perf.reproducibility_rsd_pct}%
            </div>
          </div>
        )}
      </div>

      {/* Top-right — 3D Viewer */}
      <div className="plot-container" style={{overflow:'hidden'}}>
        <div className="plot-header">
          <span className="plot-title">Electrode Architecture</span>
          <span className="input-unit">{result?`${result.geometry_3d?.layers?.length||0} layers · ${result.coating?.method||''}`:'Configure and simulate'}</span>
        </div>
        <div className="plot-canvas">
          <ElectrodeViewer3D geometry={result?.geometry_3d} coating={result?.coating} />
        </div>
      </div>

      {/* Bottom-right — Tabs */}
      <div className="card" style={{display:'flex',flexDirection:'column',overflow:'hidden',padding:0}}>
        <div style={{display:'flex',borderBottom:'1px solid var(--border-default)',background:'var(--bg-elevated)',padding:'0 16px'}}>
          {[['3d','EIS/CV Sync'],['fab','Fab Protocol'],['report','Report']].map(([k,l])=>(
            <button key={k} onClick={()=>setActiveTab(k)}
              style={{background:'none',border:'none',padding:'10px 14px',
                color:activeTab===k?'#76b900':'var(--text-secondary)',
                borderBottom:activeTab===k?'2px solid #76b900':'2px solid transparent',
                cursor:'pointer',fontWeight:600,fontSize:11}}>{l}</button>
          ))}
        </div>
        <div style={{padding:14,overflow:'auto',flex:1}}>
          {!result ? (
            <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:'var(--text-disabled)',fontSize:11}}>
              Configure parameters and run simulation to see results
            </div>
          ) : activeTab==='3d' ? (
            <div className="animate-in">
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
                <div style={{background:'rgba(66,165,245,0.08)',borderRadius:8,padding:12,border:'1px solid #42a5f533'}}>
                  <div style={{fontSize:11,fontWeight:600,color:'#42a5f5',marginBottom:8}}>EIS Sync Parameters</div>
                  {ec.eis && Object.entries(ec.eis).map(([k,v])=>(
                    <div key={k} style={{display:'flex',justifyContent:'space-between',fontSize:10,marginBottom:4}}>
                      <span style={{color:'var(--text-tertiary)'}}>{k}</span>
                      <span style={{color:'var(--text-primary)',fontFamily:'var(--font-data)'}}>{typeof v==='number'?v.toExponential?.(2)??v:v}</span>
                    </div>
                  ))}
                </div>
                <div style={{background:'rgba(255,167,38,0.08)',borderRadius:8,padding:12,border:'1px solid #ffa72633'}}>
                  <div style={{fontSize:11,fontWeight:600,color:'#ffa726',marginBottom:8}}>CV Sync Parameters</div>
                  {ec.cv && Object.entries(ec.cv).map(([k,v])=>(
                    <div key={k} style={{display:'flex',justifyContent:'space-between',fontSize:10,marginBottom:4}}>
                      <span style={{color:'var(--text-tertiary)'}}>{k}</span>
                      <span style={{color:'var(--text-primary)',fontFamily:'var(--font-data)'}}>{JSON.stringify(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div style={{marginTop:12,display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:8}}>
                <div style={{background:'var(--bg-elevated)',borderRadius:6,padding:8,textAlign:'center',border:'1px solid var(--border-default)'}}>
                  <div style={{fontSize:12,fontWeight:600,color:'#ffa726'}}>{result.coating?.thickness_nm} nm</div>
                  <div style={{fontSize:9,color:'var(--text-tertiary)'}}>Film Thickness</div>
                </div>
                <div style={{background:'var(--bg-elevated)',borderRadius:6,padding:8,textAlign:'center',border:'1px solid var(--border-default)'}}>
                  <div style={{fontSize:12,fontWeight:600,color:'#66bb6a'}}>{result.surface_chemistry?.coverage_molecules_cm2?.toExponential(1)}</div>
                  <div style={{fontSize:9,color:'var(--text-tertiary)'}}>SAM Coverage (cm⁻²)</div>
                </div>
                <div style={{background:'var(--bg-elevated)',borderRadius:6,padding:8,textAlign:'center',border:'1px solid var(--border-default)'}}>
                  <div style={{fontSize:12,fontWeight:600,color:'#42a5f5'}}>{result.ink?.conductivity_S_m?.toExponential(1)}</div>
                  <div style={{fontSize:9,color:'var(--text-tertiary)'}}>σ (S/m)</div>
                </div>
              </div>
            </div>
          ) : activeTab==='fab' ? (
            <div className="animate-in" style={{display:'flex',flexDirection:'column',gap:0}}>
              {result.fabrication_steps?.map((s,i)=>(
                <FabStep key={i} step={s} isActive={true} />
              ))}
              <div style={{marginTop:12,fontSize:10,color:'var(--text-tertiary)',fontFamily:'var(--font-data)'}}>
                Total time: {result.fabrication_steps?.reduce((a,s)=>a+s.duration_min,0)} min
                ({(result.fabrication_steps?.reduce((a,s)=>a+s.duration_min,0)/60).toFixed(1)} hours)
              </div>
            </div>
          ) : (
            <div className="animate-in" style={{fontSize:11,lineHeight:1.8,color:'var(--text-secondary)'}}>
              <div style={{fontSize:14,fontWeight:700,color:'var(--text-primary)',marginBottom:8}}>
                Biosensor Fabrication Report — {analyte} Detection
              </div>
              <div style={{marginBottom:12,padding:10,background:'var(--bg-elevated)',borderRadius:6,border:'1px solid var(--border-default)'}}>
                <strong style={{color:'var(--text-primary)'}}>1. Design Summary</strong><br/>
                Pattern: {result.pattern?.name} (Area: {result.pattern?.area_cm2} cm²)<br/>
                Ink: {result.ink?.name} (σ = {result.ink?.conductivity_S_m?.toExponential(1)} S/m)<br/>
                SAM: {result.surface_chemistry?.name} ({result.surface_chemistry?.chemistry})<br/>
                Coating: {result.coating?.method} → {result.coating?.thickness_nm} nm
              </div>
              <div style={{marginBottom:12,padding:10,background:'var(--bg-elevated)',borderRadius:6,border:'1px solid var(--border-default)'}}>
                <strong style={{color:'var(--text-primary)'}}>2. Predicted Performance</strong><br/>
                Sensitivity: {perf.sensitivity_uA_mM_cm2} μA/mM/cm²<br/>
                LOD: {perf.lod_M} M | Linear: {perf.linear_range_M}<br/>
                Response Time: {perf.response_time_s}s | Stability: {perf.stability_days} days<br/>
                Selectivity: {perf.selectivity_pct}% | RSD: {perf.reproducibility_rsd_pct}%
              </div>
              <div style={{padding:10,background:'var(--bg-elevated)',borderRadius:6,border:'1px solid var(--border-default)'}}>
                <strong style={{color:'var(--text-primary)'}}>3. EIS/CV Integration</strong><br/>
                Rs = {ec.eis?.Rs_ohm} Ω | Rct = {ec.eis?.Rct_ohm} Ω<br/>
                Cdl = {ec.eis?.Cdl_F} F | σ_w = {ec.eis?.sigma_w}<br/>
                CV Peak Current: {ec.cv?.peak_current_uA} μA
              </div>
              <div style={{
                marginTop: 12, padding: 10,
                background: 'rgba(245, 158, 11, 0.08)', borderRadius: 6,
                border: '1px dashed #f59e0b66', fontSize: 11, lineHeight: 1.5,
                color: 'var(--text-secondary)',
              }}>
                <strong style={{ color: '#f59e0b' }}>Manufacturing scaling — not modeled.</strong><br/>
                Yield, materials cost, and time-to-market values were previously
                computed via <code>Math.random()</code> and labelled as ANSYS Fluids
                output. They have been removed. A real yield model would need
                process-window data, a tolerance stack, and a cost BOM that
                we don't have wired up yet.
              </div>
              <div style={{display:'flex', gap:10, marginTop:12}}>
                <button className="btn btn-sm" style={{flex:1, background:'#76b90022',color:'#76b900',border:'1px solid #76b90055'}}
                  onClick={()=>{
                    const profile = JSON.parse(localStorage.getItem('raman_profile') || '{}');
                    generateIEEEReport({
                      title: `Computational Design and Optimization of Electrochemical Biosensor for ${analyte} Detection`,
                      authors: profile.name || 'Research Team',
                      affiliation: profile.organization || 'VidyuthLabs Pvt. Ltd.',
                      type: 'biosensor',
                      data: result,
                      params: { pattern, ink, sam, coating_method: coating, analyte, spin_rpm: spinRpm, spin_time_s: spinTime },
                      plotCanvases: [],
                    });
                  }}><Download size={12} style={{marginRight:4}} /> IEEE Report (PDF)</button>
                  <button className="btn btn-sm" style={{flex:1, background:'var(--bg-elevated)',color:'var(--text-secondary)',border:'1px solid var(--border-default)'}}
                    onClick={()=>{
                      const blob = new Blob([JSON.stringify(result,null,2)], {type:'application/json'});
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a'); a.href=url;
                      a.download=`biosensor_report_${analyte}_${Date.now()}.json`; a.click();
                  }}>Export JSON</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
