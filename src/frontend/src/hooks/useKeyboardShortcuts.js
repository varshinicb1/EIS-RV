import { useEffect } from 'react';

/**
 * Global keyboard shortcut system for RĀMAN Studio.
 * 
 * Shortcuts:
 *   Ctrl+1-9      → Navigate to panel by index
 *   Ctrl+Shift+E  → EIS panel
 *   Ctrl+Shift+C  → CV panel
 *   Ctrl+Shift+B  → Battery panel
 *   Ctrl+Shift+D  → DRT panel
 *   Ctrl+Shift+A  → Alchemi AI
 *   Ctrl+Shift+V  → Paper Validation
 *   Ctrl+Shift+I  → Data Import
 *   Ctrl+Shift+T  → Toolkit
 *   Ctrl+E        → Export CSV (dispatches custom event)
 *   Ctrl+R        → Run simulation (dispatches custom event)
 *   Ctrl+/        → Toggle sidebar
 *   Escape        → Close modal / reset
 */

const PANEL_SHORTCUTS = {
  'E': 'eis',
  'C': 'cv',
  'B': 'battery',
  'D': 'drt',
  'A': 'alchemi',
  'V': 'validation',
  'I': 'data',
  'T': 'toolkit',
  'F': 'circuit',
  'G': 'gcd',
  'M': 'materials',
  'L': 'literature',
  'S': 'biosensor',
  'W': 'workspace',
};

const PANEL_INDEX = [
  'dashboard', 'alchemi', 'biosensor', 'eis', 'cv',
  'battery', 'gcd', 'drt', 'circuit',
];

export default function useKeyboardShortcuts(onNavigate, onToggleSidebar) {
  useEffect(() => {
    const handler = (e) => {
      // Don't intercept when typing in inputs
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;

      // Ctrl+Shift+Letter → Panel navigation
      if (e.ctrlKey && e.shiftKey && PANEL_SHORTCUTS[e.key.toUpperCase()]) {
        e.preventDefault();
        const panel = PANEL_SHORTCUTS[e.key.toUpperCase()];
        if (onNavigate) onNavigate(panel);
        window.dispatchEvent(new CustomEvent('NAVIGATE_PANEL', { detail: panel }));
        return;
      }

      // Ctrl+1-9 → Panel by index
      if (e.ctrlKey && !e.shiftKey && e.key >= '1' && e.key <= '9') {
        e.preventDefault();
        const idx = parseInt(e.key) - 1;
        if (idx < PANEL_INDEX.length) {
          const panel = PANEL_INDEX[idx];
          if (onNavigate) onNavigate(panel);
          window.dispatchEvent(new CustomEvent('NAVIGATE_PANEL', { detail: panel }));
        }
        return;
      }

      // Ctrl+E → Export
      if (e.ctrlKey && !e.shiftKey && e.key === 'e') {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent('RAMAN_EXPORT'));
        return;
      }

      // Ctrl+Enter or Ctrl+R → Run simulation
      if (e.ctrlKey && !e.shiftKey && (e.key === 'r' || e.key === 'Enter')) {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent('RAMAN_RUN'));
        return;
      }

      // Ctrl+/ → Toggle sidebar
      if (e.ctrlKey && e.key === '/') {
        e.preventDefault();
        if (onToggleSidebar) onToggleSidebar();
        return;
      }

      // Escape → Reset
      if (e.key === 'Escape') {
        window.dispatchEvent(new CustomEvent('RAMAN_ESCAPE'));
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onNavigate, onToggleSidebar]);
}
