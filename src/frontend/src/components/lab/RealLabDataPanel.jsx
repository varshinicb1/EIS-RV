import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Upload, Activity, Layers, Droplet, AlertTriangle, Zap, Battery, Cpu, Search } from 'lucide-react';

// API helper
const API_BASE = '';

const apiCall = async (endpoint, options = {}) => {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
};

function fmt(val, digits = 3) {
  if (val == null || isNaN(val)) return '—';
  const num = Number(val);
  if (Math.abs(num) >= 1e5 || (Math.abs(num) < 1e-3 && num !== 0)) return num.toExponential(2);
  return num.toFixed(digits);
}

/* ─── Mini Chart (Canvas) ──────────────────────────────────────── */
function MiniChart({ xData, yData, xLabel, yLabel, color = '#10b981', width = 460, height = 220 }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!xData?.length || !yData?.length) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';

    const pad = { top: 20, right: 20, bottom: 36, left: 56 };
    const w = width - pad.left - pad.right;
    const h = height - pad.top - pad.bottom;

    const xMin = Math.min(...xData), xMax = Math.max(...xData);
    const yMin = Math.min(...yData), yMax = Math.max(...yData);
    const xRange = xMax - xMin || 1;
    const yRange = yMax - yMin || 1;

    const toX = v => pad.left + ((v - xMin) / xRange) * w;
    const toY = v => pad.top + h - ((v - yMin) / yRange) * h;

    // White background for scientific publication
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, width, height);

    // Grid
    ctx.strokeStyle = '#E5E7EB';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = pad.top + (h / 5) * i;
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + w, y); ctx.stroke();
    }

    // Axes
    ctx.strokeStyle = '#6B7280';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top);
    ctx.lineTo(pad.left, pad.top + h);
    ctx.lineTo(pad.left + w, pad.top + h);
    ctx.stroke();

    // Data line
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    for (let i = 0; i < xData.length; i++) {
      const x = toX(xData[i]), y = toY(yData[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Gradient fill
    const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + h);
    grad.addColorStop(0, color + '20');
    grad.addColorStop(1, color + '00');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(toX(xData[0]), toY(yData[0]));
    for (let i = 1; i < xData.length; i++) ctx.lineTo(toX(xData[i]), toY(yData[i]));
    ctx.lineTo(toX(xData[xData.length - 1]), pad.top + h);
    ctx.lineTo(toX(xData[0]), pad.top + h);
    ctx.closePath();
    ctx.fill();

    // Labels
    ctx.fillStyle = '#374151';
    ctx.font = '11px "Times New Roman", serif';
    ctx.textAlign = 'center';
    ctx.fillText(xLabel || '', pad.left + w / 2, height - 4);
    ctx.save();
    ctx.translate(12, pad.top + h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(yLabel || '', 0, 0);
    ctx.restore();

    // Axis tick values
    ctx.fillStyle = '#6B7280';
    ctx.font = '10px "Times New Roman", serif';
    ctx.textAlign = 'center';
    ctx.fillText(fmt(xMin, 1), pad.left, pad.top + h + 14);
    ctx.fillText(fmt(xMax, 1), pad.left + w, pad.top + h + 14);
    ctx.textAlign = 'right';
    ctx.fillText(fmt(yMin, 1), pad.left - 4, pad.top + h);
    ctx.fillText(fmt(yMax, 1), pad.left - 4, pad.top + 8);

    // Cleanup function
    return () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    };
  }, [xData, yData, xLabel, yLabel, color, width, height]);

  return <canvas ref={canvasRef} style={{ borderRadius: 8, border: '1px solid #E5E7EB', background: '#FFFFFF' }}
                 aria-label={`Chart showing ${yLabel} vs ${xLabel}`} />;
}

