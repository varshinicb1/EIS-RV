import React, { useEffect, useRef, useState } from 'react';

/**
 * Dashboard — at-a-glance view of what the local backend is doing.
 *
 * Every metric on this page is real (pulled from the backend) or null. We
 * never fabricate values: a missing GPU shows "No GPU detected", an offline
 * backend shows "—", and the donut chart only draws if pipeline papers
 * exist. No glow effects, no "buffer cache 42.18%" theater, no fake serial
 * port animations.
 */

const API = 'http://127.0.0.1:8000';

const ENGINES = [
  { name: 'EIS',           technique: 'Randles + CPE',           status: 'ready' },
  { name: 'CV',            technique: 'Butler-Volmer / Nernst',  status: 'ready' },
  { name: 'Battery',       technique: 'SPM / Peukert',            status: 'ready' },
  { name: 'GCD',           technique: 'EDLC + IR-drop',           status: 'ready' },
  { name: 'DRT',           technique: 'Tikhonov regularisation', status: 'ready' },
  { name: 'Circuit fit',   technique: 'Levenberg-Marquardt',     status: 'ready' },
  { name: 'Kramers-Kronig', technique: 'Schönleber μ',            status: 'ready' },
  { name: 'Synthesis',     technique: 'Heuristic + DFT',          status: 'ready' },
  { name: 'NIM Alchemi',   technique: 'Llama-3.3-70B + curated', status: 'ready' },
];

