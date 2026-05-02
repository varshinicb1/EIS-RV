import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Battery, 
  Activity, 
  Download, 
  RefreshCw, 
  Settings, 
  Layers, 
  Info, 
  Zap, 
  Gauge,
  Terminal,
  ChevronRight
} from 'lucide-react';

const THEME = {
  cyan: '#00f2ff',
  bg: '#020204',
  cardBg: 'rgba(5, 5, 5, 0.8)',
  accentMuted: 'rgba(0, 242, 255, 0.1)',
  success: '#00ff95',
  border: 'rgba(255, 255, 255, 0.08)',
  textPrimary: '#ffffff',
  textSecondary: '#a0a0a0',
  textTertiary: '#606060',
  fontMono: '"JetBrains Mono", monospace',
};

const CHEMISTRIES = {
  'Zn-MnO₂': { chemistry: 'zinc_MnO2', area: 1.0, C_rate: 0.5, cutoff: 0.9, cathode_loading: 10, anode_loading: 8 },
  'Ag₂O-Zn': { chemistry: 'silver_zinc', area: 1.0, C_rate: 0.5, cutoff: 1.2, cathode_loading: 8, anode_loading: 8 },
  'LiFePO₄': { chemistry: 'LiFePO4', area: 1.0, C_rate: 0.5, cutoff: 2.5, cathode_loading: 12, anode_loading: 10 },
  'LiCoO₂': { chemistry: 'LiCoO2', area: 1.0, C_rate: 1.0, cutoff: 3.0, cathode_loading: 15, anode_loading: 10 },
};

const DEFAULT = {
  chemistry: 'zinc_MnO2',
  area: 1.0,
  C_rate: 0.5,
  cutoff: 0.9,
  cathode_loading: 10,
  anode_loading: 8,
  cathode_thickness: 100,
  anode_thickness: 80,
  temperature: 25,
};

// ── HUD Components ──────────────────────────────────────────────

const CornerBracket = ({ position }) => {
  const isTop = position.includes('top');
  const isLeft = position.includes('left');
  return (
    <div style={{
      position: 'absolute',
      width: '8px',
      height: '8px',
      [isTop ? 'top' : 'bottom']: '-1px',
      [isLeft ? 'left' : 'right']: '-1px',
      borderTop: isTop ? `1px solid ${THEME.cyan}` : 'none',
      borderBottom: !isTop ? `1px solid ${THEME.cyan}` : 'none',
      borderLeft: isLeft ? `1px solid ${THEME.cyan}` : 'none',
      borderRight: !isLeft ? `1px solid ${THEME.cyan}` : 'none',
      opacity: 0.6,
      pointerEvents: 'none'
    }} />
  );
};

