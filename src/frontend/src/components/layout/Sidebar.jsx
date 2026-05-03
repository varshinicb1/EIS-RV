import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard, Atom, Microscope, BookOpen, Activity, Zap,
  Battery, Timer, BarChart2, Cpu, Database, ArrowUpToLine,
  FolderKanban, FileText, UserCircle, Circle, Calculator, CheckCircle2, Wand2,
  ChevronLeft, ChevronRight, Hash, Layers, FlaskConical
} from 'lucide-react';
import logo from '../../assets/logo.png';

const ICONS = {
  dashboard: <LayoutDashboard size={18} />,
  alchemi: <Atom size={18} />,
  alchemist_canvas: <Wand2 size={18} />,
  biosensor: <Microscope size={18} />,
  literature: <BookOpen size={18} />,
  eis: <Activity size={18} />,
  cv: <Zap size={18} />,
  battery: <Battery size={18} />,
  gcd: <Timer size={18} />,
  drt: <BarChart2 size={18} />,
  circuit: <Cpu size={18} />,
  toolkit: <Calculator size={18} />,
  materials: <Database size={18} />,
  data: <ArrowUpToLine size={18} />,
  lab: <FlaskConical size={18} />,
  validation: <CheckCircle2 size={18} />,
  workspace: <FolderKanban size={18} />,
  reports: <FileText size={18} />,
  profile: <UserCircle size={18} />,
};

const GROUPS = [
  { label: 'INTELLIGENCE_OPS', tour: 'ai-research', keys: ['alchemist_canvas', 'alchemi', 'literature'] },
  { label: 'ANALYSIS_CORE', tour: 'simulation', keys: ['dashboard', 'eis', 'cv', 'drt', 'circuit'] },
  { label: 'APPLIED_SYSTEMS', tour: 'apps', keys: ['battery', 'biosensor', 'gcd'] },
  { label: 'RESOURCE_MGMT', tour: 'management', keys: ['lab', 'materials', 'data', 'workspace', 'reports', 'profile'] },
];

