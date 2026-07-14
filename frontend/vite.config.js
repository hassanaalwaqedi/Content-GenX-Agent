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
  '/ai',
  '/docs',
  '/redoc',
  '/openapi.json',
];

// Build proxy config — each prefix forwards to the backend
const proxy = {};
for (const prefix of API_PREFIXES) {
  proxy[prefix] = {
    target: 'http://localhost:8000',
    changeOrigin: true,
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy,
  },
})
