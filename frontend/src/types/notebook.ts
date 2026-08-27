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

export interface NotebookExecutionRequest {
  pythonCode: string
  filePath: string
  projectRoot?: string
  cellIndex: number
  mode: 'full' | 'selection'
  selectionOnly: boolean
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
  [key: string]: unknown
}

export interface NotebookEditorController {
  runAll: () => Promise<void>
  runActiveCell: () => Promise<void>
  runSelection: () => Promise<void>
  stopExecution: () => Promise<void>
  isRunning: () => boolean
  getActiveCellIndex: () => number
  revealSearchMatch: (cellIndex: number, lineNumber?: number, column?: number, length?: number) => void
}

