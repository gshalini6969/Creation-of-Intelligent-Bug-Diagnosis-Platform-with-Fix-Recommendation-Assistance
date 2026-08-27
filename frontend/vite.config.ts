import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Not strictly required since the FastAPI backend already sends
    // permissive CORS headers for local dev origins, but proxying avoids
    // relying on that and keeps API calls same-origin from the browser's
    // point of view.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
