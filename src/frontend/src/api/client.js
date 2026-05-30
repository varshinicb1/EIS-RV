/**
 * Centralized API Client for RĀMAN Studio Frontend
 *
 * Handles the three environments we run in:
 *  - Vite dev server (browser): uses relative URLs + Vite proxy (/api → localhost:8000)
 *  - Tauri dev: same as above or explicit base via VITE_API_BASE
 *  - Tauri production build: MUST use absolute http://127.0.0.1:8000 because relative
 *    fetches hit Tauri's asset protocol SPA fallback and return index.html.
 *
 * Usage in components:
 *   import { api, apiFetch, isTauri, getApiBase } from '../api/client';
 *
 *   const license = await api.getLicense();
 *   const result  = await apiFetch('/api/v2/eis', { method: 'POST', body: JSON.stringify(payload) });
 */

import { isTauri as isTauriInternal } from './tauri.js';

// Re-export the reliable detector
export { isTauriInternal as isTauri };

const DEFAULT_TAURI_BACKEND = 'http://127.0.0.1:8000';

/**
 * Returns the base URL for the Python backend.
 * - Non-Tauri (Vite dev): returns '' (or VITE_API_BASE) so the proxy in vite.config.js kicks in.
 * - Tauri (dev + prod): returns absolute URL (critical for packaged builds).
 */
export function getApiBase() {
  // Allow override via .env (VITE_API_BASE=http://192.168.1.50:8000)
  const envBase = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE) || '';

  if (isTauriInternal()) {
    return envBase || DEFAULT_TAURI_BACKEND;
  }
  // Browser / Vite dev → relative is preferred because of the proxy
  return envBase || '';
}

/**
 * Low-level fetch wrapper with consistent error handling and JSON parsing.
 */
export async function apiFetch(path, options = {}) {
  const base = getApiBase();
  const url = path.startsWith('http') 
    ? path 
    : `${base}${path.startsWith('/') ? '' : '/'}${path}`;

  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`;
    try {
      const data = await res.json();
      message = data.detail || data.message || data.error || message;
    } catch {
      // Not JSON or empty body
      try {
        const text = await res.text();
        if (text) message = text.slice(0, 300);
      } catch {}
    }
    const err = new Error(message);
    err.status = res.status;
    err.url = url;
    throw err;
  }

  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  return res.text();
}

/** Convenience HTTP methods */
export const api = {
  get: (path, options) => apiFetch(path, { method: 'GET', ...(options || {}) }),
  post: (path, body, options) => apiFetch(path, { 
    method: 'POST', 
    body: body ? JSON.stringify(body) : undefined, 
    ...(options || {}) 
  }),
  put: (path, body, options) => apiFetch(path, { 
    method: 'PUT', 
    body: body ? JSON.stringify(body) : undefined, 
    ...(options || {}) 
  }),
  del: (path, options) => apiFetch(path, { method: 'DELETE', ...(options || {}) }),

  // ── High-level domain helpers (add more as needed) ─────────────────────

  // Licensing & Settings
  getLicense: () => api.get('/api/v2/auth/license'),
  activateLicense: (token) => api.post('/api/v2/auth/license/activate', { token }),
  deactivateLicense: () => api.post('/api/v2/auth/license/deactivate'),
  getHardwareId: () => api.get('/api/v2/auth/hardware-id'),
  getNvidiaKeyStatus: () => api.get('/api/v2/settings/nvidia-key/status'),
  validateNvidiaKey: (key) => api.post('/api/v2/settings/validate-nvidia-key', { key }),
  saveNvidiaKey: (key) => api.post('/api/v2/settings/nvidia-key', { key }),

  // Core Simulation
  simulateEIS: (payload) => api.post('/api/v2/eis', payload),
  simulateCV: (payload) => api.post('/api/v2/cv', payload),
  analyzeDRT: (payload) => api.post('/api/v2/drt/analyze', payload),
  fitCircuit: (payload) => api.post('/api/v2/circuit/fit', payload),
  kramersKronig: (payload) => api.post('/api/v2/kk/test', payload),

  // Lab Data
  listLabDatasets: () => api.get('/api/v2/lab/datasets'),
  importLabXlsx: (datasetId, filePath) => 
    api.post(`/api/v2/lab/datasets/${datasetId}/import/xlsx`, { file_path: filePath }),

  // Reports
  listReports: () => api.get('/api/v2/reports'),
  generateReport: (payload) => api.post('/api/v2/reports/generate', payload),

  // Research / Pipeline
  getPipelineStats: () => api.get('/api/v2/pipeline/stats'),
  searchPapers: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api.get(`/api/v2/pipeline/papers?${qs}`);
  },
  runResearchPipeline: (opts = {}) => api.post('/api/v2/pipeline/run', opts),

  // Alchemi / Materials AI
  getAlchemiStatus: () => api.get('/api/v2/alchemi/status'),
  getAlchemiProperties: (payload) => api.post('/api/v2/alchemi/properties', payload),
  alchemiChat: (payload) => api.post('/api/v2/alchemi/chat', payload),
  searchMaterials: (query) => api.get(`/api/v2/alchemi/search/${encodeURIComponent(query)}`),

  // Google Drive + Literature
  getDriveStatus: () => api.get('/api/v2/drive/status'),
  driveSync: (force = false) => api.post(`/api/v2/drive/sync?force=${force}`),
  driveReview: () => api.get('/api/v2/drive/review'),

  // System / Telemetry (used by Dashboard)
  getSystemMetrics: () => api.get('/api/v2/system/metrics', { cache: 'no-store' }),

  // Vision Tour + E2E interop (Drive + local Qwen brain + unified Lab Brain + sims)
  getHealth: () => api.get('/health'),
  getAgentStatus: () => api.get('/api/v2/agent/status'),
  structurePaper: (fullText) => api.post('/api/v2/agent/structure-paper', { full_text: fullText }),
  brainSync: () => api.post('/api/v2/brain/knowledge/sync'),
  getBrainStatus: () => api.get('/api/v2/brain/status'),
  // New from best-of-n Cand 1 winner (honest self-improving A memory)
  getEnrichmentStatus: () => api.get('/api/v2/brain/enrichment/status'),

  // Human researcher flow (FOG/Silver vanadate/Electrochem-suite real data + ML + explain)
  runFogShapAnalysis: (opts = {}) => api.post('/api/v2/lab/run-fog-shap', opts),
  analyzeSilverVanadateCVs: (opts = {}) => api.post('/api/v2/lab/analyze-silver-vanadate', opts),
  listLabArtifacts: (params = {}) => api.get(`/api/v2/lab/artifacts?${new URLSearchParams(params)}`),
};

/** Helper to build full URL (useful for <a href> or image sources) */
export function buildUrl(path) {
  const base = getApiBase();
  return path.startsWith('http') ? path : `${base}${path.startsWith('/') ? '' : '/'}${path}`;
}

export default api;