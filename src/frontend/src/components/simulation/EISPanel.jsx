import React, { useState, useRef, useEffect, useCallback } from 'react';
import BodePlot from './BodePlot';
import { renderNyquistPublication, exportCanvasAsPNG, exportDataCSV } from '../../utils/plotExporter';
import { generateIEEEReport } from '../../utils/ieeeReportGenerator';
import { Zap, Download, RefreshCw, Activity, Terminal, Layers, Info } from 'lucide-react';

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

const DEFAULT_PARAMS = {
  Rs: 10, Rct: 100, Cdl: 1e-5, sigma_w: 50, n_cpe: 0.9,
  f_min: 0.01, f_max: 1e6, n_points: 100,
};

const PRESETS = {
  'IDEAL_RANDLES': { Rs: 10, Rct: 100, Cdl: 2e-5, sigma_w: 50, n_cpe: 1.0 },
  'CPE_ROUGH_SURFACE': { Rs: 8, Rct: 150, Cdl: 3e-5, sigma_w: 40, n_cpe: 0.85 },
  'WARBURG_DIFFUSION': { Rs: 15, Rct: 200, Cdl: 1e-6, sigma_w: 150, n_cpe: 0.9 },
  'PASSIVE_COATING': { Rs: 50, Rct: 5000, Cdl: 1e-7, sigma_w: 10, n_cpe: 0.8 },
};

function NyquistPlot({ data }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!data || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    renderNyquistPublication(ctx, rect.width, rect.height, data, {
      title: 'NYQUIST_TELEMETRY // Z′ vs −Z″',
    });
  }, [data]);

  return <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />;
}

function computeEIS(p) {
  const n = p.n_points;
  const freqs = Array.from({ length: n }, (_, i) =>
    Math.pow(10, Math.log10(p.f_min) + (Math.log10(p.f_max) - Math.log10(p.f_min)) * i / (n - 1)));
  const Z_real = [], Z_imag = [];
  freqs.forEach(f => {
    const w = 2 * Math.PI * f;
    const Zw_r = p.sigma_w / Math.sqrt(w), Zw_i = -p.sigma_w / Math.sqrt(w);
    const Zf_r = p.Rct + Zw_r, Zf_i = Zw_i;
    const Yc_r = p.Cdl * Math.pow(w, p.n_cpe) * Math.cos(p.n_cpe * Math.PI / 2);
    const Yc_i = p.Cdl * Math.pow(w, p.n_cpe) * Math.sin(p.n_cpe * Math.PI / 2);
    const d = Zf_r * Zf_r + Zf_i * Zf_i;
    const Yr = Yc_r + Zf_r / d, Yi = Yc_i - Zf_i / d;
    const d2 = Yr * Yr + Yi * Yi;
    Z_real.push(p.Rs + Yr / d2); Z_imag.push(-Yi / d2);
  });
  return { frequencies: freqs, Z_real, Z_imag, engine: 'V_EMULATOR_LITE' };
}

