import React, { useEffect, useState } from 'react';
import {
  LayoutDashboard, Atom, Microscope, BookOpen, Activity, Zap,
  Battery, Timer, BarChart2, Cpu, Database, ArrowUpToLine,
  FolderKanban, FileText, UserCircle, Calculator, CheckCircle2, Wand2,
  ChevronLeft, ChevronRight, Layers, FlaskConical,
} from 'lucide-react';
import Logo, { BrandMark } from '../brand/Logo';

/**
 * Sidebar — primary navigation.
 *
 * Design notes:
 *   - Sentence-case section labels ("Intelligence", not "INTELLIGENCE_OPS").
 *   - Real backend status pill at the bottom (Online / Reconnecting / Offline);
 *     no fake buffer-cache or memory meters.
 *   - Mark-only logo when collapsed.
 *   - Single accent color, no glows or scanlines.
 */

const ICONS = {
  dashboard: LayoutDashboard,
  alchemi: Atom,
  alchemist_canvas: Wand2,
  biosensor: Microscope,
  literature: BookOpen,
  eis: Activity,
  cv: Zap,
  battery: Battery,
  gcd: Timer,
  drt: BarChart2,
  circuit: Cpu,
  toolkit: Calculator,
  materials: Database,
  data: ArrowUpToLine,
  lab: FlaskConical,
  validation: CheckCircle2,
  workspace: FolderKanban,
  reports: FileText,
  profile: UserCircle,
};

const GROUPS = [
  { label: 'Intelligence',     keys: ['alchemist_canvas', 'alchemi', 'literature'] },
  { label: 'Analysis',         keys: ['dashboard', 'eis', 'cv', 'drt', 'circuit'] },
  { label: 'Applied systems',  keys: ['battery', 'biosensor', 'gcd'] },
  { label: 'Resources',        keys: ['lab', 'materials', 'data', 'workspace', 'reports', 'profile'] },
];

export default function Sidebar({ panels, active, onSelect, collapsed, onToggle, backendStatus = 'connecting' }) {
  const panelKeys = Object.keys(panels);

  return (
    <aside style={{
      width: collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)',
      height: '100vh',
      flexShrink: 0,
      background: 'var(--bg-secondary)',
      borderRight: '1px solid var(--border-primary)',
      display: 'flex',
      flexDirection: 'column',
      transition: 'width var(--transition)',
      userSelect: 'none',
    }}>
      {/* Header — logo */}
      <div style={{
        height: 'var(--topbar-height)',
        padding: collapsed ? '0 14px' : '0 16px',
        display: 'flex',
        alignItems: 'center',
        borderBottom: '1px solid var(--border-primary)',
        flexShrink: 0,
      }}>
        {collapsed
          ? <BrandMark size={22} />
          : <Logo size={20} />}
      </div>

      {/* Navigation */}
      <nav style={{
        flex: 1,
        overflowY: 'auto',
        padding: '12px 8px',
        scrollbarWidth: 'thin',
      }}>
        {GROUPS.map(group => {
          const items = group.keys.filter(k => panelKeys.includes(k));
          if (items.length === 0) return null;
          return (
            <div key={group.label} style={{ marginBottom: 18 }}>
              {!collapsed && (
                <div style={{
                  fontSize: 10.5,
                  fontWeight: 500,
                  color: 'var(--text-tertiary)',
                  padding: '4px 10px 6px',
                  letterSpacing: '0.02em',
                }}>
                  {group.label}
                </div>
              )}
              {items.map(key => {
                const isActive = active === key;
                const IconComponent = ICONS[key] || Layers;
                return (
                  <div
                    key={key}
                    onClick={() => onSelect(key)}
                    title={collapsed ? panels[key].label : ''}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: collapsed ? '7px 0' : '7px 10px',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer',
                      color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                      background: isActive ? 'var(--accent-muted)' : 'transparent',
                      border: '1px solid transparent',
                      borderColor: isActive ? 'var(--accent-border)' : 'transparent',
                      marginBottom: 1,
                      transition: 'background var(--transition), color var(--transition)',
                      justifyContent: collapsed ? 'center' : 'flex-start',
                    }}
                    onMouseEnter={e => {
                      if (!isActive) e.currentTarget.style.background = 'var(--bg-hover)';
                    }}
                    onMouseLeave={e => {
                      if (!isActive) e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <IconComponent size={15} strokeWidth={1.75}
                      style={{ color: isActive ? 'var(--accent)' : 'currentColor', flexShrink: 0 }} />
                    {!collapsed && (
                      <span style={{
                        fontSize: 12.5,
                        fontWeight: isActive ? 500 : 400,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}>
                        {panels[key].label}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* Footer — backend status + collapse toggle */}
      <div style={{
        padding: collapsed ? '10px 8px' : '10px 12px',
        borderTop: '1px solid var(--border-primary)',
        flexShrink: 0,
      }}>
        {!collapsed && (
          <BackendStatusPill status={backendStatus} />
        )}
        <button
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            width: '100%',
            marginTop: collapsed ? 0 : 8,
            background: 'transparent',
            border: '1px solid var(--border-primary)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-tertiary)',
            cursor: 'pointer',
            padding: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'color var(--transition), border-color var(--transition)',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.color = 'var(--text-primary)';
            e.currentTarget.style.borderColor = 'var(--border-secondary)';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.color = 'var(--text-tertiary)';
            e.currentTarget.style.borderColor = 'var(--border-primary)';
          }}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>
    </aside>
  );
}

function BackendStatusPill({ status }) {
  // Status comes from App's periodic /api/health probe. We keep the
  // visualisation calm: a small dot + a label, no animation other than a
  // subtle pulse on "reconnecting".
  const map = {
    connected:    { color: 'var(--color-success)', label: 'Online',         desc: 'Backend reachable on 127.0.0.1:8000' },
    connecting:   { color: 'var(--color-warning)', label: 'Connecting…',    desc: 'Probing local backend' },
    disconnected: { color: 'var(--color-error)',   label: 'Offline',        desc: 'Backend not responding — retrying' },
  };
  const cfg = map[status] || map.connecting;

  return (
    <div title={cfg.desc} style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 10px',
      borderRadius: 'var(--radius-sm)',
      background: 'var(--bg-tertiary)',
      border: '1px solid var(--border-primary)',
      fontSize: 11,
      color: 'var(--text-secondary)',
    }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%',
        background: cfg.color,
        flexShrink: 0,
        animation: status === 'connecting' ? 'raman-pulse 1.4s ease-in-out infinite' : 'none',
      }} />
      <span style={{ flex: 1 }}>{cfg.label}</span>
    </div>
  );
}
