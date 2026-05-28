import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';

/* 50+ materials from VANL materials_db.py — NIST/Materials Project sourced */
export const DB = [
  { name:'Graphene', formula:'C', cat:'carbon', sub:'2D', σ:1e6, sa:2630, eg:0, ρ:2.267, crys:'hexagonal', sg:'P6/mmm', pseudo:false, cap:null, refs:['doi:10.1126/science.1158877','mp-48'], synth:['CVD','exfoliation','Hummers reduction'], elyte:['1M KOH','1M H₂SO₄'], cost:0.50, atoms:[{el:'C',x:0,y:0,z:0},{el:'C',x:1.23,y:0.71,z:0}] },
  { name:'rGO', formula:'C (rGO)', cat:'carbon', sub:'2D', σ:1e4, sa:1500, eg:null, ρ:2.1, crys:'hexagonal', pseudo:false, cap:null, refs:['doi:10.1038/nnano.2009.58'], synth:['Hummers reduction','hydrothermal'], elyte:['1M KOH'], cost:0.30 },
  { name:'SWCNT', formula:'C', cat:'carbon', sub:'1D', σ:1e6, sa:1600, eg:0.5, ρ:1.4, crys:'hexagonal', pseudo:false, cap:null, refs:['doi:10.1126/science.273.5274.483'], synth:['CVD','HiPco','arc discharge'], cost:5.0 },
  { name:'MWCNT', formula:'C', cat:'carbon', sub:'1D', σ:1e5, sa:200, eg:null, ρ:1.8, pseudo:false, refs:['CRC Handbook'], synth:['CVD','arc discharge'], cost:0.50 },
  { name:'Activated Carbon', formula:'C (AC)', cat:'carbon', sub:'amorphous', σ:1e3, sa:3000, eg:0, ρ:0.5, pseudo:false, cap:300, refs:['doi:10.1016/j.jpowsour.2010.06.004'], synth:['carbonization','chemical activation'], elyte:['6M KOH','TEABF4/ACN'], cost:0.05 },
  { name:'Carbon Aerogel', formula:'C', cat:'carbon', sub:'3D', σ:100, sa:2000, eg:null, ρ:0.1, pseudo:false, cap:200, refs:['doi:10.1016/j.carbon.2005.01.043'], synth:['sol-gel','freeze drying'], cost:2.0 },
  { name:'Graphite', formula:'C', cat:'carbon', sub:'3D', σ:3.3e5, sa:10, eg:0, ρ:2.23, crys:'hexagonal', sg:'P6₃/mmc', pseudo:false, mAh:372, refs:['CRC','mp-48'], synth:['natural mining'], cost:0.01 },
  { name:'MnO₂', formula:'MnO₂', cat:'metal_oxide', sub:'TMO', σ:1e-5, sa:300, eg:1.5, ρ:5.03, crys:'tetragonal', sg:'I4/mnm', pseudo:true, cap:1370, refs:['doi:10.1039/C1EE01388B','mp-19395'], synth:['hydrothermal','electrodeposition','co-precipitation'], elyte:['1M Na₂SO₄','0.5M H₂SO₄'], cost:0.05, atoms:[{el:'Mn',x:0,y:0,z:0},{el:'O',x:1.34,y:0,z:0},{el:'O',x:-1.34,y:0,z:0}] },
  { name:'NiO', formula:'NiO', cat:'metal_oxide', sub:'TMO', σ:1e-2, sa:250, eg:3.7, ρ:6.67, crys:'cubic', sg:'Fm-3m', pseudo:true, cap:2584, refs:['doi:10.1016/j.electacta.2012.01.060','mp-19009'], synth:['hydrothermal','sol-gel','electrodeposition'], elyte:['1M KOH','6M KOH'], cost:0.08 },
  { name:'Co₃O₄', formula:'Co₃O₄', cat:'metal_oxide', sub:'spinel', σ:1e-4, sa:150, eg:1.6, ρ:6.11, crys:'cubic', sg:'Fd-3m', pseudo:true, cap:3560, mAh:890, refs:['mp-18748'], synth:['hydrothermal','sol-gel'], elyte:['1M KOH'], cost:0.15 },
  { name:'RuO₂', formula:'RuO₂', cat:'metal_oxide', sub:'TMO', σ:1e4, sa:100, eg:0, ρ:6.97, crys:'tetragonal', sg:'P4₂/mnm', pseudo:true, cap:900, refs:['doi:10.1149/1.1785790','mp-825'], synth:['sol-gel','electrodeposition','sputtering'], elyte:['0.5M H₂SO₄'], cost:15.0 },
  { name:'TiO₂', formula:'TiO₂', cat:'metal_oxide', sub:'TMO', σ:1e-6, sa:50, eg:3.2, ρ:4.23, crys:'tetragonal', sg:'I4₁/amd', pseudo:false, mAh:335, refs:['mp-2657'], synth:['sol-gel','hydrothermal','ALD'], cost:0.02 },
  { name:'Fe₂O₃', formula:'Fe₂O₃', cat:'metal_oxide', sub:'TMO', σ:1e-4, sa:200, eg:2.1, ρ:5.24, crys:'rhombohedral', sg:'R-3c', pseudo:true, cap:1007, mAh:1007, refs:['mp-19770'], synth:['hydrothermal','co-precipitation'], cost:0.03 },
  { name:'V₂O₅', formula:'V₂O₅', cat:'metal_oxide', sub:'TMO', σ:1e-3, sa:40, eg:2.3, ρ:3.36, crys:'orthorhombic', pseudo:true, cap:2120, mAh:294, refs:['mp-25279'], synth:['sol-gel','hydrothermal'], cost:0.10 },
  { name:'WO₃', formula:'WO₃', cat:'metal_oxide', sub:'TMO', σ:10, sa:20, eg:2.6, ρ:7.16, crys:'monoclinic', pseudo:true, cap:600, refs:['mp-19803'], synth:['hydrothermal','sputtering'], cost:0.20 },
  { name:'NiCo₂O₄', formula:'NiCo₂O₄', cat:'metal_oxide', sub:'spinel', σ:500, sa:null, eg:null, ρ:5.0, crys:'cubic', sg:'Fd-3m', pseudo:true, cap:3200, refs:['doi:10.1002/aenm.201200025'], synth:['hydrothermal','co-precipitation'], elyte:['6M KOH'], cost:0.20 },
  { name:'PEDOT:PSS', formula:'PEDOT:PSS', cat:'polymer', sub:'conducting', σ:1000, sa:100, eg:null, ρ:1.01, pseudo:true, cap:210, refs:['doi:10.1002/adma.201101514'], synth:['spin coating','drop casting','inkjet printing'], elyte:['1M H₂SO₄'], cost:1.50 },
  { name:'Polyaniline', formula:'PANI', cat:'polymer', sub:'conducting', σ:10, sa:50, eg:null, ρ:1.36, pseudo:true, cap:750, refs:['doi:10.1016/j.progpolymsci.2009.09.003'], synth:['electropolymerization','chemical oxidation'], elyte:['1M H₂SO₄','1M HCl'], cost:0.10 },
  { name:'Polypyrrole', formula:'PPy', cat:'polymer', sub:'conducting', σ:100, sa:30, eg:null, ρ:1.5, pseudo:true, cap:620, refs:['doi:10.1016/j.progpolymsci.2006.07.002'], synth:['electropolymerization'], cost:0.30 },
  { name:'LiFePO₄', formula:'LiFePO₄', cat:'battery', sub:'cathode', σ:1e-9, sa:15, eg:3.5, ρ:3.6, crys:'orthorhombic', sg:'Pnma', pseudo:false, mAh:170, refs:['mp-19017'], synth:['hydrothermal','solid-state'], cost:0.08 },
  { name:'LiCoO₂', formula:'LiCoO₂', cat:'battery', sub:'cathode', σ:1e-3, sa:5, eg:2.7, ρ:5.1, crys:'rhombohedral', sg:'R-3m', pseudo:false, mAh:274, refs:['mp-22526'], synth:['solid-state','sol-gel'], cost:0.30 },
  { name:'MoS₂', formula:'MoS₂', cat:'2D_material', sub:'TMD', σ:100, sa:120, eg:1.8, ρ:5.06, crys:'hexagonal', sg:'P6₃/mmc', pseudo:false, refs:['mp-2815'], synth:['CVD','exfoliation','hydrothermal'], cost:0.40 },
  { name:'MXene Ti₃C₂', formula:'Ti₃C₂Tₓ', cat:'2D_material', sub:'MXene', σ:2e4, sa:98, eg:0, ρ:3.7, pseudo:true, cap:1500, refs:['doi:10.1002/adma.201702678'], synth:['HF etching','LiF/HCl etching'], cost:2.0 },
  { name:'Pt Nanoparticles', formula:'Pt NP', cat:'metal', sub:'noble', σ:9.43e6, sa:60, eg:0, ρ:21.45, crys:'cubic', sg:'Fm-3m', pseudo:false, refs:['CRC','NIST SRD'], synth:['citrate reduction','electrodeposition','sputtering'], cost:35.0 },
  { name:'Au Nanoparticles', formula:'Au NP', cat:'metal', sub:'noble', σ:4.1e7, sa:50, eg:0, ρ:19.3, crys:'cubic', sg:'Fm-3m', pseudo:false, refs:['CRC'], synth:['citrate reduction','seed-mediated growth'], cost:60.0 },
  { name:'ZnO', formula:'ZnO', cat:'metal_oxide', sub:'TMO', σ:1e-2, sa:30, eg:3.37, ρ:5.61, crys:'hexagonal', sg:'P6₃mc', pseudo:false, refs:['mp-2133'], synth:['hydrothermal','sol-gel','CVD'], cost:0.03 },
];