/* ─── Main Panel ───────────────────────────────────────────────── */
function RealLabDataPanelContent() {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [nvidiaStatus, setNvidiaStatus] = useState(null);
  const [nvidiaQuery, setNvidiaQuery] = useState('');
  const [nvidiaBusy, setNvidiaBusy] = useState(false);
  const [nvidiaResult, setNvidiaResult] = useState(null);
  const fileInputRef = useRef(null);

  // Check NVIDIA status on mount
  useEffect(() => {
    apiCall('/api/v2/nvidia/status').then(r => setNvidiaStatus(r)).catch(() => {});
  }, []);

  const handleDrop = (e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) setFile(f); };

  const uploadFile = async () => {
    if (!file) return;
    setBusy(true); setError(''); setResult(null);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const data = await apiCall('/api/v2/lab/analyze', { method: 'POST', body: fd });
      setResult(data);
    } catch (err) { 
      // Better error handling with specific messages
      console.error('Upload error:', err);
      if (err.message.includes('422') || err.message.includes('Unprocessable')) {
        setError('File format not recognized. Please upload a valid CHI608E (.xlsx) or Raman spectra (.txt) file.');
      } else if (err.message.includes('500')) {
        setError('Server error during analysis. The file may be corrupted or in an unsupported format. Please check the file and try again.');
      } else if (err.message.includes('413')) {
        setError('File too large. Please upload a smaller file (max 10MB).');
      } else {
        setError(`Analysis failed: ${err.message}`);
      }
    }
    finally { setBusy(false); }
  };

  const runNvidiaDiscovery = async () => {
    if (!nvidiaQuery.trim()) return;
    setNvidiaBusy(true); setNvidiaResult(null);
    try {
      const data = await apiCall('/api/v2/nvidia/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ application: nvidiaQuery }),
      });
      setNvidiaResult(data);
    } catch (err) { setError(err.message); }
    finally { setNvidiaBusy(false); }
  };

  /* ─── Renderers ─────────────────────────────────────────────── */

  const renderPlot = () => {
    if (!result?.plot_data) return null;
    const pd = result.plot_data;
    const tech = result.technique;

    let xData, yData, xLabel, yLabel, color;

    if (tech === 'EIS' && pd.Z_real && pd.Z_imag) {
      xData = pd.Z_real;
      yData = pd.Z_imag.map(v => -v);
      xLabel = "Z' (Ω)"; yLabel = "-Z'' (Ω)"; color = '#3b82f6';
    } else if (tech === 'GCD' && pd.time && pd.potential) {
      xData = pd.time; yData = pd.potential;
      xLabel = 'Time (s)'; yLabel = 'Potential (V)'; color = '#f59e0b';
    } else if ((tech === 'CV' || tech === 'DPV' || tech === 'DPV Calibration') && pd.potential && pd.current) {
      xData = pd.potential; yData = pd.current.map(v => v * 1e6);
      xLabel = 'Potential (V)'; yLabel = 'Current (µA)'; color = '#ec4899';
    } else if ((tech === 'Raman') && (pd.Wavenumber || pd.wavenumber || pd.Wave)) {
      xData = pd.Wavenumber || pd.wavenumber || pd.Wave;
      yData = pd.Intensity || pd.intensity || pd['#Intensity'];
      xLabel = 'Wavenumber (cm⁻¹)'; yLabel = 'Intensity (a.u.)'; color = '#f59e0b';
    } else {
      // Generic: plot first two columns
      const keys = Object.keys(pd);
      if (keys.length >= 2) {
        xData = pd[keys[0]]; yData = pd[keys[1]];
        xLabel = keys[0]; yLabel = keys[1]; color = '#10b981';
      }
    }

    if (!xData || !yData) return null;

    return (
      <div style={{ marginTop: 20 }}>
        <div style={sectionTitle}><Activity size={14} /> Interactive Plot</div>
        <MiniChart xData={xData} yData={yData} xLabel={xLabel} yLabel={yLabel} color={color} width={520} height={240} />
      </div>
    );
  };

  const renderEIS = (eis) => (
    <div style={{ marginTop: 16 }}>
      <div style={sectionTitle}><Zap size={14} color="#3b82f6" /> EIS Randles Circuit</div>
      <div style={gridStyle}>
        <StatCard label="Rs (Solution)" value={fmt(eis.Rs_ohm)} unit="Ω" />
        <StatCard label="Rct (Charge Transfer)" value={fmt(eis.Rct_ohm)} unit="Ω" accent="#10b981" />
        <StatCard label="Cdl (Double Layer)" value={fmt(eis.Cdl_F)} unit="F" />
        <StatCard label="Z Low Freq" value={fmt(eis.Z_low_freq_ohm)} unit="Ω" />
      </div>
    </div>
  );

  const renderRaman = (raman) => (
    <div style={{ marginTop: 16 }}>
      <div style={sectionTitle}><Layers size={14} color="#f59e0b" /> Raman Material ID</div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
        {raman.materials_detected?.map((m, i) => (
          <span key={i} style={tagStyle}>{m}</span>
        ))}
      </div>
      <div style={gridStyle}>
        {raman.band_assignments?.slice(0, 8).map((b, i) => (
          <div key={i} style={miniCardStyle}>
            <strong>{fmt(b.wavenumber, 0)} cm⁻¹</strong>
            <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>{b.assignment}</div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderDPV = (dpv) => (
    <div style={{ marginTop: 16 }}>
      <div style={sectionTitle}><Droplet size={14} color="#ec4899" /> DPV Analysis</div>
      {dpv.sensitivity !== undefined ? (
        <div style={gridStyle}>
          <StatCard label="Sensitivity" value={fmt(dpv.sensitivity)} unit="µA/µM/cm²" accent="#10b981" />
          <StatCard label="LOD" value={fmt(dpv.lod)} unit="µM" accent="#f59e0b" />
          <StatCard label="LOQ" value={fmt(dpv.loq)} unit="µM" />
          <StatCard label="R²" value={fmt(dpv.r_squared, 4)} accent="#3b82f6" />
        </div>
      ) : (
        <div style={gridStyle}>
          <StatCard label="Peak Current" value={fmt((dpv.peak_current_A || 0) * 1e6)} unit="µA" accent="#ec4899" />
          <StatCard label="Peak Potential" value={fmt(dpv.peak_potential_V)} unit="V" />
        </div>
      )}
      {dpv.equation && (
        <div style={{ marginTop: 8, padding: 8, background: 'rgba(255,255,255,0.03)', borderRadius: 6, fontFamily: 'monospace', fontSize: 11, color: '#94a3b8' }}>
          {dpv.equation}
        </div>
      )}
    </div>
  );

  const renderGCD = (gcd) => (
    <div style={{ marginTop: 16 }}>
      <div style={sectionTitle}><Battery size={14} color="#f59e0b" /> GCD Supercapacitor Metrics</div>
      <div style={gridStyle}>
        <StatCard label="Specific Capacitance" value={fmt(gcd.specific_capacitance_Fg)} unit="F/g" accent="#10b981" />
        <StatCard label="Energy Density" value={fmt(gcd.energy_density_Whkg)} unit="Wh/kg" accent="#3b82f6" />
        <StatCard label="Power Density" value={fmt(gcd.power_density_Wkg)} unit="W/kg" accent="#f59e0b" />
        <StatCard label="Coulombic Efficiency" value={fmt(gcd.coulombic_efficiency_pct, 1)} unit="%" accent="#ec4899" />
      </div>
      <div style={{ ...gridStyle, marginTop: 8 }}>
        <StatCard label="IR Drop" value={fmt(gcd.ir_drop_V, 4)} unit="V" />
        <StatCard label="Discharge Time" value={fmt(gcd.discharge_time_s)} unit="s" />
        <StatCard label="Charge Time" value={fmt(gcd.charge_time_s)} unit="s" />
        <StatCard label="ΔV Window" value={fmt(gcd.potential_window_V)} unit="V" />
      </div>
    </div>
  );

  const renderNvidia = () => (
    <div style={{ ...glassCard, marginTop: 24, borderTop: '4px solid #7c3aed' }}>
      <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Cpu size={18} color="#7c3aed" /> NVIDIA Material Discovery
        <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 10, background: nvidiaStatus?.available ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)', color: nvidiaStatus?.available ? '#10b981' : '#f59e0b' }}>
          {nvidiaStatus?.mode === 'cloud' ? 'CLOUD' : 'LOCAL FALLBACK'}
        </span>
      </div>
      <p style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 16px' }}>
        Ask the AI to discover materials for any application — biosensors, supercapacitors, batteries, etc.
      </p>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={nvidiaQuery}
          onChange={e => setNvidiaQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && runNvidiaDiscovery()}
          placeholder="e.g. Pb2+ detection biosensor, supercapacitor electrode..."
          style={{ flex: 1, padding: '10px 14px', background: 'rgba(15,23,42,0.6)', border: '1px solid #334155', borderRadius: 8, color: '#f8fafc', fontSize: 13, outline: 'none' }}
        />
        <button onClick={runNvidiaDiscovery} disabled={nvidiaBusy || !nvidiaQuery.trim()} style={{ ...btnStyle, width: 120 }}>
          {nvidiaBusy ? 'Searching...' : 'Discover'}
        </button>
      </div>
      {nvidiaResult?.candidates && (
        <div style={{ marginTop: 16 }}>
          {nvidiaResult.candidates.map((c, i) => (
            <div key={i} style={{ padding: 12, background: 'rgba(15,23,42,0.5)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 8, marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong style={{ color: '#f8fafc', fontSize: 14 }}>{c.name}</strong>
                <span style={{ fontSize: 11, color: '#10b981', fontFamily: 'monospace' }}>{(c.confidence * 100).toFixed(0)}% match</span>
              </div>
              <div style={{ fontSize: 12, color: '#7c3aed', fontFamily: 'monospace', marginTop: 2 }}>{c.formula}</div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>{c.rationale}</div>
              <div style={{ fontSize: 10, color: '#64748b', marginTop: 4 }}>Synthesis: {c.synthesis_route}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  /* ─── Layout ────────────────────────────────────────────────── */

  return (
    <div style={{ padding: 32, maxWidth: 1000, margin: '0 auto', background: 'linear-gradient(145deg, #0f172a 0%, #020617 100%)', minHeight: '100%', color: '#f8fafc', fontFamily: "'Inter', sans-serif" }}
         role="main" aria-label="Real Lab Data Analysis Panel">
      {/* Header */}
      <div style={{ marginBottom: 32, textAlign: 'center' }}>
        <h2 style={{ margin: '0 0 8px', fontSize: 28, fontWeight: 800, background: 'linear-gradient(90deg, #10b981, #3b82f6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          RĀMAN Studio Autonomous Analyzer
        </h2>
        <p style={{ margin: 0, fontSize: 13, color: '#94a3b8', maxWidth: 550, marginInline: 'auto' }}>
          Upload CHI608E files (.xlsx) or Raman spectra (.txt). Auto-detects EIS, CV, DPV, GCD, Raman and extracts physics-informed metrics with interactive plots.
        </p>
      </div>

      {/* Upload Zone */}
      <div style={glassCard}>
        <div onDrop={handleDrop} onDragOver={e => e.preventDefault()} onClick={() => fileInputRef.current?.click()}
          style={{ padding: 40, border: file ? '2px dashed #10b981' : '2px dashed #334155', borderRadius: 12, background: file ? 'rgba(16,185,129,0.04)' : 'rgba(15,23,42,0.5)', textAlign: 'center', cursor: 'pointer', transition: 'all 0.2s' }}>
          <Upload size={40} strokeWidth={1.5} style={{ display: 'block', margin: '0 auto 12px', color: file ? '#10b981' : '#64748b' }} />
          {file ? (
            <div>
              <strong style={{ color: '#10b981', fontSize: 16 }}>{file.name}</strong>
              <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>{(file.size / 1024).toFixed(1)} kB</div>
            </div>
          ) : (
            <div style={{ fontSize: 14, color: '#94a3b8' }}>
              Drop <strong style={{ color: '#f8fafc' }}>.xlsx</strong> / <strong style={{ color: '#f8fafc' }}>.txt</strong> here or click to browse
            </div>
          )}
          <input type="file" accept=".xlsx,.txt,.csv" ref={fileInputRef} style={{ display: 'none' }} onChange={e => setFile(e.target.files?.[0] || null)} />
        </div>

        {error && (
          <div style={{ marginTop: 16, padding: 12, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, fontSize: 12, color: '#ef4444', display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        <button onClick={uploadFile} disabled={!file || busy} style={{ ...btnStyle, width: '100%', marginTop: 16 }}>
          {busy ? 'Analyzing...' : 'Run Auto-Analysis'}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div style={{ ...glassCard, marginTop: 24, borderTop: '4px solid #10b981', animation: 'fadeIn 0.4s ease-out' }}>
          <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: 12, marginBottom: 16 }}>
            <div style={{ fontSize: 18, fontWeight: 700 }}>Analysis Results</div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
              Technique: <strong style={{ color: '#10b981', textTransform: 'uppercase' }}>{result.technique}</strong> · {result.num_points} points
              {result.original_filename && <span> · {result.original_filename}</span>}
            </div>
          </div>

          {result.eis_analysis && renderEIS(result.eis_analysis)}
          {result.raman_analysis && renderRaman(result.raman_analysis)}
          {result.dpv_analysis && renderDPV(result.dpv_analysis)}
          {result.gcd_analysis && renderGCD(result.gcd_analysis)}

          {renderPlot()}
        </div>
      )}

      {/* NVIDIA Discovery */}
      {renderNvidia()}

      <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }`}</style>
    </div>
  );
}

/* ─── Shared Styles ────────────────────────────────────────────── */
const glassCard = { background: 'rgba(30,41,59,0.4)', backdropFilter: 'blur(12px)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 16, padding: 28, marginBottom: 0, boxShadow: '0 16px 32px -8px rgba(0,0,0,0.5)' };
const gridStyle = { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 };
const sectionTitle = { fontSize: 13, fontWeight: 600, color: '#94a3b8', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 };
const tagStyle = { padding: '3px 10px', background: 'rgba(16,185,129,0.12)', color: '#10b981', borderRadius: 6, fontSize: 11, fontWeight: 600 };
const miniCardStyle = { padding: 8, background: 'rgba(15,23,42,0.5)', border: '1px solid rgba(255,255,255,0.04)', borderRadius: 6, fontSize: 11, color: '#f8fafc' };
const btnStyle = { padding: '12px 16px', fontSize: 14, fontWeight: 600, background: 'linear-gradient(135deg, #10b981, #059669)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', transition: 'all 0.2s' };

function StatCard({ label, value, unit, accent = '#f8fafc' }) {
  return (
    <div style={{ background: 'rgba(15,23,42,0.5)', border: '1px solid rgba(255,255,255,0.04)', borderRadius: 10, padding: 14 }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: accent, fontFamily: "'JetBrains Mono', monospace" }}>
        {value} <span style={{ fontSize: 11, color: '#64748b', fontWeight: 500 }}>{unit}</span>
      </div>
      <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>{label}</div>
    </div>
  );
}


export default function RealLabDataPanel() {
  return <RealLabDataPanelContent />;
}
