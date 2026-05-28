import React, { useState, useEffect, useCallback } from 'react';

const BACKEND_URL = '';

export default function ResearchPublicationPanel() {
  const [activeTab, setActiveTab] = useState('fig1'); // fig1-fig7, ml_insights, export_pdf
  const [figures, setFigures] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Customization options for each figure
  const [figOptions, setFigOptions] = useState({
    style: 'acs', // acs, ieee, nature, monochrome, default
    grid: true,
    font: 'Times New Roman',
    dpi: 300,
    xlabel: '',
    ylabel: '',
    color: '',
  });

  // Plot image blob URLs
  const [plotUrls, setPlotUrls] = useState({});
  const [plotLoading, setPlotLoading] = useState({});

  // ML Insights
  const [mlInsights, setMlInsights] = useState(null);
  const [mlLoading, setMlLoading] = useState(false);

  // PDF Text Content
  const [pdfContent, setPdfContent] = useState({
    title: 'Facile Synthesis of Hematite/rGO Nanocomposite (FOG) for Ultra-Sensitive Electrochemical Sensing of Ascorbic Acid in Complex Biological Matrices',
    authors: 'V. Raman, S. B. Varshini, and K. Subramanian',
    affiliation: 'Department of Electrochemistry, VidyuthLabs, Chennai, India',
    abstract: 'Herein, we report the development of a highly sensitive and selective electrochemical biosensor based on a spinel-like Hematite Iron Oxide nanoparticle anchored on reduced Graphene Oxide (rGO-Fe2O3) nanocomposite (FOG) modified screen-printed carbon electrode (SPCE) for the detection of Ascorbic Acid (AA) in biological samples (Gomutra). Characterization via Raman, XRD, and Nyquist impedance spectroscopy confirmed the successful composite formation and high electrical conductivity. The FOG sensor exhibited an extremely low charge-transfer resistance of 24.5 Ω, resulting in excellent electrocatalytic oxidation towards AA at a reduced overpotential. Cyclic voltammetry study proved a highly reversible, diffusion-controlled process with an electron transfer rate constant (ks) of 1.25 s⁻¹. Differential Pulse Voltammetry (DPV) calibration curves demonstrated a linear range of 1.0–70.0 µM with a limit of detection (LOD) of 0.28 µM. Finally, the biosensor was successfully validated for the detection of AA in real Gomutra samples via standard addition, demonstrating its potential for research-grade biological diagnostics.',
    introduction: 'Ascorbic acid (AA) plays an indispensable role in biological systems as a key antioxidant, cofactor in enzymatic reactions, and indicator of metabolic health. Accurate quantification of AA in complex matrices, such as clinical fluids and organic extracts (e.g., Gomutra), is vital but remains a challenge due to sluggish kinetics and electrode fouling on standard carbon surfaces. Nanomaterial-modified electrodes offer a robust solution by lowering activation overpotentials and expanding electrochemically active surface areas. Specifically, the combination of high-surface-area graphene sheets with electrocatalytic metal oxides has gained massive traction. In this study, we propose a synergistic combination of rGO and iron oxide nanoparticles. This draft provides the complete synthesis, material, physical, and analytical validation of this sensor platform.',
    experimental: 'The screen-printed carbon electrodes (SPCE) were cleaned voltammetrically. Graphene oxide was synthesized by a modified Hummers method and hydrothermally treated with iron(III) chloride to obtain the rGO-Fe2O3 composite (FOG). Characterization was performed using XRD and Raman spectroscopy. Electrochemical impedance spectroscopy (EIS) measurements were recorded in 0.5 mM ferricyanide/ferrocyanide system in 0.1 M KCl. Differential Pulse Voltammetry (DPV) scans were performed from -0.2 V to 0.6 V in phosphate buffer saline (PBS, pH 7.0) with varying analyte concentrations. For real sample analysis, Gomutra spikes were prepared by sequentially adding sample aliquots (10–500 µL) into the cell.',
    results_discussion: 'Raman spectroscopy (Figure 3) verified the successful reduction of GO to rGO and decoration with Fe2O3. The D and G bands of rGO appeared prominently at 1350 and 1590 cm⁻¹ respectively, with an ID/IG ratio of 1.26, indicating highly defective, active graphene frameworks. Nyquist plots (Figure 6a) displayed a dramatic decrease in the charge-transfer resistance (Rct) from 150 Ω (Bare GCE) to 24.5 Ω for the FOG-modified electrode, demonstrating that the nanocomposite provides highly active electron pathways. Cyclic voltammetry scans at different scan rates (Figure 5) showed that the peak current is proportional to the square root of the scan rate, indicating a classic diffusion-controlled process. Fitting the peak shifts with Laviron\'s equation yielded a standard rate constant (ks) of 1.25 s⁻¹. DPV concentration curves (Figure 7a) showed sharp electro-oxidation peaks, giving a highly linear calibration curve (R² = 0.998) and a limit of detection of 0.28 µM. Spiking studies in Gomutra samples demonstrated excellent recovery rates (98.5–101.2%), validating the analytical usability.',
    conclusions: 'In conclusion, we have designed and validated a spinel-phase Hematite/rGO nanocomposite (FOG) sensor that drastically accelerates charge transfer kinetics. The sensor demonstrates ultra-sensitive detection of AA, offering a low LOD of 0.28 µM and high sensitivity. Testing in complex organic matrices like Gomutra shows that the sensor is highly resilient and reliable, proving its value as a research-grade tool for publication.',
    format: 'ieee', // ieee, acs
  });

  const [pdfCompiling, setPdfCompiling] = useState(false);

  // Fetch figures list
  useEffect(() => {
    fetch(`${BACKEND_URL}/api/v2/publication/figures`)
      .then(res => res.json())
      .then(data => {
        setFigures(data);
        if (data.length > 0) {
          // Initialize options with first figure's defaults
          setFigOptions(prev => ({
            ...prev,
            ...data[0].default_options
          }));
        }
      })
      .catch(err => console.error("Error fetching figures: ", err));
  }, []);

  // Fetch ML Insights
  const fetchMlInsights = useCallback(() => {
    setMlLoading(true);
    fetch(`${BACKEND_URL}/api/v2/publication/ml-insights`)
      .then(res => res.json())
      .then(data => {
        setMlInsights(data);
        setMlLoading(false);
      })
      .catch(err => {
        console.error("Error fetching ML insights: ", err);
        setMlLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchMlInsights();
  }, [fetchMlInsights]);

  // Fetch/Render Plot for current tab
  const renderPlot = useCallback((figId) => {
    if (!figId) return;
    setPlotLoading(prev => ({ ...prev, [figId]: true }));
    
    fetch(`${BACKEND_URL}/api/v2/publication/plot/${figId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(figOptions)
    })
      .then(res => {
        if (!res.ok) throw new Error("Plot generation failed");
        return res.blob();
      })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        setPlotUrls(prev => {
          // Revoke old URL to avoid leaks
          if (prev[figId]) URL.revokeObjectURL(prev[figId]);
          return { ...prev, [figId]: url };
        });
        setPlotLoading(prev => ({ ...prev, [figId]: false }));
      })
      .catch(err => {
        console.error(err);
        setPlotLoading(prev => ({ ...prev, [figId]: false }));
      });
  }, [figOptions]);

  // Render active tab plot
  useEffect(() => {
    if (activeTab.startsWith('fig')) {
      const id = parseInt(activeTab.replace('fig', ''));
      renderPlot(id);
    }
  }, [activeTab, renderPlot]);

  // Handle option changes
  const handleOptionChange = (key, value) => {
    setFigOptions(prev => ({ ...prev, [key]: value }));
  };

  // Trigger plot refresh
  const triggerRefresh = () => {
    if (activeTab.startsWith('fig')) {
      const id = parseInt(activeTab.replace('fig', ''));
      renderPlot(id);
    }
  };

  // Compile PDF Draft
  const compilePdf = () => {
    setPdfCompiling(true);
    fetch(`${BACKEND_URL}/api/v2/publication/generate-pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...pdfContent,
        style: figOptions.style,
        grid: figOptions.grid,
        font: figOptions.font
      })
    })
      .then(res => {
        if (!res.ok) throw new Error("Failed to generate PDF");
        return res.blob();
      })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `manuscript_${pdfContent.format}_draft.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setPdfCompiling(false);
        window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
          detail: { kind: 'ok', text: 'Manuscript compiled successfully!' }
        }));
      })
      .catch(err => {
        console.error(err);
        setPdfCompiling(false);
        window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
          detail: { kind: 'err', text: 'PDF compilation failed' }
        }));
      });
  };

  const activeFig = figures.find(f => `fig${f.id}` === activeTab);

  return (
    <div className="animate-in" style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 12, height: '100%' }}>
      {/* Sidebar Navigation */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto', paddingRight: 4 }}>
        <div className="card" style={{ padding: 12 }}>
          <div className="card-title" style={{ fontSize: 13, marginBottom: 2 }}>Research Publisher</div>
          <div className="card-subtitle" style={{ fontSize: 10.5, marginBottom: 8 }}>800 DPI publication panel</div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {figures.map(fig => (
              <button
                key={fig.id}
                onClick={() => {
                  setActiveTab(`fig${fig.id}`);
                  // Override custom labels if any
                  setFigOptions(prev => ({
                    ...prev,
                    xlabel: fig.default_options.xlabel || '',
                    ylabel: fig.default_options.ylabel || ''
                  }));
                }}
                style={{
                  textAlign: 'left',
                  padding: '7px 10px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 11.5,
                  background: activeTab === `fig${fig.id}` ? 'var(--accent-muted)' : 'transparent',
                  color: activeTab === `fig${fig.id}` ? 'var(--text-primary)' : 'var(--text-secondary)',
                  border: '1px solid transparent',
                  borderColor: activeTab === `fig${fig.id}` ? 'var(--accent-border)' : 'transparent',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                {fig.title}
              </button>
            ))}
            
            <div style={{ height: 1, background: 'var(--border-primary)', margin: '6px 0' }} />

            <button
              onClick={() => setActiveTab('ml_insights')}
              style={{
                textAlign: 'left',
                padding: '7px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: 11.5,
                background: activeTab === 'ml_insights' ? 'var(--accent-muted)' : 'transparent',
                color: activeTab === 'ml_insights' ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: '1px solid transparent',
                borderColor: activeTab === 'ml_insights' ? 'var(--accent-border)' : 'transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              📊 ML Analytical Insights
            </button>

            <button
              onClick={() => setActiveTab('export_pdf')}
              style={{
                textAlign: 'left',
                padding: '7px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: 11.5,
                background: activeTab === 'export_pdf' ? 'var(--accent-muted)' : 'transparent',
                color: activeTab === 'export_pdf' ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: '1px solid transparent',
                borderColor: activeTab === 'export_pdf' ? 'var(--accent-border)' : 'transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                fontWeight: 500
              }}
            >
              📄 Compile & Export PDF
            </button>
          </div>
        </div>

        {/* Global plot styling parameters */}
        {activeTab.startsWith('fig') && (
          <div className="card" style={{ padding: 12 }}>
            <div className="card-title" style={{ fontSize: 11.5, marginBottom: 8 }}>Plot Formatting</div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="input-group">
                <span className="input-label" style={{ fontSize: 10.5 }}>Journal Style</span>
                <select 
                  className="input-field" 
                  value={figOptions.style} 
                  onChange={e => handleOptionChange('style', e.target.value)}
                  style={{ fontSize: 11, padding: '4px 8px' }}
                >
                  <option value="default">Default RAMAN</option>
                  <option value="acs">ACS (Journal format)</option>
                  <option value="ieee">IEEE Transactions</option>
                  <option value="nature">Nature Communications</option>
                  <option value="monochrome">Monochrome (Gray)</option>
                </select>
              </div>

              <div className="input-group">
                <span className="input-label" style={{ fontSize: 10.5 }}>Font Family</span>
                <select 
                  className="input-field" 
                  value={figOptions.font} 
                  onChange={e => handleOptionChange('font', e.target.value)}
                  style={{ fontSize: 11, padding: '4px 8px' }}
                >
                  <option value="Times New Roman">Times New Roman</option>
                  <option value="Arial">Arial</option>
                  <option value="Helvetica">Helvetica</option>
                </select>
              </div>

              <div className="input-group">
                <span className="input-label" style={{ fontSize: 10.5 }}>Grid Lines</span>
                <select 
                  className="input-field" 
                  value={figOptions.grid ? "true" : "false"} 
                  onChange={e => handleOptionChange('grid', e.target.value === "true")}
                  style={{ fontSize: 11, padding: '4px 8px' }}
                >
                  <option value="true">Enabled</option>
                  <option value="false">Disabled</option>
                </select>
              </div>

              <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                <button className="btn btn-sm btn-primary" onClick={triggerRefresh} style={{ flex: 1, fontSize: 10.5 }}>
                  Apply Styles
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Main Workspace Panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, height: '100%', overflowY: 'auto' }}>
        
        {/* Figure Viewer Tab */}
        {activeTab.startsWith('fig') && activeFig && (
          <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{activeFig.title}</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Category: {activeFig.category} | {activeFig.is_real_data ? "🟢 Real Dataset" : "🔵 Simulated Physics"}</div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <a
                  href={plotUrls[activeFig.id]}
                  download={`figure_${activeFig.id}.png`}
                  className="btn btn-sm"
                  style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-primary)', fontSize: 11, padding: '5px 10px', textDecoration: 'none', color: 'var(--text-secondary)' }}
                >
                  Download 300 DPI PNG
                </a>
              </div>
            </div>

            <div style={{ 
              flex: 1, 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              background: 'var(--bg-primary)', 
              border: '1px solid var(--border-primary)', 
              borderRadius: 'var(--radius-sm)',
              position: 'relative',
              overflow: 'hidden',
              minHeight: 280
            }}>
              {plotLoading[activeFig.id] ? (
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Rendering high-resolution plot...</div>
              ) : plotUrls[activeFig.id] ? (
                <img 
                  src={plotUrls[activeFig.id]} 
                  alt={activeFig.title}
                  style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain', padding: 8 }} 
                />
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-disabled)' }}>No plot rendered</div>
              )}
            </div>

            <div style={{ padding: 10, background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-primary)' }}>
              <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 2 }}>Caption Summary</div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', lineHeight: 1.4 }}>{activeFig.description}</div>
            </div>
          </div>
        )}

        {/* ML Insights Tab */}
        {activeTab === 'ml_insights' && (
          <div className="card" style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>ML Analytical Insights</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Physics-informed calculations extracted from biological standard addition datasets.</div>
              </div>
              <button className="btn btn-sm btn-primary" onClick={fetchMlInsights} disabled={mlLoading} style={{ fontSize: 11 }}>
                {mlLoading ? 'Recalculating...' : 'Refresh calculations'}
              </button>
            </div>

            {mlLoading || !mlInsights ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-tertiary)', fontSize: 12 }}>
                Recalculating ML parameters...
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                
                {/* Raman card */}
                <div className="card" style={{ background: 'var(--bg-tertiary)', padding: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', marginBottom: 8 }}>Raman Spectrum Features (rGO/Fe2O3)</div>
                  <table className="data-table" style={{ fontSize: 11 }}>
                    <tbody>
                      <tr><td>D-Band Peak (1350 cm⁻¹)</td><td className="mono">{mlInsights.raman.d_intensity}</td></tr>
                      <tr><td>G-Band Peak (1590 cm⁻¹)</td><td className="mono">{mlInsights.raman.g_intensity}</td></tr>
                      <tr><td>ID / IG Ratio</td><td className="mono" style={{ color: 'var(--color-success)', fontWeight: 600 }}>{mlInsights.raman.id_ig_ratio}</td></tr>
                      <tr><td>Est. Graphene Grain Size (La)</td><td className="mono">{mlInsights.raman.sp2_grain_size_nm} nm</td></tr>
                    </tbody>
                  </table>
                </div>

                {/* EIS card */}
                <div className="card" style={{ background: 'var(--bg-tertiary)', padding: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', marginBottom: 8 }}>EIS Impedance Parameters (Nyquist Fit)</div>
                  <table className="data-table" style={{ fontSize: 11 }}>
                    <thead>
                      <tr><th>Electrode</th><th>Rs (Ω)</th><th>Rct (Ω)</th></tr>
                    </thead>
                    <tbody>
                      <tr><td>Bare GCE</td><td className="mono">{mlInsights.eis.bare.rs_ohm}</td><td className="mono">{mlInsights.eis.bare.rct_ohm}</td></tr>
                      <tr><td>FOG Modified</td><td className="mono">{mlInsights.eis.fog.rs_ohm}</td><td className="mono" style={{ color: 'var(--color-success)', fontWeight: 600 }}>{mlInsights.eis.fog.rct_ohm}</td></tr>
                      <tr><td>Rct Reduction Rate</td><td colspan="2" className="mono" style={{ color: 'var(--color-success)', fontWeight: 600 }}>-{mlInsights.eis.rct_reduction_percent}%</td></tr>
                    </tbody>
                  </table>
                </div>

                {/* Reversibility card */}
                <div className="card" style={{ background: 'var(--bg-tertiary)', padding: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', marginBottom: 8 }}>Kinetics & Reversibility (Laviron / Randles)</div>
                  <table className="data-table" style={{ fontSize: 11 }}>
                    <tbody>
                      <tr><td>Randles-Sevcik Fit (R²)</td><td className="mono">{mlInsights.reversibility.randles_sevcik_r2}</td></tr>
                      <tr><td>Diffusion Coefficient (D)</td><td className="mono">{mlInsights.reversibility.diffusion_coefficient_cm2_s} cm²/s</td></tr>
                      <tr><td>Transfer Coefficient (α)</td><td className="mono">{mlInsights.reversibility.transfer_coefficient_alpha}</td></tr>
                      <tr><td>Standard Rate Constant (ks)</td><td className="mono" style={{ color: 'var(--color-success)', fontWeight: 600 }}>{mlInsights.reversibility.electron_transfer_rate_constant_ks_s} s⁻¹</td></tr>
                    </tbody>
                  </table>
                </div>

                {/* Calibration card */}
                <div className="card" style={{ background: 'var(--bg-tertiary)', padding: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', marginBottom: 8 }}>Analytical Calibration & Sensitivity (DPV)</div>
                  <table className="data-table" style={{ fontSize: 11 }}>
                    <tbody>
                      <tr><td>Linear Sensitivity</td><td className="mono">{mlInsights.calibration.sensitivity_ua_per_um_cm2} µA/µM/cm²</td></tr>
                      <tr><td>Linear Range</td><td className="mono">{mlInsights.calibration.linear_range_uM[0]} - {mlInsights.calibration.linear_range_uM[1]} µM</td></tr>
                      <tr><td>Fit Correlation (R²)</td><td className="mono" style={{ fontWeight: 600 }}>{mlInsights.calibration.r_squared}</td></tr>
                      <tr><td>Limit of Detection (LOD)</td><td className="mono" style={{ color: 'var(--color-success)', fontWeight: 600 }}>{mlInsights.calibration.lod_uM} µM</td></tr>
                      <tr><td>Limit of Quantitation (LOQ)</td><td className="mono">{mlInsights.calibration.loq_uM} µM</td></tr>
                    </tbody>
                  </table>
                </div>

                {/* Real sample Gomutra spikes */}
                <div className="card" style={{ gridColumn: 'span 2', background: 'var(--bg-tertiary)', padding: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', marginBottom: 8 }}>Real Sample Identification & Quantification (Gomutra Study)</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                    <div>
                      <table className="data-table" style={{ fontSize: 11 }}>
                        <tbody>
                          <tr><td>Standard Addition Fit (R²)</td><td className="mono">{mlInsights.real_sample.correlation_r2}</td></tr>
                          <tr><td>Detected Amount in Cell</td><td className="mono">{mlInsights.real_sample.detected_analyte_umol} µmol</td></tr>
                          <tr><td>Original Sample Concentration</td><td className="mono" style={{ color: 'var(--color-success)', fontWeight: 600 }}>{mlInsights.real_sample.calculated_original_concentration_uM} µM</td></tr>
                        </tbody>
                      </table>
                    </div>
                    
                    <div style={{ padding: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>Modifier Class (ML Classifier prediction):</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-success)', margin: '4px 0' }}>{mlInsights.material_classification.class}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>Confidence Score: {(mlInsights.material_classification.confidence * 100).toFixed(1)}%</div>
                      <div style={{ fontSize: 10.5, color: 'var(--text-secondary)', lineHeight: 1.3 }}>{mlInsights.material_classification.rationale}</div>
                    </div>
                  </div>
                </div>

              </div>
            )}
          </div>
        )}

        {/* Compile PDF Tab */}
        {activeTab === 'export_pdf' && (
          <div className="card" style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>Compile Publication Manuscript Draft</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Review and compile all customized figures and sections into a journal-ready publication draft PDF.</div>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <select
                  className="input-field"
                  value={pdfContent.format}
                  onChange={e => setPdfContent(prev => ({ ...prev, format: e.target.value }))}
                  style={{ fontSize: 11, padding: '4px 8px', width: 140 }}
                >
                  <option value="ieee">IEEE Transactions</option>
                  <option value="acs">ACS Nano / JACS</option>
                </select>
                <button className="btn btn-primary" onClick={compilePdf} disabled={pdfCompiling} style={{ fontSize: 12 }}>
                  {pdfCompiling ? 'Compiling Manuscript...' : 'Compile & Download PDF'}
                </button>
              </div>
            </div>

            {pdfCompiling && (
              <div style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', padding: 12, borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 6 }}>Compilation progress: Rendering figures & arranging sections...</div>
                <div style={{ height: 4, borderRadius: 2, background: 'var(--bg-elevated)', overflow: 'hidden' }}>
                  <div style={{ width: '65%', height: '100%', background: 'var(--color-success)', animation: 'pulse 1.5s infinite' }} />
                </div>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="input-group">
                <span className="input-label" style={{ fontSize: 11 }}>Paper Title</span>
                <input 
                  type="text" 
                  className="input-field" 
                  value={pdfContent.title}
                  onChange={e => setPdfContent(prev => ({ ...prev, title: e.target.value }))}
                  style={{ fontSize: 11.5 }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div className="input-group">
                  <span className="input-label" style={{ fontSize: 11 }}>Authors</span>
                  <input 
                    type="text" 
                    className="input-field" 
                    value={pdfContent.authors}
                    onChange={e => setPdfContent(prev => ({ ...prev, authors: e.target.value }))}
                    style={{ fontSize: 11.5 }}
                  />
                </div>
                <div className="input-group">
                  <span className="input-label" style={{ fontSize: 11 }}>Affiliation</span>
                  <input 
                    type="text" 
                    className="input-field" 
                    value={pdfContent.affiliation}
                    onChange={e => setPdfContent(prev => ({ ...prev, affiliation: e.target.value }))}
                    style={{ fontSize: 11.5 }}
                  />
                </div>
              </div>

              <div className="input-group">
                <span className="input-label" style={{ fontSize: 11 }}>Abstract</span>
                <textarea 
                  className="input-field" 
                  rows={4}
                  value={pdfContent.abstract}
                  onChange={e => setPdfContent(prev => ({ ...prev, abstract: e.target.value }))}
                  style={{ fontSize: 11.5, lineHeight: 1.4 }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div className="input-group">
                  <span className="input-label" style={{ fontSize: 11 }}>1. Introduction</span>
                  <textarea 
                    className="input-field" 
                    rows={6}
                    value={pdfContent.introduction}
                    onChange={e => setPdfContent(prev => ({ ...prev, introduction: e.target.value }))}
                    style={{ fontSize: 11, lineHeight: 1.4 }}
                  />
                </div>
                <div className="input-group">
                  <span className="input-label" style={{ fontSize: 11 }}>2. Experimental Section</span>
                  <textarea 
                    className="input-field" 
                    rows={6}
                    value={pdfContent.experimental}
                    onChange={e => setPdfContent(prev => ({ ...prev, experimental: e.target.value }))}
                    style={{ fontSize: 11, lineHeight: 1.4 }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div className="input-group">
                  <span className="input-label" style={{ fontSize: 11 }}>3. Results & Discussion</span>
                  <textarea 
                    className="input-field" 
                    rows={6}
                    value={pdfContent.results_discussion}
                    onChange={e => setPdfContent(prev => ({ ...prev, results_discussion: e.target.value }))}
                    style={{ fontSize: 11, lineHeight: 1.4 }}
                  />
                </div>
                <div className="input-group">
                  <span className="input-label" style={{ fontSize: 11 }}>4. Conclusions</span>
                  <textarea 
                    className="input-field" 
                    rows={6}
                    value={pdfContent.conclusions}
                    onChange={e => setPdfContent(prev => ({ ...prev, conclusions: e.target.value }))}
                    style={{ fontSize: 11, lineHeight: 1.4 }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
