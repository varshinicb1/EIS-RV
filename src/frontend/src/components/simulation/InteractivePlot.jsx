import React, { useRef, useState, useCallback, useEffect } from 'react';

/**
 * InteractivePlot — Adds zoom, pan, and data cursor to any canvas plot.
 *
 * Usage:
 *   <InteractivePlot
 *     data={{ x: [...], y: [...], x2?: [...], y2?: [...] }}
 *     xLabel="Z' / Ω"  yLabel="-Z'' / Ω"
 *     title="Nyquist Plot"
 *     color="#4a9eff"  color2="#ffa726"
 *     xLog={false}  yLog={false}
 *   />
 */
export default function InteractivePlot({
  data, xLabel = 'X', yLabel = 'Y', title = '',
  color = '#4a9eff', color2 = '#ffa726',
  xLog = false, yLog = false,
  lineWidth = 1.5, showPoints = true,
}) {
  const canvasRef = useRef(null);
  const [viewBox, setViewBox] = useState(null); // {xMin, xMax, yMin, yMax}
  const [cursor, setCursor] = useState(null);   // {x, y, idx, px, py}
  const [dragging, setDragging] = useState(null);

  const getDataBounds = useCallback(() => {
    if (!data?.x?.length) return { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
    data.x.forEach(v => { if (v < xMin) xMin = v; if (v > xMax) xMax = v; });
    data.y.forEach(v => { if (v < yMin) yMin = v; if (v > yMax) yMax = v; });
    if (data.y2) data.y2.forEach(v => { if (v < yMin) yMin = v; if (v > yMax) yMax = v; });
    const xPad = (xMax - xMin) * 0.05 || 0.5;
    const yPad = (yMax - yMin) * 0.05 || 0.5;
    return { xMin: xMin - xPad, xMax: xMax + xPad, yMin: yMin - yPad, yMax: yMax + yPad };
  }, [data]);

  const bounds = viewBox || getDataBounds();
  const pad = { t: 24, r: 20, b: 40, l: 60 };

  // Draw
  useEffect(() => {
    if (!data?.x?.length || !canvasRef.current) return;
    const c = canvasRef.current, ctx = c.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = c.getBoundingClientRect();
    c.width = rect.width * dpr; c.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width, h = rect.height;
    const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;
    const { xMin, xMax, yMin, yMax } = bounds;
    const xR = (xMax - xMin) || 1, yR = (yMax - yMin) || 1;
    const sx = v => pad.l + ((v - xMin) / xR) * pw;
    const sy = v => pad.t + ph - ((v - yMin) / yR) * ph;

    ctx.clearRect(0, 0, w, h);

    // Grid
    ctx.strokeStyle = '#2a2d32'; ctx.lineWidth = 0.5;
    for (let i = 0; i <= 5; i++) {
      const x = pad.l + pw / 5 * i, y = pad.t + ph / 5 * i;
      ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ph); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + pw, y); ctx.stroke();
    }
    ctx.strokeStyle = '#3a3d44'; ctx.lineWidth = 1;
    ctx.strokeRect(pad.l, pad.t, pw, ph);

    // Zero lines
    if (yMin < 0 && yMax > 0) {
      ctx.strokeStyle = '#3a3d44'; ctx.lineWidth = 0.5; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(pad.l, sy(0)); ctx.lineTo(pad.l + pw, sy(0)); ctx.stroke();
      ctx.setLineDash([]);
    }

    // Data line 1
    ctx.strokeStyle = color; ctx.lineWidth = lineWidth; ctx.lineJoin = 'round';
    ctx.beginPath();
    data.x.forEach((xv, i) => {
      const px = sx(xv), py = sy(data.y[i]);
      if (px >= pad.l && px <= pad.l + pw && py >= pad.t && py <= pad.t + ph) {
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
    });
    ctx.stroke();

    // Data line 2
    if (data.y2) {
      ctx.strokeStyle = color2; ctx.lineWidth = lineWidth;
      ctx.beginPath();
      data.x.forEach((xv, i) => {
        const px = sx(xv), py = sy(data.y2[i]);
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      });
      ctx.stroke();
    }

    // Points
    if (showPoints && data.x.length < 200) {
      const step = Math.max(1, Math.floor(data.x.length / 30));
      ctx.fillStyle = color;
      for (let i = 0; i < data.x.length; i += step) {
        ctx.beginPath(); ctx.arc(sx(data.x[i]), sy(data.y[i]), 2, 0, Math.PI * 2); ctx.fill();
      }
    }

    // Axis labels
    ctx.fillStyle = '#6b7280'; ctx.font = '10px Inter, sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(xLabel, pad.l + pw / 2, h - 4);
    ctx.save(); ctx.translate(12, pad.t + ph / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText(yLabel, 0, 0); ctx.restore();

    // Ticks
    ctx.fillStyle = '#555a62'; ctx.font = '9px monospace'; ctx.textAlign = 'center';
    for (let i = 0; i <= 4; i++) {
      const v = xMin + xR / 4 * i;
      ctx.fillText(Math.abs(v) > 1000 ? v.toExponential(1) : v.toFixed(2), sx(v), pad.t + ph + 14);
    }
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const v = yMin + yR / 4 * i;
      ctx.fillText(Math.abs(v) > 1000 ? v.toExponential(1) : v.toFixed(1), pad.l - 4, sy(v) + 3);
    }

    // Title
    if (title) {
      ctx.fillStyle = '#c9d1d9'; ctx.font = 'bold 11px Inter, sans-serif'; ctx.textAlign = 'left';
      ctx.fillText(title, pad.l + 4, pad.t - 6);
    }

    // Cursor crosshair
    if (cursor) {
      ctx.strokeStyle = '#ffffff44'; ctx.lineWidth = 0.5; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(cursor.px, pad.t); ctx.lineTo(cursor.px, pad.t + ph); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pad.l, cursor.py); ctx.lineTo(pad.l + pw, cursor.py); ctx.stroke();
      ctx.setLineDash([]);
      // Data point highlight
      ctx.fillStyle = '#fff'; ctx.beginPath();
      ctx.arc(cursor.px, cursor.py, 5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = color; ctx.beginPath();
      ctx.arc(cursor.px, cursor.py, 3, 0, Math.PI * 2); ctx.fill();
      // Value tooltip
      ctx.fillStyle = '#1a1d23ee'; ctx.fillRect(cursor.px + 10, cursor.py - 28, 120, 24);
      ctx.fillStyle = '#e0e0e0'; ctx.font = '9px monospace'; ctx.textAlign = 'left';
      ctx.fillText(`x: ${cursor.x.toPrecision(4)}`, cursor.px + 14, cursor.py - 18);
      ctx.fillText(`y: ${cursor.y.toPrecision(4)}`, cursor.px + 14, cursor.py - 8);
    }
  }, [data, bounds, cursor, color, color2, title, xLabel, yLabel, lineWidth, showPoints, pad]);

  // Mouse handlers
  const getPlotCoords = useCallback((e) => {
    const c = canvasRef.current;
    if (!c) return null;
    const rect = c.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const w = rect.width, h = rect.height;
    const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;
    if (mx < pad.l || mx > pad.l + pw || my < pad.t || my > pad.t + ph) return null;
    const { xMin, xMax, yMin, yMax } = bounds;
    const xR = xMax - xMin, yR = yMax - yMin;
    const x = xMin + ((mx - pad.l) / pw) * xR;
    const y = yMax - ((my - pad.t) / ph) * yR;
    return { x, y, mx, my };
  }, [bounds, pad]);

  const onMouseMove = useCallback((e) => {
    if (!data?.x?.length) return;
    const coords = getPlotCoords(e);
    if (!coords) { setCursor(null); return; }

    if (dragging) {
      // Pan
      const dx = coords.x - dragging.x;
      const dy = coords.y - dragging.y;
      setViewBox(prev => {
        const b = prev || getDataBounds();
        return { xMin: b.xMin - dx, xMax: b.xMax - dx, yMin: b.yMin - dy, yMax: b.yMax - dy };
      });
      return;
    }

    // Find nearest data point
    let minDist = Infinity, bestIdx = 0;
    const rect = canvasRef.current.getBoundingClientRect();
    const pw = rect.width - pad.l - pad.r, ph = rect.height - pad.t - pad.b;
    const { xMin, xMax, yMin, yMax } = bounds;
    const xR = xMax - xMin, yR = yMax - yMin;
    data.x.forEach((xv, i) => {
      const px = pad.l + ((xv - xMin) / xR) * pw;
      const py = pad.t + ph - ((data.y[i] - yMin) / yR) * ph;
      const d = (coords.mx - px) ** 2 + (coords.my - py) ** 2;
      if (d < minDist) { minDist = d; bestIdx = i; }
    });

    const xv = data.x[bestIdx], yv = data.y[bestIdx];
    const px = pad.l + ((xv - xMin) / xR) * pw;
    const py = pad.t + ph - ((yv - yMin) / yR) * ph;
    setCursor({ x: xv, y: yv, idx: bestIdx, px, py });
  }, [data, bounds, dragging, getPlotCoords, getDataBounds, pad]);

  const onWheel = useCallback((e) => {
    e.preventDefault();
    const coords = getPlotCoords(e);
    if (!coords) return;
    const factor = e.deltaY > 0 ? 1.15 : 0.87;
    const b = viewBox || getDataBounds();
    const cx = coords.x, cy = coords.y;
    setViewBox({
      xMin: cx + (b.xMin - cx) * factor,
      xMax: cx + (b.xMax - cx) * factor,
      yMin: cy + (b.yMin - cy) * factor,
      yMax: cy + (b.yMax - cy) * factor,
    });
  }, [viewBox, getPlotCoords, getDataBounds]);

  const onMouseDown = useCallback((e) => {
    const coords = getPlotCoords(e);
    if (coords) setDragging(coords);
  }, [getPlotCoords]);

  const onMouseUp = useCallback(() => setDragging(null), []);

  const resetZoom = useCallback(() => setViewBox(null), []);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', cursor: dragging ? 'grabbing' : 'crosshair' }}
        onMouseMove={onMouseMove}
        onMouseDown={onMouseDown}
        onMouseUp={onMouseUp}
        onMouseLeave={() => { setCursor(null); setDragging(null); }}
        onWheel={onWheel}
      />
      {viewBox && (
        <button onClick={resetZoom}
          style={{ position: 'absolute', top: 4, right: 4, fontSize: 9, padding: '2px 8px',
            background: '#333', color: '#aaa', border: '1px solid #555', borderRadius: 4, cursor: 'pointer' }}>
          Reset Zoom
        </button>
      )}
    </div>
  );
}
