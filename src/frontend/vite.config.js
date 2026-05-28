/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  base: './',
  root: '.',
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test/setup.js'],
    include: ['test/**/*.{test,spec}.{js,jsx}', 'src/**/*.{test,spec}.{js,jsx}'],
    css: false,
  },
  build: {
    outDir: '../../build/renderer',
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('/three/') || id.includes('three-mesh-bvh') || id.includes('three-stdlib')) return 'three-vendor';
          if (id.includes('@react-three')) return 'r3f-vendor';
          if (id.includes('@reactflow') || id.includes('reactflow')) return 'reactflow-vendor';
          if (id.includes('@theatre')) return 'theatre-vendor';
          if (id.includes('jspdf') || id.includes('html2canvas')) return 'pdf-vendor';
          if (id.includes('react-joyride') || id.includes('@gilbarbara') ||
              id.includes('@floating-ui') || id.includes('is-lite') ||
              id.includes('react-floater') || id.includes('scroll-parent') ||
              id.includes('scroll-doc') || id.includes('scrollparent')) return 'joyride-vendor';
          if (id.includes('lucide-react')) return 'icons-vendor';
          if (id.includes('react-dom') || id.includes('/react/') || id.includes('scheduler')) return 'react-vendor';
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
  server: {
    port: 5000,
    host: '0.0.0.0',
    strictPort: true,
    allowedHosts: true,
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
  },
});