export default function EISPanel() {
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [plotType, setPlotType] = useState('nyquist');

  useEffect(() => {
    const imp = sessionStorage.getItem('RAMAN_EIS_IMPORT');
    if (imp) {
      try {
        setParams(p => ({ ...p, ...JSON.parse(imp) }));
        sessionStorage.removeItem('RAMAN_EIS_IMPORT');
      } catch (e) {}
    }
  }, []);

  const updateParam = (key, val) => setParams(prev => ({ ...prev, [key]: parseFloat(val) || 0 }));

  const downloadPlotPNG = useCallback(() => {
    const container = document.querySelector('.plot-canvas');
    const canvas = container?.querySelector('canvas');
    if (!canvas) return;
    const name = plotType === 'nyquist' ? 'RAMAN_Nyquist_Plot' : 'RAMAN_Bode_Plot';
    exportCanvasAsPNG(canvas, `${name}_${Date.now()}.png`);
  }, [plotType]);

  const downloadCSV = useCallback(() => {
    if (!result) return;
    exportDataCSV(result, `RAMAN_EIS_Data_${Date.now()}.csv`, {
      'Simulation': 'EIS — Randles + CPE + Warburg',
      'Rs (Ω)': params.Rs,
      'Rct (Ω)': params.Rct,
      'Cdl (F)': params.Cdl,
      'σw (Ω·s⁻⁰·⁵)': params.sigma_w,
      'n (CPE)': params.n_cpe,
      'Freq Range (Hz)': `${params.f_min}–${params.f_max}`,
      'Engine': result.engine,
    });
  }, [result, params]);

  const downloadIEEEReport = useCallback(() => {
    if (!result) return;
    const canvases = [];
    const container = document.querySelector('.plot-canvas');
    const canvas = container?.querySelector('canvas');
    if (canvas) canvases.push(canvas);

    generateIEEEReport({
      title: 'Electrochemical Impedance Spectroscopy Analysis of Randles Circuit with CPE Correction',
      authors: localStorage.getItem('raman_profile') ? JSON.parse(localStorage.getItem('raman_profile')).name : 'Research Team',
      affiliation: localStorage.getItem('raman_profile') ? JSON.parse(localStorage.getItem('raman_profile')).organization : 'VidyuthLabs Pvt. Ltd.',
      type: 'eis',
      data: result,
      params: params,
      plotCanvases: canvases,
    });
  }, [result, params]);

  const runSimulation = useCallback(async () => {
    setRunning(true);
    setTimeout(async () => {
      try {
        setResult(computeEIS(params));
      } catch (err) {
        console.error(err);
      } finally {
        setRunning(false);
      }
    }, 800);
  }, [params]);

  const fields = [
    { key: 'Rs', label: 'ELECTROLYTE_RESISTANCE', unit: 'Ω', step: 1 },
    { key: 'Rct', label: 'CHARGE_TRANSFER_RESISTANCE', unit: 'Ω', step: 10 },
    { key: 'Cdl', label: 'DOUBLE_LAYER_CAPACITANCE', unit: 'F', step: 1e-6 },
    { key: 'sigma_w', label: 'WARBURG_COEFFICIENT', unit: 'Ω·s⁻⁰·⁵', step: 5 },
    { key: 'n_cpe', label: 'PHASE_EXPONENT_N', unit: '—', step: 0.05 },
    { key: 'n_points', label: 'FREQUENCY_RESOLUTION', unit: 'PTS', step: 10 },
  ];

  return (
    <div className="eis-panel-container" style={{ 
      display: 'grid', 
      gridTemplateColumns: '380px 1fr', 
      gap: '16px', 
      height: 'calc(100vh - 120px)',
      padding: '12px'
    }}>
      {/* Left Sidebar */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
        <div className="card" style={{ 
          padding: '20px', 
          background: THEME.cardBg,
          backdropFilter: 'blur(16px)',
          border: `1px solid ${THEME.border}`,
          borderRadius: '4px',
          position: 'relative'
        }}>
          {/* Corner Brackets */}
          <div style={{ position: 'absolute', top: 0, left: 0, width: 8, height: 8, borderTop: `1px solid ${THEME.cyan}`, borderLeft: `1px solid ${THEME.cyan}`, opacity: 0.5 }} />
          <div style={{ position: 'absolute', top: 0, right: 0, width: 8, height: 8, borderTop: `1px solid ${THEME.cyan}`, borderRight: `1px solid ${THEME.cyan}`, opacity: 0.2 }} />
          <div style={{ position: 'absolute', bottom: 0, left: 0, width: 8, height: 8, borderBottom: `1px solid ${THEME.cyan}`, borderLeft: `1px solid ${THEME.cyan}`, opacity: 0.2 }} />
          <div style={{ position: 'absolute', bottom: 0, right: 0, width: 8, height: 8, borderBottom: `1px solid ${THEME.cyan}`, borderRight: `1px solid ${THEME.cyan}`, opacity: 0.5 }} />

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px' }}>
            <Activity size={16} color={THEME.cyan} />
            <h3 style={{ margin: 0, fontSize: '11px', fontWeight: '900', letterSpacing: '2px', color: '#fff' }}>PHYSICS_PARAMETERS</h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {fields.map(f => (
              <div key={f.key}>
                <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: THEME.textSecondary, marginBottom: '6px', fontFamily: THEME.fontMono }}>
                  <span>{f.label}</span>
                  <span style={{ color: THEME.cyan }}>[{f.unit}]</span>
                </label>
                <input 
                  type="number" 
                  value={params[f.key]}
                  step={f.step}
                  onChange={e => updateParam(f.key, e.target.value)}
                  style={{ 
                    width: '100%',
                    padding: '10px',
                    background: 'rgba(0,0,0,0.5)', 
                    border: `1px solid ${THEME.border}`,
                    color: '#fff',
                    borderRadius: '2px',
                    fontSize: '13px',
                    outline: 'none',
                    fontFamily: THEME.fontMono
                  }}
                />
              </div>
            ))}
          </div>

          <button 
            onClick={runSimulation} 
            disabled={running}
            style={{ 
              width: '100%', 
              marginTop: '24px',
              padding: '14px', 
              background: running ? 'transparent' : THEME.cyan,
              color: running ? THEME.cyan : '#000',
              border: running ? `1px solid ${THEME.cyan}` : 'none',
              borderRadius: '2px',
              fontSize: '12px', 
              fontWeight: '900', 
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '10px',
              cursor: running ? 'wait' : 'pointer',
              boxShadow: running ? 'none' : `0 0 20px ${THEME.cyan}44`,
              transition: 'all 0.3s'
            }}
          >
            {running ? <RefreshCw className="animate-spin" size={16} /> : <Zap size={16} />}
            {running ? 'COMPUTING_NYQUIST...' : 'EXECUTE_SIMULATION'}
          </button>
        </div>

        <div className="card" style={{ 
          padding: '16px', 
          background: THEME.cardBg,
          border: `1px solid ${THEME.border}`,
          borderRadius: '4px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Layers size={14} color={THEME.cyan} />
            <span style={{ fontSize: '10px', fontWeight: 'bold', color: THEME.textSecondary }}>MODEL_PRESETS</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {Object.keys(PRESETS).map(name => (
              <button 
                key={name} 
                onClick={() => setParams(p => ({ ...p, ...PRESETS[name] }))}
                style={{
                  padding: '8px',
                  background: 'rgba(255,255,255,0.02)',
                  border: `1px solid ${THEME.border}`,
                  color: THEME.textSecondary,
                  fontSize: '9px',
                  fontWeight: 'bold',
                  borderRadius: '2px',
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
              >
                {name}
              </button>
            ))}
          </div>
        </div>

        {result && (
          <div className="card" style={{ 
            padding: '16px', 
            background: THEME.cardBg,
            border: `1px solid ${THEME.border}`,
            borderRadius: '4px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Download size={14} color={THEME.cyan} />
              <span style={{ fontSize: '10px', fontWeight: 'bold', color: THEME.textSecondary }}>PUBLICATION_EXPORT</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <button onClick={downloadPlotPNG} style={{ background: 'rgba(255,255,255,0.05)', color: '#fff', border: `1px solid ${THEME.border}`, padding: '10px', fontSize: '10px', fontWeight: 'bold', cursor: 'pointer', textAlign: 'left' }}>
                ⬇ DOWNLOAD_PLOT_300DPI
              </button>
              <button onClick={downloadCSV} style={{ background: 'rgba(255,255,255,0.05)', color: '#fff', border: `1px solid ${THEME.border}`, padding: '10px', fontSize: '10px', fontWeight: 'bold', cursor: 'pointer', textAlign: 'left' }}>
                ⬇ EXPORT_TELEMETRY_CSV
              </button>
              <button onClick={downloadIEEEReport} style={{ background: THEME.cyan, color: '#000', border: 'none', padding: '10px', fontSize: '10px', fontWeight: '900', cursor: 'pointer', textAlign: 'left' }}>
                📄 GENERATE_IEEE_MANUSCRIPT
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div className="card" style={{ 
          flex: 1, 
          display: 'flex', 
          flexDirection: 'column', 
          background: '#050505',
          border: `1px solid ${THEME.border}`,
          borderRadius: '4px',
          overflow: 'hidden',
          position: 'relative'
        }}>
          {/* HUD Header */}
          <div style={{ 
            padding: '16px 24px', 
            background: 'rgba(255,255,255,0.02)', 
            borderBottom: `1px solid ${THEME.border}`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <div style={{ display: 'flex', gap: '24px' }}>
              <button 
                onClick={() => setPlotType('nyquist')}
                style={{ 
                  background: 'transparent',
                  border: 'none',
                  color: plotType === 'nyquist' ? THEME.cyan : THEME.textTertiary,
                  fontSize: '11px',
                  fontWeight: '900',
                  letterSpacing: '1px',
                  cursor: 'pointer',
                  padding: '4px 0',
                  borderBottom: plotType === 'nyquist' ? `2px solid ${THEME.cyan}` : 'none'
                }}
              >
                NYQUIST_DIAGRAM
              </button>
              <button 
                onClick={() => setPlotType('bode')}
                style={{ 
                  background: 'transparent',
                  border: 'none',
                  color: plotType === 'bode' ? THEME.cyan : THEME.textTertiary,
                  fontSize: '11px',
                  fontWeight: '900',
                  letterSpacing: '1px',
                  cursor: 'pointer',
                  padding: '4px 0',
                  borderBottom: plotType === 'bode' ? `2px solid ${THEME.cyan}` : 'none'
                }}
              >
                BODE_ANALYSIS
              </button>
            </div>
            <div style={{ display: 'flex', gap: '16px', fontSize: '9px', fontFamily: THEME.fontMono, color: THEME.textTertiary }}>
              <span>ENGINE: {result?.engine || 'STANDBY'}</span>
              <span>COORD_SYS: ORTHONORMAL</span>
            </div>
          </div>

          <div className="plot-canvas" style={{ flex: 1, position: 'relative', padding: '40px' }}>
            {result ? (
              plotType === 'nyquist' ? <NyquistPlot data={result} /> : <BodePlot data={result} />
            ) : (
              <div style={{ 
                height: '100%', 
                display: 'flex', 
                flexDirection: 'column', 
                alignItems: 'center', 
                justifyContent: 'center',
                color: THEME.textTertiary,
                fontFamily: THEME.fontMono,
                fontSize: '11px',
                gap: '16px'
              }}>
                <Info size={32} opacity={0.2} />
                <span>WAITING_FOR_SIMULATION_PARAMETERS...</span>
              </div>
            )}
            
            {/* HUD Overlay Brackets */}
            <div style={{ position: 'absolute', top: 20, left: 20, width: 20, height: 20, borderTop: `1px solid ${THEME.cyan}44`, borderLeft: `1px solid ${THEME.cyan}44` }} />
            <div style={{ position: 'absolute', top: 20, right: 20, width: 20, height: 20, borderTop: `1px solid ${THEME.cyan}44`, borderRight: `1px solid ${THEME.cyan}44` }} />
            <div style={{ position: 'absolute', bottom: 20, left: 20, width: 20, height: 20, borderBottom: `1px solid ${THEME.cyan}44`, borderLeft: `1px solid ${THEME.cyan}44` }} />
            <div style={{ position: 'absolute', bottom: 20, right: 20, width: 20, height: 20, borderBottom: `1px solid ${THEME.cyan}44`, borderRight: `1px solid ${THEME.cyan}44` }} />
          </div>
        </div>

        {result && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
            {[
              { label: 'IMPEDANCE_REAL', value: params.Rs.toFixed(2), unit: 'Ω' },
              { label: 'CHARGE_TRANSFER', value: params.Rct.toFixed(1), unit: 'Ω' },
              { label: 'DIFFUSION_LIMIT', value: params.sigma_w.toFixed(1), unit: 'σ' },
              { label: 'EFFECTIVE_CAP', value: (params.Cdl * 1e6).toFixed(2), unit: 'µF' },
            ].map((stat, i) => (
              <div key={i} className="card" style={{ 
                padding: '16px', 
                background: THEME.cardBg, 
                border: `1px solid ${THEME.border}`,
                display: 'flex',
                flexDirection: 'column',
                gap: '4px'
              }}>
                <div style={{ fontSize: '9px', color: THEME.textTertiary, fontFamily: THEME.fontMono }}>{stat.label}</div>
                <div style={{ fontSize: '20px', fontWeight: '900', color: THEME.cyan }}>
                  {stat.value} <span style={{ fontSize: '10px', fontWeight: 'normal', color: THEME.textSecondary }}>{stat.unit}</span>
                </div>
              </div>
            ))}
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
      `}} />
    </div>
  );
}

