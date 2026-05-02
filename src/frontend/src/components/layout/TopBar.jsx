import React, { useState, useEffect } from 'react';
import { 
  Activity, Cpu, Database, ShieldCheck, 
  Settings, User, Bell, Search, 
  Terminal, Globe, Zap, ChevronRight
} from 'lucide-react';

export default function TopBar({ title, backendStatus }) {
  const [uptime, setUptime] = useState(0);
  const [load, setLoad] = useState(12);
  const [sessionHash] = useState(() => Math.random().toString(36).substring(2, 10).toUpperCase());

  useEffect(() => {
    const timer = setInterval(() => setUptime(prev => prev + 1), 1000);
    const loadTimer = setInterval(() => setLoad(Math.floor(Math.random() * 15) + 5), 3000);
    return () => {
      clearInterval(timer);
      clearInterval(loadTimer);
    };
  }, []);

  const formatTime = (s) => {
    const h = String(Math.floor(s / 3600)).padStart(2, '0');
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
    const sec = String(s % 60).padStart(2, '0');
    return `${h}:${m}:${sec}`;
  };

  const THEME = {
    cyan: '#00f2ff',
    bg: '#020204',
    text: '#a0a0a0',
    muted: 'rgba(255, 255, 255, 0.08)',
    fontMono: '"JetBrains Mono", monospace'
  };

  return (
    <div className="topbar" style={{
      height: '64px',
      background: 'rgba(2, 2, 4, 0.9)',
      backdropFilter: 'blur(16px) saturate(180%)',
      borderBottom: `1px solid ${THEME.muted}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
      position: 'relative',
      overflow: 'hidden',
      zIndex: 1000
    }}>
      {/* Scanline Overlay */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06))',
        backgroundSize: '100% 2px, 3px 100%',
        pointerEvents: 'none',
        zIndex: 10
      }} />
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '10%',
        background: `linear-gradient(to bottom, transparent, ${THEME.cyan}22, transparent)`,
        animation: 'scan 8s linear infinite',
        pointerEvents: 'none',
        zIndex: 11
      }} />

      {/* Instrumentation Border Bottom */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: '1px',
        background: `linear-gradient(90deg, transparent, ${THEME.cyan}, transparent)`,
        opacity: 0.5,
        boxShadow: `0 0 10px ${THEME.cyan}`
      }} />

      {/* Left: Branding & Breadcrumbs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '24px', zIndex: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ 
            width: '36px', 
            height: '36px', 
            background: 'rgba(0, 242, 255, 0.05)',
            border: `1px solid ${THEME.cyan}`,
            borderRadius: '2px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: `0 0 15px rgba(0, 242, 255, 0.2)`,
            position: 'relative'
          }}>
            <Zap size={20} color={THEME.cyan} fill={THEME.cyan} style={{ filter: `drop-shadow(0 0 5px ${THEME.cyan})` }} />
            {/* Corner Accents */}
            <div style={{ position: 'absolute', top: -1, left: -1, width: 4, height: 4, borderTop: `1px solid ${THEME.cyan}`, borderLeft: `1px solid ${THEME.cyan}` }} />
            <div style={{ position: 'absolute', bottom: -1, right: -1, width: 4, height: 4, borderBottom: `1px solid ${THEME.cyan}`, borderRight: `1px solid ${THEME.cyan}` }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ 
              fontSize: '15px', 
              fontWeight: '900', 
              letterSpacing: '2px', 
              color: '#fff',
              textTransform: 'uppercase',
              lineHeight: 1,
              textShadow: '0 0 10px rgba(255,255,255,0.3)'
            }}>
              RĀMAN STUDIO
            </span>
            <span style={{ fontSize: '9px', color: THEME.cyan, fontFamily: THEME.fontMono, marginTop: '2px', textShadow: `0 0 5px ${THEME.cyan}` }}>
              INDUSTRIAL_OS v2.0.4 // {sessionHash}
            </span>
          </div>
        </div>

        <div style={{ width: '1px', height: '32px', background: THEME.muted }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: THEME.text, fontFamily: THEME.fontMono }}>
          <Globe size={14} color={THEME.cyan} />
          <span style={{ opacity: 0.5 }}>ROOT_NODE</span>
          <ChevronRight size={10} style={{ opacity: 0.3 }} />
          <span style={{ color: '#fff', fontWeight: '600', textShadow: '0 0 8px rgba(255,255,255,0.2)' }}>{title.toUpperCase()}</span>
        </div>
      </div>

      {/* Middle: System Telemetry */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '32px',
        padding: '8px 24px',
        borderRadius: '2px',
        background: 'rgba(0, 0, 0, 0.6)',
        border: `1px solid ${THEME.muted}`,
        boxShadow: 'inset 0 0 20px rgba(0, 0, 0, 0.8)',
        position: 'relative',
        zIndex: 20
      }}>
        {/* Corner Accents for Telemetry */}
        <div style={{ position: 'absolute', top: -1, left: -1, width: 3, height: 3, borderTop: `1px solid ${THEME.cyan}`, borderLeft: `1px solid ${THEME.cyan}` }} />
        <div style={{ position: 'absolute', bottom: -1, right: -1, width: 3, height: 3, borderBottom: `1px solid ${THEME.cyan}`, borderRight: `1px solid ${THEME.cyan}` }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Cpu size={14} color={THEME.cyan} style={{ filter: `drop-shadow(0 0 5px ${THEME.cyan})` }} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '8px', color: THEME.text, textTransform: 'uppercase' }}>CPU_COMPUTE</span>
            <span style={{ fontSize: '11px', fontFamily: THEME.fontMono, color: '#fff' }}>{load}.00<span style={{ fontSize: '8px', opacity: 0.5 }}>%</span></span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Activity size={14} color={THEME.cyan} style={{ filter: `drop-shadow(0 0 5px ${THEME.cyan})` }} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '8px', color: THEME.text, textTransform: 'uppercase' }}>CORE_UPTIME</span>
            <span style={{ fontSize: '11px', fontFamily: THEME.fontMono, color: '#fff' }}>{formatTime(uptime)}</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Database size={14} color={THEME.cyan} style={{ filter: `drop-shadow(0 0 5px ${THEME.cyan})` }} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '8px', color: THEME.text, textTransform: 'uppercase' }}>PHYS_ENGINE</span>
            <span style={{ fontSize: '11px', fontFamily: THEME.fontMono, color: THEME.cyan }}>ACTIVE</span>
          </div>
        </div>
      </div>

      {/* Right: User & Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px', zIndex: 20 }}>
        <div style={{ 
          padding: '4px 12px', 
          borderRadius: '2px', 
          background: backendStatus === 'online' ? 'rgba(0, 242, 255, 0.1)' : 'rgba(255, 80, 80, 0.1)',
          border: `1px solid ${backendStatus === 'online' ? THEME.cyan : '#ff5050'}`,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          boxShadow: backendStatus === 'online' ? `0 0 10px rgba(0, 242, 255, 0.2)` : 'none'
        }}>
          <div className="pulse" style={{ 
            width: '6px', 
            height: '6px', 
            borderRadius: '50%', 
            background: backendStatus === 'online' ? THEME.cyan : '#ff5050',
            boxShadow: `0 0 8px ${backendStatus === 'online' ? THEME.cyan : '#ff5050'}`
          }} />
          <span style={{ 
            fontSize: '10px', 
            fontWeight: '900', 
            color: backendStatus === 'online' ? THEME.cyan : '#ff5050',
            fontFamily: THEME.fontMono
          }}>
            {backendStatus.toUpperCase()}
          </span>
        </div>

        <div style={{ width: '1px', height: '32px', background: THEME.muted }} />

        <div style={{ display: 'flex', gap: '8px' }}>
          <button style={{ background: 'none', border: 'none', color: THEME.text, cursor: 'pointer', padding: '6px', transition: 'color 0.2s' }} onMouseEnter={e => e.currentTarget.style.color = THEME.cyan} onMouseLeave={e => e.currentTarget.style.color = THEME.text}>
            <Bell size={18} />
          </button>
          <button style={{ background: 'none', border: 'none', color: THEME.text, cursor: 'pointer', padding: '6px', transition: 'color 0.2s' }} onMouseEnter={e => e.currentTarget.style.color = THEME.cyan} onMouseLeave={e => e.currentTarget.style.color = THEME.text}>
            <Settings size={18} />
          </button>
        </div>

        <div style={{ 
          width: '36px', 
          height: '36px', 
          borderRadius: '4px', 
          background: 'rgba(255,255,255,0.03)', 
          border: `1px solid ${THEME.muted}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          transition: 'all 0.2s ease'
        }}>
          <User size={20} color={THEME.text} />
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes scan {
          0% { top: -10%; opacity: 0; }
          50% { opacity: 0.5; }
          100% { top: 110%; opacity: 0; }
        }
        .pulse {
          animation: pulse-glow 2s infinite ease-in-out;
        }
        @keyframes pulse-glow {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.8); }
        }
      `}} />
    </div>
  );
}
