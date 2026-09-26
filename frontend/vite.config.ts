import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ mode }) => {
  // The analysis API (FastAPI). `/api/*` requests from the browser are forwarded here, so no CORS setup is needed.
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.API_PROXY_TARGET || 'http://localhost:8000';
  const proxy = { '/api': { target: apiTarget, changeOrigin: true } };
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: { port: 5174, strictPort: true, proxy },
    preview: { port: 4173, strictPort: true, proxy },
  };
  
});