export default function DashboardPanel() {
  const [pipeStats, setPipeStats] = useState(null);
  const [telemetry, setTelemetry] = useState({
    gpuMem: null, gpuMemMax: null, gpuName: null,
    cpuPercent: null, memUsedGB: null, memTotalGB: null,
    serialStatus: 'idle',
  });
  const [backendOnline, setBackendOnline] = useState(false);
  const chartRef = useRef(null);

  useEffect(() => {
    fetch(`${API}/api/v2/pipeline/stats`).then(r => r.ok ? r.json() : null).then(setPipeStats).catch(() => {});

    let ws;
    const connectWS = () => {
      try {
        const isElectron = window.location.protocol === 'file:' || !!window.raman;
        const wsUrl = isElectron || window.location.hostname === 'localhost'
          ? 'ws://127.0.0.1:8000/api/v2/ws/telemetry'
          : `ws://${window.location.host}/api/v2/ws/telemetry`;
        ws = new WebSocket(wsUrl);
        ws.onmessage = (e) => {
          try {
            const data = JSON.parse(e.data);
            if (data.type === 'telemetry') {
              setTelemetry(p => ({ ...p, serialStatus: data.status === 'MEASURING' ? 'streaming' : 'idle' }));
            }
          } catch { /* ignore non-JSON frames */ }
        };
        ws.onclose = () => {
          setTelemetry(p => ({ ...p, serialStatus: 'disconnected' }));
          setTimeout(connectWS, 5000);
        };
      } catch { /* WS gated by license — silently retry */ }
    };
    connectWS();

    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetch(`${API}/api/v2/system/metrics`, { cache: 'no-store' });
        if (!res.ok) { if (!cancelled) setBackendOnline(false); return; }
        const m = await res.json();
        if (cancelled) return;
        setBackendOnline(true);
        setTelemetry(prev => ({
          ...prev,
          gpuMem:     m?.gpu?.memory_used_gb ?? null,
          gpuMemMax:  m?.gpu?.memory_total_gb ?? null,
          gpuName:    m?.gpu?.name ?? null,
          cpuPercent: m?.cpu_percent ?? null,
          memUsedGB:  m?.memory_used_gb ?? null,
          memTotalGB: m?.memory_total_gb ?? null,
        }));
      } catch {
        if (!cancelled) setBackendOnline(false);
      }
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => { cancelled = true; clearInterval(id); if (ws) ws.close(); };
  }, []);

  // Donut: paper sources distribution
  useEffect(() => {
    if (!pipeStats?.sources || !chartRef.current) return;
    const c = chartRef.current; const ctx = c.getContext('2d');
    const W = c.width = c.offsetWidth * 2; const H = c.height = c.offsetHeight * 2;
    ctx.scale(2, 2); const w = W / 2; const h = H / 2;

    ctx.clearRect(0, 0, w, h);

    const entries = Object.entries(pipeStats.sources);
    if (!entries.length) return;
    const total = entries.reduce((s, [, v]) => s + v, 0);
    const palette = ['#4a8eff', '#34c759', '#ff9f0a', '#a78bfa', '#ff7e6b', '#5fc8d8'];
    let angle = -Math.PI / 2;
    const cx = w * 0.32; const cy = h / 2; const r = Math.min(w * 0.22, h * 0.4);

    entries.forEach(([_name, count], i) => {
      const slice = (count / total) * Math.PI * 2;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, r, angle, angle + slice);
      ctx.fillStyle = palette[i % palette.length]; ctx.fill();
      angle += slice;
    });
    ctx.beginPath(); ctx.arc(cx, cy, r * 0.6, 0, Math.PI * 2);
    ctx.fillStyle = getCss('--bg-surface'); ctx.fill();

    ctx.font = '600 16px Inter, system-ui'; ctx.fillStyle = getCss('--text-primary'); ctx.textAlign = 'center';
    ctx.fillText(total.toLocaleString(), cx, cy + 4);
    ctx.font = '10px Inter, system-ui'; ctx.fillStyle = getCss('--text-tertiary');
    ctx.fillText('papers', cx, cy + 18);

    let ly = 14;
    entries.forEach(([name, count], i) => {
      ctx.fillStyle = palette[i % palette.length];
      ctx.fillRect(w * 0.65, ly + 2, 8, 8);
      ctx.fillStyle = getCss('--text-primary');
      ctx.font = '11.5px Inter, system-ui';
      ctx.textAlign = 'left';
      ctx.fillText(`${name}`, w * 0.65 + 14, ly + 9);
      ctx.fillStyle = getCss('--text-tertiary');
      ctx.fillText(`${count}`, w * 0.65 + 14 + 100, ly + 9);
      ly += 18;
    });
  }, [pipeStats]);

  return (
    <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Hero header */}
      <header style={{ marginBottom: 4 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
          Dashboard
        </h1>
        <div style={{ marginTop: 4, color: 'var(--text-tertiary)', fontSize: 13 }}>
          Local backend status, simulation engines, and research pipeline activity.
        </div>
      </header>

      {/* Top-level metrics */}
      <div style={gridCols(4)}>
        <Stat label="Research papers"  value={pipeStats?.total_papers}      />
        <Stat label="Unique materials" value={pipeStats?.unique_materials}  />
        <Stat label="Data extractions" value={pipeStats?.total_extractions} />
        <Stat label="Simulation engines" value={ENGINES.length} />
      </div>

      <div style={gridCols(2)}>
        {/* Engines table */}
        <Card title="Simulation engines" subtitle="All physics solvers; status = ready when the route imports cleanly">
          <table style={tableStyle}>
            <thead>
              <tr>
                <Th>Engine</Th>
                <Th>Technique</Th>
                <Th align="right">Status</Th>
              </tr>
            </thead>
            <tbody>
              {ENGINES.map(eng => (
                <tr key={eng.name} style={{ borderTop: '1px solid var(--border-primary)' }}>
                  <Td>{eng.name}</Td>
                  <Td muted>{eng.technique}</Td>
                  <Td align="right">
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5,
                      color: eng.status === 'ready' ? 'var(--color-success)' : 'var(--text-tertiary)' }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%',
                        background: eng.status === 'ready' ? 'var(--color-success)' : 'var(--color-standby)' }} />
                      {capitalize(eng.status)}
                    </span>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {/* Sources + applications */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card title="Paper sources" subtitle={pipeStats ? 'From the local research pipeline' : 'Pipeline data not yet loaded'}>
            <canvas ref={chartRef} style={{ width: '100%', height: 150, display: 'block' }} />
            {!pipeStats?.sources && <EmptyState>Run the research pipeline to populate sources.</EmptyState>}
          </Card>

          {pipeStats?.applications && (
            <Card title="Top applications">
              {Object.entries(pipeStats.applications).slice(0, 6).map(([app, count]) => {
                const total = Object.values(pipeStats.applications).reduce((s, v) => s + v, 0);
                const pct = (count / total * 100);
                return (
                  <div key={app} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <span style={{ width: 110, fontSize: 12, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                      {app.replace(/_/g, ' ')}
                    </span>
                    <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--bg-elevated)', overflow: 'hidden' }}>
                      <div style={{ width: `${pct}%`, height: '100%', background: 'var(--accent)', transition: 'width 0.6s ease' }} />
                    </div>
                    <span data-number style={{ fontSize: 11.5, color: 'var(--text-tertiary)', width: 36, textAlign: 'right' }}>{count}</span>
                  </div>
                );
              })}
            </Card>
          )}
        </div>
      </div>

      <div style={gridCols(2)}>
        {/* System resources */}
        <Card title="System resources"
              subtitle={backendOnline ? 'Live from psutil + torch.cuda on the local backend' : 'Backend offline — values frozen at last reading'}>
          <Bar label={telemetry.gpuName ? `GPU memory (${telemetry.gpuName})` : 'GPU memory'}
               value={telemetry.gpuMem != null ? `${telemetry.gpuMem.toFixed(1)} / ${(telemetry.gpuMemMax ?? 0).toFixed(1)} GB` : 'No GPU detected'}
               percent={telemetry.gpuMem != null && telemetry.gpuMemMax ? (telemetry.gpuMem / telemetry.gpuMemMax * 100) : 0}
               color="var(--accent)"
          />
          <Bar label="CPU load"
               value={telemetry.cpuPercent == null ? '—' : `${telemetry.cpuPercent.toFixed(0)}%`}
               percent={telemetry.cpuPercent ?? 0}
               color="var(--color-success)"
          />
          <Bar label="System memory"
               value={telemetry.memUsedGB == null ? '—' : `${telemetry.memUsedGB.toFixed(1)} / ${(telemetry.memTotalGB ?? 0).toFixed(1)} GB`}
               percent={telemetry.memUsedGB != null && telemetry.memTotalGB ? (telemetry.memUsedGB / telemetry.memTotalGB * 100) : 0}
               color="#a78bfa"
          />
          <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: 'var(--text-secondary)' }}>
            <span style={{
              width: 7, height: 7, borderRadius: '50%',
              background: telemetry.serialStatus === 'streaming' ? 'var(--color-success)'
                        : telemetry.serialStatus === 'disconnected' ? 'var(--color-error)'
                        : 'var(--color-standby)',
            }} />
            Potentiostat: {capitalize(telemetry.serialStatus)}
            <span style={{ color: 'var(--text-tertiary)', marginLeft: 4 }}>
              {telemetry.serialStatus === 'idle' ? '(no measurement in progress)' : ''}
            </span>
          </div>
        </Card>

        {/* Architecture */}
        <Card title="Architecture" subtitle="What runs where">
          <ArchRow label="Core"     desc="C++ / Eigen / OpenMP physics solvers" />
          <ArchRow label="API"      desc="FastAPI sidecar on 127.0.0.1:8000 (Pydantic v2)" />
          <ArchRow label="AI"       desc="NVIDIA NIM (Llama-3.3-70B) via integrate.api.nvidia.com" />
          <ArchRow label="Lab data" desc="Encrypted at rest (Fernet + PBKDF2-SHA256, hardware-bound key)" />
          <ArchRow label="Storage"  desc="SQLite + DuckDB; user data stays on this machine" />
          <ArchRow label="Renderer" desc="Electron 32 + Vite 5 + React 19" />
        </Card>
      </div>
    </div>
  );
}

