import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Play, Download, Plus, X, BarChart2, Table as TableIcon, Activity } from 'lucide-react';

const THEME = {
  primary: '#00f2ff',
  secondary: '#7000ff',
  accent: '#0062ff',
  background: '#020204',
  surface: 'rgba(5, 5, 5, 0.8)',
  border: 'rgba(0, 242, 255, 0.2)',
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

const F = 96485.33, R = 8.314, T = 298.15;

function simulateCVAtRate(p, rate) {
  const n = 400, E = [], I = [];
  const A = p.area || 0.0707;
  for (let i = 0; i < n; i++) E.push(p.E_start + (p.E_vertex - p.E_start) * i / n);
  for (let i = 0; i < n; i++) E.push(p.E_vertex + (p.E_start - p.E_vertex) * i / n);
  let ipa = -Infinity, ipc = Infinity, Epa = 0, Epc = 0;
  E.forEach(e => {
    const eta = e - (p.E_formal || 0.23);
    const kf = p.k0 * Math.exp(-p.alpha * p.n_electrons * F * eta / (R * T));
    const kb = p.k0 * Math.exp((1 - p.alpha) * p.n_electrons * F * eta / (R * T));
    const D = p.D_ox || 7.6e-6;
    const C = p.C_ox * 1e-3;
    const scale = Math.sqrt(D * F * rate / (R * T));
    const j = p.n_electrons * F * A * (kf * C - kb * C) * scale * 10;
    const clamped = Math.max(-0.05, Math.min(0.05, j));
    I.push(clamped);
    if (clamped > ipa) { ipa = clamped; Epa = e; }
    if (clamped < ipc) { ipc = clamped; Epc = e; }
  });
  const ip_rs = 0.4463 * Math.pow(p.n_electrons, 1.5) * F * A *
    (p.C_ox * 1e-3) * Math.sqrt((p.D_ox || 7.6e-6) * rate * F / (R * T));
  return { E, I, ipa: Math.abs(ipa), ipc: Math.abs(ipc), Epa, Epc, dEp: Math.abs(Epa - Epc), ip_rs, rate };
}

function OverlayPlot({ studies }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!studies.length || !ref.current) return;
    const c = ref.current, ctx = c.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = c.getBoundingClientRect();
    c.width = rect.width * dpr; c.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width, h = rect.height;
    const pad = { t: 30, r: 120, b: 50, l: 70 };
    const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;

    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
    studies.forEach(s => {
      s.E.forEach(v => { if (v < xMin) xMin = v; if (v > xMax) xMax = v; });
      s.I.forEach(v => { if (v < yMin) yMin = v; if (v > yMax) yMax = v; });
    });
    const xR = (xMax - xMin) || 1, yR = (yMax - yMin) || 1;
    const sx = v => pad.l + ((v - xMin) / xR) * pw;
    const sy = v => pad.t + ph - ((v - yMin) / yR) * ph;

    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = THEME.grid; ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
      const x = pad.l + (pw / 10) * i, y = pad.t + (ph / 10) * i;
      ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ph); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + pw, y); ctx.stroke();
    }
    ctx.strokeStyle = THEME.border; ctx.lineWidth = 1; ctx.strokeRect(pad.l, pad.t, pw, ph);

    const colors = ['#00f2ff', '#0062ff', '#7000ff', '#ff00ff', '#ff0055', '#ffaa00', '#aaff00', '#00ffaa'];
    studies.forEach((s, idx) => {
      ctx.strokeStyle = colors[idx % colors.length]; ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i < s.E.length; i++) {
        if (i === 0) ctx.moveTo(sx(s.E[i]), sy(s.I[i]));
        else ctx.lineTo(sx(s.E[i]), sy(s.I[i]));
      }
      ctx.stroke();
    });

    ctx.fillStyle = THEME.textSecondary; ctx.font = `10px ${THEME.fontMono}`; ctx.textAlign = 'center';
    ctx.fillText('Potential / V vs Ref', pad.l + pw / 2, h - 10);
    ctx.save(); ctx.translate(20, pad.t + ph / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText('Current / A', 0, 0); ctx.restore();

    ctx.fillStyle = THEME.textSecondary;
    for (let i = 0; i <= 5; i++) {
      const vx = xMin + (xR / 5) * i; ctx.fillText(vx.toFixed(2), sx(vx), pad.t + ph + 20);
      const vy = yMin + (yR / 5) * i; ctx.textAlign = 'right'; ctx.fillText(vy.toExponential(1), pad.l - 10, sy(vy) + 4); ctx.textAlign = 'center';
    }

    // Legend
    ctx.textAlign = 'left'; ctx.font = `9px ${THEME.fontMono}`;
    studies.forEach((s, i) => {
      const ly = pad.t + 10 + i * 16;
      ctx.fillStyle = colors[i % colors.length];
      ctx.fillRect(w - pad.r + 10, ly, 15, 3);
      ctx.fillStyle = THEME.text;
      ctx.fillText(`${(s.rate * 1000).toFixed(0)} mV/s`, w - pad.r + 30, ly + 4);
    });
  }, [studies]);
  return <canvas ref={ref} style={{ width: '100%', height: '100%' }} />;
}

