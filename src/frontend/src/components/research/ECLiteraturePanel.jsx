import React, { useState, useEffect, useCallback, useRef } from 'react';

const API = 'http://127.0.0.1:8000';

/* ─── tiny style helpers ────────────────────────────────────────────────── */
const card  = (extra={}) => ({ background:'var(--bg-secondary)', border:'1px solid var(--border-primary)', borderRadius:'var(--radius)', padding:16, ...extra });
const mono  = { fontFamily:'var(--font-mono)', fontSize:11 };
const pill  = (c='blue') => {
  const map = { blue:'rgba(59,130,246,.15)',green:'rgba(34,197,94,.15)',amber:'rgba(245,158,11,.15)',red:'rgba(239,68,68,.15)',gray:'var(--bg-tertiary)' };
  const col = { blue:'#60a5fa',green:'#4ade80',amber:'#fbbf24',red:'#f87171',gray:'var(--text-tertiary)' };
  return { display:'inline-flex',alignItems:'center',padding:'2px 8px',borderRadius:99,fontSize:10.5,fontWeight:500, background:map[c]||map.gray, color:col[c]||col.gray };
};
const row   = { display:'flex',alignItems:'center',gap:8 };
const th    = { textAlign:'left',padding:'7px 10px',fontSize:10.5,fontWeight:600,color:'var(--text-tertiary)',borderBottom:'1px solid var(--border-primary)',whiteSpace:'nowrap',background:'var(--bg-tertiary)' };
const td    = (mono=false) => ({ padding:'6px 10px',borderBottom:'1px solid var(--border-primary)',fontSize:11.5,color:'var(--text-secondary)',verticalAlign:'top', fontFamily:mono?'var(--font-mono)':'inherit' });
const btn   = (v='ghost') => ({ padding:'7px 14px',borderRadius:'var(--radius-sm)',border:'1px solid',cursor:'pointer',fontSize:12,fontWeight:500,transition:'all .15s',
  background: v==='primary'?'var(--accent)':v==='danger'?'transparent':'transparent',
  borderColor: v==='primary'?'var(--accent)':v==='danger'?'var(--color-error)':'var(--border-secondary)',
  color: v==='primary'?'#fff':v==='danger'?'var(--color-error)':'var(--text-secondary)' });
const sectionTab = (a) => ({ padding:'6px 16px',borderRadius:0,border:'none',borderBottom:`2px solid ${a?'var(--accent)':'transparent'}`,background:'transparent',cursor:'pointer',fontSize:12.5,fontWeight:a?600:400,color:a?'var(--accent)':'var(--text-tertiary)',transition:'all .15s',whiteSpace:'nowrap' });
const input = { width:'100%',padding:'7px 10px',background:'var(--bg-tertiary)',border:'1px solid var(--border-primary)',borderRadius:'var(--radius-sm)',color:'var(--text-primary)',fontSize:12 };

const COMMERCIAL_COLOR = { high:'green', medium:'amber', low:'red' };
const NIM_SECTIONS = ['Overview','Master Table','Materials','Techniques','LOD & Sensitivity','Food Samples','Interference','Commercial','Challenges & Scope'];

