/**
 * Tauri API Bridge
 *
 * Detects whether we are running inside Tauri or in a regular browser,
 * and provides a unified interface for calling backend functions.
 *
 * In Tauri mode: calls Rust directly via `invoke`
 * In browser/Electron mode: falls back to HTTP fetch against the Python backend
 */

let tauriInvoke = null;
let tauriDialog = null;

// Lazy-load Tauri APIs (they fail gracefully if not in Tauri)
async function getTauriInvoke() {
  if (tauriInvoke) return tauriInvoke;
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    tauriInvoke = invoke;
    return invoke;
  } catch {
    return null;
  }
}

async function getTauriDialog() {
  if (tauriDialog) return tauriDialog;
  try {
    const dialog = await import('@tauri-apps/plugin-dialog');
    tauriDialog = dialog;
    return dialog;
  } catch {
    return null;
  }
}

/** True if running inside Tauri */
export function isTauri() {
  return '__TAURI_INTERNALS__' in window;
}

// ── EIS ────────────────────────────────────────────────────

export async function simulateEIS(params, fMin = 0.01, fMax = 1e6, nPoints = 100) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('simulate_eis', {
      request: { params, f_min: fMin, f_max: fMax, n_points: nPoints },
    });
  }
  // Fallback: HTTP
  const r = await fetch('/api/physics/eis/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ params, f_min: fMin, f_max: fMax, n_points: nPoints }),
  });
  if (!r.ok) throw new Error(`EIS simulation failed: ${r.status}`);
  return r.json();
}

// ── CV ─────────────────────────────────────────────────────

export async function simulateCV(params, nPoints = 500) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('simulate_cv', {
      request: { params, n_points: nPoints },
    });
  }
  const r = await fetch('/api/physics/cv/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ params, n_points: nPoints }),
  });
  if (!r.ok) throw new Error(`CV simulation failed: ${r.status}`);
  return r.json();
}

// ── DRT ────────────────────────────────────────────────────

export async function computeDRT(frequencies, zReal, zImag, params = {}) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('compute_drt', {
      request: { frequencies, z_real: zReal, z_imag: zImag, params },
    });
  }
  const r = await fetch('/api/physics/drt/compute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ frequencies, z_real: zReal, z_imag: zImag, params }),
  });
  if (!r.ok) throw new Error(`DRT computation failed: ${r.status}`);
  return r.json();
}

// ── Kramers-Kronig ─────────────────────────────────────────

export async function kramersKronigTest(frequencies, zReal, zImag) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('kramers_kronig_test', {
      request: { frequencies, z_real: zReal, z_imag: zImag },
    });
  }
  const r = await fetch('/api/physics/kk/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ frequencies, z_real: zReal, z_imag: zImag }),
  });
  if (!r.ok) throw new Error(`KK test failed: ${r.status}`);
  return r.json();
}

// ── Circuit Fitting ────────────────────────────────────────

export async function fitCircuit(frequencies, zReal, zImag, initialParams, fitParams = {}) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('fit_circuit', {
      request: {
        frequencies,
        z_real: zReal,
        z_imag: zImag,
        initial_params: initialParams,
        fit_params: fitParams,
      },
    });
  }
  const r = await fetch('/api/physics/fit/circuit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      frequencies, z_real: zReal, z_imag: zImag,
      initial_params: initialParams, fit_params: fitParams,
    }),
  });
  if (!r.ok) throw new Error(`Circuit fitting failed: ${r.status}`);
  return r.json();
}

// ── Data Import/Export ─────────────────────────────────────

export async function importCSV(filePath) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('import_csv', { filePath });
  }
  throw new Error('CSV import requires Tauri native file access');
}

export async function exportCSV(filePath, headers, data) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('export_csv', { filePath, headers, data });
  }
  throw new Error('CSV export requires Tauri native file access');
}

// ── File Dialogs ───────────────────────────────────────────

