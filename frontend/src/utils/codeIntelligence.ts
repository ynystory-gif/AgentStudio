import { api } from '../api'
import { getEditorLanguage, getEditorModelPath } from './editor'

type DefinitionTarget = {
  symbol?: string
  kind?: string
  line?: number
  column?: number
  relative_path?: string
  absolute_path?: string
  external?: boolean
  cell_index?: number | null
  content?: string
  source_line?: string
  module?: string
}

type CodeIntelligenceResult = {
  ok?: boolean
  symbol?: string
  expression?: string
  kind?: string
  active_parameter?: number
  definition?: DefinitionTarget | null
  signature?: string
  parameters?: Array<{ name?: string; annotation?: string; default?: string; documentation?: string }>
  documentation?: string
  type_hint?: string
  value_preview?: string
  module?: string
  message?: string
  prefix?: string
  completion_context?: string
  callable?: string
  completions?: Array<{
    label?: string
    kind?: string
    detail?: string
    documentation?: string
    insert_text?: string
    line?: number
    cell_index?: number | null
    parameter_name?: string
  }>
}

export type CodeIntelligenceContext = {
  root: string
  relativePath: string
  language?: string
  cellIndex?: number | null
  getNotebookContent?: () => string
  onOpenDefinition: (definition: DefinitionTarget, source?: { line: number; column: number }) => void | Promise<void>
}

type RegisteredContext = CodeIntelligenceContext & {
  editor: any
  modelUri: string
}

const MODEL_CONTEXTS = new Map<string, RegisteredContext>()
const DEFINITION_TARGETS = new Map<string, DefinitionTarget>()
const PROVIDER_MONACO = new WeakSet<object>()
const OPENER_MONACO = new WeakSet<object>()
const REQUEST_CACHE = new Map<string, Promise<CodeIntelligenceResult>>()
const MAX_CACHE_ENTRIES = 220

const PROVIDER_LANGUAGES = ['python', 'csharp', 'java', 'go', 'rust', 'php', 'ruby', 'cpp']

function trimCache(): void {
  if (REQUEST_CACHE.size <= MAX_CACHE_ENTRIES) return
  const remove = REQUEST_CACHE.size - MAX_CACHE_ENTRIES
  Array.from(REQUEST_CACHE.keys()).slice(0, remove).forEach(key => REQUEST_CACHE.delete(key))
}

function contextForModel(model: any): RegisteredContext | undefined {
  return MODEL_CONTEXTS.get(String(model?.uri?.toString?.() || ''))
}

function modelWordRange(monaco: any, model: any, position: any): any {
  const word = model?.getWordAtPosition?.(position)
  if (!word) return undefined
  return new monaco.Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn)
}

async function resolveAt(model: any, position: any, action = 'all'): Promise<CodeIntelligenceResult> {
  const context = contextForModel(model)
  if (!context) return { ok: false }
  const version = Number(model?.getVersionId?.() || 0)
  const key = [context.root, context.relativePath, context.cellIndex ?? '', String(model?.uri?.toString?.() || ''), version, position?.lineNumber || 1, position?.column || 1, action].join('|')
  const cached = REQUEST_CACHE.get(key)
  if (cached) return cached

  const request = api<CodeIntelligenceResult>('/code-intelligence/resolve', {
    method: 'POST',
    body: JSON.stringify({
      root: context.root,
      relative_path: context.relativePath,
      language: context.language || model?.getLanguageId?.() || '',
      content: String(model?.getValue?.() || ''),
      line: Number(position?.lineNumber || 1),
      column: Number(position?.column || 1),
      action,
      notebook_content: context.getNotebookContent?.() || '',
      cell_index: context.cellIndex ?? null,
    }),
  }).catch(() => ({ ok: false } as CodeIntelligenceResult))
  REQUEST_CACHE.set(key, request)
  trimCache()
  return request
}

function markdownText(value: string): string {
  return String(value || '').replace(/```/g, '\`\`\`')
}

function hoverContents(result: CodeIntelligenceResult): Array<{ value: string }> {
  const rows: Array<{ value: string }> = []
  const title = result.expression || result.symbol || ''
  if (title) rows.push({ value: `**${markdownText(result.kind || 'Symbol')}** \`${markdownText(title)}\`` })
  if (result.signature) rows.push({ value: `\`\`\`python\n${markdownText(result.signature)}\n\`\`\`` })
  if (result.type_hint) rows.push({ value: `Type: \`${markdownText(result.type_hint)}\`` })
  if (result.value_preview && !result.signature) rows.push({ value: `Value: \`${markdownText(result.value_preview)}\`` })
  if (result.documentation) rows.push({ value: markdownText(result.documentation).slice(0, 1800) })
  const definition = result.definition
  if (definition) {
    const location = definition.cell_index != null
      ? `${definition.relative_path || 'Notebook'} · Cell ${Number(definition.cell_index) + 1} · Line ${definition.line || 1}`
      : `${definition.relative_path || definition.absolute_path || definition.module || 'Definition'}:${definition.line || 1}`
    rows.push({ value: `$(link) **Ctrl+Click 정의로 이동**  \n${markdownText(location)}` })
  }
  return rows
}

