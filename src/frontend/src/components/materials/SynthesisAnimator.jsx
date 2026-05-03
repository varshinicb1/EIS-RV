import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Activity, Thermometer, Droplets, Gauge, Atom, Zap } from 'lucide-react';

/**
 * SynthesisAnimator v3 — Production-Grade Canvas Renderer
 * =========================================================
 * High-fidelity 2D synthesis visualization engine for the RĀMAN Studio
 * materials science platform.
 *
 * Design decisions:
 *   - Uses native HTML5 Canvas for zero-dependency, guaranteed rendering
 *     in Electron and any browser context (no WebGL driver issues).
 *   - Sub-pixel rendering with devicePixelRatio awareness for Retina/HiDPI.
 *   - All animation state is requestAnimationFrame-driven with proper cleanup.
 *   - Telemetry is derived deterministically from step progression (no random).
 *   - Crystal lattice uses actual atomic coordinate data from MaterialsExplorer DB.
 */

// ── Design Tokens (Midnight Instrumentation) ─────────────────────────────────
const T = {
  bg:       '#020204',
  bgPanel:  'rgba(10, 10, 14, 0.88)',
  accent:   'var(--accent)',
  warning:  'var(--color-error)',
  success:  'var(--color-success)',
  amber:    '#ffb800',
  textDim:  'rgba(255, 255, 255, 0.35)',
  textMid:  'rgba(255, 255, 255, 0.6)',
  textHi:   '#ffffff',
  border:   'rgba(74, 142, 255, 0.15)',
  font:     '"JetBrains Mono", "Fira Code", monospace',
};

// ── Utility: lerp + clamp ────────────────────────────────────────────────────
const lerp = (a, b, t) => a + (b - a) * t;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// ── Canvas Renderer ──────────────────────────────────────────────────────────

function drawBeaker(ctx, cx, cy, w, h, fillPct, liquidColor, t) {
  const bw = w * 0.36;   // beaker width
  const bh = h * 0.55;   // beaker height
  const bx = cx - bw / 2;
  const by = cy - bh * 0.3;

  // Glass body
  ctx.save();
  ctx.strokeStyle = 'rgba(74, 142, 255, 0.25)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(bx, by);
  ctx.lineTo(bx, by + bh);
  ctx.lineTo(bx + bw, by + bh);
  ctx.lineTo(bx + bw, by);
  ctx.stroke();

  // Glass rim highlight
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(bx - 4, by);
  ctx.lineTo(bx + bw + 4, by);
  ctx.stroke();

  // Graduation marks
  ctx.fillStyle = T.textDim;
  ctx.font = `8px ${T.font}`;
  for (let i = 1; i <= 4; i++) {
    const gy = by + bh - (i / 5) * bh;
    ctx.fillRect(bx + bw - 12, gy, 8, 0.5);
    ctx.fillText(`${i * 25}`, bx + bw + 4, gy + 3);
  }

  // Liquid fill
  const fillH = bh * clamp(fillPct, 0, 1);
  const ly = by + bh - fillH;

  // Liquid body gradient
  const lg = ctx.createLinearGradient(bx, ly, bx, by + bh);
  lg.addColorStop(0, liquidColor + 'aa');
  lg.addColorStop(1, liquidColor + '44');
  ctx.fillStyle = lg;
  ctx.fillRect(bx + 1, ly, bw - 2, fillH - 1);

  // Meniscus / surface wave
  ctx.strokeStyle = liquidColor;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let x = 0; x <= bw - 2; x++) {
    const wave = Math.sin((x / bw) * Math.PI * 3 + t * 2) * 2;
    if (x === 0) ctx.moveTo(bx + 1 + x, ly + wave);
    else ctx.lineTo(bx + 1 + x, ly + wave);
  }
  ctx.stroke();

  // Glow on liquid surface
  const sg = ctx.createRadialGradient(cx, ly, 0, cx, ly, bw * 0.6);
  sg.addColorStop(0, liquidColor + '22');
  sg.addColorStop(1, 'transparent');
  ctx.fillStyle = sg;
  ctx.fillRect(bx, ly - 10, bw, 20);

  ctx.restore();

  return { bx, by, bw, bh, ly, fillH };
}

