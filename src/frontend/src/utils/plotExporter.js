/**
 * RĀMAN Studio — Publication-Quality Plot Exporter
 * ==================================================
 * Based on ECS (Electrochemical Society), IUPAC, and IEEE standards:
 * 
 * NYQUIST PLOT:
 *   - 1:1 aspect ratio (orthonormal axes) — ECS requirement
 *   - X-axis: Z' / Ω (or Ω·cm²)
 *   - Y-axis: -Z'' / Ω (inverted imaginary)
 *   - Data points as discrete markers, fit lines as solid curves
 *   - No connecting lines on raw data (ECS guideline)
 *   - Frequency labels on key points
 *   
 * BODE PLOT:
 *   - Dual-axis: |Z| on log-log, Phase on semi-log
 *   - X-axis: Frequency / Hz (log scale)
 *   - Sans-serif font (Arial/Inter), 300+ DPI equivalent
 *
 * CV PLOT (IUPAC Convention):
 *   - X-axis: E / V vs. Ag/AgCl (or reference electrode)
 *   - Y-axis: I / μA (or j / mA·cm⁻²)
 *   - Scan direction arrows
 *   - Anodic scan goes right-to-left (IUPAC American convention)
 */

const EXPORT_DPI = 4;  // 4x for ~300dpi at typical screen sizes
const FONT_FAMILY = 'Inter, Arial, Helvetica, sans-serif';
const DATA_FONT = 'JetBrains Mono, Consolas, monospace';
const WATERMARK = 'RĀMAN Studio by VidyuthLabs';

/**
 * Export a canvas plot as a high-resolution PNG.
 * @param {HTMLCanvasElement} canvas - The visible canvas
 * @param {string} filename - Output filename
 * @param {number} scale - DPI multiplier (default 4x)
 */
export function exportCanvasAsPNG(canvas, filename = 'plot.png', scale = EXPORT_DPI) {
  const exportCanvas = document.createElement('canvas');
  const ctx = exportCanvas.getContext('2d');
  exportCanvas.width = canvas.width * scale / (window.devicePixelRatio || 1);
  exportCanvas.height = canvas.height * scale / (window.devicePixelRatio || 1);
  
  // Draw at high resolution
  ctx.drawImage(canvas, 0, 0, exportCanvas.width, exportCanvas.height);
  
  // Add watermark
  ctx.fillStyle = 'rgba(255,255,255,0.15)';
  ctx.font = `${10 * scale}px ${FONT_FAMILY}`;
  ctx.textAlign = 'right';
  ctx.fillText(WATERMARK, exportCanvas.width - 10 * scale, exportCanvas.height - 8 * scale);
  
  exportCanvas.toBlob(blob => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }, 'image/png');
}

/**
 * Render a publication-quality Nyquist plot to a canvas.
 * Follows ECS guidelines: 1:1 aspect ratio, no connecting lines on raw data.
 */
