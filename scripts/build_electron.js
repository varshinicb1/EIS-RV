/**
 * RĀMAN Studio — Electron Builder Configuration
 * =================================================
 * Production packaging for Windows, macOS, and Linux.
 *
 * Usage:
 *   node scripts/build_electron.js             // Current platform
 *   node scripts/build_electron.js --platform win32
 *   node scripts/build_electron.js --platform linux
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'dist');

// Ensure dist exists
if (!fs.existsSync(DIST)) fs.mkdirSync(DIST, { recursive: true });

// Parse args
const args = process.argv.slice(2);
const platformIdx = args.indexOf('--platform');
const targetPlatform = platformIdx >= 0 ? args[platformIdx + 1] : process.platform;

console.log('╔══════════════════════════════════════════╗');
console.log('║  RĀMAN Studio — Electron Builder         ║');
console.log('╚══════════════════════════════════════════╝');
console.log(`Platform: ${targetPlatform}`);
console.log(`Output:   ${DIST}`);
console.log();

// Build steps
const steps = [
    {
        name: '1. Build C++ engine',
        cmd: `python3 ${path.join(ROOT, 'scripts', 'build_cpp.py')} --test`,
        optional: true,
    },
    {
        name: '2. Build Python backend (Nuitka)',
        cmd: `python3 ${path.join(ROOT, 'scripts', 'build_nuitka.py')}`,
        optional: true,
    },
    {
        name: '3. Package Electron app',
        cmd: `npx electron-builder --${targetPlatform === 'win32' ? 'win' : targetPlatform === 'darwin' ? 'mac' : 'linux'}`,
        optional: false,
    },
];

for (const step of steps) {
    console.log(`\n🔧 ${step.name}...`);
    try {
        execSync(step.cmd, { cwd: ROOT, stdio: 'inherit' });
        console.log(`✅ ${step.name} complete`);
    } catch (err) {
        if (step.optional) {
            console.log(`⚠️  ${step.name} skipped (optional): ${err.message}`);
        } else {
            console.error(`❌ ${step.name} failed`);
            process.exit(1);
        }
    }
}

console.log('\n🎉 Build complete! Check dist/ for output.');
