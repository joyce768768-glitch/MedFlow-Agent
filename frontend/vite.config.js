import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端地址：本地默认 http://localhost:8000
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
