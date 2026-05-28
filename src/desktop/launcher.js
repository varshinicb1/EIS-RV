/**
 * RĀMAN Studio — Runtime Launcher
 * ==================================
 * Manages lifecycle of all backend processes from Electron main process:
 *   - Python 3.14 backend (FastAPI)
 *   - Python 3.13 AI engine (ZMQ/REST)
 *   - Health monitoring + auto-restart
 *
 * Architecture:
 *   Electron Main → RuntimeLauncher → { Python314, Python313_AI }
 */

const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const EventEmitter = require('events');

class RuntimeLauncher extends EventEmitter {
    constructor(options = {}) {
        super();

        this.appRoot = options.appRoot || path.resolve(__dirname, '..', '..');
        this.backendPort = options.backendPort || 8000;
        this.aiZmqPort = options.aiZmqPort || 5557;
        this.aiRestPort = options.aiRestPort || 8013;

        // Process handles
        this._backendProc = null;
        this._aiProc = null;
        this._healthInterval = null;

        // State
        this.state = {
            backend: 'stopped',   // stopped | starting | running | error
            aiEngine: 'stopped',
        };
    }

    // ── Python Path Resolution ────────────────────────────

    _findPython(version = '3.14') {
        const candidates = [];

        if (process.platform === 'win32') {
            candidates.push(
                path.join(this.appRoot, '.venv', 'Scripts', 'python.exe'),
                path.join(this.appRoot, 'python', 'python.exe'),
                'python',
            );
        } else {
            if (version === '3.13') {
                candidates.push(
                    path.join(this.appRoot, '.venv313', 'bin', 'python3'),
                    '/usr/bin/python3.13',
                    'python3.13',
                );
            }
            candidates.push(
                path.join(this.appRoot, '.venv', 'bin', 'python3'),
                path.join(this.appRoot, '.venv', 'bin', 'python'),
                '/usr/bin/python3',
                'python3',
            );
        }

        return candidates[0]; // In production, would check each exists
    }

    // ── Backend (Python 3.14) ─────────────────────────────

    async startBackend() {
        if (this._backendProc) {
            console.log('[Launcher] Backend already running');
            return;
        }

        this.state.backend = 'starting';
        this.emit('state-change', this.state);

        const python = this._findPython('3.14');
        const mainPy = path.join(this.appRoot, 'vanl', 'backend', 'main.py');

        const env = {
            ...process.env,
            PYTHONPATH: this.appRoot,
            SERVER_PORT: String(this.backendPort),
            RAMAN_MODE: 'production',
        };

        console.log(`[Launcher] Starting backend: ${python} ${mainPy}`);

        this._backendProc = spawn(python, [mainPy], {
            cwd: this.appRoot,
            env,
            stdio: ['pipe', 'pipe', 'pipe'],
        });

        this._backendProc.stdout.on('data', (data) => {
            const msg = data.toString().trim();
            if (msg) console.log(`[Backend] ${msg}`);
        });

        this._backendProc.stderr.on('data', (data) => {
            const msg = data.toString().trim();
            if (msg) console.error(`[Backend:err] ${msg}`);
        });

        this._backendProc.on('exit', (code) => {
            console.log(`[Launcher] Backend exited: code=${code}`);
            this.state.backend = code === 0 ? 'stopped' : 'error';
            this._backendProc = null;
            this.emit('state-change', this.state);
        });

        // Wait for ready
        await this._waitForHealth(
            `http://127.0.0.1:${this.backendPort}/health`,
            30000
        );

        this.state.backend = 'running';
        this.emit('state-change', this.state);
        console.log('[Launcher] ✅ Backend ready');
    }

    // ── AI Engine (Python 3.13) ───────────────────────────

    async startAIEngine() {
        if (this._aiProc) {
            console.log('[Launcher] AI engine already running');
            return;
        }

        this.state.aiEngine = 'starting';
        this.emit('state-change', this.state);

        const python = this._findPython('3.13');
        const serverPy = path.join(this.appRoot, 'src', 'ai_engine', 'server.py');

        const env = {
            ...process.env,
            RAMAN_AI_ZMQ_PORT: String(this.aiZmqPort),
            RAMAN_AI_REST_PORT: String(this.aiRestPort),
            RAMAN_AI_MODE: 'zmq',
        };

        console.log(`[Launcher] Starting AI engine: ${python} ${serverPy}`);

        this._aiProc = spawn(python, [serverPy], {
            cwd: this.appRoot,
            env,
            stdio: ['pipe', 'pipe', 'pipe'],
        });

        this._aiProc.stdout.on('data', (data) => {
            console.log(`[AI-Engine] ${data.toString().trim()}`);
        });

        this._aiProc.stderr.on('data', (data) => {
            console.error(`[AI-Engine:err] ${data.toString().trim()}`);
        });

        this._aiProc.on('exit', (code) => {
            console.log(`[Launcher] AI engine exited: code=${code}`);
            this.state.aiEngine = code === 0 ? 'stopped' : 'error';
            this._aiProc = null;
            this.emit('state-change', this.state);
        });

        // Give it time to bind ZMQ socket
        await new Promise(r => setTimeout(r, 2000));

        this.state.aiEngine = 'running';
        this.emit('state-change', this.state);
        console.log('[Launcher] ✅ AI engine ready');
    }

    // ── Health Check ──────────────────────────────────────

    _waitForHealth(url, timeoutMs = 30000) {
        return new Promise((resolve, reject) => {
            const start = Date.now();

            const check = () => {
                if (Date.now() - start > timeoutMs) {
                    return reject(new Error(`Health timeout: ${url}`));
                }

                http.get(url, (res) => {
                    if (res.statusCode === 200) {
                        resolve();
                    } else {
                        setTimeout(check, 500);
                    }
                }).on('error', () => {
                    setTimeout(check, 500);
                });
            };

            setTimeout(check, 1000); // Initial delay
        });
    }

    startHealthMonitor(intervalMs = 10000) {
        this._healthInterval = setInterval(async () => {
            // Check backend
            if (this.state.backend === 'running') {
                try {
                    await this._waitForHealth(
                        `http://127.0.0.1:${this.backendPort}/health`, 5000
                    );
                } catch {
                    console.warn('[Health] Backend unreachable — restarting');
                    this.stopBackend();
                    this.startBackend();
                }
            }
        }, intervalMs);
    }

    // ── Shutdown ──────────────────────────────────────────

    stopBackend() {
        if (this._backendProc) {
            this._backendProc.kill('SIGTERM');
            this._backendProc = null;
            this.state.backend = 'stopped';
        }
    }

    stopAIEngine() {
        if (this._aiProc) {
            this._aiProc.kill('SIGTERM');
            this._aiProc = null;
            this.state.aiEngine = 'stopped';
        }
    }

    async shutdown() {
        console.log('[Launcher] Shutting down all runtimes...');
        if (this._healthInterval) clearInterval(this._healthInterval);
        this.stopBackend();
        this.stopAIEngine();
        // Grace period
        await new Promise(r => setTimeout(r, 1000));
        console.log('[Launcher] All runtimes stopped');
    }
}

module.exports = { RuntimeLauncher };
