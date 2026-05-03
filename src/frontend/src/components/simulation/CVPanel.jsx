import React, { useState, useRef, useEffect, useCallback } from 'react';
import ScanRateStudy from './ScanRateStudy';
import { Activity, Shield, Cpu, Terminal, Layers, Info, ChevronRight, Zap } from 'lucide-react';

const THEME = {
  primary: 'var(--accent)',
  secondary: '#7000ff',
  accent: '#0062ff',
  background: '#020204',
  surface: 'rgba(5, 5, 5, 0.8)',
  border: 'rgba(74, 142, 255, 0.2)',
  text: '#e0e0e0',
  textSecondary: '#a0a0a0',
  grid: 'rgba(255, 255, 255, 0.05)',
  fontMono: '"JetBrains Mono", "Fira Code", monospace'
};

const CornerBracket = ({ position = 'top-left' }) => {
  const styles = {
    'top-left': { top: -1, left: -1, borderTop: `2px solid ${THEME.primary}`, borderLeft: `2px solid ${THEME.primary}` },
    'top-right': { top: -1, right: -1, borderTop: `2px solid ${THEME.primary}`, borderRight: `2px solid ${THEME.primary}` },
    'bottom-left': { bottom: -1, left: -1, borderBottom: `2px solid ${THEME.primary}`, borderLeft: `2px solid ${THEME.primary}` },
    'bottom-right': { bottom: -1, right: -1, borderBottom: `2px solid ${THEME.primary}`, borderRight: `2px solid ${THEME.primary}` }
  };
  return <div style={{ position: 'absolute', width: 8, height: 8, ...styles[position], pointerEvents: 'none', zIndex: 2 }} />;
};

const DEFAULT = {
  E_start: -0.3, E_vertex: 0.8, E_formal: 0.23, scan_rate: 0.05,
  C_ox: 5e-3, D_ox: 7.6e-6, k0: 0.01, alpha: 0.5, n_electrons: 1,
  area: 0.0707, n_points: 500,
};

function CVPlot({ data }) {
  const canvasRef = useRef(null);
  useEffect(() => {
    if (!data || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr; canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width, h = rect.height;
    const pad = { top: 30, right: 30, bottom: 50, left: 70 };
    const pw = w - pad.left - pad.right, ph = h - pad.top - pad.bottom;
    const E = data.E, I = data.i_total;
    const xMin = Math.min(...E), xMax = Math.max(...E);
    const yMin = Math.min(...I), yMax = Math.max(...I);
    const xR = (xMax - xMin) || 1, yR = (yMax - yMin) || 1;
    const sx = v => pad.left + ((v - xMin) / xR) * pw;
    const sy = v => pad.top + ph - ((v - yMin) / yR) * ph;

    ctx.clearRect(0, 0, w, h);
    
    // Background Grid
    ctx.strokeStyle = 'rgba(74, 142, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
      const x = pad.left + (pw / 10) * i;
      ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, pad.top + ph); ctx.stroke();
      const y = pad.top + (ph / 10) * i;
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + pw, y); ctx.stroke();
    }

    // Axes
    ctx.strokeStyle = THEME.border;
    ctx.lineWidth = 1;
    ctx.strokeRect(pad.left, pad.top, pw, ph);

    // Zero Line
    if (yMin < 0 && yMax > 0) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
      ctx.setLineDash([5, 5]);
      ctx.beginPath(); ctx.moveTo(pad.left, sy(0)); ctx.lineTo(pad.left + pw, sy(0)); ctx.stroke();
      ctx.setLineDash([]);
    }

    // Data Line
    ctx.strokeStyle = THEME.primary;
    ctx.lineWidth = 2;
    ctx.shadowBlur = 8;
    ctx.shadowColor = THEME.primary;
    ctx.beginPath();
    for (let i = 0; i < E.length; i++) {
      if (i === 0) ctx.moveTo(sx(E[i]), sy(I[i])); else ctx.lineTo(sx(E[i]), sy(I[i]));
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Peak Markers
    if (data.i_pa != null) {
      const peaks = [
        { e: data.E_pa, i: data.i_pa, color: '#ff3d00', label: 'ipa' },
        { e: data.E_pc, i: data.i_pc, color: '#00e5ff', label: 'ipc' }
      ];
      peaks.forEach(p => {
        ctx.fillStyle = p.color;
        ctx.beginPath(); ctx.arc(sx(p.e), sy(p.i), 5, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.stroke();
        
        ctx.fillStyle = '#fff';
        ctx.font = `bold 10px ${THEME.fontMono}`;
        ctx.textAlign = 'left';
        ctx.fillText(`${p.label}: ${p.i.toExponential(2)}A`, sx(p.e) + 10, sy(p.i) + (p.label === 'ipa' ? -10 : 15));
      });
    }

    // Labels & Ticks
    ctx.fillStyle = THEME.textSecondary;
    ctx.font = `10px ${THEME.fontMono}`;
    ctx.textAlign = 'center';
    ctx.fillText('Potential / V vs Ref', pad.left + pw / 2, h - 10);
    
    ctx.save();
    ctx.translate(20, pad.top + ph / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Current / A', 0, 0);
    ctx.restore();

    ctx.fillStyle = THEME.textSecondary;
    for (let i = 0; i <= 5; i++) {
      const valX = xMin + (xR / 5) * i;
      ctx.fillText(valX.toFixed(2), sx(valX), pad.top + ph + 20);
      const valY = yMin + (yR / 5) * i;
      ctx.textAlign = 'right';
      ctx.fillText(valY.toExponential(1), pad.left - 10, sy(valY) + 4);
      ctx.textAlign = 'center';
    }

    // Watermark
    ctx.globalAlpha = 0.3;
    ctx.font = `bold 12px ${THEME.fontMono}`;
    ctx.textAlign = 'right';
    ctx.fillText('RĀMAN INSTRUMENTATION', w - pad.right - 10, pad.top + 20);
    ctx.globalAlpha = 1.0;

  }, [data]);
  return <canvas ref={canvasRef} style={{ width: '100%', height: '100%', background: THEME.background }} />;
}