export default function ECLiteraturePanel() {
  const [section, setSection] = useState('Overview');
  const [ecTable, setEcTable] = useState([]);
  const [ecTotal, setEcTotal] = useState(0);
  const [review, setReview]   = useState(null);
  const [status, setStatus]   = useState(null);
  const [loading, setLoading] = useState({});
  const [filters, setFilters] = useState({ analyte:'',material:'',technique:'',has_lod:false });
  const [page, setPage]       = useState(0);
  const PAGE = 100;

  const load = (k,v) => setLoading(p=>({...p,[k]:v}));

  /* ── fetches ── */
  const fetchStatus  = useCallback(()=>fetch(`${API}/api/v2/drive/status`).then(r=>r.json()).then(setStatus).catch(()=>{}), []);
  const fetchReview  = useCallback(()=>{
    load('review',true);
    return fetch(`${API}/api/v2/drive/review`).then(r=>r.json()).then(setReview).catch(()=>{}).finally(()=>load('review',false));
  }, []);
  const fetchTable = useCallback(()=>{
    load('table',true);
    const p = new URLSearchParams({ limit:PAGE, offset:page*PAGE });
    if(filters.analyte)   p.set('analyte',filters.analyte);
    if(filters.material)  p.set('material',filters.material);
    if(filters.technique) p.set('technique',filters.technique);
    if(filters.has_lod)   p.set('has_lod','true');
    fetch(`${API}/api/v2/drive/ec-table?${p}`)
      .then(r=>r.json()).then(d=>{ setEcTable(d.records||[]); setEcTotal(d.total||0); })
      .catch(()=>{}).finally(()=>load('table',false));
  }, [filters, page]);

  useEffect(()=>{ fetchStatus(); fetchReview(); fetchTable(); },[]);
  useEffect(()=>{ if(section==='Master Table') fetchTable(); }, [section, filters, page]);
  useEffect(()=>{
    const iv = setInterval(()=>{ if(status?.sync?.running||status?.extract?.running) fetchStatus(); }, 2500);
    return ()=>clearInterval(iv);
  },[status]);

  /* ── actions ── */
  const startSync    = async(force=false)=>{ await fetch(`${API}/api/v2/drive/sync?force=${force}`,{method:'POST'}); fetchStatus(); };
  const startExtract = async(nim=true) =>{ await fetch(`${API}/api/v2/drive/extract?use_nim=${nim}`,{method:'POST'}); fetchStatus(); };
  const exportMD     = ()=>window.open(`${API}/api/v2/drive/review/markdown`,'_blank');
  const exportJSON   = ()=>window.open(`${API}/api/v2/drive/review/export`,'_blank');

  const isSyncing   = status?.sync?.running;
  const isExtracting = status?.extract?.running;

  return (
    <div style={{display:'flex',flexDirection:'column',height:'100%',gap:0}}>
      {/* ── Header bar ── */}
      <div style={{display:'flex',alignItems:'center',gap:12,paddingBottom:10,borderBottom:'1px solid var(--border-primary)',marginBottom:10,flexShrink:0}}>
        <div style={{flex:1}}>
          <div style={{fontSize:15,fontWeight:700,color:'var(--text-primary)'}}>EC Sensor Literature Review</div>
          <div style={{fontSize:11,color:'var(--text-tertiary)'}}>
            Docling · PyMuPDF · NIM validation · {ecTotal} records · {status?.drive_papers||0} Drive papers
          </div>
        </div>
        <div style={{display:'flex',gap:6}}>
          <button style={btn()} onClick={()=>{ fetchStatus(); fetchTable(); fetchReview(); }}>↻</button>
          <button style={{...btn('ghost'),opacity:isSyncing?.6:1}} disabled={isSyncing} onClick={()=>startSync()}>
            {isSyncing?'⟳ Syncing…':'⬆ Sync Drive'}
          </button>
          <button style={{...btn('primary'),opacity:isExtracting?.6:1}} disabled={isExtracting} onClick={()=>startExtract(true)}>
            {isExtracting?`⟳ ${status?.extract?.progress||'Extracting…'}`:'⚡ Extract (NIM)'}
          </button>
          <button style={btn()} onClick={exportMD}>⬇ MD</button>
          <button style={btn()} onClick={exportJSON}>⬇ JSON</button>
        </div>
      </div>

      {/* ── Auth warning ── */}
      {status && !status.connected && (
        <div style={{background:'rgba(245,158,11,.08)',border:'1px solid rgba(245,158,11,.25)',borderRadius:'var(--radius-sm)',padding:'10px 14px',fontSize:11.5,color:'#fbbf24',marginBottom:10}}>
          ⚠ Drive not connected. Share folder with: <strong style={mono}>{status.service_account_email}</strong>
          {' '}— then paste your full <code>service_account.json</code> into the <strong>GOOGLE_SERVICE_ACCOUNT_JSON</strong> secret.
        </div>
      )}

      {/* ── Progress bars ── */}
      {(isSyncing||isExtracting) && (
        <div style={{background:'rgba(59,130,246,.08)',border:'1px solid rgba(59,130,246,.2)',borderRadius:'var(--radius-sm)',padding:'8px 14px',fontSize:11.5,color:'#93c5fd',marginBottom:8}}>
          ⟳ {isSyncing ? status?.sync?.progress : status?.extract?.progress}
        </div>
      )}

      {/* ── Section tabs ── */}
      <div style={{display:'flex',overflowX:'auto',borderBottom:'1px solid var(--border-primary)',marginBottom:12,flexShrink:0}}>
        {NIM_SECTIONS.map(s=><button key={s} style={sectionTab(section===s)} onClick={()=>setSection(s)}>{s}</button>)}
      </div>

      {/* ── Content ── */}
      <div style={{flex:1,overflowY:'auto'}}>
        {section==='Overview'        && <OverviewSection status={status} review={review} onSync={startSync} onExtract={startExtract}/>}
        {section==='Master Table'    && <MasterTable records={ecTable} total={ecTotal} loading={loading.table} filters={filters} setFilters={setFilters} page={page} setPage={setPage} PAGE={PAGE}/>}
        {section==='Materials'       && <MaterialsSection review={review}/>}
        {section==='Techniques'      && <TechniquesSection review={review}/>}
        {section==='LOD & Sensitivity' && <LodSection review={review}/>}
        {section==='Food Samples'    && <FoodSection review={review}/>}
        {section==='Interference'    && <InterferenceSection review={review}/>}
        {section==='Commercial'      && <CommercialSection review={review}/>}
        {section==='Challenges & Scope' && <ChallengesSection review={review}/>}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Overview
══════════════════════════════════════════════════════════════════════════════ */
function OverviewSection({ status, review, onSync, onExtract }) {
  const stats = [
    ['Total papers', review?.total_papers ?? '—'],
    ['From Drive', review?.drive_papers ?? '—'],
    ['LOD records', review?.lod_table?.length ?? '—'],
    ['Sensitivity records', review?.sensitivity_table?.length ?? '—'],
    ['Materials found', Object.keys(review?.material_counts||{}).length],
    ['Food sample types', Object.keys(review?.food_sample_counts||{}).length],
  ];
  return (
    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
      {/* Stats */}
      <div style={card()}>
        <div style={{fontSize:12,fontWeight:600,color:'var(--text-primary)',marginBottom:12}}>Pipeline Statistics</div>
        <div style={{display:'flex',flexWrap:'wrap',gap:8}}>
          {stats.map(([l,v])=>(
            <div key={l} style={{flex:'1 1 140px',background:'var(--bg-tertiary)',borderRadius:'var(--radius-sm)',padding:'10px 12px',textAlign:'center'}}>
              <div style={{fontSize:22,fontWeight:700,color:'var(--accent)',lineHeight:1}}>{v}</div>
              <div style={{fontSize:10,color:'var(--text-tertiary)',marginTop:3}}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Sync status */}
      <div style={card()}>
        <div style={{fontSize:12,fontWeight:600,color:'var(--text-primary)',marginBottom:12}}>Sync & Extraction</div>
        {status?.sync?.last_stats && (
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,marginBottom:12}}>
            {Object.entries(status.sync.last_stats).map(([k,v])=>(
              <div key={k} style={{...row,gap:6,fontSize:11}}>
                <span style={{color:'var(--text-tertiary)',textTransform:'capitalize'}}>{k.replace(/_/g,' ')}:</span>
                <span style={{color:'var(--text-primary)',fontWeight:600}}>{v}</span>
              </div>
            ))}
          </div>
        )}
        <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
          <button style={btn('primary')} onClick={()=>onSync()}>Sync Drive</button>
          <button style={btn()} onClick={()=>onSync(true)}>Force Re-sync</button>
          <button style={btn()} onClick={()=>onExtract(true)}>Extract (NIM)</button>
          <button style={btn()} onClick={()=>onExtract(false)}>Extract (Regex)</button>
        </div>
      </div>

      {/* How it works */}
      <div style={{...card(),gridColumn:'1/-1'}}>
        <div style={{fontSize:12,fontWeight:600,color:'var(--text-primary)',marginBottom:12}}>Processing Pipeline</div>
        <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:10}}>
          {[
            ['1 Scan','Drive folder scanned recursively. 200+ PDFs / Docs found.'],
            ['2 Parse','Docling (tables+headings) → PyMuPDF → pdfminer fallback.'],
            ['3 Regex','LOD, sensitivity, scan rate, electrode type, food samples extracted.'],
            ['4 NIM AI','LLaMA-3.3-70B validates & enriches each record with structured JSON.'],
            ['5 Review','Master EC comparison table + 13-section literature review generated.'],
          ].map(([title,desc])=>(
            <div key={title} style={{background:'var(--bg-tertiary)',borderRadius:'var(--radius-sm)',padding:'10px 12px'}}>
              <div style={{fontSize:12,fontWeight:700,color:'var(--accent)',marginBottom:4}}>{title}</div>
              <div style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.5}}>{desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Top analytes */}
      {review && (
        <div style={card()}>
          <div style={{fontSize:11,fontWeight:500,color:'var(--text-tertiary)',marginBottom:10,textTransform:'uppercase',letterSpacing:'.05em'}}>Top Analytes</div>
          {Object.entries(review.analyte_counts||{}).slice(0,8).map(([a,c])=>(
            <BarRow key={a} label={a} value={c} max={Object.values(review.analyte_counts)[0]||1}/>
          ))}
        </div>
      )}

      {/* Top techniques */}
      {review && (
        <div style={card()}>
          <div style={{fontSize:11,fontWeight:500,color:'var(--text-tertiary)',marginBottom:10,textTransform:'uppercase',letterSpacing:'.05em'}}>Top Techniques</div>
          {Object.entries(review.technique_counts||{}).slice(0,8).map(([t,c])=>(
            <BarRow key={t} label={t} value={c} max={Object.values(review.technique_counts)[0]||1} color='#60a5fa'/>
          ))}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Master Table
══════════════════════════════════════════════════════════════════════════════ */
function MasterTable({ records, total, loading, filters, setFilters, page, setPage, PAGE }) {
  const [expanded, setExpanded] = useState(null);
  const setF = (k,v) => { setFilters(p=>({...p,[k]:v})); setPage(0); };

  return (
    <div style={{display:'flex',flexDirection:'column',gap:10}}>
      {/* Filters */}
      <div style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center'}}>
        <input style={{...input,width:160}} placeholder="Filter analyte…" value={filters.analyte} onChange={e=>setF('analyte',e.target.value)}/>
        <input style={{...input,width:160}} placeholder="Filter material…" value={filters.material} onChange={e=>setF('material',e.target.value)}/>
        <input style={{...input,width:130}} placeholder="Technique (CV, DPV…)" value={filters.technique} onChange={e=>setF('technique',e.target.value)}/>
        <label style={{display:'flex',alignItems:'center',gap:6,fontSize:12,color:'var(--text-secondary)',cursor:'pointer'}}>
          <input type="checkbox" checked={filters.has_lod} onChange={e=>setF('has_lod',e.target.checked)}/>
          Has LOD
        </label>
        <span style={{fontSize:11,color:'var(--text-tertiary)',marginLeft:'auto'}}>{total} records</span>
        {total > PAGE && (
          <div style={{display:'flex',gap:4}}>
            <button style={btn()} disabled={page===0} onClick={()=>setPage(p=>p-1)}>‹</button>
            <span style={{fontSize:11,color:'var(--text-tertiary)',padding:'4px 8px'}}>{page+1}/{Math.ceil(total/PAGE)}</span>
            <button style={btn()} disabled={(page+1)*PAGE>=total} onClick={()=>setPage(p=>p+1)}>›</button>
          </div>
        )}
      </div>

      {loading ? <Loading/> : (
        <div style={{overflowX:'auto'}}>
          <table style={{width:'100%',borderCollapse:'collapse',fontSize:11.5}}>
            <thead>
              <tr style={{background:'var(--bg-tertiary)'}}>
                {['Ref','Material','Electrode','Technique','LOD','Sensitivity','Sample Type','Interference','Potential','NIM'].map(h=>(
                  <th key={h} style={th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((r,i)=>(
                <React.Fragment key={r.ref||i}>
                  <tr style={{cursor:'pointer',background:expanded===i?'var(--accent-muted)':'transparent'}}
                      onClick={()=>setExpanded(expanded===i?null:i)}>
                    <td style={td()}><a href={r.url} target="_blank" rel="noreferrer" style={{color:'var(--accent)'}} onClick={e=>e.stopPropagation()}>{r.ref}</a></td>
                    <td style={{...td(),maxWidth:160}}><span title={r.material}>{(r.material||'—').slice(0,40)}{r.material?.length>40?'…':''}</span></td>
                    <td style={td()}><span style={pill('blue')}>{r.electrode||'—'}</span></td>
                    <td style={td()}>{(r.techniques||[]).map(t=><span key={t} style={{...pill('amber'),marginRight:3}}>{t}</span>)}</td>
                    <td style={td(true)}><span style={{color:'var(--color-success)',fontWeight:600}}>{r.lod||'—'}</span></td>
                    <td style={td(true)}>{r.sensitivity||'—'}</td>
                    <td style={td()}>{(r.sample_types||[]).slice(0,2).join(', ')||'—'}</td>
                    <td style={{...td(),maxWidth:160}}><span title={r.interference_study||''}>{r.interference_study?.slice(0,50)||'—'}</span></td>
                    <td style={td()}><span style={pill(COMMERCIAL_COLOR[r.commercial_potential]||'gray')}>{r.commercial_potential||'—'}</span></td>
                    <td style={td()}>{r.nim_validated?<span style={pill('green')}>✓</span>:<span style={pill('gray')}>—</span>}</td>
                  </tr>
                  {expanded===i && (
                    <tr key={`exp-${i}`}>
                      <td colSpan={10} style={{background:'var(--bg-tertiary)',padding:'12px 16px'}}>
                        <ExpandedRow r={r}/>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {!records.length && (
                <tr><td colSpan={10} style={{...td(),textAlign:'center',padding:32,color:'var(--text-tertiary)'}}>
                  No records. Sync Drive papers then click Extract (NIM).
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ExpandedRow({ r }) {
  return (
    <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12}}>
      <div>
        <Field label="Title">{r.title}</Field>
        <Field label="Authors">{(r.authors||[]).slice(0,3).join(', ')}</Field>
        <Field label="Year">{r.year}</Field>
        <Field label="Journal">{r.journal}</Field>
        <Field label="Material formula">{r.material_formula}</Field>
        <Field label="Fabrication">{r.fabrication}</Field>
      </div>
      <div>
        <Field label="Linear range">{r.linear_range}</Field>
        <Field label="Recovery">{r.recovery_pct}</Field>
        <Field label="Interferents">{(r.interferents||[]).join(', ')}</Field>
        <Field label="Interference study">{r.interference_study}</Field>
        <Field label="Sample types">{(r.sample_types||[]).join(', ')}</Field>
      </div>
      <div>
        <Field label="Commercial keywords">{(r.commercial_keywords||[]).join(', ')}</Field>
        <Field label="Characterization">{(r.characterization||[]).join(', ')}</Field>
        <Field label="Challenges">{(r.challenges||[]).join(', ')}</Field>
        <Field label="Confidence">{r.confidence ? `${(r.confidence*100).toFixed(0)}%` : '—'}</Field>
        <Field label="Source">{r.source}</Field>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  if (!children) return null;
  return (
    <div style={{marginBottom:6}}>
      <span style={{fontSize:10,color:'var(--text-tertiary)',display:'block'}}>{label}</span>
      <span style={{fontSize:11.5,color:'var(--text-primary)'}}>{children}</span>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Materials
══════════════════════════════════════════════════════════════════════════════ */
function MaterialsSection({ review }) {
  if (!review) return <Loading/>;
  const rows = review.material_formula_table || [];
  const FORMULA_TABLE = [
    ['Graphene','C (2D hexagonal lattice)','High conductivity, large surface area','Drop casting / CVD'],
    ['rGO','C + O functional groups (reduced)','Good conductivity, biocompatible','Chemical reduction'],
    ['MWCNT','(C)n multi-walled nanotube','Fast electron transfer, large ECSA','Acid treatment + drop cast'],
    ['Ti₃C₂Tₓ (MXene)','Ti₃C₂Tₓ','Metallic conductivity, hydrophilic','Selective etching of Ti₃AlC₂'],
    ['MoS₂','MoS₂','Active edge sites, large bandgap','Hydrothermal'],
    ['ZnO','ZnO','Wide bandgap semiconductor, catalytic','Hydrothermal / sol-gel'],
    ['MnO₂','MnO₂','High theoretical capacitance','Electrodeposition'],
    ['Fe₃O₄','Fe₃O₄','Magnetic, electrocatalytic','Coprecipitation'],
    ['AuNPs','Au nanoparticles','SPR effect, biocompatibility','Citrate reduction'],
    ['PANI','(C₆H₅NH)n','Conducting polymer, pH-sensitive','Electropolymerization'],
    ['ZIF-8','Zn(mIM)₂ MOF','High porosity, tunable pore size','Room-temp synthesis'],
    ['g-C₃N₄','C₃N₄ 2D material','Photocatalytic, N-rich surface','Thermal condensation'],
  ];

  return (
    <div style={{display:'flex',flexDirection:'column',gap:12}}>
      <div style={card()}>
        <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--text-primary)'}}>Reference Material Table (from literature)</div>
        <table style={{width:'100%',borderCollapse:'collapse'}}>
          <thead><tr>{['Material','Formula','Role / Properties','Fabrication'].map(h=><th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {FORMULA_TABLE.map(([name,formula,role,fab])=>(
              <tr key={name}>
                <td style={td()}>{name}</td>
                <td style={td(true)}>{formula}</td>
                <td style={td()}>{role}</td>
                <td style={td()}>{fab}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length > 0 && (
        <div style={card()}>
          <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--text-primary)'}}>Materials Detected in Your Papers ({rows.length})</div>
          <table style={{width:'100%',borderCollapse:'collapse'}}>
            <thead><tr>{['Material','Formula','Papers'].map(h=><th key={h} style={th}>{h}</th>)}</tr></thead>
            <tbody>
              {rows.map((r,i)=>(
                <tr key={i}>
                  <td style={td()}>{r.material}</td>
                  <td style={td(true)}>{r.formula||'—'}</td>
                  <td style={td()}><span style={pill('blue')}>{r.count}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Techniques
══════════════════════════════════════════════════════════════════════════════ */
function TechniquesSection({ review }) {
  const TECHNIQUES = [
    { name:'Cyclic Voltammetry (CV)', abbr:'CV', use:'Redox behaviour, ECSA, kinetics', equation:'Ip = 2.69×10⁵ n³/² A D¹/² C v¹/²', params:'Peak current, ΔEp, scan rate dependence' },
    { name:'Differential Pulse Voltammetry (DPV)', abbr:'DPV', use:'Trace-level detection, improved S/N', equation:'ΔI = I(t₁)−I(t₂)', params:'Peak potential, pulse amplitude, LOD' },
    { name:'Electrochemical Impedance Spectroscopy (EIS)', abbr:'EIS', use:'Interface characterisation, Rct', equation:'Z = Zre + jZim', params:'Rct, Rs, CPE, Warburg, Nyquist' },
    { name:'Square Wave Voltammetry (SWV)', abbr:'SWV', use:'Faster scan, lower background', equation:'ΔΨ = Ψf−Ψb', params:'Frequency, amplitude, step height' },
    { name:'Chronoamperometry (CA)', abbr:'CA', use:'Amperometric sensing, kinetics', equation:'I(t) = nFAC√(D/πt)', params:'Response time, steady-state current' },
    { name:'Linear Sweep Voltammetry (LSV)', abbr:'LSV', use:'Onset potential, Tafel slopes', equation:'Ep = E⁰ + (RT/nF)ln(v)', params:'Peak position, cathodic/anodic' },
    { name:'Stripping Voltammetry', abbr:'DPASV/SWASV', use:'Heavy metal trace detection', equation:'Pre-concentration + strip step', params:'Deposition time/potential, LOD' },
  ];

  const counts = review?.technique_counts || {};
  const total  = Object.values(counts).reduce((a,b)=>a+b,0)||1;

  return (
    <div style={{display:'flex',flexDirection:'column',gap:12}}>
      {review && Object.keys(counts).length > 0 && (
        <div style={card()}>
          <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--text-primary)'}}>Technique Distribution in Your Papers</div>
          {Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([t,c])=>(
            <div key={t} style={{marginBottom:8}}>
              <div style={{display:'flex',justifyContent:'space-between',marginBottom:3}}>
                <span style={{fontSize:12,color:'var(--text-primary)'}}>{t}</span>
                <span style={{fontSize:11,color:'var(--text-tertiary)'}}>{c} papers ({Math.round(c/total*100)}%)</span>
              </div>
              <div style={{height:5,background:'var(--bg-tertiary)',borderRadius:3}}>
                <div style={{height:'100%',width:`${c/total*100}%`,background:'var(--accent)',borderRadius:3}}/>
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={card()}>
        <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--text-primary)'}}>Electrochemical Technique Reference</div>
        <table style={{width:'100%',borderCollapse:'collapse'}}>
          <thead><tr>{['Technique','Abbr.','Primary Use','Key Equation','Parameters'].map(h=><th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {TECHNIQUES.map(t=>(
              <tr key={t.abbr}>
                <td style={td()}>{t.name}</td>
                <td style={td()}><span style={pill('blue')}>{t.abbr}</span></td>
                <td style={td()}>{t.use}</td>
                <td style={td(true)}>{t.equation}</td>
                <td style={td()}>{t.params}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   LOD & Sensitivity
══════════════════════════════════════════════════════════════════════════════ */
function LodSection({ review }) {
  if (!review) return <Loading/>;
  const lodRows = review.lod_table || [];
  const sensRows = review.sensitivity_table || [];
  return (
    <div style={{display:'flex',flexDirection:'column',gap:12}}>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
        <div style={card()}>
          <div style={{fontSize:11,fontWeight:500,color:'var(--text-tertiary)',marginBottom:8,textTransform:'uppercase',letterSpacing:'.05em'}}>LOD Formula</div>
          <div style={{...mono,fontSize:14,color:'var(--accent)',textAlign:'center',padding:'12px 0'}}>LOD = 3σ / m</div>
          <div style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.6}}>
            σ = standard deviation of blank signal<br/>
            m = slope of calibration curve
          </div>
        </div>
        <div style={card()}>
          <div style={{fontSize:11,fontWeight:500,color:'var(--text-tertiary)',marginBottom:8,textTransform:'uppercase',letterSpacing:'.05em'}}>Sensitivity</div>
          <div style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.7}}>
            Common units: µA·µM⁻¹·cm⁻², mA·mM⁻¹·cm⁻²<br/>
            Factors: surface area, conductivity, catalytic activity, porosity<br/>
            Randles–Ševčík: Ip = 2.69×10⁵ n³/² A D¹/² C v¹/²
          </div>
        </div>
      </div>

      <div style={card()}>
        <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--text-primary)'}}>LOD Comparison Table ({lodRows.length} papers)</div>
        <table style={{width:'100%',borderCollapse:'collapse'}}>
          <thead><tr>{['Paper','Year','Analyte','LOD','Sensitivity','Linear Range','Materials'].map(h=><th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {lodRows.length ? lodRows.map((r,i)=>(
              <tr key={i}>
                <td style={{...td(),maxWidth:200,fontSize:11}}>{r.title}</td>
                <td style={td()}>{r.year||'—'}</td>
                <td style={td()}><span style={pill('blue')}>{r.analyte||'—'}</span></td>
                <td style={td(true)}><strong style={{color:'var(--color-success)'}}>{r.lod||'—'}</strong></td>
                <td style={td(true)}>{r.sensitivity||'—'}</td>
                <td style={td(true)}>{r.linear_range||'—'}</td>
                <td style={{...td(),fontSize:10.5}}>{(r.materials||[]).slice(0,2).join(', ')}</td>
              </tr>
            )) : <tr><td colSpan={7} style={{...td(),textAlign:'center',color:'var(--text-tertiary)',padding:24}}>Sync &amp; extract papers to populate</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Food Samples
══════════════════════════════════════════════════════════════════════════════ */
function FoodSection({ review }) {
  if (!review) return <Loading/>;
  const counts = review.food_sample_counts || {};
  const CATEGORIES = {
    'Beverages': ['apple juice','orange juice','grape juice','wine','beer','tea','coffee','milk'],
    'Water': ['tap water','river water','lake water','drinking water','seawater','groundwater'],
    'Biological': ['blood serum','urine','saliva','sweat','plasma','whole blood'],
    'Produce': ['spinach','lettuce','tomato','potato','onion','garlic','pepper','vegetable','fruit'],
    'Other Food': ['honey','fish','meat','eggs','cheese','yogurt','soy sauce','vinegar'],
  };
  return (
    <div style={{display:'flex',flexDirection:'column',gap:12}}>
      {Object.entries(CATEGORIES).map(([cat,items])=>{
        const found = items.filter(i=>Object.keys(counts).some(k=>k.includes(i)||i.includes(k)));
        if (!found.length && !Object.keys(counts).length) return null;
        return (
          <div key={cat} style={card()}>
            <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--text-primary)'}}>{cat}</div>
            <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
              {items.map(item=>{
                const c = Object.entries(counts).find(([k])=>k.includes(item)||item.includes(k));
                return (
                  <div key={item} style={{...pill(c?'green':'gray'),padding:'4px 12px',fontSize:11.5}}>
                    {item.charAt(0).toUpperCase()+item.slice(1)}
                    {c && <span style={{marginLeft:6,opacity:.7}}>×{c[1]}</span>}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
      {Object.keys(counts).length === 0 && (
        <div style={{...card(),textAlign:'center',padding:32,color:'var(--text-tertiary)'}}>
          Sync Drive papers to see food sample analysis
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Interference
══════════════════════════════════════════════════════════════════════════════ */
function InterferenceSection({ review }) {
  if (!review) return <Loading/>;
  const mentions = review.interference_mentions || {};
  const entries  = Object.entries(mentions).sort((a,b)=>b[1]-a[1]);
  const COMMON = ['ascorbic acid','dopamine','uric acid','glucose','glutathione','citric acid',
    'Na⁺','K⁺','Cl⁻','Ca²⁺','Mg²⁺','Fe³⁺','Cu²⁺','Zn²⁺','Pb²⁺','Cd²⁺','Hg²⁺'];
  return (
    <div style={{display:'flex',flexDirection:'column',gap:12}}>
      <div style={card()}>
        <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--text-primary)'}}>Common Interferents in EC Sensor Research</div>
        <div style={{display:'flex',flexWrap:'wrap',gap:6,marginBottom:16}}>
          {COMMON.map(k=>(
            <span key={k} style={{...pill(mentions[k]?'amber':'gray'),padding:'3px 10px',fontSize:11}}>
              {k}{mentions[k]?` ×${mentions[k]}`:''}
            </span>
          ))}
        </div>
        <div style={{fontSize:11.5,color:'var(--text-secondary)',lineHeight:1.7}}>
          <strong>Anti-interference coefficient (AIC)</strong> = (ΔI_analyte / ΔI_interferent) × 100%<br/>
          Good selectivity: AIC &lt; 5% signal change at 10× concentration of interfering species.
        </div>
      </div>

      {entries.length > 0 && (
        <div style={card()}>
          <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--text-primary)'}}>Interferents Detected in Your Papers</div>
          <table style={{width:'100%',borderCollapse:'collapse'}}>
            <thead><tr><th style={th}>Interferent</th><th style={th}>Mentioned in (papers)</th></tr></thead>
            <tbody>
              {entries.map(([k,v])=>(
                <tr key={k}><td style={td()}>{k}</td><td style={td()}><span style={pill('blue')}>{v}</span></td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Commercial
══════════════════════════════════════════════════════════════════════════════ */
function CommercialSection({ review }) {
  if (!review) return <Loading/>;
  const score = Math.round((review.commercial_score_avg||0)*100);
  const CRITERIA = [
    ['Low-cost fabrication','Screen printing, inkjet, roll-to-roll'],
    ['Miniaturization','Wearable, handheld, portable formats'],
    ['Rapid detection','< 5 min assay time'],
    ['Disposable electrodes','Eliminates cross-contamination'],
    ['Smartphone integration','Wireless readout, app-based'],
    ['Mass manufacturing','Reproducible batch fabrication'],
    ['Regulatory pathway','CE/FDA-ready design'],
    ['IoT connectivity','RFID, NFC, Bluetooth sensors'],
  ];
  return (
    <div style={{display:'flex',flexDirection:'column',gap:12}}>
      <div style={{display:'grid',gridTemplateColumns:'1fr 2fr',gap:12}}>
        <div style={card()}>
          <div style={{fontSize:12,fontWeight:600,marginBottom:12,color:'var(--text-primary)'}}>Commercial Readiness Score</div>
          <div style={{fontSize:48,fontWeight:800,color:score>50?'var(--color-success)':score>25?'#fbbf24':'var(--color-error)',textAlign:'center',lineHeight:1}}>{score}%</div>
          <div style={{height:8,background:'var(--bg-tertiary)',borderRadius:4,margin:'12px 0',overflow:'hidden'}}>
            <div style={{height:'100%',width:`${score}%`,background:score>50?'var(--color-success)':'#fbbf24',borderRadius:4}}/>
          </div>
          <div style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.6,textAlign:'center'}}>
            of papers mention POC/commercial keywords
          </div>
        </div>
        <div style={card()}>
          <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--text-primary)'}}>Commercialization Criteria</div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
            {CRITERIA.map(([k,v])=>(
              <div key={k} style={{background:'var(--bg-tertiary)',borderRadius:'var(--radius-sm)',padding:'8px 10px'}}>
                <div style={{fontSize:11.5,fontWeight:600,color:'var(--text-primary)',marginBottom:2}}>{k}</div>
                <div style={{fontSize:10.5,color:'var(--text-tertiary)'}}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Challenges & Scope
══════════════════════════════════════════════════════════════════════════════ */
function ChallengesSection({ review }) {
  if (!review) return <Loading/>;
  const challenges = Object.entries(review.challenge_counts||{}).sort((a,b)=>b[1]-a[1]);
  const SCOPE = [
    { title:'Advanced Materials', items:['MXene/2D heterostructures','Single-atom catalysts','Quantum dots','High-entropy oxides','Covalent organic frameworks (COFs)'] },
    { title:'Emerging Technologies', items:['AI-assisted real-time sensing','Self-powered triboelectric sensors','Wearable sweat/tear sensors','Flexible/stretchable electronics','Microfluidic electrochemical chips'] },
    { title:'Research Opportunities', items:['Multi-analyte multiplexed arrays','Non-invasive continuous monitoring','Green synthesis (aqueous, room-temp)','Real-time wireless IoT monitoring','Smartphone colorimetric readout'] },
    { title:'Clinical Translation', items:['GMP-compliant fabrication','Clinical validation (n≥100 patients)','Regulatory submission (CE/FDA)','Point-of-care for low-resource settings','Telemedicine-integrated sensing'] },
  ];
  return (
    <div style={{display:'flex',flexDirection:'column',gap:12}}>
      {challenges.length > 0 && (
        <div style={card()}>
          <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--text-primary)'}}>Challenges Identified in Literature</div>
          <div style={{display:'flex',flexWrap:'wrap',gap:8}}>
            {challenges.map(([ch,c])=>(
              <div key={ch} style={{background:'var(--bg-tertiary)',border:'1px solid var(--border-primary)',borderRadius:'var(--radius-sm)',padding:'6px 12px',display:'flex',alignItems:'center',gap:8}}>
                <span style={{fontSize:12,color:'var(--text-primary)',textTransform:'capitalize'}}>{ch.replace(/-/g,' ')}</span>
                <span style={pill('amber')}>{c}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
        {SCOPE.map(({title,items})=>(
          <div key={title} style={card()}>
            <div style={{fontSize:12,fontWeight:600,marginBottom:10,color:'var(--accent)'}}>{title}</div>
            {items.map(item=>(
              <div key={item} style={{display:'flex',gap:8,marginBottom:6,alignItems:'flex-start'}}>
                <span style={{color:'var(--accent)',fontWeight:700,flexShrink:0}}>→</span>
                <span style={{fontSize:11.5,color:'var(--text-secondary)',lineHeight:1.5}}>{item}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Shared helpers
══════════════════════════════════════════════════════════════════════════════ */
function BarRow({ label, value, max, color='var(--accent)' }) {
  return (
    <div style={{marginBottom:7}}>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:2}}>
        <span style={{fontSize:11.5,color:'var(--text-primary)',textTransform:'capitalize'}}>{label}</span>
        <span style={{fontSize:11,color:'var(--text-tertiary)'}}>{value}</span>
      </div>
      <div style={{height:4,background:'var(--bg-tertiary)',borderRadius:2}}>
        <div style={{height:'100%',width:`${value/max*100}%`,background:color,borderRadius:2}}/>
      </div>
    </div>
  );
}

function Loading() {
  return <div style={{padding:32,textAlign:'center',color:'var(--text-tertiary)',fontSize:12}}>Loading…</div>;
}
