import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

/**
 * RĀMAN Studio — IEEE Conference Paper Generator
 * =================================================
 * Generates publication-ready reports in IEEE two-column format.
 * Based on IEEE Transactions template specifications:
 * - A4/Letter paper, two-column layout
 * - Times New Roman 10pt body (simulated with jsPDF serif)
 * - Sections: Abstract, Introduction, Methodology, Results, Conclusion, References
 * - Automatic content filling from simulation data
 * - VidyuthLabs branded header and footer
 *
 * Reference: IEEE Author Guidelines (ieee.org/publications/services/standards)
 */

const BRAND = {
  name: 'VidyuthLabs',
  studio: 'RAMAN Studio',
  tagline: 'Electrochemical Research Platform',
  color: [74, 158, 255],  // #4a9eff
  green: [118, 185, 0],   // #76b900
};

const PAGE = {
  width: 210,  // A4 mm
  height: 297,
  marginTop: 25,
  marginBottom: 20,
  marginLeft: 20,
  marginRight: 20,
  colGap: 6,
  headerHeight: 15,
  footerHeight: 10,
};

function getColWidth() {
  return (PAGE.width - PAGE.marginLeft - PAGE.marginRight - PAGE.colGap) / 2;
}

/**
 * Generate an IEEE-formatted PDF report from simulation data.
 * @param {Object} config - Report configuration
 * @param {string} config.title - Paper title
 * @param {string} config.authors - Author names
 * @param {string} config.affiliation - Organization
 * @param {string} config.abstract - Abstract text
 * @param {string} config.type - Report type: 'eis', 'cv', 'battery', 'biosensor', 'alchemi'
 * @param {Object} config.data - Simulation result data
 * @param {Object} config.params - Simulation parameters
 * @param {HTMLCanvasElement[]} config.plotCanvases - Array of canvas elements to embed
 */
