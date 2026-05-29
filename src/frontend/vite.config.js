/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Detect if running inside Tauri
const isTauri = !!process.env.TAURI_ENV_PLATFORM;

export default defineConfig({
  plugins: [react()],
  base: isTauri ? '/' : './',
  root: '.',
  // Prevent vite from obscuring Rust errors
  clearScreen: false,
  // Tauri uses a fixed port; fail if it's not available
  server: {
    port: isTauri ? 5173 : 5000,
    host: '0.0.0.0',
    strictPort: true,
    allowedHosts: true,
    ...(isTauri ? {} : {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          ws: true,
        },
        '/health': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    }),
  },
  // Environment variables that start with TAURI_ are exposed to JS
  envPrefix: ['VITE_', 'TAURI_'],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test/setup.js'],
    include: ['test/**/*.{test,spec}.{js,jsx}', 'src/**/*.{test,spec}.{js,jsx}'],
    css: false,
  },
  build: {
    // Tauri reads from dist/, Electron from build/renderer/
    outDir: isTauri ? 'dist' : '../../build/renderer',
    emptyOutDir: true,
    // Produce sourcemaps for Tauri debug builds
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
    chunkSizeWarningLimit: 1200,
    // Don't minify in debug mode for easier debugging
    minify: process.env.TAURI_ENV_DEBUG ? false : 'esbuild',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          // Keep heavy 3D libs separate but avoid circular deps with React/icons
          if (id.includes('/three/') || id.includes('three-mesh-bvh') || id.includes('three-stdlib')) return 'three-vendor';
          if (id.includes('@react-three')) return 'r3f-vendor';
          if (id.includes('jspdf') || id.includes('html2canvas')) return 'pdf-vendor';
          // Everything else goes into a single vendor chunk to prevent inter-chunk cycles
          return 'vendor';
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
});
