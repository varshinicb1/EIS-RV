/**
 * Scientific Plot Styling - Publication-Ready White Theme
 * 
 * Consistent styling for all plots across RĀMAN Studio.
 * Follows Nature/Science journal figure guidelines.
 */

export const SCIENTIFIC_PLOT_STYLE = {
  // Colors
  background: '#FFFFFF',
  gridColor: '#E5E7EB',
  axisColor: '#6B7280',
  textColor: '#374151',
  textPrimaryColor: '#111827',
  
  // Data colors (colorblind-friendly palette)
  dataColors: {
    primary: '#2563EB',    // Blue
    secondary: '#DC2626',  // Red
    tertiary: '#059669',   // Green
    quaternary: '#7C3AED', // Purple
    quinary: '#EA580C',    // Orange
  },
  
  // Line styles
  lineWidth: 2,
  gridLineWidth: 0.5,
  axisLineWidth: 1.5,
  
  // Fonts (Times New Roman for publication)
  fontFamily: '"Times New Roman", Times, serif',
  fontSize: {
    title: 14,
    axis: 12,
    tick: 10,
    legend: 10,
  },
  
  // Padding
  padding: {
    top: 40,
    right: 30,
    bottom: 60,
    left: 70,
  },
};

/**
 * Setup canvas for scientific plotting
 */
export function setupScientificCanvas(canvas, width, height) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.scale(dpr, dpr);
  canvas.style.width = width + 'px';
  canvas.style.height = height + 'px';
  
  // White background
  ctx.fillStyle = SCIENTIFIC_PLOT_STYLE.background;
  ctx.fillRect(0, 0, width, height);
  
  return { ctx, width, height };
}

/**
 * Draw scientific axes with grid
 */
export function drawScientificAxes(ctx, width, height, xLabel, yLabel, xRange, yRange, options = {}) {
  const style = SCIENTIFIC_PLOT_STYLE;
  const pad = options.padding || style.padding;
  const pw = width - pad.left - pad.right;
  const ph = height - pad.top - pad.bottom;
  
  // Grid
  ctx.strokeStyle = style.gridColor;
  ctx.lineWidth = style.gridLineWidth;
  ctx.setLineDash([2, 2]);
  
  // Vertical grid lines
  for (let i = 0; i <= 10; i++) {
    const x = pad.left + (pw * i / 10);
    ctx.beginPath();
    ctx.moveTo(x, pad.top);
    ctx.lineTo(x, pad.top + ph);
    ctx.stroke();
  }
  
  // Horizontal grid lines
  for (let i = 0; i <= 10; i++) {
    const y = pad.top + (ph * i / 10);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(pad.left + pw, y);
    ctx.stroke();
  }
  
  ctx.setLineDash([]);
  
  // Axes
  ctx.strokeStyle = style.axisColor;
  ctx.lineWidth = style.axisLineWidth;
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + ph);
  ctx.lineTo(pad.left + pw, pad.top + ph);
  ctx.stroke();
  
  // Axis labels
  ctx.fillStyle = style.textPrimaryColor;
  ctx.font = `${style.fontSize.axis}px ${style.fontFamily}`;
  ctx.textAlign = 'center';
  ctx.fillText(xLabel, pad.left + pw / 2, height - 15);
  
  ctx.save();
  ctx.translate(20, pad.top + ph / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(yLabel, 0, 0);
  ctx.restore();
  
  // Tick labels
  ctx.fillStyle = style.textColor;
  ctx.font = `${style.fontSize.tick}px ${style.fontFamily}`;
  
  // X-axis ticks
  ctx.textAlign = 'center';
  for (let i = 0; i <= 10; i++) {
    const x = pad.left + (pw * i / 10);
    const val = xRange[0] + (xRange[1] - xRange[0]) * i / 10;
    ctx.fillText(val.toFixed(val < 10 ? 1 : 0), x, pad.top + ph + 20);
  }
  
  // Y-axis ticks
  ctx.textAlign = 'right';
  for (let i = 0; i <= 10; i++) {
    const y = pad.top + ph - (ph * i / 10);
    const val = yRange[0] + (yRange[1] - yRange[0]) * i / 10;
    ctx.fillText(val.toFixed(val < 10 ? 1 : 0), pad.left - 10, y + 4);
  }
}

/**
 * Draw data line
 */
export function drawDataLine(ctx, xData, yData, xRange, yRange, width, height, color, options = {}) {
  const style = SCIENTIFIC_PLOT_STYLE;
  const pad = options.padding || style.padding;
  const pw = width - pad.left - pad.right;
  const ph = height - pad.top - pad.bottom;
  
  ctx.strokeStyle = color || style.dataColors.primary;
  ctx.lineWidth = options.lineWidth || style.lineWidth;
  ctx.beginPath();
  
  for (let i = 0; i < xData.length; i++) {
    const x = pad.left + ((xData[i] - xRange[0]) / (xRange[1] - xRange[0])) * pw;
    const y = pad.top + ph - ((yData[i] - yRange[0]) / (yRange[1] - yRange[0])) * ph;
    
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  
  ctx.stroke();
}

/**
 * Export canvas as PNG with white background
 */
export function exportScientificPlot(canvas, filename) {
  const link = document.createElement('a');
  link.download = filename || `plot_${Date.now()}.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
}
