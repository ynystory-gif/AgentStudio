export type TerminalProcessState = 'idle' | 'starting' | 'running' | 'exited'
export type TerminalConnectionState = 'connecting' | 'connected' | 'closed' | 'error'

export interface TerminalSession {
  id: string
  name: string
  projectId?: string | number | null
  projectName?: string
  root?: string
  cwd?: string
  command?: string
  output?: string
  busy?: boolean
  interrupting?: boolean
  hasVenv?: boolean
  processState?: TerminalProcessState
  exitCode?: number | null
}

export interface ProjectTerminalStatus {
  projectName?: string
  root: string
  hasVenv?: boolean
}

export interface TerminalErrorInfo {
  stage?: string
  message?: string
  detail?: string
  logPath?: string
  sessionId?: string
  root?: string
  wsUrl?: string
  time?: string
}

export interface TerminalCompletionItem {
  kind?: 'folder' | 'file' | 'command' | string
  label: string
  insert_text?: string
  detail?: string
  [key: string]: unknown
}

export interface TerminalCompletionState {
  sessionId: string
  requestKey: string
  loading: boolean
  items: TerminalCompletionItem[]
  selectedIndex: number
  replaceStart: number
  replaceEnd: number
  token?: string
  cwd?: string
  error?: string | null
  liveFiltering?: boolean
}

export type TerminalServerMessage =
  | { type: 'history'; data?: string }
  | { type: 'output'; data?: string }
  | { type: 'ready'; has_venv?: boolean }
  | { type: 'cleared' }
  | { type: 'interrupted' }
  | { type: 'process_exit'; exit_code?: number | null }
  | {
      type: 'error'
      stage?: string
      message?: string
      detail?: string
      log_path?: string
      session_id?: string
      root?: string
    }
  | { type: string; [key: string]: unknown }
  | { type: 'unknown'; raw: unknown }

export type TerminalClientMessage =
  | { type: 'input'; data: string }
  | { type: 'command'; data: string }
  | { type: 'interrupt' }
  | { type: 'clear' }
