import { useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from 'react'
import type { SqlExecutionMessage, SqlExecutionResult, SqlExecutionResultSet, SqlResultCell } from '../../types/database'

type SqlResultTab = 'DATA' | 'MESSAGES'

export interface SqlResultsPaneProps {
  result: SqlExecutionResult | null
  resultTab: SqlResultTab
  onResultTabChange: (tab: SqlResultTab) => void
  messages: SqlExecutionMessage[]
  queryBusy?: boolean
  activeResultSetIndex: number
  onActiveResultSetIndexChange: (index: number) => void
}

const PANE_WIDTH_STORAGE_KEY = 'agentstudio.sql.resultsPaneWidth'
const DEFAULT_RESULT_PANE_MIN = 360
const DEFAULT_CHAT_PANE_MIN = 300
const DEFAULT_COLUMN_WIDTH = 150
const MIN_COLUMN_WIDTH = 72
const MAX_COLUMN_WIDTH = 720

function safeText(value: SqlResultCell): string {
  if (value === null) return 'NULL'
  if (value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function normalizedResultSets(result: SqlExecutionResult | null): SqlExecutionResultSet[] {
  const provided = Array.isArray(result?.result_sets) ? result.result_sets : []
  if (provided.length) return provided
  if (Array.isArray(result?.columns) && result.columns.length) {
    return [{
      result_index: 1,
      statement_index: 1,
      sql: '',
      columns: result.columns,
      rows: Array.isArray(result.rows) ? result.rows : [],
      row_count: Number(result.row_count || result.rows?.length || 0),
      truncated: Boolean(result.truncated),
    }]
  }
  return []
}

export function SqlResultsPane({
  result,
  resultTab,
  onResultTabChange,
  messages,
  queryBusy = false,
  activeResultSetIndex,
  onActiveResultSetIndexChange,
}: SqlResultsPaneProps) {
  const paneRef = useRef<HTMLElement | null>(null)
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({})
  const resultSets = useMemo(() => normalizedResultSets(result), [result])
  const boundedIndex = resultSets.length
    ? Math.max(0, Math.min(activeResultSetIndex, resultSets.length - 1))
    : 0
  const activeResult = resultSets[boundedIndex] ?? null

  useEffect(() => {
    if (!resultSets.length) {
      if (activeResultSetIndex !== 0) onActiveResultSetIndexChange(0)
      return
    }
    if (boundedIndex !== activeResultSetIndex) onActiveResultSetIndexChange(boundedIndex)
  }, [activeResultSetIndex, boundedIndex, onActiveResultSetIndexChange, resultSets.length])

  useEffect(() => {
    const pane = paneRef.current
    const parent = pane?.parentElement
    if (!parent) return
    try {
      const saved = Number(localStorage.getItem(PANE_WIDTH_STORAGE_KEY))
      if (Number.isFinite(saved) && saved >= DEFAULT_RESULT_PANE_MIN) {
        const parentWidth = parent.getBoundingClientRect().width
        const maxWidth = Math.max(DEFAULT_RESULT_PANE_MIN, parentWidth - DEFAULT_CHAT_PANE_MIN)
        parent.style.setProperty('--sql-results-user-width', `${Math.min(saved, maxWidth)}px`)
      }
    } catch {
      // Local storage is optional; the CSS default remains usable.
    }
  }, [])

  const beginPaneResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    const pane = paneRef.current
    const parent = pane?.parentElement
    if (!pane || !parent) return

    const parentRect = parent.getBoundingClientRect()
    const previousCursor = document.body.style.cursor
    const previousSelect = document.body.style.userSelect
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const onMove = (moveEvent: PointerEvent) => {
      const desired = parentRect.right - moveEvent.clientX
      const maxWidth = Math.max(DEFAULT_RESULT_PANE_MIN, parentRect.width - DEFAULT_CHAT_PANE_MIN)
      const next = Math.max(DEFAULT_RESULT_PANE_MIN, Math.min(maxWidth, desired))
      parent.style.setProperty('--sql-results-user-width', `${next}px`)
      try { localStorage.setItem(PANE_WIDTH_STORAGE_KEY, String(Math.round(next))) } catch { /* optional */ }
      try { window.dispatchEvent(new Event('resize')) } catch { /* optional */ }
    }

    const cleanup = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', cleanup)
      window.removeEventListener('pointercancel', cleanup)
      document.body.style.cursor = previousCursor
      document.body.style.userSelect = previousSelect
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', cleanup)
    window.addEventListener('pointercancel', cleanup)
  }

  const beginColumnResize = (event: ReactPointerEvent<HTMLSpanElement>, columnIndex: number) => {
    event.preventDefault()
    event.stopPropagation()
    const header = event.currentTarget.closest('th')
    if (!(header instanceof HTMLElement) || !activeResult) return
    const key = `${activeResult.result_index}:${columnIndex}`
    const startX = event.clientX
    const startWidth = header.getBoundingClientRect().width || DEFAULT_COLUMN_WIDTH
    const previousCursor = document.body.style.cursor
    const previousSelect = document.body.style.userSelect
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const onMove = (moveEvent: PointerEvent) => {
      const next = Math.max(MIN_COLUMN_WIDTH, Math.min(MAX_COLUMN_WIDTH, startWidth + moveEvent.clientX - startX))
      setColumnWidths(previous => ({ ...previous, [key]: next }))
    }

    const cleanup = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', cleanup)
      window.removeEventListener('pointercancel', cleanup)
      document.body.style.cursor = previousCursor
      document.body.style.userSelect = previousSelect
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', cleanup)
    window.addEventListener('pointercancel', cleanup)
  }

  const columnStyle = (columnIndex: number): CSSProperties | undefined => {
    if (!activeResult) return undefined
    const width = columnWidths[`${activeResult.result_index}:${columnIndex}`]
    if (!width) return undefined
    return { width, minWidth: width, maxWidth: width }
  }

  return <section ref={paneRef} className="sql-results-pane">
    <div
      className="sql-results-pane-resizer"
      role="separator"
      aria-orientation="vertical"
      aria-label="SQL 결과 영역 너비 조절"
      title="좌우로 드래그하여 Data Output 영역 너비 조절"
      onPointerDown={beginPaneResize}
    ><span /></div>

    <div className="sql-results-tabs">
      <button type="button" className={resultTab === 'DATA' ? 'active' : ''} onClick={() => onResultTabChange('DATA')}>
        Data Output{resultSets.length > 1 ? ` (${resultSets.length} results)` : activeResult?.columns?.length ? ` (${activeResult.row_count || 0})` : ''}
      </button>
      <button type="button" className={resultTab === 'MESSAGES' ? 'active' : ''} onClick={() => onResultTabChange('MESSAGES')}>
        Messages{messages.length ? ` (${messages.length})` : ''}
      </button>
      <div className="sql-result-summary">
        {queryBusy ? 'SQL 실행 중...' : result?.message || 'SQL을 실행하면 결과가 여기에 표시됩니다.'}
      </div>
    </div>

    <div className="sql-results-body">
      {resultTab === 'DATA'
        ? (activeResult?.columns?.length
            ? <div className={`sql-data-output ${resultSets.length > 1 ? 'multi' : 'single'}`}>
                {resultSets.length > 1 && <div className="sql-result-set-tabs" role="tablist" aria-label="SELECT 실행 결과 목록">
                  {resultSets.map((item, index) => <button
                    type="button"
                    role="tab"
                    aria-selected={index === boundedIndex}
                    className={index === boundedIndex ? 'active' : ''}
                    key={`${item.result_index}-${item.statement_index}`}
                    title={item.sql || `SQL #${item.statement_index}`}
                    onClick={() => onActiveResultSetIndexChange(index)}
                  >
                    <strong>Result {item.result_index}</strong>
                    <span>SQL #{item.statement_index} · {item.row_count.toLocaleString()} rows{item.truncated ? '+' : ''}</span>
                  </button>)}
                </div>}
                <div className="sql-data-table-wrap">
                  <table className="sql-data-table">
                    <thead><tr>
                      <th className="row-index">#</th>
                      {activeResult.columns.map((column, index) => <th key={`${column}-${index}`} style={columnStyle(index)}>
                        <span className="sql-column-title">{column}</span>
                        <span
                          className="sql-column-resize-handle"
                          role="separator"
                          aria-orientation="vertical"
                          aria-label={`${column} 컬럼 너비 조절`}
                          title="좌우로 드래그하여 컬럼 너비 조절"
                          onPointerDown={(event: ReactPointerEvent<HTMLSpanElement>) => beginColumnResize(event, index)}
                        />
                      </th>)}
                    </tr></thead>
                    <tbody>{activeResult.rows.map((row, rowIndex) => <tr key={rowIndex}>
                      <td className="row-index">{rowIndex + 1}</td>
                      {activeResult.columns.map((_, cellIndex) => {
                        const cell = row[cellIndex]
                        const text = safeText(cell)
                        return <td key={cellIndex} style={columnStyle(cellIndex)} title={cell === null ? 'NULL' : text}>
                          {cell === null ? <span className="sql-null">NULL</span> : text}
                        </td>
                      })}
                    </tr>)}</tbody>
                  </table>
                </div>
              </div>
            : <div className="sql-result-empty">조회 결과가 없습니다. SELECT 문을 실행하면 표 형태로 표시됩니다.</div>)
        : <div className="sql-message-list">
            {messages.length
              ? messages.map((item, index) => <div className={`sql-message ${item.type || 'info'}`} key={`${item.time}-${index}`}><span>{item.time}</span><p>{item.text}</p></div>)
              : <div className="sql-result-empty">실행 메시지가 없습니다.</div>}
          </div>}
    </div>
  </section>
}
