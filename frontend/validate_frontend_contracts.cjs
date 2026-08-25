const fs = require('fs')
const path = require('path')

const appPath = path.join(__dirname, 'src', 'App.jsx')
const source = fs.readFileSync(appPath, 'utf8')

function fail(message) {
  console.error(`[frontend-contract] ${message}`)
  process.exitCode = 1
}

function namedImports(modulePath) {
  const escaped = modulePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = source.match(new RegExp(`import\\s*\\{([^}]*)\\}\\s*from\\s*['"]${escaped}['"]`))
  return new Set(
    (match?.[1] || '')
      .split(',')
      .map(value => value.trim().split(/\s+as\s+/)[0])
      .filter(Boolean)
  )
}

const importedApiNames = namedImports('./api')
for (const name of ['api', 'connectJobs', 'runtimeInfo']) {
  const used = new RegExp(`\\b${name}\\s*\\(`).test(source)
  if (used && !importedApiNames.has(name)) {
    fail(`${name}() is used by App.jsx but is not imported from ./api`)
  }
}

const componentContracts = [
  ['./components/notebook/NotebookEditor', ['NotebookEditor']],
  ['./components/viewers/DocumentViewers', ['PdfViewer', 'PresentationViewer']],
  ['./components/common/CommonUi', ['MiniBadge', 'SectionTitle', 'StatusDot', 'StudioIcon']],
  ['./components/reports/ReportComponents', ['FileChangeList', 'KeyValueGrid', 'MetricCard', 'ReportSection', 'StatusBadge', 'WorkflowMiniMap']],
  ['./components/architecture/ArchitecturePanels', ['AgentStudioArchitecturePanel', 'GeneratedAgentArchitecturePanel']],
  ['./components/llm/LlmCatalogPanel', ['LlmCatalogPanel']],
  ['./components/database/DatabaseBrowsers', ['DatabaseBrowserContextMenus', 'FirestoreBrowserPanel', 'RedisBrowserPanel', 'SqlObjectTreePanel']],
  ['./components/database/DatabaseDiagramViewer', ['DatabaseDiagramViewer']],
  ['./components/database/SqlResultsPane', ['SqlResultsPane']],
  ['./components/terminal/TerminalPanel', ['TerminalPanel']],
  ['./components/system/SystemRuntimePanels', ['OllamaSettingsPanel', 'RuntimeDatabasePanel', 'ServicePortSettingsPanel', 'SystemStatusSummary']],
]

for (const [modulePath, names] of componentContracts) {
  const importedNames = namedImports(modulePath)
  for (const name of names) {
    const used = new RegExp(`<${name}(?:\\s|/|>)`).test(source)
    if (used && !importedNames.has(name)) {
      fail(`<${name}> is used by App.jsx but is not imported from ${modulePath}`)
    }
  }
}

const editorUtilImports = namedImports('./utils/editor')
for (const name of ['isDatabaseDiagramFile']) {
  const used = new RegExp(`\\b${name}\\s*\\(`).test(source)
  if (used && !editorUtilImports.has(name)) {
    fail(`${name}() is used by App.jsx but is not imported from ./utils/editor`)
  }
}

const terminalUtilImports = namedImports('./utils/terminal')
for (const name of [
  'parseTerminalServerMessage',
  'serializeTerminalClientMessage',
  'terminalCellWidth',
  'terminalNextCharacter',
  'terminalPreviousCharacter',
]) {
  const used = new RegExp(`\\b${name}\\s*\\(`).test(source)
  if (used && !terminalUtilImports.has(name)) {
    fail(`${name}() is used by App.jsx but is not imported from ./utils/terminal`)
  }
}

if (!process.exitCode) {
  console.log('[frontend-contract] App.jsx critical API/component imports: OK')
}


