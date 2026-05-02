import { useState, useEffect, createContext, useContext, useCallback } from 'react';

/**
 * RĀMAN Studio Theme System
 * =========================
 * Professional multi-theme system with CSS custom property switching.
 * Themes: midnight (default), obsidian, arctic, lab-green, royal-purple
 */

const THEMES = {
  midnight: {
    label: 'Midnight Black',
    description: 'Pure black instrumentation aesthetic',
    vars: {
      '--bg-primary':       '#000000',
      '--bg-secondary':     '#0a0a0c',
      '--bg-tertiary':      '#111114',
      '--bg-elevated':      '#161619',
      '--bg-surface':       '#0d0d10',
      '--bg-input':         '#050507',
      '--accent':           '#4a9eff',
      '--accent-hover':     '#5eaeff',
      '--accent-muted':     'rgba(74, 158, 255, 0.12)',
      '--accent-border':    'rgba(74, 158, 255, 0.25)',
      '--text-primary':     '#e8eaed',
      '--text-secondary':   '#9aa0a6',
      '--text-tertiary':    '#5f6368',
      '--text-disabled':    '#3c4043',
      '--text-value':       '#c8cdd3',
      '--border-primary':   '#1f2125',
      '--border-secondary': '#2a2d32',
    },
  },
  obsidian: {
    label: 'Obsidian',
    description: 'Deep charcoal with warm accents',
    vars: {
      '--bg-primary':       '#0b0b0e',
      '--bg-secondary':     '#121217',
      '--bg-tertiary':      '#1a1a1f',
      '--bg-elevated':      '#1f1f25',
      '--bg-surface':       '#14141a',
      '--bg-input':         '#08080c',
      '--accent':           '#ffa726',
      '--accent-hover':     '#ffb74d',
      '--accent-muted':     'rgba(255, 167, 38, 0.12)',
      '--accent-border':    'rgba(255, 167, 38, 0.25)',
      '--text-primary':     '#e8e6e3',
      '--text-secondary':   '#a09c97',
      '--text-tertiary':    '#6b665f',
      '--text-disabled':    '#4a4640',
      '--text-value':       '#d4cfc8',
      '--border-primary':   '#222028',
      '--border-secondary': '#302d35',
    },
  },
  arctic: {
    label: 'Arctic Light',
    description: 'High-contrast light theme for bright labs',
    vars: {
      '--bg-primary':       '#f8f9fb',
      '--bg-secondary':     '#ffffff',
      '--bg-tertiary':      '#eef0f4',
      '--bg-elevated':      '#e8eaee',
      '--bg-surface':       '#ffffff',
      '--bg-input':         '#f2f3f6',
      '--accent':           '#1a73e8',
      '--accent-hover':     '#1565c0',
      '--accent-muted':     'rgba(26, 115, 232, 0.08)',
      '--accent-border':    'rgba(26, 115, 232, 0.20)',
      '--text-primary':     '#1a1a2e',
      '--text-secondary':   '#5f6368',
      '--text-tertiary':    '#9aa0a6',
      '--text-disabled':    '#bdc1c6',
      '--text-value':       '#2d3748',
      '--border-primary':   '#e0e2e6',
      '--border-secondary': '#d2d4d8',
    },
  },
  'lab-green': {
    label: 'Lab Green',
    description: 'NVIDIA-inspired research green',
    vars: {
      '--bg-primary':       '#020804',
      '--bg-secondary':     '#091210',
      '--bg-tertiary':      '#0f1a16',
      '--bg-elevated':      '#15221d',
      '--bg-surface':       '#0b1612',
      '--bg-input':         '#030a06',
      '--accent':           '#76b900',
      '--accent-hover':     '#8cd200',
      '--accent-muted':     'rgba(118, 185, 0, 0.12)',
      '--accent-border':    'rgba(118, 185, 0, 0.25)',
      '--text-primary':     '#e0eed6',
      '--text-secondary':   '#8faa80',
      '--text-tertiary':    '#5a7050',
      '--text-disabled':    '#3a4a34',
      '--text-value':       '#c0d8b0',
      '--border-primary':   '#1a2e20',
      '--border-secondary': '#253a2b',
    },
  },
  'royal-purple': {
    label: 'Royal Purple',
    description: 'Deep violet for focused research',
    vars: {
      '--bg-primary':       '#060410',
      '--bg-secondary':     '#0c0a18',
      '--bg-tertiary':      '#14101f',
      '--bg-elevated':      '#1a1528',
      '--bg-surface':       '#100d1a',
      '--bg-input':         '#04030a',
      '--accent':           '#ab47bc',
      '--accent-hover':     '#ce93d8',
      '--accent-muted':     'rgba(171, 71, 188, 0.12)',
      '--accent-border':    'rgba(171, 71, 188, 0.25)',
      '--text-primary':     '#e8e0f0',
      '--text-secondary':   '#a090b8',
      '--text-tertiary':    '#6a5a80',
      '--text-disabled':    '#443a56',
      '--text-value':       '#d0c0e0',
      '--border-primary':   '#201830',
      '--border-secondary': '#2e2240',
    },
  },
};

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    try {
      return localStorage.getItem('raman-theme') || 'midnight';
    } catch { return 'midnight'; }
  });

  const applyTheme = useCallback((themeId) => {
    const t = THEMES[themeId];
    if (!t) return;
    const root = document.documentElement;
    Object.entries(t.vars).forEach(([prop, val]) => {
      root.style.setProperty(prop, val);
    });
  }, []);

  const setTheme = useCallback((themeId) => {
    if (!THEMES[themeId]) return;
    setThemeState(themeId);
    applyTheme(themeId);
    try { localStorage.setItem('raman-theme', themeId); } catch {}
  }, [applyTheme]);

  useEffect(() => {
    applyTheme(theme);
  }, []); // Apply on mount

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themes: THEMES }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within <ThemeProvider>');
  return ctx;
}

export { THEMES };
export default useTheme;
