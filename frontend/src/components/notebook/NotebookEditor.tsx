import React, { useEffect, useRef, useState } from 'react'
import Editor from '@monaco-editor/react'
import { getEditorModelPath } from '../../utils/editor'
import { notebookKernelLanguage, parseNotebookDocument, textToNotebookSource } from '../../utils/notebook'
import type {
  NotebookCell,
  NotebookDocument,
  NotebookEditorController,
  NotebookExecutionRequest,
  NotebookExecutionResult,
  NotebookOutputData,
} from '../../types/notebook'
import { NotebookMarkdown, NotebookOutput, notebookSourceToText } from './NotebookRenderers'

interface NotebookSelection {
  startLineNumber: number
  startColumn: number
  endLineNumber: number
  endColumn: number
  isEmpty?: () => boolean
}

interface NotebookEditorModelLike {
  getValueInRange: (selection: NotebookSelection) => string
}

interface NotebookEditorLayoutInfoLike {
  height?: number
}

interface NotebookMonacoEditorLike {
  getValue?: () => string
  getModel?: () => NotebookEditorModelLike | null
  getSelection?: () => NotebookSelection | null
  getDomNode?: () => HTMLElement | null
  getScrollTop?: () => number
  getScrollHeight?: () => number
  getLayoutInfo?: () => NotebookEditorLayoutInfoLike
}

interface NotebookCursorSelectionEvent {
  selection?: NotebookSelection
}

interface RememberedCellSelection {
  selection: NotebookSelection
  text: string
}

