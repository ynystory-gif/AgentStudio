const editorLanguageByExtension: Record<string, string> = {
  ts: 'typescript',
  tsx: 'typescript',
  mts: 'typescript',
  cts: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  py: 'python',
  pyw: 'python',
  json: 'json',
  jsonc: 'json',
  ipynb: 'json',
  md: 'markdown',
  markdown: 'markdown',
  html: 'html',
  htm: 'html',
  css: 'css',
  scss: 'scss',
  less: 'less',
  sql: 'sql',
  yaml: 'yaml',
  yml: 'yaml',
  xml: 'xml',
  svg: 'xml',
  sh: 'shell',
  bash: 'shell',
  zsh: 'shell',
  ps1: 'powershell',
  psm1: 'powershell',
  psd1: 'powershell',
  bat: 'bat',
  cmd: 'bat',
  cs: 'csharp',
  java: 'java',
  c: 'cpp',
  h: 'cpp',
  cc: 'cpp',
  cpp: 'cpp',
  cxx: 'cpp',
  hpp: 'cpp',
  go: 'go',
  rs: 'rust',
  php: 'php',
  rb: 'ruby',
  ini: 'ini',
  toml: 'ini',
  txt: 'plaintext',
  log: 'plaintext',
  prisma: 'plaintext',
}

export function getEditorLanguage(filePath = ''): string {
  const normalized = String(filePath || '').replace(/\\/g, '/').toLowerCase()
  const fileName = normalized.split('/').pop() || ''

  if (fileName === 'dockerfile' || fileName.startsWith('dockerfile.')) return 'dockerfile'
  if (fileName === '.env' || fileName.startsWith('.env.')) return 'ini'
  if (fileName === '.gitignore' || fileName === '.dockerignore' || fileName === '.npmignore') return 'plaintext'
  if (fileName === 'makefile') return 'plaintext'

  const dot = fileName.lastIndexOf('.')
  const ext = dot >= 0 ? fileName.slice(dot + 1) : ''
  return editorLanguageByExtension[ext] || 'plaintext'
}

export function getEditorModelPath(projectRoot = '', filePath = ''): string {
  const rootKey = encodeURIComponent(String(projectRoot || 'workspace').replace(/\\/g, '/'))
  const relative = String(filePath || 'untitled').replace(/\\/g, '/').replace(/^\/+/, '')
  return `agentstudio://model/${rootKey}/${encodeURIComponent(relative)}`
}

export const isNotebookFile = (filePath = ''): boolean => String(filePath || '').toLowerCase().endsWith('.ipynb')
export const isPdfFile = (filePath = ''): boolean => String(filePath || '').toLowerCase().endsWith('.pdf')
export const isDatabaseDiagramFile = (filePath = ''): boolean => String(filePath || '').toLowerCase().endsWith('.agentdiag.json')

export function isPresentationFile(filePath = ''): boolean {
  const value = String(filePath || '').toLowerCase()
  return value.endsWith('.ppt') || value.endsWith('.pptx')
}

export function isImageFile(filePath = ''): boolean {
  const ext = String(filePath || '').trim().toLowerCase().split('.').pop() || ''
  return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'ico', 'avif'].includes(ext)
}

export const isBinaryPreviewFile = (filePath = ''): boolean =>
  isPdfFile(filePath) || isPresentationFile(filePath) || isImageFile(filePath)


// v5.462: Code editors use one shared VS Code-style pair typing policy.
// Monaco handles opening pairs, closing-character overtype/skip and paired Backspace
// deletion. Selected text is intentionally NOT auto-surrounded: when a selection
// exists, the user's typed opening character replaces that selection exactly.
// The explicit escaped-double-quote guard
// below preserves the outer auto-generated quote when the user types \" inside
// a quoted string, so the caret remains inside the string.
export const CODE_EDITOR_PAIR_TYPING_OPTIONS = {
  autoClosingBrackets: 'always',
  autoClosingQuotes: 'always',
  autoClosingDelete: 'always',
  autoClosingOvertype: 'always',
  autoSurround: 'never',
} as const

type PairTypingSelectionLike = {
  startLineNumber?: number
  startColumn?: number
  endLineNumber?: number
  endColumn?: number
  isEmpty?: () => boolean
}

type PairTypingModelLike = {
  getLineContent?: (lineNumber: number) => string
}

type PairTypingKeyboardEventLike = {
  browserEvent?: { key?: string; isComposing?: boolean; ctrlKey?: boolean; altKey?: boolean; metaKey?: boolean } | null
  preventDefault?: () => void
  stopPropagation?: () => void
}