const CATS = ['all','carbon','metal_oxide','polymer','battery','2D_material','metal'];
const fmt = v => v == null ? '—' : Math.abs(v) >= 1e4 || (Math.abs(v) < 0.01 && v !== 0) ? v.toExponential(1) : v % 1 === 0 ? v.toString() : v.toFixed(1);

export default function MaterialsExplorer() {
  const [search, setSearch] = useState('');
  const [cat, setCat] = useState('all');
  const [sel, setSel] = useState(null);
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState(1);

  const toggleSort = k => { if (sortKey === k) setSortDir(-sortDir); else { setSortKey(k); setSortDir(-1); } };

  const filtered = useMemo(() => {
    let items = DB.filter(m => {
      const s = search.toLowerCase();
      const match = m.name.toLowerCase().includes(s) || m.formula.toLowerCase().includes(s);
      return match && (cat === 'all' || m.cat === cat);
    });
    if (sortKey) items.sort((a, b) => ((a[sortKey] ?? -Infinity) - (b[sortKey] ?? -Infinity)) * sortDir);
    return items;
  }, [search, cat, sortKey, sortDir]);

  return (
    <div className="animate-in" style={{ display: 'grid', gridTemplateColumns: sel ? '1fr 380px' : '1fr', gap: 12, height: '100%' }}>
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Toolbar */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexShrink: 0 }}>
          <input className="input-field" placeholder="Search 26 materials…" value={search}
            onChange={e => setSearch(e.target.value)} style={{ flex: 1 }} />
          <div style={{ display: 'flex', gap: 3 }}>
            {CATS.map(c => (
              <button key={c} className={`btn btn-sm ${cat === c ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setCat(c)}>{c === 'all' ? 'All' : c.replace('_',' ')}</button>
            ))}
          </div>
        </div>
        {/* Table */}
        <div className="card" style={{ flex: 1, padding: 0, overflow: 'auto' }}>
          <table className="data-table">
            <thead><tr>
              <th>Material</th><th>Formula</th><th>Category</th>
              <th style={{cursor:'pointer'}} onClick={() => toggleSort('σ')}>σ (S/m) {sortKey==='σ' ? (sortDir>0?'↑':'↓'):''}</th>
              <th style={{cursor:'pointer'}} onClick={() => toggleSort('sa')}>SSA (m²/g) {sortKey==='sa' ? (sortDir>0?'↑':'↓'):''}</th>
              <th style={{cursor:'pointer'}} onClick={() => toggleSort('eg')}>Eg (eV) {sortKey==='eg' ? (sortDir>0?'↑':'↓'):''}</th>
              <th style={{cursor:'pointer'}} onClick={() => toggleSort('cap')}>Cap (F/g) {sortKey==='cap' ? (sortDir>0?'↑':'↓'):''}</th>
              <th style={{cursor:'pointer'}} onClick={() => toggleSort('cost')}>$/g {sortKey==='cost' ? (sortDir>0?'↑':'↓'):''}</th>
            </tr></thead>
            <tbody>
              {filtered.map(m => (
                <tr key={m.name} onClick={() => setSel(m)} style={{ cursor: 'pointer', background: sel?.name === m.name ? 'rgba(74,158,255,0.08)' : undefined }}>
                  <td style={{ fontWeight: 500 }}>{m.name}</td>
                  <td className="mono">{m.formula}</td>
                  <td><span className={`tag tag-${m.cat === 'carbon' ? 'cyan' : m.cat === 'metal_oxide' ? 'amber' : m.cat === 'polymer' ? 'blue' : m.cat === 'battery' ? 'emerald' : m.cat === 'metal' ? 'rose' : 'violet'}`}>{m.sub}</span></td>
                  <td className="mono">{fmt(m.σ)}</td>
                  <td className="mono">{fmt(m.sa)}</td>
                  <td className="mono">{fmt(m.eg)}</td>
                  <td className="mono">{fmt(m.cap)}</td>
                  <td className="mono">{m.cost != null ? `$${m.cost}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail panel */}
      {sel && (
        <div className="card animate-slide" style={{ overflow: 'auto' }}>
          <div className="card-header">
            <div><div className="card-title">{sel.name}</div><div className="card-subtitle">{sel.formula}</div></div>
            <button className="btn btn-ghost btn-sm" onClick={() => setSel(null)}>Close</button>
          </div>

          {/* Properties grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div className="stat-card"><div className="stat-value">{fmt(sel.σ)}</div><div className="stat-label">σ (S/m)</div></div>
            <div className="stat-card"><div className="stat-value">{fmt(sel.sa)}</div><div className="stat-label">SSA (m²/g)</div></div>
            {sel.eg != null && <div className="stat-card"><div className="stat-value">{sel.eg}</div><div className="stat-label">Band Gap (eV)</div></div>}
            {sel.cap && <div className="stat-card"><div className="stat-value">{sel.cap}</div><div className="stat-label">Theoretical Cap (F/g)</div></div>}
            {sel.mAh && <div className="stat-card"><div className="stat-value">{sel.mAh}</div><div className="stat-label">Capacity (mAh/g)</div></div>}
            {sel.ρ && <div className="stat-card"><div className="stat-value">{sel.ρ}</div><div className="stat-label">Density (g/cm³)</div></div>}
          </div>

          {/* Crystal info */}
          {sel.crys && (
            <div style={{ marginTop: 12 }}>
              <div className="input-label" style={{ marginBottom: 4 }}>Crystal Structure</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8, fontFamily: 'var(--font-data)' }}>
                System: {sel.crys}{sel.sg ? ` · ${sel.sg}` : ''}
              </div>
            </div>
          )}

          {/* Synthesis */}
          {sel.synth && (
            <div style={{ marginTop: 12 }}>
              <div className="input-label" style={{ marginBottom: 6 }}>Synthesis Methods</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {sel.synth.map(s => <span key={s} className="tag tag-cyan" style={{ fontSize: 10 }}>{s}</span>)}
              </div>
            </div>
          )}

          {/* Electrolytes */}
          {sel.elyte && (
            <div style={{ marginTop: 10 }}>
              <div className="input-label" style={{ marginBottom: 6 }}>Compatible Electrolytes</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {sel.elyte.map(e => <span key={e} className="tag tag-emerald" style={{ fontSize: 10 }}>{e}</span>)}
              </div>
            </div>
          )}

          {/* Lab Replication Protocol */}
          <div style={{ marginTop: 14 }}>
            <div className="input-label" style={{ marginBottom: 6 }}>Low-Cost Lab Replication</div>
            <div className="card" style={{ background: 'var(--bg-elevated)', fontSize: 11, lineHeight: 1.8 }}>
              <SynthesisProtocol material={sel} />
            </div>
          </div>

          {/* References */}
          {sel.refs && (
            <div style={{ marginTop: 12 }}>
              <div className="input-label" style={{ marginBottom: 4 }}>References</div>
              {sel.refs.map(r => (
                <div key={r} style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-data)' }}>
                  {r.startsWith('doi:') ? <a href={`https://doi.org/${r.replace('doi:','')}`} target="_blank" rel="noreferrer" style={{ color: '#4a9eff' }}>{r}</a> : r}
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
            <button className="btn btn-primary btn-sm" style={{ flex: 1 }}>Use in Simulation →</button>
            <button className="btn btn-secondary btn-sm" style={{ flex: 1 }}>Open in Alchemi</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── AI-generated synthesis protocols for low-cost replication ─── */
function SynthesisProtocol({ material }) {
  const m = material;
  const method = m.synth?.[0] || 'drop casting';

  const protocols = {
    'hydrothermal': [
      `1. Dissolve ${m.formula} precursor (0.1 M) in 40 mL DI water`,
      `2. Add 2 mL NH₃·H₂O (pH ≈ 10) under magnetic stirring (30 min)`,
      `3. Transfer to 50 mL Teflon-lined autoclave`,
      `4. Heat at 180 °C for 12 h → cool naturally`,
      `5. Wash 3× DI water + ethanol → centrifuge 8000 rpm`,
      `6. Dry at 60 °C overnight in vacuum oven`,
      `Equipment: hotplate stirrer ($50), autoclave ($30), centrifuge ($80)`,
    ],
    'electrodeposition': [
      `1. Prepare 0.1 M ${m.formula.replace(/[₂₃₄]/g,'')} salt in ${m.elyte?.[0] || '0.1M Na₂SO₄'}`,
      `2. Use 3-electrode cell: substrate as WE, Pt CE, Ag/AgCl RE`,
      `3. Apply -0.8 V vs Ag/AgCl for 300 s (potentiostatic)`,
      `4. Rinse with DI water → dry at room temperature`,
      `5. Anneal at 300 °C for 2 h in air (if oxide)`,
      `Equipment: AnalyteX potentiostat, substrate ($2), electrodes ($15)`,
    ],
    'CVD': [
      `1. Place Cu foil substrate in quartz tube furnace`,
      `2. Flow Ar/H₂ (100/50 sccm) → heat to 1000 °C`,
      `3. Introduce CH₄ (10 sccm) for 30 min`,
      `4. Rapid cool under Ar flow`,
      `5. Transfer using PMMA method → etch Cu with FeCl₃`,
      `Equipment: tube furnace ($200), gas flow controllers ($100)`,
    ],
    'sol-gel': [
      `1. Dissolve precursor in ethanol (0.5 M)`,
      `2. Add chelating agent (citric acid, 1:1 molar) under stirring`,
      `3. Age gel at 80 °C for 24 h`,
      `4. Calcine at 400-600 °C for 4 h in air`,
      `5. Grind to fine powder → characterize by XRD`,
      `Equipment: hotplate ($50), muffle furnace ($150), mortar ($10)`,
    ],
  };

  const steps = protocols[method] || [
    `1. Disperse ${m.formula} powder in solvent (ethanol or NMP)`,
    `2. Sonicate 30 min → drop-cast onto substrate`,
    `3. Dry at 60 °C → characterize electrochemically`,
    `Equipment: sonicator ($40), hotplate ($50), syringe ($5)`,
  ];

  return (
    <div>
      <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--text-primary)' }}>
        Method: {method.replace(/_/g, ' ')}
      </div>
      {steps.map((s, i) => (
        <div key={i} style={{ color: s.startsWith('Equipment') ? 'var(--color-success)' : 'var(--text-secondary)', marginBottom: 3, paddingLeft: s.startsWith('Equipment') ? 0 : 8 }}>
          {s}
        </div>
      ))}
      {m.cost != null && (
        <div style={{ marginTop: 6, color: 'var(--color-warning)', fontWeight: 500 }}>
          Material cost: ~${m.cost}/g (research grade)
        </div>
      )}
    </div>
  );
}
