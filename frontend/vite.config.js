import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 开发环境下，把 /api 开头的请求代理到本地后端（FastAPI，8000 端口）。
    // 这样前端代码里只需要写相对路径 /api/...，既避免 CORS 往返，
    // 也让 dev / 生产（挂载 dist 后同源）行为一致。
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
