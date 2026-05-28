import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Download, Sparkles, Brain, Info, Save, FolderOpen } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

// API helper
const API_BASE = '';

const apiCall = async (endpoint, options = {}) => {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
};

// LocalStorage keys
const STORAGE_KEYS = {
  ANALYSES: 'raman-saved-analyses',
  LAST_ANALYSIS: 'raman-last-analysis',
  USER_PROFILE: 'raman-profile',
};

const THEME = {
  cyan: 'var(--accent)',
  bg: '#020204',
  cardBg: 'rgba(5, 5, 5, 0.8)',
  success: '#00ff95',
  border: 'rgba(255, 255, 255, 0.08)',
  textPrimary: '#ffffff',
  textSecondary: '#a0a0a0',
  textTertiary: '#606060',
};

// Research-grade plot renderer with WHITE BACKGROUND for publication
function renderSpectrumPlot(ctx, width, height, data, options = {}) {
  const { wavenumber, intensity, corrected_intensity, baseline, peaks, showPeaks, showBaseline, showFit, cosmicRay, fourier, voigt } = options;
  
  // SCIENTIFIC WHITE THEME - Publication ready
  const bgColor = '#FFFFFF';
  const gridColor = '#E5E7EB';
  const axisColor = '#6B7280';
  const textColor = '#374151';
  const textPrimaryColor = '#111827';
  const lineColor = '#2563EB';  // Blue for data
  const fillColorTop = 'rgba(37,99,235,0.3)';
  const fillColorBottom = 'rgba(37,99,235,0.05)';
  
  ctx.fillStyle = bgColor;
  ctx.fillRect(0, 0, width, height);
  
  if (!wavenumber?.length || !intensity?.length) return;
  
  const pad = { l: 70, r: 30, t: 40, b: 60 };
  const pw = width - pad.l - pad.r;
  const ph = height - pad.t - pad.b;
  
  const xMin = Math.min(...wavenumber);
  const xMax = Math.max(...wavenumber);
  
  // Use corrected intensity if available, otherwise raw intensity
  const displayIntensity = corrected_intensity?.length ? corrected_intensity : intensity;
  const yMin = Math.min(...displayIntensity);
  const yMax = Math.max(...displayIntensity);
  const yRange = yMax - yMin;
  
  const toX = v => pad.l + ((v - xMin) / (xMax - xMin)) * pw;
  const toY = v => pad.t + ph - ((v - yMin) / yRange) * ph;
  
  // Grid
  ctx.strokeStyle = gridColor;
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 10; i++) {
    const x = pad.l + (pw * i) / 10;
    ctx.beginPath();
    ctx.moveTo(x, pad.t);
    ctx.lineTo(x, pad.t + ph);
    ctx.stroke();
  }
  for (let i = 0; i <= 5; i++) {
    const y = pad.t + (ph * i) / 5;
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(pad.l + pw, y);
    ctx.stroke();
  }
  
  // Axes
  ctx.strokeStyle = axisColor;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(pad.l, pad.t);
  ctx.lineTo(pad.l, pad.t + ph);
  ctx.lineTo(pad.l + pw, pad.t + ph);
  ctx.stroke();
  
  // Draw baseline if available and requested
  if (showBaseline && baseline?.length) {
    ctx.beginPath();
    ctx.strokeStyle = '#00ff95';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 3]);
    wavenumber.forEach((wn, i) => {
      if (i === 0) ctx.moveTo(toX(wn), toY(baseline[i]));
      else ctx.lineTo(toX(wn), toY(baseline[i]));
    });
    ctx.stroke();
    ctx.setLineDash([]);
  }
  
  // Spectrum fill (use corrected intensity)
  ctx.beginPath();
  ctx.moveTo(toX(wavenumber[0]), toY(yMin));
  wavenumber.forEach((wn, i) => ctx.lineTo(toX(wn), toY(displayIntensity[i])));
  ctx.lineTo(toX(wavenumber[wavenumber.length - 1]), toY(yMin));
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + ph);
  grad.addColorStop(0, fillColorTop);
  grad.addColorStop(1, fillColorBottom);
  ctx.fillStyle = grad;
  ctx.fill();
  
  // Spectrum line (use corrected intensity)
  ctx.beginPath();
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = 2;
  wavenumber.forEach((wn, i) => {
    if (i === 0) ctx.moveTo(toX(wn), toY(displayIntensity[i]));
    else ctx.lineTo(toX(wn), toY(displayIntensity[i]));
  });
  ctx.stroke();
  
  // Peak markers (use corrected intensity for peak positions)
  if (showPeaks && peaks?.length) {
    peaks.forEach(p => {
      const px = toX(p.position_cm);
      // Find the intensity at the peak position in the displayed data
      const peakIndex = wavenumber.findIndex(wn => Math.abs(wn - p.position_cm) < 1);
      const peakIntensity = peakIndex >= 0 ? displayIntensity[peakIndex] : p.intensity;
      const py = toY(peakIntensity);
      
      // Draw different marker for fitted peaks
      if (showFit && p.fit_position_cm) {
        // Draw fitted peak position with different color
        const fitPx = toX(p.fit_position_cm);
        const fitPy = toY(peakIntensity); // Use same intensity for now
        
        // Draw cross for fitted position
        ctx.beginPath();
        ctx.strokeStyle = '#00ff95';
        ctx.lineWidth = 2;
        ctx.moveTo(fitPx - 5, fitPy - 5);
        ctx.lineTo(fitPx + 5, fitPy + 5);
        ctx.moveTo(fitPx + 5, fitPy - 5);
        ctx.lineTo(fitPx - 5, fitPy + 5);
        ctx.stroke();
        
        // Draw fitted peak label
        ctx.font = 'bold 10px monospace';
        ctx.fillStyle = '#00ff95';
        ctx.textAlign = 'center';
        ctx.fillText(`F:${p.fit_position_cm?.toFixed(1)}`, fitPx, fitPy - 15);
      }
      
      // Draw regular peak marker
      ctx.beginPath();
      ctx.arc(px, py, 6, 0, Math.PI * 2);
      ctx.fillStyle = '#ff0d0d';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
      
      // Peak label
      ctx.font = 'bold 10px monospace';
      ctx.fillStyle = '#fff';
      ctx.textAlign = 'center';
      ctx.fillText(`${p.position_cm.toFixed(1)}`, px, py - 12);
    });
  }
  
  // Axis labels
  ctx.font = '12px system-ui';
  ctx.fillStyle = textColor;
  ctx.textAlign = 'center';
  
  // X-axis ticks
  for (let i = 0; i <= 5; i++) {
    const val = xMin + ((xMax - xMin) * i) / 5;
    const x = pad.l + (pw * i) / 5;
    ctx.fillText(val.toFixed(0), x, pad.t + ph + 20);
  }
  ctx.fillText('Raman Shift (cm⁻¹)', pad.l + pw / 2, pad.t + ph + 45);
  
  // Y-axis ticks
  ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    const val = yMin + (yRange * i) / 4;
    const y = pad.t + ph - (ph * i) / 4;
    ctx.fillText(val.toFixed(2), pad.l - 10, y + 4);
  }
  ctx.save();
  ctx.translate(15, pad.t + ph / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText('Intensity (a.u.)', 0, 0);
  ctx.restore();
  
  // Title
  ctx.font = 'bold 14px system-ui';
  ctx.fillStyle = textPrimaryColor;
  ctx.textAlign = 'left';
  ctx.fillText('Raman Spectrum Analysis', pad.l, 20);
  
  // Metadata
  ctx.font = '10px monospace';
  ctx.fillStyle = textColor;
  ctx.textAlign = 'right';
  const intensityType = corrected_intensity?.length ? 'Corrected' : 'Raw';
  let analysisStatus = `${wavenumber.length} pts · ${peaks?.length || 0} peaks · ${intensityType}`;
  
  // Add analysis options status
  if (cosmicRay) analysisStatus += ' · CR✓';
  if (fourier) analysisStatus += ' · FFT✓';
  if (voigt) analysisStatus += ' · Voigt✓';
  
  ctx.fillText(analysisStatus, width - pad.r, 20);
  
  // Add visual indicator for processing
  if (cosmicRay || fourier || voigt) {
    ctx.fillStyle = '#059669';
    ctx.font = 'bold 11px system-ui';
    ctx.textAlign = 'left';
    ctx.fillText('✓ PROCESSED', pad.l, 20);
  }
}