// ── Client-side battery simulation (demo/offline mode) ──────────
function simulateBatteryLocal(params) {
  const { C_rate, cutoff, cathode_loading, anode_loading, area } = params;
  
  // OCV model (simplified zinc-MnO2 polynomial)
  const ocvCoeffs = [1.60, -0.25, -0.15, 0.05, 0.0, 0.0];
  function ocv(soc) {
    let v = 0;
    for (let i = 0; i < ocvCoeffs.length; i++) v += ocvCoeffs[i] * Math.pow(soc, i);
    return Math.max(cutoff * 0.9, Math.min(v, 1.65));
  }

  // Capacity
  const Q_cathode = cathode_loading * area * 308 / 1000;
  const Q_anode = anode_loading * area * 820 / 1000;
  const Q = Math.min(Q_cathode, Q_anode);
  const I = Q * C_rate / 1000;
  const R_int = 2.5;

  const n = 400;
  const soc = [], V = [], t = [], cap = [];
  let delivered = 0;

  for (let i = 0; i < n; i++) {
    const s = 0.99 - (0.98 * i / (n - 1));
    const V_ocv = ocv(s);
    const eta_ohmic = I * R_int;
    const eta_act = 0.0257 * Math.asinh(I / (area * 2 * 5e-3));
    const eta_conc = 0.05 * (1 / (s + 0.01) - 1);
    const v = V_ocv - eta_ohmic - eta_act - Math.min(eta_conc, 0.5);
    
    if (v < cutoff) break;
    
    soc.push(s);
    V.push(v);
    delivered = Q * (0.99 - s);
    cap.push(delivered);
    const t_h = delivered / (I * 1000);
    t.push(t_h * 60);
  }

  const avgV = V.reduce((a, b) => a + b, 0) / V.length;
  const energy = delivered * avgV;

  // Ragone data
  const ragone_E = [], ragone_P = [];
  for (let c = 0.1; c <= 20; c *= 1.3) {
    const Ic = Q * c / 1000;
    const vAvg = ocv(0.5) - Ic * R_int;
    if (vAvg < cutoff) break;
    const qEff = Q * Math.pow(C_rate / c, 0.15);
    const eWh = Math.min(qEff, Q) * vAvg / 1000;
    const massKg = (cathode_loading + anode_loading) * area * 1e-6;
    const tH = Math.min(qEff, Q) / (Ic * 1000);
    ragone_E.push(eWh / massKg);
    ragone_P.push((eWh / Math.max(tH, 1e-9)) / massKg);
  }

  return {
    engine: 'V_EMULATOR_LITE',
    discharge: { soc, V, t_min: t, cap_mAh: cap },
    metrics: {
      theoretical_mAh: Q,
      delivered_mAh: delivered,
      utilization: (delivered / Q * 100),
      energy_mWh: energy,
      avg_V: avgV,
      R_int: R_int,
    },
    ragone: { E: ragone_E, P: ragone_P },
  };
}

// ── Discharge Curve Canvas ──────────────────────────────────────
function DischargePlot({ data }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || !data) return;
    const canvas = ref.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width, H = rect.height;
    const pad = { t: 30, r: 20, b: 40, l: 50 };
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    
    ctx.clearRect(0, 0, W, H);

    if (!data.discharge || data.discharge.cap_mAh.length < 2) return;

    const xArr = data.discharge.cap_mAh;
    const yArr = data.discharge.V;
    const xMin = 0, xMax = Math.max(...xArr) * 1.05;
    const yMin = Math.min(...yArr) * 0.95, yMax = Math.max(...yArr) * 1.05;

    // Grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)'; 
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = pad.t + (ph * i / 5);
      ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + pw, y); ctx.stroke();
      const x = pad.l + (pw * i / 5);
      ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ph); ctx.stroke();
    }

    // Axes
    ctx.strokeStyle = THEME.border;
    ctx.strokeRect(pad.l, pad.t, pw, ph);

    // Ticks
    ctx.fillStyle = THEME.textTertiary;
    ctx.font = `9px ${THEME.fontMono}`;
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (let i = 0; i <= 5; i++) {
      const val = yMax - (yMax - yMin) * i / 5;
      ctx.fillText(val.toFixed(2), pad.l - 8, pad.t + ph * i / 5);
    }
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (let i = 0; i <= 5; i++) {
      const val = xMin + (xMax - xMin) * i / 5;
      ctx.fillText(val.toFixed(1), pad.l + pw * i / 5, pad.t + ph + 8);
    }

    // Labels
    ctx.fillStyle = THEME.textSecondary;
    ctx.font = `10px ${THEME.fontMono}`;
    ctx.textAlign = 'center';
    ctx.fillText('CAPACITY (mAh)', pad.l + pw / 2, H - 5);
    ctx.save();
    ctx.translate(15, pad.t + ph / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('VOLTAGE (V)', 0, 0);
    ctx.restore();

    // Data
    ctx.strokeStyle = THEME.cyan;
    ctx.lineWidth = 2;
    ctx.shadowBlur = 8;
    ctx.shadowColor = THEME.cyan;
    ctx.beginPath();
    for (let i = 0; i < xArr.length; i++) {
      const x = pad.l + ((xArr[i] - xMin) / (xMax - xMin)) * pw;
      const y = pad.t + ((yMax - yArr[i]) / (yMax - yMin)) * ph;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Gradient fill
    const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + ph);
    grad.addColorStop(0, 'rgba(0, 242, 255, 0.1)');
    grad.addColorStop(1, 'rgba(0, 242, 255, 0)');
    ctx.fillStyle = grad;
    ctx.lineTo(pad.l + ((xArr[xArr.length-1] - xMin) / (xMax - xMin)) * pw, pad.t + ph);
    ctx.lineTo(pad.l, pad.t + ph);
    ctx.closePath();
    ctx.fill();
  }, [data]);

  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />;
}

