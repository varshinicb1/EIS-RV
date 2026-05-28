/**
 * Lab Data Cleaner Panel
 * =======================
 * Autonomous electrochemical data cleaner with NVIDIA AI analysis.
 *
 * Features:
 * - Drag-and-drop xlsx upload
 * - Auto-detects CHI EIS, DPV, CV formats
 * - Shows cleaned data with quality report
 * - Calibration curve (R², sensitivity, LOD, LOQ)
 * - NVIDIA NIM AI analysis with structured interpretation
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  FlaskConical, Upload, Zap, Brain, CheckCircle2, AlertTriangle,
  BarChart3, TrendingUp, Activity, Sparkles, RefreshCcw, ChevronDown,
  ChevronRight, FileSpreadsheet, X,
} from 'lucide-react';

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

// ── helpers ───────────────────────────────────────────────────────────────
const fmt = (v, d = 3) => {
  if (v == null || Number.isNaN(v)) return '—';
  const a = Math.abs(v);
  if (a === 0) return '0';
  if (a >= 1e4 || a < 0.001) return v.toExponential(2);
  return v.toFixed(d);
};

async function apiPost(path, body) {
  return apiCall(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function apiUpload(path, file) {
  const fd = new FormData();
  fd.append('file', file);
  return apiCall(path, { method: 'POST', body: fd });
}

// ── Nyquist mini-plot ─────────────────────────────────────────────────────
function NyquistMini({ rows, height = 200 }) {
  if (!rows?.length) return null;
  const zr = rows.map(r => parseFloat(r.zreal_ohm));
  const zi = rows.map(r => -parseFloat(r.zimag_ohm));
  const xMin = Math.min(...zr), xMax = Math.max(...zr);
  const yMin = 0, yMax = Math.max(...zi);
  const W = 400, H = height, p = { l: 50, r: 10, t: 10, b: 30 };
  const pw = W - p.l - p.r, ph = H - p.t - p.b;
  const x = v => p.l + (v - xMin) / (xMax - xMin || 1) * pw;
  const y = v => p.t + ph - (v - yMin) / (yMax - yMin || 1) * ph;
  const pts = zr.map((r, i) => `${x(r)},${y(zi[i])}`).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: 420, height }}>
      <rect width={W} height={H} fill="var(--bg-elevated)" rx={4} />
      <line x1={p.l} y1={p.t} x2={p.l} y2={p.t + ph} stroke="var(--border-primary)" />
      <line x1={p.l} y1={p.t + ph} x2={p.l + pw} y2={p.t + ph} stroke="var(--border-primary)" />
      <text x={p.l + pw / 2} y={H - 6} fontSize={9} fill="var(--text-tertiary)" textAnchor="middle">Z′ (Ω)</text>
      <text x={12} y={p.t + ph / 2} fontSize={9} fill="var(--text-tertiary)" textAnchor="middle"
            transform={`rotate(-90 12 ${p.t + ph / 2})`}>−Z″ (Ω)</text>
      <polyline points={pts} fill="none" stroke="var(--color-success)" strokeWidth={1.5} />
      {zr.map((r, i) => <circle key={i} cx={x(r)} cy={y(zi[i])} r={2} fill="var(--color-success)" opacity={0.7} />)}
    </svg>
  );
}

// ── Calibration chart ─────────────────────────────────────────────────────
function CalibrationChart({ peakTable, linearRange, slope, intercept }) {
  const entries = Object.entries(peakTable || {})
    .filter(([, r]) => r.concentration > 0)
    .sort((a, b) => a[1].concentration - b[1].concentration);
  if (!entries.length) return null;

  const concs  = entries.map(([, r]) => r.concentration);
  const inets  = entries.map(([, r]) => {
    const v = r.i_net_a;
    return Math.abs(v) < 0.01 ? v * 1e6 : v;
  });
  const xMin = 0, xMax = Math.max(...concs);
  const yMin = Math.min(0, ...inets), yMax = Math.max(...inets);
  const W = 400, H = 200, p = { l: 55, r: 15, t: 10, b: 35 };
  const pw = W - p.l - p.r, ph = H - p.t - p.b;
  const x = v => p.l + (v - xMin) / (xMax - xMin || 1) * pw;
  const y = v => p.t + ph - (v - yMin) / (yMax - yMin || 1) * ph;

  // Fit line
  const fitX = [xMin, xMax];
  const fitY = fitX.map(c => slope * c + intercept);
  const fitPts = fitX.map((c, i) => `${x(c)},${y(fitY[i])}`).join(' ');

  // Linear range highlight
  const lrX1 = linearRange ? x(linearRange[0]) : null;
  const lrX2 = linearRange ? x(linearRange[1]) : null;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: 420, height: H }}>
      <rect width={W} height={H} fill="var(--bg-elevated)" rx={4} />
      {lrX1 && <rect x={lrX1} y={p.t} width={lrX2 - lrX1} height={ph}
                     fill="rgba(74,158,255,0.06)" />}
      <line x1={p.l} y1={p.t} x2={p.l} y2={p.t + ph} stroke="var(--border-primary)" />
      <line x1={p.l} y1={p.t + ph} x2={p.l + pw} y2={p.t + ph} stroke="var(--border-primary)" />
      <text x={p.l + pw / 2} y={H - 8} fontSize={9} fill="var(--text-tertiary)" textAnchor="middle">Concentration (µM)</text>
      <text x={12} y={p.t + ph / 2} fontSize={9} fill="var(--text-tertiary)" textAnchor="middle"
            transform={`rotate(-90 12 ${p.t + ph / 2})`}>I_net (µA)</text>
      <polyline points={fitPts} fill="none" stroke="var(--color-warning)" strokeWidth={1.5} strokeDasharray="4 2" />
      {entries.map(([label, r], i) => {
        const inet = Math.abs(r.i_net_a) < 0.01 ? r.i_net_a * 1e6 : r.i_net_a;
        return <circle key={i} cx={x(r.concentration)} cy={y(inet)} r={4}
                       fill="var(--color-success)" stroke="var(--bg-elevated)" strokeWidth={1} />;
      })}
    </svg>
  );
}

// ── Sheet result card ─────────────────────────────────────────────────────
function SheetCard({ sheetName, sheetInfo, cleanedData, onCalibrate }) {
  const [open, setOpen] = useState(true);
  const fmt_type = sheetInfo?.format || 'unknown';
  const qr = cleanedData?.quality_report || {};
  const series = cleanedData?.series || {};
  const eisData = cleanedData?.eis_data || [];

  const typeColor = {
    chi_eis: 'var(--color-success)',
    interleaved_conc: '#4a9eff',
    simple_xy: 'var(--color-warning)',
    unknown: 'var(--text-tertiary)',
  }[fmt_type] || 'var(--text-tertiary)';

  return (
    <div style={{ border: '1px solid var(--border-primary)', borderRadius: 8, marginBottom: 10, overflow: 'hidden' }}>
      {/* Header */}
      <div onClick={() => setOpen(o => !o)}
           style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
                    background: 'var(--bg-elevated)', cursor: 'pointer' }}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span style={{ fontWeight: 600, fontSize: 13 }}>{sheetName}</span>
        <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4,
                       background: `${typeColor}22`, color: typeColor, fontWeight: 600 }}>
          {fmt_type}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-tertiary)' }}>
          {sheetInfo?.rows_in} → {sheetInfo?.rows_out} rows
        </span>
        {sheetInfo?.rs_ohm && (
          <span style={{ fontSize: 10, color: 'var(--color-success)', marginLeft: 8 }}>
            Rs={sheetInfo.rs_ohm}Ω  Rct={sheetInfo.rct_ohm}Ω
          </span>
        )}
      </div>

      {open && (
        <div style={{ padding: 14 }}>
          {/* EIS: Nyquist + stats */}
          {fmt_type === 'chi_eis' && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 12 }}>
                {[
                  ['Rs', `${qr.rs_ohm} Ω`],
                  ['Rct', `${qr.rct_ohm} Ω`],
                  ['f_char', `${qr.f_char_hz} Hz`],
                  ['Points', qr.cleaned_rows],
                ].map(([l, v]) => (
                  <div key={l} style={{ background: 'var(--bg-surface)', borderRadius: 6, padding: '8px 10px',
                                        border: '1px solid var(--border-primary)' }}>
                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-success)',
                                  fontFamily: 'var(--font-data)' }}>{v}</div>
                    <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>{l}</div>
                  </div>
                ))}
              </div>
              {eisData.length > 0 && <NyquistMini rows={eisData} />}
            </div>
          )}

          {/* DPV/CV: series list + calibrate button */}
          {fmt_type === 'interleaved_conc' && Object.keys(series).length > 0 && (
            <div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10 }}>
                {Object.keys(series).map(label => (
                  <span key={label} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4,
                                             background: 'rgba(74,158,255,0.1)', color: '#4a9eff' }}>
                    {label}
                  </span>
                ))}
              </div>
              <button className="btn btn-sm btn-primary"
                      onClick={() => onCalibrate(series)}>
                <TrendingUp size={12} style={{ marginRight: 4 }} />
                Compute Calibration Curve
              </button>
            </div>
          )}

          {/* Issues */}
          {(sheetInfo?.issues || []).map((issue, i) => (
            <div key={i} style={{ fontSize: 10, color: 'var(--color-warning)', marginTop: 6,
                                   display: 'flex', alignItems: 'center', gap: 4 }}>
              <AlertTriangle size={10} /> {issue}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Calibration result card ───────────────────────────────────────────────
function CalibrationCard({ result }) {
  if (!result) return null;
  if (result.error) return (
    <div style={{ padding: 12, color: 'var(--color-error)', fontSize: 12 }}>
      Calibration error: {result.error}
    </div>
  );
  return (
    <div style={{ border: '1px solid var(--border-primary)', borderRadius: 8, padding: 14, marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <TrendingUp size={16} color="#4a9eff" />
        <span style={{ fontWeight: 600, fontSize: 14 }}>Calibration Curve</span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--color-success)', fontWeight: 600 }}>
          R² = {result.r_squared?.toFixed(4)}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
        {[
          ['Equation', result.equation],
          ['Sensitivity', `${fmt(result.sensitivity_uA_per_uM, 4)} µA/µM`],
          ['Linear Range', `${result.linear_range?.[0]}–${result.linear_range?.[1]} µM`],
          ['LOD', `${fmt(result.lod_uM, 2)} µM`],
          ['LOQ', `${fmt(result.loq_uM, 2)} µM`],
          ['Points', result.n_points],
        ].map(([l, v]) => (
          <div key={l} style={{ background: 'var(--bg-surface)', borderRadius: 6, padding: '8px 10px',
                                border: '1px solid var(--border-primary)' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)',
                          fontFamily: 'var(--font-data)', wordBreak: 'break-all' }}>{v}</div>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>{l}</div>
          </div>
        ))}
      </div>

      <CalibrationChart
        peakTable={result.peak_table}
        linearRange={result.linear_range}
        slope={result.sensitivity_uA_per_uM}
        intercept={result.intercept_uA}
      />
    </div>
  );
}

// ── AI Analysis card ──────────────────────────────────────────────────────
function AIAnalysisCard({ cleaningResult, calibrationResult, nimConfigured }) {
  const [context, setContext]   = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);

  const run = useCallback(async () => {
    setLoading(true); setError(null); setAnalysis(null);
    try {
      const result = await apiPost('/api/v1/lab-cleaner/ai-analyze', {
        cleaning_result:     cleaningResult,
        calibration_result:  calibrationResult,
        context:             context || undefined,
      });
      setAnalysis(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [cleaningResult, calibrationResult, context]);

  return (
    <div style={{ border: '1px solid var(--border-primary)', borderRadius: 8, padding: 14, marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Brain size={16} color="#a855f7" />
        <span style={{ fontWeight: 600, fontSize: 14 }}>AI Analysis</span>
        <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4,
                       background: nimConfigured ? 'rgba(168,85,247,0.15)' : 'rgba(255,100,100,0.1)',
                       color: nimConfigured ? '#a855f7' : 'var(--color-error)' }}>
          {nimConfigured ? 'NVIDIA NIM' : 'API key required'}
        </span>
        {analysis && (
          <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-tertiary)' }}>
            {analysis.model} · {analysis.tokens} tokens
          </span>
        )}
      </div>

      <textarea
        className="input-field"
        rows={2}
        placeholder="Optional context: electrode type, analyte, application, expected results..."
        value={context}
        onChange={e => setContext(e.target.value)}
        style={{ width: '100%', fontSize: 11, marginBottom: 10, resize: 'vertical' }}
      />

      <button
        className="btn btn-primary"
        onClick={run}
        disabled={loading || !nimConfigured}
        style={{ width: '100%', marginBottom: 12 }}
      >
        {loading
          ? <><RefreshCcw size={13} style={{ marginRight: 6, animation: 'spin 1s linear infinite' }} />Analyzing with NVIDIA NIM…</>
          : <><Sparkles size={13} style={{ marginRight: 6 }} />Analyze with AI</>
        }
      </button>

      {!nimConfigured && (
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', padding: '8px 12px',
                      background: 'var(--bg-elevated)', borderRadius: 6, marginBottom: 8 }}>
          Set <code>NVIDIA_API_KEY</code> in your <code>.env</code> file to enable AI analysis.
        </div>
      )}

      {error && (
        <div style={{ fontSize: 11, color: 'var(--color-error)', padding: '8px 12px',
                      background: 'rgba(239,83,80,0.06)', borderRadius: 6, marginBottom: 8 }}>
          {error}
        </div>
      )}

      {analysis?.analysis && (
        <div style={{ fontSize: 12, lineHeight: 1.8, color: 'var(--text-primary)',
                      background: 'var(--bg-elevated)', borderRadius: 8, padding: 16,
                      border: '1px solid var(--border-primary)', whiteSpace: 'pre-wrap',
                      maxHeight: 600, overflowY: 'auto' }}>
          {/* Render markdown-like bold headers */}
          {analysis.analysis.split('\n').map((line, i) => {
            if (line.startsWith('**') && line.endsWith('**')) {
              return <div key={i} style={{ fontWeight: 700, color: '#a855f7', marginTop: 12, marginBottom: 4 }}>
                {line.replace(/\*\*/g, '')}
              </div>;
            }
            if (/^\d+\.\s\*\*/.test(line)) {
              const clean = line.replace(/\*\*/g, '');
              return <div key={i} style={{ fontWeight: 600, color: '#4a9eff', marginTop: 10, marginBottom: 2 }}>
                {clean}
              </div>;
            }
            return <div key={i}>{line}</div>;
          })}
        </div>
      )}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────
function LabCleanerPanelContent() {
  const [file, setFile]               = useState(null);
  const [cleaning, setCleaning]       = useState(false);
  const [cleanResult, setCleanResult] = useState(null);
  const [cleanError, setCleanError]   = useState(null);
  const [calibResult, setCalibResult] = useState(null);
  const [nimStatus, setNimStatus]     = useState(null);
  const fileRef = useRef(null);

  // Check NIM status on mount
  React.useEffect(() => {
    apiCall('/api/v1/lab-cleaner/status')
      .then(d => setNimStatus(d))
      .catch(() => setNimStatus({ nim_configured: false }));
  }, []);

  const handleDrop = useCallback(e => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f?.name.endsWith('.xlsx')) setFile(f);
  }, []);

  const handleClean = useCallback(async () => {
    if (!file) return;
    setCleaning(true); setCleanError(null); setCleanResult(null); setCalibResult(null);
    try {
      const result = await apiUpload('/api/v1/lab-cleaner/clean', file);
      setCleanResult(result);
    } catch (e) {
      setCleanError(e.message);
    } finally {
      setCleaning(false);
    }
  }, [file]);

  const handleCalibrate = useCallback(async (series) => {
    try {
      const result = await apiPost('/api/v1/lab-cleaner/calibration', { series });
      setCalibResult(result);
    } catch (e) {
      setCalibResult({ error: e.message });
    }
  }, []);

  const reset = () => {
    setFile(null); setCleanResult(null); setCleanError(null); setCalibResult(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  return (
    <div style={{ padding: 20, height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16 }}
         role="main" aria-label="Lab Data Cleaner Panel">

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <FlaskConical size={20} color="var(--color-success)" />
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Lab Data Cleaner</div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            Autonomous cleaning for CHI EIS, DPV, CV xlsx files + NVIDIA AI analysis
          </div>
        </div>
        {nimStatus && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6,
                        fontSize: 11, padding: '4px 10px', borderRadius: 6,
                        background: nimStatus.nim_configured ? 'rgba(168,85,247,0.1)' : 'var(--bg-elevated)',
                        border: '1px solid var(--border-primary)' }}>
            <Brain size={12} color={nimStatus.nim_configured ? '#a855f7' : 'var(--text-tertiary)'} />
            {nimStatus.nim_configured ? `NIM: ${nimStatus.nim_model}` : 'NIM: not configured'}
          </div>
        )}
      </div>

      {/* Upload zone */}
      <div
        onDrop={handleDrop}
        onDragOver={e => e.preventDefault()}
        onClick={() => fileRef.current?.click()}
        style={{
          border: `2px dashed ${file ? 'var(--color-success)' : 'var(--border-secondary)'}`,
          borderRadius: 12, padding: 28, textAlign: 'center', cursor: 'pointer',
          background: file ? 'rgba(0,200,100,0.04)' : 'var(--bg-elevated)',
          transition: 'all 0.2s',
        }}
      >
        <input type="file" accept=".xlsx" ref={fileRef} style={{ display: 'none' }}
               onChange={e => setFile(e.target.files?.[0] || null)} />
        <FileSpreadsheet size={32} style={{ margin: '0 auto 10px', opacity: 0.6,
                                            color: file ? 'var(--color-success)' : 'var(--text-tertiary)' }} />
        {file ? (
          <div>
            <div style={{ fontWeight: 600, color: 'var(--color-success)', fontSize: 14 }}>{file.name}</div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4 }}>
              {(file.size / 1024).toFixed(1)} kB — click to change
            </div>
          </div>
        ) : (
          <div>
            <div style={{ fontWeight: 500, fontSize: 14 }}>Drop your xlsx file here</div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4 }}>
              Supports CHI608E EIS, DPV, CV — any format auto-detected
            </div>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          className="btn btn-primary"
          onClick={handleClean}
          disabled={!file || cleaning}
          style={{ flex: 1 }}
        >
          {cleaning
            ? <><RefreshCcw size={14} style={{ marginRight: 6, animation: 'spin 1s linear infinite' }} />Cleaning…</>
            : <><Zap size={14} style={{ marginRight: 6 }} />Clean Data</>
          }
        </button>
        {(cleanResult || file) && (
          <button className="btn btn-ghost" onClick={reset}>
            <X size={14} />
          </button>
        )}
      </div>

      {/* Error */}
      {cleanError && (
        <div style={{ padding: 12, background: 'rgba(239,83,80,0.06)', border: '1px solid var(--color-error)',
                      borderRadius: 8, fontSize: 12, color: 'var(--color-error)' }}>
          <AlertTriangle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
          {cleanError}
        </div>
      )}

      {/* Results */}
      {cleanResult && (
        <>
          {/* Summary bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
                        background: 'rgba(0,200,100,0.06)', border: '1px solid rgba(0,200,100,0.2)',
                        borderRadius: 8 }}>
            <CheckCircle2 size={16} color="var(--color-success)" />
            <span style={{ fontWeight: 600, fontSize: 13 }}>{cleanResult.filename}</span>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              {Object.keys(cleanResult.sheets || {}).length} sheets cleaned
            </span>
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--color-success)' }}>
              {cleanResult.output_files} files generated
            </span>
          </div>

          {/* Sheet cards */}
          {Object.entries(cleanResult.sheets || {}).map(([sheetName, sheetInfo]) => (
            <SheetCard
              key={sheetName}
              sheetName={sheetName}
              sheetInfo={sheetInfo}
              cleanedData={cleanResult.cleaned_data?.[sheetName]}
              onCalibrate={handleCalibrate}
            />
          ))}

          {/* Calibration result */}
          {calibResult && <CalibrationCard result={calibResult} />}

          {/* AI Analysis */}
          <AIAnalysisCard
            cleaningResult={cleanResult}
            calibrationResult={calibResult}
            nimConfigured={nimStatus?.nim_configured}
          />
        </>
      )}
    </div>
  );
}


export default function LabCleanerPanel() {
  return <LabCleanerPanelContent />;
}
