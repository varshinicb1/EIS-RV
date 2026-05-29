import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, Trash2, KeyRound, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import useTheme, { THEMES } from '../../hooks/useTheme';

/**
 * Profile + Settings panel.
 *
 *  - Personal info (name, org, role, ...) → localStorage
 *  - Profile picture upload → localStorage as data URL (cap 256 KB)
 *  - License (live from /api/v2/auth/license, activate/deactivate flow)
 *  - NVIDIA NIM API key (validate live, save via /api/v2/settings/nvidia-key)
 *  - Theme picker (light / dark / high-contrast)
 *  - Notification preferences (local)
 */

const API = 'http://127.0.0.1:8000';

const DEFAULT_PROFILE = {
  name: '',
  email: '',
  organization: '',
  role: '',
  department: '',
  orcid: '',
  avatar: '',           // data URL
};

const EMPTY_LICENSE = {
  status: 'unknown', plan: 'unknown', sub: null, expires_at: null,
  days_remaining: null, features: [], hardware: null, degraded_hardware: false, message: '',
};

const STATUS_LABEL = {
  ok: 'Licensed', trial: 'Trial', trial_expired: 'Trial expired',
  expired: 'License expired', invalid: 'Invalid license',
  hardware_mismatch: 'Bound to a different machine',
  not_activated: 'Not activated', unknown: 'Loading…',
};

function colorForStatus(status) {
  if (status === 'ok' || status === 'trial') return 'var(--color-success)';
  if (status === 'trial_expired' || status === 'expired') return 'var(--color-warning)';
  return 'var(--color-error)';
}

