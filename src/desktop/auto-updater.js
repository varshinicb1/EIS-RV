/**
 * RĀMAN Studio — Auto-Updater Module
 * =====================================
 * Checks for updates and applies them seamlessly.
 * 
 * Uses electron-updater with GitHub Releases as the update server.
 * Falls back gracefully if electron-updater is not installed.
 */

let autoUpdater = null;

try {
    const { autoUpdater: au } = require('electron-updater');
    autoUpdater = au;
} catch (e) {
    // electron-updater not installed — fallback to manual check
    console.log('[AutoUpdater] electron-updater not available, using manual check');
}

/**
 * Initialize auto-updater with event handlers.
 * @param {BrowserWindow} mainWindow - The main application window
 */
function initAutoUpdater(mainWindow) {
    if (!autoUpdater) {
        // Manual update check via GitHub API
        initManualUpdateCheck(mainWindow);
        return;
    }

    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = true;

    autoUpdater.on('checking-for-update', () => {
        sendStatus(mainWindow, 'checking', 'Checking for updates...');
    });

    autoUpdater.on('update-available', (info) => {
        sendStatus(mainWindow, 'available', `Update ${info.version} available`, info);
    });

    autoUpdater.on('update-not-available', () => {
        sendStatus(mainWindow, 'current', 'You have the latest version');
    });

    autoUpdater.on('download-progress', (progress) => {
        sendStatus(mainWindow, 'downloading', 
            `Downloading: ${Math.round(progress.percent)}%`, 
            { percent: progress.percent });
    });

    autoUpdater.on('update-downloaded', (info) => {
        sendStatus(mainWindow, 'ready', `Update ${info.version} ready to install`, info);
    });

    autoUpdater.on('error', (err) => {
        sendStatus(mainWindow, 'error', `Update error: ${err.message}`);
    });

    // Check on startup (after 10s delay)
    setTimeout(() => autoUpdater.checkForUpdates(), 10000);
}

/**
 * Manual update check via GitHub API (fallback when electron-updater unavailable).
 */
function initManualUpdateCheck(mainWindow) {
    const https = require('https');
    const { app } = require('electron');
    
    const checkForUpdates = () => {
        const options = {
            hostname: 'api.github.com',
            path: '/repos/VidyuthLabs/raman-studio/releases/latest',
            headers: { 'User-Agent': 'RAMAN-Studio' },
            timeout: 10000,
        };

        const req = https.get(options, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const release = JSON.parse(data);
                    const latest = release.tag_name?.replace('v', '') || '0.0.0';
                    const current = app.getVersion();
                    if (latest > current) {
                        sendStatus(mainWindow, 'available', 
                            `Update ${latest} available (current: ${current})`,
                            { version: latest, url: release.html_url });
                    } else {
                        sendStatus(mainWindow, 'current', 'You have the latest version');
                    }
                } catch (e) {
                    // Silently fail — not critical
                }
            });
        });
        req.on('error', () => {});
        req.on('timeout', () => req.destroy());
    };

    setTimeout(checkForUpdates, 15000);
}

function sendStatus(mainWindow, status, message, data = null) {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('update-status', { status, message, data });
    }
}

/**
 * Download and install available update.
 */
function downloadUpdate() {
    if (autoUpdater) {
        autoUpdater.downloadUpdate();
    }
}

/**
 * Install downloaded update and restart.
 */
function installUpdate() {
    if (autoUpdater) {
        autoUpdater.quitAndInstall(false, true);
    }
}

/**
 * Force check for updates.
 */
function checkForUpdates() {
    if (autoUpdater) {
        autoUpdater.checkForUpdates();
    }
}

module.exports = { initAutoUpdater, downloadUpdate, installUpdate, checkForUpdates };
