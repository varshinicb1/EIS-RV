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
            padding: '11px 18px',
            background: 'rgba(2, 2, 4, 0.97)',
            backdropFilter: 'blur(20px) saturate(160%)',
            border: `1px solid ${
              t.kind === 'ok' ? 'rgba(0, 255, 157, 0.4)' :
              t.kind === 'err' ? 'rgba(255, 107, 107, 0.4)' :
              'rgba(0, 242, 255, 0.3)'}`,
            borderRadius: 4,
            boxShadow: '0 10px 40px rgba(0,0,0,0.6)',
            color: t.kind === 'ok' ? '#00ff9d' : t.kind === 'err' ? '#ff6b6b' : '#00f2ff',
            fontFamily: '"JetBrains Mono", monospace', fontSize: 11,
            letterSpacing: '0.03em',
            display: 'flex', alignItems: 'center', gap: 10,
          }}
        >
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: t.kind === 'ok' ? '#00ff9d' : t.kind === 'err' ? '#ff6b6b' : '#00f2ff',
            boxShadow: `0 0 8px ${t.kind === 'ok' ? '#00ff9d' : t.kind === 'err' ? '#ff6b6b' : '#00f2ff'}`,
            flexShrink: 0,
          }} />
          <span style={{ color: '#fff', flex: 1 }}>{t.text}</span>
        </div>
      ))}
    </div>
  );
}
