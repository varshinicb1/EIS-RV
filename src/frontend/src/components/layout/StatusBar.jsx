import React, { useEffect, useState } from 'react';

/**
 * StatusBar — bottom bar with real, useful state.
 *
 * Left:   backend version + active panel
 * Centre: backend reachability summary
 * Right:  NIM availability + license summary
 *
 * No theatrical "buffer cache 42.18 %" or fake session ids. Every value is
 * either real (pulled from the backend) or computed deterministically.
 */
export default function StatusBar({ backendStatus, licenseInfo, nimConfigured, activePanel }) {
  const [backendVersion, setBackendVersion] = useState(null);
  const [routeCount, setRouteCount] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const fetchMeta = async () => {
      try {
        const api = window.raman?.api;
        const get = (p) => api ? api.get(p) : fetch(`http://127.0.0.1:8000${p}`).then(r => r.ok ? r.json() : Promise.reject(r));
        const h = await get('/api/health');
        if (cancelled) return;
        setBackendVersion(h?.version || null);
        try {
          const o = await get('/openapi.json');
          if (!cancelled) setRouteCount(Object.keys(o?.paths || {}).length);
        } catch { /* openapi can be slow on cold start */ }
      } catch {
        if (!cancelled) { setBackendVersion(null); setRouteCount(null); }
      }
    };
    fetchMeta();
    // Refresh once a minute — version doesn't change often.
    const id = setInterval(fetchMeta, 60_000);
    return () => { cancelled = true; clearInterval(id); };
  }, [backendStatus]);

  const isOnline = backendStatus === 'connected';

  const dot = (color) => (
    <span style={{
      width: 6, height: 6, borderRadius: '50%', background: color,
      display: 'inline-block', marginRight: 6, flexShrink: 0,
    }} />
  );

  return (
    <footer style={{
      height: 'var(--statusbar-height)',
      flexShrink: 0,
      background: 'var(--bg-tertiary)',
      borderTop: '1px solid var(--border-primary)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 14px',
      fontSize: 11,
      color: 'var(--text-tertiary)',
      gap: 18,
    }}>
      <Slot>
        <strong style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>RĀMAN Studio</strong>
        {backendVersion && <span data-number>v{backendVersion}</span>}
      </Slot>

      <Sep />

      <Slot title={isOnline ? 'Backend reachable on 127.0.0.1:8000' : 'Backend not responding — retrying every 5s'}>
        {dot(isOnline ? 'var(--color-success)' : backendStatus === 'connecting' ? 'var(--color-warning)' : 'var(--color-error)')}
        {isOnline ? 'Backend online'
          : backendStatus === 'connecting' ? 'Connecting…'
          : 'Backend offline'}
        {isOnline && routeCount != null && <span style={{ marginLeft: 6 }}>· <span data-number>{routeCount}</span> routes</span>}
      </Slot>

      <div style={{ flex: 1 }} />

      <Slot title={nimConfigured ? 'NVIDIA NIM key set; AI features active.'
        : 'AI features inactive. Set NVIDIA_API_KEY in .env to enable NIM-grounded suggestions.'}>
        {dot(nimConfigured ? 'var(--color-success)' : 'var(--color-standby)')}
        AI: {nimConfigured ? 'configured' : 'inactive'}
      </Slot>

      <Sep />

      <Slot>
        Panel: <span style={{ color: 'var(--text-secondary)' }}>{prettify(activePanel)}</span>
      </Slot>

      <Sep />

      <Slot title={licenseInfo?.message || ''}>
        {licenseInfo
          ? `${capitalize(licenseInfo.plan || licenseInfo.status || 'unknown')}${licenseInfo.days_remaining != null ? ` · ${licenseInfo.days_remaining}d` : ''}`
          : 'Licence: —'}
      </Slot>
    </footer>
  );
}

function Slot({ children, title }) {
  return (
    <span title={title} style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  );
}

function Sep() {
  return <span style={{ width: 1, height: 12, background: 'var(--border-primary)' }} />;
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function prettify(panelKey) {
  if (!panelKey) return '—';
  const map = {
    dashboard: 'Dashboard',
    alchemi: 'Materials AI',
    alchemist_canvas: 'Alchemist Canvas',
    biosensor: 'Biosensor Fab',
    literature: 'Literature Mining',
    eis: 'EIS',
    cv: 'Cyclic Voltammetry',
    battery: 'Battery',
    gcd: 'GCD',
    drt: 'DRT',
    circuit: 'Circuit Fitting',
    toolkit: 'Toolkit',
    materials: 'Materials',
    data: 'Data Import',
    lab: 'Lab Data',
    validation: 'Paper Validation',
    workspace: 'Workspace',
    reports: 'Reports',
    profile: 'Profile',
  };
  return map[panelKey] || panelKey;
}
