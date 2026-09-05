export type NotebookAttachments = Record<string, Record<string, unknown>>

export interface NotebookOutputData {
  output_type?: string
  name?: string
  text?: unknown
  traceback?: unknown
  ename?: unknown
  evalue?: unknown
  data?: Record<string, unknown>
  [key: string]: unknown
}

export interface NotebookCell {
  id?: string
  cell_type?: string
  source?: unknown
  metadata?: Record<string, unknown>
  attachments?: NotebookAttachments
  outputs?: NotebookOutputData[]
  execution_count?: number | null
  [key: string]: unknown
}

export interface NotebookDocument {
  cells: NotebookCell[]
  metadata?: {
    kernelspec?: Record<string, unknown>
    language_info?: Record<string, unknown>
    [key: string]: unknown
  }
  nbformat?: number
  nbformat_minor?: number
  [key: string]: unknown
}

export type NotebookParseResult =
  | { ok: true; error: ''; notebook: NotebookDocument }
  | { ok: false; error: string; notebook: null }

export interface NotebookDependencyDiagnostic {
  code?: string
  message?: string
  install_command?: string
  requirements_command?: string
  [key: string]: unknown
}

export interface NotebookLiveOutputEvent {
  event?: 'clear_output' | 'display_data' | 'update_display_data' | 'stream' | string
  wait?: boolean
  display_id?: string
  output?: NotebookOutputData
  [key: string]: unknown
}

export interface NotebookExecutionRequest {
  pythonCode: string
  filePath: string
  projectRoot?: string
  cellIndex: number
  mode: 'full' | 'selection'
  selectionOnly: boolean
  onOutputEvent?: (event: NotebookLiveOutputEvent) => void
}

export interface NotebookExecutionResult {
  ok?: boolean
  cancelled?: boolean
  stdout?: string
  stderr?: string
  traceback?: string
  error_type?: string
  error_message?: string
  interpreter?: string
  dependency_diagnostic?: NotebookDependencyDiagnostic | null
  rich_outputs?: NotebookOutputData[]
  streaming?: boolean
  [key: string]: unknown
}

export interface NotebookDebugVariable {
  name: string
  type?: string
  value?: string
  scope?: string
}

export interface NotebookDebugStackFrame {
  function?: string
  file?: string
  line?: number
}

export interface NotebookDebugResult extends NotebookExecutionResult {
  event?: 'idle' | 'paused' | 'evaluate' | 'finished' | 'stopped' | 'error' | string
  debug_active?: boolean
  cell_index?: number
  line?: number
  source_line?: string
  reason?: string
  variables?: NotebookDebugVariable[]
  stack?: NotebookDebugStackFrame[]
  evaluate_result?: string
  evaluate_error?: string
  exception?: { type?: string; message?: string } | null
}

export interface NotebookDebugStartRequest {
  pythonCode: string
  filePath: string
  projectRoot?: string
  cellIndex: number
  breakpoints: number[]
}

export interface NotebookDebugCommandRequest {
  command: 'continue' | 'step_over' | 'step_into' | 'step_out' | 'stop' | 'evaluate'
  expression?: string
  filePath: string
  projectRoot?: string
}

export interface NotebookEditorController {
  runAll: () => Promise<void>
  runActiveCell: () => Promise<void>
  runSelection: () => Promise<void>
  stopExecution: () => Promise<void>
  isRunning: () => boolean
  getActiveCellIndex: () => number
  getLiveContent: () => string
  flushPendingChanges: () => string
  revealSearchMatch: (cellIndex: number, lineNumber?: number, column?: number, length?: number) => void
}

