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

export const isBinaryPreviewFile = (filePath = ''): boolean => isPdfFile(filePath) || isPresentationFile(filePath)