function simulateCV(p) {
  const n = p.n_points, E = [], I = [];
  for (let i = 0; i < n; i++) E.push(p.E_start + (p.E_vertex - p.E_start) * i / n);
  for (let i = 0; i < n; i++) E.push(p.E_vertex + (p.E_start - p.E_vertex) * i / n);
  const F = 96485.3, R = 8.314, T = 298.15, A = p.area || 0.0707;
  let ipa = -Infinity, ipc = Infinity, Epa = 0, Epc = 0;
  E.forEach(e => {
    const eta = e - (p.E_formal || 0.23);
    const kf = p.k0 * Math.exp(-p.alpha * p.n_electrons * F * eta / (R * T));
    const kb = p.k0 * Math.exp((1 - p.alpha) * p.n_electrons * F * eta / (R * T));
    const j = p.n_electrons * F * A * (kf * p.C_ox * 1e-3 - kb * p.C_ox * 1e-3);
    const clamped = Math.max(-0.01, Math.min(0.01, j));
    I.push(clamped);
    if (clamped > ipa) { ipa = clamped; Epa = e; }
    if (clamped < ipc) { ipc = clamped; Epc = e; }
  });
  return { E, i_total: I, i_pa: ipa, i_pc: ipc, E_pa: Epa, E_pc: Epc, dEp: Math.abs(Epa - Epc), engine: 'V_EMULATOR_LITE' };
}