const MAX_AVATAR_BYTES = 256 * 1024;   // 256 KB → fits comfortably in localStorage

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

  // ── License ───────────────────────────────────────────────────
  const [license, setLicense] = useState(EMPTY_LICENSE);
  const [licenseError, setLicenseError] = useState('');
  const [licenseInput, setLicenseInput] = useState('');
  const [activating, setActivating] = useState(false);
  const [activateError, setActivateError] = useState('');
  const [hwIdCopied, setHwIdCopied] = useState(false);

  // ── NVIDIA API key ────────────────────────────────────────────
  const [keyStatus, setKeyStatus] = useState({ configured: false, tail: null });
  const [keyInput, setKeyInput] = useState('');
  const [validateState, setValidateState] = useState({ kind: 'idle' });   // idle | working | ok | bad
  const [savingKey, setSavingKey] = useState(false);
  const fileInputRef = useRef(null);

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

  const refreshKeyStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/v2/settings/nvidia-key/status`);
      if (r.ok) setKeyStatus(await r.json());
    } catch { /* offline */ }
  }, []);

  useEffect(() => {
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
    refreshKeyStatus();
  }, [refreshLicense, refreshKeyStatus]);

  const handleSave = useCallback(() => {
    try { localStorage.setItem('raman-profile', JSON.stringify(profile)); } catch {}
    setSavedToast(true);
    setTimeout(() => setSavedToast(false), 1500);
  }, [profile]);

  const updateField = (f, v) => setProfile(p => ({ ...p, [f]: v }));

  // ── Avatar upload ─────────────────────────────────────────────
  const onPickAvatar = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!/^image\//.test(file.type)) {
      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
        detail: { kind: 'err', text: 'Pick an image file (jpg, png, webp).' },
      }));
      return;
    }
    if (file.size > MAX_AVATAR_BYTES * 4) {
      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
        detail: { kind: 'err', text: 'Pick a smaller image (under ~1 MB; we resize to 256 KB).' },
      }));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => downscaleToDataUrl(reader.result, 192).then(url => {
      updateField('avatar', url);
    });
    reader.readAsDataURL(file);
  };

  const clearAvatar = () => updateField('avatar', '');

  // ── License activate / deactivate ────────────────────────────
  const handleActivate = useCallback(async () => {
    const token = licenseInput.trim();
    if (!token) { setActivateError('Paste a license token first.'); return; }
    setActivating(true);
    setActivateError('');
    try {
      const r = await fetch(`${API}/api/v2/auth/license/activate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        const detail = data?.detail;
        const msg = typeof detail === 'string' ? detail : detail?.message || `HTTP ${r.status}`;
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
    if (!window.confirm("Deactivate this license?")) return;
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

  // ── NVIDIA key validation + save ─────────────────────────────
  const validateKey = useCallback(async () => {
    const key = keyInput.trim();
    if (!key) { setValidateState({ kind: 'bad', error: 'Paste a key first.' }); return; }
    if (!key.startsWith('nvapi-')) {
      setValidateState({ kind: 'bad', error: 'NVIDIA keys start with "nvapi-".' });
      return;
    }
    setValidateState({ kind: 'working' });
    try {
      const r = await fetch(`${API}/api/v2/settings/validate-nvidia-key`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key }),
      });
      const data = await r.json();
      if (data.valid) {
        setValidateState({ kind: 'ok', model: data.model, latency: data.latency_s });
      } else {
        setValidateState({ kind: 'bad', error: data.error || 'Key was rejected by NVIDIA.' });
      }
    } catch (e) {
      setValidateState({ kind: 'bad', error: `Network error: ${e.message}` });
    }
  }, [keyInput]);

  const saveKey = useCallback(async (clear = false) => {
    setSavingKey(true);
    try {
      const r = await fetch(`${API}/api/v2/settings/nvidia-key`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(clear ? { clear: true } : { api_key: keyInput.trim() }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
        detail: { kind: 'ok', text: clear ? 'NVIDIA key removed.' : 'NVIDIA key saved. AI features active.' },
      }));
      setKeyInput('');
      setValidateState({ kind: 'idle' });
      await refreshKeyStatus();
    } catch (e) {
      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
        detail: { kind: 'err', text: `Could not save key: ${e.message}` },
      }));
    } finally {
      setSavingKey(false);
    }
  }, [keyInput, refreshKeyStatus]);

  // ── Style tokens ─────────────────────────────────────────────
  const sty = {
    section: {
      background: 'var(--bg-elevated)',
      borderRadius: 'var(--radius-md)',
      border: '1px solid var(--border-primary)',
      marginBottom: 14, padding: 16,
      boxShadow: 'var(--shadow-sm)',
    },
    sectionTitle: { fontSize: 13.5, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 },
    row: {
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '8px 0', borderBottom: '1px solid var(--border-primary)',
    },
    lbl: { width: 120, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', flexShrink: 0 },
    chip: (color) => ({
      padding: '3px 8px', borderRadius: 99, fontSize: 10.5, fontWeight: 500,
      background: `${color}1A`, color, border: `1px solid ${color}55`,
    }),
  };

  const initials = profile.name
    ? profile.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : '–';

  const statusColor = colorForStatus(license.status);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, height: '100%', overflow: 'auto', padding: 2 }} className="animate-in">

      {/* ─── LEFT COLUMN ───────────────────────────────────── */}
      <div>

        {/* Identity + avatar */}
        <div style={{ ...sty.section, display: 'flex', alignItems: 'center', gap: 16 }}>
          <Avatar src={profile.avatar} initials={initials} onPick={() => fileInputRef.current?.click()} onClear={clearAvatar} />
          <input ref={fileInputRef} type="file" accept="image/*" onChange={onPickAvatar} style={{ display: 'none' }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {profile.name || 'Set your name below'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
              {profile.role || 'Researcher'}{profile.organization ? ` · ${profile.organization}` : ''}
            </div>
          </div>
          <span style={sty.chip(statusColor)}>
            {license.days_remaining != null && license.status === 'trial'
              ? `Trial · ${license.days_remaining}d`
              : STATUS_LABEL[license.status] || license.status}
          </span>
        </div>

        {/* Personal info */}
        <div style={sty.section}>
          <div style={sty.sectionTitle}>Personal information</div>
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
                value={profile[k]}
                onChange={e => updateField(k, e.target.value)}
                placeholder={l}
                style={inputStyle}
              />
            </div>
          ))}
          <button onClick={handleSave} style={{ ...primaryBtn, marginTop: 10, width: '100%' }}>
            {savedToast ? '✓ Saved' : 'Save profile'}
          </button>
        </div>

        {/* Notifications */}
        <div style={sty.section}>
          <div style={sty.sectionTitle}>Notifications</div>
          {Object.entries(notifications).map(([k, v]) => (
            <div key={k} style={{ ...sty.row, cursor: 'pointer' }} onClick={() => setNotifications(n => ({ ...n, [k]: !v }))}>
              <span style={{ flex: 1, fontSize: 12, color: 'var(--text-secondary)' }}>
                {labelize(k)}
              </span>
              <Switch on={v} />
            </div>
          ))}
        </div>
      </div>

      {/* ─── RIGHT COLUMN ──────────────────────────────────── */}
      <div>

        {/* AI provider — NVIDIA NIM key */}
        <div style={sty.section}>
          <div style={{ ...sty.sectionTitle, display: 'flex', alignItems: 'center', gap: 8 }}>
            <KeyRound size={15} strokeWidth={1.75} />
            AI provider · NVIDIA NIM
            {keyStatus.configured && (
              <span style={{ ...sty.chip('var(--color-success)'), marginLeft: 'auto' }}>
                Configured · {keyStatus.tail}
              </span>
            )}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginBottom: 10, lineHeight: 1.5 }}>
            Used for material property estimates, synthesis planning, and the supercap recommender.
            Get a key from <a href="https://build.nvidia.com" target="_blank" rel="noopener noreferrer"
              style={{ color: 'var(--accent)' }}>build.nvidia.com</a> (free tier available).
            Key is stored locally in <code style={{ fontFamily: 'var(--font-data)', fontSize: 11 }}>.env</code>;
            never sent anywhere except integrate.api.nvidia.com.
          </div>

          <input
            value={keyInput}
            onChange={e => { setKeyInput(e.target.value); setValidateState({ kind: 'idle' }); }}
            placeholder="nvapi-xxxxxxxxxxxxxxxxxxxxxxxx"
            spellCheck={false}
            type="password"
            autoComplete="off"
            style={{ ...inputStyle, fontFamily: 'var(--font-data)', fontSize: 12 }}
          />

          {validateState.kind === 'ok' && (
            <div style={validBox(true)}>
              <CheckCircle2 size={14} style={{ flexShrink: 0 }} />
              <span>Key validated — model <strong>{validateState.model}</strong> reachable in {validateState.latency?.toFixed(1)}s</span>
            </div>
          )}
          {validateState.kind === 'bad' && (
            <div style={validBox(false)}>
              <AlertCircle size={14} style={{ flexShrink: 0 }} />
              <span>{validateState.error}</span>
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button
              onClick={validateKey}
              disabled={!keyInput.trim() || validateState.kind === 'working'}
              style={{ ...secondaryBtn, flex: 1, opacity: !keyInput.trim() ? 0.5 : 1 }}
            >
              {validateState.kind === 'working'
                ? <><Loader2 size={13} className="raman-spin" /> Checking…</>
                : 'Validate'}
            </button>
            <button
              onClick={() => saveKey(false)}
              disabled={!keyInput.trim() || savingKey || validateState.kind !== 'ok'}
              style={{ ...primaryBtn, flex: 1, opacity: validateState.kind !== 'ok' ? 0.5 : 1 }}
              title={validateState.kind !== 'ok' ? 'Validate the key first' : 'Save and activate the key'}
            >
              {savingKey ? 'Saving…' : 'Save key'}
            </button>
          </div>

          {keyStatus.configured && (
            <button
              onClick={() => saveKey(true)}
              disabled={savingKey}
              style={{ ...secondaryBtn, marginTop: 8, width: '100%', color: 'var(--color-error)', borderColor: 'rgba(220,38,38,0.30)' }}
            >
              Remove saved key
            </button>
          )}
        </div>

        {/* License */}
        <div style={sty.section}>
          <div style={sty.sectionTitle}>License</div>

          {licenseError && (
            <div style={errorBoxStyle}>{licenseError}</div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
            <Stat label="Plan" value={license.plan || '—'} color={statusColor} />
            <Stat label="Days remaining" value={license.days_remaining ?? '—'} color="var(--accent)" />
          </div>

          <div style={sty.row}>
            <span style={sty.lbl}>Status</span>
            <span style={{ fontSize: 12, color: statusColor, fontFamily: 'var(--font-data)' }}>
              {STATUS_LABEL[license.status] || license.status}
            </span>
          </div>
          {license.expires_at && (
            <div style={sty.row}>
              <span style={sty.lbl}>Expires</span>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-data)' }}>
                {new Date(license.expires_at * 1000).toISOString().slice(0, 10)}
              </span>
            </div>
          )}
          <div style={sty.row}>
            <span style={sty.lbl}>Hardware id</span>
            <span style={{ flex: 1, fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-data)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {license.hardware ? license.hardware.slice(0, 20) + '…' : '…'}
            </span>
            <button onClick={copyHardwareId} style={{ ...secondaryBtn, fontSize: 11, padding: '4px 9px' }}>
              {hwIdCopied ? '✓ Copied' : 'Copy'}
            </button>
          </div>

          <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px dashed var(--border-secondary)' }}>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginBottom: 6 }}>
              Paste a license token to activate (or reactivate):
            </div>
            <textarea
              value={licenseInput}
              onChange={e => setLicenseInput(e.target.value)}
              placeholder="RMNS1.eyJhbGc...."
              spellCheck={false}
              rows={3}
              style={{ ...inputStyle, fontFamily: 'var(--font-data)', fontSize: 11, resize: 'vertical', minHeight: 60 }}
            />
            {activateError && (
              <div style={validBox(false)}>{activateError}</div>
            )}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button
                onClick={handleActivate}
                disabled={activating || !licenseInput.trim()}
                style={{ ...primaryBtn, flex: 1 }}
              >
                {activating ? 'Verifying…' : 'Activate'}
              </button>
              {license.status === 'ok' && (
                <button onClick={handleDeactivate} style={secondaryBtn}>Deactivate</button>
              )}
            </div>
          </div>
        </div>

        {/* Theme */}
        <div style={sty.section}>
          <div style={sty.sectionTitle}>Appearance</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
            {Object.values(themes).map(t => (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
                style={{
                  background: theme === t.id ? 'var(--accent-muted)' : 'var(--bg-surface)',
                  border: `1px solid ${theme === t.id ? 'var(--accent)' : 'var(--border-primary)'}`,
                  borderRadius: 'var(--radius-sm)',
                  padding: 12, cursor: 'pointer', textAlign: 'left',
                  transition: 'all 150ms',
                }}
              >
                <ThemeSwatch themeId={t.id} />
                <div style={{
                  fontSize: 12, fontWeight: 500, marginTop: 8,
                  color: theme === t.id ? 'var(--accent)' : 'var(--text-primary)',
                }}>
                  {t.label}
                </div>
                <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', marginTop: 2, lineHeight: 1.4 }}>
                  {t.description}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── small components ─────────────────────────────────────────

function Avatar({ src, initials, onPick, onClear }) {
  return (
    <div style={{
      position: 'relative', width: 64, height: 64, flexShrink: 0,
      borderRadius: '50%',
      background: src ? 'transparent' : 'var(--accent)',
      overflow: 'hidden',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      border: '1px solid var(--border-secondary)',
    }}>
      {src ? (
        <img src={src} alt="profile" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      ) : (
        <span style={{ fontSize: 20, fontWeight: 600, color: '#fff', letterSpacing: '-0.02em' }}>
          {initials}
        </span>
      )}
      <button
        onClick={onPick}
        title="Change photo"
        style={{
          position: 'absolute', bottom: 0, right: 0,
          width: 24, height: 24, borderRadius: '50%',
          background: 'var(--bg-elevated)', border: '1px solid var(--border-secondary)',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text-primary)',
        }}
      >
        <Camera size={12} />
      </button>
      {src && (
        <button
          onClick={onClear}
          title="Remove photo"
          style={{
            position: 'absolute', top: 0, right: 0,
            width: 22, height: 22, borderRadius: '50%',
            background: 'var(--bg-elevated)', border: '1px solid var(--border-secondary)',
            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--color-error)',
          }}
        >
          <Trash2 size={11} />
        </button>
      )}
    </div>
  );
}

function ThemeSwatch({ themeId }) {
  // Render a small token preview in the actual colours of each theme.
  // We can't easily evaluate the other themes' CSS vars at runtime
  // without a temporary DOM scoping trick, so we use known values.
  const presets = {
    light: { bg: '#fbfbfd', surface: '#ffffff', accent: '#2563eb', text: '#18181b', border: '#e2e8f0' },
    dark:  { bg: '#0d0d10', surface: '#1c1c24', accent: '#4a8eff', text: '#ededf0', border: '#2a2a35' },
    hc:    { bg: '#ffffff', surface: '#ffffff', accent: '#0000ee', text: '#000000', border: '#000000' },
  };
  const p = presets[themeId] || presets.light;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 4, padding: 6,
      background: p.bg, border: `1px solid ${p.border}`,
      borderRadius: 'var(--radius-sm)',
    }}>
      <span style={{ width: 12, height: 12, borderRadius: 6, background: p.surface, border: `1px solid ${p.border}` }} />
      <span style={{ width: 12, height: 12, borderRadius: 6, background: p.accent }} />
      <span style={{ flex: 1, height: 4, borderRadius: 2, background: p.text, opacity: 0.85 }} />
    </div>
  );
}

function Stat({ label, value, color = 'var(--text-primary)' }) {
  return (
    <div style={{
      background: 'var(--bg-surface)',
      borderRadius: 'var(--radius-sm)',
      padding: 10,
      border: '1px solid var(--border-primary)',
    }}>
      <div data-number style={{ fontSize: 17, fontWeight: 600, color, textTransform: 'capitalize' }}>{value}</div>
      <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>{label}</div>
    </div>
  );
}

function Switch({ on }) {
  return (
    <div style={{
      width: 32, height: 18, borderRadius: 9, padding: 2,
      background: on ? 'var(--accent)' : 'var(--bg-input)',
      border: `1px solid ${on ? 'transparent' : 'var(--border-secondary)'}`,
      transition: 'background 150ms',
    }}>
      <div style={{
        width: 12, height: 12, borderRadius: 6,
        background: on ? '#fff' : 'var(--text-tertiary)',
        transform: on ? 'translateX(14px)' : 'translateX(0)',
        transition: 'transform 150ms',
      }} />
    </div>
  );
}

// ── helpers ──────────────────────────────────────────────────

function labelize(camel) {
  return camel
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, c => c.toUpperCase());
}

// Downscale + JPEG-encode an image to a data URL roughly fitting the
// MAX_AVATAR_BYTES budget. Square crop, 192px max side.
function downscaleToDataUrl(srcDataUrl, maxSize = 192) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = maxSize; c.height = maxSize;
      const ctx = c.getContext('2d');
      // Center-crop to square.
      const s = Math.min(img.width, img.height);
      const sx = (img.width - s) / 2;
      const sy = (img.height - s) / 2;
      ctx.drawImage(img, sx, sy, s, s, 0, 0, maxSize, maxSize);
      // Try JPEG q=0.85; if too large, drop quality.
      let q = 0.85;
      let out = c.toDataURL('image/jpeg', q);
      while (out.length > MAX_AVATAR_BYTES * 1.4 && q > 0.4) {
        q -= 0.1;
        out = c.toDataURL('image/jpeg', q);
      }
      resolve(out);
    };
    img.onerror = () => resolve('');
    img.src = srcDataUrl;
  });
}