export default function UnifiedSpectroscopyPanel() {
  return <UnifiedSpectroscopyPanelContent />;
}

function UnifiedSpectroscopyPanelContent() {
  const canvasRef = useRef(null);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  
  // Get current theme
  const { theme: currentTheme } = useTheme();
  
  // Saved analyses
  const [savedAnalyses, setSavedAnalyses] = useState([]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [analysisName, setAnalysisName] = useState('');
  const [showLoadDialog, setShowLoadDialog] = useState(false);
  
  // Load saved analyses on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.ANALYSES);
      if (saved) {
        setSavedAnalyses(JSON.parse(saved));
      }
      
      // Try to restore last analysis
      const lastAnalysis = localStorage.getItem(STORAGE_KEYS.LAST_ANALYSIS);
      if (lastAnalysis) {
        const data = JSON.parse(lastAnalysis);
        setResult(data.result);
        setCosmicRay(data.options?.cosmicRay || false);
        setFourier(data.options?.fourier || false);
        setVoigt(data.options?.voigt || false);
      }
    } catch (e) {
      console.error('Failed to load saved data:', e);
    }
  }, []);
  
  // Display options
  const [showPeaks, setShowPeaks] = useState(true);
  const [showBaseline, setShowBaseline] = useState(false);
  const [showFit, setShowFit] = useState(false);
  const [showRawData, setShowRawData] = useState(false); // Toggle to show raw vs processed
  
  // Analysis options
  const [cosmicRay, setCosmicRay] = useState(false);
  const [fourier, setFourier] = useState(false);
  const [voigt, setVoigt] = useState(false);
  
  // AI analysis
  const [aiAnalysis, setAiAnalysis] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [apiKeyStatus, setApiKeyStatus] = useState({ configured: false });
  
  // Check API key status on mount
  useEffect(() => {
    (async () => {
      try {
        const r = await apiCall('/api/v2/settings/nvidia-key/status');
        setApiKeyStatus(r);
      } catch (e) {
        console.error('Failed to check API key status:', e);
      }
    })();
  }, []);
  
  // Auto-analyze on file upload
  const handleFileChange = useCallback(async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    
    setFile(f);
    setError(null);
    setLoading(true);
    setResult(null);
    setAiAnalysis(null);
    
    try {
      const formData = new FormData();
      formData.append('file', f);
      formData.append('cosmic_ray_removal', cosmicRay.toString());
      formData.append('fourier_filtering', fourier.toString());
      formData.append('voigt_fitting', voigt.toString());
      
      const res = await fetch(`${API_BASE}/api/v1/unified-spectroscopy/analyze`, {
        method: 'POST',
        body: formData,
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${res.status}`);
      }
      
      const data = await res.json();
      console.log('Analysis result:', data);
      
      // Verify we got processed data
      if (!data.corrected_intensity || data.corrected_intensity.length === 0) {
        console.warn('No corrected_intensity in response, using raw intensity');
      }
      
      setResult(data);
      
      // Save to localStorage
      try {
        localStorage.setItem(STORAGE_KEYS.LAST_ANALYSIS, JSON.stringify({
          result: data,
          options: { cosmicRay, fourier, voigt },
          timestamp: Date.now(),
        }));
      } catch (e) {
        console.error('Failed to save to localStorage:', e);
      }
    } catch (err) {
      setError(err.message || 'Analysis failed');
      console.error('Analysis error:', err);
    } finally {
      setLoading(false);
    }
  }, [cosmicRay, fourier, voigt]);
  
  // Reanalyze when options change
  const reanalyze = useCallback(async () => {
    if (!file) return;
    
    setLoading(true);
    setError(null);
    setAiAnalysis(null);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('cosmic_ray_removal', cosmicRay.toString());
      formData.append('fourier_filtering', fourier.toString());
      formData.append('voigt_fitting', voigt.toString());
      
      const res = await fetch(`${API_BASE}/api/v1/unified-spectroscopy/analyze`, {
        method: 'POST',
        body: formData,
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${res.status}`);
      }
      
      const data = await res.json();
      console.log('Reanalysis result:', data);
      setResult(data);
    } catch (err) {
      setError(err.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  }, [file, cosmicRay, fourier, voigt]);
  
  // AI analysis with peak reasoning
  const runAIAnalysis = useCallback(async () => {
    if (!result || !apiKeyStatus.configured) return;
    
    setAiLoading(true);
    try {
      // Build detailed peak information
      const peakInfo = result.peaks?.slice(0, 10).map((p, i) => 
        `Peak ${i + 1}: ${p.position_cm?.toFixed(1)} cm⁻¹ (intensity: ${p.intensity?.toFixed(3)}, FWHM: ${p.fwhm_cm?.toFixed(1)} cm⁻¹)`
      ).join('\n') || 'No peaks detected';
      
      const materialInfo = result.material_matches?.map(m => 
        `${m.material || m.description}: ${(m.confidence * 100).toFixed(0)}% confidence (${m.matched_peaks}/${m.total_peaks} peaks matched)`
      ).join('\n') || 'No material matches';
      
      const prompt = `You are a Raman spectroscopy expert. Analyze this spectrum and provide detailed insights for a research publication.

**Spectrum Data:**
- Total peaks detected: ${result.peaks?.length || 0}
- Data points: ${result.n_points || 0}
- Wavenumber range: ${result.wavenumber_range?.[0]?.toFixed(1)} - ${result.wavenumber_range?.[1]?.toFixed(1)} cm⁻¹

**Detected Peaks:**
${peakInfo}

**Material Identification:**
${materialInfo}

**Analysis Options Applied:**
${cosmicRay ? '- Cosmic ray removal (BoxSERS method)\n' : ''}${fourier ? '- Fourier filtering (SpectraGuru method)\n' : ''}${voigt ? '- Voigt peak fitting (RamanLab method)\n' : ''}

Please provide:

1. **Material Identification Confidence**: Assess the reliability of the material matches based on peak positions and intensities.

2. **Peak Assignments & Reasoning**: For each major peak, explain:
   - What molecular vibration or bond it represents
   - Why this peak appears at this specific wavenumber
   - What this tells us about the material structure

3. **Spectroscopic Features**: Identify key features like:
   - Characteristic bands (D, G, 2D for carbon materials, etc.)
   - Peak broadening or splitting
   - Intensity ratios
   - Background fluorescence

4. **Data Quality Assessment**: Comment on:
   - Signal-to-noise ratio
   - Baseline quality
   - Peak resolution
   - Any artifacts or anomalies

5. **Publication Recommendations**: Suggest:
   - Which peaks to highlight in figures
   - Comparison with standard reference data
   - Additional measurements or controls needed
   - How to present this data in a manuscript

Keep the analysis concise but scientifically rigorous. Use proper spectroscopic terminology.`;
      
      const res = await apiCall('/api/v2/alchemi/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, temperature: 0.3 }),
      });
      
      if (res?.ok) {
        setAiAnalysis(res.answer);
      } else {
        setAiAnalysis(`Error: ${res?.error || 'AI analysis failed'}`);
      }
    } catch (err) {
      setAiAnalysis(`Error: ${err.message}`);
    } finally {
      setAiLoading(false);
    }
  }, [result, apiKeyStatus, cosmicRay, fourier, voigt]);
  
  // Draw plot
  useEffect(() => {
    if (!result || !canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    
    renderSpectrumPlot(ctx, rect.width, rect.height, result, {
      wavenumber: result.wavenumber,
      intensity: result.intensity,
      corrected_intensity: result.corrected_intensity,
      baseline: result.baseline,
      peaks: result.peaks,
      showPeaks,
      showBaseline,
      showFit,
      cosmicRay,
      fourier,
      voigt,
      theme: currentTheme,
    });
  }, [result, showPeaks, showBaseline, showFit, cosmicRay, fourier, voigt, currentTheme]);
  
  // Export PNG
  const exportPNG = useCallback(() => {
    if (!canvasRef.current) return;
    const link = document.createElement('a');
    link.download = `raman_spectrum_${Date.now()}.png`;
    link.href = canvasRef.current.toDataURL('image/png');
    link.click();
  }, []);
  
  // Save analysis
  const saveAnalysis = useCallback(() => {
    if (!result) return;
    
    const name = analysisName.trim() || `Analysis_${new Date().toLocaleString()}`;
    
    const analysis = {
      id: Date.now(),
      name,
      result,
      options: { cosmicRay, fourier, voigt },
      displayOptions: { showPeaks, showBaseline, showFit },
      timestamp: Date.now(),
      fileName: file?.name || 'unknown',
    };
    
    const updated = [...savedAnalyses, analysis];
    setSavedAnalyses(updated);
    
    try {
      localStorage.setItem(STORAGE_KEYS.ANALYSES, JSON.stringify(updated));
      setShowSaveDialog(false);
      setAnalysisName('');
      
      // Show success message
      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
        detail: { kind: 'ok', text: `Analysis saved: ${name}` },
      }));
    } catch (e) {
      console.error('Failed to save analysis:', e);
      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
        detail: { kind: 'err', text: 'Failed to save analysis' },
      }));
    }
  }, [result, analysisName, savedAnalyses, cosmicRay, fourier, voigt, showPeaks, showBaseline, showFit, file]);
  
  // Load analysis
  const loadAnalysis = useCallback((analysis) => {
    setResult(analysis.result);
    setCosmicRay(analysis.options?.cosmicRay || false);
    setFourier(analysis.options?.fourier || false);
    setVoigt(analysis.options?.voigt || false);
    setShowPeaks(analysis.displayOptions?.showPeaks ?? true);
    setShowBaseline(analysis.displayOptions?.showBaseline ?? false);
    setShowFit(analysis.displayOptions?.showFit ?? false);
    setShowLoadDialog(false);
    
    window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
      detail: { kind: 'ok', text: `Loaded: ${analysis.name}` },
    }));
  }, []);
  
  // Delete analysis
  const deleteAnalysis = useCallback((id) => {
    const updated = savedAnalyses.filter(a => a.id !== id);
    setSavedAnalyses(updated);
    
    try {
      localStorage.setItem(STORAGE_KEYS.ANALYSES, JSON.stringify(updated));
      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
        detail: { kind: 'ok', text: 'Analysis deleted' },
      }));
    } catch (e) {
      console.error('Failed to delete analysis:', e);
    }
  }, [savedAnalyses]);
  
  return (
    <div className="animate-in" style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 12, height: '100%' }} role="main" aria-label="Unified Spectroscopy Analysis">
      {error && (
        <div className="error-banner" role="alert" style={{ gridColumn: '1 / -1', marginBottom: 12 }}>
          {error}
        </div>
      )}
      {/* Left sidebar */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflow: 'auto' }}>
        {/* Upload */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Sparkles size={14} color={THEME.cyan} />
                Unified Spectroscopy
              </div>
              <div className="card-subtitle">7 research sources · Publication-ready</div>
            </div>
          </div>
          
          <div className="input-group">
            <span className="input-label">Raman spectrum file</span>
            <input
              type="file"
              accept=".txt,.csv"
              onChange={handleFileChange}
              className="input-field"
              style={{ padding: '8px', fontSize: '11px' }}
            />
            {file && (
              <div style={{ fontSize: 10, color: THEME.textTertiary, marginTop: 4 }}>
                {file.name}
              </div>
            )}
          </div>
          
          {loading && (
            <div style={{ fontSize: 11, color: THEME.cyan, textAlign: 'center', padding: '8px 0' }}>
              ⟳ Analyzing spectrum...
            </div>
          )}
        </div>
        
        {/* Analysis options */}
        <div className="card">
          <div className="card-title">Analysis Options</div>
          <div style={{ fontSize: 10, color: THEME.textTertiary, marginBottom: 10, lineHeight: 1.5 }}>
            All spectra are automatically smoothed using Savitzky-Golay filter and baseline-corrected using AsLS method.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 11 }}>
              <input
                type="checkbox"
                checked={cosmicRay}
                onChange={e => setCosmicRay(e.target.checked)}
                style={{ width: 14, height: 14 }}
              />
              <span>Cosmic ray removal <span style={{ color: THEME.textTertiary }}>(BoxSERS)</span></span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 11 }}>
              <input
                type="checkbox"
                checked={fourier}
                onChange={e => setFourier(e.target.checked)}
                style={{ width: 14, height: 14 }}
              />
              <span>Fourier filtering <span style={{ color: THEME.textTertiary }}>(SpectraGuru)</span></span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 11 }}>
              <input
                type="checkbox"
                checked={voigt}
                onChange={e => setVoigt(e.target.checked)}
                style={{ width: 14, height: 14 }}
              />
              <span>Voigt peak fitting <span style={{ color: THEME.textTertiary }}>(RamanLab)</span></span>
            </label>
            {(cosmicRay || fourier || voigt) && (
              <div style={{ marginTop: 4, padding: 8, background: 'rgba(5, 150, 105, 0.15)', border: '1px solid rgba(5, 150, 105, 0.3)', borderRadius: 4, fontSize: 10, color: THEME.success, fontWeight: 600 }}>
                ✓ ACTIVE: {[cosmicRay && 'Cosmic Ray', fourier && 'Fourier', voigt && 'Voigt'].filter(Boolean).join(' + ')}
              </div>
            )}
          </div>
          {file && (
            <button className="btn btn-primary" onClick={reanalyze} disabled={loading} style={{ width: '100%', marginTop: 12, fontSize: 11 }}>
              {loading ? '⟳ Reanalyzing...' : '▶ Reanalyze'}
            </button>
          )}
        </div>
        
        {/* Display options */}
        {result && (
          <div className="card">
            <div className="card-title">Display Options</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 11 }}>
                <input
                  type="checkbox"
                  checked={showPeaks}
                  onChange={e => setShowPeaks(e.target.checked)}
                  style={{ width: 14, height: 14 }}
                />
                <span>Show peak markers</span>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 11 }}>
                <input
                  type="checkbox"
                  checked={showBaseline}
                  onChange={e => setShowBaseline(e.target.checked)}
                  style={{ width: 14, height: 14 }}
                />
                <span>Show baseline correction</span>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 11 }}>
                <input
                  type="checkbox"
                  checked={showFit}
                  onChange={e => setShowFit(e.target.checked)}
                  style={{ width: 14, height: 14 }}
                />
                <span>Show fitted peaks</span>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 11, marginTop: 8, paddingTop: 8, borderTop: `1px solid ${THEME.border}` }}>
                <input
                  type="checkbox"
                  checked={showRawData}
                  onChange={e => setShowRawData(e.target.checked)}
                  style={{ width: 14, height: 14 }}
                />
                <span style={{ color: showRawData ? '#f59e0b' : 'inherit' }}>
                  Show raw data (compare)
                </span>
              </label>
            </div>
            {showRawData && (
              <div style={{ fontSize: 10, color: '#f59e0b', marginTop: 8, padding: 8, background: 'rgba(245,158,11,0.1)', borderRadius: 4 }}>
                ⚠️ Raw data overlay enabled. You'll see the unprocessed spectrum in orange for comparison.
              </div>
            )}
          </div>
        )}
        
        {/* Export */}
        {result && (
          <div className="card">
            <div className="card-title">Save & Export</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button className="btn" onClick={() => setShowSaveDialog(true)} style={{ width: '100%', fontSize: 11 }}>
                <Save size={14} style={{ marginRight: 6 }} />
                Save Analysis
              </button>
              <button className="btn" onClick={exportPNG} style={{ width: '100%', fontSize: 11 }}>
                <Download size={14} style={{ marginRight: 6 }} />
                Download PNG (300 DPI)
              </button>
            </div>
          </div>
        )}
        
        {/* Load saved analyses */}
        {savedAnalyses.length > 0 && (
          <div className="card">
            <div className="card-title">Saved Analyses ({savedAnalyses.length})</div>
            <button className="btn" onClick={() => setShowLoadDialog(true)} style={{ width: '100%', fontSize: 11 }}>
              <FolderOpen size={14} style={{ marginRight: 6 }} />
              Load Analysis
            </button>
          </div>
        )}
        
        {/* AI Analysis */}
        {result && (
          <div className="card">
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Brain size={14} color={THEME.cyan} />
              AI Peak Analysis & Reasoning
            </div>
            <div style={{ fontSize: 10, color: THEME.textTertiary, marginBottom: 10, lineHeight: 1.5 }}>
              Get detailed peak assignments, molecular vibrations, and publication recommendations from NVIDIA NIM.
            </div>
            {!apiKeyStatus.configured ? (
              <div style={{ fontSize: 10, color: '#f59e0b', lineHeight: 1.5, padding: 10, background: 'rgba(245,158,11,0.08)', borderRadius: 4, border: '1px solid rgba(245,158,11,0.2)' }}>
                <strong>NVIDIA API key not configured.</strong><br/>
                Configure in Profile → Settings or edit <code>src/.env</code> to enable AI analysis with peak reasoning.
              </div>
            ) : (
              <>
                <button
                  className="btn btn-primary"
                  onClick={runAIAnalysis}
                  disabled={aiLoading}
                  style={{ width: '100%', fontSize: 11, marginBottom: 8 }}
                >
                  {aiLoading ? '⟳ Analyzing...' : '▶ Run AI Peak Analysis'}
                </button>
                {aiAnalysis && (
                  <div style={{
                    fontSize: 10,
                    color: THEME.textSecondary,
                    lineHeight: 1.6,
                    padding: 10,
                    background: 'rgba(255,255,255,0.02)',
                    borderRadius: 4,
                    border: `1px solid ${THEME.border}`,
                    whiteSpace: 'pre-wrap',
                    maxHeight: 400,
                    overflow: 'auto',
                  }}>
                    {aiAnalysis}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
      
      {/* Main content */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Plot */}
        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
          <div style={{
            padding: '16px 24px',
            background: 'rgba(255,255,255,0.02)',
            borderBottom: `1px solid ${THEME.border}`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div style={{ fontSize: 11, fontWeight: 900, letterSpacing: '1px', color: THEME.textPrimary }}>
              RAMAN_SPECTRUM_TELEMETRY
            </div>
            <div style={{ fontSize: 9, fontFamily: 'var(--font-data)', color: THEME.textTertiary }}>
              ENGINE: UNIFIED_V1 · COORD_SYS: ORTHONORMAL
            </div>
          </div>
          
          <div style={{ flex: 1, position: 'relative', padding: 40 }}>
            {result ? (
              <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} aria-label="Raman spectrum plot" />
            ) : (
              <div style={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: THEME.textTertiary,
                fontSize: 11,
                gap: 16,
              }}>
                <Info size={32} opacity={0.2} />
                <span>UPLOAD_SPECTRUM_FILE_TO_BEGIN...</span>
              </div>
            )}
            
            {/* HUD brackets */}
            <div style={{ position: 'absolute', top: 20, left: 20, width: 20, height: 20, borderTop: `1px solid ${THEME.cyan}44`, borderLeft: `1px solid ${THEME.cyan}44` }} />
            <div style={{ position: 'absolute', top: 20, right: 20, width: 20, height: 20, borderTop: `1px solid ${THEME.cyan}44`, borderRight: `1px solid ${THEME.cyan}44` }} />
            <div style={{ position: 'absolute', bottom: 20, left: 20, width: 20, height: 20, borderBottom: `1px solid ${THEME.cyan}44`, borderLeft: `1px solid ${THEME.cyan}44` }} />
            <div style={{ position: 'absolute', bottom: 20, right: 20, width: 20, height: 20, borderBottom: `1px solid ${THEME.cyan}44`, borderRight: `1px solid ${THEME.cyan}44` }} />
          </div>
        </div>
        
        {/* Stats */}
        {result && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            {[
              { label: 'PEAKS_DETECTED', value: result.peaks?.length || 0, unit: 'peaks' },
              { label: 'DATA_POINTS', value: result.n_points || 0, unit: 'pts' },
              { label: 'WAVENUMBER_MIN', value: result.wavenumber_range?.[0]?.toFixed(1) || 0, unit: 'cm⁻¹' },
              { label: 'WAVENUMBER_MAX', value: result.wavenumber_range?.[1]?.toFixed(1) || 0, unit: 'cm⁻¹' },
            ].map((stat, i) => (
              <div key={i} className="card" style={{
                padding: 16,
                background: THEME.cardBg,
                border: `1px solid ${THEME.border}`,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}>
                <div style={{ fontSize: 9, color: THEME.textTertiary, fontFamily: 'var(--font-data)' }}>
                  {stat.label}
                </div>
                <div style={{ fontSize: 20, fontWeight: 900, color: THEME.cyan }}>
                  {stat.value} <span style={{ fontSize: 10, fontWeight: 'normal', color: THEME.textSecondary }}>{stat.unit}</span>
                </div>
              </div>
            ))}
          </div>
        )}
        
        {/* Peaks table */}
        {result?.peaks?.length > 0 && (
          <div className="card">
            <div className="card-title">Detected Peaks ({result.peaks.length})</div>
            <div style={{ overflow: 'auto', maxHeight: 200 }}>
              <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
                <thead style={{ background: 'rgba(255,255,255,0.02)', position: 'sticky', top: 0 }}>
                  <tr>
                    <th style={{ padding: '8px', textAlign: 'left', color: THEME.textTertiary }}>#</th>
                    <th style={{ padding: '8px', textAlign: 'left', color: THEME.textTertiary }}>Position (cm⁻¹)</th>
                    <th style={{ padding: '8px', textAlign: 'left', color: THEME.textTertiary }}>Intensity</th>
                    <th style={{ padding: '8px', textAlign: 'left', color: THEME.textTertiary }}>Prominence</th>
                    <th style={{ padding: '8px', textAlign: 'left', color: THEME.textTertiary }}>FWHM</th>
                  </tr>
                </thead>
                <tbody>
                  {result.peaks.slice(0, 20).map((p, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${THEME.border}` }}>
                      <td style={{ padding: '6px 8px', color: THEME.textSecondary }}>{i + 1}</td>
                      <td style={{ padding: '6px 8px', fontFamily: 'var(--font-data)', color: THEME.textPrimary }}>
                        {p.position_cm?.toFixed(2)}
                      </td>
                      <td style={{ padding: '6px 8px', fontFamily: 'var(--font-data)', color: THEME.textPrimary }}>
                        {p.intensity?.toFixed(3)}
                      </td>
                      <td style={{ padding: '6px 8px', fontFamily: 'var(--font-data)', color: THEME.textPrimary }}>
                        {p.prominence?.toFixed(3)}
                      </td>
                      <td style={{ padding: '6px 8px', fontFamily: 'var(--font-data)', color: THEME.textPrimary }}>
                        {p.fwhm_cm?.toFixed(2) || 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        
        {/* Material matches */}
        {result?.material_matches?.length > 0 && (
          <div className="card">
            <div className="card-title">Material Identification</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {result.material_matches.map((m, i) => (
                <div key={i} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 10,
                  background: 'rgba(255,255,255,0.02)',
                  border: `1px solid ${THEME.border}`,
                  borderRadius: 4,
                }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: THEME.textPrimary }}>
                      {m.description || m.material}
                    </div>
                    <div style={{ fontSize: 10, color: THEME.textTertiary }}>
                      {m.matched_peaks} of {m.total_peaks} peaks matched
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 18, fontWeight: 900, color: THEME.cyan }}>
                      {(m.confidence * 100).toFixed(0)}%
                    </div>
                    <div style={{ fontSize: 9, color: THEME.textTertiary }}>confidence</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      
      {error && (
        <div style={{
          position: 'fixed',
          bottom: 20,
          right: 20,
          padding: 16,
          background: '#f87171',
          color: '#fff',
          borderRadius: 6,
          fontSize: 12,
          maxWidth: 400,
          zIndex: 1000,
        }}>
          {error}
        </div>
      )}
      
      {/* Save Dialog */}
      {showSaveDialog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 2000,
        }} onClick={() => setShowSaveDialog(false)}>
          <div className="card" style={{
            width: 400,
            maxWidth: '90%',
            padding: 24,
          }} onClick={e => e.stopPropagation()}>
            <div className="card-title" style={{ marginBottom: 16 }}>Save Analysis</div>
            <div className="input-group" style={{ marginBottom: 16 }}>
              <span className="input-label">Analysis Name</span>
              <input
                type="text"
                className="input-field"
                placeholder="Enter name (optional)"
                value={analysisName}
                onChange={e => setAnalysisName(e.target.value)}
                onKeyPress={e => e.key === 'Enter' && saveAnalysis()}
                autoFocus
              />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn" onClick={() => setShowSaveDialog(false)} style={{ flex: 1 }}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={saveAnalysis} style={{ flex: 1 }}>
                Save
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Load Dialog */}
      {showLoadDialog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 2000,
        }} onClick={() => setShowLoadDialog(false)}>
          <div className="card" style={{
            width: 600,
            maxWidth: '90%',
            maxHeight: '80vh',
            padding: 24,
            overflow: 'auto',
          }} onClick={e => e.stopPropagation()}>
            <div className="card-title" style={{ marginBottom: 16 }}>Load Saved Analysis</div>
            {savedAnalyses.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: THEME.textTertiary }}>
                No saved analyses
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {savedAnalyses.slice().reverse().map(analysis => (
                  <div key={analysis.id} style={{
                    padding: 12,
                    background: 'rgba(255,255,255,0.02)',
                    border: `1px solid ${THEME.border}`,
                    borderRadius: 4,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: THEME.textPrimary }}>
                        {analysis.name}
                      </div>
                      <div style={{ fontSize: 10, color: THEME.textTertiary, marginTop: 4 }}>
                        {new Date(analysis.timestamp).toLocaleString()} · {analysis.fileName}
                      </div>
                      <div style={{ fontSize: 10, color: THEME.textSecondary, marginTop: 4 }}>
                        {analysis.result.peaks?.length || 0} peaks · 
                        {analysis.options.cosmicRay ? ' CR' : ''}
                        {analysis.options.fourier ? ' FFT' : ''}
                        {analysis.options.voigt ? ' Voigt' : ''}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button 
                        className="btn btn-primary" 
                        onClick={() => loadAnalysis(analysis)}
                        style={{ fontSize: 11, padding: '6px 12px' }}
                      >
                        Load
                      </button>
                      <button 
                        className="btn" 
                        onClick={() => deleteAnalysis(analysis.id)}
                        style={{ fontSize: 11, padding: '6px 12px', background: '#f87171' }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <button className="btn" onClick={() => setShowLoadDialog(false)} style={{ width: '100%', marginTop: 16 }}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
