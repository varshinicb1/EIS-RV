import React, { useState, useEffect, useRef } from 'react';

const API = 'http://127.0.0.1:8000';

export default function DashboardPanel() {
  const [pipeStats, setPipeStats] = useState(null);
  const chartRef = useRef(null);

  // Telemetry is populated from /api/v2/system/metrics. Anything we don't
  // have a real value for stays null so the UI can render a "—".
  const [telemetry, setTelemetry] = useState({
    gpuMem: null,
    gpuMemMax: null,
    gpuName: null,
    gpuOk: false,
    cpuPercent: null,
    memUsedGB: null,
    memTotalGB: null,
    serialStatus: 'IDLE',
  });

  useEffect(() => {
    fetch(`${API}/api/v2/pipeline/stats`).then(r => r.json()).then(setPipeStats).catch(() => {});

    // WebSocket Telemetry
    let ws;
    const connectWS = () => {
      try {
        // In Electron, window.location is file://, so window.location.host is
        // empty — that's why the WS URL was previously coming out as
        // "ws://api/v2/ws/telemetry" (missing host) and getting blocked by
        // the CSP. Always point at the local sidecar in production.
        const isElectron = window.location.protocol === 'file:' || !!window.raman;
        const wsUrl = isElectron || window.location.hostname === 'localhost'
          ? 'ws://127.0.0.1:8000/api/v2/ws/telemetry'
          : `ws://${window.location.host}/api/v2/ws/telemetry`;
        ws = new WebSocket(wsUrl);
        ws.onmessage = (e) => {
          const data = JSON.parse(e.data);
          if (data.type === 'telemetry') {
            setTelemetry(p => ({
              ...p,
              serialStatus: data.status === 'MEASURING' ? 'STREAMING' : 'IDLE',
            }));
          }
        };
        ws.onclose = () => {
          setTelemetry(p => ({ ...p, serialStatus: 'DISCONNECTED' }));
          setTimeout(connectWS, 5000);
        };
      } catch(e) {}
    };
    connectWS();

    // Real metrics from /api/v2/system/metrics — psutil + torch.cuda when
    // available, null otherwise. The previous code used Math.random() here
    // and rendered the result as if it were live GPU memory; that has been
    // removed.
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetch(`${API}/api/v2/system/metrics`, { cache: 'no-store' });
        if (!res.ok) return;
        const m = await res.json();
        if (cancelled) return;
        setTelemetry(prev => ({
          ...prev,
          gpuMem:     m?.gpu?.memory_used_gb ?? null,
          gpuMemMax:  m?.gpu?.memory_total_gb ?? null,
          gpuName:    m?.gpu?.name ?? null,
          gpuOk:      Boolean(m?.gpu?.available),
          cpuPercent: m?.cpu_percent ?? null,
          memUsedGB:  m?.memory_used_gb ?? null,
          memTotalGB: m?.memory_total_gb ?? null,
        }));
      } catch {
        // Backend unreachable — leave previous values; nothing fabricated.
      }
    };
    tick();
    const int = setInterval(tick, 2000);

    return () => {
      clearInterval(int);
      if (ws) ws.close();
    };
  }, []);

  // Draw source distribution chart
  useEffect(() => {
    if (!pipeStats?.sources || !chartRef.current) return;
    const c = chartRef.current; const ctx = c.getContext('2d');
    const W = c.width = c.offsetWidth * 2; const H = c.height = c.offsetHeight * 2;
    ctx.scale(2, 2); const w = W / 2; const h = H / 2;

    ctx.fillStyle = '#0d1117'; ctx.fillRect(0, 0, w, h);

    const entries = Object.entries(pipeStats.sources);
    if (!entries.length) return;
    const total = entries.reduce((s, [, v]) => s + v, 0);
    const colors = ['#4a9eff', '#ffa726', '#ab47bc', '#66bb6a', '#ef5350'];
    let angle = -Math.PI / 2;
    const cx = w * 0.35; const cy = h / 2; const r = Math.min(w * 0.25, h * 0.4);

    entries.forEach(([name, count], i) => {
      const slice = (count / total) * Math.PI * 2;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, r, angle, angle + slice);
      ctx.fillStyle = colors[i % colors.length]; ctx.fill();
      ctx.strokeStyle = '#0d1117'; ctx.lineWidth = 2; ctx.stroke();
      angle += slice;
    });
    // Inner cutout (donut)
    ctx.beginPath(); ctx.arc(cx, cy, r * 0.55, 0, Math.PI * 2);
    ctx.fillStyle = '#0d1117'; ctx.fill();
    // Center text
    ctx.font = 'bold 16px system-ui'; ctx.fillStyle = '#c9d1d9'; ctx.textAlign = 'center';
    ctx.fillText(total.toLocaleString(), cx, cy + 4);
    ctx.font = '9px monospace'; ctx.fillStyle = '#8b949e';
    ctx.fillText('PAPERS', cx, cy + 16);
    // Legend
    let ly = 15;
    entries.forEach(([name, count], i) => {
      ctx.fillStyle = colors[i % colors.length]; ctx.fillRect(w * 0.7, ly, 10, 10);
      ctx.fillStyle = '#c9d1d9'; ctx.font = '10px system-ui'; ctx.textAlign = 'left';
      ctx.fillText(`${name} (${count})`, w * 0.7 + 14, ly + 9);
      ly += 18;
    });
  }, [pipeStats]);

  const engines = [
    { name: 'EIS', status: 'ready', desc: 'Electrochemical Impedance Spectroscopy', technique: 'Randles Circuit' },
    { name: 'CV', status: 'ready', desc: 'Cyclic Voltammetry', technique: 'Butler-Volmer' },
    { name: 'Battery', status: 'ready', desc: 'Printed Battery Simulation', technique: 'SPM / Peukert' },
    { name: 'GCD', status: 'ready', desc: 'Galvanostatic Charge-Discharge', technique: 'EDLC Model' },
    { name: 'DRT', status: 'ready', desc: 'Distribution of Relaxation Times', technique: 'Tikhonov Regularization' },
    { name: 'Circuit Fit', status: 'ready', desc: 'Equivalent Circuit CNLS Fitting', technique: 'LM / DE Optimizer' },
    { name: 'K-K Validation', status: 'ready', desc: 'Kramers-Kronig Consistency', technique: 'Boukamp Lin-KK' },
    { name: 'Synthesis', status: 'ready', desc: 'Virtual Synthesis Engine', technique: 'Physics Heuristic' },
    { name: 'AI / Alchemi', status: 'standby', desc: 'NVIDIA Quantum MLIP', technique: 'ORB-v3 / MACE-MP' },
  ];

  return (
    <div className="animate-in">
      <div className="dashboard-header">
        <h1>RĀMAN Studio</h1>
        <p>Electrochemical Research Platform — VidyuthLabs</p>
      </div>

      {/* Hero Stats */}
      <div className="grid-4" style={{ marginBottom: 14 }}>
        <div className="stat-card" style={{ background: 'linear-gradient(135deg, rgba(74,158,255,0.15), rgba(74,158,255,0.05))' }}>
          <div className="stat-value" style={{ fontSize: 28, color: '#4a9eff' }}>{pipeStats?.total_papers?.toLocaleString() || '—'}</div>
          <div className="stat-label">Research Papers</div>
        </div>
        <div className="stat-card" style={{ background: 'linear-gradient(135deg, rgba(118,185,0,0.15), rgba(118,185,0,0.05))' }}>
          <div className="stat-value" style={{ fontSize: 28, color: '#76b900' }}>{pipeStats?.unique_materials || '—'}</div>
          <div className="stat-label">Unique Materials</div>
        </div>
        <div className="stat-card" style={{ background: 'linear-gradient(135deg, rgba(255,167,38,0.15), rgba(255,167,38,0.05))' }}>
          <div className="stat-value" style={{ fontSize: 28, color: '#ffa726' }}>{pipeStats?.total_extractions?.toLocaleString() || '—'}</div>
          <div className="stat-label">Data Extractions</div>
        </div>
        <div className="stat-card" style={{ background: 'linear-gradient(135deg, rgba(171,71,188,0.15), rgba(171,71,188,0.05))' }}>
          <div className="stat-value" style={{ fontSize: 28 }}>9</div>
          <div className="stat-label">Simulation Engines</div>
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 14 }}>
        {/* Engines */}
        <div className="card">
          <div className="card-title">Simulation Engines</div>
          <table className="data-table">
            <thead><tr><th>Engine</th><th>Technique</th><th>Status</th></tr></thead>
            <tbody>
              {engines.map(eng => (
                <tr key={eng.name}>
                  <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{eng.name}</td>
                  <td className="mono">{eng.technique}</td>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10, fontFamily: 'var(--font-data)',
                      color: eng.status === 'ready' ? 'var(--color-success)' : 'var(--color-standby)' }}>
                      <span style={{ width: 5, height: 5, borderRadius: '50%', background: eng.status === 'ready' ? 'var(--color-success)' : 'var(--color-standby)' }} />
                      {eng.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Research Pipeline Stats */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="card" style={{ flex: 1 }}>
            <div className="card-title">Research Paper Sources</div>
            <canvas ref={chartRef} style={{ width: '100%', height: 140, display: 'block' }} />
          </div>

          {/* Application distribution */}
          {pipeStats?.applications && (
            <div className="card">
              <div className="card-title" style={{ marginBottom: 8 }}>Application Domains</div>
              {Object.entries(pipeStats.applications).slice(0, 6).map(([app, count]) => {
                const total = Object.values(pipeStats.applications).reduce((s, v) => s + v, 0);
                const pct = (count / total * 100).toFixed(0);
                return (
                  <div key={app} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ width: 80, fontSize: 10, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{app.replace('_', ' ')}</span>
                    <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--bg-elevated)' }}>
                      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 3,
                        background: app === 'fuel_cell' ? '#4a9eff' : app === 'battery' ? '#ffa726' : app === 'supercapacitor' ? '#76b900' : app === 'biosensor' ? '#ef5350' : '#ab47bc' }} />
                    </div>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--text-tertiary)', width: 50, textAlign: 'right' }}>{count}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Architecture & Telemetry */}
      <div className="grid-2">
        {/* Hardware Telemetry */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header" style={{ marginBottom: 16 }}>
            <div className="card-title">Live Hardware Telemetry</div>
            <span className="tag tag-blue" style={{ animation: 'pulse 2s infinite' }}>● ONLINE</span>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* GPU memory — real values from torch.cuda.mem_get_info on the backend */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                <span style={{ color: 'var(--text-secondary)' }}>
                  GPU memory{telemetry.gpuName ? ` · ${telemetry.gpuName}` : ''}
                </span>
                <span className="mono" style={{ color: '#4a9eff' }}>
                  {telemetry.gpuMem == null
                    ? 'no GPU detected'
                    : `${telemetry.gpuMem.toFixed(1)} / ${(telemetry.gpuMemMax ?? 0).toFixed(1)} GB`}
                </span>
              </div>
              <div style={{ width: '100%', height: 6, borderRadius: 3, background: 'var(--bg-elevated)', overflow: 'hidden' }}>
                <div style={{
                  width: telemetry.gpuMem != null && telemetry.gpuMemMax
                    ? `${Math.min(100, (telemetry.gpuMem / telemetry.gpuMemMax) * 100)}%`
                    : '0%',
                  height: '100%', background: '#4a9eff', transition: 'width 1s ease',
                }} />
              </div>
            </div>

            {/* CPU + system memory — from psutil */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                <span style={{ color: 'var(--text-secondary)' }}>CPU load · system memory</span>
                <span className="mono" style={{ color: '#66bb6a' }}>
                  {telemetry.cpuPercent == null ? '—' : `${telemetry.cpuPercent.toFixed(0)}%`}
                  {' · '}
                  {telemetry.memUsedGB == null
                    ? '—'
                    : `${telemetry.memUsedGB.toFixed(1)} / ${(telemetry.memTotalGB ?? 0).toFixed(1)} GB`}
                </span>
              </div>
              <div style={{ width: '100%', height: 6, borderRadius: 3, background: 'var(--bg-elevated)', overflow: 'hidden' }}>
                <div style={{
                  width: telemetry.cpuPercent != null ? `${Math.min(100, telemetry.cpuPercent)}%` : '0%',
                  height: '100%', background: '#66bb6a', transition: 'width 1s ease',
                }} />
              </div>
            </div>

            {/* Potentiostat Bridge */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                <span style={{ color: 'var(--text-secondary)' }}>Potentiostat Bridge (Serial COM3)</span>
                <span className="mono" style={{ color: telemetry.serialStatus === 'STREAMING' ? '#66bb6a' : telemetry.serialStatus === 'DISCONNECTED' ? '#ef5350' : '#ffa726' }}>{telemetry.serialStatus}</span>
              </div>
              <div style={{ width: '100%', height: 6, borderRadius: 3, background: 'var(--bg-elevated)', overflow: 'hidden' }}>
                <div style={{ width: telemetry.serialStatus === 'STREAMING' ? '100%' : telemetry.serialStatus === 'IDLE' ? '10%' : '0%', height: '100%', background: telemetry.serialStatus === 'STREAMING' ? '#66bb6a' : telemetry.serialStatus === 'DISCONNECTED' ? '#ef5350' : '#ffa726', transition: 'width 1s ease' }} />
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-title">System Architecture</div>
          <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
            <div><span className="mono" style={{ color: 'var(--text-tertiary)', marginRight: 6 }}>CORE </span> C++ / Eigen / OpenMP physics solvers</div>
            <div><span className="mono" style={{ color: 'var(--text-tertiary)', marginRight: 6 }}>API  </span> Python 3.14 / FastAPI v2 orchestration</div>
            <div><span className="mono" style={{ color: 'var(--text-tertiary)', marginRight: 6 }}>AI   </span> Python 3.13 / NVIDIA Alchemi (isolated)</div>
            <div><span className="mono" style={{ color: 'var(--text-tertiary)', marginRight: 6 }}>NLP  </span> Regex + Pattern NLP extraction pipeline</div>
            <div><span className="mono" style={{ color: 'var(--text-tertiary)', marginRight: 6 }}>DATA </span> SQLite + DuckDB + CSV/JSON export</div>
            <div><span className="mono" style={{ color: 'var(--text-tertiary)', marginRight: 6 }}>UI   </span> Electron / Vite / React renderer</div>
          </div>
        </div>
      </div>
    </div>
  );
}
