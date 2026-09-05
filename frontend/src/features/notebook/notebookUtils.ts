import type { NotebookDocument, NotebookParseResult } from '../../types/notebook'

// Python 커널 Notebook 안에 교육용 raw SQL 셀이 들어 있는 경우
// Python ast.parse()로 보내지 않고 기존 DB Workspace 실행기로 라우팅합니다.
// Jupyter의 %%sql 표기도 함께 허용하며, 교재에서 Python 주석 형태로 붙인
// '# ...' 안내 줄은 SQL 주석 '-- ...'로 바꿔 DB에 전달합니다.
export function normalizeNotebookSqlCode(source: LegacyValue = ''): string {
  const lines = String(source ?? '').replace(/\r\n|\r/g, '\n').split('\n')
  let magicRemoved = false
  const normalized: string[] = []

  for (const raw of lines) {
    const trimmed = raw.trim()
    if (!magicRemoved && /^%%sql(?:\s|$)/i.test(trimmed)) {
      magicRemoved = true
      const rest = trimmed.replace(/^%%sql(?:\s+)?/i, '')
      if (rest) normalized.push(rest)
      continue
    }

    const match = raw.match(/^(\s*)#(.*)$/)
    if (match) {
      normalized.push(`${match[1] || ''}--${match[2] || ''}`)
    } else {
      normalized.push(raw)
    }
  }

  return normalized.join('\n')
}

export function looksLikeNotebookSqlCode(source: LegacyValue = ''): boolean {
  const raw = String(source ?? '')
  if (/^\s*%%sql(?:\s|$)/i.test(raw)) return true

  const normalized = normalizeNotebookSqlCode(raw)
  const lines = normalized.split('\n')
  let inBlockComment = false

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) continue
    if (inBlockComment) {
      if (line.includes('*/')) inBlockComment = false
      continue
    }
    if (line.startsWith('/*')) {
      if (!line.includes('*/')) inBlockComment = true
      continue
    }
    if (line.startsWith('--')) continue

    return /^(?:BEGIN\s*(?:;|TRANSACTION\b)|START\s+TRANSACTION\b|COMMIT\s*;|ROLLBACK\s*;|SELECT\s+|INSERT\s+INTO\s+|UPDATE\s+[\w"`\[]+\s+SET\s+|DELETE\s+FROM\s+|CREATE\s+(?:TABLE|VIEW|INDEX|SCHEMA|DATABASE|SEQUENCE|FUNCTION|PROCEDURE)\b|ALTER\s+(?:TABLE|VIEW|SCHEMA|DATABASE|SEQUENCE)\b|DROP\s+(?:TABLE|VIEW|INDEX|SCHEMA|DATABASE|SEQUENCE|FUNCTION|PROCEDURE)\b|TRUNCATE\s+(?:TABLE\s+)?|MERGE\s+INTO\s+|GRANT\s+|REVOKE\s+|EXPLAIN\s+|VACUUM(?:\s|;|$)|ANALYZE(?:\s|;|$))/i.test(line)
  }

  return false
}

export interface NotebookSqlResult {
  message?: unknown
  columns?: unknown[]
  rows?: unknown[][]
  [key: string]: unknown
}

export function formatNotebookSqlResult(result: NotebookSqlResult | null | undefined): string {
  const lines: string[] = []
  if (result?.message) lines.push(String(result.message))

  const columns = Array.isArray(result?.columns) ? result.columns : []
  const rows = Array.isArray(result?.rows) ? result.rows : []

  if (columns.length) {
    const displayRows = rows.slice(0, 50)
    lines.push(columns.map(String).join(' | '))
    lines.push(columns.map(() => '---').join(' | '))
    for (const row of displayRows) {
      lines.push((Array.isArray(row) ? row : []).map((value: LegacyValue) => value === null ? 'NULL' : String(value)).join(' | '))
    }
    if (rows.length > displayRows.length) {
      lines.push(`... Notebook 출력은 ${displayRows.length}행까지만 표시합니다. 전체 조회 ${rows.length}행`)
    }
  }

  return (lines.join('\n') || 'SQL 실행 완료') + '\n'
}

export function textToNotebookSource(text: LegacyValue = ''): string[] {
  const normalized = String(text ?? '').replace(/\r\n|\r/g, '\n')
  if (!normalized) return []
  const parts = normalized.split('\n')
  return parts
    .map((line: LegacyValue, index: LegacyValue) => index < parts.length - 1 ? `${line}\n` : line)
    .filter((line: LegacyValue, index: LegacyValue) => line !== '' || index < parts.length - 1)
}

export function parseNotebookDocument(value: LegacyValue = ''): NotebookParseResult {
  try {
    const notebook = JSON.parse(String(value || '')) as unknown
    if (!notebook || typeof notebook !== 'object' || !Array.isArray((notebook as NotebookDocument).cells)) {
      return {
        ok: false,
        error: '유효한 Jupyter Notebook 형식이 아닙니다. cells 배열을 찾을 수 없습니다.',
        notebook: null,
      }
    }
    return { ok: true, error: '', notebook: notebook as NotebookDocument }
  } catch (error) {
    return {
      ok: false,
      error: `Notebook JSON 해석 실패: ${error instanceof Error ? error.message : String(error)}`,
      notebook: null,
    }
  }
}

export function notebookKernelLanguage(notebook: NotebookDocument | null | undefined): string {
  const metadata = notebook?.metadata || {}
  const kernelspec = metadata.kernelspec || {}
  const languageInfo = metadata.language_info || {}
  return String(kernelspec.language || languageInfo.name || kernelspec.name || 'python').toLowerCase()
}
