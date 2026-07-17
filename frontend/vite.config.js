import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// All backend route prefixes that need proxying
const API_PREFIXES = [
  '/auth',
  '/health',
  '/connectors',
  '/stats',
  '/videos',
  '/creators',
  '/datasets',
  '/pipeline',
  '/trends',
  '/opportunities',
  '/platforms',
  '/ai',
  '/docs',
  '/redoc',
  '/openapi.json',
];

// Build proxy config — each prefix forwards to the backend
const proxy = {};
for (const prefix of API_PREFIXES) {
  proxy[prefix] = {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
    ...(['/pipeline', '/videos', '/creators', '/platforms'].includes(prefix) ? {
      bypass(req) {
        const pathname = req.url?.split('?')[0];
        const isDirectSpaRoute = pathname === prefix || pathname === `${prefix}/`
          || (prefix === '/platforms' && (pathname === '/platforms/reddit' || pathname === '/platforms/reddit/'));
        if (req.method === 'GET' && isDirectSpaRoute) {
          return '/index.html';
        }
      },
    } : {}),
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy,
  },
})