export default function Sidebar({ panels, active, onSelect, collapsed, onToggle }) {
  const panelKeys = Object.keys(panels);

  const THEME = {
    cyan: '#00f2ff',
    bg: '#020204',
    text: '#808080',
    activeText: '#ffffff',
    muted: 'rgba(255, 255, 255, 0.05)',
    fontMono: '"JetBrains Mono", monospace'
  };

  const [metrics, setMetrics] = useState({ buffer_cache_percent: 42.18, memory_used_percent: 50.0 });

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/system/metrics');
        if (res.ok) {
          const data = await res.json();
          if (data && typeof data.buffer_cache_percent === 'number') {
            setMetrics(data);
          }
        }
      } catch (err) {
        // Silently fail if endpoint isn't available yet
      }
    };
    
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`} style={{
      background: 'rgba(2, 2, 4, 0.98)',
      backdropFilter: 'blur(24px) saturate(160%)',
      borderRight: `1px solid ${THEME.muted}`,
      transition: 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
      display: 'flex',
      flexDirection: 'column',
      width: collapsed ? '68px' : '280px',
      zIndex: 1001,
      position: 'relative'
    }}>
      {/* Sidebar Header */}
      <div className="sidebar-header" style={{
        padding: '24px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        borderBottom: `1px solid ${THEME.muted}`
      }}>
        <div style={{
          width: '36px',
          height: '36px',
          background: THEME.bg,
          border: `1px solid ${THEME.cyan}`,
          borderRadius: '4px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          boxShadow: `0 0 15px rgba(0, 242, 255, 0.1)`,
          position: 'relative'
        }}>
          <Zap size={20} color={THEME.cyan} fill={THEME.cyan} style={{ filter: `drop-shadow(0 0 5px ${THEME.cyan})` }} />
          <div style={{ position: 'absolute', top: -1, left: -1, width: 3, height: 3, borderTop: `1px solid ${THEME.cyan}`, borderLeft: `1px solid ${THEME.cyan}` }} />
          <div style={{ position: 'absolute', bottom: -1, right: -1, width: 3, height: 3, borderBottom: `1px solid ${THEME.cyan}`, borderRight: `1px solid ${THEME.cyan}` }} />
        </div>
        {!collapsed && (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ 
              fontSize: '14px', 
              fontWeight: '900', 
              color: '#fff', 
              letterSpacing: '2px',
              textTransform: 'uppercase',
              lineHeight: 1
            }}>
              RĀMAN STUDIO
            </span>
            <span style={{ fontSize: '9px', color: THEME.cyan, fontFamily: THEME.fontMono, marginTop: '4px' }}>
              INSTRUMENTATION_OPS
            </span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav" style={{ 
        flex: 1, 
        overflowY: 'auto', 
        padding: '20px 10px',
        scrollbarWidth: 'none'
      }}>
        {GROUPS.map(group => {
          const groupItems = group.keys.filter(k => panelKeys.includes(k));
          if (!groupItems.length) return null;
          return (
            <div key={group.label} style={{ marginBottom: '28px' }}>
              {!collapsed && (
                <div style={{
                  fontSize: '9px', 
                  fontWeight: '800', 
                  color: 'rgba(255, 255, 255, 0.15)',
                  padding: '0 12px 12px', 
                  letterSpacing: '2px', 
                  textTransform: 'uppercase',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontFamily: THEME.fontMono
                }}>
                  <span style={{ color: THEME.cyan, opacity: 0.5 }}>#</span> {group.label}
                  <div style={{ flex: 1, height: '1px', background: 'rgba(255, 255, 255, 0.05)' }} />
                </div>
              )}
              {groupItems.map(key => (
                <div
                  key={key}
                  className={`sidebar-item ${active === key ? 'active' : ''}`}
                  onClick={() => onSelect(key)}
                  title={panels[key].label}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '12px 14px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    color: active === key ? THEME.cyan : THEME.text,
                    background: active === key ? 'rgba(0, 242, 255, 0.04)' : 'transparent',
                    border: `1px solid ${active === key ? 'rgba(0, 242, 255, 0.1)' : 'transparent'}`,
                    marginBottom: '4px',
                    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    position: 'relative'
                  }}
                >
                  {active === key && (
                    <div style={{
                      position: 'absolute',
                      right: '0',
                      top: '20%',
                      height: '60%',
                      width: '2px',
                      background: THEME.cyan,
                      borderRadius: '4px 0 0 4px',
                      boxShadow: `0 0 10px ${THEME.cyan}`
                    }} />
                  )}
                  <span style={{ 
                    display: 'flex', 
                    alignItems: 'center',
                    flexShrink: 0,
                    color: active === key ? THEME.cyan : THEME.text,
                    filter: active === key ? `drop-shadow(0 0 5px ${THEME.cyan}44)` : 'none'
                  }}>
                    {ICONS[key] || <Circle size={18} />}
                  </span>
                  {!collapsed && (
                    <span style={{ 
                      fontSize: '13px', 
                      fontWeight: active === key ? '800' : '500',
                      whiteSpace: 'nowrap',
                      letterSpacing: active === key ? '0.5px' : '0'
                    }}>
                      {panels[key].label.toUpperCase()}
                    </span>
                  )}
                </div>
              ))}
            </div>
          );
        })}
      </nav>

      {/* Sidebar Footer */}
      <div className="sidebar-footer" style={{
        padding: '20px',
        borderTop: `1px solid ${THEME.muted}`,
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        background: 'rgba(0,0,0,0.2)'
      }}>
        {!collapsed && (
          <div style={{
            background: 'rgba(255, 255, 255, 0.02)',
            borderRadius: '4px',
            padding: '12px',
            border: `1px solid ${THEME.muted}`,
            fontFamily: THEME.fontMono
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '8px', color: '#606060' }}>BUFFER_CACHE</span>
              <span style={{ fontSize: '9px', color: THEME.cyan }}>{metrics.buffer_cache_percent.toFixed(2)}%</span>
            </div>
            <div style={{ width: '100%', height: '2px', background: '#111', borderRadius: '1px', overflow: 'hidden' }}>
              <div style={{ width: `${metrics.buffer_cache_percent}%`, height: '100%', background: THEME.cyan, boxShadow: `0 0 10px ${THEME.cyan}`, transition: 'width 1s ease-in-out' }} />
            </div>
          </div>
        )}

        <button 
          onClick={onToggle} 
          style={{
            width: '100%',
            background: 'transparent',
            border: `1px solid ${THEME.muted}`,
            borderRadius: '4px',
            padding: '10px',
            color: '#606060',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.3s ease'
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = THEME.cyan;
            e.currentTarget.style.color = THEME.cyan;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = THEME.muted;
            e.currentTarget.style.color = '#606060';
          }}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>
    </aside>
  );
}
