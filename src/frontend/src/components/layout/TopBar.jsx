import React from 'react';
import { Settings, HelpCircle } from 'lucide-react';

/**
 * TopBar — application-wide chrome.
 *
 *   [ Panel title    ]                                           [ License pill ] [ ⚙ ] [ ? ]
 *
 * No drag region (we run windowed-default), no scanline, no mono caps. The
 * title comes from the active panel's metadata. Status info that's repeated
 * elsewhere (sidebar status pill, status bar) is intentionally NOT mirrored
 * here — keeping each surface single-purpose.
 */
export default function TopBar({ title, licenseInfo }) {
  return (
    <header style={{
      height: 'var(--topbar-height)',
      flexShrink: 0,
      background: 'var(--bg-secondary)',
      borderBottom: '1px solid var(--border-primary)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 16px',
    }}>
      <div style={{
        fontSize: 14,
        fontWeight: 500,
        color: 'var(--text-primary)',
        letterSpacing: '-0.005em',
      }}>
        {title}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <LicensePill info={licenseInfo} />
        <IconBtn label="Help" onClick={() => window.open('https://github.com/varshinicb1/EIS-RV/blob/master/README.md', '_blank', 'noopener')}>
          <HelpCircle size={16} strokeWidth={1.75} />
        </IconBtn>
        <IconBtn label="Settings" onClick={() => window.dispatchEvent(new CustomEvent('NAVIGATE_PANEL', { detail: 'profile' }))}>
          <Settings size={16} strokeWidth={1.75} />
        </IconBtn>
      </div>
    </header>
  );
}

function LicensePill({ info }) {
  if (!info) return null;
  const status = info.status;
  const days = info.days_remaining ?? null;
  const plan = info.plan || 'unknown';

  let kind = 'neutral';
  let label = plan;
  if (status === 'ok' && plan && plan !== 'trial') {
    label = `${plan.charAt(0).toUpperCase() + plan.slice(1)} licence`;
    kind = 'ok';
  } else if (status === 'trial') {
    label = `Trial · ${days ?? '—'}d left`;
    kind = days != null && days <= 3 ? 'warning' : 'ok';
  } else if (status === 'trial_expired') {
    label = 'Trial expired';
    kind = 'error';
  } else if (status === 'expired') {
    label = 'Licence expired';
    kind = 'error';
  } else if (status === 'hardware_mismatch') {
    label = 'Hardware mismatch';
    kind = 'error';
  } else {
    label = 'Activate licence';
    kind = 'warning';
  }

  const colors = {
    ok:      { bg: 'rgba(52, 199, 89, 0.10)',  fg: 'var(--color-success)',  bd: 'rgba(52, 199, 89, 0.25)' },
    warning: { bg: 'rgba(255, 159, 10, 0.10)', fg: 'var(--color-warning)',  bd: 'rgba(255, 159, 10, 0.25)' },
    error:   { bg: 'rgba(255, 69, 58, 0.10)',  fg: 'var(--color-error)',    bd: 'rgba(255, 69, 58, 0.25)' },
    neutral: { bg: 'var(--bg-tertiary)',        fg: 'var(--text-secondary)', bd: 'var(--border-primary)' },
  }[kind];

  return (
    <button
      onClick={() => window.dispatchEvent(new CustomEvent('NAVIGATE_PANEL', { detail: 'profile' }))}
      title={info.message || `Plan: ${plan}`}
      style={{
        background: colors.bg,
        border: `1px solid ${colors.bd}`,
        color: colors.fg,
        borderRadius: 'var(--radius-sm)',
        padding: '4px 10px',
        fontSize: 11.5,
        fontWeight: 500,
        cursor: 'pointer',
        fontFamily: 'var(--font-ui)',
        transition: 'background var(--transition)',
      }}
    >
      {label}
    </button>
  );
}

function IconBtn({ children, onClick, label }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      style={{
        background: 'transparent',
        border: 'none',
        color: 'var(--text-tertiary)',
        padding: 6,
        borderRadius: 'var(--radius-sm)',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        transition: 'color var(--transition), background var(--transition)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.color = 'var(--text-primary)';
        e.currentTarget.style.background = 'var(--bg-hover)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.color = 'var(--text-tertiary)';
        e.currentTarget.style.background = 'transparent';
      }}
    >
      {children}
    </button>
  );
}
