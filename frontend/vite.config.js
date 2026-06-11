import { defineConfig } from 'vite'

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    proxy: {
      // forward API calls to backend during development
      '/api': 'http://localhost:8000',
      '/routes': 'http://localhost:8000',
      '/stream': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: false,
      },
    },
  },
})