export interface NotebookEditorProps {
  value: string
  filePath?: string
  projectRoot?: string
  onChange?: (value: string) => void
  onExecutePython?: (request: NotebookExecutionRequest) => Promise<NotebookExecutionResult | null | undefined> | NotebookExecutionResult | null | undefined
  onStopPython?: () => Promise<unknown> | unknown
  controllerRef?: React.MutableRefObject<NotebookEditorController | null> | null
  onEditorFocus?: () => void
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
  controllerRef,
  onEditorFocus,
}: NotebookEditorProps) {
  const parsed = React.useMemo(() => parseNotebookDocument(value), [value])
  const cellEditorsRef = useRef<Record<number, NotebookMonacoEditorLike | undefined>>({})
  const cellSelectionsRef = useRef<Record<number, RememberedCellSelection | undefined>>({})
  const [editingMarkdown, setEditingMarkdown] = useState<Record<number, boolean>>({})
  const [activeCellIndex, setActiveCellIndex] = useState(0)
  const [runningCells, setRunningCells] = useState<Record<number, boolean>>({})
  const [runAllBusy, setRunAllBusy] = useState(false)
  const [stopBusy, setStopBusy] = useState(false)
  const cancelRequestedRef = useRef(false)
  const executionCounterRef = useRef(0)

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
  }, [filePath])

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
    patchCell(index, { source: textToNotebookSource(text) })
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
    }

    executionCounterRef.current += 1
    next.cells[index] = {
      ...cell,
      execution_count: executionCounterRef.current,
      outputs,
    }
    return next
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
    try {
      const result = await onExecutePython?.({
        pythonCode,
        filePath: String(filePath || ''),
        cellIndex: index,
        mode: reset ? 'full' : 'selection',
        selectionOnly,
      })
      if (!result) return notebook
      return applyExecutionResult(notebook, index, result)
    } catch (error) {
      return applyExecutionResult(notebook, index, errorToExecutionResult(error))
    } finally {
      setRunningCells(prev => ({ ...prev, [index]: false }))
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

  useEffect(() => {
    if (!controllerRef) return
    controllerRef.current = {
      runAll,
      runActiveCell,
      runSelection,
      stopExecution,
      isRunning: () => runAllBusy || Object.values(runningCells).some(Boolean),
      getActiveCellIndex: () => activeCellIndex,
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
    commitNotebook(notebook)
    setActiveCellIndex(insertAt)
    if (cellType === 'markdown') setEditingMarkdown(prev => ({ ...prev, [insertAt]: true }))
  }

  const deleteCell = (index: number) => {
    if (!parsed.ok) return
    const notebook = structuredClone(parsed.notebook)
    if (!notebook.cells[index]) return
    notebook.cells.splice(index, 1)
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
    return <div className="notebook-editor-shell notebook-invalid">
      <div className="notebook-invalid-banner">
        <strong>Notebook 보기로 열 수 없습니다.</strong>
        <span>{parsed.error}</span>
        <small>원본 JSON을 수정하면 유효한 .ipynb 형식이 되는 즉시 Notebook 보기로 전환됩니다.</small>
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
    className="notebook-editor-shell"
    onMouseDownCapture={() => onEditorFocus?.()}
    onFocusCapture={() => onEditorFocus?.()}
  >
    <div className="notebook-toolbar">
      <div className="notebook-toolbar-left">
        <strong>Jupyter Notebook</strong>
        <span className="notebook-kernel-chip">{kernel || 'python'}</span>
        <span className="notebook-cell-count">{notebook.cells.length} cells</span>
      </div>
      <div className="notebook-toolbar-actions">
        <button type="button" onClick={() => addCell('code')}>＋ 코드</button>
        <button type="button" onClick={() => addCell('markdown')}>＋ Markdown</button>
        <button type="button" onClick={clearAllOutputs}>출력 모두 지우기</button>
      </div>
    </div>

    <div className="notebook-cells">
      {notebook.cells.map((cell, index) => {
        const cellType = String(cell?.cell_type || 'raw')
        const source = notebookSourceToText(cell?.source)
        const active = index === activeCellIndex
        const running = !!runningCells[index]
        const lineCount = Math.max(1, source.replace(/\r\n|\r/g, '\n').split('\n').length)
        const editorHeight = Math.min(520, Math.max(92, lineCount * 20 + 30))

        return <section
          key={cell?.id || `cell-${index}`}
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
                  <button type="button" disabled={running || runAllBusy} onClick={(event: React.MouseEvent<HTMLButtonElement>) => { event.stopPropagation(); void runCell(index) }}>{running ? '실행 중…' : '▶ 셀 실행'}</button>
                  <button
                    type="button"
                    disabled={running || runAllBusy}
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

            {cellType === 'code'
              ? <Editor
                  height={`${editorHeight}px`}
                  path={`${getEditorModelPath(projectRoot, filePath)}?cell=${index}`}
                  language="python"
                  value={source}
                  onChange={nextValue => updateCellSource(index, nextValue ?? '')}
                  onMount={editor => {
                    cellEditorsRef.current[index] = editor
                    editor.onDidFocusEditorText(() => {
                      setActiveCellIndex(index)
                      onEditorFocus?.()
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
                    fontSize: 13,
                    lineNumbers: 'on',
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    tabSize: 4,
                    insertSpaces: true,
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
              : cellType === 'markdown'
                ? (editingMarkdown[index]
                    ? <Editor
                        height={`${Math.min(520, Math.max(100, lineCount * 20 + 36))}px`}
                        path={`${getEditorModelPath(projectRoot, filePath)}?markdown=${index}`}
                        language="markdown"
                        value={source}
                        onChange={nextValue => updateCellSource(index, nextValue ?? '')}
                        theme="vs-dark"
                        options={{
                          minimap: { enabled: false },
                          fontSize: 13,
                          lineNumbers: 'off',
                          scrollBeyondLastLine: false,
                          automaticLayout: true,
                          wordWrap: 'on',
                          overviewRulerLanes: 0,
                          mouseWheelZoom: false,
                          scrollbar: { vertical: 'auto', horizontal: 'auto', alwaysConsumeMouseWheel: false },
                        }}
                      />
                    : <div className="notebook-markdown-cell" onDoubleClick={() => setEditingMarkdown(prev => ({ ...prev, [index]: true }))}><NotebookMarkdown text={source} attachments={cell.attachments || {}} /></div>)
                : <pre className="notebook-raw-cell">{source}</pre>}

            {cellType === 'code' && Array.isArray(cell.outputs) && cell.outputs.length > 0 &&
              <div className="notebook-cell-outputs">
                {cell.outputs.map((output, outputIndex) => <NotebookOutput key={outputIndex} output={output} />)}
              </div>}
          </div>
        </section>
      })}
    </div>
  </div>
}
