import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Proxy all /api/* requests to the FastAPI backend.
      // The SSE stream (GET /api/v1/stream/connect) must NOT be buffered.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Do NOT configure ws:true here — SSE uses HTTP, not WS.
        configure: (proxy) => {
          // Disable response buffering so SSE events arrive immediately.
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['x-accel-buffering'] = 'no';
          });
        },
      },
    },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
      },
    },
  },
});
