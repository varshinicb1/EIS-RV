import React, { useEffect, useState } from 'react';
import { AlertCircle, X } from 'lucide-react';

/**
 * OfflineBanner — an explicit notice when the local FastAPI sidecar isn't
 * reachable. Appears at the very top of the main pane, above TopBar, and
 * disappears as soon as the next health probe succeeds.
 *
 * The first probe runs on mount, and the banner is rate-limited so we don't
 * flash it on a single slow request: it shows only after we've seen
 * `disconnected` for ≥ 4 seconds.
 */
export default function OfflineBanner({ backendStatus }) {
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (backendStatus === 'connected') {
      setVisible(false);
      setDismissed(false);
      return;
    }
    if (backendStatus !== 'disconnected') return;
    const t = setTimeout(() => setVisible(true), 4000);
    return () => clearTimeout(t);
  }, [backendStatus]);

  if (!visible || dismissed) return null;

  return (
    <div role="status" style={{
      flexShrink: 0,
      padding: '8px 16px',
      background: 'rgba(255, 69, 58, 0.08)',
      borderBottom: '1px solid rgba(255, 69, 58, 0.25)',
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      fontSize: 12.5,
      color: 'var(--color-error)',
    }}>
      <AlertCircle size={15} strokeWidth={2} style={{ flexShrink: 0 }} />
      <div style={{ flex: 1, color: 'var(--text-primary)' }}>
        <strong style={{ fontWeight: 600, color: 'var(--color-error)' }}>Backend offline.</strong>
        <span style={{ marginLeft: 6, color: 'var(--text-secondary)' }}>
          Could not reach the local RĀMAN service on 127.0.0.1:8000. Retrying every 5 seconds.
          Panels that need the backend will show errors until it reconnects.
        </span>
      </div>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        title="Hide until next disconnect"
        style={{
          background: 'transparent',
          border: '1px solid rgba(255, 69, 58, 0.3)',
          borderRadius: 'var(--radius-sm)',
          color: 'var(--color-error)',
          padding: '3px 6px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <X size={13} />
      </button>
    </div>
  );
}
