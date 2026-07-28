import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const BACKEND = process.env.AGENTIC_EDA_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxying both surfaces means the browser sees a single origin, so there
      // is no CORS in development and artifact URLs returned by the API can be
      // dropped straight into <img src>.
      '/api': {
        target: BACKEND,
        changeOrigin: true,
      },
      '/artifacts': {
        target: BACKEND,
        changeOrigin: true,
      },
    },
  },
})