export default function CVPanel() {
  const [params, setParams] = useState(DEFAULT);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [mode, setMode] = useState('single');

  const exportCSV = useCallback(() => {
    if (!result) return;
    let csv = 'E_V,i_A\n';
    for (let i = 0; i < result.E.length; i++) csv += `${result.E[i]},${result.i_total[i]}\n`;
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `cv_export_${new Date().getTime()}.csv`; a.click();
  }, [result]);

  const run = useCallback(async () => {
    setRunning(true);
    try {
      // Absolute URL: in a packaged Electron build the renderer is loaded
      // from file:// where a relative `/api/v2/cv` resolves to file:///api/v2/cv
      // and silently fails — fall through to the local JS approximation.
      const res = await fetch('http://127.0.0.1:8000/api/v2/cv', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      if (res.ok) {
        const data = await res.json();
        setResult({ ...data, engine: 'SENTINEL_CORE' });
      } else throw new Error();
    } catch { 
      setTimeout(() => {
        setResult(simulateCV(params)); 
        setRunning(false);
      }, 600);
    }
  }, [params]);

  const fields = [
    { key: 'E_start', label: 'E START', unit: 'V', step: 0.05 },
    { key: 'E_vertex', label: 'E VERTEX', unit: 'V', step: 0.05 },
    { key: 'E_formal', label: 'E⁰ FORMAL', unit: 'V', step: 0.01 },
    { key: 'scan_rate', label: 'SCAN RATE', unit: 'V/s', step: 0.01 },
    { key: 'k0', label: 'HET. RATE (k⁰)', unit: 'cm/s', step: 0.001 },
    { key: 'alpha', label: 'TRANSFER (α)', unit: '—', step: 0.05 },
    { key: 'C_ox', label: 'CONC. (Ox)', unit: 'M', step: 1e-3 },
    { key: 'D_ox', label: 'DIFFUSION', unit: 'cm²/s', step: 1e-7 },
    { key: 'area', label: 'AREA', unit: 'cm²', step: 0.01 },
  ];

  return (
    <div style={{ padding: '20px', background: THEME.background, color: THEME.text, minHeight: '100%', fontFamily: 'var(--font-data)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, borderBottom: `1px solid ${THEME.border}`, paddingBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Activity size={20} color={THEME.primary} />
          <h2 style={{ margin: 0, fontSize: 18, letterSpacing: '2px', fontWeight: 800 }}>CYCLIC VOLTAMMETRY</h2>
        </div>
        <div style={{ display: 'flex', gap: 15, fontSize: 10, color: THEME.textSecondary }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}><Cpu size={12} /> {result?.engine || 'STANDBY'}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}><Shield size={12} /> ENCRYPTED</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}><Terminal size={12} /> v2.4.0-STABLE</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 20 }}>
        {/* Left Column: Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
          <div style={{ position: 'relative', background: THEME.surface, border: `1px solid ${THEME.border}`, padding: 20 }}>
            <CornerBracket position="top-left" />
            <CornerBracket position="top-right" />
            <CornerBracket position="bottom-left" />
            <CornerBracket position="bottom-right" />
            
            <div style={{ display: 'flex', gap: 5, marginBottom: 20, background: 'rgba(0,0,0,0.3)', padding: 4, borderRadius: 4 }}>
              <button 
                onClick={() => setMode('single')}
                style={{ 
                  flex: 1, padding: '8px', background: mode === 'single' ? THEME.primary : 'transparent',
                  color: mode === 'single' ? '#000' : THEME.text, border: 'none', fontSize: 10, fontWeight: 700, cursor: 'pointer'
                }}>SINGLE CV</button>
              <button 
                onClick={() => setMode('scanrate')}
                style={{ 
                  flex: 1, padding: '8px', background: mode === 'scanrate' ? THEME.primary : 'transparent',
                  color: mode === 'scanrate' ? '#000' : THEME.text, border: 'none', fontSize: 10, fontWeight: 700, cursor: 'pointer'
                }}>SCAN RATE STUDY</button>
            </div>

            <div style={{ display: 'grid', gap: 12 }}>
              {fields.map(f => (
                <div key={f.key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: THEME.textSecondary }}>
                    <span>{f.label}</span>
                    <span>{f.unit}</span>
                  </div>
                  <input 
                    type="number" 
                    value={params[f.key]} 
                    step={f.step}
                    onChange={e => setParams(p => ({ ...p, [f.key]: parseFloat(e.target.value) || 0 }))}
                    style={{ 
                      background: 'rgba(255,255,255,0.05)', border: `1px solid ${THEME.border}`, 
                      color: THEME.primary, padding: '8px', fontSize: 12, outline: 'none', fontFamily: 'var(--font-data)'
                    }}
                  />
                </div>
              ))}
            </div>

            <button 
              onClick={run} 
              disabled={running || mode === 'scanrate'}
              style={{ 
                width: '100%', marginTop: 20, padding: '12px', background: THEME.primary, color: '#000',
                border: 'none', fontWeight: 800, fontSize: 12, cursor: 'pointer', opacity: (running || mode === 'scanrate') ? 0.5 : 1
              }}>
              {running ? 'COMPUTING SIGNAL...' : mode === 'scanrate' ? 'USE RIGHT PANEL' : 'EXECUTE SIMULATION'}
            </button>
          </div>

          {result && mode === 'single' && (
            <div style={{ position: 'relative', background: THEME.surface, border: `1px solid ${THEME.border}`, padding: 15 }}>
              <div style={{ fontSize: 11, fontWeight: 800, color: THEME.primary, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Info size={14} /> PEAK DIAGNOSTICS
              </div>
              <div style={{ display: 'grid', gap: 8 }}>
                {[
                  { label: 'IPA', val: result.i_pa?.toExponential(3) + ' A' },
                  { label: 'IPC', val: result.i_pc?.toExponential(3) + ' A' },
                  { label: 'EPA', val: result.E_pa?.toFixed(3) + ' V' },
                  { label: 'EPC', val: result.E_pc?.toFixed(3) + ' V' },
                  { label: 'ΔEP', val: (result.dEp * 1000)?.toFixed(1) + ' mV' },
                ].map(item => (
                  <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: 4 }}>
                    <span style={{ color: THEME.textSecondary }}>{item.label}</span>
                    <span style={{ color: THEME.primary }}>{item.val}</span>
                  </div>
                ))}
              </div>
              <div style={{ 
                marginTop: 10, padding: 8, background: 'rgba(74, 142, 255, 0.1)', border: `1px solid ${THEME.primary}`,
                fontSize: 10, textAlign: 'center', fontWeight: 700, color: THEME.primary
              }}>
                {result.dEp < 0.07 ? 'SYSTEM: FULLY REVERSIBLE' : result.dEp < 0.2 ? 'SYSTEM: QUASI-REVERSIBLE' : 'SYSTEM: IRREVERSIBLE'}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Visualization */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {mode === 'single' ? (
            <>
              <div style={{ position: 'relative', height: '500px', background: THEME.surface, border: `1px solid ${THEME.border}`, padding: 20 }}>
                <CornerBracket position="top-left" />
                <CornerBracket position="top-right" />
                <CornerBracket position="bottom-left" />
                <CornerBracket position="bottom-right" />
                
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 15 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Layers size={16} color={THEME.primary} />
                    <span style={{ fontSize: 12, fontWeight: 800 }}>VOLTAMMETRIC RESPONSE</span>
                  </div>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <button onClick={exportCSV} style={{ background: 'transparent', border: `1px solid ${THEME.border}`, color: THEME.text, fontSize: 10, padding: '4px 10px', cursor: 'pointer' }}>EXPORT DATA</button>
                    <div style={{ background: 'rgba(255,255,255,0.05)', padding: '4px 10px', fontSize: 10 }}>RT_TELEMETRY: ACTIVE</div>
                  </div>
                </div>

                <div style={{ height: 'calc(100% - 40px)' }}>
                  {result ? <CVPlot data={result} /> : (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: THEME.textSecondary }}>
                      <Zap size={40} style={{ marginBottom: 10, opacity: 0.3 }} />
                      <span style={{ fontSize: 11 }}>AWAITING SIGNAL EXECUTION...</span>
                    </div>
                  )}
                </div>
              </div>

              {result && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 15 }}>
                  {[
                    { label: 'ANODIC PEAK (ipa)', val: result.i_pa?.toExponential(2), unit: 'A', icon: <ChevronRight size={14} />, color: '#ff3d00' },
                    { label: 'CATHODIC PEAK (ipc)', val: result.i_pc?.toExponential(2), unit: 'A', icon: <ChevronRight size={14} />, color: '#00e5ff' },
                    { label: 'PEAK SEPARATION (ΔEp)', val: ((result.dEp || 0) * 1000).toFixed(1), unit: 'mV', icon: <ChevronRight size={14} />, color: THEME.primary }
                  ].map((stat, i) => (
                    <div key={i} style={{ position: 'relative', background: THEME.surface, border: `1px solid ${THEME.border}`, padding: 15, display: 'flex', flexDirection: 'column', gap: 5 }}>
                      <div style={{ fontSize: 9, color: THEME.textSecondary, display: 'flex', alignItems: 'center', gap: 5 }}>{stat.icon} {stat.label}</div>
                      <div style={{ fontSize: 20, fontWeight: 900, color: stat.color }}>{stat.val} <span style={{ fontSize: 12, fontWeight: 400 }}>{stat.unit}</span></div>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <ScanRateStudy baseParams={params} />
          )}
        </div>
      </div>
    </div>
  );
}