function targetUri(monaco: any, context: RegisteredContext, definition: DefinitionTarget): any {
  if (definition.cell_index != null) {
    return monaco.Uri.parse(`${getEditorModelPath(context.root, definition.relative_path || context.relativePath)}?cell=${definition.cell_index}`)
  }
  if (definition.relative_path) {
    return monaco.Uri.parse(getEditorModelPath(context.root, definition.relative_path))
  }
  const externalKey = encodeURIComponent(String(definition.absolute_path || definition.module || definition.symbol || 'external'))
  return monaco.Uri.parse(`agentstudio://external-definition/${externalKey}`)
}

function ensureTargetModel(monaco: any, context: RegisteredContext, definition: DefinitionTarget): any {
  const uri = targetUri(monaco, context, definition)
  const uriKey = String(uri.toString())
  DEFINITION_TARGETS.set(uriKey, definition)
  let model = monaco.editor.getModel?.(uri)
  if (!model && definition.content) {
    const language = getEditorLanguage(definition.relative_path || definition.absolute_path || '') || context.language || 'python'
    model = monaco.editor.createModel(String(definition.content || ''), language, uri)
  }
  return { uri, model }
}

function installOpener(monaco: any): void {
  if (OPENER_MONACO.has(monaco)) return
  OPENER_MONACO.add(monaco)
  monaco.editor.registerEditorOpener?.({
    openCodeEditor: async (source: any, resource: any, selection: any) => {
      const definition = DEFINITION_TARGETS.get(String(resource?.toString?.() || ''))
      const sourceContext = contextForModel(source?.getModel?.())
      if (!definition || !sourceContext) return false
      const position = source?.getPosition?.() || { lineNumber: 1, column: 1 }
      await sourceContext.onOpenDefinition(definition, {
        line: Number(position.lineNumber || 1),
        column: Number(position.column || 1),
      })
      return true
    },
  })
}

function installProviders(monaco: any): void {
  if (PROVIDER_MONACO.has(monaco)) return
  PROVIDER_MONACO.add(monaco)
  installOpener(monaco)

  PROVIDER_LANGUAGES.forEach(language => {
    monaco.languages.registerDefinitionProvider(language, {
      provideDefinition: async (model: any, position: any) => {
        const context = contextForModel(model)
        if (!context) return null
        const result = await resolveAt(model, position, 'definition')
        if (!result?.definition) return null
        const { uri } = ensureTargetModel(monaco, context, result.definition)
        const line = Math.max(1, Number(result.definition.line || 1))
        const column = Math.max(1, Number(result.definition.column || 1))
        return {
          uri,
          range: new monaco.Range(line, column, line, column + Math.max(1, String(result.definition.symbol || result.symbol || '').length)),
        }
      },
    })

    monaco.languages.registerHoverProvider(language, {
      provideHover: async (model: any, position: any) => {
        if (!contextForModel(model)) return null
        const result = await resolveAt(model, position, 'hover')
        if (!result?.ok || (!result.definition && !result.signature && !result.documentation && !result.value_preview)) return null
        return {
          range: modelWordRange(monaco, model, position),
          contents: hoverContents(result),
        }
      },
    })

    monaco.languages.registerCompletionItemProvider(language, {
      triggerCharacters: ['.'],
      provideCompletionItems: async (model: any, position: any) => {
        if (!contextForModel(model)) return { suggestions: [] }
        const result = await resolveAt(model, position, 'completion')
        const completions = Array.isArray(result?.completions) ? result.completions : []
        const prefix = String(result?.prefix || '')
        const startColumn = Math.max(1, Number(position?.column || 1) - prefix.length)
        const kindMap: Record<string, number> = {
          variable: monaco.languages.CompletionItemKind.Variable,
          parameter: monaco.languages.CompletionItemKind.Variable,
          function: monaco.languages.CompletionItemKind.Function,
          class: monaco.languages.CompletionItemKind.Class,
          module: monaco.languages.CompletionItemKind.Module,
          builtin: monaco.languages.CompletionItemKind.Function,
          keyword: monaco.languages.CompletionItemKind.Property,
        }
        return {
          suggestions: completions.map((item: any, index: number) => ({
            label: String(item?.label || ''),
            kind: kindMap[String(item?.kind || '')] ?? monaco.languages.CompletionItemKind.Text,
            detail: String(item?.detail || item?.kind || ''),
            documentation: item?.documentation ? String(item.documentation) : undefined,
            insertText: String(item?.insert_text || item?.label || ''),
            sortText: String(index).padStart(4, '0'),
            range: {
              startLineNumber: Number(position?.lineNumber || 1),
              startColumn,
              endLineNumber: Number(position?.lineNumber || 1),
              endColumn: Number(position?.column || 1),
            },
          })),
        }
      },
    })
  })

  monaco.languages.registerSignatureHelpProvider('python', {
    signatureHelpTriggerCharacters: ['(', ','],
    signatureHelpRetriggerCharacters: [','],
    provideSignatureHelp: async (model: any, position: any) => {
      if (!contextForModel(model)) return null
      const result = await resolveAt(model, position, 'signature')
      if (!result?.signature) return null
      const params = Array.isArray(result.parameters) ? result.parameters : []
      return {
        value: {
          signatures: [{
            label: result.signature,
            documentation: result.documentation || undefined,
            parameters: params.map(parameter => ({
              label: parameter.name || '',
              documentation: parameter.documentation || [parameter.annotation, parameter.default ? `default=${parameter.default}` : ''].filter(Boolean).join(' · ') || undefined,
            })),
          }],
          activeSignature: 0,
          activeParameter: Math.max(0, Math.min(Math.max(0, params.length - 1), Number(result.active_parameter || 0))),
        },
        dispose: () => undefined,
      }
    },
  })
}

