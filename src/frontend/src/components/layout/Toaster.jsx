import React, { useState, useEffect } from 'react';

/**
 * Listens for `RAMAN_TOAST` window CustomEvents and renders ephemeral
 * notifications. Any panel can fire:
 *
 *   window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
 *     detail: { kind: 'ok' | 'info' | 'err', text: '...', durationMs?: 3500 }
 *   }));
 *
 * Toasts auto-dismiss after `durationMs` (default 3.5s) or when clicked.
 * Mount this once in App.jsx.
 */
export default function Toaster() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    const onToast = (e) => {
      const id = `t_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const detail = e?.detail || {};
      const t = {
        id,
        kind: detail.kind || 'info',
        text: String(detail.text || ''),
        duration: Number(detail.durationMs ?? 3500),
      };
      setToasts(prev => [...prev, t]);
      setTimeout(() => {
        setToasts(prev => prev.filter(x => x.id !== id));
      }, t.duration);
    };
    window.addEventListener('RAMAN_TOAST', onToast);
    return () => window.removeEventListener('RAMAN_TOAST', onToast);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div style={{
      position: 'fixed', bottom: 28, left: '50%', transform: 'translateX(-50%)',
      display: 'flex', flexDirection: 'column', gap: 8, zIndex: 9999,
      pointerEvents: 'none',
    }}>
      {toasts.map(t => (
        <div
          key={t.id}
          onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))}
          style={{
            pointerEvents: 'auto', cursor: 'pointer', minWidth: 280, maxWidth: 540,
            padding: '10px 16px',
            background: 'var(--bg-elevated)',
            border: `1px solid ${
              t.kind === 'ok' ? 'rgba(52, 199, 89, 0.35)' :
              t.kind === 'err' ? 'rgba(255, 69, 58, 0.35)' :
              'var(--accent-border)'}`,
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-ui)', fontSize: 12.5,
            display: 'flex', alignItems: 'center', gap: 10,
          }}
        >
          <span style={{
            width: 7, height: 7, borderRadius: '50%',
            background: t.kind === 'ok' ? 'var(--color-success)'
                     : t.kind === 'err' ? 'var(--color-error)'
                     : 'var(--accent)',
            flexShrink: 0,
          }} />
          <span style={{ flex: 1 }}>{t.text}</span>
        </div>
      ))}
    </div>
  );
}
