import React, { useRef, useEffect } from 'react';

export default function BodePlot({ data }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!data?.frequencies || !ref.current) return;
    const c = ref.current, ctx = c.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = c.getBoundingClientRect();
    c.width = rect.width * dpr; c.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width, h = rect.height;
    const pad = { t: 16, r: 50, b: 36, l: 52 };
    const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;

    const freq = data.frequencies;
    const logF = freq.map(f => Math.log10(f));
    const mag = freq.map((_, i) => Math.sqrt(data.Z_real[i] ** 2 + data.Z_imag[i] ** 2));
    const phase = freq.map((_, i) => Math.atan2(data.Z_imag[i], data.Z_real[i]) * 180 / Math.PI);
    const logMag = mag.map(m => Math.log10(m));

    const xMin = Math.min(...logF), xMax = Math.max(...logF);
    const yMinM = Math.min(...logMag), yMaxM = Math.max(...logMag);
    const yMinP = Math.min(...phase, -90), yMaxP = Math.max(...phase, 0);
    const xR = (xMax - xMin) || 1;
    const yRM = (yMaxM - yMinM) || 1, yRP = (yMaxP - yMinP) || 1;

    const sx = v => pad.l + ((v - xMin) / xR) * pw;
    const syM = v => pad.t + ph - ((v - yMinM) / yRM) * ph;
    const syP = v => pad.t + ph - ((v - yMinP) / yRP) * ph;

    ctx.clearRect(0, 0, w, h);

    // Grid
    ctx.strokeStyle = '#2a2d32'; ctx.lineWidth = 0.5;
    for (let i = 0; i <= 6; i++) {
      const x = pad.l + (pw / 6) * i, y = pad.t + (ph / 6) * i;
      ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ph); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + pw, y); ctx.stroke();
    }
    ctx.strokeStyle = '#3a3d44'; ctx.lineWidth = 1;
    ctx.strokeRect(pad.l, pad.t, pw, ph);

    // |Z| trace (left axis)
    ctx.strokeStyle = '#4a9eff'; ctx.lineWidth = 1.5; ctx.beginPath();
    logF.forEach((lf, i) => i === 0 ? ctx.moveTo(sx(lf), syM(logMag[i])) : ctx.lineTo(sx(lf), syM(logMag[i])));
    ctx.stroke();

    // Phase trace (right axis)
    ctx.strokeStyle = '#ffa726'; ctx.lineWidth = 1.5; ctx.beginPath();
    logF.forEach((lf, i) => i === 0 ? ctx.moveTo(sx(lf), syP(phase[i])) : ctx.lineTo(sx(lf), syP(phase[i])));
    ctx.stroke();

    // X-axis labels
    ctx.fillStyle = '#6b7280'; ctx.font = '10px Inter, sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('log₁₀(f / Hz)', pad.l + pw / 2, h - 4);
    ctx.fillStyle = '#555a62'; ctx.font = '9px monospace';
    for (let x = Math.ceil(xMin); x <= Math.floor(xMax); x++) {
      ctx.fillText(`10^${x}`, sx(x), pad.t + ph + 14);
    }

    // Left axis (|Z|) labels
    ctx.fillStyle = '#4a9eff'; ctx.font = '9px monospace'; ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const v = yMinM + yRM / 4 * i;
      ctx.fillText(`10^${v.toFixed(1)}`, pad.l - 4, syM(v) + 3);
    }
    ctx.save(); ctx.translate(10, pad.t + ph / 2); ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center'; ctx.fillText('log |Z| / Ω', 0, 0); ctx.restore();

    // Right axis (phase) labels
    ctx.fillStyle = '#ffa726'; ctx.font = '9px monospace'; ctx.textAlign = 'left';
    for (let i = 0; i <= 4; i++) {
      const v = yMinP + yRP / 4 * i;
      ctx.fillText(`${v.toFixed(0)}°`, pad.l + pw + 4, syP(v) + 3);
    }
    ctx.save(); ctx.translate(w - 6, pad.t + ph / 2); ctx.rotate(Math.PI / 2);
    ctx.textAlign = 'center'; ctx.fillText('Phase / °', 0, 0); ctx.restore();

    // Legend
    ctx.textAlign = 'left'; ctx.font = '9px monospace';
    ctx.fillStyle = '#4a9eff'; ctx.fillRect(pad.l + 8, pad.t + 6, 14, 3);
    ctx.fillStyle = '#aaa'; ctx.fillText('|Z|', pad.l + 26, pad.t + 10);
    ctx.fillStyle = '#ffa726'; ctx.fillRect(pad.l + 8, pad.t + 18, 14, 3);
    ctx.fillStyle = '#aaa'; ctx.fillText('Phase', pad.l + 26, pad.t + 22);
  }, [data]);

  return <canvas ref={ref} style={{ width: '100%', height: '100%' }} />;
}