export function generateIEEEReport(config) {
  const doc = new jsPDF('p', 'mm', 'a4');
  const colW = getColWidth();
  let y = PAGE.marginTop;

  // === PAGE HEADER (RAMAN Studio branding) ===
  addBrandHeader(doc);

  // === TITLE ===
  doc.setFont('times', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(0, 0, 0);
  const titleLines = doc.splitTextToSize(config.title || 'Electrochemical Analysis Report', PAGE.width - PAGE.marginLeft - PAGE.marginRight);
  y = PAGE.marginTop + PAGE.headerHeight;
  titleLines.forEach(line => {
    doc.text(line, PAGE.width / 2, y, { align: 'center' });
    y += 6;
  });

  // === AUTHORS ===
  doc.setFont('times', 'normal');
  doc.setFontSize(11);
  doc.text(config.authors || 'Dr. Varshini C.B.', PAGE.width / 2, y + 2, { align: 'center' });
  y += 6;
  
  doc.setFontSize(9);
  doc.setTextColor(80, 80, 80);
  doc.text(config.affiliation || 'VidyuthLabs Pvt. Ltd., Department of Electrochemistry & Nanomaterials', PAGE.width / 2, y, { align: 'center' });
  y += 4;
  doc.text(`Report Generated: ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`, PAGE.width / 2, y, { align: 'center' });
  y += 8;

  // === HORIZONTAL RULE ===
  doc.setDrawColor(200, 200, 200);
  doc.setLineWidth(0.3);
  doc.line(PAGE.marginLeft, y, PAGE.width - PAGE.marginRight, y);
  y += 6;

  // === ABSTRACT ===
  doc.setTextColor(0, 0, 0);
  doc.setFont('times', 'bolditalic');
  doc.setFontSize(9);
  doc.text('Abstract—', PAGE.marginLeft, y);
  
  doc.setFont('times', 'italic');
  doc.setFontSize(9);
  const abstractText = config.abstract || generateAbstract(config);
  const abstractLines = doc.splitTextToSize(abstractText, PAGE.width - PAGE.marginLeft - PAGE.marginRight);
  doc.text(abstractLines, PAGE.marginLeft + 17, y);
  y += abstractLines.length * 3.5 + 4;

  // === KEYWORDS ===
  doc.setFont('times', 'bolditalic');
  doc.setFontSize(8);
  doc.text('Keywords—', PAGE.marginLeft, y);
  doc.setFont('times', 'italic');
  doc.text(generateKeywords(config.type), PAGE.marginLeft + 18, y);
  y += 8;

  // === HORIZONTAL RULE ===
  doc.line(PAGE.marginLeft, y, PAGE.width - PAGE.marginRight, y);
  y += 6;

  // === TWO-COLUMN BODY ===
  let colY = y;
  let currentCol = 0; // 0 = left, 1 = right
  const colX = [PAGE.marginLeft, PAGE.marginLeft + colW + PAGE.colGap];

  // Helper: add section
  const addSection = (num, title, content) => {
    // Section header
    doc.setFont('times', 'bold');
    doc.setFontSize(10);
    doc.setTextColor(0, 0, 0);
    
    if (colY > PAGE.height - PAGE.marginBottom - 30) {
      if (currentCol === 0) {
        currentCol = 1;
        colY = y;
      } else {
        doc.addPage();
        addBrandHeader(doc);
        addPageFooter(doc, doc.internal.getNumberOfPages());
        colY = PAGE.marginTop + PAGE.headerHeight;
        currentCol = 0;
      }
    }

    doc.text(`${num}. ${title.toUpperCase()}`, colX[currentCol], colY);
    colY += 5;

    // Section body
    doc.setFont('times', 'normal');
    doc.setFontSize(9);
    doc.setTextColor(30, 30, 30);
    const bodyLines = doc.splitTextToSize(content, colW - 2);
    
    bodyLines.forEach(line => {
      if (colY > PAGE.height - PAGE.marginBottom - 10) {
        if (currentCol === 0) {
          currentCol = 1;
          colY = y;
        } else {
          doc.addPage();
          addBrandHeader(doc);
          addPageFooter(doc, doc.internal.getNumberOfPages());
          colY = PAGE.marginTop + PAGE.headerHeight;
          currentCol = 0;
        }
      }
      doc.text(line, colX[currentCol] + 1, colY);
      colY += 3.5;
    });

    colY += 3;
  };

  // Generate sections based on report type
  const sections = generateSections(config);
  sections.forEach((s, i) => addSection(toRoman(i + 1), s.title, s.content));

  // === DATA TABLE ===
  if (config.data && config.type === 'eis') {
    if (colY > PAGE.height - 60) {
      doc.addPage();
      addBrandHeader(doc);
      colY = PAGE.marginTop + PAGE.headerHeight;
    }
    
    doc.setFont('times', 'bold');
    doc.setFontSize(9);
    doc.text('TABLE I', PAGE.width / 2, colY + 5, { align: 'center' });
    doc.setFont('times', 'normal');
    doc.setFontSize(8);
    doc.text('EQUIVALENT CIRCUIT PARAMETERS', PAGE.width / 2, colY + 9, { align: 'center' });

    autoTable(doc, {
      startY: colY + 12,
      margin: { left: PAGE.marginLeft + 10, right: PAGE.marginRight + 10 },
      head: [['Parameter', 'Value', 'Unit']],
      body: generateParamsTable(config),
      theme: 'plain',
      styles: { fontSize: 8, font: 'times', cellPadding: 1.5 },
      headStyles: { fontStyle: 'bold', halign: 'center', lineWidth: 0.3, lineColor: [0, 0, 0] },
      bodyStyles: { halign: 'center' },
      columnStyles: { 0: { halign: 'left' } },
      didDrawPage: () => {
        addBrandHeader(doc);
        addPageFooter(doc, doc.internal.getNumberOfPages());
      },
    });
  }

  // === EMBED PLOTS ===
  if (config.plotCanvases?.length) {
    doc.addPage();
    addBrandHeader(doc);
    let plotY = PAGE.marginTop + PAGE.headerHeight + 5;

    doc.setFont('times', 'bold');
    doc.setFontSize(10);
    doc.text('FIGURES', PAGE.width / 2, plotY, { align: 'center' });
    plotY += 8;

    config.plotCanvases.forEach((canvas, idx) => {
      if (!canvas) return;
      try {
        const imgData = canvas.toDataURL('image/png');
        const plotW = PAGE.width - PAGE.marginLeft - PAGE.marginRight - 20;
        const plotH = plotW * 0.6;

        if (plotY + plotH > PAGE.height - PAGE.marginBottom - 20) {
          doc.addPage();
          addBrandHeader(doc);
          plotY = PAGE.marginTop + PAGE.headerHeight + 5;
        }

        doc.addImage(imgData, 'PNG', PAGE.marginLeft + 10, plotY, plotW, plotH);
        plotY += plotH + 4;

        // Figure caption
        doc.setFont('times', 'normal');
        doc.setFontSize(8);
        doc.setTextColor(0, 0, 0);
        doc.text(`Fig. ${idx + 1}. ${getFigureCaption(config.type, idx)}`, PAGE.width / 2, plotY, { align: 'center' });
        plotY += 10;
      } catch (e) {
        console.warn('Could not embed plot canvas:', e);
      }
    });
  }

  // === REFERENCES ===
  doc.addPage();
  addBrandHeader(doc);
  let refY = PAGE.marginTop + PAGE.headerHeight;
  doc.setFont('times', 'bold');
  doc.setFontSize(10);
  doc.text('REFERENCES', PAGE.marginLeft, refY);
  refY += 5;

  const refs = generateReferences(config.type);
  doc.setFont('times', 'normal');
  doc.setFontSize(8);
  refs.forEach((ref, i) => {
    const refLines = doc.splitTextToSize(`[${i + 1}] ${ref}`, PAGE.width - PAGE.marginLeft - PAGE.marginRight);
    refLines.forEach(line => {
      doc.text(line, PAGE.marginLeft, refY);
      refY += 3;
    });
    refY += 1;
  });

  // Footer on all pages
  const totalPages = doc.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    addPageFooter(doc, i);
  }

  // Save
  const filename = `RAMAN_IEEE_${config.type || 'report'}_${Date.now()}.pdf`;
  doc.save(filename);
  return filename;
}

