export type CodexAccount = {
  type?: string
  authMode?: string
  email?: string
  planType?: string | null
}

export type CodexModel = {
  id?: string
  model?: string
  displayName?: string
  description?: string
  isDefault?: boolean
  defaultReasoningEffort?: string
  supportedReasoningEfforts?: Array<string | { reasoningEffort?: string; description?: string; effort?: string; value?: string; label?: string }>
}

export type CodexStatus = {
  enabled?: boolean
  installed: boolean
  path?: string
  version?: string
  windows_install_command?: string
  npm_install_command?: string
  running: boolean
  initialized: boolean
  pid?: number | null
  started_cwd?: string
  account?: CodexAccount | null
  requires_openai_auth?: boolean
  models?: CodexModel[]
  current_thread_id?: string
  active_turn_id?: string
  pending_requests?: CodexServerRequest[]
  rate_limits?: CodexRateLimitsResponse
  rate_limits_error?: string
  rate_limits_refreshed_at?: number
  last_error?: string
  stderr_tail?: string[]
}

export type CodexThread = {
  id: string
  name?: string | null
  cwd?: string | null
  createdAt?: number
  updatedAt?: number
  model?: string
  status?: string | { type?: string }
}

export type CodexServerRequest = {
  request_id: string
  method: string
  params: Record<string, unknown>
}

export type CodexTranscriptItem = {
  id: string
  kind: 'user' | 'assistant' | 'reasoning' | 'command' | 'file' | 'system' | 'error'
  text: string
  title?: string
  status?: string
  command?: string
  cwd?: string
  diff?: string
  createdAt: number
}

export type CodexRateLimitWindow = {
  usedPercent?: number
  resetsAt?: number | null
  windowDurationMins?: number | null
}

export type CodexRateLimitSnapshot = {
  limitId?: string | null
  limitName?: string | null
  planType?: string | null
  primary?: CodexRateLimitWindow | null
  secondary?: CodexRateLimitWindow | null
  individualLimit?: {
    limit?: string
    used?: string
    remainingPercent?: number
    resetsAt?: number
  } | null
  credits?: {
    balance?: string | null
    hasCredits?: boolean
    unlimited?: boolean
  } | null
}

export type CodexRateLimitsResponse = {
  rateLimits?: CodexRateLimitSnapshot
  rateLimitsByLimitId?: Record<string, CodexRateLimitSnapshot> | null
  rateLimitResetCredits?: { availableCount?: number } | null
}
