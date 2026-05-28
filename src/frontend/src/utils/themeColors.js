/**
 * Theme-aware colour helpers for non-CSS contexts.
 *
 * HTML5 `<canvas>` 2D and THREE.js do NOT resolve CSS custom properties
 * at use time, so any plot or 3D scene that wants to honour the active
 * theme has to read tokens explicitly.
 *
 * Usage:
 *   import { getCss, plotPalette } from '../../utils/themeColors';
 *   ctx.fillStyle = getCss('--plot-axis');
 *   const series = plotPalette();
 *   ctx.strokeStyle = series[0];   // theme series-1 colour
 *
 * Accepts a fallback for the very-first paint before the theme has
 * applied (rare but cheap to handle).
 */

export function getCss(varName, fallback = '#000') {
  if (typeof window === 'undefined' || !document.documentElement) return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  return v || fallback;
}

export function plotPalette() {
  return [
    getCss('--plot-series-1', '#1f77b4'),
    getCss('--plot-series-2', '#ff7f0e'),
    getCss('--plot-series-3', '#2ca02c'),
    getCss('--plot-series-4', '#d62728'),
    getCss('--plot-series-5', '#9467bd'),
    getCss('--plot-series-6', '#8c564b'),
    getCss('--plot-series-7', '#e377c2'),
  ];
}

export function plotTheme() {
  return {
    bg:    getCss('--plot-bg', '#ffffff'),
    axis:  getCss('--plot-axis', '#1f2937'),
    grid:  getCss('--plot-grid', 'rgba(15,23,42,0.10)'),
    text:  getCss('--plot-text', '#1f2937'),
    palette: plotPalette(),
    fontUI:   getCss('--font-ui',   'Inter, sans-serif'),
    fontPlot: getCss('--font-plot', 'Georgia, Times New Roman, serif'),
    fontData: getCss('--font-data', 'IBM Plex Mono, monospace'),
  };
}

/**
 * Subscribe to theme changes (data-theme attribute mutations on <html>).
 * Returns an unsubscribe function. Call inside a useEffect:
 *
 *   useEffect(() => onThemeChange(redraw), []);
 *
 * Without this, plots painted once at mount stay in the theme that was
 * active at mount time even after the user toggles theme.
 */
export function onThemeChange(handler) {
  if (typeof window === 'undefined' || !document.documentElement) return () => {};
  const obs = new MutationObserver((records) => {
    for (const r of records) {
      if (r.attributeName === 'data-theme') {
        handler();
        break;
      }
    }
  });
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  return () => obs.disconnect();
}