for (const [label, pattern] of [
  ['editor tab Save As menu', /다른 이름으로 저장\.\.\./],
  ['native Save As picker', /window\.showSaveFilePicker\(/],
  ['Save As uses current editor buffer', /editorFileContents\[relativePath\]/],
  ['binary Save As raw endpoint', /\/files\/raw\?/],
]) {
  if (!pattern.test(source)) {
    fail(`Editor Save As contract missing: ${label}`)
  }
}

if (!process.exitCode) {
  console.log('[frontend-contract] Editor tab Save As file picker: OK')
}

const notebookEditorPath = path.join(__dirname, 'src', 'components', 'notebook', 'NotebookEditor.tsx')
const notebookEditorSource = fs.readFileSync(notebookEditorPath, 'utf8')
for (const [label, pattern] of [
  ['file-keyed notebook outer scroll cache', /NOTEBOOK_SCROLL_POSITIONS\s*=\s*new Map/],
  ['notebook outer scroll capture', /onScroll=\{event\s*=>\s*rememberOuterScroll\(event\.currentTarget\.scrollTop\)\}/],
  ['notebook scroll restore layout effect', /useLayoutEffect\s*\(\s*\(\)\s*=>[\s\S]*NOTEBOOK_SCROLL_POSITIONS\.get\(scrollKey\)/],
]) {
  if (!pattern.test(notebookEditorSource)) {
    fail(`NotebookEditor scroll contract missing: ${label}`)
  }
}

if (!process.exitCode) {
  console.log('[frontend-contract] Notebook cross-editor scroll restore: OK')
}


for (const [label, pattern] of [
  ['OpenAI usage toggle', /OpenAI 사용<\/span>/],
  ['OpenAI enabled setting save', /saveGroup\(\['OPENAI_ENABLED','OPENAI_API_KEY','OPENAI_MODEL','OPENAI_EMBEDDING_MODEL'\]\)/],
  ['AUTO Ollama-first strategy', /AI_PROVIDER_STRATEGY:'ollama_first'/],
  ['AUTO remains available without OpenAI', /className=\{aiRuntimeStatus\?\.mode==='auto'[\s\S]*disabled=\{aiModeBusy\}/],
  ['OpenAI mode disabled while unavailable', /aiRuntimeStatus\?\.providers\?\.openai\?\.enabled===false\|\|!aiRuntimeStatus\?\.providers\?\.openai\?\.configured/],
  ['Codex manual mode', /onClick=\{\(\)=>applyAiMode\('codex'\)\}/],
  ['local-only runtime notice', /외부 Provider 비사용 · LLM\/Embedding 작업은 Ollama 로컬에서 처리됩니다/],
  ['Codex settings master switch', /<CodexSettingsPanel[\s\S]*CODEX_ENABLED/],
]) {
  if (!pattern.test(source)) {
    fail(`Adaptive AI frontend contract missing: ${label}`)
  }
}

if (!process.exitCode) {
  console.log('[frontend-contract] Ollama-first / OpenAI / Codex routing controls: OK')
}

const browserUtilImports = namedImports('./utils/browser')
for (const name of ['browserTitleForUrl', 'extractLocalDevelopmentUrls', 'normalizeBrowserUrl']) {
  const used = new RegExp(`\\b${name}\\s*\\(`).test(source)
  if (used && !browserUtilImports.has(name)) {
    fail(`${name}() is used by App.jsx but is not imported from ./utils/browser`)
  }
}

const browserComponentImports = namedImports('./components/browser/WebBrowserWorkspace')
if (/<WebBrowserWorkspace(?:\s|\/|>)/.test(source) && !browserComponentImports.has('WebBrowserWorkspace')) {
  fail('<WebBrowserWorkspace> is used by App.jsx but is not imported from ./components/browser/WebBrowserWorkspace')
}

for (const [label, pattern] of [
  ['workspace browser tab beside LLM', /\['BROWSER','웹브라우저'\]/],
  ['fixed default browser tab', /DEFAULT_WEB_BROWSER_ID='web-browser-fixed'/],
  ['browser workspace render', /workspaceTab==='BROWSER'&&<WebBrowserWorkspace/],
  ['terminal local URL detector', /detectTerminalWebServices\(sessionId,incoming\)/],
  ['user-approved default browser action', /기본 웹브라우저에서 열기/],
  ['user-approved additional browser action', /추가 웹브라우저 탭/],
  ['browser detection toggle', /webUrlDetectionEnabled/],
]) {
  if (!pattern.test(source)) {
    fail(`Workspace web browser contract missing: ${label}`)
  }
}

if (/webBrowserTabs\.map\(tab=>\{/.test(source)) {
  fail('web browser tabs must not be rendered inside the CODE file-tab strip')
}

if (!process.exitCode) {
  console.log('[frontend-contract] Workspace browser + user-approved URL detection: OK')
}


const browserComponentPath = path.join(__dirname, 'src', 'components', 'browser', 'EmbeddedWebBrowser.tsx')
const browserComponentSource = fs.readFileSync(browserComponentPath, 'utf8')
const chromiumViewportPath = path.join(__dirname, 'src', 'components', 'browser', 'ChromiumRemoteViewport.tsx')
const chromiumViewportSource = fs.readFileSync(chromiumViewportPath, 'utf8')
const browserUtilsPath = path.join(__dirname, 'src', 'utils', 'browser.ts')
const browserUtilsSource = fs.readFileSync(browserUtilsPath, 'utf8')
for (const [label, pattern, target] of [
  ['internal IP direct iframe branch', /isLocalDevelopmentUrl\(normalized\)\) return normalized/, browserUtilsSource],
  ['external Chrome CDP mode indicator', /외부 사이트 · Chrome CDP 실시간/, browserComponentSource],
  ['external Chromium viewport component', /<ChromiumRemoteViewport/, browserComponentSource],
  ['Chromium navigate API', /\/web-browser\/chromium\/\$\{encodedSessionId\}\/navigate/, chromiumViewportSource],
  ['Chrome CDP screencast websocket', /\/web-browser\/cdp\/\$\{encodedSessionId\}\/stream/, chromiumViewportSource],
  ['Chromium popup forwarding', /onRemotePopup\(tab\.id, popup\)/, chromiumViewportSource],
  ['remote mouse click forwarding', /sendAction\('click'/, chromiumViewportSource],
  ['remote wheel forwarding', /sendAction\('scroll'/, chromiumViewportSource],
  ['remote keyboard text forwarding', /sendAction\('text'/, chromiumViewportSource],
  ['Chrome CDP diagnostics API', /web-browser\/chromium\/diagnostics/, chromiumViewportSource],
  ['Chrome CDP diagnostics visible log', /Chrome CDP 진단 로그/, chromiumViewportSource],
  ['Chrome CDP diagnostics copy', /진단 로그 복사/, chromiumViewportSource],
  ['startup retry only by explicit force_restart', /force_restart:\s*true/, chromiumViewportSource],
  ['startup attempt URL latch', /lastAttemptUrlRef/, chromiumViewportSource],
  ['websocket retry is bounded', /retryCount\s*<\s*2/, chromiumViewportSource],
  ['state polling only after ready', /if \(!tab\.url \|\| !ready \|\| error\) return/, chromiumViewportSource],
  ['inactive browser screencast suspend', /action:\s*'suspend'/, chromiumViewportSource],
]) {
  if (!pattern.test(target)) {
    fail(`Chromium browser contract missing: ${label}`)
  }
}
if (!process.exitCode) {
  console.log('[frontend-contract] Chrome CDP screencast + popup tabs + startup diagnostics + internal direct browser: OK')
}


for (const [label, pattern] of [
  ['editor code starts empty instead of file-selection placeholder', /const \[code,setCode\]=useState\(''\)/],
  ['file loading path state', /const \[fileLoadingPath,setFileLoadingPath\]=useState\(''\)/],
  ['open file requires cached content before fast activation', /hasCachedContent=Object\.prototype\.hasOwnProperty\.call\(editorFileContents,requestedPath\)/],
  ['save blocked while authoritative file content is loading', /저장 대기 · 파일 로딩 중/],
  ['save-as blocked while authoritative file content is loading', /다른 이름 저장 대기 · 파일 로딩 중/],
  ['loading gate renders before notebook parser', /fileLoading&&fileLoadingPath===selected[\s\S]*파일을 불러오는 중입니다\./],
]) {
  if (!pattern.test(source)) {
    fail(`Editor authoritative-load contract missing: ${label}`)
  }
}

if (!process.exitCode) {
  console.log('[frontend-contract] Editor authoritative disk load / placeholder-save guard: OK')
}

const codexComponentImports = namedImports('./components/codex/CodexPanel')
if (/<CodexPanel(?:\s|\/|>)/.test(source) && !codexComponentImports.has('CodexPanel')) {
  fail('<CodexPanel> is used by App.jsx but is not imported from ./components/codex/CodexPanel')
}
const codexPanelPath = path.join(__dirname, 'src', 'components', 'codex', 'CodexPanel.tsx')
const codexPanelSource = fs.readFileSync(codexPanelPath, 'utf8')
for (const [label, pattern, target] of [
  ['Codex right-panel tab', /codeRightPanelTab==='CODEX'/, source],
  ['Codex right-panel render', /<CodexPanel/, source],
  ['ChatGPT managed login', /\/codex\/login\/chatgpt/, codexPanelSource],
  ['Codex event websocket', /\/codex\/events/, codexPanelSource],
  ['Codex thread start', /\/codex\/thread\/start/, codexPanelSource],
  ['Codex turn stream start', /\/codex\/turn\/start/, codexPanelSource],
  ['Codex interrupt', /\/codex\/turn\/interrupt/, codexPanelSource],
  ['Codex approval flow', /\/codex\/approval/, codexPanelSource],
  ['command approval UI', /명령 실행 승인 요청/, codexPanelSource],
  ['file change approval UI', /파일 변경 승인 요청/, codexPanelSource],
  ['current model reasoning effort field', /row\.reasoningEffort\s*\|\|\s*row\.effort/, codexPanelSource],
  ['default reasoning effort support', /defaultReasoningEffort/, codexPanelSource],
  ['request user input UI', /item\/tool\/requestUserInput/, codexPanelSource],
  ['request user input answer payload', /answers\[id\]\s*=\s*\{\s*answers:\s*value\s*\?\s*\[value\]\s*:\s*\[\]\s*\}/, codexPanelSource],
  ['stable Codex status callback', /const refreshStatus = useCallback\([\s\S]*?\}, \[projectRoot\]\)/, codexPanelSource],
  ['safe Codex default-model fallback', /return preferred \? modelId\(preferred\) : current/, codexPanelSource],
]) {
  if (!pattern.test(target)) fail(`Codex panel contract missing: ${label}`)
}
if (!process.exitCode) {
  console.log('[frontend-contract] VS Code-style Codex right panel + v2 protocol UI: OK')
}

const attachmentPickerPath = path.join(__dirname, 'src', 'components', 'ai', 'AiAttachmentPicker.tsx')
const attachmentPickerSource = fs.readFileSync(attachmentPickerPath, 'utf8')
for (const [label, pattern, target] of [
  ['Agent interview attachment picker', /attachments=\{interviewAttachments\}/, source],
  ['Agent interview attachment ids', /attachment_ids:interviewAttachments\.map/, source],
  ['Workflow attachment ids', /attachment_ids:interviewAttachments\.map/, source],
  ['Code editor attachment picker', /attachments=\{codeEditAttachments\}/, source],
  ['Code editor attachment ids', /attachment_ids:codeEditAttachments\.map/, source],
  ['Codex attachment picker', /attachments=\{attachments\}/, codexPanelSource],
  ['Codex attachment ids', /attachment_ids:\s*attachments\.map/, codexPanelSource],
  ['native attachment picker API', /\/ai\/attachments\/pick/, attachmentPickerSource],
  ['attachment release API', /\/ai\/attachments\/release/, attachmentPickerSource],
  ['multi-file count UI', /참고 파일 \{attachments\.length\}개/, attachmentPickerSource],
]) {
  if (!pattern.test(target)) fail(`AI attachment frontend contract missing: ${label}`)
}
if (!process.exitCode) {
  console.log('[frontend-contract] Agent interview + LLM code edit + Codex reference-file attachments: OK')
}

for (const [label, pattern] of [
  ['authoritative workspace root ref', /const workspaceRootRef=useRef\(''\)/],
  ['workspace root resolver includes last loaded root', /const resolveWorkspaceRoot=\(\)=>String\([\s\S]*workspaceRootRef\.current/],
  ['file list stores successful root', /workspaceRootRef\.current=targetRoot[\s\S]*setFiles\(nextFiles\)/],
  ['open file resolves root before read', /const openFile=async\(relativePath\)=>\{[\s\S]*const workspaceRoot=resolveWorkspaceRoot\(\)[\s\S]*root:workspaceRoot,[\s\S]*relative_path:requestedPath/],
  ['external reload resolves root', /const reloadExternalEditorFile=async[\s\S]*const workspaceRoot=resolveWorkspaceRoot\(\)[\s\S]*root:workspaceRoot,relative_path:editorPath/],
  ['editor write resolves root', /const writeEditorFile=async[\s\S]*const workspaceRoot=resolveWorkspaceRoot\(\)/],
  ['new project clears stale workspace root', /setNewAgentProjectRoot\(''\)[\s\S]*setRoot\(''\)[\s\S]*workspaceRootRef\.current=''/],
]) {
  if (!pattern.test(source)) {
    fail(`Project-root file load contract missing: ${label}`)
  }
}

if (/root:activeWorkspaceRoot,\s*relative_path:requestedPath/.test(source)) {
  fail('openFile must not send transient activeWorkspaceRoot directly')
}

if (!process.exitCode) {
  console.log('[frontend-contract] Project root retained across file load/read/write operations: OK')
}
