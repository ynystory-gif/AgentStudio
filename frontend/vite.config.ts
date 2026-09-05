import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const frontendDir = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(frontendDir, '..')

function readRootEnvValue(key: string): string {
  const envPath = path.join(projectRoot, '.env')
  if (!fs.existsSync(envPath)) return ''
  const prefix = `${key}=`
  const lines = fs.readFileSync(envPath, 'utf8').split(/\r?\n/)
  const match = lines.filter((line) => line.trimStart().startsWith(prefix)).at(-1)
  return match ? match.slice(match.indexOf('=') + 1).trim() : ''
}

const host = process.env.AGENTSTUDIO_FRONTEND_HOST || '127.0.0.1'
const configuredFrontendPort = process.env.AGENTSTUDIO_FRONTEND_PORT || readRootEnvValue('AGENTSTUDIO_FRONTEND_PORT')
if (!configuredFrontendPort) throw new Error('프로젝트 루트 .env에 AGENTSTUDIO_FRONTEND_PORT가 필요합니다.')
const port = Number(configuredFrontendPort)
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error(`AGENTSTUDIO_FRONTEND_PORT 값이 올바르지 않습니다: ${configuredFrontendPort}`)
const backendMainPath = path.resolve(frontendDir, '../backend/app/main.py')

function agentStudioVersionSyncPlugin(): Plugin {
  const readBackendVersion = () => {
    try {
      const source = fs.readFileSync(backendMainPath, 'utf8')
      return source.match(/FastAPI\s*\([\s\S]*?version\s*=\s*["'](\d+\.\d+)["']/)?.[1] || '5.412'
    } catch {
      return '5.412'
    }
  }

  return {
    name: 'agentstudio-version-sync',
    enforce: 'pre',
    transform(code, id) {
      if (!/[\\/]src[\\/]app[\\/]App\.tsx$/.test(id)) return null
      const version = readBackendVersion()
      const transformed = code.replace(
        /const\s+AGENTSTUDIO_FRONTEND_VERSION\s*=\s*['"][^'"]+['"]/, 
        `const AGENTSTUDIO_FRONTEND_VERSION='${version}'`
      )
      return transformed === code ? null : { code: transformed, map: null }
    }
  }
}

export default defineConfig({
  plugins: [agentStudioVersionSyncPlugin(), react()],
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