export function renderNyquistPublication(ctx, w, h, data, options = {}) {
  const { showFit = false, fitData = null, title = '', areaCorrect = false, area_cm2 = 1 } = options;
  const pad = { top: 30, right: 24, bottom: 48, left: 64 };
  const pw = w - pad.left - pad.right;
  const ph = h - pad.top - pad.bottom;

  // Clear
  ctx.fillStyle = '#000000';
  ctx.fillRect(0, 0, w, h);

  if (!data?.Z_real?.length) {
    ctx.fillStyle = '#555';
    ctx.font = `12px ${FONT_FAMILY}`;
    ctx.textAlign = 'center';
    ctx.fillText('No data — run simulation first', w / 2, h / 2);
    return;
  }

  const aFactor = areaCorrect ? area_cm2 : 1;
  const unit = areaCorrect ? 'Ω·cm²' : 'Ω';
  const zr = data.Z_real.map(v => v * aFactor);
  const zi = data.Z_imag.map(v => -v * aFactor);

  // Compute ranges with 1:1 aspect ratio (ECS standard)
  let xMin = Math.min(...zr), xMax = Math.max(...zr);
  let yMin = Math.min(...zi, 0), yMax = Math.max(...zi);
  let xRange = xMax - xMin || 1;
  let yRange = yMax - yMin || 1;

  // Enforce 1:1 aspect ratio
  const aspectData = xRange / yRange;
  const aspectPlot = pw / ph;
  if (aspectData > aspectPlot) {
    // Data is wider than plot — expand y range
    const newYRange = xRange / aspectPlot;
    const yMid = (yMin + yMax) / 2;
    yMin = yMid - newYRange / 2;
    yMax = yMid + newYRange / 2;
    yRange = newYRange;
  } else {
    // Data is taller — expand x range
    const newXRange = yRange * aspectPlot;
    const xMid = (xMin + xMax) / 2;
    xMin = xMid - newXRange / 2;
    xMax = xMid + newXRange / 2;
    xRange = newXRange;
  }

  // Add 5% padding
  const xPad = xRange * 0.05, yPad = yRange * 0.05;
  xMin -= xPad; xMax += xPad; xRange = xMax - xMin;
  yMin -= yPad; yMax += yPad; yRange = yMax - yMin;

  const sx = v => pad.left + ((v - xMin) / xRange) * pw;
  const sy = v => pad.top + ph - ((v - yMin) / yRange) * ph;

  // Grid
  ctx.strokeStyle = '#1a1c20';
  ctx.lineWidth = 0.5;
  const nGrid = 8;
  for (let i = 0; i <= nGrid; i++) {
    const x = pad.left + (pw / nGrid) * i;
    const y = pad.top + (ph / nGrid) * i;
    ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, pad.top + ph); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + pw, y); ctx.stroke();
  }

  // Axis frame
  ctx.strokeStyle = '#333';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(pad.left, pad.top, pw, ph);

  // Tick marks and values
  ctx.fillStyle = '#888';
  ctx.font = `10px ${DATA_FONT}`;

  // X ticks
  ctx.textAlign = 'center';
  for (let i = 0; i <= 5; i++) {
    const val = xMin + (xRange / 5) * i;
    const x = sx(val);
    ctx.beginPath(); ctx.moveTo(x, pad.top + ph); ctx.lineTo(x, pad.top + ph + 4); ctx.strokeStyle = '#555'; ctx.stroke();
    ctx.fillText(formatTick(val), x, pad.top + ph + 16);
  }

  // Y ticks
  ctx.textAlign = 'right';
  for (let i = 0; i <= 5; i++) {
    const val = yMin + (yRange / 5) * i;
    const y = sy(val);
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left - 4, y); ctx.strokeStyle = '#555'; ctx.stroke();
    ctx.fillText(formatTick(val), pad.left - 8, y + 3);
  }

  // Axis labels (publication standard: Quantity / Unit)
  ctx.fillStyle = '#aaa';
  ctx.font = `12px ${FONT_FAMILY}`;
  ctx.textAlign = 'center';
  ctx.fillText(`Z' / ${unit}`, pad.left + pw / 2, h - 6);

  ctx.save();
  ctx.translate(14, pad.top + ph / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(`−Z'' / ${unit}`, 0, 0);
  ctx.restore();

  // Title
  if (title) {
    ctx.fillStyle = '#ccc';
    ctx.font = `bold 13px ${FONT_FAMILY}`;
    ctx.textAlign = 'center';
    ctx.fillText(title, w / 2, 16);
  }

  // Fit line (if provided — solid line per ECS)
  if (showFit && fitData) {
    ctx.strokeStyle = '#ef5350';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([]);
    ctx.beginPath();
    const fzr = fitData.Z_real.map(v => v * aFactor);
    const fzi = fitData.Z_imag.map(v => -v * aFactor);
    for (let i = 0; i < fzr.length; i++) {
      i === 0 ? ctx.moveTo(sx(fzr[i]), sy(fzi[i])) : ctx.lineTo(sx(fzr[i]), sy(fzi[i]));
    }
    ctx.stroke();
  }

  // Data points — discrete markers only (ECS guideline: no connecting lines on raw data)
  const markerInterval = Math.max(1, Math.floor(zr.length / 40));
  for (let i = 0; i < zr.length; i += markerInterval) {
    const x = sx(zr[i]), y = sy(zi[i]);
    // Open circle marker
    ctx.strokeStyle = '#4a9eff';
    ctx.lineWidth = 1.5;
    ctx.fillStyle = 'rgba(74, 158, 255, 0.3)';
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  // Frequency labels on select points
  if (data.frequencies?.length) {
    const freqLabels = [0, Math.floor(zr.length * 0.25), Math.floor(zr.length * 0.5), Math.floor(zr.length * 0.75), zr.length - 1];
    ctx.fillStyle = '#76b900';
    ctx.font = `8px ${DATA_FONT}`;
    ctx.textAlign = 'left';
    freqLabels.forEach(idx => {
      if (idx >= zr.length) return;
      const f = data.frequencies[idx];
      const label = f >= 1000 ? `${(f / 1000).toFixed(1)}kHz` : f >= 1 ? `${f.toFixed(1)}Hz` : `${(f * 1000).toFixed(1)}mHz`;
      ctx.fillText(label, sx(zr[idx]) + 5, sy(zi[idx]) - 5);
    });
  }

  // Watermark
  ctx.fillStyle = 'rgba(255,255,255,0.08)';
  ctx.font = `9px ${FONT_FAMILY}`;
  ctx.textAlign = 'right';
  ctx.fillText(WATERMARK, w - 8, h - 4);
}

function formatTick(val) {
  if (Math.abs(val) >= 1e4) return val.toExponential(1);
  if (Math.abs(val) >= 100) return val.toFixed(0);
  if (Math.abs(val) >= 1) return val.toFixed(1);
  return val.toExponential(1);
}

/**
 * Export simulation data as publication-ready CSV.
 */
export function exportDataCSV(data, filename, metadata = {}) {
  const lines = [];
  // Header with metadata
  lines.push(`# ${WATERMARK}`);
  lines.push(`# Generated: ${new Date().toISOString()}`);
  Object.entries(metadata).forEach(([k, v]) => lines.push(`# ${k}: ${v}`));
  lines.push('#');
  
  if (data.frequencies) {
    lines.push('Frequency_Hz,Z_real_Ohm,Z_imag_Ohm,Z_mag_Ohm,Phase_deg');
    for (let i = 0; i < data.frequencies.length; i++) {
      const zr = data.Z_real[i], zi = data.Z_imag[i];
      const mag = Math.sqrt(zr * zr + zi * zi);
      const phase = Math.atan2(zi, zr) * 180 / Math.PI;
      lines.push(`${data.frequencies[i]},${zr},${zi},${mag},${phase}`);
    }
  }
  
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