export async function openFileDialog(filters = []) {
  const dialog = await getTauriDialog();
  if (dialog) {
    const result = await dialog.open({
      multiple: false,
      filters: filters.length ? filters : [
        { name: 'CSV Files', extensions: ['csv', 'txt'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    return result;
  }
  // Browser fallback: use input element
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = filters.map(f => f.extensions.map(e => `.${e}`).join(',')).join(',') || '.csv,.txt';
    input.onchange = () => resolve(input.files[0]?.name || null);
    input.click();
  });
}

export async function saveFileDialog(defaultName, filters = []) {
  const dialog = await getTauriDialog();
  if (dialog) {
    const result = await dialog.save({
      defaultPath: defaultName,
      filters: filters.length ? filters : [
        { name: 'CSV Files', extensions: ['csv'] },
        { name: 'JSON Files', extensions: ['json'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    return result;
  }
  return null;
}

// ── Project Management ─────────────────────────────────────

export async function createProject(name, description = '') {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('create_project', { name, description });
  }
  return {
    id: `proj_${Date.now()}`,
    name,
    description,
    created_at: new Date().toISOString(),
    modified_at: new Date().toISOString(),
    version: '3.0.0',
    datasets: [],
    simulations: [],
  };
}

export async function saveProject(filePath, project) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('save_project', { filePath, project });
  }
  // Browser fallback: download as JSON
  const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filePath || 'project.raman';
  a.click();
  URL.revokeObjectURL(url);
}

export async function loadProject(filePath) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('load_project', { filePath });
  }
  throw new Error('Project loading requires Tauri native file access');
}

// ── Analysis Engine (Python) ────────────────────────────────

export async function runAnalysis(filePath, style = 'nature', outputDir = null) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('run_analysis', {
      file_path: filePath,
      style,
      output_dir: outputDir,
    });
  }
  const r = await fetch('/api/analysis/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: filePath, style, output_dir: outputDir }),
  });
  if (!r.ok) throw new Error(`Analysis failed: ${r.status}`);
  return r.json();
}

export async function listPlotStyles() {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('list_plot_styles');
  }
  return [
    'nature', 'science', 'acs', 'ieee', 'rsc', 'elsevier',
    'springer', 'wiley', 'aps', 'iop', 'aip', 'agu',
    'default', 'dark', 'presentation',
  ];
}

export async function listExampleDatasets() {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('list_example_datasets');
  }
  return [];
}

// ── Materials Screening ─────────────────────────────────────

export async function searchElectrodeMaterials(category = null) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('search_electrode_materials', { category });
  }
  return [];
}

export async function predictMaterialPerformance(formula, bandGap, energyAboveHull, density) {
  const invoke = await getTauriInvoke();
  if (invoke) {
    return invoke('predict_material_performance', {
      formula,
      band_gap: bandGap,
      energy_above_hull: energyAboveHull,
      density,
    });
  }
  throw new Error('Material prediction requires Tauri backend');
}

// ── Utility: All Available Engines ──────────────────────────

export function getAvailableEngines() {
  return [
    {
      id: 'eis_simulator',
      name: 'EIS Simulator',
      description: 'Randles/CPE impedance simulation with Warburg diffusion',
      backend: 'Rust (nalgebra + rayon)',
    },
    {
      id: 'cv_simulator',
      name: 'CV Simulator',
      description: 'Cyclic voltammetry with Butler-Volmer kinetics and iR correction',
      backend: 'Rust (convolution + Crank-Nicolson)',
    },
    {
      id: 'drt_analyzer',
      name: 'DRT Analyzer',
      description: 'Distribution of Relaxation Times via Tikhonov regularization',
      backend: 'Rust (nalgebra) + pyDRTtools (Python)',
    },
    {
      id: 'circuit_fitter',
      name: 'Circuit Fitter',
      description: 'Levenberg-Marquardt CNLS fitting for equivalent circuits',
      backend: 'Rust + impedance.py (Python)',
    },
    {
      id: 'analysis_engine',
      name: 'Auto-Analysis Engine',
      description: 'Auto-detect technique (CV/EIS/DPV/GCD/Raman), extract metrics, publication plots',
      backend: 'Electrochem-Suite (Python) + MADAP',
    },
    {
      id: 'materials_screener',
      name: 'Materials Screener',
      description: 'Screen electrode materials for supercapacitor/sensor applications',
      backend: 'Materials Project API + ML prediction',
    },
    {
      id: 'ml_predictor',
      name: 'ML Property Predictor',
      description: 'Predict capacitance, sensitivity, LOD from material features',
      backend: 'scikit-learn (inverse-distance weighted from literature data)',
    },
  ];
}
