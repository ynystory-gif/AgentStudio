import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const host = process.env.AGENTSTUDIO_FRONTEND_HOST || '127.0.0.1'
const port = Number(process.env.AGENTSTUDIO_FRONTEND_PORT || 5173)

export default defineConfig({
  plugins: [react()],
  server: {
    host,
    port,
    strictPort: true,

    // Browser와 Vite dev server가 반드시 같은 HMR endpoint를 사용합니다.
    // SYSTEM_ADMIN이 5174 등 다른 포트를 선택해도 clientPort까지 같이 바뀝니다.
    hmr: {
      protocol: 'ws',
      host,
      port,
      clientPort: port
    },

    // Windows 로컬 개발 환경에서 파일 감시가 과도한 재시작을 유발하지 않도록
    // 기본 native watcher를 사용합니다.
    watch: {
      usePolling: false
    }
  }
})
