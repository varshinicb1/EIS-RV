import React, { useState, useEffect } from 'react';
import { 
  Wifi, Shield, Cpu, Activity, Clock, 
  Terminal, Globe, HardDrive, Zap, BarChart
} from 'lucide-react';

// Real backend latency — measure round-trip time of /health.
async function measureLatency() {
  try {
    const t0 = performance.now();
    const r = await fetch('http://127.0.0.1:8000/health', { cache: 'no-store' });
    if (!r.ok) return null;
    return Math.round(performance.now() - t0);
  } catch {
    return null;
  }
}

export default function StatusBar({ backendStatus, activePanel }) {
  // Latency is a real /health round-trip; null when the backend is offline.
  // FPS is a real requestAnimationFrame counter (no fakery there).
  const [latency, setLatency] = useState(null);
  const [fps, setFps] = useState(60);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const ms = await measureLatency();
      if (!cancelled) setLatency(ms);
    };
    tick();
    const latInterval = setInterval(tick, 5000);

    let lastTime = performance.now();
    let frameCount = 0;
    let fpsReq;
    const updateFps = () => {
      frameCount++;
      const time = performance.now();
      if (time >= lastTime + 1000) {
        setFps(frameCount);
        frameCount = 0;
        lastTime = time;
      }
      fpsReq = requestAnimationFrame(updateFps);
    };
    fpsReq = requestAnimationFrame(updateFps);

    return () => {
      cancelled = true;
      clearInterval(latInterval);
      cancelAnimationFrame(fpsReq);
    };
  }, []);

  const THEME = {
    cyan: '#00f2ff',
    bg: '#020204',
    text: '#a0a0a0',
    muted: 'rgba(255, 255, 255, 0.08)',
    success: '#00ff95'
  };

  const cornerBracketStyle = {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '4px 12px',
    border: `1px solid ${THEME.muted}`,
    background: 'rgba(0, 0, 0, 0.4)',
  };

  const bracketTL = { content: '""', position: 'absolute', top: -1, left: -1, width: 4, height: 4, borderTop: `1px solid ${THEME.cyan}`, borderLeft: `1px solid ${THEME.cyan}` };
  const bracketBR = { content: '""', position: 'absolute', bottom: -1, right: -1, width: 4, height: 4, borderBottom: `1px solid ${THEME.cyan}`, borderRight: `1px solid ${THEME.cyan}` };

  return (
    <div className="statusbar" style={{
      height: '32px',
      background: 'rgba(2, 2, 4, 0.98)',
      borderTop: `1px solid ${THEME.muted}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 12px',
      fontSize: '10px',
      color: THEME.text,
      fontFamily: '"JetBrains Mono", monospace',
      letterSpacing: '0.5px',
      position: 'relative',
      zIndex: 1000
    }}>
      <style dangerouslySetInnerHTML={{ __html: `
        .status-bracket::before { content: ""; position: absolute; top: -1px; left: -1px; width: 4px; height: 4px; border-top: 1px solid ${THEME.cyan}; border-left: 1px solid ${THEME.cyan}; }
        .status-bracket::after { content: ""; position: absolute; bottom: -1px; right: -1px; width: 4px; height: 4px; border-bottom: 1px solid ${THEME.cyan}; border-right: 1px solid ${THEME.cyan}; }
      `}} />

      {/* Left: System Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div className="status-bracket" style={cornerBracketStyle}>
          <Shield size={12} color={THEME.success} style={{ filter: `drop-shadow(0 0 4px ${THEME.success})` }} />
          <span style={{ color: THEME.success, fontWeight: '700' }}>SECURE_SESSION</span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', opacity: 0.8 }}>
          <Terminal size={12} color={THEME.cyan} />
          <span style={{ color: '#fff', fontWeight: '600' }}>{activePanel.toUpperCase()}</span>
          <span style={{ color: THEME.text }}>[MODULE_LOADED]</span>
        </div>
      </div>

      {/* Center: Environment Information */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '20px',
        opacity: 0.8
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Globe size={12} />
          <span>V-LAN // 127.0.0.1</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Cpu size={12} />
          <span>CUDA_CORE_v12.4</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <BarChart size={12} />
          <span>THREADS: 16/16</span>
        </div>
      </div>

      {/* Right: Telemetry */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div className="status-bracket" style={cornerBracketStyle}>
          <Activity size={12} color={fps > 55 ? THEME.success : '#ffcc00'} style={{ filter: fps > 55 ? `drop-shadow(0 0 4px ${THEME.success})` : 'none' }} />
          <span style={{ color: fps > 55 ? THEME.success : '#ffcc00' }}>{fps} <span style={{ opacity: 0.5 }}>RENDER_SYNC</span></span>
        </div>

        <div className="status-bracket" style={cornerBracketStyle}>
          <Zap size={12} color={THEME.cyan} style={{ filter: `drop-shadow(0 0 4px ${THEME.cyan})` }} />
          <span style={{ color: THEME.cyan }}>
            {latency === null ? '—' : `${latency}ms`}{' '}
            <span style={{ opacity: 0.5 }}>BACKEND_RTT</span>
          </span>
        </div>

        <div className="status-bracket" style={{
          ...cornerBracketStyle,
          background: backendStatus === 'connected' ? 'rgba(0, 242, 255, 0.1)' : 'rgba(255, 80, 80, 0.1)',
          borderColor: backendStatus === 'connected' ? 'rgba(0, 242, 255, 0.3)' : 'rgba(255, 80, 80, 0.3)',
        }}>
          <Wifi size={12} color={backendStatus === 'connected' ? THEME.cyan : '#ff5050'} style={{ filter: `drop-shadow(0 0 4px ${backendStatus === 'connected' ? THEME.cyan : '#ff5050'})` }} />
          <span style={{ 
            color: backendStatus === 'connected' ? THEME.cyan : '#ff5050',
            fontWeight: '900'
          }}>
            {backendStatus === 'connected' ? 'NODE_SYNC_ESTABLISHED' : 'NODE_SYNC_LOST'}
          </span>
        </div>
      </div>
    </div>
  );
}
