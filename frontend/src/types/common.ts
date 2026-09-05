import type { CSSProperties } from 'react'

export interface AgentStudioRuntimeConfig {
  AGENTSTUDIO_ROOT?: string
  BACKEND_HOST?: string
  BACKEND_PORT?: number
  FRONTEND_PORT?: number
  API_BASE_URL?: string
  WS_BASE_URL?: string
}

export type JobEvent = {
  type?: string
  job?: unknown
  [key: string]: unknown
}

export interface RuntimeInfo {
  apiBase: string
  wsBase: string
  config: AgentStudioRuntimeConfig
}

export type ApiErrorKind = 'network' | 'http'

export type CssVarProperties = CSSProperties & Record<`--${string}`, string | number | undefined>
