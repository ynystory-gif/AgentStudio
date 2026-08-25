export interface WebBrowserTab {
  id: string
  title: string
  url: string
  history: string[]
  historyIndex: number
  revision: number
  fixed: boolean
  detected?: boolean
  remoteSessionId?: string
}

export interface DetectedWebService {
  url: string
  sessionId?: string
  detectedAt: number
}

export interface ChromiumBrowserPopup {
  session_id: string
  url: string
  title: string
}

export interface ChromiumBrowserState {
  ok: boolean
  session_id: string
  url: string
  title: string
  loading: boolean
  viewport_width: number
  viewport_height: number
  popups: ChromiumBrowserPopup[]
  transport?: string
  frame_revision?: number
  profile_dir?: string
}

export interface ChromiumScreencastFrame {
  type: 'frame' | 'error'
  revision?: number
  data?: string
  url?: string
  loading?: boolean
  message?: string
}

export interface ChromiumStartupAttempt {
  browser: string
  executable: string
  runtime_profile_dir: string
  startup_log_path: string
  command: string[]
  pid?: number | null
  exit_code?: number | null
  devtools_active_port_exists: boolean
  devtools_active_port: string
  cdp_http_url: string
  cdp_ws_url: string
  last_error: string
  startup_log_tail: string
  handoff_detected?: boolean
  handoff_pids?: number[]
  cleanup_killed?: number
  cleanup_remaining?: number
  startup_log_archived_path?: string
  startup_log_archived_exists?: boolean
  startup_log_archive_error?: string
}

export interface ChromiumStartupDiagnostics {
  status: 'idle' | 'starting' | 'ready' | 'failed' | string
  stage: string
  message: string
  hint: string
  started_at: string
  updated_at: string
  proxy: {
    http_proxy_set: boolean
    https_proxy_set: boolean
    no_proxy: string
  }
  candidates: string[]
  attempts: ChromiumStartupAttempt[]
  cdp_http_url: string
  cdp_ws_url: string
  guard?: {
    failure_latched?: boolean
    failure_at?: number
    failure_message?: string
  }
  log_path: string
  log_exists?: boolean
  log_size_bytes?: number
  log_write_error?: string
  worker?: {
    mode?: string
    pid?: number | null
    python?: string
    platform?: string
    event_loop_policy?: string
    endpoint?: string
    log_path?: string
    log_exists?: boolean
    log_tail?: string
    exception_type?: string
    exception_repr?: string
    traceback?: string
  }
}
