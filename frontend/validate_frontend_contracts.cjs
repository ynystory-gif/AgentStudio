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
  ['./components/terminal/TerminalPanel', ['TerminalPanel']],
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
