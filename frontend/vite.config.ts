import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const backend = env.BACKEND_URL || 'http://127.0.0.1:8000'
  const proxy = {
    '/api': { target: backend },
    '/assets': { target: backend },
    '/ws': { target: backend, ws: true },
  }
  return {
    plugins: [vue()],
    build: {
      assetsDir: 'frontend-assets',
      rollupOptions: { output: { manualChunks: { 'charts-core': ['echarts/core'], 'chart-types': ['echarts/charts'] } } },
    },
    server: { port: 5173, strictPort: true, proxy },
    preview: { proxy },
  }
})
