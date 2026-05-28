import { createContext, useCallback, useContext, useEffect, useState } from 'react';

/**
 * Theme switching via the [data-theme] attribute on <html>.
 * Three themes are supported and defined in src/styles/index.css:
 *
 *   light   — default; clean white surface with deep-blue accent.
 *   dark    — calm charcoal for late-night work.
 *   hc      — high-contrast (WCAG AAA): pure black on white,
 *             hard borders, link-blue accent, yellow secondary.
 *
 * Persisted to localStorage under "raman-theme".
 */

export const THEMES = {
  light: { id: 'light', label: 'Light',          description: 'Clean white surface — default for daytime work.' },
  dark:  { id: 'dark',  label: 'Dark',           description: 'Calm charcoal for low-light environments.' },
  hc:    { id: 'hc',    label: 'High contrast',  description: 'WCAG AAA — black on white, hard borders.' },
};

const ThemeContext = createContext(null);

const STORAGE_KEY = 'raman-theme';

function readPersistedTheme() {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return THEMES[v] ? v : 'light';
  } catch {
    return 'light';
  }
}

function applyTheme(themeId) {
  const root = document.documentElement;
  if (themeId === 'light') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', themeId);
  }
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => readPersistedTheme());

  const setTheme = useCallback((themeId) => {
    if (!THEMES[themeId]) return;
    setThemeState(themeId);
    applyTheme(themeId);
    try { localStorage.setItem(STORAGE_KEY, themeId); } catch { /* private mode */ }
  }, []);

  // Apply the persisted theme on mount, and listen for system preference
  // changes so a user who picks "light" but flips OS to dark mode keeps
  // their explicit choice.
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

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

export default useTheme;
