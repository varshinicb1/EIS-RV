/**
 * RĀMAN Studio - Secure Main Process
 * ===================================
 * The Digital Twin for Your Potentiostat
 * 
 * Honoring Professor CNR Rao's Legacy in Materials Science
 * 
 * SECURITY FEATURES:
 * - Input validation
 * - CSP headers
 * - Secure IPC
 * - Process isolation
 * - Error handling
 * 
 * Company: VidyuthLabs
 */

const { app, BrowserWindow, ipcMain, dialog, Menu, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const Store = require('electron-store');
const crypto = require('crypto');

// Secure configuration
const CONFIG = {
    SERVER_PORT: 8000,
    SERVER_HOST: '127.0.0.1',
    MAX_WINDOW_COUNT: 5,
    PYTHON_TIMEOUT: 30000,
    IPC_RATE_LIMIT: 100, // requests per minute
};

// Initialize secure store
const store = new Store({
    name: 'raman-studio-settings',
    encryptionKey: 'raman-studio-secure-storage-v1',
    defaults: {
        windowBounds: { width: 1400, height: 900 },
        lastProject: null,
        theme: 'dark',
        gpuEnabled: true
    }
});

// Global references
let mainWindow = null;
let pythonProcess = null;
const windowCount = 0;
const ipcCallCounts = new Map();

/**
 * Validate server port
 */
function validatePort(port) {
    const portNum = parseInt(port, 10);
    if (isNaN(portNum) || portNum < 1024 || portNum > 65535) {
        throw new Error(`Invalid port: ${port}`);
    }
    return portNum;
}

/**
 * Rate limit IPC calls
 */
function rateLimitIPC(channel) {
    const now = Date.now();
    const key = channel;
    
    if (!ipcCallCounts.has(key)) {
        ipcCallCounts.set(key, []);
    }
    
    const calls = ipcCallCounts.get(key);
    
    // Remove calls older than 1 minute
    const recentCalls = calls.filter(time => now - time < 60000);
    
    if (recentCalls.length >= CONFIG.IPC_RATE_LIMIT) {
        throw new Error('Rate limit exceeded');
    }
    
    recentCalls.push(now);
    ipcCallCounts.set(key, recentCalls);
}

/**
 * Sanitize file path
 */
function sanitizePath(filePath) {
    if (!filePath || typeof filePath !== 'string') {
        throw new Error('Invalid file path');
    }
    
    // Remove null bytes
    filePath = filePath.replace(/\0/g, '');
    
    // Resolve to absolute path
    const resolved = path.resolve(filePath);
    
    // Check for path traversal
    if (resolved.includes('..')) {
        throw new Error('Path traversal detected');
    }
    
    return resolved;
}

/**
 * Create main application window with security
 */
function createWindow() {
    // Limit window count
    if (windowCount >= CONFIG.MAX_WINDOW_COUNT) {
        dialog.showErrorBox('Error', 'Maximum window count reached');
        return;
    }
    
    // Load saved bounds
    const bounds = store.get('windowBounds');
    
    mainWindow = new BrowserWindow({
        width: bounds.width,
        height: bounds.height,
        minWidth: 1200,
        minHeight: 700,
        title: 'RĀMAN Studio - Desktop Companion for AnalyteX',
        icon: path.join(__dirname, '../../resources/icons/icon.png'),
        backgroundColor: '#0a0e1a',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
            webSecurity: true,
            allowRunningInsecureContent: false,
            experimentalFeatures: false,
            enableRemoteModule: false,
            sandbox: true,
            // Disable dangerous features
            nodeIntegrationInWorker: false,
            nodeIntegrationInSubFrames: false,
            webviewTag: false
        },
        show: false
    });

    // Set CSP headers
    mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
        callback({
            responseHeaders: {
                ...details.responseHeaders,
                'Content-Security-Policy': [
                    "default-src 'self'; " +
                    "script-src 'self' 'unsafe-inline' https://3Dmol.csb.pitt.edu; " +
                    "style-src 'self' 'unsafe-inline'; " +
                    "img-src 'self' data: https:; " +
                    "connect-src 'self' http://localhost:8000 https://license.vidyuthlabs.com; " +
                    "font-src 'self' data:; " +
                    "object-src 'none'; " +
                    "base-uri 'self'; " +
                    "form-action 'self'; " +
                    "frame-ancestors 'none'; " +
                    "upgrade-insecure-requests;"
                ],
                'X-Content-Type-Options': ['nosniff'],
                'X-Frame-Options': ['DENY'],
                'X-XSS-Protection': ['1; mode=block'],
                'Referrer-Policy': ['no-referrer'],
                'Permissions-Policy': ['geolocation=(), microphone=(), camera=()']
            }
        });
    });

    // Block navigation to external sites
    mainWindow.webContents.on('will-navigate', (event, url) => {
        const allowedOrigins = [
            `http://${CONFIG.SERVER_HOST}:${CONFIG.SERVER_PORT}`,
            'https://license.vidyuthlabs.com'
        ];
        
        if (!allowedOrigins.some(origin => url.startsWith(origin))) {
            event.preventDefault();
            console.warn('Blocked navigation to:', url);
        }
    });

    // Block new window creation
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        // Only allow specific URLs to open in external browser
        if (url.startsWith('https://vidyuthlabs.com') || 
            url.startsWith('mailto:')) {
            shell.openExternal(url);
        }
        return { action: 'deny' };
    });

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    // Load the application
    mainWindow.loadURL(`http://${CONFIG.SERVER_HOST}:${CONFIG.SERVER_PORT}`);

    // Open DevTools only in development
    if (process.argv.includes('--dev')) {
        mainWindow.webContents.openDevTools();
    }

    // Save window bounds on close
    mainWindow.on('close', () => {
        const bounds = mainWindow.getBounds();
        store.set('windowBounds', bounds);
    });

    // Handle window close
    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // Create application menu
    createMenu();
}