function drawParticles(ctx, particles, t) {
  for (const p of particles) {
    const x = p.x + Math.sin(t * p.freq + p.phase) * p.amp;
    const y = p.y - t * p.rise * 0.3;
    const wrappedY = ((y % p.bounds.h) + p.bounds.h) % p.bounds.h + p.bounds.top;

    if (wrappedY < p.bounds.top || wrappedY > p.bounds.top + p.bounds.h) continue;

    const alpha = 0.3 + Math.sin(t * 3 + p.phase) * 0.3;
    ctx.fillStyle = p.color + Math.round(alpha * 255).toString(16).padStart(2, '0');
    ctx.beginPath();
    ctx.arc(x, wrappedY, p.size, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawLattice(ctx, atoms, cx, cy, scale, angle, active, color) {
  if (!atoms || atoms.length === 0) return;

  ctx.save();
  ctx.translate(cx, cy);

  // Rotate lattice
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);

  const elementColors = {
    'C':  '#6b7280',
    'Mn': '#a855f7',
    'O':  '#ef4444',
    'Fe': '#f97316',
    'Co': '#3b82f6',
    'Ni': '#22c55e',
    'Li': '#facc15',
    'Ti': '#94a3b8',
    'V':  '#8b5cf6',
    'Mo': '#06b6d4',
    'S':  '#eab308',
    'Pt': '#d4d4d8',
    'Au': '#fbbf24',
    'Zn': '#a3a3a3',
    'Ru': '#64748b',
    'W':  '#78716c',
    'N':  '#2563eb',
    'P':  '#16a34a',
  };

  // Draw bonds between nearby atoms
  if (active) {
    ctx.strokeStyle = color + '33';
    ctx.lineWidth = 1;
    for (let i = 0; i < atoms.length; i++) {
      for (let j = i + 1; j < atoms.length; j++) {
        const a = atoms[i], b = atoms[j];
        const dx = (b.x - a.x), dy = (b.y - a.y), dz = (b.z || 0) - (a.z || 0);
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist < 3) {
          const ax = a.x * cos - (a.z || 0) * sin;
          const ay = a.y;
          const bx2 = b.x * cos - (b.z || 0) * sin;
          const by2 = b.y;
          ctx.beginPath();
          ctx.moveTo(ax * scale, ay * scale);
          ctx.lineTo(bx2 * scale, by2 * scale);
          ctx.stroke();
        }
      }
    }
  }

  // Draw atoms
  for (const atom of atoms) {
    const ax = atom.x * cos - (atom.z || 0) * sin;
    const ay = atom.y;
    const r = active ? 8 : 5;
    const ec = elementColors[atom.el] || '#888';

    // Glow
    if (active) {
      const glow = ctx.createRadialGradient(ax * scale, ay * scale, 0, ax * scale, ay * scale, r * 2.5);
      glow.addColorStop(0, color + '44');
      glow.addColorStop(1, 'transparent');
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(ax * scale, ay * scale, r * 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // Atom sphere
    const grad = ctx.createRadialGradient(ax * scale - 2, ay * scale - 2, 1, ax * scale, ay * scale, r);
    grad.addColorStop(0, '#fff');
    grad.addColorStop(0.5, ec);
    grad.addColorStop(1, '#000');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(ax * scale, ay * scale, r, 0, Math.PI * 2);
    ctx.fill();

    // Label
    if (active) {
      ctx.fillStyle = T.textHi;
      ctx.font = `bold 7px ${T.font}`;
      ctx.textAlign = 'center';
      ctx.fillText(atom.el, ax * scale, ay * scale + r + 10);
    }
  }

  ctx.restore();
}

function drawGrid(ctx, w, h, t) {
  ctx.save();
  ctx.strokeStyle = 'rgba(74, 142, 255, 0.03)';
  ctx.lineWidth = 0.5;
  const spacing = 24;
  for (let x = 0; x < w; x += spacing) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y < h; y += spacing) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  ctx.restore();
}

// ── Telemetry HUD Widget ─────────────────────────────────────────────────────

const HUDWidget = ({ icon, label, value, color, unit }) => (
  <div style={{
    padding: '8px 12px',
    background: T.bgPanel,
    border: `1px solid ${T.border}`,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    minWidth: 150,
    borderRadius: 2,
  }}>
    <div style={{ color, display: 'flex', alignItems: 'center' }}>{icon}</div>
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 8, color: T.textDim, fontWeight: 800, letterSpacing: '0.12em', fontFamily: T.font }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 700, color: T.textHi, fontFamily: T.font }}>
        {value}
        {unit && <span style={{ fontSize: 9, opacity: 0.5, marginLeft: 2 }}>{unit}</span>}
      </div>
    </div>
  </div>
);