function IpVsSqrtVPlot({ studies }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!studies.length || !ref.current) return;
    const c = ref.current, ctx = c.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = c.getBoundingClientRect();
    c.width = rect.width * dpr; c.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width, h = rect.height;
    const pad = { t: 30, r: 150, b: 50, l: 70 };
    const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;

    const xs = studies.map(s => Math.sqrt(s.rate));
    const ys_a = studies.map(s => s.ipa * 1e6);
    const ys_c = studies.map(s => s.ipc * 1e6);
    const ys_rs = studies.map(s => s.ip_rs * 1e6);

    const xMin = 0, xMax = Math.max(...xs) * 1.1;
    const yMax = Math.max(...ys_a, ...ys_c, ...ys_rs) * 1.15;
    const sx = v => pad.l + (v / xMax) * pw;
    const sy = v => pad.t + ph - (v / yMax) * ph;

    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = THEME.grid; ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
      const x = pad.l + pw / 10 * i, y = pad.t + ph / 10 * i;
      ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ph); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + pw, y); ctx.stroke();
    }
    ctx.strokeStyle = THEME.border; ctx.lineWidth = 1; ctx.strokeRect(pad.l, pad.t, pw, ph);

    // Linear fit line
    ctx.strokeStyle = 'rgba(0, 242, 255, 0.3)'; ctx.lineWidth = 1; ctx.setLineDash([5, 5]);
    ctx.beginPath(); ctx.moveTo(sx(0), sy(0)); ctx.lineTo(sx(xs[xs.length-1]), sy(ys_rs[ys_rs.length-1])); ctx.stroke(); ctx.setLineDash([]);

    // Points
    const drawPoint = (x, y, color, size = 4) => {
      ctx.fillStyle = color; ctx.beginPath(); ctx.arc(sx(x), sy(y), size, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 0.5; ctx.stroke();
    };
    xs.forEach((x, i) => {
      drawPoint(x, ys_a[i], '#ff3d00');
      drawPoint(x, ys_c[i], '#00e5ff');
      drawPoint(x, ys_rs[i], '#7000ff', 3);
    });

    const mean_y = ys_a.reduce((a, b) => a + b, 0) / ys_a.length;
    const ss_tot = ys_a.reduce((a, v) => a + (v - mean_y) ** 2, 0);
    const ss_res = ys_a.reduce((a, v, i) => a + (v - ys_rs[i]) ** 2, 0);
    const r2 = ss_tot > 0 ? 1 - ss_res / ss_tot : 0;

    ctx.fillStyle = THEME.textSecondary; ctx.font = `10px ${THEME.fontMono}`; ctx.textAlign = 'center';
    ctx.fillText('√ν / (V/s)^0.5', pad.l + pw / 2, h - 10);
    ctx.save(); ctx.translate(20, pad.t + ph / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText('|ip| / µA', 0, 0); ctx.restore();

    ctx.fillStyle = THEME.textSecondary;
    for (let i = 0; i <= 5; i++) {
      const vx = (xMax / 5) * i; ctx.fillText(vx.toFixed(2), sx(vx), pad.t + ph + 20);
      const vy = (yMax / 5) * i; ctx.textAlign = 'right'; ctx.fillText(vy.toFixed(1), pad.l - 10, sy(vy) + 4); ctx.textAlign = 'center';
    }

    // Legend
    ctx.textAlign = 'left'; ctx.font = `9px ${THEME.fontMono}`;
    [['#ff3d00', 'ipa (Anodic)'], ['#00e5ff', '|ipc| (Cathodic)'], ['#7000ff', 'Randles-Ševčík (Theoretical)']].forEach(([c, l], i) => {
      ctx.fillStyle = c; ctx.fillRect(w - pad.r + 10, pad.t + 10 + i * 18, 12, 4);
      ctx.fillStyle = THEME.text; ctx.fillText(l, w - pad.r + 28, pad.t + 14 + i * 18);
    });
    ctx.fillStyle = THEME.primary; ctx.font = `bold 11px ${THEME.fontMono}`;
    ctx.fillText(`LINEARITY R² = ${r2.toFixed(4)}`, w - pad.r + 10, pad.t + 80);
  }, [studies]);
  return <canvas ref={ref} style={{ width: '100%', height: '100%' }} />;
}