// === HELPER FUNCTIONS ===

function addBrandHeader(doc) {
  // Thin branded strip at top
  doc.setFillColor(0, 0, 0);
  doc.rect(0, 0, PAGE.width, 12, 'F');
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7);
  doc.setTextColor(...BRAND.color);
  doc.text(`${BRAND.studio}`, PAGE.marginLeft, 8);
  doc.setTextColor(150, 150, 150);
  doc.setFont('helvetica', 'normal');
  doc.text(`by ${BRAND.name} — ${BRAND.tagline}`, PAGE.marginLeft + 30, 8);
  doc.setTextColor(100, 100, 100);
  doc.text(new Date().toISOString().split('T')[0], PAGE.width - PAGE.marginRight, 8, { align: 'right' });
}

function addPageFooter(doc, pageNum) {
  doc.setFont('times', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(120, 120, 120);
  doc.text(`${pageNum}`, PAGE.width / 2, PAGE.height - 10, { align: 'center' });
  doc.setFontSize(6);
  doc.text('Generated by RAMAN Studio — VidyuthLabs Pvt. Ltd.', PAGE.width / 2, PAGE.height - 6, { align: 'center' });
}

function toRoman(num) {
  const map = [[10,'X'],[9,'IX'],[5,'V'],[4,'IV'],[1,'I']];
  let result = '';
  for (const [val, sym] of map) {
    while (num >= val) { result += sym; num -= val; }
  }
  return result;
}

function generateAbstract(config) {
  const type = config.type || 'eis';
  const params = config.params || {};
  const data = config.data || {};

  const abstracts = {
    eis: `This paper presents electrochemical impedance spectroscopy (EIS) analysis performed using the RAMAN Studio simulation platform. The impedance response of an electrochemical system was modeled using a modified Randles equivalent circuit with constant phase element (CPE) correction. The solution resistance (Rs = ${params.Rs || '—'} Ohm), charge transfer resistance (Rct = ${params.Rct || '—'} Ohm), and double-layer capacitance (Cdl = ${params.Cdl || '—'} F) were characterized across a frequency range of ${params.f_min || 0.01} Hz to ${params.f_max || '1e6'} Hz. Nyquist and Bode representations were generated following Electrochemical Society (ECS) publication guidelines with 1:1 aspect ratio orthonormal axes. The results demonstrate the platform's capability for high-fidelity electrochemical impedance modeling with publication-grade visualization output.`,
    cv: `Cyclic voltammetry (CV) analysis was performed to characterize the electrochemical behavior of the target system. The experiment was simulated using Butler-Volmer kinetics with Nernstian diffusion constraints. The resulting voltammograms follow IUPAC conventions with anodic currents plotted as positive values. Peak separation, reversibility indices, and diffusion coefficients were extracted from the simulation data.`,
    biosensor: `This report details the computational design and fabrication protocol for an electrochemical biosensor targeting ${config.params?.analyte || 'glucose'} detection. The sensor architecture employs ${config.params?.pattern || 'screen-printed'} electrode geometry with ${config.params?.ink || 'gold nanoparticle'} ink formulation and ${config.params?.sam || 'thiol-gold'} surface functionalization. Performance metrics including sensitivity, limit of detection (LOD), response time, and selectivity were predicted through multi-physics simulation.`,
    alchemi: `Materials characterization was performed using the NVIDIA Alchemi quantum simulation engine integrated within RAMAN Studio. The material's electronic structure, including bandgap, HOMO-LUMO levels, density, and thermal properties were computed using machine-learned interatomic potentials (MLIP). Electrochemical impedance and cyclic voltammetry parameters were automatically derived from the quantum mechanical properties for seamless integration with experimental measurement workflows.`,
    battery: `Printed battery performance was simulated using single-particle model (SPM) methodology. The galvanostatic charge-discharge characteristics, capacity retention, and rate capability were analyzed across multiple C-rates. The simulation incorporates Peukert's law for capacity correction and provides predictive aging curves for lifecycle estimation.`,
  };
  return abstracts[type] || abstracts.eis;
}

function generateKeywords(type) {
  const kw = {
    eis: 'electrochemical impedance spectroscopy, Randles circuit, CPE, Nyquist plot, Bode analysis',
    cv: 'cyclic voltammetry, Butler-Volmer kinetics, electron transfer, redox potential',
    biosensor: 'biosensor, electrode fabrication, SAM, analyte detection, LOD',
    alchemi: 'materials informatics, MLIP, quantum simulation, bandgap, electronic structure',
    battery: 'printed battery, SPM, galvanostatic, C-rate, capacity retention',
  };
  return kw[type] || kw.eis;
}

function generateSections(config) {
  const type = config.type || 'eis';
  const p = config.params || {};
  const d = config.data || {};

  if (type === 'eis') {
    return [
      { title: 'Introduction', content: `Electrochemical Impedance Spectroscopy (EIS) is a powerful technique for characterizing electrochemical systems by measuring the impedance response as a function of frequency [1]. The technique provides critical information about charge transfer kinetics, mass transport, and interfacial properties. In this study, we employ the RAMAN Studio simulation engine to model the impedance response of a Randles-type equivalent circuit with constant phase element (CPE) correction for electrode roughness effects [2]. The simulation covers a frequency range spanning ${p.f_min || 0.01} Hz to ${p.f_max || '1e6'} Hz with ${p.n_points || 100} logarithmically-spaced data points. All plots follow the Electrochemical Society (ECS) publication guidelines, including orthonormal 1:1 aspect ratio for Nyquist representations [3].` },
      { title: 'Experimental / Simulation Setup', content: `The electrochemical system was modeled using the following equivalent circuit parameters: Solution resistance Rs = ${p.Rs || '—'} Ohm, Charge transfer resistance Rct = ${p.Rct || '—'} Ohm, Double-layer capacitance / CPE coefficient Cdl = ${p.Cdl || '—'} F, Warburg coefficient sigma_w = ${p.sigma_w || '—'} Ohm.s^(-0.5), CPE exponent n = ${p.n_cpe || '—'}. The impedance was computed using the modified Randles circuit: Z(omega) = Rs + 1 / [Y_CPE + 1/(Rct + Z_W)], where Y_CPE = Q0(j.omega)^n and Z_W = sigma_w(1-j)/sqrt(omega). The computation was performed using the RAMAN Studio C++/Python hybrid engine with double-precision floating-point arithmetic.` },
      { title: 'Results and Discussion', content: `The impedance data is presented in both Nyquist (Z' vs. -Z'') and Bode (|Z| and phase vs. frequency) representations. The Nyquist plot exhibits the characteristic semicircular arc at high frequencies attributed to the parallel combination of Rct and Cdl, followed by a 45-degree Warburg diffusion tail at lower frequencies. The semicircle diameter corresponds to the charge transfer resistance Rct = ${p.Rct || '—'} Ohm, while the high-frequency intercept yields Rs = ${p.Rs || '—'} Ohm. The CPE exponent n = ${p.n_cpe || '—'} indicates ${(p.n_cpe || 0.9) > 0.95 ? 'near-ideal capacitive behavior' : 'non-ideal capacitive behavior consistent with surface roughness or heterogeneity'}. The Bode magnitude plot shows the expected plateau at high frequencies (|Z| approaches Rs) and increasing impedance at low frequencies dominated by Warburg diffusion. The phase angle approaches zero at the highest frequencies (purely resistive behavior) and shows a characteristic minimum near the RC time constant frequency.` },
      { title: 'Conclusion', content: `The EIS simulation demonstrates the capability of RAMAN Studio for high-fidelity electrochemical impedance modeling. The Randles circuit with CPE correction accurately captures the essential physics of charge transfer, double-layer charging, and mass transport phenomena. The publication-quality plots generated by the platform follow ECS guidelines and are suitable for direct inclusion in peer-reviewed manuscripts. Future work will extend the analysis to include temperature-dependent kinetics and multi-element equivalent circuit optimization using the integrated Levenberg-Marquardt / Differential Evolution fitting engine.` },
    ];
  }

  if (type === 'biosensor') {
    const perf = d?.performance || {};
    return [
      { title: 'Introduction', content: `Electrochemical biosensors represent a critical technology for point-of-care diagnostics, environmental monitoring, and food safety [1]. This report presents the computational design and optimization of an electrochemical biosensor for ${p.analyte || 'glucose'} detection using the RAMAN Studio biosensor fabrication engine. The platform integrates electrode geometry design, ink formulation selection, surface chemistry optimization, and performance prediction in a unified workflow.` },
      { title: 'Sensor Architecture', content: `The biosensor was designed using a ${p.pattern || 'screen-printed'} electrode pattern with ${p.ink || 'gold nanoparticle'} ink formulation. Surface functionalization employed ${p.sam || 'thiol-gold'} self-assembled monolayer (SAM) chemistry. The coating was applied using ${p.coating_method || 'spin'} coating technique${p.coating_method === 'spin' ? ` at ${p.spin_rpm || 3000} RPM for ${p.spin_time_s || 30} seconds` : ''}. The electrode geometry was optimized for maximum electroactive surface area while maintaining reproducible manufacturing tolerance.` },
      { title: 'Predicted Performance', content: `The simulation predicts the following performance metrics: Sensitivity = ${perf.sensitivity_uA_mM_cm2 || '—'} uA/mM/cm2, Limit of Detection (LOD) = ${perf.lod_M || '—'} M, Response Time = ${perf.response_time_s || '—'} s, Operational Stability = ${perf.stability_days || '—'} days, Selectivity = ${perf.selectivity_pct || '—'}%, Reproducibility (RSD) = ${perf.reproducibility_rsd_pct || '—'}%. These metrics indicate ${(perf.sensitivity_uA_mM_cm2 || 0) > 50 ? 'excellent' : 'adequate'} sensitivity for clinical-grade ${p.analyte || 'glucose'} detection applications.` },
      { title: 'Conclusion', content: `The computational biosensor design platform demonstrates the ability to predict key performance metrics prior to physical fabrication, significantly reducing development time and material costs. The designed sensor shows promising characteristics for ${p.analyte || 'glucose'} detection with competitive sensitivity and LOD values compared to published literature [2-4]. Physical validation through fabrication and electrochemical testing is recommended as the next step.` },
    ];
  }

  // Default generic sections
  return [
    { title: 'Introduction', content: 'This report presents electrochemical analysis results generated using the RAMAN Studio platform by VidyuthLabs. The analysis employs state-of-the-art computational methods for accurate prediction of electrochemical behavior.' },
    { title: 'Methodology', content: 'The simulation was configured using the parameters specified in the accompanying data tables. The computation engine utilizes hybrid C++/Python architecture for optimal performance and numerical accuracy.' },
    { title: 'Results', content: 'The simulation results are presented in the accompanying figures and tables. Detailed analysis of the electrochemical response reveals the characteristic features of the modeled system.' },
    { title: 'Conclusion', content: 'The RAMAN Studio platform provides publication-quality simulation and visualization capabilities for electrochemical research. The results are suitable for direct inclusion in peer-reviewed publications following IEEE and ECS formatting guidelines.' },
  ];
}

function generateParamsTable(config) {
  const p = config.params || {};
  const type = config.type || 'eis';

  if (type === 'eis') {
    return [
      ['Rs (Solution Resistance)', `${p.Rs || '—'}`, 'Ohm'],
      ['Rct (Charge Transfer Resistance)', `${p.Rct || '—'}`, 'Ohm'],
      ['Cdl / Q0 (Capacitance / CPE)', `${p.Cdl || '—'}`, 'F'],
      ['sigma_w (Warburg Coefficient)', `${p.sigma_w || '—'}`, 'Ohm.s^-0.5'],
      ['n (CPE Exponent)', `${p.n_cpe || '—'}`, '—'],
      ['Frequency Range', `${p.f_min || 0.01} - ${p.f_max || '1e6'}`, 'Hz'],
      ['Data Points', `${p.n_points || 100}`, '—'],
    ];
  }
  return [['Parameter', 'Value', 'Unit']];
}

function getFigureCaption(type, idx) {
  const captions = {
    eis: ['Nyquist plot (Z\' vs. -Z\'\') of the electrochemical system. Data points represent simulated impedance; solid line shows equivalent circuit fit.', 'Bode plot showing impedance magnitude and phase angle as functions of frequency.'],
    cv: ['Cyclic voltammogram showing current response as a function of applied potential (IUPAC convention).'],
    biosensor: ['3D electrode architecture rendering showing substrate, working electrode, and functionalization layers.', 'Fabrication protocol timeline with critical process steps highlighted.'],
    alchemi: ['3D molecular structure visualization of the analyzed material with element-colored spheres and bond representations.'],
  };
  return (captions[type] || captions.eis)[idx] || `Simulation result visualization (Figure ${idx + 1}).`;
}

function generateReferences(type) {
  const refs = {
    eis: [
      'E. Barsoukov and J. R. Macdonald, "Impedance Spectroscopy: Theory, Experiment, and Applications," 3rd ed. Hoboken, NJ: Wiley, 2018.',
      'B. A. Boukamp, "A Linear Kronig-Kramers Transform Test for Immittance Data Validation," J. Electrochem. Soc., vol. 142, no. 6, pp. 1885-1894, 1995.',
      'M. E. Orazem and B. Tribollet, "Electrochemical Impedance Spectroscopy," 2nd ed. Hoboken, NJ: Wiley, 2017.',
      'A. Lasia, "Electrochemical Impedance Spectroscopy and its Applications," New York: Springer, 2014.',
      'Electrochemical Society, "Guide for Authors," J. Electrochem. Soc., 2024. [Online]. Available: https://iopscience.iop.org/journal/1945-7111',
    ],
    cv: [
      'A. J. Bard and L. R. Faulkner, "Electrochemical Methods: Fundamentals and Applications," 3rd ed. Hoboken, NJ: Wiley, 2022.',
      'R. G. Compton and C. E. Banks, "Understanding Voltammetry," 3rd ed. London: World Scientific, 2018.',
      'N. Elgrishi et al., "A Practical Beginner\'s Guide to Cyclic Voltammetry," J. Chem. Educ., vol. 95, no. 2, pp. 197-206, 2018.',
    ],
    biosensor: [
      'J. Wang, "Electrochemical Biosensors: Towards Point-of-Care Cancer Diagnostics," Biosens. Bioelectron., vol. 21, no. 10, pp. 1887-1892, 2006.',
      'A. P. F. Turner, "Biosensors: Sense and Sensibility," Chem. Soc. Rev., vol. 42, no. 8, pp. 3184-3196, 2013.',
      'P. Yáñez-Sedeño et al., "Electrochemical Biosensors in Hormone Detection," Anal. Chem., vol. 92, pp. 12083-12113, 2020.',
      'S. Kurbanoglu et al., "Electrochemical Biosensor Development," Biosens. Bioelectron., vol. 151, p. 111996, 2020.',
    ],
    alchemi: [
      'M. Rupp et al., "Machine Learning for Molecular and Materials Science," Nature, vol. 559, pp. 547-555, 2018.',
      'C. Chen et al., "A Universal Graph Deep Learning Interatomic Potential for the Periodic Table," Nat. Comput. Sci., vol. 2, pp. 718-728, 2022.',
      'I. Batatia et al., "MACE: Higher Order Equivariant Message Passing Neural Networks," NeurIPS 2022.',
    ],
  };
  return refs[type] || refs.eis;
}

export default generateIEEEReport;