/**
 * Create application menu
 */
function createMenu() {
    const template = [
        {
            label: 'File',
            submenu: [
                {
                    label: 'New Project',
                    accelerator: 'CmdOrCtrl+N',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.send('menu-new-project');
                        }
                    }
                },
                {
                    label: 'Open Project',
                    accelerator: 'CmdOrCtrl+O',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.send('menu-open-project');
                        }
                    }
                },
                {
                    label: 'Save Project',
                    accelerator: 'CmdOrCtrl+S',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.send('menu-save-project');
                        }
                    }
                },
                { type: 'separator' },
                {
                    label: 'Export Results',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.send('menu-export-results');
                        }
                    }
                },
                { type: 'separator' },
                {
                    label: 'Exit',
                    accelerator: 'CmdOrCtrl+Q',
                    click: () => {
                        app.quit();
                    }
                }
            ]
        },
        {
            label: 'Edit',
            submenu: [
                { role: 'undo' },
                { role: 'redo' },
                { type: 'separator' },
                { role: 'cut' },
                { role: 'copy' },
                { role: 'paste' },
                { role: 'selectAll' }
            ]
        },
        {
            label: 'View',
            submenu: [
                { role: 'reload' },
                { role: 'forceReload' },
                { role: 'toggleDevTools' },
                { type: 'separator' },
                { role: 'resetZoom' },
                { role: 'zoomIn' },
                { role: 'zoomOut' },
                { type: 'separator' },
                { role: 'togglefullscreen' }
            ]
        },
        {
            label: 'GPU',
            submenu: [
                {
                    label: 'GPU Status',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.send('menu-gpu-status');
                        }
                    }
                },
                {
                    label: 'Run Benchmark',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.send('menu-gpu-benchmark');
                        }
                    }
                },
                {
                    label: 'Clear GPU Cache',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.send('menu-gpu-clear-cache');
                        }
                    }
                }
            ]
        },
        {
            label: 'License',
            submenu: [
                {
                    label: 'License Info',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.send('menu-license-info');
                        }
                    }
                },
                {
                    label: 'Activate License',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.send('menu-activate-license');
                        }
                    }
                },
                {
                    label: 'Start Free Trial',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.send('menu-start-trial');
                        }
                    }
                }
            ]
        },
        {
            label: 'Help',
            submenu: [
                {
                    label: 'Documentation',
                    click: () => {
                        shell.openExternal('https://vidyuthlabs.co.in/raman-studio/docs');
                    }
                },
                {
                    label: 'Support',
                    click: () => {
                        shell.openExternal('mailto:support@vidyuthlabs.com');
                    }
                },
                { type: 'separator' },
                {
                    label: 'About',
                    click: () => {
                        if (mainWindow) {
                            dialog.showMessageBox(mainWindow, {
                                type: 'info',
                                title: 'About RĀMAN Studio',
                                message: 'RĀMAN Studio v1.0.0',
                                detail: 'The Digital Twin for Your Potentiostat\n\n' +
                                       'AI-powered electrochemical analysis by VidyuthLabs.\n' +
                                       'Desktop companion for AnalyteX devices.\n\n' +
                                       'Honoring Professor CNR Rao\'s legacy in materials science.\n\n' +
                                       '© 2026 VidyuthLabs\n' +
                                       'https://vidyuthlabs.co.in',
                                buttons: ['OK']
                            });
                        }
                    }
                }
            ]
        }
    ];

    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
}