// ── Ragone Plot Canvas ──────────────────────────────────────────
function RagonePlot({ data }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || !data?.ragone) return;
    const canvas = ref.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width, H = rect.height;
    const pad = { t: 30, r: 20, b: 40, l: 50 };
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    
    ctx.clearRect(0, 0, W, H);

    const { E, P } = data.ragone;
    if (!E.length) return;

    const logE = E.map(v => Math.log10(Math.max(v, 1e-6)));
    const logP = P.map(v => Math.log10(Math.max(v, 1e-6)));
    const xMin = Math.floor(Math.min(...logP)), xMax = Math.ceil(Math.max(...logP));
    const yMin = Math.floor(Math.min(...logE)), yMax = Math.ceil(Math.max(...logE));

    // Grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let i = yMin; i <= yMax; i++) {
      const y = pad.t + ((yMax - i) / (yMax - yMin)) * ph;
      ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + pw, y); ctx.stroke();
    }
    for (let i = xMin; i <= xMax; i++) {
      const x = pad.l + ((i - xMin) / (xMax - xMin)) * pw;
      ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ph); ctx.stroke();
    }

    ctx.strokeStyle = THEME.border;
    ctx.strokeRect(pad.l, pad.t, pw, ph);

    // Ticks
    ctx.fillStyle = THEME.textTertiary;
    ctx.font = `9px ${THEME.fontMono}`;
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (let i = yMin; i <= yMax; i++) {
      ctx.fillText(`10^${i}`, pad.l - 8, pad.t + ((yMax - i) / (yMax - yMin)) * ph);
    }
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (let i = xMin; i <= xMax; i++) {
      ctx.fillText(`10^${i}`, pad.l + ((i - xMin) / (xMax - xMin)) * pw, pad.t + ph + 8);
    }

    // Labels
    ctx.fillStyle = THEME.textSecondary;
    ctx.font = `10px ${THEME.fontMono}`;
    ctx.textAlign = 'center';
    ctx.fillText('POWER DENSITY (W/kg)', pad.l + pw / 2, H - 5);
    ctx.save();
    ctx.translate(15, pad.t + ph / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('ENERGY DENSITY (Wh/kg)', 0, 0);
    ctx.restore();

    // Line
    ctx.strokeStyle = '#ef5350';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < logE.length; i++) {
      const x = pad.l + ((logP[i] - xMin) / (xMax - xMin)) * pw;
      const y = pad.t + ((yMax - logE[i]) / (yMax - yMin)) * ph;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Data points
    ctx.fillStyle = '#ef5350';
    for (let i = 0; i < logE.length; i++) {
      const x = pad.l + ((logP[i] - xMin) / (xMax - xMin)) * pw;
      const y = pad.t + ((yMax - logE[i]) / (yMax - yMin)) * ph;
      ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.stroke();
    }
  }, [data]);

  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />;
}

