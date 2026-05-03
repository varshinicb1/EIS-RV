import React, { useState, useCallback, useRef } from 'react';

/**
 * Data Import/Export panel — loads real experimental CSV/JSON data
 * for overlay comparison against simulations.
 */

const SUPPORTED_FORMATS = [
  { ext: '.csv', desc: 'Comma-separated values (Gamry, CH Instruments, etc.)' },
  { ext: '.json', desc: 'JSON export from RĀMAN Studio' },
  { ext: '.dta', desc: 'Gamry DTA format (text section)' },
  { ext: '.mpt', desc: 'BioLogic EC-Lab MPT format' },
  { ext: '.z', desc: 'ZView / Scribner impedance format' },
  { ext: '.txt', desc: 'Tab/space delimited text data' },
];

function parseCSV(text) {
  const lines = text.trim().split('\n').filter(l => l.trim() && !l.startsWith('#'));
  if (lines.length < 2) return null;

  // Detect separator
  const sep = lines[0].includes('\t') ? '\t' : lines[0].includes(';') ? ';' : ',';
  const headers = lines[0].split(sep).map(h => h.trim().replace(/"/g, ''));
  const rows = lines.slice(1).map(l => l.split(sep).map(v => parseFloat(v.trim())));
  const validRows = rows.filter(r => r.every(v => !isNaN(v)));

  const columns = {};
  headers.forEach((h, i) => {
    columns[h] = validRows.map(r => r[i]);
  });

  return { headers, columns, nRows: validRows.length, nCols: headers.length };
}

function guessDataType(headers) {
  const h = headers.map(s => s.toLowerCase());
  if (h.some(s => s.includes('z_real') || s.includes("z'") || s.includes('zre')))
    return 'EIS';
  if (h.some(s => s.includes('potential') || s.includes('e_v') || s.includes('voltage')))
    return h.some(s => s.includes('current') || s.includes('i_a')) ? 'CV' : 'GCD';
  if (h.some(s => s.includes('capacity') || s.includes('soc')))
    return 'Battery';
  if (h.some(s => s.includes('freq') || s.includes('frequency')))
    return 'EIS';
  return 'Unknown';
}

function DataPreviewPlot({ data, xCol, yCol }) {
  const ref = useRef(null);

  React.useEffect(() => {
    if (!ref.current || !data || !xCol || !yCol) return;
    const canvas = ref.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width, H = rect.height;
    const pad = { t: 12, r: 16, b: 36, l: 52 };
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;

    ctx.fillStyle = '#111214';
    ctx.fillRect(0, 0, W, H);

    const xArr = data.columns[xCol];
    const yArr = data.columns[yCol];
    if (!xArr || !yArr) return;

    const xMin = Math.min(...xArr), xMax = Math.max(...xArr);
    const yMin = Math.min(...yArr), yMax = Math.max(...yArr);
    const xRange = (xMax - xMin) || 1, yRange = (yMax - yMin) || 1;

    // Grid
    ctx.strokeStyle = '#1e2024'; ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = pad.t + ph * i / 5;
      ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + pw, y); ctx.stroke();
      const x = pad.l + pw * i / 5;
      ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ph); ctx.stroke();
    }
    ctx.strokeStyle = '#383c42'; ctx.lineWidth = 1;
    ctx.strokeRect(pad.l, pad.t, pw, ph);

    // Ticks
    ctx.fillStyle = '#6b7280'; ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (let i = 0; i <= 4; i++) {
      const val = yMax - yRange * i / 4;
      const label = Math.abs(val) > 1000 || (Math.abs(val) < 0.01 && val !== 0) ? val.toExponential(1) : val.toFixed(2);
      ctx.fillText(label, pad.l - 5, pad.t + ph * i / 4);
    }
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (let i = 0; i <= 4; i++) {
      const val = xMin + xRange * i / 4;
      const label = Math.abs(val) > 1000 || (Math.abs(val) < 0.01 && val !== 0) ? val.toExponential(1) : val.toFixed(2);
      ctx.fillText(label, pad.l + pw * i / 4, pad.t + ph + 5);
    }

    // Axis labels
    ctx.fillStyle = '#9aa0a6'; ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(xCol, pad.l + pw / 2, H - 4);
    ctx.save(); ctx.translate(12, pad.t + ph / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText(yCol, 0, 0);
    ctx.restore();

    // Data points
    const step = Math.max(1, Math.floor(xArr.length / 2000));
    ctx.fillStyle = '#ffa726';
    for (let i = 0; i < xArr.length; i += step) {
      const x = pad.l + ((xArr[i] - xMin) / xRange) * pw;
      const y = pad.t + ((yMax - yArr[i]) / yRange) * ph;
      ctx.beginPath(); ctx.arc(x, y, 2.5, 0, Math.PI * 2); ctx.fill();
    }

    // Connect with line
    ctx.strokeStyle = '#ffa726'; ctx.lineWidth = 1; ctx.globalAlpha = 0.5;
    ctx.beginPath();
    for (let i = 0; i < xArr.length; i += step) {
      const x = pad.l + ((xArr[i] - xMin) / xRange) * pw;
      const y = pad.t + ((yMax - yArr[i]) / yRange) * ph;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  }, [data, xCol, yCol]);

  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />;
}

export default function DataImportPanel() {
  const [fileData, setFileData] = useState(null);
  const [fileName, setFileName] = useState('');
  const [xCol, setXCol] = useState('');
  const [yCol, setYCol] = useState('');
  const [dataType, setDataType] = useState('');
  const fileInputRef = useRef(null);

  const handleFile = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target.result;
      const parsed = parseCSV(text);
      if (parsed) {
        setFileData(parsed);
        const guess = guessDataType(parsed.headers);
        setDataType(guess);
        // Auto-select axes based on guess
        if (guess === 'EIS') {
          const zr = parsed.headers.find(h => /z.?re|z'/i.test(h));
          const zi = parsed.headers.find(h => /z.?im|z''/i.test(h));
          if (zr) setXCol(zr);
          if (zi) setYCol(zi);
        } else if (parsed.headers.length >= 2) {
          setXCol(parsed.headers[0]);
          setYCol(parsed.headers[1]);
        }
      }
    };
    reader.readAsText(file);
  }, []);

  const exportJSON = useCallback(() => {
    if (!fileData) return;
    const blob = new Blob([JSON.stringify(fileData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = fileName.replace(/\.[^.]+$/, '.json'); a.click();
    URL.revokeObjectURL(url);
  }, [fileData, fileName]);

  return (
    <div className="simulation-layout animate-in">
      {/* Left panel — file selection */}
      <div className="card" style={{ overflow: 'auto' }}>
        <div className="card-header">
          <div>
            <div className="card-title">Data Import</div>
            <div className="card-subtitle">Load experimental data files</div>
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <input type="file" ref={fileInputRef}
            accept=".csv,.json,.txt,.dta,.mpt,.z"
            style={{ display: 'none' }}
            onChange={handleFile} />
          <button className="btn btn-primary" style={{ width: '100%' }}
            onClick={() => fileInputRef.current?.click()}>
            Select File
          </button>
        </div>

        {fileName && (
          <div className="card" style={{ background: 'var(--bg-elevated)', marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-data)', color: 'var(--text-primary)', marginBottom: 4 }}>
              {fileName}
            </div>
            {fileData && (
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>
                <div>Rows: <span className="mono">{fileData.nRows}</span></div>
                <div>Columns: <span className="mono">{fileData.nCols}</span></div>
                <div>Type: <span className="mono" style={{
                  color: dataType === 'Unknown' ? 'var(--color-standby)' : 'var(--color-success)'
                }}>{dataType}</span></div>
              </div>
            )}
          </div>
        )}

        {fileData && (
          <>
            <div className="input-group">
              <span className="input-label">X-Axis Column</span>
              <select className="input-field" value={xCol}
                onChange={e => setXCol(e.target.value)}>
                {fileData.headers.map(h => <option key={h} value={h}>{h}</option>)}
              </select>
            </div>
            <div className="input-group">
              <span className="input-label">Y-Axis Column</span>
              <select className="input-field" value={yCol}
                onChange={e => setYCol(e.target.value)}>
                {fileData.headers.map(h => <option key={h} value={h}>{h}</option>)}
              </select>
            </div>

            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <button className="btn btn-secondary btn-lg" style={{ flex: 1 }} onClick={exportJSON}>
                Export JSON
              </button>
              <button className="btn btn-primary btn-lg" style={{ flex: 1 }}
                onClick={() => {
                  // Store data for overlay in EIS/CV panels via sessionStorage
                  const overlayData = JSON.stringify({
                    type: dataType,
                    x: fileData.columns[xCol],
                    y: fileData.columns[yCol],
                    xLabel: xCol,
                    yLabel: yCol,
                  });
                  sessionStorage.setItem('RAMAN_OVERLAY_DATA', overlayData);
                  window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
                    detail: {
                      kind: 'ok',
                      text: `Data stored for overlay. Switch to the ${dataType} panel to see comparison.`,
                    },
                  }));
                }}>
                Overlay in {dataType || 'Sim'}
              </button>
            </div>
          </>
        )}

        <div style={{ marginTop: 16 }}>
          <div className="card-title" style={{ fontSize: 11, marginBottom: 6 }}>Supported Formats</div>
          <table className="data-table">
            <thead><tr><th>Format</th><th>Source</th></tr></thead>
            <tbody>
              {SUPPORTED_FORMATS.map(f => (
                <tr key={f.ext}>
                  <td className="mono">{f.ext}</td>
                  <td>{f.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Right panel — preview */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="plot-container" style={{ flex: 1 }}>
          <div className="plot-header">
            <span className="plot-title">Data Preview</span>
            {fileData && <span className="input-unit">{fileData.nRows} points</span>}
          </div>
          <div className="plot-canvas">
            {fileData && xCol && yCol ? (
              <DataPreviewPlot data={fileData} xCol={xCol} yCol={yCol} />
            ) : (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                height: '100%', color: 'var(--text-disabled)', fontSize: 11,
                fontFamily: 'var(--font-data)',
              }}>
                {fileData ? 'Select X and Y columns to plot' : 'No file loaded — select a data file to preview'}
              </div>
            )}
          </div>
        </div>

        {fileData && (
          <div className="card">
            <div className="card-title" style={{ marginBottom: 8 }}>Column Summary</div>
            <table className="data-table">
              <thead>
                <tr><th>Column</th><th>Min</th><th>Max</th><th>Mean</th><th>Points</th></tr>
              </thead>
              <tbody>
                {fileData.headers.map(h => {
                  const col = fileData.columns[h];
                  const min = Math.min(...col);
                  const max = Math.max(...col);
                  const mean = col.reduce((a, b) => a + b, 0) / col.length;
                  const fmt = v => Math.abs(v) > 1000 || (Math.abs(v) < 0.01 && v !== 0) ? v.toExponential(2) : v.toFixed(3);
                  return (
                    <tr key={h}>
                      <td className="mono" style={{ fontWeight: 500 }}>{h}</td>
                      <td className="mono">{fmt(min)}</td>
                      <td className="mono">{fmt(max)}</td>
                      <td className="mono">{fmt(mean)}</td>
                      <td className="mono">{col.length}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