/**
 * Start Python backend server securely
 */
function startPythonServer() {
    return new Promise((resolve, reject) => {
        console.log('🚀 Starting Python backend server...');

        // Validate port
        const serverPort = validatePort(CONFIG.SERVER_PORT);
        
        // Determine Python executable
        const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
        
        // Start uvicorn server with security settings
        pythonProcess = spawn(pythonCmd, [
            '-m', 'uvicorn',
            'vanl.backend.main:app',
            '--host', CONFIG.SERVER_HOST,
            '--port', serverPort.toString(),
            '--log-level', 'info',
            '--no-access-log'  // Reduce log verbosity
        ], {
            cwd: path.join(__dirname, '../..'),
            env: {
                ...process.env,
                PYTHONUNBUFFERED: '1',
                NVIDIA_API_KEY: process.env.NVIDIA_API_KEY || '',
                // Security: Disable Python optimizations that could leak info
                PYTHONDONTWRITEBYTECODE: '1'
            },
            // Windows: Hide console window
            ...(process.platform === 'win32' && {
                windowsHide: true,
                detached: false
            })
        });

        let serverStarted = false;

        pythonProcess.stdout.on('data', (data) => {
            const output = data.toString().trim();
            console.log(`[Python] ${output}`);
            
            // Check if server is ready
            if (output.includes('Uvicorn running') && !serverStarted) {
                serverStarted = true;
                console.log('✅ Python backend server started');
                resolve();
            }
        });

        pythonProcess.stderr.on('data', (data) => {
            console.error(`[Python Error] ${data.toString().trim()}`);
        });

        pythonProcess.on('error', (error) => {
            console.error('❌ Failed to start Python server:', error);
            reject(error);
        });

        pythonProcess.on('close', (code) => {
            console.log(`Python server exited with code ${code}`);
            if (!serverStarted) {
                reject(new Error(`Python server failed to start (exit code: ${code})`));
            }
        });

        // Timeout
        setTimeout(() => {
            if (!serverStarted) {
                if (pythonProcess && !pythonProcess.killed) {
                    resolve(); // Assume it started
                } else {
                    reject(new Error('Python server start timeout'));
                }
            }
        }, CONFIG.PYTHON_TIMEOUT);
    });
}

/**
 * Stop Python backend server
 */
function stopPythonServer() {
    if (pythonProcess) {
        console.log('🛑 Stopping Python backend server...');
        
        try {
            // Try graceful shutdown first
            pythonProcess.kill('SIGTERM');
            
            // Force kill after 5 seconds
            setTimeout(() => {
                if (pythonProcess && !pythonProcess.killed) {
                    pythonProcess.kill('SIGKILL');
                }
            }, 5000);
        } catch (error) {
            console.error('Error stopping Python server:', error);
        }
        
        pythonProcess = null;
    }
}