// ── style fragments ─────────────────────────────────────────

const inputStyle = {
  width: '100%',
  flex: 1,
  background: 'var(--bg-input)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-sm)',
  padding: '7px 10px',
  fontSize: 12.5,
  fontFamily: 'var(--font-ui)',
  color: 'var(--text-primary)',
  outline: 'none',
  transition: 'border-color 150ms',
};

const primaryBtn = {
  padding: '8px 14px',
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  fontSize: 12.5,
  fontWeight: 500,
  cursor: 'pointer',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
  fontFamily: 'var(--font-ui)',
};

const secondaryBtn = {
  padding: '7px 12px',
  background: 'transparent',
  color: 'var(--text-primary)',
  border: '1px solid var(--border-secondary)',
  borderRadius: 'var(--radius-sm)',
  fontSize: 12.5,
  cursor: 'pointer',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
  fontFamily: 'var(--font-ui)',
};

const errorBoxStyle = {
  padding: 10, marginBottom: 10, borderRadius: 'var(--radius-sm)',
  background: 'rgba(220, 38, 38, 0.08)', border: '1px solid rgba(220, 38, 38, 0.25)',
  fontSize: 11.5, color: 'var(--color-error)',
};

function validBox(ok) {
  const color = ok ? 'var(--color-success)' : 'var(--color-error)';
  return {
    display: 'flex', alignItems: 'flex-start', gap: 8,
    marginTop: 8, padding: 8,
    background: ok ? 'rgba(22, 163, 74, 0.06)' : 'rgba(220, 38, 38, 0.06)',
    border: `1px solid ${ok ? 'rgba(22,163,74,0.25)' : 'rgba(220,38,38,0.25)'}`,
    borderRadius: 'var(--radius-sm)',
    fontSize: 11.5, color,
    lineHeight: 1.4,
  };
}
