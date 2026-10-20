import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    watch: {
      usePolling: true,
      interval: 100,
    },
    proxy: {
      '/api': {
        target: process.env.VNX_BACKEND_URL || 'http://localhost:8080',
        changeOrigin: true,
        secure: false,
      }
    }
  }
});