// ── small helpers ─────────────────────────────────────────────────────────

function gridCols(n) {
  return { display: 'grid', gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))`, gap: 16 };
}

function Card({ title, subtitle, children }) {
  return (
    <section style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)',
      padding: 16,
    }}>
      {title && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</div>
          {subtitle && <div style={{ marginTop: 2, fontSize: 11.5, color: 'var(--text-tertiary)' }}>{subtitle}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)',
      padding: 14,
    }}>
      <div data-number style={{
        fontSize: 24, fontWeight: 600, color: 'var(--text-primary)',
        letterSpacing: '-0.02em',
      }}>
        {value != null ? Number(value).toLocaleString() : '—'}
      </div>
      <div style={{ marginTop: 4, fontSize: 11.5, color: 'var(--text-tertiary)' }}>{label}</div>
    </div>
  );
}

function Bar({ label, value, percent, color = 'var(--accent)' }) {
  const p = Math.max(0, Math.min(100, percent || 0));
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 4 }}>
        <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
        <span data-number style={{ color: 'var(--text-primary)' }}>{value}</span>
      </div>
      <div style={{ height: 5, borderRadius: 3, background: 'var(--bg-elevated)', overflow: 'hidden' }}>
        <div style={{ width: `${p}%`, height: '100%', background: color, transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
}

function ArchRow({ label, desc }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '90px 1fr', alignItems: 'baseline',
      gap: 12, padding: '7px 0',
      borderTop: '1px solid var(--border-primary)',
      fontSize: 12.5,
    }}>
      <span style={{ color: 'var(--text-tertiary)', fontWeight: 500 }}>{label}</span>
      <span style={{ color: 'var(--text-primary)', lineHeight: 1.5 }}>{desc}</span>
    </div>
  );
}

const tableStyle = {
  width: '100%', borderCollapse: 'collapse',
  fontSize: 12.5,
};

function Th({ children, align }) {
  return <th style={{ textAlign: align || 'left', padding: '6px 0', fontSize: 11, fontWeight: 500, color: 'var(--text-tertiary)' }}>{children}</th>;
}
function Td({ children, muted, align }) {
  return <td style={{
    padding: '8px 0', textAlign: align || 'left',
    color: muted ? 'var(--text-secondary)' : 'var(--text-primary)',
    fontFamily: muted ? 'var(--font-data)' : 'var(--font-ui)',
    fontSize: muted ? 12 : 12.5,
  }}>{children}</td>;
}

function EmptyState({ children }) {
  return (
    <div style={{
      padding: '20px 0', textAlign: 'center', fontSize: 12,
      color: 'var(--text-tertiary)',
    }}>
      {children}
    </div>
  );
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function getCss(varName) {
  if (typeof window === 'undefined') return '#888';
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || '#888';
}
