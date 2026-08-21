export interface AgentStudioRuntimeConfig {
  BACKEND_HOST?: string
  BACKEND_PORT?: number
  FRONTEND_PORT?: number
}

export type JobEvent = {
  type?: string
  [key: string]: unknown
}

export interface RuntimeInfo {
  apiBase: string
  wsBase: string
  config: AgentStudioRuntimeConfig
}

export type ApiErrorKind = 'network' | 'http'
