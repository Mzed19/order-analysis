import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget =
    process.env.VITE_PROXY_TARGET || env.VITE_PROXY_TARGET || 'http://localhost:8003'

  return {
    base: '/contract-ai/',
    plugins: [react()],
    server: {
      host: true,
      port: 3000,
      hmr: {
        host: 'www.michaeldumontdev.com',
        clientPort: 443,
        protocol: 'wss'
      },
      watch: {
        usePolling: true,
      },
      allowedHosts: [
        'www.michaeldumontdev.com',
        'emporium-never-perpetual.ngrok-free.dev'
      ],
      // Mesma origem via ngrok → elimina CORS no browser
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})
