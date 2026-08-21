/// <reference types="vite/client" />

import type { AgentStudioRuntimeConfig } from './types/common'

declare global {
  interface Window {
    __AGENTSTUDIO_CONFIG__?: AgentStudioRuntimeConfig
  }
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

export {}
