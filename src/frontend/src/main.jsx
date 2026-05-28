import React from 'react';
import ReactDOM from 'react-dom/client';

// Bundled fonts — Electron has no system Inter/Plex Mono guaranteed. Importing
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

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