export function registerCodeIntelligence(monaco: any, editor: any, context: CodeIntelligenceContext): { dispose: () => void } {
  if (!monaco || !editor?.getModel) return { dispose: () => undefined }
  installProviders(monaco)
  const model = editor.getModel()
  const uriKey = String(model?.uri?.toString?.() || '')
  if (!uriKey) return { dispose: () => undefined }
  MODEL_CONTEXTS.set(uriKey, { ...context, editor, modelUri: uriKey })

  // v5.472: Ctrl+Space is completion-only. It must never be reused for
  // definition navigation. The completion provider ranks callable keyword
  // arguments first when the caret is inside a call, then code-defined symbols
  // from the current/previous Notebook cells or file, followed by imports and
  // builtins. The suggestion widget opens at the current caret and inserts the
  // selected candidate in place.
  let completionGuardUntil = 0
  const keyDisposable = editor.onKeyDown?.((event: any) => {
    const browserEvent = event?.browserEvent
    const ctrlOrMeta = Boolean(event?.ctrlKey || browserEvent?.ctrlKey || event?.metaKey || browserEvent?.metaKey)
    const isSpace = event?.keyCode === monaco.KeyCode.Space || browserEvent?.code === 'Space' || browserEvent?.key === ' '
    if (!ctrlOrMeta || !isSpace) return
    completionGuardUntil = Date.now() + 2500
    event?.preventDefault?.()
    event?.stopPropagation?.()
    browserEvent?.preventDefault?.()
    browserEvent?.stopPropagation?.()
    editor.focus?.()
    Promise.resolve().then(() => {
      editor.trigger?.('theanova-code-intelligence', 'editor.action.triggerSuggest', {})
    })
  })

  // Ctrl+Click remains the only mouse gesture for definition navigation. Ignore
  // clicks while the Ctrl+Space completion interaction is active and ignore
  // Monaco content widgets (including the suggestion menu), so choosing a
  // completion while Ctrl is still physically held cannot jump to a definition.
  const mouseDisposable = editor.onMouseDown?.(async (event: any) => {
    const browserEvent = event?.event?.browserEvent
    const ctrlKey = Boolean(event?.event?.ctrlKey || browserEvent?.ctrlKey)
    const leftButton = event?.event?.leftButton !== false
    const position = event?.target?.position
    const targetType = event?.target?.type
    const contentTextType = monaco?.editor?.MouseTargetType?.CONTENT_TEXT
    const targetElement = event?.target?.element || browserEvent?.target
    const insideSuggestionWidget = Boolean(targetElement?.closest?.('.suggest-widget, .monaco-list, .monaco-editor-hover'))
    if (Date.now() < completionGuardUntil) return
    if (insideSuggestionWidget) return
    if (contentTextType != null && targetType !== contentTextType) return
    if (!ctrlKey || !leftButton || !position) return
    const result = await resolveAt(editor.getModel?.(), position, 'definition')
    if (!result?.definition) return
    event?.event?.preventDefault?.()
    event?.event?.stopPropagation?.()
    await context.onOpenDefinition(result.definition, {
      line: Number(position.lineNumber || 1),
      column: Number(position.column || 1),
    })
  })

  const modelDisposable = editor.onDidChangeModel?.(() => {
    MODEL_CONTEXTS.delete(uriKey)
    const nextKey = String(editor.getModel?.()?.uri?.toString?.() || '')
    if (nextKey) MODEL_CONTEXTS.set(nextKey, { ...context, editor, modelUri: nextKey })
  })

  return {
    dispose: () => {
      const current = MODEL_CONTEXTS.get(uriKey)
      if (current?.editor === editor) MODEL_CONTEXTS.delete(uriKey)
      keyDisposable?.dispose?.()
      mouseDisposable?.dispose?.()
      modelDisposable?.dispose?.()
    },
  }
}
