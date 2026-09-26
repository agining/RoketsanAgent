import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ mode }) => {
  // The analysis API (FastAPI). `/api/*` requests from the browser are forwarded here, so no CORS setup is needed.
  const envDir = fileURLToPath(new URL('../', import.meta.url));
  const env = loadEnv(mode, envDir, '');
  const apiTarget = env.API_PROXY_TARGET || 'http://localhost:8000';
  const proxy = { '/api': { target: apiTarget, changeOrigin: true } };
  return {
    envDir,
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: { port: 5173, strictPort: true, proxy },
    preview: { port: 4173, strictPort: true, proxy },
  };
});
