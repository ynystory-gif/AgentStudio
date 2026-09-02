import React, { useEffect, useLayoutEffect, useRef, useState } from 'react'
import Editor from '@monaco-editor/react'
import { CODE_EDITOR_PAIR_TYPING_OPTIONS, getEditorModelPath, registerEscapedDoubleQuotePairGuard } from '../../utils/editor'
import { registerCodeIntelligence } from '../../utils/codeIntelligence'
import { notebookKernelLanguage, parseNotebookDocument, textToNotebookSource } from '../../utils/notebook'
import type {
  NotebookCell,
  NotebookDocument,
  NotebookEditorController,
  NotebookExecutionRequest,
  NotebookExecutionResult,
  NotebookOutputData,
  NotebookLiveOutputEvent,
  NotebookDebugResult,
  NotebookDebugStartRequest,
  NotebookDebugCommandRequest,
} from '../../types/notebook'
import { NotebookMarkdown, NotebookOutput, notebookSourceToText } from './NotebookRenderers'
import './NotebookEditorResize.css'

interface NotebookSelection {
  startLineNumber: number
  startColumn: number
  endLineNumber: number
  endColumn: number
  isEmpty?: () => boolean
}

interface NotebookEditorModelLike {
  getValueInRange: (selection: NotebookSelection) => string
  getLineCount?: () => number
}

interface NotebookEditorPositionLike {
  lineNumber?: number
  column?: number
}

interface NotebookEditorMouseDownEventLike {
  target?: {
    type?: number
    position?: NotebookEditorPositionLike | null
  } | null
}

interface NotebookEditorDecorationLike {
  range: {
    startLineNumber: number
    startColumn: number
    endLineNumber: number
    endColumn: number
  }
  options: {
    isWholeLine?: boolean
    glyphMarginClassName?: string
    glyphMarginHoverMessage?: { value: string }
    className?: string
    hoverMessage?: { value: string }
  }
}

interface NotebookEditorLayoutInfoLike {
  height?: number
}

interface NotebookMonacoEditorLike {
  getValue?: () => string
  setValue?: (value: string) => void
  getModel?: () => NotebookEditorModelLike | null
  getSelection?: () => NotebookSelection | null
  getPosition?: () => NotebookEditorPositionLike | null
  hasTextFocus?: () => boolean
  getDomNode?: () => HTMLElement | null
  getScrollTop?: () => number
  getScrollHeight?: () => number
  getLayoutInfo?: () => NotebookEditorLayoutInfoLike
  revealLineInCenter?: (lineNumber: number) => void
  setSelection?: (selection: NotebookSelection) => void
  setPosition?: (position: { lineNumber: number; column: number }) => void
  deltaDecorations?: (oldDecorations: string[], newDecorations: NotebookEditorDecorationLike[]) => string[]
  onMouseDown?: (listener: (event: NotebookEditorMouseDownEventLike) => void) => { dispose?: () => void }
  addAction?: (descriptor: {
    id: string
    label: string
    precondition?: string
    contextMenuGroupId?: string
    contextMenuOrder?: number
    run: (editor: NotebookMonacoEditorLike) => void
  }) => { dispose?: () => void }
  focus?: () => void
}

interface NotebookCursorSelectionEvent {
  selection?: NotebookSelection
}

interface RememberedCellSelection {
  selection: NotebookSelection
  text: string
}

interface NotebookLineBookmark {
  cellIndex: number
  lineNumber: number
}

const NOTEBOOK_LINE_BOOKMARKS = new Map<string, NotebookLineBookmark[]>()
const NOTEBOOK_BOOKMARK_STORAGE_PREFIX = 'theanova.agentstudio.notebook.line-bookmarks::'

interface NotebookLineBreakpoint {
  cellIndex: number
  lineNumber: number
}

const NOTEBOOK_LINE_BREAKPOINTS = new Map<string, NotebookLineBreakpoint[]>()
const NOTEBOOK_BREAKPOINT_STORAGE_PREFIX = 'theanova.agentstudio.notebook.breakpoints::'

function isPythonNotebookKernel(kernel: unknown): boolean {
  const value = String(kernel || '').trim().toLowerCase()
  return value === 'python' || value.startsWith('python') || value.includes('ipykernel')
}

function normalizeNotebookLineBreakpoints(value: unknown): NotebookLineBreakpoint[] {
  if (!Array.isArray(value)) return []
  const unique = new Map<string, NotebookLineBreakpoint>()
  value.forEach(item => {
    const raw = item as Partial<NotebookLineBreakpoint>
    const cellIndex = Number(raw?.cellIndex)
    const lineNumber = Number(raw?.lineNumber)
    if (!Number.isInteger(cellIndex) || cellIndex < 0 || !Number.isInteger(lineNumber) || lineNumber < 1) return
    unique.set(`${cellIndex}:${lineNumber}`, { cellIndex, lineNumber })
  })
  return Array.from(unique.values()).sort((a, b) => a.cellIndex - b.cellIndex || a.lineNumber - b.lineNumber)
}

function getNotebookLineBreakpoints(key: string): NotebookLineBreakpoint[] {
  if (!key) return []
  const cached = NOTEBOOK_LINE_BREAKPOINTS.get(key)
  if (cached) return cached
  let loaded: NotebookLineBreakpoint[] = []
  try {
    const raw = window.localStorage.getItem(`${NOTEBOOK_BREAKPOINT_STORAGE_PREFIX}${key}`)
    if (raw) loaded = normalizeNotebookLineBreakpoints(JSON.parse(raw))
  } catch {
    loaded = []
  }
  NOTEBOOK_LINE_BREAKPOINTS.set(key, loaded)
  return loaded
}

function storeNotebookLineBreakpoints(key: string, breakpoints: NotebookLineBreakpoint[]): NotebookLineBreakpoint[] {
  const normalized = normalizeNotebookLineBreakpoints(breakpoints)
  if (!key) return normalized
  NOTEBOOK_LINE_BREAKPOINTS.set(key, normalized)
  try {
    window.localStorage.setItem(`${NOTEBOOK_BREAKPOINT_STORAGE_PREFIX}${key}`, JSON.stringify(normalized))
  } catch {
    // localStorage를 사용할 수 없는 환경에서도 현재 세션에서는 유지합니다.
  }
  return normalized
}

function normalizeNotebookLineBookmarks(value: unknown): NotebookLineBookmark[] {
  if (!Array.isArray(value)) return []
  const unique = new Map<string, NotebookLineBookmark>()
  value.forEach(item => {
    const raw = item as Partial<NotebookLineBookmark>
    const cellIndex = Number(raw?.cellIndex)
    const lineNumber = Number(raw?.lineNumber)
    if (!Number.isInteger(cellIndex) || cellIndex < 0 || !Number.isInteger(lineNumber) || lineNumber < 1) return
    unique.set(`${cellIndex}:${lineNumber}`, { cellIndex, lineNumber })
  })
  return Array.from(unique.values()).sort((a, b) => a.cellIndex - b.cellIndex || a.lineNumber - b.lineNumber)
}

function getNotebookLineBookmarks(key: string): NotebookLineBookmark[] {
  if (!key) return []
  const cached = NOTEBOOK_LINE_BOOKMARKS.get(key)
  if (cached) return cached
  let loaded: NotebookLineBookmark[] = []
  try {
    const raw = window.localStorage.getItem(`${NOTEBOOK_BOOKMARK_STORAGE_PREFIX}${key}`)
    if (raw) loaded = normalizeNotebookLineBookmarks(JSON.parse(raw))
  } catch {
    loaded = []
  }
  NOTEBOOK_LINE_BOOKMARKS.set(key, loaded)
  return loaded
}

function storeNotebookLineBookmarks(key: string, bookmarks: NotebookLineBookmark[]): NotebookLineBookmark[] {
  const normalized = normalizeNotebookLineBookmarks(bookmarks)
  if (!key) return normalized
  NOTEBOOK_LINE_BOOKMARKS.set(key, normalized)
  try {
    window.localStorage.setItem(`${NOTEBOOK_BOOKMARK_STORAGE_PREFIX}${key}`, JSON.stringify(normalized))
  } catch {
    // localStorage가 비활성화된 환경에서도 현재 세션 Map으로 북마크 기능은 유지합니다.
  }
  return normalized
}

// NotebookEditor is conditionally mounted by App.jsx. Switching from an .ipynb
// file to another editor type (SQL, source code, diagram, etc.) unmounts this
// component, so component-local scroll state would be lost. Keep the outer
// notebook scroll position at module scope, keyed by project + file path, so
// returning to the notebook restores the exact viewport during this app run.
const NOTEBOOK_SCROLL_POSITIONS = new Map<string, number>()
// v5.485: Keep user-resized code-cell heights outside the component so the
// height survives temporary NotebookEditor unmounts while switching files.
const NOTEBOOK_CELL_EDITOR_HEIGHTS = new Map<string, number>()
const NOTEBOOK_CELL_EDITOR_MIN_HEIGHT = 92
const NOTEBOOK_CELL_EDITOR_MAX_HEIGHT = 2400

function notebookCellEditorHeightKey(scrollKey: string, cellIndex: number): string {
  return `${scrollKey}::${cellIndex}`
}

function notebookScrollKey(projectRoot?: string, filePath?: string): string {
  const path = String(filePath || '').trim().replace(/\\/g, '/')
  if (!path) return ''
  const root = String(projectRoot || '').trim().replace(/\\/g, '/')
  return `${root}::${path}`
}