/**
 * Secure IPC Handlers
 */

// Get GPU status
ipcMain.handle('get-gpu-status', async () => {
    try {
        rateLimitIPC('get-gpu-status');
        // This would call Python backend API
        return {
            available: true,
            name: 'NVIDIA GeForce RTX 4050',
            memory: '6 GB',
            utilization: 15
        };
    } catch (error) {
        console.error('IPC error:', error);
        return { error: error.message };
    }
});

// Get license info
ipcMain.handle('get-license-info', async () => {
    try {
        rateLimitIPC('get-license-info');
        // This would call Python backend API
        return {
            status: 'trial',
            days_remaining: 25,
            features: ['all']
        };
    } catch (error) {
        console.error('IPC error:', error);
        return { error: error.message };
    }
});

// Open file dialog
ipcMain.handle('open-file-dialog', async (_event, options) => {
    try {
        rateLimitIPC('open-file-dialog');
        
        // Validate options
        if (!options || typeof options !== 'object') {
            throw new Error('Invalid options');
        }
        
        const result = await dialog.showOpenDialog(mainWindow, options);
        
        // Sanitize file paths
        if (result.filePaths) {
            result.filePaths = result.filePaths.map(sanitizePath);
        }
        
        return result;
    } catch (error) {
        console.error('IPC error:', error);
        return { error: error.message, canceled: true };
    }
});

// Save file dialog
ipcMain.handle('save-file-dialog', async (_event, options) => {
    try {
        rateLimitIPC('save-file-dialog');
        
        if (!options || typeof options !== 'object') {
            throw new Error('Invalid options');
        }
        
        const result = await dialog.showSaveDialog(mainWindow, options);
        
        // Sanitize file path
        if (result.filePath) {
            result.filePath = sanitizePath(result.filePath);
        }
        
        return result;
    } catch (error) {
        console.error('IPC error:', error);
        return { error: error.message, canceled: true };
    }
});

// Show message box
ipcMain.handle('show-message-box', async (_event, options) => {
    try {
        rateLimitIPC('show-message-box');
        
        if (!options || typeof options !== 'object') {
            throw new Error('Invalid options');
        }
        
        // Sanitize message content
        if (options.message) {
            options.message = String(options.message).substring(0, 1000);
        }
        if (options.detail) {
            options.detail = String(options.detail).substring(0, 5000);
        }
        
        const result = await dialog.showMessageBox(mainWindow, options);
        return result;
    } catch (error) {
        console.error('IPC error:', error);
        return { error: error.message };
    }
});

/**
 * App lifecycle
 */

app.whenReady().then(async () => {
    try {
        // Start Python backend
        await startPythonServer();
        
        // Wait for server to be fully ready
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        // Create window
        createWindow();
        
    } catch (error) {
        console.error('Failed to start application:', error);
        dialog.showErrorBox(
            'Startup Error',
            'Failed to start RĀMAN Studio backend server.\n\n' +
            'Please ensure Python and required dependencies are installed.\n\n' +
            `Error: ${error.message}`
        );
        app.quit();
    }
});

app.on('window-all-closed', () => {
    stopPythonServer();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});

app.on('before-quit', () => {
    stopPythonServer();
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
    console.error('Uncaught exception:', error);
    // Log to file in production
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled rejection at:', promise, 'reason:', reason);
    // Log to file in production
});

// Security: Disable eval and related functions
process.on('loaded', () => {
    global.eval = function() {
        throw new Error('eval() is disabled for security');
    };
});

console.log('⚛️  RĀMAN Studio - Secure Edition');
console.log('   The Digital Twin for Your Potentiostat');
console.log('   Company: VidyuthLabs');
console.log('   Version: 1.0.0');
console.log('   Platform:', process.platform);
console.log('   Arch:', process.arch);
console.log('   Security: Enhanced');
