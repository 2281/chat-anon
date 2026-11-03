import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// dev-сервер с проксированием API и WebSocket в backend внутри docker-сети
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: 'http://backend:8000', changeOrigin: true },
      '/ws': { target: 'ws://backend:8000', ws: true, changeOrigin: true },
      // пути бакета S3 (presigned upload/download) — на MinIO. Имя бакета (chatanon)
      // должно совпадать с S3_BUCKET. changeOrigin подставляет Host minio:9000,
      // поэтому подпись s3v4 (подписанный на minio:9000) остаётся валидной.
      '/chatanon': { target: 'http://minio:9000', changeOrigin: true },
    },
  },
})