function formatNotebookExecutionElapsed(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(Number(milliseconds || 0) / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export interface NotebookEditorProps {
  value: string
  filePath?: string
  projectRoot?: string
  onChange?: (value: string) => void
  onExecutePython?: (request: NotebookExecutionRequest) => Promise<NotebookExecutionResult | null | undefined> | NotebookExecutionResult | null | undefined
  onStopPython?: () => Promise<unknown> | unknown
  onDebugPython?: (request: NotebookDebugStartRequest) => Promise<NotebookDebugResult | null | undefined> | NotebookDebugResult | null | undefined
  onDebugCommand?: (request: NotebookDebugCommandRequest) => Promise<NotebookDebugResult | null | undefined> | NotebookDebugResult | null | undefined
  controllerRef?: React.MutableRefObject<NotebookEditorController | null> | null
  onEditorFocus?: () => void
  onAddLlmReference?: (reference: {
    path?: string
    text: string
    start_line: number
    start_column: number
    end_line: number
    end_column: number
    cell_index?: number
    source?: string
  }) => void
  onNavigateProjectDefinition?: (definition: any, sourceLocation?: { line: number; column: number; cellIndex?: number }) => void | Promise<void>
  onExternalDefinitionPreview?: (definition: any) => void
}

function extractNotebookNameErrorSymbol(result: NotebookExecutionResult): string {
  if (String(result?.error_type || '') !== 'NameError') return ''
  const message = String(result?.error_message || '')
  const match = message.match(/name ['"]([^'"]+)['"] is not defined/)
  return String(match?.[1] || '').trim()
}

function findNotebookDefinitionCells(notebook: NotebookDocument, symbol: string): number[] {
  const safeSymbol = String(symbol || '').trim()
  if (!safeSymbol) return []
  const escaped = safeSymbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const patterns = [
    new RegExp(`(^|\\n)\\s*${escaped}\\s*(?::[^=\\n]+)?=`, 'm'),
    new RegExp(`(^|\\n)\\s*(?:async\\s+)?def\\s+${escaped}\\s*\\(`, 'm'),
    new RegExp(`(^|\\n)\\s*class\\s+${escaped}\\b`, 'm'),
    new RegExp(`(^|\\n)\\s*from\\s+[^\\n]+\\s+import\\s+[^\\n]*\\b${escaped}\\b`, 'm'),
    new RegExp(`(^|\\n)\\s*import\\s+[^\\n]*\\b${escaped}\\b`, 'm'),
  ]
  const matches: number[] = []
  notebook.cells.forEach((cell, index) => {
    if (cell?.cell_type !== 'code') return
    const source = notebookSourceToText(cell.source)
    if (patterns.some(pattern => pattern.test(source))) matches.push(index)
  })
  return matches
}

function errorToExecutionResult(error: unknown): NotebookExecutionResult {
  if (error instanceof Error) {
    return {
      ok: false,
      stdout: '',
      stderr: '',
      error_type: error.name || 'NotebookExecutionError',
      error_message: error.message || String(error),
      traceback: error.stack || String(error),
    }
  }
  return {
    ok: false,
    stdout: '',
    stderr: '',
    error_type: 'NotebookExecutionError',
    error_message: String(error),
    traceback: String(error),
  }
}

export function NotebookEditor({
  value,
  filePath,
  projectRoot,
  onChange,
  onExecutePython,
  onStopPython,
  onDebugPython,
  onDebugCommand,
  controllerRef,
  onEditorFocus,
  onAddLlmReference,
  onNavigateProjectDefinition,
  onExternalDefinitionPreview,
}: NotebookEditorProps) {
  const parsed = React.useMemo(() => parseNotebookDocument(value), [value])
  const shellRef = useRef<HTMLDivElement | null>(null)
  const scrollKey = React.useMemo(() => notebookScrollKey(projectRoot, filePath), [projectRoot, filePath])
  const scrollKeyRef = useRef(scrollKey)
  const cellEditorsRef = useRef<Record<number, NotebookMonacoEditorLike | undefined>>({})
  const cellBookmarkDecorationsRef = useRef<Record<number, string[] | undefined>>({})
  const cellDebugDecorationsRef = useRef<Record<number, string[] | undefined>>({})
  const cellSelectionsRef = useRef<Record<number, RememberedCellSelection | undefined>>({})
  // Monaco cell models must remain the source of truth while the user is typing.
  // Serializing the whole .ipynb on every keystroke and feeding the resulting
  // source back through the controlled `value` prop can make Monaco replace the
  // model and move the caret to the end of the cell. Keep cell editors
  // uncontrolled after mount and mirror the latest text here for external sync.
  const latestCellSourcesRef = useRef<Record<number, string>>({})
  const codeNavigationHistoryRef = useRef<{ back: Array<{ cellIndex: number; line: number; column: number }>; forward: Array<{ cellIndex: number; line: number; column: number }> }>({ back: [], forward: [] })
  const [editingMarkdown, setEditingMarkdown] = useState<Record<number, boolean>>({})
  const [activeCellIndex, setActiveCellIndex] = useState(0)
  const [bookmarkRevision, setBookmarkRevision] = useState(0)
  const [breakpointRevision, setBreakpointRevision] = useState(0)
  const [debugState, setDebugState] = useState<NotebookDebugResult | null>(null)
  const [debugBusy, setDebugBusy] = useState(false)
  const [debugExpression, setDebugExpression] = useState('')
  const [debugConsole, setDebugConsole] = useState<Array<{ expression: string; result: string; error?: boolean }>>([])
  const [runningCells, setRunningCells] = useState<Record<number, boolean>>({})
  // v5.473: arbitrary Python code cannot expose a reliable percentage, so long
  // Notebook runs use an indeterminate progress strip plus elapsed time. This
  // makes it obvious that the kernel is still working without inventing a fake %.
  const executionStartedAtRef = useRef<Record<number, number>>({})
  const executionProgressDelayRef = useRef<Record<number, number>>({})
  const [executionProgressVisible, setExecutionProgressVisible] = useState<Record<number, boolean>>({})
  const [executionHeartbeatAt, setExecutionHeartbeatAt] = useState(() => Date.now())
  const [liveOutputsByCell, setLiveOutputsByCell] = useState<Record<number, NotebookOutputData[] | undefined>>({})
  // v5.412: clear_output(wait=True) must keep the previous frame visible until
  // the replacement rich output is ready. This mirrors Jupyter's deferred-clear
  // semantics and prevents animation frames from flashing to an empty region.
  const pendingLiveClearWaitRef = useRef<Record<number, boolean>>({})
  const replaceLiveOutputOnNextEventRef = useRef<Record<number, boolean>>({})
  const [runAllBusy, setRunAllBusy] = useState(false)
  const [stopBusy, setStopBusy] = useState(false)
  const cancelRequestedRef = useRef(false)
  const executionCounterRef = useRef(0)
  const bookmarks = React.useMemo(() => getNotebookLineBookmarks(scrollKey), [scrollKey, bookmarkRevision])
  const breakpoints = React.useMemo(() => getNotebookLineBreakpoints(scrollKey), [scrollKey, breakpointRevision])

  useEffect(() => {
    scrollKeyRef.current = scrollKey
  }, [scrollKey])

  const beginCellEditorResize = (index: number, event: React.PointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    const handle = event.currentTarget
    const container = handle.parentElement as HTMLDivElement | null
    if (!container) return

    const startY = event.clientY
    const startHeight = container.getBoundingClientRect().height
    const heightKey = notebookCellEditorHeightKey(scrollKey, index)
    const maxHeight = Math.min(
      NOTEBOOK_CELL_EDITOR_MAX_HEIGHT,
      Math.max(900, Math.round(window.innerHeight * 2.5)),
    )

    const onPointerMove = (moveEvent: PointerEvent) => {
      const nextHeight = Math.min(
        maxHeight,
        Math.max(NOTEBOOK_CELL_EDITOR_MIN_HEIGHT, startHeight + (moveEvent.clientY - startY)),
      )
      const roundedHeight = Math.round(nextHeight)
      container.style.height = `${roundedHeight}px`
      NOTEBOOK_CELL_EDITOR_HEIGHTS.set(heightKey, roundedHeight)
    }

    const finishResize = () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', finishResize)
      window.removeEventListener('pointercancel', finishResize)
      document.body.classList.remove('notebook-cell-resizing')
    }

    document.body.classList.add('notebook-cell-resizing')
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', finishResize)
    window.addEventListener('pointercancel', finishResize)
  }

  useEffect(() => {
    const hasRunningCell = Object.values(runningCells).some(Boolean)
    if (!hasRunningCell) return
    setExecutionHeartbeatAt(Date.now())
    const timer = window.setInterval(() => setExecutionHeartbeatAt(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [runningCells])

  useEffect(() => {
    if (!parsed.ok) return
    const maxCount = (parsed.notebook.cells || []).reduce((max, cell) => {
      const count = Number(cell?.execution_count)
      return Number.isFinite(count) ? Math.max(max, count) : max
    }, 0)
    executionCounterRef.current = Math.max(executionCounterRef.current, maxCount)
  }, [filePath, parsed.ok])

  useEffect(() => {
    cellSelectionsRef.current = {}
    latestCellSourcesRef.current = {}
    cellBookmarkDecorationsRef.current = {}
    cellDebugDecorationsRef.current = {}
    setDebugState(null)
    setDebugConsole([])
    pendingLiveClearWaitRef.current = {}
    replaceLiveOutputOnNextEventRef.current = {}
    Object.values(executionProgressDelayRef.current).forEach(timer => window.clearTimeout(timer))
    executionProgressDelayRef.current = {}
    executionStartedAtRef.current = {}
    setExecutionProgressVisible({})
    setRunningCells({})
    setLiveOutputsByCell({})
  }, [filePath])

  useEffect(() => {
    if (!parsed.ok) return
    parsed.notebook.cells.forEach((cell, index) => {
      const source = notebookSourceToText(cell?.source)
      const previous = latestCellSourcesRef.current[index]
      const editor = cellEditorsRef.current[index]
      const current = editor?.getValue?.()

      if (previous === undefined) {
        latestCellSourcesRef.current[index] = source
        return
      }

      // Local typing updates latestCellSourcesRef synchronously before the
      // serialized notebook prop comes back, so source===previous here. A
      // mismatch means an external reload/Agent edit changed the cell. Do not
      // overwrite a focused Monaco model; defer the external value until blur.
      if (source !== previous) {
        latestCellSourcesRef.current[index] = source
        if (editor && current === previous && !editor.hasTextFocus?.()) {
          editor.setValue?.(source)
        }
      }
    })
  }, [parsed])

  useLayoutEffect(() => {
    if (!scrollKey) return
    const remembered = NOTEBOOK_SCROLL_POSITIONS.get(scrollKey)
    if (remembered == null) return

    let cancelled = false
    let firstFrame = 0
    let secondFrame = 0
    let settleTimer = 0

    const restore = () => {
      if (cancelled) return
      const shell = shellRef.current
      if (!shell) return
      const maxScrollTop = Math.max(0, shell.scrollHeight - shell.clientHeight)
      shell.scrollTop = Math.min(Math.max(0, remembered), maxScrollTop)
    }

    // Restore once before paint, then again after Monaco/cell layout settles.
    // The repeated restore matters for long notebooks whose scrollHeight grows
    // during the first layout frames.
    restore()
    firstFrame = window.requestAnimationFrame(() => {
      restore()
      secondFrame = window.requestAnimationFrame(restore)
    })
    settleTimer = window.setTimeout(restore, 80)

    return () => {
      const shell = shellRef.current
      if (shell) NOTEBOOK_SCROLL_POSITIONS.set(scrollKey, Math.max(0, shell.scrollTop))
      cancelled = true
      if (firstFrame) window.cancelAnimationFrame(firstFrame)
      if (secondFrame) window.cancelAnimationFrame(secondFrame)
      if (settleTimer) window.clearTimeout(settleTimer)
    }
  }, [scrollKey, parsed.ok])

  const rememberOuterScroll = (scrollTop: number) => {
    if (!scrollKey) return
    NOTEBOOK_SCROLL_POSITIONS.set(scrollKey, Math.max(0, Number(scrollTop) || 0))
  }

  const updateBookmarkState = (next: NotebookLineBookmark[]): NotebookLineBookmark[] => {
    const stored = storeNotebookLineBookmarks(scrollKeyRef.current, next)
    setBookmarkRevision(value => value + 1)
    return stored
  }

  const toggleLineBookmark = (cellIndex: number, lineNumber: number): void => {
    const key = scrollKeyRef.current
    if (!key) return
    const safeCellIndex = Math.max(0, Number(cellIndex) || 0)
    const safeLineNumber = Math.max(1, Number(lineNumber) || 1)
    const current = getNotebookLineBookmarks(key)
    const exists = current.some(item => item.cellIndex === safeCellIndex && item.lineNumber === safeLineNumber)
    updateBookmarkState(exists
      ? current.filter(item => !(item.cellIndex === safeCellIndex && item.lineNumber === safeLineNumber))
      : [...current, { cellIndex: safeCellIndex, lineNumber: safeLineNumber }])
  }

  const applyBookmarkDecorations = (cellIndex: number, editor?: NotebookMonacoEditorLike): void => {
    const targetEditor = editor || cellEditorsRef.current[cellIndex]
    if (!targetEditor?.deltaDecorations) return
    const previous = cellBookmarkDecorationsRef.current[cellIndex] || []
    const maxLineNumber = Math.max(1, Number(targetEditor.getModel?.()?.getLineCount?.()) || 1)
    const nextDecorations: NotebookEditorDecorationLike[] = getNotebookLineBookmarks(scrollKeyRef.current)
      .filter(item => item.cellIndex === cellIndex && item.lineNumber <= maxLineNumber)
      .map(item => ({
        range: {
          startLineNumber: item.lineNumber,
          startColumn: 1,
          endLineNumber: item.lineNumber,
          endColumn: 1,
        },
        options: {
          isWholeLine: true,
          glyphMarginClassName: 'notebook-line-bookmark-glyph',
          glyphMarginHoverMessage: { value: `북마크 · Cell ${cellIndex + 1} · Line ${item.lineNumber}` },
        },
      }))
    cellBookmarkDecorationsRef.current[cellIndex] = targetEditor.deltaDecorations(previous, nextDecorations)
  }

  useEffect(() => {
    Object.entries(cellEditorsRef.current).forEach(([indexText, editor]) => {
      if (!editor) return
      applyBookmarkDecorations(Number(indexText), editor)
    })
  }, [bookmarkRevision, scrollKey])


  const updateBreakpointState = (next: NotebookLineBreakpoint[]): NotebookLineBreakpoint[] => {
    const stored = storeNotebookLineBreakpoints(scrollKeyRef.current, next)
    setBreakpointRevision(value => value + 1)
    return stored
  }

  const toggleLineBreakpoint = (cellIndex: number, lineNumber: number): void => {
    if (debugState?.debug_active) return
    const key = scrollKeyRef.current
    if (!key) return
    const safeCellIndex = Math.max(0, Number(cellIndex) || 0)
    const safeLineNumber = Math.max(1, Number(lineNumber) || 1)
    const current = getNotebookLineBreakpoints(key)
    const exists = current.some(item => item.cellIndex === safeCellIndex && item.lineNumber === safeLineNumber)
    updateBreakpointState(exists
      ? current.filter(item => !(item.cellIndex === safeCellIndex && item.lineNumber === safeLineNumber))
      : [...current, { cellIndex: safeCellIndex, lineNumber: safeLineNumber }])
  }

  const applyDebugDecorations = (cellIndex: number, editor?: NotebookMonacoEditorLike): void => {
    const targetEditor = editor || cellEditorsRef.current[cellIndex]
    if (!targetEditor?.deltaDecorations) return
    const previous = cellDebugDecorationsRef.current[cellIndex] || []
    const maxLineNumber = Math.max(1, Number(targetEditor.getModel?.()?.getLineCount?.()) || 1)
    const decorations: NotebookEditorDecorationLike[] = getNotebookLineBreakpoints(scrollKeyRef.current)
      .filter(item => item.cellIndex === cellIndex && item.lineNumber <= maxLineNumber)
      .map(item => ({
        range: { startLineNumber: item.lineNumber, startColumn: 1, endLineNumber: item.lineNumber, endColumn: 1 },
        options: {
          isWholeLine: true,
          glyphMarginClassName: 'notebook-debug-breakpoint-glyph',
          glyphMarginHoverMessage: { value: `중단점 · Cell ${cellIndex + 1} · Line ${item.lineNumber}` },
        },
      }))

    if (debugState?.debug_active && Number(debugState.cell_index) === cellIndex && Number(debugState.line) >= 1) {
      const debugLine = Math.min(maxLineNumber, Math.max(1, Number(debugState.line)))
      decorations.push({
        range: { startLineNumber: debugLine, startColumn: 1, endLineNumber: debugLine, endColumn: 1 },
        options: {
          isWholeLine: true,
          className: 'notebook-debug-current-line',
          hoverMessage: { value: `현재 디버그 위치 · Line ${debugLine}` },
        },
      })
    }
    cellDebugDecorationsRef.current[cellIndex] = targetEditor.deltaDecorations(previous, decorations)
  }

  useEffect(() => {
    Object.entries(cellEditorsRef.current).forEach(([indexText, editor]) => {
      if (!editor) return
      applyDebugDecorations(Number(indexText), editor)
    })
  }, [breakpointRevision, debugState, scrollKey])

  const revealBookmark = (bookmark: NotebookLineBookmark): void => {
    const maxIndex = parsed.ok ? Math.max(0, parsed.notebook.cells.length - 1) : 0
    const safeCellIndex = Math.max(0, Math.min(bookmark.cellIndex, maxIndex))
    const editor = cellEditorsRef.current[safeCellIndex]
    const maxLineNumber = Math.max(1, Number(editor?.getModel?.()?.getLineCount?.()) || bookmark.lineNumber || 1)
    const safeLineNumber = Math.max(1, Math.min(bookmark.lineNumber, maxLineNumber))
    setActiveCellIndex(safeCellIndex)
    const section = shellRef.current?.querySelector(`[data-notebook-cell-index="${safeCellIndex}"]`) as HTMLElement | null
    section?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
    window.setTimeout(() => {
      const targetEditor = cellEditorsRef.current[safeCellIndex]
      targetEditor?.revealLineInCenter?.(safeLineNumber)
      targetEditor?.setPosition?.({ lineNumber: safeLineNumber, column: 1 })
      targetEditor?.focus?.()
    }, 80)
  }

  const moveToBookmark = (direction: 1 | -1): void => {
    const current = getNotebookLineBookmarks(scrollKeyRef.current)
    if (!current.length) return
    const currentLine = Math.max(0, Number(cellEditorsRef.current[activeCellIndex]?.getPosition?.()?.lineNumber) || 0)
    let target: NotebookLineBookmark | undefined
    if (direction > 0) {
      target = current.find(item => item.cellIndex > activeCellIndex || (item.cellIndex === activeCellIndex && item.lineNumber > currentLine))
      target ||= current[0]
    } else {
      target = [...current].reverse().find(item => item.cellIndex < activeCellIndex || (item.cellIndex === activeCellIndex && item.lineNumber < currentLine))
      target ||= current[current.length - 1]
    }
    if (target) revealBookmark(target)
  }

  const clearBookmarks = (): void => {
    const current = getNotebookLineBookmarks(scrollKeyRef.current)
    if (!current.length) return
    if (!window.confirm(`현재 Notebook의 북마크 ${current.length}개를 모두 해제하시겠습니까?`)) return
    updateBookmarkState([])
  }

  const toggleActiveLineBookmark = (): void => {
    if (!parsed.ok || parsed.notebook.cells[activeCellIndex]?.cell_type !== 'code') return
    const editor = cellEditorsRef.current[activeCellIndex]
    if (!editor) return
    const lineNumber = Math.max(1, Number(editor.getPosition?.()?.lineNumber) || 1)
    toggleLineBookmark(activeCellIndex, lineNumber)
    editor?.revealLineInCenter?.(lineNumber)
    editor?.setPosition?.({ lineNumber, column: 1 })
    editor?.focus?.()
  }

  const shiftBookmarksForInsertedCell = (insertAt: number): void => {
    const current = getNotebookLineBookmarks(scrollKeyRef.current)
    if (!current.length) return
    updateBookmarkState(current.map(item => item.cellIndex >= insertAt
      ? { ...item, cellIndex: item.cellIndex + 1 }
      : item))
  }

  const shiftBreakpointsForInsertedCell = (insertAt: number): void => {
    const current = getNotebookLineBreakpoints(scrollKeyRef.current)
    if (!current.length) return
    updateBreakpointState(current.map(item => item.cellIndex >= insertAt
      ? { ...item, cellIndex: item.cellIndex + 1 }
      : item))
  }

  const shiftBookmarksForDeletedCell = (deletedIndex: number): void => {
    const current = getNotebookLineBookmarks(scrollKeyRef.current)
    if (!current.length) return
    updateBookmarkState(current
      .filter(item => item.cellIndex !== deletedIndex)
      .map(item => item.cellIndex > deletedIndex
        ? { ...item, cellIndex: item.cellIndex - 1 }
        : item))
  }

  const shiftBreakpointsForDeletedCell = (deletedIndex: number): void => {
    const current = getNotebookLineBreakpoints(scrollKeyRef.current)
    if (!current.length) return
    updateBreakpointState(current
      .filter(item => item.cellIndex !== deletedIndex)
      .map(item => item.cellIndex > deletedIndex
        ? { ...item, cellIndex: item.cellIndex - 1 }
        : item))
  }

  const commitNotebook = (notebook: NotebookDocument) => {
    const serialized = JSON.stringify(notebook, null, 1) + '\n'
    onChange?.(serialized)
  }

  const patchCell = (index: number, patch: Partial<NotebookCell>) => {
    if (!parsed.ok) return
    const notebook = structuredClone(parsed.notebook)
    const current = notebook.cells[index]
    if (!current) return
    notebook.cells[index] = { ...current, ...patch }
    commitNotebook(notebook)
  }

  const updateCellSource = (index: number, text: string) => {
    // Mirror synchronously before React serializes the notebook so Ctrl+S / blur
    // never observes a stale cell value. The Monaco model itself stays intact,
    // which preserves caret/selection through typing, deletion and paste.
    latestCellSourcesRef.current[index] = text
    patchCell(index, { source: textToNotebookSource(text) })
  }

  const buildLiveNotebookContent = (): string => {
    if (!parsed.ok) return value
    const notebook = structuredClone(parsed.notebook)
    Object.entries(latestCellSourcesRef.current).forEach(([indexText, source]) => {
      const index = Number(indexText)
      if (!Number.isInteger(index)) return
      const cell = notebook.cells[index]
      if (!cell || cell.cell_type !== 'code') return
      notebook.cells[index] = { ...cell, source: textToNotebookSource(String(source ?? '')) }
    })
    return JSON.stringify(notebook, null, 1) + '\n'
  }

  const revealCodeDefinition = (cellIndex: number, line: number, column = 1): void => {
    const maxIndex = parsed.ok ? Math.max(0, parsed.notebook.cells.length - 1) : 0
    const safeCellIndex = Math.max(0, Math.min(maxIndex, Number(cellIndex) || 0))
    const safeLine = Math.max(1, Number(line) || 1)
    const safeColumn = Math.max(1, Number(column) || 1)
    setActiveCellIndex(safeCellIndex)
    const section = shellRef.current?.querySelector(`[data-notebook-cell-index="${safeCellIndex}"]`) as HTMLElement | null
    section?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
    window.setTimeout(() => {
      const targetEditor = cellEditorsRef.current[safeCellIndex]
      targetEditor?.revealLineInCenter?.(safeLine)
      targetEditor?.setPosition?.({ lineNumber: safeLine, column: safeColumn })
      targetEditor?.focus?.()
    }, 70)
  }

  const notebookCurrentCodeLocation = (fallbackCellIndex = activeCellIndex): { cellIndex: number; line: number; column: number } => {
    const editor = cellEditorsRef.current[fallbackCellIndex]
    const position = editor?.getPosition?.() || { lineNumber: 1, column: 1 }
    return {
      cellIndex: fallbackCellIndex,
      line: Math.max(1, Number(position.lineNumber || 1)),
      column: Math.max(1, Number(position.column || 1)),
    }
  }

  const openNotebookDefinition = async (definition: any, sourceLocation?: { line: number; column: number }, sourceCellIndex = activeCellIndex): Promise<void> => {
    if (!definition) return
    if (definition.external || (!definition.relative_path && definition.absolute_path)) {
      onExternalDefinitionPreview?.(definition)
      return
    }
    const targetPath = String(definition.relative_path || filePath || '').replace(/\\/g, '/')
    const currentPath = String(filePath || '').replace(/\\/g, '/')
    if (targetPath && currentPath && targetPath.toLowerCase() !== currentPath.toLowerCase()) {
      await onNavigateProjectDefinition?.(definition, {
        line: Math.max(1, Number(sourceLocation?.line || 1)),
        column: Math.max(1, Number(sourceLocation?.column || 1)),
        cellIndex: sourceCellIndex,
      })
      return
    }
    if (definition.cell_index == null) {
      await onNavigateProjectDefinition?.(definition, {
        line: Math.max(1, Number(sourceLocation?.line || 1)),
        column: Math.max(1, Number(sourceLocation?.column || 1)),
        cellIndex: sourceCellIndex,
      })
      return
    }
    const history = codeNavigationHistoryRef.current
    history.back = [...history.back, {
      cellIndex: sourceCellIndex,
      line: Math.max(1, Number(sourceLocation?.line || notebookCurrentCodeLocation(sourceCellIndex).line)),
      column: Math.max(1, Number(sourceLocation?.column || notebookCurrentCodeLocation(sourceCellIndex).column)),
    }].slice(-80)
    history.forward = []
    revealCodeDefinition(Number(definition.cell_index), Number(definition.line || 1), Number(definition.column || 1))
  }

  const navigateNotebookCodeHistory = (direction: 1 | -1): void => {
    const history = codeNavigationHistoryRef.current
    const source = direction < 0 ? history.back : history.forward
    if (!source.length) return
    const target = source[source.length - 1]
    if (!target) return
    const current = notebookCurrentCodeLocation()
    if (direction < 0) {
      history.back = source.slice(0, -1)
      history.forward = [...history.forward, current].slice(-80)
    } else {
      history.forward = source.slice(0, -1)
      history.back = [...history.back, current].slice(-80)
    }
    revealCodeDefinition(target.cellIndex, target.line, target.column)
  }

  const applyExecutionResult = (
    notebook: NotebookDocument,
    index: number,
    result: NotebookExecutionResult,
  ): NotebookDocument => {
    const next = structuredClone(notebook)
    const cell = next.cells[index]
    if (!cell) return next

    const outputs: NotebookOutputData[] = []
    const stdout = String(result?.stdout || '')
    const stderr = String(result?.stderr || '')
    const trace = String(result?.traceback || '')

    if (Array.isArray(result?.rich_outputs)) {
      result.rich_outputs.forEach(output => {
        if (output && typeof output === 'object') outputs.push(output)
      })
    }

    if (stdout) outputs.push({ name: 'stdout', output_type: 'stream', text: textToNotebookSource(stdout) })
    if (stderr) outputs.push({ name: 'stderr', output_type: 'stream', text: textToNotebookSource(stderr) })

    if (result?.cancelled) {
      outputs.push({
        name: 'stderr',
        output_type: 'stream',
        text: textToNotebookSource('[실행 취소] 사용자가 Notebook 실행을 중지했습니다.\n'),
      })
    } else if (!result?.ok) {
      outputs.push({
        output_type: 'error',
        ename: String(result?.error_type || 'PythonError'),
        evalue: String(result?.error_message || '실행 실패'),
        traceback: trace ? trace.replace(/\r\n|\r/g, '\n').split('\n') : [],
      })
      const dependency = result?.dependency_diagnostic
      if (dependency?.code === 'PYTHON_MODULE_NOT_FOUND') {
        const diagnostic = [
          `[패키지 설치 필요] ${dependency.message || ''}`,
          `설치 명령: ${dependency.install_command || ''}`,
          dependency.requirements_command ? `requirements.txt 전체 설치: ${dependency.requirements_command}` : '',
          '※ 에이전트 스튜디오는 프로젝트 가상환경을 자동 변경하지 않습니다.',
        ].filter(Boolean).join('\n')
        outputs.push({ name: 'stderr', output_type: 'stream', text: textToNotebookSource(diagnostic + '\n') })
      }

      const missingSymbol = extractNotebookNameErrorSymbol(result)
      if (missingSymbol) {
        const definitionCells = findNotebookDefinitionCells(notebook, missingSymbol)
        const candidateText = definitionCells.length
          ? `정의 후보 셀: ${definitionCells.map(cellIndex => `Cell ${cellIndex + 1}`).join(', ')}`
          : '현재 Notebook에서 이 이름을 정의하는 셀을 찾지 못했습니다.'
        const diagnostic = [
          `[NameError 안내] ${missingSymbol} 이(가) 현재 Python 실행 세션에 정의되어 있지 않습니다.`,
          candidateText,
          '가능한 원인: 정의 셀을 아직 실행하지 않았거나, 앞 셀이 실패했거나, Backend/Notebook 세션이 재시작되어 이전 변수 상태가 초기화되었습니다.',
          definitionCells.length ? '정의 후보 셀을 먼저 실행한 뒤 현재 셀을 다시 실행하거나, 전체 실행을 사용하세요.' : '변수 이름과 이전 실행 결과를 확인한 뒤 다시 실행하세요.',
        ].join('\n')
        outputs.push({ name: 'stderr', output_type: 'stream', text: textToNotebookSource(diagnostic + '\n') })
      }
    }

    executionCounterRef.current += 1
    next.cells[index] = {
      ...cell,
      execution_count: executionCounterRef.current,
      outputs,
    }
    return next
  }

  const handleLiveOutputEvent = (index: number, event: NotebookLiveOutputEvent): void => {
    const eventName = String(event?.event || '')
    if (eventName === 'clear_output') {
      if (Boolean(event?.wait)) {
        // Jupyter clear_output(wait=True): do not blank the current frame now.
        // The next output will atomically replace it.
        pendingLiveClearWaitRef.current[index] = true
      } else {
        pendingLiveClearWaitRef.current[index] = false
        replaceLiveOutputOnNextEventRef.current[index] = false
        setLiveOutputsByCell(prev => ({ ...prev, [index]: [] }))
      }
      return
    }

    const output = event?.output
    if (!output || typeof output !== 'object') return

    const replaceCurrent = Boolean(
      pendingLiveClearWaitRef.current[index] || replaceLiveOutputOnNextEventRef.current[index],
    )
    pendingLiveClearWaitRef.current[index] = false
    replaceLiveOutputOnNextEventRef.current[index] = false

    setLiveOutputsByCell(prev => {
      const current = replaceCurrent
        ? []
        : (Array.isArray(prev[index]) ? prev[index]!.slice() : [])
      if (eventName === 'update_display_data' && event.display_id) {
        const displayId = String(event.display_id)
        const found = current.findIndex(item => String((item as any)?.transient?.display_id || '') === displayId)
        const nextOutput = { ...output, transient: { ...((output as any).transient || {}), display_id: displayId } }
        if (found >= 0) current[found] = nextOutput
        else current.push(nextOutput)
      } else {
        current.push(output)
      }
      return { ...prev, [index]: current }
    })
  }

  const executeCellFromNotebook = async (
    notebook: NotebookDocument,
    index: number,
    { selectionOnly = false, reset = false }: { selectionOnly?: boolean; reset?: boolean } = {},
  ): Promise<NotebookDocument> => {
    const cell = notebook?.cells?.[index]
    if (!cell || cell.cell_type !== 'code') return notebook

    const kernel = notebookKernelLanguage(notebook)
    if (kernel && !kernel.includes('python')) {
      window.alert(`현재 Notebook 실행은 Python 커널을 지원합니다. 이 파일의 커널은 '${kernel}'입니다.`)
      return notebook
    }

    const editor = cellEditorsRef.current[index]
    const fullCode = editor?.getValue?.() ?? notebookSourceToText(cell.source)
    let pythonCode = fullCode

    if (selectionOnly) {
      const model = editor?.getModel?.()
      const liveSelection = editor?.getSelection?.()
      const remembered = cellSelectionsRef.current[index]
      const selection = (liveSelection && !liveSelection.isEmpty?.())
        ? liveSelection
        : remembered?.selection
      pythonCode = (selection && model) ? model.getValueInRange(selection) : (remembered?.text || '')
      if (!String(pythonCode || '').trim()) {
        window.alert('현재 Notebook Code 셀에서 선택된 Python 코드가 없습니다. 실행할 코드를 드래그한 뒤 다시 선택 실행을 눌러주세요.')
        return notebook
      }
    }

    if (!String(pythonCode || '').trim()) return notebook

    setRunningCells(prev => ({ ...prev, [index]: true }))
    executionStartedAtRef.current[index] = Date.now()
    setExecutionHeartbeatAt(Date.now())
    setExecutionProgressVisible(prev => ({ ...prev, [index]: false }))
    const previousProgressTimer = executionProgressDelayRef.current[index]
    if (previousProgressTimer) window.clearTimeout(previousProgressTimer)
    executionProgressDelayRef.current[index] = window.setTimeout(() => {
      setExecutionProgressVisible(prev => ({ ...prev, [index]: true }))
    }, 650)
    pendingLiveClearWaitRef.current[index] = false
    replaceLiveOutputOnNextEventRef.current[index] = true
    // Keep the previous rendered output on screen until the first new output
    // arrives. This avoids an initial white/empty flash on animation reruns.
    const previousOutputs = Array.isArray(cell.outputs) ? cell.outputs : []
    setLiveOutputsByCell(prev => ({ ...prev, [index]: previousOutputs }))
    try {
      const result = await onExecutePython?.({
        pythonCode,
        filePath: String(filePath || ''),
        projectRoot: String(projectRoot || ''),
        cellIndex: index,
        mode: reset ? 'full' : 'selection',
        selectionOnly,
        onOutputEvent: event => handleLiveOutputEvent(index, event),
      })
      if (!result) return notebook
      return applyExecutionResult(notebook, index, result)
    } catch (error) {
      return applyExecutionResult(notebook, index, errorToExecutionResult(error))
    } finally {
      const progressTimer = executionProgressDelayRef.current[index]
      if (progressTimer) window.clearTimeout(progressTimer)
      delete executionProgressDelayRef.current[index]
      delete executionStartedAtRef.current[index]
      setExecutionProgressVisible(prev => {
        if (!Object.prototype.hasOwnProperty.call(prev, index)) return prev
        const next = { ...prev }
        delete next[index]
        return next
      })
      setRunningCells(prev => ({ ...prev, [index]: false }))
      pendingLiveClearWaitRef.current[index] = false
      replaceLiveOutputOnNextEventRef.current[index] = false
      // Give the parent notebook document one paint cycle to commit the final
      // rich output before removing the temporary streaming layer.
      window.setTimeout(() => {
        setLiveOutputsByCell(prev => {
          const next = { ...prev }
          delete next[index]
          return next
        })
      }, 80)
    }
  }

  const rememberCellSelection = (index: number): boolean => {
    const editor = cellEditorsRef.current[index]
    const model = editor?.getModel?.()
    const selection = editor?.getSelection?.()
    if (!model || !selection || selection.isEmpty?.()) return false

    const selectedText = model.getValueInRange(selection)
    if (!String(selectedText || '').trim()) return false

    cellSelectionsRef.current[index] = {
      selection: {
        startLineNumber: selection.startLineNumber,
        startColumn: selection.startColumn,
        endLineNumber: selection.endLineNumber,
        endColumn: selection.endColumn,
      },
      text: selectedText,
    }
    setActiveCellIndex(index)
    return true
  }

  const runCell = async (
    index: number,
    options: { selectionOnly?: boolean; reset?: boolean } = {},
  ): Promise<void> => {
    if (!parsed.ok) return
    cancelRequestedRef.current = false
    setActiveCellIndex(index)
    const next = await executeCellFromNotebook(parsed.notebook, index, options)
    if (next !== parsed.notebook) commitNotebook(next)
  }

  const runAll = async (): Promise<void> => {
    if (!parsed.ok || runAllBusy) return
    cancelRequestedRef.current = false
    setRunAllBusy(true)
    try {
      let working = structuredClone(parsed.notebook)
      let firstCode = true
      for (let index = 0; index < working.cells.length; index += 1) {
        const currentCell = working.cells[index]
        if (currentCell?.cell_type !== 'code') continue
        if (!notebookSourceToText(currentCell?.source).trim()) continue
        setActiveCellIndex(index)
        working = await executeCellFromNotebook(working, index, { selectionOnly: false, reset: firstCode })
        firstCode = false
        commitNotebook(working)
        if (cancelRequestedRef.current) break
        if (working.cells[index]?.outputs?.some(output => output.output_type === 'error')) break
      }
    } finally {
      setRunAllBusy(false)
    }
  }

  const runActiveCell = async (): Promise<void> => runCell(activeCellIndex, { selectionOnly: false, reset: false })
  const runSelection = async (): Promise<void> => runCell(activeCellIndex, { selectionOnly: true, reset: false })

  const revealDebugLine = (state: NotebookDebugResult): void => {
    const cellIndex = Math.max(0, Number(state.cell_index) || 0)
    const lineNumber = Math.max(1, Number(state.line) || 1)
    setActiveCellIndex(cellIndex)
    const section = shellRef.current?.querySelector(`[data-notebook-cell-index="${cellIndex}"]`) as HTMLElement | null
    section?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
    window.setTimeout(() => {
      const editor = cellEditorsRef.current[cellIndex]
      editor?.revealLineInCenter?.(lineNumber)
      editor?.setPosition?.({ lineNumber, column: 1 })
      editor?.focus?.()
    }, 60)
  }

  const handleDebugResponse = (state: NotebookDebugResult | null | undefined): void => {
    if (!state) return
    const event = String(state.event || '')
    if (event === 'evaluate') {
      const expression = debugExpression.trim()
      const error = String(state.evaluate_error || '')
      const result = error || String(state.evaluate_result ?? '')
      if (expression) {
        setDebugConsole(prev => [...prev, { expression, result, error: !!error }].slice(-50))
      }
      setDebugState(prev => ({ ...(prev || {}), ...state, debug_active: true }))
      return
    }
    setDebugState(state)
    if (state.debug_active && event === 'paused') revealDebugLine(state)
    if (!state.debug_active && ['finished', 'stopped', 'error'].includes(event)) {
      const cellIndex = Math.max(0, Number(state.cell_index) || Number(debugState?.cell_index) || activeCellIndex)
      if (parsed.ok && parsed.notebook.cells[cellIndex]?.cell_type === 'code') {
        const result: NotebookExecutionResult = {
          ...state,
          ok: event === 'finished' ? true : !!state.ok,
          cancelled: event === 'stopped' || !!state.cancelled,
        }
        const next = applyExecutionResult(parsed.notebook, cellIndex, result)
        commitNotebook(next)
      }
    }
  }

  const startDebugCell = async (index: number): Promise<void> => {
    if (!parsed.ok || debugBusy || debugState?.debug_active) return
    const cell = parsed.notebook.cells[index]
    if (cell?.cell_type !== 'code') return
    const editor = cellEditorsRef.current[index]
    const pythonCode = editor?.getValue?.() ?? latestCellSourcesRef.current[index] ?? notebookSourceToText(cell.source)
    if (!String(pythonCode || '').trim()) return
    const lines = getNotebookLineBreakpoints(scrollKeyRef.current)
      .filter(item => item.cellIndex === index)
      .map(item => item.lineNumber)
    setDebugBusy(true)
    setDebugConsole([])
    setActiveCellIndex(index)
    try {
      const result = await onDebugPython?.({
        pythonCode,
        filePath: String(filePath || ''),
        projectRoot: String(projectRoot || ''),
        cellIndex: index,
        breakpoints: lines,
      })
      handleDebugResponse(result)
    } catch (error) {
      handleDebugResponse({ ...errorToExecutionResult(error), event: 'error', debug_active: false, cell_index: index })
    } finally {
      setDebugBusy(false)
    }
  }

  const sendDebugCommand = async (command: NotebookDebugCommandRequest['command'], expression = ''): Promise<void> => {
    if (!debugState?.debug_active || debugBusy) return
    setDebugBusy(true)
    try {
      const result = await onDebugCommand?.({
        command,
        expression,
        filePath: String(filePath || ''),
        projectRoot: String(projectRoot || ''),
      })
      handleDebugResponse(result)
      if (command === 'evaluate' && result) setDebugExpression('')
    } catch (error) {
      handleDebugResponse({ ...errorToExecutionResult(error), event: 'error', debug_active: false, cell_index: debugState.cell_index })
    } finally {
      setDebugBusy(false)
    }
  }

  useEffect(() => {
    if (!debugState?.debug_active) return
    const onDebugShortcut = (event: KeyboardEvent) => {
      let command: NotebookDebugCommandRequest['command'] | '' = ''
      if (event.key === 'F5' && !event.shiftKey) command = 'continue'
      else if (event.key === 'F10') command = 'step_over'
      else if (event.key === 'F11' && event.shiftKey) command = 'step_out'
      else if (event.key === 'F11') command = 'step_into'
      else if (event.key === 'F5' && event.shiftKey) command = 'stop'
      if (!command) return
      event.preventDefault()
      event.stopPropagation()
      void sendDebugCommand(command)
    }
    window.addEventListener('keydown', onDebugShortcut, true)
    return () => window.removeEventListener('keydown', onDebugShortcut, true)
  }, [debugState?.debug_active, debugBusy, filePath, projectRoot])

  const stopExecution = async (): Promise<void> => {
    if (stopBusy) return
    cancelRequestedRef.current = true
    setStopBusy(true)
    try {
      await onStopPython?.()
    } finally {
      setStopBusy(false)
    }
  }

  const revealSearchMatch = (cellIndex: number, lineNumber = 1, column = 1, length = 1): void => {
    const maxIndex = parsed.ok ? Math.max(0, parsed.notebook.cells.length - 1) : 0
    const safeIndex = Math.max(0, Math.min(Number(cellIndex) || 0, maxIndex))
    setActiveCellIndex(safeIndex)
    const section = shellRef.current?.querySelector(`[data-notebook-cell-index="${safeIndex}"]`) as HTMLElement | null
    section?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
    const editor = cellEditorsRef.current[safeIndex]
    if (!editor) return
    const safeLine = Math.max(1, Number(lineNumber) || 1)
    const safeColumn = Math.max(1, Number(column) || 1)
    editor.revealLineInCenter?.(safeLine)
    editor.setSelection?.({
      startLineNumber: safeLine,
      startColumn: safeColumn,
      endLineNumber: safeLine,
      endColumn: safeColumn + Math.max(1, Number(length) || 1),
    })
    editor.focus?.()
  }

  useEffect(() => {
    if (!controllerRef) return
    controllerRef.current = {
      runAll,
      runActiveCell,
      runSelection,
      stopExecution,
      isRunning: () => runAllBusy || Object.values(runningCells).some(Boolean),
      getActiveCellIndex: () => activeCellIndex,
      revealSearchMatch,
    }
    return () => {
      if (controllerRef.current?.runAll === runAll) controllerRef.current = null
    }
  })

  const addCell = (cellType: 'code' | 'markdown') => {
    if (!parsed.ok) return
    const notebook = structuredClone(parsed.notebook)
    const insertAt = Math.min(notebook.cells.length, Math.max(0, activeCellIndex + 1))
    const cell: NotebookCell = cellType === 'markdown'
      ? { cell_type: 'markdown', metadata: {}, source: [] }
      : { cell_type: 'code', execution_count: null, metadata: {}, outputs: [], source: [] }
    notebook.cells.splice(insertAt, 0, cell)
    shiftBookmarksForInsertedCell(insertAt)
    shiftBreakpointsForInsertedCell(insertAt)
    commitNotebook(notebook)
    setActiveCellIndex(insertAt)
    if (cellType === 'markdown') setEditingMarkdown(prev => ({ ...prev, [insertAt]: true }))
  }

  const deleteCell = (index: number) => {
    if (!parsed.ok) return
    const notebook = structuredClone(parsed.notebook)
    if (!notebook.cells[index]) return
    notebook.cells.splice(index, 1)
    shiftBookmarksForDeletedCell(index)
    shiftBreakpointsForDeletedCell(index)
    commitNotebook(notebook)
    setActiveCellIndex(Math.max(0, Math.min(index, notebook.cells.length - 1)))
  }

  const clearAllOutputs = () => {
    if (!parsed.ok) return
    const notebook = structuredClone(parsed.notebook)
    notebook.cells = notebook.cells.map(cell => cell?.cell_type === 'code'
      ? { ...cell, execution_count: null, outputs: [] }
      : cell)
    commitNotebook(notebook)
  }

  const handoffNotebookWheelAtBoundary = (index: number, event: React.WheelEvent<HTMLElement>) => {
    if (event.ctrlKey || !event.deltaY) return
    const editor = cellEditorsRef.current[index]
    if (!editor) return

    const domNode = editor.getDomNode?.()
    const target = event.target as Node | null
    if (!domNode || !target || !domNode.contains(target)) return

    const scrollTop = Number(editor.getScrollTop?.() || 0)
    const scrollHeight = Number(editor.getScrollHeight?.() || 0)
    const viewportHeight = Number(editor.getLayoutInfo?.()?.height || 0)
    const maxScrollTop = Math.max(0, scrollHeight - viewportHeight)
    const atTop = scrollTop <= 1
    const atBottom = scrollTop >= maxScrollTop - 1
    const wantsOuterScroll = (event.deltaY < 0 && atTop) || (event.deltaY > 0 && atBottom)
    if (!wantsOuterScroll) return

    const shell = domNode.closest?.('.notebook-editor-shell') as HTMLElement | null
    if (!shell) return

    const multiplier = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? Math.max(120, shell.clientHeight) : 1
    shell.scrollTop += event.deltaY * multiplier
    event.preventDefault()
    event.stopPropagation()
  }

  if (!parsed.ok) {
    const agentStudioPlaceholder = /^\s*\/\/\s*파일을 선택하세요\.?\s*$/.test(String(value || ''))
    return <div
      ref={shellRef}
      className="notebook-editor-shell notebook-invalid"
      onScroll={event => rememberOuterScroll(event.currentTarget.scrollTop)}
    >
      <div className="notebook-invalid-banner">
        <strong>{agentStudioPlaceholder ? 'Notebook 원본 내용이 손상되었을 수 있습니다.' : 'Notebook 보기로 열 수 없습니다.'}</strong>
        <span>{parsed.error}</span>
        <small>{agentStudioPlaceholder
          ? '로드 완료 후에도 이 문구가 보이면 디스크의 .ipynb 내용 자체가 AgentStudio의 과거 기본 placeholder로 바뀐 상태일 수 있습니다. 저장하지 말고 원본/백업/.ipynb_checkpoints 파일을 확인하세요.'
          : '원본 JSON을 수정하면 유효한 .ipynb 형식이 되는 즉시 Notebook 보기로 전환됩니다.'}</small>
      </div>
      <Editor
        className="main-monaco-editor"
        height="100%"
        path={getEditorModelPath(projectRoot, filePath)}
        language="json"
        value={value}
        onChange={nextValue => onChange?.(nextValue ?? '')}
        theme="vs-dark"
        options={{ minimap: { enabled: false }, fontSize: 13, automaticLayout: true, tabSize: 2 }}
      />
    </div>
  }

  const notebook = parsed.notebook
  const kernel = notebookKernelLanguage(notebook)

  return <div
    ref={shellRef}
    className="notebook-editor-shell"
    onScroll={event => rememberOuterScroll(event.currentTarget.scrollTop)}
    onMouseDownCapture={() => onEditorFocus?.()}
    onFocusCapture={() => onEditorFocus?.()}
  >
    <div className="notebook-toolbar">
      <div className="notebook-toolbar-left">
        <strong>Jupyter Notebook</strong>
        <span className="notebook-kernel-chip">{kernel || 'python'}</span>
        <span className="notebook-cell-count">{notebook.cells.length} cells</span>
        <span className="notebook-bookmark-hint" title="줄 번호는 북마크, 줄 번호 왼쪽의 glyph 여백은 빨간 디버그 중단점입니다.">🔖 줄 번호=북마크 · ● 왼쪽 여백=중단점</span>
      </div>
      <div className="notebook-toolbar-actions">
        <div className="notebook-bookmark-navigation" aria-label="Notebook 북마크 이동">
          <button type="button" className="notebook-bookmark-toggle" disabled={notebook.cells[activeCellIndex]?.cell_type !== 'code'} title="현재 활성 Code 셀의 커서 줄에 북마크 추가/해제" onClick={toggleActiveLineBookmark}>🔖 현재 줄</button>
          <button type="button" disabled={!bookmarks.length} title="이전 북마크로 이동" onClick={() => moveToBookmark(-1)}>◀</button>
          <span className="notebook-bookmark-count" title="현재 Notebook에 저장된 줄 북마크 수"><i aria-hidden="true" />북마크 {bookmarks.length}</span>
          <button type="button" disabled={!bookmarks.length} title="다음 북마크로 이동" onClick={() => moveToBookmark(1)}>▶</button>
          {bookmarks.length > 0 && <button type="button" title="현재 Notebook의 북마크 모두 해제" onClick={clearBookmarks}>모두 해제</button>}
        </div>
        <button type="button" onClick={() => addCell('code')}>＋ 코드</button>
        <button type="button" onClick={() => addCell('markdown')}>＋ Markdown</button>
        <button type="button" onClick={clearAllOutputs}>출력 모두 지우기</button>
      </div>
    </div>

    {(debugState?.debug_active || breakpoints.length > 0) && <div className="notebook-debug-toolbar" role="region" aria-label="Notebook 디버그 도구">
      <div className="notebook-debug-toolbar-status">
        <span className="notebook-debug-dot" />
        <strong>{debugState?.debug_active ? '디버그 일시정지' : '중단점 준비'}</strong>
        {debugState?.debug_active
          ? <span>Cell {Number(debugState.cell_index || 0) + 1} · Line {Number(debugState.line || 1)}</span>
          : <span>중단점 {breakpoints.length}개 · 디버그 시작 후 F10/F11을 사용할 수 있습니다.</span>}
        {debugState?.reason === 'exception' && <em>예외</em>}
      </div>
      <div className="notebook-debug-toolbar-actions">
        {!debugState?.debug_active && <button type="button" className={debugBusy ? 'busy' : ''} disabled={debugBusy || !isPythonNotebookKernel(kernel)} title="중단점이 있는 셀 또는 현재 셀에서 디버그 시작" onClick={() => {
          const activeHasBreakpoint = breakpoints.some(item => item.cellIndex === activeCellIndex)
          const targetCell = activeHasBreakpoint ? activeCellIndex : (breakpoints[0]?.cellIndex ?? activeCellIndex)
          void startDebugCell(targetCell)
        }}>{debugBusy ? '시작 중…' : '▶ 디버그 시작'}</button>}
        <button type="button" disabled={debugBusy || !debugState?.debug_active} title="계속 (F5)" onClick={() => void sendDebugCommand('continue')}>▶ 계속</button>
        <button type="button" disabled={debugBusy || !debugState?.debug_active} title="다음 줄 / Step Over (F10)" onClick={() => void sendDebugCommand('step_over')}>↷ 다음 줄</button>
        <button type="button" disabled={debugBusy || !debugState?.debug_active} title="함수 안으로 / Step Into (F11)" onClick={() => void sendDebugCommand('step_into')}>↓ 함수 안</button>
        <button type="button" disabled={debugBusy || !debugState?.debug_active} title="함수 밖으로 / Step Out (Shift+F11)" onClick={() => void sendDebugCommand('step_out')}>↑ 함수 밖</button>
        <button type="button" className="danger" disabled={debugBusy || !debugState?.debug_active} title="디버그 종료 (Shift+F5)" onClick={() => void sendDebugCommand('stop')}>■ 종료</button>
      </div>
    </div>}

    <div className="notebook-cells">
      {notebook.cells.map((cell, index) => {
        const cellType = String(cell?.cell_type || 'raw')
        const source = notebookSourceToText(cell?.source)
        const active = index === activeCellIndex
        const running = !!runningCells[index]
        const progressVisible = running && !!executionProgressVisible[index]
        const executionStartedAt = Number(executionStartedAtRef.current[index] || executionHeartbeatAt)
        const executionElapsed = formatNotebookExecutionElapsed(executionHeartbeatAt - executionStartedAt)
        const lineCount = Math.max(1, source.replace(/\r\n|\r/g, '\n').split('\n').length)
        const autoEditorHeight = Math.min(520, Math.max(NOTEBOOK_CELL_EDITOR_MIN_HEIGHT, lineCount * 20 + 30))
        const storedEditorHeight = NOTEBOOK_CELL_EDITOR_HEIGHTS.get(notebookCellEditorHeightKey(scrollKey, index))
        const editorHeight = Math.min(
          NOTEBOOK_CELL_EDITOR_MAX_HEIGHT,
          Math.max(NOTEBOOK_CELL_EDITOR_MIN_HEIGHT, storedEditorHeight ?? autoEditorHeight),
        )

        return <section
          key={cell?.id || `cell-${index}`}
          data-notebook-cell-index={index}
          className={`notebook-cell ${cellType} ${active ? 'active' : ''}`}
          onMouseDown={() => setActiveCellIndex(index)}
          onWheelCapture={(event: React.WheelEvent<HTMLElement>) => cellType === 'code' && handoffNotebookWheelAtBoundary(index, event)}
        >
          <div className="notebook-cell-gutter">
            {cellType === 'code'
              ? <span>{cell.execution_count != null ? `[${cell.execution_count}]` : '[ ]'}</span>
              : <span>{cellType === 'markdown' ? 'M' : 'R'}</span>}
          </div>

          <div className="notebook-cell-main">
            <div className="notebook-cell-toolbar">
              <span>{cellType === 'code' ? 'Code' : cellType === 'markdown' ? 'Markdown' : 'Raw'}</span>
              <div>
                {cellType === 'code' && <>
                  <button type="button" disabled={running || runAllBusy || !!debugState?.debug_active} onClick={(event: React.MouseEvent<HTMLButtonElement>) => { event.stopPropagation(); void runCell(index) }}>{running ? '실행 중…' : '▶ 셀 실행'}</button>
                  <button type="button" className="notebook-debug-cell-button" disabled={running || runAllBusy || debugBusy || !!debugState?.debug_active || !isPythonNotebookKernel(kernel)} title="현재 셀을 디버그합니다. 줄 번호 왼쪽 여백을 클릭하면 중단점을 설정할 수 있습니다." onClick={(event: React.MouseEvent<HTMLButtonElement>) => { event.stopPropagation(); void startDebugCell(index) }}>{debugBusy ? '🐞 시작 중…' : '🐞 디버그 셀'}</button>
                  <button
                    type="button"
                    disabled={running || runAllBusy || !!debugState?.debug_active}
                    onMouseDown={(event: React.MouseEvent<HTMLButtonElement>) => {
                      event.preventDefault()
                      event.stopPropagation()
                      rememberCellSelection(index)
                    }}
                    onClick={(event: React.MouseEvent<HTMLButtonElement>) => {
                      event.stopPropagation()
                      void runCell(index, { selectionOnly: true })
                    }}
                  >▣ 선택 실행</button>
                  {(running || runAllBusy) && <button type="button" className="danger execution-stop-button" disabled={stopBusy} onClick={(event: React.MouseEvent<HTMLButtonElement>) => { event.stopPropagation(); void stopExecution() }}>■ {stopBusy ? '정지 중…' : '실행 정지'}</button>}
                </>}
                {cellType === 'markdown' && <button type="button" onClick={(event: React.MouseEvent<HTMLButtonElement>) => { event.stopPropagation(); setEditingMarkdown(prev => ({ ...prev, [index]: !prev[index] })) }}>{editingMarkdown[index] ? '미리보기' : '편집'}</button>}
                <button type="button" className="danger" onClick={(event: React.MouseEvent<HTMLButtonElement>) => { event.stopPropagation(); deleteCell(index) }}>삭제</button>
              </div>
            </div>

            {cellType === 'code' && progressVisible && <div className="notebook-execution-progress" role="status" aria-live="polite">
              <div className="notebook-execution-progress-head">
                <strong>{runAllBusy ? '전체 실행 중' : '셀 실행 중'}</strong>
                <span>{executionElapsed}</span>
              </div>
              <div className="notebook-execution-progress-track" role="progressbar" aria-label="Notebook Python 실행 중" aria-valuetext={`실행 중 ${executionElapsed}`}>
                <i />
              </div>
              <small>Python 실행 결과를 기다리고 있습니다. 실행 시간이 길어도 이 표시가 움직이면 작업은 계속 진행 중입니다.</small>
            </div>}

            {cellType === 'code'
              ? <div
                  className="notebook-code-editor-resizable"
                  style={{ height: `${editorHeight}px` }}
                >
                  <Editor
                    height="100%"
                  path={`${getEditorModelPath(projectRoot, filePath)}?cell=${index}`}
                  language="python"
                  defaultValue={source}
                  onChange={nextValue => updateCellSource(index, nextValue ?? '')}
                  onMount={(editor, monaco) => {
                    cellEditorsRef.current[index] = editor as unknown as NotebookMonacoEditorLike
                    latestCellSourcesRef.current[index] = editor.getValue?.() ?? source
                    registerEscapedDoubleQuotePairGuard(editor as unknown as any)
                    registerCodeIntelligence(monaco, editor, {
                      root: String(projectRoot || ''),
                      relativePath: String(filePath || ''),
                      language: 'python',
                      cellIndex: index,
                      getNotebookContent: buildLiveNotebookContent,
                      onOpenDefinition: (definition, sourceLocation) => openNotebookDefinition(definition, sourceLocation, index),
                    })
                    editor.addCommand?.(monaco.KeyMod.Alt | monaco.KeyCode.LeftArrow, () => navigateNotebookCodeHistory(-1))
                    editor.addCommand?.(monaco.KeyMod.Alt | monaco.KeyCode.RightArrow, () => navigateNotebookCodeHistory(1))
                    editor.addAction?.({
                      id: `theanova.llm-reference-selection.cell-${index}`,
                      label: 'LLM 참조 문구',
                      precondition: 'editorHasSelection',
                      contextMenuGroupId: '9_cutcopypaste',
                      contextMenuOrder: 3.5,
                      run: currentEditor => {
                        const selection = currentEditor?.getSelection?.()
                        const model = currentEditor?.getModel?.()
                        if (!selection || !model || selection.isEmpty?.()) return
                        const selectedText = String(model.getValueInRange(selection) || '')
                        if (!selectedText.trim()) return
                        setActiveCellIndex(index)
                        onAddLlmReference?.({
                          path: filePath,
                          text: selectedText,
                          start_line: selection.startLineNumber,
                          start_column: selection.startColumn,
                          end_line: selection.endLineNumber,
                          end_column: selection.endColumn,
                          cell_index: index,
                          source: 'notebook-code-cell-selection',
                        })
                        // v5.466: 직전 참조 selection이 다음 우클릭에서 다시
                        // 사용되지 않도록 참조 등록 직후 caret로 접습니다.
                        currentEditor?.setSelection?.({
                          startLineNumber: selection.endLineNumber,
                          startColumn: selection.endColumn,
                          endLineNumber: selection.endLineNumber,
                          endColumn: selection.endColumn,
                        })
                        currentEditor?.focus?.()
                      },
                    })
                    applyBookmarkDecorations(index, editor)
                    applyDebugDecorations(index, editor)
                    editor.onMouseDown?.((event: NotebookEditorMouseDownEventLike) => {
                      // Monaco MouseTargetType: glyph=2, line number=3, line decoration=4.
                      // VS Code와 비슷하게 glyph 여백(줄 번호보다 더 왼쪽)은 빨간
                      // 디버그 중단점, 줄 번호/장식 영역은 기존 파란 북마크입니다.
                      const targetType = Number(event?.target?.type)
                      if (![2, 3, 4].includes(targetType)) return
                      const lineNumber = Number(event?.target?.position?.lineNumber)
                      if (!Number.isInteger(lineNumber) || lineNumber < 1) return
                      setActiveCellIndex(index)
                      if (targetType === 2) toggleLineBreakpoint(index, lineNumber)
                      else toggleLineBookmark(index, lineNumber)
                    })
                    editor.onDidFocusEditorText(() => {
                      setActiveCellIndex(index)
                      onEditorFocus?.()
                    })
                    editor.onDidBlurEditorText(() => {
                      // If an external Agent/Reload changed this cell while it was
                      // focused, apply that authoritative value only after blur.
                      // Normal typing already mirrors the same value, so this does
                      // not disturb the user's caret during editing.
                      const expected = latestCellSourcesRef.current[index]
                      const current = editor.getValue?.() ?? ''
                      if (typeof expected === 'string' && expected !== current) {
                        editor.setValue?.(expected)
                      }
                    })
                    editor.onDidChangeCursorSelection((event: NotebookCursorSelectionEvent) => {
                      const selection = event?.selection
                      const model = editor.getModel?.()
                      if (!selection || !model || selection.isEmpty?.()) return
                      const selectedText = model.getValueInRange(selection)
                      if (!String(selectedText || '').trim()) return
                      cellSelectionsRef.current[index] = {
                        selection: {
                          startLineNumber: selection.startLineNumber,
                          startColumn: selection.startColumn,
                          endLineNumber: selection.endLineNumber,
                          endColumn: selection.endColumn,
                        },
                        text: selectedText,
                      }
                      setActiveCellIndex(index)
                    })
                  }}
                  theme="vs-dark"
                  options={{
                    minimap: { enabled: false },
                    glyphMargin: true,
                    lineNumbersMinChars: 3,
                    lineDecorationsWidth: 14,
                    fontSize: 13,
                    lineNumbers: 'on',
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    tabSize: 4,
                    insertSpaces: true,
                    // v5.462: Notebook code cells use the same VS Code-style pair typing
                    // as source editors. The cell stays uncontrolled while focused, so Monaco
                    // can insert (), {}, [], and "" without losing the caret during the
                    // Notebook JSON mirror update. Escaped " quotes are guarded explicitly.
                    ...CODE_EDITOR_PAIR_TYPING_OPTIONS,
                    folding: false,
                    renderLineHighlight: 'line',
                    overviewRulerLanes: 0,
                    mouseWheelZoom: false,
                    scrollbar: {
                      vertical: 'auto',
                      horizontal: 'auto',
                      alwaysConsumeMouseWheel: false,
                    },
                  }}
                  />
                  <div
                    className="notebook-code-editor-resize-handle"
                    role="separator"
                    aria-orientation="horizontal"
                    aria-label="코드 셀 높이 조절"
                    title="위/아래로 드래그해 코드 셀 높이를 조절합니다. 더블클릭하면 자동 높이로 돌아갑니다."
                    onPointerDown={(event: React.PointerEvent<HTMLDivElement>) => beginCellEditorResize(index, event)}
                    onDoubleClick={(event: React.MouseEvent<HTMLDivElement>) => {
                      event.preventDefault()
                      event.stopPropagation()
                      NOTEBOOK_CELL_EDITOR_HEIGHTS.delete(notebookCellEditorHeightKey(scrollKey, index))
                      const container = event.currentTarget.parentElement as HTMLDivElement | null
                      if (container) container.style.height = `${autoEditorHeight}px`
                    }}
                  >
                    <span />
                  </div>
                </div>
              : cellType === 'markdown'
                ? (editingMarkdown[index]
                    ? <Editor
                        height={`${Math.min(520, Math.max(100, lineCount * 20 + 36))}px`}
                        path={`${getEditorModelPath(projectRoot, filePath)}?markdown=${index}`}
                        language="markdown"
                        defaultValue={source}
                        onMount={(editor) => {
                          editor.addAction?.({
                            id: `theanova.llm-reference-selection.markdown-${index}`,
                            label: 'LLM 참조 문구',
                            precondition: 'editorHasSelection',
                            contextMenuGroupId: '9_cutcopypaste',
                            contextMenuOrder: 3.5,
                            run: currentEditor => {
                              const selection = currentEditor?.getSelection?.()
                              const model = currentEditor?.getModel?.()
                              if (!selection || !model || selection.isEmpty?.()) return
                              const selectedText = String(model.getValueInRange(selection) || '')
                              if (!selectedText.trim()) return
                              setActiveCellIndex(index)
                              onAddLlmReference?.({
                                path: filePath,
                                text: selectedText,
                                start_line: selection.startLineNumber,
                                start_column: selection.startColumn,
                                end_line: selection.endLineNumber,
                                end_column: selection.endColumn,
                                cell_index: index,
                                source: 'notebook-markdown-selection',
                              })
                              currentEditor?.setSelection?.({
                                startLineNumber: selection.endLineNumber,
                                startColumn: selection.endColumn,
                                endLineNumber: selection.endLineNumber,
                                endColumn: selection.endColumn,
                              })
                              currentEditor?.focus?.()
                            },
                          })
                        }}
                        onChange={nextValue => updateCellSource(index, nextValue ?? '')}
                        theme="vs-dark"
                        options={{
                          minimap: { enabled: false },
                          fontSize: 13,
                          lineNumbers: 'off',
                          scrollBeyondLastLine: false,
                          automaticLayout: true,
                          wordWrap: 'on',
                          autoClosingBrackets: 'never',
                          autoClosingQuotes: 'never',
                          autoClosingDelete: 'never',
                          autoClosingOvertype: 'never',
                          autoSurround: 'never',
                          overviewRulerLanes: 0,
                          mouseWheelZoom: false,
                          scrollbar: { vertical: 'auto', horizontal: 'auto', alwaysConsumeMouseWheel: false },
                        }}
                      />
                    : <div className="notebook-markdown-cell" onDoubleClick={() => setEditingMarkdown(prev => ({ ...prev, [index]: true }))}><NotebookMarkdown text={source} attachments={cell.attachments || {}} /></div>)
                : <pre className="notebook-raw-cell">{source}</pre>}

            {cellType === 'code' && debugState?.debug_active && Number(debugState.cell_index) === index && <div className="notebook-debug-panel">
              <div className="notebook-debug-current">
                <strong>현재 위치</strong>
                <code>Line {Number(debugState.line || 1)} · {String(debugState.source_line || '').trim() || '(빈 줄)'}</code>
                {debugState.exception && <span className="notebook-debug-exception">{debugState.exception.type}: {debugState.exception.message}</span>}
              </div>
              <div className="notebook-debug-grid">
                <section>
                  <header>변수 <span>{Array.isArray(debugState.variables) ? debugState.variables.length : 0}</span></header>
                  <div className="notebook-debug-variable-list">
                    {(debugState.variables || []).length === 0 && <small>현재 프레임에 표시할 변수가 없습니다.</small>}
                    {(debugState.variables || []).map((item, itemIndex) => <div className="notebook-debug-variable" key={`${item.name}-${itemIndex}`}>
                      <b>{item.name}</b><i>{item.type || ''}</i><code title={item.value || ''}>{item.value || ''}</code>
                    </div>)}
                  </div>
                </section>
                <section>
                  <header>호출 스택 <span>{Array.isArray(debugState.stack) ? debugState.stack.length : 0}</span></header>
                  <div className="notebook-debug-stack-list">
                    {(debugState.stack || []).map((frame, frameIndex) => <button type="button" key={`${frame.function}-${frame.line}-${frameIndex}`} onClick={() => revealDebugLine({ ...debugState, line: frame.line })}>
                      <b>{frame.function || '<module>'}</b><span>Line {frame.line || 0}</span>
                    </button>)}
                  </div>
                </section>
              </div>
              <div className="notebook-debug-console">
                <header>디버그 콘솔</header>
                {debugConsole.length > 0 && <div className="notebook-debug-console-history">
                  {debugConsole.map((item, itemIndex) => <div key={`${item.expression}-${itemIndex}`} className={item.error ? 'error' : ''}><span>› {item.expression}</span><code>{item.result}</code></div>)}
                </div>}
                <div className="notebook-debug-console-input">
                  <input value={debugExpression} onChange={event => setDebugExpression(event.target.value)} placeholder="예: all_tokens, len(all_tokens), word_counts" onKeyDown={event => { if (event.key === 'Enter' && debugExpression.trim()) { event.preventDefault(); void sendDebugCommand('evaluate', debugExpression.trim()) } }} />
                  <button type="button" disabled={debugBusy || !debugExpression.trim()} onClick={() => void sendDebugCommand('evaluate', debugExpression.trim())}>평가</button>
                </div>
              </div>
            </div>}

            {cellType === 'code' && (() => {
              const hasLiveOutputs = Object.prototype.hasOwnProperty.call(liveOutputsByCell, index)
              const visibleOutputs = hasLiveOutputs ? (liveOutputsByCell[index] || []) : (Array.isArray(cell.outputs) ? cell.outputs : [])
              if (!visibleOutputs.length) return null
              return (
                <div className={`notebook-cell-outputs${hasLiveOutputs ? ' live' : ''}`}>
                  {visibleOutputs.map((output, outputIndex) => <NotebookOutput key={outputIndex} output={output} />)}
                </div>
              )
            })()}
          </div>
        </section>
      })}
    </div>
  </div>
}