// ── Main Battery Panel ──────────────────────────────────────────
export default function BatteryPanel() {
  const [params, setParams] = useState(DEFAULT);
  const [result, setResult] = useState(null);
  const [computing, setComputing] = useState(false);

  const update = (k, v) => setParams(p => ({ ...p, [k]: v }));

  const loadPreset = (name) => {
    const p = CHEMISTRIES[name];
    if (p) setParams(prev => ({ ...prev, ...p }));
  };

  const simulate = useCallback(async () => {
    setComputing(true);
    // Simulate real-world latency
    await new Promise(r => setTimeout(r, 600));
    try {
      // Try backend first
      const api = window.raman?.api;
      if (api) {
        const res = await api.call('/api/simulate/battery', params);
        setResult({ ...res, engine: 'V_EMULATOR_PRO' });
      } else {
        setResult(simulateBatteryLocal(params));
      }
    } catch {
      setResult(simulateBatteryLocal(params));
    } finally {
      setComputing(false);
    }
  }, [params]);

  const exportCSV = useCallback(() => {
    if (!result?.discharge) return;
    const { cap_mAh, V, t_min, soc } = result.discharge;
    let csv = 'SOC,Capacity_mAh,Voltage_V,Time_min\n';
    for (let i = 0; i < V.length; i++) {
      csv += `${soc[i]?.toFixed(4) ?? ''},${cap_mAh[i]?.toFixed(4) ?? ''},${V[i]?.toFixed(4) ?? ''},${t_min[i]?.toFixed(3) ?? ''}\n`;
    }
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `battery_discharge_${params.chemistry}.csv`; a.click();
    URL.revokeObjectURL(url);
  }, [result, params]);

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '320px 1fr',
      gap: '20px',
      height: 'calc(100vh - 140px)',
      padding: '10px',
      background: THEME.bg,
      color: THEME.textPrimary,
      fontFamily: 'Inter, sans-serif'
    }}>
      {/* ── Left Sidebar: Parameters ── */}
      <div style={{
        background: THEME.cardBg,
        border: `1px solid ${THEME.border}`,
        borderRadius: '4px',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        position: 'relative',
        overflowY: 'auto'
      }}>
        <CornerBracket position="top-left" />
        <CornerBracket position="top-right" />
        <CornerBracket position="bottom-left" />
        <CornerBracket position="bottom-right" />

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <Battery size={20} color={THEME.cyan} />
          <div style={{ fontSize: '14px', fontWeight: 'bold', letterSpacing: '1px' }}>BATTERY_SIM_V2</div>
        </div>

        <div style={{ fontSize: '11px', color: THEME.textTertiary, marginBottom: '8px' }}>
          CONFIGURE ELECTROCHEMICAL PARAMETERS FOR NANO-ARCHITECTURE SIMULATION.
        </div>

        {/* Presets */}
        <div style={{ marginBottom: '8px' }}>
          <div style={{ fontSize: '10px', fontWeight: 'bold', color: THEME.textSecondary, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={12} /> CHEMISTRY_PRESETS
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            {Object.keys(CHEMISTRIES).map(name => (
              <button key={name} 
                onClick={() => loadPreset(name)}
                style={{
                  padding: '6px',
                  background: 'rgba(255,255,255,0.02)',
                  border: `1px solid ${THEME.border}`,
                  color: params.chemistry === CHEMISTRIES[name].chemistry ? THEME.cyan : THEME.textSecondary,
                  fontSize: '9px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  borderRadius: '2px',
                  textAlign: 'left'
                }}>
                {name.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Inputs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {[
            { key: 'C_rate', label: 'DISCHARGE_RATE', unit: 'C', icon: Gauge },
            { key: 'area', label: 'ACTIVE_AREA', unit: 'cm²', icon: Activity },
            { key: 'cathode_loading', label: 'CATHODE_LOAD', unit: 'mg/cm²', icon: Layers },
            { key: 'anode_loading', label: 'ANODE_LOAD', unit: 'mg/cm²', icon: Layers },
            { key: 'cutoff', label: 'V_CUTOFF', unit: 'V', icon: Zap },
            { key: 'temperature', label: 'TEMP_K', unit: '°C', icon: Info },
          ].map(field => (
            <div key={field.key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <div style={{ fontSize: '9px', fontWeight: 'bold', color: THEME.textSecondary, display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <field.icon size={10} /> {field.label}
                </div>
                <div style={{ fontSize: '9px', color: THEME.cyan, fontWeight: 'mono' }}>{field.unit}</div>
              </div>
              <input 
                type="number"
                value={params[field.key]}
                onChange={e => update(field.key, parseFloat(e.target.value))}
                style={{
                  width: '100%',
                  background: 'rgba(0,0,0,0.3)',
                  border: `1px solid ${THEME.border}`,
                  padding: '8px',
                  color: THEME.textPrimary,
                  fontSize: '12px',
                  fontFamily: THEME.fontMono,
                  borderRadius: '2px'
                }}
              />
            </div>
          ))}
        </div>

        <div style={{ marginTop: 'auto', display: 'flex', gap: '8px' }}>
          <button 
            onClick={simulate}
            disabled={computing}
            style={{
              flex: 1,
              padding: '12px',
              background: computing ? THEME.accentMuted : THEME.cyan,
              border: 'none',
              color: computing ? THEME.cyan : '#000',
              fontWeight: 'bold',
              fontSize: '12px',
              cursor: 'pointer',
              borderRadius: '2px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              transition: 'all 0.2s'
            }}>
            {computing ? <RefreshCw size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {computing ? 'COMPUTING...' : 'RUN_SIMULATION'}
          </button>
          {result && (
            <button 
              onClick={exportCSV}
              style={{
                width: '40px',
                background: 'rgba(255,255,255,0.05)',
                border: `1px solid ${THEME.border}`,
                color: THEME.textPrimary,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '2px'
              }}>
              <Download size={16} />
            </button>
          )}
        </div>
      </div>

      {/* ── Right Content: Plots & Metrics ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', overflowY: 'auto' }}>
        
        {/* Top Header: Telemetry Status */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '10px 15px',
          background: 'rgba(255,255,255,0.02)',
          border: `1px solid ${THEME.border}`,
          borderRadius: '4px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: result ? THEME.success : THEME.textTertiary }} />
              <span style={{ fontSize: '10px', fontWeight: 'bold', color: THEME.textSecondary }}>STATUS: {result ? 'READY' : 'IDLE'}</span>
            </div>
            <div style={{ height: '12px', width: '1px', background: THEME.border }} />
            <div style={{ fontSize: '10px', fontWeight: 'bold', color: THEME.textSecondary }}>ENGINE: <span style={{ color: THEME.cyan }}>{result?.engine || 'N/A'}</span></div>
          </div>
          <div style={{ fontSize: '10px', color: THEME.textTertiary, fontFamily: THEME.fontMono }}>
            {new Date().toISOString().split('T')[1].split('.')[0]} // SYS_ID: BATT_77
          </div>
        </div>

        {/* Metrics Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '15px'
        }}>
          {[
            { label: 'ENERGY_DENSITY', value: result?.metrics?.energy_mWh?.toFixed(2) || '0.00', unit: 'mWh', icon: Zap },
            { label: 'UTILIZATION', value: result?.metrics?.utilization?.toFixed(1) || '0.0', unit: '%', icon: Activity },
            { label: 'DELIVERED_CAP', value: result?.metrics?.delivered_mAh?.toFixed(2) || '0.00', unit: 'mAh', icon: Battery },
            { label: 'AVG_VOLTAGE', value: result?.metrics?.avg_V?.toFixed(3) || '0.000', unit: 'V', icon: Gauge },
          ].map((stat, i) => (
            <div key={i} style={{
              background: THEME.cardBg,
              border: `1px solid ${THEME.border}`,
              padding: '15px',
              borderRadius: '4px',
              position: 'relative'
            }}>
              <div style={{ fontSize: '9px', fontWeight: 'bold', color: THEME.textSecondary, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <stat.icon size={10} color={THEME.cyan} /> {stat.label}
              </div>
              <div style={{ fontSize: '20px', fontWeight: '900', color: THEME.cyan, fontFamily: THEME.fontMono }}>
                {stat.value} <span style={{ fontSize: '10px', fontWeight: 'normal', color: THEME.textSecondary }}>{stat.unit}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Plots Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '20px',
          flex: 1,
          minHeight: '400px'
        }}>
          {/* Discharge Curve */}
          <div style={{
            background: THEME.cardBg,
            border: `1px solid ${THEME.border}`,
            borderRadius: '4px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            position: 'relative'
          }}>
            <CornerBracket position="top-left" />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
              <div style={{ fontSize: '11px', fontWeight: 'bold', letterSpacing: '1px' }}>DISCHARGE_TELEMETRY // V vs. Q</div>
              <Terminal size={12} color={THEME.textTertiary} />
            </div>
            <div style={{ flex: 1, position: 'relative' }}>
              {!result && <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', color: THEME.textTertiary, fontSize: '10px' }}>WAITING_FOR_DATA_INJECTION...</div>}
              <DischargePlot data={result} />
            </div>
          </div>

          {/* Ragone Plot */}
          <div style={{
            background: THEME.cardBg,
            border: `1px solid ${THEME.border}`,
            borderRadius: '4px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            position: 'relative'
          }}>
            <CornerBracket position="top-left" />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
              <div style={{ fontSize: '11px', fontWeight: 'bold', letterSpacing: '1px' }}>RAGONE_CHARACTERISTIC // E vs. P</div>
              <Terminal size={12} color={THEME.textTertiary} />
            </div>
            <div style={{ flex: 1, position: 'relative' }}>
              {!result && <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', color: THEME.textTertiary, fontSize: '10px' }}>WAITING_FOR_DATA_INJECTION...</div>}
              <RagonePlot data={result} />
            </div>
          </div>
        </div>

        {/* Device Summary Table */}
        {result && (
          <div style={{
            background: THEME.cardBg,
            border: `1px solid ${THEME.border}`,
            padding: '20px',
            borderRadius: '4px',
            position: 'relative'
          }}>
            <div style={{ fontSize: '11px', fontWeight: 'bold', marginBottom: '15px', color: THEME.textSecondary }}>DEVICE_SUMMARY_REPORT</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px' }}>
              {[
                { label: 'THEORETICAL_CAP', value: result.metrics.theoretical_mAh?.toFixed(3), unit: 'mAh' },
                { label: 'INTERNAL_RESISTANCE', value: result.metrics.R_int?.toFixed(2), unit: 'Ω' },
                { label: 'ACTIVE_CHEMISTRY', value: params.chemistry, unit: '' },
                { label: 'DISCHARGE_REGIME', value: params.C_rate, unit: 'C' }
              ].map((item, i) => (
                <div key={i}>
                  <div style={{ fontSize: '8px', color: THEME.textTertiary, marginBottom: '4px' }}>{item.label}</div>
                  <div style={{ fontSize: '12px', fontWeight: 'bold', color: THEME.textPrimary, fontFamily: THEME.fontMono }}>
                    {item.value} <span style={{ fontSize: '9px', color: THEME.textSecondary }}>{item.unit}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .animate-spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        ::-webkit-scrollbar {
          width: 4px;
          height: 4px;
        }
        ::-webkit-scrollbar-track {
          background: rgba(0, 0, 0, 0.2);
        }
        ::-webkit-scrollbar-thumb {
          background: ${THEME.border};
          border-radius: 2px;
        }
        ::-webkit-scrollbar-thumb:hover {
          background: ${THEME.textTertiary};
        }
      `}} />
    </div>
  );
}