type PairTypingEditorLike = {
  getSelection?: () => PairTypingSelectionLike | null
  getPosition?: () => { lineNumber?: number; column?: number } | null
  getModel?: () => PairTypingModelLike | null
  executeEdits?: (
    source: string,
    edits: Array<{
      range: {
        startLineNumber: number
        startColumn: number
        endLineNumber: number
        endColumn: number
      }
      text: string
      forceMoveMarkers?: boolean
    }>,
  ) => boolean
  setPosition?: (position: { lineNumber: number; column: number }) => void
  onKeyDown?: (listener: (event: PairTypingKeyboardEventLike) => void) => { dispose?: () => void }
}

function pairTypingSelectionIsEmpty(selection: PairTypingSelectionLike | null | undefined): boolean {
  if (!selection) return false
  if (typeof selection.isEmpty === 'function') return selection.isEmpty()
  return Number(selection.startLineNumber || 0) === Number(selection.endLineNumber || 0)
    && Number(selection.startColumn || 0) === Number(selection.endColumn || 0)
}

/**
 * Protects the outer auto-generated double quote while typing an escaped quote.
 *
 * Example (| = caret):
 *   "\\|" + "  ->  "\\"|"
 *
 * An odd number of consecutive backslashes means the typed quote is escaped and
 * must be inserted literally. An even number means the quote can behave as the
 * normal closing quote, allowing Monaco's autoClosingOvertype to skip it once.
 */
export function registerEscapedDoubleQuotePairGuard(editor: PairTypingEditorLike | null | undefined) {
  if (!editor?.onKeyDown) return { dispose: () => undefined }
  return editor.onKeyDown(event => {
    const browserEvent = event?.browserEvent
    if (browserEvent?.isComposing) return

    const key = String(browserEvent?.key || '')
    const selection = editor.getSelection?.()

    // v5.469: normal editor replacement semantics take priority over pair typing.
    // If text is selected, typing an opening pair character replaces the selected
    // text with exactly that character. Do not create (), {}, [], "" and do not
    // wrap the previous selection. Example: selected `abc` + `(` => `(`.
    if (selection && !pairTypingSelectionIsEmpty(selection) && ['(', '{', '[', '"'].includes(key)) {
      if (browserEvent?.ctrlKey || browserEvent?.altKey || browserEvent?.metaKey || !editor.executeEdits) return
      const startLineNumber = Number(selection.startLineNumber || 0)
      const startColumn = Number(selection.startColumn || 0)
      const endLineNumber = Number(selection.endLineNumber || 0)
      const endColumn = Number(selection.endColumn || 0)
      if (!startLineNumber || !startColumn || !endLineNumber || !endColumn) return

      event.preventDefault?.()
      event.stopPropagation?.()
      editor.executeEdits('theanova.selection-exact-character-replace', [{
        range: { startLineNumber, startColumn, endLineNumber, endColumn },
        text: key,
        forceMoveMarkers: true,
      }])
      editor.setPosition?.({ lineNumber: startLineNumber, column: startColumn + key.length })
      return
    }

    if (key !== '"') return
    if (!pairTypingSelectionIsEmpty(selection)) return

    const position = editor.getPosition?.()
    const model = editor.getModel?.()
    const lineNumber = Number(position?.lineNumber || 0)
    const column = Number(position?.column || 0)
    if (!lineNumber || !column || !model?.getLineContent || !editor.executeEdits) return

    const lineContent = String(model.getLineContent(lineNumber) || '')
    const offset = Math.max(0, column - 1)

    // Only intervene when Monaco is about to overtype the existing outer quote.
    if (lineContent[offset] !== '"') return

    let slashCount = 0
    for (let cursor = offset - 1; cursor >= 0 && lineContent[cursor] === '\\'; cursor -= 1) {
      slashCount += 1
    }

    // Odd backslash count => the new quote is escaped and must stay inside.
    if (slashCount % 2 !== 1) return

    event.preventDefault?.()
    event.stopPropagation?.()

    editor.executeEdits('theanova.escaped-double-quote-pair-guard', [{
      range: {
        startLineNumber: lineNumber,
        startColumn: column,
        endLineNumber: lineNumber,
        endColumn: column,
      },
      text: '"',
      forceMoveMarkers: true,
    }])
    // The original auto-generated quote moved one column to the right. Keep the
    // caret immediately before it, i.e. still inside the quoted string.
    editor.setPosition?.({ lineNumber, column: column + 1 })
  })
}