export default function ScanRateStudy({ baseParams }) {
  const [rates, setRates] = useState([0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]);
  const [studies, setStudies] = useState([]);
  const [activeView, setActiveView] = useState('overlay');
  const [customRate, setCustomRate] = useState('');

  const p = baseParams || { E_start: -0.3, E_vertex: 0.8, k0: 0.01, alpha: 0.5, n_electrons: 1, C_ox: 5e-3, D_ox: 7.6e-6, area: 0.0707, E_formal: 0.23 };

  const runStudy = useCallback(() => {
    const results = rates.map(r => simulateCVAtRate(p, r));
    setStudies(results);
  }, [rates, p]);

  useEffect(() => { if (rates.length > 0) runStudy(); }, []);

  const addRate = () => {
    const v = parseFloat(customRate);
    if (v > 0 && !rates.includes(v)) {
      setRates([...rates, v].sort((a, b) => a - b));
      setCustomRate('');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 15, height: '100%' }}>
      {/* Controls HUD */}
      <div style={{ position: 'relative', background: THEME.surface, border: `1px solid ${THEME.border}`, padding: 15 }}>
        <CornerBracket position="top-left" />
        <CornerBracket position="top-right" />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 15 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Activity size={16} color={THEME.primary} />
            <span style={{ fontSize: 12, fontWeight: 900, letterSpacing: '1px' }}>SCAN RATE ANALYZER</span>
          </div>
          
          <div style={{ display: 'flex', gap: 10 }}>
            <div style={{ display: 'flex', gap: 4, background: 'rgba(0,0,0,0.3)', padding: 4, borderRadius: 4 }}>
              {[
                { k: 'overlay', icon: <Activity size={12} />, label: 'OVERLAY' },
                { k: 'ipv', icon: <BarChart2 size={12} />, label: 'KINETICS' },
                { k: 'table', icon: <TableIcon size={12} />, label: 'DATAGRID' }
              ].map(v => (
                <button key={v.k} onClick={() => setActiveView(v.k)} style={{
                  display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', border: 'none',
                  background: activeView === v.k ? THEME.primary : 'transparent',
                  color: activeView === v.k ? '#000' : THEME.text, fontSize: 9, fontWeight: 800, cursor: 'pointer'
                }}>{v.icon} {v.label}</button>
              ))}
            </div>
            <button onClick={() => {
              const csv = 'rate,ipa,ipc,epa,epc\n' + studies.map(s => `${s.rate},${s.ipa},${s.ipc},${s.Epa},${s.Epc}`).join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
              a.download = 'scan_rate_study.csv'; a.click();
            }} style={{ background: 'transparent', border: `1px solid ${THEME.border}`, color: THEME.text, fontSize: 9, padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
              <Download size={12} /> EXPORT CSV
            </button>
          </div>
        </div>

        <div style={{ marginTop: 15, display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', flex: 1 }}>
            {rates.map(r => (
              <div key={r} style={{ background: 'rgba(0,242,255,0.1)', border: `1px solid ${THEME.border}`, padding: '4px 8px', fontSize: 9, display: 'flex', alignItems: 'center', gap: 5 }}>
                {r >= 1 ? `${r} V/s` : `${(r * 1000).toFixed(0)} mV/s`}
                <X size={10} style={{ cursor: 'pointer' }} onClick={() => setRates(rates.filter(x => x !== r))} />
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 5 }}>
            <input type="number" value={customRate} onChange={e => setCustomRate(e.target.value)} placeholder="ADD V/s" style={{ width: 80, background: 'rgba(255,255,255,0.05)', border: `1px solid ${THEME.border}`, color: THEME.primary, padding: '6px', fontSize: 10, fontFamily: THEME.fontMono }} />
            <button onClick={addRate} style={{ background: THEME.surface, border: `1px solid ${THEME.border}`, color: THEME.primary, padding: '6px', cursor: 'pointer' }}><Plus size={14} /></button>
            <button onClick={runStudy} style={{ background: THEME.primary, color: '#000', border: 'none', padding: '6px 15px', fontWeight: 800, fontSize: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}><Play size={12} fill="#000" /> RECOMPUTE</button>
          </div>
        </div>
      </div>

      {/* Main Plot Area */}
      <div style={{ flex: 1, position: 'relative', background: THEME.surface, border: `1px solid ${THEME.border}`, padding: 20 }}>
        <CornerBracket position="bottom-left" />
        <CornerBracket position="bottom-right" />
        
        {activeView === 'overlay' && (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 11, fontWeight: 800, marginBottom: 15, color: THEME.textSecondary }}>MULTI-RATE POTENTIOSTATIC OVERLAY [N={studies.length}]</div>
            <div style={{ flex: 1 }}>{studies.length > 0 ? <OverlayPlot studies={studies} /> : null}</div>
          </div>
        )}

        {activeView === 'ipv' && (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 11, fontWeight: 800, marginBottom: 15, color: THEME.textSecondary }}>RANDLES-ŠEVČÍK MASS TRANSPORT ANALYSIS</div>
            <div style={{ flex: 1 }}>{studies.length > 0 ? <IpVsSqrtVPlot studies={studies} /> : null}</div>
          </div>
        )}

        {activeView === 'table' && (
          <div style={{ height: '100%', overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
              <thead>
                <tr style={{ background: 'rgba(0,242,255,0.1)', color: THEME.primary }}>
                  {['ν (V/s)', '√ν', 'ipa (µA)', '|ipc| (µA)', 'Epa (V)', 'Epc (V)', 'ΔEp (mV)', 'ip(RS)'].map(h => (
                    <th key={h} style={{ padding: '10px', textAlign: 'left', borderBottom: `1px solid ${THEME.border}` }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {studies.map((s, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '10px' }}>{s.rate}</td>
                    <td style={{ padding: '10px' }}>{Math.sqrt(s.rate).toFixed(3)}</td>
                    <td style={{ padding: '10px', color: '#ff3d00' }}>{(s.ipa * 1e6).toFixed(2)}</td>
                    <td style={{ padding: '10px', color: '#00e5ff' }}>{(s.ipc * 1e6).toFixed(2)}</td>
                    <td style={{ padding: '10px' }}>{s.Epa.toFixed(3)}</td>
                    <td style={{ padding: '10px' }}>{s.Epc.toFixed(3)}</td>
                    <td style={{ padding: '10px' }}>{(s.dEp * 1000).toFixed(1)}</td>
                    <td style={{ padding: '10px', color: THEME.textSecondary }}>{(s.ip_rs * 1e6).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
