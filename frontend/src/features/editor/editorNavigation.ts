import {
  getEditorLanguage,
  isBinaryPreviewFile,
  isDatabaseDiagramFile,
  isNotebookFile,
  isPdfFile,
  isPresentationFile,
} from '../../utils/editor'

export const normalizeProjectRelativePath=(value: LegacyValue='')=>String(value||'').replace(/\\/g,'/').replace(/^\/+/, '')

const TEXT_EDITOR_BOOKMARK_STORAGE_PREFIX='theanova.agentstudio.text-editor.line-bookmarks::'
const TEXT_EDITOR_BOOKMARK_CACHE=new Map<LegacyValue,LegacyValue>()

export const normalizeTextEditorLineBookmarks=(value: LegacyValue)=>Array.from(new Set((Array.isArray(value)?value:[])
  .map((item: LegacyValue)=>Number(item))
  .filter((item: LegacyValue)=>Number.isInteger(item)&&item>=1)))
  .sort((a: LegacyValue,b: LegacyValue)=>a-b)

export const textEditorBookmarkStorageKey=(projectRoot: LegacyValue='',filePath: LegacyValue='')=>{
  const path=normalizeProjectRelativePath(filePath)
  if(!path) return ''
  const normalizedRoot=String(projectRoot||'').trim().replace(/\\/g,'/').replace(/\/+$/,'')
  return `${normalizedRoot}::${path}`
}

export const loadTextEditorLineBookmarks=(key: LegacyValue='')=>{
  if(!key) return []
  if(TEXT_EDITOR_BOOKMARK_CACHE.has(key)) return TEXT_EDITOR_BOOKMARK_CACHE.get(key)
  let value:LegacyValue[]=[]
  try{
    const raw=window.localStorage.getItem(`${TEXT_EDITOR_BOOKMARK_STORAGE_PREFIX}${key}`)
    if(raw) value=normalizeTextEditorLineBookmarks(JSON.parse(raw))
  }catch{}
  TEXT_EDITOR_BOOKMARK_CACHE.set(key,value)
  return value
}

export const storeTextEditorLineBookmarks=(key: LegacyValue='',bookmarks:LegacyValue[]=[])=>{
  const value=normalizeTextEditorLineBookmarks(bookmarks)
  if(!key) return value
  TEXT_EDITOR_BOOKMARK_CACHE.set(key,value)
  try{window.localStorage.setItem(`${TEXT_EDITOR_BOOKMARK_STORAGE_PREFIX}${key}`,JSON.stringify(value))}catch{}
  return value
}

const TEXT_EDITOR_BREAKPOINT_STORAGE_PREFIX='theanova.agentstudio.text-editor.breakpoints::'
const TEXT_EDITOR_BREAKPOINT_CACHE=new Map<LegacyValue,LegacyValue>()

export const loadTextEditorBreakpoints=(key: LegacyValue='')=>{
  if(!key) return []
  if(TEXT_EDITOR_BREAKPOINT_CACHE.has(key)) return TEXT_EDITOR_BREAKPOINT_CACHE.get(key)
  let value:LegacyValue[]=[]
  try{
    const raw=window.localStorage.getItem(`${TEXT_EDITOR_BREAKPOINT_STORAGE_PREFIX}${key}`)
    if(raw) value=normalizeTextEditorLineBookmarks(JSON.parse(raw))
  }catch{}
  TEXT_EDITOR_BREAKPOINT_CACHE.set(key,value)
  return value
}

export const storeTextEditorBreakpoints=(key: LegacyValue='',breakpoints: LegacyValue=[])=>{
  const value=normalizeTextEditorLineBookmarks(breakpoints)
  if(!key) return value
  TEXT_EDITOR_BREAKPOINT_CACHE.set(key,value)
  try{window.localStorage.setItem(`${TEXT_EDITOR_BREAKPOINT_STORAGE_PREFIX}${key}`,JSON.stringify(value))}catch{}
  return value
}

const SOURCE_DEBUG_LANGUAGES=new Set(['python','javascript','typescript','powershell','bat','shell','csharp','java','cpp','go','rust','php','ruby'])
const SOURCE_DEBUG_EXTENSIONS=new Set(['py','pyw','js','jsx','mjs','cjs','ts','tsx','mts','cts','ps1','psm1','cmd','bat','sh','bash','zsh','cs','java','c','cc','cpp','cxx','go','rs','php','rb','pl','lua','r','swift','kts'])
const CSV_SPREADSHEET_EXTENSIONS=new Set(['csv','tsv'])

export const sourceDebugExtension=(filePath: LegacyValue='')=>{
  const name=normalizeProjectRelativePath(filePath).split('/').pop()||''
  const dot=name.lastIndexOf('.')
  return dot>=0?name.slice(dot+1).toLowerCase():''
}

export const isSourceDebugFile=(filePath: LegacyValue='')=>SOURCE_DEBUG_EXTENSIONS.has(sourceDebugExtension(filePath))||SOURCE_DEBUG_LANGUAGES.has(getEditorLanguage(filePath))
export const sourceDebugSupportsStep=(filePath: LegacyValue='')=>['py','pyw'].includes(sourceDebugExtension(filePath))

export const isBookmarkableTextEditorFile=(filePath: LegacyValue='')=>{
  const path=String(filePath||'').trim()
  const extension=sourceDebugExtension(path)
  return !!path
    &&!isNotebookFile(path)
    &&!isPdfFile(path)
    &&!isPresentationFile(path)
    &&!isDatabaseDiagramFile(path)
    &&!CSV_SPREADSHEET_EXTENSIONS.has(extension)
    &&!isBinaryPreviewFile(path)
}
