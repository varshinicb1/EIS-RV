import React from 'react';

/**
 * RĀMAN Studio brand mark + wordmark.
 *
 * The mark is a stylised three-line scattering pattern (Stokes / anti-Stokes
 * peaks around the Rayleigh line — the namesake physics) drawn at 1px stroke,
 * matching the rest of the UI's restraint. No glow, no gradients.
 *
 * Variants:
 *   <Logo />            → mark + wordmark, default
 *   <Logo markOnly />   → mark only (used in collapsed sidebar)
 *   <Logo size={16} />  → scales mark + text together
 */
export default function Logo({
  size = 18,
  markOnly = false,
  color,           // override mark stroke
  textColor,       // override wordmark color
  subtitle,        // optional small subtitle below wordmark
  className,
  style = {},
}) {
  const stroke = color || 'var(--accent)';
  const text = textColor || 'var(--text-primary)';

  return (
    <div className={className} style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 10,
      ...style,
    }}>
      <BrandMark size={size} stroke={stroke} />
      {!markOnly && (
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1, gap: 1 }}>
          <span style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 600,
            fontSize: Math.round(size * 0.78),
            color: text,
            letterSpacing: '-0.005em',
          }}>
            RĀMAN <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}>Studio</span>
          </span>
          {subtitle && (
            <span style={{
              fontFamily: 'var(--font-ui)',
              fontWeight: 400,
              fontSize: Math.round(size * 0.52),
              color: 'var(--text-tertiary)',
            }}>
              {subtitle}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function BrandMark({ size = 18, stroke = 'var(--accent)' }) {
  // Tiny Raman scattering motif: central Rayleigh peak (taller) flanked by
  // two side bands (Stokes / anti-Stokes). Drawn into a 24×24 viewBox so it
  // crisp-renders at any device pixel ratio.
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      role="img"
      aria-label="RĀMAN Studio"
      style={{ flexShrink: 0 }}
    >
      <rect x="0.5" y="0.5" width="23" height="23" rx="5"
            stroke="var(--border-secondary)" strokeWidth="1" fill="var(--bg-elevated)" />
      {/* baseline */}
      <line x1="4" y1="17" x2="20" y2="17" stroke="var(--text-disabled)" strokeWidth="1" />
      {/* anti-Stokes peak (left) */}
      <line x1="7" y1="17" x2="7" y2="13" stroke={stroke} strokeWidth="1.4" strokeLinecap="round" />
      {/* Rayleigh peak (center, tallest) */}
      <line x1="12" y1="17" x2="12" y2="7" stroke={stroke} strokeWidth="1.6" strokeLinecap="round" />
      {/* Stokes peak (right) */}
      <line x1="17" y1="17" x2="17" y2="11" stroke={stroke} strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export { BrandMark };
