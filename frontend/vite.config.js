import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
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
      'www.michaeldumontdev.com'
    ]
  },
})