// ── Main Component ───────────────────────────────────────────────────────────

const SynthesisAnimator = ({ protocolSteps = [], materialAtoms = [] }) => {
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const [activeStep, setActiveStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const startTime = useRef(Date.now());
  const particlesRef = useRef([]);

  // Deterministic telemetry derived from step index
  const stepFrac = protocolSteps.length > 0 ? activeStep / protocolSteps.length : 0;
  const telemetry = {
    temp: (22 + stepFrac * 68).toFixed(1),
    ph:   (7.0 - stepFrac * 5.5).toFixed(2),
    pressure: (1.0 + Math.sin(activeStep) * 0.12).toFixed(3),
  };

  const step = protocolSteps[activeStep] || protocolSteps[0] || {};
  const isCritical = !!step.critical;

  // Determine liquid color from step context
  const getLiquidColor = useCallback(() => {
    const action = (step.action || '').toLowerCase();
    if (action.includes('kmno4') || action.includes('exothermic')) return '#ff00ff';
    if (action.includes('reduce') || action.includes('neutralize')) return '#334155';
    if (action.includes('microwave') || action.includes('anneal')) return '#ff6b35';
    return T.accent;
  }, [step]);

  // Initialize particles once
  useEffect(() => {
    const arr = [];
    for (let i = 0; i < 40; i++) {
      arr.push({
        x: 0, y: 0,
        size: 1 + Math.random() * 2,
        freq: 1 + Math.random() * 3,
        phase: Math.random() * Math.PI * 2,
        amp: 2 + Math.random() * 8,
        rise: 5 + Math.random() * 15,
        color: i % 3 === 0 ? T.accent : i % 3 === 1 ? '#ffffff' : T.success,
        bounds: { top: 0, h: 0 },
      });
    }
    particlesRef.current = arr;
  }, []);

  // Step progression timer
  useEffect(() => {
    if (!protocolSteps || protocolSteps.length === 0) return;
    const stepDuration = 5000;
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime.current;
      const loopTime = elapsed % (protocolSteps.length * stepDuration);
      const idx = Math.floor(loopTime / stepDuration);
      const pct = (loopTime % stepDuration) / stepDuration;
      setActiveStep(idx);
      setProgress(pct);
    }, 32); // ~30fps state updates
    return () => clearInterval(interval);
  }, [protocolSteps]);

  // Canvas rendering loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const render = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;

      // Only resize if needed
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);
      }

      const t = (Date.now() - startTime.current) / 1000;
      const liquidColor = getLiquidColor();
      const fillPct = 0.15 + stepFrac * 0.65;

      // Clear
      ctx.clearRect(0, 0, w, h);

      // Background gradient
      const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
      bgGrad.addColorStop(0, '#020204');
      bgGrad.addColorStop(1, '#0a0a14');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, w, h);

      // Grid
      drawGrid(ctx, w, h, t);

      // Beaker
      const cx = w * 0.4;
      const cy = h * 0.5;
      const beaker = drawBeaker(ctx, cx, cy, w, h, fillPct, liquidColor, t);

      // Update particle bounds to be inside beaker liquid
      for (const p of particlesRef.current) {
        p.x = beaker.bx + 4 + Math.random() * (beaker.bw - 8);
        p.bounds.top = beaker.ly + 2;
        p.bounds.h = beaker.fillH - 4;
      }
      drawParticles(ctx, particlesRef.current, t);

      // Crystal lattice (right side of canvas)
      const latticeActive = activeStep > 0;
      const latticeAngle = t * 0.3;
      const latticeScale = 25 + (latticeActive ? Math.sin(t * 0.5) * 3 : 0);
      drawLattice(
        ctx, materialAtoms,
        w * 0.75, h * 0.45,
        latticeScale, latticeAngle,
        latticeActive, liquidColor
      );

      // Lattice label
      if (materialAtoms.length > 0) {
        ctx.fillStyle = latticeActive ? T.accent : T.textDim;
        ctx.font = `bold 9px ${T.font}`;
        ctx.textAlign = 'center';
        ctx.fillText(
          latticeActive ? 'CRYSTAL_GROWTH_DETECTED' : 'LATTICE_STANDBY',
          w * 0.75, h * 0.75
        );
        ctx.fillStyle = T.textDim;
        ctx.font = `8px ${T.font}`;
        ctx.fillText(`${materialAtoms.length} atoms · unit cell`, w * 0.75, h * 0.75 + 14);
      }

      // Scanline effect
      ctx.fillStyle = `rgba(0, 242, 255, ${0.01 + Math.sin(t * 4) * 0.005})`;
      const scanY = (t * 40) % h;
      ctx.fillRect(0, scanY, w, 1);

      animRef.current = requestAnimationFrame(render);
    };

    animRef.current = requestAnimationFrame(render);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [activeStep, stepFrac, getLiquidColor, materialAtoms]);

  return (
    <div style={{
      position: 'relative',
      height: 420,
      background: T.bg,
      border: `1px solid ${T.border}`,
      borderRadius: 4,
      overflow: 'hidden',
      marginTop: 12,
    }}>
      {/* Status bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10,
        padding: '10px 14px',
        display: 'flex', alignItems: 'center', gap: 10,
        background: 'linear-gradient(to bottom, rgba(2,2,4,0.9), transparent)',
      }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: isCritical ? T.warning : T.success,
          boxShadow: `0 0 8px ${isCritical ? T.warning : T.success}`,
          animation: 'pulse 2s ease-in-out infinite',
        }} />
        <div>
          <div style={{ fontSize: 10, fontWeight: 900, color: T.textHi, letterSpacing: '0.15em', fontFamily: T.font }}>
            {isCritical ? 'CRITICAL_SYNTH_STATE' : 'PHYSICS_ENGINE_ACTIVE'}
          </div>
          <div style={{ fontSize: 8, color: T.textDim, fontFamily: T.font }}>
            RENDER_CORE: CANVAS_HF_V3 · {materialAtoms.length} ATOMS LOADED
          </div>
        </div>
      </div>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', display: 'block' }}
      />

      {/* Telemetry HUD (right side overlay) */}
      <div style={{
        position: 'absolute', top: 60, right: 14,
        display: 'flex', flexDirection: 'column', gap: 6, zIndex: 10,
      }}>
        <HUDWidget icon={<Thermometer size={14} />} label="CORE_TEMP" value={telemetry.temp} unit="°C" color={isCritical ? T.warning : T.accent} />
        <HUDWidget icon={<Droplets size={14} />} label="IONIC_PH" value={telemetry.ph} color={T.success} />
        <HUDWidget icon={<Gauge size={14} />} label="ATM_PRES" value={telemetry.pressure} unit="atm" color={T.accent} />
      </div>

      {/* Phase info bar */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10,
        padding: '14px 16px',
        background: T.bgPanel,
        borderTop: `1px solid ${T.border}`,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        backdropFilter: 'blur(12px)',
      }}>
        <div style={{ flex: 1, borderLeft: `3px solid ${isCritical ? T.warning : T.accent}`, paddingLeft: 12 }}>
          <div style={{ fontSize: 9, color: T.textDim, fontWeight: 800, letterSpacing: '0.2em', fontFamily: T.font }}>
            PHASE // {activeStep + 1} OF {protocolSteps.length || 1}
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: T.textHi, fontFamily: T.font, marginTop: 2 }}>
            {step.phase || 'STANDBY'}
          </div>
          <div style={{ fontSize: 11, color: T.textMid, marginTop: 2, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {step.action || 'Awaiting protocol...'}
          </div>
        </div>
        <div style={{ width: 130, textAlign: 'right' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: T.textDim, fontFamily: T.font }}>
            <span>SYNC</span>
            <span>{Math.round(progress * 100)}%</span>
          </div>
          <div style={{ height: 2, background: 'rgba(255,255,255,0.05)', marginTop: 4, borderRadius: 1 }}>
            <div style={{
              height: '100%', borderRadius: 1,
              width: `${progress * 100}%`,
              background: isCritical ? T.warning : T.accent,
              transition: 'width 0.1s linear',
            }} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default SynthesisAnimator;
