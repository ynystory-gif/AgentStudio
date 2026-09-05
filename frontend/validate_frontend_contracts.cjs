const fs = require('fs')
const path = require('path')

const appPath = path.join(__dirname, 'src', 'app', 'App.tsx')
const source = fs.readFileSync(appPath, 'utf8')

// v5.506: an in-place upgrade can leave the v5.503 offline-only shim on disk.
// Never allow that declaration into a real package-backed React/xterm build.
const obsoleteTypeShimNames = ['__temp_typecheck_shim__.d.ts']
for (const fileName of obsoleteTypeShimNames) {
  const stalePath = path.join(__dirname, 'src', fileName)
  if (fs.existsSync(stalePath)) {
    console.error(`[frontend-contract] obsolete TypeScript shim detected: ${stalePath}`)
    console.error('[frontend-contract] Delete the stale file or start through SYSTEM_ADMIN.ps1, which removes it automatically.')
    process.exitCode = 1
  }
}

function fail(message) {
  console.error(`[frontend-contract] ${message}`)
  process.exitCode = 1
}


// App structure contract: keep the application shell under src/app and move features incrementally.
const legacyRootAppPath = path.join(__dirname, 'src', 'App.tsx')
const workflowFeaturePath = path.join(__dirname, 'src', 'features', 'workflow', 'WorkflowDiagrams.tsx')
const editorFeaturePath = path.join(__dirname, 'src', 'features', 'editor', 'editorNavigation.ts')
const mainPath = path.join(__dirname, 'src', 'main.tsx')
const mainSource = fs.readFileSync(mainPath, 'utf8')
if (fs.existsSync(legacyRootAppPath)) fail('legacy src/App.tsx must not be restored; use src/app/App.tsx')
if (!fs.existsSync(workflowFeaturePath)) fail('workflow feature module missing: src/features/workflow/WorkflowDiagrams.tsx')
if (!fs.existsSync(editorFeaturePath)) fail('editor feature module missing: src/features/editor/editorNavigation.ts')
if (!/import App from ['"]\.\/app\/App['"]/.test(mainSource)) fail('main.tsx must import App from ./app/App')
for (const name of ['FactoryWorkflowDiagram', 'DevelopmentStageWorkflowDiagram', 'TargetWorkflowDiagram']) {
  if (source.includes(`function ${name}(`) || source.includes(`export function ${name}(`)) fail(`${name} must remain outside app/App.tsx`)
}
if (!/from ['"]\.\.\/features\/workflow\/WorkflowDiagrams['"]/.test(source)) {
  fail('app/App.tsx must consume workflow diagrams through features/workflow')
}
for (const name of ['normalizeTextEditorLineBookmarks', 'loadTextEditorLineBookmarks', 'storeTextEditorLineBookmarks', 'loadTextEditorBreakpoints', 'storeTextEditorBreakpoints', 'isSourceDebugFile', 'sourceDebugSupportsStep', 'isBookmarkableTextEditorFile']) {
  if (source.includes(`const ${name}=`) || source.includes(`function ${name}(`)) fail(`${name} must remain outside app/App.tsx`)
}
if (!/from ['"]\.\.\/features\/editor['"]/.test(source)) {
  fail('app/App.tsx must consume editor navigation helpers through features/editor')
}
if (!process.exitCode) console.log('[frontend-contract] Incremental App/feature structure: OK')
const bundledFeaturePaths = [
  ['editor CSV viewer', path.join(__dirname, 'src', 'features', 'editor', 'components', 'CsvSpreadsheetViewer.tsx')],
  ['editor document viewers', path.join(__dirname, 'src', 'features', 'editor', 'components', 'DocumentViewers.tsx')],
  ['project search input', path.join(__dirname, 'src', 'features', 'project', 'components', 'DebouncedProjectSearchInput.tsx')],
  ['project memo panel', path.join(__dirname, 'src', 'features', 'project', 'components', 'ProjectMemoPanel.tsx')],
  ['notebook editor', path.join(__dirname, 'src', 'features', 'notebook', 'components', 'NotebookEditor.tsx')],
  ['notebook renderers', path.join(__dirname, 'src', 'features', 'notebook', 'components', 'NotebookRenderers.tsx')],
  ['notebook utils', path.join(__dirname, 'src', 'features', 'notebook', 'notebookUtils.ts')],
]
for (const [label, featurePath] of bundledFeaturePaths) {
  if (!fs.existsSync(featurePath)) fail(`incremental feature separation missing: ${label}`)
}
const retiredFeaturePaths = [
  path.join(__dirname, 'src', 'components', 'notebook'),
  path.join(__dirname, 'src', 'components', 'memo', 'ProjectMemoPanel.tsx'),
  path.join(__dirname, 'src', 'components', 'viewers', 'DocumentViewers.tsx'),
  path.join(__dirname, 'src', 'utils', 'notebook.ts'),
]
for (const retiredPath of retiredFeaturePaths) {
  if (fs.existsSync(retiredPath)) fail(`retired pre-feature path must not return: ${retiredPath}`)
}
if (source.includes('function CsvSpreadsheetViewer(')) fail('CsvSpreadsheetViewer must remain outside app/App.tsx')
if (source.includes('const DebouncedProjectSearchInput=')) fail('DebouncedProjectSearchInput must remain outside app/App.tsx')
if (!process.exitCode) console.log('[frontend-contract] Editor + Project + Notebook separation: OK')


const secondBundleFeaturePaths = [
  ['database setup', path.join(__dirname, 'src', 'features', 'database', 'AgentDatabaseSetup.tsx')],
  ['database browsers', path.join(__dirname, 'src', 'features', 'database', 'components', 'DatabaseBrowsers.tsx')],
  ['database ERD', path.join(__dirname, 'src', 'features', 'database', 'components', 'DatabaseErdPanel.tsx')],
  ['codex panel', path.join(__dirname, 'src', 'features', 'codex', 'components', 'CodexPanel.tsx')],
  ['codex settings', path.join(__dirname, 'src', 'features', 'codex', 'components', 'CodexSettingsPanel.tsx')],
  ['media workflow editor', path.join(__dirname, 'src', 'features', 'workflow', 'components', 'MediaWorkflowEditor.tsx')],
]
for (const [label, featurePath] of secondBundleFeaturePaths) if (!fs.existsSync(featurePath)) fail(`second feature separation missing: ${label}`)
for (const retiredPath of [path.join(__dirname,'src','components','database'),path.join(__dirname,'src','components','codex'),path.join(__dirname,'src','components','media','MediaWorkflowEditor.tsx')]) if (fs.existsSync(retiredPath)) fail(`retired pre-feature path must not return: ${retiredPath}`)
if (source.includes('function AgentDatabaseSetupPanel(')) fail('AgentDatabaseSetupPanel must remain outside app/App.tsx')
if (!process.exitCode) console.log('[frontend-contract] Database + Workflow + Codex separation: OK')

function namedImports(modulePath) {
  const candidatePaths = modulePath.startsWith('./')
    ? [modulePath, `../${modulePath.slice(2)}`]
    : [modulePath]
  const importLine = source.split(/\r?\n/).find(line =>
    line.trimStart().startsWith('import ') && candidatePaths.some(candidatePath =>
      line.includes(`from '${candidatePath}'`) || line.includes(`from "${candidatePath}"`)
    )
  ) || ''
  const braceStart = importLine.indexOf('{')
  const braceEnd = importLine.indexOf('}', braceStart + 1)
  const body = braceStart >= 0 && braceEnd > braceStart ? importLine.slice(braceStart + 1, braceEnd) : ''
  return new Set(
    body
      .split(',')
      .map(value => value.trim().split(/\s+as\s+/)[0])
      .filter(Boolean)
  )
}

const importedApiNames = namedImports('./api')
for (const name of ['api', 'connectJobs', 'runtimeInfo']) {
  const used = new RegExp(`\\b${name}\\s*\\(`).test(source)
  if (used && !importedApiNames.has(name)) {
    fail(`${name}() is used by App.tsx but is not imported from ./api`)
  }
}

const componentContracts = [
  ['./features/notebook/components/NotebookEditor', ['NotebookEditor']],
  ['./features/editor/components/DocumentViewers', ['PdfViewer', 'PresentationViewer']],
  ['./components/common/CommonUi', ['MiniBadge', 'SectionTitle', 'StatusDot', 'StudioIcon']],
  ['./components/reports/ReportComponents', ['FileChangeList', 'KeyValueGrid', 'MetricCard', 'ReportSection', 'StatusBadge', 'WorkflowMiniMap']],
  ['./components/architecture/ArchitecturePanels', ['AgentStudioArchitecturePanel', 'GeneratedAgentArchitecturePanel']],
  ['./components/llm/LlmCatalogPanel', ['LlmCatalogPanel']],
  ['./features/database/components/DatabaseBrowsers', ['DatabaseBrowserContextMenus', 'FirestoreBrowserPanel', 'RedisBrowserPanel', 'SqlObjectTreePanel']],
  ['./features/database/components/DatabaseDiagramViewer', ['DatabaseDiagramViewer']],
  ['./features/database/components/SqlResultsPane', ['SqlResultsPane']],
  ['./components/terminal/TerminalPanel', ['TerminalPanel']],
  ['./components/system/SystemRuntimePanels', ['OllamaSettingsPanel', 'RuntimeDatabasePanel', 'ServicePortSettingsPanel', 'SystemStatusSummary']],
]

for (const [modulePath, names] of componentContracts) {
  const importedNames = namedImports(modulePath)
  for (const name of names) {
    const used = new RegExp(`<${name}(?:\\s|/|>)`).test(source)
    if (used && !importedNames.has(name)) {
      fail(`<${name}> is used by App.tsx but is not imported from ${modulePath}`)
    }
  }
}

const editorUtilImports = namedImports('./utils/editor')
for (const name of ['isDatabaseDiagramFile']) {
  const used = new RegExp(`\\b${name}\\s*\\(`).test(source)
  if (used && !editorUtilImports.has(name)) {
    fail(`${name}() is used by App.tsx but is not imported from ./utils/editor`)
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
    fail(`${name}() is used by App.tsx but is not imported from ./utils/terminal`)
  }
}

if (!process.exitCode) {
  console.log('[frontend-contract] App.tsx critical API/component imports: OK')
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

const notebookEditorPath = path.join(__dirname, 'src', 'features', 'notebook', 'components', 'NotebookEditor.tsx')
const notebookEditorSource = fs.readFileSync(notebookEditorPath, 'utf8')
for (const [label, pattern] of [
  ['file-keyed notebook outer scroll cache', /NOTEBOOK_SCROLL_POSITIONS\s*=\s*new Map/],
  ['notebook outer scroll capture', /onScroll=\{\(event(?::\s*[^)]+)?\)\s*=>\s*rememberOuterScroll\(event\.currentTarget\.scrollTop\)\}/],
  ['notebook scroll restore layout effect', /useLayoutEffect\s*\(\s*\(\)\s*=>[\s\S]*NOTEBOOK_SCROLL_POSITIONS\.get\(scrollKey\)/],
]) {
  if (!pattern.test(notebookEditorSource)) {
    fail(`NotebookEditor scroll contract missing: ${label}`)
  }
}

if (!process.exitCode) {
  console.log('[frontend-contract] Notebook cross-editor scroll restore: OK')
}


const systemPagePath = path.join(__dirname, 'src', 'features', 'system', 'SystemPage.tsx')
const systemPageSource = fs.existsSync(systemPagePath) ? fs.readFileSync(systemPagePath, 'utf8') : ''
const adaptiveAiSource = `${source}\n${systemPageSource}`

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
  if (!pattern.test(adaptiveAiSource)) {
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
    fail(`${name}() is used by App.tsx but is not imported from ./utils/browser`)
  }
}

const browserComponentImports = namedImports('./components/browser/WebBrowserWorkspace')
if (/<WebBrowserWorkspace(?:\s|\/|>)/.test(source) && !browserComponentImports.has('WebBrowserWorkspace')) {
  fail('<WebBrowserWorkspace> is used by App.tsx but is not imported from ./components/browser/WebBrowserWorkspace')
}

const workspaceTypesPathForBrowser = path.join(__dirname, 'src', 'features', 'workspace', 'workspace.types.ts')
const workspaceTypesSourceForBrowser = fs.existsSync(workspaceTypesPathForBrowser) ? fs.readFileSync(workspaceTypesPathForBrowser, 'utf8') : ''
for (const [label, pattern, target] of [
  ['workspace browser tab beside LLM', /id:'BROWSER',label:'웹브라우저'/, workspaceTypesSourceForBrowser],
  ['fixed default browser tab', /DEFAULT_WEB_BROWSER_ID='web-browser-fixed'/, source],
  ['browser workspace render', /workspaceTab==='BROWSER'&&<WebBrowserWorkspace/, source],
  ['terminal local URL detector', /detectTerminalWebServices\(sessionId,incoming\)/, source],
  ['user-approved default browser action', /기본 웹브라우저에서 열기/, source],
  ['user-approved additional browser action', /추가 웹브라우저 탭/, source],
  ['browser detection toggle', /webUrlDetectionEnabled/, source],
]) {
  if (!pattern.test(target)) {
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


const editorControllerOwnershipPath = path.join(__dirname, 'src', 'features', 'editor', 'hooks', 'useEditorController.ts')
const editorControllerOwnershipSource = fs.existsSync(editorControllerOwnershipPath)
  ? fs.readFileSync(editorControllerOwnershipPath, 'utf8')
  : ''
const editorOwnershipSource = source + '\n' + editorControllerOwnershipSource

for (const [label, pattern] of [
  ['editor code starts empty instead of file-selection placeholder', /const \[code,setCode\]=useState\(''\)/],
  ['file loading path state', /const \[fileLoadingPath,setFileLoadingPath\]=useState\(''\)/],
  ['open file requires cached content before fast activation', /hasCachedContent=Object\.prototype\.hasOwnProperty\.call\(editorFileContents,requestedPath\)/],
  ['save blocked while authoritative file content is loading', /저장 대기 · 파일 로딩 중/],
  ['save-as blocked while authoritative file content is loading', /다른 이름 저장 대기 · 파일 로딩 중/],
  ['loading gate renders before notebook parser', /fileLoading&&fileLoadingPath===selected[\s\S]*파일을 불러오는 중입니다\./],
]) {
  if (!pattern.test(editorOwnershipSource)) {
    fail(`Editor authoritative-load contract missing: ${label}`)
  }
}

if (!process.exitCode) {
  console.log('[frontend-contract] Editor authoritative disk load / placeholder-save guard: OK')
}

const codexComponentImports = namedImports('./features/codex/components/CodexPanel')
if (/<CodexPanel(?:\s|\/|>)/.test(source) && !codexComponentImports.has('CodexPanel')) {
  fail('<CodexPanel> is used by App.tsx but is not imported from ./features/codex/components/CodexPanel')
}
const codexPanelPath = path.join(__dirname, 'src', 'features', 'codex', 'components', 'CodexPanel.tsx')
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
  ['Codex usage settings popover', /codex-usage-popover/, codexPanelSource],
  ['Codex force refresh usage', /\/codex\/rate-limits\?force=\$\{force \? 'true' : 'false'\}/, codexPanelSource],
  ['Codex five-hour usage label', /minutes === 300[^\n]*'5시간'/, codexPanelSource],
  ['Codex weekly usage label', /minutes === 10080[^\n]*'1주'/, codexPanelSource],
  ['Codex remaining usage title', /남은 사용량/, codexPanelSource],
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

for (const [label, ok] of [
  ['authoritative workspace root ref', source.includes("const workspaceRootRef=useRef('')")],
  ['authoritative file-tree root ref', source.includes("const fileTreeRootRef=useRef('')")],
  ['per-editor project root map', /const editorFileRootRef=useRef(?:<[^>]+>)?\(\{\}\)/.test(editorOwnershipSource)],
  ['workspace root resolver includes last loaded root', /const resolveWorkspaceRoot=\(preferredRoot(?::[^=)]+)?=''\)=>/.test(source) && source.includes('||workspaceRootRef.current')],
  ['file list stores successful root', source.includes('workspaceRootRef.current=targetRoot') && source.includes('fileTreeRootRef.current=targetRoot') && source.includes('setFiles(nextFiles)')],
  ['open file resolves tree root before read', /const openFile=async\(relativePath(?::[^,]+)?,rootOverride(?::[^=)]+)?=''\)=>/.test(source) && source.includes("resolveWorkspaceRoot(rootOverride||fileTreeRootRef.current||'')") && source.includes('root:workspaceRoot')],
  ['external reload resolves root', source.includes('const reloadExternalEditorFile=async') && source.includes('fileTreeRootRef.current||editorFileRootRef.current?.[editorPath]')],
  ['editor write resolves root', source.includes('const writeEditorFile=async') && source.includes('editorFileRootRef.current?.[relativePath]||fileTreeRootRef.current')],
  ['new project clears stale workspace root', source.includes("workspaceRootRef.current=''") && source.includes("fileTreeRootRef.current=''") && source.includes('editorFileRootRef.current={}')],
]) {
  if (!ok) {
    fail(`Project-root file load contract missing: ${label}`)
  }
}

if (/root:activeWorkspaceRoot,\s*relative_path:requestedPath/.test(source)) {
  fail('openFile must not send transient activeWorkspaceRoot directly')
}

if (!process.exitCode) {
  console.log('[frontend-contract] Project root retained across file load/read/write operations: OK')
}

// v5.511: AgentStudio API/WS runtime must come from SYSTEM_ADMIN-generated runtime-config.js.
{
  const apiSource = fs.readFileSync(path.join(__dirname, 'src', 'api.ts'), 'utf8')
  if (/BACKEND_PORT\s*\|\|\s*8000/.test(apiSource) || /VITE_API_BASE_URL/.test(apiSource)) {
    fail('AgentStudio API client must not use hard-coded/build-time port fallback; use runtime-config.js')
  }
  if (!apiSource.includes('cfg.API_BASE_URL') || !apiSource.includes('cfg.WS_BASE_URL')) {
    fail('AgentStudio API/WS client must use runtime-config.js API_BASE_URL/WS_BASE_URL')
  }
  if (!process.exitCode) console.log('[frontend-contract] Root .env -> runtime-config API/WS routing: OK')
}

// v5.512: Database provider startup source of truth is project-root .env, not local app_settings.
const dbRuntimePath = path.join(__dirname, '..', 'backend', 'app', 'services', 'database_runtime_service.py')
const dbRuntimeSource = fs.readFileSync(dbRuntimePath, 'utf8')
if (!dbRuntimeSource.includes('desired = _normalize_provider(getattr(get_settings(), "agentstudio_database_provider", PROVIDER_LOCAL))')) fail('database provider must come from root .env-backed Settings')
if (dbRuntimeSource.includes('desired = _normalize_provider(state.get(PROVIDER_SETTING_KEY))')) fail('local app_settings provider must not override root .env')
if (!process.exitCode) console.log('[frontend-contract] Root .env authoritative DB provider for auth/runtime: OK')

const workspaceShellPath = path.join(__dirname, 'src', 'features', 'workspace', 'WorkspaceShell.tsx')
const workspaceLayoutHookPath = path.join(__dirname, 'src', 'features', 'workspace', 'hooks', 'useWorkspaceLayout.ts')
const workspaceTypesPath = path.join(__dirname, 'src', 'features', 'workspace', 'workspace.types.ts')
for (const [label,filePath] of [['WorkspaceShell',workspaceShellPath],['useWorkspaceLayout',workspaceLayoutHookPath],['workspace types',workspaceTypesPath]]) {
  if (!fs.existsSync(filePath)) fail(`Workspace ownership extraction missing: ${label}`)
}
const workspaceTypesSource = fs.readFileSync(workspaceTypesPath,'utf8')
for (const tab of ['DESIGN','WORKFLOW','CODE','RUN','REPORT','ARCHITECTURE','DB_ERD','SCHEDULER','LLM','BROWSER']) {
  if (!workspaceTypesSource.includes(`'${tab}'`)) fail(`Workspace tab registry missing: ${tab}`)
}
console.log('[frontend-contract] Workspace Shell + Tab ownership separation: OK')

const terminalControllerPath = path.join(__dirname,'src','features','terminal','hooks','useTerminalController.ts')
const terminalSocketServicePath = path.join(__dirname,'src','features','terminal','services','terminalSocketService.ts')
if (!fs.existsSync(terminalControllerPath)) fail('Terminal Controller extraction missing')
if (!fs.existsSync(terminalSocketServicePath)) fail('Terminal Socket service extraction missing')
const terminalControllerSource = fs.readFileSync(terminalControllerPath,'utf8')
for (const token of [
  'terminalSessions','terminalSocketsRef','xtermInstancesRef','xtermCommandBuffersRef',
  'terminalReconnectTimersRef','fitTerminalViewport','sendSocketMessage','scheduleReconnect'
]) {
  if (!terminalControllerSource.includes(token)) fail(`Terminal ownership missing: ${token}`)
}
console.log('[frontend-contract] Terminal Controller ownership separation: OK')

const projectControllerPath = path.join(__dirname,'src','features','project','hooks','useProjectController.ts')
const editorControllerPath = path.join(__dirname,'src','features','editor','hooks','useEditorController.ts')
const editorFileServicePath = path.join(__dirname,'src','features','editor','services','editorFileService.ts')
for (const [label,filePath] of [['Project Controller',projectControllerPath],['Editor Controller',editorControllerPath],['Editor File Service',editorFileServicePath]]) {
  if (!fs.existsSync(filePath)) fail(`${label} separation missing`)
}
const projectControllerSource = fs.readFileSync(projectControllerPath,'utf8')
for (const token of ['projectSearch','projectLoadProgress','beginProjectLoad','filterProjects']) {
  if (!projectControllerSource.includes(token)) fail(`Project Controller ownership missing: ${token}`)
}
const editorControllerSource = fs.readFileSync(editorControllerPath,'utf8')
for (const token of ['editorInstanceRef','editorFileRootRef','editorTextSearchQuery','editorTabsScrollRef','toggleBookmark','rememberSelection','rememberScroll']) {
  if (!editorControllerSource.includes(token)) fail(`Editor Controller ownership missing: ${token}`)
}
const editorFileServiceSource = fs.readFileSync(editorFileServicePath,'utf8')
for (const token of ['readEditorTextFile','writeEditorTextFile','searchEditorProjectText']) {
  if (!editorFileServiceSource.includes(token)) fail(`Editor file service missing: ${token}`)
}
console.log('[frontend-contract] Project + Editor Controller ownership separation: OK')

const databaseControllerPath = path.join(__dirname,'src','features','database','hooks','useDatabaseController.ts')
const databaseServicePath = path.join(__dirname,'src','features','database','services','databaseService.ts')
const workflowControllerPath = path.join(__dirname,'src','features','workflow','hooks','useWorkflowController.ts')
const workflowServicePath = path.join(__dirname,'src','features','workflow','services','workflowService.ts')
for (const [label,filePath] of [['Database Controller',databaseControllerPath],['Database Service',databaseServicePath],['Workflow Controller',workflowControllerPath],['Workflow Service',workflowServicePath]]) if (!fs.existsSync(filePath)) fail(`${label} separation missing`)
const dbControllerSource=fs.readFileSync(databaseControllerPath,'utf8')
for(const token of ['sqlProfile','sqlConnectionStatus','sqlQueryResult','loadSqlObjects','connectSql','disconnectSql','runSql','rebuildDatabasePreview']) if(!dbControllerSource.includes(token)) fail(`Database Controller ownership missing: ${token}`)
const wfControllerSource=fs.readFileSync(workflowControllerPath,'utf8')
for(const token of ['workflowDefinition','targetWorkflowPreview','workflowProgress','useEffect','loadWorkflowDefinition','inspectWorkflowProviderStatus']) if(!wfControllerSource.includes(token)) fail(`Workflow Controller ownership missing: ${token}`)
console.log('[frontend-contract] Database + Workflow State/Service ownership separation: OK')

const agentDevelopmentControllerPath = path.join(__dirname,'src','features','agent-development','hooks','useAgentDevelopmentController.ts')
const agentDevelopmentControllerSource = fs.existsSync(agentDevelopmentControllerPath)
  ? fs.readFileSync(agentDevelopmentControllerPath,'utf8')
  : ''
for (const token of ['developmentProgress','developmentFinalStatus','builderMessagesEndRef']) {
  if (!agentDevelopmentControllerSource.includes(token)) fail(`Agent development state ownership missing: ${token}`)
}
console.log('[frontend-contract] Agent development state ownership preserved: OK')

const agentBuilderControllerPath=path.join(__dirname,'src','features','agent-builder','hooks','useAgentBuilderController.ts')
const externalProjectControllerPath=path.join(__dirname,'src','features','external-project','hooks','useExternalProjectController.ts')
const externalProjectServicePath=path.join(__dirname,'src','features','external-project','services','externalProjectService.ts')
const codexProposalControllerPath=path.join(__dirname,'src','features','codex','hooks','useCodexProposalController.ts')
for(const [label,filePath] of [
 ['Agent Builder Controller',agentBuilderControllerPath],
 ['Agent Development Controller',agentDevelopmentControllerPath],
 ['External Project Controller',externalProjectControllerPath],
 ['External Project Service',externalProjectServicePath],
 ['Codex Proposal Controller',codexProposalControllerPath],
]) if(!fs.existsSync(filePath)) fail(`${label} separation missing`)
const agentBuilderControllerSource=fs.readFileSync(agentBuilderControllerPath,'utf8')
for(const token of ['confirmedInterviewRequirements','requirementRecommendations','developmentStagePlan','requirementDraftCandidate']){
  if(!agentBuilderControllerSource.includes(token)) fail(`Agent Builder ownership missing: ${token}`)
}
const externalProjectControllerSource=fs.readFileSync(externalProjectControllerPath,'utf8')
for(const token of ['externalProjectPath','externalProjectAnalysis','externalProjectProgress','beginExternalProjectAnalysis']){
  if(!externalProjectControllerSource.includes(token)) fail(`External Project ownership missing: ${token}`)
}
const codexProposalControllerSource=fs.readFileSync(codexProposalControllerPath,'utf8')
if(!codexProposalControllerSource.includes('registerCodexCodeProposal')) fail('Codex proposal handler ownership missing')
console.log('[frontend-contract] Agent Builder + Development + External Project + Codex residual separation: OK')

const transparencyPanelPath=path.join(__dirname,'src','features','agent-development','components','AgentExecutionTransparencyPanel.tsx')
if(!fs.existsSync(transparencyPanelPath)) fail('Agent execution transparency panel missing')
const transparencySource=fs.readFileSync(transparencyPanelPath,'utf8')
for(const token of ['지금 처리 중','현재까지 정리된 내용','요구사항 분석 내용 보기','실제 Backend 진행 이벤트','AI 내부 사고 과정을 임의로 만들어 표시하지 않습니다.']){
  if(!transparencySource.includes(token)) fail(`Execution transparency detail missing: ${token}`)
}
for(const token of ['mode="DESIGN"','mode="DEVELOPMENT"','requirementItems={getRequirementKeywordStatus()}','events={developmentProgress.events||[]}']){
  if(!source.includes(token)) fail(`Execution transparency integration missing: ${token}`)
}
console.log('[frontend-contract] Design/development transparent progress details: OK')

for(const token of [
  'const hasExplicitBlenderRequirement=',
  'const resolveRestoredAgentSpecialization=',
  "specializationSource==='USER'",
  "source:'USER'",
  "setAgentSpecialization(resolveRestoredAgentSpecialization(snapshot))",
]){
  if(!source.includes(token)) fail(`Blender project-scope gate missing: ${token}`)
}
if(source.includes("snapshot?.workflow_preview?.three_d_agent_plan?.type||'GENERAL'")) fail('Blender specialization must not be inferred from stale workflow preview')
if(source.includes("setAgentSpecialization('BLENDER_3D')") && source.includes("restoredPreview?.three_d_agent_plan")) fail('Restored 3D plan must not force Blender specialization')
console.log('[frontend-contract] Project-scoped Blender specialization gate: OK')

const blenderWorkflowCardPath=path.join(__dirname,'src','features','agent-builder','components','BlenderAgentWorkflowCard.tsx')
if(!fs.existsSync(blenderWorkflowCardPath)) fail('Blender Agent Workflow card feature separation missing')
const blenderWorkflowCardSource=fs.readFileSync(blenderWorkflowCardPath,'utf8')
if(!blenderWorkflowCardSource.includes('3D 제작 Agent · Blender MCP')) fail('Blender card content missing')
for(const token of [
  'autoFinalizeDatabasePlanFromApprovedResource',
  "approval_source:'APPROVED_DATABASE_RESOURCE_PLAN'",
  '설계 검토 전에 승인한 DB Resource Plan을 재사용',
  '사전 승인 반영',
]){
  if(!source.includes(token)) fail(`Pre-approved DB design reuse missing: ${token}`)
}
console.log('[frontend-contract] Blender card separation + pre-approved DB design reuse: OK')

if(!source.includes("['DESIGN','WORKFLOW','RUN'].includes(workspaceTab)?<>")) fail('Workflow/Run left panel must reuse Agent design sidebar')
if(!source.includes('현재 Workflow는 이 Agent 설계 요구사항을 기준으로 생성됩니다.')) fail('Workflow design-context note missing')
console.log('[frontend-contract] Workflow left sidebar reuses Agent design context: OK')

if(!source.includes("workspaceTab==='CODE'&&codeRightPanelTab==='MEMO'?'memo-scroll-info-panel':''")) fail('Code Memo whole-right scroll class missing')
const memoPanelPath=path.join(__dirname,'src','features','project','components','ProjectMemoPanel.tsx')
const memoPanelSource=fs.existsSync(memoPanelPath)?fs.readFileSync(memoPanelPath,'utf8'):''
if(!memoPanelSource.includes("panelMode === 'LIVE' ? 'live-mode' : 'memo-mode'")) fail('Project Memo live-mode class missing')
if(!memoPanelSource.includes('project-live-bottom-spacer')) fail('Project Memo bottom visibility spacer missing')
const styleSource=fs.readFileSync(path.join(__dirname,'src','styles.css'),'utf8')
for(const token of ['.workspace-info-panel.memo-scroll-info-panel','.project-memo-panel.live-mode .project-live-transcript','height:clamp(460px,58vh,760px)']){
  if(!styleSource.includes(token)) fail(`Live transcript vertical workspace style missing: ${token}`)
}
console.log('[frontend-contract] Memo live Transcript tall view + whole right scroll: OK')

const memoPanel560Path=path.join(__dirname,'src','features','project','components','ProjectMemoPanel.tsx')
const memo560=fs.readFileSync(memoPanel560Path,'utf8')
const summaryButtonIndex=memo560.indexOf("✦ 요약정리")
const summaryFileButtonIndex=memo560.indexOf("💾 요약 파일 저장")
if(summaryButtonIndex<0||summaryFileButtonIndex<0||summaryButtonIndex>summaryFileButtonIndex) fail('요약정리 버튼은 요약 파일 저장보다 앞에 있어야 합니다.')
for(const token of ['liveSummaryErrorLogPath','parseSummaryErrorDetail','project-live-summary-log-path']){
  if(!memo560.includes(token)) fail(`Transcript summary error log UI missing: ${token}`)
}
console.log('[frontend-contract] Transcript summary button order + error log path: OK')

for(const token of ['agentDesignAutoSaveTabRef','latestDesignProjectSaveRef','userActionSaveTimerRef','saveRequirementDraft(','requirementCheckpointSignatureRef']){
  if(source.includes(token)) fail(`Agent Design autosave must be removed: ${token}`)
}
console.log('[frontend-contract] Agent Design autosave removed: OK')

const memoPanel562=fs.readFileSync(path.join(__dirname,'src','features','project','components','ProjectMemoPanel.tsx'),'utf8')
for(const token of ['liveSummaryFallback','project-live-summary-provider-notice','project-live-summary-bottom','로컬 요약 생성 완료']){
  if(!memoPanel562.includes(token)) fail(`v5.562 transcript summary separation missing: ${token}`)
}
if(memoPanel562.indexOf('project-live-summary-provider-notice') > memoPanel562.indexOf('project-live-summary-bottom')) fail('Provider notice must render before the separate bottom summary')
console.log('[frontend-contract] Transcript provider warning + bottom summary separation: OK')

const notebook563Path=path.join(__dirname,'src','features','notebook','components','NotebookEditor.tsx')
const notebook563=fs.readFileSync(notebook563Path,'utf8')
for(const token of [
  'sourceCommitTimerRef',
  'scheduleSourceCommit',
  'flushPendingSourceChanges',
  'window.setTimeout(() =>',
  '}, 900)',
  'getLiveContent: () => buildLiveNotebookContent()',
  'flushPendingChanges: () => flushPendingSourceChanges()',
]){
  if(!notebook563.includes(token)) fail(`Notebook deferred serialization missing: ${token}`)
}
if(notebook563.includes("patchCell(index, { source: textToNotebookSource(text) })")) fail('Notebook typing must not serialize through patchCell on every keystroke')
for(const token of ['notebookEditorControllerRef.current?.flushPendingChanges?.()','liveNotebookContent']){
  if(!source.includes(token)) fail(`Notebook Ctrl+S live-buffer protection missing: ${token}`)
}
console.log('[frontend-contract] Notebook deferred serialization + live Ctrl+S buffer: OK')

const nb564=fs.readFileSync(path.join(__dirname,'src','features','notebook','components','NotebookEditor.tsx'),'utf8')
for(const token of ['requestIdleCallback','}, 900)','sourceCommitIdleRef']){
  if(!nb564.includes(token)) fail(`Notebook idle serialization optimization missing: ${token}`)
}
for(const token of [
  'editorWorkspaceStorageKey',
  'persistEditorWorkspace',
  'restoreEditorWorkspace',
  'theanova.agentstudio.editor-workspace::',
  'await restoreEditorWorkspace(projectRoot)',
]){
  if(!source.includes(token)) fail(`Project-scoped editor workspace restore missing: ${token}`)
}
console.log('[frontend-contract] Notebook idle typing + project editor tab restore: OK')

const promptComposerPath=path.join(__dirname,'src','features','editor','components','CodeLlmPromptComposer.tsx')
if(!fs.existsSync(promptComposerPath)) fail('Code LLM local prompt composer missing')
const promptComposer=fs.readFileSync(promptComposerPath,'utf8')
for(const token of ['React.memo','const [prompt,setPrompt]=useState','onSubmit(value)']){
  if(!promptComposer.includes(token)) fail(`LLM prompt hot-path isolation missing: ${token}`)
}
if(source.includes("const [codeEditPrompt,setCodeEditPrompt]=useState('')")) fail('LLM code prompt must not live in App state')
for(const token of ['useDeferredValue(projectFileSearch)','const projectTree=useMemo(','const projectTreeForDisplay=useMemo(']){
  if(!source.includes(token)) fail(`Project tree render optimization missing: ${token}`)
}
console.log('[frontend-contract] Global typing hot-path isolation + project tree memoization: OK')

if(source.includes('autoSaveEnabled={true}')) fail('Agent Design toolbar must not advertise autosave')
if((source.match(/autoSaveEnabled=\{false\}/g)||[]).length<2) fail('Agent Design toolbars must show autosave disabled')
if(!source.includes("자동 저장은 사용하지 않습니다. 필요한 내용은 먼저 '지금 저장'으로 저장해 주세요.")) fail('Manual save warning missing')
console.log('[frontend-contract] Manual Agent Design save only: OK')

for(const token of [
  'persistRequirementCheckpoint(',
  'latestDesignProjectSaveRef',
  'userActionSaveTimerRef',
  'agentDesignAutoSaveTabRef',
  'saveRequirementDraft(',
]){
  if(source.includes(token)) fail(`Removed Agent Design autosave symbol leaked back into App.tsx: ${token}`)
}
if(!source.includes('Automatic project-folder checkpoint persistence was removed in v5.566.')){
  fail('Draft restore must remain local-only after Agent Design autosave removal')
}
console.log('[frontend-contract] v5.567 autosave orphan reference cleanup: OK')

for(const token of [
  'default_prompt_text',
  'ai_recommended_prompt_text',
  'custom_prompt_text',
  "api('/workflow/prompt-module/recommend'",
  'AI 추천 Prompt 생성',
  'effective_prompt_text',
]){
  if(!source.includes(token)) fail(`Prompt Registry editable modes missing: ${token}`)
}
console.log('[frontend-contract] Prompt Registry default/AI/custom editable prompt text: OK')

for(const token of [
  'const [promptEditingId,setPromptEditingId]',
  'tool-prompt-list-item',
  "isEditing?'닫기':'수정'",
  'tool-prompt-edit-form',
  'AI 추천 Prompt 생성',
]){
  if(!source.includes(token)) fail(`Prompt Registry list-first editor missing: ${token}`)
}
console.log('[frontend-contract] Prompt Registry list-first/edit-on-demand UI: OK')

for(const token of [
  "ui_layout:uiLayoutConfig||confirmedInterviewRequirements?.ui_layout||{}",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "PPT 파일 크기가 비정상적으로 작습니다",
]){
  if(!source.includes(token)) fail(`PPT export frontend hardening missing: ${token}`)
}
console.log('[frontend-contract] PPT export null-safe payload + MIME validation: OK')

for(const token of [
  "api('/presentation/open'",
  "body:JSON.stringify({path:saved.path})",
  "PPT 저장 완료 · 문서 실행 요청 완료",
  "문서 자동 열기 실패",
]){
  if(!source.includes(token)) fail(`PPT auto-open flow missing: ${token}`)
}
console.log('[frontend-contract] PPT save then OS auto-open: OK')

const workspaceTypes572=fs.readFileSync(path.join(__dirname,'src','features','workspace','workspace.types.ts'),'utf8')
const runTab572=workspaceTypes572.indexOf("{id:'RUN',label:'실행 결과'")
const codeTab572=workspaceTypes572.indexOf("{id:'CODE',label:'코드 편집'")
if(runTab572<0||codeTab572<0||runTab572>codeTab572) fail('실행 결과 탭은 코드 편집 탭보다 앞에 있어야 합니다.')
if(!source.includes("['DESIGN','WORKFLOW','RUN'].includes(workspaceTab)?<>")) fail('실행 결과 탭 좌측은 신규 Agent 설계 Context를 사용해야 합니다.')
if(!source.includes("workspaceTab==='RUN'&&<div className=\"design-left-context-note\">현재 실행 결과는 이 Agent 설계 요구사항과 개발 계획을 기준으로 확인합니다.</div>")) fail('실행 결과 설계 Context 안내가 없습니다.')
console.log('[frontend-contract] RUN/CODE tab swap + RUN design left context: OK')

const aiTrendsComponent=fs.readFileSync(path.join(__dirname,'src','features','ai-trends','components','AITrendsDashboard.tsx'),'utf8')
const aiTrendsHook=fs.readFileSync(path.join(__dirname,'src','features','ai-trends','hooks','useAITrends.ts'),'utf8')
if(!source.includes('<AITrendsDashboard data={aiTrends.data}')) fail('Home AI Trends dashboard missing')
if(!source.includes("useAITrends(screen==='HOME')")) fail('Home AI Trends daily load hook missing')
if(!aiTrendsComponent.includes('오늘 수집한 데이터를 표시하고 있습니다.')) fail('AI Trends daily cache status UI missing')
if(!aiTrendsHook.includes("api") && !aiTrendsHook.includes("loadAITrends")) fail('AI Trends hook service binding missing')
console.log('[frontend-contract] AI Trends feature + daily cache UI: OK')
