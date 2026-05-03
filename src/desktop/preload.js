/**
 * RĀMAN Studio — Electron Preload Script
 * ========================================
 * Context bridge between renderer (React) and main process.
 * Exposes a secure API via window.raman.
 *
 * Security: Only whitelisted channels are exposed.
 * No direct Node.js access in the renderer.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Whitelist of allowed IPC channels
const ALLOWED_SEND = [
    'app-ready',
    'request-gpu-status',
    'request-license-info',
];

const ALLOWED_INVOKE = [
    'get-gpu-status',
    'get-license-info',
    'open-file-dialog',
    'save-file-dialog',
    'show-message-box',
];

const ALLOWED_RECEIVE = [
    'menu-new-project',
    'menu-open-project',
    'menu-save-project',
    'menu-export-results',
    'menu-gpu-status',
    'menu-gpu-benchmark',
    'menu-gpu-clear-cache',
    'menu-license-info',
    'menu-activate-license',
    'menu-start-trial',
    'simulation-progress',
    'simulation-complete',
];

contextBridge.exposeInMainWorld('raman', {
    // ── Version Info ──────────────────────────────────────
    version: '2.0.0',
    platform: process.platform,

    // ── IPC: Send (fire-and-forget) ──────────────────────
    send: (channel, data) => {
        if (ALLOWED_SEND.includes(channel)) {
            ipcRenderer.send(channel, data);
        } else {
            console.warn('Blocked IPC send:', channel);
        }
    },

    // ── IPC: Invoke (request-response) ───────────────────
    invoke: (channel, ...args) => {
        if (ALLOWED_INVOKE.includes(channel)) {
            return ipcRenderer.invoke(channel, ...args);
        }
        console.warn('Blocked IPC invoke:', channel);
        return Promise.reject(new Error(`Blocked channel: ${channel}`));
    },

    // ── IPC: Receive (listen for events) ─────────────────
    on: (channel, callback) => {
        if (ALLOWED_RECEIVE.includes(channel)) {
            const subscription = (_event, ...args) => callback(...args);
            ipcRenderer.on(channel, subscription);
            return () => ipcRenderer.removeListener(channel, subscription);
        }
        console.warn('Blocked IPC listener:', channel);
        return () => {};
    },

    // ── Backend API helpers ──────────────────────────────
    api: {
        /**
         * Call the Python backend API.
         * @param {string} endpoint - API path (e.g., '/api/simulate')
         * @param {object} data - Request body
         * @returns {Promise<object>} Response data
         */
        call: async (endpoint, data = {}) => {
            const port = 8000;
            const url = `http://127.0.0.1:${port}${endpoint}`;
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                });
                if (!response.ok) {
                    let body = '';
                    try { body = (await response.text()).slice(0, 300); } catch {}
                    const err = new Error(`POST ${endpoint} → ${response.status}: ${body}`);
                    err.status = response.status;
                    err.url = url;
                    throw err;
                }
                return await response.json();
            } catch (error) {
                console.error(`API POST ${endpoint} failed:`, error?.message || error);
                throw error;
            }
        },

        /**
         * GET request to backend.
         */
        get: async (endpoint) => {
            const port = 8000;
            const url = `http://127.0.0.1:${port}${endpoint}`;
            try {
                const response = await fetch(url);
                if (!response.ok) {
                    let body = '';
                    try { body = (await response.text()).slice(0, 300); } catch {}
                    const err = new Error(`GET ${endpoint} → ${response.status}: ${body}`);
                    err.status = response.status;
                    err.url = url;
                    throw err;
                }
                return await response.json();
            } catch (error) {
                console.error(`API GET ${endpoint} failed:`, error?.message || error);
                throw error;
            }
        },
    },
});

console.log('🔒 RĀMAN Studio preload initialized (context-isolated)');
