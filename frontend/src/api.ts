import type {
  AgentStudioRuntimeConfig,
  ApiErrorKind,
  JobEvent,
  RuntimeInfo
} from './types/common'

export class AgentStudioApiError extends Error {
  readonly kind: ApiErrorKind
  readonly network: boolean
  readonly apiBase: string
  readonly url: string
  readonly path: string
  readonly status?: number
  readonly responseBody?: string
  override readonly cause?: unknown

  constructor(
    message: string,
    details: {
      kind: ApiErrorKind
      apiBase: string
      url: string
      path: string
      status?: number
      responseBody?: string
      cause?: unknown
    }
  ) {
    super(message)
    this.name = details.kind === 'network' ? 'BackendFetchError' : 'BackendHttpError'
    this.kind = details.kind
    this.network = details.kind === 'network'
    this.apiBase = details.apiBase
    this.url = details.url
    this.path = details.path
    this.status = details.status
    this.responseBody = details.responseBody
    this.cause = details.cause
  }
}

function getRuntimeConfig(): AgentStudioRuntimeConfig {
  return window.__AGENTSTUDIO_CONFIG__ || {}
}

function getApiBase(): string {
  const envBase = import.meta.env.VITE_API_BASE_URL
  if (envBase) return envBase.replace(/\/$/, '')

  const cfg = getRuntimeConfig()
  const host = cfg.BACKEND_HOST || window.location.hostname || '127.0.0.1'
  const port = cfg.BACKEND_PORT || 8000
  return `${window.location.protocol}//${host}:${port}/api`
}

function getWsBase(): string {
  const cfg = getRuntimeConfig()
  const host = cfg.BACKEND_HOST || window.location.hostname || '127.0.0.1'
  const port = cfg.BACKEND_PORT || 8000
  return `ws://${host}:${port}/api/ws`
}

export async function api<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const apiBase = getApiBase()
  const url = `${apiBase}${path}`

  let res: Response

  try {
    res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...((options.headers || {}) as Record<string, string>)
      },
      ...options
    })
  } catch (cause) {
    throw new AgentStudioApiError(`Backend 연결 실패: ${url}`, {
      kind: 'network',
      apiBase,
      url,
      path,
      cause
    })
  }

  if (!res.ok) {
    const body = await res.text()
    throw new AgentStudioApiError(
      `Backend HTTP ${res.status}: ${body || res.statusText}`,
      {
        kind: 'http',
        status: res.status,
        apiBase,
        url,
        path,
        responseBody: body
      }
    )
  }

  return res.json() as Promise<T>
}

export function connectJobs(onEvent: (event: JobEvent) => void): WebSocket {
  const ws = new WebSocket(getWsBase())
  ws.onmessage = event => onEvent(JSON.parse(event.data) as JobEvent)
  ws.onopen = () => ws.send('connected')
  return ws
}

export function runtimeInfo(): RuntimeInfo {
  return {
    apiBase: getApiBase(),
    wsBase: getWsBase(),
    config: getRuntimeConfig()
  }
}
