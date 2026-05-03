import React, { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../../hooks/useTheme';

// Backend endpoints. The desktop app spawns the FastAPI sidecar on :8000.
const API = 'http://127.0.0.1:8000';

const DEFAULT_PROFILE = {
  name: '',
  email: '',
  organization: '',
  role: '',
  department: '',
  orcid: '',
};

// What the /api/v2/auth/license endpoint returns. Source of truth.
const EMPTY_LICENSE = {
  status: 'unknown',
  plan: 'unknown',
  sub: null,
  expires_at: null,
  days_remaining: null,
  features: [],
  hardware: null,
  degraded_hardware: false,
  message: '',
};

const STATUS_LABEL = {
  ok: 'Licensed',
  trial: 'Trial',
  trial_expired: 'Trial expired',
  expired: 'License expired',
  invalid: 'Invalid license',
  hardware_mismatch: 'License bound to a different machine',
  not_activated: 'Not activated',
  unknown: 'Loading…',
};

function colorForStatus(status) {
  switch (status) {
    case 'ok':
      return 'var(--color-success)';
    case 'trial':
      return 'var(--color-success)';
    default:
      return '#f87171';
  }
}

export default function UserProfilePanel() {
  const { theme, setTheme, themes } = useTheme();

  const [profile, setProfile] = useState(DEFAULT_PROFILE);
  const [savedToast, setSavedToast] = useState(false);
  const [notifications, setNotifications] = useState({
    emailDigest: true,
    simulationComplete: true,
    systemAlerts: true,
    weeklyReport: false,
  });

  // ---- License state (from backend) ----
  const [license, setLicense] = useState(EMPTY_LICENSE);
  const [licenseError, setLicenseError] = useState('');
  const [licenseInput, setLicenseInput] = useState('');
  const [activating, setActivating] = useState(false);
  const [activateError, setActivateError] = useState('');
  const [hwIdCopied, setHwIdCopied] = useState(false);

  const refreshLicense = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/v2/auth/license`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setLicense({ ...EMPTY_LICENSE, ...data });
      setLicenseError('');
    } catch (e) {
      setLicenseError(`Could not reach the local backend at ${API}: ${e.message}`);
    }
  }, []);

  useEffect(() => {
    // Local profile + notifications.
    try {
      const sp = localStorage.getItem('raman-profile');
      if (sp) {
        const parsed = JSON.parse(sp);
        if (parsed && typeof parsed === 'object') {
          setProfile({ ...DEFAULT_PROFILE, ...parsed });
        }
      }
    } catch {
      try { localStorage.removeItem('raman-profile'); } catch {}
    }
    refreshLicense();
  }, [refreshLicense]);

  const handleSave = useCallback(() => {
    try { localStorage.setItem('raman-profile', JSON.stringify(profile)); } catch {}
    setSavedToast(true);
    setTimeout(() => setSavedToast(false), 1500);
  }, [profile]);

  const updateField = (f, v) => setProfile(p => ({ ...p, [f]: v }));

  const handleActivate = useCallback(async () => {
    const token = licenseInput.trim();
    if (!token) {
      setActivateError('Paste a license token first.');
      return;
    }
    setActivating(true);
    setActivateError('');
    try {
      const r = await fetch(`${API}/api/v2/auth/license/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        const detail = data?.detail;
        const msg = typeof detail === 'string'
          ? detail
          : detail?.message || `HTTP ${r.status}`;
        setActivateError(msg);
      } else {
        setLicenseInput('');
        await refreshLicense();
      }
    } catch (e) {
      setActivateError(`Network error: ${e.message}`);
    } finally {
      setActivating(false);
    }
  }, [licenseInput, refreshLicense]);

  const handleDeactivate = useCallback(async () => {
    if (!window.confirm(
      "Deactivate this license? You'll be able to activate it again on this machine, "
      + "or move it to another machine by issuing a new token bound to that hardware id."
    )) return;
    try {
      await fetch(`${API}/api/v2/auth/license/deactivate`, { method: 'POST' });
      await refreshLicense();
    } catch (e) {
      setActivateError(`Network error: ${e.message}`);
    }
  }, [refreshLicense]);

  const copyHardwareId = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/v2/auth/hardware-id`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      await navigator.clipboard.writeText(data.hardware_id);
      setHwIdCopied(true);
      setTimeout(() => setHwIdCopied(false), 1500);
    } catch (e) {
      setActivateError(`Could not read hardware id: ${e.message}`);
    }
  }, []);

  const sty = {
    section: { background: 'var(--bg-elevated)', borderRadius: 8, border: '1px solid var(--border-primary)', marginBottom: 12, padding: 16 },
    row: { display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid var(--border-primary)' },
    lbl: { width: 120, fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)', flexShrink: 0 },
    chip: (color) => ({ padding: '3px 8px', borderRadius: 4, fontSize: 9, fontWeight: 600, background: `${color}1F`, color, border: `1px solid ${color}55` }),
  };

  const initials = profile.name
    ? profile.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : '–';

  const statusColor = colorForStatus(license.status);
  const statusLabel = license.days_remaining != null && license.status === 'trial'
    ? `Trial — ${license.days_remaining} day${license.days_remaining === 1 ? '' : 's'} left`
    : license.days_remaining != null && license.status === 'ok'
      ? `${license.plan} — ${license.days_remaining} day${license.days_remaining === 1 ? '' : 's'}`
      : STATUS_LABEL[license.status] || license.status;

  const isLicensed = license.status === 'ok';
  const isTrial    = license.status === 'trial';

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, height: '100%', overflow: 'auto', padding: 2 }} className="animate-in">
      {/* ──────────── LEFT COLUMN ──────────── */}
      <div>
        {/* Avatar + identity */}
        <div style={{ ...sty.section, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: 14, background: 'linear-gradient(135deg, var(--accent), #76b900)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 700, color: '#000' }}>
            {initials}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
              {profile.name || 'Set your name below'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              {profile.role || 'Researcher'}{profile.organization ? ` · ${profile.organization}` : ''}
            </div>
          </div>
          <span style={sty.chip(statusColor)}>{statusLabel}</span>
        </div>

        {/* Personal info */}
        <div style={sty.section}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>Personal information</div>
          {[
            ['name', 'Full name'],
            ['email', 'Email'],
            ['organization', 'Organization'],
            ['role', 'Role'],
            ['department', 'Department'],
            ['orcid', 'ORCID'],
          ].map(([k, l]) => (
            <div key={k} style={sty.row}>
              <span style={sty.lbl}>{l}</span>
              <input
                className="input-field"
                value={profile[k]}
                onChange={e => updateField(k, e.target.value)}
                style={{ flex: 1, fontSize: 12 }}
                placeholder={l}
              />
            </div>
          ))}
        </div>

        {/* Notifications */}
        <div style={sty.section}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>Notifications</div>
          {Object.entries(notifications).map(([k, v]) => (
            <div key={k} style={{ ...sty.row, cursor: 'pointer' }} onClick={() => setNotifications(n => ({ ...n, [k]: !v }))}>
              <span style={{ flex: 1, fontSize: 11, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{k.replace(/([A-Z])/g, ' $1')}</span>
              <div style={{ width: 32, height: 16, borderRadius: 8, padding: 2, background: v ? 'var(--accent)' : 'var(--bg-primary)', border: `1px solid ${v ? 'transparent' : 'var(--border-secondary)'}`, transition: 'all 0.2s' }}>
                <div style={{ width: 12, height: 12, borderRadius: 6, background: v ? '#000' : 'var(--text-tertiary)', transform: v ? 'translateX(14px)' : 'translateX(0)', transition: 'transform 0.2s' }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ──────────── RIGHT COLUMN ──────────── */}
      <div>
        {/* License — backend-driven */}
        <div style={sty.section}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>License</div>

          {licenseError && (
            <div style={{
              padding: 10, marginBottom: 10, borderRadius: 6,
              background: '#7f1d1d33', border: '1px solid #7f1d1d',
              fontSize: 11, color: '#fca5a5',
            }}>
              {licenseError}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
            <div style={{ background: 'var(--bg-primary)', borderRadius: 6, padding: 10, border: '1px solid var(--border-primary)' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: statusColor, textTransform: 'capitalize' }}>
                {license.plan || '—'}
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>Plan</div>
            </div>
            <div style={{ background: 'var(--bg-primary)', borderRadius: 6, padding: 10, border: '1px solid var(--border-primary)' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent)' }}>
                {license.days_remaining ?? '—'}
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>Days remaining</div>
            </div>
          </div>

          <div style={sty.row}>
            <span style={sty.lbl}>Status</span>
            <span style={{ fontSize: 11, color: statusColor, fontFamily: 'var(--font-data)' }}>
              {STATUS_LABEL[license.status] || license.status}
            </span>
          </div>
          {license.sub && (
            <div style={sty.row}>
              <span style={sty.lbl}>Subscriber</span>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-data)' }}>
                {license.sub}
              </span>
            </div>
          )}
          {license.expires_at && (
            <div style={sty.row}>
              <span style={sty.lbl}>Expires</span>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-data)' }}>
                {new Date(license.expires_at * 1000).toISOString().slice(0, 10)}
              </span>
            </div>
          )}
          <div style={sty.row}>
            <span style={sty.lbl}>Hardware id</span>
            <span style={{ flex: 1, fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-data)' }}>
              {license.hardware || '…'}
              {license.degraded_hardware && (
                <span style={{ marginLeft: 8, ...sty.chip('#f59e0b'), display: 'inline-block' }}>degraded</span>
              )}
            </span>
            <button
              className="btn btn-sm"
              onClick={copyHardwareId}
              style={{ fontSize: 10, padding: '4px 8px' }}
              title="Copy the full hardware id (paste into the license server when issuing a token)"
            >
              {hwIdCopied ? '✓ Copied' : 'Copy id'}
            </button>
          </div>

          {/* Features list */}
          {license.features?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ ...sty.lbl, marginBottom: 6 }}>Features</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {license.features.map(f => (
                  <span key={f} style={sty.chip('var(--accent)')}>{f}</span>
                ))}
              </div>
            </div>
          )}

          {/* Activation form */}
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px dashed var(--border-secondary)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8, lineHeight: 1.5 }}>
              {isLicensed
                ? 'Replace the active license by pasting a new token below.'
                : isTrial
                  ? 'You\'re on a 30-day trial — no card needed. Paste a license token below to activate.'
                  : 'Trial expired or license invalid. Paste a license token below to activate.'}
            </div>
            <textarea
              className="input-field"
              value={licenseInput}
              onChange={e => setLicenseInput(e.target.value)}
              placeholder="RMNS1.eyJhbGc...."
              spellCheck={false}
              rows={3}
              style={{
                width: '100%', fontSize: 10, fontFamily: 'var(--font-data)',
                resize: 'vertical', minHeight: 60,
              }}
            />
            {activateError && (
              <div style={{ fontSize: 11, color: '#f87171', marginTop: 6 }}>
                {activateError}
              </div>
            )}
            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <button
                className="btn btn-sm btn-primary"
                onClick={handleActivate}
                disabled={activating || !licenseInput.trim()}
                style={{ flex: 1, fontSize: 11 }}
              >
                {activating ? 'Verifying…' : 'Activate'}
              </button>
              {isLicensed && (
                <button
                  className="btn btn-sm"
                  onClick={handleDeactivate}
                  style={{ fontSize: 11 }}
                >
                  Deactivate
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Theme */}
        <div style={sty.section}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>Theme</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
            {Object.entries(themes).map(([id, t]) => (
              <button key={id} onClick={() => setTheme(id)} style={{ background: theme === id ? 'var(--accent-muted)' : 'var(--bg-primary)', border: `2px solid ${theme === id ? 'var(--accent)' : 'var(--border-primary)'}`, borderRadius: 6, padding: 8, cursor: 'pointer', textAlign: 'center', transition: 'all 0.2s' }}>
                <div style={{ display: 'flex', justifyContent: 'center', gap: 3, marginBottom: 4 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: t.vars['--bg-primary'], border: '1px solid #444' }} />
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: t.vars['--accent'] }} />
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: t.vars['--text-primary'], border: '1px solid #444' }} />
                </div>
                <div style={{ fontSize: 9, fontWeight: 600, color: theme === id ? 'var(--accent)' : 'var(--text-primary)' }}>{t.label}</div>
              </button>
            ))}
          </div>
        </div>

        <button className="btn btn-primary" onClick={handleSave} style={{ width: '100%', marginTop: 8, background: savedToast ? 'var(--color-success)' : 'linear-gradient(135deg, var(--accent), #76b900)', transition: 'all 0.3s' }}>
          {savedToast ? '✓ Saved' : 'Save profile'}
        </button>
      </div>
    </div>
  );
}
