import React from 'react';
import ReactDOM from 'react-dom/client';

// Bundled fonts — Tauri has no system Inter/Plex Mono guaranteed. Importing
// the variable-weight roman + italic + the four common static weights covers
// every use we have without bloating the bundle by much (~110 KB total gzip).
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';

import App from './App';
import './styles/index.css';

// ── Tauri compatibility shim ──────────────────────────────────────
// If running inside Tauri, expose window.raman with the same API
// surface the Electron preload used, so the rest of the UI doesn't
// need to change.
(async () => {
  if (typeof window !== 'undefined' && window.__TAURI_INTERNALS__) {
    const { open, save } = await import('@tauri-apps/plugin-dialog');
    const { listen } = await import('@tauri-apps/api/event');
    const { invoke } = await import('@tauri-apps/api/core');

    const BACKEND = 'http://127.0.0.1:8000';

    window.raman = {
      api: {
        get: (path) => fetch(BACKEND + path).then(r => r.ok ? r.json() : Promise.reject(r)),
        call: (path, body) => fetch(BACKEND + path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }).then(r => r.ok ? r.json() : Promise.reject(r)),
      },
      fs: {
        openProject: async () => {
          const path = await open({
            title: 'Open RĀMAN project',
            filters: [{ name: 'RĀMAN project', extensions: ['raman', 'json'] }],
          });
          if (!path) return null;
          const content = await invoke('plugin:fs|read_text_file', { path });
          return { path, content };
        },
        saveProject: async (content, defaultPath) => {
          const path = await save({
            title: 'Save RĀMAN project',
            defaultPath: defaultPath || 'project.raman',
            filters: [{ name: 'RĀMAN project', extensions: ['raman', 'json'] }],
          });
          if (!path) return null;
          await invoke('plugin:fs|write_text_file', { path, contents: content });
          return { path };
        },
        openLabXlsx: async () => {
          const path = await open({
            title: 'Open lab data',
            filters: [{ name: 'Lab data', extensions: ['xlsx', 'xls', 'csv', 'json'] }],
          });
          if (!path) return null;
          const arr = await invoke('plugin:fs|read_file', { path });
          const buf = new Uint8Array(arr);
          const name = path.split(/[\\/]/).pop();
          return { path, name, buffer: btoa(String.fromCharCode(...buf)) };
        },
      },
      onMenu: (event, callback) => {
        const unlisten = listen('menu:' + event, (e) => callback(e.payload));
        return () => unlisten.then(fn => fn());
      },
    };
  }
})();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
