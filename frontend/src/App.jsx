import React, { useEffect, useState, useRef, useMemo, useDeferredValue, memo } from 'react'
import Editor, { DiffEditor } from '@monaco-editor/react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { api, connectJobs, runtimeInfo } from './api'
import { NotebookEditor } from './components/notebook/NotebookEditor'
import { PdfViewer, PresentationViewer } from './components/viewers/DocumentViewers'
import { MiniBadge, SectionTitle, StatusDot, StudioIcon } from './components/common/CommonUi'
import { FileChangeList, KeyValueGrid, MetricCard, ReportSection, StatusBadge, WorkflowMiniMap } from './components/reports/ReportComponents'
import { ArchitectureConformancePanel, AsBuiltAgentArchitecturePanel, GeneratedAgentArchitecturePanel } from './components/architecture/ArchitecturePanels'
import { LlmCatalogPanel } from './components/llm/LlmCatalogPanel'
import { DatabaseBrowserContextMenus, FirestoreBrowserPanel, RedisBrowserPanel, SqlObjectTreePanel } from './components/database/DatabaseBrowsers'
import { DatabaseDiagramViewer } from './components/database/DatabaseDiagramViewer'
import { DatabaseErdPanel } from './components/database/DatabaseErdPanel'
import { SqlResultsPane } from './components/database/SqlResultsPane'
import { TerminalPanel } from './components/terminal/TerminalPanel'
import { GpuSettingsPanel, OllamaSettingsPanel, RuntimeDatabasePanel, ServicePortSettingsPanel, SystemStatusSummary } from './components/system/SystemRuntimePanels'
import { WebBrowserWorkspace } from './components/browser/WebBrowserWorkspace'
import { CodexPanel } from './components/codex/CodexPanel'
import { CodexSettingsPanel } from './components/codex/CodexSettingsPanel'
import { AiAttachmentPicker } from './components/ai/AiAttachmentPicker'
import { AgentActivityProgress } from './components/ai/AgentActivityProgress'
import { AgentDesignProjectToolbar, AgentFeatureManager } from './components/ai/AgentDesignProjectManager'
import { parseTerminalServerMessage, serializeTerminalClientMessage, terminalCellWidth, terminalNextCharacter, terminalPreviousCharacter } from './utils/terminal'
import { getEditorLanguage, getEditorModelPath, isBinaryPreviewFile, isDatabaseDiagramFile, isNotebookFile, isPdfFile, isPresentationFile } from './utils/editor'
import { formatNotebookSqlResult, looksLikeNotebookSqlCode, normalizeNotebookSqlCode } from './utils/notebook'
import { browserTitleForUrl, extractLocalDevelopmentUrls, normalizeBrowserUrl, usesBackendBrowserProxy } from './utils/browser'
import { AgentWorkCenterPanel, GlobalCommandPalette, HelpCenterPanel } from './components/global/GlobalStudioOverlays'

const AGENTSTUDIO_FRONTEND_VERSION='5.390'

const DebouncedProjectSearchInput=memo(function DebouncedProjectSearchInput({value,onCommit,placeholder='프로젝트 검색...'}){
  const [localValue,setLocalValue]=useState(value||'')
  useEffect(()=>{ setLocalValue(value||'') },[value])
  useEffect(()=>{
    const timer=window.setTimeout(()=>{
      if((value||'')!==localValue) onCommit(localValue)
    },180)
    return()=>window.clearTimeout(timer)
  },[localValue,value,onCommit])
  return <input
    className="project-search"
    value={localValue}
    onChange={event=>setLocalValue(event.target.value)}
    placeholder={placeholder}
    autoComplete="off"
    spellCheck={false}
  />
})


const joinWin = (root, file) => `${root}\\${file}`.replaceAll('\\\\', '\\')
const localIsoDate = () => {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`
}
const localIsoMonth = () => localIsoDate().slice(0,7)
const normalizeProjectRelativePath=(value='')=>String(value||'').replace(/\\/g,'/').replace(/^\/+/, '')
const TEXT_EDITOR_BOOKMARK_STORAGE_PREFIX='theanova.agentstudio.text-editor.line-bookmarks::'
const TEXT_EDITOR_BOOKMARK_CACHE=new Map()
const normalizeTextEditorLineBookmarks=(value)=>Array.from(new Set((Array.isArray(value)?value:[])
  .map(item=>Number(item))
  .filter(item=>Number.isInteger(item)&&item>=1)))
  .sort((a,b)=>a-b)
const textEditorBookmarkStorageKey=(projectRoot='',filePath='')=>{
  const path=normalizeProjectRelativePath(filePath)
  if(!path) return ''
  const normalizedRoot=String(projectRoot||'').trim().replace(/\\/g,'/').replace(/\/+$/,'')
  return `${normalizedRoot}::${path}`
}
const loadTextEditorLineBookmarks=(key='')=>{
  if(!key) return []
  if(TEXT_EDITOR_BOOKMARK_CACHE.has(key)) return TEXT_EDITOR_BOOKMARK_CACHE.get(key)
  let value=[]
  try{
    const raw=window.localStorage.getItem(`${TEXT_EDITOR_BOOKMARK_STORAGE_PREFIX}${key}`)
    if(raw) value=normalizeTextEditorLineBookmarks(JSON.parse(raw))
  }catch{}
  TEXT_EDITOR_BOOKMARK_CACHE.set(key,value)
  return value
}
const storeTextEditorLineBookmarks=(key='',bookmarks=[])=>{
  const value=normalizeTextEditorLineBookmarks(bookmarks)
  if(!key) return value
  TEXT_EDITOR_BOOKMARK_CACHE.set(key,value)
  try{window.localStorage.setItem(`${TEXT_EDITOR_BOOKMARK_STORAGE_PREFIX}${key}`,JSON.stringify(value))}catch{}
  return value
}
const isBookmarkableTextEditorFile=(filePath='')=>{
  const path=String(filePath||'').trim()
  return !!path
    &&!isNotebookFile(path)
    &&!isPdfFile(path)
    &&!isPresentationFile(path)
    &&!isDatabaseDiagramFile(path)
    &&!isBinaryPreviewFile(path)
}
const sanitizeInterviewDisplayText=(value='')=>{
  let text=String(value||'')
  // v5.334 and older stored attachment labels in every user message. They are
  // session metadata, not conversation content, so strip them when restoring
  // old drafts and before rendering.
  text=text.replace(/(?:\r?\n){0,2}📎\s*참고 파일:[^\r\n]*/g,'')

  // Never render credentials that may have existed in an older saved draft.
  text=text.replace(/\bsk-[A-Za-z0-9_-]{16,}\b/g,'[REDACTED_TOKEN]')
  text=text.replace(/\bAIza[0-9A-Za-z_-]{20,}\b/g,'[REDACTED_TOKEN]')
  text=text.replace(/\bgh[pousr]_[A-Za-z0-9]{20,}\b/g,'[REDACTED_TOKEN]')
  text=text.replace(/\bxox[baprs]-[A-Za-z0-9-]{16,}\b/g,'[REDACTED_TOKEN]')
  text=text.replace(/((?:postgres(?:ql)?|mysql|mariadb|redis):\/\/[^:\s/@]+:)([^@\s/]+)(@)/gi,'$1[REDACTED]$3')
  text=text.replace(/(^|\n)(\s*(?:OPENAI_API_KEY|TAVILY_API_KEY|GEMINI_API_KEY|LANGCHAIN_API_KEY|SUPABASE_DB_PASSWORD|PGPASSWORD|[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD))\s*=\s*)([^\r\n]+)/g,(_m,start,prefix,raw)=>{
    const value=String(raw||'').trim().toLowerCase()
    if(value.includes('getenv(')||value.includes('os.getenv')||value.startsWith('${')||value.startsWith('$env:')||value.startsWith('<')||value.includes('[redacted]')){
      return `${start}${prefix}${raw}`
    }
    return `${start}${prefix}[REDACTED]`
  })
  return text.trim()
}
const parseAttachmentSummarySections=(value='')=>{
  const text=sanitizeInterviewDisplayText(value)
  if(!text) return []
  const sections=[]
  let current={title:'AI 정리',lines:[]}
  for(const rawLine of text.split(/\r?\n/)){
    const line=String(rawLine||'').trim()
    const heading=line.match(/^#{1,3}\s+(.+)$/)
    if(heading){
      if(current.lines.length||current.title!=='AI 정리') sections.push(current)
      current={title:heading[1].trim(),lines:[]}
      continue
    }
    if(line) current.lines.push(line.replace(/^[-*]\s+/,''))
  }
  if(current.lines.length||current.title!=='AI 정리') sections.push(current)
  return sections
}

function AttachmentAnalysisSummaryCard({summary='',files=[],requirements=[],coverage={},compact=false,restored=false,onClear=null}){
  const cardRef=useRef(null)
  const resizeRef=useRef({active:false,pointerId:null,startY:0,startHeight:0,currentHeight:0})
  const defaultPanelHeight=()=>{
    const viewportHeight=typeof window!=='undefined'?window.innerHeight:900
    return Math.round(Math.min(440,Math.max(280,viewportHeight*0.42)))
  }
  const readSavedPanelHeight=()=>{
    if(compact) return null
    try{
      const stored=Number(window.localStorage.getItem('agentstudio.attachmentAnalysisSummaryHeight')||0)
      if(Number.isFinite(stored)&&stored>=180) return stored
    }catch{}
    return defaultPanelHeight()
  }
  const [panelHeight,setPanelHeight]=useState(readSavedPanelHeight)
  const clampPanelHeight=(value)=>{
    const viewportHeight=typeof window!=='undefined'?window.innerHeight:900
    const maximum=Math.max(260,Math.floor(viewportHeight*0.72))
    return Math.round(Math.min(maximum,Math.max(180,Number(value)||defaultPanelHeight())))
  }
  const persistPanelHeight=(value)=>{
    try{window.localStorage.setItem('agentstudio.attachmentAnalysisSummaryHeight',String(clampPanelHeight(value)))}catch{}
  }
  const resetPanelHeight=()=>{
    if(compact) return
    const next=defaultPanelHeight()
    setPanelHeight(next)
    persistPanelHeight(next)
  }
  const beginPanelResize=(event)=>{
    if(compact) return
    const currentHeight=cardRef.current?.getBoundingClientRect?.().height||panelHeight||defaultPanelHeight()
    resizeRef.current={active:true,pointerId:event.pointerId,startY:event.clientY,startHeight:currentHeight,currentHeight}
    try{event.currentTarget.setPointerCapture(event.pointerId)}catch{}
    event.preventDefault()
  }
  const movePanelResize=(event)=>{
    const state=resizeRef.current
    if(compact||!state.active||state.pointerId!==event.pointerId) return
    const next=clampPanelHeight(state.startHeight+(event.clientY-state.startY))
    state.currentHeight=next
    setPanelHeight(next)
    event.preventDefault()
  }
  const endPanelResize=(event)=>{
    const state=resizeRef.current
    if(!state.active||state.pointerId!==event.pointerId) return
    state.active=false
    try{event.currentTarget.releasePointerCapture(event.pointerId)}catch{}
    const finalHeight=clampPanelHeight(state.currentHeight||panelHeight||defaultPanelHeight())
    setPanelHeight(finalHeight)
    persistPanelHeight(finalHeight)
    event.preventDefault()
  }
  const resizePanelFromKeyboard=(event)=>{
    if(compact||!['ArrowUp','ArrowDown','Home'].includes(event.key)) return
    event.preventDefault()
    if(event.key==='Home'){
      resetPanelHeight()
      return
    }
    const step=event.shiftKey?80:32
    const next=clampPanelHeight((panelHeight||defaultPanelHeight())+(event.key==='ArrowDown'?step:-step))
    setPanelHeight(next)
    persistPanelHeight(next)
  }

  const safeSummary=sanitizeInterviewDisplayText(summary)
  const safeRequirements=(Array.isArray(requirements)?requirements:[])
    .map(item=>({
      id:String(item?.id||''),
      category:String(item?.category||'FUNCTIONAL'),
      text:sanitizeInterviewDisplayText(item?.text||''),
      source:String(item?.source||''),
      location:String(item?.location||''),
      status:String(item?.status||''),
    }))
    .filter(item=>item.text)
  if(!safeSummary&&!safeRequirements.length) return null
  const sections=parseAttachmentSummarySections(safeSummary)
  const safeFiles=(Array.isArray(files)?files:[])
    .map(item=>({name:String(item?.name||''),path:String(item?.path||'')}))
    .filter(item=>item.name||item.path)
  const requirementCount=Number(coverage?.requirement_count||safeRequirements.length||0)
  const categoryCounts=coverage?.categories&&typeof coverage.categories==='object'?coverage.categories:{}
  return <div
    ref={cardRef}
    className={`attachment-ai-summary-card ${compact?'compact':'resizable'}`}
    style={!compact&&panelHeight?{height:`${clampPanelHeight(panelHeight)}px`}:undefined}
  >
    <div className="attachment-ai-summary-head">
      <div>
        <strong>첨부 파일 AI 정리</strong>
        <small>{restored?'이전 인터뷰에서 저장된 분석 결과':'문서 요구사항을 구조적으로 추출해 Context에 반영한 결과'}</small>
      </div>
      <div className="attachment-ai-summary-head-meta">
        <span className="attachment-ai-summary-status">✓ 요구사항 {requirementCount||'-'}개</span>
        {!compact&&<small>내부 스크롤 · 아래 조절선을 드래그해 높이 변경</small>}
      </div>
    </div>
    <div className="attachment-ai-summary-scroll" tabIndex={compact?-1:0}>
      {safeFiles.length>0&&<div className="attachment-ai-summary-files">
        {safeFiles.slice(0,compact?4:12).map((item,index)=><span key={`${item.path||item.name}-${index}`} title={item.path||item.name}>{item.name||item.path}</span>)}
        {compact&&safeFiles.length>4&&<span>+{safeFiles.length-4}개</span>}
      </div>}
      {safeSummary&&<div className="attachment-ai-summary-sections">
        {sections.slice(0,compact?2:10).map((section,index)=><div className="attachment-ai-summary-section" key={`${section.title}-${index}`}>
          <b>{section.title}</b>
          {section.lines.length>0
            ? <ul>{section.lines.slice(0,compact?2:12).map((line,lineIndex)=><li key={lineIndex}>{line}</li>)}</ul>
            : <span>-</span>}
        </div>)}
      </div>}
      {safeRequirements.length>0&&<div className="attachment-requirement-registry">
        <div className="attachment-requirement-registry-head">
          <div><b>추출 요구사항</b><span>Notebook Markdown·문제 문장·제약·기술 단서를 Requirement Registry로 보존합니다.</span></div>
          {!compact&&<em>{Object.entries(categoryCounts).map(([key,value])=>`${key} ${value}`).slice(0,8).join(' · ')}</em>}
        </div>
        <div className="attachment-requirement-list">
          {safeRequirements.slice(0,compact?5:60).map((item,index)=><div className="attachment-requirement-row" key={`${item.id}-${index}`} title={`${item.source}${item.location?` / ${item.location}`:''}`}>
            <span>{item.id||`REQ-${index+1}`}</span>
            <i>{item.category}</i>
            <b>{item.text}</b>
            {!compact&&<small>{item.source}{item.location?` · ${item.location}`:''}</small>}
          </div>)}
          {compact&&safeRequirements.length>5&&<div className="attachment-requirement-more">+ {safeRequirements.length-5}개 요구사항</div>}
        </div>
      </div>}
    </div>
    {!compact&&<div className="attachment-ai-summary-actions">
      <button type="button" onClick={()=>{try{navigator.clipboard?.writeText([safeSummary,...safeRequirements.map(item=>`${item.id} [${item.category}] ${item.text}`)].filter(Boolean).join('\n'))}catch{}}}>정리 내용 복사</button>
      <button type="button" onClick={resetPanelHeight}>기본 높이</button>
      {typeof onClear==='function'&&<button type="button" className="danger" onClick={onClear}>첨부 분석 Context 지우기</button>}
    </div>}
    {!compact&&<div
      className="attachment-ai-summary-resize-handle"
      role="separator"
      aria-orientation="horizontal"
      aria-label="첨부 파일 AI 정리 창 높이 조절"
      tabIndex={0}
      title="위아래로 드래그해 높이를 조절합니다. 더블클릭하면 기본 높이로 돌아갑니다."
      onPointerDown={beginPanelResize}
      onPointerMove={movePanelResize}
      onPointerUp={endPanelResize}
      onPointerCancel={endPanelResize}
      onDoubleClick={resetPanelHeight}
      onKeyDown={resizePanelFromKeyboard}
    ><span></span><em>높이 조절</em><span></span></div>}
  </div>
}


const UI_LAYOUT_TEMPLATES=[
  {id:'headless_agent',name:'UI 없음 / Headless Agent',category:'기타',description:'화면 없이 API·MCP·배치·Agent Runtime만 생성',app_type:'headless',navigation:'none',main_layout:'none',theme:'auto',components:['api','agent','tools'],header:false,sidebar:false,footer:false,user_menu:false,sidebar_collapsible:false,responsive:false,enabled:false,keywords:['ui 없음','화면 없음','headless','api only','배치']},
  {id:'ai_commerce_split',name:'AI Commerce Split',category:'쇼핑/검색',description:'AI 상담과 상품 검색 결과를 좌우로 나누는 웹앱',app_type:'web_app',navigation:'header_sidebar',main_layout:'two_column',theme:'light',components:['search','product_grid','ai_chat','cart','order_history'],header:true,sidebar:true,footer:false,user_menu:true,sidebar_collapsible:true,keywords:['상품','쇼핑','주문','추천','검색','commerce']},
  {id:'commerce_dashboard',name:'Commerce Dashboard',category:'쇼핑/검색',description:'KPI·상품·주문을 한 화면에 배치한 대시보드',app_type:'dashboard',navigation:'header_sidebar',main_layout:'dashboard',theme:'light',components:['kpi','search','product_grid','orders','chart'],header:true,sidebar:true,footer:false,user_menu:true,sidebar_collapsible:true,keywords:['상품','쇼핑','주문','매출','대시보드']},
  {id:'commerce_catalog',name:'Commerce Catalog',category:'쇼핑/검색',description:'상단 검색과 필터 사이드바, 상품 카드 중심 레이아웃',app_type:'web_app',navigation:'header_sidebar',main_layout:'grid',theme:'light',components:['search','filter','product_grid','cart'],header:true,sidebar:true,footer:true,user_menu:true,sidebar_collapsible:false,keywords:['상품','검색','catalog','e-commerce']},
  {id:'ai_chat_workspace',name:'AI Chat Workspace',category:'AI/Chat',description:'좌측 대화 목록과 중앙 AI 상담, 우측 Context 패널',app_type:'chat',navigation:'left',main_layout:'three_column',theme:'dark',components:['conversation_list','ai_chat','context_panel','attachments'],header:true,sidebar:true,footer:false,user_menu:true,sidebar_collapsible:true,keywords:['상담','채팅','chat','agent','rag']},
  {id:'rag_knowledge',name:'RAG Knowledge Workspace',category:'AI/Chat',description:'문서·검색·답변 Context를 함께 보는 RAG 작업공간',app_type:'web_app',navigation:'header_sidebar',main_layout:'two_column',theme:'dark',components:['file_list','search','ai_chat','sources','context_panel'],header:true,sidebar:true,footer:false,user_menu:true,sidebar_collapsible:true,keywords:['rag','문서','파일','벡터','지식']},
  {id:'mcp_console',name:'MCP Tool Console',category:'AI/Chat',description:'Agent, MCP Server, Tool 실행 상태를 관리하는 콘솔',app_type:'admin',navigation:'left',main_layout:'dashboard',theme:'dark',components:['agent_status','tool_list','mcp_servers','logs','terminal'],header:true,sidebar:true,footer:false,user_menu:true,sidebar_collapsible:true,keywords:['mcp','tool','server','도구']},
  {id:'saas_dashboard',name:'SaaS Dashboard',category:'대시보드',description:'좌측 메뉴 + KPI + Chart + Table의 표준 웹앱',app_type:'dashboard',navigation:'header_sidebar',main_layout:'dashboard',theme:'light',components:['kpi','chart','table','activity'],header:true,sidebar:true,footer:false,user_menu:true,sidebar_collapsible:true,keywords:['대시보드','dashboard','analytics']},
  {id:'analytics_dashboard',name:'Analytics Dashboard',category:'대시보드',description:'차트와 필터를 강조한 데이터 분석 화면',app_type:'dashboard',navigation:'header_sidebar',main_layout:'dashboard',theme:'light',components:['filter','kpi','chart','table'],header:true,sidebar:true,footer:false,user_menu:true,sidebar_collapsible:true,keywords:['분석','통계','매출','analytics','chart']},
  {id:'admin_crud',name:'Admin CRUD',category:'관리자',description:'리스트·상세·편집 화면을 빠르게 오가는 관리자 UI',app_type:'admin',navigation:'header_sidebar',main_layout:'two_column',theme:'light',components:['menu','table','detail','form','activity'],header:true,sidebar:true,footer:false,user_menu:true,sidebar_collapsible:true,keywords:['관리자','crud','관리','admin']},
  {id:'search_portal',name:'Search Portal',category:'웹앱',description:'큰 검색창과 필터, 결과 리스트를 중심으로 한 포털',app_type:'web_app',navigation:'top',main_layout:'one_column',theme:'light',components:['search','filter','result_list','pagination'],header:true,sidebar:false,footer:true,user_menu:true,sidebar_collapsible:false,keywords:['검색','search','portal']},
  {id:'workspace_sidebar',name:'Workspace Sidebar',category:'웹앱',description:'접을 수 있는 좌측 메뉴와 넓은 작업영역',app_type:'web_app',navigation:'left',main_layout:'one_column',theme:'dark',components:['sidebar','workspace','toolbar','activity'],header:true,sidebar:true,footer:false,user_menu:true,sidebar_collapsible:true,keywords:['workspace','코드','파일','작업']},
  {id:'topnav_webapp',name:'Top Navigation Web App',category:'웹앱',description:'상위 메뉴 중심의 넓고 단순한 웹앱',app_type:'web_app',navigation:'top',main_layout:'one_column',theme:'light',components:['topnav','content','cards','table'],header:true,sidebar:false,footer:true,user_menu:true,sidebar_collapsible:false,keywords:['웹앱','web app','상단 메뉴']},
  {id:'landing_app',name:'Landing + App',category:'웹사이트',description:'소개 Landing과 실제 앱 진입을 함께 제공',app_type:'website',navigation:'top',main_layout:'landing',theme:'light',components:['hero','features','cta','app_preview','footer'],header:true,sidebar:false,footer:true,user_menu:false,sidebar_collapsible:false,keywords:['랜딩','소개','landing','website']},
  {id:'mobile_responsive',name:'Mobile Responsive',category:'모바일',description:'모바일 우선 Card/Grid 구조의 반응형 웹앱',app_type:'mobile_web',navigation:'top',main_layout:'mobile',theme:'light',components:['mobile_nav','cards','search','bottom_actions'],header:true,sidebar:false,footer:false,user_menu:true,sidebar_collapsible:false,keywords:['모바일','mobile','responsive']},
  {id:'monitoring_console',name:'Monitoring Console',category:'대시보드',description:'상태 카드·로그·실시간 이벤트를 집중 표시',app_type:'dashboard',navigation:'left',main_layout:'dashboard',theme:'dark',components:['status','metrics','logs','events','table'],header:true,sidebar:true,footer:false,user_menu:true,sidebar_collapsible:true,keywords:['모니터링','로그','status','monitoring']},
]

const uiLayoutTemplateById=(id)=>UI_LAYOUT_TEMPLATES.find(item=>item.id===id)||UI_LAYOUT_TEMPLATES[0]

// v5.384: Layout는 화면 모양만 고르는 값이 아니라, 화면을 떠났다가 돌아왔을 때
// 실행 중 Agent와 사용자의 작업 Context를 어떻게 복원할지도 함께 정의합니다.
// Agent Runtime 자체는 UI lifecycle과 분리되어 항상 유지되며 사용자가 끌 수 없습니다.
const UI_LAYOUT_RUNTIME_BASE=Object.freeze({
  agent_runtime_persistent:true,
  restore_screen_state:true,
  restore_scroll_position:true,
  restore_draft_input:false,
  restore_selection_state:true,
  show_running_tasks:true,
  runtime_status_position:'top_statusbar',
  screen_restore_mode:'auto',
  notify_agent_complete:true,
  notify_agent_failure:true,
  run_item_navigate:true,
  event_stream_auto_reconnect:true,
  event_stream_resync:true,
})
const uiLayoutRuntimeDefaults=(template={})=>{
  const base={...UI_LAYOUT_RUNTIME_BASE}
  if(template.id==='headless_agent'){
    return {...base,restore_screen_state:false,restore_scroll_position:false,restore_draft_input:false,restore_selection_state:false,screen_restore_mode:'state_rehydrate'}
  }
  if(['ai_chat_workspace','rag_knowledge'].includes(template.id)){
    return {...base,restore_draft_input:true,restore_selection_state:true,screen_restore_mode:'auto'}
  }
  if(template.id==='mcp_console'||template.id==='monitoring_console'||template.app_type==='dashboard'){
    return {...base,restore_draft_input:false,restore_selection_state:true,screen_restore_mode:'auto'}
  }
  if(template.app_type==='mobile_web'){
    return {...base,restore_draft_input:true,restore_selection_state:true,screen_restore_mode:'auto'}
  }
  if(template.app_type==='website'){
    return {...base,restore_draft_input:false,restore_selection_state:false,screen_restore_mode:'state_rehydrate'}
  }
  return base
}
const normalizeUILayoutConfig=(template,value={})=>({
  ...template,
  ...uiLayoutRuntimeDefaults(template),
  ...(value&&typeof value==='object'?value:{}),
  // 플랫폼 고정 정책: 메뉴/탭 이동은 실행 중 Agent를 중단시키지 않습니다.
  agent_runtime_persistent:true,
  event_stream_auto_reconnect:true,
  event_stream_resync:true,
})
const uiThemeSelectValue=(config={})=>config?.theme==='custom'&&config?.theme_id?`custom:${config.theme_id}`:(config?.theme||'light')
const uiThemeColors=(config={})=>config?.theme==='custom'?(config?.theme_tokens?.colors||{}):{}
const uiThemeIsDark=(config={})=>{
  if(config?.theme==='dark') return true
  if(config?.theme!=='custom') return false
  const value=String(uiThemeColors(config).background||'#ffffff').replace('#','')
  if(!/^[0-9a-fA-F]{6}$/.test(value)) return false
  const r=parseInt(value.slice(0,2),16),g=parseInt(value.slice(2,4),16),b=parseInt(value.slice(4,6),16)
  return ((.2126*r+.7152*g+.0722*b)/255)<.48
}
const uiThemeWireframeStyle=(config={})=>{
  if(config?.theme!=='custom') return undefined
  const colors=uiThemeColors(config)
  return {
    '--ui-theme-primary':colors.primary||'#2563eb',
    '--ui-theme-background':colors.background||'#f8fafc',
    '--ui-theme-surface':colors.surface||'#ffffff',
    '--ui-theme-text':colors.textPrimary||'#0f172a',
    '--ui-theme-border':colors.border||'#dbe4ee',
    '--ui-theme-secondary':colors.secondary||colors.textSecondary||'#64748b',
  }
}
const buildImageThemeRules=(tokens={})=>{
  const colors=tokens.colors||{},radius=tokens.radius||{}
  return {
    component_rules:{
      button:{background:colors.primary||'#2563eb',color:'#ffffff',radius:radius.button??8},
      card:{background:colors.surface||'#ffffff',border:colors.border||'#dbe4ee',radius:radius.card??12},
      input:{background:colors.surface||'#ffffff',border:colors.border||'#dbe4ee',radius:radius.input??8},
      header:{background:colors.surface||'#ffffff',accent:colors.primary||'#2563eb'},
      sidebar:{background:colors.background||'#f8fafc',active:colors.primary||'#2563eb'},
    },
    layout_rules:{headerHeight:64,sidebarWidth:240,contentMaxWidth:1440,contentGap:20},
  }
}
const extractThemeTokensFromImage=async(file)=>{
  if(!file) throw new Error('화면 캡처 이미지를 선택하세요.')
  if(file.size>25*1024*1024) throw new Error('Theme 분석 이미지는 25MB 이하 파일을 사용하세요.')
  const imageUrl=URL.createObjectURL(file)
  try{
    const image=await new Promise((resolve,reject)=>{
      const img=new Image()
      img.onload=()=>resolve(img)
      img.onerror=()=>reject(new Error('이미지를 읽을 수 없습니다.'))
      img.src=imageUrl
    })
    const scale=Math.min(1,180/Math.max(image.naturalWidth||1,image.naturalHeight||1))
    const width=Math.max(1,Math.round((image.naturalWidth||1)*scale))
    const height=Math.max(1,Math.round((image.naturalHeight||1)*scale))
    const canvas=document.createElement('canvas'); canvas.width=width; canvas.height=height
    const ctx=canvas.getContext('2d',{willReadFrequently:true})
    if(!ctx) throw new Error('브라우저 Canvas를 사용할 수 없어 이미지를 분석하지 못했습니다.')
    ctx.drawImage(image,0,0,width,height)
    const data=ctx.getImageData(0,0,width,height).data
    const buckets=new Map()
    for(let i=0;i<data.length;i+=16){
      if(data[i+3]<180) continue
      const r=Math.round(data[i]/32)*32,g=Math.round(data[i+1]/32)*32,b=Math.round(data[i+2]/32)*32
      const key=[Math.min(255,r),Math.min(255,g),Math.min(255,b)].join(',')
      buckets.set(key,(buckets.get(key)||0)+1)
    }
    const palette=[...buckets.entries()].sort((a,b)=>b[1]-a[1]).slice(0,18).map(([key])=>{
      const [r,g,b]=key.split(',').map(Number)
      return '#'+[r,g,b].map(v=>v.toString(16).padStart(2,'0')).join('')
    })
    const rgb=(hex)=>[parseInt(hex.slice(1,3),16),parseInt(hex.slice(3,5),16),parseInt(hex.slice(5,7),16)]
    const lum=(hex)=>{const [r,g,b]=rgb(hex);return(.2126*r+.7152*g+.0722*b)/255}
    const sat=(hex)=>{const a=rgb(hex).map(v=>v/255),hi=Math.max(...a),lo=Math.min(...a);return hi===lo?0:(hi-lo)/Math.max(hi,.001)}
    const list=palette.length?palette:['#2563eb','#f8fafc','#ffffff','#0f172a','#dbe4ee']
    const darkest=[...list].sort((a,b)=>lum(a)-lum(b))[0]
    const lightest=[...list].sort((a,b)=>lum(b)-lum(a))[0]
    const saturated=list.filter(c=>lum(c)>.12&&lum(c)<.92&&sat(c)>=.28).sort((a,b)=>sat(b)-sat(a))
    const primary=saturated[0]||list[0]
    const backgrounds=list.filter(c=>lum(c)>=.86)
    const background=backgrounds[0]||lightest
    const border=list.find(c=>lum(c)>=.62&&lum(c)<=.92&&sat(c)<.25)||'#dbe4ee'
    const secondary=list.find(c=>lum(c)>=.18&&lum(c)<=.55)||'#475569'
    const tokens={
      colors:{primary,secondary,background,surface:lightest,textPrimary:darkest,textSecondary:secondary,border,success:'#16a34a',danger:'#dc2626'},
      typography:{fontFamily:"system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",headingWeight:700,bodyWeight:400},
      radius:{button:8,card:12,input:8},shadow:{card:'0 8px 24px rgba(15,23,42,.10)'},spacing:{unit:4,density:'comfortable'}
    }
    return {tokens,preview_colors:list.slice(0,6),...buildImageThemeRules(tokens)}
  }finally{ URL.revokeObjectURL(imageUrl) }
}

const uiLayoutSummary=(value)=>{
  if(!value?.template_id) return ''
  const template=uiLayoutTemplateById(value.template_id)
  if(value?.enabled===false||value?.template_id==='headless_agent') return 'UI 없음 · Headless Agent · Agent Runtime 유지'
  const nav={header_sidebar:'상단+좌측 메뉴',left:'좌측 메뉴',top:'상단 메뉴',none:'메뉴 없음'}[value.navigation]||value.navigation||''
  const themeLabel=value.theme==='custom'?(value.theme_name||'Custom Theme'):(value.theme==='dark'?'Dark':value.theme==='auto'?'Auto':'Light')
  const parts=[template?.name||value.template_id,nav,value.footer?'Footer':'',value.user_menu?'사용자 메뉴':'',themeLabel,value.agent_runtime_persistent!==false?'Agent 실행 유지':''].filter(Boolean)
  return parts.join(' · ')
}

function UILayoutWireframe({config={},compact=false}){
  const template=uiLayoutTemplateById(config.template_id)
  const merged={...template,...config}
  const components=Array.isArray(merged.components)?merged.components:[]
  const hasSidebar=Boolean(merged.sidebar)
  const hasHeader=Boolean(merged.header)
  const hasFooter=Boolean(merged.footer)
  const userMenu=Boolean(merged.user_menu)
  const layout=merged.main_layout||'one_column'
  const cards=Math.min(compact?4:6,Math.max(3,components.length||4))
  const customTheme=merged.theme==='custom'
  return <div style={uiThemeWireframeStyle(merged)} className={`ui-layout-wireframe ${customTheme?'custom':uiThemeIsDark(merged)?'dark':'light'} ${compact?'compact':''}`}>
    {hasHeader&&<div className="ui-layout-wf-header"><i></i><div className="ui-layout-wf-nav"><span></span><span></span><span></span></div>{userMenu&&<b></b>}</div>}
    <div className="ui-layout-wf-body">
      {hasSidebar&&<div className="ui-layout-wf-sidebar"><i></i><i></i><i></i><i></i><i></i></div>}
      <div className={`ui-layout-wf-main ${layout}`}>
        <div className="ui-layout-wf-search"></div>
        <div className="ui-layout-wf-kpis"><span></span><span></span><span></span></div>
        <div className="ui-layout-wf-content">
          {Array.from({length:cards}).map((_,index)=><span key={index}></span>)}
        </div>
      </div>
      {layout==='three_column'&&<div className="ui-layout-wf-context"><span></span><span></span><span></span></div>}
    </div>
    {hasFooter&&<div className="ui-layout-wf-footer"><span></span><span></span><span></span></div>}
  </div>
}

function UILayoutTemplateGallery({open,value,onClose,onApply,purposeText=''}){
  const currentTemplate=uiLayoutTemplateById(value?.template_id)
  const [selectedId,setSelectedId]=useState(value?.template_id||currentTemplate.id)
  const [category,setCategory]=useState('추천')
  const [draft,setDraft]=useState(()=>normalizeUILayoutConfig(currentTemplate,{...value,template_id:value?.template_id||currentTemplate.id}))
  const [customThemes,setCustomThemes]=useState([])
  const [frontendThemeTargets,setFrontendThemeTargets]=useState([])
  const [frontendThemeListOpen,setFrontendThemeListOpen]=useState(false)
  const [themeImportOpen,setThemeImportOpen]=useState(false)
  const [themeImportMode,setThemeImportMode]=useState('url')
  const [themeImportName,setThemeImportName]=useState('')
  const [themeImportUrl,setThemeImportUrl]=useState('')
  const [themeImportFile,setThemeImportFile]=useState(null)
  const [themeImportPreview,setThemeImportPreview]=useState(null)
  const [themeImportBusy,setThemeImportBusy]=useState(false)
  const [themeImportError,setThemeImportError]=useState('')
  const [themeBackendWarning,setThemeBackendWarning]=useState('')
  useEffect(()=>{
    if(!open) return
    const template=uiLayoutTemplateById(value?.template_id)
    const next=normalizeUILayoutConfig(template,{...value,template_id:value?.template_id||template.id})
    setSelectedId(next.template_id)
    setDraft(next)
  },[open,value?.template_id])
  useEffect(()=>{
    if(!open) return
    let alive=true
    Promise.allSettled([api('/ui-themes'),api('/ui-themes/frontend-targets')]).then(results=>{
      if(!alive) return
      const themeResult=results[0]?.status==='fulfilled'?results[0].value:null
      const frontendResult=results[1]?.status==='fulfilled'?results[1].value:null
      setCustomThemes(Array.isArray(themeResult?.themes)?themeResult.themes:[])
      setFrontendThemeTargets(Array.isArray(frontendResult?.targets)?frontendResult.targets:[])
      const rejected=results.find(item=>item?.status==='rejected')
      setThemeBackendWarning(rejected?String(rejected.reason?.message||'Theme Backend API 연결을 확인할 수 없습니다.'):'')
    }).catch(error=>{if(alive){setCustomThemes([]);setFrontendThemeTargets([]);setThemeBackendWarning(String(error?.message||error))}})
    return()=>{alive=false}
  },[open])
  if(!open) return null
  const purpose=String(purposeText||'').toLowerCase()
  const scored=UI_LAYOUT_TEMPLATES.map(template=>({
    template,
    score:(template.keywords||[]).reduce((sum,key)=>sum+(purpose.includes(String(key).toLowerCase())?2:0),0)
      +(value?.app_type&&template.app_type===value.app_type?1:0)
  })).sort((a,b)=>b.score-a.score)
  const recommendedIds=new Set(scored.slice(0,5).map(item=>item.template.id))
  const categories=['추천','웹앱','대시보드','쇼핑/검색','AI/Chat','관리자','웹사이트','모바일','기타']
  const visible=UI_LAYOUT_TEMPLATES.filter(template=>category==='추천'?recommendedIds.has(template.id):template.category===category)
  const choose=(template)=>{
    setSelectedId(template.id)
    setDraft(normalizeUILayoutConfig(template,{template_id:template.id}))
  }
  const patch=(next)=>setDraft(prev=>({...prev,...next}))
  const selectThemeValue=(raw)=>{
    const value=String(raw||'light')
    if(value.startsWith('custom:')){
      const themeId=Number(value.slice(7))
      const theme=customThemes.find(item=>Number(item.id)===themeId)
      if(theme) patch({theme:'custom',theme_id:theme.id,theme_name:theme.name,theme_tokens:theme.tokens||{},theme_component_rules:theme.component_rules||{},theme_layout_rules:theme.layout_rules||{},theme_source_type:theme.source_type||'',theme_source_url:theme.source_url||''})
      return
    }
    patch({theme:value,theme_id:null,theme_name:'',theme_tokens:{},theme_component_rules:{},theme_layout_rules:{},theme_source_type:'',theme_source_url:''})
  }
  const importTheme=async()=>{
    setThemeImportBusy(true); setThemeImportError('')
    try{
      const name=String(themeImportName||'').trim()
      if(!name) throw new Error('Theme 이름을 입력하세요.')
      let result
      if(themeImportMode==='url'){
        const url=String(themeImportUrl||'').trim()
        if(!url) throw new Error('웹사이트 URL을 입력하세요.')
        result=await api('/ui-themes/import-url',{method:'POST',body:JSON.stringify({name,url,scope:'GLOBAL'})})
      }else{
        if(!themeImportFile) throw new Error('화면 캡처 이미지를 선택하세요.')
        const analysis=themeImportPreview||await extractThemeTokensFromImage(themeImportFile)
        result=await api('/ui-themes/import-image',{method:'POST',body:JSON.stringify({name,file_name:themeImportFile.name,tokens:analysis.tokens,component_rules:analysis.component_rules,layout_rules:analysis.layout_rules,preview_colors:analysis.preview_colors,scope:'GLOBAL'})})
      }
      const theme=result?.theme
      if(!theme) throw new Error('Theme 저장 결과를 확인할 수 없습니다.')
      setCustomThemes(prev=>[theme,...prev.filter(item=>Number(item.id)!==Number(theme.id))])
      patch({theme:'custom',theme_id:theme.id,theme_name:theme.name,theme_tokens:theme.tokens||{},theme_component_rules:theme.component_rules||{},theme_layout_rules:theme.layout_rules||{},theme_source_type:theme.source_type||'',theme_source_url:theme.source_url||''})
      setThemeImportOpen(false); setThemeImportName(''); setThemeImportUrl(''); setThemeImportFile(null); setThemeImportPreview(null)
    }catch(error){setThemeImportError(String(error?.message||error))}finally{setThemeImportBusy(false)}
  }
  const chooseThemeImage=async(file)=>{
    setThemeImportFile(file||null); setThemeImportPreview(null); setThemeImportError('')
    if(!file) return
    if(!String(file.type||'').startsWith('image/')){setThemeImportError('이미지 파일을 선택하세요.');return}
    try{setThemeImportPreview(await extractThemeTokensFromImage(file))}catch(error){setThemeImportError(String(error?.message||error))}
  }
  const deleteCustomTheme=async(theme)=>{
    if(!theme?.id) return
    if(!window.confirm(`Theme '${theme.name}'을(를) 삭제하시겠습니까?`)) return
    try{
      await api(`/ui-themes/${theme.id}`,{method:'DELETE'})
      setCustomThemes(prev=>prev.filter(item=>Number(item.id)!==Number(theme.id)))
      if(Number(draft.theme_id)===Number(theme.id)) selectThemeValue('auto')
    }catch(error){setThemeImportError(String(error?.message||error))}
  }
  const selected=uiLayoutTemplateById(selectedId)
  return <div className="ui-layout-gallery-backdrop" role="dialog" aria-modal="true" aria-label="UI Layout Template Gallery">
    <div className="ui-layout-gallery-modal">
      <div className="ui-layout-gallery-head">
        <div><span>NEW AGENT · UI / LAYOUT</span><strong>레이아웃 템플릿 갤러리</strong><small>화면 구조와 함께 메뉴 이동 후 상태 복원, 실행 중 Agent 표시, 완료/실패 알림 정책을 설정합니다.</small></div>
        <button type="button" onClick={onClose}>×</button>
      </div>
      <div className="ui-layout-gallery-toolbar">
        {categories.map(item=><button key={item} type="button" className={category===item?'active':''} onClick={()=>setCategory(item)}>{item}</button>)}
      </div>
      <div className="ui-layout-gallery-body">
        <div className="ui-layout-gallery-grid">
          {visible.map(template=><button type="button" key={template.id} className={`ui-layout-template-card ${selectedId===template.id?'selected':''}`} onClick={()=>choose(template)}>
            <UILayoutWireframe config={{...template,template_id:template.id}} compact={true}/>
            <div><strong>{template.name}</strong><small>{template.description}</small></div>
            {recommendedIds.has(template.id)&&<span className="ui-layout-recommended">추천</span>}
          </button>)}
        </div>
        <aside className="ui-layout-config-panel">
          <div className="ui-layout-config-preview"><UILayoutWireframe config={draft}/></div>
          <div className="ui-layout-config-title"><strong>{selected.name}</strong><small>{selected.description}</small></div>

          <section className="ui-layout-config-section">
            <div className="ui-layout-config-section-head"><strong>UI 구성</strong><small>화면에 표시할 공통 영역</small></div>
            <div className="ui-layout-toggle-grid">
              <label><input type="checkbox" checked={Boolean(draft.header)} onChange={e=>patch({header:e.target.checked})}/>상단 Header</label>
              <label><input type="checkbox" checked={Boolean(draft.sidebar)} onChange={e=>patch({sidebar:e.target.checked,navigation:e.target.checked?(draft.header?'header_sidebar':'left'):(draft.header?'top':'none')})}/>좌측 메뉴</label>
              <label><input type="checkbox" checked={Boolean(draft.sidebar_collapsible)} disabled={!draft.sidebar} onChange={e=>patch({sidebar_collapsible:e.target.checked})}/>Sidebar 접기</label>
              <label><input type="checkbox" checked={Boolean(draft.footer)} onChange={e=>patch({footer:e.target.checked})}/>Footer</label>
              <label><input type="checkbox" checked={Boolean(draft.user_menu)} onChange={e=>patch({user_menu:e.target.checked})}/>사용자 메뉴</label>
              <label><input type="checkbox" checked={draft.responsive!==false} onChange={e=>patch({responsive:e.target.checked})}/>반응형</label>
            </div>
          </section>

          <section className="ui-layout-config-section">
            <div className="ui-layout-config-section-head"><strong>레이아웃</strong><small>화면 배치와 Theme</small></div>
            <label className="ui-layout-select-field"><span>Main Layout</span><select value={draft.main_layout||'one_column'} onChange={e=>patch({main_layout:e.target.value})}><option value="one_column">1 Column</option><option value="two_column">2 Column</option><option value="three_column">3 Column</option><option value="grid">Card Grid</option><option value="dashboard">Dashboard</option><option value="landing">Landing</option><option value="mobile">Mobile First</option></select></label>
            <div className="ui-layout-theme-field">
              <label className="ui-layout-select-field"><span>Theme</span><select value={uiThemeSelectValue(draft)} onChange={e=>selectThemeValue(e.target.value)}><option value="light">Light</option><option value="dark">Dark</option><option value="auto">Auto</option>{customThemes.length>0&&<optgroup label="사용자 Theme">{customThemes.map(theme=><option key={theme.id} value={`custom:${theme.id}`}>{theme.name}</option>)}</optgroup>}</select></label>
              <button type="button" className="ui-layout-theme-import-button" onClick={()=>{setThemeImportOpen(value=>!value);setThemeImportError('')}}>+ 스타일 가져오기</button>
            </div>
            <div className="ui-layout-theme-target-summary">
              <div>
                <strong>Frontend Theme 적용</strong>
                <small>공통 Design Token을 선택한 Frontend/스타일 방식으로 자동 변환합니다.</small>
              </div>
              <div className="ui-layout-theme-target-actions">
                <span>{frontendThemeTargets.length||'–'} Adapters</span>
                <button type="button" onClick={()=>setFrontendThemeListOpen(true)}>지원 목록 보기</button>
              </div>
            </div>
            {themeBackendWarning&&<div className="ui-layout-theme-backend-warning"><b>Theme Backend 확인 필요</b><span>{themeBackendWarning}</span><small>SYSTEM_ADMIN에서 Backend까지 완전히 재시작하면 Frontend/Backend 버전 불일치도 함께 해소됩니다.</small></div>}
            {draft.theme==='custom'&&<div className="ui-layout-selected-theme">
              <div className="ui-layout-theme-palette">{(draft.theme_tokens?.colors?Object.values(draft.theme_tokens.colors).slice(0,5):[]).map((color,index)=><i key={`${color}-${index}`} style={{background:String(color)}}></i>)}</div>
              <div><strong>{draft.theme_name||'Custom Theme'}</strong><small>{draft.theme_source_type==='URL'?'URL 분석 Theme':draft.theme_source_type==='IMAGE'?'화면 캡처 Theme':'사용자 Theme'} · 선택된 Frontend 기술의 native Theme 방식으로 자동 변환 적용</small></div>
              <button type="button" onClick={()=>deleteCustomTheme(customThemes.find(item=>Number(item.id)===Number(draft.theme_id)))}>삭제</button>
            </div>}
            {themeImportOpen&&<div className="ui-layout-theme-import-panel">
              <div className="ui-layout-theme-import-tabs"><button type="button" className={themeImportMode==='url'?'active':''} onClick={()=>{setThemeImportMode('url');setThemeImportError('')}}>웹사이트 URL</button><button type="button" className={themeImportMode==='image'?'active':''} onClick={()=>{setThemeImportMode('image');setThemeImportError('')}}>화면 캡처 이미지</button></div>
              <label><span>Theme 이름</span><input value={themeImportName} onChange={e=>setThemeImportName(e.target.value)} placeholder="예: 쇼핑몰 A 스타일"/></label>
              {themeImportMode==='url'
                ?<label><span>URL</span><input value={themeImportUrl} onChange={e=>setThemeImportUrl(e.target.value)} placeholder="https://example.com"/></label>
                :<label className="ui-layout-theme-file"><span>화면 캡처</span><input type="file" accept="image/*" onChange={e=>chooseThemeImage(e.target.files?.[0]||null)}/></label>}
              {themeImportPreview&&<div className="ui-layout-theme-import-palette">{(themeImportPreview.preview_colors||[]).map((color,index)=><i key={`${color}-${index}`} style={{background:color}} title={color}></i>)}</div>}
              <small className="ui-layout-theme-import-help">URL은 HTML/CSS의 색상·폰트·Radius·Shadow를 분석합니다. 캡처 이미지는 색상 중심으로 Design Token을 추정합니다. 저장된 Theme은 등록된 Frontend/스타일 Adapter에 맞게 자동 변환되고, 목록에 없는 Frontend도 Generic Adapter를 사용합니다. 지원 목록은 Theme 바로 아래의 ‘지원 Frontend/스타일 목록 보기’에서 확인할 수 있습니다. 로고·문구·이미지·고유 콘텐츠는 복제하지 않습니다.</small>
              {customThemes.length>0&&<div className="ui-layout-theme-library"><strong>저장된 Theme</strong>{customThemes.slice(0,8).map(theme=><div key={theme.id}><span className="ui-layout-theme-library-palette">{(theme.preview_colors||[]).slice(0,4).map((color,index)=><i key={`${color}-${index}`} style={{background:color}}></i>)}</span><b>{theme.name}</b><em>{theme.source_type==='URL'?'URL':theme.source_type==='IMAGE'?'이미지':'Custom'}</em><button type="button" onClick={()=>{selectThemeValue(`custom:${theme.id}`);setThemeImportOpen(false)}}>적용</button><button type="button" className="danger" onClick={()=>deleteCustomTheme(theme)}>삭제</button></div>)}</div>}
              {themeImportError&&<div className="ui-layout-theme-import-error">{themeImportError}</div>}
              <div className="ui-layout-theme-import-actions"><button type="button" onClick={()=>setThemeImportOpen(false)}>취소</button><button type="button" className="primary" disabled={themeImportBusy} onClick={importTheme}>{themeImportBusy?'분석·저장 중...':'분석 후 Theme 저장'}</button></div>
            </div>}
            <label className="ui-layout-select-field"><span>사용자 메뉴 위치</span><select value={draft.user_menu_position||'header_right'} disabled={!draft.user_menu} onChange={e=>patch({user_menu_position:e.target.value})}><option value="header_right">상단 우측</option><option value="sidebar_bottom">Sidebar 하단</option><option value="profile_page">Profile 페이지</option></select></label>
          </section>

          <section className="ui-layout-config-section runtime">
            <div className="ui-layout-config-section-head"><strong>실행 및 상태 유지</strong><small>다른 메뉴를 사용해도 실행과 작업 Context를 이어갑니다.</small></div>
            <div className="ui-layout-runtime-lock">
              <span aria-hidden="true">🔒</span>
              <div><strong>메뉴 이동 시 Agent 실행 유지</strong><small>UI lifecycle과 Agent Runtime을 분리하여 메뉴·탭 이동으로 실행을 중단하지 않습니다.</small></div>
              <em>항상 ON</em>
            </div>
            <div className="ui-layout-toggle-grid runtime">
              <label><input type="checkbox" checked={draft.restore_screen_state!==false} disabled={selectedId==='headless_agent'} onChange={e=>patch({restore_screen_state:e.target.checked})}/>이전 화면 상태 복원</label>
              <label><input type="checkbox" checked={draft.restore_scroll_position!==false} disabled={selectedId==='headless_agent'} onChange={e=>patch({restore_scroll_position:e.target.checked})}/>스크롤 위치 복원</label>
              <label><input type="checkbox" checked={Boolean(draft.restore_draft_input)} disabled={selectedId==='headless_agent'} onChange={e=>patch({restore_draft_input:e.target.checked})}/>입력 중 내용 복원</label>
              <label><input type="checkbox" checked={draft.restore_selection_state!==false} disabled={selectedId==='headless_agent'} onChange={e=>patch({restore_selection_state:e.target.checked})}/>선택/탭 상태 복원</label>
              <label><input type="checkbox" checked={draft.show_running_tasks!==false} onChange={e=>patch({show_running_tasks:e.target.checked})}/>실행 중 작업 표시</label>
            </div>
            <label className="ui-layout-select-field"><span>실행 상태 위치</span><select value={draft.runtime_status_position||'top_statusbar'} disabled={draft.show_running_tasks===false} onChange={e=>patch({runtime_status_position:e.target.value})}><option value="top_statusbar">상단 상태바</option><option value="sidebar">좌측 메뉴</option><option value="right_panel">우측 패널</option><option value="bottom_statusbar">하단 상태바</option><option value="floating_button">플로팅 버튼</option></select></label>
            <label className="ui-layout-select-field"><span>화면 유지 방식</span><select value={draft.screen_restore_mode||'auto'} disabled={selectedId==='headless_agent'} onChange={e=>patch({screen_restore_mode:e.target.value})}><option value="auto">자동 (권장)</option><option value="keep_alive">화면 유지 (Keep Alive)</option><option value="state_rehydrate">상태 저장 후 재생성</option></select></label>
            <div className="ui-layout-runtime-note"><b>자동 복구</b><span>WebSocket/SSE 재연결 · 현재 run 상태 재조회 · 누락 이벤트 재동기화는 플랫폼 기본 정책으로 적용됩니다.</span></div>
          </section>

          <section className="ui-layout-config-section">
            <div className="ui-layout-config-section-head"><strong>알림</strong><small>백그라운드 실행 결과를 놓치지 않도록 표시합니다.</small></div>
            <div className="ui-layout-toggle-grid">
              <label><input type="checkbox" checked={draft.notify_agent_complete!==false} onChange={e=>patch({notify_agent_complete:e.target.checked})}/>Agent 완료 알림</label>
              <label><input type="checkbox" checked={draft.notify_agent_failure!==false} onChange={e=>patch({notify_agent_failure:e.target.checked})}/>Agent 실패 알림</label>
              <label className="wide"><input type="checkbox" checked={draft.run_item_navigate!==false} onChange={e=>patch({run_item_navigate:e.target.checked})}/>실행 작업 클릭 시 해당 화면으로 이동</label>
            </div>
          </section>

          <div className="ui-layout-component-tags">{(draft.components||[]).map(item=><span key={item}>{item}</span>)}</div>
          <div className="ui-layout-config-actions"><button type="button" onClick={onClose}>취소</button><button type="button" className="primary" onClick={()=>onApply(normalizeUILayoutConfig(selected,{...draft,template_id:selectedId,selected_at:new Date().toISOString()}))}>이 레이아웃 사용</button></div>
        </aside>
      </div>

      {frontendThemeListOpen&&<div className="ui-layout-theme-target-modal-backdrop" onMouseDown={()=>setFrontendThemeListOpen(false)}>
        <div className="ui-layout-theme-target-modal" onMouseDown={event=>event.stopPropagation()}>
          <div className="ui-layout-theme-target-modal-head">
            <div>
              <span>THEME ADAPTER REGISTRY</span>
              <strong>지원 Frontend / 스타일 목록</strong>
              <small>Theme Design Token을 각 Frontend와 UI Framework에 맞는 방식으로 변환합니다.</small>
            </div>
            <button type="button" onClick={()=>setFrontendThemeListOpen(false)}>×</button>
          </div>
          <div className="ui-layout-theme-target-modal-stats">
            <b>{frontendThemeTargets.length}</b>
            <span>등록된 Adapter</span>
            <small>목록에 없는 기술은 Generic Theme Adapter로 처리합니다.</small>
          </div>
          <div className="ui-layout-theme-target-list modal-list">
            {frontendThemeTargets.length===0
              ?<div className="ui-layout-theme-target-empty">Frontend 목록을 불러오는 중이거나 Backend 연결을 확인할 수 없습니다.</div>
              :Array.from(new Set(frontendThemeTargets.map(item=>item.group||'기타'))).map(group=><div key={group} className="ui-layout-theme-target-group"><strong>{group}</strong><div>{frontendThemeTargets.filter(item=>(item.group||'기타')===group).map(item=><span key={item.id} title={item.strategy||''}><b>{item.label}</b><em>{item.language}</em></span>)}</div></div>)}
            <small className="ui-layout-theme-target-footnote">목록에 없는 Frontend도 Generic Theme Adapter를 사용해 같은 색상·타이포그래피·Radius·Shadow·Spacing 의미를 유지합니다.</small>
          </div>
        </div>
      </div>}
    </div>
  </div>
}

const protectInterviewAssistantAnswer=(value='')=>{
  const text=sanitizeInterviewDisplayText(value)
  if(!text) return text

  // Legacy v5.334~v5.336 drafts can contain an attachment body copied almost
  // verbatim by a local model. Some of those dumps were flattened into one
  // very long visual line, so do not rely only on line-start code markers.
  const lineCodeSignals=(text.match(/(?:^|\n)\s*(?:```|import\s+|from\s+\S+\s+import|def\s+|class\s+|SELECT\s+|CREATE\s+)/gim)||[]).length
  const inlineCodeSignals=(text.match(/\b(?:import|from|def|class|streamlit|langchain|psycopg|redis|pgvector|openai|pinecone|chromadb|faiss|select|create|insert|update|delete)\b/gi)||[]).length
  const hasLargeFence=/```(?:python|py|javascript|typescript|sql|json|bash|powershell)?/i.test(text)&&text.length>=1200
  const looksLikeFlattenedDump=text.length>=1800&&inlineCodeSignals>=12
  const looksLikeMultilineDump=text.length>=2200&&lineCodeSignals>=4

  if(hasLargeFence||looksLikeFlattenedDump||looksLikeMultilineDump){
    return '이전에 저장된 첨부 파일 원문/긴 코드 출력은 현재 인터뷰에서 제외했습니다. 참고 파일은 다시 선택하면 안전한 분석 Context로만 반영됩니다.\n\n현재 요구사항을 이어서 진행해 주세요.'
  }
  return text
}
const DEFAULT_WEB_BROWSER_ID='web-browser-fixed'
function SystemPage() {
  const [status,setStatus]=useState({})
  const [runtimeLoopStatus,setRuntimeLoopStatus]=useState(null)
  const [settings,setSettings]=useState({})
  const [tests,setTests]=useState({})
  const [message,setMessage]=useState('')
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const [pgvectorInstall,setPgvectorInstall]=useState(null)
  const [pgvectorInfo,setPgvectorInfo]=useState(null)
  const [pgPathCheck,setPgPathCheck]=useState(null)
  const [pgAdminUser,setPgAdminUser]=useState('postgres')
  const [pgAdminPassword,setPgAdminPassword]=useState('')
  const [agentDbName,setAgentDbName]=useState('theanova_agentstudio')
  const [agentDbUser,setAgentDbUser]=useState('theanova_agentstudio_app')
  const [agentDbPassword,setAgentDbPassword]=useState('')
  const [dbProvision,setDbProvision]=useState(null)
  const [ollamaInstall,setOllamaInstall]=useState(null)
  const [ollamaRuntime,setOllamaRuntime]=useState(null)
  const [ollamaRuntimeBusy,setOllamaRuntimeBusy]=useState(false)
  const [gpuRuntime,setGpuRuntime]=useState(null)
  const [gpuRuntimeBusy,setGpuRuntimeBusy]=useState(false)
  const [portInfo,setPortInfo]=useState(null)
  const [portCheckBusy,setPortCheckBusy]=useState(false)
  const [machineName,setMachineName]=useState('')
  const [machineNameBusy,setMachineNameBusy]=useState(false)
  const [databaseRuntime,setDatabaseRuntime]=useState(null)
  const [databaseProviderChoice,setDatabaseProviderChoice]=useState('local')
  const [supabaseRuntimeUrl,setSupabaseRuntimeUrl]=useState('')
  const [supabaseLanggraphRuntimeUrl,setSupabaseLanggraphRuntimeUrl]=useState('')
  const [supabaseRuntimeSchema,setSupabaseRuntimeSchema]=useState('theanova_agentstudio')
  const [databaseRuntimeBusy,setDatabaseRuntimeBusy]=useState(false)
  const [supabaseInfoSaveBusy,setSupabaseInfoSaveBusy]=useState(false)
  const [databaseRuntimeResult,setDatabaseRuntimeResult]=useState(null)
  const pgAdminPasswordRef=useRef(null)
  const agentDbPasswordRef=useRef(null)

  const readPgAdminPassword=()=>String(pgAdminPasswordRef.current?.value ?? pgAdminPassword ?? '')
  const readAgentDbPassword=()=>String(agentDbPasswordRef.current?.value ?? agentDbPassword ?? '')

  const refresh=async()=>{
    try{
      const [s,cfg]=await Promise.all([api('/system/status'),api('/settings')])
      setStatus(s); setSettings(cfg); setMachineName(cfg?._machine?.pending_pc_name||cfg?._machine?.pc_name||''); setError('')

      try{
        setOllamaRuntime(await api('/settings/ollama/runtime/status'))
      }catch{
        setOllamaRuntime(null)
      }

      try{
        setGpuRuntime(await api('/settings/gpu/runtime/status'))
      }catch{
        setGpuRuntime(null)
      }

      try{
        const dbRuntime=await api('/settings/database-runtime')
        setDatabaseRuntime(dbRuntime)
        setDatabaseProviderChoice(dbRuntime?.selected_provider||dbRuntime?.active_provider||'local')
        setSupabaseRuntimeSchema(String(dbRuntime?.supabase_schema||'theanova_agentstudio'))
      }catch{
        setDatabaseRuntime(null)
      }

      const backendPort=Number(cfg.AGENTSTUDIO_BACKEND_PORT||8000)
      const frontendPort=Number(cfg.AGENTSTUDIO_FRONTEND_PORT||5173)
      const currentFrontendPort=Number(window.location.port||5173)
      try{
        const ports=await api(
          `/system/ports/recommend?backend_port=${backendPort}&frontend_port=${frontendPort}&current_frontend_port=${currentFrontendPort}`
        )
        setPortInfo(ports)
      }catch{
        setPortInfo(null)
      }
    }catch(e){setError(String(e))}
  }

  useEffect(()=>{refresh()},[])

  const valueOf=(key)=>{
    const v=settings[key]
    if(v && typeof v==='object' && 'configured' in v) return ''
    return v ?? ''
  }

  const configured=(key)=>{
    const v=settings[key]
    return !!(v && typeof v==='object' && v.configured)
  }

  const setValue=(key,value)=>setSettings(p=>({...p,[key]:value}))

  const saveGroup=async(keys)=>{
    setBusy(true); setMessage(''); setError('')
    try{
      const values={}
      keys.forEach(k=>{ values[k]=valueOf(k) })
      const r=await api('/settings',{method:'POST',body:JSON.stringify({values})})
      setSettings(r.settings)
      if(keys.includes('DATABASE_URL')){
        const saved=r?.saved_bootstrap?.DATABASE_URL||''
        const target=(()=>{
          try{ const u=new URL(saved.replace('postgresql+asyncpg://','http://').replace('postgresql+psycopg://','http://').replace('postgresql://','http://')); return `${u.username}@${u.hostname}:${u.port||5432}${u.pathname}` }catch{return ''}
        })()
        setMessage(`${r.message||'DB 설정을 저장했습니다.'}${target?` 저장 확인: ${target}`:''}`)
      }else{
        setMessage(r.message)
      }
    }catch(e){setError(String(e))}
    finally{setBusy(false)}
  }

  const saveDatabaseEnv=async()=>{
    setBusy(true); setMessage(''); setError('')
    try{
      const payload={
        database_url:String(valueOf('DATABASE_URL')||'').trim(),
        langgraph_database_url:String(valueOf('LANGGRAPH_DATABASE_URL')||'').trim(),
        postgresql_root:String(valueOf('POSTGRESQL18_ROOT')||'').trim()
      }
      const r=await api('/settings/database-env',{method:'POST',body:JSON.stringify(payload)})
      // 응답도 DB가 아니라 backend/.env에서 재읽은 실제 저장값입니다.
      setSettings(prev=>({
        ...prev,
        DATABASE_URL:r?.saved?.DATABASE_URL ?? payload.database_url,
        LANGGRAPH_DATABASE_URL:r?.saved?.LANGGRAPH_DATABASE_URL ?? payload.langgraph_database_url,
        POSTGRESQL18_ROOT:r?.saved?.POSTGRESQL18_ROOT ?? payload.postgresql_root
      }))
      setMessage(`${r.message||'DB 연결 설정을 .env에 저장했습니다.'} 저장 위치: ${r.env_path||'backend/.env'}`)
    }catch(e){
      setError(String(e))
    }finally{setBusy(false)}
  }

  const saveSupabaseRuntimeInfo=async()=>{
    setSupabaseInfoSaveBusy(true); setMessage(''); setError(''); setDatabaseRuntimeResult(null)
    try{
      const r=await api('/settings/database-runtime/supabase/save',{
        method:'POST',
        body:JSON.stringify({
          database_url:String(supabaseRuntimeUrl||'').trim(),
          langgraph_database_url:String(supabaseLanggraphRuntimeUrl||'').trim(),
          schema:String(supabaseRuntimeSchema||'theanova_agentstudio').trim()
        })
      })
      setDatabaseRuntimeResult(r)
      setMessage(r?.message||'Supabase PostgreSQL 연결 정보를 저장했습니다.')
      // 비밀번호가 포함될 수 있는 URL 원문은 저장 성공 후 브라우저 입력 상태에서도 제거합니다.
      setSupabaseRuntimeUrl('')
      setSupabaseLanggraphRuntimeUrl('')
      setDatabaseRuntime(await api('/settings/database-runtime'))
    }catch(e){
      setError(String(e))
      setDatabaseRuntimeResult({ok:false,message:String(e)})
    }finally{
      setSupabaseInfoSaveBusy(false)
    }
  }

  const activateRuntimeDatabase=async()=>{
    setDatabaseRuntimeBusy(true); setMessage(''); setError(''); setDatabaseRuntimeResult(null)
    try{
      const payload={
        provider:databaseProviderChoice,
        supabase_database_url:String(supabaseRuntimeUrl||'').trim(),
        supabase_langgraph_database_url:String(supabaseLanggraphRuntimeUrl||'').trim(),
        supabase_db_schema:String(supabaseRuntimeSchema||'theanova_agentstudio').trim(),
        initialize_schema:databaseProviderChoice==='supabase'
      }
      const r=await api('/settings/database-runtime/activate',{method:'POST',body:JSON.stringify(payload)})
      setDatabaseRuntimeResult(r)
      setMessage(r?.message||'Runtime DB 전환을 완료했습니다.')
      const next=await api('/settings/database-runtime')
      setDatabaseRuntime(next)
      setDatabaseProviderChoice(next?.selected_provider||next?.active_provider||databaseProviderChoice)
      await refresh()
    }catch(e){
      setError(String(e))
      setDatabaseRuntimeResult({ok:false,message:String(e)})
    }finally{
      setDatabaseRuntimeBusy(false)
    }
  }

  const initializeSupabaseRuntimeSchema=async()=>{
    setDatabaseRuntimeBusy(true); setMessage(''); setError(''); setDatabaseRuntimeResult(null)
    try{
      const r=await api('/settings/database-runtime/supabase/initialize-schema',{
        method:'POST',
        body:JSON.stringify({
          database_url:String(supabaseRuntimeUrl||'').trim(),
          langgraph_database_url:String(supabaseLanggraphRuntimeUrl||'').trim(),
          schema:String(supabaseRuntimeSchema||'theanova_agentstudio').trim()
        })
      })
      setDatabaseRuntimeResult(r)
      setMessage(r?.message||'Supabase 스키마 준비/검증을 완료했습니다.')
      setDatabaseRuntime(await api('/settings/database-runtime'))
    }catch(e){
      setError(String(e))
      setDatabaseRuntimeResult({ok:false,message:String(e)})
    }finally{
      setDatabaseRuntimeBusy(false)
    }
  }

  const downloadSupabaseSchemaScript=()=>{
    const base=runtimeInfo().apiBase
    window.open(`${base}/settings/database-runtime/supabase/schema-script`,'_blank','noopener,noreferrer')
  }

  const saveMachineName=async()=>{
    const nextName=String(machineName||'').trim()
    if(!nextName){
      setError('PC 이름을 입력하세요.')
      return
    }
    setMachineNameBusy(true); setMessage(''); setError('')
    try{
      const r=await api('/settings/machine-name',{
        method:'POST',
        body:JSON.stringify({pc_name:nextName})
      })
      if(r?.settings) setSettings(r.settings)
      setMachineName(r?.pending_pc_name||r?.pc_name||r?.settings?._machine?.pending_pc_name||r?.settings?._machine?.pc_name||nextName)
      setMessage(r?.message||`PC 이름을 ${nextName}(으)로 저장했습니다.`)
    }catch(e){
      setError(String(e))
    }finally{
      setMachineNameBusy(false)
    }
  }

  const checkPortRecommendations=async()=>{
    setPortCheckBusy(true)
    setError('')
    try{
      const backendPort=Number(valueOf('AGENTSTUDIO_BACKEND_PORT')||8000)
      const frontendPort=Number(valueOf('AGENTSTUDIO_FRONTEND_PORT')||5173)

      if(!Number.isInteger(backendPort)||backendPort<1024||backendPort>65535){
        throw new Error('Backend 포트는 1024~65535 사이의 숫자를 입력하세요.')
      }
      if(!Number.isInteger(frontendPort)||frontendPort<1024||frontendPort>65535){
        throw new Error('Frontend 포트는 1024~65535 사이의 숫자를 입력하세요.')
      }

      const currentFrontendPort=Number(window.location.port||5173)
      const result=await api(
        `/system/ports/recommend?backend_port=${backendPort}&frontend_port=${frontendPort}&current_frontend_port=${currentFrontendPort}`
      )
      setPortInfo(result)
      return result
    }catch(e){
      setError(String(e))
      return null
    }finally{
      setPortCheckBusy(false)
    }
  }

  const applyRecommendedPorts=async()=>{
    const result=portInfo||await checkPortRecommendations()
    if(!result) return
    setValue('AGENTSTUDIO_BACKEND_PORT',String(result.backend?.recommended||8000))
    setValue('AGENTSTUDIO_FRONTEND_PORT',String(result.frontend?.recommended||5173))
    setMessage('추천 포트를 입력했습니다. 포트 설정 저장 후 SYSTEM_ADMIN.cmd를 다시 실행하면 적용됩니다.')
  }

  const savePortSettings=async()=>{
    const backendPort=Number(valueOf('AGENTSTUDIO_BACKEND_PORT')||8000)
    const frontendPort=Number(valueOf('AGENTSTUDIO_FRONTEND_PORT')||5173)
    if(backendPort===frontendPort){
      setError('Backend와 Frontend는 서로 다른 포트를 사용해야 합니다.')
      return
    }
    const result=await checkPortRecommendations()
    if(!result) return

    setBusy(true); setMessage(''); setError('')
    try{
      const r=await api('/settings',{
        method:'POST',
        body:JSON.stringify({values:{
          AGENTSTUDIO_BACKEND_PORT:String(backendPort),
          AGENTSTUDIO_FRONTEND_PORT:String(frontendPort)
        }})
      })
      setSettings(r.settings)
      setMessage(
        '서비스 포트를 저장했습니다. 다음 SYSTEM_ADMIN.cmd 재실행부터 적용됩니다. '+
        '지정 포트가 다른 프로그램에서 사용 중이면 해당 프로그램을 종료하지 않고 사용 가능한 다음 포트로 안전하게 대체합니다.'
      )
      await checkPortRecommendations()
    }catch(e){
      setError(String(e))
    }finally{
      setBusy(false)
    }
  }

  const portStateLabel=(state)=>({
    current:'현재 AgentStudio 사용 중',
    available:'사용 가능',
    in_use:'다른 프로그램이 사용 중',
    conflict_with_backend:'Backend 포트와 중복'
  }[state]||state||'-')

  const testOne=async(name)=>{
    setBusy(true)
    try{
      const options={method:'POST'}
      if(name==='postgresql' || name==='pgvector'){
        options.body=JSON.stringify({database_url:String(valueOf('DATABASE_URL')||'').trim()})
      }
      const r=await api(`/settings/test/${name}`,options)
      setTests(p=>({...p,[name]:r}))
    }catch(e){
      setTests(p=>({...p,[name]:{ok:false,message:String(e)}}))
    }finally{setBusy(false)}
  }

  const testAll=async()=>{
    setBusy(true)
    try{ setTests(await api('/settings/test-all',{method:'POST'})) }
    catch(e){setError(String(e))}
    finally{setBusy(false)}
  }


  const loadPgvectorInfo=async()=>{
    try{setPgvectorInfo(await api(`/settings/pgvector/windows18/info?postgresql_root=${encodeURIComponent(valueOf('POSTGRESQL18_ROOT'))}`))}
    catch(e){setPgvectorInfo({error:String(e)})}
  }


  const pollPgvectorJob=async(jobId)=>{
    let unchanged=0
    let lastSignature=''

    for(let i=0;i<240;i++){
      try{
        const j=await api(`/jobs/${jobId}`)
        const signature=`${j.status}|${j.progress}|${j.message}`

        if(signature===lastSignature) unchanged++
        else unchanged=0
        lastSignature=signature

        setPgvectorInstall(current=>({
          ...(current||{}),
          job_id:jobId,
          status:j.status,
          progress:j.progress||0,
          message:
            unchanged>=15 && ['QUEUED','RUNNING'].includes(j.status)
              ? `${j.message} (응답 대기 중 - Backend 작업 상태를 확인하고 있습니다.)`
              : (j.message||''),
          result:j.result||{}
        }))

        if(['SUCCESS','FAILED','CANCELLED'].includes(j.status)){
          if(j.status==='SUCCESS') setPgAdminPassword('')
          setBusy(false)
          if(j.status==='SUCCESS'){
            setTimeout(()=>testOne('pgvector'),300)
          }
          return
        }
      }catch(e){
        setPgvectorInstall(current=>({
          ...(current||{}),
          message:`Job 상태 확인 중 오류: ${String(e)}`
        }))
      }

      await new Promise(r=>setTimeout(r,1000))
    }

    setBusy(false)
    setPgvectorInstall(current=>({
      ...(current||{}),
      status:'FAILED',
      message:'설치 작업 상태 확인 제한시간을 초과했습니다.'
    }))
  }

  const installPgvector18=async()=>{
    if(!pgAdminUser.trim()){
      setPgvectorInstall({status:'FAILED',progress:0,message:'PostgreSQL 관리자 사용자명을 입력하세요.'})
      return
    }
    const effectiveAdminPassword=readPgAdminPassword()
    if(!effectiveAdminPassword){
      setPgvectorInstall({status:'FAILED',progress:0,message:'PostgreSQL 관리자 비밀번호를 입력하세요.'})
      return
    }

    const confirmed=window.confirm(`PostgreSQL 18용 Windows pgvector를 다운로드하고 설치합니다.

설치 중 Windows 관리자 권한(UAC) 창이 나오면 허용을 선택해야 합니다.
계속하시겠습니까?`)
    if(!confirmed) return

    setBusy(true)
    setPgvectorInstall({
      status:'QUEUED',
      progress:0,
      message:'설치 작업을 준비하고 있습니다.'
    })

    try{
      // 긴 설치 작업은 Backend Job으로 시작하고 즉시 Job ID를 받습니다.
      const job=await api('/settings/pgvector/windows18/install',{method:'POST',body:JSON.stringify({postgresql_root:valueOf('POSTGRESQL18_ROOT'),admin_user:pgAdminUser,admin_password:effectiveAdminPassword})})
      setPgvectorInstall({
        status:job.status,
        progress:job.progress||0,
        message:job.message||'설치 작업을 시작했습니다.',
        job_id:job.id
      })
      pollPgvectorJob(job.id)
    }catch(e){
      setPgvectorInstall({
        status:'FAILED',
        progress:0,
        message:'설치 Job 시작 실패: '+String(e)
      })
      setBusy(false)
    }
  }


  const validatePgPath=async()=>{
    try{
      const r=await api('/settings/pgvector/windows18/validate-path',{
        method:'POST',
        body:JSON.stringify({postgresql_root:valueOf('POSTGRESQL18_ROOT'),admin_user:pgAdminUser,admin_password:readPgAdminPassword()})
      })
      setPgPathCheck(r)
    }catch(e){
      setPgPathCheck({ok:false,message:String(e)})
    }
  }

  const testPostgresqlAdmin=async()=>{
    const effectiveAdminPassword=readPgAdminPassword()
    setBusy(true)
    try{
      const r=await api('/settings/test/postgresql-admin',{
        method:'POST',
        body:JSON.stringify({admin_user:pgAdminUser,admin_password:effectiveAdminPassword})
      })
      setTests(p=>({...p,postgresqlAdmin:r}))
    }catch(e){
      setTests(p=>({...p,postgresqlAdmin:{ok:false,message:String(e)}}))
    }finally{
      setBusy(false)
    }
  }


  const provisionAgentstudioDb=async()=>{
    const effectiveAdminPassword=readPgAdminPassword()
    const effectiveAppPassword=readAgentDbPassword()
    if(!pgAdminUser.trim() || !effectiveAdminPassword){
      setDbProvision({ok:false,message:'PostgreSQL 관리자 사용자/비밀번호를 입력하세요.'})
      return
    }
    const missing=[]
    if(!agentDbName.trim()) missing.push('DB 이름')
    if(!agentDbUser.trim()) missing.push('앱 사용자')
    if(!effectiveAppPassword) missing.push('앱 비밀번호')
    if(missing.length){
      setDbProvision({ok:false,message:`입력되지 않은 항목: ${missing.join(', ')}`})
      return
    }

    if(!window.confirm(
      `AgentStudio 전용 DB "${agentDbName}"를 생성하고 권한과 pgvector를 설정합니다.\n\n` +
      `앱 사용자: ${agentDbUser}\n계속하시겠습니까?`
    )) return

    setBusy(true)
    setDbProvision({ok:null,message:'AgentStudio DB 생성 및 권한 설정 중...'})

    try{
      const r=await api('/settings/database/provision-agentstudio',{
        method:'POST',
        body:JSON.stringify({
          postgresql_root:valueOf('POSTGRESQL18_ROOT'),
          admin_user:pgAdminUser,
          admin_password:effectiveAdminPassword,
          app_user:agentDbUser,
          app_password:effectiveAppPassword,
          database_name:agentDbName
        })
      })
      setDbProvision(r)
      if(r?.ok){
        setAgentDbPassword('')
        setPgAdminPassword('')
        await refresh()
      }
    }catch(e){
      setDbProvision({ok:false,message:String(e)})
    }finally{
      setBusy(false)
    }
  }


  const refreshGpuRuntime=async()=>{
    try{
      const runtime=await api('/settings/gpu/runtime/status')
      setGpuRuntime(runtime)
      return runtime
    }catch(e){
      setGpuRuntime({ok:false,available:false,enabled:false,message:String(e)})
      return null
    }
  }

  const startGpuRuntime=async()=>{
    setGpuRuntimeBusy(true)
    setMessage('')
    setError('')
    try{
      const result=await api('/settings/gpu/runtime/start',{method:'POST'})
      setGpuRuntime(result)
      if(result?.ok){
        setMessage(result.message||'GPU 가속을 시작했습니다.')
        setTimeout(()=>{ refreshGpuRuntime(); refreshOllamaRuntime() },300)
      }else{
        setError(result?.message||'GPU 가속 시작에 실패했습니다.')
      }
    }catch(e){
      setError('GPU 가속 시작 실패: '+String(e))
    }finally{
      setGpuRuntimeBusy(false)
    }
  }

  const stopGpuRuntime=async()=>{
    if(!window.confirm('AgentStudio GPU 가속을 정지하시겠습니까?\n\nAgentStudio 관리 Ollama와 생성 Agent 테스트는 가능한 경우 CPU 모드로 실행됩니다.')) return
    setGpuRuntimeBusy(true)
    setMessage('')
    setError('')
    try{
      const result=await api('/settings/gpu/runtime/stop',{method:'POST'})
      setGpuRuntime(result)
      if(result?.ok){
        setMessage(result.message||'GPU 가속을 정지했습니다.')
        setTimeout(()=>{ refreshGpuRuntime(); refreshOllamaRuntime() },300)
      }else{
        setError(result?.message||'GPU 가속 정지에 실패했습니다.')
      }
    }catch(e){
      setError('GPU 가속 정지 실패: '+String(e))
    }finally{
      setGpuRuntimeBusy(false)
    }
  }

  const refreshOllamaRuntime=async()=>{
    try{
      const runtime=await api('/settings/ollama/runtime/status')
      setOllamaRuntime(runtime)
      return runtime
    }catch(e){
      setOllamaRuntime({ok:false,message:String(e),running:false,installed:false})
      return null
    }
  }

  const startOllamaRuntime=async()=>{
    setOllamaRuntimeBusy(true)
    setMessage('')
    setError('')
    try{
      const result=await api('/settings/ollama/runtime/start',{method:'POST'})
      setOllamaRuntime(result)
      if(result.ok){
        setMessage(result.message||'Ollama 서버가 시작되었습니다.')
        setTimeout(()=>testOne('ollama'),300)
      }else{
        setError(result.message||'Ollama 서버 시작에 실패했습니다.')
      }
    }catch(e){
      setError('Ollama 서버 시작 실패: '+String(e))
    }finally{
      setOllamaRuntimeBusy(false)
    }
  }

  const stopOllamaRuntime=async()=>{
    if(!window.confirm('AgentStudio가 시작한 Ollama 서버를 종료하시겠습니까?')) return
    setOllamaRuntimeBusy(true)
    setMessage('')
    setError('')
    try{
      const result=await api('/settings/ollama/runtime/stop',{method:'POST'})
      setOllamaRuntime(result)
      if(result.ok){
        setMessage(result.message||'Ollama 서버를 종료했습니다.')
      }else{
        setError(result.message||'Ollama 서버 종료에 실패했습니다.')
      }
    }catch(e){
      setError('Ollama 서버 종료 실패: '+String(e))
    }finally{
      setOllamaRuntimeBusy(false)
    }
  }

  const pollOllamaJob=async(jobId)=>{
    for(let i=0;i<600;i++){
      try{
        const j=await api(`/jobs/${jobId}`)
        setOllamaInstall(current=>({
          ...(current||{}),
          job_id:jobId,
          status:j.status,
          progress:j.progress||0,
          message:j.message||'',
          result:j.result||{}
        }))
        if(['SUCCESS','FAILED','CANCELLED'].includes(j.status)){
          setBusy(false)
          if(j.status==='SUCCESS'){
            setTimeout(()=>{ refreshOllamaRuntime(); testOne('ollama') },1000)
          }
          return
        }
      }catch(e){
        setOllamaInstall(p=>({...p,message:'설치 상태 확인 실패: '+String(e)}))
      }
      await new Promise(r=>setTimeout(r,1000))
    }
    setBusy(false)
    setOllamaInstall({status:'FAILED',progress:0,message:'Ollama 설치 작업 확인 시간이 초과되었습니다.'})
  }

  const installOllama=async()=>{
    if(!window.confirm(
      'Ollama를 설치합니다. 공용 모델 경로가 설정되어 있으면 해당 경로에 모델을 저장하고, 비어 있으면 Ollama 기본 모델 경로를 사용합니다. 계속하시겠습니까?'
    )) return

    setBusy(true)
    setOllamaInstall({status:'QUEUED',progress:0,message:'Ollama 설치 작업을 준비합니다.'})

    try{
      const job=await api('/settings/ollama/windows/install',{
        method:'POST',
        body:JSON.stringify({common_models_root:valueOf('COMMON_MODELS_ROOT')})
      })
      setOllamaInstall({
        job_id:job.id,
        status:job.status,
        progress:job.progress||0,
        message:job.message||'설치 작업을 시작했습니다.'
      })
      pollOllamaJob(job.id)
    }catch(e){
      setBusy(false)
      setOllamaInstall({status:'FAILED',progress:0,message:'Ollama 설치 시작 실패: '+String(e)})
    }
  }


  const cancelSystemJob=async(jobId,label='작업')=>{
    if(!jobId) return
    try{
      await api(`/jobs/${encodeURIComponent(jobId)}/cancel`,{method:'POST'})
      setMessage(`${label} 실행 중지 요청을 보냈습니다.`)
      setBusy(false)
    }catch(e){
      setError(`${label} 실행 중지 실패: ${String(e)}`)
    }
  }


  const chooseFolder=async(name,label)=>{
    try{
      const r=await api('/system/pick-folder',{
        method:'POST',
        body:JSON.stringify({
          title:`${label} 선택`,
          initial_path:valueOf(name)
        })
      })
      if(r.ok && !r.cancelled && r.path){
        setValue(name,r.path)
      }
    }catch(e){
      setError('경로 선택 실패: '+String(e))
    }
  }

  const renderPathField=(label,name,placeholder='')=><label className="setting-field">
    <span>{label}</span>
    <div className="path-input-row">
      <input
        type="text"
        value={valueOf(name)}
        placeholder={placeholder}
        onChange={e=>setValue(name,e.target.value)}
      />
      <button
        type="button"
        className="path-find-button"
        onClick={()=>chooseFolder(name,label)}
      >경로 찾기</button>
    </div>
  </label>


  const migrateSettingsToDb=async()=>{
    setBusy(true); setMessage(''); setError('')
    try{
      const r=await api('/settings/migrate-to-db',{method:'POST'})
      if(r?.ok===false){
        setMessage(r?.message||'공용 DB 연결 복구 후 다시 동기화하세요.')
      }else{
        setMessage(r?.message||`설정 DB 동기화 완료: 신규 ${r.migrated||0}개 / 수정 ${r.updated||0}개`)
      }
      await refresh()
    }catch(e){
      setError('설정 DB 이관 실패: '+String(e))
    }finally{
      setBusy(false)
    }
  }

  const renderField=(label,name,type='text',placeholder='')=><label className="setting-field">
    <span>{label}</span>
    <input
      type={type}
      value={valueOf(name)}
      placeholder={configured(name) ? '설정됨 - 변경할 때만 새 값을 입력' : placeholder}
      onChange={e=>setValue(name,e.target.value)}
    />
  </label>

  const renderTestResult=(name)=>{
    const r=tests[name]
    if(!r) return null
    return <div className={r.ok?'test-result okbox':'test-result badbox'}>
      <div>{r.message}</div>
      {r.target&&<div><b>연결 대상:</b> {`${r.target.user||'?'}@${r.target.host||'?'}:${r.target.port||'?'} / ${r.target.database||'?'}`}</div>}
      {!r.ok&&r.sqlstate&&<div><b>PostgreSQL 코드:</b> {r.sqlstate}</div>}
      {!r.ok&&r.error_type&&<div><b>오류 유형:</b> {r.error_type}</div>}
      {!r.ok&&r.url&&<div><b>연결 URL:</b> {r.url}</div>}
      {!r.ok&&r.port_open!==undefined&&<div><b>포트 상태:</b> {r.port_open?'열림':'연결 안 됨'}</div>}
      {!r.ok&&r.ollama_exe&&<div><b>Ollama 실행 파일:</b> {r.ollama_exe}</div>}
      {!r.ok&&r.recommendation&&<div><b>확인 사항:</b> {r.recommendation}</div>}
      {!r.ok&&r.log_path&&<div className="connection-log-path">
        <b>로그 파일:</b>
        <code>{r.log_path}</code>
        <button
          type="button"
          onClick={()=>navigator.clipboard?.writeText?.(r.log_path)}
          title="로그 파일 경로 복사"
        >경로 복사</button>
      </div>}
    </div>
  }

  const checkRuntimeLoop=async()=>{
    try{
      const result=await api('/health/runtime')
      setRuntimeLoopStatus(result)
      return result
    }catch(e){
      setRuntimeLoopStatus({
        ok:false,
        message:String(e)
      })
      return null
    }
  }


  return <div className="system-page"><div className="system-card system-card-wide">
    <div className="system-head">
      <div><h1>THEANOVA AgentStudio - 시스템 관리</h1>
      <p>설정 입력 → 저장 → 연결 테스트 순서로 관리합니다.</p>
      <div className="hint-box settings-storage-note">
        일반 PC별 설정은 공용 PostgreSQL <b>app_settings</b>를 사용하고 각 PC의 <b>.env</b>를 fallback cache로 유지합니다.
        단, <b>DATABASE URL / LangGraph DB URL은 DB 연결 자체에 필요한 bootstrap 정보이므로 예외적으로 backend/.env에만 저장</b>하며 app_settings에는 저장하지 않습니다.
      </div>
      {settings?._storage?.db_connected===false&&<div className="settings-db-offline-warning">
        <strong>공용 DB 연결 안 됨 · 현재 .env fallback 모드</strong>
        <span>DATABASE URL의 호스트/포트/사용자/비밀번호를 확인하고 [DB 설정 .env 저장] → [AgentStudio DB 연결 테스트] 순서로 복구하세요.</span>
      </div>}
      <div className="machine-scope-info machine-scope-editable">
        <div className="machine-scope-title">
          <span>AgentStudio PC 이름</span>
          <small>공용 DB에서 환경설정을 구분하는 유니크 이름입니다. 사용자가 수정할 수 있습니다.</small>
        </div>
        <div className="machine-name-edit-row">
          <input
            value={machineName}
            maxLength={64}
            onChange={e=>setMachineName(e.target.value)}
            onKeyDown={e=>{if(e.key==='Enter'&&!e.nativeEvent?.isComposing){e.preventDefault();saveMachineName()}}}
            placeholder="예: OFFICE-PC-01"
            aria-label="AgentStudio PC 이름"
          />
          <button type="button" disabled={machineNameBusy} onClick={saveMachineName}>
            {machineNameBusy?'확인 중...':'PC 이름 저장'}
          </button>
        </div>
        <div className="machine-scope-meta">
          <span>Windows PC 이름</span>
          <strong>{settings?._machine?.system_host_name||'확인 중...'}</strong>
          <span className={`machine-unique-badge ${settings?._machine?.pending_pc_name?'pending':settings?._machine?.unique_verified?'':'unverified'}`}>
            {settings?._machine?.pending_pc_name?'검증 대기':settings?._machine?.unique_verified?'UNIQUE':'DB 확인 필요'}
          </span>
        </div>
        {settings?._machine?.pending_pc_name&&<small>요청 PC 이름: <b>{settings._machine.pending_pc_name}</b> · 공용 DB 연결 후 중복 검증이 완료되면 자동 적용됩니다.</small>}
        {!settings?._machine?.pending_pc_name&&<small>환경 설정 기준: PC_NAME + 설정 Key · .env: AGENTSTUDIO_PC_NAME · 중복 이름은 저장되지 않습니다.</small>}
      </div>
      <div className="runtime-port-info">
        API: {runtimeInfo().apiBase} · Frontend: {window.location.origin}
      </div>
      </div>
      <div className="button-row">
        <button onClick={refresh}>설정 다시 읽기</button>
        <button disabled={busy} onClick={migrateSettingsToDb}>설정 DB 이관</button>
        <button onClick={testAll}>전체 연결 테스트</button>
        <button onClick={()=>location.href='/'}>AgentStudio 열기</button>
      </div>
    </div>

    {message&&<div className="success-box">{message}</div>}
    {error&&<div className="error">{error}</div>}

    <div className="settings-sections">
      <ServicePortSettingsPanel
        busy={busy}
        portCheckBusy={portCheckBusy}
        portInfo={portInfo}
        runtimeApiBase={runtimeInfo().apiBase}
        frontendOrigin={window.location.origin}
        valueOf={valueOf}
        setValue={setValue}
        portStateLabel={portStateLabel}
        onCheckRecommendations={checkPortRecommendations}
        onApplyRecommendations={applyRecommendedPorts}
        onSave={savePortSettings}
      />

      <section className="settings-panel settings-panel-wide">
        <h2>기본 경로 설정</h2>
        <div className="hint-box">
          신규 에이전트 생성 시 개별 경로를 입력하지 않으면 아래 기본 경로를 사용합니다.
        </div>
        <div className="two-col-fields">
          {renderPathField("프로젝트 기본 경로","DEFAULT_PROJECT_ROOT","Agent 프로젝트 기본 폴더")}
          {renderPathField("Cache 기본 경로","DEFAULT_CACHE_ROOT","비우면 프로젝트경로\\\\cache")}
          {renderPathField("Temp 기본 경로","DEFAULT_TEMP_ROOT","비우면 프로젝트경로\\\\temp")}
          {renderPathField("Output 기본 경로","DEFAULT_OUTPUT_ROOT","비우면 프로젝트경로\\\\output")}
          {renderPathField("공용 모델 경로","COMMON_MODELS_ROOT","비우면 프로젝트경로\\\\models")}
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup([
            'DEFAULT_PROJECT_ROOT','DEFAULT_CACHE_ROOT','DEFAULT_TEMP_ROOT',
            'DEFAULT_OUTPUT_ROOT','COMMON_MODELS_ROOT'
          ])}>기본 경로 저장</button>
        </div>
      </section>

      <section className="settings-panel settings-panel-wide weather-settings-panel">
        <h2>홈 날씨 설정</h2>
        <div className="hint-box">
          메인 화면에 오늘의 아침·점심·저녁·밤 날씨를 표시합니다. 현재 위치 사용을 켜면 브라우저 위치 권한을 사용하고,
          권한이 없거나 끈 경우 아래 기본 지역을 사용합니다. 추가 지역은 세미콜론(;)으로 구분해 최대 4개까지 표시합니다. 오늘 한 번 조회한 날씨는 로컬 캐시에 저장하고 같은 날에는 저장된 데이터를 우선 사용합니다.
        </div>
        <label className="setting-checkbox-row">
          <input
            type="checkbox"
            checked={String(valueOf('WEATHER_AUTO_LOCATION')||'true').toLowerCase()!=='false'}
            onChange={e=>setValue('WEATHER_AUTO_LOCATION',e.target.checked?'true':'false')}
          />
          <span>메인 화면에서 현재 위치 날씨 사용</span>
        </label>
        <div className="two-col-fields">
          {renderField("기본 날씨 지역","WEATHER_LOCATION","text","예: 부천시, 서울, Busan")}
          {renderField("추가 지역","WEATHER_EXTRA_LOCATIONS","text","예: 부일로815번길 36; 인천; 부산")}
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup([
            'WEATHER_AUTO_LOCATION','WEATHER_LOCATION','WEATHER_EXTRA_LOCATIONS'
          ])}>날씨 설정 저장</button>
        </div>
      </section>

      <div className="settings-balanced-columns">
        <div className="settings-column settings-column-left">
      <section className="settings-panel">
        <h2>PostgreSQL / LangGraph</h2>

        <RuntimeDatabasePanel
          providerChoice={databaseProviderChoice}
          runtime={databaseRuntime}
          result={databaseRuntimeResult}
          supabaseRuntimeUrl={supabaseRuntimeUrl}
          supabaseLanggraphRuntimeUrl={supabaseLanggraphRuntimeUrl}
          supabaseRuntimeSchema={supabaseRuntimeSchema}
          runtimeBusy={databaseRuntimeBusy}
          infoSaveBusy={supabaseInfoSaveBusy}
          onProviderChoice={setDatabaseProviderChoice}
          onSupabaseRuntimeUrl={setSupabaseRuntimeUrl}
          onSupabaseLanggraphRuntimeUrl={setSupabaseLanggraphRuntimeUrl}
          onSupabaseRuntimeSchema={setSupabaseRuntimeSchema}
          onSaveSupabaseInfo={saveSupabaseRuntimeInfo}
          onInitializeSupabaseSchema={initializeSupabaseRuntimeSchema}
          onDownloadSupabaseSchema={downloadSupabaseSchemaScript}
          onActivateRuntimeDatabase={activateRuntimeDatabase}
        />

        {renderField("로컬 DATABASE URL (기본 / Control DB)","DATABASE_URL","text","")}
        {renderField("로컬 LangGraph DB URL","LANGGRAPH_DATABASE_URL","text","")}
        {renderPathField("PostgreSQL 18 설치 경로","POSTGRESQL18_ROOT","PostgreSQL 18이 설치된 폴더를 입력하세요.")}
        <label className="setting-field">
          <span>PostgreSQL 관리자 사용자</span>
          <input value={pgAdminUser} onChange={e=>setPgAdminUser(e.target.value)} placeholder="예: postgres"/>
        </label>
        <label className="setting-field">
          <span>PostgreSQL 관리자 비밀번호 (저장하지 않음)</span>
          <input ref={pgAdminPasswordRef} type="password" value={pgAdminPassword} onInput={e=>setPgAdminPassword(e.currentTarget.value)} onChange={e=>setPgAdminPassword(e.target.value)} autoComplete="new-password" placeholder="DB 생성/pgvector 관리자 작업에만 사용"/>
        </label>
        <div className="hint-box credential-scope-hint">
          <b>비밀번호 사용 범위:</b> [관리자 계정 테스트/전용 DB 생성/pgvector 설치]는 위 관리자 비밀번호를 사용합니다.
          [AgentStudio DB 연결 테스트/AgentStudio DB pgvector 테스트]는 <b>화면에 현재 입력되어 있는 DATABASE URL</b>의 사용자/비밀번호를 즉시 사용합니다.
          DB 설정 저장을 먼저 누르지 않아도 현재 입력값으로 테스트합니다. 두 비밀번호는 서로 다를 수 있습니다.
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={testPostgresqlAdmin}>관리자 계정 테스트</button>
        </div>
        {renderTestResult('postgresqlAdmin')}
        <div className="provision-box">
          <h3>AgentStudio 전용 DB 생성</h3>
          <label className="setting-field">
            <span>데이터베이스 이름</span>
            <input value={agentDbName} onChange={e=>setAgentDbName(e.target.value)}/>
          </label>
          <label className="setting-field">
            <span>AgentStudio 앱 사용자</span>
            <input value={agentDbUser} onChange={e=>setAgentDbUser(e.target.value)}/>
          </label>
          <label className="setting-field">
            <span>AgentStudio 앱 비밀번호 (저장하지 않음)</span>
            <input ref={agentDbPasswordRef} type="password" value={agentDbPassword} onInput={e=>setAgentDbPassword(e.currentTarget.value)} onChange={e=>setAgentDbPassword(e.target.value)} autoComplete="new-password"/>
          </label>
          <button className="primary-install" disabled={busy} onClick={provisionAgentstudioDb}>
            theanova_agentstudio DB 생성 + pgvector 설치 + 권한 + 테이블 초기화
          </button>
          {dbProvision&&<div className={
            dbProvision.ok===true ? 'test-result okbox' :
            dbProvision.ok===false ? 'test-result badbox' :
            'test-result install-running'
          }>
            {dbProvision.message}
            {dbProvision.database_url&&<div>DATABASE URL: {dbProvision.database_url}</div>}
            {dbProvision.langgraph_database_url&&<div>LangGraph DB URL: {dbProvision.langgraph_database_url}</div>}
            {dbProvision.table_count!==undefined&&<div>생성/확인된 테이블 수: {dbProvision.table_count}</div>}
            {dbProvision.agentstudio_tables?.length>0&&<details>
              <summary>AgentStudio 테이블 ({dbProvision.agentstudio_tables.length})</summary>
              <div className="table-list">{dbProvision.agentstudio_tables.join(', ')}</div>
            </details>}
            {dbProvision.langgraph_tables?.length>0&&<details>
              <summary>LangGraph 테이블 ({dbProvision.langgraph_tables.length})</summary>
              <div className="table-list">{dbProvision.langgraph_tables.join(', ')}</div>
            </details>}
          </div>}
        </div>

        <div className="hint-box">
          <b>저장 위치:</b> DATABASE URL과 LangGraph DB URL은 DB 연결 이전에 필요한 bootstrap 설정이므로 <b>backend/.env에만 저장</b>합니다.
          PostgreSQL app_settings에는 저장하지 않습니다. PostgreSQL이 연결되지 않은 상태에서도 저장할 수 있습니다.
          PostgreSQL 관리자 비밀번호와 AgentStudio 앱 비밀번호는 저장하지 않습니다.
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={saveDatabaseEnv}>DB 설정 .env 저장</button>
          <button onClick={()=>testOne('postgresql')}>AgentStudio DB 연결 테스트</button>
          <button type="button" onClick={checkRuntimeLoop}>Event Loop 확인</button>
          <button onClick={()=>testOne('pgvector')}>AgentStudio DB pgvector 테스트</button>
          {runtimeLoopStatus&&<div className="runtime-loop-status">
            Event Loop: {runtimeLoopStatus.event_loop||runtimeLoopStatus.message}
            {runtimeLoopStatus.is_selector===true&&' · Selector 정상'}
            {runtimeLoopStatus.is_proactor===true&&' · Proactor 오류'}
          </div>}
          <button disabled={busy} onClick={()=>saveGroup(['POSTGRESQL18_ROOT'])}>PostgreSQL 경로 저장</button>
          <button onClick={validatePgPath}>PostgreSQL 경로 확인</button>
          <button className="primary-install" disabled={busy || (pgvectorInstall && ['QUEUED','RUNNING'].includes(pgvectorInstall.status))} onClick={installPgvector18}>{pgvectorInstall && ['QUEUED','RUNNING'].includes(pgvectorInstall.status) ? 'pgvector 설치 진행 중...' : 'PostgreSQL 18 x64 pgvector 다운로드 및 설치'}</button>
          {pgvectorInstall?.job_id&&['QUEUED','RUNNING'].includes(pgvectorInstall.status)&&<button className="execution-stop-button" onClick={()=>cancelSystemJob(pgvectorInstall.job_id,'pgvector 설치')}>■ 실행 정지</button>}
          <button onClick={loadPgvectorInfo}>설치 패키지 정보</button>
        </div>
        {renderTestResult("postgresql")}{renderTestResult("pgvector")}
        {pgPathCheck&&<div className={pgPathCheck.ok?'test-result okbox':'test-result badbox'}>
          {pgPathCheck.message}
          {pgPathCheck.psql&&<div>psql.exe: {pgPathCheck.psql}</div>}
          {pgPathCheck.version&&<div>{pgPathCheck.version}</div>}
        </div>}
        {pgvectorInfo&&<div className="install-info">
          <b>PostgreSQL 경로:</b> {pgvectorInfo.postgresql_root||'자동 탐지 실패'}<br/>
          <b>패키지:</b> {pgvectorInfo.release?.release_name||pgvectorInfo.error||'-'}<br/>
          {pgvectorInfo.release?.asset_name&&<><b>파일:</b> {pgvectorInfo.release.asset_name}</>}
        </div>}
        {pgvectorInstall&&<div className={
          pgvectorInstall.status==='SUCCESS'
            ?'test-result okbox'
            :pgvectorInstall.status==='FAILED'
              ?'test-result badbox'
              :'test-result install-running'
        }>
          <div><b>설치 상태:</b> {pgvectorInstall.status}</div>
          <progress max="100" value={pgvectorInstall.progress||0}/>
          <div>{pgvectorInstall.message}</div>
          {pgvectorInstall.result?.release?.release_name&&
            <div>설치 패키지: {pgvectorInstall.result.release.release_name}</div>}
          {pgvectorInstall.result?.postgresql_root&&
            <div>설치 경로: {pgvectorInstall.result.postgresql_root}</div>}
          {pgvectorInstall.result?.traceback&&
            <details><summary>상세 오류</summary><pre>{pgvectorInstall.result.traceback}</pre></details>}
        </div>}
      </section>

      <section className="settings-panel">
        <h2>LangSmith</h2>
        {renderField("LangSmith API Key","LANGSMITH_API_KEY","password","")}
        {renderField("Project","LANGSMITH_PROJECT","text","")}
        {renderField("Tracing (true/false)","LANGSMITH_TRACING","text","")}
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup(['LANGSMITH_API_KEY','LANGSMITH_PROJECT','LANGSMITH_TRACING'])}>LangSmith 설정 저장</button>
          <button onClick={()=>testOne('langsmith')}>LangSmith 연결 테스트</button>
        </div>
        {renderTestResult("langsmith")}
      </section>
        </div>

        <div className="settings-column settings-column-right">
      <section className="settings-panel">
        <h2>OpenAI</h2>
        <label className="setting-checkbox-row">
          <input
            type="checkbox"
            checked={String(valueOf('OPENAI_ENABLED')||'true').toLowerCase()!=='false'}
            onChange={e=>setValue('OPENAI_ENABLED',e.target.checked?'true':'false')}
          />
          <span>OpenAI 사용</span>
        </label>
        <div className="hint-box">
          <b>OpenAI 사용</b>을 끄면 OpenAI API를 Provider 후보에서 제외합니다. 일반 AI 작업과 Embedding은 Ollama를 우선 사용하며,
          Codex를 별도로 켠 경우 복잡한 코딩/요구사항 작업은 Codex까지 마지막 보조 Provider로 사용할 수 있습니다. 저장된 OpenAI API Key는 삭제하지 않습니다.
        </div>
        {renderField("OpenAI API Key","OPENAI_API_KEY","password","")}
        {renderField("GPT 코딩 모델","OPENAI_MODEL","text","")}
        {renderField("Embedding 모델","OPENAI_EMBEDDING_MODEL","text","")}
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup(['OPENAI_ENABLED','OPENAI_API_KEY','OPENAI_MODEL','OPENAI_EMBEDDING_MODEL'])}>OpenAI 설정 저장</button>
          <button disabled={String(valueOf('OPENAI_ENABLED')||'true').toLowerCase()==='false'} onClick={()=>testOne('openai')}>OpenAI 연결 테스트</button>
        </div>
        {String(valueOf('OPENAI_ENABLED')||'true').toLowerCase()==='false'&&
          <div className="test-result okbox">OpenAI 비사용 · OpenAI API 호출을 하지 않습니다. Ollama가 우선이며 Codex 사용 설정은 별도로 적용됩니다.</div>}
        {renderTestResult("openai")}
      </section>

      <CodexSettingsPanel
        enabled={String(valueOf('CODEX_ENABLED')||'false').toLowerCase()==='true'}
        busy={busy}
        onEnabledChange={enabled=>setValue('CODEX_ENABLED',enabled?'true':'false')}
        onSave={()=>saveGroup(['CODEX_ENABLED'])}
      />

      <GpuSettingsPanel
        busy={gpuRuntimeBusy}
        runtime={gpuRuntime}
        onStart={startGpuRuntime}
        onStop={stopGpuRuntime}
        onRefresh={refreshGpuRuntime}
      />

      <OllamaSettingsPanel
        busy={busy}
        runtimeBusy={ollamaRuntimeBusy}
        runtime={ollamaRuntime}
        install={ollamaInstall}
        valueOf={valueOf}
        setValue={setValue}
        renderField={renderField}
        renderTestResult={renderTestResult}
        onSave={()=>saveGroup(['OLLAMA_BASE_URL','OLLAMA_MODEL','OLLAMA_EMBEDDING_MODEL','OLLAMA_AUTO_START'])}
        onTest={()=>{refreshOllamaRuntime();testOne('ollama')}}
        onStart={startOllamaRuntime}
        onStop={stopOllamaRuntime}
        onInstall={installOllama}
        onRefresh={refreshOllamaRuntime}
      />

      <section className="settings-panel">
        <h2>Tavily</h2>
        {renderField("Tavily API Key","TAVILY_API_KEY","password","")}
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup(['TAVILY_API_KEY'])}>Tavily 설정 저장</button>
          <button onClick={()=>testOne('tavily')}>Tavily 연결 테스트</button>
        </div>
        {renderTestResult("tavily")}
      </section>

      <section className="settings-panel">
        <h2>AI Provider 라우팅</h2>
        <label>Provider 전략
          <select value={String(valueOf('AI_PROVIDER_STRATEGY')||'ollama_first')} onChange={e=>setValue('AI_PROVIDER_STRATEGY',e.target.value)}>
            <option value="ollama_first">자동 · 일반 Ollama 우선 / 고난도 Codex 우선</option>
            <option value="manual">수동 Provider 지정</option>
          </select>
        </label>
        <label>로컬/일반 작업 Provider
          <select value={String(valueOf('LOCAL_LLM_PROVIDER')||'auto')} onChange={e=>setValue('LOCAL_LLM_PROVIDER',e.target.value)}>
            <option value="auto">자동</option><option value="ollama">Ollama</option><option value="openai">OpenAI API</option>
          </select>
        </label>
        <label>코딩 Provider
          <select value={String(valueOf('CODING_LLM_PROVIDER')||'auto')} onChange={e=>setValue('CODING_LLM_PROVIDER',e.target.value)}>
            <option value="auto">자동</option><option value="ollama">Ollama</option><option value="openai">OpenAI API</option><option value="codex">Codex</option>
          </select>
        </label>
        <label>요구사항/Agent 설계 Provider
          <select value={String(valueOf('REQUIREMENTS_LLM_PROVIDER')||'auto')} onChange={e=>setValue('REQUIREMENTS_LLM_PROVIDER',e.target.value)}>
            <option value="auto">자동</option><option value="ollama">Ollama</option><option value="openai">OpenAI API</option><option value="codex">Codex</option>
          </select>
        </label>
        <div className="hint-box">
          자동 모드에서는 일반 요약·분류·인터뷰·간단한 코드 작업은 <b>Ollama 우선</b>으로 처리하고 필요한 작업만 OpenAI/Codex로 보조합니다.
          반대로 <b>Workflow 전체/LangGraph 분기, DB Entity·관계, 복잡한 다중파일 변경, 실행·디버깅·대규모 수정</b>은
          활성화된 Provider 기준 <b>Codex → OpenAI → Ollama</b> 순으로 품질을 우선합니다. 수동 모드에서는 아래 Provider 선택값을 존중합니다.
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup(['AI_PROVIDER_STRATEGY','LOCAL_LLM_PROVIDER','CODING_LLM_PROVIDER','REQUIREMENTS_LLM_PROVIDER'])}>라우팅 설정 저장</button>
        </div>
      </section>
        </div>
      </div>

      <section className="settings-panel settings-panel-wide">
        <h2>로컬 프로젝트 / 실행 정책</h2>
        <div className="two-col-fields">
          {renderPathField("허용 프로젝트 경로","ALLOWED_PROJECT_ROOTS","프로젝트 작업을 허용할 루트 폴더")}
          {renderPathField("Sandbox 경로","SANDBOX_ROOT","Sandbox 폴더")}
          {renderField("명령 최대 실행시간(초)","MAX_COMMAND_SECONDS","text","")}
          {renderField("자동 승인 Risk Level","AUTO_APPROVE_RISK_LEVEL","text","")}
          {renderField("자동 Debug 최대 반복","MAX_DEBUG_ITERATIONS","text","")}
          {renderField("Project Analyzer 최대 파일","PROJECT_ANALYZER_MAX_FILES","text","")}
          {renderField("MCP Timeout(초)","MCP_DEFAULT_TIMEOUT_SECONDS","text","")}
          {renderField("MCP Registry 갱신주기(초)","MCP_REGISTRY_REFRESH_SECONDS","text","")}
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup([
            'ALLOWED_PROJECT_ROOTS','SANDBOX_ROOT','MAX_COMMAND_SECONDS','AUTO_APPROVE_RISK_LEVEL',
            'MAX_DEBUG_ITERATIONS','PROJECT_ANALYZER_MAX_FILES','MCP_DEFAULT_TIMEOUT_SECONDS',
            'MCP_REGISTRY_REFRESH_SECONDS'
          ])}>로컬/실행 설정 저장</button>
        </div>
      </section>
    </div>

    <SystemStatusSummary status={status}/>
  </div></div>
}


const WORKFLOW_ICON_RULES=[
  [['transport','stdio','streamable'],'⇄'],
  [['security','보안','경로 검증','허용'],'🛡'],
  [['extension','확장자'],'✓'],
  [['provider','모델 선택','llm provider'],'◉'],
  [['export','내보내기','txt','md 저장'],'⇩'],
  [['upload','등록','업로드','publish'],'⇧'],
  [['auth','인증','oauth','login'],'◉'],
  [['validate','검증','확인','check'],'✓'],
  [['select','선택','choose'],'⌁'],
  [['analy','분석','analyze'],'⌕'],
  [['plan','계획','설계','design'],'◇'],
  [['search','조회','검색','find'],'⌕'],
  [['download','다운로드'],'⇩'],
  [['generate','생성','작성','create'],'✦'],
  [['save','저장','persist'],'▣'],
  [['test','테스트','시험'],'▶'],
  [['retry','재시도','복구','repair'],'↻'],
  [['error','실패','오류','fail'],'!'],
  [['channel','채널'],'▦'],
  [['video','영상'],'▷'],
  [['file','파일'],'▤'],
  [['message','질문','대화','chat'],'✉'],
  [['database','db','데이터'],'◫'],
  [['api','mcp','tool','도구'],'⚙'],
]

function workflowIconFor(text=''){
  const value=String(text).toLowerCase()
  for(const [keys,icon] of WORKFLOW_ICON_RULES){
    if(keys.some(key=>value.includes(String(key).toLowerCase()))){
      return icon
    }
  }
  return '◆'
}

function normalizeTargetStep(step,index){
  if(typeof step==='string'){
    return {
      name:step,
      label:step,
      description:'',
      icon:workflowIconFor(step),
      index
    }
  }

  const item=step||{}
  const label=
    item.label
    || item.title
    || item.name
    || item.step
    || `Step ${index+1}`

  return {
    ...item,
    name:item.name||label,
    label,
    description:
      item.description
      || item.purpose
      || item.detail
      || item.reason
      || '',
    icon:item.icon||workflowIconFor(label),
    index
  }
}

function FactoryNodeCard({node,index}){
  const accent=node?.accent||'default'

  return <div className={`factory-node-card ${accent}`}>
    <div className="factory-node-visual">
      <span className="factory-node-icon">{node?.icon||'◆'}</span>
      <span className="factory-node-number">{String(index+1).padStart(2,'0')}</span>
    </div>
    <div className="factory-node-copy">
      <strong>{node?.label||node?.name}</strong>
      <small>{node?.description||''}</small>
    </div>
  </div>
}

function FactoryPhaseCard({phase,phaseIndex,isLast=false}){
  return <div className="factory-phase-wrap">
    <section className={`factory-phase-card phase-${String(phase?.id||'').toLowerCase()}`}>
      <header className="factory-phase-head">
        <div className="factory-phase-symbol">{phase?.icon||'◇'}</div>
        <div>
          <span>PHASE {String(phaseIndex+1).padStart(2,'0')}</span>
          <strong>{phase?.title||phase?.id}</strong>
          <small>{phase?.subtitle||''}</small>
        </div>
      </header>

      <div className="factory-phase-nodes">
        {(phase?.nodes||[]).map((node,index)=>
          <FactoryNodeCard
            key={node?.name||index}
            node={node}
            index={index}
          />
        )}
      </div>
    </section>
    {!isLast&&<div className="factory-phase-connector">
      <span></span>
      <b>→</b>
      <span></span>
    </div>}
  </div>
}

function FactoryWorkflowDiagram({definition}){
  const fallback=[
    {
      id:'DISCOVER',
      title:'요구 이해',
      subtitle:'무엇을 왜 만들지 정리합니다.',
      icon:'◎',
      nodes:[
        {label:'요구사항 분석',description:'목표·입력·출력·제약 구조화',icon:'✦'},
        {label:'프로젝트 분석',description:'기존 구조와 관련 파일 파악',icon:'⌕'}
      ]
    },
    {
      id:'DESIGN',
      title:'Agent 설계',
      subtitle:'기능·도구·구조·업무 흐름을 결정합니다.',
      icon:'◇',
      nodes:[
        {label:'기능 설계',description:'핵심 능력 정의',icon:'✣'},
        {label:'Tool / MCP 판단',description:'외부 기능 연결 방식 결정',icon:'⚙'},
        {label:'Agent 아키텍처',description:'컴포넌트와 상태 설계',icon:'⬡'},
        {label:'대상 Agent Workflow',description:'실제 업무 흐름 설계',icon:'⇢',accent:'target'},
        {label:'파일 계획',description:'수정·생성 파일 배치',icon:'▤'}
      ]
    },
    {
      id:'BUILD',
      title:'제작',
      subtitle:'코드와 실행 환경을 구성합니다.',
      icon:'⌘',
      nodes:[
        {label:'체크포인트',description:'변경 전 복구 지점',icon:'◈'},
        {label:'실행 승인',description:'실제 변경 전 확인',icon:'✓'},
        {label:'코드 생성 / 수정',description:'파일 생성과 최소 수정',icon:'</>'},
        {label:'환경 구성',description:'패키지·환경변수 설정',icon:'⚡'}
      ]
    },
    {
      id:'VERIFY',
      title:'검증 & 완성',
      subtitle:'실행·복구·완료를 확인합니다.',
      icon:'✓',
      nodes:[
        {label:'테스트',description:'실행·기능 검증',icon:'▶'},
        {label:'디버그 / 복구',description:'실패 원인 분석 후 재수정',icon:'↻',accent:'warning'},
        {label:'완성 패키지',description:'결과 정리',icon:'▣'},
        {label:'최종 검토',description:'완료 조건 확인',icon:'★'}
      ]
    }
  ]

  const phases=definition?.factory_phases||fallback

  return <div className="factory-workflow-diagram">
    <div className="factory-start-pill">
      <span>USER</span>
      <b>“OO 에이전트 만들어줘”</b>
    </div>

    <div className="factory-start-line">
      <span></span><b>↓</b><span></span>
    </div>

    <div className="factory-phase-grid">
      {phases.map((phase,index)=>
        <FactoryPhaseCard
          key={phase.id||index}
          phase={phase}
          phaseIndex={index}
          isLast={index===phases.length-1}
        />
      )}
    </div>

    <div className="factory-repair-band">
      <div className="repair-band-icon">↻</div>
      <div>
        <strong>자동 복구 루프</strong>
        <small>테스트 실패 시 원인을 분석하고 코드를 다시 수정한 뒤 재검증합니다.</small>
      </div>
      <div className="repair-band-flow">
        <span>TEST</span><b>→</b>
        <span className="warn">DEBUG</span><b>→</b>
        <span>CODE</span><b>→</b>
        <span>ENV</span><b>→</b>
        <span>RE-TEST</span>
      </div>
    </div>

    <div className="factory-complete-pill">
      <span>★</span>
      <div>
        <strong>실행 가능한 Agent 프로그램 완성</strong>
        <small>코드 생성만이 아니라 테스트와 최종 검토까지 통과한 상태</small>
      </div>
    </div>
  </div>
}

function TargetWorkflowDiagram({workflow}){
  const [selectedGroup,setSelectedGroup]=useState(null)

  const rawSteps=(workflow?.steps||[]).map((step,index)=>{
    if(typeof step==='string'){
      return {
        name:`step_${index+1}`,
        label:step,
        description:'',
        type:'process',
        icon:'◆'
      }
    }

    return {
      ...step,
      name:step?.name||`step_${index+1}`,
      label:step?.label||step?.name||`Step ${index+1}`,
      description:step?.description||'',
      type:step?.type||'process',
      icon:step?.icon||workflowIconFor(step),
    }
  })

  if(!rawSteps.length){
    return <div className="target-empty">
      <div className="target-empty-graphic">
        <span>◇</span>
        <i></i>
        <span>◆</span>
        <i></i>
        <span>★</span>
      </div>
      <strong>아직 대상 Agent Workflow가 없습니다.</strong>
      <p>에이전트 개발 요청을 분석하면 실제 업무 단계가 시각적인 Workflow로 표시됩니다.</p>
    </div>
  }

  const classifyStep=(step)=>{
    const text=[
      step?.name,
      step?.label,
      step?.description,
      step?.type
    ].join(' ').toLowerCase()

    if(
      text.includes('complete')
      || text.includes('완료')
    ) return 'COMPLETE'

    if(
      text.includes('save')
      || text.includes('저장')
      || text.includes('output')
      || text.includes('storage')
    ) return 'SAVE'

    if(
      text.includes('display')
      || text.includes('결과 표시')
      || text.includes('ui')
      || text.includes('react')
    ) return 'OUTPUT'

    if(
      text.includes('llm')
      || text.includes('provider')
      || text.includes('model')
      || text.includes('요약 생성')
      || text.includes('generate_summary')
    ) return 'LLM'

    if(
      text.includes('mcp')
      || text.includes('transport')
      || text.includes('tool')
      || text.includes('파일 읽기')
      || text.includes('file_read')
    ) return 'MCP'

    if(
      text.includes('validate')
      || text.includes('검증')
      || text.includes('파일 선택')
      || text.includes('input')
      || text.includes('extension')
      || text.includes('root')
    ) return 'INPUT'

    return 'INPUT'
  }

  const groupDefinitions=[
    {
      id:'INPUT',
      title:'입력 / 검증',
      subtitle:'파일 선택과 접근 검증',
      icon:'✓'
    },
    {
      id:'MCP',
      title:'MCP 파일 처리',
      subtitle:'Client · Transport · Server · Tool',
      icon:'⚙'
    },
    {
      id:'LLM',
      title:'LLM 요약',
      subtitle:'Provider 확인과 AI 요약',
      icon:'✦'
    },
    {
      id:'OUTPUT',
      title:'결과 표시',
      subtitle:'React UI 결과 제공',
      icon:'◆'
    },
    {
      id:'SAVE',
      title:'선택적 저장',
      subtitle:'형식 · 경로 검증 · 저장',
      icon:'▣'
    },
    {
      id:'COMPLETE',
      title:'완료',
      subtitle:'업무 처리 종료',
      icon:'★'
    }
  ]

  const groups=groupDefinitions
    .map(def=>({
      ...def,
      steps:rawSteps.filter(step=>classifyStep(step)===def.id)
    }))
    .filter(group=>group.steps.length>0 || group.id==='COMPLETE')

  const activeGroup=groups.find(x=>x.id===selectedGroup)

  if(activeGroup){
    return <div className="grouped-workflow-detail">
      <div className="grouped-detail-head">
        <button
          type="button"
          onClick={()=>setSelectedGroup(null)}
          className="grouped-detail-back"
        >
          ← 전체 Workflow
        </button>

        <div className="grouped-detail-title">
          <span>{activeGroup.icon}</span>
          <div>
            <small>WORKFLOW GROUP</small>
            <strong>{activeGroup.title}</strong>
            <p>{activeGroup.subtitle}</p>
          </div>
        </div>
      </div>

      <div className="target-workflow-diagram detailed">
        <div className="target-start-card">
          <span className="target-start-icon">◎</span>
          <div>
            <small>START</small>
            <strong>{activeGroup.title}</strong>
          </div>
        </div>

        <div className="target-flow-track">
          {activeGroup.steps.map((step,index)=><div className="target-step-wrap" key={`${step.name}-${index}`}>
            <article className="target-step-card">
              <div className="target-step-top">
                <span className="target-step-icon">{step.icon}</span>
                <span className="target-step-index">{String(index+1).padStart(2,'0')}</span>
              </div>
              <strong>{step.label}</strong>
              {step.description&&<small>{step.description}</small>}
            </article>
            {index<activeGroup.steps.length-1&&<div className="target-step-arrow">
              <span></span><b>→</b><span></span>
            </div>}
          </div>)}
        </div>

        <div className="target-end-card">
          <span>★</span>
          <div>
            <small>GROUP COMPLETE</small>
            <strong>{activeGroup.title} 완료</strong>
          </div>
        </div>
      </div>
    </div>
  }

  return <div className="grouped-workflow-overview">
    <div className="grouped-workflow-head">
      <div>
        <small>TARGET AGENT WORKFLOW</small>
        <strong>{workflow?.name||'Agent Workflow'}</strong>
      </div>
      <span>그룹을 클릭하면 상세 단계가 표시됩니다.</span>
    </div>

    <div className="grouped-workflow-track">
      {groups.map((group,index)=><div className="grouped-workflow-wrap" key={group.id}>
        <button
          type="button"
          className={`grouped-workflow-card ${group.id.toLowerCase()}`}
          onClick={()=>group.steps.length&&setSelectedGroup(group.id)}
          disabled={!group.steps.length}
          title={`${group.title} 상세 보기`}
        >
          <span className="grouped-workflow-icon">{group.icon}</span>
          <strong>{group.title}</strong>
          <small>{group.steps.length}단계</small>
        </button>

        {index<groups.length-1&&<div className="grouped-workflow-arrow">
          <span></span>
          <b>→</b>
          <span></span>
        </div>}
      </div>)}
    </div>

    {(workflow?.requirement_coverage?.length>0)&&<div className="workflow-coverage-panel compact">
      <div className="workflow-coverage-head">
        <div>
          <small>REQUIREMENT TRACEABILITY</small>
          <strong>요구사항 반영 확인</strong>
        </div>
        <span>
          {workflow.requirement_coverage.filter(x=>x?.status==='covered').length}
          /{workflow.requirement_coverage.length} 반영
        </span>
      </div>
    </div>}
  </div>
}


function redevelopmentResumeNodeForFailure(stage='',status=''){
  const raw=String(stage||'').trim().toLowerCase().replace(/[-/]/g,'_')
  const previous={
    requirement_analysis:'requirement_analysis',
    analyze_project:'requirement_analysis',
    capability_design:'analyze_project',
    tool_mcp_decision:'capability_design',
    agent_architecture:'tool_mcp_decision',
    database_design:'agent_architecture',
    target_workflow_design:'database_design',
    project_file_plan:'target_workflow_design',
    requirement_coverage_gate:'project_file_plan',
    settings_requirement_analysis:'requirement_coverage_gate',
    settings_schema_design:'settings_requirement_analysis',
    settings_ui_design:'settings_schema_design',
    checkpoint:'settings_ui_design',
    approval:'checkpoint',
    code_generation:'code_generation',
    settings_generator:'code_generation',
    settings_validation:'settings_generator',
    build_artifact_validation:'settings_validation',
    as_built_architecture:'build_artifact_validation',
    architecture_conformance:'as_built_architecture',
    environment_configuration:'architecture_conformance',
    test:'environment_configuration',
    debug:'test',
    package_completion:'test',
    review:'package_completion',
  }
  if(previous[raw]) return previous[raw]
  const upper=String(status||'').toUpperCase()
  if(upper.includes('TEST')) return 'environment_configuration'
  if(upper.includes('ARCHITECTURE')) return 'as_built_architecture'
  if(upper.includes('SETTINGS')) return 'settings_generator'
  if(upper.includes('CODE_PLAN')||upper.includes('COVERAGE')) return 'project_file_plan'
  return 'settings_validation'
}


function AgentBuildActionBar({
  stage='REQUIREMENTS',
  busy=false,
  message='',
  workflowEnabled=true,
  onWorkflow,
  onCreateProject,
  onStartDevelopment,
  onRedevelop,
  redevelopmentEnabled=false,
  redevelopmentInfo=null,
  onStop,
  compact=false,
}){
  const workflowReady=[
    'WORKFLOW_READY',
    'PROJECT_CREATED',
    'BUILDING'
  ].includes(stage)

  const projectReady=[
    'PROJECT_CREATED',
    'BUILDING'
  ].includes(stage)

  return <div className={`shared-build-actions ${compact?'compact':''}`}>
    <div className="shared-build-stage">
      <span className="done">1</span>
      <b>요구사항</b>
      <i>→</i>

      <span className={workflowReady?'done':'active'}>2</span>
      <b>설계</b>
      <i>→</i>

      <span className={projectReady?'done':''}>3</span>
      <b>프로젝트</b>
      <i>→</i>

      <span className={stage==='BUILDING'?'done':''}>4</span>
      <b>개발/검증</b>
    </div>

    <div className="shared-build-buttons">
      <button
        type="button"
        className={stage==='REQUIREMENTS'?'primary':''}
        disabled={busy||!workflowEnabled||stage==='BUILDING'}
        onClick={onWorkflow}
      >
        ◇ 설계 검토
      </button>

      <button
        type="button"
        className={stage==='WORKFLOW_READY'||(stage==='REQUIREMENTS'&&workflowEnabled)?'primary':''}
        disabled={busy||stage==='BUILDING'||stage==='PROJECT_CREATED'||(stage==='REQUIREMENTS'&&!workflowEnabled)}
        onClick={onCreateProject}
        title={stage==='REQUIREMENTS'?'Workflow/DB 설계를 준비합니다. DB가 필요하면 설계 확인 후 프로젝트를 생성합니다.':'확정된 설계를 기준으로 프로젝트를 생성합니다.'}
      >
        ＋ 프로젝트 생성
      </button>

      <button
        type="button"
        className={stage==='PROJECT_CREATED'?'primary success':''}
        disabled={busy||stage!=='PROJECT_CREATED'||redevelopmentEnabled}
        onClick={onStartDevelopment}
        title={redevelopmentEnabled?'이전 실패 기록이 있으므로 재개발 시작을 사용하세요.':'처음 개발을 시작합니다.'}
      >
        ▶ 개발 시작
      </button>

      <button
        type="button"
        className={redevelopmentEnabled?'redevelopment-start-button active':'redevelopment-start-button'}
        disabled={busy||!redevelopmentEnabled}
        onClick={onRedevelop}
        title={redevelopmentEnabled
          ? `이전 실패 ${redevelopmentInfo?.failure_stage||'지점'} 직전 단계(${redevelopmentInfo?.resume_from_node||'-'})부터 재개합니다.`
          : '프로젝트 이름/경로에서 재개 가능한 실패 기록이 확인되면 활성화됩니다.'}
      >
        ↻ 재개발 시작
      </button>
      {busy&&onStop&&<button type="button" className="execution-stop-button" onClick={onStop}>■ 실행 정지</button>}
    </div>

    {redevelopmentEnabled&&
      <div className="shared-redevelopment-info">
        <strong>이전 개발 실패 기록 발견</strong>
        <span>{redevelopmentInfo?.status||'FAILED'} · 실패 단계 {redevelopmentInfo?.failure_stage||'-'} · 재개 {redevelopmentInfo?.resume_from_node||'-'}부터</span>
      </div>
    }
    {message&&<div className="shared-build-message">{message}</div>}
  </div>
}

function IDE() {
  const [root,setRoot]=useState('')
  // Keep the last authoritative project root that successfully populated the
  // file tree. React project/root state can briefly be empty while project
  // switching or DB metadata refreshes are in flight; file operations must not
  // lose the root during that transient window.
  const workspaceRootRef=useRef('')
  // The file tree has its own authoritative root. Some project-open flows can
  // populate the tree before React's project/root state has committed, so file
  // operations must be able to use the exact root that produced the visible tree.
  const fileTreeRootRef=useRef('')

  const [newAgentName,setNewAgentName]=useState('')
  const [newAgentProjectRoot,setNewAgentProjectRoot]=useState('')
  const [newAgentCachePath,setNewAgentCachePath]=useState('')
  const [newAgentTempPath,setNewAgentTempPath]=useState('')
  const [newAgentOutputPath,setNewAgentOutputPath]=useState('')
  const [newAgentVenvPath,setNewAgentVenvPath]=useState('')
  const [newAgentModelsPath,setNewAgentModelsPath]=useState('')
  const [newAgentCreateResult,setNewAgentCreateResult]=useState(null)
  const [projectListOpen,setProjectListOpen]=useState(false)
  const [projectSwitcherOpen,setProjectSwitcherOpen]=useState(false)
  const [projectList,setProjectList]=useState([])
  const [projectListLoading,setProjectListLoading]=useState(false)
  const [selectedProjectId,setSelectedProjectId]=useState(null)
  const [screen,setScreen]=useState('HOME')
  const [weatherDashboard,setWeatherDashboard]=useState(null)
  const [weatherBusy,setWeatherBusy]=useState(false)
  const [weatherError,setWeatherError]=useState('')
  const weatherRequestTokenRef=useRef(0)
  const [showPathSettings,setShowPathSettings]=useState(false)
  const [usageOpen,setUsageOpen]=useState(false)
  const [commandPaletteOpen,setCommandPaletteOpen]=useState(false)
  const [agentWorkCenterOpen,setAgentWorkCenterOpen]=useState(false)
  const [builderStarted,setBuilderStarted]=useState(false)
  const [defaultPaths,setDefaultPaths]=useState({})

  const [projectLoadMessage,setProjectLoadMessage]=useState('')
  const [projectTerminalSessions,setProjectTerminalSessions]=useState({})
  const [activeTerminalProjectId,setActiveTerminalProjectId]=useState(null)
  const terminalSocketsRef=useRef({})
  const terminalIntentionalCloseRef=useRef({})
  const terminalOutputRefs=useRef({})
  const terminalInlineInputRef=useRef(null)
  const xtermInstancesRef=useRef({})
  const xtermContainersRef=useRef({})
  const xtermFitAddonsRef=useRef({})
  const xtermDisposablesRef=useRef({})
  const xtermCommandBuffersRef=useRef({})
  const xtermCommandHistoryRef=useRef({})
  const xtermHistoryIndexRef=useRef({})
  const xtermCursorIndexRef=useRef({})
  const xtermPromptRef=useRef({})
  const xtermOutputParseBufferRef=useRef({})
  const xtermRequiredColsRef=useRef({})
  const xtermSetCommandLineRef=useRef({})
  // Keyboard-only terminal text selection state. Shift+Up/Down extends the
  // selected buffer lines without feeding arrow escape sequences into the
  // local command-history handler. This mirrors the familiar terminal
  // selection workflow while preserving normal Up/Down history navigation.
  const xtermKeyboardSelectionRef=useRef({})
  const terminalCommandBusyRef=useRef({})
  const terminalCwdRef=useRef({})
  const terminalRootRef=useRef({})
  const terminalCompletionRef=useRef(null)
  const terminalCompletionTimerRef=useRef({})
  const [terminalCompletion,setTerminalCompletion]=useState(null)

  // v5.189: 터미널은 일반 콘솔처럼 현재 화면 폭에 맞춰 자동 줄바꿈합니다.
  // 입력/터미널 선택 시 가로 스크롤 위치를 강제로 변경하는 로직은 사용하지 않습니다.
  const scrollTerminalHorizontallyToEnd=()=>{}
  const scrollTerminalHorizontallyToStart=()=>{}
  const scrollTerminalHorizontallyToCaret=()=>{}

  const fitTerminalViewport=(id)=>{
    const term=xtermInstancesRef.current[id]
    const container=xtermContainersRef.current[id]
    const fit=xtermFitAddonsRef.current[id]
    if(!term||!container) return

    const rect=container.getBoundingClientRect?.()
    if(!rect||rect.width<120||rect.height<80) return

    // 동적으로 열 수를 늘려 가로 스크롤을 만드는 대신,
    // 현재 보이는 터미널 폭/높이에 맞는 cols/rows만 적용합니다.
    let proposed=null
    try{ proposed=fit?.proposeDimensions?.()||null }catch{}

    const targetCols=Math.max(20,proposed?.cols||term.cols||80)
    // xterm의 마지막 입력 줄/커서가 컨테이너 하단에 가려지지 않도록
    // 화면에 맞는 행 수에서 1행을 안전 여백으로 확보합니다.
    const proposedRows=proposed?.rows||term.rows||24
    const targetRows=Math.max(2,proposedRows-1)

    try{
      container.style.removeProperty('--terminal-min-width')
      container.style.removeProperty('--terminal-required-cols')
    }catch{}

    try{
      if(term.cols!==targetCols||term.rows!==targetRows){
        term.resize(targetCols,targetRows)
      }
    }catch{}
  }

  const fileLoadTokenRef=useRef(0)
  // v5.363: every project/new-Agent context gets an epoch.  Pending async
  // analysis from an older project must never write back into the new design.
  const projectContextEpochRef=useRef(0)


  const [terminalConnectionState,setTerminalConnectionState]=useState({})
  const [terminalErrors,setTerminalErrors]=useState({})



  const [gitInfo,setGitInfo]=useState(null)
  const [gitInfoLoading,setGitInfoLoading]=useState(false)
  const [gitCommitMessage,setGitCommitMessage]=useState('')
  const [gitActionBusy,setGitActionBusy]=useState('')
  const [gitActionResult,setGitActionResult]=useState(null)


  const [projectLoadProgress,setProjectLoadProgress]=useState({
    active:false,
    percent:0,
    message:'',
    failed:false
  })

  const [externalProjectPath,setExternalProjectPath]=useState('')
  const [externalProjectAnalysis,setExternalProjectAnalysis]=useState(null)
  const [externalProjectLoading,setExternalProjectLoading]=useState(false)
  const [externalProjectPickerLoading,setExternalProjectPickerLoading]=useState(false)
  const [externalProjectPickerMessage,setExternalProjectPickerMessage]=useState('')

  const [externalProjectProgress,setExternalProjectProgress]=useState(0)
  const [externalProjectStatus,setExternalProjectStatus]=useState('')
  const [externalProjectStep,setExternalProjectStep]=useState('')
  const [externalProjectMode,setExternalProjectMode]=useState(false)
  const [loadedProjectAnalysis,setLoadedProjectAnalysis]=useState(null)
  const [files,setFiles]=useState([])
  const [projectFileSearch,setProjectFileSearch]=useState('')
  const [fileLoading,setFileLoading]=useState(false)
  const [fileLoadingPath,setFileLoadingPath]=useState('')
  const [editorLoadErrors,setEditorLoadErrors]=useState({})
  const [fileCreateLoading,setFileCreateLoading]=useState(false)
  const fileCreateBusyRef=useRef(false)
  const [projectDirs,setProjectDirs]=useState([])
  const [selected,setSelected]=useState('')
  const [openEditorFiles,setOpenEditorFiles]=useState([])
  const [editorFileContents,setEditorFileContents]=useState({})
  const editorFileContentsRef=useRef({})
  const [editorFileDirty,setEditorFileDirty]=useState({})
  const [editorFileDiskMeta,setEditorFileDiskMeta]=useState({})
  const editorFileDiskMetaRef=useRef({})
  // Remember the project root for every opened relative path so an editor tab
  // never falls back to another project's root after project switching.
  const editorFileRootRef=useRef({})
  const [editorExternalState,setEditorExternalState]=useState({})
  const [pdfPreviewRevision,setPdfPreviewRevision]=useState({})
  const [presentationPreviewRevision,setPresentationPreviewRevision]=useState({})
  const projectFileSnapshotRef=useRef(null)
  const fileWatchBusyRef=useRef(false)
  const openEditorFilesRef=useRef([])
  const editorFileDirtyRef=useRef({})
  const selectedEditorFileRef=useRef('')
  const [pinnedEditorFiles,setPinnedEditorFiles]=useState([])
  const [fileSaveStatus,setFileSaveStatus]=useState('')
  const [editorTabMenu,setEditorTabMenu]=useState(null)
  const [editorFilesMenu,setEditorFilesMenu]=useState(null)
  const [editorCloseConfirm,setEditorCloseConfirm]=useState(null)
  const [webBrowserTabs,setWebBrowserTabs]=useState(()=>[{
    id:DEFAULT_WEB_BROWSER_ID,
    title:'Chrome',
    url:'',
    history:[],
    historyIndex:-1,
    revision:0,
    fixed:true
  }])
  const [activeWebBrowserId,setActiveWebBrowserId]=useState(DEFAULT_WEB_BROWSER_ID)
  const [webUrlDetectionEnabled,setWebUrlDetectionEnabled]=useState(true)
  const [detectedWebService,setDetectedWebService]=useState(null)
  const detectedWebUrlsRef=useRef(new Set())
  const [fileTreeSelectedPaths,setFileTreeSelectedPaths]=useState([])
  const fileTreeSelectionAnchorRef=useRef('')
  const [fileTreeContextMenu,setFileTreeContextMenu]=useState(null)
  const [fileDeleteConfirm,setFileDeleteConfirm]=useState(null)
  const [externalChangeConfirm,setExternalChangeConfirm]=useState(null)
  const [externalFileNotifications,setExternalFileNotifications]=useState([])
  const [externalNotificationOpen,setExternalNotificationOpen]=useState(false)


  const [code,setCode]=useState('')
  const [focusOwner,setFocusOwner]=useState('editor')
  const focusOwnerRef=useRef('editor')
  const editorInstanceRef=useRef(null)
  const editorBookmarkDecorationIdsRef=useRef([])
  const [editorBookmarkRevision,setEditorBookmarkRevision]=useState(0)
  const notebookEditorControllerRef=useRef(null)
  const editorTabsScrollRef=useRef(null)
  const [editorTextSearchOpen,setEditorTextSearchOpen]=useState(false)
  const [editorTextSearchScope,setEditorTextSearchScope]=useState('CURRENT')
  const [editorTextSearchQuery,setEditorTextSearchQuery]=useState('')
  const [editorTextSearchResults,setEditorTextSearchResults]=useState([])
  const [editorTextSearchBusy,setEditorTextSearchBusy]=useState(false)
  const [editorTextSearchError,setEditorTextSearchError]=useState('')
  const [editorTextSearchMeta,setEditorTextSearchMeta]=useState(null)
  const editorTextSearchInputRef=useRef(null)
  const editorTextSearchRequestRef=useRef(0)
  const [pdfSearchNavigation,setPdfSearchNavigation]=useState({})

  const setFocusOwnerSafe=(owner)=>{
    focusOwnerRef.current=owner
    setFocusOwner(owner)
  }

  const isTextEntryFocused=()=>{
    if(typeof document==='undefined') return false
    const el=document.activeElement
    if(!el) return false
    const tag=String(el.tagName||'').toLowerCase()
    return tag==='textarea'||tag==='input'||tag==='select'||!!el.isContentEditable
  }

  const canAutoFocusTerminal=()=>
    focusOwnerRef.current==='terminal'&&!isTextEntryFocused()

  const activeWebBrowserTab=webBrowserTabs.find(tab=>tab.id===activeWebBrowserId)||webBrowserTabs[0]||null

  const activateWebBrowser=(tabId)=>{
    if(!tabId) return
    setWorkspaceTab('BROWSER')
    setActiveWebBrowserId(tabId)
    setEditorTabMenu(null)
    setEditorFilesMenu(null)
    setFocusOwnerSafe('editor')
  }

  const updateWebBrowserTab=(tabId,updater)=>{
    setWebBrowserTabs(prev=>prev.map(tab=>tab.id===tabId?updater(tab):tab))
  }

  const navigateWebBrowser=(tabId,value,{replace=false}={})=>{
    const url=normalizeBrowserUrl(value)
    const current=webBrowserTabs.find(tab=>tab.id===tabId)
    if(current&&(current.remoteSessionId||usesBackendBrowserProxy(current.url))&&!usesBackendBrowserProxy(url)){
      const remoteSessionId=current.remoteSessionId||current.id
      api(`/web-browser/chromium/${encodeURIComponent(remoteSessionId)}`,{method:'DELETE'}).catch(()=>{})
    }
    updateWebBrowserTab(tabId,tab=>{
      if(!url){
        return {...tab,url:'',history:[],historyIndex:-1,revision:tab.revision+1,title:tab.fixed?'Chrome':'Browser'}
      }
      if(replace&&tab.historyIndex>=0){
        const history=[...tab.history]
        history[tab.historyIndex]=url
        return {...tab,url,history,revision:tab.revision+1,title:tab.fixed?'Chrome':browserTitleForUrl(url)}
      }
      const base=tab.historyIndex>=0?tab.history.slice(0,tab.historyIndex+1):[]
      const history=[...base,url]
      return {...tab,url,history,historyIndex:history.length-1,revision:tab.revision+1,title:tab.fixed?'Chrome':browserTitleForUrl(url)}
    })
    activateWebBrowser(tabId)
  }

  const openWebBrowserTab=(value='',{preferFixed=false,detected=false,remoteSessionId=''}={})=>{
    const url=normalizeBrowserUrl(value)
    if(preferFixed){
      navigateWebBrowser(DEFAULT_WEB_BROWSER_ID,url)
      return DEFAULT_WEB_BROWSER_ID
    }
    const id=`web-browser-${Date.now()}-${Math.random().toString(36).slice(2,7)}`
    const tab={
      id,
      title:url?browserTitleForUrl(url):'Browser',
      url,
      history:url?[url]:[],
      historyIndex:url?0:-1,
      revision:0,
      fixed:false,
      detected:!!detected,
      remoteSessionId:remoteSessionId||undefined
    }
    setWebBrowserTabs(prev=>[...prev,tab])
    setWorkspaceTab('BROWSER')
    setActiveWebBrowserId(id)
    setFocusOwnerSafe('editor')
    return id
  }

  const syncRemoteWebBrowserState=(tabId,state)=>{
    const rawUrl=String(state?.url||'').trim()
    const url=/^https?:\/\//i.test(rawUrl)?normalizeBrowserUrl(rawUrl):''
    updateWebBrowserTab(tabId,tab=>{
      const nextTitle=tab.fixed?'Chrome':String(state?.title||'').trim()||browserTitleForUrl(url||tab.url)
      if(!url) return nextTitle===tab.title?tab:{...tab,title:nextTitle}
      if(tab.url===url) return nextTitle===tab.title?tab:{...tab,title:nextTitle}
      const base=tab.historyIndex>=0?tab.history.slice(0,tab.historyIndex+1):[]
      const history=base[base.length-1]===url?base:[...base,url]
      return {...tab,url,title:nextTitle,history,historyIndex:history.length-1}
    })
  }

  const openRemoteWebBrowserPopup=(parentTabId,popup)=>{
    const remoteSessionId=String(popup?.session_id||'').trim()
    if(!remoteSessionId) return
    setWebBrowserTabs(prev=>{
      const existing=prev.find(tab=>tab.remoteSessionId===remoteSessionId)
      if(existing){
        setActiveWebBrowserId(existing.id)
        return prev
      }
      const rawUrl=String(popup?.url||'').trim()
      const url=/^https?:\/\//i.test(rawUrl)?normalizeBrowserUrl(rawUrl):''
      const id=`web-browser-${Date.now()}-${Math.random().toString(36).slice(2,7)}`
      const title=String(popup?.title||'').trim()||browserTitleForUrl(url)||'Popup'
      setActiveWebBrowserId(id)
      return [...prev,{
        id,
        title,
        url,
        history:url?[url]:[],
        historyIndex:url?0:-1,
        revision:0,
        fixed:false,
        detected:false,
        remoteSessionId
      }]
    })
    setWorkspaceTab('BROWSER')
    setFocusOwnerSafe('editor')
  }

  const closeWebBrowserTab=(tabId)=>{
    if(tabId===DEFAULT_WEB_BROWSER_ID) return
    const closing=webBrowserTabs.find(tab=>tab.id===tabId)
    const remoteSessionId=closing?.remoteSessionId||tabId
    api(`/web-browser/chromium/${encodeURIComponent(remoteSessionId)}`,{method:'DELETE'}).catch(()=>{})
    setWebBrowserTabs(prev=>{
      const index=prev.findIndex(tab=>tab.id===tabId)
      const next=prev.filter(tab=>tab.id!==tabId)
      if(activeWebBrowserId===tabId){
        const fallback=next[Math.min(Math.max(index-1,0),Math.max(next.length-1,0))]||next.find(tab=>tab.fixed)||null
        setActiveWebBrowserId(fallback?.id||DEFAULT_WEB_BROWSER_ID)
      }
      return next
    })
  }

  const stepWebBrowserHistory=(tabId,direction)=>{
    updateWebBrowserTab(tabId,tab=>{
      const nextIndex=Math.max(0,Math.min(tab.history.length-1,tab.historyIndex+direction))
      if(nextIndex===tab.historyIndex||!tab.history[nextIndex]) return tab
      return {...tab,url:tab.history[nextIndex],historyIndex:nextIndex,revision:tab.revision+1}
    })
  }

  const reloadWebBrowser=(tabId)=>updateWebBrowserTab(tabId,tab=>({...tab,revision:tab.revision+1}))
  const homeWebBrowser=(tabId)=>{
    const current=webBrowserTabs.find(tab=>tab.id===tabId)
    if(current&&(current.remoteSessionId||usesBackendBrowserProxy(current.url))){
      const remoteSessionId=current.remoteSessionId||current.id
      api(`/web-browser/chromium/${encodeURIComponent(remoteSessionId)}`,{method:'DELETE'}).catch(()=>{})
    }
    updateWebBrowserTab(tabId,tab=>({...tab,url:'',history:[],historyIndex:-1,revision:tab.revision+1,title:tab.fixed?'Chrome':'Browser',remoteSessionId:undefined}))
  }
  const openWebBrowserExternal=(value)=>{
    const url=normalizeBrowserUrl(value)
    if(url) window.open(url,'_blank','noopener,noreferrer')
  }

  const detectTerminalWebServices=(sessionId,text)=>{
    if(!webUrlDetectionEnabled||!text) return
    for(const url of extractLocalDevelopmentUrls(text)){
      if(detectedWebUrlsRef.current.has(url)) continue
      setDetectedWebService(current=>{
        if(current) return current
        detectedWebUrlsRef.current.add(url)
        return {url,sessionId,detectedAt:Date.now()}
      })
      break
    }
  }

  const scrollEditorTabs=(direction=1)=>{
    const strip=editorTabsScrollRef.current
    if(!strip) return
    const distance=Math.max(260,Math.min(520,Math.round(strip.clientWidth*0.72)))
    strip.scrollBy({left:direction*distance,behavior:'smooth'})
  }

  useEffect(()=>{
    const strip=editorTabsScrollRef.current
    if(!strip||!selected) return
    const active=Array.from(strip.querySelectorAll('.code-file-tab'))
      .find(node=>node?.dataset?.editorPath===selected)
    active?.scrollIntoView({behavior:'smooth',block:'nearest',inline:'nearest'})
  },[selected,openEditorFiles.length])

  const provider='auto'
  const [aiRuntimeStatus,setAiRuntimeStatus]=useState(null)
  const [aiModeMenuOpen,setAiModeMenuOpen]=useState(false)
  const [aiModeBusy,setAiModeBusy]=useState(false)
  const [aiModeError,setAiModeError]=useState('')
  const [tab,setTab]=useState('TERMINAL')
  const [terminal,setTerminal]=useState('')
  const [command,setCommand]=useState('git status')
  const [jobs,setJobs]=useState({})
  const [workflowReq,setWorkflowReq]=useState('')
  const [uiLayoutConfig,setUiLayoutConfig]=useState(null)
  const [uiLayoutGalleryOpen,setUiLayoutGalleryOpen]=useState(false)
  const [confirmedInterviewRequirements,setConfirmedInterviewRequirements]=useState({})
  const [designProjectId,setDesignProjectId]=useState(null)
  const [designProjectSavedAt,setDesignProjectSavedAt]=useState('')
  const [designProjectVersion,setDesignProjectVersion]=useState(1)
  const [designFeatureRegistry,setDesignFeatureRegistry]=useState([])
  const [designProjectSaving,setDesignProjectSaving]=useState(false)
  const [requirementDraftRestored,setRequirementDraftRestored]=useState(false)
  const [requirementDraftSavedAt,setRequirementDraftSavedAt]=useState('')
  const [requirementDraftCandidate,setRequirementDraftCandidate]=useState(null)
  const [requirementDraftDecisionPending,setRequirementDraftDecisionPending]=useState(false)
  const requirementDraftDecisionPendingRef=useRef(false)
  const [restoredBuildResume,setRestoredBuildResume]=useState(null)
  const [redevelopmentInfo,setRedevelopmentInfo]=useState(null)
  const requirementCheckpointSignatureRef=useRef('')
  const builderMessagesEndRef=useRef(null)
  const [workflow,setWorkflow]=useState(null)
  const [workflowDefinition,setWorkflowDefinition]=useState(null)
  const [workflowView,setWorkflowView]=useState('STUDIO')
  const [targetWorkflowPreview,setTargetWorkflowPreview]=useState(null)
  const [previousTargetWorkflowPreview,setPreviousTargetWorkflowPreview]=useState(null)
  const [targetWorkflowLoading,setTargetWorkflowLoading]=useState(false)
  const [workflowProgress,setWorkflowProgress]=useState({
    active:false,
    percent:0,
    stage:'대기',
    detail:'',
    startedAt:null
  })
  const [developmentProgress,setDevelopmentProgress]=useState({
    active:false,
    percent:0,
    stage:'대기',
    detail:'',
    startedAt:null,
    elapsedSeconds:0,
    events:[]
  })
  const [developmentFinalStatus,setDevelopmentFinalStatus]=useState(null)
  const [targetWorkflowError,setTargetWorkflowError]=useState('')
  const [targetWorkflowQuality,setTargetWorkflowQuality]=useState(null)
  const [databaseDesignFinalizeBusy,setDatabaseDesignFinalizeBusy]=useState(false)
  const [liveDatabasePreview,setLiveDatabasePreview]=useState(null)
  const [liveDatabasePreviewLoading,setLiveDatabasePreviewLoading]=useState(false)
  const [liveDatabasePreviewError,setLiveDatabasePreviewError]=useState('')
  const [liveDatabasePreviewTab,setLiveDatabasePreviewTab]=useState('MODULES')
  const [agentBuildStage,setAgentBuildStage]=useState('REQUIREMENTS')
  const [agentBuildBusy,setAgentBuildBusy]=useState(false)
  const [projectCreateFlowBusy,setProjectCreateFlowBusy]=useState(false)
  const [agentBuildMessage,setAgentBuildMessage]=useState('')
  const [codingStyleReport,setCodingStyleReport]=useState(null)
  const [llmUsageSummary,setLlmUsageSummary]=useState(null)
  const [llmCatalog,setLlmCatalog]=useState(null)
  const [llmHistory,setLlmHistory]=useState(null)
  const [llmCatalogLoading,setLlmCatalogLoading]=useState(false)
  const [llmCatalogError,setLlmCatalogError]=useState('')
  const [llmUsageScope,setLlmUsageScope]=useState('today')
  const [llmUsageDate,setLlmUsageDate]=useState(localIsoDate)
  const [llmUsageMonth,setLlmUsageMonth]=useState(localIsoMonth)
  const [reportGeneratedAt,setReportGeneratedAt]=useState('')
  const [pptExportBusy,setPptExportBusy]=useState('')
  const [pptExportError,setPptExportError]=useState('')
  const [dbErdReport,setDbErdReport]=useState(null)
  const [dbErdBusy,setDbErdBusy]=useState(false)
  const [dbErdError,setDbErdError]=useState('')
  const [analysis,setAnalysis]=useState(null)
  const [mcpName,setMcpName]=useState('Local MCP')
  const [mcpEndpoint,setMcpEndpoint]=useState('http://127.0.0.1:8001/mcp')
  const [mcpServers,setMcpServers]=useState([])
  const [mcpTools,setMcpTools]=useState([])
  const [mcpAddOpen,setMcpAddOpen]=useState(false)
  const [mcpAddBusy,setMcpAddBusy]=useState(false)
  const [mcpAddError,setMcpAddError]=useState('')
  const [mcpAddForm,setMcpAddForm]=useState({
    name:'',
    endpoint:'',
    trust_level:'UNTRUSTED',
    allow_read_without_prompt:false,
    allow_write_without_prompt:false,
  })
  const [memoryQuery,setMemoryQuery]=useState('')
  const [memoryResult,setMemoryResult]=useState([])











  const [chat,setChat]=useState([{role:'assistant',content:'만들고 싶은 AI Agent + MCP 프로그램을 말씀해 주세요. 필요한 질문은 한 번에 하나씩 하겠습니다.'}])
  const [interviewAttachments,setInterviewAttachments]=useState([])
  const [interviewAttachmentMemory,setInterviewAttachmentMemory]=useState('')
  const [interviewAttachmentSummary,setInterviewAttachmentSummary]=useState('')
  const [interviewAttachmentSummaryFiles,setInterviewAttachmentSummaryFiles]=useState([])
  const [interviewAttachmentRequirements,setInterviewAttachmentRequirements]=useState([])
  const [interviewAttachmentRequirementCoverage,setInterviewAttachmentRequirementCoverage]=useState({})
  const [interviewAttachmentSummaryBusy,setInterviewAttachmentSummaryBusy]=useState(false)
  const [interviewAttachmentSummaryError,setInterviewAttachmentSummaryError]=useState('')
  const interviewAttachmentSummaryRunRef=useRef('')
  const interviewAbortRef=useRef(null)
  const interviewSummaryAbortRef=useRef(null)
  const [interviewRetryPayload,setInterviewRetryPayload]=useState(null)
  const [interviewActivityError,setInterviewActivityError]=useState('')
  const [requirementManualOverrides,setRequirementManualOverrides]=useState({})
  const [requirementRedefineId,setRequirementRedefineId]=useState('')
  const [requirementRedefineText,setRequirementRedefineText]=useState('')
  const [interviewAttachmentAnalysis,setInterviewAttachmentAnalysis]=useState({busy:false,ready:true,overallProgress:100,failedFiles:0,successfulFiles:0,files:[]})
  const [input,setInput]=useState('')
  const [busy,setBusy]=useState(false)
  const [workspaceTab,setWorkspaceTab]=useState('DESIGN')
  const [workspaceLeftCollapsed,setWorkspaceLeftCollapsed]=useState(()=>{
    try{return localStorage.getItem('agentstudio.workspace.leftCollapsed')==='1'}catch{return false}
  })
  const [workspaceRightCollapsed,setWorkspaceRightCollapsed]=useState(()=>{
    try{return localStorage.getItem('agentstudio.workspace.rightCollapsed')==='1'}catch{return false}
  })
  const [workspaceBottomCollapsed,setWorkspaceBottomCollapsed]=useState(()=>{
    try{return localStorage.getItem('agentstudio.workspace.bottomCollapsed')==='1'}catch{return false}
  })
  const [workspaceBottomHeight,setWorkspaceBottomHeight]=useState(()=>{
    try{
      const saved=Number(localStorage.getItem('agentstudio.workspace.bottomHeight'))
      return Number.isFinite(saved)&&saved>=305?saved:305
    }catch{return 305}
  })
  const workspaceLayoutRef=useRef(null)
  const workspaceResizeCleanupRef=useRef(null)
  const workspaceBottomResizeCleanupRef=useRef(null)
  const [workspaceResizeSide,setWorkspaceResizeSide]=useState(null)
  const [workspaceBottomResizing,setWorkspaceBottomResizing]=useState(false)
  const [workspaceLeftWidth,setWorkspaceLeftWidth]=useState(()=>{
    try{
      const saved=Number(localStorage.getItem('agentstudio.workspace.leftWidth'))
      return Number.isFinite(saved)&&saved>=230?saved:270
    }catch{return 270}
  })
  const [workspaceRightWidth,setWorkspaceRightWidth]=useState(()=>{
    try{
      const saved=Number(localStorage.getItem('agentstudio.workspace.rightWidth'))
      return Number.isFinite(saved)&&saved>=260?saved:300
    }catch{return 300}
  })
  const [codeEditPrompt,setCodeEditPrompt]=useState('')
  const [codeEditAttachments,setCodeEditAttachments]=useState([])
  const [codeEditAttachmentAnalysis,setCodeEditAttachmentAnalysis]=useState({busy:false,ready:true,overallProgress:100,failedFiles:0,successfulFiles:0,files:[]})
  const [codeEditScope,setCodeEditScope]=useState('FILE')
  const [codeEditChat,setCodeEditChat]=useState([
    {
      role:'assistant',
      content:'수정할 파일을 선택한 뒤 원하는 변경 내용을 입력하세요. 현재 파일 코드를 기준으로 수정안을 만들고 적용할 수 있습니다.'
    }
  ])
  const codeEditChatRef=useRef(null)
  const [codeEditBusy,setCodeEditBusy]=useState(false)
  const [codeEditProposal,setCodeEditProposal]=useState(null)
  const [codeDiffReview,setCodeDiffReview]=useState(null)
  const [codeRightPanelTab,setCodeRightPanelTab]=useState('FILES')
  const [sqlProfile,setSqlProfile]=useState({
    connection_id:'',
    name:'PostgreSQL 연결',
    db_type:'postgresql',
    host:'127.0.0.1',
    port:5432,
    database:'',
    schema_name:'',
    username:'postgres',
    password:'',
    driver:'ODBC Driver 18 for SQL Server',
    service_name:'FREEPDB1',
    project_id:'',
    service_account_json:'',
    dashboard_url:'',
    ssl_mode:'',
    trust_server_certificate:true,
    credential_saved:false
  })
  const [sqlConnections,setSqlConnections]=useState([])
  const [sqlSupabaseConnectionUrl,setSqlSupabaseConnectionUrl]=useState('')
  const [sqlConnectionImport,setSqlConnectionImport]=useState({busy:false,db_type:'',source_name:'',message:'',error:''})
  const [sqlDatabaseManual,setSqlDatabaseManual]=useState(false)
  const [sqlConnectionStatus,setSqlConnectionStatus]=useState(null)
  const [sqlConnectionBusy,setSqlConnectionBusy]=useState(false)
  const [sqlQueryBusy,setSqlQueryBusy]=useState(false)
  const sqlStopRequestedRef=useRef(false)
  const [pythonExecutionState,setPythonExecutionState]=useState({busy:false,root:'',sessionId:'',label:'',kind:''})
  const pythonStopRequestedRef=useRef(false)
  const [cmdExecution,setCmdExecution]=useState({busy:false,executionId:'',path:'',pid:null})
  const [activeWorkflowJobId,setActiveWorkflowJobId]=useState('')
  const [globalStopBusy,setGlobalStopBusy]=useState(false)
  const [sqlQueryResult,setSqlQueryResult]=useState(null)
  const [sqlResultTab,setSqlResultTab]=useState('DATA')
  const [sqlResultSetIndex,setSqlResultSetIndex]=useState(0)
  const [sqlMessages,setSqlMessages]=useState([])
  const [sqlDbObjects,setSqlDbObjects]=useState(null)
  const [sqlDbObjectsBusy,setSqlDbObjectsBusy]=useState(false)
  const [sqlDbObjectsError,setSqlDbObjectsError]=useState('')
  const [sqlDbObjectExpanded,setSqlDbObjectExpanded]=useState({})
  const [firestoreBrowser,setFirestoreBrowser]=useState(null)
  const [firestoreBrowserBusy,setFirestoreBrowserBusy]=useState(false)
  const [firestoreBrowserError,setFirestoreBrowserError]=useState('')
  const [firestoreCollectionFilter,setFirestoreCollectionFilter]=useState('')
  const [firestoreDocumentFilter,setFirestoreDocumentFilter]=useState('')
  const [firestoreSelectedCollection,setFirestoreSelectedCollection]=useState('')
  const [firestoreDocuments,setFirestoreDocuments]=useState(null)
  const [firestoreDocumentsBusy,setFirestoreDocumentsBusy]=useState(false)
  const [firestoreSelectedDocument,setFirestoreSelectedDocument]=useState('')
  const [firestoreDocumentDetail,setFirestoreDocumentDetail]=useState(null)
  const [firestoreDocumentDetailBusy,setFirestoreDocumentDetailBusy]=useState(false)
  const [firestoreContextMenu,setFirestoreContextMenu]=useState(null)
  const [firestoreScriptBusy,setFirestoreScriptBusy]=useState('')
  const [redisBrowser,setRedisBrowser]=useState(null)
  const [redisBrowserBusy,setRedisBrowserBusy]=useState(false)
  const [redisBrowserError,setRedisBrowserError]=useState('')
  const [redisKeyFilter,setRedisKeyFilter]=useState('')
  const [redisTypeFilter,setRedisTypeFilter]=useState('all')
  const [redisSelectedKey,setRedisSelectedKey]=useState('')
  const [redisKeyDetail,setRedisKeyDetail]=useState(null)
  const [redisKeyDetailBusy,setRedisKeyDetailBusy]=useState(false)
  const [redisKeyExpanded,setRedisKeyExpanded]=useState({})
  const [redisContextMenu,setRedisContextMenu]=useState(null)
  const [redisScriptBusy,setRedisScriptBusy]=useState('')
  const [sqlObjectActionBusy,setSqlObjectActionBusy]=useState('')
  const [sqlObjectContextMenu,setSqlObjectContextMenu]=useState(null)
  const [sqlSchemaContextMenu,setSqlSchemaContextMenu]=useState(null)
  const [sqlDatabaseContextMenu,setSqlDatabaseContextMenu]=useState(null)
  const [sqlAdminPrompt,setSqlAdminPrompt]=useState(null)
  const [sqliteProjectStatus,setSqliteProjectStatus]=useState(null)
  const [sqliteProjectStatusBusy,setSqliteProjectStatusBusy]=useState(false)
  const sqlLoadedRootRef=useRef('')

  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.leftCollapsed',workspaceLeftCollapsed?'1':'0')}catch{}
  },[workspaceLeftCollapsed])
  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.rightCollapsed',workspaceRightCollapsed?'1':'0')}catch{}
  },[workspaceRightCollapsed])
  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.bottomCollapsed',workspaceBottomCollapsed?'1':'0')}catch{}
  },[workspaceBottomCollapsed])
  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.bottomHeight',String(Math.round(workspaceBottomHeight)))}catch{}
  },[workspaceBottomHeight])
  useEffect(()=>{
    const timer=setTimeout(()=>{
      try{window.dispatchEvent(new Event('resize'))}catch(_){}
    },40)
    return ()=>clearTimeout(timer)
  },[workspaceBottomHeight,workspaceBottomCollapsed])
  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.leftWidth',String(Math.round(workspaceLeftWidth)))}catch{}
  },[workspaceLeftWidth])
  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.rightWidth',String(Math.round(workspaceRightWidth)))}catch{}
  },[workspaceRightWidth])
  useEffect(()=>()=>{
    try{workspaceResizeCleanupRef.current?.()}catch{}
    try{workspaceBottomResizeCleanupRef.current?.()}catch{}
  },[])

  const beginWorkspaceBottomResize=(event)=>{
    if(workspaceBottomCollapsed) return
    event.preventDefault()
    event.stopPropagation()
    const main=event.currentTarget?.closest?.('.workspace-main')
    if(!main) return
    const rect=main.getBoundingClientRect()
    const startY=event.clientY
    const startHeight=workspaceBottomHeight
    const minimum=305
    const topMinimum=180
    const maxHeight=Math.max(minimum,rect.height-42-6-topMinimum)
    const previousCursor=document.body.style.cursor
    const previousSelect=document.body.style.userSelect
    document.body.style.cursor='row-resize'
    document.body.style.userSelect='none'
    setWorkspaceBottomResizing(true)

    const onMove=(moveEvent)=>{
      const delta=startY-moveEvent.clientY
      const next=Math.max(minimum,Math.min(maxHeight,startHeight+delta))
      setWorkspaceBottomHeight(next)
    }
    const cleanup=()=>{
      window.removeEventListener('pointermove',onMove)
      window.removeEventListener('pointerup',cleanup)
      window.removeEventListener('pointercancel',cleanup)
      document.body.style.cursor=previousCursor
      document.body.style.userSelect=previousSelect
      setWorkspaceBottomResizing(false)
      workspaceBottomResizeCleanupRef.current=null
    }
    workspaceBottomResizeCleanupRef.current=cleanup
    window.addEventListener('pointermove',onMove)
    window.addEventListener('pointerup',cleanup)
    window.addEventListener('pointercancel',cleanup)
  }

  const getWorkspacePanelMinimum=(side)=>{
    const compact=typeof window!=='undefined'&&window.innerWidth<=1150
    return side==='left'?(compact?230:270):(compact?260:300)
  }

  const beginWorkspacePanelResize=(side,event)=>{
    if((side==='left'&&workspaceLeftCollapsed)||(side==='right'&&workspaceRightCollapsed)) return
    event.preventDefault()
    event.stopPropagation()

    const host=workspaceLayoutRef.current
    if(!host) return
    const rect=host.getBoundingClientRect()
    const startX=event.clientX
    const startWidth=side==='left'?workspaceLeftWidth:workspaceRightWidth
    const otherWidth=side==='left'
      ? (workspaceRightCollapsed?0:workspaceRightWidth)
      : (workspaceLeftCollapsed?0:workspaceLeftWidth)
    const minWidth=getWorkspacePanelMinimum(side)
    const centerMinimum=420
    const maxWidth=Math.max(minWidth,rect.width-otherWidth-centerMinimum)

    const previousCursor=document.body.style.cursor
    const previousSelect=document.body.style.userSelect
    document.body.style.cursor='col-resize'
    document.body.style.userSelect='none'
    setWorkspaceResizeSide(side)

    const onMove=(moveEvent)=>{
      const delta=side==='left'
        ? moveEvent.clientX-startX
        : startX-moveEvent.clientX
      const next=Math.max(minWidth,Math.min(maxWidth,startWidth+delta))
      if(side==='left') setWorkspaceLeftWidth(next)
      else setWorkspaceRightWidth(next)
    }
    const cleanup=()=>{
      window.removeEventListener('pointermove',onMove)
      window.removeEventListener('pointerup',cleanup)
      window.removeEventListener('pointercancel',cleanup)
      document.body.style.cursor=previousCursor
      document.body.style.userSelect=previousSelect
      setWorkspaceResizeSide(null)
      workspaceResizeCleanupRef.current=null
    }
    workspaceResizeCleanupRef.current=cleanup
    window.addEventListener('pointermove',onMove)
    window.addEventListener('pointerup',cleanup)
    window.addEventListener('pointercancel',cleanup)
  }

  useEffect(()=>{
    // 프로젝트를 전환하면 이전 프로젝트의 AI 코드 제안/Diff가 새 프로젝트에
    // 남아 보이지 않도록 검토 상태를 초기화합니다.
    setCodeEditProposal(null)
    setCodeDiffReview(null)
    setCodeRightPanelTab('FILES')
  },[root])

  const scrollCodeEditChatToBottom=(behavior='smooth')=>{
    requestAnimationFrame(()=>{
      const el=codeEditChatRef.current
      if(!el) return
      try{
        el.scrollTo({top:el.scrollHeight,behavior})
      }catch{
        el.scrollTop=el.scrollHeight
      }
    })
  }

  useEffect(()=>{
    // 새 사용자 요청, AI 진행 상태, AI 응답이 추가될 때 가장 최근 메시지를 보여줍니다.
    if(workspaceTab!=='CODE') return
    scrollCodeEditChatToBottom(codeEditBusy?'auto':'smooth')
  },[codeEditChat.length,codeEditBusy,codeEditProposal,workspaceTab])

  const [terminalSessions,setTerminalSessions]=useState([
    {
      id:'terminal-1',
      name:'PowerShell',
      command:'',
      output:'',
      processState:'idle',
      exitCode:null,
    }
  ])
  const [activeTerminalId,setActiveTerminalId]=useState('terminal-1')
  const [terminalNameEditId,setTerminalNameEditId]=useState(null)
  const [terminalNameDraft,setTerminalNameDraft]=useState('')

  const [projectSearch,setProjectSearch]=useState('')
  const [projectFilter,setProjectFilter]=useState('ALL')
  const [projectListStatus,setProjectListStatus]=useState('DB 프로젝트 목록을 아직 읽지 않았습니다.')
  const [projectListLogPath,setProjectListLogPath]=useState('')
  const [projectDbDiagnostic,setProjectDbDiagnostic]=useState(null)


  const [fileTreeExpanded,setFileTreeExpanded]=useState({})
  const [fileTreeSelected,setFileTreeSelected]=useState('')
  const [fileTreeRename,setFileTreeRename]=useState(null)



  useEffect(()=>{const ws=connectJobs(evt=>{
    if(evt.type==='job'){
      setJobs(prev=>{
        const id=evt.job.id
        const before=prev[id]
        if(before&&before.status===evt.job.status&&before.progress===evt.job.progress&&before.message===evt.job.message&&before.result===evt.job.result){
          return prev
        }
        const next={...prev,[id]:evt.job}
        const ids=Object.keys(next)
        if(ids.length<=80) return next
        for(const staleId of ids.slice(0,ids.length-80)) delete next[staleId]
        return next
      })
      if(evt.job.result?.output)setTerminal(evt.job.result.output)

      setPgvectorInstall(current=>{
        if(!current?.job_id || current.job_id!==evt.job.id) return current
        const next={
          ...current,
          status:evt.job.status,
          progress:evt.job.progress||0,
          message:evt.job.message||'',
          result:evt.job.result||{}
        }
        if(evt.job.status==='SUCCESS' || evt.job.status==='FAILED' || evt.job.status==='CANCELLED'){
          setBusy(false)
          if(evt.job.status==='SUCCESS'){
            setTimeout(()=>testOne('pgvector'),300)
          }
        }
        return next
      })
    }
  });return()=>ws.close()},[])


  // v5.371 Global Command Palette: keep typing inside the palette local to the
  // overlay component while Ctrl+K only toggles the lightweight parent flag.
  useEffect(()=>{
    const handleGlobalCommandShortcut=(event)=>{
      if((event.ctrlKey||event.metaKey)&&String(event.key||'').toLowerCase()==='k'){
        event.preventDefault()
        setCommandPaletteOpen(true)
      }
      if(event.key==='Escape'){
        setCommandPaletteOpen(false)
        setAgentWorkCenterOpen(false)
      }
    }
    window.addEventListener('keydown',handleGlobalCommandShortcut)
    return()=>window.removeEventListener('keydown',handleGlobalCommandShortcut)
  },[])

  // v5.370: release browser-side long-lived resources when the SPA unloads.
  useEffect(()=>()=>{
    for(const socket of Object.values(terminalSocketsRef.current||{})){
      try{ socket?.close?.(1000,'app_unmount') }catch{}
    }
    terminalSocketsRef.current={}
    for(const disposable of Object.values(xtermDisposablesRef.current||{})){
      try{ disposable?.dispose?.() }catch{}
    }
    xtermDisposablesRef.current={}
    for(const term of Object.values(xtermInstancesRef.current||{})){
      try{ term?.dispose?.() }catch{}
    }
    xtermInstancesRef.current={}
  },[])



  const chooseAgentFolder=async(setter,currentValue,label)=>{
    try{
      const r=await api('/system/pick-folder',{
        method:'POST',
        body:JSON.stringify({
          title:`${label} 선택`,
          initial_path:currentValue||''
        })
      })
      if(r.ok && !r.cancelled && r.path){
        setter(r.path)
      }
    }catch(e){
      setNewAgentCreateResult({
        ok:false,
        message:'경로 선택 실패: '+String(e)
      })
    }
  }

  const loadDefaultPaths=async()=>{
    try{
      const d=await api('/settings/default-paths')
      setDefaultPaths(d||{})
      // 신규 Agent의 프로젝트 경로는 사용자가 직접 입력하거나 '경로 찾기'로 선택합니다.
      // 시스템 기본 project_root를 실제 input value로 자동 주입하지 않습니다.
      if(!newAgentCachePath && d?.cache_root) setNewAgentCachePath(d.cache_root)
      if(!newAgentTempPath && d?.temp_root) setNewAgentTempPath(d.temp_root)
      if(!newAgentOutputPath && d?.output_root) setNewAgentOutputPath(d.output_root)
      if(!newAgentModelsPath && d?.common_models_root) setNewAgentModelsPath(d.common_models_root)
    }catch(e){}
  }

  useEffect(()=>{
    const timer=setTimeout(()=>{
      saveRequirementDraft()
    },350)

    return()=>clearTimeout(timer)
  },[
    chat,
    workflowReq,
    confirmedInterviewRequirements,
    targetWorkflowPreview,
    targetWorkflowQuality,
    agentBuildStage,
    newAgentName,
    newAgentProjectRoot,
    interviewAttachmentSummary,
    interviewAttachmentMemory,
    requirementManualOverrides,
    designFeatureRegistry,
    uiLayoutConfig,
    restoredBuildResume
  ])

  useEffect(()=>{
    // v5.370: Resume candidates come from both browser localStorage and the
    // project folder. A failed build must be recoverable after a browser restart,
    // another PC session, or localStorage cleanup.
    const projectPath=String(newAgentProjectRoot||'').trim()
    if(!projectPath){
      setRequirementDraftCandidate(null)
      setRequirementDraftDecisionPending(false)
      setRequirementDraftRestored(false)
      setRestoredBuildResume(null)
      setRedevelopmentInfo(null)
      return
    }

    let cancelled=false
    const timer=setTimeout(async()=>{
      try{
        const key=requirementDraftKeyFor(projectPath,newAgentName)
        let localSnapshot=null
        try{
          const raw=localStorage.getItem(key)
          localSnapshot=raw?JSON.parse(raw):null
        }catch{}

        let serverResult=null
        try{
          serverResult=await api(`/workflow/design-checkpoint?project_root=${encodeURIComponent(projectPath)}`)
        }catch(e){
          console.warn('프로젝트 Resume Checkpoint 확인 실패',e)
        }
        if(cancelled) return

        const serverSnapshot=(serverResult?.checkpoint&&typeof serverResult.checkpoint==='object')
          ? serverResult.checkpoint
          : null
        const localTime=Date.parse(String(localSnapshot?.saved_at||''))||0
        const serverTime=Date.parse(String(serverSnapshot?.saved_at||''))||0
        const snapshot=(serverTime>=localTime?serverSnapshot:localSnapshot)||serverSnapshot||localSnapshot
        const runtime=(serverResult?.runtime&&typeof serverResult.runtime==='object')?serverResult.runtime:{}

        if(!snapshot && !serverResult?.available){
          setRequirementDraftCandidate(null)
          setRequirementDraftDecisionPending(false)
          setRequirementDraftRestored(false)
          setRequirementDraftSavedAt('')
          setRestoredBuildResume(null)
          setRedevelopmentInfo(null)
          return
        }

        const buildResume={
          ...(snapshot?.build_resume&&typeof snapshot.build_resume==='object'?snapshot.build_resume:{}),
          source:String(serverResult?.checkpoint_source||snapshot?.build_resume?.source||'LOCAL_DRAFT'),
          run_id:String(
            runtime?.current_run?.run_id
            ||runtime?.workflow_state?.diagnostic_run_id
            ||runtime?.workflow_state?.thread_id
            ||snapshot?.build_resume?.run_id
            ||''
          ),
          status:String(
            runtime?.current_run?.status
            ||runtime?.workflow_state?.diagnostic_status
            ||runtime?.workflow_state?.status
            ||snapshot?.build_resume?.status
            ||''
          ),
          failure_stage:String(runtime?.workflow_state?.diagnostic_failure_stage||snapshot?.build_resume?.failure_stage||''),
          failure_reason:String(runtime?.workflow_state?.diagnostic_failure_reason||runtime?.workflow_state?.error||snapshot?.build_resume?.failure_reason||''),
          project_root:projectPath,
          workflow_state:runtime?.workflow_state||snapshot?.build_resume?.workflow_state||{},
          requirements_snapshot:runtime?.requirements_snapshot||{}
        }

        const redevelopment=(serverResult?.redevelopment&&typeof serverResult.redevelopment==='object')
          ? serverResult.redevelopment
          : null
        setRedevelopmentInfo(redevelopment?.available?redevelopment:null)
        setRequirementDraftCandidate({
          key,
          snapshot,
          build_resume:buildResume,
          redevelopment,
          saved_at:String(snapshot?.saved_at||''),
          agent_name:String(snapshot?.agent_name||''),
          project_root:String(snapshot?.project_root||projectPath),
          source:String(serverResult?.checkpoint_source||(serverTime>=localTime&&serverSnapshot?'PROJECT_CHECKPOINT':'LOCAL_DRAFT'))
        })
        setRequirementDraftDecisionPending(true)
        setRequirementDraftRestored(false)
        setRequirementDraftSavedAt(String(snapshot?.saved_at||''))
      }catch(e){
        console.warn('이전 요구사항/개발 기록 확인 실패',e)
        if(!cancelled){
          setRequirementDraftCandidate(null)
          setRequirementDraftDecisionPending(false)
          setRedevelopmentInfo(null)
        }
      }
    },120)

    return()=>{
      cancelled=true
      clearTimeout(timer)
    }
  },[newAgentProjectRoot,newAgentName])

  useEffect(()=>{
    requirementDraftDecisionPendingRef.current=requirementDraftDecisionPending
  },[requirementDraftDecisionPending])

  useEffect(()=>{loadDefaultPaths()},[])
  useEffect(()=>{refreshProjectList()},[])
  useEffect(()=>{loadWorkflowDefinition()},[])
  useEffect(()=>{
    builderMessagesEndRef.current?.scrollIntoView({
      behavior:'smooth',
      block:'end'
    })
  },[chat,busy])

  const summarizeInterviewAttachments=async()=>{
    if(!interviewAttachments.length || interviewAttachmentSummaryBusy || busy) return
    if(interviewAttachmentAnalysis.busy||!interviewAttachmentAnalysis.ready) return
    if(interviewAttachmentAnalysis.successfulFiles===0&&interviewAttachmentAnalysis.failedFiles>0) return

    const attachmentIds=interviewAttachments
      .map(item=>String(item?.attachment_id||'').trim())
      .filter(Boolean)
    if(!attachmentIds.length) return

    const signature=attachmentIds.join('|')
    const selectedFiles=interviewAttachments.map(item=>({
      name:String(item?.name||''),
      path:String(item?.path||'')
    }))

    interviewAttachmentSummaryRunRef.current=signature
    setInterviewAttachmentSummaryBusy(true)
    setInterviewAttachmentSummaryError('')
    setInterviewActivityError('')
    setInterviewRetryPayload(null)

    const controller=new AbortController()
    interviewSummaryAbortRef.current=controller

    try{
      const result=await api('/chat/interview/attachments/summary',{
        method:'POST',
        signal:controller.signal,
        body:JSON.stringify({
          attachment_ids:attachmentIds,
          attachment_memory:interviewAttachmentMemory,
          provider,
          project_root:newAgentProjectRoot||root||''
        })
      })

      const summary=sanitizeInterviewDisplayText(result?.summary||'')
      if(!result?.ok||!summary){
        throw new Error(
          (Array.isArray(result?.attachment_warnings)&&result.attachment_warnings.length
            ? result.attachment_warnings.join(' / ')
            : '첨부 파일에서 요구사항 요약을 만들지 못했습니다.')
        )
      }

      setInterviewAttachmentSummary(summary)
      setInterviewAttachmentRequirements(Array.isArray(result?.attachment_requirements)?result.attachment_requirements:[])
      setInterviewAttachmentRequirementCoverage(result?.attachment_requirement_coverage&&typeof result.attachment_requirement_coverage==='object'?result.attachment_requirement_coverage:{})
      setInterviewAttachmentSummaryFiles(prev=>{
        const merged=[...prev,...selectedFiles]
        const seen=new Set()
        return merged.filter(item=>{
          const key=String(item.path||item.name||'').toLowerCase()
          if(!key||seen.has(key)) return false
          seen.add(key)
          return true
        })
      })
      setInterviewAttachmentMemory(
        sanitizeInterviewDisplayText(result?.attachment_memory||summary)
      )

      setInterviewAttachments([])
      setInterviewAttachmentAnalysis({
        busy:false,ready:true,overallProgress:100,failedFiles:0,successfulFiles:0,files:[]
      })
      setInterviewRetryPayload(null)

      void api('/ai/attachments/release',{
        method:'POST',
        body:JSON.stringify({attachment_ids:attachmentIds})
      }).catch(()=>{})
    }catch(e){
      const aborted=controller.signal.aborted || String(e?.name||'')==='AbortError'
      interviewAttachmentSummaryRunRef.current=''
      const message=aborted
        ? '첨부 파일 통합 분석을 사용자가 취소했습니다.'
        : '첨부 파일 요구사항 정리 실패: '+String(e?.message||e)
      setInterviewAttachmentSummaryError(message)
      setInterviewActivityError(message)
      setInterviewRetryPayload({type:'SUMMARY'})
    }finally{
      if(interviewSummaryAbortRef.current===controller) interviewSummaryAbortRef.current=null
      setInterviewAttachmentSummaryBusy(false)
    }
  }


  const deferredProjectSearch=useDeferredValue(projectSearch)
  const filteredProjects = useMemo(()=>projectList
    .filter(p=>{
      const q=(deferredProjectSearch||'').trim().toLowerCase()
      if(q && !`${p.name||''} ${p.project_root||''}`.toLowerCase().includes(q)){
        return false
      }

      if(projectFilter==='FAVORITE'){
        return !!p.is_favorite
      }

      if(projectFilter==='RECENT'){
        return !!p.last_opened_at
      }

      return true
    })
    .sort((a,b)=>{
      if(projectFilter==='RECENT'){
        return new Date(b.last_opened_at||0)-new Date(a.last_opened_at||0)
      }
      return (b.is_favorite?1:0)-(a.is_favorite?1:0)
        || new Date(b.last_opened_at||b.updated_at||0)-new Date(a.last_opened_at||a.updated_at||0)
    }),[projectList,deferredProjectSearch,projectFilter])
  const currentProject = projectList.find(p=>p.id===selectedProjectId) || null
  const currentProjectName = currentProject?.name || newAgentName || (root ? root.split(/[\\/]/).filter(Boolean).pop() : '') || '프로젝트 선택'
  const currentProjectPath = currentProject?.project_root || currentProject?.root_path || root || newAgentProjectRoot || ''
  const activeWorkspaceRoot = currentProjectPath
  const resolveWorkspaceRoot=(preferredRoot='')=>{
    const activeTerminalRoot=String(
      terminalSessions.find(item=>item.id===activeTerminalId)?.root
      ||terminalRootRef.current?.[activeTerminalId]
      ||''
    ).trim()

    return String(
      preferredRoot
      ||activeWorkspaceRoot
      ||root
      ||newAgentProjectRoot
      ||fileTreeRootRef.current
      ||workspaceRootRef.current
      ||activeTerminalRoot
      ||externalProjectAnalysis?.project_root
      ||''
    ).trim()
  }

  useEffect(()=>{
    const nextRoot=String(activeWorkspaceRoot||'').trim()
    if(nextRoot){
      workspaceRootRef.current=nextRoot
    }
  },[activeWorkspaceRoot])

  const editorBookmarkKeyForPath=(filePath='')=>{
    const path=normalizeProjectRelativePath(filePath)
    if(!path) return ''
    const projectRoot=String(
      editorFileRootRef.current?.[filePath]
      ||editorFileRootRef.current?.[path]
      ||fileTreeRootRef.current
      ||workspaceRootRef.current
      ||activeWorkspaceRoot
      ||root
      ||newAgentProjectRoot
      ||''
    ).trim()
    return textEditorBookmarkStorageKey(projectRoot,path)
  }
  const getEditorBookmarksForPath=(filePath='')=>{
    if(!isBookmarkableTextEditorFile(filePath)) return []
    return loadTextEditorLineBookmarks(editorBookmarkKeyForPath(filePath))
  }
  const applyEditorBookmarkDecorations=(editor=editorInstanceRef.current,filePath=selectedEditorFileRef.current||selected||'')=>{
    if(!editor?.deltaDecorations) return
    const path=normalizeProjectRelativePath(filePath)
    const model=editor.getModel?.()
    const maxLine=Math.max(1,Number(model?.getLineCount?.()||1))
    const bookmarks=isBookmarkableTextEditorFile(path)?getEditorBookmarksForPath(path):[]
    const decorations=bookmarks
      .filter(line=>line<=maxLine)
      .map(line=>({
        range:{startLineNumber:line,startColumn:1,endLineNumber:line,endColumn:1},
        options:{
          isWholeLine:true,
          glyphMarginClassName:'editor-line-bookmark-glyph',
          glyphMarginHoverMessage:{value:`북마크 · Line ${line}`},
        },
      }))
    editorBookmarkDecorationIdsRef.current=editor.deltaDecorations(editorBookmarkDecorationIdsRef.current||[],decorations)
  }
  const toggleEditorLineBookmark=(filePath=selectedEditorFileRef.current||selected||'',lineNumber=null,editor=editorInstanceRef.current)=>{
    const path=normalizeProjectRelativePath(filePath)
    if(!isBookmarkableTextEditorFile(path)) return
    const positionLine=Number(lineNumber||editor?.getPosition?.()?.lineNumber||1)
    if(!Number.isInteger(positionLine)||positionLine<1) return
    const key=editorBookmarkKeyForPath(path)
    const current=loadTextEditorLineBookmarks(key)
    const exists=current.includes(positionLine)
    storeTextEditorLineBookmarks(key,exists?current.filter(line=>line!==positionLine):[...current,positionLine])
    setEditorBookmarkRevision(value=>value+1)
    window.requestAnimationFrame(()=>applyEditorBookmarkDecorations(editor,path))
    editor?.setPosition?.({lineNumber:positionLine,column:1})
    editor?.revealLineInCenter?.(positionLine)
    editor?.focus?.()
  }
  const moveToEditorBookmark=(direction=1)=>{
    const editor=editorInstanceRef.current
    const path=normalizeProjectRelativePath(selectedEditorFileRef.current||selected||'')
    const bookmarks=getEditorBookmarksForPath(path)
    if(!editor||!bookmarks.length) return
    const currentLine=Math.max(0,Number(editor.getPosition?.()?.lineNumber||0))
    let target
    if(direction>0){
      target=bookmarks.find(line=>line>currentLine)??bookmarks[0]
    }else{
      target=[...bookmarks].reverse().find(line=>line<currentLine)??bookmarks[bookmarks.length-1]
    }
    editor.revealLineInCenter?.(target)
    editor.setPosition?.({lineNumber:target,column:1})
    editor.focus?.()
  }
  const clearEditorBookmarks=()=>{
    const path=normalizeProjectRelativePath(selectedEditorFileRef.current||selected||'')
    const key=editorBookmarkKeyForPath(path)
    const current=loadTextEditorLineBookmarks(key)
    if(!current.length) return
    if(!window.confirm(`현재 파일의 북마크 ${current.length}개를 모두 해제하시겠습니까?`)) return
    storeTextEditorLineBookmarks(key,[])
    setEditorBookmarkRevision(value=>value+1)
    window.requestAnimationFrame(()=>applyEditorBookmarkDecorations(editorInstanceRef.current,path))
  }
  const activeTextEditorBookmarks=isBookmarkableTextEditorFile(selected)?getEditorBookmarksForPath(selected):[]

  useEffect(()=>{
    if(!editorInstanceRef.current) return
    const timer=window.setTimeout(()=>applyEditorBookmarkDecorations(editorInstanceRef.current,selected),0)
    return()=>window.clearTimeout(timer)
  },[selected,editorBookmarkRevision])

  const workspaceSummary = loadedProjectAnalysis?.summary || currentProject?.description || '프로젝트 분석 정보가 아직 없습니다.'
  const isSqlFile=!!selected?.toLowerCase?.().endsWith('.sql')

  const sqlProfileForType=(dbType,previous={})=>{
    const kind=String(dbType||'postgresql').toLowerCase()
    const common={connection_id:'',name:'DB 연결',db_type:kind,host:'',port:0,database:'',schema_name:'',username:'',password:'',driver:'',service_name:'',project_id:'',service_account_json:'',dashboard_url:'',ssl_mode:'',trust_server_certificate:true,credential_saved:false}
    const defaults=kind==='sqlite3'
      ? {...common,name:'SQLite3 연결',db_type:'sqlite3',database:'',driver:'Python sqlite3 (stdlib)'}
      : kind==='firestore'
        ? {...common,name:'Google Cloud Firestore 연결',db_type:'firestore',database:'(default)',driver:'google-cloud-firestore',dashboard_url:'https://console.cloud.google.com/firestore/databases'}
        : kind==='supabase'
          ? {...common,name:'Supabase 연결',db_type:'supabase',host:'',port:5432,database:'postgres',schema_name:'public',username:'postgres',driver:'psycopg',dashboard_url:'https://supabase.com/dashboard',ssl_mode:'require'}
          : kind==='redis'
            ? {...common,name:'Redis 연결',db_type:'redis',host:'127.0.0.1',port:6379,database:'0',username:'',driver:'redis-py'}
          : kind==='mssql'
            ? {...common,name:'MSSQL 연결',db_type:'mssql',host:'127.0.0.1',port:1433,driver:'ODBC Driver 18 for SQL Server'}
            : kind==='oracle'
              ? {...common,name:'Oracle 연결',db_type:'oracle',host:'127.0.0.1',port:1521,service_name:'FREEPDB1'}
              : {...common,name:'PostgreSQL 연결',db_type:'postgresql',host:'127.0.0.1',port:5432,schema_name:'public',username:'postgres'}
    return {...defaults,...previous,db_type:kind,port:(previous.db_type===kind&&previous.port!==undefined)?previous.port:defaults.port}
  }


  const applySupabaseConnectionUrl=()=>{
    const raw=String(sqlSupabaseConnectionUrl||'').trim()
    if(!raw) return
    try{
      const normalized=raw.replace(/^postgresql\+[^:]+:/i,'postgresql:').replace(/^postgres:/i,'postgresql:')
      const parsed=new URL(normalized)
      const host=parsed.hostname||''
      const port=Number(parsed.port||5432)
      const database=decodeURIComponent((parsed.pathname||'/postgres').replace(/^\//,'')||'postgres')
      const username=decodeURIComponent(parsed.username||'postgres')
      const password=decodeURIComponent(parsed.password||'')
      const optionsValue=decodeURIComponent(parsed.searchParams.get('options')||'')
      const optionSchemaMatch=optionsValue.match(/(?:^|\s)-csearch_path=([^\s]+)/i)
      const schemaName=String(parsed.searchParams.get('schema')||parsed.searchParams.get('search_path')||optionSchemaMatch?.[1]||'').split(',')[0].trim()
      if(!host) throw new Error('Host를 읽을 수 없습니다.')
      setSqlProfile(prev=>({...prev,db_type:'supabase',host,port,database,schema_name:schemaName||prev.schema_name||'public',username,password,ssl_mode:prev.ssl_mode||'require'}))
      setSqlSupabaseConnectionUrl('')
      setSqlMessages(prev=>[{type:'info',text:'Supabase Connection URL을 Host/Port/Database/Schema/User/Password로 분해했습니다. 원본 URL은 저장하지 않습니다.',time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`Supabase Connection URL 형식 확인 필요: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }
  }

  const importSqlConnectionFile=async(dbType)=>{
    const kind=String(dbType||'').toLowerCase()
    if(!['supabase','firestore','redis'].includes(kind)) return
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot){
      setSqlConnectionImport({busy:false,db_type:kind,source_name:'',message:'',error:'먼저 프로젝트를 선택하세요.'})
      return
    }
    setSqlConnectionImport({busy:true,db_type:kind,source_name:'',message:'파일 선택창을 여는 중...',error:''})
    try{
      const result=await api('/sql/import-connection-file',{
        method:'POST',
        body:JSON.stringify({root:workspaceRoot,db_type:kind,initial_path:workspaceRoot})
      })
      if(result?.cancelled){
        setSqlConnectionImport({busy:false,db_type:kind,source_name:'',message:'파일 선택을 취소했습니다.',error:''})
        return
      }
      const imported=result?.profile||{}
      const detected=Array.isArray(result?.detected_fields)?result.detected_fields:[]
      const detectedKind=String(result?.db_type||imported?.db_type||kind).toLowerCase()
      const targetKind=['supabase','firestore','redis'].includes(detectedKind)?detectedKind:kind
      setSqlProfile(prev=>{
        const defaults=sqlProfileForType(targetKind)
        const previousDefaultName=sqlProfileForType(prev.db_type||kind).name
        const providerChanged=targetKind!==kind
        const keepName=providerChanged
          ? defaults.name
          : ((!prev.name||prev.name===previousDefaultName)?defaults.name:prev.name)
        const hasImportedPassword=Object.prototype.hasOwnProperty.call(imported,'password')&&String(imported.password||'')!==''
        return {
          ...defaults,
          ...(providerChanged?{}:prev),
          ...imported,
          db_type:targetKind,
          connection_id:providerChanged?'':(prev.connection_id||''),
          name:keepName,
          password:Object.prototype.hasOwnProperty.call(imported,'password')?String(imported.password||''):(providerChanged?'':(prev.password||'')),
          credential_saved:hasImportedPassword?false:(providerChanged?false:!!prev.credential_saved)
        }
      })
      setSqlDatabaseManual(true)
      if(kind==='supabase'||targetKind==='supabase') setSqlSupabaseConnectionUrl('')
      const safeFields=detected.map(field=>field==='password'?'password(감지됨)':field).join(', ')
      const switched=targetKind!==kind?` · 파일 형식 감지: ${sqlProfileForType(targetKind).name}`:''
      const text=String(result?.message||`${result?.source_name||'연결 파일'} 분석 완료`) + switched + (safeFields?` · ${safeFields}`:'')
      setSqlConnectionImport({busy:false,db_type:targetKind,source_name:result?.source_name||'',message:text,error:''})
      setSqlMessages(prev=>[{type:'info',text,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }catch(e){
      let text=String(e?.message||e||'연결 설정 파일 분석 실패')
      try{
        const raw=String(e?.responseBody||'')
        if(raw){
          const parsed=JSON.parse(raw)
          const detail=parsed?.detail
          text=String((detail&&typeof detail==='object'?(detail.message||detail.detail):detail)||text)
        }
      }catch{}
      text=text.replace(/^Backend HTTP \d+:\s*/,'').trim()
      setSqlConnectionImport({busy:false,db_type:kind,source_name:'',message:'',error:text})
      setSqlMessages(prev=>[{type:'error',text:`연결 설정 파일 확인 필요: ${text}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }
  }

  const getSqlDatabaseHistory=()=>{
    if(['sqlite3','oracle','firestore'].includes(String(sqlProfile.db_type||'').toLowerCase())) return []
    const kind=String(sqlProfile.db_type||'').toLowerCase()
    const host=String(sqlProfile.host||'').trim().toLowerCase()
    const port=Number(sqlProfile.port||0)
    const historyRows=Array.isArray(sqlConnectionStatus?.database_history)?sqlConnectionStatus.database_history:[]
    const historyValues=historyRows
      .filter(item=>String(item?.db_type||'').toLowerCase()===kind)
      .filter(item=>String(item?.host||'').trim().toLowerCase()===host)
      .filter(item=>Number(item?.port||0)===port)
      .map(item=>String(item?.database||'').trim())
      .filter(Boolean)
    const savedProfileValues=(sqlConnections||[])
      .filter(item=>String(item?.db_type||'').toLowerCase()===kind)
      .filter(item=>String(item?.host||'').trim().toLowerCase()===host)
      .filter(item=>Number(item?.port||0)===port)
      .map(item=>String(item?.database||'').trim())
      .filter(Boolean)
    return [...new Set([...historyValues,...savedProfileValues])].sort((a,b)=>a.localeCompare(b,undefined,{sensitivity:'base'}))
  }

  const applySqlWorkspaceStatus=(status,{preservePassword=true}={})=>{
    if(!status) return
    setSqlConnectionStatus(status)
    if(Array.isArray(status.connections)) setSqlConnections(status.connections)
    if(status?.profile){
      setSqlDatabaseManual(false)
      setSqlProfile(prev=>({
        ...sqlProfileForType(status.profile.db_type||'postgresql',status.profile),
        password:preservePassword&&prev.connection_id===status.profile.connection_id?(prev.password||''):''
      }))
    }
  }

  const newSqlWorkspaceConnection=(dbType=sqlProfile.db_type||'postgresql')=>{
    const fresh=sqlProfileForType(dbType)
    setSqlSupabaseConnectionUrl('')
    setSqlConnectionImport({busy:false,db_type:'',source_name:'',message:'',error:''})
    setSqlDatabaseManual(false)
    setSqlProfile(fresh)
    setSqlConnectionStatus(prev=>prev?{...prev,connected:false,connected_at:null,profile:fresh}:prev)
    setSqlDbObjects(null)
    setSqlDbObjectsError('')
    setSqlDbObjectExpanded({})
    resetFirestoreBrowser()
    setRedisBrowser(null)
    setRedisBrowserError('')
    setRedisSelectedKey('')
    setRedisKeyDetail(null)
    setRedisKeyExpanded({})
  }

  const selectSqlWorkspaceConnection=async(connectionId)=>{
    if(!activeWorkspaceRoot) return
    setSqlSupabaseConnectionUrl('')
    const cid=String(connectionId||'')
    if(!cid){
      newSqlWorkspaceConnection()
      return
    }
    setSqlConnectionBusy(true)
    try{
      const status=await api('/sql/activate',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,connection_id:cid})
      })
      applySqlWorkspaceStatus(status,{preservePassword:false})
      if(status?.connected&&status?.profile?.db_type==='redis'){
        resetFirestoreBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadRedisKeys({quiet:true,preserveSelection:false})
      }else if(status?.connected&&status?.profile?.db_type==='firestore'){
        resetRedisBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadFirestoreCollections({quiet:true,preserveSelection:false})
      }else if(status?.connected){
        resetFirestoreBrowser()
        resetRedisBrowser()
        await loadSqlDbObjects({quiet:true})
      }else{
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        resetFirestoreBrowser()
        resetRedisBrowser()
      }
      if(status?.profile?.db_type==='sqlite3') await loadSqliteProjectStatus({quiet:true})
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`DB 연결 선택 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const loadSqliteProjectStatus=async({quiet=false}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot) return null
    if(!quiet) setSqliteProjectStatusBusy(true)
    try{
      const status=await api(`/sql/sqlite-status?root=${encodeURIComponent(workspaceRoot)}`)
      setSqliteProjectStatus(status)
      setSqlProfile(prev=>{
        if(prev.db_type!=='sqlite3'||String(prev.database||'').trim()) return prev
        return {...prev,database:status?.recommended_database||'data/app.db'}
      })
      return status
    }catch(e){
      setSqliteProjectStatus({ok:false,error:String(e),database_files:[],node_packages:[]})
      return null
    }finally{
      if(!quiet) setSqliteProjectStatusBusy(false)
    }
  }

  const loadSqlDbObjects=async({quiet=false}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot) return null
    if(['firestore','redis'].includes(String(sqlProfile.db_type||'').toLowerCase())){
      setSqlDbObjects(null)
      setSqlDbObjectsError('')
      return null
    }
    if(!quiet) setSqlDbObjectsBusy(true)
    setSqlDbObjectsError('')
    try{
      const objects=await api(`/sql/objects?root=${encodeURIComponent(workspaceRoot)}`)
      setSqlDbObjects(objects)
      setSqlDbObjectExpanded(prev=>{
        const next={...prev}
        const firstSchema=objects?.schemas?.[0]
        if(firstSchema){
          const schemaKey=`schema:${firstSchema.name}`
          if(next[schemaKey]===undefined) next[schemaKey]=true
          const tableKey=`category:${firstSchema.name}:tables`
          if(next[tableKey]===undefined) next[tableKey]=true
        }
        return next
      })
      return objects
    }catch(e){
      setSqlDbObjects(null)
      setSqlDbObjectsError(String(e))
      return null
    }finally{
      if(!quiet) setSqlDbObjectsBusy(false)
    }
  }

  const resetFirestoreBrowser=()=>{
    setFirestoreBrowser(null)
    setFirestoreBrowserError('')
    setFirestoreSelectedCollection('')
    setFirestoreDocuments(null)
    setFirestoreSelectedDocument('')
    setFirestoreDocumentDetail(null)
  }

  const loadFirestoreDocumentDetail=async(path,{quiet=false}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    const documentPath=String(path||'')
    if(!workspaceRoot||!documentPath) return null
    if(!quiet) setFirestoreDocumentDetailBusy(true)
    try{
      const detail=await api(`/sql/firestore/document?root=${encodeURIComponent(workspaceRoot)}&path=${encodeURIComponent(documentPath)}`)
      setFirestoreSelectedDocument(documentPath)
      setFirestoreDocumentDetail(detail)
      return detail
    }catch(e){
      setFirestoreDocumentDetail(null)
      setFirestoreBrowserError(String(e))
      return null
    }finally{
      if(!quiet) setFirestoreDocumentDetailBusy(false)
    }
  }

  const loadFirestoreDocuments=async(collection,{quiet=false,preserveSelection=true}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    const collectionPath=String(collection||'')
    if(!workspaceRoot||!collectionPath) return null
    if(!quiet) setFirestoreDocumentsBusy(true)
    setFirestoreBrowserError('')
    try{
      const result=await api(`/sql/firestore/documents?root=${encodeURIComponent(workspaceRoot)}&collection=${encodeURIComponent(collectionPath)}&limit=500`)
      setFirestoreSelectedCollection(collectionPath)
      setFirestoreDocuments(result)
      const documents=Array.isArray(result?.documents)?result.documents:[]
      const previous=preserveSelection?String(firestoreSelectedDocument||''):''
      const nextPath=previous&&documents.some(item=>String(item?.path||'')===previous)?previous:(documents[0]?.path||'')
      if(nextPath){
        await loadFirestoreDocumentDetail(nextPath,{quiet:true})
      }else{
        setFirestoreSelectedDocument('')
        setFirestoreDocumentDetail(null)
      }
      return result
    }catch(e){
      setFirestoreDocuments(null)
      setFirestoreSelectedDocument('')
      setFirestoreDocumentDetail(null)
      setFirestoreBrowserError(String(e))
      return null
    }finally{
      if(!quiet) setFirestoreDocumentsBusy(false)
    }
  }

  const loadFirestoreCollections=async({quiet=false,preserveSelection=true}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot) return null
    if(!quiet) setFirestoreBrowserBusy(true)
    setFirestoreBrowserError('')
    try{
      const result=await api(`/sql/firestore/collections?root=${encodeURIComponent(workspaceRoot)}&limit=1000`)
      setFirestoreBrowser(result)
      const collections=Array.isArray(result?.collections)?result.collections:[]
      const previous=preserveSelection?String(firestoreSelectedCollection||''):''
      const nextCollection=previous&&collections.some(item=>String(item?.path||'')===previous)?previous:(collections[0]?.path||'')
      if(nextCollection){
        await loadFirestoreDocuments(nextCollection,{quiet:true,preserveSelection})
      }else{
        setFirestoreSelectedCollection('')
        setFirestoreDocuments(null)
        setFirestoreSelectedDocument('')
        setFirestoreDocumentDetail(null)
      }
      return result
    }catch(e){
      setFirestoreBrowser(null)
      setFirestoreDocuments(null)
      setFirestoreDocumentDetail(null)
      setFirestoreBrowserError(String(e))
      return null
    }finally{
      if(!quiet) setFirestoreBrowserBusy(false)
    }
  }

  const resetRedisBrowser=()=>{
    setRedisBrowser(null)
    setRedisBrowserError('')
    setRedisSelectedKey('')
    setRedisKeyDetail(null)
    setRedisKeyExpanded({})
    setRedisContextMenu(null)
  }

  const loadRedisKeyDetail=async(key,{quiet=false}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    const keyName=String(key||'')
    if(!workspaceRoot||!keyName) return null
    if(!quiet) setRedisKeyDetailBusy(true)
    try{
      const detail=await api(`/sql/redis/key?root=${encodeURIComponent(workspaceRoot)}&key=${encodeURIComponent(keyName)}&max_items=500`)
      const observedAt=Date.now()
      const nextDetail=detail&&typeof detail==='object'
        ? {...detail,__ttl_observed_at_ms:observedAt}
        : detail
      setRedisSelectedKey(keyName)
      setRedisKeyDetail(nextDetail)
      return nextDetail
    }catch(e){
      setRedisKeyDetail(null)
      setRedisBrowserError(String(e))
      return null
    }finally{
      if(!quiet) setRedisKeyDetailBusy(false)
    }
  }

  const loadRedisKeys=async({quiet=false,preserveSelection=true}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot) return null
    if(!quiet) setRedisBrowserBusy(true)
    setRedisBrowserError('')
    try{
      const raw=String(redisKeyFilter||'').trim()
      const hasGlob=/[*?\[]/.test(raw)
      const pattern=raw?(hasGlob?raw:`*${raw}*`):'*'
      const result=await api(`/sql/redis/keys?root=${encodeURIComponent(workspaceRoot)}&pattern=${encodeURIComponent(pattern)}&limit=2000`)
      const observedAt=Date.now()
      const nextResult=result&&typeof result==='object'
        ? {...result,__ttl_observed_at_ms:observedAt}
        : result
      setRedisBrowser(nextResult)
      const keys=Array.isArray(nextResult?.keys)?nextResult.keys:[]
      const previous=preserveSelection?String(redisSelectedKey||''):''
      const nextKey=previous&&keys.some(item=>String(item?.key||'')===previous)?previous:(keys[0]?.key||'')
      if(nextKey){
        await loadRedisKeyDetail(nextKey,{quiet:true})
      }else{
        setRedisSelectedKey('')
        setRedisKeyDetail(null)
      }
      return nextResult
    }catch(e){
      setRedisBrowser(null)
      setRedisKeyDetail(null)
      setRedisBrowserError(String(e))
      return null
    }finally{
      if(!quiet) setRedisBrowserBusy(false)
    }
  }

  const toggleRedisKeyGroup=(path)=>{
    setRedisKeyExpanded(prev=>({...prev,[path]:prev[path]===false?true:false}))
  }

  const openFirestoreContextMenu=(event,node)=>{
    if(!sqlConnectionStatus?.connected||String(sqlProfile.db_type||'').toLowerCase()!=='firestore') return
    event.preventDefault()
    event.stopPropagation()
    const menuWidth=306
    const menuHeight=402
    const x=Math.max(8,Math.min(event.clientX,window.innerWidth-menuWidth-8))
    const y=Math.max(8,Math.min(event.clientY,window.innerHeight-menuHeight-8))
    const nodeKind=node?.kind==='document'?'document':'collection'
    const path=String(node?.path||'')
    const label=String(node?.label||path||'Firestore')
    if(nodeKind==='collection'&&path){
      setFirestoreSelectedCollection(path)
      if(firestoreSelectedCollection!==path) loadFirestoreDocuments(path,{quiet:true,preserveSelection:false})
    }else if(nodeKind==='document'&&path){
      const parts=path.split('/').filter(Boolean)
      const collectionPath=parts.slice(0,-1).join('/')
      if(collectionPath) setFirestoreSelectedCollection(collectionPath)
      setFirestoreSelectedDocument(path)
      if(firestoreSelectedDocument!==path) loadFirestoreDocumentDetail(path,{quiet:true})
    }
    setRedisContextMenu(null)
    setSqlObjectContextMenu(null)
    setSqlDatabaseContextMenu(null)
    setFirestoreContextMenu({x,y,nodeKind,path,label})
  }

  const createFirestorePythonScript=async(action)=>{
    const menu=firestoreContextMenu
    if(!menu||!activeWorkspaceRoot||!sqlConnectionStatus?.connected||firestoreScriptBusy) return
    const normalized=String(action||'').toLowerCase()
    setFirestoreContextMenu(null)
    setFirestoreScriptBusy(normalized)
    try{
      const response=await api('/sql/firestore/script',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,action:normalized,path:menu.path||'',node_kind:menu.nodeKind||'collection'})
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{type:'success',text:response?.message||'Firestore 임시 Python 코드를 생성했습니다.',time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{type:'error',text:`Firestore Python 코드 생성 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setFirestoreScriptBusy('')
    }
  }

  const openRedisContextMenu=(event,node)=>{
    if(!sqlConnectionStatus?.connected||String(sqlProfile.db_type||'').toLowerCase()!=='redis') return
    event.preventDefault()
    event.stopPropagation()
    const menuWidth=286
    const menuHeight=390
    const x=Math.max(8,Math.min(event.clientX,window.innerWidth-menuWidth-8))
    const y=Math.max(8,Math.min(event.clientY,window.innerHeight-menuHeight-8))
    const payload={
      x,y,
      nodeKind:node?.kind==='group'?'group':'key',
      key:String(node?.key||''),
      keyType:String(node?.keyType||''),
      prefix:String(node?.prefix||''),
      label:String(node?.label||node?.key||node?.prefix||'Redis'),
    }
    if(payload.nodeKind==='key'&&payload.key){
      setRedisSelectedKey(payload.key)
      if(redisSelectedKey!==payload.key) loadRedisKeyDetail(payload.key,{quiet:true})
    }
    setFirestoreContextMenu(null)
    setSqlObjectContextMenu(null)
    setSqlDatabaseContextMenu(null)
    setRedisContextMenu(payload)
  }

  const createRedisPythonScript=async(action)=>{
    const menu=redisContextMenu
    if(!menu||!activeWorkspaceRoot||!sqlConnectionStatus?.connected||redisScriptBusy) return
    const normalized=String(action||'').toLowerCase()
    setRedisContextMenu(null)
    setRedisScriptBusy(normalized)
    try{
      const response=await api('/sql/redis/script',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          action:normalized,
          key:menu.key||'',
          key_type:menu.keyType||'',
          prefix:menu.prefix||'',
          node_kind:menu.nodeKind||'key',
        })
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||'Redis 임시 Python 코드를 생성했습니다.',
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`Redis Python 코드 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setRedisScriptBusy('')
    }
  }


  useEffect(()=>{
    if(!redisContextMenu) return
    const close=()=>setRedisContextMenu(null)
    const onKey=(event)=>{if(event.key==='Escape') close()}
    window.addEventListener('mousedown',close)
    window.addEventListener('scroll',close,true)
    window.addEventListener('resize',close)
    window.addEventListener('keydown',onKey,true)
    return ()=>{
      window.removeEventListener('mousedown',close)
      window.removeEventListener('scroll',close,true)
      window.removeEventListener('resize',close)
      window.removeEventListener('keydown',onKey,true)
    }
  },[redisContextMenu])

  useEffect(()=>{
    if(!firestoreContextMenu) return
    const close=()=>setFirestoreContextMenu(null)
    const onKey=(event)=>{if(event.key==='Escape') close()}
    window.addEventListener('mousedown',close)
    window.addEventListener('scroll',close,true)
    window.addEventListener('resize',close)
    window.addEventListener('keydown',onKey,true)
    return ()=>{
      window.removeEventListener('mousedown',close)
      window.removeEventListener('scroll',close,true)
      window.removeEventListener('resize',close)
      window.removeEventListener('keydown',onKey,true)
    }
  },[firestoreContextMenu])

  const toggleSqlDbObject=(key)=>{
    setSqlDbObjectExpanded(prev=>({...prev,[key]:!prev[key]}))
  }

  const openSqlDbObject=async(schemaName,category,item)=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected||!item?.name) return
    const busyKey=`${schemaName}:${category}:${item.name}`
    if(sqlObjectActionBusy) return
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/object-open',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          schema:schemaName,
          category,
          name:item.name
        })
      })
      if(response?.relative_path){
        await openFile(response.relative_path)
      }
      if(response?.result){
        setSqlQueryResult(response.result)
        setSqlResultTab(response.result?.columns?.length?'DATA':'MESSAGES')
      }else{
        setSqlResultTab('MESSAGES')
      }
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||`${schemaName}.${item.name} 임시 SQL을 생성했습니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`DB 객체 열기 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const openSqlObjectContextMenu=(event,schemaName,category,item)=>{
    if(category!=='tables'||!item?.name) return
    event.preventDefault()
    event.stopPropagation()
    const menuWidth=270
    const menuHeight=500
    const x=Math.max(8,Math.min(event.clientX,window.innerWidth-menuWidth-8))
    const y=Math.max(8,Math.min(event.clientY,window.innerHeight-menuHeight-8))
    setSqlSchemaContextMenu(null)
    setSqlObjectContextMenu({x,y,schemaName,category,item})
  }

  const openSqlSchemaContextMenu=(event,schemaName)=>{
    if(!sqlConnectionStatus?.connected||!schemaName) return
    event.preventDefault()
    event.stopPropagation()
    setSqlObjectContextMenu(null)
    setSqlDatabaseContextMenu(null)
    const menuWidth=330
    const menuHeight=150
    const x=Math.max(8,Math.min(event.clientX,window.innerWidth-menuWidth-8))
    const y=Math.max(8,Math.min(event.clientY,window.innerHeight-menuHeight-8))
    setSqlSchemaContextMenu({x,y,schemaName})
  }

  const createSqlSchemaDiagram=async(schemaName)=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected||!schemaName) return
    const busyKey=`${schemaName}:schema-diagram`
    if(sqlObjectActionBusy) return
    setSqlSchemaContextMenu(null)
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/schema-diagram',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,schema:schemaName})
      })
      if(response?.relative_path){
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||`${schemaName} 스키마 전체 다이어그램을 생성했습니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`스키마 전체 다이어그램 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const createSqlTableDiagram=async(schemaName,item)=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected||!item?.name) return
    const busyKey=`${schemaName}:table-diagram:${item.name}`
    if(sqlObjectActionBusy) return
    setSqlObjectContextMenu(null)
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/table-diagram',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          schema:schemaName,
          category:'tables',
          name:item.name
        })
      })
      if(response?.relative_path){
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||`${schemaName}.${item.name} 다이어그램을 생성했습니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`테이블 다이어그램 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const createSqlTableScript=async(schemaName,item)=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected||!item?.name) return
    const busyKey=`${schemaName}:table-script:${item.name}`
    if(sqlObjectActionBusy) return
    setSqlObjectContextMenu(null)
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/table-script',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          schema:schemaName,
          category:'tables',
          name:item.name
        })
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||`${schemaName}.${item.name} 테이블 스크립트를 생성했습니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`테이블 스크립트 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const createSqlTableAlterScript=async(schemaName,item)=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected||!item?.name) return
    const busyKey=`${schemaName}:table-alter-script:${item.name}`
    if(sqlObjectActionBusy) return
    setSqlObjectContextMenu(null)
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/table-alter-script',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          schema:schemaName,
          category:'tables',
          name:item.name
        })
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||`${schemaName}.${item.name} 테이블 수정 스크립트를 생성했습니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`테이블 수정 스크립트 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const createSqlTableDmlScript=async(schemaName,item,action)=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected||!item?.name) return
    const normalized=String(action||'').toLowerCase()
    const busyKey=`${schemaName}:table-${normalized}-script:${item.name}`
    if(sqlObjectActionBusy) return
    setSqlObjectContextMenu(null)
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/table-dml-script',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          schema:schemaName,
          name:item.name,
          action:normalized,
        })
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||`${schemaName}.${item.name} ${normalized.toUpperCase()} 스크립트를 생성했습니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`테이블 ${normalized.toUpperCase()} 스크립트 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const openSqlDatabaseContextMenu=(event)=>{
    if(!sqlConnectionStatus?.connected) return
    event.preventDefault()
    event.stopPropagation()
    setSqlObjectContextMenu(null)
    setSqlSchemaContextMenu(null)
    const menuWidth=310
    const menuHeight=520
    const x=Math.max(8,Math.min(event.clientX,window.innerWidth-menuWidth-8))
    const y=Math.max(8,Math.min(event.clientY,window.innerHeight-menuHeight-8))
    setSqlDatabaseContextMenu({x,y})
  }

  const createPostgresqlAdminScript=async(action,value='')=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected) return
    if(sqlObjectActionBusy) return
    const busyKey=`database-admin:${action}`
    setSqlDatabaseContextMenu(null)
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/postgresql-admin-script',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,action,value:String(value??'')})
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||'PostgreSQL 관리 SQL을 임시 파일로 생성했습니다.',
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`PostgreSQL 관리 SQL 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const openSqlAdminPrompt=(action)=>{
    const configs={
      table_locks:{title:'특정 테이블 Lock만 보기',label:'테이블 이름',placeholder:'customers',value:'customers',danger:false},
      cancel_backend:{title:'쿼리만 중지하고 DB 접속 유지',label:'중지할 세션 PID',placeholder:'예: 138',value:'',danger:true},
      terminate_backend:{title:'DB 연결 자체를 강제로 종료',label:'종료할 세션 PID',placeholder:'예: 138',value:'',danger:true},
      terminate_others:{title:'다른 세션만 종료',label:'종료 대상 세션 상태',placeholder:'idle in transaction',value:'idle in transaction',danger:true},
    }
    const config=configs[action]
    if(!config) return
    setSqlDatabaseContextMenu(null)
    setSqlAdminPrompt({action,...config})
  }

  const submitSqlAdminPrompt=async()=>{
    const prompt=sqlAdminPrompt
    if(!prompt) return
    const value=String(prompt.value??'').trim()
    if(!value){
      return
    }
    setSqlAdminPrompt(null)
    await createPostgresqlAdminScript(prompt.action,value)
  }

  useEffect(()=>{
    if(!sqlSchemaContextMenu) return
    const close=()=>setSqlSchemaContextMenu(null)
    const onKey=(event)=>{ if(event.key==='Escape') close() }
    window.addEventListener('mousedown',close)
    window.addEventListener('scroll',close,true)
    window.addEventListener('resize',close)
    window.addEventListener('keydown',onKey,true)
    return ()=>{
      window.removeEventListener('mousedown',close)
      window.removeEventListener('scroll',close,true)
      window.removeEventListener('resize',close)
      window.removeEventListener('keydown',onKey,true)
    }
  },[sqlSchemaContextMenu])

  useEffect(()=>{
    if(!sqlObjectContextMenu) return
    const close=()=>setSqlObjectContextMenu(null)
    const onKey=(event)=>{ if(event.key==='Escape') close() }
    window.addEventListener('mousedown',close)
    window.addEventListener('scroll',close,true)
    window.addEventListener('resize',close)
    window.addEventListener('keydown',onKey,true)
    return ()=>{
      window.removeEventListener('mousedown',close)
      window.removeEventListener('scroll',close,true)
      window.removeEventListener('resize',close)
      window.removeEventListener('keydown',onKey,true)
    }
  },[sqlObjectContextMenu])

  useEffect(()=>{
    if(!sqlDatabaseContextMenu) return
    const close=()=>setSqlDatabaseContextMenu(null)
    const onKey=(event)=>{ if(event.key==='Escape') close() }
    window.addEventListener('mousedown',close)
    window.addEventListener('scroll',close,true)
    window.addEventListener('resize',close)
    window.addEventListener('keydown',onKey,true)
    return ()=>{
      window.removeEventListener('mousedown',close)
      window.removeEventListener('scroll',close,true)
      window.removeEventListener('resize',close)
      window.removeEventListener('keydown',onKey,true)
    }
  },[sqlDatabaseContextMenu])

  const loadSqlWorkspaceProfileForType=async(dbType)=>{
    // v5.239 compatibility helper: create a new unsaved profile of the chosen DB type.
    const kind=String(dbType||'postgresql').toLowerCase()
    const fresh=sqlProfileForType(kind)
    setSqlProfile(fresh)
    if(kind==='sqlite3') await loadSqliteProjectStatus({quiet:true})
    return fresh
  }

  const loadSqlWorkspaceStatus=async()=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot) return null
    try{
      const status=await api(`/sql/status?root=${encodeURIComponent(workspaceRoot)}`)
      const rootChanged=sqlLoadedRootRef.current!==workspaceRoot
      sqlLoadedRootRef.current=workspaceRoot
      applySqlWorkspaceStatus(status,{preservePassword:!rootChanged})
      if(status?.connected&&status?.profile?.db_type==='redis'){
        resetFirestoreBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadRedisKeys({quiet:true})
      }else if(status?.connected&&status?.profile?.db_type==='firestore'){
        resetRedisBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadFirestoreCollections({quiet:true})
      }else if(status?.connected){
        resetFirestoreBrowser()
        resetRedisBrowser()
        await loadSqlDbObjects({quiet:true})
      }else{
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        resetFirestoreBrowser()
        resetRedisBrowser()
      }
      return status
    }catch(e){
      setSqlConnections([])
      setSqlConnectionStatus({connected:false,error:String(e),connections:[]})
      return null
    }
  }

  const saveSqlWorkspaceProfile=async()=>{
    if(!activeWorkspaceRoot) return
    setSqlConnectionBusy(true)
    try{
      const result=await api('/sql/profile',{
        method:'POST',
        body:JSON.stringify({...sqlProfile,root:activeWorkspaceRoot})
      })
      if(Array.isArray(result?.connections)) setSqlConnections(result.connections)
      setSqlProfile(prev=>({
        ...sqlProfileForType(result?.profile?.db_type||prev.db_type,result?.profile||prev),
        password:prev.password
      }))
      const status=await api(`/sql/status?root=${encodeURIComponent(activeWorkspaceRoot)}`)
      applySqlWorkspaceStatus(status,{preservePassword:false})
      setSqlMessages(prev=>[{
        type:'info',
        text:`DB 연결 정보를 저장했습니다. · ${result?.profile?.name||sqlProfile.name||String(sqlProfile.db_type||'').toUpperCase()}${result?.profile?.credential_saved?' · 비밀번호 Windows 보안 저장 완료':''}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`DB 설정 저장 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const renameSqlWorkspaceConnection=async()=>{
    if(!activeWorkspaceRoot||!sqlProfile.connection_id) return
    const nextName=String(sqlProfile.name||'').trim()
    if(!nextName){
      setSqlMessages(prev=>[{type:'warning',text:'변경할 연결 이름을 입력하세요.',time:new Date().toLocaleTimeString()},...prev].slice(0,100))
      return
    }
    setSqlConnectionBusy(true)
    try{
      const result=await api('/sql/profile/rename',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,connection_id:sqlProfile.connection_id,name:nextName})
      })
      applySqlWorkspaceStatus(result,{preservePassword:true})
      setSqlMessages(prev=>[{
        type:'info',
        text:`DB 연결 이름을 '${result?.profile?.name||nextName}'(으)로 변경했습니다. 연결 ID와 저장된 자격증명은 그대로 유지됩니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`DB 연결 이름 변경 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const deleteSqlWorkspaceConnection=async()=>{
    if(!activeWorkspaceRoot||!sqlProfile.connection_id) return
    const label=sqlProfile.name||String(sqlProfile.db_type||'DB').toUpperCase()
    if(!window.confirm(`저장된 DB 연결 '${label}'을 삭제하시겠습니까?\n현재 연결 중이면 연결도 함께 해제됩니다.`)) return
    setSqlConnectionBusy(true)
    try{
      const status=await api('/sql/profile/delete',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,connection_id:sqlProfile.connection_id})
      })
      applySqlWorkspaceStatus(status,{preservePassword:false})
      if(!status?.profile?.connection_id) newSqlWorkspaceConnection(sqlProfile.db_type)
      if(status?.connected&&status?.profile?.db_type==='redis'){
        resetFirestoreBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadRedisKeys({quiet:true,preserveSelection:false})
      }else if(status?.connected&&status?.profile?.db_type==='firestore'){
        resetRedisBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadFirestoreCollections({quiet:true,preserveSelection:false})
      }else if(status?.connected){
        resetFirestoreBrowser()
        resetRedisBrowser()
        await loadSqlDbObjects({quiet:true})
      }else{
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        resetFirestoreBrowser()
        resetRedisBrowser()
      }
      setSqlMessages(prev=>[{type:'info',text:`DB 연결 '${label}'을 삭제했습니다.`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`DB 연결 삭제 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const connectSqlWorkspace=async()=>{
    if(!activeWorkspaceRoot) return
    setSqlConnectionBusy(true)
    try{
      const status=await api('/sql/connect',{
        method:'POST',
        body:JSON.stringify({...sqlProfile,root:activeWorkspaceRoot})
      })
      applySqlWorkspaceStatus(status,{preservePassword:false})
      setSqlMessages(prev=>[{
        type:'success',
        text:`${status?.profile?.name||String(status?.profile?.db_type||sqlProfile.db_type).toUpperCase()} 연결 성공${status?.profile?.credential_saved?' · 저장된 보안 자격증명 사용 가능':''}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
      if((status?.profile?.db_type||sqlProfile.db_type)==='redis'){
        resetFirestoreBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadRedisKeys({quiet:true,preserveSelection:false})
      }else if((status?.profile?.db_type||sqlProfile.db_type)==='firestore'){
        resetRedisBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadFirestoreCollections({quiet:true,preserveSelection:false})
      }else{
        resetFirestoreBrowser()
        resetRedisBrowser()
        await loadSqlDbObjects({quiet:true})
      }
      if((status?.profile?.db_type||sqlProfile.db_type)==='sqlite3') await loadSqliteProjectStatus({quiet:true})
    }catch(e){
      setSqlConnectionStatus(prev=>({...prev,connected:false,error:String(e)}))
      setSqlMessages(prev=>[{type:'error',text:`DB 연결 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const disconnectSqlWorkspace=async()=>{
    if(!activeWorkspaceRoot) return
    setSqlConnectionBusy(true)
    try{
      const status=await api('/sql/disconnect',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,connection_id:sqlProfile.connection_id||''})
      })
      applySqlWorkspaceStatus(status,{preservePassword:true})
      setSqlDbObjects(null)
      setSqlDbObjectsError('')
      setSqlDbObjectExpanded({})
      resetFirestoreBrowser()
      resetRedisBrowser()
      setSqlMessages(prev=>[{type:'info',text:`${sqlProfile.name||'데이터베이스'} 연결을 해제했습니다.`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`연결 해제 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const runSqlEditor=async({selectionOnly=false}={})=>{
    if(!isSqlFile||sqlQueryBusy) return
    if(!sqlConnectionStatus?.connected){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{type:'warning',text:'현재 선택된 DB 연결이 연결되어 있지 않습니다. 저장된 연결을 선택해 연결한 뒤 SQL을 실행하세요.',time:new Date().toLocaleTimeString()},...prev].slice(0,100))
      return
    }
    let statement=code||''
    let label='전체 SQL'
    if(selectionOnly){
      const editor=editorInstanceRef.current
      const selection=editor?.getSelection?.()
      const model=editor?.getModel?.()
      const selectedText=(selection&&model)?model.getValueInRange(selection):''
      if(!selectedText.trim()){
        setSqlResultTab('MESSAGES')
        setSqlMessages(prev=>[{type:'warning',text:'선택된 SQL이 없습니다.',time:new Date().toLocaleTimeString()},...prev].slice(0,100))
        return
      }
      statement=selectedText
      label='선택 SQL'
    }
    if(!statement.trim()) return

    sqlStopRequestedRef.current=false
    setSqlQueryBusy(true)
    try{
      const result=await api('/sql/execute',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,sql:statement,max_rows:1000})
      })
      setSqlQueryResult(result)
      const resultSetCount=Array.isArray(result?.result_sets)?result.result_sets.length:0
      setSqlResultSetIndex(resultSetCount?resultSetCount-1:0)
      setSqlResultTab(resultSetCount||result?.columns?.length?'DATA':'MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:`${label} 실행 완료 · ${result?.message||''} · ${result?.elapsed_ms||0}ms`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      if(sqlStopRequestedRef.current){
        setSqlMessages(prev=>[{type:'warning',text:`${label} 실행을 사용자가 중지했습니다.`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
      }else{
        setSqlMessages(prev=>[{type:'error',text:`${label} 실행 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
      }
    }finally{
      setSqlQueryBusy(false)
      sqlStopRequestedRef.current=false
    }
  }

  const stopSqlExecution=async()=>{
    if(!activeWorkspaceRoot||!sqlQueryBusy) return
    sqlStopRequestedRef.current=true
    try{
      const result=await api('/sql/cancel',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,connection_id:sqlProfile.connection_id||''})
      })
      setSqlMessages(prev=>[{
        type:result?.cancelled?'warning':'info',
        text:result?.message||'SQL 실행 중지 요청을 보냈습니다.',
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`SQL 실행 중지 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }
  }

  useEffect(()=>{
    if(workspaceTab!=='CODE') return
    if(isSqlFile){
      setCodeRightPanelTab('SQL_DB')
      setWorkspaceRightCollapsed(false)
      loadSqlWorkspaceStatus()
      loadSqliteProjectStatus({quiet:true})
    }
  },[workspaceTab,selected,activeWorkspaceRoot])

  const refreshAiRuntimeStatus=async()=>{
    try{
      const status=await api('/llm/runtime-status')
      setAiRuntimeStatus(status)
      setAiModeError('')
      return status
    }catch(e){
      setAiModeError(String(e))
      return null
    }
  }

  const applyAiMode=async(mode)=>{
    if(aiModeBusy) return
    const openaiEnabled=aiRuntimeStatus?.providers?.openai?.enabled!==false
    if(!openaiEnabled&&mode==='openai') return
    if(mode==='ollama'&&!aiRuntimeStatus?.providers?.ollama?.connected) return
    if(mode==='openai'&&!aiRuntimeStatus?.providers?.openai?.configured) return
    if(mode==='codex'&&(!aiRuntimeStatus?.providers?.codex?.enabled||!aiRuntimeStatus?.providers?.codex?.installed)) return

    const values=mode==='openai'
      ? {
          AI_PROVIDER_STRATEGY:'manual',
          LOCAL_LLM_PROVIDER:'openai',
          CODING_LLM_PROVIDER:'openai',
          REQUIREMENTS_LLM_PROVIDER:'openai'
        }
      : mode==='ollama'
        ? {
            AI_PROVIDER_STRATEGY:'manual',
            LOCAL_LLM_PROVIDER:'ollama',
            CODING_LLM_PROVIDER:'ollama',
            REQUIREMENTS_LLM_PROVIDER:'ollama'
          }
        : mode==='codex'
          ? {
              AI_PROVIDER_STRATEGY:'manual',
              LOCAL_LLM_PROVIDER:'ollama',
              CODING_LLM_PROVIDER:'codex',
              REQUIREMENTS_LLM_PROVIDER:'codex'
            }
          : {
              AI_PROVIDER_STRATEGY:'ollama_first',
              LOCAL_LLM_PROVIDER:'auto',
              CODING_LLM_PROVIDER:'auto',
              REQUIREMENTS_LLM_PROVIDER:'auto'
            }

    setAiModeBusy(true)
    setAiModeError('')
    try{
      await api('/settings',{
        method:'POST',
        body:JSON.stringify({values})
      })
      await refreshAiRuntimeStatus()
      setAiModeMenuOpen(false)
    }catch(e){
      setAiModeError(String(e))
    }finally{
      setAiModeBusy(false)
    }
  }

  const aiModeName={auto:'AUTO',openai:'OpenAI',ollama:'Ollama',codex:'Codex'}[aiRuntimeStatus?.mode]||'확인 중'
  const aiPrimaryProvider=(aiRuntimeStatus?.primary_provider||'').toLowerCase()
  const aiPrimaryModel=aiRuntimeStatus?.primary_model||''
  const aiPrimaryProviderLabel=aiPrimaryProvider==='openai'?'OpenAI':aiPrimaryProvider==='ollama'?'Ollama':aiPrimaryProvider==='codex'?'Codex':''
  const aiModeHeaderLabel=aiRuntimeStatus
    ? `AI 모드 · ${aiModeName} · ${aiPrimaryProviderLabel}${aiPrimaryModel?` · ${aiPrimaryModel}`:''}`
    : 'AI 모드 · 상태 확인 중'
  const aiInterviewLabel=aiRuntimeStatus
    ? `${aiModeName} · ${aiPrimaryProviderLabel}${aiPrimaryModel?` · ${aiPrimaryModel}`:''}`
    : 'AI 상태 확인 중'

  useEffect(()=>{
    refreshAiRuntimeStatus()
  },[])

  const diagnoseProjectDatabase=async()=>{
    try{
      const result=await api('/projects/diagnostics')
      setProjectDbDiagnostic(result)

      const logPath=
        result?.api_log_path
        || result?.backend_log_path
        || ''

      setProjectListLogPath(logPath)

      return result
    }catch(e){
      setProjectDbDiagnostic({
        ok:false,
        message:String(e),
        path:'Frontend -> FastAPI -> PostgreSQL'
      })

      setProjectListLogPath(
        'FastAPI 진단 API 호출 자체가 실패했습니다. Backend 로그: <AgentStudio>\\logs\\system_manager.log'
      )

      return null
    }
  }

  const refreshProjectList=async()=>{
    setProjectListLoading(true)
    setProjectListLogPath('')

    try{
      // 프로젝트 목록은 반드시 FastAPI를 통해 조회합니다.
      // Frontend가 PostgreSQL에 직접 연결하지 않습니다.
      const rows=await api('/projects')
      const normalized=Array.isArray(rows)?rows:[]

      setProjectList(normalized)
      setProjectListStatus(
        `FastAPI → PostgreSQL 연결 정상 · DB 프로젝트 ${normalized.length}건 로드됨`
      )

      // 성공한 경우에도 실제 DB 경로/건수를 진단 API로 확인합니다.
      const diag=await diagnoseProjectDatabase()
      if(diag?.ok){
        setProjectListStatus(
          `FastAPI → PostgreSQL 연결 정상 · DB 프로젝트 ${diag.project_count}건`
        )
      }

      return normalized
    }catch(e){
      console.error('프로젝트 목록 새로고침 실패',e)

      setProjectList([])
      setProjectListStatus(
        'FastAPI 프로젝트 목록 호출 실패: '+String(e)
      )

      // REST 호출이 실패했을 때 가능한 경우 진단 API를 추가 호출하여
      // DB 오류인지 FastAPI/CORS/서버 오류인지 구분하고 로그 경로를 표시합니다.
      const diag=await diagnoseProjectDatabase()

      if(diag?.ok===false){
        setProjectListStatus(
          'FastAPI는 응답했지만 PostgreSQL 조회 실패: '
          +(diag.message||'상세 로그를 확인하세요.')
        )
      }else if(!diag){
        setProjectListStatus(
          'FastAPI 프로젝트 API 호출 실패: '+String(e)
        )
      }

      return []
    }finally{
      setProjectListLoading(false)
    }
  }

  const loadGitInfo=async(rootOverride=null)=>{
    const targetRoot=rootOverride||root
    if(!targetRoot){
      setGitInfo(null)
      return null
    }

    setGitInfoLoading(true)
    try{
      const info=await api(`/project/git-info?root=${encodeURIComponent(targetRoot)}`)
      setGitInfo(info)
      return info
    }catch(e){
      setGitInfo({
        ok:false,
        is_git:false,
        message:String(e)
      })
      return null
    }finally{
      setGitInfoLoading(false)
    }
  }

  const runGitAction=async(action)=>{
    if(!root) return null

    if((action==='commit'||action==='sync')&&!gitCommitMessage.trim()){
      setGitActionResult({
        ok:false,
        action,
        stderr:'커밋 메시지를 입력하세요.'
      })
      return null
    }

    setGitActionBusy(action)
    setGitActionResult(null)

    try{
      const result=await api('/project/git-action',{
        method:'POST',
        body:JSON.stringify({
          root,
          action,
          message:gitCommitMessage.trim()
        })
      })

      setGitActionResult(result)

      if(result?.ok){
        await loadGitInfo(root)
        if(action==='sync'||action==='commit'){
          setGitCommitMessage('')
        }
      }

      return result
    }catch(e){
      setGitActionResult({
        ok:false,
        action,
        stderr:String(e)
      })
      return null
    }finally{
      setGitActionBusy('')
    }
  }



  const activateProjectTerminal=async(project)=>{
    const projectId=project?.id
    const projectRoot=project?.project_root||project?.root_path||''
    if(!projectId||!projectRoot) return null

    const sessionId=`project-${projectId}`
    setActiveTerminalProjectId(projectId)

    const existing=terminalSessions.find(t=>t.id===sessionId)

    // 프로젝트를 이동해도 이미 만들어진 터미널은 그대로 유지합니다.
    // 사용자가 × 버튼으로 닫기 전에는 새로 만들거나 WebSocket을 교체하지 않습니다.
    if(existing){
      setActiveTerminalId(sessionId)

      // WebSocket이 닫혔더라도 Backend PowerShell 세션은 살아 있을 수 있습니다.
      // 같은 sessionId로 다시 연결하면 Backend가 기존 세션을 재사용하고
      // history를 보내 줍니다.
      if(existing.processState!=='exited'){
        await connectProjectTerminal(project,sessionId)
      }

      const restoreView=()=>{
        const term=xtermInstancesRef.current[sessionId]
        fitTerminalViewport(sessionId)
        try{
          if(term){
            term.refresh(0,Math.max(0,term.rows-1))
            term.scrollToBottom()
          }
        }catch{}

        if(
          existing.processState!=='exited'
          && canAutoFocusTerminal()
        ){
          try{ term?.focus() }catch{}
        }
      }

      setTimeout(restoreView,30)
      setTimeout(restoreView,150)
      setTimeout(restoreView,350)

      return sessionId
    }

    const session={
      id:sessionId,
      name:project?.name
        ? `${project.name} PowerShell`
        : 'Project PowerShell',
      projectId,
      projectName:project?.name||'',
      root:projectRoot,
      cwd:projectRoot,
      command:'',
      output:'',
      busy:false,
      processState:'starting',
      exitCode:null,
    }

    setTerminalSessions(prev=>[
      ...prev,
      session
    ])

    setActiveTerminalId(sessionId)

    await connectProjectTerminal(project,sessionId)

    setTimeout(async()=>{
      await ensureXtermInstance(sessionId)
      if(canAutoFocusTerminal()){
        focusXterm(sessionId)
      }
    },100)

    return sessionId
  }



  const processTerminalRawOutput=(sessionId,incoming,{reset=false}={})=>{
    detectTerminalWebServices(sessionId,incoming)
    const term=xtermInstancesRef.current[sessionId]

    if(reset){
      xtermOutputParseBufferRef.current[sessionId]=''
      xtermPromptRef.current[sessionId]=''
      xtermCommandBuffersRef.current[sessionId]=''
      xtermCursorIndexRef.current[sessionId]=0
      terminalCommandBusyRef.current[sessionId]=false
      xtermRequiredColsRef.current[sessionId]=0

      try{
        term?.reset()
        term?.clear()
      }catch{}
    }

    const pending=xtermOutputParseBufferRef.current[sessionId]||''
    const combined=pending+(incoming||'')
    const normalized=combined.replace(/\r\n/g,'\n')
    const parts=normalized.split('\n')
    const complete=parts.slice(0,-1)

    xtermOutputParseBufferRef.current[sessionId]=
      normalized.endsWith('\n')
        ? ''
        : parts[parts.length-1]

    const visible=[]
    let nextCwd=null
    let nextPrompt=null

    for(const line of complete){
      if(line.startsWith('__THEANOVA_CWD__=')){
        nextCwd=line.slice('__THEANOVA_CWD__='.length).trim()
        continue
      }

      if(line.startsWith('__THEANOVA_PROMPT__=')){
        nextPrompt=line.slice('__THEANOVA_PROMPT__='.length)
        continue
      }

      visible.push(line)
    }

    if(nextCwd){
      terminalCwdRef.current[sessionId]=nextCwd
      setTerminalSessions(prev=>prev.map(t=>
        t.id===sessionId
          ? {...t,cwd:nextCwd}
          : t
      ))
    }

    if(visible.length){
      writeXterm(
        sessionId,
        visible.join('\r\n')+'\r\n'
      )
    }

    if(nextPrompt!==null){
      xtermPromptRef.current[sessionId]=nextPrompt
      xtermCommandBuffersRef.current[sessionId]=''
      xtermCursorIndexRef.current[sessionId]=0
      terminalCommandBusyRef.current[sessionId]=false
      setTerminalSessions(prev=>prev.map(t=>t.id===sessionId?{...t,busy:false,interrupting:false}:t))
      fitTerminalViewport(sessionId)
      writeXterm(sessionId,nextPrompt)
      requestAnimationFrame(()=>{
        const promptTerm=xtermInstancesRef.current[sessionId]
        promptTerm?.scrollToBottom()
        if(
          activeTerminalId===sessionId
          && canAutoFocusTerminal()
        ){
          try{ promptTerm?.focus() }catch{}
        }
      })
    }

    requestAnimationFrame(()=>{
      const activeTerm=xtermInstancesRef.current[sessionId]

      fitTerminalViewport(sessionId)
      try{
        if(activeTerm){
          activeTerm.refresh(
            0,
            Math.max(0,activeTerm.rows-1)
          )
          activeTerm.scrollToBottom()
        }
      }catch{}
    })
  }


  const connectProjectTerminal=async(project,sessionId)=>{
    setTerminalErrors(prev=>({
      ...prev,
      [sessionId]:null
    }))

    const projectRoot=
      project?.project_root
      || project?.root_path
      || ''

    if(!projectRoot) return null

    terminalRootRef.current[sessionId]=projectRoot
    if(!terminalCwdRef.current[sessionId]){
      terminalCwdRef.current[sessionId]=projectRoot
    }

    const existing=terminalSocketsRef.current[sessionId]

    if(existing&&existing.readyState===WebSocket.OPEN){
      return existing
    }

    const cfg=window.__AGENTSTUDIO_CONFIG__||{}
    const host=cfg.BACKEND_HOST||window.location.hostname||'127.0.0.1'
    const port=cfg.BACKEND_PORT||8000
    const protocol=window.location.protocol==='https:'?'wss':'ws'

    const wsUrl=
      `${protocol}://${host}:${port}/ws/terminal/${encodeURIComponent(sessionId)}`
      + `?root=${encodeURIComponent(projectRoot)}`
      + `&project_name=${encodeURIComponent(project?.name||'')}`

    const ws=new WebSocket(wsUrl)
    terminalSocketsRef.current[sessionId]=ws

    setTerminalErrors(prev=>({
      ...prev,
      [sessionId]:null
    }))

    setTerminalConnectionState(prev=>({
      ...prev,
      [sessionId]:'connecting'
    }))

    ws.onopen=()=>{
      setTerminalConnectionState(prev=>({
        ...prev,
        [sessionId]:'connected'
      }))
    }

    ws.onmessage=(event)=>{
      try{
        const msg=parseTerminalServerMessage(event.data)

        if(msg.type==='history'){
          processTerminalRawOutput(
            sessionId,
            msg.data||'',
            {reset:true}
          )
          return
        }

        if(msg.type==='output'){
          processTerminalRawOutput(
            sessionId,
            msg.data||''
          )
        }

        if(msg.type==='ready'){
          setTerminalErrors(prev=>({
            ...prev,
            [sessionId]:null
          }))
          setTerminalConnectionState(prev=>({
            ...prev,
            [sessionId]:'connected'
          }))

          setTerminalSessions(prev=>prev.map(t=>
            t.id===sessionId
              ? {
                  ...t,
                  hasVenv:!!msg.has_venv,
                  cwd:t.cwd||projectRoot,
                  processState:'running',
                  exitCode:null,
                  interrupting:false
                }
              : t
          ))

          setTimeout(async()=>{
            await ensureXtermInstance(sessionId)

            if(canAutoFocusTerminal()){
              focusXterm(sessionId)
            }
          },50)
        }

        if(msg.type==='cleared'){
          return
        }

        if(msg.type==='interrupted'){
          // 'interrupted' means that the stop signal/child-tree termination
          // request was delivered.  It does NOT mean PowerShell has already
          // returned to its prompt.  Keep the command busy until the prompt
          // marker arrives so a second Ctrl+C can still be sent if shutdown
          // is taking longer than expected.  The prompt can race ahead of
          // this ACK, so ignore a late ACK once the parser already marked the
          // command idle.
          if(terminalCommandBusyRef.current[sessionId]){
            setTerminalSessions(prev=>prev.map(t=>
              t.id===sessionId
                ? {
                    ...t,
                    busy:true,
                    interrupting:true
                  }
                : t
            ))
          }
        }

        if(msg.type==='process_exit'){
          const exitCode=msg.exit_code
          terminalCommandBusyRef.current[sessionId]=false

          setTerminalSessions(prev=>prev.map(t=>
            t.id===sessionId
              ? {
                  ...t,
                  processState:'exited',
                  exitCode,
                  command:'',
                  busy:false,
                  interrupting:false
                }
              : t
          ))

          setTerminalConnectionState(prev=>({
            ...prev,
            [sessionId]:'closed'
          }))

          writeXterm(
            sessionId,
            `\r\n[터미널 종료] PowerShell 프로세스가 종료되었습니다. ExitCode=${exitCode ?? '-'}\r\n`
          )

          return
        }

        if(msg.type==='error'){
          const errorInfo={
            stage:msg.stage||'websocket',
            message:msg.message||'알 수 없는 터미널 오류',
            detail:msg.detail||'',
            logPath:msg.log_path||'',
            sessionId:msg.session_id||sessionId,
            root:msg.root||projectRoot,
            wsUrl,
            time:new Date().toLocaleString()
          }

          setTerminalErrors(prev=>({
            ...prev,
            [sessionId]:errorInfo
          }))

          setTerminalSessions(prev=>prev.map(t=>
            t.id===sessionId
              ? {
                  ...t,
                  output:
                    (t.output||'')
                    + '\n[ERROR] '
                    + errorInfo.message
                    + '\n'
                    + (
                      errorInfo.logPath
                        ? `[로그] ${errorInfo.logPath}\n`
                        : ''
                    )
                }
              : t
          ))
        }

      }catch(e){
        const errorInfo={
          stage:'message_parse',
          message:String(e),
          detail:'',
          logPath:'',
          sessionId,
          root:projectRoot,
          wsUrl,
          time:new Date().toLocaleString()
        }

        setTerminalErrors(prev=>({
          ...prev,
          [sessionId]:errorInfo
        }))
      }
    }

    ws.onerror=(event)=>{
      const errorInfo={
        stage:'websocket_error',
        message:'WebSocket 연결/통신 오류가 발생했습니다.',
        detail:
          `readyState=${ws.readyState}\n`
          + `url=${wsUrl}`,
        logPath:'',
        sessionId,
        root:projectRoot,
        wsUrl,
        time:new Date().toLocaleString()
      }

      setTerminalErrors(prev=>({
        ...prev,
        [sessionId]:errorInfo
      }))

      setTerminalConnectionState(prev=>({
        ...prev,
        [sessionId]:'error'
      }))
    }

    ws.onclose=(event)=>{
          if(terminalIntentionalCloseRef.current[sessionId]){
            terminalIntentionalCloseRef.current[sessionId]=false
            return
          }

      setTerminalConnectionState(prev=>({
        ...prev,
        [sessionId]:'closed'
      }))

      if(
        event.code!==1000
        && !terminalErrors[sessionId]
      ){
        const errorInfo={
          stage:'websocket_close',
          message:`WebSocket가 비정상 종료되었습니다. code=${event.code}`,
          detail:`reason=${event.reason||'(없음)'}`,
          logPath:'',
          sessionId,
          root:projectRoot,
          wsUrl,
          time:new Date().toLocaleString()
        }

        setTerminalErrors(prev=>({
          ...prev,
          [sessionId]:errorInfo
        }))
      }

      if(terminalSocketsRef.current[sessionId]===ws){
        delete terminalSocketsRef.current[sessionId]
      }
    }

    return ws
  }

  useEffect(()=>{
    // 기본 PowerShell 탭은 선택 프로젝트가 아니라 AgentStudio 설치 경로를 사용합니다.
    // SYSTEM_ADMIN.ps1이 runtime-config.js에 실제 설치 경로를 기록합니다.
    const cfg=window.__AGENTSTUDIO_CONFIG__||{}
    const agentStudioRoot=String(cfg.AGENTSTUDIO_ROOT||'').trim()
    const sessionId='terminal-1'

    if(!agentStudioRoot) return

    terminalRootRef.current[sessionId]=agentStudioRoot
    terminalCwdRef.current[sessionId]=agentStudioRoot

    setTerminalSessions(prev=>prev.map(t=>
      t.id===sessionId
        ? {
            ...t,
            name:'PowerShell',
            projectId:'agentstudio-root',
            projectName:'AgentStudio',
            root:agentStudioRoot,
            cwd:agentStudioRoot,
            processState:t.processState==='exited'?'exited':'starting'
          }
        : t
    ))

    let cancelled=false
    const connectDefault=async()=>{
      try{
        await ensureXtermInstance(sessionId)
        if(cancelled) return
        await connectProjectTerminal({
          id:'agentstudio-root',
          name:'AgentStudio',
          project_root:agentStudioRoot
        },sessionId)
      }catch(e){
        console.error('기본 AgentStudio PowerShell 연결 실패',e)
      }
    }

    const timer=setTimeout(connectDefault,80)
    return()=>{
      cancelled=true
      clearTimeout(timer)
    }
    // runtime config는 앱 시작 시 고정되므로 한 번만 연결합니다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[])

  const sendTerminalInput=async(id)=>{
    const target=terminalSessions.find(t=>t.id===id)
    if(!target||!target.command.trim()) return

    let ws=terminalSocketsRef.current[id]

    if(!ws||ws.readyState!==WebSocket.OPEN){
      ws=await connectProjectTerminal(
        {
          id:target.projectId,
          name:target.projectName,
          project_root:target.root||root
        },
        id
      )
    }

    if(!ws) return

    if(ws.readyState===WebSocket.CONNECTING){
      await new Promise(resolve=>{
        const done=()=>resolve()
        ws.addEventListener('open',done,{once:true})
        setTimeout(resolve,2500)
      })
    }

    if(ws.readyState!==WebSocket.OPEN){
      setTerminalSessions(prev=>prev.map(t=>
        t.id===id
          ? {
              ...t,
              output:(t.output||'')
                + '\n[ERROR] 터미널 연결이 열리지 않았습니다.\n'
            }
          : t
      ))
      return
    }

    const cmd=target.command.trim()
    const cwd=target.cwd||target.root||root||''
    const prompt=`${target.hasVenv?'(.venv) ':''}PS ${cwd}> `

    setTerminalSessions(prev=>prev.map(t=>
      t.id===id
        ? {
            ...t,
            command:'',
            output:(t.output||'')
              + (t.output?.endsWith('\n')||!t.output?'':'\n')
              + prompt
              + cmd
              + '\n'
          }
        : t
    ))

    terminalCommandBusyRef.current[id]=true
    setTerminalSessions(prev=>prev.map(t=>t.id===id?{...t,busy:true,interrupting:false}:t))
    ws.send(serializeTerminalClientMessage({
      type:'input',
      data:cmd+'\r\n'
    }))

    scrollTerminalToBottom(id,'auto')

    setTimeout(()=>{
      terminalInlineInputRef.current?.focus()
    },30)
  }

  const interruptTerminal=(id)=>{
    const ws=terminalSocketsRef.current[id]
    if(ws&&ws.readyState===WebSocket.OPEN){
      // Keep the command in a busy/interrupting state until the backend
      // command wrapper emits the normal prompt marker.  This prevents the
      // first Ctrl+C acknowledgement from making later Ctrl+C presses local
      // only while Streamlit/Python is still shutting down.
      terminalCommandBusyRef.current[id]=true
      setTerminalSessions(prev=>prev.map(t=>t.id===id?{...t,busy:true,interrupting:true}:t))
      ws.send(serializeTerminalClientMessage({type:'interrupt'}))
    }
  }


  const setTerminalCompletionState=(next)=>{
    terminalCompletionRef.current=next
    setTerminalCompletion(next)
  }

  const closeTerminalCompletion=(sessionId=null)=>{
    const current=terminalCompletionRef.current
    if(sessionId){
      clearTimeout(terminalCompletionTimerRef.current[sessionId])
      delete terminalCompletionTimerRef.current[sessionId]
    }else{
      Object.values(terminalCompletionTimerRef.current).forEach(timer=>clearTimeout(timer))
      terminalCompletionTimerRef.current={}
    }
    if(!current) return
    if(sessionId&&current.sessionId!==sessionId) return
    setTerminalCompletionState(null)
  }

  const moveTerminalCompletionSelection=(delta)=>{
    const current=terminalCompletionRef.current
    if(!current?.items?.length) return
    const length=current.items.length
    const selectedIndex=(current.selectedIndex+delta+length)%length
    setTerminalCompletionState({...current,selectedIndex})
  }

  const applyTerminalCompletion=(itemOverride=null)=>{
    const current=terminalCompletionRef.current
    if(!current) return false

    const item=itemOverride||current.items?.[current.selectedIndex]
    if(!item) return false

    const id=current.sessionId
    const buffer=xtermCommandBuffersRef.current[id]||''
    const start=Math.max(0,Math.min(current.replaceStart??0,buffer.length))
    const end=Math.max(start,Math.min(current.replaceEnd??start,buffer.length))
    const insertText=String(item.insert_text??item.label??'')
    const nextBuffer=buffer.slice(0,start)+insertText+buffer.slice(end)
    const nextCursor=start+insertText.length
    const setter=xtermSetCommandLineRef.current[id]

    if(typeof setter==='function'){
      setter(nextBuffer,nextCursor)
      closeTerminalCompletion(id)
      setTimeout(()=>focusXterm(id),0)
      return true
    }

    return false
  }

  const requestTerminalCompletion=async(id,buffer,cursor,{preserveItems=false}={})=>{
    const projectRoot=terminalRootRef.current[id]||root||''
    if(!projectRoot) return

    const cwd=terminalCwdRef.current[id]||projectRoot
    const requestKey=`${id}:${Date.now()}:${Math.random().toString(16).slice(2)}`
    const current=terminalCompletionRef.current
    const canPreserve=preserveItems&&current?.sessionId===id

    if(canPreserve){
      setTerminalCompletionState({
        ...current,
        requestKey,
        loading:false,
        error:null,
        liveFiltering:true
      })
    }else{
      setTerminalCompletionState({
        sessionId:id,
        requestKey,
        loading:true,
        items:[],
        selectedIndex:0,
        replaceStart:cursor,
        replaceEnd:cursor,
        token:'',
        liveFiltering:false
      })
    }

    try{
      const result=await api('/terminal/completions',{
        method:'POST',
        body:JSON.stringify({root:projectRoot,cwd,buffer,cursor})
      })

      if(terminalCompletionRef.current?.requestKey!==requestKey) return

      const items=Array.isArray(result?.items)?result.items:[]
      setTerminalCompletionState({
        sessionId:id,
        requestKey,
        loading:false,
        items,
        selectedIndex:0,
        replaceStart:Number(result?.replace_start??cursor),
        replaceEnd:Number(result?.replace_end??cursor),
        token:String(result?.token||''),
        cwd:String(result?.cwd||cwd),
        liveFiltering:false
      })
    }catch(e){
      if(terminalCompletionRef.current?.requestKey!==requestKey) return
      setTerminalCompletionState({
        sessionId:id,
        requestKey,
        loading:false,
        items:canPreserve?(terminalCompletionRef.current?.items||[]):[],
        selectedIndex:0,
        replaceStart:cursor,
        replaceEnd:cursor,
        error:String(e),
        liveFiltering:false
      })
    }
  }

  const scheduleTerminalCompletionRefresh=(id,buffer,cursor)=>{
    const current=terminalCompletionRef.current
    if(current?.sessionId!==id) return
    clearTimeout(terminalCompletionTimerRef.current[id])
    terminalCompletionTimerRef.current[id]=setTimeout(()=>{
      delete terminalCompletionTimerRef.current[id]
      requestTerminalCompletion(id,buffer,cursor,{preserveItems:true})
    },85)
  }

  const scrollTerminalToBottom=(id,behavior='smooth')=>{
    requestAnimationFrame(()=>{
      const el=terminalOutputRefs.current[id]
      if(!el) return
      el.scrollTo({top:el.scrollHeight,behavior})
    })
  }


  const ensureXtermInstance=async(id)=>{
    const container=xtermContainersRef.current[id]
    if(!container) return null

    if(xtermInstancesRef.current[id]){
      const rect=container.getBoundingClientRect()

      if(
        screen==='WORKSPACE'
        && workspaceTab==='CODE'
        && rect.width>=120
        && rect.height>=80
      ){
        fitTerminalViewport(id)
      }

      return xtermInstancesRef.current[id]
    }

    const term=new XTerm({
      cursorBlink:true,
      cursorStyle:'block',
      cursorInactiveStyle:'outline',
      convertEol:true,
      scrollback:1500,
      fontFamily:'Consolas, "Cascadia Mono", monospace',
      fontSize:13,
      lineHeight:1.25,
      theme:{
        background:'#071009',
        foreground:'#d8e2ec',
        cursor:'#f2f5f8',
        selectionBackground:'#264d73',
        black:'#071009',
        brightBlack:'#66717c',
        green:'#57d978',
        brightGreen:'#82ec9e',
        yellow:'#e8c36a',
        brightYellow:'#f3dc91',
        blue:'#5f9eea',
        brightBlue:'#83b8f5',
        red:'#e06c75',
        brightRed:'#f08a91',
        cyan:'#56c7d9',
        brightCyan:'#79dceb',
        white:'#d8e2ec',
        brightWhite:'#ffffff'
      }
    })

    const fitAddon=new FitAddon()
    term.loadAddon(fitAddon)
    term.open(container)

    xtermInstancesRef.current[id]=term
    xtermFitAddonsRef.current[id]=fitAddon

    {
      const rect=container.getBoundingClientRect()

      if(
        screen==='WORKSPACE'
        && workspaceTab==='CODE'
        && rect.width>=120
        && rect.height>=80
      ){
        fitTerminalViewport(id)
      }
    }

    xtermCommandBuffersRef.current[id]=''
    xtermCommandHistoryRef.current[id]=
      xtermCommandHistoryRef.current[id]||[]
    xtermHistoryIndexRef.current[id]=
      xtermCommandHistoryRef.current[id].length
    xtermCursorIndexRef.current[id]=0

    const redrawCurrentLine=(value,cursorIndex)=>{
      const prompt=xtermPromptRef.current[id]||''
      fitTerminalViewport(id)
      term.write('\x1b[2K\r')

      // Keep pasted PowerShell blocks readable exactly as multi-line input.
      // The local command buffer uses LF, while xterm display uses CRLF so
      // every pasted line starts at column 0 just like VS Code Terminal.
      const displayValue=String(value||'').replace(/\r\n|\r|\n/g,'\r\n')
      term.write(prompt+displayValue)

      const tail=value.slice(cursorIndex)
      if(!/[\r\n]/.test(tail)){
        const moveLeft=terminalCellWidth(tail)
        if(moveLeft>0){
          term.write(`\x1b[${moveLeft}D`)
        }
      }
    }

    const setCommandLine=(value,cursorIndex=value.length)=>{
      xtermCommandBuffersRef.current[id]=value
      xtermCursorIndexRef.current[id]=Math.max(
        0,
        Math.min(cursorIndex,value.length)
      )
      redrawCurrentLine(
        xtermCommandBuffersRef.current[id],
        xtermCursorIndexRef.current[id]
      )
    }

    xtermSetCommandLineRef.current[id]=setCommandLine


    const clearKeyboardTerminalSelection=()=>{
      delete xtermKeyboardSelectionRef.current[id]
    }

    const extendKeyboardTerminalSelection=(direction)=>{
      const activeBuffer=term.buffer?.active
      if(!activeBuffer) return

      const maxLine=Math.max(0,activeBuffer.length-1)
      const currentLine=Math.max(
        0,
        Math.min(maxLine,(activeBuffer.baseY||0)+(activeBuffer.cursorY||0))
      )

      let state=xtermKeyboardSelectionRef.current[id]
      if(!state){
        state={anchor:currentLine,focus:currentLine}
      }

      const nextFocus=Math.max(
        0,
        Math.min(maxLine,state.focus+(direction<0?-1:1))
      )
      state={...state,focus:nextFocus}
      xtermKeyboardSelectionRef.current[id]=state

      const start=Math.min(state.anchor,state.focus)
      const end=Math.max(state.anchor,state.focus)
      term.selectLines(start,end)

      // Keep the newly extended edge visible while the user holds Shift and
      // presses Up/Down repeatedly. scrollLines only affects the viewport; it
      // does not alter PowerShell history or the local input buffer.
      if(direction<0){
        const viewportTop=activeBuffer.viewportY||0
        if(nextFocus<=viewportTop) term.scrollLines(-1)
      }else{
        const viewportTop=activeBuffer.viewportY||0
        const visibleRows=Math.max(1,term.rows||1)
        if(nextFocus>=viewportTop+visibleRows-1) term.scrollLines(1)
      }
    }

    term.attachCustomKeyEventHandler(event=>{
      // Only the terminal may consume keyboard input while it is the explicit
      // focus owner. Notebook/Monaco/LLM clicks can leave xterm's hidden
      // textarea mounted, and older builds could therefore keep receiving
      // Backspace after the user had moved back to the editor.
      if(event.type==='keydown'&&focusOwnerRef.current!=='terminal'){
        return false
      }

      if(
        event.type==='keydown'
        && event.shiftKey
        && !event.ctrlKey
        && !event.altKey
        && !event.metaKey
        && (event.code==='ArrowUp'||event.code==='ArrowDown')
      ){
        event.preventDefault?.()
        extendKeyboardTerminalSelection(event.code==='ArrowUp'?-1:1)
        return false
      }

      if(
        event.type==='keydown'
        && !event.shiftKey
        && (event.code==='ArrowUp'||event.code==='ArrowDown')
      ){
        clearKeyboardTerminalSelection()
        if(term.hasSelection()) term.clearSelection()
      }

      if(
        event.type==='keydown'
        && event.ctrlKey
        && !event.altKey
        && !event.metaKey
      ){
        // VS Code compatible copy semantics:
        // selected terminal text -> clipboard, otherwise Ctrl+C is passed
        // through to xterm/onData where it remains the PowerShell interrupt.
        if(event.code==='KeyC'&&term.hasSelection()){
          const selected=term.getSelection()
          if(selected){
            navigator.clipboard?.writeText?.(selected).catch(err=>
              console.warn('[Terminal] clipboard copy failed',err)
            )
          }
          return false
        }

        // Ctrl+V is handled only by the browser/xterm native paste event.
        // Do not read navigator.clipboard here: doing both would emit the
        // clipboard text twice. Returning false skips xterm key processing
        // while leaving the browser paste event as the single input source.
        if(event.code==='KeyV'){
          return false
        }

        if(event.code==='Space'){
          requestTerminalCompletion(
            id,
            xtermCommandBuffersRef.current[id]||'',
            xtermCursorIndexRef.current[id]??0
          )
          return false
        }
      }
      return true
    })

    const eraseTerminalCellsBackward=(count)=>{
      const cells=Math.max(0,Number(count)||0)
      if(!cells) return

      const activeBuffer=term.buffer?.active
      const cols=Math.max(1,Number(term.cols)||1)
      let cursorX=Math.max(0,Number(activeBuffer?.cursorX)||0)
      let sequence=''

      // Backspace (\b) does not reliably cross a soft-wrapped xterm row.
      // Move explicitly across the row boundary and erase in-place so a long
      // PowerShell command is shortened instead of being redrawn repeatedly.
      for(let index=0;index<cells;index++){
        if(cursorX>0){
          sequence+='\x1b[D\x1b[X'
          cursorX-=1
        }else{
          sequence+=`\x1b[A\x1b[${cols}G\x1b[X`
          cursorX=cols-1
        }
      }

      if(sequence) term.write(sequence)
    }

    const disposable=term.onData(data=>{
      // Defensive input gate matching attachCustomKeyEventHandler above.
      // Program output uses term.write() and is unaffected by this guard.
      if(focusOwnerRef.current!=='terminal') return

      const currentSession=terminalSessions.find(t=>t.id===id)
      if(currentSession?.processState==='exited') return

      const ws=terminalSocketsRef.current[id]
      if(!ws||ws.readyState!==WebSocket.OPEN) return

      // Any normal terminal input starts a new editing action, so keyboard
      // selection mode ends. Ctrl+C with a selection is intercepted above and
      // therefore still copies before this path is reached.
      if(data!=='\x00'){
        clearKeyboardTerminalSelection()
        if(term.hasSelection()) term.clearSelection()
      }

      let buffer=xtermCommandBuffersRef.current[id]||''
      let cursor=xtermCursorIndexRef.current[id]??buffer.length

      // Ctrl+Space (NUL) opens the AgentStudio terminal completion menu.
      if(data==='\x00'){
        requestTerminalCompletion(id,buffer,cursor)
        return
      }

      // xterm native paste arrives through onData as one payload. Keep it
      // as the single source of truth so Ctrl+V is inserted exactly once.
      // Preserve multi-line PowerShell blocks in the local command buffer;
      // pasting never executes the command until the user presses Enter.
      if(data.length>1&&/[\r\n]/.test(data)){
        const pasted=String(data).replace(/\r\n|\r/g,'\n')
        buffer=buffer.slice(0,cursor)+pasted+buffer.slice(cursor)
        cursor+=pasted.length
        xtermCommandBuffersRef.current[id]=buffer
        xtermCursorIndexRef.current[id]=cursor
        closeTerminalCompletion(id)
        setCommandLine(buffer,cursor)
        return
      }

      // A single-line paste can also arrive as one multi-character onData
      // payload. It is handled by the normal printable-text path below once.

      const activeCompletion=terminalCompletionRef.current
      if(activeCompletion?.sessionId===id){
        if(data==='\x1b[A'){
          moveTerminalCompletionSelection(-1)
          return
        }
        if(data==='\x1b[B'){
          moveTerminalCompletionSelection(1)
          return
        }
        if(data==='\t'||data==='\r'){
          if(activeCompletion.items?.length){
            applyTerminalCompletion()
            return
          }
          closeTerminalCompletion(id)
        }else if(data==='\x1b'){
          closeTerminalCompletion(id)
          return
        }
        // Keep the popup open for normal typing/backspace/delete/cursor moves.
        // The candidate list is refreshed from the current buffer below.
      }else if(data==='\t'){
        requestTerminalCompletion(id,buffer,cursor)
        return
      }

      // Enter
      if(data==='\r'){
        // Move cursor visually to line end before newline.
        const right=terminalCellWidth(buffer.slice(cursor))
        if(right>0){
          term.write(`\x1b[${right}C`)
        }
        term.write('\r\n',()=>revealTerminalBottom(id))

        const command=buffer
        xtermCommandBuffersRef.current[id]=''
        xtermCursorIndexRef.current[id]=0

        if(command.trim()){
          const history=xtermCommandHistoryRef.current[id]||[]
          history.push(command)
          xtermCommandHistoryRef.current[id]=history
          xtermHistoryIndexRef.current[id]=history.length
        }

        terminalCommandBusyRef.current[id]=!!command.trim()
        setTerminalSessions(prev=>prev.map(t=>t.id===id?{...t,busy:!!command.trim(),interrupting:false}:t))
        ws.send(serializeTerminalClientMessage({
          type:'command',
          data:command
        }))

        term.scrollToBottom()
        return
      }

      // Ctrl+C
      if(data==='\x03'){
        closeTerminalCompletion(id)
        const commandRunning=!!terminalCommandBusyRef.current[id]
        const hadLocalInput=!!buffer
        xtermCommandBuffersRef.current[id]=''
        xtermCursorIndexRef.current[id]=0

        // VS Code/PowerShell style: when no command is running, Ctrl+C only
        // cancels the current local input line. Do not signal the idle
        // PowerShell process, which can otherwise enter debugger mode.
        if(!commandRunning){
          const prompt=xtermPromptRef.current[id]||''
          term.write('^C\r\n'+prompt)
          return
        }

        term.write('^C\r\n')
        interruptTerminal(id)
        return
      }

      // Backspace
      if(data==='\x7f'){
        if(cursor>0){
          const atEnd=cursor===buffer.length
          const previous=terminalPreviousCharacter(buffer,cursor)
          const removed=previous.text
          buffer=buffer.slice(0,previous.start)+buffer.slice(cursor)
          cursor=previous.start

          if(atEnd){
            xtermCommandBuffersRef.current[id]=buffer
            xtermCursorIndexRef.current[id]=cursor

            // One Hangul/CJK character occupies two terminal cells. Erase by
            // display-cell width rather than JavaScript string length so
            // repeated Backspace always reaches the prompt without leaving
            // half-width remnants on screen.
            const eraseCells=Math.max(1,terminalCellWidth(removed))
            eraseTerminalCellsBackward(eraseCells)
            fitTerminalViewport(id)
          }else{
            setCommandLine(buffer,cursor)
          }
          scheduleTerminalCompletionRefresh(id,buffer,cursor)
        }
        return
      }

      // Delete
      if(data==='\x1b[3~'){
        if(cursor<buffer.length){
          const next=terminalNextCharacter(buffer,cursor)
          buffer=buffer.slice(0,cursor)+buffer.slice(next.end)
          setCommandLine(buffer,cursor)
          scheduleTerminalCompletionRefresh(id,buffer,cursor)
        }
        return
      }

      // Left
      if(data==='\x1b[D'){
        if(cursor>0){
          const previous=terminalPreviousCharacter(buffer,cursor)
          cursor=previous.start
          xtermCursorIndexRef.current[id]=cursor
          const move=Math.max(1,terminalCellWidth(previous.text))
          term.write(`\x1b[${move}D`)
          scheduleTerminalCompletionRefresh(id,buffer,cursor)
        }
        return
      }

      // Right
      if(data==='\x1b[C'){
        if(cursor<buffer.length){
          const next=terminalNextCharacter(buffer,cursor)
          cursor=next.end
          xtermCursorIndexRef.current[id]=cursor
          const move=Math.max(1,terminalCellWidth(next.text))
          term.write(`\x1b[${move}C`)
          scheduleTerminalCompletionRefresh(id,buffer,cursor)
        }
        return
      }

      // Home
      if(data==='\x1b[H'||data==='\x1b[1~'){
        setCommandLine(buffer,0)
        scheduleTerminalCompletionRefresh(id,buffer,0)
        return
      }

      // End
      if(data==='\x1b[F'||data==='\x1b[4~'){
        setCommandLine(buffer,buffer.length)
        scheduleTerminalCompletionRefresh(id,buffer,buffer.length)
        return
      }

      // Up history
      if(data==='\x1b[A'){
        const history=xtermCommandHistoryRef.current[id]||[]
        if(!history.length) return

        let index=xtermHistoryIndexRef.current[id]
        index=Math.max(0,(index??history.length)-1)
        xtermHistoryIndexRef.current[id]=index

        const value=history[index]||''
        setCommandLine(value,value.length)
        return
      }

      // Down history
      if(data==='\x1b[B'){
        const history=xtermCommandHistoryRef.current[id]||[]
        if(!history.length) return

        let index=xtermHistoryIndexRef.current[id]
        index=Math.min(
          history.length,
          (index??history.length)+1
        )
        xtermHistoryIndexRef.current[id]=index

        const value=index<history.length
          ? history[index]
          : ''

        setCommandLine(value,value.length)
        return
      }

      // Ignore unsupported control sequences.
      if(data.startsWith('\x1b')||data<' '){
        return
      }

      // Insert printable text at current cursor position.
      const insertAtEnd=cursor===buffer.length
      buffer=
        buffer.slice(0,cursor)
        +data
        +buffer.slice(cursor)

      cursor+=data.length
      xtermCommandBuffersRef.current[id]=buffer
      xtermCursorIndexRef.current[id]=cursor

      if(insertAtEnd){
        // 화면 폭을 넘는 입력은 xterm의 기본 동작으로 다음 줄에 자동 줄바꿈합니다.
        fitTerminalViewport(id)
        term.write(data)
      }else{
        // Mid-line editing is rare; keep the existing redraw path for it.
        setCommandLine(buffer,cursor)
      }

      scheduleTerminalCompletionRefresh(id,buffer,cursor)
    })

    xtermDisposablesRef.current[id]=disposable

    if(canAutoFocusTerminal()){
      term.focus()
    }
    return term
  }

  const revealTerminalBottom=(id)=>{
    const term=xtermInstancesRef.current[id]
    if(!term) return

    const reveal=()=>{
      try{
        term.scrollToBottom()
        term.refresh(0,Math.max(0,term.rows-1))
      }catch{}
    }

    reveal()
    requestAnimationFrame(reveal)
    setTimeout(reveal,25)
  }

  const writeXterm=(id,text,{keepRight=false}={})=>{
    const term=xtermInstancesRef.current[id]
    if(!term||!text) return
    fitTerminalViewport(id)
    // xterm.write는 buffer 반영이 비동기일 수 있으므로 write 완료 뒤에
    // scrollToBottom을 수행해야 마지막 prompt/caret까지 실제로 보입니다.
    term.write(text,()=>revealTerminalBottom(id))
  }

  const focusXterm=(id,{force=false}={})=>{
    requestAnimationFrame(()=>{
      if(!force&&!canAutoFocusTerminal()) return
      const term=xtermInstancesRef.current[id]
      fitTerminalViewport(id)
      term?.focus()
    })
  }


  const clearTerminalView=(id)=>{
    if(!id) return

    const term=xtermInstancesRef.current[id]
    const prompt=xtermPromptRef.current[id]||''
    const buffer=xtermCommandBuffersRef.current[id]||''
    const busy=!!terminalCommandBusyRef.current[id]

    // Clear any partially parsed old output so it cannot reappear after Clear.
    xtermOutputParseBufferRef.current[id]=''

    try{
      if(term){
        term.write('\x1b[2J\x1b[3J\x1b[H',()=>{
          if(!busy){
            term.write(prompt+buffer,()=>{
              try{
                term.scrollToBottom()
                term.refresh(0,Math.max(0,term.rows-1))
              }catch{}
            })
          }else{
            try{
              term.scrollToBottom()
              term.refresh(0,Math.max(0,term.rows-1))
            }catch{}
          }
        })
      }
    }catch{}

    setTerminalSessions(prev=>prev.map(t=>
      t.id===id
        ? {...t,output:''}
        : t
    ))

    // Also clear Backend replay history so reconnecting does not restore
    // output that the user explicitly cleared. The shell process is kept alive.
    const ws=terminalSocketsRef.current[id]
    try{
      if(ws?.readyState===WebSocket.OPEN){
        ws.send(serializeTerminalClientMessage({type:'clear'}))
      }
    }catch{}

    setTimeout(()=>{
      fitTerminalViewport(id)
      if(canAutoFocusTerminal()){
        try{ xtermInstancesRef.current[id]?.focus() }catch{}
      }
    },0)
  }

  const restartTerminalSession=async(id)=>{
    const old=terminalSessions.find(t=>t.id===id)
    if(!old?.root) return

    // 기존 세션을 재시작하기 위해 닫는 것은 정상 동작입니다.
    terminalIntentionalCloseRef.current[id]=true

    setTerminalErrors(prev=>({
      ...prev,
      [id]:null
    }))

    const ws=terminalSocketsRef.current[id]
    try{ ws?.close() }catch{}
    delete terminalSocketsRef.current[id]

    try{
      xtermInstancesRef.current[id]?.clear()
      xtermInstancesRef.current[id]?.reset()
    }catch{}

    xtermCommandBuffersRef.current[id]=''
    xtermCursorIndexRef.current[id]=0
    terminalCommandBusyRef.current[id]=false
    xtermPromptRef.current[id]=''
    xtermOutputParseBufferRef.current[id]=''
    xtermRequiredColsRef.current[id]=0

    setTerminalSessions(prev=>prev.map(t=>
      t.id===id
        ? {
            ...t,
            processState:'starting',
            exitCode:null,
            command:'',
            output:''
          }
        : t
    ))

    terminalIntentionalCloseRef.current[id]=false

    await connectProjectTerminal(
      {
        id:old.projectId,
        name:old.projectName,
        project_root:old.root
      },
      id
    )

    setTimeout(async()=>{
      await ensureXtermInstance(id)
      if(canAutoFocusTerminal()){
        focusXterm(id)
      }
    },100)
  }


  // v5.145 terminal layout restore:
  // CODE 탭이 실제로 보일 때만 xterm fit을 수행합니다.
  // 숨겨진 상태에서 fit하면 0/1px 크기를 열/행으로 계산해 화면이 깨질 수 있습니다.
  useEffect(()=>{
    if(
      !activeTerminalId
      || screen!=='WORKSPACE'
      || workspaceTab!=='CODE'
      || isSqlFile
    ) return

    const restore=()=>{
      const term=xtermInstancesRef.current[activeTerminalId]
      const current=terminalSessions.find(
        t=>t.id===activeTerminalId
      )

      fitTerminalViewport(activeTerminalId)
      try{
        if(term){
          term.refresh(0,Math.max(0,term.rows-1))
          term.scrollToBottom()
        }
      }catch{}

      if(
        current?.processState!=='exited'
        && canAutoFocusTerminal()
      ){
        try{ term?.focus() }catch{}
      }
    }

    const a=setTimeout(restore,20)
    const b=setTimeout(restore,120)
    const c=setTimeout(restore,300)

    return()=>{
      clearTimeout(a)
      clearTimeout(b)
      clearTimeout(c)
    }
  },[activeTerminalId,terminalSessions.length,screen,workspaceTab,isSqlFile,selected])



  useEffect(()=>{
    const closeEditorTabContextMenu=()=>{
      setEditorTabMenu(null)
      setEditorFilesMenu(null)
    }

    const closeEditorTabContextMenuByKey=(e)=>{
      if(e.key==='Escape'){
        setEditorTabMenu(null)
        setEditorFilesMenu(null)
      }
    }

    window.addEventListener(
      'mousedown',
      closeEditorTabContextMenu
    )

    window.addEventListener(
      'keydown',
      closeEditorTabContextMenuByKey
    )

    return()=>{
      window.removeEventListener(
        'mousedown',
        closeEditorTabContextMenu
      )

      window.removeEventListener(
        'keydown',
        closeEditorTabContextMenuByKey
      )
    }
  },[])


  async function loadFiles(rootOverride=null){
    const targetRoot=String(rootOverride||resolveWorkspaceRoot()||'').trim()

    if(!targetRoot){
      fileTreeRootRef.current=''
      setFiles([])
      setProjectDirs([])
      return {files:[],dirs:[]}
    }

    try{
      const [fileRows,dirRows]=await Promise.all([
        api(`/files?root=${encodeURIComponent(targetRoot)}`),
        api(`/folders?root=${encodeURIComponent(targetRoot)}`)
      ])

      // Keep every project path in one canonical form inside the UI.
      // Windows Backend responses may contain `\\` while tree node paths use `/`.
      // Comparing those raw strings made a selected nested folder look unknown and
      // caused new files to fall back to the project root.
      const nextFiles=(Array.isArray(fileRows)?fileRows:(fileRows?.files||[]))
        .map(normalizeProjectRelativePath)
        .filter(Boolean)
      const nextDirs=(Array.isArray(dirRows)?dirRows:(dirRows?.folders||[]))
        .map(normalizeProjectRelativePath)
        .filter(Boolean)

      const previousTreeRoot=String(fileTreeRootRef.current||'').trim()
      if(previousTreeRoot&&previousTreeRoot.toLocaleLowerCase()!==targetRoot.toLocaleLowerCase()){
        setProjectFileSearch('')
        setEditorTextSearchResults([])
        setEditorTextSearchMeta(null)
        setEditorTextSearchError('')
      }
      workspaceRootRef.current=targetRoot
      fileTreeRootRef.current=targetRoot
      setFiles(nextFiles)
      setProjectDirs(nextDirs)

      return {files:nextFiles,dirs:nextDirs}
    }catch(e){
      console.error('프로젝트 파일/폴더 목록 로드 실패',e)
      if(String(fileTreeRootRef.current||'').trim()===targetRoot){
        fileTreeRootRef.current=''
      }
      setFiles([])
      setProjectDirs([])
      throw e
    }
  }

  const addExternalFileNotification=(path,status)=>{
    const normalized=normalizeProjectRelativePath(path)
    if(!normalized) return
    setExternalFileNotifications(prev=>{
      const filtered=prev.filter(item=>item.path!==normalized)
      return [{
        id:`${Date.now()}-${normalized}`,
        path:normalized,
        status,
        time:new Date().toISOString()
      },...filtered].slice(0,50)
    })
    // External changes must be visible immediately instead of only changing
    // the bell badge. The user can close the menu after reviewing it.
    setExternalNotificationOpen(true)
  }

  const reloadExternalEditorFile=async(editorPath,{activate=false}={})=>{
    const normalized=normalizeProjectRelativePath(editorPath)
    const workspaceRoot=resolveWorkspaceRoot(
      fileTreeRootRef.current||editorFileRootRef.current?.[editorPath]||''
    )
    if(!workspaceRoot){
      throw new Error('프로젝트 root를 확인할 수 없습니다. 프로젝트를 다시 선택한 뒤 파일을 열어주세요.')
    }

    if(isBinaryPreviewFile(editorPath)){
      let latest={exists:true,mtime_ns:0,size:0}
      try{
        latest=await api(`/files/meta?root=${encodeURIComponent(workspaceRoot)}&relative_path=${encodeURIComponent(editorPath)}`)
      }catch(_){ }
      const latestMeta={
        mtime_ns:latest.mtime_ns||Date.now(),
        size:latest.size||0,
        sha256:latest.sha256||''
      }
      editorFileDiskMetaRef.current={
        ...editorFileDiskMetaRef.current,
        [normalized]:latestMeta
      }
      setEditorFileDiskMeta(prev=>({...prev,[normalized]:latestMeta}))
      setEditorFileDirty(prev=>({...prev,[editorPath]:false}))
      setEditorExternalState(prev=>{
        const copy={...prev}; delete copy[normalized]; return copy
      })
      if(isPdfFile(editorPath)){
        setPdfPreviewRevision(prev=>({...prev,[normalized]:Date.now()}))
      }else{
        setPresentationPreviewRevision(prev=>({...prev,[normalized]:Date.now()}))
      }
      if(activate||selectedEditorFileRef.current===editorPath){
        setSelected(editorPath)
        setFileTreeSelected(editorPath)
        setFileTreeSelectedPaths([editorPath])
        setCode('')
        setFileSaveStatus(isPdfFile(editorPath)?'PDF 미리보기 새로고침':'PowerPoint 미리보기 새로고침')
      }
      return latest
    }

    const latest=await api('/files/read',{
      method:'POST',
      body:JSON.stringify({root:workspaceRoot,relative_path:editorPath})
    })
    const latestContent=latest.content??''
    setEditorFileContents(prev=>({...prev,[editorPath]:latestContent}))
    setEditorFileDirty(prev=>({...prev,[editorPath]:false}))
    const latestMeta={
      mtime_ns:latest.mtime_ns||0,
      size:latest.size||0,
      sha256:latest.sha256||''
    }
    editorFileDiskMetaRef.current={
      ...editorFileDiskMetaRef.current,
      [normalized]:latestMeta
    }
    setEditorFileDiskMeta(prev=>({
      ...prev,
      [normalized]:latestMeta
    }))
    setEditorExternalState(prev=>{
      const copy={...prev}; delete copy[normalized]; return copy
    })
    if(activate||selectedEditorFileRef.current===editorPath){
      setSelected(editorPath)
      setFileTreeSelected(editorPath)
      setFileTreeSelectedPaths([editorPath])
      setCode(latestContent)
      setFileSaveStatus('외부 파일 로드 완료')
    }
    return latest
  }

  const openExternalChangePrompt=(editorPath,{mode='external_notice',pendingContent=null}={})=>{
    const normalized=normalizeProjectRelativePath(editorPath)
    setExternalChangeConfirm({
      path:editorPath,
      normalized,
      mode,
      pendingContent,
      loading:false,
      loadingAction:'',
      error:''
    })
  }

  const handleExternalChangeDecision=async(action)=>{
    const pending=externalChangeConfirm
    if(!pending||pending.loading) return

    if(action==='cancel'){
      setExternalChangeConfirm(null)
      return
    }

    setExternalChangeConfirm(prev=>prev?{
      ...prev,
      loading:true,
      loadingAction:action,
      error:''
    }:prev)

    try{
      if(action==='load_external'){
        await reloadExternalEditorFile(pending.path,{activate:true})
        setExternalFileNotifications(prev=>prev.filter(item=>item.path!==pending.normalized))
        setExternalChangeConfirm(null)
        return
      }

      if(action==='force_save'){
        const currentContent=
          pending.pendingContent
          ?? editorFileContents[pending.path]
          ?? (selectedEditorFileRef.current===pending.path?code:'')
          ?? ''

        const result=await writeEditorFile(
          pending.path,
          currentContent,
          {force:true,promptOnConflict:false}
        )

        setTerminal(prev=>
          (prev||'')
          + `\n[외부 변경 무시 저장 완료] ${result?.path||result?.fullPath||pending.path}`
          + (result?.bytes!=null?` (${result.bytes} bytes)`:'')
          + '\n'
        )
        setFileSaveStatus('저장 완료')
        setExternalFileNotifications(prev=>prev.filter(item=>item.path!==pending.normalized))
        setExternalChangeConfirm(null)
        return
      }

      setExternalChangeConfirm(null)
    }catch(e){
      setFileSaveStatus('저장 실패')
      setExternalChangeConfirm(prev=>prev?{
        ...prev,
        loading:false,
        loadingAction:'',
        error:String(e)
      }:prev)
    }
  }

  const handleExternalNotificationClick=(item)=>{
    if(!item?.path) return
    setExternalNotificationOpen(false)
    const normalized=normalizeProjectRelativePath(item.path)
    const editorPath=(openEditorFilesRef.current||[]).find(
      path=>normalizeProjectRelativePath(path)===normalized
    )||item.path
    if(openEditorFilesRef.current?.includes(editorPath)){
      activateEditorFile(editorPath)
    }
    if(item.status==='modified_conflict'){
      openExternalChangePrompt(editorPath)
      return
    }
    setExternalFileNotifications(prev=>prev.filter(row=>row.id!==item.id))
  }

  const handleExternalNotificationIgnore=(item)=>{
    if(!item?.path) return
    const normalized=normalizeProjectRelativePath(item.path)

    // Ignore means: keep the current AgentStudio editor buffer and dismiss
    // this notification. Do NOT advance the disk baseline, because the
    // external file is still different. A later save will therefore use the
    // v5.207 save-conflict dialog and let the user explicitly choose whether
    // to load external content or force-save the AgentStudio content.
    if(item.status==='modified_conflict'){
      setEditorExternalState(prev=>({
        ...prev,
        [normalized]:'modified_ignored'
      }))
      if(selectedEditorFileRef.current&&
        normalizeProjectRelativePath(selectedEditorFileRef.current)===normalized){
        setFileSaveStatus('외부 변경 무시')
      }
    }

    setExternalFileNotifications(prev=>prev.filter(row=>row.id!==item.id))
  }

  // v5.333: detect external file changes with native OS notifications.
  //
  // Previous versions called /files/snapshot every 1.5 seconds. That walked the
  // project tree even while the user was idle and Uvicorn also wrote an access
  // log line for every poll. On HDD systems this was enough to keep the disk
  // awake continuously. The watcher below is event-driven: while nothing
  // changes there is no project scan, no open-file hashing, and no polling log.
  const currentFileWatchRoot=resolveWorkspaceRoot(fileTreeRootRef.current||root||'')
  useEffect(()=>{
    fileWatchBusyRef.current=false

    const watchRoot=String(currentFileWatchRoot||'').trim()
    if(!watchRoot||screen!=='WORKSPACE') return

    let cancelled=false
    let socket=null
    let reconnectTimer=null
    let reconnectDelay=1000
    let reconcileTimer=null
    let connectedOnce=false
    const queuedChanges=new Map()

    const queueChangeRows=(rows=[])=>{
      const priority={modified:1,added:2,deleted:3}
      for(const row of Array.isArray(rows)?rows:[]){
        const path=normalizeProjectRelativePath(row?.path)
        const kind=String(row?.kind||'modified').toLowerCase()
        if(!path||!priority[kind]) continue
        const before=queuedChanges.get(path)
        if(!before||priority[kind]>=priority[before]) queuedChanges.set(path,kind)
      }

      if(reconcileTimer) clearTimeout(reconcileTimer)
      reconcileTimer=setTimeout(()=>{
        reconcileTimer=null
        void drainQueuedChanges()
      },180)
    }

    const reconcileOpenFiles=async(changedRows,{checkAllOpen=false}={})=>{
      const openMap=new Map(
        (openEditorFilesRef.current||[]).map(path=>[normalizeProjectRelativePath(path),path])
      )
      if(!openMap.size) return

      const explicitDeleted=new Set()
      const candidateKeys=new Set()

      if(checkAllOpen){
        for(const key of openMap.keys()) candidateKeys.add(key)
      }

      for(const row of changedRows||[]){
        const key=normalizeProjectRelativePath(row?.path)
        if(!key||!openMap.has(key)) continue
        candidateKeys.add(key)
        if(row?.kind==='deleted') explicitDeleted.add(key)
      }

      if(!candidateKeys.size) return

      let hashStateFiles={}
      try{
        const workspaceRoot=resolveWorkspaceRoot(watchRoot)||watchRoot
        const hashState=await api('/files/hash-state',{
          method:'POST',
          body:JSON.stringify({
            root:workspaceRoot,
            relative_paths:[...candidateKeys]
          })
        })
        hashStateFiles=hashState?.files||{}
      }catch(e){
        console.warn('열린 파일 SHA-256 상태 조회 실패',e)
        return
      }

      const deletedKeys=new Set(explicitDeleted)
      const modifiedKeys=new Set()

      for(const key of candidateKeys){
        const latest=hashStateFiles[key]
        const baseline=editorFileDiskMetaRef.current?.[key]

        if(!latest?.exists){
          deletedKeys.add(key)
          continue
        }

        // A delete+create rename/save sequence can report a transient delete.
        // The authoritative hash state wins when the file already exists again.
        deletedKeys.delete(key)

        const latestSha=String(latest.sha256||'')
        const baselineSha=String(baseline?.sha256||'')

        if(baselineSha&&latestSha){
          if(latestSha!==baselineSha){
            modifiedKeys.add(key)
          }else if(
            baseline?.mtime_ns!==latest.mtime_ns
            || baseline?.size!==latest.size
          ){
            const refreshed={
              mtime_ns:latest.mtime_ns||0,
              size:latest.size||0,
              sha256:latestSha
            }
            editorFileDiskMetaRef.current={
              ...editorFileDiskMetaRef.current,
              [key]:refreshed
            }
            setEditorFileDiskMeta(prev=>({...prev,[key]:refreshed}))
          }
          continue
        }

        if(latestSha){
          // Older/binary tabs may not have a SHA baseline yet. Initialize it
          // once; subsequent native events are hash-authoritative.
          const initialized={
            mtime_ns:latest.mtime_ns||baseline?.mtime_ns||0,
            size:latest.size||baseline?.size||0,
            sha256:latestSha
          }
          editorFileDiskMetaRef.current={
            ...editorFileDiskMetaRef.current,
            [key]:initialized
          }
          setEditorFileDiskMeta(prev=>({...prev,[key]:initialized}))
          continue
        }

        if(
          baseline
          &&(
            baseline.mtime_ns!==latest.mtime_ns
            || baseline.size!==latest.size
          )
        ){
          modifiedKeys.add(key)
        }
      }

      for(const key of deletedKeys){
        const editorPath=openMap.get(key)
        if(!editorPath) continue
        setEditorExternalState(prev=>({...prev,[key]:'deleted'}))
        if(
          selectedEditorFileRef.current
          && normalizeProjectRelativePath(selectedEditorFileRef.current)===key
        ){
          setFileSaveStatus('외부 삭제 감지')
        }
        addExternalFileNotification(editorPath,'deleted')
      }

      for(const key of modifiedKeys){
        const editorPath=openMap.get(key)
        if(!editorPath) continue
        const isCurrent=(
          selectedEditorFileRef.current
          && normalizeProjectRelativePath(selectedEditorFileRef.current)===key
        )
        const isDirty=!!editorFileDirtyRef.current?.[editorPath]

        if(isDirty){
          setEditorExternalState(prev=>({...prev,[key]:'modified_conflict'}))
          if(isCurrent){
            setFileSaveStatus('외부 변경 충돌')
            openExternalChangePrompt(editorPath)
          }
          addExternalFileNotification(editorPath,'modified_conflict')
          continue
        }

        try{
          await reloadExternalEditorFile(editorPath,{activate:isCurrent})
          if(cancelled) return
          if(isCurrent) setFileSaveStatus('외부 변경 자동 반영')
          addExternalFileNotification(editorPath,'modified_reloaded')
        }catch(e){
          console.error('외부 변경 파일 다시 읽기 실패',editorPath,e)
        }
      }
    }

    const drainQueuedChanges=async()=>{
      if(cancelled) return
      if(fileWatchBusyRef.current){
        if(!reconcileTimer){
          reconcileTimer=setTimeout(()=>{
            reconcileTimer=null
            void drainQueuedChanges()
          },120)
        }
        return
      }

      const rows=[...queuedChanges.entries()].map(([path,kind])=>({path,kind}))
      queuedChanges.clear()
      if(!rows.length) return

      fileWatchBusyRef.current=true
      try{
        if(rows.some(row=>row.kind==='added'||row.kind==='deleted')){
          try{ await loadFiles(watchRoot) }catch(_){ }
        }
        await reconcileOpenFiles(rows)
      }finally{
        fileWatchBusyRef.current=false
        if(queuedChanges.size&&!reconcileTimer){
          reconcileTimer=setTimeout(()=>{
            reconcileTimer=null
            void drainQueuedChanges()
          },120)
        }
      }
    }

    const reconcileAfterReconnect=async()=>{
      if(cancelled||fileWatchBusyRef.current) return
      fileWatchBusyRef.current=true
      try{
        // A reconnect is rare. One tree refresh + opened-file hash check makes
        // changes that happened during the disconnected window visible without
        // returning to continuous polling.
        try{ await loadFiles(watchRoot) }catch(_){ }
        await reconcileOpenFiles([],{checkAllOpen:true})
      }finally{
        fileWatchBusyRef.current=false
      }
    }

    const connectWatcher=()=>{
      if(cancelled) return
      const apiBase=String(runtimeInfo().apiBase||'')
      const wsBase=apiBase.replace(/^http:/,'ws:').replace(/^https:/,'wss:')
      const wsUrl=`${wsBase}/files/watch?root=${encodeURIComponent(watchRoot)}`
      const ws=new WebSocket(wsUrl)
      socket=ws

      ws.onmessage=(event)=>{
        if(cancelled||socket!==ws) return
        try{
          const payload=JSON.parse(event.data)
          if(payload?.type==='ready'){
            reconnectDelay=1000
            if(connectedOnce) void reconcileAfterReconnect()
            connectedOnce=true
            return
          }
          if(payload?.type==='changes'){
            queueChangeRows(payload.changes||[])
            return
          }
          if(payload?.type==='error'){
            console.warn('프로젝트 파일 감시 서버 오류',payload?.message||payload)
          }
        }catch(e){
          console.warn('프로젝트 파일 감시 이벤트 해석 실패',e)
        }
      }

      ws.onerror=()=>{
        try{ ws.close() }catch(_){ }
      }

      ws.onclose=()=>{
        if(cancelled||socket!==ws) return
        socket=null
        reconnectTimer=setTimeout(connectWatcher,reconnectDelay)
        reconnectDelay=Math.min(reconnectDelay*2,10000)
      }
    }

    connectWatcher()

    return()=>{
      cancelled=true
      queuedChanges.clear()
      if(reconcileTimer) clearTimeout(reconcileTimer)
      if(reconnectTimer) clearTimeout(reconnectTimer)
      if(socket){
        try{ socket.close() }catch(_){ }
      }
      socket=null
      fileWatchBusyRef.current=false
    }
  },[currentFileWatchRoot,screen])

  const createNewAgentProject=async()=>{
    const createContextEpoch=projectContextEpochRef.current
    if(!newAgentName.trim()){
      setNewAgentCreateResult({ok:false,message:'에이전트 이름을 입력하세요.'})
      return
    }
    if(!newAgentProjectRoot.trim()){
      setNewAgentCreateResult({ok:false,message:'프로젝트 경로를 입력하세요.'})
      return
    }
    try{
      const r=await api('/projects/create-agent',{
        method:'POST',
        body:JSON.stringify({
          name:newAgentName,
          project_root:newAgentProjectRoot,
          cache_path:newAgentCachePath,
          temp_path:newAgentTempPath,
          output_path:newAgentOutputPath,
          venv_path:newAgentVenvPath,
          models_path:newAgentModelsPath
        })
      })
      if(projectContextEpochRef.current!==createContextEpoch) return
      setNewAgentCreateResult(r)
      if(r.ok){
        setSelectedProjectId(r.project_id||null)
        const createdRoot=r.project_root||newAgentProjectRoot
        setRoot(createdRoot)
        setProjectLoadMessage(`프로젝트 #${r.project_id||''} ${r.name||newAgentName} 생성 완료`)
        setScreen('WORKSPACE')
        setTimeout(()=>loadFiles(createdRoot),100)
        setTimeout(()=>refreshAdaptiveProjectAnalysis(createdRoot,workflowReq||newAgentName),180)
      }
    }catch(e){
      setNewAgentCreateResult({ok:false,message:String(e)})
    }
  }


  const openProjectList=async()=>{
    setProjectListOpen(true)
    setProjectListLoading(true)
    setProjectLoadMessage('')
    try{
      const rows=await api('/projects')
      setProjectList(Array.isArray(rows)?rows:[])
    }catch(e){
      setProjectList([])
      setProjectLoadMessage('프로젝트 목록 조회 실패: '+String(e))
    }finally{
      setProjectListLoading(false)
    }
  }

  const refreshAdaptiveProjectAnalysis=async(projectRoot,requestText='',expectedContextEpoch=null)=>{
    const targetRoot=String(projectRoot||'').trim()
    if(!targetRoot) return null
    const requestContextEpoch=Number.isInteger(expectedContextEpoch)
      ? expectedContextEpoch
      : projectContextEpochRef.current
    try{
      const adaptive=await api('/project/adaptive-report',{
        method:'POST',
        body:JSON.stringify({
          project_root:targetRoot,
          request:String(requestText||workflowReq||'프로젝트 성격에 맞는 Workflow, 분석 리포트, Architecture를 구성')
        })
      })
      if(adaptive?.ok){
        // A project load/analysis can finish after the user has already clicked
        // '+ 신규 Agent 만들기'.  Ignore that stale response completely.
        if(projectContextEpochRef.current!==requestContextEpoch) return null
        setLoadedProjectAnalysis(prev=>({
          ...(prev||{}),
          ...adaptive,
          adaptive_report:adaptive
        }))
        return adaptive
      }
    }catch(error){
      console.warn('Project adaptive analysis failed:',error)
    }
    return null
  }

  const loadProject=async(projectId)=>{
    const loadContextEpoch=++projectContextEpochRef.current
    // Do not let the previous project's tree root leak into file operations
    // while the new project metadata is loading.
    fileTreeRootRef.current=''
    setProjectLoadMessage('프로젝트를 불러오는 중...')
    setProjectLoadProgress({
      active:true,
      percent:5,
      message:'프로젝트 정보를 불러오는 중...',
      failed:false
    })

    try{
      const p=await api(`/projects/${projectId}`)
      if(projectContextEpochRef.current!==loadContextEpoch) return

      if(!p.ok){
        const msg=p.message||'프로젝트를 불러오지 못했습니다.'
        setProjectLoadMessage(msg)
        setProjectLoadProgress({
          active:true,
          percent:100,
          message:msg,
          failed:true
        })
        return
      }

      setProjectLoadProgress({
        active:true,
        percent:20,
        message:'프로젝트 경로를 적용하는 중...',
        failed:false
      })

      const projectRoot=p.project_root||root||''

      // v5.356: 다른 프로젝트의 Agent Factory/Workflow Snapshot이 새 프로젝트에
      // 우선 적용되지 않도록 프로젝트 전환 시 실행/설계 상태를 먼저 비웁니다.
      setWorkflow(null)
      setTargetWorkflowPreview(null)
      setPreviousTargetWorkflowPreview(null)
      setTargetWorkflowQuality(null)
      setDevelopmentFinalStatus(null)
      setLoadedProjectAnalysis(null)
      setAnalysis(null)
      setDbErdReport(null)
      setLiveDatabasePreview(null)
      setWorkflowReq(p.description||'')

      setSelectedProjectId(p.id)
      setNewAgentName(p.name||'')
      setNewAgentProjectRoot(projectRoot)
      setNewAgentCachePath(p.cache_path||'')
      setNewAgentTempPath(p.temp_path||'')
      setNewAgentOutputPath(p.output_path||'')
      setNewAgentVenvPath(p.venv_path||'')
      setNewAgentModelsPath(p.models_path||'')
      setLoadedProjectAnalysis(p.analysis||null)
      setRoot(projectRoot)

      setProjectLoadProgress({
        active:true,
        percent:40,
        message:'프로젝트 파일과 폴더를 불러오는 중...',
        failed:false
      })

      // setRoot()의 비동기 state 반영을 기다리지 않고
      // API에서 받은 projectRoot를 직접 사용한다.
      await loadFiles(projectRoot)
      setProjectLoadProgress({
        active:true,
        percent:55,
        message:'프로젝트 성격과 Workflow / Architecture를 분석하는 중...',
        failed:false
      })
      await refreshAdaptiveProjectAnalysis(projectRoot,p.description||p.name||'',loadContextEpoch)
      if(projectContextEpochRef.current!==loadContextEpoch) return
      await activateProjectTerminal(p)
      await loadGitInfo(projectRoot)

      setProjectLoadProgress({
        active:true,
        percent:70,
        message:'프로젝트 상태를 갱신하는 중...',
        failed:false
      })

      setNewAgentCreateResult({
        ok:true,
        message:'프로젝트를 불러왔습니다.',
        project_id:p.id,
        project_root:projectRoot,
        cache_path:p.cache_path,
        temp_path:p.temp_path,
        output_path:p.output_path,
        venv_path:p.venv_path,
        models_path:p.models_path
      })

      await refreshProjectList()

      setProjectLoadProgress({
        active:true,
        percent:90,
        message:'작업공간을 준비하는 중...',
        failed:false
      })

      setProjectLoadMessage(`프로젝트 #${p.id} ${p.name} 불러오기 완료`)
      setProjectListOpen(false)
      setWorkspaceTab('CODE')
      setWorkflowView('TARGET')
      setScreen('WORKSPACE')

      setProjectLoadProgress({
        active:true,
        percent:100,
        message:'프로젝트 로딩 완료',
        failed:false
      })

      setTimeout(()=>{
        setProjectLoadProgress({
          active:false,
          percent:0,
          message:'',
          failed:false
        })
      },800)
    }catch(e){
      const msg='프로젝트 불러오기 실패: '+String(e)
      setProjectLoadMessage(msg)
      setProjectLoadProgress({
        active:true,
        percent:100,
        message:msg,
        failed:true
      })
      setTimeout(()=>{
        setProjectLoadProgress(prev=>({...prev,active:false}))
      },3000)
    }
  }


  const startNewProject=()=>{
    // v5.363: this is a hard project-context boundary, not just a navigation action.
    // Invalidate every pending load/adaptive-analysis request before clearing state.
    projectContextEpochRef.current+=1
    setAgentBuildMessage('')
    setWorkspaceTab('DESIGN')
    setWorkflowView('TARGET')
    setScreen('WORKSPACE')
    setInput('')
    setNewAgentCreateResult(null)
    setSelectedProjectId(null)
    setGitInfo(null)

    // Clear ALL project-derived analysis/design state.  In v5.360 these values
    // survived startNewProject(), so Workflow/Report/Architecture could fall back
    // to the previously loaded project's adaptive report (e.g. MINI_PRO).
    setLoadedProjectAnalysis(null)
    setExternalProjectAnalysis(null)
    setAnalysis(null)
    setDbErdReport(null)
    setDbErdError('')
    setLiveDatabasePreview(null)
    setLiveDatabasePreviewError('')
    setCodingStyleReport(null)
    setReportGeneratedAt('')
    setPptExportError('')
    setDevelopmentFinalStatus(null)
    setDevelopmentProgress({active:false,percent:0,stage:'대기',detail:'',startedAt:null,elapsedSeconds:0,events:[]})
    setWorkflowProgress({active:false,percent:0,stage:'대기',detail:'',startedAt:null})
    setTargetWorkflowError('')
    setWorkflowReq('')
    setUiLayoutConfig(null)
    setUiLayoutGalleryOpen(false)
    setConfirmedInterviewRequirements({})
    setDesignProjectId(null)
    setDesignProjectSavedAt('')
    setDesignProjectVersion(1)
    setDesignFeatureRegistry([])

    // '신규 Agent 만들기'는 기존 프로젝트/설계에서 사용하던 경로를 이어받지 않습니다.
    // 프로젝트 경로 input은 항상 빈 value로 시작하고 사용자가 직접 입력하거나 선택합니다.
    setNewAgentName('')
    setNewAgentProjectRoot('')
    setRoot('')
    workspaceRootRef.current=''
    fileTreeRootRef.current=''
    editorFileRootRef.current={}

    // 경로를 새로 선택해도 동일 경로의 과거 Draft를 자동 복원하지 않습니다.
    // Draft가 있으면 우측에서 사용자가 직접 이어서 불러올 수 있습니다.
    setAgentBuildStage('REQUIREMENTS')
    setWorkflow(null)
    setTargetWorkflowPreview(null)
    setPreviousTargetWorkflowPreview(null)
    setTargetWorkflowQuality(null)
    setBuilderStarted(false)
    setInterviewAttachments([])
    setInterviewAttachmentMemory('')
    setInterviewAttachmentSummary('')
    setInterviewAttachmentSummaryFiles([])
    setInterviewAttachmentRequirements([])
    setInterviewAttachmentRequirementCoverage({})
    setInterviewAttachmentSummaryBusy(false)
    setInterviewAttachmentSummaryError('')
    interviewAttachmentSummaryRunRef.current=''
    setRequirementManualOverrides({})
    setUiLayoutConfig(null)
    setUiLayoutGalleryOpen(false)
    setRequirementRedefineId('')
    setRequirementRedefineText('')
    setRequirementDraftCandidate(null)
    setRequirementDraftDecisionPending(false)
    setRequirementDraftRestored(false)
    setRequirementDraftSavedAt('')
    setRestoredBuildResume(null)
    requirementCheckpointSignatureRef.current=''
    setInterviewAttachmentAnalysis({busy:false,ready:true,overallProgress:100,failedFiles:0,successfulFiles:0,files:[]})
    setChat([{
      role:'assistant',
      content:'어떤 AI Agent + MCP 프로그램을 만들고 싶으신가요? 먼저 프로그램의 목적을 한 문장으로 말씀해 주세요.'
    }])

    loadDefaultPaths()
  }

  useEffect(()=>{ openEditorFilesRef.current=openEditorFiles },[openEditorFiles])
  useEffect(()=>{ editorFileContentsRef.current=editorFileContents },[editorFileContents])
  useEffect(()=>{ editorFileDirtyRef.current=editorFileDirty },[editorFileDirty])
  useEffect(()=>{ editorFileDiskMetaRef.current=editorFileDiskMeta },[editorFileDiskMeta])
  useEffect(()=>{ selectedEditorFileRef.current=selected },[selected])

  useEffect(()=>{
    setFileTreeSelectedPaths([])
    fileTreeSelectionAnchorRef.current=''
    setFileTreeContextMenu(null)
    setExternalNotificationOpen(false)
    setExternalFileNotifications([])
  },[root])

  const writeEditorFile=async(relativePath,content,{force=false,promptOnConflict=true}={})=>{
    const workspaceRoot=resolveWorkspaceRoot(
      editorFileRootRef.current?.[relativePath]||fileTreeRootRef.current||''
    )
    if(!workspaceRoot || !relativePath){
      throw new Error('프로젝트와 파일을 먼저 선택하세요.')
    }

    const normalizedRoot=String(workspaceRoot).replace(/[\\/]+$/,'')
    const normalizedSelected=String(relativePath).replace(/^[\\/]+/,'')
    const fullPath=`${normalizedRoot}\\${normalizedSelected.replace(/\//g,'\\')}`

    const metaKey=normalizeProjectRelativePath(relativePath)
    const baseline=editorFileDiskMetaRef.current?.[metaKey]
    if(editorExternalState[metaKey]==='deleted'){
      throw new Error('파일이 AgentStudio 밖에서 삭제되었습니다. 프로젝트 트리를 확인한 뒤 새 파일로 다시 생성하거나 탭을 닫아주세요.')
    }

    let result
    try{
      result=await api('/file/write',{
        method:'POST',
        body:JSON.stringify({
          path:fullPath,
          content:content??'',
          expected_mtime_ns:baseline?.mtime_ns||null,
          expected_sha256:baseline?.sha256||null,
          force:!!force
        })
      })
    }catch(e){
      if(e?.status===409){
        setEditorExternalState(prev=>({...prev,[metaKey]:'modified_conflict'}))
        if(promptOnConflict&&selectedEditorFileRef.current===relativePath){
          openExternalChangePrompt(relativePath,{
            mode:'save_conflict',
            pendingContent:content??''
          })
        }else if(selectedEditorFileRef.current!==relativePath){
          addExternalFileNotification(relativePath,'modified_conflict')
        }
      }
      throw e
    }

    if(result?.mtime_ns){
      const nextMeta={
        mtime_ns:result.mtime_ns,
        size:result.size??result.bytes??0,
        sha256:result.sha256||''
      }
      editorFileDiskMetaRef.current={
        ...editorFileDiskMetaRef.current,
        [metaKey]:nextMeta
      }
      setEditorFileDiskMeta(prev=>({...prev,[metaKey]:nextMeta}))
      setEditorExternalState(prev=>{
        const next={...prev}; delete next[metaKey]; return next
      })
      if(projectFileSnapshotRef.current?.files){
        projectFileSnapshotRef.current={
          ...projectFileSnapshotRef.current,
          files:{...projectFileSnapshotRef.current.files,[metaKey]:nextMeta}
        }
      }
    }

    setEditorFileContents(prev=>({
      ...prev,
      [relativePath]:content??''
    }))

    setEditorFileDirty(prev=>({
      ...prev,
      [relativePath]:false
    }))
    editorFileRootRef.current[relativePath]=workspaceRoot

    return {
      ...result,
      fullPath
    }
  }

  const saveFile=async()=>{
    // v5.372: Ctrl+S saves the actual active editor file even when the top
    // project selector is empty. Notebook/file-tree tabs retain their own root.
    const selectedPath=normalizeProjectRelativePath(
      selectedEditorFileRef.current||selected||''
    )

    const hasKnownContent=
      Object.prototype.hasOwnProperty.call(editorFileContentsRef.current||{},selectedPath)
      ||Object.prototype.hasOwnProperty.call(editorFileContents,selectedPath)
    if(selectedPath&&(fileLoadingPath===selectedPath||(!isBinaryPreviewFile(selectedPath)&&!hasKnownContent))){
      setFileSaveStatus('저장 대기 · 파일 로딩 중')
      setTerminal(prev=>(prev||'')+'\n[저장 대기] 파일 내용을 디스크에서 불러오는 중에는 저장하지 않습니다. 로드 완료 후 다시 저장하세요.\n')
      return
    }
    if(editorLoadErrors[selectedPath]){
      setFileSaveStatus('저장 차단 · 파일 로드 실패')
      setTerminal(prev=>(prev||'')+'\n[저장 차단] 파일 로드가 실패한 탭은 디스크에 저장하지 않습니다. 먼저 다시 불러오세요.\n')
      return
    }
    if(isBinaryPreviewFile(selectedPath)){
      const presentation=isPresentationFile(selectedPath)
      setFileSaveStatus(presentation?'PowerPoint 읽기 전용':'PDF 읽기 전용')
      setTerminal(prev=>(prev||'')+`\n[${presentation?'PowerPoint':'PDF'}] 바이너리 문서는 미리보기 전용이며 텍스트 저장을 수행하지 않습니다.\n`)
      return
    }
    setFileSaveStatus('저장 중')
    const saveRoot=resolveWorkspaceRoot(
      editorFileRootRef.current?.[selectedPath]
      ||fileTreeRootRef.current
      ||workspaceRootRef.current
      ||''
    )
    if(!saveRoot || !selectedPath){
      setFileSaveStatus('저장 실패')
      setTerminal(prev=>(prev||'')+'\n[저장 실패] 현재 편집 파일의 프로젝트 경로를 확인할 수 없습니다. 프로젝트 파일 트리에서 파일을 다시 열어 주세요.\n')
      return
    }

    try{
      const currentContent=
        editorFileContentsRef.current?.[selectedPath]
        ?? editorFileContents[selectedPath]
        ?? (selectedPath===selected?code:'')
        ?? ''

      const result=await writeEditorFile(
        selectedPath,
        currentContent
      )

      editorFileContentsRef.current={
        ...editorFileContentsRef.current,
        [selectedPath]:currentContent
      }

      setTerminal(prev=>
        (prev||'')
        + `\n[저장 완료 · Ctrl+S] ${result?.path||result.fullPath}`
        + (result?.bytes!=null?` (${result.bytes} bytes)`:'')
        + '\n'
      )

      setFileSaveStatus('저장 완료')
    }catch(e){
      if(e?.status===409){
        setFileSaveStatus('외부 변경 충돌')
        setTerminal(prev=>(prev||'')+'\n[저장 보류] 외부 파일 변경이 감지되어 사용자 선택을 기다립니다.\n')
      }else{
        setFileSaveStatus('저장 실패')
        setTerminal(prev=>(prev||'')+'\n[저장 실패] '+String(e)+'\n')
      }
    }

    if(focusOwnerRef.current==='editor'){
      setTimeout(()=>{
        try{ editorInstanceRef.current?.focus() }catch{}
      },0)
    }
  }

  const saveDirtyEditorPaths=async(paths,{label='모두 저장'}={})=>{
    const dirtyPaths=(paths||[]).filter(
      path=>!!editorFileDirty[path]
    )

    if(!dirtyPaths.length){
      return {saved:[],failed:[]}
    }

    setFileSaveStatus('저장 중')

    const saved=[]
    const failed=[]

    for(const path of dirtyPaths){
      const content=
        editorFileContentsRef.current?.[path]
        ?? (path===selected
          ? (editorFileContents[path] ?? code ?? '')
          : (editorFileContents[path] ?? ''))

      try{
        const result=await writeEditorFile(path,content)
        saved.push(result?.path||result.fullPath||path)
      }catch(e){
        failed.push({path,error:String(e)})
      }
    }

    setTerminal(prev=>{
      let text=(prev||'')
        + `\n[${label}] ${saved.length}개 파일 저장 완료`

      if(failed.length){
        text+=` / ${failed.length}개 실패`
        for(const item of failed){
          text+=`\n  - ${item.path}: ${item.error}`
        }
      }

      return text+'\n'
    })

    setFileSaveStatus(
      failed.length?'저장 실패':'저장 완료'
    )

    return {saved,failed}
  }

  const saveAllDirtyFiles=async()=>{
    if(!resolveWorkspaceRoot(fileTreeRootRef.current||workspaceRootRef.current||'')){
      setFileSaveStatus('저장 실패')
      setTerminal(prev=>(prev||'')+'\n[모두 저장 실패] 프로젝트를 먼저 선택하세요.\n')
      return
    }

    const dirtyPaths=openEditorFiles.filter(
      path=>!!editorFileDirty[path]
    )

    if(!dirtyPaths.length){
      setFileSaveStatus('저장 완료')
      setTerminal(prev=>(prev||'')+'\n[모두 저장] 수정된 열린 파일이 없습니다.\n')
      return
    }

    await saveDirtyEditorPaths(dirtyPaths,{label:'모두 저장'})

    if(focusOwnerRef.current==='editor'){
      setTimeout(()=>{
        try{ editorInstanceRef.current?.focus() }catch{}
      },0)
    }
  }

  useEffect(()=>{
    const handleEditorSaveShortcut=(e)=>{
      const isSave=
        (e.ctrlKey||e.metaKey)
        && String(e.key).toLowerCase()==='s'

      if(!isSave) return

      // v5.246: AgentStudio 내부 어디에 포커스가 있든 브라우저의
      // "웹페이지 저장(Ctrl+S)" 기본 동작이 먼저 실행되지 않게 합니다.
      // Notebook Cell, AI 변경 제안, LLM 입력창, 파일 트리 등에서도
      // 동일하게 적용됩니다.
      e.preventDefault()
      e.stopPropagation()

      // 키를 오래 누를 때 같은 파일을 중복 저장하지 않습니다.
      if(e.repeat) return

      // Ctrl+Shift+S: 코드 작업공간에서 수정된 모든 열린 파일 저장.
      // 상단 Project selector의 root 값에 의존하지 않습니다.
      if(e.shiftKey){
        if(
          screen==='WORKSPACE'
          && workspaceTab==='CODE'
        ){
          saveAllDirtyFiles()
        }
        return
      }

      // Ctrl+S: 현재 열린 파일 저장. 상단 프로젝트 선택이 비어 있어도
      // editor/file-tree root가 있으면 Notebook/Source/SQL을 저장합니다.
      const shortcutPath=normalizeProjectRelativePath(
        selectedEditorFileRef.current||selected||''
      )
      if(
        screen==='WORKSPACE'
        && workspaceTab==='CODE'
        && shortcutPath
      ){
        saveFile()
      }
    }

    window.addEventListener(
      'keydown',
      handleEditorSaveShortcut,
      true
    )

    return()=>{
      window.removeEventListener(
        'keydown',
        handleEditorSaveShortcut,
        true
      )
    }
  },[
    selected,
    code,
    root,
    screen,
    workspaceTab,
    openEditorFiles,
    editorFileContents,
    editorFileDirty
  ])



  useEffect(()=>{
    if(
      screen!=='WORKSPACE'
      || workspaceTab!=='CODE'
      || isSqlFile
      || !activeTerminalId
    ){
      return
    }

    const restorePersistentTerminal=()=>{
      const activeContainer=
        xtermContainersRef.current[activeTerminalId]
      const activeRect=
        activeContainer?.getBoundingClientRect?.()

      if(
        !activeRect
        || activeRect.width<120
        || activeRect.height<80
      ){
        return false
      }

      try{
        for(const terminal of terminalSessions){
          const id=terminal.id
          const container=xtermContainersRef.current[id]
          const rect=container?.getBoundingClientRect?.()

          if(
            !rect
            || rect.width<120
            || rect.height<80
          ){
            continue
          }

          const term=xtermInstancesRef.current[id]
          fitTerminalViewport(id)
          term?.refresh(
            0,
            Math.max(0,(term?.rows||1)-1)
          )
        }

        xtermInstancesRef.current[
          activeTerminalId
        ]?.scrollToBottom()
      }catch{}

      try{
        editorInstanceRef.current?.layout()
      }catch{}

      return true
    }

    let observer=null
    const activeContainer=
      xtermContainersRef.current[activeTerminalId]

    if(
      activeContainer
      && typeof ResizeObserver!=='undefined'
    ){
      observer=new ResizeObserver(()=>{
        if(
          screen==='WORKSPACE'
          && workspaceTab==='CODE'
        ){
          requestAnimationFrame(
            restorePersistentTerminal
          )
        }
      })
      observer.observe(activeContainer)
    }

    const timers=[
      40,
      120,
      260,
      500,
      900,
    ].map(delay=>
      setTimeout(()=>{
        requestAnimationFrame(
          restorePersistentTerminal
        )
      },delay)
    )

    return()=>{
      observer?.disconnect()
      timers.forEach(clearTimeout)
    }
  },[screen,workspaceTab,activeTerminalId,terminalSessions.length,isSqlFile,selected])



  // v5.231: SQL Workspace에서는 terminal-pane이 display:none 상태가 됩니다.
  // SQL 파일 -> 일반 코드 파일로 돌아올 때 xterm DOM은 그대로 유지되지만
  // display:none 동안의 0px geometry를 기준으로 cols/rows가 stale해질 수 있습니다.
  // 파일 종류 전환 직후 visible geometry가 안정된 다음 active terminal을 다시 fit/refresh합니다.
  useEffect(()=>{
    if(
      screen!=='WORKSPACE'
      || workspaceTab!=='CODE'
      || isSqlFile
      || !activeTerminalId
    ) return

    let cancelled=false
    const restoreVisibleTerminal=()=>{
      if(cancelled) return
      const container=xtermContainersRef.current[activeTerminalId]
      const term=xtermInstancesRef.current[activeTerminalId]
      const rect=container?.getBoundingClientRect?.()
      if(!rect||rect.width<120||rect.height<80) return

      fitTerminalViewport(activeTerminalId)
      try{
        term?.refresh(0,Math.max(0,(term?.rows||1)-1))
        term?.scrollToBottom()
      }catch{}
    }

    let raf2=0
    const raf1=requestAnimationFrame(()=>{
      raf2=requestAnimationFrame(restoreVisibleTerminal)
    })
    const timers=[60,180,420].map(delay=>setTimeout(restoreVisibleTerminal,delay))

    return()=>{
      cancelled=true
      cancelAnimationFrame(raf1)
      if(raf2) cancelAnimationFrame(raf2)
      timers.forEach(clearTimeout)
    }
  },[screen,workspaceTab,isSqlFile,selected,activeTerminalId])



  const refreshMcp=async()=>{
    try{
      const servers=await api('/mcp/servers')
      setMcpServers(Array.isArray(servers)?servers:(servers?.servers||[]))
      const tools=await api('/mcp/tools')
      setMcpTools(Array.isArray(tools)?tools:(tools?.tools||[]))
    }catch(e){
      console.error('MCP 목록 새로고침 실패',e)
    }
  }

  const openMcpAddDialog=()=>{
    setMcpAddError('')
    setMcpAddOpen(true)
    setScreen('MCP')
    refreshMcp()
  }

  const closeMcpAddDialog=()=>{
    if(mcpAddBusy) return
    setMcpAddOpen(false)
    setMcpAddError('')
  }

  const submitMcpServer=async()=>{
    const name=String(mcpAddForm.name||'').trim()
    const endpoint=String(mcpAddForm.endpoint||'').trim()

    if(!name){
      setMcpAddError('MCP 서버 이름을 입력하세요.')
      return
    }
    if(!endpoint){
      setMcpAddError('MCP Endpoint를 입력하세요.')
      return
    }

    setMcpAddBusy(true)
    setMcpAddError('')
    try{
      const created=await api('/mcp/servers',{
        method:'POST',
        body:JSON.stringify({
          name,
          endpoint,
          trust_level:mcpAddForm.trust_level||'UNTRUSTED',
          allow_read_without_prompt:!!mcpAddForm.allow_read_without_prompt,
          allow_write_without_prompt:!!mcpAddForm.allow_write_without_prompt,
        })
      })

      let syncWarning=''
      if(created?.id){
        try{
          await api(`/mcp/servers/${created.id}/sync`,{method:'POST'})
        }catch(syncError){
          syncWarning=`서버는 등록되었지만 Tool 동기화에 실패했습니다: ${String(syncError)}`
        }
      }

      await refreshMcp()
      setMcpAddForm({
        name:'',
        endpoint:'',
        trust_level:'UNTRUSTED',
        allow_read_without_prompt:false,
        allow_write_without_prompt:false,
      })

      if(syncWarning){
        setMcpAddError(syncWarning)
      }else{
        setMcpAddOpen(false)
      }
    }catch(e){
      setMcpAddError(String(e))
    }finally{
      setMcpAddBusy(false)
    }
  }

  const syncMcpServer=async(serverId)=>{
    if(!serverId) return
    try{
      await api(`/mcp/servers/${serverId}/sync`,{method:'POST'})
      await refreshMcp()
    }catch(e){
      setMcpAddError(`MCP Tool 동기화 실패: ${String(e)}`)
      setMcpAddOpen(true)
    }
  }



  const getEditorFileFullPath=(relativePath)=>{
    if(!relativePath) return root||''

    const cleanRoot=String(root||'')
      .replace(/[\\/]+$/,'')

    const cleanRelative=String(relativePath)
      .replace(/^[\\/]+/,'')
      .replace(/\//g,'\\')

    return cleanRoot
      ? `${cleanRoot}\\${cleanRelative}`
      : cleanRelative
  }

  const copyEditorFileFullPath=async(relativePath)=>{
    const fullPath=getEditorFileFullPath(relativePath)
    if(!fullPath) return

    try{
      await navigator.clipboard.writeText(fullPath)
      setEditorTabMenu(null)
    }catch(e){
      window.prompt('전체 경로를 복사하세요.',fullPath)
    }
  }

  const getSaveAsPickerOptions=(relativePath)=>{
    const fileName=String(relativePath||'file.txt').replace(/\\/g,'/').split('/').pop()||'file.txt'
    const lower=fileName.toLowerCase()
    const extension=(lower.match(/\.[^.]+$/)||['.txt'])[0]
    const mimeByExtension={
      '.ipynb':'application/x-ipynb+json',
      '.json':'application/json',
      '.sql':'application/sql',
      '.py':'text/x-python',
      '.js':'text/javascript',
      '.jsx':'text/javascript',
      '.ts':'text/typescript',
      '.tsx':'text/typescript',
      '.md':'text/markdown',
      '.txt':'text/plain',
      '.csv':'text/csv',
      '.html':'text/html',
      '.css':'text/css',
      '.ps1':'text/plain',
      '.cmd':'text/plain',
      '.bat':'text/plain',
      '.yaml':'application/yaml',
      '.yml':'application/yaml',
      '.toml':'application/toml',
      '.xml':'application/xml',
      '.pdf':'application/pdf',
      '.ppt':'application/vnd.ms-powerpoint',
      '.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    }
    const pickerExtension=lower.endsWith('.agentdiag.json')?'.json':extension
    const mime=mimeByExtension[pickerExtension]||'application/octet-stream'
    return {
      suggestedName:fileName,
      types:[{
        description:`${pickerExtension.replace(/^\./,'').toUpperCase()} 파일`,
        accept:{[mime]:[pickerExtension]}
      }]
    }
  }

  const readEditorFileBlobForSaveAs=async(relativePath)=>{
    if(!relativePath) throw new Error('저장할 파일이 없습니다.')

    if(!isBinaryPreviewFile(relativePath)){
      const content=
        relativePath===selected
          ? (editorFileContents[relativePath] ?? code ?? '')
          : (editorFileContents[relativePath] ?? '')
      return new Blob([content],{type:'text/plain;charset=utf-8'})
    }

    const workspaceRoot=resolveWorkspaceRoot(
      editorFileRootRef.current?.[relativePath]||fileTreeRootRef.current||''
    )
    if(!workspaceRoot) throw new Error('프로젝트가 선택되지 않았습니다.')
    const info=runtimeInfo()
    const params=new URLSearchParams({
      root:String(workspaceRoot),
      relative_path:String(relativePath)
    })
    const response=await fetch(`${info.apiBase}/files/raw?${params.toString()}`)
    if(!response.ok){
      const body=await response.text().catch(()=>'')
      throw new Error(`원본 파일 읽기 실패 (${response.status})${body?`: ${body}`:''}`)
    }
    return response.blob()
  }

  const saveEditorFileAs=async(relativePath)=>{
    setEditorTabMenu(null)
    if(!relativePath) return
    if(fileLoadingPath===relativePath||(!isBinaryPreviewFile(relativePath)&&!Object.prototype.hasOwnProperty.call(editorFileContents,relativePath))){
      setFileSaveStatus('다른 이름 저장 대기 · 파일 로딩 중')
      setTerminal(prev=>(prev||'')+'\n[다른 이름으로 저장 대기] 파일 내용을 불러오는 중에는 저장하지 않습니다.\n')
      return
    }
    if(editorLoadErrors[relativePath]){
      setFileSaveStatus('다른 이름 저장 차단 · 파일 로드 실패')
      setTerminal(prev=>(prev||'')+'\n[다른 이름으로 저장 차단] 파일 로드가 실패한 탭입니다. 먼저 다시 불러오세요.\n')
      return
    }

    if(typeof window.showSaveFilePicker!=='function'){
      window.alert('현재 브라우저에서는 파일 저장 위치 선택 기능을 지원하지 않습니다. Chrome/Edge 최신 버전에서 실행해 주세요.')
      return
    }

    try{
      // Native file picker must be opened while the right-click action still
      // has a transient user activation. Choose the destination first, then
      // read/fetch the current tab bytes. This is especially important for
      // PDF/PPT/PPTX because their source bytes come from the Backend.
      const handle=await window.showSaveFilePicker(getSaveAsPickerOptions(relativePath))
      const blob=await readEditorFileBlobForSaveAs(relativePath)
      const writable=await handle.createWritable()
      await writable.write(blob)
      await writable.close()
      setFileSaveStatus('다른 이름으로 저장 완료')
      setTerminal(prev=>(prev||'')+`\n[다른 이름으로 저장 완료] ${handle.name||relativePath}\n`)
    }catch(e){
      if(e?.name==='AbortError') return
      setFileSaveStatus('다른 이름으로 저장 실패')
      setTerminal(prev=>(prev||'')+`\n[다른 이름으로 저장 실패] ${String(e?.message||e)}\n`)
      window.alert(`다른 이름으로 저장에 실패했습니다.\n${String(e?.message||e)}`)
    }
  }


  const activateEditorFile=(relativePath)=>{
    if(!relativePath) return

    const hasCachedContent=Object.prototype.hasOwnProperty.call(editorFileContents,relativePath)
    const cachedRoot=String(editorFileRootRef.current?.[relativePath]||'').trim()
    const currentRoot=resolveWorkspaceRoot(fileTreeRootRef.current||'')
    const normalizeRoot=value=>String(value||'').trim().replace(/\\/g,'/').replace(/\/+$/,'').toLowerCase()
    const cachedRootMatches=!cachedRoot||!currentRoot||normalizeRoot(cachedRoot)===normalizeRoot(currentRoot)
    if(!isBinaryPreviewFile(relativePath)&&(!hasCachedContent||!cachedRootMatches)){
      // An open tab can outlive its in-memory content during project/file state
      // transitions. Never activate an empty/default buffer for that file;
      // reload the authoritative disk content first.
      openFile(relativePath,currentRoot||fileTreeRootRef.current||'')
      return
    }

    setSelected(relativePath)
    setFileTreeSelected(relativePath)
    setFileTreeSelectedPaths([relativePath])
    setCode(editorFileContents[relativePath]??'')
    setFileSaveStatus('')

    if(editorExternalState[normalizeProjectRelativePath(relativePath)]==='modified_conflict'){
      openExternalChangePrompt(relativePath)
    }
  }

  const toggleEditorFilePin=(relativePath)=>{
    if(!relativePath) return

    setPinnedEditorFiles(prev=>
      prev.includes(relativePath)
        ? prev.filter(path=>path!==relativePath)
        : [...prev,relativePath]
    )

    setEditorTabMenu(null)
  }

  const closeEditorFiles=(pathsToClose)=>{
    const closeSet=new Set(pathsToClose||[])
    if(!closeSet.size) return

    const selectedIndex=openEditorFiles.indexOf(selected)
    const nextFiles=openEditorFiles.filter(
      path=>!closeSet.has(path)
    )

    setOpenEditorFiles(nextFiles)

    setEditorFileContents(prev=>{
      const next={...prev}
      for(const path of closeSet){
        delete next[path]
      }
      return next
    })

    setEditorFileDirty(prev=>{
      const next={...prev}
      for(const path of closeSet){
        delete next[path]
      }
      return next
    })

    setPinnedEditorFiles(prev=>
      prev.filter(path=>!closeSet.has(path))
    )

    if(closeSet.has(selected)){
      const nextActive=
        nextFiles[Math.min(
          Math.max(selectedIndex,0),
          Math.max(nextFiles.length-1,0)
        )]
        || nextFiles[nextFiles.length-1]
        || ''

      setSelected(nextActive)
      setFileTreeSelected(nextActive)
      setCode(
        nextActive
          ? (editorFileContents[nextActive]??'')
          : ''
      )
      setFileSaveStatus('')
    }
  }

  const requestEditorFilesClose=(pathsToClose)=>{
    const openSet=new Set(openEditorFiles)
    const targets=[...new Set(pathsToClose||[])].filter(
      path=>openSet.has(path)
    )

    setEditorFilesMenu(null)
    setEditorTabMenu(null)

    if(!targets.length) return

    const dirtyPaths=targets.filter(
      path=>!!editorFileDirty[path]
    )

    if(!dirtyPaths.length){
      closeEditorFiles(targets)
      return
    }

    setEditorCloseConfirm({
      paths:targets,
      dirtyPaths,
      saving:false,
      error:''
    })
  }

  const handleEditorCloseDecision=async(decision)=>{
    const pending=editorCloseConfirm
    if(!pending || pending.saving) return

    if(decision==='cancel'){
      setEditorCloseConfirm(null)
      return
    }

    if(decision==='discard'){
      closeEditorFiles(pending.paths)
      setEditorCloseConfirm(null)
      return
    }

    if(decision!=='save') return

    setEditorCloseConfirm(prev=>prev?{
      ...prev,
      saving:true,
      error:''
    }:prev)

    const {failed}=await saveDirtyEditorPaths(
      pending.dirtyPaths,
      {label:'닫기 전 저장'}
    )

    if(failed.length){
      setEditorCloseConfirm(prev=>prev?{
        ...prev,
        saving:false,
        error:`${failed.length}개 파일 저장에 실패했습니다. 실패한 파일을 확인한 뒤 다시 시도하세요.`
      }:prev)
      return
    }

    closeEditorFiles(pending.paths)
    setEditorCloseConfirm(null)
  }

  const closeAllEditorFiles=()=>{
    requestEditorFilesClose([...openEditorFiles])
  }

  const closeUnpinnedEditorFiles=()=>{
    const pinned=new Set(pinnedEditorFiles)
    requestEditorFilesClose(
      openEditorFiles.filter(path=>!pinned.has(path))
    )
  }

  const closeEditorFile=(relativePath)=>{
    requestEditorFilesClose([relativePath])
  }

  const updateActiveEditorCode=(value)=>{
    setFocusOwnerSafe('editor')
    const next=value??''

    setCode(next)

    // Notebook cells own independent Monaco models. Refocusing the global
    // source-editor instance after every serialized .ipynb change can steal
    // focus/caret from the active cell and make the caret jump to the end.
    // Keep the historical refocus behavior only for the single-file editor.
    if(!isNotebookFile(selected)){
      queueMicrotask(()=>{
        if(focusOwnerRef.current==='editor'){
          try{ editorInstanceRef.current?.focus() }catch{}
        }
      })
    }
    setFileSaveStatus('')

    if(selected){
      // Keep an immediate mirror for Ctrl+S. React state may still be queued
      // when Ctrl+S is pressed immediately after the last Notebook keystroke.
      editorFileContentsRef.current={
        ...editorFileContentsRef.current,
        [selected]:next
      }

      setEditorFileContents(prev=>({
        ...prev,
        [selected]:next
      }))

      setEditorFileDirty(prev=>({
        ...prev,
        [selected]:true
      }))
    }
  }


  const openFile=async(relativePath,rootOverride='')=>{
    setWorkspaceTab('CODE')

    const requestedPath=relativePath
    if(!requestedPath) return

    const workspaceRoot=resolveWorkspaceRoot(rootOverride||fileTreeRootRef.current||'')
    const cachedRoot=String(editorFileRootRef.current?.[requestedPath]||'').trim()
    const normalizeRoot=value=>String(value||'').trim().replace(/\\/g,'/').replace(/\/+$/,'').toLowerCase()
    const cachedRootMatches=!cachedRoot||!workspaceRoot||normalizeRoot(cachedRoot)===normalizeRoot(workspaceRoot)
    const hasCachedContent=Object.prototype.hasOwnProperty.call(editorFileContents,requestedPath)
    if(openEditorFiles.includes(requestedPath)&&(isBinaryPreviewFile(requestedPath)||hasCachedContent)&&cachedRootMatches){
      setSelected(requestedPath)
      setFileTreeSelected(requestedPath)
      setCode(editorFileContents[requestedPath]??'')
      setFileSaveStatus('')
      return
    }

    const token=++fileLoadTokenRef.current

    setSelected(requestedPath)
    setFileTreeSelected(requestedPath)
    setFileLoading(true)
    setFileLoadingPath(requestedPath)

    try{
      if(!workspaceRoot){
        throw new Error('프로젝트 root를 확인할 수 없습니다. 프로젝트를 다시 선택한 뒤 파일을 열어주세요.')
      }

      if(isBinaryPreviewFile(requestedPath)){
        let meta=null
        try{
          meta=await api(`/files/meta?root=${encodeURIComponent(workspaceRoot)}&relative_path=${encodeURIComponent(requestedPath)}`)
        }catch(_){ }

        if(token!==fileLoadTokenRef.current) return

        const metaKey=normalizeProjectRelativePath(requestedPath)
        if(meta?.exists){
          const loadedMeta={
            mtime_ns:meta.mtime_ns||0,
            size:meta.size||0,
            sha256:meta.sha256||''
          }
          editorFileDiskMetaRef.current={
            ...editorFileDiskMetaRef.current,
            [metaKey]:loadedMeta
          }
          setEditorFileDiskMeta(prev=>({...prev,[metaKey]:loadedMeta}))
        }

        setOpenEditorFiles(prev=>prev.includes(requestedPath)?prev:[...prev,requestedPath])
        editorFileRootRef.current[requestedPath]=workspaceRoot
        setEditorFileContents(prev=>({...prev,[requestedPath]:''}))
        setEditorFileDirty(prev=>({...prev,[requestedPath]:false}))
        if(isPdfFile(requestedPath)){
          setPdfPreviewRevision(prev=>({...prev,[metaKey]:Date.now()}))
        }else{
          setPresentationPreviewRevision(prev=>({...prev,[metaKey]:Date.now()}))
        }
        setCode('')
        setSelected(requestedPath)
        setFileTreeSelected(requestedPath)
        setFileSaveStatus(isPdfFile(requestedPath)?'PDF 미리보기':'PowerPoint 미리보기')
        return
      }

      const r=await api('/files/read',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          relative_path:requestedPath
        })
      })

      if(token!==fileLoadTokenRef.current) return

      const content=r.content??''
      const canonicalPath=r.relative_path||requestedPath
      editorFileRootRef.current[canonicalPath]=workspaceRoot
      editorFileRootRef.current[requestedPath]=workspaceRoot
      const metaKey=normalizeProjectRelativePath(canonicalPath)
      if(r.mtime_ns){
        const loadedMeta={
          mtime_ns:r.mtime_ns,
          size:r.size||0,
          sha256:r.sha256||''
        }
        editorFileDiskMetaRef.current={
          ...editorFileDiskMetaRef.current,
          [metaKey]:loadedMeta
        }
        setEditorFileDiskMeta(prev=>({
          ...prev,
          [metaKey]:loadedMeta
        }))
        setEditorExternalState(prev=>{
          const next={...prev}; delete next[metaKey]; return next
        })
      }

      setOpenEditorFiles(prev=>
        prev.includes(requestedPath)
          ? prev
          : [...prev,requestedPath]
      )
      setEditorFileContents(prev=>({
        ...prev,
        [requestedPath]:content
      }))
      setEditorFileDirty(prev=>({
        ...prev,
        [requestedPath]:false
      }))

      setCode(content)
      setSelected(requestedPath)
      setFileTreeSelected(requestedPath)
      setEditorLoadErrors(prev=>{const next={...prev}; delete next[requestedPath]; return next})
      setFileSaveStatus('')
    }catch(e){
      if(token!==fileLoadTokenRef.current) return

      const message=String(e?.message||e)

      // v5.250: 파일 읽기 실패 메시지를 실제 Editor buffer에 넣지 않습니다.
      // 과거에는 이 오류 placeholder가 Ctrl+S/저장 경로를 통해 실제 .ipynb에
      // 덮어써질 수 있었습니다. 오류는 전용 상태로만 표시합니다.
      setOpenEditorFiles(prev=>
        prev.includes(requestedPath)
          ? prev
          : [...prev,requestedPath]
      )
      setEditorLoadErrors(prev=>({
        ...prev,
        [requestedPath]:{
          message,
          path:requestedPath,
          time:new Date().toISOString(),
        }
      }))
      setEditorFileDirty(prev=>({
        ...prev,
        [requestedPath]:false
      }))

      const previous=editorFileContents[requestedPath]
      setCode(previous??'')
      setSelected(requestedPath)
      setFileTreeSelected(requestedPath)
      setFileSaveStatus('파일 로드 실패')
    }finally{
      if(token===fileLoadTokenRef.current){
        setFileLoading(false)
        setFileLoadingPath('')
      }
    }
  }

  const loadWorkflowDefinition=async()=>{
    try{
      const result=await api('/workflow/definition')
      setWorkflowDefinition(result)
      return result
    }catch(e){
      setWorkflowDefinition({
        ok:false,
        error:String(e)
      })
      return null
    }
  }

  const requirementKeywordDefinitions=[
    {id:'purpose',label:'목적',keywords:['agent','요약','프로그램','만들']},
    {id:'files',label:'파일 형식',keywords:['.txt','.md','.py','파일 형식','확장자']},
    {id:'output',label:'결과 형식',keywords:['한국어','json','결과','저장','.txt','.md']},
    {id:'llm',label:'LLM',keywords:['gpt-4o-mini','openai','ollama','llm']},
    {id:'ui',label:'UI / Layout',keywords:['react','vite','streamlit','웹 gui','웹 ui','웹앱','대시보드','layout','레이아웃']},
    {id:'backend',label:'Backend',keywords:['fastapi','uvicorn','backend','백엔드']},
    {id:'mcp',label:'MCP / Transport',keywords:['mcp','stdio','streamable http','transport']},
    {id:'database',label:'DB',keywords:['데이터베이스','database','postgresql','db']},
    {id:'permission',label:'권한 / 파일 접근',keywords:['권한','인증','rbac','project root','프로젝트 root','root 내부']},
    {id:'runtime',label:'실행 환경',keywords:['windows 10','windows 11','python 3.12','온프레미스','로컬 pc','local']},
    {id:'limits',label:'처리 제한',keywords:['10mb','120초','timeout','타임아웃','chunk','청크']}
  ]

  const requirementDraftKeyFor=(projectPath='',agentName='')=>{
    const path=String(projectPath||'')
      .trim()
      .replace(/[\\/]+$/,'')
      .toLowerCase()

    const name=String(agentName||'')
      .trim()
      .toLowerCase()

    const identity=path||name||'unsaved-agent'
    return `theanova.agentstudio.requirements.v1::${identity}`
  }

  const requirementDraftKey=()=>
    requirementDraftKeyFor(newAgentProjectRoot||root||'',newAgentName||'')

  const requirementConversationText=()=>{
    const manualLines=Object.entries(requirementManualOverrides||{})
      .map(([id,value])=>{
        const def=requirementKeywordDefinitions.find(item=>item.id===id)
        return `${def?.label||id}: ${String(value||'')}`
      })
    return [
      ...(chat||[]).map(item=>String(item?.content||'')),
      interviewAttachmentSummary||'',
      ...manualLines
    ]
      .join('\n')
      .toLowerCase()
  }

  const getRequirementKeywordStatus=()=>{
    const text=requirementConversationText()
    const firstUser=(chat||[]).find(item=>item?.role==='user')
    const confirmed=confirmedInterviewRequirements||{}

    const includesAny=(values=[])=>values.some(value=>
      text.includes(String(value).toLowerCase())
    )

    const unique=(values=[])=>[
      ...new Set(
        values
          .map(value=>String(value||'').trim())
          .filter(Boolean)
      )
    ]

    const getValue=(id)=>{
      const manualValue=String(requirementManualOverrides?.[id]||'').trim()
      if(manualValue) return manualValue
      switch(id){
        case 'purpose':{
          const raw=String(
            confirmed?.original_request
            ||firstUser?.content
            ||workflowReq
            ||''
          ).trim()

          if(!raw) return ''

          // 사용자가 긴 한 문장 안에 기술 스택과 목적을 함께 적어도
          // 목적 카드에는 기술 스택이 아니라 Agent의 핵심 목적을 표시합니다.
          const normalizedPurpose=raw.replace(/\s+/g,' ').trim()
          const agentPurposeMatch=normalizedPurpose.match(
            /(?:^|[.。!?]\s*)(?:나는\s*)?(.{2,80}?(?:Agent|에이전트))(?:를|을)?\s*(?:만들|개발|생성)/i
          )
          if(agentPurposeMatch?.[1]){
            return agentPurposeMatch[1]
              .replace(/^(?:PostgreSQL|Redis|pgvector|OpenAI|Ollama)(?:\s*[,·+]\s*(?:PostgreSQL|Redis|pgvector|OpenAI|Ollama))*\s*(?:를|을)?\s*사용하는\s*/i,'')
              .trim()
          }

          if(
            includesAny(['파일','요약'])
            &&includesAny(['agent','에이전트'])
          ){
            return '프로젝트 파일 요약 Agent'
          }

          return normalizedPurpose.length>48
            ? `${normalizedPurpose.slice(0,48)}…`
            : normalizedPurpose
        }

        case 'files':{
          const values=
            confirmed?.file_access?.allowed_extensions?.length
              ? confirmed.file_access.allowed_extensions
              : [
                  text.includes('.txt')?'.txt':'',
                  text.includes('.md')?'.md':'',
                  text.includes('.py')?'.py':''
                ]

          return unique(values).join(', ')
        }

        case 'output':{
          const values=[]

          if(
            confirmed?.result?.ui_display
            ||includesAny(['react 웹 ui','react ui','웹 ui'])
          ){
            values.push('React UI')
          }
          if(includesAny(['한국어 텍스트','한국어'])){
            values.push('한국어')
          }
          if(includesAny(['json 구조','json'])){
            values.push('JSON API')
          }

          const formats=
            confirmed?.result?.export_formats
            ||[
              text.includes('.txt')?'TXT':'',
              text.includes('.md')?'MD':''
            ]

          const normalizedFormats=unique(formats)
            .map(value=>value.replace('.','').toUpperCase())

          if(normalizedFormats.length){
            values.push(`${normalizedFormats.join('/')} 저장`)
          }

          return unique(values).join(' · ')
        }

        case 'llm':{
          const values=[]

          const defaultModel=
            confirmed?.llm?.default_model
            ||(text.includes('gpt-4o-mini')?'gpt-4o-mini':'')

          if(defaultModel) values.push(defaultModel)

          if(
            confirmed?.llm?.ollama_supported
            ||text.includes('ollama')
          ){
            values.push('Ollama')
          }

          return unique(values).join(', ')
        }

        case 'ui':{
          if(uiLayoutConfig?.template_id){
            const framework=String(confirmed?.ui||'').trim()
            return [framework,uiLayoutSummary(uiLayoutConfig)].filter(Boolean).join(' · ')
          }
          if(
            String(confirmed?.ui||'').toLowerCase().includes('react')
            ||includesAny(['react + vite','react+vite','react 기반'])
          ){
            return includesAny(['vite'])?'React + Vite':'React'
          }
          if(includesAny(['streamlit'])) return 'Streamlit'
          return confirmed?.ui||''
        }

        case 'backend':{
          const values=[]

          if(
            String(confirmed?.backend||'').toLowerCase().includes('fastapi')
            ||text.includes('fastapi')
          ){
            values.push('FastAPI')
          }

          if(text.includes('uvicorn')){
            values.push('Uvicorn')
          }

          return unique(values).join(' + ')
        }

        case 'mcp':{
          const values=[]

          const transport=
            confirmed?.mcp?.default_transport
            ||(text.includes('stdio')?'stdio':'')

          if(transport) values.push(transport)

          if(
            confirmed?.mcp?.future_transport==='streamable_http'
            ||text.includes('streamable http')
          ){
            values.push('Streamable HTTP 확장')
          }

          return unique(values).join(' · ')
        }

        case 'database':{
          if(
            confirmed?.database?.enabled===false
            ||includesAny([
              '데이터베이스를 사용하지',
              'db 사용하지',
              '이번 버전에서는 db',
              '이번 버전에서는 데이터베이스'
            ])
          ){
            return (
              confirmed?.database?.future_extension
              ||text.includes('postgresql')
            )
              ? '미사용 · PostgreSQL 확장'
              : '미사용'
          }

          const values=[]
          if(text.includes('postgresql')) values.push('PostgreSQL')
          if(text.includes('redis')) values.push('Redis')
          if(text.includes('pgvector')||text.includes('vector search')||text.includes('벡터 검색')) values.push('pgvector')
          return unique(values).join(' · ')
        }

        case 'permission':{
          const values=[]

          if(
            confirmed?.file_access?.restrict_to_project_root
            ||includesAny([
              'project root 내부',
              '프로젝트 root 내부',
              'root 내부'
            ])
          ){
            values.push('Project Root 내부')
          }

          const extensions=
            confirmed?.file_access?.allowed_extensions||[]

          if(extensions.length){
            values.push(
              `${extensions.join('/')} 제한`
            )
          }

          if(
            includesAny([
              '사용자 인증이나 역할 기반 권한 관리',
              '별도의 사용자 인증',
              'rbac는 사용하지',
              '단일 로컬 사용자'
            ])
          ){
            values.push('로그인/RBAC 없음')
          }

          return unique(values).join(' · ')
        }

        case 'runtime':{
          const values=[]

          if(
            includesAny(['windows 10/11','windows 10','windows 11'])
          ){
            values.push('Windows 10/11')
          }

          if(
            includesAny(['python 3.12'])
          ){
            values.push('Python 3.12')
          }

          if(
            includesAny(['.venv','가상환경'])
          ){
            values.push('.venv')
          }

          if(
            includesAny(['온프레미스'])
          ){
            values.push('온프레미스')
          }

          return unique(values).join(' · ')
        }

        case 'limits':{
          const values=[]

          if(
            includesAny(['10mb','10 mb'])
          ){
            values.push('10MB')
          }

          if(
            includesAny(['120초','120초로','120 second','120s'])
          ){
            values.push('120초')
          }

          if(
            includesAny(['chunk','청크'])
          ){
            values.push('Chunking')
          }

          return unique(values).join(' · ')
        }

        default:
          return ''
      }
    }

    return requirementKeywordDefinitions.map(def=>{
      let collected=def.keywords.some(keyword=>
        text.includes(String(keyword).toLowerCase())
      )

      if(def.id==='purpose'){
        collected=Boolean(
          String(firstUser?.content||workflowReq||'').trim()
        )
      }

      if(def.id==='llm' && confirmed?.llm){
        collected=true
      }
      if(def.id==='files' && confirmed?.file_access?.allowed_extensions?.length){
        collected=true
      }
      if(def.id==='mcp' && confirmed?.mcp){
        collected=true
      }
      if(def.id==='database' && confirmed?.database){
        collected=true
      }
      if(def.id==='output' && confirmed?.result){
        collected=true
      }
      if(def.id==='ui' && (confirmed?.ui||confirmed?.ui_layout?.template_id||uiLayoutConfig?.template_id)){
        collected=true
      }
      if(def.id==='backend' && confirmed?.backend){
        collected=true
      }
      if(
        def.id==='permission'
        &&confirmed?.file_access?.restrict_to_project_root
      ){
        collected=true
      }

      const value=getValue(def.id)

      if(String(requirementManualOverrides?.[def.id]||'').trim()){
        collected=true
      }

      // 명확한 실제 값이 추출되면 해당 슬롯은 수집 완료로 간주합니다.
      if(value){
        collected=true
      }

      return {
        ...def,
        collected,
        value
      }
    })
  }


  const getBuilderConversationSummary=()=>{
    const statuses=getRequirementKeywordStatus()
    const byId=Object.fromEntries(statuses.map(item=>[item.id,item]))
    const conversation=[
      ...(chat||[]).filter(item=>item?.role==='user').map(item=>String(item?.content||'')),
      interviewAttachmentSummary||'',
      ...Object.values(requirementManualOverrides||{}).map(value=>String(value||'')),
    ].join('\n').toLowerCase()
    const uniqueValues=(values=[])=>[...new Set(values.filter(Boolean))]
    const normalizeDatabaseValues=(values=[])=>{
      const canonical=[]
      const add=(raw)=>{
        const token=String(raw||'').trim()
        if(!token) return
        const lower=token.toLowerCase()
        let label=token
        if(lower.includes('postgresql')) label='PostgreSQL'
        else if(lower==='redis'||lower.includes('redis ')) label='Redis'
        else if(lower.includes('pgvector')||lower==='vector db'||lower==='vector search') label='pgvector'
        if(!canonical.includes(label)) canonical.push(label)
      }
      values.forEach(value=>{
        String(value||'')
          .split(/\s*[·,+/]\s*/g)
          .map(part=>part.trim())
          .filter(Boolean)
          .forEach(add)
      })
      return canonical
    }
    const features=[]
    const addFeature=(label,...keywords)=>{
      if(keywords.some(keyword=>conversation.includes(String(keyword).toLowerCase()))){
        features.push(label)
      }
    }
    addFeature('자연어 검색','자연어','semantic search','의미 기반')
    addFeature('Hybrid Search','hybrid','pgvector','벡터 검색','vector 검색')
    addFeature('상품 추천','추천')
    addFeature('재고 확인','재고')
    addFeature('주문 처리','주문')
    addFeature('RAG','rag','faq','knowledge base','지식베이스')
    addFeature('파일 분석','파일 분석','첨부 파일','문서 분석')
    addFeature('코드 편집','코드 편집','코드 수정')
    addFeature('리포트','리포트','보고서')
    addFeature('대화/상담','대화','상담','챗봇')

    const integrations=[]
    const addIntegration=(label,...keywords)=>{
      if(keywords.some(keyword=>conversation.includes(String(keyword).toLowerCase()))){
        integrations.push(label)
      }
    }
    addIntegration('PostgreSQL','postgresql')
    addIntegration('Redis','redis')
    addIntegration('pgvector','pgvector','벡터 검색','vector search')
    addIntegration('MCP','mcp')
    addIntegration('OpenAI','openai','gpt-')
    addIntegration('Ollama','ollama')

    const mcpToolValues=uniqueValues([
      byId.mcp?.value,
      integrations.includes('MCP')?'MCP':'',
    ]).join(' · ')
    const databaseValues=normalizeDatabaseValues([
      byId.database?.value,
      ...integrations.filter(value=>['PostgreSQL','Redis','pgvector'].includes(value)),
    ]).join(' · ')
    const runtimeValues=uniqueValues([
      byId.runtime?.value,
      byId.backend?.value,
      byId.llm?.value,
    ]).join(' · ')
    const collected=statuses.filter(item=>item.collected).length

    return {
      purpose:byId.purpose?.value||'대화에서 목적을 확인하는 중',
      features:uniqueValues(features).slice(0,6).join(' · ')||'핵심 기능을 확인하는 중',
      mcpTools:mcpToolValues||'외부 MCP / Tool 필요 여부를 확인하는 중',
      database:databaseValues||'DB / Cache / Vector 구성을 확인하는 중',
      runtime:runtimeValues||'실행 환경을 확인하는 중',
      uiLayout:uiLayoutConfig?.template_id?uiLayoutSummary(uiLayoutConfig):'레이아웃 템플릿을 선택하는 중',
      confirmation:`요구사항 ${collected}/${statuses.length} · ${targetWorkflowPreview?'Workflow 설계됨':'인터뷰 진행 중'}`,
      collectedItems:statuses.filter(item=>item.collected&&item.value),
    }
  }

  const buildRequirementDraftSnapshot=(resumeOverride=null)=>{
    return {
      version:3,
      saved_at:new Date().toISOString(),
      agent_name:newAgentName||'',
      design_project_id:designProjectId||null,
      design_project_version:designProjectVersion||1,
      project_root:newAgentProjectRoot||root||'',
      workflow_request:workflowReq||'',
      chat:Array.isArray(chat)?chat:[],
      confirmed_requirements:confirmedInterviewRequirements||{},
      workflow_preview:targetWorkflowPreview||null,
      workflow_quality:targetWorkflowQuality||null,
      agent_build_stage:agentBuildStage||'REQUIREMENTS',
      attachment_memory:interviewAttachmentMemory||'',
      attachment_summary:interviewAttachmentSummary||'',
      attachment_summary_files:interviewAttachmentSummaryFiles||[],
      attachment_requirements:interviewAttachmentRequirements||[],
      attachment_requirement_coverage:interviewAttachmentRequirementCoverage||{},
      manual_requirement_overrides:requirementManualOverrides||{},
      feature_registry:designFeatureRegistry||[],
      ui_layout:uiLayoutConfig||null,
      build_resume:resumeOverride||(restoredBuildResume&&typeof restoredBuildResume==='object'?restoredBuildResume:null)
    }
  }

  const persistRequirementCheckpoint=(snapshot)=>{
    const projectRoot=String(snapshot?.project_root||newAgentProjectRoot||root||'').trim()
    if(!projectRoot||!snapshot) return
    try{
      const signature=JSON.stringify({...snapshot,saved_at:''})
      if(requirementCheckpointSignatureRef.current===signature) return
      requirementCheckpointSignatureRef.current=signature
      void api('/workflow/design-checkpoint',{
        method:'POST',
        body:JSON.stringify({project_root:projectRoot,snapshot})
      }).catch(error=>{
        console.warn('프로젝트 Resume Checkpoint 저장 실패',error)
        if(requirementCheckpointSignatureRef.current===signature){
          requirementCheckpointSignatureRef.current=''
        }
      })
    }catch(e){
      console.warn('Resume Checkpoint 직렬화 실패',e)
    }
  }

  const saveRequirementDraft=(resumeOverride=null)=>{
    try{
      // If an older Draft exists for a newly selected path, do not silently
      // overwrite it before the user decides whether to restore or ignore it.
      if(requirementDraftDecisionPendingRef.current) return false

      const snapshot=buildRequirementDraftSnapshot(resumeOverride)
      const hasUsefulData=
        snapshot.chat.some(item=>item?.role==='user')
        || Boolean(snapshot.workflow_request)
        || Object.keys(snapshot.confirmed_requirements||{}).length>0
        || Boolean(snapshot.workflow_preview)
        || Boolean(snapshot.attachment_summary)
        || (Array.isArray(snapshot.attachment_requirements)&&snapshot.attachment_requirements.length>0)
        || Object.keys(snapshot.manual_requirement_overrides||{}).length>0
        || (Array.isArray(snapshot.feature_registry)&&snapshot.feature_registry.length>0)
        || Boolean(snapshot.ui_layout?.template_id)

      if(!hasUsefulData) return false

      localStorage.setItem(
        requirementDraftKey(),
        JSON.stringify(snapshot)
      )
      setRequirementDraftSavedAt(snapshot.saved_at)
      persistRequirementCheckpoint(snapshot)
      return true
    }catch(e){
      console.warn('요구사항 Draft 저장 실패',e)
      return false
    }
  }

  const restoreRequirementDraft=async(keyOverride='')=>{
    try{
      const key=keyOverride||requirementDraftKey()
      let snapshot=(requirementDraftCandidate?.snapshot&&typeof requirementDraftCandidate.snapshot==='object')
        ? requirementDraftCandidate.snapshot
        : null
      if(!snapshot){
        const raw=localStorage.getItem(key)
        snapshot=raw?JSON.parse(raw):null
      }
      if(!snapshot) return false

      if(Array.isArray(snapshot?.chat) && snapshot.chat.length){
        const restoredChat=snapshot.chat.map(item=>({
          ...item,
          content:item?.role==='assistant'
            ? protectInterviewAssistantAnswer(item?.content||'')
            : sanitizeInterviewDisplayText(item?.content||'')
        })).filter(item=>String(item?.content||'').trim())
        setChat(restoredChat)
        setBuilderStarted(restoredChat.some(item=>item?.role==='user'))
      }else if(snapshot?.workflow_request){
        setChat([
          {role:'assistant',content:'이전 Agent 설계/개발 기록을 복원했습니다. 기존 요구사항과 실패 지점부터 이어서 진행할 수 있습니다.'},
          {role:'user',content:sanitizeInterviewDisplayText(snapshot.workflow_request)}
        ])
        setBuilderStarted(true)
      }

      const restoredAttachmentMemory=sanitizeInterviewDisplayText(snapshot?.attachment_memory||'')
      if(restoredAttachmentMemory) setInterviewAttachmentMemory(restoredAttachmentMemory)
      const restoredAttachmentSummary=sanitizeInterviewDisplayText(snapshot?.attachment_summary||'')
      setInterviewAttachmentSummary(restoredAttachmentSummary)
      setInterviewAttachmentSummaryFiles(
        Array.isArray(snapshot?.attachment_summary_files)
          ? snapshot.attachment_summary_files.map(item=>({name:String(item?.name||''),path:String(item?.path||'')})).filter(item=>item.name||item.path)
          : []
      )
      setInterviewAttachmentRequirements(Array.isArray(snapshot?.attachment_requirements)?snapshot.attachment_requirements:[])
      setInterviewAttachmentRequirementCoverage(snapshot?.attachment_requirement_coverage&&typeof snapshot.attachment_requirement_coverage==='object'?snapshot.attachment_requirement_coverage:{})
      setRequirementManualOverrides(snapshot?.manual_requirement_overrides&&typeof snapshot.manual_requirement_overrides==='object'?snapshot.manual_requirement_overrides:{})
      setDesignFeatureRegistry(Array.isArray(snapshot?.feature_registry)?snapshot.feature_registry:[])
      if(snapshot?.design_project_id) setDesignProjectId(snapshot.design_project_id)
      if(snapshot?.design_project_version) setDesignProjectVersion(snapshot.design_project_version)
      setUiLayoutConfig(snapshot?.ui_layout&&typeof snapshot.ui_layout==='object'?snapshot.ui_layout:null)

      if(snapshot?.workflow_request) setWorkflowReq(snapshot.workflow_request)
      if(snapshot?.confirmed_requirements) setConfirmedInterviewRequirements(snapshot.confirmed_requirements)
      if(snapshot?.workflow_preview){
        setTargetWorkflowPreview(snapshot.workflow_preview)
        setPreviousTargetWorkflowPreview(snapshot.workflow_preview)
        setTargetWorkflowQuality(snapshot.workflow_quality||null)
      }

      const resumeCandidate=(requirementDraftCandidate?.build_resume&&typeof requirementDraftCandidate.build_resume==='object')
        ? requirementDraftCandidate.build_resume
        : (snapshot?.build_resume&&typeof snapshot.build_resume==='object'?snapshot.build_resume:null)
      if(resumeCandidate){
        setRestoredBuildResume(resumeCandidate)
        const restoredState=resumeCandidate?.workflow_state&&typeof resumeCandidate.workflow_state==='object'
          ? resumeCandidate.workflow_state
          : null
        if(restoredState&&Object.keys(restoredState).length){
          setWorkflow({state:restoredState,failure_diagnostics:{
            project_root:resumeCandidate.project_root||snapshot.project_root||'',
            run_id:resumeCandidate.run_id||'',
            status:resumeCandidate.status||restoredState.diagnostic_status||restoredState.status||'',
            failure_stage:resumeCandidate.failure_stage||restoredState.diagnostic_failure_stage||'',
            failure_reason:resumeCandidate.failure_reason||restoredState.diagnostic_failure_reason||restoredState.error||''
          }})
        }
        const status=String(resumeCandidate.status||restoredState?.diagnostic_status||restoredState?.status||'')
        const failed=/(FAIL|ERROR|INCOMPLETE|EXCEPTION)/i.test(status)
        if(failed){
          setAgentBuildStage('PROJECT_CREATED')
          setAgentBuildMessage(`이전 개발 실패 기록 복원됨${status?` · ${status}`:''}. 기존 생성 파일과 진단 기록을 사용해 다시 개발할 수 있습니다.`)
        }else if(snapshot?.workflow_preview){
          setAgentBuildStage(snapshot?.agent_build_stage==='PROJECT_CREATED'?'PROJECT_CREATED':'WORKFLOW_READY')
        }
      }else if(snapshot?.workflow_preview){
        setAgentBuildStage(snapshot?.agent_build_stage==='PROJECT_CREATED'?'PROJECT_CREATED':'WORKFLOW_READY')
      }else if(snapshot?.agent_build_stage){
        setAgentBuildStage(snapshot.agent_build_stage==='BUILDING'?'PROJECT_CREATED':snapshot.agent_build_stage)
      }

      if(snapshot?.agent_name && !newAgentName) setNewAgentName(snapshot.agent_name)

      // Rewrite local draft in the current safe v2 format and persist it to the project folder.
      const safeSnapshot={...snapshot,version:3,build_resume:resumeCandidate||snapshot?.build_resume||null}
      try{ localStorage.setItem(key,JSON.stringify(safeSnapshot)) }catch{}
      persistRequirementCheckpoint(safeSnapshot)

      setRequirementDraftSavedAt(snapshot?.saved_at||'')
      setRequirementDraftRestored(true)
      setRequirementDraftCandidate(null)
      setRequirementDraftDecisionPending(false)
      return true
    }catch(e){
      console.warn('요구사항/개발 기록 복원 실패',e)
      return false
    }
  }

  const keepCurrentInterviewInsteadOfDraft=()=>{
    // The user explicitly chose the current/new interview. From this point the
    // normal autosave may replace the older Draft for this path.
    requirementDraftDecisionPendingRef.current=false
    setRequirementDraftCandidate(null)
    setRequirementDraftDecisionPending(false)
    setRequirementDraftRestored(false)

    try{
      const snapshot=buildRequirementDraftSnapshot()
      const hasUsefulData=
        snapshot.chat.some(item=>item?.role==='user')
        ||Boolean(snapshot.workflow_request)
        ||Object.keys(snapshot.confirmed_requirements||{}).length>0
        ||Boolean(snapshot.workflow_preview)
        ||Boolean(snapshot.attachment_summary)
        ||Object.keys(snapshot.manual_requirement_overrides||{}).length>0
        ||(Array.isArray(snapshot.feature_registry)&&snapshot.feature_registry.length>0)
        ||Boolean(snapshot.ui_layout?.template_id)
      if(hasUsefulData){
        localStorage.setItem(requirementDraftKey(),JSON.stringify(snapshot))
        setRequirementDraftSavedAt(snapshot.saved_at)
      }else{
        setRequirementDraftSavedAt('')
      }
    }catch(e){
      console.warn('현재 인터뷰 Draft 저장 실패',e)
      setRequirementDraftSavedAt('')
    }
  }

  const clearRequirementDraft=()=>{
    try{
      localStorage.removeItem(requirementDraftKey())
    }catch{}
    setRequirementDraftSavedAt('')
    setRequirementDraftRestored(false)
    setRequirementDraftCandidate(null)
    setRequirementDraftDecisionPending(false)
    setInterviewAttachmentMemory('')
    setInterviewAttachmentSummary('')
    setInterviewAttachmentSummaryFiles([])
    setInterviewAttachmentRequirements([])
    setInterviewAttachmentRequirementCoverage({})
    setRequirementManualOverrides({})
  }

  const invalidateRequirementWorkflowAfterEdit=(message='요구사항이 변경되었습니다. Workflow를 다시 설계해 주세요.')=>{
    setWorkflowReq('')
    if(targetWorkflowPreview){
      setPreviousTargetWorkflowPreview(targetWorkflowPreview)
    }
    setTargetWorkflowPreview(null)
    setTargetWorkflowQuality(null)
    setAgentBuildStage('REQUIREMENTS')
    setAgentBuildMessage(message)
  }

  const removeRequirementConversationTurn=(messageIndex)=>{
    const index=Number(messageIndex)
    if(!Number.isInteger(index)||index<0) return
    const removedOverrideId=String(chat?.[index]?.requirement_override||'')
    const nextChat=(chat||[]).filter((_item,currentIndex)=>{
      if(currentIndex===index) return false
      if(currentIndex===index+1 && chat?.[index+1]?.role==='assistant') return false
      return true
    })
    if(removedOverrideId){
      setRequirementManualOverrides(prev=>{
        const next={...(prev||{})}
        delete next[removedOverrideId]
        return next
      })
    }
    setChat(nextChat)
    setConfirmedInterviewRequirements({})
    invalidateRequirementWorkflowAfterEdit('지난 사용자 답변을 삭제했습니다. 변경된 내용으로 요구사항을 다시 확인합니다.')
    setTimeout(()=>buildConfirmedRequirementsFromChat(nextChat),0)
  }

  const clearRestoredRequirementContent=()=>{
    const accepted=window.confirm(
      '이 프로젝트 경로에 저장된 지난 대화와 수집 요구사항을 모두 삭제하고 처음부터 다시 정의할까요?\n\n프로젝트 파일 자체는 삭제되지 않습니다.'
    )
    if(!accepted) return

    try{ localStorage.removeItem(requirementDraftKey()) }catch{}
    setChat([{
      role:'assistant',
      content:'기존 요구사항을 초기화했습니다. 어떤 AI Agent + MCP 프로그램을 만들고 싶으신가요? 먼저 프로그램의 목적을 한 문장으로 다시 정의해 주세요.'
    }])
    setBuilderStarted(false)
    setInput('')
    setConfirmedInterviewRequirements({})
    setRequirementManualOverrides({})
    setRequirementRedefineId('')
    setRequirementRedefineText('')
    const attachmentIdsToRelease=(interviewAttachments||[]).map(item=>item?.attachment_id).filter(Boolean)
    if(attachmentIdsToRelease.length){
      void api('/ai/attachments/release',{
        method:'POST',
        body:JSON.stringify({attachment_ids:attachmentIdsToRelease})
      }).catch(()=>{})
    }
    setInterviewAttachments([])
    setInterviewAttachmentMemory('')
    setInterviewAttachmentSummary('')
    setInterviewAttachmentSummaryFiles([])
    setInterviewAttachmentSummaryError('')
    interviewAttachmentSummaryRunRef.current=''
    setRequirementDraftRestored(false)
    setRequirementDraftSavedAt('')
    setRequirementDraftCandidate(null)
    setRequirementDraftDecisionPending(false)
    requirementDraftDecisionPendingRef.current=false
    setRestoredBuildResume(null)
    requirementCheckpointSignatureRef.current=''
    setPreviousTargetWorkflowPreview(null)
    invalidateRequirementWorkflowAfterEdit('지난 요구사항을 삭제했습니다. 새 요구사항을 다시 정의해 주세요.')
  }

  const beginRequirementRedefinition=(id,value='')=>{
    setRequirementRedefineId(String(id||''))
    setRequirementRedefineText(
      String(requirementManualOverrides?.[id]||value||'')
    )
  }

  const cancelRequirementRedefinition=()=>{
    setRequirementRedefineId('')
    setRequirementRedefineText('')
  }

  const saveRequirementRedefinition=()=>{
    const id=String(requirementRedefineId||'').trim()
    const value=String(requirementRedefineText||'').trim()
    if(!id||!value) return
    const def=requirementKeywordDefinitions.find(item=>item.id===id)
    const nextOverrides={...(requirementManualOverrides||{}),[id]:value}
    setRequirementManualOverrides(nextOverrides)
    setChat(prev=>[
      ...prev.filter(item=>item?.requirement_override!==id),
      {
        role:'user',
        content:`요구사항 재정의 - ${def?.label||id}: ${value}. 이 내용을 이전 대화보다 최신 기준으로 적용해 주세요.`,
        requirement_override:id
      }
    ])
    setConfirmedInterviewRequirements(prev=>({
      ...(prev||{}),
      manual_overrides:nextOverrides
    }))
    invalidateRequirementWorkflowAfterEdit(`${def?.label||id} 요구사항을 재정의했습니다. 변경된 기준으로 Workflow를 다시 설계할 수 있습니다.`)
    cancelRequirementRedefinition()
  }

  const getDetectedAgentFeatureNames=()=>{
    const text=requirementConversationText()
    const names=[]
    const add=(label,...keywords)=>{
      if(keywords.some(keyword=>text.includes(String(keyword).toLowerCase()))&&!names.includes(label)) names.push(label)
    }
    add('회원 로그인 / 인증','회원','로그인','인증','auth')
    add('권한 / RBAC','권한','rbac','role','permission')
    add('자연어 검색','자연어','semantic search','의미 기반')
    add('Hybrid Search','hybrid','pgvector','벡터 검색','vector search')
    add('상품 추천','상품 추천','추천 상품','recommend')
    add('상품 관리','상품','product','catalog')
    add('재고 확인','재고','inventory')
    add('장바구니','장바구니','cart')
    add('주문 처리','주문','order')
    add('RAG','rag','faq','knowledge base','지식베이스')
    add('파일 분석','파일 분석','첨부 파일','문서 분석')
    add('코드 편집','코드 편집','코드 수정')
    add('리포트','리포트','보고서')
    add('대화 / 상담','대화','상담','챗봇')
    add('관리자 화면','관리자','admin')
    return names
  }

  const designProjectProgressInfo=()=>{
    const total=getRequirementKeywordStatus().length||1
    const collected=getRequirementKeywordStatus().filter(item=>item.collected).length
    let progress=Math.round((collected/total)*55)
    let status='INTERVIEWING'
    if(targetWorkflowLoading){ status='DESIGNING'; progress=Math.max(progress,65) }
    else if(agentBuildBusy||projectCreateFlowBusy){ status='GENERATING'; progress=Math.max(progress,80) }
    else if(agentBuildStage==='PROJECT_CREATED'){ status='READY_TO_GENERATE'; progress=Math.max(progress,75) }
    else if(targetWorkflowPreview){ status='READY_TO_GENERATE'; progress=Math.max(progress,70) }
    if(developmentFinalStatus?.ok===true){ status='GENERATED'; progress=100 }
    if(developmentFinalStatus?.ok===false){ status='FAILED'; progress=Math.max(progress,80) }
    return {status,progress:Math.max(0,Math.min(100,progress))}
  }

  const saveAgentDesignProject=async({createVersion=false,versionLabel=''}={})=>{
    if(designProjectSaving) return null
    const snapshot=buildRequirementDraftSnapshot()
    const hasUserContent=(snapshot.chat||[]).some(item=>item?.role==='user')
      ||Boolean(snapshot.workflow_request)
      ||Boolean(snapshot.agent_name)
      ||(Array.isArray(snapshot.feature_registry)&&snapshot.feature_registry.length>0)
    if(!hasUserContent){
      setAgentBuildMessage('먼저 Agent 이름이나 설계 인터뷰 내용을 입력해 주세요.')
      return null
    }
    const currentAssistant=[...(chat||[])].reverse().find(item=>item?.role==='assistant')
    const {status,progress}=designProjectProgressInfo()
    setDesignProjectSaving(true)
    try{
      const result=await api('/agent-design-projects/save',{
        method:'POST',
        body:JSON.stringify({
          id:designProjectId||null,
          name:String(newAgentName||'').trim()||String(getBuilderConversationSummary()?.purpose||'').trim()||'새 Agent 설계',
          project_root:String(newAgentProjectRoot||'').trim(),
          status,
          progress,
          current_stage:agentBuildStage||'REQUIREMENTS',
          current_question:currentAssistant?String(currentAssistant.content||''):'',
          langgraph_thread_id:designProjectId?`agent_design_${designProjectId}`:'',
          snapshot,
          feature_registry:designFeatureRegistry||[],
          create_version:Boolean(createVersion),
          version_label:String(versionLabel||'')
        })
      })
      const project=result?.project
      if(project){
        setDesignProjectId(project.id)
        setDesignProjectSavedAt(project.updated_at||new Date().toISOString())
        setDesignProjectVersion(project.version_no||1)
        setRequirementDraftSavedAt(project.updated_at||snapshot.saved_at)
        setAgentBuildMessage(createVersion
          ? `설계 프로젝트 v${project.version_no||1} 저장 완료 · 변경 전 Snapshot을 보존했습니다.`
          : 'Agent 설계 프로젝트를 저장했습니다. 다른 작업 후 프로젝트 목록에서 다시 열어 이어서 진행할 수 있습니다.')
      }
      return project||null
    }catch(e){
      setAgentBuildMessage('설계 프로젝트 저장 실패: '+String(e?.message||e))
      return null
    }finally{
      setDesignProjectSaving(false)
    }
  }

  const loadAgentDesignProject=async(project)=>{
    const snapshot=project?.snapshot&&typeof project.snapshot==='object'?project.snapshot:{}
    startNewProject()
    setDesignProjectId(project?.id||null)
    setDesignProjectSavedAt(project?.updated_at||snapshot?.saved_at||'')
    setDesignProjectVersion(project?.version_no||snapshot?.design_project_version||1)
    setDesignFeatureRegistry(Array.isArray(project?.feature_registry)?project.feature_registry:(Array.isArray(snapshot?.feature_registry)?snapshot.feature_registry:[]))
    setNewAgentName(String(snapshot?.agent_name||project?.name||''))
    setNewAgentProjectRoot(String(snapshot?.project_root||project?.project_root||''))
    setWorkflowReq(String(snapshot?.workflow_request||''))
    const restoredChat=Array.isArray(snapshot?.chat)&&snapshot.chat.length?snapshot.chat:[{
      role:'assistant',
      content:'저장된 Agent 설계 프로젝트를 불러왔습니다. 마지막 설계 상태부터 이어서 진행해 주세요.'
    }]
    setChat(restoredChat)
    setBuilderStarted(restoredChat.some(item=>item?.role==='user'))
    setConfirmedInterviewRequirements(snapshot?.confirmed_requirements&&typeof snapshot.confirmed_requirements==='object'?snapshot.confirmed_requirements:{})
    setTargetWorkflowPreview(snapshot?.workflow_preview||null)
    setPreviousTargetWorkflowPreview(snapshot?.workflow_preview||null)
    setTargetWorkflowQuality(snapshot?.workflow_quality||null)
    setAgentBuildStage(snapshot?.agent_build_stage||project?.current_stage||'REQUIREMENTS')
    setInterviewAttachmentMemory(snapshot?.attachment_memory||'')
    setInterviewAttachmentSummary(snapshot?.attachment_summary||'')
    setInterviewAttachmentSummaryFiles(Array.isArray(snapshot?.attachment_summary_files)?snapshot.attachment_summary_files:[])
    setInterviewAttachmentRequirements(Array.isArray(snapshot?.attachment_requirements)?snapshot.attachment_requirements:[])
    setInterviewAttachmentRequirementCoverage(snapshot?.attachment_requirement_coverage&&typeof snapshot.attachment_requirement_coverage==='object'?snapshot.attachment_requirement_coverage:{})
    setRequirementManualOverrides(snapshot?.manual_requirement_overrides&&typeof snapshot.manual_requirement_overrides==='object'?snapshot.manual_requirement_overrides:{})
    setUiLayoutConfig(snapshot?.ui_layout&&typeof snapshot.ui_layout==='object'?snapshot.ui_layout:null)
    setRequirementDraftRestored(true)
    setRequirementDraftSavedAt(project?.updated_at||snapshot?.saved_at||'')
    setAgentBuildMessage(`설계 프로젝트 #${project?.id||''}을 불러왔습니다. 이전 인터뷰와 기능 정의를 이어서 진행합니다.`)
  }

  const handleDesignFeatureChange=async(action,item,payload={})=>{
    const now=new Date().toISOString()
    const existingName=String(item?.name||'').trim()
    const nextName=String(payload?.name||existingName||'').trim()
    if(!nextName) return

    if(action==='REMOVE'&&designProjectId){
      await saveAgentDesignProject({
        createVersion:true,
        versionLabel:`${existingName||nextName} 기능 삭제 전 자동 Snapshot`
      })
    }else if(['ADD','MODIFY','DISABLE'].includes(action)&&designProjectId){
      await saveAgentDesignProject({
        createVersion:true,
        versionLabel:`${existingName||nextName} 기능 ${action==='ADD'?'추가':action==='MODIFY'?'수정':'비활성화'} 전 Snapshot`
      })
    }

    setDesignFeatureRegistry(prev=>{
      const list=Array.isArray(prev)?[...prev]:[]
      const targetName=String(existingName||nextName).trim().toLowerCase()
      const index=list.findIndex(feature=>String(feature?.name||'').trim().toLowerCase()===targetName)
      const base=index>=0?list[index]:{
        id:`feature_${Date.now()}_${Math.random().toString(36).slice(2,7)}`,
        name:existingName||nextName,
        source:item?.source==='DISCOVERED'?'DISCOVERED':'MANUAL',
        created_at:now,
      }
      const status=action==='REMOVE'?'REMOVED':action==='DISABLE'?'DISABLED':'ACTIVE'
      const changed={
        ...base,
        original_name:base.original_name||existingName||nextName,
        name:nextName,
        description:String(payload?.description??base.description??''),
        status,
        change_type:action,
        impact:Array.isArray(payload?.impact)?payload.impact:base.impact||[],
        updated_at:now,
      }
      if(index>=0) list[index]=changed
      else list.push(changed)
      return list
    })

    const actionLabel={ADD:'기능 추가',MODIFY:'기능 수정/재정의',DISABLE:'기능 비활성화',REMOVE:'기능 삭제',RESTORE:'기능 복원'}[action]||'기능 변경'
    const impactText=Array.isArray(payload?.impact)&&payload.impact.length?` 영향 영역: ${payload.impact.join(', ')}.`:''
    setChat(prev=>[...prev,{
      role:'user',
      content:`${actionLabel} - ${nextName}${payload?.description?`: ${payload.description}`:''}.${impactText} 이 변경을 최신 요구사항으로 적용하고, 관련 UI/API/DB/권한/Workflow/테스트에 미치는 영향만 추가로 확인해 주세요. 기존에 확정된 다른 요구사항은 유지해 주세요.`,
      feature_change:true,
      feature_name:nextName,
      feature_action:action,
    }])
    setConfirmedInterviewRequirements(prev=>({
      ...(prev||{}),
      feature_registry:[...(designFeatureRegistry||[])]
    }))
    invalidateRequirementWorkflowAfterEdit(`${nextName} ${actionLabel}이 반영되었습니다. 변경된 기능의 영향도를 기준으로 Workflow를 증분 재설계할 수 있습니다.`)
  }

  useEffect(()=>{
    if(!designProjectId||designProjectSaving||requirementDraftDecisionPending) return undefined
    const timer=setTimeout(()=>{
      void saveAgentDesignProject()
    },1200)
    return()=>clearTimeout(timer)
  },[
    designProjectId,
    chat,
    designFeatureRegistry,
    confirmedInterviewRequirements,
    targetWorkflowPreview,
    targetWorkflowQuality,
    agentBuildStage,
    newAgentName,
    newAgentProjectRoot,
    uiLayoutConfig,
    requirementManualOverrides
  ])

  const buildRequirementRequestFromCollectedInfo=()=>{
    const userMessages=(chat||[])
      .filter(item=>item?.role==='user')
      .map(item=>String(item?.content||'').trim())
      .filter(Boolean)

    const confirmed=confirmedInterviewRequirements||{}
    const rows=[]

    if(userMessages.length){
      rows.push(userMessages.join('\n\n'))
    }else if(workflowReq?.trim()){
      rows.push(workflowReq.trim())
    }else{
      if(confirmed.original_request){
        rows.push(confirmed.original_request)
      }
      if(confirmed.ui){
        rows.push(`UI: ${confirmed.ui}`)
      }
      if(confirmed.backend){
        rows.push(`Backend: ${confirmed.backend}`)
      }
      if(confirmed.llm){
        rows.push(
          `LLM: ${confirmed.llm.default_provider||''} ${confirmed.llm.default_model||''}; Ollama 전환 가능`
        )
      }
      if(confirmed.file_access?.allowed_extensions?.length){
        rows.push(
          `파일 형식: ${confirmed.file_access.allowed_extensions.join(', ')}`
        )
      }
      if(confirmed.mcp){
        rows.push(
          `MCP: ${confirmed.mcp.default_transport||'stdio'}`
        )
      }
      if(confirmed.database){
        rows.push(
          `DB: ${confirmed.database.enabled?'사용':'현재 미사용'}`
        )
      }
    }

    if(interviewAttachmentSummary?.trim()){
      rows.push(
        '[첨부 파일에서 파악한 요구사항 요약]\n'+interviewAttachmentSummary.trim()
      )
    }
    if(Array.isArray(interviewAttachmentRequirements)&&interviewAttachmentRequirements.length){
      rows.push(
        '[첨부 파일 Deep Requirement Registry - 명시적 문서 요구사항 우선]\n'
        +interviewAttachmentRequirements.slice(0,80).map(item=>
          `${item?.id||'REQ'} [${item?.category||'FUNCTIONAL'}] ${String(item?.text||'').trim()}${item?.source?` (출처: ${item.source}${item?.location?` / ${item.location}`:''})`:''}`
        ).filter(Boolean).join('\n')
      )
    }

    if(uiLayoutConfig?.template_id){
      rows.push(
        '[사용자가 선택한 UI / Layout 설계 - 코드 생성 시 반드시 반영]\n'
        +JSON.stringify(uiLayoutConfig,null,2)
      )
    }

    const manualRows=Object.entries(requirementManualOverrides||{})
      .map(([id,value])=>{
        const text=String(value||'').trim()
        if(!text) return ''
        const def=requirementKeywordDefinitions.find(item=>item.id===id)
        return `- ${def?.label||id}: ${text}`
      })
      .filter(Boolean)
    if(manualRows.length){
      rows.push(
        '[사용자가 직접 재정의한 최신 요구사항 - 이전 대화보다 우선]\n'+manualRows.join('\n')
      )
    }

    const featureRows=(designFeatureRegistry||[])
      .map(feature=>{
        const name=String(feature?.name||'').trim()
        if(!name) return ''
        const status=String(feature?.status||'ACTIVE').toUpperCase()
        const action=String(feature?.change_type||'BASE').toUpperCase()
        const description=String(feature?.description||'').trim()
        return `- ${name} | 상태=${status} | 변경=${action}${description?` | ${description}`:''}`
      })
      .filter(Boolean)
    if(featureRows.length){
      rows.push(
        '[기능 관리 Registry - 최신 기능 추가/수정/비활성화/삭제 상태, 이전 요구사항보다 우선]\n'
        +featureRows.join('\n')
        +'\nREMOVED 기능은 신규 설계/생성 대상에서 제거하고, DISABLED 기능은 코드/DB 삭제 없이 비활성화 상태로 유지합니다. 관련 없는 기존 기능은 변경하지 않습니다.'
      )
    }

    return rows.filter(Boolean).join('\n\n')
  }

  useEffect(()=>{
    // v5.360: 사용자 인터뷰 응답을 가장 먼저 반환합니다. 대화 LLM 처리 중에는
    // DB 초안 재계산을 시작하지 않고, 응답이 화면에 표시된 뒤 Background Preview로 갱신합니다.
    if(busy||interviewAttachmentSummaryBusy){
      return undefined
    }

    const requestText=buildRequirementRequestFromCollectedInfo().trim()
    const hasUserRequirement=Boolean(
      requestText
      &&((chat||[]).some(item=>item?.role==='user')||workflowReq?.trim()||interviewAttachmentSummary?.trim())
    )

    if(!hasUserRequirement){
      setLiveDatabasePreview(null)
      setLiveDatabasePreviewError('')
      setLiveDatabasePreviewLoading(false)
      return undefined
    }

    let cancelled=false
    const timer=setTimeout(async()=>{
      setLiveDatabasePreviewLoading(true)
      setLiveDatabasePreviewError('')
      try{
        const result=await api('/database-design/preview',{
          method:'POST',
          body:JSON.stringify({
            request:requestText,
            confirmed_requirements:buildConfirmedRequirementsFromChat()
          })
        })
        if(cancelled) return
        setLiveDatabasePreview({
          ...(result?.database_plan||{}),
          ddl_preview:String(result?.ddl_preview||'')
        })
      }catch(error){
        if(cancelled) return
        setLiveDatabasePreviewError(String(error))
      }finally{
        if(!cancelled) setLiveDatabasePreviewLoading(false)
      }
    },900)

    return ()=>{
      cancelled=true
      clearTimeout(timer)
    }
  },[chat,workflowReq,confirmedInterviewRequirements,requirementManualOverrides,interviewAttachmentSummary,interviewAttachmentRequirements,busy,interviewAttachmentSummaryBusy])

  const canDesignFromCollectedInfo=()=>{
    const statuses=getRequirementKeywordStatus()
    const collectedCount=statuses.filter(x=>x.collected).length
    return Boolean(
      workflowReq?.trim()
      || (chat||[]).some(item=>item?.role==='user')
      || collectedCount>=3
      || targetWorkflowPreview
    )
  }


  const buildConfirmedRequirementsFromChat=(sourceChat=chat)=>{
    const userMessages=(sourceChat||[])
      .filter(item=>item?.role==='user')
      .map(item=>String(item?.content||'').trim())
      .filter(Boolean)

    const assistantMessages=(sourceChat||[])
      .filter(item=>item?.role==='assistant')
      .map(item=>String(item?.content||'').trim())
      .filter(Boolean)

    const manualRequirementLines=Object.entries(requirementManualOverrides||{})
      .map(([id,value])=>{
        const def=requirementKeywordDefinitions.find(item=>item.id===id)
        return `${def?.label||id}: ${String(value||'')}`
      })
    const allText=[
      ...userMessages,
      ...assistantMessages,
      interviewAttachmentSummary||'',
      ...(interviewAttachmentRequirements||[]).map(item=>String(item?.text||'')),
      uiLayoutConfig?.template_id?uiLayoutSummary(uiLayoutConfig):'',
      ...manualRequirementLines,
      ...(designFeatureRegistry||[]).map(feature=>`${feature?.name||''} ${feature?.description||''} ${feature?.status||''} ${feature?.change_type||''}`)
    ].join('\n').toLowerCase()

    const has=(...values)=>values.some(value=>
      allText.includes(String(value).toLowerCase())
    )

    const extensions=[
      has('.txt')?'.txt':'',
      has('.md')?'.md':'',
      has('.py')?'.py':''
    ].filter(Boolean)

    const requirements={
      original_request:String(requirementManualOverrides?.purpose||'').trim()||userMessages[0]||workflowReq||interviewAttachmentSummary||'',
      user_answers:userMessages.slice(1),
      latest_analysis:
        [...assistantMessages]
          .reverse()
          .find(text=>text.includes('요구사항 분석 완료'))||'',

      ui:has('streamlit')
        ? 'Streamlit'
        : has('react')
          ? (has('vite')?'React + Vite':'React 기반 웹 GUI')
          : '',
      ui_layout:uiLayoutConfig?.template_id?{...uiLayoutConfig}:null,

      backend:has('fastapi')
        ? (has('uvicorn')?'FastAPI + Uvicorn':'FastAPI')
        : '',

      llm:{
        default_provider:has('openai')?'OpenAI':'',
        default_model:has('gpt-4o-mini')?'gpt-4o-mini':'',
        configurable_provider:has(
          'provider',
          '설정 파일',
          '환경변수',
          '.env'
        ),
        ollama_supported:has('ollama')
      },

      file_access:{
        allowed_extensions:
          extensions.length
            ? extensions
            : ['.txt','.md','.py'],
        restrict_to_project_root:has(
          'project root 내부',
          '프로젝트 root 내부',
          'root 내부'
        ),
        user_select_or_input:has(
          '파일을 선택',
          '파일 선택',
          '파일을 지정',
          '파일 경로'
        )
      },

      mcp:{
        default_transport:has('stdio')?'stdio':'',
        future_transport:has('streamable http')
          ? 'streamable_http'
          : '',
        transport_layer_separated:has(
          'transport 계층',
          'transport를 분리',
          'transport 계층을 분리'
        )
      },

      database:{
        enabled:!(
          has(
            '데이터베이스를 사용하지',
            'db 사용하지',
            '이번 버전에서는 db',
            '이번 버전에서는 데이터베이스'
          )
        ),
        future_extension:has('postgresql')
      },

      result:{
        ui_display:has(
          'react 웹 ui',
          'react ui',
          '웹 ui'
        ),
        language:has('한국어')?'ko':'',
        api_format:has('json')?'json':'',
        export_formats:[
          has('.txt','txt 파일')?'txt':'',
          has('.md','md 파일')?'md':''
        ].filter(Boolean)
      },

      processing:{
        max_file_size_mb:has('10mb','10 mb')?10:null,
        timeout_seconds:has('120초','120 second','120s')?120:null,
        chunking:has('chunk','청크')
      },

      runtime:{
        os:has('windows 10/11','windows 10','windows 11')
          ? 'Windows 10/11'
          : '',
        python:has('python 3.12')?'3.12':'',
        virtual_env:has('.venv','가상환경')?'.venv':'',
        deployment:has('온프레미스')?'on-premise':''
      },

      auth:{
        enabled:!(
          has(
            '별도의 사용자 인증',
            '사용자 인증이나 역할 기반 권한 관리',
            'rbac는 사용하지'
          )
        ),
        rbac:false
      },
      attachment_summary:interviewAttachmentSummary||'',
      attachment_requirements:(interviewAttachmentRequirements||[]).slice(0,120),
      attachment_requirement_coverage:interviewAttachmentRequirementCoverage||{},
      manual_overrides:{...(requirementManualOverrides||{})},
      feature_registry:(designFeatureRegistry||[]).map(feature=>({...feature}))
    }

    setConfirmedInterviewRequirements(requirements)
    return requirements
  }


  const isBuildContinueCommand=(text='')=>{
    const value=String(text||'')
      .trim()
      .replace(/[.!?]+$/g,'')
      .replace(/\s+/g,' ')

    return [
      '진행',
      '진행해',
      '진행해줘',
      '이대로 진행',
      '이대로 진행해',
      '이대로 진행해줘',
      '프로젝트 생성',
      '개발 시작',
      '개발해줘',
      '만들어줘',
      '생성해줘'
    ].includes(value)
  }

  const finalizeDatabaseDesign=async()=>{
    const plan=targetWorkflowPreview?.database_plan||{}
    if(!plan?.enabled){
      setTargetWorkflowPreview(prev=>prev?{...prev,database_plan:{...plan,confirmed:true,finalized:true}}:prev)
      return true
    }
    if(databaseDesignFinalizeBusy) return false
    setDatabaseDesignFinalizeBusy(true)
    setAgentBuildMessage('DB Module/Entity/PK/FK를 검증하고 PostgreSQL DDL을 생성하고 있습니다...')
    try{
      const result=await api('/database-design/finalize',{
        method:'POST',
        body:JSON.stringify({database_plan:plan})
      })
      if(!result?.ok){
        const errors=(result?.validation?.errors||[]).join('\n')
        throw new Error(errors||result?.message||'DB 설계 검증 실패')
      }
      const finalized=result.database_plan||plan
      const migrationFiles=(finalized?.migration_files||[])
        .map(item=>({
          path:String(item?.path||''),
          purpose:String(item?.purpose||'확정된 PostgreSQL DB Migration'),
          required:false,
          component:'Database Migration'
        }))
        .filter(item=>item.path)
      setTargetWorkflowPreview(prev=>{
        if(!prev) return prev
        const filePlan={...(prev.file_plan||{})}
        const current=Array.isArray(filePlan.new_files)?[...filePlan.new_files]:[]
        const known=new Set(current.map(item=>String(item?.path||item||'').replace(/\\/g,'/').toLowerCase()))
        for(const item of migrationFiles){
          const key=item.path.replace(/\\/g,'/').toLowerCase()
          if(!known.has(key)){
            current.push(item)
            known.add(key)
          }
        }
        filePlan.new_files=current
        return {...prev,database_plan:finalized,file_plan:filePlan}
      })
      setAgentBuildMessage(`DB 설계 확정 완료 · Module ${(finalized.modules||[]).length}개 · Table ${(finalized.tables||[]).length}개 · Migration 준비 완료`)
      setTimeout(()=>saveRequirementDraft(),0)
      return true
    }catch(e){
      setAgentBuildMessage(`DB 설계 확정 실패: ${String(e)}`)
      return false
    }finally{
      setDatabaseDesignFinalizeBusy(false)
    }
  }


  const createAgentProjectFromInterview=async()=>{
    const name=newAgentName.trim()
    const projectRoot=newAgentProjectRoot.trim()

    if(!name){
      setAgentBuildMessage('에이전트 이름을 먼저 입력하세요.')
      return false
    }

    if(!projectRoot){
      setAgentBuildMessage('프로젝트 경로를 먼저 입력하거나 경로 찾기로 선택하세요.')
      return false
    }

    const requestCreate=async(forceRecreate=false)=>{
      return await api('/projects/create-agent',{
        method:'POST',
        body:JSON.stringify({
          name,
          project_root:projectRoot,
          cache_path:newAgentCachePath,
          temp_path:newAgentTempPath,
          output_path:newAgentOutputPath,
          venv_path:newAgentVenvPath,
          models_path:newAgentModelsPath,
          force_recreate:forceRecreate,
          database_plan:targetWorkflowPreview?.database_plan||{}
        })
      })
    }

    setAgentBuildBusy(true)
    setAgentBuildMessage('프로젝트 폴더와 프로젝트 정보를 생성하고 있습니다...')

    try{
      let result=await requestCreate(false)

      if(
        result?.ok===false
        && result?.conflict_type==='PROJECT_PATH_ALREADY_REGISTERED'
        && result?.can_recreate
      ){
        const recreate=window.confirm(
          '이미 등록된 프로젝트 경로입니다.\\n\\n'
          +'기존 DB 프로젝트 정보를 재사용하고 이 경로에 Agent를 재생성하시겠습니까?\\n\\n'
          +'[확인] 재생성\\n'
          +'[취소] 신규 Agent 설계 화면에서 경로 변경'
        )

        if(!recreate){
          setNewAgentCreateResult(result)
          setAgentBuildMessage(
            '프로젝트 재생성을 취소했습니다. 경로를 변경하려면 "신규 Agent 설계" 버튼을 이용하세요.'
          )
          return false
        }

        setAgentBuildMessage('기존 프로젝트를 재사용하여 재생성 준비 중입니다...')
        result=await requestCreate(true)
      }

      setNewAgentCreateResult(result)

      if(!result?.ok){
        throw new Error(result?.message||'프로젝트 생성에 실패했습니다.')
      }

      const resolvedRoot=result.project_root||projectRoot

      setSelectedProjectId(result.project_id||null)
      setRoot(resolvedRoot)
      setAgentBuildStage('PROJECT_CREATED')
      const databaseFileCount=Array.isArray(result?.database_files)?result.database_files.length:0
      setAgentBuildMessage(
        (result?.recreated
          ? `프로젝트 재생성 준비 완료${result.project_id?` · Project #${result.project_id}`:''}`
          : `프로젝트 생성 완료${result.project_id?` · Project #${result.project_id}`:''}`)
        +(databaseFileCount?` · DB Migration ${databaseFileCount}개 생성`:'')
      )

      try{ await refreshProjectList() }catch(_){}
      try{ await loadFiles(resolvedRoot) }catch(_){}

      return true
    }catch(e){
      setAgentBuildMessage(`프로젝트 생성 실패: ${String(e)}`)
      return false
    }finally{
      setAgentBuildBusy(false)
      setActiveWorkflowJobId('')
    }
  }

  const createAgentProjectSmart=async()=>{
    if(projectCreateFlowBusy||agentBuildBusy||targetWorkflowLoading) return false

    if(!newAgentName.trim()){
      setAgentBuildMessage('프로젝트 생성 전 에이전트 이름을 입력하세요.')
      return false
    }
    if(!newAgentProjectRoot.trim()){
      setAgentBuildMessage('프로젝트 생성 전 프로젝트 경로를 입력하거나 경로 찾기로 선택하세요.')
      return false
    }

    setProjectCreateFlowBusy(true)
    try{
      let workflowResult=null
      if(agentBuildStage==='REQUIREMENTS'){
        setAgentBuildMessage('프로젝트 생성에 필요한 Workflow와 DB Module 설계를 먼저 자동 분석하고 있습니다...')
        workflowResult=await previewTargetWorkflow()
        if(!workflowResult){
          setAgentBuildMessage('Workflow 설계가 완료되지 않아 프로젝트 생성을 중단했습니다. 위 오류를 확인한 뒤 다시 시도하세요.')
          return false
        }
      }

      const databasePlan=workflowResult?.database_plan||targetWorkflowPreview?.database_plan||{}
      if(databasePlan?.enabled&&!databasePlan?.finalized){
        setAgentBuildMessage('DB 설계 확인이 필요합니다. Workflow 화면의 DB 자동 설계에서 Module/테이블을 확인한 뒤 "DB 설계 확정"을 눌러주세요.')
        setScreen('WORKSPACE')
        setWorkspaceTab('WORKFLOW')
        setWorkflowView('TARGET')
        return false
      }

      if(agentBuildStage==='BUILDING'){
        setAgentBuildMessage('현재 Agent 개발이 진행 중이므로 새 프로젝트 생성을 시작할 수 없습니다.')
        return false
      }

      setAgentBuildMessage('Workflow/DB 설계 준비 완료 · 프로젝트 폴더와 DB 정보를 생성합니다...')
      return await createAgentProjectFromInterview()
    }finally{
      setProjectCreateFlowBusy(false)
    }
  }


  const runProjectCodingStyleValidation=async(projectRoot)=>{
    const rootPath=(projectRoot||root||newAgentProjectRoot||'').trim()

    if(!rootPath){
      return null
    }

    try{
      const rows=await api(`/files?root=${encodeURIComponent(rootPath)}`)
      const fileRows=Array.isArray(rows)?rows:(rows?.files||[])
      const codeFiles=fileRows.filter(item=>{
        const path=typeof item==='string'?item:(item?.path||item?.full_path||'')
        return /\.(py|js|jsx|ts|tsx)$/i.test(path)
      }).slice(0,80)

      const results=[]

      for(const item of codeFiles){
        const path=typeof item==='string'?item:(item?.path||item?.full_path||'')
        if(!path) continue

        try{
          const file=await api(`/file?path=${encodeURIComponent(path)}`)
          const content=typeof file==='string'?file:(file?.content||'')

          const validation=await api('/coding-style/validate',{
            method:'POST',
            body:JSON.stringify({
              code:content,
              request:workflowReq||'',
              path,
              project_scope:true
            })
          })

          results.push({
            path,
            ok:validation?.ok!==false,
            violations:validation?.violations||[]
          })
        }catch(_){}
      }

      const violations=results.flatMap(row=>
        (row.violations||[]).map(item=>({
          ...item,
          path:row.path
        }))
      )

      const fail=violations.filter(item=>String(item?.severity||'').toLowerCase()==='error')
      const warning=violations.filter(item=>String(item?.severity||'').toLowerCase()==='warning')

      const report={
        checked_files:results.length,
        pass:Math.max(0,results.length-fail.length),
        warning:warning.length,
        fail:fail.length,
        violations,
        ok:fail.length===0
      }

      setCodingStyleReport(report)
      setReportGeneratedAt(new Date().toISOString())
      return report
    }catch(e){
      const report={
        checked_files:0,
        pass:0,
        warning:0,
        fail:1,
        violations:[{
          severity:'error',
          message:`코딩 스타일 검증 실행 실패: ${String(e)}`
        }],
        ok:false
      }
      setCodingStyleReport(report)
      return report
    }
  }

  const ensureGpuAccelerationForPhase=async({request='',phase='development',actionLabel='작업'}={})=>{
    let recommendation=null
    try{
      recommendation=await api('/settings/gpu/recommendation',{
        method:'POST',
        body:JSON.stringify({
          request:String(request||''),
          confirmed_requirements:confirmedInterviewRequirements||{},
          ai_mode:String(aiRuntimeStatus?.mode||''),
          phase
        })
      })
    }catch(_){
      // GPU 상태 확인 실패 때문에 일반 CPU 작업까지 차단하지 않습니다.
      return true
    }

    if(!recommendation?.recommended) return true
    const gpu=recommendation?.gpu||{}
    if(gpu?.enabled) return true

    const reasons=(recommendation?.reasons||[]).filter(Boolean)
    const reasonText=reasons.length?`\n\n권장 사유\n- ${reasons.join('\n- ')}`:''

    if(!gpu?.available){
      return window.confirm(
        `${actionLabel}은 GPU 가속 사용을 권장하는 작업입니다.${reasonText}\n\n`+
        '현재 지원되는 NVIDIA GPU를 감지하지 못했습니다.\nCPU 모드로 계속 진행하시겠습니까?'
      )
    }

    const accepted=window.confirm(
      `${actionLabel}은 GPU 가속 사용을 권장하는 작업입니다.${reasonText}\n\n`+
      '[확인]을 누르면 AgentStudio GPU 가속을 시작한 뒤 계속 진행합니다.\n'+
      '[취소]를 누르면 현재 작업을 시작하지 않습니다.'
    )
    if(!accepted) return false

    setAgentBuildMessage('GPU 가속을 시작하고 실행 환경을 준비하고 있습니다...')
    try{
      const started=await api('/settings/gpu/runtime/start',{method:'POST'})
      if(!started?.ok){
        window.alert(`GPU 가속을 시작하지 못했습니다.\n${started?.message||'GPU 상태를 확인해 주세요.'}`)
        return false
      }
      const ollamaMessage=started?.ollama?.message?` · ${started.ollama.message}`:''
      setAgentBuildMessage(`GPU 가속 준비 완료${ollamaMessage}`)
      return true
    }catch(e){
      window.alert(`GPU 가속 시작 실패: ${String(e)}`)
      return false
    }
  }

  const cancelAgentDevelopment=async()=>{
    const jobId=activeWorkflowJobId
    if(!jobId) return
    try{
      await api(`/jobs/${encodeURIComponent(jobId)}/cancel`,{method:'POST'})
      setAgentBuildMessage('Agent 개발 실행 중지 요청을 보냈습니다.')
      setDevelopmentProgress(prev=>({...prev,active:false,stage:'실행 취소',detail:'사용자가 Agent Factory 실행을 중지했습니다.'}))
    }catch(e){
      window.alert(`Agent 개발 실행 중지 실패: ${e}`)
    }
  }

  const startAgentDevelopment=async(options={})=>{
    const redevelopment=options?.redevelopment===true
    const request=(
      workflowReq
      || chat.find(x=>x?.role==='user')?.content
      || ''
    ).trim()

    if(!request&&!redevelopment){
      setAgentBuildMessage('개발 요청 내용이 없습니다.')
      return
    }

    if(!redevelopment){
      if(agentBuildStage==='REQUIREMENTS'){
        setAgentBuildMessage('먼저 대상 Agent Workflow를 설계합니다...')
        await previewTargetWorkflow(request)
        return
      }

      if(agentBuildStage==='WORKFLOW_READY'){
        setAgentBuildMessage('개발 전에 프로젝트를 먼저 생성해야 합니다.')
        return
      }

      if(agentBuildStage!=='PROJECT_CREATED'){
        return
      }

      const databasePlan=targetWorkflowPreview?.database_plan||{}
      if(databasePlan?.enabled&&!databasePlan?.finalized){
        setAgentBuildMessage('DB 설계가 확정되지 않아 개발을 시작하지 않습니다. Workflow 화면에서 DB 설계를 확인/확정해 주세요.')
        setWorkspaceTab('WORKFLOW')
        setWorkflowView('TARGET')
        return
      }
    }else if(!redevelopmentInfo?.available){
      setAgentBuildMessage('재개발 가능한 이전 실패 기록을 찾지 못했습니다. 프로젝트 이름과 경로를 다시 확인해 주세요.')
      return
    }

    const projectRoot=(root||newAgentProjectRoot||'').trim()

    if(!projectRoot){
      setAgentBuildMessage('프로젝트 경로가 없습니다.')
      return
    }

    if(!(await ensureGpuAccelerationForPhase({
      request:request||buildRequirementRequestFromCollectedInfo(),
      phase:'development',
      actionLabel:redevelopment?'재개발 시작':'개발 시작'
    }))){
      setAgentBuildMessage('GPU 권장 안내에서 작업이 취소되었습니다.')
      return
    }

    // v5.166: Frontend만 새 버전이고 이전 Backend가 살아 있는 혼합 실행을 차단합니다.
    // 실제 사용자 로그에서 v5.165 UI가 v5.164 Backend의 /workflow/start를 호출한 사례가 있어
    // Agent Factory 시작 전에 Health Version을 반드시 확인합니다.
    try{
      const health=await api('/health')
      const backendVersion=String(health?.version||'').trim()
      if(backendVersion!==AGENTSTUDIO_FRONTEND_VERSION){
        const message=(
          `AgentStudio 버전이 서로 다릅니다. Frontend v${AGENTSTUDIO_FRONTEND_VERSION} / `+
          `Backend v${backendVersion||'확인 불가'}\n\n`+
          '기존 AgentStudio Backend/Frontend를 모두 종료한 뒤 현재 버전의 SYSTEM_ADMIN.cmd로 다시 실행해 주세요.'
        )
        setAgentBuildMessage(message)
        window.alert(message)
        return
      }
    }catch(e){
      const message=`Backend 버전 확인에 실패했습니다. Agent 개발을 시작하지 않습니다.\n${String(e)}`
      setAgentBuildMessage(message)
      window.alert(message)
      return
    }

    // 개발 시작을 누르면 즉시 실행 결과 탭으로 이동하여
    // Progress/최종 상태/실패 리포트를 같은 화면에서 확인합니다.
    setScreen('WORKSPACE')
    setWorkspaceTab('RUN')

    setAgentBuildBusy(true)
    setAgentBuildStage('BUILDING')
    setDevelopmentFinalStatus(null)
    setAgentBuildMessage(
      redevelopment
        ? `재개발 시작 · 이전 실패 ${redevelopmentInfo?.failure_stage||'-'} 직전 단계(${redevelopmentInfo?.resume_from_node||'-'})부터 이어서 검증합니다...`
        : 'Agent Factory 개발 Workflow를 시작합니다...'
    )

    const startedAt=Date.now()
    const workflowThreadId=`${redevelopment?'redevelop':'agent'}-${Date.now()}`
    let effectiveWorkflowThreadId=workflowThreadId

    setDevelopmentProgress({
      active:true,
      percent:4,
      stage:'개발 준비',
      detail:'프로젝트 경로, 요구사항, Workflow, 설정 정보를 Agent Factory에 전달할 준비를 하고 있습니다.',
      startedAt,
      elapsedSeconds:0,
      events:[]
    })

    let progressTimer=null
    let percent=10

    try{
      setDevelopmentProgress(prev=>({
        ...prev,
        percent:10,
        stage:redevelopment?'재개발 Checkpoint 복원':'Agent Factory 시작',
        detail:redevelopment
          ? `완료된 요구사항/설계는 재사용하고 ${redevelopmentInfo?.resume_from_node||'실패 직전 단계'}부터 이어서 실행합니다.`
          : '설계 결과와 등록된 Coding Style을 개발 Workflow에 전달했습니다.'
      }))

      /*
       * v5.166: 긴 LangGraph 실행은 Background Job을 유지하고, 시작 전 Backend 버전도 검증합니다.
       * Backend Background Job을 시작한 뒤 짧은 /jobs/{id} 조회로 상태를 받습니다.
       * 브라우저/프록시의 장기 연결이 끊겨도 Backend 작업과 진단 파일 생성은 계속됩니다.
       */
      progressTimer=setInterval(()=>{
        const elapsedSeconds=Math.max(
          0,
          Math.floor((Date.now()-startedAt)/1000)
        )

        percent=Math.min(
          88,
          percent+Math.max(
            1,
            Math.round((88-percent)*0.055)
          )
        )

        let stage='Agent Factory 실행 중'
        let detail='요구사항을 실제 프로젝트 코드로 변환하는 Agent Factory가 실행되고 있습니다.'

        if(percent>=30){
          stage='코드 생성 / 검증 진행 중'
          detail='파일 생성·수정, Settings 생성, Coding Style 및 필수 산출물 검증을 수행하는 Workflow 응답을 기다리고 있습니다.'
        }

        if(percent>=58){
          stage='테스트 / 자동 복구 진행 중'
          detail='생성 코드의 테스트, 실패 시 디버그·재생성, 환경 구성 및 검증 결과를 기다리고 있습니다.'
        }

        if(percent>=78){
          stage='패키징 / 최종 검토 진행 중'
          detail='Agent Factory의 최종 산출물·테스트·분석 결과가 반환되기를 기다리고 있습니다.'
        }

        setDevelopmentProgress(prev=>{
          const hasRealEvents=Array.isArray(prev?.events)&&prev.events.length>0
          return {
            ...prev,
            percent:hasRealEvents?Math.max(prev?.percent||0,percent):percent,
            stage:hasRealEvents?prev.stage:stage,
            detail:hasRealEvents?prev.detail:detail,
            elapsedSeconds
          }
        })
      },900)

      const workflowJob=redevelopment
        ? await api('/workflow/redevelop-start-job',{
            method:'POST',
            body:JSON.stringify({
              project_root:projectRoot,
              request,
              test_command:'python -m compileall .',
              provider,
              agent_name:newAgentName||''
            })
          })
        : await api('/workflow/start-job',{
            method:'POST',
            body:JSON.stringify({
              thread_id:workflowThreadId,
              project_root:projectRoot,
              request,
              target_files:[],
              test_command:'python -m compileall .',
              provider,
              design_bundle:{
                ...(targetWorkflowPreview||{}),
                confirmed_requirements:buildConfirmedRequirementsFromChat(),
                interview_messages:(chat||[]).map(item=>({
                  role:item?.role||'',
                  content:item?.content||''
                })),
                interview_context:buildRequirementRequestFromCollectedInfo(),
                previous_build_state:(()=>{
                  const restoredState=(restoredBuildResume?.workflow_state&&typeof restoredBuildResume.workflow_state==='object')
                    ? restoredBuildResume.workflow_state
                    : {}
                  if(Object.keys(restoredState).length && String(restoredBuildResume?.project_root||projectRoot||'')===String(projectRoot||'')){
                    return restoredState
                  }
                  return (
                    ['FULL_REUSE','PARTIAL_REVISE'].includes(String(targetWorkflowPreview?.design_runtime?.incremental_revision?.mode||''))
                    && String(workflow?.state?.project_root||'')===String(projectRoot||'')
                  )?(workflow?.state||{}):{}
                })(),
                resume_context:restoredBuildResume?{
                  run_id:restoredBuildResume.run_id||'',
                  status:restoredBuildResume.status||'',
                  failure_stage:restoredBuildResume.failure_stage||'',
                  failure_reason:restoredBuildResume.failure_reason||'',
                  continue_failed_build:true
                }:{}
              }
            })
          })

      if(!workflowJob?.id){
        throw new Error('Agent Factory Background Job ID를 받지 못했습니다.')
      }
      effectiveWorkflowThreadId=String(workflowJob?.thread_id||workflowThreadId)
      setActiveWorkflowJobId(workflowJob.id)

      let jobState=workflowJob
      let pollNetworkFailures=0

      while(!['SUCCESS','FAILED','CANCELLED'].includes(jobState?.status)){
        await new Promise(resolve=>setTimeout(resolve,1000))

        try{
          jobState=await api(`/jobs/${workflowJob.id}`)
          pollNetworkFailures=0
        }catch(pollError){
          pollNetworkFailures+=1

          if(pollNetworkFailures<8){
            setDevelopmentProgress(prev=>({
              ...prev,
              detail:`Backend Job 상태 연결을 다시 확인하고 있습니다. 재시도 ${pollNetworkFailures}/7`
            }))
            continue
          }

          throw pollError
        }

        if(jobState?.ok===false && jobState?.error==='Job not found'){
          throw new Error(
            'Agent Factory Job을 Backend에서 찾을 수 없습니다. Backend가 실행 중 재시작되었을 가능성이 있습니다.'
          )
        }

        if(Number.isFinite(Number(jobState?.progress))){
          const backendProgress=Math.max(4,Math.min(93,Number(jobState.progress)||0))
          setDevelopmentProgress(prev=>({
            ...prev,
            percent:Math.max(prev?.percent||0,backendProgress),
            stage:jobState?.last_node
              ? `Agent Factory · ${jobState.last_node}`
              : 'Agent Factory Background Job 실행 중',
            detail:jobState?.message||prev?.detail||'Agent Factory가 실행 중입니다.',
            events:Array.isArray(jobState?.events)?jobState.events.slice(-10):(prev?.events||[])
          }))
        }
      }

      if(jobState?.status==='FAILED'){
        const jobError=new Error(
          jobState?.message||jobState?.result?.message||'Agent Factory Background Job 실행 실패'
        )
        jobError.workflowJob=jobState
        throw jobError
      }

      if(jobState?.status==='CANCELLED'){
        throw new Error('Agent Factory Background Job이 취소되었습니다.')
      }

      const result=jobState?.result||{}

      if(progressTimer){
        clearInterval(progressTimer)
        progressTimer=null
      }

      setDevelopmentProgress(prev=>({
        ...prev,
        percent:94,
        stage:'개발 결과 정리',
        detail:'Agent Factory 실행 결과, 생성 파일, 테스트, 디버그 및 사용량 정보를 화면에 반영하고 있습니다.',
        elapsedSeconds:Math.max(
          0,
          Math.floor((Date.now()-startedAt)/1000)
        )
      }))

      setWorkflow(result)

      const workflowState=result?.state||{}
      const status=workflowState?.status||'STARTED'
      const finalStatus=classifyDevelopmentStatus(workflowState)

      setDevelopmentFinalStatus(finalStatus)
      const completedResume={
        source:'AGENT_BUILD',
        run_id:String(result?.thread_id||effectiveWorkflowThreadId||''),
        status:String(finalStatus?.status||workflowState?.status||''),
        failure_stage:String(workflowState?.diagnostic_failure_stage||''),
        failure_reason:String(workflowState?.diagnostic_failure_reason||workflowState?.error||''),
        project_root:projectRoot,
        workflow_state:workflowState
      }
      setRestoredBuildResume(completedResume)
      if(finalStatus.kind==='success'){
        setRedevelopmentInfo(null)
      }else if(finalStatus.kind==='failure'||finalStatus.kind==='action'){
        const failureStage=String(workflowState?.diagnostic_failure_stage||'')
        setRedevelopmentInfo({
          available:true,
          status:String(finalStatus?.status||workflowState?.status||''),
          run_id:String(result?.thread_id||effectiveWorkflowThreadId||''),
          failure_stage:failureStage,
          failure_reason:String(workflowState?.diagnostic_failure_reason||workflowState?.error||''),
          resume_from_node:redevelopmentResumeNodeForFailure(failureStage,finalStatus?.status||workflowState?.status||'')
        })
      }
      saveRequirementDraft(completedResume)

      setAgentBuildMessage(
        finalStatus.kind==='success'
          ? 'Agent 개발 완료'
          : finalStatus.kind==='failure'
            ? 'Agent 개발 실패'
            : finalStatus.kind==='action'
              ? '디버그 조치 필요'
              : finalStatus.kind==='waiting'
                ? '사용자 조치 대기'
                : `개발 Workflow 종료 · 상태: ${status}`
      )

      if(finalStatus.kind==='success'){
        window.alert(
          `Agent 개발이 완료되었습니다.\n\n최종 상태: ${finalStatus.status||status}`
        )
      }else if(finalStatus.kind==='failure'){
        window.alert(
          `Agent 개발에 실패했습니다.\n\n${finalStatus.detail}`
        )
      }else if(finalStatus.kind==='action'){
        window.alert(
          `Agent 개발이 아직 완료되지 않았습니다.\n\n${finalStatus.detail}`
        )
      }

      try{ await loadFiles(projectRoot) }catch(_){}
      try{ await runProjectCodingStyleValidation(projectRoot) }catch(_){}
      try{ await refreshLlmUsage(projectRoot) }catch(_){}

      setDevelopmentProgress(prev=>({
        ...prev,
        active:true,
        percent:100,
        stage:
          finalStatus.kind==='success'
            ? 'Agent 개발 완료'
            : finalStatus.kind==='failure'
              ? 'Agent 개발 실패'
              : finalStatus.kind==='action'
                ? '디버그 조치 필요'
                : finalStatus.kind==='waiting'
                  ? '사용자 조치 대기'
                  : 'Agent Factory 실행 종료',
        detail:finalStatus.detail,
        elapsedSeconds:Math.max(
          0,
          Math.floor((Date.now()-startedAt)/1000)
        )
      }))

      setScreen('WORKSPACE')
      setWorkspaceTab('RUN')

      setTimeout(()=>{
        setDevelopmentProgress(prev=>({
          ...prev,
          active:false
        }))
      },2500)
    }catch(e){
      if(progressTimer){
        clearInterval(progressTimer)
        progressTimer=null
      }

      const transportErrorMessage=(
        e?.network
          ? `Workflow 응답 연결 오류\nAPI: ${e?.url||'-'}`
          : String(e)
      )

      let recoveredDiagnostics=null

      // Workflow 응답 fetch가 끊겼더라도 Backend가 다시 응답할 수 있으면
      // 프로젝트에 이미 생성된 진단 파일을 즉시 복구 조회합니다.
      try{
        recoveredDiagnostics=await api(
          `/workflow/diagnostics?project_root=${encodeURIComponent(projectRoot)}&run_id=${encodeURIComponent(effectiveWorkflowThreadId)}`
        )
      }catch(diagError){
        console.error(
          '실패 진단 자료 재조회 실패',
          diagError
        )
      }

      const diagnosticFiles=recoveredDiagnostics?.files||{}
      const toPath=(key)=>diagnosticFiles?.[key]?.path||''

      const syntheticDiagnostics=recoveredDiagnostics
        ? {
            project_root:recoveredDiagnostics.project_root||projectRoot,
            run_id:recoveredDiagnostics.run_id||effectiveWorkflowThreadId,
            run_started_at:recoveredDiagnostics.run_started_at||'',
            diagnostic_generated_at:recoveredDiagnostics.diagnostic_generated_at||'',
            diagnostics_fresh:recoveredDiagnostics.diagnostics_fresh===true,
            status:recoveredDiagnostics.status||'FAILED',
            failure_stage:recoveredDiagnostics.failure_stage||'network/fetch',
            failure_reason:
              recoveredDiagnostics.failure_reason
              ||transportErrorMessage,
            actual_file_count:recoveredDiagnostics.actual_file_count||0,
            planned_file_count:recoveredDiagnostics.planned_file_count||0,
            failure_report:toPath('failure_report'),
            workflow_state:toPath('workflow_state'),
            requirements_snapshot:toPath('requirements_snapshot'),
            generated_artifacts:toPath('generated_artifacts'),
            debug_patch:toPath('debug_patch'),
            recovery_plan:toPath('recovery_plan'),
            files:diagnosticFiles,
            file_apply:recoveredDiagnostics.file_apply,
            test:recoveredDiagnostics.test,
            debug:recoveredDiagnostics.debug,
            code_plan_validation:recoveredDiagnostics.code_plan_validation||{},
            missing_required_paths:recoveredDiagnostics.missing_required_paths||[]
          }
        : {
            project_root:projectRoot,
            run_id:effectiveWorkflowThreadId,
            run_started_at:new Date(startedAt).toISOString(),
            diagnostic_generated_at:'',
            diagnostics_fresh:false,
            status:'FETCH_FAILED',
            failure_stage:'network/fetch',
            failure_reason:transportErrorMessage,
            actual_file_count:0,
            planned_file_count:0,
            files:{
              failure_report:{
                path:`${projectRoot}\\reports\\failure_report.md`,
                exists:null
              },
              workflow_state:{
                path:`${projectRoot}\\reports\\workflow_state.json`,
                exists:null
              },
              requirements_snapshot:{
                path:`${projectRoot}\\reports\\requirements_snapshot.json`,
                exists:null
              },
              generated_artifacts:{
                path:`${projectRoot}\\reports\\generated_artifacts.json`,
                exists:null
              },
              debug_patch:{
                path:`${projectRoot}\\debug\\debug_patch.json`,
                exists:null
              },
              recovery_plan:{
                path:`${projectRoot}\\debug\\recovery_plan.md`,
                exists:null
              },
              agent_factory_log:{
                path:`${projectRoot}\\logs\\agent_factory.log`,
                exists:null
              },
              workflow_execution_log:{
                path:`${projectRoot}\\logs\\workflow_execution.log`,
                exists:null
              }
            },
            file_apply:{executed:false,count:0},
            test:{executed:false,returncode:null},
            debug:{executed:false,count:0},
            code_plan_validation:{},
            missing_required_paths:[]
          }

      const recoveredStillRunning=(
        recoveredDiagnostics?.status==='RUNNING'
        ||recoveredDiagnostics?.status==='DIAGNOSTICS_STALE'
      )

      const failureStatus={
        kind:recoveredStillRunning?'action':'failure',
        title:recoveredStillRunning
          ? 'Backend 작업 상태를 다시 확인해야 합니다.'
          : 'Agent 개발에 실패했습니다.',
        detail:
          recoveredDiagnostics
            ? (
                recoveredDiagnostics.diagnostics_fresh===false
                  ? (
                      `상태: ${recoveredDiagnostics.status||'DIAGNOSTICS_STALE'}\n`
                      +'현재 실행의 최종 진단 파일이 아직 생성되지 않았습니다. '
                      +'이전 실행 파일을 이번 실패 원인으로 표시하지 않습니다.'
                    )
                  : (
                      `상태: ${recoveredDiagnostics.status||'UNKNOWN'}\n`
                      +`원인: ${recoveredDiagnostics.failure_reason||'진단 원인이 기록되지 않았습니다.'}`
                      +(e?.network
                        ? `\n참고: 화면 연결은 중간에 끊겼지만 Backend 진단 재조회는 성공했습니다.`
                        : '')
                    )
              )
            : (
                `${transportErrorMessage} · Backend에 연결할 수 없어 `
                +'진단 파일 존재 여부는 확인하지 못했습니다.'
              ),
        status:
          recoveredDiagnostics?.status
          ||'FETCH_FAILED'
      }

      const failedResume={
        source:'AGENT_BUILD_FAILURE',
        run_id:String(recoveredDiagnostics?.run_id||effectiveWorkflowThreadId||''),
        status:String(failureStatus.status||''),
        failure_stage:String(recoveredDiagnostics?.failure_stage||'network/fetch'),
        failure_reason:String(recoveredDiagnostics?.failure_reason||transportErrorMessage||''),
        project_root:projectRoot,
        workflow_state:(recoveredDiagnostics?.workflow_state&&typeof recoveredDiagnostics.workflow_state==='object')
          ? recoveredDiagnostics.workflow_state
          : {
              project_root:projectRoot,
              request,
              thread_id:effectiveWorkflowThreadId,
              diagnostic_status:failureStatus.status,
              diagnostic_failure_stage:recoveredDiagnostics?.failure_stage||'network/fetch',
              diagnostic_failure_reason:recoveredDiagnostics?.failure_reason||transportErrorMessage
            }
      }
      setRestoredBuildResume(failedResume)
      setRedevelopmentInfo({
        available:!recoveredStillRunning,
        status:String(failureStatus.status||''),
        run_id:String(recoveredDiagnostics?.run_id||effectiveWorkflowThreadId||''),
        failure_stage:String(recoveredDiagnostics?.failure_stage||'network/fetch'),
        failure_reason:String(recoveredDiagnostics?.failure_reason||transportErrorMessage||''),
        resume_from_node:redevelopmentResumeNodeForFailure(
          recoveredDiagnostics?.failure_stage||'network/fetch',
          failureStatus.status||''
        )
      })
      saveRequirementDraft(failedResume)

      setWorkflow({
        state:{
          status:failureStatus.status,
          error:(
            recoveredDiagnostics?.failure_reason
            ||transportErrorMessage
          ),
          patch_result:[],
          test_result:{},
          debug_history:[]
        },
        failure_diagnostics:syntheticDiagnostics
      })

      setDevelopmentFinalStatus(failureStatus)
      setAgentBuildMessage(
        recoveredStillRunning
          ? `개발 상태 재확인 필요: ${failureStatus.status}`
          : `개발 실패: ${failureStatus.status}`
      )

      window.alert(
        (recoveredStillRunning
          ? `Agent 개발의 현재 상태를 다시 확인해야 합니다.\n\n`
          : `Agent 개발에 실패했습니다.\n\n`)
        +`${failureStatus.detail}\n\n`
        +(recoveredStillRunning
          ? '실행 결과 탭에서 현재 실행 ID와 진단 파일 업데이트 시각을 확인하세요.'
          : '실행 결과 탭의 실패 진단 영역에서 로그/진단 파일 경로를 확인하세요.')
      )

      setDevelopmentProgress(prev=>({
        ...prev,
        active:false,
        percent:recoveredStillRunning?Math.max(prev?.percent||0,10):0,
        stage:recoveredStillRunning?'상태 재확인 필요':'개발 실패',
        detail:failureStatus.detail,
        elapsedSeconds:Math.max(
          0,
          Math.floor((Date.now()-startedAt)/1000)
        )
      }))

      setScreen('WORKSPACE')
      setWorkspaceTab('RUN')
    }finally{
      // v5.377: Agent Factory가 성공/실패/취소로 종료되면 전역 실행 정지 버튼의
      // 원인이 되는 activeWorkflowJobId도 반드시 해제합니다. 완료된 Job ID를
      // 남겨두면 hasActiveExecution이 true로 유지되어 작업이 끝난 뒤에도
      // 상단 '실행 정지' 버튼이 계속 표시될 수 있습니다.
      setActiveWorkflowJobId('')
      setAgentBuildBusy(false)
    }
  }

  const previewTargetWorkflow=async(requestText)=>{
    const request=(
      requestText
      || workflowReq
      || buildRequirementRequestFromCollectedInfo()
      || ''
    ).trim()

    if(!request){
      setTargetWorkflowError('에이전트 개발 요청 내용을 입력하세요.')
      return false
    }

    if(!(await ensureGpuAccelerationForPhase({request,phase:'design',actionLabel:'설계 검토'}))){
      setTargetWorkflowError('GPU 권장 안내에서 설계 검토가 취소되었습니다.')
      return false
    }

    setTargetWorkflowLoading(true)
    setTargetWorkflowError('')
    setWorkflowProgress({
      active:true,
      percent:5,
      stage:'요구사항 준비',
      detail:'인터뷰에서 확정된 요구사항을 Workflow 설계 입력으로 정리하고 있습니다.',
      startedAt:Date.now()
    })

    let progressTimer=null
    let percent=18

    try{
      setWorkflowProgress(prev=>({
        ...prev,
        percent:18,
        stage:'AI Workflow 설계 요청',
        detail:'요구사항과 프로젝트 정보를 AI 설계 엔진에 전달했습니다.'
      }))

      // v5.341: Workflow/LangGraph는 고성능 설계 호출로 만들고, DB가 필요한 경우 Entity/관계를 전용 고성능 단계에서 추가 보강합니다.
      // 내부 LLM의 임의 퍼센트를 만들지 않고 실제 응답 대기 상태만 점진적으로 표시합니다.
      progressTimer=setInterval(()=>{
        percent=Math.min(82,percent+Math.max(1,Math.round((82-percent)*0.08)))

        setWorkflowProgress(prev=>({
          ...prev,
          percent,
          stage:'AI 설계 응답 대기',
          detail:
            percent<45
              ? '대상 Agent의 기능·MCP·Architecture·DB Module·Workflow를 설계하고 있습니다.'
              : percent<68
                ? 'AI 설계 결과를 기다리고 있습니다. 복잡한 요구사항은 시간이 더 걸릴 수 있습니다.'
                : '설계 응답을 기다리는 중입니다. 완료되면 요구사항 반영 검사를 진행합니다.'
        }))
      },650)

      const result=await api('/workflow/preview',{
        method:'POST',
        body:JSON.stringify({
          request,
          project_root:root||newAgentProjectRoot||'',
          provider,
          interview_messages:(chat||[]).map(item=>({
            role:item?.role||'',
            content:item?.content||''
          })),
          confirmed_requirements:buildConfirmedRequirementsFromChat(),
          attachment_ids:interviewAttachments.map(item=>item.attachment_id),
          attachment_memory:interviewAttachmentMemory,
          previous_design:targetWorkflowPreview||previousTargetWorkflowPreview||{}
        })
      })

      if(progressTimer){
        clearInterval(progressTimer)
        progressTimer=null
      }

      setWorkflowProgress(prev=>({
        ...prev,
        percent:90,
        stage:'Workflow 검증',
        detail:'생성된 Workflow의 단계·분기·재시도·실패 처리와 요구사항 반영 여부를 확인하고 있습니다.'
      }))

      if(result?.ok===false){
        throw new Error(result.message||'Workflow 분석 실패')
      }

      const nextAttachmentMemory=String(result?.attachment_memory||interviewAttachmentMemory||'')
      if(nextAttachmentMemory) setInterviewAttachmentMemory(nextAttachmentMemory)

      // v5.360: 파일을 일반 인터뷰 메시지와 함께 보낸 경우에도 Backend가
      // 만든 안전한 구조화 요약을 사용자 화면과 Draft에 남깁니다. 원문 Context는
      // 표시하지 않고 요구사항/기술/추가 확인 항목만 보여 줍니다.
      const visibleAttachmentSummary=sanitizeInterviewDisplayText(result?.attachment_summary||'')
      if(visibleAttachmentSummary){
        setInterviewAttachmentSummary(visibleAttachmentSummary)
        setInterviewAttachmentSummaryFiles(prev=>{
          const merged=[...(Array.isArray(prev)?prev:[]),...submittedAttachmentFiles]
          const seen=new Set()
          return merged.filter(item=>{
            const key=String(item?.path||item?.name||'').toLowerCase()
            if(!key||seen.has(key)) return false
            seen.add(key)
            return true
          })
        })
      }
      if(interviewAttachments.length){
        const consumedIds=interviewAttachments.map(item=>item.attachment_id)
        setInterviewAttachments([])
        setInterviewAttachmentAnalysis({busy:false,ready:true,overallProgress:100,failedFiles:0,successfulFiles:0,files:[]})
        void api('/ai/attachments/release',{
          method:'POST',
          body:JSON.stringify({attachment_ids:consumedIds})
        }).catch(()=>{})
      }

      // 브라우저가 90% 상태를 실제로 한 번 그릴 수 있도록 다음 frame까지 기다립니다.
      await new Promise(resolve=>
        requestAnimationFrame(()=>
          requestAnimationFrame(resolve)
        )
      )

      setWorkflowReq(request)
      setTargetWorkflowPreview(result)
      setPreviousTargetWorkflowPreview(result)
      setTargetWorkflowQuality(result?.workflow_quality||null)
      setAgentBuildStage('WORKFLOW_READY')
      const revision=result?.design_runtime?.incremental_revision||{}
      const revisionMode=String(revision?.mode||'')
      setAgentBuildMessage(
        revisionMode==='FULL_REUSE'
          ? '변경된 요구사항이 없어 기존 Workflow/Architecture/DB 설계를 그대로 재사용했습니다. (설계 LLM 호출 0회)'
          : revisionMode==='PARTIAL_REVISE'
            ? `변경된 부분만 증분 설계했습니다. 영향 영역: ${(revision?.affected_sections||[]).join(', ')||'-'}`
            : revisionMode==='FULL_REDESIGN'||revisionMode==='FULL_REDESIGN_FALLBACK'
              ? '큰 구조 변경을 감지해 전체 Workflow/Architecture/DB 설계를 다시 생성했습니다.'
              : '대상 Agent Workflow 설계가 완료되었습니다.'
      )
      setWorkflowView('TARGET')
      setWorkspaceTab('WORKFLOW')

      // Workflow 설계 결과까지 Draft에 보존합니다.
      setTimeout(()=>saveRequirementDraft(),0)

      setWorkflowProgress(prev=>({
        ...prev,
        active:true,
        percent:100,
        stage:'Workflow 설계 완료',
        detail:'대상 Agent Workflow와 요구사항 반영 검사가 완료되었습니다.'
      }))

      setTimeout(()=>{
        setWorkflowProgress(prev=>({
          ...prev,
          active:false
        }))
      },1800)
      return result
    }catch(e){
      if(progressTimer){
        clearInterval(progressTimer)
        progressTimer=null
      }

      setTargetWorkflowError(String(e))
      setWorkflowProgress(prev=>({
        ...prev,
        active:false,
        percent:0,
        stage:'Workflow 설계 실패',
        detail:String(e)
      }))
      return false
    }finally{
      setTargetWorkflowLoading(false)
    }
  }

  const runCmd=async()=>{
    if(!root || !command.trim()) return

    try{
      const result=await api('/jobs/command',{
        method:'POST',
        body:JSON.stringify({
          command:command.trim(),
          cwd:root
        })
      })

      setTerminal(prev=>
        (prev||'')
        + `\n[명령 작업 시작] ${command.trim()}`
        + (result?.id?`\nJob: ${result.id}`:'')
        + '\n'
      )
    }catch(e){
      setTerminal(prev=>(prev||'')+'\n[명령 실행 실패] '+String(e)+'\n')
    }
  }

  const sendChat=async(messageOverride='',retryPayload=null)=>{
    const typedMessage=String(messageOverride||input).trim()
    const message=typedMessage || (interviewAttachments.length
      ? '첨부한 참고 파일을 분석해서 Agent 요구사항을 파악해줘.'
      : '')
    if(!message || busy || interviewAttachmentSummaryBusy) return
    if(interviewAttachments.length&&!interviewAttachmentAnalysis.ready) return
    const requirementsDone=chat.some(item=>
      item?.role==='assistant'
      && String(item?.content||'').includes('요구사항 분석 완료')
    )

    if(requirementsDone && isBuildContinueCommand(message)){
      setInput('')
      setChat(prev=>[
        ...prev,
        {role:'user',content:message},
        {
          role:'assistant',
          content:
            agentBuildStage==='REQUIREMENTS'
              ? '확인했습니다. 요구사항을 기준으로 대상 Agent Workflow 설계를 시작합니다.'
              : agentBuildStage==='WORKFLOW_READY'
                ? 'Workflow 설계가 완료되어 있습니다. 프로젝트 생성 버튼을 눌러 다음 단계로 진행하세요.'
                : agentBuildStage==='PROJECT_CREATED'
                  ? '확인했습니다. Agent Factory 개발 Workflow를 시작합니다.'
                  : '현재 제작 Workflow를 진행하고 있습니다.'
        }
      ])

      if(agentBuildStage==='REQUIREMENTS'){
        await previewTargetWorkflow()
      }else if(agentBuildStage==='PROJECT_CREATED'){
        await startAgentDevelopment()
      }

      return
    }
    setWorkflowReq(prev=>prev?.trim()?prev:message)

    const isRetry=Boolean(retryPayload?.historyBeforeSend)
    const historyBeforeSend=isRetry ? retryPayload.historyBeforeSend : [...chat]
    const userMessage={role:'user',content:sanitizeInterviewDisplayText(message)}

    if(!isRetry) setChat(prev=>[...prev,userMessage])
    setInput('')
    setBusy(true)
    setInterviewActivityError('')
    setInterviewRetryPayload(null)

    const controller=new AbortController()
    interviewAbortRef.current=controller
    const retryRecord={type:'CHAT',message,historyBeforeSend}
    const submittedAttachmentFiles=(interviewAttachments||[]).map(item=>({
      name:String(item?.name||''),
      path:String(item?.path||'')
    })).filter(item=>item.name||item.path)

    try{
      const result=await api('/chat/interview',{
        method:'POST',
        signal:controller.signal,
        body:JSON.stringify({
          message,
          history:historyBeforeSend,
          provider,
          project_root:newAgentProjectRoot||root||'',
          attachment_ids:interviewAttachments.map(item=>item.attachment_id),
          attachment_memory:interviewAttachmentMemory
        })
      })

      const answer=protectInterviewAssistantAnswer(
        result?.answer
        || result?.message
        || '응답을 받지 못했습니다.'
      )
      const attachmentWarning=Array.isArray(result?.attachment_warnings)&&result.attachment_warnings.length
        ? `\n\n[참고 파일 알림] ${result.attachment_warnings.join(' / ')}`
        : ''
      const nextAttachmentMemory=String(result?.attachment_memory||interviewAttachmentMemory||'')
      if(nextAttachmentMemory) setInterviewAttachmentMemory(nextAttachmentMemory)
      const visibleAttachmentSummary=sanitizeInterviewDisplayText(result?.attachment_summary||'')
      const minedAttachmentRequirements=Array.isArray(result?.attachment_requirements)?result.attachment_requirements:[]
      if(visibleAttachmentSummary) setInterviewAttachmentSummary(visibleAttachmentSummary)
      if(minedAttachmentRequirements.length) setInterviewAttachmentRequirements(minedAttachmentRequirements)
      if(result?.attachment_requirement_coverage&&typeof result.attachment_requirement_coverage==='object') setInterviewAttachmentRequirementCoverage(result.attachment_requirement_coverage)
      if((visibleAttachmentSummary||minedAttachmentRequirements.length)&&submittedAttachmentFiles.length){
        setInterviewAttachmentSummaryFiles(prev=>{
          const merged=[...(Array.isArray(prev)?prev:[]),...submittedAttachmentFiles]
          const seen=new Set()
          return merged.filter(item=>{
            const key=String(item?.path||item?.name||'').toLowerCase()
            if(!key||seen.has(key)) return false
            seen.add(key)
            return true
          })
        })
      }
      if(interviewAttachments.length){
        const consumedIds=interviewAttachments.map(item=>item.attachment_id)
        setInterviewAttachments([])
        setInterviewAttachmentAnalysis({busy:false,ready:true,overallProgress:100,failedFiles:0,successfulFiles:0,files:[]})
        void api('/ai/attachments/release',{
          method:'POST',
          body:JSON.stringify({attachment_ids:consumedIds})
        }).catch(()=>{})
      }

      setChat(prev=>[
        ...prev,
        {role:'assistant',content:answer+attachmentWarning}
      ])
      setInterviewRetryPayload(null)

      setTimeout(()=>{
        buildConfirmedRequirementsFromChat()
        saveRequirementDraft()
      },0)
    }catch(e){
      const aborted=controller.signal.aborted || String(e?.name||'')==='AbortError'
      const messageText=aborted
        ? '현재 AI 응답 대기를 사용자가 취소했습니다. 필요하면 현재 요청을 다시 시도할 수 있습니다.'
        : '대화 요청 실패: '+String(e?.message||e)
      setInterviewActivityError(messageText)
      setInterviewRetryPayload(retryRecord)
      setChat(prev=>[
        ...prev,
        {role:'assistant',content:messageText}
      ])
    }finally{
      if(interviewAbortRef.current===controller) interviewAbortRef.current=null
      setBusy(false)
    }
  }

  const cancelInterviewActivity=()=>{
    if(interviewAbortRef.current){
      try{interviewAbortRef.current.abort()}catch{}
    }
    if(interviewSummaryAbortRef.current){
      try{interviewSummaryAbortRef.current.abort()}catch{}
    }
  }

  const retryInterviewActivity=async()=>{
    const retry=interviewRetryPayload
    if(!retry) return
    if(retry.type==='SUMMARY'){
      await summarizeInterviewAttachments()
      return
    }
    if(retry.type==='CHAT'){
      await sendChat(retry.message,retry)
    }
  }


  const sendBuilderAnswer=async()=>{
    if(!input.trim()&&!interviewAttachments.length) return
    setBuilderStarted(true)
    await sendChat()
  }

  const goWorkspace=()=>{
    if(selectedProjectId || newAgentProjectRoot){
      if(newAgentProjectRoot) setRoot(newAgentProjectRoot)
      setScreen('WORKSPACE')
    }
  }

  const pathPreview=(value, fallback)=>value?.trim()?value:`${newAgentProjectRoot||'<프로젝트 경로>'}\\${fallback}`

  const weatherPositionStorageKey='agentstudio.weather.devicePosition.v1'

  const readStoredWeatherPosition=()=>{
    try{
      const raw=localStorage.getItem(weatherPositionStorageKey)
      if(!raw) return null
      const parsed=JSON.parse(raw)
      const latitude=Number(parsed?.latitude)
      const longitude=Number(parsed?.longitude)
      const savedAt=Number(parsed?.savedAt||0)
      if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||!savedAt) return null
      if(Date.now()-savedAt>24*60*60*1000) return null
      return {latitude,longitude}
    }catch{
      return null
    }
  }

  const storeWeatherPosition=(position)=>{
    if(!position) return
    try{
      localStorage.setItem(weatherPositionStorageKey,JSON.stringify({
        latitude:Number(position.latitude),
        longitude:Number(position.longitude),
        savedAt:Date.now(),
      }))
    }catch{}
  }

  const getDeviceWeatherPosition=(force=false)=>new Promise((resolve)=>{
    if(!force){
      const cached=readStoredWeatherPosition()
      if(cached){
        resolve(cached)
        return
      }
    }

    if(!navigator.geolocation){
      resolve(null)
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position)=>{
        const value={
          latitude:position.coords.latitude,
          longitude:position.coords.longitude,
        }
        storeWeatherPosition(value)
        resolve(value)
      },
      ()=>resolve(readStoredWeatherPosition()),
      {
        enableHighAccuracy:false,
        timeout:6000,
        maximumAge:15*60*1000,
      }
    )
  })

  const refreshHomeWeather=async(forceRefresh=false)=>{
    const token=++weatherRequestTokenRef.current
    setWeatherBusy(true)
    setWeatherError('')

    try{
      let config={auto_location:false}
      try{
        config=await api('/weather/config')
      }catch{}

      let position=null
      if(config?.auto_location){
        position=await getDeviceWeatherPosition(forceRefresh)
      }

      const query=new URLSearchParams()
      if(position){
        query.set('latitude',String(position.latitude))
        query.set('longitude',String(position.longitude))
      }
      if(forceRefresh){
        query.set('force_refresh','true')
      }

      const suffix=query.toString()?`?${query.toString()}`:''
      const result=await api(`/weather/dashboard${suffix}`)
      if(token!==weatherRequestTokenRef.current) return
      setWeatherDashboard(result)
      if(Array.isArray(result?.errors)&&result.errors.length){
        setWeatherError(result.errors.join(' · '))
      }
    }catch(error){
      if(token!==weatherRequestTokenRef.current) return
      // 기존 날씨가 화면에 있다면 네트워크 오류 때문에 지우지 않습니다.
      setWeatherError(String(error?.message||error))
    }finally{
      if(token===weatherRequestTokenRef.current){
        setWeatherBusy(false)
      }
    }
  }

  useEffect(()=>{
    if(screen==='HOME'){
      refreshHomeWeather(false)
    }
  },[screen])

  const renderWeatherPeriod=(period)=><div className="home-weather-period" key={period.key||period.label}>
    <span className="home-weather-period-icon" aria-hidden="true">{period.icon||'🌡️'}</span>
    <div>
      <strong>{period.label||'-'}</strong>
      <small>{period.condition||'-'}</small>
    </div>
    <b>{period.temperature===null||period.temperature===undefined?'-':`${Math.round(Number(period.temperature))}°`}</b>
    {period.precipitation_probability!==null&&period.precipitation_probability!==undefined&&
      <em>강수 {Math.round(Number(period.precipitation_probability))}%</em>}
  </div>

  const renderHomeWeather=()=>{
    const locations=Array.isArray(weatherDashboard?.locations)?weatherDashboard.locations:[]

    return <section className="home-weather-section">
      <div className="home-weather-head">
        <div>
          <small>TODAY WEATHER</small>
          <strong>오늘의 날씨</strong>
          <span>아침 · 점심 · 저녁 · 밤</span>
        </div>
        <div className="home-weather-actions">
          <button type="button" onClick={()=>refreshHomeWeather(true)} disabled={weatherBusy}>
            {weatherBusy?'불러오는 중...':'↻ 새로고침'}
          </button>
          <button type="button" onClick={()=>location.href='/system'}>지역 설정</button>
        </div>
      </div>

      {weatherBusy&&!locations.length&&<div className="home-weather-empty">현재 지역의 오늘 날씨를 불러오고 있습니다...</div>}

      {!weatherBusy&&!locations.length&&<div className="home-weather-empty">
        <span>📍</span>
        <div>
          <strong>날씨 지역을 확인할 수 없습니다.</strong>
          <small>{weatherError||weatherDashboard?.message||'브라우저 위치 권한을 허용하거나 설정에서 기본 지역을 입력하세요.'}</small>
        </div>
      </div>}

      {locations.length>0&&<div className="home-weather-location-list">
        {locations.map((location,index)=><article className="home-weather-location-card" key={`${location.name}-${index}`}>
          <header>
            <div>
              <span>{location.source==='device'?'📍':'🌐'}</span>
              <div>
                <strong>{location.name||'지역 날씨'}</strong>
                <small>
                  {location.source==='device'?'현재 위치':'설정 지역'} · {location.date||'오늘'}
                  {location.cache?.hit?' · 저장된 데이터':''}
                </small>
              </div>
            </div>
            <div className="home-weather-daily">
              <span>{location.daily?.icon||'🌡️'}</span>
              <strong>{location.daily?.temperature_min===null||location.daily?.temperature_min===undefined?'-':Math.round(Number(location.daily.temperature_min))}° / {location.daily?.temperature_max===null||location.daily?.temperature_max===undefined?'-':Math.round(Number(location.daily.temperature_max))}°</strong>
            </div>
          </header>
          <div className="home-weather-period-grid">
            {(location.periods||[]).map(renderWeatherPeriod)}
          </div>
        </article>)}
      </div>}

      {weatherError&&locations.length>0&&<div className="home-weather-errors">
        <strong>일부 지역 날씨를 가져오지 못했습니다.</strong>
        <span>{weatherError}</span>
      </div>}

      <footer>
        날씨 데이터: {weatherDashboard?.provider||'Open-Meteo'}
        {weatherDashboard?.cache?.all_cached?' · 오늘 저장된 데이터 사용':' · 오늘 데이터 로컬 저장'}
        {' · '}위치 권한은 날씨 조회에만 사용합니다.
      </footer>
    </section>
  }

  const renderHomeScreen=()=> <div className="studio-home">
    <div className="hero-panel">
      <div className="eyebrow">THEANOVA AGENTSTUDIO</div>
      <h1>AI Agent + MCP 프로그램을<br/>대화로 설계하고 코드로 완성합니다.</h1>
      <p>처음부터 모든 설정을 알 필요가 없습니다. AgentStudio가 한 번에 하나씩 질문하고, 요구사항을 정리한 뒤 프로젝트를 생성합니다.</p>
      <div className="hero-actions">
        <button className="hero-primary" onClick={startNewProject}>＋ 신규 에이전트 만들기</button>
        <button className="hero-secondary" onClick={openProjectList}>▣ 기존 프로젝트 불러오기</button>
      </div>
    </div>

    {renderHomeWeather()}

    <div className="home-grid">
      <button className="home-card accent" onClick={startNewProject}>
        <span className="card-icon">＋</span>
        <strong>신규 생성</strong>
        <small>AI와 대화하면서 목적·MCP·기능·실행환경을 한 단계씩 결정합니다.</small>
        <span className="card-link">설계 시작 →</span>
      </button>
      <button className="home-card" onClick={openProjectList}>
        <span className="card-icon">▣</span>
        <strong>불러오기</strong>
        <small>DB 저장 프로젝트를 선택하거나, DB에 없는 기존 프로젝트 폴더를 지정해 분석하고 작업을 이어갑니다.</small>
        <span className="card-link">프로젝트 선택 →</span>
      </button>
      <button className="home-card" onClick={()=>setUsageOpen(true)}>
        <span className="card-icon">?</span>
        <strong>사용 방법</strong>
        <small>프로젝트 생성부터 MCP 연결, 코드 수정, 테스트까지 전체 흐름을 확인합니다.</small>
        <span className="card-link">가이드 보기 →</span>
      </button>
    </div>

    <div className="workflow-strip">
      <div><b>1</b><span>아이디어 설명</span><small>무엇을 만들지 말합니다.</small></div>
      <i>→</i>
      <div><b>2</b><span>AI 인터뷰</span><small>질문은 한 번에 하나씩.</small></div>
      <i>→</i>
      <div><b>3</b><span>프로젝트 생성</span><small>경로·DB·환경을 준비합니다.</small></div>
      <i>→</i>
      <div><b>4</b><span>코딩 & MCP</span><small>수정·실행·검증을 반복합니다.</small></div>
    </div>
  </div>

  const renderBuilderScreen=()=>{
    const leftSummary=getBuilderConversationSummary()
    const builderSteps=[
      ['01','목적',leftSummary.purpose],
      ['02','기능',leftSummary.features],
      ['03','MCP / Tool',leftSummary.mcpTools],
      ['04','DB 설계',leftSummary.database],
      ['05','UI / Layout',leftSummary.uiLayout],
      ['06','실행 환경',leftSummary.runtime],
      ['07','확인',leftSummary.confirmation]
    ]
    return <div className="builder-shell">
    <aside className="builder-steps">
      <button className="back-link" onClick={()=>setScreen('HOME')}>← 홈으로</button>
      <div className="builder-title">신규 Agent 설계</div>
      {builderSteps.map((s,i)=><div className={`builder-step ${i===0||builderStarted?'on':''}`} key={s[0]}>
        <b>{s[0]}</b><div><strong>{s[1]}</strong><small title={s[2]}>{s[2]}</small></div>
      </div>)}
      <div className="builder-live-summary">
        <strong>대화 요구사항 요약</strong>
        {leftSummary.collectedItems.length
          ? <div className="builder-live-summary-list">
              {leftSummary.collectedItems.slice(0,8).map(item=><div key={item.id}>
                <span>{item.label}</span><b>{item.value}</b>
              </div>)}
            </div>
          : <small>대화를 시작하면 확정된 내용이 여기에 자동 정리됩니다.</small>}
      </div>
      {(interviewAttachmentSummary||interviewAttachmentRequirements.length>0)&&<AttachmentAnalysisSummaryCard
        summary={interviewAttachmentSummary}
        files={interviewAttachmentSummaryFiles}
        requirements={interviewAttachmentRequirements}
        coverage={interviewAttachmentRequirementCoverage}
        compact={true}
        restored={requirementDraftRestored}
      />}
      <div className="builder-tip">
        <strong>질문 방식 · Quality Gate</strong>
        <span>이미 답한 내용과 AgentStudio가 자동 설계할 기술 세부사항은 다시 묻지 않고, 사용자 결정이 필요한 질문 하나만 이어갑니다.</span>
      </div>
    </aside>

    <section className="builder-chat">
      <AgentDesignProjectToolbar
        designProjectId={designProjectId}
        projectName={newAgentName||leftSummary.purpose}
        savedAt={designProjectSavedAt||requirementDraftSavedAt}
        status={designProjectProgressInfo().status}
        progress={designProjectProgressInfo().progress}
        onNew={()=>{
          const hasWork=(chat||[]).some(item=>item?.role==='user')||Boolean(designProjectId)
          if(hasWork&&!window.confirm('현재 Agent 설계를 종료하고 새 설계 프로젝트를 시작할까요?\n\n저장하지 않은 변경이 있다면 먼저 프로젝트 저장을 눌러주세요.')) return
          startNewProject()
        }}
        onSave={()=>saveAgentDesignProject({createVersion:true,versionLabel:'사용자 수동 저장 Snapshot'})}
        onLoad={loadAgentDesignProject}
      />
      <div className="builder-chat-head">
        <div><span className="ai-avatar">AI</span><div><strong>Agent 설계 인터뷰</strong><small>{aiInterviewLabel}</small></div></div>
        <div className="builder-head-actions">
          <button type="button" className="builder-layout-button" onClick={()=>setUiLayoutGalleryOpen(true)}>▦ UI Layout</button>
          <button
            type="button"
            className="builder-workflow-button"
            onClick={()=>{
              const request=
                workflowReq
                || buildRequirementRequestFromCollectedInfo()
                || chat.find(x=>x.role==='user')?.content
                || ''

              if(request){
                saveRequirementDraft()
                setRoot(newAgentProjectRoot||root)
                setScreen('WORKSPACE')
                previewTargetWorkflow(request)
              }else{
                setTargetWorkflowError('먼저 만들 Agent의 요구사항을 입력하세요.')
              }
            }}
          >
            ◇ Workflow 보기
          </button>
          <span className="live-dot">● 대화형 수집</span>
        </div>
      </div>
      <div className="builder-messages">
        {chat.map((m,i)=><div key={i} className={`builder-msg ${m.role}`}>
          <span>{m.role==='assistant'?'AI':'나'}</span>
          <div>{m.role==='assistant'?protectInterviewAssistantAnswer(m.content):sanitizeInterviewDisplayText(m.content)}</div>
        </div>)}
        {busy&&<div className="builder-msg assistant"><span>AI</span><div>답변을 분석하고 다음 질문을 준비하고 있습니다...</div></div>}
        <div ref={builderMessagesEndRef} className="builder-messages-end" aria-hidden="true"></div>
      </div>
      <AgentBuildActionBar
        stage={agentBuildStage}
        busy={agentBuildBusy||projectCreateFlowBusy||targetWorkflowLoading}
        message={agentBuildMessage}
        workflowEnabled={canDesignFromCollectedInfo()}
        onWorkflow={()=>previewTargetWorkflow()}
        onCreateProject={createAgentProjectSmart}
        onStartDevelopment={startAgentDevelopment}
        onRedevelop={()=>startAgentDevelopment({redevelopment:true})}
        redevelopmentEnabled={Boolean(redevelopmentInfo?.available)}
        redevelopmentInfo={redevelopmentInfo}
        onStop={cancelAgentDevelopment}
      />

      <div className="builder-input">
        <textarea value={input} onChange={e=>setInput(e.target.value)}
          onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendBuilderAnswer()}}}
          placeholder="현재 질문에 답해주세요. Shift+Enter로 줄바꿈"/>
        <button onClick={sendBuilderAnswer} disabled={busy||!input.trim()}>답변 보내기</button>
      </div>
    </section>

    <aside className="builder-summary">
      <div className="summary-head">
        <div><strong>프로젝트 구성</strong><small>생성 전에 언제든 수정할 수 있습니다.</small></div>
      </div>

      <div className="requirement-collection-card">
        <div className="requirement-collection-head">
          <div>
            <strong>요구사항 수집 현황</strong>
            <small>
              대화에서 확인된 항목은 자동 저장됩니다.
            </small>
          </div>
          <span>
            {getRequirementKeywordStatus().filter(x=>x.collected).length}
            /{getRequirementKeywordStatus().length}
          </span>
        </div>

        <div className="requirement-keyword-grid">
          {getRequirementKeywordStatus().map(item=>
            <div
              key={item.id}
              className={`requirement-keyword ${item.collected?'collected':'pending'}`}
            >
              <i>{item.collected?'✓':'○'}</i>
              <span>{item.label}</span>
              <b>{item.collected?'수집 완료':'미수집'}</b>
            </div>
          )}
        </div>

        <div className="requirement-draft-info">
          <span>
            {requirementDraftDecisionPending
              ? (requirementDraftCandidate?.build_resume?.status
                  ? `이전 요구사항 + 개발 기록 발견 · ${requirementDraftCandidate.build_resume.status}`
                  : '같은 경로의 이전 요구사항 Draft 발견')
              : requirementDraftRestored
                ? (restoredBuildResume?.status
                    ? `이전 수집/개발 기록 복원됨 · ${restoredBuildResume.status}`
                    : '이전 수집 정보 복원됨')
                : requirementDraftSavedAt
                  ? '수집 정보 저장됨'
                  : '수집 정보 저장 대기'}
          </span>
          {requirementDraftSavedAt&&
            <small>
              {new Date(requirementDraftSavedAt).toLocaleString()}
            </small>
          }
        </div>

        {requirementDraftCandidate&&requirementDraftDecisionPending&&
          <div className="requirement-draft-choice">
            <p>{requirementDraftCandidate?.build_resume?.status
              ? '이 경로에 이전 Agent 설계와 개발 실행 기록이 있습니다. 요구사항·Workflow·실패 진단을 함께 복원해 이어서 개발할 수 있습니다.'
              : '프로젝트 경로만 선택한 상태에서는 과거 대화를 자동으로 불러오지 않습니다.'}</p>
            <div>
              <button
                type="button"
                className="requirement-draft-restore-button"
                onClick={()=>restoreRequirementDraft(requirementDraftCandidate.key)}
              >
                {requirementDraftCandidate?.build_resume?.status?'이전 설계/개발 기록 이어서 불러오기':'이전 요구사항 이어서 불러오기'}
              </button>
              <button
                type="button"
                className="requirement-draft-ignore-button"
                onClick={keepCurrentInterviewInsteadOfDraft}
              >
                현재 인터뷰 유지
              </button>
            </div>
          </div>
        }

        {canDesignFromCollectedInfo()&&
          <button
            type="button"
            className="requirement-direct-workflow-button"
            disabled={targetWorkflowLoading}
            onClick={()=>{
              saveRequirementDraft()
              setRoot(newAgentProjectRoot||root)
              setScreen('WORKSPACE')
              previewTargetWorkflow(
                buildRequirementRequestFromCollectedInfo()
              )
            }}
          >
            {targetWorkflowPreview
              ? '◇ 저장된 요구사항으로 Workflow 다시 설계'
              : '◇ 수집된 요구사항으로 바로 Workflow 설계'}
          </button>
        }

        <details className="requirement-collected-details">
          <summary>수집된 내용 보기</summary>
          <div>
            {(chat||[])
              .filter(item=>item?.role==='user')
              .map((item,index)=>
                <p key={index}>{item.content}</p>
              )}
            {!(chat||[]).some(item=>item?.role==='user')&&
              <p>아직 사용자 답변이 없습니다.</p>
            }
          </div>
        </details>
      </div>
      <AgentFeatureManager
        detectedFeatures={getDetectedAgentFeatureNames()}
        features={designFeatureRegistry}
        onChange={handleDesignFeatureChange}
      />
      <div className={`ui-layout-choice-card ${uiLayoutConfig?.template_id?'selected':''}`}>
        <div className="ui-layout-choice-head"><div><strong>UI / Layout</strong><small>썸네일을 보고 웹/웹앱 화면 구조를 선택합니다.</small></div><span>{uiLayoutConfig?.template_id?'선택됨':'선택 전'}</span></div>
        {uiLayoutConfig?.template_id?<><UILayoutWireframe config={uiLayoutConfig} compact={true}/><b>{uiLayoutSummary(uiLayoutConfig)}</b></>:<div className="ui-layout-choice-empty">좌측 메뉴, 상단 메뉴, Footer, 사용자 메뉴, Dashboard/Chat/Search Layout 등을 시각적으로 고를 수 있습니다.</div>}
        <button type="button" onClick={()=>setUiLayoutGalleryOpen(true)}>{uiLayoutConfig?.template_id?'레이아웃 변경':'레이아웃 템플릿 선택'}</button>
      </div>
      <label className="ux-field"><span>에이전트 이름</span><input value={newAgentName} onChange={e=>setNewAgentName(e.target.value)} placeholder="예: YouTube MCP Agent"/></label>
      <label className="ux-field required"><span>프로젝트 경로</span>
          <div className="path-input-row">
            <input value={newAgentProjectRoot} onChange={e=>setNewAgentProjectRoot(e.target.value)} placeholder="예: F:\\Source\\repos\\Theanova\\AI\\MyAgent"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentProjectRoot,newAgentProjectRoot,'프로젝트 경로')}>경로 찾기</button>
          </div>
        </label>

      <button className="path-toggle" onClick={()=>setShowPathSettings(v=>!v)}>
        <span>고급 경로 설정</span><b>{showPathSettings?'−':'＋'}</b>
      </button>
      {showPathSettings&&<div className="path-settings">
        <label className="ux-field"><span>Cache</span>
          <div className="path-input-row">
            <input value={newAgentCachePath} onChange={e=>setNewAgentCachePath(e.target.value)} placeholder="비우면 프로젝트\\cache"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentCachePath,newAgentCachePath,'Cache 경로')}>경로 찾기</button>
          </div>
        </label>
        <label className="ux-field"><span>Temp</span>
          <div className="path-input-row">
            <input value={newAgentTempPath} onChange={e=>setNewAgentTempPath(e.target.value)} placeholder="비우면 프로젝트\\temp"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentTempPath,newAgentTempPath,'Temp 경로')}>경로 찾기</button>
          </div>
        </label>
        <label className="ux-field"><span>Output</span>
          <div className="path-input-row">
            <input value={newAgentOutputPath} onChange={e=>setNewAgentOutputPath(e.target.value)} placeholder="비우면 프로젝트\\output"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentOutputPath,newAgentOutputPath,'Output 경로')}>경로 찾기</button>
          </div>
        </label>
        <label className="ux-field"><span>가상환경</span>
          <div className="path-input-row">
            <input value={newAgentVenvPath} onChange={e=>setNewAgentVenvPath(e.target.value)} placeholder="비우면 프로젝트\\venv"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentVenvPath,newAgentVenvPath,'가상환경 경로')}>경로 찾기</button>
          </div>
        </label>
        <label className="ux-field"><span>공통 모델</span>
          <div className="path-input-row">
            <input value={newAgentModelsPath} onChange={e=>setNewAgentModelsPath(e.target.value)} placeholder="비우면 프로젝트\\models"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentModelsPath,newAgentModelsPath,'공용 모델 경로')}>경로 찾기</button>
          </div>
        </label>
      </div>}

      {loadedProjectAnalysis&&<div className="imported-project-analysis">
        <div className="imported-analysis-head">
          <strong>기존 프로젝트 분석 정보</strong>
          <span>DB 저장됨</span>
        </div>

        {loadedProjectAnalysis.summary&&<div className="analysis-info-block">
          <b>프로젝트 요약</b>
          <p>{loadedProjectAnalysis.summary}</p>
        </div>}

        {loadedProjectAnalysis.tech_stack?.length>0&&<div className="analysis-info-block">
          <b>기술 스택</b>
          <div className="analysis-tags">
            {loadedProjectAnalysis.tech_stack.map((x,i)=><span key={i}>{typeof x==='string'?x:JSON.stringify(x)}</span>)}
          </div>
        </div>}

        {loadedProjectAnalysis.entry_points?.length>0&&<div className="analysis-info-block">
          <b>실행 진입점</b>
          {loadedProjectAnalysis.entry_points.slice(0,8).map((x,i)=><code key={i}>{typeof x==='string'?x:JSON.stringify(x)}</code>)}
        </div>}

        {loadedProjectAnalysis.mcp_tools?.length>0&&<div className="analysis-info-block">
          <b>MCP / Tool</b>
          {loadedProjectAnalysis.mcp_tools.slice(0,10).map((x,i)=><code key={i}>{typeof x==='string'?x:JSON.stringify(x)}</code>)}
        </div>}

        {loadedProjectAnalysis.major_files?.length>0&&<details className="analysis-files">
          <summary>주요 파일 {loadedProjectAnalysis.major_files.length}개</summary>
          <div>
            {loadedProjectAnalysis.major_files.slice(0,30).map((x,i)=><code key={i}>{typeof x==='string'?x:JSON.stringify(x)}</code>)}
          </div>
        </details>}
      </div>}

      <div className="path-preview">
        <strong>생성될 경로</strong>
        {!newAgentProjectRoot.trim()&&<small className="path-preview-hint">프로젝트 경로를 입력하거나 선택하면 실제 생성 경로가 표시됩니다.</small>}
        <div><span>Cache</span><code>{pathPreview(newAgentCachePath,'cache')}</code></div>
        <div><span>Temp</span><code>{pathPreview(newAgentTempPath,'temp')}</code></div>
        <div><span>Output</span><code>{pathPreview(newAgentOutputPath,'output')}</code></div>
        <div><span>Venv</span><code>{pathPreview(newAgentVenvPath,'venv')}</code></div>
        <div><span>Models</span><code>{pathPreview(newAgentModelsPath,'models')}</code></div>
      </div>

      {selectedProjectId
        ? <button className="create-project-cta" onClick={()=>setScreen('WORKSPACE')}>
            분석된 프로젝트 작업공간 열기
          </button>
        : <button className="create-project-cta" onClick={createNewAgentProject}
            disabled={!newAgentName.trim()||!newAgentProjectRoot.trim()}>
            프로젝트 생성
          </button>}
      <small className="cta-note">
        {selectedProjectId
          ? `Project #${selectedProjectId} · 분석 정보와 프로젝트 정보가 PostgreSQL에 저장되어 있습니다.`
          : 'FastAPI를 통해 폴더를 만들고 PostgreSQL에 프로젝트 정보를 저장합니다.'}
      </small>
      {newAgentCreateResult&&<div className={newAgentCreateResult.ok?'ux-result good':'ux-result bad'}>{newAgentCreateResult.message}</div>}
    </aside>
    <UILayoutTemplateGallery
      open={uiLayoutGalleryOpen}
      value={uiLayoutConfig}
      purposeText={buildRequirementRequestFromCollectedInfo()}
      onClose={()=>setUiLayoutGalleryOpen(false)}
      onApply={(config)=>{
        setUiLayoutConfig(config)
        setUiLayoutGalleryOpen(false)
        setRequirementManualOverrides(prev=>({...prev,ui:uiLayoutSummary(config)}))
        setConfirmedInterviewRequirements(prev=>({...prev,ui_layout:config}))
        invalidateRequirementWorkflowAfterEdit('UI / Layout 템플릿을 변경했습니다. 선택한 레이아웃을 기준으로 Workflow와 코드 구조를 다시 설계할 수 있습니다.')
        setTimeout(()=>saveRequirementDraft(),0)
      }}
    />
  </div>
  }


  const activeTerminal =
    terminalSessions.find(t=>t.id===activeTerminalId)
    || terminalSessions[0]

  const updateTerminal=(id,patch)=>{
    setTerminalSessions(prev=>prev.map(t=>t.id===id?{...t,...patch}:t))
  }

  const waitForTerminalContainer=async(id,attempts=20)=>{
    for(let i=0;i<attempts;i+=1){
      if(xtermContainersRef.current[id]){
        return xtermContainersRef.current[id]
      }
      await new Promise(resolve=>setTimeout(resolve,25))
    }
    return null
  }

  const addTerminal=async()=>{
    const project=currentProject
    const projectRoot=
      project?.project_root
      || project?.root_path
      || root
      || ''

    if(!projectRoot){
      setTerminal(prev=>(prev||'')+'\n[터미널 생성 실패] 먼저 프로젝트를 선택하세요.\n')
      return null
    }

    const n=terminalSessions.length+1
    const id=`terminal-${Date.now()}-${n}`
    const projectId=project?.id||selectedProjectId||null
    const projectName=project?.name||currentProjectName||'프로젝트'

    const next={
      id,
      name:`Terminal ${n}`,
      projectId,
      projectName,
      root:projectRoot,
      cwd:projectRoot,
      command:'',
      output:'',
      busy:false,
      processState:'starting',
      exitCode:null,
    }

    setTerminalSessions(prev=>[...prev,next])
    setActiveTerminalProjectId(projectId)
    setActiveTerminalId(id)
    setFocusOwnerSafe('terminal')

    // React가 새 terminal DOM을 실제로 mount한 뒤 xterm을 먼저 준비합니다.
    // WebSocket history/ready 메시지가 xterm 생성보다 먼저 도착하면 prompt가
    // 유실되어 빈 터미널처럼 보일 수 있으므로 연결 순서를 보장합니다.
    const container=await waitForTerminalContainer(id)
    if(!container){
      setTerminalSessions(prev=>prev.map(t=>
        t.id===id
          ? {...t,processState:'exited',exitCode:1}
          : t
      ))
      setTerminalErrors(prev=>({
        ...prev,
        [id]:{
          stage:'terminal_create',
          message:'새 터미널 화면을 초기화하지 못했습니다.',
          root:projectRoot,
          sessionId:id,
          time:new Date().toLocaleString()
        }
      }))
      return null
    }

    await ensureXtermInstance(id)

    const ws=await connectProjectTerminal(
      {
        id:projectId,
        name:projectName,
        project_root:projectRoot
      },
      id
    )

    if(!ws){
      return null
    }

    setTimeout(()=>{
      const term=xtermInstancesRef.current[id]
      fitTerminalViewport(id)
      try{
        term?.refresh(0,Math.max(0,(term?.rows||1)-1))
        term?.scrollToBottom()
        term?.focus()
      }catch{}
    },80)

    return id
  }

  const runPowerShellTextInTerminal=async(scriptText,{sourceLabel='PowerShell'}={})=>{
    const script=String(scriptText||'').replace(/\r\n|\r/g,'\n')
    if(!script.trim()){
      window.alert('실행할 PowerShell 코드가 없습니다.')
      return false
    }

    let targetId=activeTerminalId
    let target=terminalSessions.find(t=>t.id===targetId)

    if(!target||target.processState==='exited'){
      targetId=await addTerminal()
      if(!targetId) return false
      target={
        id:targetId,
        projectId:currentProject?.id||selectedProjectId||null,
        projectName:currentProject?.name||currentProjectName||'프로젝트',
        root:currentProject?.project_root||currentProject?.root_path||root||'',
        cwd:currentProject?.project_root||currentProject?.root_path||root||''
      }
    }

    await waitForTerminalContainer(targetId)
    const term=await ensureXtermInstance(targetId)
    if(!term) return false

    let ws=terminalSocketsRef.current[targetId]
    if(!ws||ws.readyState!==WebSocket.OPEN){
      const projectRoot=target.root||root||''
      ws=await connectProjectTerminal({
        id:target.projectId||selectedProjectId||null,
        name:target.projectName||currentProjectName||'프로젝트',
        project_root:projectRoot
      },targetId)
    }

    if(!ws) return false
    if(ws.readyState===WebSocket.CONNECTING){
      await new Promise(resolve=>{
        ws.addEventListener('open',resolve,{once:true})
        setTimeout(resolve,2500)
      })
    }
    if(ws.readyState!==WebSocket.OPEN){
      window.alert('PowerShell 터미널 연결이 열리지 않았습니다.')
      return false
    }

    // Show exactly what will run in the active terminal, then execute the
    // whole block as one logical PowerShell command.  Backend v5.200+ wraps
    // multi-line commands in a UTF-8 ScriptBlock, preserving backticks,
    // Korean text, variables, and Set-Location state.
    const setter=xtermSetCommandLineRef.current[targetId]
    if(typeof setter==='function'){
      setter(script,script.length)
    }else{
      term.write(script.replace(/\n/g,'\r\n'))
    }

    term.write('\r\n')
    xtermCommandBuffersRef.current[targetId]=''
    xtermCursorIndexRef.current[targetId]=0

    const history=xtermCommandHistoryRef.current[targetId]||[]
    history.push(script)
    xtermCommandHistoryRef.current[targetId]=history
    xtermHistoryIndexRef.current[targetId]=history.length

    terminalCommandBusyRef.current[targetId]=true
    setTerminalSessions(prev=>prev.map(t=>t.id===targetId?{...t,busy:true}:t))
    ws.send(serializeTerminalClientMessage({type:'command',data:script}))
    setActiveTerminalId(targetId)
    setFocusOwnerSafe('terminal')

    requestAnimationFrame(()=>{
      try{
        term.scrollToBottom()
        term.focus()
      }catch{}
    })

    setTerminal(prev=>(prev||'')+`\n[${sourceLabel}] 터미널 실행 요청을 전송했습니다.\n`)
    return true
  }

  const runCurrentPowerShellFile=async({selectionOnly=false}={})=>{
    if(!selected?.toLowerCase?.().endsWith('.ps1')) return

    let script=code
    let label=`PowerShell 전체 실행 · ${selected}`

    if(selectionOnly){
      const editor=editorInstanceRef.current
      const selection=editor?.getSelection?.()
      const model=editor?.getModel?.()
      const selectedText=(selection&&model)
        ? model.getValueInRange(selection)
        : ''

      if(!selectedText.trim()){
        window.alert('선택된 PowerShell 코드가 없습니다.')
        return
      }
      script=selectedText
      label=`PowerShell 선택 실행 · ${selected}`
    }

    await runPowerShellTextInTerminal(script,{sourceLabel:label})
  }

  const stopPythonExecution=async()=>{
    const state=pythonExecutionState||{}
    if(!state.busy||!state.root||!state.sessionId) return null
    const runtimeSessionId=state.runtimeSessionId||state.sessionId
    const outputTerminalId=state.terminalSessionId||state.sessionId
    pythonStopRequestedRef.current=true
    try{
      if(state.kind==='sql'){
        sqlStopRequestedRef.current=true
        const result=await api('/sql/cancel',{
          method:'POST',
          body:JSON.stringify({root:state.root,connection_id:sqlProfile.connection_id||''})
        })
        const term=xtermInstancesRef.current[outputTerminalId]
        term?.write?.('\r\n\x1b[33m[실행 정지] Notebook SQL 실행 중지 요청을 보냈습니다.\x1b[0m\r\n')
        return result
      }
      const result=await api('/python/stop',{
        method:'POST',
        body:JSON.stringify({root:state.root,session_id:runtimeSessionId})
      })
      const term=xtermInstancesRef.current[outputTerminalId]
      term?.write?.('\r\n\x1b[33m[실행 정지] Python/Notebook 실행 중지 요청을 보냈습니다. 다음 실행은 새 Python 세션에서 시작됩니다.\x1b[0m\r\n')
      return result
    }catch(e){
      console.error('Notebook/Python 실행 중지 실패',e)
      return null
    }
  }

  const runCurrentPythonFile=async({selectionOnly=false}={})=>{
    const filePath=normalizeProjectRelativePath(selectedEditorFileRef.current||selected||'')
    if(!filePath.toLowerCase().endsWith('.py')) return

    const workspaceRoot=resolveWorkspaceRoot(
      editorFileRootRef.current?.[filePath]
      ||editorFileRootRef.current?.[selectedEditorFileRef.current]
      ||fileTreeRootRef.current
      ||''
    )
    if(!workspaceRoot){
      setProjectSwitcherOpen(true)
      window.alert('Python 파일을 실행할 프로젝트 경로를 확인하지 못했습니다. 상단 프로젝트 선택에서 프로젝트를 지정해 주세요.')
      return
    }

    let pythonCode=code
    let mode='full'
    let sourceLabel=`Python 전체 실행 · ${filePath}`

    if(selectionOnly){
      const editor=editorInstanceRef.current
      const selection=editor?.getSelection?.()
      const model=editor?.getModel?.()
      const selectedText=(selection&&model)
        ? model.getValueInRange(selection)
        : ''

      if(!selectedText.trim()){
        window.alert('선택된 Python 코드가 없습니다.')
        return
      }

      pythonCode=selectedText
      mode='selection'
      sourceLabel=`Python 선택 실행 · ${filePath}`
    }

    if(!String(pythonCode||'').trim()){
      window.alert('실행할 Python 코드가 없습니다.')
      return
    }

    let targetId=activeTerminalId
    let target=terminalSessions.find(t=>t.id===targetId)
    if(!target||target.processState==='exited'){
      targetId=await addTerminal()
      if(!targetId) return
    }

    await waitForTerminalContainer(targetId)
    const term=await ensureXtermInstance(targetId)
    if(!term){
      window.alert('Python 실행 결과를 표시할 터미널을 준비하지 못했습니다.')
      return
    }

    const terminalSessionId=targetId||'python-default'
    pythonStopRequestedRef.current=false
    setPythonExecutionState({busy:true,root:workspaceRoot,sessionId:terminalSessionId,label:sourceLabel})
    const displayCode=selectionOnly
      ? String(pythonCode).replace(/\r\n|\r/g,'\n')
      : ''

    try{
      term.write(`\r\n\x1b[36m[${sourceLabel}]\x1b[0m\r\n`)
      if(displayCode){
        term.write(displayCode.replace(/\n/g,'\r\n'))
        term.write('\r\n')
      }
      term.write('\x1b[90m실행 중...\x1b[0m\r\n')
      term.scrollToBottom()

      const result=await api('/python/execute',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          relative_path:filePath,
          code:pythonCode,
          mode,
          session_id:terminalSessionId,
        })
      })

      const stdout=String(result?.stdout||'')
      const stderr=String(result?.stderr||'')
      const trace=String(result?.traceback||'')

      if(stdout){
        term.write(stdout.replace(/\r\n|\r|\n/g,'\r\n'))
        if(!stdout.endsWith('\n')&&!stdout.endsWith('\r')) term.write('\r\n')
      }
      if(stderr){
        term.write('\x1b[33m'+stderr.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m')
        if(!stderr.endsWith('\n')&&!stderr.endsWith('\r')) term.write('\r\n')
      }
      if(result?.cancelled){
        term.write('\x1b[33m[실행 취소] 사용자가 Python 실행을 중지했습니다.\x1b[0m\r\n')
      }else if(!result?.ok){
        const errorText=trace||`${result?.error_type||'PythonError'}: ${result?.error_message||'실행 실패'}`
        term.write('\x1b[31m'+errorText.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m')
        if(!errorText.endsWith('\n')&&!errorText.endsWith('\r')) term.write('\r\n')

        const dependency=result?.dependency_diagnostic
        if(dependency?.code==='PYTHON_MODULE_NOT_FOUND'){
          const lines=[
            '',
            `[패키지 설치 필요] ${dependency.message||''}`,
            `설치 명령: ${dependency.install_command||''}`,
          ]
          if(dependency.requirements_command){
            lines.push(`requirements.txt 전체 설치: ${dependency.requirements_command}`)
          }
          lines.push('※ 에이전트 스튜디오는 프로젝트 가상환경을 자동 변경하지 않습니다.')
          term.write('\x1b[33m'+lines.join('\r\n')+'\x1b[0m\r\n')
        }
      }else if(!stdout&&!stderr){
        term.write('\x1b[90m(출력 없음)\x1b[0m\r\n')
      }

      term.write(`\x1b[90mPython: ${String(result?.interpreter||'').replace(/\x1b/g,'')} · 세션: ${selectionOnly?'유지':'초기화 후 유지'}\x1b[0m\r\n`)
      term.scrollToBottom()
      setActiveTerminalId(targetId)
      setTerminal(prev=>(prev||'')+`\n[${sourceLabel}] ${result?.ok?'완료':'실패'}\n`)
    }catch(e){
      if(pythonStopRequestedRef.current){
        term.write('\x1b[33m[실행 취소] 사용자가 Python 실행을 중지했습니다.\x1b[0m\r\n')
      }else{
        const message=`Python 실행 실패: ${e}`
        term.write('\x1b[31m'+message.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m\r\n')
        term.scrollToBottom()
        window.alert(message)
      }
    }finally{
      setPythonExecutionState(prev=>prev.sessionId===terminalSessionId?{busy:false,root:'',sessionId:'',label:''}:prev)
      pythonStopRequestedRef.current=false
    }
  }


  const executeNotebookPythonCode=async({pythonCode,filePath,projectRoot='',cellIndex=0,mode='selection',selectionOnly=false}={})=>{
    const normalizedPath=normalizeProjectRelativePath(filePath||selectedEditorFileRef.current||selected||'')
    const workspaceRoot=resolveWorkspaceRoot(
      projectRoot
      ||editorFileRootRef.current?.[normalizedPath]
      ||editorFileRootRef.current?.[selectedEditorFileRef.current]
      ||fileTreeRootRef.current
      ||''
    )
    if(!workspaceRoot){
      setProjectSwitcherOpen(true)
      window.alert('Notebook이 열린 프로젝트 경로를 확인하지 못했습니다. 상단 프로젝트 선택에서 프로젝트를 지정하거나 프로젝트 파일 트리에서 Notebook을 다시 열어 주세요.')
      return null
    }
    if(!String(pythonCode||'').trim()){
      window.alert('실행할 Notebook 코드가 없습니다.')
      return null
    }

    const sqlMode=looksLikeNotebookSqlCode(pythonCode)
    const executableCode=sqlMode?normalizeNotebookSqlCode(pythonCode):String(pythonCode||'')

    let targetId=activeTerminalId
    let target=terminalSessions.find(t=>t.id===targetId)
    if(!target||target.processState==='exited'){
      targetId=await addTerminal()
      if(!targetId) return null
    }

    await waitForTerminalContainer(targetId)
    const term=await ensureXtermInstance(targetId)
    if(!term){
      window.alert('Notebook 실행 결과를 표시할 터미널을 준비하지 못했습니다.')
      return null
    }

    const terminalSessionId=targetId||'python-default'
    const runtimeSessionId=`notebook::${normalizedPath.toLocaleLowerCase()}`
    const sourceLabel=`Notebook ${sqlMode?'SQL':(selectionOnly?'선택':'셀')} 실행 · ${normalizedPath} · Cell ${Number(cellIndex)+1}`
    pythonStopRequestedRef.current=false
    setPythonExecutionState({
      busy:true,
      root:workspaceRoot,
      sessionId:runtimeSessionId,
      runtimeSessionId,
      terminalSessionId,
      label:sourceLabel,
      kind:sqlMode?'sql':'python'
    })

    try{
      term.write(`\r\n\x1b[36m[${sourceLabel}]\x1b[0m\r\n`)
      if(selectionOnly||sqlMode){
        term.write(String(executableCode).replace(/\r\n|\r|\n/g,'\r\n'))
        term.write('\r\n')
      }
      term.write('\x1b[90m실행 중...\x1b[0m\r\n')
      term.scrollToBottom()

      if(sqlMode){
        if(!sqlConnectionStatus?.connected){
          const message='Notebook SQL 셀을 실행하려면 우측 DB 연결 영역에서 데이터베이스를 먼저 연결해야 합니다.'
          term.write('\x1b[31m'+message+'\x1b[0m\r\n')
          return {ok:false,stdout:'',stderr:'',error_type:'DatabaseNotConnected',error_message:message,traceback:''}
        }
        try{
          const sqlResult=await api('/sql/execute',{
            method:'POST',
            body:JSON.stringify({root:workspaceRoot,sql:executableCode,max_rows:1000})
          })
          const stdout=formatNotebookSqlResult(sqlResult)
          setSqlQueryResult(sqlResult)
          setSqlResultTab(sqlResult?.columns?.length?'DATA':'MESSAGES')
          setSqlMessages(prev=>[{
            type:'success',
            text:`Notebook SQL 셀 실행 완료 · ${sqlResult?.message||''} · ${sqlResult?.elapsed_ms||0}ms`,
            time:new Date().toLocaleTimeString()
          },...prev].slice(0,100))
          term.write('\x1b[32m'+stdout.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m')
          term.write(`\x1b[90mDB: ${String(sqlConnectionStatus?.profile?.name||sqlProfile?.name||sqlConnectionStatus?.db_type||sqlProfile?.db_type||'연결된 DB')} · Notebook SQL 자동 감지\x1b[0m\r\n`)
          term.scrollToBottom()
          setActiveTerminalId(targetId)
          setTerminal(prev=>(prev||'')+`\n[${sourceLabel}] 완료\n`)
          return {ok:true,stdout,stderr:'',traceback:'',error_type:'',error_message:'',sql_result:sqlResult,execution_kind:'sql'}
        }catch(e){
          if(sqlStopRequestedRef.current){
            const message='사용자가 Notebook SQL 실행을 중지했습니다.'
            term.write('\x1b[33m[실행 취소] '+message+'\x1b[0m\r\n')
            return {ok:false,cancelled:true,error_type:'ExecutionCancelled',error_message:message,stdout:'',stderr:'',traceback:''}
          }
          const message=`Notebook SQL 실행 실패: ${e}`
          term.write('\x1b[31m'+message.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m\r\n')
          term.scrollToBottom()
          return {ok:false,stdout:'',stderr:'',error_type:'SqlExecutionError',error_message:String(e),traceback:message,execution_kind:'sql'}
        }
      }

      const result=await api('/python/execute',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          relative_path:normalizedPath,
          code:executableCode,
          mode:mode==='full'?'full':'selection',
          session_id:runtimeSessionId,
          capture_last_expression:true,
          notebook_mode:true,
          cell_index:Number(cellIndex),
        })
      })

      const stdout=String(result?.stdout||'')
      const stderr=String(result?.stderr||'')
      const trace=String(result?.traceback||'')
      if(stdout){
        term.write(stdout.replace(/\r\n|\r|\n/g,'\r\n'))
        if(!stdout.endsWith('\n')&&!stdout.endsWith('\r')) term.write('\r\n')
      }
      if(stderr){
        term.write('\x1b[33m'+stderr.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m')
        if(!stderr.endsWith('\n')&&!stderr.endsWith('\r')) term.write('\r\n')
      }
      if(!result?.ok){
        const errorText=trace||`${result?.error_type||'PythonError'}: ${result?.error_message||'실행 실패'}`
        term.write('\x1b[31m'+errorText.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m')
        if(!errorText.endsWith('\n')&&!errorText.endsWith('\r')) term.write('\r\n')

        const dependency=result?.dependency_diagnostic
        if(dependency?.code==='PYTHON_MODULE_NOT_FOUND'){
          const lines=[
            '',
            `[패키지 설치 필요] ${dependency.message||''}`,
            `설치 명령: ${dependency.install_command||''}`,
          ]
          if(dependency.requirements_command) lines.push(`requirements.txt 전체 설치: ${dependency.requirements_command}`)
          lines.push('※ 에이전트 스튜디오는 프로젝트 가상환경을 자동 변경하지 않습니다.')
          term.write('\x1b[33m'+lines.join('\r\n')+'\x1b[0m\r\n')
        }
      }else if(!stdout&&!stderr){
        term.write('\x1b[90m(출력 없음)\x1b[0m\r\n')
      }

      term.write(`\x1b[90mPython: ${String(result?.interpreter||'').replace(/\x1b/g,'')} · Notebook 세션: ${runtimeSessionId} · Root: ${workspaceRoot}\x1b[0m\r\n`)
      term.scrollToBottom()
      setActiveTerminalId(targetId)
      setTerminal(prev=>(prev||'')+`\n[${sourceLabel}] ${result?.ok?'완료':'실패'}\n`)
      return result
    }catch(e){
      if(pythonStopRequestedRef.current){
        term.write('\x1b[33m[실행 취소] 사용자가 Notebook 실행을 중지했습니다.\x1b[0m\r\n')
        return {ok:false,cancelled:true,error_type:'ExecutionCancelled',error_message:'사용자가 Notebook 실행을 중지했습니다.',stdout:'',stderr:'',traceback:''}
      }
      const message=`Notebook Python 실행 실패: ${e}`
      term.write('\x1b[31m'+message.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m\r\n')
      term.scrollToBottom()
      throw e
    }finally{
      setPythonExecutionState(prev=>(prev.runtimeSessionId===runtimeSessionId||prev.sessionId===runtimeSessionId)?{busy:false,root:'',sessionId:'',runtimeSessionId:'',terminalSessionId:'',label:'',kind:''}:prev)
      pythonStopRequestedRef.current=false
    }
  }

  const stopCurrentCmdFile=async()=>{
    const executionId=cmdExecution?.executionId
    if(!executionId||!cmdExecution?.busy) return
    try{
      await api(`/files/execute-cmd/${encodeURIComponent(executionId)}/stop`,{method:'POST'})
      setTerminal(prev=>(prev||'')+'\n[CMD 실행 정지] 사용자가 실행을 중지했습니다.\n')
    }catch(e){
      window.alert(`CMD 실행 중지 실패: ${e}`)
    }finally{
      setCmdExecution({busy:false,executionId:'',path:'',pid:null})
    }
  }

  const runCurrentCmdFile=async()=>{
    const filePath=normalizeProjectRelativePath(selectedEditorFileRef.current||selected||'')
    if(!filePath.toLowerCase().endsWith('.cmd')||cmdExecution?.busy) return

    const workspaceRoot=resolveWorkspaceRoot(
      editorFileRootRef.current?.[filePath]
      ||editorFileRootRef.current?.[selectedEditorFileRef.current]
      ||fileTreeRootRef.current
      ||''
    )
    if(!workspaceRoot){
      setProjectSwitcherOpen(true)
      window.alert('CMD 파일을 실행할 프로젝트 경로를 확인하지 못했습니다. 상단 프로젝트 선택에서 프로젝트를 지정해 주세요.')
      return
    }

    try{
      const result=await api('/files/execute-cmd',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          relative_path:filePath
        })
      })
      const executionId=String(result?.execution_id||'')
      setCmdExecution({busy:!!executionId,executionId,path:result?.path||filePath,pid:result?.pid||null})
      setTerminal(prev=>(prev||'')+`\n[CMD 실행] ${result?.path||filePath}${result?.pid?` · PID ${result.pid}`:''}\n`)
      if(executionId){
        const poll=async()=>{
          try{
            const state=await api(`/files/execute-cmd/${encodeURIComponent(executionId)}/status`)
            if(state?.running){
              setTimeout(poll,800)
            }else{
              setCmdExecution(prev=>prev.executionId===executionId?{busy:false,executionId:'',path:'',pid:null}:prev)
            }
          }catch{
            setCmdExecution(prev=>prev.executionId===executionId?{busy:false,executionId:'',path:'',pid:null}:prev)
          }
        }
        setTimeout(poll,800)
      }
    }catch(e){
      setCmdExecution({busy:false,executionId:'',path:'',pid:null})
      window.alert(`CMD 실행 실패: ${e}`)
    }
  }

  useEffect(()=>{
    const onEditorRunShortcut=(event)=>{
      if(workspaceTab!=='CODE') return

      const path=normalizeProjectRelativePath(selectedEditorFileRef.current||selected||'').toLowerCase()

      if(event.key==='F5' && (path.endsWith('.ps1')||path.endsWith('.py')||path.endsWith('.cmd')||path.endsWith('.sql')||path.endsWith('.ipynb'))){
        event.preventDefault()
        event.stopPropagation()
        if(path.endsWith('.ps1')){
          runCurrentPowerShellFile({selectionOnly:false})
        }else if(path.endsWith('.py')){
          runCurrentPythonFile({selectionOnly:false})
        }else if(path.endsWith('.sql')){
          runSqlEditor({selectionOnly:false})
        }else if(path.endsWith('.ipynb')){
          notebookEditorControllerRef.current?.runAll?.()
        }else{
          runCurrentCmdFile()
        }
        return
      }

      if(event.key==='F8' && (path.endsWith('.ps1')||path.endsWith('.py')||path.endsWith('.sql')||path.endsWith('.ipynb'))){
        event.preventDefault()
        event.stopPropagation()
        if(path.endsWith('.sql')){
          runSqlEditor({selectionOnly:true})
        }else if(path.endsWith('.py')){
          runCurrentPythonFile({selectionOnly:true})
        }else if(path.endsWith('.ipynb')){
          notebookEditorControllerRef.current?.runSelection?.()
        }else{
          runCurrentPowerShellFile({selectionOnly:true})
        }
      }
    }

    window.addEventListener('keydown',onEditorRunShortcut,true)
    return()=>window.removeEventListener('keydown',onEditorRunShortcut,true)
  },[workspaceTab,selected,code,activeWorkspaceRoot,sqlQueryBusy,sqlConnectionStatus?.connected])

  const removeTerminal=(id)=>{
    if(terminalSessions.length===1) return

    terminalIntentionalCloseRef.current[id]=true

    const ws=terminalSocketsRef.current[id]
    try{
      if(ws){
        ws.close(1000,'user_closed_terminal')
      }
    }catch{}
    delete terminalSocketsRef.current[id]

    try{
      xtermDisposablesRef.current[id]?.dispose?.()
    }catch{}
    delete xtermDisposablesRef.current[id]

    try{
      xtermInstancesRef.current[id]?.dispose?.()
    }catch{}
    delete xtermInstancesRef.current[id]
    delete xtermContainersRef.current[id]
    delete xtermFitAddonsRef.current[id]
    delete xtermCommandBuffersRef.current[id]
    delete xtermCommandHistoryRef.current[id]
    delete xtermHistoryIndexRef.current[id]
    delete xtermCursorIndexRef.current[id]
    delete xtermPromptRef.current[id]
    delete xtermOutputParseBufferRef.current[id]
    delete xtermRequiredColsRef.current[id]
    delete xtermSetCommandLineRef.current[id]
    delete xtermKeyboardSelectionRef.current[id]
    delete terminalCwdRef.current[id]
    delete terminalRootRef.current[id]
    closeTerminalCompletion(id)

    setTerminalErrors(prev=>({
      ...prev,
      [id]:null
    }))

    setTerminalSessions(prev=>{
      const index=prev.findIndex(t=>t.id===id)
      const next=prev.filter(t=>t.id!==id)

      if(activeTerminalId===id){
        const nextActive=
          next[Math.min(index,next.length-1)]
          || next[next.length-1]
          || null

        setActiveTerminalId(nextActive?.id||'')
        setActiveTerminalProjectId(nextActive?.projectId||null)
      }

      return next
    })
  }

  const startRenameTerminal=(terminal)=>{
    setTerminalNameEditId(terminal.id)
    setTerminalNameDraft(terminal.name)
  }

  const saveTerminalName=(id)=>{
    const name=(terminalNameDraft||'').trim()
    if(name){
      updateTerminal(id,{name})
    }
    setTerminalNameEditId(null)
    setTerminalNameDraft('')
  }

  const runTerminalSession=async(id)=>{
    await sendTerminalInput(id)
  }


  const askCodeEditorLLM=async()=>{
    const prompt=codeEditPrompt.trim()
    if(!prompt) return
    if(codeEditAttachments.length&&!codeEditAttachmentAnalysis.ready) return

    const projectMode=codeEditScope==='PROJECT'
    const workspaceRoot=resolveWorkspaceRoot(
      projectMode ? (fileTreeRootRef.current||'') : (editorFileRootRef.current?.[selected]||fileTreeRootRef.current||'')
    )

    if(!workspaceRoot){
      setCodeEditChat(prev=>[
        ...prev,
        {role:'user',content:prompt},
        {
          role:'assistant',
          content:'먼저 작업할 프로젝트를 선택해주세요.'
        }
      ])
      setCodeEditPrompt('')
      return
    }

    if(!projectMode&&!selected){
      setCodeEditChat(prev=>[
        ...prev,
        {role:'user',content:prompt},
        {
          role:'assistant',
          content:'파일 단위 작업에서는 먼저 수정할 파일을 선택해주세요.'
        }
      ])
      setCodeEditPrompt('')
      return
    }

    if(!projectMode&&editorLoadErrors[selected]){
      setCodeEditChat(prev=>[
        ...prev,
        {role:'user',content:prompt},
        {
          role:'assistant',
          content:'현재 파일은 불러오기에 실패한 상태입니다. 원본 보호를 위해 LLM 코드 수정도 차단했습니다. 파일을 다시 불러온 뒤 시도해주세요.'
        }
      ])
      setCodeEditPrompt('')
      return
    }

    if(!projectMode&&isBinaryPreviewFile(selected)){
      const presentation=isPresentationFile(selected)
      setCodeEditChat(prev=>[
        ...prev,
        {role:'user',content:prompt},
        {
          role:'assistant',
          content:presentation
            ? 'PPT/PPTX는 바이너리 문서이므로 파일 단위 코드 수정 대상이 아닙니다. 원본을 보존한 채 PDF 미리보기로 열립니다.'
            : 'PDF는 바이너리 문서이므로 파일 단위 코드 수정 대상이 아닙니다. PDF는 미리보기 전용으로 열립니다.'
        }
      ])
      setCodeEditPrompt('')
      return
    }

    const targetPath=selected
    const currentCode=
      targetPath
        ? (editorFileContents[targetPath] ?? code ?? '')
        : ''

    setCodeEditChat(prev=>[
      ...prev,
      {
        role:'user',
        content:
          `${projectMode?'[프로젝트]':'[파일]'} ${prompt}`
          +(codeEditAttachments.length
            ? `\n\n📎 참고 파일: ${codeEditAttachments.map(item=>item.name).join(', ')}`
            : '')
      }
    ])
    scrollCodeEditChatToBottom('smooth')

    setCodeEditPrompt('')
    setCodeEditBusy(true)
    setCodeEditProposal(null)
    setCodeDiffReview(null)

    try{
      if(projectMode){
        const result=await api('/ai/project-edit',{
          method:'POST',
          body:JSON.stringify({
            root:workspaceRoot,
            instruction:prompt,
            max_context_files:10,
            attachment_ids:codeEditAttachments.map(item=>item.attachment_id)
          })
        })

        const changedFiles=
          Array.isArray(result.files)
            ? result.files
            : []

        if(!changedFiles.length){
          throw new Error(
            'Backend에서 생성/수정된 프로젝트 파일이 반환되지 않았습니다.'
          )
        }

        // 프로젝트 단위 작업은 Backend가 실제 파일까지 저장합니다.
        // 이미 열려 있는 탭은 새 내용으로 즉시 동기화합니다.
        setEditorFileContents(prev=>{
          const next={...prev}

          for(const file of changedFiles){
            if(file?.path){
              next[file.path]=file.content??''
            }
          }

          return next
        })

        setEditorFileDirty(prev=>{
          const next={...prev}

          for(const file of changedFiles){
            if(file?.path){
              next[file.path]=false
            }
          }

          return next
        })

        await loadFiles(workspaceRoot)

        const primary=
          result.primary_file
          || changedFiles[0]?.path
          || ''

        if(primary){
          // 프로젝트 결과 대표 파일을 코드 편집기에 자동 활성화
          setWorkspaceTab('CODE')
          setFocusOwnerSafe('editor')

          setOpenEditorFiles(prev=>
            prev.includes(primary)
              ? prev
              : [...prev,primary]
          )

          const primaryResult=
            changedFiles.find(f=>f.path===primary)

          if(primaryResult){
            setSelected(primary)
            setFileTreeSelected(primary)
            setCode(primaryResult.content??'')
          }else{
            await openFile(primary,workspaceRoot)
          }

          setTimeout(()=>{
            try{ editorInstanceRef.current?.focus() }catch{}
          },0)
        }

        const created=Number(result.created_count||0)
        const updated=Number(result.updated_count||0)

        setCodeEditChat(prev=>[
          ...prev,
          {
            role:'assistant',
            content:
              `${result.summary||'프로젝트 코딩 작업을 완료했습니다.'} `
              +`신규 파일 ${created}개, 수정 파일 ${updated}개를 프로젝트에 저장했습니다.`
              +(Array.isArray(result?.attachment_warnings)&&result.attachment_warnings.length
                ? `\n[참고 파일 알림] ${result.attachment_warnings.join(' / ')}`
                : '')
          }
        ])

        return
      }

      // FILE mode
      const result=await api('/ai/edit',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          path:targetPath,
          instruction:prompt,
          content:currentCode,
          active_cell_index:isNotebookFile(targetPath)
            ? notebookEditorControllerRef.current?.getActiveCellIndex?.()
            : null,
          attachment_ids:codeEditAttachments.map(item=>item.attachment_id)
        })
      })

      const proposedCode =
        result.code
        || result.content
        || result.updated_code
        || result.result
        || ''

      if(!proposedCode){
        throw new Error(
          'Backend에서 수정된 코드가 반환되지 않았습니다.'
        )
      }

      const explanation =
        (result.message || '코드 수정 제안을 만들었습니다.')
        +(Array.isArray(result?.attachment_warnings)&&result.attachment_warnings.length
          ? `\n[참고 파일 알림] ${result.attachment_warnings.join(' / ')}`
          : '')

      // FILE 모드에서는 AI 응답을 즉시 원본 Editor에 덮어쓰지 않습니다.
      // 우측 `AI 변경 제안` 탭에서 먼저 코드를 검토한 뒤 Apply -> Diff -> 적용
      // 순서로 사용자가 명시적으로 반영하도록 합니다.
      setCodeEditProposal({
        path:targetPath,
        code:proposedCode,
        displayCode:result.cell_code||proposedCode,
        editScope:result.edit_scope||'file',
        activeCellIndex:result.active_cell_index??null,
        contextBudget:result.context_budget||null,
        baseCode:currentCode,
        explanation,
        instruction:prompt,
        createdAt:new Date().toISOString()
      })
      setCodeDiffReview(null)
      setCodeRightPanelTab('PROPOSAL')
      setWorkspaceRightCollapsed(false)
      setWorkspaceTab('CODE')

      setCodeEditChat(prev=>[
        ...prev,
        {
          role:'assistant',
          content:
            explanation
            +' 우측 `AI 변경 제안` 탭에서 코드를 확인한 뒤 Apply를 눌러 현재 소스와 비교할 수 있습니다.'
        }
      ])

    }catch(e){
      let readableError=String(e?.message||e)
      if(e?.responseBody){
        try{
          const parsed=JSON.parse(e.responseBody)
          const detail=parsed?.detail||parsed
          if(detail?.code==='CONTEXT_BUDGET_EXCEEDED'||detail?.code==='MODEL_CONTEXT_OVERFLOW'){
            readableError=detail.message||'LLM Context 길이를 초과했습니다.'
            if(detail.active_cell_index!==undefined){
              readableError+=` 대상 Notebook Cell ${Number(detail.active_cell_index)+1}.`
            }
            if(detail.prompt_chars){
              readableError+=` 요청 Context 약 ${Number(detail.prompt_chars).toLocaleString('ko-KR')}자.`
            }
          }else if(typeof detail?.message==='string'){
            readableError=detail.message
          }else if(typeof detail==='string'){
            readableError=detail
          }
        }catch{}
      }
      setCodeEditChat(prev=>[
        ...prev,
        {
          role:'assistant',
          content:
            `${projectMode?'프로젝트 코딩':'코드 수정'} 실패: `
            +readableError
        }
      ])
    }finally{
      setCodeEditBusy(false)
    }
  }

  const openCodeEditDiffReview=async()=>{
    if(!codeEditProposal?.code||!codeEditProposal?.path) return

    const proposalPath=codeEditProposal.path

    if(!openEditorFilesRef.current?.includes(proposalPath)){
      try{ await openFile(proposalPath) }catch{}
    }else{
      activateEditorFile(proposalPath)
    }

    const currentContent=
      editorFileContents[proposalPath]
      ?? (selectedEditorFileRef.current===proposalPath?code:'')
      ?? codeEditProposal.baseCode
      ?? ''

    setCodeDiffReview({
      path:proposalPath,
      original:currentContent,
      modified:codeEditProposal.code,
      explanation:codeEditProposal.explanation||'',
      instruction:codeEditProposal.instruction||''
    })
    setWorkspaceTab('CODE')
  }

  const applyCodeEditProposal=()=>{
    if(!codeDiffReview?.modified||!codeDiffReview?.path) return

    const targetPath=codeDiffReview.path
    const nextCode=codeDiffReview.modified

    setSelected(targetPath)
    setFileTreeSelected(targetPath)
    setCode(nextCode)

    setOpenEditorFiles(prev=>
      prev.includes(targetPath)?prev:[...prev,targetPath]
    )

    setEditorFileContents(prev=>({
      ...prev,
      [targetPath]:nextCode
    }))

    setEditorFileDirty(prev=>({
      ...prev,
      [targetPath]:true
    }))

    setCodeEditChat(prev=>[
      ...prev,
      {
        role:'assistant',
        content:'Diff에서 확인한 AI 변경안을 현재 편집기에 머지했습니다. 아직 디스크에는 저장하지 않았습니다. Ctrl+S로 저장하세요.'
      }
    ])

    setCodeDiffReview(null)
    setCodeEditProposal(null)
  }

  const cancelCodeDiffReview=()=>{
    setCodeDiffReview(null)
  }

  const discardCodeEditProposal=()=>{
    setCodeDiffReview(null)
    setCodeEditProposal(null)
    setCodeRightPanelTab('FILES')
    setCodeEditChat(prev=>[
      ...prev,
      {role:'assistant',content:'AI 변경 제안을 취소했습니다.'}
    ])
  }


  const buildCurrentFileTextSearchResults=(query)=>{
    const needle=String(query||'')
    if(!needle.trim()||!selected) return []
    const loweredNeedle=needle.toLocaleLowerCase()
    const results=[]
    const pushTextMatches=(text,extra={})=>{
      const lines=String(text||'').replace(/\r\n|\r/g,'\n').split('\n')
      for(let lineIndex=0;lineIndex<lines.length;lineIndex+=1){
        const rawLine=lines[lineIndex]
        const compare=rawLine.toLocaleLowerCase()
        let start=0
        while(true){
          const column=compare.indexOf(loweredNeedle,start)
          if(column<0) break
          results.push({
            path:selected,
            line_number:lineIndex+1,
            column:column+1,
            snippet:rawLine.trim().slice(0,240),
            ...extra
          })
          if(results.length>=300) return
          start=column+Math.max(1,loweredNeedle.length)
        }
      }
    }

    if(isNotebookFile(selected)){
      try{
        const notebook=JSON.parse(String(code||''))
        const cells=Array.isArray(notebook?.cells)?notebook.cells:[]
        cells.forEach((cell,cellIndex)=>{
          if(results.length>=300) return
          const source=Array.isArray(cell?.source)?cell.source.join(''):String(cell?.source||'')
          pushTextMatches(source,{
            cell_index:cellIndex,
            cell_number:cellIndex+1,
            cell_type:String(cell?.cell_type||'')
          })
        })
        return results
      }catch{
        // Invalid/partially edited notebook JSON: fall back to the live buffer.
      }
    }
    pushTextMatches(code)
    return results
  }

  const openEditorTextSearch=(scope='CURRENT')=>{
    setEditorTextSearchScope(scope)
    setEditorTextSearchOpen(true)
    setEditorTextSearchError('')
    setEditorTextSearchResults([])
    setEditorTextSearchMeta(null)
    window.setTimeout(()=>editorTextSearchInputRef.current?.focus?.(),0)
  }

  const runEditorTextSearch=async()=>{
    const requestId=++editorTextSearchRequestRef.current
    const query=String(editorTextSearchQuery||'').trim()
    if(!query){
      setEditorTextSearchResults([])
      setEditorTextSearchMeta(null)
      setEditorTextSearchError('찾을 텍스트를 입력하세요.')
      return
    }
    setEditorTextSearchBusy(true)
    setEditorTextSearchError('')
    try{
      if(editorTextSearchScope==='CURRENT'){
        if(!selected){
          setEditorTextSearchResults([])
          setEditorTextSearchError('현재 열린 파일이 없습니다.')
          return
        }
        if(isPdfFile(selected)){
          const pdfKey=normalizeProjectRelativePath(selected)
          setPdfSearchNavigation(prev=>{
            if(!prev?.[pdfKey]) return prev
            const next={...prev}
            delete next[pdfKey]
            return next
          })
          const workspaceRoot=resolveWorkspaceRoot(editorFileRootRef.current?.[selected]||fileTreeRootRef.current||'')
          if(!workspaceRoot){
            setEditorTextSearchResults([])
            setEditorTextSearchError('PDF를 검색할 프로젝트 root를 확인할 수 없습니다.')
            return
          }
          const response=await api('/files/search-text',{
            method:'POST',
            body:JSON.stringify({
              root:workspaceRoot,
              relative_path:normalizeProjectRelativePath(selected),
              query,
              max_results:300,
              max_files:1
            })
          })
          if(requestId!==editorTextSearchRequestRef.current) return
          const results=Array.isArray(response?.results)?response.results:[]
          setEditorTextSearchResults(results)
          setEditorTextSearchMeta(response||null)
          if(response?.document_type==='pdf' && Number(response?.pdf_text_pages||0)===0){
            setEditorTextSearchError('이 PDF에서 검색 가능한 텍스트를 추출하지 못했습니다. 이미지로만 된 PDF는 OCR이 필요할 수 있습니다.')
          }
          return
        }
        if(isBinaryPreviewFile(selected)||isPresentationFile(selected)||isDatabaseDiagramFile(selected)){
          setEditorTextSearchResults([])
          setEditorTextSearchError('현재 파일 형식은 텍스트 찾기를 지원하지 않습니다.')
          return
        }
        const results=buildCurrentFileTextSearchResults(query)
        setEditorTextSearchResults(results)
        setEditorTextSearchMeta({files_scanned:1,truncated:results.length>=300,live_buffer:true})
        return
      }

      const workspaceRoot=resolveWorkspaceRoot(fileTreeRootRef.current||editorFileRootRef.current?.[selected]||'')
      if(!workspaceRoot){
        setEditorTextSearchResults([])
        setEditorTextSearchError('프로젝트 root를 확인할 수 없습니다. 프로젝트를 다시 선택해 주세요.')
        return
      }
      const response=await api('/files/search-text',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          query,
          max_results:300,
          max_files:10000
        })
      })
      if(requestId!==editorTextSearchRequestRef.current) return
      setEditorTextSearchResults(Array.isArray(response?.results)?response.results:[])
      setEditorTextSearchMeta(response||null)
    }catch(e){
      if(requestId===editorTextSearchRequestRef.current){
        setEditorTextSearchResults([])
        setEditorTextSearchMeta(null)
        setEditorTextSearchError(String(e?.message||e))
      }
    }finally{
      if(requestId===editorTextSearchRequestRef.current) setEditorTextSearchBusy(false)
    }
  }

  const revealEditorTextSearchResult=async(result)=>{
    const path=normalizeProjectRelativePath(result?.path||selected)
    if(!path) return
    const workspaceRoot=editorFileRootRef.current?.[path]||fileTreeRootRef.current||resolveWorkspaceRoot()
    if(path!==selected){
      try{ await openFile(path,workspaceRoot) }catch{return}
    }
    const reveal=()=>{
      if(isPdfFile(path) && Number(result?.page_number||0)>0){
        const key=normalizeProjectRelativePath(path)
        setPdfSearchNavigation(prev=>({
          ...prev,
          [key]:{
            page:Number(result.page_number),
            query:String(editorTextSearchQuery||''),
            snippet:String(result?.match_line||result?.snippet||''),
            matchId:String(result?.match_id||''),
            nonce:Date.now()
          }
        }))
        return true
      }
      if(Number.isInteger(result?.cell_index) && notebookEditorControllerRef.current?.revealSearchMatch){
        notebookEditorControllerRef.current.revealSearchMatch(
          Number(result.cell_index),
          Number(result.line_number||1),
          Number(result.column||1),
          String(editorTextSearchQuery||'').length
        )
        return true
      }
      const editor=editorInstanceRef.current
      if(!editor?.setSelection) return false
      const line=Math.max(1,Number(result?.line_number||1))
      const column=Math.max(1,Number(result?.column||1))
      const length=Math.max(1,String(editorTextSearchQuery||'').length)
      editor.revealLineInCenter?.(line)
      editor.setSelection({
        startLineNumber:line,
        startColumn:column,
        endLineNumber:line,
        endColumn:column+length
      })
      editor.focus?.()
      return true
    }
    window.setTimeout(()=>{ if(!reveal()) window.setTimeout(reveal,180) },60)
  }


  const buildProjectTree=(fileList,dirList=[])=>{
    const rootNode={name:'',path:'',type:'folder',children:{}}

    for(const raw of dirList){
      const parts=String(raw).replace(/\\/g,'/').split('/').filter(Boolean)
      let node=rootNode

      parts.forEach((part,index)=>{
        const path=parts.slice(0,index+1).join('/')

        if(!node.children[part]){
          node.children[part]={
            name:part,
            path,
            type:'folder',
            children:{}
          }
        }else{
          node.children[part].type='folder'
        }

        node=node.children[part]
      })
    }

    for(const raw of fileList){
      const parts=String(raw).replace(/\\/g,'/').split('/').filter(Boolean)
      let node=rootNode

      parts.forEach((part,index)=>{
        const path=parts.slice(0,index+1).join('/')
        const isLast=index===parts.length-1

        if(!node.children[part]){
          node.children[part]={
            name:part,
            path,
            type:isLast?'file':'folder',
            children:{}
          }
        }

        if(!isLast){
          node.children[part].type='folder'
        }

        node=node.children[part]
      })
    }

    const sortNode=(node)=>{
      const items=Object.values(node.children||{})
      items.sort((a,b)=>{
        if(a.type!==b.type) return a.type==='folder'?-1:1
        return a.name.localeCompare(b.name,'ko')
      })
      node.sortedChildren=items
      items.forEach(sortNode)
      return node
    }

    return sortNode(rootNode)
  }

  const projectTree=buildProjectTree(files,projectDirs)
  const projectFileSearchNeedle=String(projectFileSearch||'').trim().toLocaleLowerCase()
  const projectFileSearchMatches=projectFileSearchNeedle
    ? files.filter(path=>String(path||'').toLocaleLowerCase().includes(projectFileSearchNeedle))
    : files
  const projectTreeForDisplay=projectFileSearchNeedle
    ? buildProjectTree(projectFileSearchMatches,[])
    : projectTree

  useEffect(()=>{
    // v5.349: 검색 결과는 처음에는 일치 파일의 상위 폴더를 자동으로 펼칩니다.
    // 이후에는 fileTreeExpanded 상태만 사용하므로 사용자가 검색 중에도 + / - 버튼으로
    // 폴더를 자유롭게 접고 다시 펼칠 수 있습니다. 검색 결과를 강제로 열린 상태로
    // 고정하지 않습니다.
    if(!projectFileSearchNeedle) return
    const ancestors={}
    projectFileSearchMatches.forEach(path=>{
      const parts=normalizeProjectRelativePath(path).split('/').filter(Boolean)
      let current=''
      parts.slice(0,-1).forEach(part=>{
        current=current?`${current}/${part}`:part
        ancestors[current]=true
      })
    })
    setFileTreeExpanded(prev=>({...prev,...ancestors}))
  },[projectFileSearchNeedle])

  const toggleTreeFolder=(path)=>{
    setFileTreeExpanded(prev=>({...prev,[path]:!prev[path]}))
  }

  const resolveFileCreateParent=()=>{
    const selectedPath=normalizeProjectRelativePath(fileTreeSelected)
    if(!selectedPath) return ''

    const fileSet=new Set(files.map(normalizeProjectRelativePath))
    const dirSet=new Set(projectDirs.map(normalizeProjectRelativePath))

    if(dirSet.has(selectedPath)) return selectedPath
    if(fileSet.has(selectedPath)){
      return selectedPath.split('/').slice(0,-1).join('/')
    }

    // The rendered tree itself is built from canonical `/` paths. If a folder
    // was selected just before an async tree refresh, preserve that selected
    // nested path instead of silently falling back to project root.
    const findNode=(node,path)=>{
      if(!node) return null
      if(node.path===path) return node
      for(const child of node.sortedChildren||[]){
        const found=findNode(child,path)
        if(found) return found
      }
      return null
    }
    const selectedNode=findNode(projectTree,selectedPath)
    return selectedNode?.type==='folder' ? selectedPath : ''
  }

  const createProjectFolder=async()=>{
    const workspaceRoot=resolveWorkspaceRoot()
    if(!workspaceRoot) return

    const parent=resolveFileCreateParent()

    const name=window.prompt('새 폴더 이름을 입력하세요.')
    if(!name?.trim()) return

    const relativePath=[parent,name.trim()].filter(Boolean).join('/')

    try{
      await api('/files/folder',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          relative_path:relativePath
        })
      })

      await loadFiles()
      setFileTreeExpanded(prev=>({
        ...prev,
        [parent]:true,
        [relativePath]:true
      }))
      setFileTreeSelected(relativePath)
      setFileTreeSelectedPaths([normalizeProjectRelativePath(relativePath)])
    }catch(e){
      window.alert('폴더 생성 실패: '+String(e))
    }
  }

  const createProjectFile=async()=>{
    const workspaceRoot=resolveWorkspaceRoot()
    if(!workspaceRoot||fileCreateLoading||fileCreateBusyRef.current) return

    const parent=resolveFileCreateParent()

    const name=window.prompt(
      '새 파일 이름을 입력하세요.',
      'new_file.py'
    )

    if(!name?.trim()) return
    fileCreateBusyRef.current=true

    const relativePath=[parent,name.trim()]
      .filter(Boolean)
      .join('/')

    setFileCreateLoading(true)

    try{
      const result=await api('/files/create',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          relative_path:relativePath
        })
      })

      if(!result?.ok||!result?.exists||!result?.relative_path){
        throw new Error('Backend 응답은 성공했지만 실제 디스크 파일 검증에 실패했습니다.')
      }

      const canonicalPath=result.relative_path
      await loadFiles()

      setFileTreeExpanded(prev=>({
        ...prev,
        [normalizeProjectRelativePath(parent)]:true
      }))

      setFileTreeSelected(canonicalPath)
      setFileTreeSelectedPaths([normalizeProjectRelativePath(canonicalPath)])
      if(result?.mtime_ns){
        const createdKey=normalizeProjectRelativePath(canonicalPath)
        const createdMeta={
          mtime_ns:result.mtime_ns,
          size:result.size||0,
          sha256:result.sha256||''
        }
        editorFileDiskMetaRef.current={
          ...editorFileDiskMetaRef.current,
          [createdKey]:createdMeta
        }
        setEditorFileDiskMeta(prev=>({
          ...prev,
          [createdKey]:createdMeta
        }))
      }

      // Backend에서 실제 디스크 생성과 검증이 끝난 뒤에만 Editor tab을 엽니다.
      if(canonicalPath){
        try{
          await openFile(canonicalPath)
        }catch(openError){
          console.error(
            '새 파일 자동 열기 실패:',
            openError
          )
        }
      }
    }catch(e){
      window.alert('파일 생성 실패: '+String(e))
    }finally{
      setFileCreateLoading(false)
      fileCreateBusyRef.current=false
    }
  }



  const migrateOpenEditorPathAfterRename=(oldPath,newPath)=>{
    if(!oldPath||!newPath||oldPath===newPath) return

    const oldNorm=String(oldPath).replace(/\\/g,'/')
    const newNorm=String(newPath).replace(/\\/g,'/')

    const remap=(path)=>{
      const normalized=String(path||'').replace(/\\/g,'/')

      if(normalized===oldNorm){
        return newNorm
      }

      // 폴더 이름 변경 시 열린 하위 파일들의 경로도 함께 이동
      if(normalized.startsWith(oldNorm+'/')){
        return newNorm+normalized.slice(oldNorm.length)
      }

      return path
    }

    setOpenEditorFiles(prev=>{
      const mapped=prev.map(remap)

      return mapped.filter(
        (path,index,array)=>
          array.indexOf(path)===index
      )
    })

    setEditorFileContents(prev=>{
      const next={}

      for(const [path,content] of Object.entries(prev)){
        next[remap(path)]=content
      }

      return next
    })

    setEditorFileDirty(prev=>{
      const next={}

      for(const [path,dirty] of Object.entries(prev)){
        next[remap(path)]=dirty
      }

      return next
    })

    setSelected(prev=>remap(prev))
    setFileTreeSelected(prev=>remap(prev))

    setEditorTabMenu(prev=>
      prev
        ? {
            ...prev,
            path:remap(prev.path)
          }
        : prev
    )
  }


  const beginRenameTreeItem=(node)=>{
    setFileTreeSelected(node.path)
    setFileTreeRename({
      path:node.path,
      value:node.name
    })
  }

  const saveTreeRename=async()=>{
    if(!fileTreeRename?.path) return
    const workspaceRoot=resolveWorkspaceRoot()
    if(!workspaceRoot){
      window.alert('프로젝트 root를 확인할 수 없습니다. 프로젝트를 다시 선택해주세요.')
      return
    }

    const oldPath=fileTreeRename.path
    const nextName=fileTreeRename.value.trim()

    if(!nextName) return

    const currentName=
      oldPath
        .replace(/\\/g,'/')
        .split('/')
        .filter(Boolean)
        .pop()
      || ''

    // 이름이 실제로 바뀌지 않았다면 API 호출 없이 편집 종료
    if(nextName===currentName){
      setFileTreeRename(null)
      return
    }

    try{
      const result=await api('/files/rename',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          relative_path:oldPath,
          new_name:nextName
        })
      })

      const newPath=result.new_relative_path||''

      if(newPath){
        // 파일 시스템 이름 변경과 열린 코드 탭 상태를 동일하게 맞춤
        migrateOpenEditorPathAfterRename(
          oldPath,
          newPath
        )
      }

      setFileTreeSelected(newPath)
      setFileTreeSelectedPaths(newPath?[normalizeProjectRelativePath(newPath)]:[])
      setFileTreeRename(null)

      await loadFiles()

      // 현재 열려 있던 파일이라면 같은 편집 내용을 유지한 채
      // 새 경로 탭이 계속 활성 상태가 되도록 함
      if(
        newPath
        && selected===oldPath
      ){
        setSelected(newPath)
      }
    }catch(e){
      window.alert('이름 변경 실패: '+String(e))
    }
  }

  const getSelectedProjectFiles=()=>{
    const fileSet=new Set(files.map(normalizeProjectRelativePath))
    return (fileTreeSelectedPaths.length?fileTreeSelectedPaths:[fileTreeSelected])
      .map(normalizeProjectRelativePath)
      .filter(path=>path&&fileSet.has(path))
  }

  const selectProjectTreeNode=(node,event)=>{
    const path=normalizeProjectRelativePath(node.path)
    if(!path) return
    setFocusOwnerSafe('tree')

    if(node.type==='folder'){
      setFileTreeSelected(path)
      setFileTreeSelectedPaths([path])
      fileTreeSelectionAnchorRef.current=path
      toggleTreeFolder(path)
      return
    }

    const ordered=files.map(normalizeProjectRelativePath).filter(Boolean)
    if(event?.shiftKey && fileTreeSelectionAnchorRef.current){
      const anchor=fileTreeSelectionAnchorRef.current
      const a=ordered.indexOf(anchor)
      const b=ordered.indexOf(path)
      if(a>=0&&b>=0){
        const [start,end]=a<=b?[a,b]:[b,a]
        const range=ordered.slice(start,end+1)
        setFileTreeSelectedPaths(range)
        setFileTreeSelected(path)
        return
      }
    }

    if(event?.ctrlKey||event?.metaKey){
      setFileTreeSelectedPaths(prev=>{
        const current=new Set(prev.map(normalizeProjectRelativePath).filter(Boolean))
        if(current.has(path)) current.delete(path)
        else current.add(path)
        const next=[...current]
        setFileTreeSelected(next.includes(path)?path:(next[next.length-1]||''))
        return next
      })
      fileTreeSelectionAnchorRef.current=path
      return
    }

    setFileTreeSelected(path)
    setFileTreeSelectedPaths([path])
    fileTreeSelectionAnchorRef.current=path
    setWorkspaceTab('CODE')
    openFile(path)
  }

  const requestProjectFilesDelete=(paths=null)=>{
    const fileSet=new Set(files.map(normalizeProjectRelativePath))
    const candidates=(paths||getSelectedProjectFiles())
      .map(normalizeProjectRelativePath)
      .filter(path=>path&&fileSet.has(path))
    const targets=[...new Set(candidates)]
    setFileTreeContextMenu(null)
    if(!targets.length) return
    const dirtyCount=targets.filter(path=>!!editorFileDirty[path]).length
    setFileDeleteConfirm({
      paths:targets,
      deleting:false,
      error:'',
      dirtyCount
    })
  }

  const confirmProjectFilesDelete=async()=>{
    const pending=fileDeleteConfirm
    if(!pending||pending.deleting) return
    const workspaceRoot=resolveWorkspaceRoot()
    if(!workspaceRoot){
      setFileDeleteConfirm(prev=>prev?{...prev,error:'프로젝트 root를 확인할 수 없습니다. 프로젝트를 다시 선택해주세요.'}:prev)
      return
    }
    setFileDeleteConfirm(prev=>prev?{...prev,deleting:true,error:''}:prev)
    try{
      const result=await api('/files/delete',{
        method:'POST',
        body:JSON.stringify({root:workspaceRoot,relative_paths:pending.paths})
      })
      const deleted=[...(result?.deleted||[]),...(result?.missing||[])]
        .map(normalizeProjectRelativePath)
      closeEditorFiles(deleted)
      setFileTreeSelectedPaths([])
      setFileTreeSelected('')
      editorFileDiskMetaRef.current={...editorFileDiskMetaRef.current}
      for(const path of deleted) delete editorFileDiskMetaRef.current[path]
      setEditorFileDiskMeta(prev=>{
        const next={...prev}; for(const path of deleted) delete next[path]; return next
      })
      setEditorExternalState(prev=>{
        const next={...prev}; for(const path of deleted) delete next[path]; return next
      })
      setExternalFileNotifications(prev=>prev.filter(item=>!deleted.includes(item.path)))
      await loadFiles(workspaceRoot)
      setFileDeleteConfirm(null)
      if(result?.lock_recovered){
        const released=[]
        if((result?.released_sqlite_connections||[]).length) released.push('SQL Workspace SQLite 연결')
        if((result?.reset_python_sessions||[]).length) released.push('Python/Notebook 실행 세션')
        if(released.length){
          window.alert(`${released.join(' 및 ')}을 종료해 DB 파일 잠금을 해제한 뒤 삭제했습니다.`)
        }
      }
    }catch(e){
      let message=String(e)
      try{
        const payload=JSON.parse(String(e?.responseBody||''))
        const detail=payload?.detail
        if(detail&&typeof detail==='object'&&detail.message){
          message=String(detail.message)
          if(detail.original_error) message+=`\n\n${String(detail.original_error)}`
        }else if(typeof detail==='string'&&detail){
          message=detail
        }
      }catch{}
      setFileDeleteConfirm(prev=>prev?{...prev,deleting:false,error:message}:prev)
    }
  }

  const openProjectFileContextMenu=(node,event)=>{
    event.preventDefault()
    event.stopPropagation()
    if(node.type!=='file') return
    const path=normalizeProjectRelativePath(node.path)
    const current=new Set(fileTreeSelectedPaths.map(normalizeProjectRelativePath))
    let paths
    if(current.has(path)&&current.size){
      paths=[...current]
    }else{
      paths=[path]
      setFileTreeSelected(path)
      setFileTreeSelectedPaths(paths)
      fileTreeSelectionAnchorRef.current=path
    }
    setFocusOwnerSafe('tree')
    setFileTreeContextMenu({x:event.clientX,y:event.clientY,paths})
  }

  useEffect(()=>{
    const onKeyDown=(event)=>{
      if(event.key==='Delete' && focusOwnerRef.current==='tree'){
        const targets=getSelectedProjectFiles()
        if(targets.length){
          event.preventDefault()
          event.stopPropagation()
          requestProjectFilesDelete(targets)
        }
      }
      if(event.key==='Escape'){
        setFileTreeContextMenu(null)
      }
    }
    const closeMenu=()=>setFileTreeContextMenu(null)
    window.addEventListener('keydown',onKeyDown,true)
    window.addEventListener('mousedown',closeMenu)
    return()=>{
      window.removeEventListener('keydown',onKeyDown,true)
      window.removeEventListener('mousedown',closeMenu)
    }
  },[files,fileTreeSelectedPaths,fileTreeSelected,editorFileDirty,root])

  const renderProjectTreeNode=(node,depth=0)=>{
    const isFolder=node.type==='folder'
    const expanded=!!fileTreeExpanded[node.path]
    const selectedNode=fileTreeSelectedPaths.map(normalizeProjectRelativePath).includes(normalizeProjectRelativePath(node.path))
      || (!fileTreeSelectedPaths.length && normalizeProjectRelativePath(fileTreeSelected)===normalizeProjectRelativePath(node.path))

    return <div key={node.path} className="tree-node">
      <div
        className={selectedNode?'tree-row selected':'tree-row'}
        style={{paddingLeft:`${depth*14+6}px`}}
        onClick={(e)=>{
          e.stopPropagation()
          selectProjectTreeNode(node,e)
        }}
        onDoubleClick={(e)=>{
          e.stopPropagation()
          if(isFolder){
            toggleTreeFolder(node.path)
          }else{
            setFileTreeSelected(node.path)
            setFileTreeSelectedPaths([normalizeProjectRelativePath(node.path)])
            fileTreeSelectionAnchorRef.current=normalizeProjectRelativePath(node.path)
            setWorkspaceTab('CODE')
            openFile(node.path,fileTreeRootRef.current||resolveWorkspaceRoot())
          }
        }}
        onContextMenu={(e)=>openProjectFileContextMenu(node,e)}
      >
        <span
          className={isFolder?'tree-toggle visible':'tree-toggle'}
          onClick={(e)=>{
            if(!isFolder) return
            e.stopPropagation()
            toggleTreeFolder(node.path)
          }}
        >
          {isFolder?(expanded?'−':'+'):''}
        </span>

        <span className={isFolder?'tree-icon folder':'tree-icon file'}>
          {isFolder?(expanded?'📂':'📁'):'📄'}
        </span>

        {fileTreeRename?.path===node.path ? (
          <input
            className="tree-rename-input"
            value={fileTreeRename.value}
            autoFocus
            onClick={(e)=>e.stopPropagation()}
            onDoubleClick={(e)=>e.stopPropagation()}
            onChange={(e)=>setFileTreeRename({
              ...fileTreeRename,
              value:e.target.value
            })}
            onBlur={()=>{
              setFileTreeRename(null)
            }}
            onKeyDown={(e)=>{
              if(e.key==='Enter'){
                e.preventDefault()
                e.stopPropagation()
                saveTreeRename()
                return
              }

              if(e.key==='Escape'){
                e.preventDefault()
                e.stopPropagation()
                setFileTreeRename(null)
              }
            }}
          />
        ) : (
          <span className="tree-name">{node.name}</span>
        )}

        <button
          type="button"
          className="tree-rename-button tree-rename-pencil"
          title="이름 변경"
          aria-label={`${node.name} 이름 변경`}
          onMouseDown={(e)=>{
            e.preventDefault()
            e.stopPropagation()
          }}
          onClick={(e)=>{
            e.preventDefault()
            e.stopPropagation()
            beginRenameTreeItem(node)
          }}
          onDoubleClick={(e)=>{
            e.stopPropagation()
          }}
        >
          ✎
        </button>
      </div>

      {isFolder && expanded && node.sortedChildren?.map((child)=>
        renderProjectTreeNode(child,depth+1)
      )}
    </div>
  }


  const toggleProjectFavorite=async(project,e=null)=>{
    if(e) e.stopPropagation()
    try{
      const result=await api(`/projects/${project.id}/favorite`,{
        method:'POST',
        body:JSON.stringify({
          is_favorite:!project.is_favorite
        })
      })

      if(result.ok){
        setProjectList(prev=>prev.map(p=>
          p.id===project.id
            ? {...p,is_favorite:result.is_favorite}
            : p
        ))
      }
    }catch(err){
      console.error('즐겨찾기 변경 실패',err)
    }
  }


  const renderProjectLibraryScreen=()=> <div className="nav-page-shell">
    <div className="nav-page-head">
      <div>
        <div className="eyebrow">PROJECT LIBRARY</div>
        <h2>프로젝트 관리</h2>
        <p>저장된 프로젝트를 조회하고 최근 프로젝트와 즐겨찾기를 관리합니다.</p>
        <div className="project-library-db-status">
          <div>{projectListLoading?'DB 프로젝트 목록 불러오는 중...':projectListStatus}</div>
          <div>연결 경로: Frontend → FastAPI → PostgreSQL</div>
          {projectListLogPath&&<code>{projectListLogPath}</code>}
        </div>
      </div>
      <div className="nav-page-actions">
        <button type="button" onClick={refreshProjectList}>DB 새로고침</button>
        <button type="button" onClick={openProjectList}>프로젝트 불러오기</button>
        <button type="button" className="primary" onClick={startNewProject}>＋ 새 Agent</button>
      </div>
    </div>

    <div className="nav-page-grid">
      <section className="nav-page-card">
        <SectionTitle title={`전체 프로젝트 (${projectList.length})`}/>
        <div className="nav-project-list">
          {projectList.length===0&&<div className="empty-mini">저장된 프로젝트가 없습니다.</div>}
          {projectList.map(p=><button
            key={p.id}
            className={selectedProjectId===p.id?'nav-project-row active':'nav-project-row'}
            onClick={()=>loadProject(p.id)}
          >
            <span className="project-icon">▣</span>
            <div>
              <strong>{p.name}</strong>
              <small>{p.project_root}</small>
            </div>
            <span className={p.is_favorite?'nav-favorite active':'nav-favorite'}>★</span>
          </button>)}
        </div>
      </section>

      <section className="nav-page-card">
        <SectionTitle title="최근 프로젝트"/>
        <div className="nav-project-list">
          {projectList
            .filter(p=>p.last_opened_at)
            .sort((a,b)=>new Date(b.last_opened_at)-new Date(a.last_opened_at))
            .slice(0,10)
            .map(p=><button
              key={p.id}
              className="nav-project-row"
              onClick={()=>loadProject(p.id)}
            >
              <span className="project-icon">◷</span>
              <div>
                <strong>{p.name}</strong>
                <small>{new Date(p.last_opened_at).toLocaleString()}</small>
              </div>
            </button>)}
        </div>
      </section>

      <section className="nav-page-card">
        <SectionTitle title="즐겨찾기"/>
        <div className="nav-project-list">
          {projectList.filter(p=>p.is_favorite).length===0
            ? <div className="empty-mini">즐겨찾기 프로젝트가 없습니다.</div>
            : projectList.filter(p=>p.is_favorite).map(p=><button
                key={p.id}
                className="nav-project-row"
                onClick={()=>loadProject(p.id)}
              >
                <span className="project-icon">★</span>
                <div>
                  <strong>{p.name}</strong>
                  <small>{p.project_root}</small>
                </div>
              </button>)}
        </div>
      </section>
    </div>
  </div>

  const renderMcpScreen=()=> <div className="nav-page-shell">
    <div className="nav-page-head">
      <div>
        <div className="eyebrow">MCP / TOOL</div>
        <h2>MCP 도구 관리</h2>
        <p>MCP 서버와 등록된 도구를 확인하고 동기화합니다.</p>
      </div>
      <div className="nav-page-actions">
        <button className="primary" onClick={openMcpAddDialog}>＋ MCP 연결 추가</button>
        <button onClick={refreshMcp}>새로고침</button>
      </div>
    </div>

    <div className="nav-page-grid two">
      <section className="nav-page-card">
        <SectionTitle title={`MCP 서버 (${mcpServers.length})`}/>
        <div className="nav-project-list">
          {mcpServers.length===0&&<div className="empty-mini">등록된 MCP 서버가 없습니다.</div>}
          {mcpServers.map((s,i)=><div className="nav-project-row static mcp-server-row" key={s.id||i}>
            <span className="project-icon">◉</span>
            <div>
              <strong>{s.name||'MCP Server'}</strong>
              <small>{s.endpoint||''}</small>
              <small>{s.status?`상태: ${s.status}`:'상태 확인 필요'}</small>
            </div>
            <button type="button" className="mcp-sync-button" onClick={()=>syncMcpServer(s.id)}>Tool 동기화</button>
          </div>)}
        </div>
      </section>

      <section className="nav-page-card">
        <SectionTitle title={`MCP 도구 (${mcpTools.length})`}/>
        <div className="nav-project-list">
          {mcpTools.length===0&&<div className="empty-mini">등록된 MCP 도구가 없습니다.</div>}
          {mcpTools.map((t,i)=><div className="nav-project-row static" key={t.id||i}>
            <span className="project-icon">⌘</span>
            <div><strong>{t.name||String(t)}</strong><small>{t.category||'MCP Tool'}</small></div>
          </div>)}
        </div>
      </section>
    </div>
  </div>

  const renderToolsScreen=()=> <div className="nav-page-shell">
    <div className="nav-page-head">
      <div>
        <div className="eyebrow">TOOLS</div>
        <h2>도구 / 실행 관리</h2>
        <p>프로젝트 실행, 터미널, 코드 편집 및 작업 상태를 관리합니다.</p>
      </div>
      <div className="nav-page-actions">
        <button className="primary" onClick={goWorkspace}>작업공간 열기</button>
      </div>
    </div>
    <div className="nav-page-grid two">
      <section className="nav-page-card">
        <SectionTitle title="빠른 실행"/>
        <button className="nav-big-action" onClick={goWorkspace}>▣ 작업공간 열기</button>
        <button className="nav-big-action" onClick={()=>setWorkspaceTab('RUN')}>▶ 실행 결과</button>
      </section>
      <section className="nav-page-card">
        <SectionTitle title="현재 프로젝트"/>
        <h3>{currentProjectName}</h3>
        <code>{currentProjectPath||'프로젝트가 선택되지 않았습니다.'}</code>
      </section>
    </div>
  </div>


  const changeProjectFilter=async(filter)=>{
    setProjectFilter(filter)
    await refreshProjectList()
  }

  const classifyDevelopmentStatus=(workflowState={})=>{
    const status=String(workflowState?.status||'').toUpperCase()
    const testReturncode=(
      workflowState?.test_result?.returncode
      ??workflowState?.package_result?.test_returncode
      ??workflowState?.test_returncode
      ??null
    )
    const artifactOk=workflowState?.build_artifact_validation?.ok===true
    const launcherOk=(
      workflowState?.launcher_generation_result?.ok===true
      ||workflowState?.package_result?.launcher_generation?.ok===true
    )
    const appliedFiles=Array.isArray(workflowState?.patch_result)
      ? workflowState.patch_result.length
      : 0

    const errorText=String(
      workflowState?.error
      ||workflowState?.last_error
      ||workflowState?.message
      ||''
    ).trim()

    // substring 포함 여부가 아니라 정확한 최종 상태만 성공으로 인정합니다.
    // CODE_PLAN_INCOMPLETE 안의 "COMPLETE" 때문에 성공으로 오판하던 버그를 차단합니다.
    const successfulFinalStatuses=new Set([
      'COMPLETED',
      'SUCCESS'
    ])

    const failedStatuses=new Set([
      'FAILED',
      'ERROR',
      'INCOMPLETE',
      'CODE_PLAN_INCOMPLETE',
      'REPAIR_PLAN_INCOMPLETE',
      'TEST_REPAIR_PLAN_FAILED',
      'TEST_REPAIR_PLAN_INCOMPLETE',
      'BUILD_FAILED',
      'TEST_FAILED',
      'PACKAGE_FAILED',
      'LAUNCHER_GENERATION_FAILED',
      'FILE_APPLY_FAILED',
      'FAILED_NO_ARTIFACTS',
      'REQUIREMENT_COVERAGE_FAILED',
      'BUILD_ARTIFACT_STALLED',
      'DEBUG_STOPPED',
      'ABORTED'
    ])

    const waitingStatuses=new Set([
      'DEBUG_PATCH_READY',
      'WAITING_APPROVAL',
      'APPROVAL_REQUIRED',
      'CHECKPOINT',
      'PAUSED',
      'WAITING',
      'REVIEW_REQUIRED'
    ])

    if(successfulFinalStatuses.has(status)){
      const missingEvidence=[]

      if(testReturncode!==0){
        missingEvidence.push(
          testReturncode===null
            ? '테스트 실행 결과가 없습니다.'
            : `테스트 ReturnCode=${testReturncode}`
        )
      }

      if(!artifactOk){
        missingEvidence.push('최종 산출물 검증이 완료되지 않았습니다.')
      }

      if(!launcherOk){
        missingEvidence.push('SYSTEM_ADMIN.cmd 실행 진입점 검증이 완료되지 않았습니다.')
      }

      if(appliedFiles<=0){
        missingEvidence.push('실제 생성/수정된 파일이 확인되지 않았습니다.')
      }

      if(missingEvidence.length===0){
        return {
          kind:'success',
          title:'Agent 개발이 완료되었습니다.',
          detail:
            `파일 ${appliedFiles}개 생성/수정, `
            +`테스트 통과(ReturnCode=0), `
            +'SYSTEM_ADMIN.cmd 생성 및 최종 산출물 검증까지 완료되었습니다.',
          status
        }
      }

      return {
        kind:'failure',
        title:'Agent 개발 완료 조건을 충족하지 못했습니다.',
        detail:missingEvidence.join(' '),
        status:'INCOMPLETE'
      }
    }

    if(
      failedStatuses.has(status)
      ||testReturncode>0
    ){
      const repairValidation=workflowState?.repair_plan_validation||{}
      const repairTargets=Array.isArray(repairValidation?.targets)?repairValidation.targets:[]
      const missingRepairTargets=Array.isArray(repairValidation?.missing_repair_targets)?repairValidation.missing_repair_targets:[]
      const repairDetail=(status==='TEST_REPAIR_PLAN_INCOMPLETE'||status==='TEST_REPAIR_PLAN_FAILED')
        ? [
            '테스트 실패 자동 복구가 적용 가능한 수정안을 만들지 못했습니다.',
            repairTargets.length?`분석 대상: ${repairTargets.join(', ')}`:'',
            missingRepairTargets.length?`아직 수정안을 만들지 못한 파일: ${missingRepairTargets.join(', ')}`:'',
            'v5.360은 Focused Repair와 대상 파일 단독 Recovery를 자동으로 시도한 뒤에도 적용 가능한 Patch가 없을 때만 이 상태로 종료합니다.'
          ].filter(Boolean).join(' ')
        : ''

      return {
        kind:'failure',
        title:'Agent 개발에 실패했습니다.',
        detail:
          repairDetail
          ||errorText
          ||(
            testReturncode>0
              ? `테스트가 실패했습니다. ReturnCode=${testReturncode}`
              : `Workflow 상태: ${status||'FAILED'}`
          ),
        status
      }
    }

    if(waitingStatuses.has(status)){
      return {
        kind:status==='DEBUG_PATCH_READY'?'action':'waiting',
        title:
          status==='DEBUG_PATCH_READY'
            ? '디버그 패치가 준비되었습니다.'
            : '사용자 조치를 기다리고 있습니다.',
        detail:
          status==='DEBUG_PATCH_READY'
            ? '개발이 완료된 상태가 아닙니다. 생성된 디버그 패치를 검토하거나 Workflow를 재개해야 합니다.'
            : 'Workflow가 완료되지 않았습니다. 승인·검토·재개 등 다음 조치가 필요합니다.',
        status
      }
    }

    return {
      kind:'info',
      title:'Agent Factory 실행이 종료되었습니다.',
      detail:`완료 여부를 확정할 수 없는 상태입니다: ${status||'UNKNOWN'}`,
      status
    }
  }



  const renderDevelopmentProgress=()=>(
    developmentProgress.active
      ? <div className="development-progress-card">
          <div className="development-progress-head">
            <div>
              <span className="development-progress-pulse">●</span>
              <div>
                <strong>{developmentProgress.stage}</strong>
                <small>{developmentProgress.detail}</small>
              </div>
            </div>

            <div className="development-progress-stats">
              <b>{developmentProgress.percent}%</b>
              <span>{developmentProgress.elapsedSeconds}s</span>
            </div>
          </div>

          <div
            className="development-progress-track"
            role="progressbar"
            aria-label="Agent 개발 진행률"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow={developmentProgress.percent}
          >
            <div
              className="development-progress-fill"
              style={{width:`${developmentProgress.percent}%`}}
            />
          </div>

          <div className="development-progress-stages">
            {[
              ['준비',4],
              ['Factory',10],
              ['코드/검증',30],
              ['테스트/복구',58],
              ['패키징',78],
              ['완료',100]
            ].map(([label,threshold])=><span
              key={label}
              className={
                developmentProgress.percent>=threshold
                  ? 'done'
                  : ''
              }
            >
              <i></i>{label}
            </span>)}
          </div>

          {Array.isArray(developmentProgress.events)&&developmentProgress.events.length>0&&<div className="development-live-log">
            <div className="development-live-log-head">
              <strong>생성 진행 로그</strong>
              <small>LLM 추가 호출 없음 · Node 완료 이벤트만 표시</small>
            </div>
            <div className="development-live-log-list">
              {developmentProgress.events.slice(-8).map((event,index)=><div className="development-live-log-row" key={`${event?.at||''}-${event?.node||''}-${index}`}>
                <span>{String(event?.at||'').slice(11,19)||'--:--:--'}</span>
                <b>{event?.node||event?.status||'workflow'}</b>
                <em>{event?.message||''}</em>
              </div>)}
            </div>
          </div>}
        </div>
      : null
  )


  const copyDiagnosticPath=async(path)=>{
    if(!path) return
    try{
      await navigator.clipboard.writeText(path)
    }catch(e){
      window.prompt('전체 경로를 복사하세요.',path)
    }
  }

  const formatDiagnosticTime=(value)=>{
    if(!value) return '-'
    try{
      const date=new Date(value)
      if(Number.isNaN(date.getTime())) return String(value)
      return date.toLocaleString('ko-KR',{hour12:false})
    }catch(_){
      return String(value)
    }
  }

  const renderFailureDiagnostics=()=>{
    const d=workflow?.failure_diagnostics||workflow?.state?.failure_diagnostics
    if(!d) return null
    if(developmentFinalStatus?.kind==='success') return null

    const diagnosticsProjectRoot=(
      d.project_root
      ||String(d.failure_report||'').replace(
        /[\\/]+reports[\\/]+failure_report\.md$/i,
        ''
      )
    )

    return <div className="failure-diagnostics-card">
      <div className="failure-diagnostics-head">
        <div>
          <span>!</span>
          <div>
            <strong>
              {(d.diagnostics_fresh===false||d.status==='RUNNING'||d.status==='DIAGNOSTICS_STALE')
                ? '현재 실행의 진단 자료를 확인하고 있습니다.'
                : '실패 진단 자료가 생성되었습니다.'}
            </strong>
            <small>
              {(d.diagnostics_fresh===false||d.status==='RUNNING'||d.status==='DIAGNOSTICS_STALE')
                ? '이전 실행의 실패 파일을 현재 실행 결과로 사용하지 않습니다.'
                : '실패 원인과 재시도 자료를 프로젝트 폴더에 저장했습니다.'}
            </small>
          </div>
        </div>
        <b>{d.status||'FAILED'}</b>
      </div>

      <div className="failure-diagnostics-run-info">
        <div><span>실행 ID</span><strong title={d.run_id||''}>{d.run_id||'-'}</strong></div>
        <div><span>실행 시작</span><strong>{formatDiagnosticTime(d.run_started_at)}</strong></div>
        <div><span>진단 생성</span><strong>{formatDiagnosticTime(d.diagnostic_generated_at)}</strong></div>
        <div>
          <span>현재 실행 자료</span>
          <strong className={d.diagnostics_fresh===false?'no':'ok'}>
            {d.diagnostics_fresh===false?'아님 / 대기':'맞음'}
          </strong>
        </div>
      </div>

      <div className="failure-diagnostics-summary">
        <div><span>실패 단계</span><strong>{d.failure_stage||'-'}</strong></div>
        <div><span>실제 Agent 파일</span><strong>{d.actual_file_count||0}개</strong></div>
        <div><span>계획 파일</span><strong>{d.planned_file_count||0}개</strong></div>
      </div>

      {(()=>{
        const cp=d.code_plan_validation||{}
        const missing=(
          cp.missing_required_paths
          ||d.missing_required_paths
          ||[]
        )
        if(
          !Object.keys(cp).length
          &&missing.length===0
        ) return null

        return <div className="failure-code-plan">
          <div className="failure-code-plan-head">
            <strong>Code Plan 완전성</strong>
            <b className={missing.length===0?'ok':'no'}>
              {missing.length===0
                ? '필수 파일 포함 완료'
                : `필수 파일 ${missing.length}개 누락`}
            </b>
          </div>
          <div className="failure-code-plan-stats">
            <span>Required <b>{cp.required_count??'-'}개</b></span>
            <span>기존 존재 <b>{cp.existing_count??'-'}개</b></span>
            <span>Plan 변경 <b>{cp.planned_change_count??'-'}개</b></span>
            <span>자동 보강 <b>{cp.supplement_rounds??0}회</b></span>
          </div>
          {missing.length>0
            ? <div className="failure-code-plan-missing">
                {missing.map(path=><code key={path}>{path}</code>)}
              </div>
            : null}
        </div>
      })()}

      <div className="failure-execution-state">
        <div>
          <span>파일 적용</span>
          <strong className={d.file_apply?.executed?'ok':'no'}>
            {d.file_apply?.executed
              ? `실행됨 · ${d.file_apply?.count||0}개`
              : '실행되지 않음'}
          </strong>
        </div>
        <div>
          <span>테스트</span>
          <strong className={d.test?.executed?'ok':'no'}>
            {d.test?.executed
              ? `실행됨 · ReturnCode ${d.test?.returncode??'-'}`
              : '실행되지 않음'}
          </strong>
        </div>
        <div>
          <span>디버그/복구</span>
          <strong className={d.debug?.executed?'ok':'no'}>
            {d.debug?.executed
              ? `실행됨 · ${d.debug?.count||0}회`
              : '실행되지 않음'}
          </strong>
        </div>
      </div>

      <div className="failure-diagnostics-reason">
        <span>실패 원인</span>
        <p>{d.failure_reason||'원인 정보가 없습니다.'}</p>
      </div>

      {(()=>{
        const fa=d.file_apply_validation||{}
        const failure=fa.failure||{}
        const recoveries=fa.focused_recoveries||[]
        if(!Object.keys(fa).length) return null
        if(!failure.target&&!recoveries.length&&fa.ok!==false) return null
        return <div className="failure-file-apply-details">
          <div className="failure-file-apply-details-head">
            <strong>Patch 적용 상세</strong>
            <small>문자열 일치 실패와 자동 복구 시도를 구분해서 표시합니다.</small>
          </div>
          {failure.target?<div className="failure-file-apply-target">
            <span>실패 대상</span>
            <code>{failure.target}</code>
            <small>Change {Number(failure.change_index??-1)+1} · Replacement {Number(failure.replacement_index??-1)+1}</small>
          </div>:null}
          {recoveries.length>0?<div className="failure-file-apply-recoveries">
            {recoveries.map((item,index)=><div key={`${item.target||'recovery'}-${index}`}>
              <b>자동 복구 {index+1}</b>
              <code>{item.target||'-'}</code>
              <span>{item.strategy||'focused recovery'}</span>
            </div>)}
          </div>:null}
        </div>
      })()}

      {(()=>{
        const details=d.build_artifact_validation?.placeholder_details||[]
        if(!details.length) return null
        return <div className="failure-placeholder-details">
          <div className="failure-placeholder-details-head">
            <strong>Placeholder 상세 위치</strong>
            <small>실제로 미구현으로 판정된 줄만 표시합니다.</small>
          </div>
          {details.map((item,index)=><div className="failure-placeholder-file" key={`${item.path||'file'}-${index}`}>
            <code>{item.path||'-'}</code>
            {(item.findings||[]).map((finding,i)=><div className="failure-placeholder-finding" key={`${finding.line||i}-${i}`}>
              <b>Line {finding.line??'-'}</b>
              <span>{finding.reason||'placeholder'}</span>
              <code>{finding.snippet||''}</code>
            </div>)}
          </div>)}
        </div>
      })()}

      {diagnosticsProjectRoot&&
        <div className="failure-diagnostics-root">
          <div className="failure-diagnostics-root-head">
            <strong>기준 프로젝트 폴더</strong>
            <button
              type="button"
              className="failure-file-copy-button"
              onClick={()=>copyDiagnosticPath(diagnosticsProjectRoot)}
            >
              경로 복사
            </button>
          </div>
          <code title={diagnosticsProjectRoot}>{diagnosticsProjectRoot}</code>
        </div>
      }

      <div className="failure-diagnostics-files">
        <strong>진단 / 로그 파일</strong>
        <small>경로를 생략하지 않고 전체 표시합니다. 필요한 경로는 ‘경로 복사’ 버튼으로 복사할 수 있습니다.</small>
        {[
          ['실패 리포트','failure_report',d.failure_report],
          ['Workflow State','workflow_state',d.workflow_state],
          ['요구사항 Snapshot','requirements_snapshot',d.requirements_snapshot],
          ['생성 산출물','generated_artifacts',d.generated_artifacts],
          ['Debug Patch','debug_patch',d.debug_patch],
          ['복구 계획','recovery_plan',d.recovery_plan],
          ['Agent Factory Log','agent_factory_log',''],
          ['Workflow Log','workflow_execution_log',''],
          ['Test Log','test_log',''],
          ['Debug Log','debug_log','']
        ].map(([label,key,fallback])=>{
          const info=d.files?.[key]
          const path=info?.path||fallback
          if(!path) return null

          return <div key={label} className="failure-file-row">
            <div className="failure-file-row-head">
              <span className="failure-file-label">{label}</span>
              <b className={
                info?.exists===true
                  ? 'exists'
                  : info?.exists===false
                    ? 'missing'
                    : 'unknown'
              }>
                {info?.exists===true
                  ? '✓ 있음'
                  : info?.exists===false
                    ? '× 없음'
                    : '? 확인 불가'}
              </b>
              <button
                type="button"
                className="failure-file-copy-button"
                onClick={()=>copyDiagnosticPath(path)}
                title="전체 경로 복사"
              >
                경로 복사
              </button>
            </div>
            <code className="failure-file-path" title={path}>{path}</code>
            <small className="failure-file-modified">
              마지막 업데이트: {formatDiagnosticTime(info?.modified_at)}
              {info?.size?` · ${Number(info.size).toLocaleString()} bytes`:''}
            </small>
          </div>
        })}
      </div>
    </div>
  }


  const renderDevelopmentFinalStatus=()=>{
    if(!developmentFinalStatus) return null

    const item=developmentFinalStatus

    return <div className={`development-final-status ${item.kind}`}>
      <div className="development-final-status-icon">
        {item.kind==='success'
          ? '✓'
          : item.kind==='failure'
            ? '!'
            : item.kind==='action'
              ? '↻'
              : item.kind==='waiting'
                ? '…'
                : 'i'}
      </div>

      <div className="development-final-status-body">
        <div className="development-final-status-head">
          <strong>{item.title}</strong>
          <span>{item.status||'UNKNOWN'}</span>
        </div>
        <p>{item.detail}</p>

        {(item.kind==='action'||item.kind==='waiting')&&
          <small>
            이 상태에서는 개발이 완료된 것으로 판단하지 않습니다.
          </small>
        }
      </div>

      <button
        type="button"
        className="development-final-status-close"
        onClick={()=>setDevelopmentFinalStatus(null)}
        title="상태 메시지 닫기"
      >
        ×
      </button>
    </div>
  }


  const refreshLlmUsage=async(
    projectRootOverride='',
    scopeOverride='',
    dateOverride='',
    monthOverride=''
  )=>{
    const target=(
      projectRootOverride
      || root
      || newAgentProjectRoot
      || ''
    ).trim()
    const scope=scopeOverride||llmUsageScope||'today'
    const selectedDate=dateOverride||llmUsageDate||localIsoDate()
    const selectedMonth=monthOverride||llmUsageMonth||localIsoMonth()
    const query=new URLSearchParams({
      project_root:target,
      scope,
      date:selectedDate,
      month:selectedMonth,
    })

    try{
      const result=await api(`/usage/summary?${query.toString()}`)
      setLlmUsageSummary(result)
      return result
    }catch(e){
      console.error('LLM 사용량 조회 실패',e)
      return null
    }
  }


  const refreshLlmCatalog=async()=>{
    setLlmCatalogLoading(true)
    setLlmCatalogError('')
    try{
      const [catalogResult,historyResult]=await Promise.all([
        api('/llm/catalog'),
        api('/llm/history?days=10&limit=500'),
      ])
      setLlmCatalog(catalogResult)
      setLlmHistory(historyResult)
      return {catalog:catalogResult,history:historyResult}
    }catch(e){
      console.error('LLM 요청/응답 기록 조회 실패',e)
      setLlmCatalogError(String(e?.message||e))
      return null
    }finally{
      setLlmCatalogLoading(false)
    }
  }

  const formatTokenCount=(value)=>
    Number(value||0).toLocaleString('ko-KR')

  const formatUsd=(value)=>{
    const amount=Number(value||0)
    return `$${amount.toFixed(amount<0.01?6:4)}`
  }

  const renderLlmUsagePanel=(reportMode=false)=>{
    const projectUsage=llmUsageSummary?.project||{}
    const studioUsage=llmUsageSummary?.studio||llmUsageSummary?.daily||{}
    const studioLabel=llmUsageSummary?.period_label||'AgentStudio 오늘 전체'

    return <div className={
      reportMode
        ? 'llm-usage-dashboard report-usage'
        : 'llm-usage-dashboard'
    }>
      <div className="llm-usage-title">
        <div>
          <small>{reportMode?'LLM COST ANALYSIS':'PAID LLM USAGE'}</small>
          <strong>유료 토큰 / 비용</strong>
        </div>
        <button type="button" onClick={()=>refreshLlmUsage()}>
          ↻ 새로고침
        </button>
      </div>

      <div className="llm-usage-filter">
        <label>
          <span>AgentStudio 조회</span>
          <select
            value={llmUsageScope}
            onChange={e=>setLlmUsageScope(e.target.value)}
          >
            <option value="today">오늘 전체</option>
            <option value="all">전체 누적</option>
            <option value="month">월별 선택</option>
            <option value="day">일별 선택</option>
          </select>
        </label>
        {llmUsageScope==='month'&&<label>
          <span>월</span>
          <input
            type="month"
            value={llmUsageMonth}
            onChange={e=>setLlmUsageMonth(e.target.value)}
          />
        </label>}
        {llmUsageScope==='day'&&<label>
          <span>날짜</span>
          <input
            type="date"
            value={llmUsageDate}
            onChange={e=>setLlmUsageDate(e.target.value)}
          />
        </label>}
        <small>{studioLabel}</small>
      </div>

      <div className="llm-usage-groups">
        <div className="llm-usage-group">
          <b>현재 Agent / 프로젝트 (오늘)</b>
          <div><span>Input</span><strong>{formatTokenCount(projectUsage.input_tokens)}</strong></div>
          <div><span>Cached Input</span><strong>{formatTokenCount(projectUsage.cached_input_tokens)}</strong></div>
          <div><span>Output</span><strong>{formatTokenCount(projectUsage.output_tokens)}</strong></div>
          <div><span>Total</span><strong>{formatTokenCount(projectUsage.total_tokens)}</strong></div>
          <div className="cost"><span>총 추정 비용</span><strong>{formatUsd(projectUsage.cost_usd)}</strong></div>
        </div>

        <div className="llm-usage-group daily">
          <b>{studioLabel}</b>
          <div><span>Input</span><strong>{formatTokenCount(studioUsage.input_tokens)}</strong></div>
          <div><span>Cached Input</span><strong>{formatTokenCount(studioUsage.cached_input_tokens)}</strong></div>
          <div><span>Output</span><strong>{formatTokenCount(studioUsage.output_tokens)}</strong></div>
          <div><span>Total</span><strong>{formatTokenCount(studioUsage.total_tokens)}</strong></div>
          <div className="cost"><span>선택 기간 총 추정 비용</span><strong>{formatUsd(studioUsage.cost_usd)}</strong></div>
        </div>
      </div>

      <small className="llm-usage-note">
        {llmUsageSummary?.pricing_note
          || 'API token usage를 기준으로 추정 비용을 계산합니다.'}
      </small>
    </div>
  }


  useEffect(()=>{
    if(
      screen==='WORKSPACE'
      && (
        workspaceTab==='RUN'
        || workspaceTab==='REPORT'
        || workspaceTab==='ARCHITECTURE'
      )
    ){
      refreshLlmUsage()
    }
    if(screen==='WORKSPACE'&&workspaceTab==='LLM'){
      refreshLlmCatalog()
    }
  },[screen,workspaceTab,root,llmUsageScope,llmUsageDate,llmUsageMonth])


  const getWorkflowReportState=()=>{
    const state=workflow?.state||workflow||{}
    const packageResult=state?.package_result||{}
    const testResult=state?.test_result||{}
    const adaptive=selectedProjectId
      ? (loadedProjectAnalysis?.adaptive_report
        ||(loadedProjectAnalysis?.project_type?loadedProjectAnalysis:null)
        ||{})
      : {}
    const adaptiveArchitecture=adaptive?.architecture||{}
    const targetWorkflow=state?.target_agent_workflow
      || targetWorkflowPreview?.target_agent_workflow
      || adaptive?.workflow
      || {}
    const requirementSpec=state?.requirement_spec
      || targetWorkflowPreview?.requirement_spec
      || adaptive?.requirement_spec
      || {}
    const capabilityPlan=state?.capability_plan
      || targetWorkflowPreview?.capability_plan
      || adaptive?.capability_plan
      || {}
    const toolMcpPlan=state?.tool_mcp_plan
      || targetWorkflowPreview?.tool_mcp_plan
      || adaptive?.tool_mcp_plan
      || {}
    const architecture=state?.agent_architecture
      || targetWorkflowPreview?.agent_architecture
      || adaptiveArchitecture
      || {}
    const databasePlan=state?.database_plan
      || targetWorkflowPreview?.database_plan
      || {}
    const asBuiltArchitecture=state?.as_built_architecture
      || packageResult?.as_built_architecture
      || {}
    const architectureConformance=state?.architecture_conformance
      || packageResult?.architecture_conformance
      || {}
    const executionBaseline=adaptive?.execution_baseline||{}
    const runtimeStatus=state?.status
      ||executionBaseline?.status
      ||(adaptive?.project_type?'PROJECT_LOADED':'NOT_STARTED')

    return {
      state,
      status:runtimeStatus,
      packageResult,
      testResult,
      targetWorkflow,
      requirementSpec,
      capabilityPlan,
      toolMcpPlan,
      architecture,
      asBuiltArchitecture,
      architectureConformance,
      databasePlan,
      projectProfile:adaptive,
      analysisReport:adaptive?.analysis_report||{},
      settingsPlan:state?.settings_plan||packageResult?.settings_plan||{},
      settingsValidation:state?.settings_validation_result||packageResult?.settings_validation||{},
      settingsGeneration:state?.settings_generation_result||{},
      createdFiles:packageResult?.created_files||[],
      modifiedFiles:packageResult?.modified_files||[],
      debugHistory:state?.debug_history||[],
      debugIteration:Number(state?.debug_iteration||0),
      testCommand:packageResult?.test_command||state?.test_command||executionBaseline?.test_command||'',
      testReturncode:
        packageResult?.test_returncode
        ?? testResult?.returncode
        ?? executionBaseline?.test_returncode
        ?? null
    }
  }

  const refreshDbErd=async()=>{
    if(dbErdBusy) return
    setDbErdBusy(true)
    setDbErdError('')
    try{
      const r=getWorkflowReportState()
      const result=await api('/db-erd/analyze',{
        method:'POST',
        body:JSON.stringify({
          project_root:resolveWorkspaceRoot(),
          database_plan:r.databasePlan||{},
          project_profile:r.projectProfile||{},
          workflow_request:workflowReq||r.requirementSpec?.goal||'',
          deck_type:'AGENT'
        })
      })
      setDbErdReport(result||null)
    }catch(error){
      setDbErdError(error instanceof Error?error.message:String(error||'DB ERD 분석 실패'))
    }finally{
      setDbErdBusy(false)
    }
  }

  useEffect(()=>{
    if(screen==='WORKSPACE'&&workspaceTab==='DB_ERD'){
      refreshDbErd()
    }
  },[screen,workspaceTab,root])

  const exportWorkspacePowerPoint=async(scope='ALL',deckType='AGENT')=>{
    const exportScope=String(scope||'ALL').toUpperCase()
    const exportDeckType=String(deckType||'AGENT').toUpperCase()
    const busyKey=`${exportDeckType}:${exportScope}`
    if(pptExportBusy) return
    setPptExportError('')
    setPptExportBusy(busyKey)

    try{
      const r=getWorkflowReportState()
      const reportSnapshot={
        status:r.status,
        testResult:r.testResult,
        targetWorkflow:r.targetWorkflow,
        requirementSpec:r.requirementSpec,
        capabilityPlan:r.capabilityPlan,
        toolMcpPlan:r.toolMcpPlan,
        architecture:r.architecture,
        asBuiltArchitecture:r.asBuiltArchitecture,
        architectureConformance:r.architectureConformance,
        databasePlan:r.databasePlan,
        projectProfile:r.projectProfile,
        analysisReport:r.analysisReport,
        settingsPlan:r.settingsPlan,
        settingsValidation:r.settingsValidation,
        settingsGeneration:r.settingsGeneration,
        createdFiles:r.createdFiles,
        modifiedFiles:r.modifiedFiles,
        debugHistory:r.debugHistory,
        debugIteration:r.debugIteration,
        testCommand:r.testCommand,
        testReturncode:r.testReturncode
      }

      const response=await fetch(`${runtimeInfo().apiBase}/presentation/export`,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          scope:exportScope,
          deck_type:exportDeckType,
          project_name:currentProjectName||'AgentStudio Project',
          project_root:resolveWorkspaceRoot(),
          generated_at:new Date().toISOString(),
          workflow_request:workflowReq||r.requirementSpec?.goal||'',
          workflow_definition:workflowDefinition||{},
          report:reportSnapshot,
          coding_style_report:codingStyleReport||{},
          llm_usage_summary:llmUsageSummary||{},
          db_erd:dbErdReport||{},
          ui_layout:uiLayoutConfig||confirmedInterviewRequirements?.ui_layout||null
        })
      })

      if(!response.ok){
        const text=await response.text()
        let message=text
        try{
          const parsed=JSON.parse(text)
          message=parsed?.detail?.message||parsed?.detail||text
        }catch{}
        throw new Error(String(message||`HTTP ${response.status}`))
      }

      const blob=await response.blob()
      const disposition=String(response.headers.get('Content-Disposition')||'')
      let filename=''
      const encodedMatch=disposition.match(/filename\*=UTF-8''([^;]+)/i)
      const plainMatch=disposition.match(/filename=\"?([^\";]+)\"?/i)
      if(encodedMatch?.[1]){
        try{ filename=decodeURIComponent(encodedMatch[1].trim()) }catch{}
      }
      if(!filename&&plainMatch?.[1]) filename=plainMatch[1].trim()
      if(!filename){
        const safeProject=String(currentProjectName||'AgentStudio_Project').replace(/[\\/:*?"<>|]+/g,'_')
        const label={ALL:'전체',WORKFLOW:'워크플로우',RUN:'실행결과',REPORT:'분석리포트',ARCHITECTURE:'아키텍처',DB_ERD:'DB_ERD'}[exportScope]||exportScope
        filename=exportDeckType==='STUDIO'
          ? `THEANOVA_AgentStudio_Studio_PPT_${label}.pptx`
          : `${safeProject}_${exportScope==='ALL'?'Agent_PPT_전체':label}.pptx`
      }

      const url=URL.createObjectURL(blob)
      const anchor=document.createElement('a')
      anchor.href=url
      anchor.download=filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(()=>URL.revokeObjectURL(url),1500)
    }catch(error){
      const message=error instanceof Error?error.message:String(error||'알 수 없는 오류')
      setPptExportError(message)
      window.alert(`PPT 다운로드 실패: ${message}`)
    }finally{
      setPptExportBusy('')
    }
  }

  const renderWorkspaceScreen=()=>{
    const leftSummary=getBuilderConversationSummary()
    const designBuilderSteps=[
      ['01','목적',leftSummary.purpose],
      ['02','기능',leftSummary.features],
      ['03','MCP / Tool',leftSummary.mcpTools],
      ['04','DB 설계',leftSummary.database],
      ['05','실행 환경',leftSummary.runtime],
      ['06','확인',leftSummary.confirmation],
    ]

    return <div
    ref={workspaceLayoutRef}
    className={`ux-workspace workspace-panel-layout ${workspaceLeftCollapsed?'workspace-left-collapsed':''} ${workspaceRightCollapsed?'workspace-right-collapsed':''} ${workspaceResizeSide?'workspace-resizing':''}`}
    style={{
      '--workspace-left-user-width':`${workspaceLeftWidth}px`,
      '--workspace-right-user-width':`${workspaceRightWidth}px`,
      '--workspace-bottom-user-height':`${workspaceBottomHeight}px`,
    }}
  >
    {projectLoadProgress.active&&<div className={projectLoadProgress.failed?'project-load-progress failed':'project-load-progress'}>
      <div className="project-load-progress-head">
        <strong>{projectLoadProgress.message}</strong>
        <span>{projectLoadProgress.percent}%</span>
      </div>
      <div className="project-load-progress-track">
        <div className="project-load-progress-fill" style={{width:`${projectLoadProgress.percent}%`}} />
      </div>
    </div>}
    <aside className="workspace-project-panel" aria-hidden={workspaceLeftCollapsed}>
      {workspaceTab==='DESIGN'?<>
        <div className="design-left-panel">
          <div className="unified-design-title">신규 Agent 설계</div>

          {designBuilderSteps.map((s,i)=><div
            className={`builder-step ${i===0||builderStarted?'on':''}`}
            key={s[0]}
          >
            <b>{s[0]}</b>
            <div>
              <strong>{s[1]}</strong>
              <small title={s[2]}>{s[2]}</small>
            </div>
          </div>)}

          <div className="builder-live-summary">
            <strong>대화 요구사항 요약</strong>
            {leftSummary.collectedItems.length
              ? <div className="builder-live-summary-list">
                  {leftSummary.collectedItems.slice(0,8).map(item=><div key={item.id}>
                    <span>{item.label}</span><b>{item.value}</b>
                  </div>)}
                </div>
              : <small>대화를 시작하면 확정된 내용이 여기에 자동 정리됩니다.</small>}
          </div>

          {(interviewAttachmentSummary||interviewAttachmentRequirements.length>0)&&<AttachmentAnalysisSummaryCard
            summary={interviewAttachmentSummary}
            files={interviewAttachmentSummaryFiles}
            requirements={interviewAttachmentRequirements}
            coverage={interviewAttachmentRequirementCoverage}
            compact={true}
            restored={requirementDraftRestored}
          />}

          <div className="builder-tip">
            <strong>질문 방식 · Quality Gate</strong>
            <span>
              이미 답한 내용과 AgentStudio가 자동 설계할 기술 세부사항은 다시 묻지 않고,
              사용자 결정이 필요한 질문 하나만 이어갑니다.
            </span>
          </div>
        </div>
      </>:<>

      <div className="panel-title-row">
        <strong>프로젝트</strong>
        <button onClick={startNewProject}>＋ 새 프로젝트</button>
      </div>
      <DebouncedProjectSearchInput value={projectSearch} onCommit={setProjectSearch} placeholder="프로젝트 검색..."/>
      <div className="project-filter-tabs">
        <button
          className={projectFilter==='ALL'?'active':''}
          onClick={()=>changeProjectFilter('ALL')}
        >전체</button>
        <button
          className={projectFilter==='RECENT'?'active':''}
          onClick={()=>changeProjectFilter('RECENT')}
        >최근</button>
        <button
          className={projectFilter==='FAVORITE'?'active':''}
          onClick={()=>changeProjectFilter('FAVORITE')}
        >즐겨찾기</button>
      </div>

      <div className={projectListLoading?'project-list-status loading':'project-list-status'}>
        <div>
          {projectListLoading?'DB 프로젝트 목록 불러오는 중...':projectListStatus}
        </div>
        <div className="project-db-path">
          연결 경로: Frontend → FastAPI → PostgreSQL
          <br/>
          API 주소: {runtimeInfo().apiBase}
        </div>
        {projectListLogPath&&<div className="project-log-path">
          <strong>로그 전체 경로</strong>
          <code>{projectListLogPath}</code>
        </div>}
      </div>
      <div className="project-list-scroll">
        {filteredProjects.length===0&&<div className="empty-mini">
          {projectListLoading
            ? 'DB 프로젝트 목록을 불러오는 중입니다.'
            : projectList.length===0
              ? 'DB에 저장된 프로젝트가 없습니다.'
              : projectFilter==='RECENT'
                ? '최근 사용 기록이 있는 프로젝트가 없습니다.'
                : projectFilter==='FAVORITE'
                  ? '즐겨찾기 프로젝트가 없습니다.'
                  : '조건에 맞는 프로젝트가 없습니다.'}
        </div>}
        {filteredProjects.map(p=><button key={p.id}
          className={selectedProjectId===p.id?'project-list-item active':'project-list-item'}
          onClick={()=>loadProject(p.id)}>
          <span className="project-icon">▣</span>
          <div className="project-item-main">
            <strong>{p.name}</strong>
            <small>{p.project_root}</small>
            {p.last_opened_at&&<em>
              최근 {new Date(p.last_opened_at).toLocaleString()}
            </em>}
          </div>
          <span
            className={p.is_favorite?'project-favorite active':'project-favorite'}
            title={p.is_favorite?'즐겨찾기 해제':'즐겨찾기 추가'}
            onClick={e=>toggleProjectFavorite(p,e)}
          >★</span>
        </button>)}
      </div>
      <div className="project-git-card">
        <div className="project-git-head">
          <strong>Git 연결</strong>
          <button
            type="button"
            onClick={()=>loadGitInfo()}
            disabled={gitInfoLoading||!root}
            title="Git 상태 새로고침"
          >
            {gitInfoLoading?'...':'↻'}
          </button>
        </div>

        {!root&&<div className="project-git-empty">프로젝트를 선택하세요.</div>}

        {root&&!gitInfo&&
          <div className="project-git-empty">
            Git 정보를 확인하는 중입니다.
          </div>
        }

        {gitInfo&&gitInfo.is_git===false&&
          <div className="project-git-empty">
            <span className="git-dot off"/>
            {gitInfo.message||'Git 저장소가 아닙니다.'}
          </div>
        }

        {gitInfo?.is_git===true&&<>
          <div className="project-git-row">
            <span>상태</span>
            <strong className={gitInfo.clean?'git-ok':'git-warn'}>
              {gitInfo.clean?'Clean':`${gitInfo.changed_count}개 변경`}
            </strong>
          </div>

          <div className="project-git-row">
            <span>브랜치</span>
            <code title={gitInfo.branch||''}>{gitInfo.branch||'-'}</code>
          </div>

          <div className="project-git-row">
            <span>HEAD</span>
            <code>{gitInfo.head||'-'}</code>
          </div>

          <div className="project-git-row">
            <span>동기화</span>
            <strong>
              {gitInfo.sync_status==='up-to-date'&&'최신'}
              {gitInfo.sync_status==='ahead'&&`Ahead ${gitInfo.ahead}`}
              {gitInfo.sync_status==='behind'&&`Behind ${gitInfo.behind}`}
              {gitInfo.sync_status==='diverged'&&`Ahead ${gitInfo.ahead} / Behind ${gitInfo.behind}`}
            </strong>
          </div>

          <div className="project-git-origin">
            <span>origin</span>
            <code title={gitInfo.origin||''}>
              {gitInfo.origin||'원격 저장소 없음'}
            </code>
          </div>
        </>}

        {gitInfo?.is_git===true&&<>
          <div className="git-commit-box">
            <input
              value={gitCommitMessage}
              onChange={e=>setGitCommitMessage(e.target.value)}
              placeholder="커밋 메시지"
              disabled={!!gitActionBusy}
            />
          </div>

          <div className="git-action-grid">
            <button type="button" onClick={()=>runGitAction('status')} disabled={!!gitActionBusy}>상태</button>
            <button type="button" onClick={()=>runGitAction('fetch')} disabled={!!gitActionBusy}>Fetch</button>
            <button type="button" onClick={()=>runGitAction('pull')} disabled={!!gitActionBusy}>Pull</button>
            <button type="button" onClick={()=>runGitAction('add')} disabled={!!gitActionBusy}>Add</button>
            <button type="button" onClick={()=>runGitAction('commit')} disabled={!!gitActionBusy}>Commit</button>
            <button type="button" onClick={()=>runGitAction('push')} disabled={!!gitActionBusy}>Push</button>
            <button type="button" className="primary" onClick={()=>runGitAction('sync')} disabled={!!gitActionBusy}>
              {gitActionBusy==='sync'?'업로드 중...':'수정파일 올리기'}
            </button>
            <button type="button" onClick={()=>runGitAction('log')} disabled={!!gitActionBusy}>로그</button>
            <button type="button" onClick={()=>runGitAction('diff')} disabled={!!gitActionBusy}>Diff</button>
          </div>

          {gitActionResult&&<div className={gitActionResult.ok?'git-action-result ok':'git-action-result failed'}>
            <strong>
              {gitActionResult.ok?'Git 작업 완료':'Git 작업 실패'}
              {gitActionResult.action?` · ${gitActionResult.action}`:''}
            </strong>
            {gitActionResult.stdout&&<pre>{gitActionResult.stdout}</pre>}
            {gitActionResult.stderr&&<pre>{gitActionResult.stderr}</pre>}
          </div>}
        </>}

      </div>

      <div className="quick-start-box">
        <SectionTitle title="빠른 시작"/>
        <button onClick={startNewProject}>＋ 새 Agent 만들기</button>
        <button onClick={()=>{setScreen('MCP');refreshMcp()}}>◉ MCP 도구 확인</button>
        <button onClick={()=>location.href='/system'}>⚙ 시스템 진단</button>
      </div>
    
      </>}
    </aside>

    {!workspaceLeftCollapsed&&<div
      className={`workspace-panel-resizer workspace-panel-resizer-left ${workspaceResizeSide==='left'?'active':''}`}
      role="separator"
      aria-orientation="vertical"
      aria-label="좌측 영역 너비 조절"
      title="드래그하여 좌측 영역 너비 조절"
      onPointerDown={event=>beginWorkspacePanelResize('left',event)}
    />}

    <main className={`workspace-main workspace-tab-${workspaceTab.toLowerCase()} ${
      ['RUN','REPORT','ARCHITECTURE','DB_ERD','LLM','BROWSER'].includes(workspaceTab)
        ? 'compact-workspace result-only-workspace'
        : workspaceTab==='CODE'&&!isBinaryPreviewFile(selected)
          ? 'workspace-with-bottom-tools code-tools-workspace'
          : 'workspace-clean-design'
    } ${workspaceBottomCollapsed?'workspace-bottom-collapsed':''} ${workspaceBottomResizing?'workspace-bottom-resizing':''}`}>
      <div className="workspace-tabs workspace-tabs-with-panel-controls">
        <button
          type="button"
          className={`workspace-panel-toggle workspace-panel-toggle-left ${workspaceLeftCollapsed?'collapsed':''}`}
          onClick={()=>setWorkspaceLeftCollapsed(v=>!v)}
          title={workspaceLeftCollapsed?'좌측 영역 열기':'좌측 영역 닫기'}
          aria-label={workspaceLeftCollapsed?'좌측 영역 열기':'좌측 영역 닫기'}
          aria-pressed={!workspaceLeftCollapsed}
        >
          <span aria-hidden="true">{workspaceLeftCollapsed?'▶':'◀'}</span>
        </button>
        <div className="workspace-tab-list">
          {[
            ['DESIGN','에이전트 설계'],
            ['WORKFLOW','워크플로우'],
            ['CODE','코드 편집'],
            ['RUN','실행 결과'],
            ['REPORT','분석 리포트'],
            ['ARCHITECTURE','아키텍처'],
            ['DB_ERD','DB ERD'],
            ['LLM','LLM 리스트'],
            ['BROWSER','웹브라우저']
          ].map(([k,t])=><button key={k}
            className={workspaceTab===k?'active':''}
            onClick={()=>setWorkspaceTab(k)}>{t}</button>)}
        </div>
        {['WORKFLOW','RUN','REPORT','ARCHITECTURE','DB_ERD'].includes(workspaceTab)&&<div className="workspace-ppt-export-group">
          <button
            type="button"
            className="workspace-ppt-export-button all"
            onClick={()=>exportWorkspacePowerPoint('ALL','AGENT')}
            disabled={!!pptExportBusy}
            title="현재 생성 중인 Agent 또는 로드된 프로젝트의 워크플로우·실행결과·분석리포트·아키텍처·DB ERD 전체를 PowerPoint로 다운로드"
          >
            {pptExportBusy==='AGENT:ALL'?'PPT 생성 중...':'▣ Agent PPT'}
          </button>
          <button
            type="button"
            className="workspace-ppt-export-button studio"
            onClick={()=>exportWorkspacePowerPoint('ALL','STUDIO')}
            disabled={!!pptExportBusy}
            title="THEANOVA AgentStudio 자체의 전체 Workflow·기능·Runtime·Architecture·DB ERD 문서를 PowerPoint로 다운로드"
          >
            {pptExportBusy==='STUDIO:ALL'?'PPT 생성 중...':'▣ Studio PPT'}
          </button>
        </div>}
        <button
          type="button"
          className={`workspace-panel-toggle workspace-panel-toggle-right ${workspaceRightCollapsed?'collapsed':''}`}
          onClick={()=>setWorkspaceRightCollapsed(v=>!v)}
          title={workspaceRightCollapsed?'우측 영역 열기':'우측 영역 닫기'}
          aria-label={workspaceRightCollapsed?'우측 영역 열기':'우측 영역 닫기'}
          aria-pressed={!workspaceRightCollapsed}
        >
          <span aria-hidden="true">{workspaceRightCollapsed?'◀':'▶'}</span>
        </button>
      </div>

      <div className={
        ['RUN','REPORT','ARCHITECTURE','DB_ERD','LLM','BROWSER'].includes(workspaceTab)
          ? 'workspace-top-pane compact-result-pane'
          : 'workspace-top-pane'
      }>
        {workspaceTab==='DESIGN'&&<div className="unified-agent-design">
          <section className="unified-design-chat">
            <AgentDesignProjectToolbar
              designProjectId={designProjectId}
              projectName={newAgentName||getBuilderConversationSummary().purpose}
              savedAt={designProjectSavedAt||requirementDraftSavedAt}
              status={designProjectProgressInfo().status}
              progress={designProjectProgressInfo().progress}
              onNew={()=>{
                const hasWork=(chat||[]).some(item=>item?.role==='user')||Boolean(designProjectId)
                if(hasWork&&!window.confirm('현재 Agent 설계를 종료하고 새 설계 프로젝트를 시작할까요?\n\n저장하지 않은 변경이 있다면 먼저 프로젝트 저장을 눌러주세요.')) return
                startNewProject()
              }}
              onSave={()=>saveAgentDesignProject({createVersion:true,versionLabel:'사용자 수동 저장 Snapshot'})}
              onLoad={loadAgentDesignProject}
            />
            <div className="builder-chat-head">
              <div>
                <span className="ai-avatar">AI</span>
                <div>
                  <strong>Agent 설계 인터뷰</strong>
                  <small>{aiInterviewLabel}</small>
                </div>
              </div>

              <div className="builder-head-actions">
                <button type="button" className="builder-layout-button" onClick={()=>setUiLayoutGalleryOpen(true)}>▦ UI Layout</button>
                <button
                  type="button"
                  className="builder-workflow-button"
                  onClick={()=>{
                    const request=
                      workflowReq
                      ||buildRequirementRequestFromCollectedInfo()
                      ||chat.find(x=>x.role==='user')?.content
                      ||''

                    if(request){
                      saveRequirementDraft()
                      setRoot(newAgentProjectRoot||root)
                      setWorkspaceTab('WORKFLOW')
                      setWorkflowView('TARGET')
                      previewTargetWorkflow(request)
                    }else{
                      setTargetWorkflowError(
                        '먼저 만들 Agent의 요구사항을 입력하세요.'
                      )
                    }
                  }}
                >
                  ◇ Workflow 보기
                </button>
                <span className="live-dot">● 대화형 수집</span>
              </div>
            </div>

            <div className="builder-messages unified">
              {chat.map((m,i)=><div
                key={i}
                className={`builder-msg ${m.role}`}
              >
                <span>{m.role==='assistant'?'AI':'나'}</span>
                <div>{m.role==='assistant'?protectInterviewAssistantAnswer(m.content):sanitizeInterviewDisplayText(m.content)}</div>
              </div>)}

              {busy&&<div className="builder-msg assistant">
                <span>AI</span>
                <div>답변을 분석하고 다음 질문을 준비하고 있습니다...</div>
              </div>}

              <div
                ref={builderMessagesEndRef}
                className="builder-messages-end"
                aria-hidden="true"
              />
            </div>

            <AiAttachmentPicker
              attachments={interviewAttachments}
              onChange={setInterviewAttachments}
              projectRoot={newAgentProjectRoot||root||''}
              initialPath={newAgentProjectRoot||root||''}
              disabled={busy||interviewAttachmentSummaryBusy}
              label="참고 파일 선택"
              title="Agent 설계 인터뷰에서 분석할 요구사항/설계/코드 파일을 선택하세요."
              maxFiles={12}
              analysisPurpose="Agent 설계 인터뷰 참고 파일 분석 준비"
              analysisActive={busy||interviewAttachmentSummaryBusy}
              onAnalysisStateChange={setInterviewAttachmentAnalysis}
            />
            {interviewAttachments.length>0&&interviewAttachmentAnalysis.ready&&!busy&&!interviewAttachmentSummaryBusy&&<div className="attachment-ready-gate">
              <div>
                <strong>✓ 첨부 Context 준비 완료</strong>
                <span>파일 첨부만으로 DB·Workflow·Architecture 심층 분석을 자동 시작하지 않습니다. 답변 보내기 또는 아래 버튼을 눌렀을 때 본격 분석합니다.</span>
              </div>
              <button type="button" onClick={summarizeInterviewAttachments}>첨부만 먼저 분석</button>
            </div>}
            <AgentActivityProgress
              active={busy||interviewAttachmentSummaryBusy}
              kind={interviewAttachmentSummaryBusy?'ATTACHMENT_SUMMARY':busy?'INTERVIEW':'IDLE'}
              attachmentCount={interviewAttachments.length}
              attachmentState={interviewAttachmentAnalysis}
              databasePreviewLoading={liveDatabasePreviewLoading}
              error={interviewActivityError}
              canRetry={!!interviewRetryPayload}
              onCancel={cancelInterviewActivity}
              onRetry={retryInterviewActivity}
            />
            {interviewAttachmentSummaryBusy&&<div className="attachment-intent-summary loading">
              <div className="attachment-intent-summary-head">
                <strong>첨부 파일 통합 요구사항을 분석하고 있습니다...</strong>
                <span>AI 통합 분석</span>
              </div>
              <p>사용자가 시작한 첨부 분석입니다. 상세 진행 상태와 Backend Heartbeat는 위 진행 패널에서 확인할 수 있습니다.</p>
            </div>}
            {interviewAttachmentSummaryError&&<div className="attachment-intent-summary error">
              <div className="attachment-intent-summary-head"><strong>첨부 요구사항 정리 실패</strong></div>
              <p>{interviewAttachmentSummaryError}</p>
            </div>}
            {(interviewAttachmentSummary||interviewAttachmentRequirements.length>0)&&<AttachmentAnalysisSummaryCard
              summary={interviewAttachmentSummary}
              files={interviewAttachmentSummaryFiles}
              requirements={interviewAttachmentRequirements}
              coverage={interviewAttachmentRequirementCoverage}
              restored={requirementDraftRestored}
              onClear={()=>{
                setInterviewAttachmentSummary('')
                setInterviewAttachmentSummaryFiles([])
                setInterviewAttachmentRequirements([])
                setInterviewAttachmentRequirementCoverage({})
                setInterviewAttachmentMemory('')
                setConfirmedInterviewRequirements({})
                invalidateRequirementWorkflowAfterEdit('첨부 파일 분석 Context를 지웠습니다. 남은 요구사항 기준으로 다시 정의해 주세요.')
              }}
            />}
            {interviewAttachmentMemory&&!interviewAttachments.length&&!interviewAttachmentSummary&&<div className="interview-attachment-memory">
              <span>✓ 참고 파일 분석 내용이 현재 인터뷰 Context에 반영되었습니다. 원본 첨부는 자동 해제되어 다음 질문에 반복 첨부되지 않습니다.</span>
              <button type="button" onClick={()=>setInterviewAttachmentMemory('')}>참고 Context 지우기</button>
            </div>}

            <div className="builder-input unified">
              <textarea
                value={input}
                onChange={e=>setInput(e.target.value)}
                onKeyDown={e=>{
                  if(e.key==='Enter'&&!e.shiftKey){
                    e.preventDefault()
                    sendBuilderAnswer()
                  }
                }}
                placeholder="현재 질문에 답해주세요. Shift+Enter로 줄바꿈"
              />
              <button
                onClick={sendBuilderAnswer}
                disabled={busy||interviewAttachmentSummaryBusy||(!input.trim()&&!interviewAttachments.length)||(interviewAttachments.length&&!interviewAttachmentAnalysis.ready)}
              >
                답변 보내기
              </button>
            </div>
          </section>
        </div>}
        {workspaceTab==='DESIGN'&&<UILayoutTemplateGallery
          open={uiLayoutGalleryOpen}
          value={uiLayoutConfig}
          purposeText={buildRequirementRequestFromCollectedInfo()}
          onClose={()=>setUiLayoutGalleryOpen(false)}
          onApply={(config)=>{
            setUiLayoutConfig(config)
            setUiLayoutGalleryOpen(false)
            setRequirementManualOverrides(prev=>({...prev,ui:uiLayoutSummary(config)}))
            setConfirmedInterviewRequirements(prev=>({...prev,ui_layout:config}))
            invalidateRequirementWorkflowAfterEdit('UI / Layout 템플릿을 변경했습니다. 선택한 레이아웃을 기준으로 Workflow와 코드 구조를 다시 설계할 수 있습니다.')
            setTimeout(()=>saveRequirementDraft(),0)
          }}
        />}

        {workspaceTab==='WORKFLOW'&&<div className="workflow-page visual-workflow-page">
          <div className="workflow-page-head visual">
            <div>
              <span className="workflow-eyebrow">THEANOVA AGENT FACTORY MAP</span>
              <h2>Workflow 설계도</h2>
              <p>단계를 나열하는 화면이 아니라, Agent가 어떻게 설계되고 움직이는지 한눈에 보는 구조도입니다.</p>
            </div>
            <div className="workspace-export-actions">
              <button
                type="button"
                className="workspace-ppt-export-button"
                onClick={()=>exportWorkspacePowerPoint('WORKFLOW','AGENT')}
                disabled={!!pptExportBusy}
              >
                {pptExportBusy==='AGENT:WORKFLOW'?'PPT 생성 중...':'▣ PPT 다운로드'}
              </button>
              <button type="button" onClick={loadWorkflowDefinition}>↻ 새로고침</button>
            </div>
          </div>
          {pptExportError&&<div className="workspace-export-error">PPT 내보내기 오류: {pptExportError}</div>}

          <div className="workflow-view-tabs visual">
            <button
              type="button"
              className={workflowView==='STUDIO'?'active':''}
              onClick={()=>setWorkflowView('STUDIO')}
            >
              <span>◇</span>
              <div><strong>AgentStudio 제작 흐름</strong><small>Agent Factory 전체 공정</small></div>
            </button>
            <button
              type="button"
              className={workflowView==='TARGET'?'active target':''}
              onClick={()=>setWorkflowView('TARGET')}
            >
              <span>⇢</span>
              <div><strong>개발 대상 Agent 흐름</strong><small>실제 업무 수행 Workflow</small></div>
            </button>
          </div>

          {workflowView==='STUDIO'&&<div className="workflow-canvas-card visual-factory-canvas">
            <div className="workflow-section-head visual">
              <div>
                <span className="section-visual-icon">◇</span>
                <div>
                  <strong>THEANOVA AgentStudio 제작 Workflow</strong>
                  <small>자연어 요구를 실행 가능한 Agent 프로그램으로 만드는 전체 제작 공정</small>
                </div>
              </div>
              <span className="workflow-type-badge">AGENT FACTORY</span>
            </div>

            <FactoryWorkflowDiagram definition={workflowDefinition}/>
          </div>}

          {workflowView==='TARGET'&&<div className="workflow-canvas-card visual-target-canvas">
            <div className="workflow-section-head visual">
              <div>
                <span className="section-visual-icon target">⇢</span>
                <div>
                  <strong>{targetWorkflowPreview?.target_agent_workflow?.name||(selectedProjectId?loadedProjectAnalysis?.adaptive_report?.workflow?.name:null)||'개발 대상 Agent Workflow'}</strong>
                  <small>{selectedProjectId&&loadedProjectAnalysis?.adaptive_report?.workflow?.source==='PROJECT_SOURCE_INFERENCE'?'현재 프로젝트 소스에서 추론한 실제 처리 흐름':'실제 사용자가 Agent를 실행했을 때 처리되는 업무 순서'}</small>
                </div>
              </div>
              <span className="workflow-type-badge target">TARGET AGENT</span>
            </div>

            <div className="target-workflow-request visual">
              <div className="target-request-icon">✦</div>
              <textarea
                value={workflowReq}
                onChange={e=>setWorkflowReq(e.target.value)}
                placeholder="예: 유튜브 영상을 자동 업로드하는 에이전트를 만들어줘"
              />
              <button
                type="button"
                onClick={()=>previewTargetWorkflow()}
                disabled={targetWorkflowLoading||!workflowReq.trim()}
              >
                {targetWorkflowLoading
                  ? '분석 중...'
                  : agentBuildStage==='WORKFLOW_READY'
                    ? '◇ Workflow 다시 설계'
                    : '◇ Workflow 설계'}
              </button>
            </div>

            {workflowProgress.active&&<div className="workflow-progress-card">
              <div className="workflow-progress-head">
                <div>
                  <span className="workflow-progress-pulse">●</span>
                  <div>
                    <strong>{workflowProgress.stage}</strong>
                    <small>{workflowProgress.detail}</small>
                  </div>
                </div>
                <b>{workflowProgress.percent}%</b>
              </div>

              <div
                className="workflow-progress-track"
                role="progressbar"
                aria-label="Workflow 설계 진행률"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow={workflowProgress.percent}
              >
                <div
                  className="workflow-progress-fill"
                  style={{width:`${workflowProgress.percent}%`}}
                />
              </div>

              <div className="workflow-progress-stages">
                {[
                  ['요구사항',5],
                  ['AI 설계',18],
                  ['응답 대기',45],
                  ['검증',90],
                  ['완료',100]
                ].map(([label,threshold])=><span
                  key={label}
                  className={
                    workflowProgress.percent>=threshold
                      ? 'done'
                      : ''
                  }
                >
                  <i></i>{label}
                </span>)}
              </div>
            </div>}

            {targetWorkflowError&&<div className="workflow-error">{targetWorkflowError}</div>}

            {targetWorkflowQuality&&<div className={`workflow-quality-bar ${targetWorkflowQuality.warning?'warning':'ok'}`}>
              <div>
                <span>{targetWorkflowQuality.warning?'!':'✓'}</span>
                <div>
                  <strong>Workflow 요구사항 반영 검사</strong>
                  <small>
                    단계 {targetWorkflowQuality.step_count}개 ·
                    분기 {targetWorkflowQuality.has_branch?'있음':'없음'} ·
                    재시도 {targetWorkflowQuality.has_retry?'있음':'없음'} ·
                    실패처리 {targetWorkflowQuality.has_failure_policy?'있음':'없음'}
                  </small>
                </div>
              </div>
              {targetWorkflowQuality.warning&&<b>{targetWorkflowQuality.warning}</b>}
            </div>}

            {targetWorkflowPreview?.design_runtime&&<div className="workflow-provider-routing-note">
              <strong>고난도 설계 AI</strong>
              <span>Workflow / LangGraph: {String(targetWorkflowPreview.design_runtime.workflow_provider||'-').toUpperCase()}</span>
              <span>DB Entity / 관계: {String(targetWorkflowPreview.design_runtime.database_provider||'해당 없음').toUpperCase()}</span>
              <small>자동 모드 우선순위: Codex → OpenAI → Ollama</small>
            </div>}

            {targetWorkflowPreview?.database_plan&&<div className={`database-design-card ${targetWorkflowPreview.database_plan.enabled?'enabled':'disabled'} ${targetWorkflowPreview.database_plan.finalized?'finalized':''}`}>
              <div className="database-design-head">
                <div>
                  <span className="database-design-icon">▦</span>
                  <div>
                    <strong>DB 자동 설계</strong>
                    <small>{targetWorkflowPreview.database_plan.enabled
                      ? 'Core + 기능별 Module + Custom Business Entity를 조립한 PostgreSQL 설계입니다.'
                      : '현재 요구사항에는 영속 DB가 필요하지 않아 DB Module을 생성하지 않습니다.'}</small>
                  </div>
                </div>
                <span className={targetWorkflowPreview.database_plan.finalized?'database-design-status done':'database-design-status'}>
                  {targetWorkflowPreview.database_plan.finalized?'확정':'확인 필요'}
                </span>
              </div>

              {targetWorkflowPreview.database_plan.enabled&&<>
                <div className="database-design-strategy">{targetWorkflowPreview.database_plan.strategy}</div>
                <div className="database-module-list">
                  {(targetWorkflowPreview.database_plan.modules||[]).map(module=><span key={module.id} className={module.required?'required':''} title={module.reason}>
                    {module.label||module.id}{module.required?' · 필수':''}
                  </span>)}
                </div>

                <div className="database-design-summary-grid">
                  <div><small>Module</small><strong>{(targetWorkflowPreview.database_plan.modules||[]).length}</strong></div>
                  <div><small>Table</small><strong>{(targetWorkflowPreview.database_plan.tables||[]).length}</strong></div>
                  <div><small>Relationship</small><strong>{(targetWorkflowPreview.database_plan.relationships||[]).length}</strong></div>
                  <div><small>Validator</small><strong>{targetWorkflowPreview.database_plan.validation?.valid===false?'FAIL':'PASS'}</strong></div>
                </div>

                <div className="database-table-plan-list">
                  {(targetWorkflowPreview.database_plan.tables||[]).map(table=><div key={table.name} className="database-table-plan-row">
                    <div>
                      <strong>{table.name}</strong>
                      <span>{table.module}</span>
                    </div>
                    <small>{table.purpose}</small>
                    <em>{(table.columns||[]).length} columns</em>
                  </div>)}
                </div>

                {(targetWorkflowPreview.database_plan.validation?.warnings||[]).length>0&&<div className="database-design-warning">
                  {(targetWorkflowPreview.database_plan.validation.warnings||[]).map((warning,index)=><div key={index}>! {warning}</div>)}
                </div>}
                {(targetWorkflowPreview.database_plan.validation?.errors||[]).length>0&&<div className="database-design-error">
                  {(targetWorkflowPreview.database_plan.validation.errors||[]).map((error,index)=><div key={index}>× {error}</div>)}
                </div>}

                <div className="database-design-policy">{targetWorkflowPreview.database_plan.jsonb_policy}</div>

                <div className="database-design-actions">
                  <button
                    type="button"
                    className="primary"
                    disabled={databaseDesignFinalizeBusy||targetWorkflowPreview.database_plan.validation?.valid===false||targetWorkflowPreview.database_plan.finalized}
                    onClick={()=>finalizeDatabaseDesign()}
                  >
                    {databaseDesignFinalizeBusy?'DDL 생성 중...':targetWorkflowPreview.database_plan.finalized?'✓ DB 설계 확정됨':'✓ DB 설계 확정 · DDL 생성'}
                  </button>
                  {targetWorkflowPreview.database_plan.finalized&&<span>backend/migrations/001_initial_schema.sql 생성 준비 완료</span>}
                </div>

                {targetWorkflowPreview.database_plan.finalized&&targetWorkflowPreview.database_plan.ddl&&<details className="database-ddl-preview">
                  <summary>PostgreSQL DDL 미리보기</summary>
                  <pre>{targetWorkflowPreview.database_plan.ddl}</pre>
                </details>}
              </>}
            </div>}

            <TargetWorkflowDiagram workflow={targetWorkflowPreview?.target_agent_workflow||(selectedProjectId?loadedProjectAnalysis?.adaptive_report?.workflow:null)}/>
          </div>}
        </div>}

        <div className={
          workspaceTab==='CODE'
            ? 'full-code-pane persistent-code-editor visible'
            : 'full-code-pane persistent-code-editor hidden'
        }>
          <div className="file-path-bar">{selected||'파일을 선택하세요.'}</div>
          
          <div className="code-editor-stack">
<div className="code-file-tabs-shell">
            <button
              type="button"
              className={
                focusOwner==='editor'
                  ? 'editor-focus-indicator active editor-files-menu-trigger'
                  : 'editor-focus-indicator editor-files-menu-trigger'
              }
              title="열린 파일 관리"
              onClick={(e)=>{
                e.stopPropagation()
                const rect=e.currentTarget.getBoundingClientRect()
                setEditorTabMenu(null)
                setEditorFilesMenu(prev=>
                  prev
                    ? null
                    : {
                        x:rect.left,
                        y:rect.bottom+3
                      }
                )
              }}
            >
              편집 <span className="editor-files-menu-caret">▾</span>
            </button>

            <button
              type="button"
              className="code-file-tabs-nav left"
              title="이전 열린 파일 보기"
              aria-label="열린 파일 탭을 왼쪽으로 스크롤"
              onClick={()=>scrollEditorTabs(-1)}
            >
              ‹
            </button>

            <div
              className="code-file-tabs"
              ref={editorTabsScrollRef}
              onWheel={(event)=>{
                if(Math.abs(event.deltaY)<=Math.abs(event.deltaX)) return
                event.currentTarget.scrollLeft+=event.deltaY
                event.preventDefault()
              }}
            >
              {openEditorFiles.map(path=>{
                const fileName=
                  path.replace(/\\/g,'/').split('/').pop()||path
                const active=selected===path
                const dirty=!!editorFileDirty[path]
                const pinned=pinnedEditorFiles.includes(path)

                return (
                  <div
                    key={path}
                    data-editor-path={path}
                    className={[
                      'code-file-tab',
                      active?'active':'',
                      pinned?'pinned':''
                    ].filter(Boolean).join(' ')}
                    title={getEditorFileFullPath(path)}
                    onContextMenu={(e)=>{
                      e.preventDefault()

                      setEditorTabMenu({
                        path,
                        x:e.clientX,
                        y:e.clientY
                      })
                    }}
                  >
                    <button
                      type="button"
                      className="code-file-tab-select"
                      onClick={()=>activateEditorFile(path)}
                    >
                      <span className="code-file-tab-name">
                        {fileName}
                      </span>
                      {dirty&&
                        <span
                          className="code-file-tab-dirty"
                          title="저장되지 않은 변경"
                        >
                          ●
                        </span>
                      }
                      {editorExternalState[normalizeProjectRelativePath(path)]&&
                        <span
                          className="code-file-tab-external"
                          title={editorExternalState[normalizeProjectRelativePath(path)]==='deleted'?'외부에서 파일이 삭제되었습니다.':'외부 변경이 감지되었습니다.'}
                        >
                          ↻
                        </span>
                      }
                    </button>
                    <button
                      type="button"
                      className={
                        pinned
                          ? 'code-file-tab-pin pinned'
                          : 'code-file-tab-pin'
                      }
                      onClick={(e)=>{
                        e.stopPropagation()
                        toggleEditorFilePin(path)
                      }}
                      title={pinned?'핀 고정 해제':'핀 고정'}
                      aria-pressed={pinned}
                    >
                      📌
                    </button>
                    <button
                      type="button"
                      className="code-file-tab-close"
                      onClick={(e)=>{
                        e.stopPropagation()
                        closeEditorFile(path)
                      }}
                      title="파일 닫기"
                    >
                      ×
                    </button>
                  </div>
                )
              })}
              {openEditorFiles.length===0&&
                <div className="code-file-tab-empty">열린 파일이 없습니다.</div>
              }
            </div>

            <button
              type="button"
              className="code-file-tabs-nav right"
              title="다음 열린 파일 보기"
              aria-label="열린 파일 탭을 오른쪽으로 스크롤"
              onClick={()=>scrollEditorTabs(1)}
            >
              ›
            </button>

            <div className="code-file-actions-fixed">
              <button
                type="button"
                className="powershell-run-button editor-find-toolbar-button"
                onClick={()=>openEditorTextSearch('CURRENT')}
                disabled={!selected}
                title="현재 파일에서 찾기 · 검색창에서 프로젝트 전체로 전환할 수 있습니다."
              >
                ⌕ 찾기
              </button>
              {isBookmarkableTextEditorFile(selected)&&!editorLoadErrors[selected]&&
                <div className="editor-bookmark-toolbar" aria-label="현재 텍스트 파일 북마크">
                  <button
                    type="button"
                    className="powershell-run-button editor-bookmark-toggle-button"
                    title="현재 커서 줄에 북마크 추가/해제 · 코드 왼쪽 파란 북마크 여백을 클릭해도 됩니다."
                    onClick={()=>toggleEditorLineBookmark()}
                  >
                    🔖 현재 줄
                  </button>
                  <button type="button" disabled={!activeTextEditorBookmarks.length} title="이전 북마크로 이동" onClick={()=>moveToEditorBookmark(-1)}>◀</button>
                  <span className="editor-bookmark-count" title="현재 파일에 저장된 줄 북마크 수"><i aria-hidden="true" />{activeTextEditorBookmarks.length}</span>
                  <button type="button" disabled={!activeTextEditorBookmarks.length} title="다음 북마크로 이동" onClick={()=>moveToEditorBookmark(1)}>▶</button>
                  {activeTextEditorBookmarks.length>0&&<button type="button" className="editor-bookmark-clear-button" title="현재 파일의 북마크 모두 해제" onClick={clearEditorBookmarks}>해제</button>}
                </div>
              }
              {selected?.toLowerCase?.().endsWith('.ps1')&&
                <div className="powershell-editor-actions">
                  <button
                    type="button"
                    className="powershell-run-button"
                    title="F5 · 현재 PowerShell 파일 전체 내용을 터미널에서 실행"
                    onClick={()=>runCurrentPowerShellFile({selectionOnly:false})}
                  >
                    ▶ 전체 실행 <span className="editor-run-shortcut">F5</span>
                  </button>
                  <button
                    type="button"
                    className="powershell-run-button selection"
                    title="F8 · 현재 Editor에서 선택한 PowerShell 코드만 터미널에서 실행"
                    onClick={()=>runCurrentPowerShellFile({selectionOnly:true})}
                  >
                    ▣ 선택 실행 <span className="editor-run-shortcut">F8</span>
                  </button>
                  {activeTerminal?.busy&&<button type="button" className="powershell-run-button execution-stop-button" onClick={()=>interruptTerminal(activeTerminalId)}>■ 실행 정지</button>}
                </div>
              }
              {selected?.toLowerCase?.().endsWith('.py')&&
                <div className="powershell-editor-actions python-editor-actions">
                  <button
                    type="button"
                    className="powershell-run-button python"
                    title="F5 · 현재 Python 파일 전체 Editor 내용을 프로젝트 Python 환경에서 실행"
                    onClick={()=>runCurrentPythonFile({selectionOnly:false})}
                  >
                    ▶ 전체 실행 <span className="editor-run-shortcut">F5</span>
                  </button>
                  <button
                    type="button"
                    className="powershell-run-button python selection"
                    title="F8 · 현재 Editor에서 선택한 Python 코드만 지속형 Python 세션에서 실행"
                    onClick={()=>runCurrentPythonFile({selectionOnly:true})}
                  >
                    ▣ 선택 실행 <span className="editor-run-shortcut">F8</span>
                  </button>
                  {pythonExecutionState.busy&&<button type="button" className="powershell-run-button execution-stop-button" onClick={stopPythonExecution}>■ 실행 정지</button>}
                </div>
              }
              {isNotebookFile(selected)&&!editorLoadErrors[selected]&&
                <div className="powershell-editor-actions notebook-editor-actions">
                  <button
                    type="button"
                    className="powershell-run-button python"
                    title="F5 · Notebook의 모든 Python Code 셀을 위에서부터 순서대로 실행"
                    onClick={()=>notebookEditorControllerRef.current?.runAll?.()}
                  >
                    ▶ 전체 실행 <span className="editor-run-shortcut">F5</span>
                  </button>
                  <button
                    type="button"
                    className="powershell-run-button python selection"
                    title="현재 선택된 Notebook Code 셀 전체 실행"
                    onClick={()=>notebookEditorControllerRef.current?.runActiveCell?.()}
                  >
                    ▶ 셀 실행
                  </button>
                  <button
                    type="button"
                    className="powershell-run-button python selection"
                    title="F8 · 현재 Notebook Code 셀에서 선택한 Python 코드만 실행"
                    onClick={()=>notebookEditorControllerRef.current?.runSelection?.()}
                  >
                    ▣ 선택 실행 <span className="editor-run-shortcut">F8</span>
                  </button>
                  {pythonExecutionState.busy&&<button type="button" className="powershell-run-button execution-stop-button" onClick={()=>notebookEditorControllerRef.current?.stopExecution?.()}>■ 실행 정지</button>}
                </div>
              }
              {selected?.toLowerCase?.().endsWith('.cmd')&&
                <div className="powershell-editor-actions cmd-editor-actions">
                  <button
                    type="button"
                    className="powershell-run-button cmd"
                    title="F5 · 현재 CMD 파일 실행"
                    onClick={runCurrentCmdFile}
                    disabled={cmdExecution.busy}
                  >
                    {cmdExecution.busy?'실행 중…':'▶ 실행'} <span className="editor-run-shortcut">F5</span>
                  </button>
                  {cmdExecution.busy&&<button type="button" className="powershell-run-button execution-stop-button" onClick={stopCurrentCmdFile}>■ 실행 정지</button>}
                </div>
              }
              {selected?.toLowerCase?.().endsWith('.sql')&&
                <div className="powershell-editor-actions sql-editor-actions">
                  <span className={sqlConnectionStatus?.connected?'sql-connection-chip connected':'sql-connection-chip'}>
                    {sqlConnectionStatus?.connected?'● DB 연결됨':'○ DB 연결 필요'}
                  </span>
                  <button
                    type="button"
                    className="powershell-run-button sql"
                    title="F5 · 현재 SQL 파일 전체 실행"
                    onClick={()=>runSqlEditor({selectionOnly:false})}
                    disabled={sqlQueryBusy}
                  >
                    ▶ 전체 실행 <span className="editor-run-shortcut">F5</span>
                  </button>
                  <button
                    type="button"
                    className="powershell-run-button sql selection"
                    title="F8 · 현재 선택한 SQL만 실행"
                    onClick={()=>runSqlEditor({selectionOnly:true})}
                    disabled={sqlQueryBusy}
                  >
                    ▣ 선택 실행 <span className="editor-run-shortcut">F8</span>
                  </button>
                  {sqlQueryBusy&&<button type="button" className="powershell-run-button execution-stop-button" onClick={stopSqlExecution}>■ 실행 정지</button>}
                </div>
              }
            </div>
          </div>

          {editorTextSearchOpen&&<div className="editor-text-search-panel">
            <div className="editor-text-search-head">
              <div className="editor-text-search-scope">
                <button type="button" className={editorTextSearchScope==='CURRENT'?'active':''} onClick={()=>{setEditorTextSearchScope('CURRENT');setEditorTextSearchResults([]);setEditorTextSearchMeta(null)}}>현재 파일</button>
                <button type="button" className={editorTextSearchScope==='PROJECT'?'active':''} onClick={()=>{setEditorTextSearchScope('PROJECT');setEditorTextSearchResults([]);setEditorTextSearchMeta(null)}}>프로젝트 전체</button>
              </div>
              <form onSubmit={e=>{e.preventDefault();runEditorTextSearch()}}>
                <input
                  ref={editorTextSearchInputRef}
                  value={editorTextSearchQuery}
                  onChange={e=>setEditorTextSearchQuery(e.target.value)}
                  placeholder={editorTextSearchScope==='CURRENT'?'현재 파일에서 찾을 텍스트':'프로젝트에서 찾을 텍스트'}
                />
                <button type="submit" disabled={editorTextSearchBusy||!editorTextSearchQuery.trim()}>{editorTextSearchBusy?'검색 중…':'찾기'}</button>
                <button type="button" className="close" onClick={()=>setEditorTextSearchOpen(false)} title="검색 닫기">×</button>
              </form>
            </div>
            {editorTextSearchError&&<div className="editor-text-search-error">{editorTextSearchError}</div>}
            {!editorTextSearchError&&editorTextSearchMeta&&<div className="editor-text-search-summary">
              <strong>{editorTextSearchResults.length}개 결과</strong>
              {editorTextSearchScope==='PROJECT'&&<span> · 파일 {Number(editorTextSearchMeta?.files_scanned||0)}개 검색</span>}
              {editorTextSearchMeta?.live_buffer&&<span> · 저장 전 편집 내용 포함</span>}
              {editorTextSearchMeta?.document_type==='pdf'&&<span> · PDF {Number(editorTextSearchMeta?.pdf_pages_scanned||0)}쪽 검색</span>}
              {editorTextSearchMeta?.document_type==='pdf'&&<span> · 텍스트 {Number(editorTextSearchMeta?.pdf_text_pages||0)}쪽 추출</span>}
              {editorTextSearchMeta?.document_type==='pdf'&&Number(editorTextSearchMeta?.pdf_duplicate_matches_removed||0)>0&&<span> · 중복 {Number(editorTextSearchMeta.pdf_duplicate_matches_removed)}개 정리</span>}
              {Number(editorTextSearchMeta?.skipped_large||0)>0&&<span> · 큰 파일 {Number(editorTextSearchMeta.skipped_large)}개 제외</span>}
              {Number(editorTextSearchMeta?.skipped_binary||0)>0&&<span> · 바이너리 {Number(editorTextSearchMeta.skipped_binary)}개 제외</span>}
              {editorTextSearchMeta?.truncated&&<span> · 결과 상한에 도달</span>}
            </div>}
            <div className="editor-text-search-results">
              {editorTextSearchResults.map((row,index)=><button
                type="button"
                className="editor-text-search-result"
                key={`${row.path}-${row.cell_index??''}-${row.line_number}-${row.column}-${index}`}
                onClick={()=>revealEditorTextSearchResult(row)}
              >
                <span className="path">{row.path}</span>
                <span className="location">{Number(row?.page_number||0)>0?`페이지 ${Number(row.page_number)}${Number(row?.page_match_index||0)>1?` · 페이지 내 결과 ${Number(row.page_match_index)}`:''}`:`${Number.isInteger(row.cell_index)?`셀 ${Number(row.cell_index)+1} · `:''}L${row.line_number}:C${row.column}`}</span>
                <code>{row.snippet||'(빈 줄)'}</code>
              </button>)}
              {editorTextSearchMeta&&!editorTextSearchBusy&&!editorTextSearchResults.length&&!editorTextSearchError&&<div className="editor-text-search-empty">검색 결과가 없습니다.</div>}
            </div>
          </div>}

          {editorFilesMenu&&
            <div
              className="editor-tab-context-menu editor-files-actions-menu"
              style={{
                left:editorFilesMenu.x,
                top:editorFilesMenu.y
              }}
              onMouseDown={e=>e.stopPropagation()}
            >
              <button
                type="button"
                onClick={closeAllEditorFiles}
                disabled={openEditorFiles.length===0}
              >
                열린 파일 모두 닫기
              </button>
              <button
                type="button"
                onClick={closeUnpinnedEditorFiles}
                disabled={!openEditorFiles.some(
                  path=>!pinnedEditorFiles.includes(path)
                )}
              >
                핀 고정되지 않은 파일 모두 닫기
              </button>
            </div>
          }


          {editorTabMenu&&
            <div
              className="editor-tab-context-menu"
              style={{
                left:editorTabMenu.x,
                top:editorTabMenu.y
              }}
              onMouseDown={e=>e.stopPropagation()}
            >
              <button
                type="button"
                onClick={()=>
                  toggleEditorFilePin(
                    editorTabMenu.path
                  )
                }
              >
                {pinnedEditorFiles.includes(editorTabMenu.path)
                  ? '핀 고정 해제'
                  : '핀 고정'}
              </button>
              <button
                type="button"
                onClick={()=>saveEditorFileAs(editorTabMenu.path)}
              >
                다른 이름으로 저장...
              </button>
              <button
                type="button"
                onClick={()=>
                  copyEditorFileFullPath(
                    editorTabMenu.path
                  )
                }
              >
                전체 경로 복사
              </button>
            </div>
          }

{fileLoading&&fileLoadingPath===selected
            ? <div className="editor-load-error-shell">
                <div className="editor-load-error-card">
                  <span className="editor-load-error-icon">…</span>
                  <div>
                    <strong>파일을 불러오는 중입니다.</strong>
                    <p>디스크의 실제 파일 내용을 읽은 뒤 편집기를 표시합니다.</p>
                    <code>{selected}</code>
                    <small>로드가 완료되기 전에는 편집/저장을 시작하지 않아 잘못된 기본 버퍼가 원본 파일에 사용되지 않습니다.</small>
                  </div>
                </div>
              </div>
            : editorLoadErrors[selected]
            ? <div className="editor-load-error-shell">
                <div className="editor-load-error-card">
                  <span className="editor-load-error-icon">!</span>
                  <div>
                    <strong>파일을 불러오지 못했습니다.</strong>
                    <p>{editorLoadErrors[selected]?.message||'파일 읽기 오류가 발생했습니다.'}</p>
                    <code>{selected}</code>
                    <small>오류 내용은 파일 본문에 넣지 않았으며 저장도 차단되어 원본 파일을 보호합니다.</small>
                    <button type="button" onClick={()=>openFile(selected,editorFileRootRef.current?.[selected]||fileTreeRootRef.current||'')}>↻ 다시 불러오기</button>
                  </div>
                </div>
              </div>
            : codeDiffReview
            ? <div className="code-diff-review-shell">
                <div className="code-diff-review-toolbar">
                  <div>
                    <strong>AI 변경 비교</strong>
                    <span>{codeDiffReview.path}</span>
                  </div>
                  <div className="code-diff-review-actions">
                    <button type="button" className="apply" onClick={applyCodeEditProposal}>변경 적용</button>
                    <button type="button" onClick={cancelCodeDiffReview}>취소</button>
                  </div>
                </div>
                <DiffEditor
                  className="main-monaco-editor code-diff-editor"
                  height="100%"
                  original={codeDiffReview.original}
                  modified={codeDiffReview.modified}
                  language={getEditorLanguage(codeDiffReview.path)}
                  theme="vs-dark"
                  options={{
                    readOnly:true,
                    originalEditable:false,
                    renderSideBySide:true,
                    automaticLayout:true,
                    minimap:{enabled:false},
                    fontSize:13,
                    scrollBeyondLastLine:false,
                    renderOverviewRuler:true
                  }}
                />
              </div>
            : isDatabaseDiagramFile(selected)
              ? <DatabaseDiagramViewer
                  value={code}
                  filePath={selected}
                />
            : isPdfFile(selected)
              ? <PdfViewer
                  filePath={selected}
                  projectRoot={resolveWorkspaceRoot(editorFileRootRef.current?.[selected]||fileTreeRootRef.current||'')}
                  revision={pdfPreviewRevision[normalizeProjectRelativePath(selected)]||0}
                  page={pdfSearchNavigation[normalizeProjectRelativePath(selected)]?.page||0}
                  searchQuery={pdfSearchNavigation[normalizeProjectRelativePath(selected)]?.query||''}
                  navigationToken={pdfSearchNavigation[normalizeProjectRelativePath(selected)]?.nonce||0}
                  matchSnippet={pdfSearchNavigation[normalizeProjectRelativePath(selected)]?.snippet||''}
                />
              : isPresentationFile(selected)
              ? <PresentationViewer
                  filePath={selected}
                  projectRoot={resolveWorkspaceRoot()}
                  revision={presentationPreviewRevision[normalizeProjectRelativePath(selected)]||0}
                />
              : isNotebookFile(selected)
              ? <NotebookEditor
                  value={code}
                  filePath={selected}
                  projectRoot={resolveWorkspaceRoot(editorFileRootRef.current?.[selected]||fileTreeRootRef.current||'')}
                  onChange={v=>updateActiveEditorCode(v)}
                  onExecutePython={executeNotebookPythonCode}
                  onStopPython={stopPythonExecution}
                  controllerRef={notebookEditorControllerRef}
                  onEditorFocus={()=>setFocusOwnerSafe('editor')}
                />
              : <Editor
            beforeMount={(monaco)=>{
              const ts=monaco.languages.typescript
              const sharedCompilerOptions={
                target:ts.ScriptTarget.ES2022 ?? ts.ScriptTarget.Latest,
                allowNonTsExtensions:true,
                allowJs:true,
                checkJs:false,
                moduleResolution:ts.ModuleResolutionKind.NodeJs ?? ts.ModuleResolutionKind.Node10,
                module:ts.ModuleKind.ESNext ?? ts.ModuleKind.CommonJS,
                jsx:ts.JsxEmit.ReactJSX ?? ts.JsxEmit.React,
                esModuleInterop:true,
                allowSyntheticDefaultImports:true
              }

              ts.typescriptDefaults.setEagerModelSync(true)
              ts.javascriptDefaults.setEagerModelSync(true)
              ts.typescriptDefaults.setCompilerOptions(sharedCompilerOptions)
              ts.javascriptDefaults.setCompilerOptions(sharedCompilerOptions)
              ts.typescriptDefaults.setDiagnosticsOptions({
                noSyntaxValidation:false,
                noSemanticValidation:true,
                noSuggestionDiagnostics:false
              })
              ts.javascriptDefaults.setDiagnosticsOptions({
                noSyntaxValidation:false,
                noSemanticValidation:true,
                noSuggestionDiagnostics:false
              })
            }}
            onMount={(editor,monaco)=>{
              editorInstanceRef.current=editor

              const model=editor.getModel()
              const expectedLanguage=getEditorLanguage(selected)
              if(model&&expectedLanguage){
                monaco.editor.setModelLanguage(model,expectedLanguage)
              }

              editor.onDidFocusEditorText(()=>{
                setFocusOwnerSafe('editor')
              })

              editor.onDidBlurEditorText(()=>{
                if(focusOwnerRef.current!=='terminal'){
                  focusOwnerRef.current='editor'
                }
              })

              // v5.382: Source/text editors use the same Visual Studio-style
              // bookmark gutter as Notebook cells. The explicit toolbar button
              // removes ambiguity, while glyph/line-number gutter clicks remain
              // available for fast mouse navigation.
              editor.onMouseDown?.((event)=>{
                const targetType=Number(event?.target?.type)
                if(![2,3,4].includes(targetType)) return
                const lineNumber=Number(event?.target?.position?.lineNumber)
                if(!Number.isInteger(lineNumber)||lineNumber<1) return
                toggleEditorLineBookmark(selectedEditorFileRef.current||selected||'',lineNumber,editor)
              })
              editor.onDidChangeModel?.(()=>{
                window.setTimeout(()=>applyEditorBookmarkDecorations(editor,selectedEditorFileRef.current||selected||''),0)
              })
              applyEditorBookmarkDecorations(editor,selectedEditorFileRef.current||selected||'')
            }}
            className="main-monaco-editor"
            height="100%"
            path={getEditorModelPath(root,selected)}
            language={getEditorLanguage(selected)}
            value={code}
            onChange={v=>updateActiveEditorCode(v)}
            theme="vs-dark"
            options={{
              minimap:{enabled:false},
              glyphMargin:true,
              lineNumbers:'on',
              lineNumbersMinChars:3,
              lineDecorationsWidth:14,
              fontSize:13,
              automaticLayout:true,
              tabSize:2,
              insertSpaces:true,
              detectIndentation:true,
              formatOnPaste:true,
              autoClosingBrackets:'never',
              autoClosingQuotes:'never',
              autoClosingDelete:'never',
              autoClosingOvertype:'never',
              autoSurround:'never',
              bracketPairColorization:{enabled:true},
              guides:{bracketPairs:true},
              suggestOnTriggerCharacters:true,
              quickSuggestions:{other:true,comments:false,strings:true}
            }}
          />}

          </div>
        </div>

        {workspaceTab==='RUN'&&(()=>{
          const r=getWorkflowReportState()
          const adaptiveProject=Boolean(r.projectProfile?.project_type)&&!r.packageResult?.created_files
          const testPassed=r.testReturncode===0
          const testKnown=r.testReturncode!==null&&r.testReturncode!==undefined

          return <div className="execution-dashboard">
            <div className="dashboard-hero execution">
              <div>
                <span className="dashboard-eyebrow">{adaptiveProject?'PROJECT EXECUTION STATUS':'AGENT FACTORY EXECUTION'}</span>
                <h2>실행 결과</h2>
                <p>{adaptiveProject?`${r.projectProfile?.project_type_label||'현재 프로젝트'}의 실행 준비 상태와 실제 테스트 결과를 확인합니다.`:'Agent 제작 Workflow의 실행·테스트·파일 변경·디버그 상태를 실시간으로 확인합니다.'}</p>
              </div>
              <div className="report-hero-actions">
                <button
                  type="button"
                  className="workspace-ppt-export-button"
                  onClick={()=>exportWorkspacePowerPoint('RUN','AGENT')}
                  disabled={!!pptExportBusy}
                >
                  {pptExportBusy==='AGENT:RUN'?'PPT 생성 중...':'▣ PPT 다운로드'}
                </button>
                <StatusBadge status={r.status}/>
              </div>
            </div>
            {pptExportError&&<div className="workspace-export-error">PPT 내보내기 오류: {pptExportError}</div>}

            {renderDevelopmentFinalStatus()}
            {renderFailureDiagnostics()}
            {renderDevelopmentProgress()}

            <div className="metric-grid execution-metrics">
              <MetricCard
                label="개발 상태"
                value={r.status}
                sub="현재 Workflow 상태"
                tone={String(r.status).includes('COMPLETED')?'success':'info'}
                icon="◆"
              />
              <MetricCard
                label="테스트"
                value={testKnown?(testPassed?'PASS':'FAIL'):'대기'}
                sub={`Exit Code ${testKnown?r.testReturncode:'-'}`}
                tone={testKnown?(testPassed?'success':'danger'):'default'}
                icon="▶"
              />
              <MetricCard
                label="생성 파일"
                value={`${r.createdFiles.length}개`}
                sub={`수정 ${r.modifiedFiles.length}개`}
                tone="info"
                icon="＋"
              />
              <MetricCard
                label="디버그"
                value={`${r.debugIteration}회`}
                sub={r.debugIteration?'자동 복구 수행':'재시도 없음'}
                tone={r.debugIteration?'warning':'default'}
                icon="↻"
              />
            </div>

            {renderLlmUsagePanel(false)}

            <div className="execution-main-grid">
              <ReportSection
                icon="▶"
                title="테스트 실행"
                subtitle="최종 실행 명령과 결과"
              >
                <KeyValueGrid items={[
                  {label:'명령',value:r.testCommand},
                  {label:'Exit Code',value:testKnown?r.testReturncode:'-'},
                  {label:'상태',value:testKnown?(testPassed?'성공':'실패'):'미실행'}
                ]}/>
                {r.testResult?.output&&
                  <pre className="execution-log">{r.testResult.output}</pre>}
              </ReportSection>

              <ReportSection
                icon="▤"
                title="파일 변경"
                subtitle={adaptiveProject?"현재 실행에서 생성/수정된 파일":"AgentStudio가 실제로 만든 파일"}
              >
                <FileChangeList
                  created={r.createdFiles}
                  modified={r.modifiedFiles}
                />
              </ReportSection>
            </div>

            <div className="execution-main-grid lower">
              <ReportSection
                icon="↻"
                title="디버그 / 복구"
                subtitle="테스트 실패 시 자동 수정 기록"
              >
                {r.debugHistory.length
                  ? <div className="debug-history-list">
                      {r.debugHistory.map((item,index)=>
                        <div className="debug-history-item" key={index}>
                          <span>{String(index+1).padStart(2,'0')}</span>
                          <pre>{typeof item==='string'?item:JSON.stringify(item,null,2)}</pre>
                        </div>
                      )}
                    </div>
                  : <div className="report-empty-mini">디버그 기록이 없습니다.</div>
                }
              </ReportSection>

              <ReportSection
                icon="⌘"
                title="터미널"
                subtitle="현재 프로젝트 터미널 출력"
              >
                <pre className="execution-terminal-preview">
                  {activeTerminal?.output||'터미널 출력이 아직 없습니다.'}
                </pre>
              </ReportSection>
            </div>
          </div>
        })()}

        {workspaceTab==='REPORT'&&(()=>{
          const r=getWorkflowReportState()
          const adaptiveProject=Boolean(r.projectProfile?.project_type)
          const style=codingStyleReport||{
            checked_files:0,
            pass:0,
            warning:0,
            fail:0,
            violations:[],
            ok:true
          }

          const goal=
            r.requirementSpec?.goal
            || workflowReq
            || '요구사항 정보 없음'

          const capabilities=
            r.capabilityPlan?.capabilities||[]

          const mcpDecisions=
            r.toolMcpPlan?.decisions||[]

          return <div className="analysis-report-dashboard">
            <div className="dashboard-hero report">
              <div>
                <span className="dashboard-eyebrow">{adaptiveProject?'PROJECT ADAPTIVE ANALYSIS':'AGENT DEVELOPMENT REPORT'}</span>
                <h2>분석 리포트</h2>
                <p>{adaptiveProject?`${r.projectProfile?.project_type_label||'현재 프로젝트'} 성격과 실제 감지 기술을 기준으로 Workflow·Architecture·Tool·Data 구성을 분석합니다.`:'요구사항부터 Architecture, MCP, Workflow, 코드 품질, 최종 완료 상태까지 한 번에 확인합니다.'}</p>
              </div>
              <div className="report-hero-actions">
                <button
                  type="button"
                  className="workspace-ppt-export-button"
                  onClick={()=>exportWorkspacePowerPoint('REPORT','AGENT')}
                  disabled={!!pptExportBusy}
                >
                  {pptExportBusy==='AGENT:REPORT'?'PPT 생성 중...':'▣ PPT 다운로드'}
                </button>
                <button
                  type="button"
                  onClick={()=>runProjectCodingStyleValidation(root||newAgentProjectRoot)}
                >
                  ↻ 코딩 스타일 재검증
                </button>
                <StatusBadge status={r.status}/>
              </div>
            </div>
            {pptExportError&&<div className="workspace-export-error">PPT 내보내기 오류: {pptExportError}</div>}

            <div className="metric-grid report-metrics">
              <MetricCard
                label="Workflow 단계"
                value={`${(r.targetWorkflow?.steps||[]).length}개`}
                sub={`분기 ${(r.targetWorkflow?.branches||[]).length}개`}
                icon="⇢"
                tone="info"
              />
              <MetricCard
                label="MCP / Tool"
                value={`${mcpDecisions.length}개`}
                sub="연결 판단 결과"
                icon="⚙"
              />
              <MetricCard
                label="코딩 스타일"
                value={style.fail===0?'PASS':'FAIL'}
                sub={`경고 ${style.warning} · 오류 ${style.fail}`}
                icon="✓"
                tone={style.fail===0?(style.warning?'warning':'success'):'danger'}
              />
              <MetricCard
                label="최종 상태"
                value={r.status}
                sub={reportGeneratedAt?`검증 ${new Date(reportGeneratedAt).toLocaleTimeString()}`:'아직 검증 전'}
                icon="★"
                tone={String(r.status).includes('COMPLETED')?'success':'info'}
              />
            </div>

            {renderFailureDiagnostics()}
            {renderLlmUsagePanel(true)}

            <div className="report-layout">
              <ReportSection
                icon="✦"
                title={adaptiveProject?"프로젝트 성격 / 목표":"요구사항"}
                subtitle={adaptiveProject?"소스 분석 기반 프로젝트 프로필":"인터뷰에서 확정된 Agent 목표"}
                className="span-2"
              >
                <div className="requirement-goal-box">{goal}</div>
                <KeyValueGrid items={[
                  {
                    label:'Acceptance Criteria',
                    value:`${(r.requirementSpec?.acceptance_criteria||[]).length}개`
                  },
                  {
                    label:'제약 조건',
                    value:`${(r.requirementSpec?.constraints||[]).length}개`
                  }
                ]}/>
              </ReportSection>

              <ReportSection
                icon="⬡"
                title={adaptiveProject?"Project Architecture":"Agent Architecture"}
                subtitle={adaptiveProject?"실제 감지 구성 요소와 인터페이스":"구성 요소와 인터페이스"}
              >
                <KeyValueGrid items={[
                  {label:'Components',value:`${(r.architecture?.components||[]).length}개`},
                  {label:'Interfaces',value:`${(r.architecture?.interfaces||[]).length}개`},
                  {label:'Persistence',value:`${(r.architecture?.persistence||[]).length}개`},
                  {label:'Security',value:`${(r.architecture?.security||[]).length}개`}
                ]}/>
              </ReportSection>

              <ReportSection
                icon="⇢"
                title="대상 Agent Workflow"
                subtitle="실제 업무 처리 순서"
                className="span-2"
              >
                <WorkflowMiniMap workflow={r.targetWorkflow}/>
              </ReportSection>

              <ReportSection
                icon="⚙"
                title="MCP / Tool"
                subtitle="Capability별 연결 방식"
              >
                {mcpDecisions.length
                  ? <div className="mcp-decision-list">
                      {mcpDecisions.map((item,index)=>
                        <div className="mcp-decision-row" key={index}>
                          <span>{item.execution_type||'none'}</span>
                          <div>
                            <strong>{item.capability||`Capability ${index+1}`}</strong>
                            <small>{item.reason||''}</small>
                          </div>
                        </div>
                      )}
                    </div>
                  : <div className="report-empty-mini">MCP / Tool 판단 정보가 없습니다.</div>
                }
              </ReportSection>

              <ReportSection
                icon="✣"
                title="Capabilities"
                subtitle="Agent가 가져야 할 기능"
              >
                {capabilities.length
                  ? <div className="capability-chip-list">
                      {capabilities.map((item,index)=>
                        <span key={index}>{typeof item==='string'?item:JSON.stringify(item)}</span>
                      )}
                    </div>
                  : <div className="report-empty-mini">Capability 정보가 없습니다.</div>
                }
              </ReportSection>

              <ReportSection
                icon="⚙"
                title="Settings Generator"
                subtitle="생성 대상 Agent의 설정 화면/API 생성 상태"
                className="span-2"
              >
                {r.settingsPlan?.enabled
                  ? <div className="settings-generator-report">
                      <div className="settings-generator-summary">
                        <div>
                          <span>설정 카테고리</span>
                          <strong>{(r.settingsPlan?.categories||[]).length}개</strong>
                        </div>
                        <div>
                          <span>Secret 보호</span>
                          <strong>{r.settingsPlan?.security?.never_return_secret_plaintext?'ON':'확인 필요'}</strong>
                        </div>
                        <div>
                          <span>생성 상태</span>
                          <strong>{r.settingsGeneration?.enabled===false?'불필요':'생성 대상'}</strong>
                        </div>
                        <div>
                          <span>검증</span>
                          <strong>{r.settingsValidation?.ok===true?'PASS':r.settingsValidation?.ok===false?'FAIL':'대기'}</strong>
                        </div>
                      </div>

                      <div className="settings-category-list">
                        {(r.settingsPlan?.categories||[]).map((category,index)=>
                          <div className="settings-category-card" key={category.id||index}>
                            <strong>{category.label||category.id||`설정 ${index+1}`}</strong>
                            <div>
                              {(category.fields||[]).map((field,fieldIndex)=>
                                <span key={field.key||fieldIndex}>
                                  {field.label||field.key}
                                  {field.secret&&<b>SECRET</b>}
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>

                      {r.settingsValidation?.checks?.length>0&&
                        <div className="settings-validation-list">
                          {r.settingsValidation.checks.map((item,index)=>
                            <div className={item.ok?'ok':'fail'} key={index}>
                              <span>{item.ok?'✓':'!'}</span>
                              <code>{item.path||item.type}</code>
                            </div>
                          )}
                        </div>
                      }
                    </div>
                  : <div className="report-empty-mini">
                      이 Agent에는 별도 Settings UI가 필요하지 않은 것으로 설계되었습니다.
                    </div>
                }
              </ReportSection>

              <ReportSection
                icon="▤"
                title="코드 생성 결과"
                subtitle="실제 생성 및 수정 파일"
                className="span-2"
              >
                <FileChangeList
                  created={r.createdFiles}
                  modified={r.modifiedFiles}
                />
              </ReportSection>

              <ReportSection
                icon="✓"
                title="Coding Style Validation"
                subtitle="등록한 코딩 규칙 적용 여부"
                className="span-2 coding-style-report"
              >
                <div className="style-score-grid">
                  <div className="style-score success">
                    <span>PASS</span>
                    <strong>{style.pass}</strong>
                  </div>
                  <div className="style-score warning">
                    <span>WARNING</span>
                    <strong>{style.warning}</strong>
                  </div>
                  <div className="style-score danger">
                    <span>FAIL</span>
                    <strong>{style.fail}</strong>
                  </div>
                  <div className="style-score info">
                    <span>FILES</span>
                    <strong>{style.checked_files}</strong>
                  </div>
                </div>

                {style.violations?.length
                  ? <div className="style-violation-list">
                      {style.violations.slice(0,80).map((item,index)=>
                        <div className={`style-violation-row ${String(item.severity||'warning').toLowerCase()}`} key={index}>
                          <span>{String(item.severity||'warning').toUpperCase()}</span>
                          <code>{item.path||'-'}</code>
                          <strong>{item.rule_id||''}</strong>
                          <p>{item.message||''}</p>
                        </div>
                      )}
                    </div>
                  : <div className="style-clean-result">
                      <span>✓</span>
                      <div>
                        <strong>코딩 스타일 위반이 없습니다.</strong>
                        <small>검사된 파일 기준으로 Error/Warning이 발견되지 않았습니다.</small>
                      </div>
                    </div>
                }
              </ReportSection>

              <ReportSection
                icon="★"
                title="최종 완료 상태"
                subtitle={adaptiveProject?"프로젝트 분석 / 실행 상태":"Agent Factory 완료 조건"}
                className="span-2 final-status-section"
              >
                <div className={`final-status-card ${String(r.status).includes('COMPLETED')?'completed':'pending'}`}>
                  <span>{String(r.status).includes('COMPLETED')?'★':'…'}</span>
                  <div>
                    <strong>{r.status}</strong>
                    <small>
                      {String(r.status).includes('COMPLETED')
                        ? '코드 생성 · 테스트 · 패키지 · 최종 검토가 완료되었습니다.'
                        : (adaptiveProject&&r.status==='PROJECT_LOADED'
                          ? '프로젝트 소스 분석이 완료되었으며 실제 실행/테스트 전 상태입니다.'
                          : 'Agent Factory Workflow가 아직 최종 완료 상태가 아닙니다.')}
                    </small>
                  </div>
                </div>
              </ReportSection>
            </div>
          </div>
        })()}

        {workspaceTab==='ARCHITECTURE'&&(()=>{
          const r=getWorkflowReportState()
          const adaptiveProject=Boolean(r.architecture?.source==='PROJECT_SOURCE_INFERENCE')
          const designArchitectureReady=Boolean(
            (r.architecture?.components||[]).length
            ||(r.architecture?.interfaces||[]).length
            ||(r.architecture?.persistence||[]).length
            ||(r.architecture?.state||[]).length
            ||(r.architecture?.security||[]).length
          )
          const asBuiltArchitectureReady=Boolean(
            (r.asBuiltArchitecture?.components||[]).length
            ||Number(r.asBuiltArchitecture?.scan?.source_file_count||0)>0
          )
          const conformanceReady=Boolean(
            r.architectureConformance
            &&(r.architectureConformance.status||r.architectureConformance.checked_at||r.architectureConformance.mismatches?.length||r.architectureConformance.ok===true)
          )
          return <div className="analysis-report-dashboard architecture-dashboard">
            <div className="dashboard-hero report architecture-hero">
              <div>
                <span className="dashboard-eyebrow">ARCHITECTURE VISUALIZATION</span>
                <h2>아키텍처</h2>
                <p>{adaptiveProject?`${r.projectProfile?.project_type_label||'현재 프로젝트'}에서 실제 감지한 구성 요소·인터페이스·DB·인프라를 기준으로 아키텍처를 구성합니다.`:'설계 아키텍처와 실제 생성 코드를 역분석한 As-Built 구조를 비교하고 일치 여부를 검증합니다.'}</p>
              </div>
              <div className="report-hero-actions">
                <button
                  type="button"
                  className="workspace-ppt-export-button"
                  onClick={()=>exportWorkspacePowerPoint('ARCHITECTURE','AGENT')}
                  disabled={!!pptExportBusy}
                >
                  {pptExportBusy==='AGENT:ARCHITECTURE'?'PPT 생성 중...':'▣ PPT 다운로드'}
                </button>
                <button type="button" onClick={()=>setWorkspaceTab('REPORT')}>↔ 분석 리포트 보기</button>
                <StatusBadge status={r.status} />
              </div>
            </div>
            {pptExportError&&<div className="workspace-export-error">PPT 내보내기 오류: {pptExportError}</div>}

            <div className="metric-grid report-metrics">
              <MetricCard label="구성 요소" value={designArchitectureReady?`${(r.architecture?.components||[]).length}개`:'-'} sub={designArchitectureReady?(adaptiveProject?'Project Adaptive':'Design Architecture'):'설계 전'} icon="⬢" tone="info" />
              <MetricCard label="인터페이스" value={designArchitectureReady?`${(r.architecture?.interfaces||[]).length}개`:'-'} sub={designArchitectureReady?'연결 지점':'설계 전'} icon="⇄" tone="default" />
              <MetricCard label="영속성" value={designArchitectureReady?`${(r.architecture?.persistence||[]).length}개`:'-'} sub={designArchitectureReady?'DB / 상태 저장':'설계 전'} icon="💾" tone="warning" />
              <MetricCard
                label={adaptiveProject?'프로젝트 유형':'Conformance'}
                value={adaptiveProject?(r.projectProfile?.project_type_label||'Project'):(conformanceReady?`${Number(r.architectureConformance?.score||0).toFixed(0)}점`:'-')}
                sub={adaptiveProject?'소스 기반 자동 분류':(conformanceReady?(r.architectureConformance?.ok?'PASS':'검증 필요'):'코드 생성 후 검증')}
                icon={adaptiveProject?'◇':'✓'}
                tone={adaptiveProject?'info':(conformanceReady&&r.architectureConformance?.ok?'success':'warning')}
              />
            </div>

            {designArchitectureReady
              ? <GeneratedAgentArchitecturePanel report={r} />
              : <div className="architecture-lifecycle-empty">
                  <span>◇</span>
                  <div>
                    <small>DESIGN ARCHITECTURE · NOT STARTED</small>
                    <strong>아키텍처가 아직 생성되지 않았습니다.</strong>
                    <p>요구사항 수집 후 <b>설계 검토</b>를 실행하면 목표 Architecture · Workflow · DB 설계를 함께 생성합니다. 내부 Requirement State/대화 JSON은 이 영역에 표시하지 않습니다.</p>
                  </div>
                  <button type="button" disabled={!canDesignFromCollectedInfo()||targetWorkflowLoading} onClick={()=>{setWorkspaceTab('WORKFLOW');setWorkflowView('TARGET');previewTargetWorkflow()}}>◇ 설계 검토</button>
                </div>
            }

            {!adaptiveProject&&(asBuiltArchitectureReady
              ? <AsBuiltAgentArchitecturePanel report={r} />
              : <div className="architecture-lifecycle-empty secondary">
                  <span>⌁</span>
                  <div>
                    <small>AS-BUILT ARCHITECTURE · PENDING</small>
                    <strong>실제 생성 코드 분석 대기 중</strong>
                    <p>프로젝트 코드 생성 후 실제 파일·클래스·함수·Framework 증거를 정적 분석하여 As-Built Architecture를 만듭니다.</p>
                  </div>
                </div>
            )}

            {!adaptiveProject&&(conformanceReady
              ? <ArchitectureConformancePanel report={r} />
              : <div className="architecture-lifecycle-empty secondary">
                  <span>✓</span>
                  <div>
                    <small>ARCHITECTURE CONFORMANCE · PENDING</small>
                    <strong>Design ↔ As-Built 비교 대기 중</strong>
                    <p>As-Built 분석 후 설계와 실제 구현을 비교하고 85점 기준 및 Critical 누락 여부를 검증합니다.</p>
                  </div>
                </div>
            )}
          </div>
        })()}

        {workspaceTab==='DB_ERD'&&(()=>{
          const summary=dbErdReport?.summary||{}
          const r=getWorkflowReportState()
          return <div className="analysis-report-dashboard db-erd-dashboard">
            <div className="dashboard-hero report db-erd-hero">
              <div>
                <span className="dashboard-eyebrow">DATABASE MODEL VISUALIZATION</span>
                <h2>DB ERD</h2>
                <p>현재 Agent 또는 로드된 프로젝트에서 사용하는 PostgreSQL·SQL DB·pgvector·Redis·Document DB를 DB별로 분리하여 ERD / Data Model로 표시합니다.</p>
              </div>
              <div className="report-hero-actions">
                <button
                  type="button"
                  className="workspace-ppt-export-button"
                  onClick={()=>exportWorkspacePowerPoint('DB_ERD','AGENT')}
                  disabled={!!pptExportBusy}
                >
                  {pptExportBusy==='AGENT:DB_ERD'?'PPT 생성 중...':'▣ PPT 다운로드'}
                </button>
                <button type="button" onClick={()=>setWorkspaceTab('ARCHITECTURE')}>↔ 아키텍처 보기</button>
                <StatusBadge status={r.status} />
              </div>
            </div>
            {pptExportError&&<div className="workspace-export-error">PPT 내보내기 오류: {pptExportError}</div>}
            <div className="metric-grid report-metrics">
              <MetricCard label="DB / Store" value={`${Number(summary.database_count||0)}개`} sub="DB별 개별 모델" icon="▣" tone="info" />
              <MetricCard label="Tables" value={`${Number(summary.table_count||0)}개`} sub="관계형 + Vector" icon="▤" tone="default" />
              <MetricCard label="Relations" value={`${Number(summary.relationship_count||0)}개`} sub="FK / Reference" icon="⇄" tone="warning" />
              <MetricCard label="Redis / Collections" value={`${Number(summary.redis_key_count||0)} / ${Number(summary.collection_count||0)}`} sub="Key Pattern / Collection" icon="◇" tone="success" />
            </div>
            <DatabaseErdPanel
              report={dbErdReport}
              loading={dbErdBusy}
              error={dbErdError}
              onRefresh={refreshDbErd}
            />
          </div>
        })()}

        {workspaceTab==='LLM'&&<LlmCatalogPanel
          catalog={llmCatalog}
          history={llmHistory}
          loading={llmCatalogLoading}
          error={llmCatalogError}
          onRefresh={refreshLlmCatalog}
        />}

        {workspaceTab==='BROWSER'&&<WebBrowserWorkspace
          tabs={webBrowserTabs}
          activeTabId={activeWebBrowserTab?.id||DEFAULT_WEB_BROWSER_ID}
          detectionEnabled={webUrlDetectionEnabled}
          onDetectionEnabledChange={setWebUrlDetectionEnabled}
          onActivateTab={activateWebBrowser}
          onCloseTab={closeWebBrowserTab}
          onNavigate={navigateWebBrowser}
          onBack={tabId=>stepWebBrowserHistory(tabId,-1)}
          onForward={tabId=>stepWebBrowserHistory(tabId,1)}
          onReload={reloadWebBrowser}
          onHome={homeWebBrowser}
          onOpenNewTab={url=>openWebBrowserTab(url||'',{preferFixed:false})}
          onOpenExternal={openWebBrowserExternal}
          onRemoteState={syncRemoteWebBrowserState}
          onRemotePopup={openRemoteWebBrowserPopup}
        />}
      </div>

      {detectedWebService&&<div className="web-service-detection-toast" role="status" aria-live="polite">
        <div className="web-service-detection-copy">
          <span className="web-service-detection-icon">🌐</span>
          <div>
            <strong>웹 서비스 URL 감지</strong>
            <code>{detectedWebService.url}</code>
            <small>자동으로 열지 않습니다. 표시 방법을 선택하세요.</small>
          </div>
        </div>
        <div className="web-service-detection-actions">
          <button type="button" onClick={()=>{openWebBrowserTab(detectedWebService.url,{preferFixed:true,detected:true});setDetectedWebService(null)}}>기본 웹브라우저에서 열기</button>
          <button type="button" className="primary" onClick={()=>{openWebBrowserTab(detectedWebService.url,{detected:true});setDetectedWebService(null)}}>추가 웹브라우저 탭</button>
          <button type="button" onClick={()=>setDetectedWebService(null)}>무시</button>
        </div>
      </div>}

      {workspaceTab==='CODE'&&!isBinaryPreviewFile(selected)&&<div className={`workspace-bottom-control-rail ${workspaceBottomCollapsed?'collapsed':''}`}>
        {!workspaceBottomCollapsed&&<div
          className="workspace-bottom-resizer workspace-bottom-resizer-inline"
          role="separator"
          aria-orientation="horizontal"
          aria-label="하단 영역 높이 조절"
          title="위아래로 드래그하여 LLM 대화형 코드 편집/터미널 영역 높이 조절"
          onPointerDown={beginWorkspaceBottomResize}
        ><span /></div>}
        <button
          type="button"
          className={`workspace-panel-toggle workspace-panel-toggle-bottom workspace-panel-toggle-bottom-rail ${workspaceBottomCollapsed?'collapsed':''}`}
          onClick={()=>setWorkspaceBottomCollapsed(v=>!v)}
          title={workspaceBottomCollapsed?'하단 LLM/터미널 영역 열기':'하단 LLM/터미널 영역 닫기'}
          aria-label={workspaceBottomCollapsed?'하단 영역 열기':'하단 영역 닫기'}
          aria-pressed={!workspaceBottomCollapsed}
        >
          <span aria-hidden="true">{workspaceBottomCollapsed?'▲':'▼'}</span>
        </button>
      </div>}

      <div className={
        workspaceTab==='CODE'&&!isBinaryPreviewFile(selected)&&!workspaceBottomCollapsed
          ? `workspace-bottom-grid fixed-bottom-tools persistent-code-tools visible ${isSqlFile?'sql-workspace-bottom':''}`
          : 'workspace-bottom-grid fixed-bottom-tools persistent-code-tools hidden'
      }>
        {isSqlFile&&<SqlResultsPane
          result={sqlQueryResult}
          resultTab={sqlResultTab}
          onResultTabChange={setSqlResultTab}
          messages={sqlMessages}
          queryBusy={sqlQueryBusy}
          activeResultSetIndex={sqlResultSetIndex}
          onActiveResultSetIndexChange={setSqlResultSetIndex}
        />}
        <section className={`editor-pane ux-editor-pane llm-code-chat-panel ${isSqlFile?'sql-chat-pane':''}`}>
          <div className="pane-title ux-pane-title">
            <strong>LLM 대화형 코드 편집</strong>
            <div>
              <span>{selected ? selected.split(/[\\/]/).pop() : '파일 선택 필요'}</span>

              {selected&&editorFileDirty[selected]&&
                <span className="file-save-status dirty" title="저장되지 않은 변경">●</span>
              }

              {fileSaveStatus==='저장 중'&&
                <span className="file-save-status saving">저장 중...</span>
              }

              {fileSaveStatus==='저장 완료'&&!editorFileDirty[selected]&&
                <span className="file-save-status saved">저장 완료</span>
              }

              {fileSaveStatus==='저장 실패'&&
                <span className="file-save-status failed">저장 실패</span>
              }

              <button onClick={saveFile} disabled={!selected||isBinaryPreviewFile(selected)}>상단 코드 저장</button>
            </div>
          </div>

          <div className="code-llm-side chat-only">
            <div className="code-llm-head">
              <div>
                <MiniBadge>AI</MiniBadge>
                <strong>
                  {codeEditScope==='PROJECT'
                    ? '프로젝트 전체 코딩'
                    : '선택된 파일과 대화하며 코드 수정'}
                </strong>
              </div>
              <small>
                {codeEditScope==='PROJECT'
                  ? `현재 대상 프로젝트: ${currentProjectName}`
                  : selected
                    ? `현재 대상 파일: ${selected}`
                    : '파일 단위 작업은 먼저 파일을 선택하세요.'}
              </small>
            </div>

            <div className="code-llm-chat" ref={codeEditChatRef}>
              {codeEditChat.map((m,i)=><div
                key={i}
                className={`code-edit-message ${m.role}`}
              >
                <span>{m.role==='assistant'?'AI':'나'}</span>
                <div>{m.content}</div>
              </div>)}

              {codeEditBusy&&<div className="code-edit-message assistant">
                <span>AI</span>
                <div>
                  {codeEditScope==='PROJECT'
                    ? '프로젝트 구조를 분석하고 필요한 파일 생성/수정을 진행하고 있습니다...'
                    : '현재 상단 편집기의 코드를 기준으로 수정안을 생성하고 있습니다...'}
                </div>
              </div>}

              {codeEditProposal&&<div className="code-edit-proposal proposal-ready-note">
                <div className="proposal-head">
                  <strong>AI 변경 제안 준비됨</strong>
                  <span>{codeEditProposal.path?.split(/[\\/]/).pop()||''}</span>
                </div>
                <p>우측 `AI 변경 제안` 탭에서 코드를 확인하고 Apply로 Diff 비교를 시작하세요.</p>
                <div className="proposal-actions">
                  <button className="apply" onClick={()=>{setCodeRightPanelTab('PROPOSAL');setWorkspaceRightCollapsed(false)}}>
                    우측 제안 보기
                  </button>
                </div>
              </div>}
            </div>

            <AiAttachmentPicker
              attachments={codeEditAttachments}
              onChange={setCodeEditAttachments}
              projectRoot={root||''}
              initialPath={root||''}
              disabled={codeEditBusy}
              compact
              label="참고 파일 선택"
              title="LLM 대화형 코드 편집에 함께 분석할 참고 파일을 선택하세요."
              maxFiles={12}
              analysisPurpose="LLM 대화형 코드 편집 참고 파일 분석 준비"
              analysisActive={codeEditBusy}
              onAnalysisStateChange={setCodeEditAttachmentAnalysis}
            />

            <div className="code-llm-input">
              <select
                className="code-edit-scope-select"
                value={codeEditScope}
                onChange={e=>setCodeEditScope(e.target.value)}
                disabled={codeEditBusy}
                title="코드 작업 범위"
              >
                <option value="FILE">파일 단위</option>
                <option value="PROJECT">프로젝트 단위</option>
              </select>

              <textarea
                value={codeEditPrompt}
                onFocus={()=>setFocusOwnerSafe('code-chat')}
                onPointerDown={()=>setFocusOwnerSafe('code-chat')}
                onChange={e=>setCodeEditPrompt(e.target.value)}
                placeholder={
                  codeEditScope==='PROJECT'
                    ? '예: 유튜브 등록 에이전트를 만들어줘. 필요한 신규 파일도 생성해줘.'
                    : selected
                      ? '예: print hello 를 찍어줘.'
                      : '파일 단위 작업은 먼저 수정할 파일을 선택하세요.'
                }
                disabled={
                  codeEditBusy
                  || (codeEditAttachments.length&&!codeEditAttachmentAnalysis.ready)
                  || !root
                  || (codeEditScope==='FILE'&&!selected)
                }
                onKeyDown={e=>{
                  if(e.key!=='Enter') return

                  // 한글 IME 조합 중 Enter는 전송하거나 줄바꿈 처리하지 않습니다.
                  if(e.nativeEvent?.isComposing) return

                  // 파일 단위 / 프로젝트 단위 모두 Shift+Enter 또는 Alt+Enter로
                  // 현재 커서 위치에 한 줄을 추가합니다. 브라우저/OS별 Alt+Enter
                  // 기본 동작 차이를 없애기 위해 직접 개행을 삽입합니다.
                  if(e.shiftKey||e.altKey){
                    e.preventDefault()
                    e.stopPropagation()
                    const target=e.currentTarget
                    const start=Number(target.selectionStart??codeEditPrompt.length)
                    const end=Number(target.selectionEnd??start)
                    const next=`${codeEditPrompt.slice(0,start)}\n${codeEditPrompt.slice(end)}`
                    const caret=start+1
                    setCodeEditPrompt(next)
                    requestAnimationFrame(()=>{
                      try{
                        target.focus()
                        target.setSelectionRange(caret,caret)
                      }catch(_){}
                    })
                    return
                  }

                  e.preventDefault()
                  e.stopPropagation()
                  askCodeEditorLLM()
                }}
                title="Enter: 실행 · Shift+Enter / Alt+Enter: 줄바꿈"
              />

              <button
                onClick={askCodeEditorLLM}
                disabled={
                  codeEditBusy
                  || !root
                  || (codeEditScope==='FILE'&&!selected)
                  || !codeEditPrompt.trim()
                }
              >
                {codeEditScope==='PROJECT'
                  ? '프로젝트 코딩'
                  : '파일 수정'}
              </button>
            </div>
          </div>
        </section>

        <TerminalPanel
          hiddenForSql={isSqlFile}
          sessions={terminalSessions}
          activeTerminalId={activeTerminalId}
          activeTerminal={activeTerminal}
          errors={terminalErrors}
          terminalNameEditId={terminalNameEditId}
          terminalNameDraft={terminalNameDraft}
          activeTerminalProjectId={activeTerminalProjectId}
          projectTerminalSessions={projectTerminalSessions}
          completion={terminalCompletion}
          completionRef={terminalCompletionRef}
          onDismissError={sessionId=>setTerminalErrors(prev=>({...prev,[sessionId]:null}))}
          onNameDraftChange={setTerminalNameDraft}
          onSaveName={saveTerminalName}
          onCancelRename={()=>{ setTerminalNameEditId(null); setTerminalNameDraft('') }}
          onSelectTerminal={terminal=>{
            setFocusOwnerSafe('terminal')
            setActiveTerminalId(terminal.id)
            setTimeout(()=>focusXterm(terminal.id,{force:true}),0)
          }}
          onStartRename={startRenameTerminal}
          onRemoveTerminal={removeTerminal}
          onRestartTerminal={restartTerminalSession}
          onInterruptTerminal={interruptTerminal}
          onClearTerminal={clearTerminalView}
          onAddTerminal={addTerminal}
          onBindTerminalContainer={(terminal,el)=>{
            if(!el) return
            xtermContainersRef.current[terminal.id]=el
            setTimeout(async()=>{
              await ensureXtermInstance(terminal.id)
              if(
                activeTerminalId===terminal.id
                && terminal.processState!=='exited'
                && canAutoFocusTerminal()
              ){
                focusXterm(terminal.id)
              }
            },0)
          }}
          onTerminalMouseDown={terminal=>{
            if(terminal.processState==='exited') return
            setFocusOwnerSafe('terminal')
          }}
          onTerminalClick={terminal=>{
            if(terminal.processState==='exited') return
            setFocusOwnerSafe('terminal')
            focusXterm(terminal.id,{force:true})
          }}
          onCompletionHover={index=>{
            const current=terminalCompletionRef.current
            if(current?.sessionId===activeTerminalId){
              setTerminalCompletionState({...current,selectedIndex:index})
            }
          }}
          onApplyCompletion={applyTerminalCompletion}
        />
      </div>
    </main>

    {!workspaceRightCollapsed&&<div
      className={`workspace-panel-resizer workspace-panel-resizer-right ${workspaceResizeSide==='right'?'active':''}`}
      role="separator"
      aria-orientation="vertical"
      aria-label="우측 영역 너비 조절"
      title="드래그하여 우측 영역 너비 조절"
      onPointerDown={event=>beginWorkspacePanelResize('right',event)}
    />}

    <aside
      className={`workspace-info-panel ${workspaceTab==='DESIGN'?'design-info-panel':''}`}
      aria-hidden={workspaceRightCollapsed}
    >
      {workspaceTab==='DESIGN'&&<>
        <div className="info-card unified-project-config">
          <div className="summary-head">
            <div>
              <strong>프로젝트 구성</strong>
              <small>생성 전에 언제든 수정할 수 있습니다.</small>
            </div>
          </div>

          <div className="unified-feature-manager-shell">
            <AgentFeatureManager
              detectedFeatures={getDetectedAgentFeatureNames()}
              features={designFeatureRegistry}
              onChange={handleDesignFeatureChange}
            />
          </div>

          <div className={`ui-layout-choice-card ${uiLayoutConfig?.template_id?'selected':''}`}>
            <div className="ui-layout-choice-head">
              <div><strong>UI / Layout</strong><small>좌측 메뉴·상단 메뉴·Footer·사용자 메뉴·웹/웹앱 구조를 시각적으로 선택합니다.</small></div>
              <span>{uiLayoutConfig?.template_id?'선택됨':'선택 전'}</span>
            </div>
            {uiLayoutConfig?.template_id
              ? <><UILayoutWireframe config={uiLayoutConfig} compact={true}/><b>{uiLayoutSummary(uiLayoutConfig)}</b></>
              : <div className="ui-layout-choice-empty">Agent 성격에 맞는 레이아웃 템플릿을 선택하세요.</div>}
            <button type="button" onClick={()=>setUiLayoutGalleryOpen(true)}>{uiLayoutConfig?.template_id?'레이아웃 변경':'레이아웃 템플릿 선택'}</button>
          </div>

          <label className="ux-field">
            <span>에이전트 이름</span>
            <input
              value={newAgentName}
              onChange={e=>setNewAgentName(e.target.value)}
              placeholder="예: YouTube MCP Agent"
            />
          </label>

          <label className="ux-field required">
            <span>프로젝트 경로</span>
            <div className="path-input-row">
              <input
                value={newAgentProjectRoot}
                onChange={e=>setNewAgentProjectRoot(e.target.value)}
                placeholder="예: F:\\Source\\repos\\Theanova\\AI\\MyAgent"
              />
              <button
                type="button"
                className="path-find-button"
                onClick={()=>
                  chooseAgentFolder(
                    setNewAgentProjectRoot,
                    newAgentProjectRoot,
                    '프로젝트 경로'
                  )
                }
              >
                경로 찾기
              </button>
            </div>
          </label>

          <button
            className="path-toggle"
            onClick={()=>setShowPathSettings(v=>!v)}
          >
            <span>고급 경로 설정</span>
            <b>{showPathSettings?'−':'＋'}</b>
          </button>

          {showPathSettings&&<div className="path-settings">
            {[
              ['Cache',newAgentCachePath,setNewAgentCachePath,'Cache 경로'],
              ['Temp',newAgentTempPath,setNewAgentTempPath,'Temp 경로'],
              ['Output',newAgentOutputPath,setNewAgentOutputPath,'Output 경로'],
              ['가상환경',newAgentVenvPath,setNewAgentVenvPath,'가상환경 경로'],
              ['공통 모델',newAgentModelsPath,setNewAgentModelsPath,'공용 모델 경로']
            ].map(([label,value,setter,title])=>
              <label className="ux-field" key={label}>
                <span>{label}</span>
                <div className="path-input-row">
                  <input
                    value={value}
                    onChange={e=>setter(e.target.value)}
                    placeholder="비우면 기본 경로 사용"
                  />
                  <button
                    type="button"
                    className="path-find-button"
                    onClick={()=>chooseAgentFolder(setter,value,title)}
                  >
                    경로 찾기
                  </button>
                </div>
              </label>
            )}
          </div>}

          <div className="path-preview compact">
            <strong>생성될 경로</strong>
            <div><span>Cache</span><code>{pathPreview(newAgentCachePath,'cache')}</code></div>
            <div><span>Temp</span><code>{pathPreview(newAgentTempPath,'temp')}</code></div>
            <div><span>Output</span><code>{pathPreview(newAgentOutputPath,'output')}</code></div>
            <div><span>Venv</span><code>{pathPreview(newAgentVenvPath,'venv')}</code></div>
            <div><span>Models</span><code>{pathPreview(newAgentModelsPath,'models')}</code></div>
          </div>
        </div>

        <div className="info-card right-agent-build-card">
          <SectionTitle title="Agent 제작 진행"/>
          <AgentBuildActionBar
            stage={agentBuildStage}
            busy={agentBuildBusy||projectCreateFlowBusy||targetWorkflowLoading}
            message={agentBuildMessage}
            workflowEnabled={canDesignFromCollectedInfo()}
            onWorkflow={()=>{
              setWorkspaceTab('WORKFLOW')
              setWorkflowView('TARGET')
              previewTargetWorkflow()
            }}
            onCreateProject={createAgentProjectSmart}
            onStartDevelopment={startAgentDevelopment}
            onRedevelop={()=>startAgentDevelopment({redevelopment:true})}
            redevelopmentEnabled={Boolean(redevelopmentInfo?.available)}
            redevelopmentInfo={redevelopmentInfo}
            onStop={cancelAgentDevelopment}
            compact
          />
          {renderDevelopmentFinalStatus()}
          {renderDevelopmentProgress()}
        </div>

        <div className="info-card live-database-preview-card">
          <div className="live-db-preview-head">
            <div>
              <strong>DB 실시간 설계 · 초안</strong>
              <small>대화에서 확정되는 요구사항만으로 Module Registry를 즉시 갱신합니다.</small>
            </div>
            <span className={`live-db-preview-status ${liveDatabasePreview?.enabled?'active':''}`}>
              {liveDatabasePreviewLoading?'갱신 중':liveDatabasePreview?.enabled?'초안':'대기'}
            </span>
          </div>

          {liveDatabasePreviewError&&<div className="live-db-preview-error">{liveDatabasePreviewError}</div>}

          {!liveDatabasePreview&& !liveDatabasePreviewLoading&&
            <div className="live-db-preview-empty">DB 관련 요구사항을 말하면 Module · Entity · 관계 초안이 여기에 표시됩니다.</div>
          }

          {liveDatabasePreview&&<>
            <div className="live-db-preview-summary">
              <div><small>Module</small><strong>{(liveDatabasePreview.modules||[]).length}</strong></div>
              <div><small>Entity</small><strong>{(liveDatabasePreview.tables||[]).length}</strong></div>
              <div><small>관계</small><strong>{(liveDatabasePreview.relationships||[]).length}</strong></div>
              <div><small>검증</small><strong>{liveDatabasePreview.validation?.valid===false?'FAIL':'PASS'}</strong></div>
            </div>

            <div className="live-db-preview-tabs">
              {[['MODULES','Module'],['ENTITIES','Entity'],['RELATIONS','관계'],['DDL','DDL']].map(([id,label])=>
                <button
                  type="button"
                  key={id}
                  className={liveDatabasePreviewTab===id?'active':''}
                  onClick={()=>setLiveDatabasePreviewTab(id)}
                >{label}</button>
              )}
            </div>

            <div className="live-db-preview-body">
              {liveDatabasePreviewTab==='MODULES'&&<div className="live-db-module-list">
                {(liveDatabasePreview.technologies||[]).length>0&&<div className="live-db-technology-row">
                  <strong>사용 기술</strong>
                  <div>{(liveDatabasePreview.technologies||[]).map(item=><span key={item}>{item}</span>)}</div>
                </div>}
                {(liveDatabasePreview.modules||[]).map(module=><div key={module.id}>
                  <strong>{module.label||module.id}</strong>
                  <small>{module.reason||''}</small>
                </div>)}
                {liveDatabasePreview.redis_plan?.enabled&&<div className="live-db-redis-module">
                  <strong>Redis Cache / Session</strong>
                  <small>{liveDatabasePreview.redis_plan.policy}</small>
                  <div className="live-db-redis-keys">
                    {(liveDatabasePreview.redis_plan.keys||[]).map(item=><div key={item.key}>
                      <code>{item.key}</code><span>{item.purpose}</span><em>{item.ttl}</em>
                    </div>)}
                  </div>
                </div>}
                {!(liveDatabasePreview.modules||[]).length&&!liveDatabasePreview.redis_plan?.enabled&&<small>현재 DB Module이 선택되지 않았습니다.</small>}
              </div>}

              {liveDatabasePreviewTab==='ENTITIES'&&<div className="live-db-entity-list">
                {(liveDatabasePreview.tables||[]).map(table=><details key={table.name}>
                  <summary><strong>{table.name}</strong><span>{table.module||'CUSTOM'}</span><em>{(table.columns||[]).length} columns</em></summary>
                  <small>{table.purpose||''}</small>
                  <div className="live-db-column-list">
                    {(table.columns||[]).map(column=><div key={`${table.name}-${column.name}`}>
                      <code>{column.name}</code>
                      <span>{column.type}</span>
                      {column.primary_key&&<b>PK</b>}
                      {column.references&&<b>FK → {column.references}</b>}
                    </div>)}
                  </div>
                </details>)}
                {!(liveDatabasePreview.tables||[]).length&&<small>아직 예상 Entity가 없습니다.</small>}
              </div>}

              {liveDatabasePreviewTab==='RELATIONS'&&<div className="live-db-relation-list">
                {(liveDatabasePreview.relationships||[]).map((relation,index)=><div key={`${relation.from}-${relation.to}-${index}`}>
                  <code>{relation.from}</code><span>→</span><code>{relation.to}</code><small>{relation.type||''}</small>
                </div>)}
                {!(liveDatabasePreview.relationships||[]).length&&<small>아직 예상 FK 관계가 없습니다.</small>}
              </div>}

              {liveDatabasePreviewTab==='DDL'&&<div className="live-db-ddl-preview">
                <small>이 내용은 실시간 초안이며 DB 설계 확정 전에는 Migration 파일로 저장되지 않습니다.</small>
                <pre>{liveDatabasePreview.ddl_preview||'-- DB 요구사항이 확정되면 PostgreSQL DDL Preview가 표시됩니다.'}</pre>
              </div>}
            </div>

            <div className="live-db-preview-foot">
              <span>실시간 초안</span>
              <small>최종 Entity/PK/FK는 설계 검토 단계에서 Codex → OpenAI → Ollama 및 Validator를 거쳐 확정합니다.</small>
            </div>
          </>}
        </div>

        <div className="info-card requirement-collection-wrapper">
          <div className="requirement-collection-card active-design">
            <div className="requirement-collection-head">
              <div>
                <strong>요구사항 수집 현황</strong>
                <small>이미 확인된 내용은 다시 묻지 않고 Workflow 설계에 재사용합니다.</small>
              </div>
              <span>
                {getRequirementKeywordStatus().filter(x=>x.collected).length}
                /{getRequirementKeywordStatus().length}
              </span>
            </div>

            <div className="requirement-value-list">
              {getRequirementKeywordStatus().map(item=>
                <div
                  key={item.id}
                  className={`requirement-value-row ${item.collected?'collected':'pending'}`}
                  title={
                    item.collected
                      ? `${item.label}: ${item.value||'수집 완료'}`
                      : `${item.label}: 아직 미수집`
                  }
                >
                  <i>{item.collected?'✓':'○'}</i>
                  <span className="requirement-value-label">{item.label}</span>
                  <em>:</em>
                  <strong className="requirement-value-text">
                    {item.value||'미수집'}
                  </strong>
                  <b>
                    {item.collected?'완료':'미수집'}
                  </b>
                </div>
              )}
            </div>

            <div className="requirement-draft-info">
              <span>
                {requirementDraftDecisionPending
                  ? '◉ 같은 경로의 이전 요구사항 Draft 발견'
                  : requirementDraftRestored
                    ? '✓ 이전 요구사항 복원됨'
                    : requirementDraftSavedAt
                      ? '✓ 요구사항 자동 저장됨'
                      : '○ 요구사항 수집 중'}
              </span>
              {requirementDraftSavedAt&&
                <small>{new Date(requirementDraftSavedAt).toLocaleString()}</small>
              }
            </div>

            {requirementDraftCandidate&&requirementDraftDecisionPending&&
              <div className="requirement-draft-choice compact">
                <p>같은 프로젝트 경로의 예전 인터뷰가 있습니다. 자동 복원하지 않습니다.</p>
                <div>
                  <button
                    type="button"
                    className="requirement-draft-restore-button"
                    onClick={()=>restoreRequirementDraft(requirementDraftCandidate.key)}
                  >
                    이전 요구사항 이어서 불러오기
                  </button>
                  <button
                    type="button"
                    className="requirement-draft-ignore-button"
                    onClick={keepCurrentInterviewInsteadOfDraft}
                  >
                    현재 인터뷰 유지
                  </button>
                </div>
              </div>
            }

            <details className="requirement-edit-details">
              <summary>이전 작업 / 요구사항 재정의</summary>
              <div className="requirement-edit-help">
                기존 경로에서 불러온 내용도 자유롭게 정리할 수 있습니다. 사용자 답변을 삭제하면 바로 다음 AI 응답도 함께 제거되며, 요구사항을 바꾸면 기존 Workflow는 자동으로 무효화됩니다.
              </div>

              <div className="requirement-edit-actions">
                <button
                  type="button"
                  className="requirement-reset-all-button"
                  onClick={clearRestoredRequirementContent}
                >
                  지난 내용 전체 삭제 후 재정의
                </button>
              </div>

              <div className="requirement-history-editor">
                <strong>사용자 답변</strong>
                {(chat||[])
                  .map((item,messageIndex)=>({item,messageIndex}))
                  .filter(row=>row.item?.role==='user')
                  .map(({item,messageIndex})=><div className="requirement-history-edit-row" key={`history-${messageIndex}`}>
                    <p>{sanitizeInterviewDisplayText(item.content)}</p>
                    <button type="button" onClick={()=>removeRequirementConversationTurn(messageIndex)}>삭제</button>
                  </div>)}
                {!(chat||[]).some(item=>item?.role==='user')&&<small>삭제하거나 재정의할 사용자 답변이 없습니다.</small>}
              </div>

              <div className="requirement-redefine-editor">
                <strong>요구사항 항목 재정의</strong>
                {getRequirementKeywordStatus().map(item=><div className="requirement-redefine-row" key={`redefine-${item.id}`}>
                  <div>
                    <span>{item.label}</span>
                    <em>{item.value||'미수집'}</em>
                  </div>
                  <button type="button" onClick={()=>beginRequirementRedefinition(item.id,item.value)}>재정의</button>
                  {String(requirementManualOverrides?.[item.id]||'').trim()&&<button
                    type="button"
                    className="requirement-override-clear-button"
                    onClick={()=>{
                      setRequirementManualOverrides(prev=>{
                        const next={...(prev||{})}
                        delete next[item.id]
                        return next
                      })
                      setChat(prev=>prev.filter(message=>message?.requirement_override!==item.id))
                      setConfirmedInterviewRequirements({})
                      invalidateRequirementWorkflowAfterEdit(`${item.label} 수동 재정의를 해제했습니다. 필요하면 다시 정의해 주세요.`)
                    }}
                  >재정의 해제</button>}
                  {requirementRedefineId===item.id&&<div className="requirement-redefine-input">
                    <textarea
                      value={requirementRedefineText}
                      onChange={e=>setRequirementRedefineText(e.target.value)}
                      placeholder={`${item.label} 요구사항을 새 기준으로 입력하세요.`}
                    />
                    <div>
                      <button type="button" onClick={saveRequirementRedefinition} disabled={!requirementRedefineText.trim()}>저장</button>
                      <button type="button" onClick={cancelRequirementRedefinition}>취소</button>
                    </div>
                  </div>}
                </div>)}
              </div>
            </details>

            <details className="requirement-collected-details">
              <summary>수집된 사용자 답변 보기</summary>
              <div>
                {(chat||[])
                  .filter(item=>item?.role==='user')
                  .map((item,index)=>
                    <p key={index}>{item.content}</p>
                  )}
                {!(chat||[]).some(item=>item?.role==='user')&&
                  <p>아직 사용자 답변이 없습니다.</p>
                }
              </div>
            </details>
          </div>
        </div>

      </>}

      {workspaceTab!=='DESIGN'&&workspaceTab!=='CODE'&&<>
      <div className="info-card">
        <div className="info-card-head"><strong>프로젝트 정보</strong><MiniBadge tone="green">활성</MiniBadge></div>
        <h3>{currentProjectName}</h3>
        <code>{currentProjectPath||'경로 미지정'}</code>
      </div>

      <div className="info-card">
        <SectionTitle title="프로젝트 요약"/>
        <p>{workspaceSummary}</p>
        {loadedProjectAnalysis?.tech_stack?.length>0&&<>
          <strong className="sub-label">기술 스택</strong>
          <div className="analysis-tags">
            {loadedProjectAnalysis.tech_stack.slice(0,8).map((x,i)=><span key={i}>{typeof x==='string'?x:JSON.stringify(x)}</span>)}
          </div>
        </>}
      </div>

      <div className="info-card">
        <SectionTitle title={`MCP 도구 (${mcpTools.length})`} action={<button onClick={openMcpAddDialog}>＋ 추가</button>}/>
        <div className="tool-list">
          {mcpTools.slice(0,8).map((t,i)=><div className="tool-row" key={i}>
            <span className="tool-status">●</span>
            <div><strong>{t.name||String(t)}</strong><small>{t.category||'MCP Tool'}</small></div>
          </div>)}
          {mcpTools.length===0&&<small className="muted">등록된 MCP 도구가 없습니다.</small>}
        </div>
      </div>

      </>}
      {workspaceTab==='WORKFLOW'&&
      <div className="info-card right-agent-build-card">
        <SectionTitle title="Agent 제작 진행"/>
        <AgentBuildActionBar
          stage={agentBuildStage}
          busy={agentBuildBusy||projectCreateFlowBusy||targetWorkflowLoading}
          message={agentBuildMessage}
          workflowEnabled={canDesignFromCollectedInfo()}
          onWorkflow={()=>{
            setWorkspaceTab('WORKFLOW')
            setWorkflowView('TARGET')
            previewTargetWorkflow()
          }}
          onCreateProject={createAgentProjectSmart}
          onStartDevelopment={startAgentDevelopment}
          onRedevelop={()=>startAgentDevelopment({redevelopment:true})}
          redevelopmentEnabled={Boolean(redevelopmentInfo?.available)}
          redevelopmentInfo={redevelopmentInfo}
          onStop={cancelAgentDevelopment}
          compact
        />
      </div>}

      {workspaceTab==='CODE'&&
      <div className="code-right-panel-shell">
        <div className="code-right-panel-tabs code-four-tabs" role="tablist" aria-label="코드 편집 우측 패널">
          <button
            type="button"
            className={codeRightPanelTab==='FILES'?'active':''}
            onClick={()=>setCodeRightPanelTab('FILES')}
          >프로젝트 파일</button>
          <button
            type="button"
            className={codeRightPanelTab==='PROPOSAL'?'active':''}
            onClick={()=>setCodeRightPanelTab('PROPOSAL')}
          >
            AI 변경 제안
            {codeEditProposal&&<span className="code-proposal-badge">1</span>}
          </button>
          <button
            type="button"
            className={codeRightPanelTab==='SQL_DB'?'active':''}
            onClick={()=>{setCodeRightPanelTab('SQL_DB');loadSqlWorkspaceStatus()}}
          >
            DB 연결
            <span className={sqlConnectionStatus?.connected?'sql-tab-dot connected':'sql-tab-dot'}></span>
          </button>
          <button
            type="button"
            className={codeRightPanelTab==='CODEX'?'active':''}
            onClick={()=>{setCodeRightPanelTab('CODEX');if(workspaceRightWidth<420)setWorkspaceRightWidth(420)}}
            title="ChatGPT 계정으로 사용하는 Codex"
          >Codex</button>
        </div>

        {codeRightPanelTab==='CODEX'&&
        <CodexPanel
          projectRoot={resolveWorkspaceRoot()}
          activeFile={selected||''}
        />}

        {codeRightPanelTab==='FILES'&&
        <div className="info-card files-card project-tree-card code-tab-panel">
          <div className="project-tree-head">
            <strong>프로젝트 파일 ({files.length})</strong>
            <div className="project-tree-actions">
              <button
                type="button"
                className="project-tree-icon-button"
                onClick={createProjectFolder}
                title="새 폴더"
                aria-label="새 폴더"
              >
                <span aria-hidden="true">📁</span>
              </button>
              <button
                type="button"
                className={
                  fileCreateLoading
                    ? 'project-tree-icon-button file-action-loading'
                    : 'project-tree-icon-button'
                }
                onClick={createProjectFile}
                disabled={fileCreateLoading}
                title={fileCreateLoading?'파일 생성 중':'새 파일'}
                aria-label="새 파일"
              >
                <span aria-hidden="true">
                  {fileCreateLoading?'…':'📄'}
                </span>
              </button>
              <button
                type="button"
                className="project-tree-icon-button"
                disabled={!root||!fileTreeSelected}
                onClick={()=>{
                  if(!root||!fileTreeSelected) return
                  const parts=fileTreeSelected.replace(/\\/g,'/').split('/')
                  beginRenameTreeItem({
                    path:fileTreeSelected,
                    name:parts[parts.length-1],
                    type:projectDirs.includes(fileTreeSelected)?'folder':'file'
                  })
                }}
                title={!root?'프로젝트를 먼저 선택하세요':(!fileTreeSelected?'이름을 변경할 파일/폴더를 선택하세요':'이름 변경')}
                aria-label="이름 변경"
              >
                <span aria-hidden="true">✎</span>
              </button>
            </div>
          </div>

          <div className="project-file-search-box">
            <span aria-hidden="true">⌕</span>
            <input
              value={projectFileSearch}
              onChange={e=>setProjectFileSearch(e.target.value)}
              placeholder="파일명 또는 경로 찾기"
              aria-label="현재 프로젝트 파일 찾기"
            />
            {projectFileSearch&&<button type="button" onClick={()=>setProjectFileSearch('')} title="파일 검색 지우기">×</button>}
          </div>
          {projectFileSearchNeedle&&<div className="project-file-search-summary">
            {projectFileSearchMatches.length}개 파일 찾음 · 전체 {files.length}개
          </div>}

          <div className="project-tree-help">
            클릭: 파일 열기 · Ctrl/Shift: 멀티 선택 · DEL: 삭제 · 우클릭: 메뉴 · ✎: 이름 변경
          </div>

          <div className="project-tree-view">
            {projectTreeForDisplay.sortedChildren?.length
              ? projectTreeForDisplay.sortedChildren.map(node=>renderProjectTreeNode(node,0))
              : <div className="empty-mini">{projectFileSearchNeedle?'검색 결과가 없습니다.':'프로젝트 파일이 없습니다.'}</div>}
          </div>

          {fileTreeContextMenu&&
            <div
              className="project-tree-context-menu"
              style={{left:fileTreeContextMenu.x,top:fileTreeContextMenu.y}}
              onMouseDown={e=>e.stopPropagation()}
            >
              <button
                type="button"
                className="danger"
                onClick={()=>requestProjectFilesDelete(fileTreeContextMenu.paths)}
              >파일 삭제</button>
            </div>
          }
        </div>}

        {codeRightPanelTab==='SQL_DB'&&
        <div className="info-card sql-connection-panel code-tab-panel">
          <div className="sql-connection-panel-head">
            <div>
              <strong>데이터베이스 연결</strong>
              <small>프로젝트별 연결 설정을 유지합니다.</small>
            </div>
            <span className={sqlConnectionStatus?.connected?'sql-status connected':'sql-status'}>
              {sqlConnectionStatus?.connected?'● 연결됨':'○ 연결 안됨'}
            </span>
          </div>

          <div className="sql-profile-manager">
            <label className="sql-field sql-saved-connection-select">
              <span>저장된 DB 연결</span>
              <select
                value={sqlProfile.connection_id||''}
                onChange={e=>selectSqlWorkspaceConnection(e.target.value)}
                disabled={sqlConnectionBusy}
              >
                <option value="">+ 새 DB 연결 만들기</option>
                {sqlConnections.map(item=><option value={item.connection_id} key={item.connection_id}>
                  {item.connected?'●':'○'} {item.name} · {String(item.db_type||'').toUpperCase()}
                </option>)}
              </select>
            </label>
            <div className="sql-profile-manager-actions">
              <button type="button" onClick={()=>newSqlWorkspaceConnection(sqlProfile.db_type)} disabled={sqlConnectionBusy}>+ 새 연결</button>
              <button type="button" className="danger" onClick={deleteSqlWorkspaceConnection} disabled={sqlConnectionBusy||!sqlProfile.connection_id}>저장 연결 삭제</button>
            </div>
            {!!sqlConnections.length&&<div className="sql-saved-connection-chips">
              {sqlConnections.map(item=><button
                type="button"
                key={`chip-${item.connection_id}`}
                className={`${item.connected?'connected ':''}${sqlProfile.connection_id===item.connection_id?'active':''}`.trim()}
                onClick={()=>selectSqlWorkspaceConnection(item.connection_id)}
                title={`${item.name} · ${String(item.db_type||'').toUpperCase()}${item.connected?' · 연결됨':' · 연결 안됨'}`}
              >
                <span>{item.connected?'●':'○'}</span>
                <b>{item.name}</b>
                <em>{String(item.db_type||'').toUpperCase()}</em>
              </button>)}
            </div>}
          </div>

          <label className="sql-field">
            <span>연결 이름</span>
            <input
              value={sqlProfile.name||''}
              onChange={e=>setSqlProfile(prev=>({...prev,name:e.target.value}))}
              placeholder="예: 운영 MSSQL / 개발 PostgreSQL / Supabase / Firestore / Redis"
            />
            {sqlProfile.connection_id&&<small className="muted">저장된 PostgreSQL/Supabase/Firestore/Redis/MSSQL/Oracle/SQLite3 연결 이름을 수정할 수 있습니다. 접속 정보와 저장 비밀번호는 변경하지 않습니다.</small>}
          </label>
          {sqlProfile.connection_id&&<div className="sql-profile-manager-actions">
            <button type="button" onClick={renameSqlWorkspaceConnection} disabled={sqlConnectionBusy||!String(sqlProfile.name||'').trim()}>연결 이름 변경 저장</button>
          </div>}

          <label className="sql-field">
            <span>DB 종류</span>
            <select value={sqlProfile.db_type} onChange={e=>{
              const nextType=e.target.value
              setSqlSupabaseConnectionUrl('')
              setSqlConnectionImport({busy:false,db_type:'',source_name:'',message:'',error:''})
              setSqlProfile(prev=>{
                const previousDefaultName=sqlProfileForType(prev.db_type||'postgresql').name
                const nextDefaultName=sqlProfileForType(nextType).name
                return {
                  ...sqlProfileForType(nextType),
                  connection_id:prev.connection_id||'',
                  name:(!prev.name||prev.name===previousDefaultName)?nextDefaultName:prev.name,
                  credential_saved:prev.db_type===nextType?!!prev.credential_saved:false,
                  password:''
                }
              })
              if(nextType==='sqlite3') loadSqliteProjectStatus({quiet:true})
            }}>
              <option value="postgresql">PostgreSQL</option>
              <option value="supabase">Supabase (PostgreSQL)</option>
              <option value="firestore">Google Cloud Firestore</option>
              <option value="redis">Redis (Key-Value)</option>
              <option value="mssql">MSSQL</option>
              <option value="oracle">Oracle</option>
              <option value="sqlite3">SQLite3</option>
            </select>
          </label>

          {sqlProfile.db_type==='firestore'
            ? <>
                <div className="sql-connection-import-card firestore-import-card">
                  <div>
                    <strong>Firestore Service Account JSON 자동 등록</strong>
                    <small>Google Cloud/Firebase Service Account JSON을 분석해 Project ID와 JSON 파일 경로를 자동 등록합니다. Private Key 내용은 설정에 복사하지 않습니다.</small>
                  </div>
                  <button type="button" onClick={()=>importSqlConnectionFile('firestore')} disabled={sqlConnectionImport.busy}>
                    {sqlConnectionImport.busy&&sqlConnectionImport.db_type==='firestore'?'분석 중...':'Service Account JSON 찾기 / 로드'}
                  </button>
                  {sqlConnectionImport.db_type==='firestore'&&sqlConnectionImport.message&&<p className="ok">{sqlConnectionImport.message}</p>}
                  {sqlConnectionImport.db_type==='firestore'&&sqlConnectionImport.error&&<p className="error">{sqlConnectionImport.error}</p>}
                </div>
                <label className="sql-field">
                  <span>Google Cloud Project ID</span>
                  <input value={sqlProfile.project_id||''} onChange={e=>setSqlProfile(prev=>({...prev,project_id:e.target.value}))} placeholder="예: my-firebase-project"/>
                </label>
                <label className="sql-field">
                  <span>Firestore Database ID</span>
                  <input value={sqlProfile.database||''} onChange={e=>setSqlProfile(prev=>({...prev,database:e.target.value}))} placeholder="(default)"/>
                </label>
                <label className="sql-field">
                  <span>Service Account JSON 경로</span>
                  <input value={sqlProfile.service_account_json||''} onChange={e=>setSqlProfile(prev=>({...prev,service_account_json:e.target.value}))} placeholder="serviceAccountKey.json · 비워두면 GOOGLE_APPLICATION_CREDENTIALS/ADC 사용"/>
                </label>
                <div className="sql-connection-info">
                  <div><span>드라이버</span><code>google-cloud-firestore</code></div>
                  <div><span>구조</span><code>Collection → Document → Field</code></div>
                  <small>Service Account JSON 파일 자체의 내용은 AgentStudio 설정에 저장하지 않고 파일 경로만 저장합니다.</small>
                </div>
              </>
            : sqlProfile.db_type==='redis'
            ? <>
                <div className="sql-connection-import-card">
                  <div>
                    <strong>Redis 연결 파일 자동 등록</strong>
                    <small>Python/JSON/.env 파일에서 Redis 연결 정보를 분석합니다. Python 파일은 실행하지 않고 AST로만 읽습니다.</small>
                  </div>
                  <button type="button" onClick={()=>importSqlConnectionFile('redis')} disabled={sqlConnectionImport.busy}>
                    {sqlConnectionImport.busy&&sqlConnectionImport.db_type==='redis'?'분석 중...':'파일 찾기 / 로드'}
                  </button>
                  {sqlConnectionImport.db_type==='redis'&&sqlConnectionImport.message&&<p className="ok">{sqlConnectionImport.message}</p>}
                  {sqlConnectionImport.db_type==='redis'&&sqlConnectionImport.error&&<p className="error">{sqlConnectionImport.error}</p>}
                </div>
                <div className="sql-field-grid two">
                  <label className="sql-field"><span>Host</span><input value={sqlProfile.host||''} onChange={e=>setSqlProfile(prev=>({...prev,host:e.target.value}))} placeholder="127.0.0.1"/></label>
                  <label className="sql-field"><span>Port</span><input type="number" value={sqlProfile.port||6379} onChange={e=>setSqlProfile(prev=>({...prev,port:Number(e.target.value)||6379}))} placeholder="6379"/></label>
                </div>
                <label className="sql-field">
                  <span>Redis DB index</span>
                  <input type="number" min="0" value={sqlProfile.database??'0'} onChange={e=>setSqlProfile(prev=>({...prev,database:String(Math.max(0,Number(e.target.value)||0))}))} placeholder="0"/>
                </label>
                <label className="sql-field">
                  <span>사용자 (ACL 사용 시)</span>
                  <input value={sqlProfile.username||''} onChange={e=>setSqlProfile(prev=>({...prev,username:e.target.value}))} placeholder="비워두면 기본 사용자"/>
                </label>
                <label className="sql-field">
                  <span>비밀번호 {sqlProfile.credential_saved&&<em className="sql-credential-saved">Windows 보안 저장됨</em>}</span>
                  <input
                    type="password"
                    value={sqlProfile.password||''}
                    onChange={e=>setSqlProfile(prev=>({...prev,password:e.target.value}))}
                    placeholder={sqlProfile.credential_saved?'저장된 비밀번호 사용 · 변경할 때만 새 비밀번호 입력':'비밀번호가 없으면 비워두세요'}
                  />
                </label>
                <div className="sql-connection-info">
                  <div><span>드라이버</span><code>redis-py</code></div>
                  <div><span>구조</span><code>Key → Value · String / Hash / List / Set / ZSet</code></div>
                  <small>Redis는 SQL DB가 아니라 NoSQL Key-Value 데이터베이스입니다. 연결/인증/PING 테스트를 지원하며 SQL 실행은 사용하지 않습니다.</small>
                </div>
              </>
            : sqlProfile.db_type==='sqlite3'
            ? <>
                <label className="sql-field">
                  <span>SQLite DB 파일</span>
                  <input
                    value={sqlProfile.database||''}
                    onChange={e=>setSqlProfile(prev=>({...prev,database:e.target.value}))}
                    placeholder="data/app.db 또는 기존 .sqlite/.sqlite3 파일"
                    list="sqlite-project-db-files"
                  />
                  <datalist id="sqlite-project-db-files">
                    {(sqliteProjectStatus?.database_files||[]).map(path=><option value={path} key={path}/>) }
                  </datalist>
                </label>
                <div className="sqlite-project-status-card">
                  <div className="sqlite-project-status-head">
                    <div>
                      <strong>프로젝트 SQLite3 상태</strong>
                      <small>AgentStudio SQL Workspace는 Python 표준 sqlite3 모듈을 사용합니다.</small>
                    </div>
                    <button type="button" onClick={()=>loadSqliteProjectStatus()} disabled={sqliteProjectStatusBusy}>{sqliteProjectStatusBusy?'…':'↻ 확인'}</button>
                  </div>
                  <div className="sqlite-status-grid">
                    <div><span>AgentStudio sqlite3</span><strong className={sqliteProjectStatus?.agentstudio_python?.available?'ok':'warn'}>{sqliteProjectStatus?.agentstudio_python?.available?`사용 가능 · ${sqliteProjectStatus.agentstudio_python.sqlite_version||''}`:'확인 필요'}</strong></div>
                    <div><span>프로젝트 Python</span><strong className={sqliteProjectStatus?.project_python?.sqlite3_available?'ok':''}>{sqliteProjectStatus?.project_python?.found?(sqliteProjectStatus.project_python.sqlite3_available?`sqlite3 ${sqliteProjectStatus.project_python.sqlite_version||''}`:'sqlite3 사용 불가'):'가상환경 미탐지'}</strong></div>
                    <div><span>Node sqlite 패키지</span><strong>{(sqliteProjectStatus?.node_packages||[]).length?sqliteProjectStatus.node_packages.map(item=>`${item.name} ${item.version}`).join(', '):'설치 항목 없음'}</strong></div>
                    <div><span>SQLite CLI</span><strong>{sqliteProjectStatus?.sqlite_cli||'PATH에서 미탐지'}</strong></div>
                  </div>
                  <div className="sqlite-db-file-list">
                    <span>프로젝트 DB 파일 {(sqliteProjectStatus?.database_files||[]).length}개</span>
                    {(sqliteProjectStatus?.database_files||[]).length
                      ? (sqliteProjectStatus.database_files||[]).slice(0,12).map(path=><button type="button" key={path} onClick={()=>setSqlProfile(prev=>({...prev,database:path}))}>{path}</button>)
                      : <small>발견된 DB 파일이 없습니다. 예: data/app.db 를 입력하면 연결 시 생성합니다.</small>}
                  </div>
                </div>
              </>
            : <>
                {sqlProfile.db_type==='supabase'&&<>
                  <div className="sql-connection-import-card">
                    <div>
                      <strong>Supabase JSON 자동 등록</strong>
                      <small>JSON의 PostgreSQL URL 또는 Host/Port/Database/Schema/User/Password/SSL 정보를 분석해 아래 입력란에 자동 등록합니다.</small>
                    </div>
                    <button type="button" onClick={()=>importSqlConnectionFile('supabase')} disabled={sqlConnectionImport.busy}>
                      {sqlConnectionImport.busy&&sqlConnectionImport.db_type==='supabase'?'분석 중...':'JSON 파일 찾기 / 로드'}
                    </button>
                    {sqlConnectionImport.db_type==='supabase'&&sqlConnectionImport.message&&<p className="ok">{sqlConnectionImport.message}</p>}
                    {sqlConnectionImport.db_type==='supabase'&&sqlConnectionImport.error&&<p className="error">{sqlConnectionImport.error}</p>}
                  </div>
                  <label className="sql-field">
                    <span>Supabase Connection URL</span>
                    <input
                      type="password"
                      value={sqlSupabaseConnectionUrl}
                      onChange={e=>setSqlSupabaseConnectionUrl(e.target.value)}
                      placeholder="postgresql://USER:PASSWORD@HOST:5432/postgres"
                      autoComplete="off"
                    />
                  </label>
                  <div className="sql-profile-manager-actions">
                    <button type="button" onClick={applySupabaseConnectionUrl} disabled={!String(sqlSupabaseConnectionUrl||'').trim()}>Connection URL 적용</button>
                  </div>
                  <small className="muted">Dashboard에서 복사한 URL은 저장하지 않고 아래 연결 필드로만 분해합니다.</small>
                </>}
                <div className="sql-field-grid two">
                  <label className="sql-field"><span>Host</span><input value={sqlProfile.host||''} onChange={e=>setSqlProfile(prev=>({...prev,host:e.target.value}))}/></label>
                  <label className="sql-field"><span>Port</span><input type="number" value={sqlProfile.port||''} onChange={e=>setSqlProfile(prev=>({...prev,port:Number(e.target.value)||0}))}/></label>
                </div>

                {sqlProfile.db_type!=='oracle'
                  ? (()=>{
                      const history=getSqlDatabaseHistory()
                      const current=String(sqlProfile.database||'')
                      const canUseHistory=history.length>=2&&!sqlDatabaseManual&&(!current||history.includes(current))
                      return <label className="sql-field">
                        <span>Database {history.length>=2&&<em className="sql-database-history-count">접속 이력 {history.length}개</em>}</span>
                        {canUseHistory
                          ? <div className="sql-database-history-control">
                              <select
                                value={current}
                                onChange={e=>setSqlProfile(prev=>({...prev,database:e.target.value}))}
                              >
                                <option value="">Database 선택</option>
                                {history.map(dbName=><option key={dbName} value={dbName}>{dbName}</option>)}
                              </select>
                              <button type="button" onClick={()=>{setSqlDatabaseManual(true);setSqlProfile(prev=>({...prev,database:''}))}}>직접 입력</button>
                            </div>
                          : <div className="sql-database-history-control">
                              <input
                                value={current}
                                onChange={e=>setSqlProfile(prev=>({...prev,database:e.target.value}))}
                                placeholder={sqlProfile.db_type==='mssql'?'master':'postgres'}
                              />
                              {history.length>=2&&<button type="button" onClick={()=>{setSqlDatabaseManual(false);setSqlProfile(prev=>({...prev,database:history[0]||''}))}}>이력 선택</button>}
                            </div>}
                      </label>
                    })()
                  : <label className="sql-field"><span>Service Name</span><input value={sqlProfile.service_name||''} onChange={e=>setSqlProfile(prev=>({...prev,service_name:e.target.value}))} placeholder="FREEPDB1 / XEPDB1"/></label>}

                {['postgresql','supabase'].includes(sqlProfile.db_type)&&<label className="sql-field">
                  <span>Schema</span>
                  <input
                    value={sqlProfile.schema_name||''}
                    onChange={e=>setSqlProfile(prev=>({...prev,schema_name:e.target.value}))}
                    placeholder={sqlProfile.db_type==='supabase'?'예: theanova_agentstudio / public':'예: training_practice / public'}
                  />
                  <small className="muted">{sqlProfile.db_type==='supabase'
                    ? 'Supabase PostgreSQL 연결 후 기본 search_path를 Schema → extensions → public 순서로 적용합니다. 비우면 public을 사용합니다.'
                    : 'PostgreSQL 연결 후 기본 search_path를 Schema → public 순서로 적용합니다. Local/Docker/원격 PostgreSQL 모두 동일하며 비우면 public을 사용합니다.'}</small>
                </label>}

                <label className="sql-field"><span>사용자</span><input value={sqlProfile.username||''} onChange={e=>setSqlProfile(prev=>({...prev,username:e.target.value}))}/></label>
                <label className="sql-field">
                  <span>비밀번호 {sqlProfile.credential_saved&&<em className="sql-credential-saved">Windows 보안 저장됨</em>}</span>
                  <input
                    type="password"
                    value={sqlProfile.password||''}
                    onChange={e=>setSqlProfile(prev=>({...prev,password:e.target.value}))}
                    placeholder={sqlProfile.credential_saved?'저장된 비밀번호 사용 · 변경할 때만 새 비밀번호 입력':'DB 비밀번호'}
                  />
                </label>

                {sqlProfile.db_type==='mssql'&&<>
                  <label className="sql-field"><span>ODBC Driver</span><input value={sqlProfile.driver||''} onChange={e=>setSqlProfile(prev=>({...prev,driver:e.target.value}))}/></label>
                  <label className="sql-check-field"><input type="checkbox" checked={!!sqlProfile.trust_server_certificate} onChange={e=>setSqlProfile(prev=>({...prev,trust_server_certificate:e.target.checked}))}/><span>Trust Server Certificate</span></label>
                </>}
                {sqlProfile.db_type==='supabase'&&
                  <label className="sql-field"><span>SSL Mode</span><input value={sqlProfile.ssl_mode||'require'} onChange={e=>setSqlProfile(prev=>({...prev,ssl_mode:e.target.value}))} placeholder="require"/></label>}
              </>}

          <div className="sql-connection-actions">
            <button type="button" onClick={saveSqlWorkspaceProfile} disabled={sqlConnectionBusy}>연결 정보 저장</button>
            <button type="button" className="primary" onClick={connectSqlWorkspace} disabled={sqlConnectionBusy}>{sqlConnectionBusy?'처리 중...':'연결 / 테스트'}</button>
            <button type="button" onClick={disconnectSqlWorkspace} disabled={sqlConnectionBusy||!sqlConnectionStatus?.connected}>현재 연결 해제</button>
            <button type="button" onClick={loadSqlWorkspaceStatus} disabled={sqlConnectionBusy}>상태 새로고침</button>
            {sqlProfile.db_type==='supabase'&&<button type="button" onClick={()=>window.open('https://supabase.com/dashboard','_blank','noopener,noreferrer')}>Supabase Dashboard</button>}
            {sqlProfile.db_type==='firestore'&&<button type="button" onClick={()=>window.open('https://console.cloud.google.com/firestore/databases','_blank','noopener,noreferrer')}>Google Cloud Firestore</button>}
          </div>

          <div className="sql-connection-info">
            <div><span>현재 파일</span><code>{selected}</code></div>
            <div><span>선택 연결</span><strong>{sqlProfile.name||'새 DB 연결'} · {String(sqlProfile.db_type||'').toUpperCase()}</strong></div>
            <div><span>현재 연결 상태</span><strong>{sqlConnectionStatus?.connected?'연결 유지 중':'연결 필요'}</strong></div>
            <div><span>저장된 연결</span><code>{sqlConnectionStatus?.saved_connection_count??sqlConnections.length}개 · 연결 중 {sqlConnectionStatus?.connected_connection_count??sqlConnections.filter(item=>item.connected).length}개</code></div>
            {sqlProfile.db_type==='sqlite3'&&<div><span>DB 파일</span><code>{sqlConnectionStatus?.profile?.database||sqlProfile.database||'-'}</code></div>}
            {['postgresql','supabase'].includes(sqlProfile.db_type)&&<div><span>{sqlProfile.db_type==='supabase'?'Supabase Schema':'PostgreSQL Schema'}</span><code>{sqlConnectionStatus?.profile?.schema_name||sqlProfile.schema_name||'public'}</code></div>}
            {sqlConnectionStatus?.connected_at&&<div><span>연결 시각</span><code>{sqlConnectionStatus.connected_at}</code></div>}
            {!!(sqlConnectionStatus?.saved_db_types||[]).length&&<div><span>등록된 DB 종류</span><code>{sqlConnectionStatus.saved_db_types.map(v=>String(v).toUpperCase()).join(', ')}</code></div>}
            {sqlConnectionStatus?.profile_storage_path&&<div><span>연결 정보 저장 위치</span><code title={sqlConnectionStatus.profile_storage_path}>{sqlConnectionStatus.profile_storage_path}</code></div>}
            {!['sqlite3','firestore'].includes(sqlProfile.db_type)&&<div><span>비밀번호 저장</span><code>{sqlConnectionStatus?.credential_storage||'Windows DPAPI'}</code></div>}
            {sqlProfile.db_type==='firestore'&&<div><span>인증</span><code>{sqlProfile.service_account_json?'Service Account JSON':'GOOGLE_APPLICATION_CREDENTIALS / ADC'}</code></div>}
            <small>{sqlProfile.db_type==='sqlite3'
              ? 'SQLite3도 여러 DB 파일을 각각 별도의 연결로 등록할 수 있습니다.'
              : sqlProfile.db_type==='firestore'
                ? 'Firestore는 NoSQL 문서형 DB입니다. AgentStudio에서는 Project/Database/Service Account 경로를 저장하고 연결을 테스트합니다.'
                : sqlProfile.db_type==='supabase'
                  ? 'Supabase는 PostgreSQL 기반 관리형 플랫폼으로 psycopg와 SSL(require)을 사용해 SQL Workspace에 연결합니다.'
                  : sqlProfile.db_type==='redis'
                    ? 'Redis는 NoSQL Key-Value DB입니다. Host/Port/DB index/ACL 사용자/비밀번호를 저장하고 redis-py PING으로 연결한 뒤 Key Browser에서 데이터를 조회합니다.'
                    : '동일한 DB 종류도 연결 이름을 다르게 하여 여러 개 등록할 수 있습니다. Windows에서는 비밀번호를 DPAPI 현재 사용자 범위로 암호화하여 저장하며 평문으로 기록하지 않습니다.'}</small>
          </div>

          <div className="sql-object-explorer">
            <div className="sql-object-explorer-head">
              <div>
                <strong>{sqlProfile.db_type==='firestore'?'Firestore 연결':sqlProfile.db_type==='redis'?'Redis 연결':'DB Object Explorer'}</strong>
                <small>{sqlProfile.db_type==='firestore'?'NoSQL Document Database · Collection → Document → Field':sqlProfile.db_type==='redis'?'NoSQL Key-Value Database · String / Hash / List / Set / ZSet':'테이블 · 뷰 · 프로시저 · 함수 · 인덱스 · 시퀀스 · 트리거'}</small>
                <small className="sql-object-doubleclick-help">{sqlProfile.db_type==='firestore'?'Firestore 인증 후 Collection/Document/Field를 읽기 전용으로 탐색합니다. SQL 실행은 사용하지 않습니다.':sqlProfile.db_type==='redis'?'Redis 인증/PING 후 Key Browser에서 실제 Key/Value를 읽기 전용으로 조회합니다. SQL 실행은 사용하지 않습니다.':'더블클릭: 테이블은 전체 컬럼 SELECT 조회 · 기타 객체는 수정용 임시 SQL 생성'}</small>
              </div>
              <button
                type="button"
                onClick={()=>sqlProfile.db_type==='firestore'?loadFirestoreCollections():sqlProfile.db_type==='redis'?loadRedisKeys():loadSqlDbObjects()}
                disabled={!sqlConnectionStatus?.connected||(sqlProfile.db_type==='firestore'?firestoreBrowserBusy:sqlProfile.db_type==='redis'?redisBrowserBusy:sqlDbObjectsBusy)}
                title={sqlProfile.db_type==='firestore'?'Firestore Collection 목록 새로고침':sqlProfile.db_type==='redis'?'Redis Key 목록 새로고침':'DB 객체 목록 새로고침'}
              >
                {(sqlProfile.db_type==='firestore'?firestoreBrowserBusy:sqlProfile.db_type==='redis'?redisBrowserBusy:sqlDbObjectsBusy)?'…':'↻'}
              </button>
            </div>

            {sqlProfile.db_type==='firestore'
              ? <FirestoreBrowserPanel
                  connected={sqlConnectionStatus?.connected}
                  profile={sqlProfile}
                  browser={firestoreBrowser}
                  browserBusy={firestoreBrowserBusy}
                  browserError={firestoreBrowserError}
                  collectionFilter={firestoreCollectionFilter}
                  documentFilter={firestoreDocumentFilter}
                  selectedCollection={firestoreSelectedCollection}
                  documents={firestoreDocuments}
                  documentsBusy={firestoreDocumentsBusy}
                  selectedDocument={firestoreSelectedDocument}
                  documentDetail={firestoreDocumentDetail}
                  documentDetailBusy={firestoreDocumentDetailBusy}
                  setCollectionFilter={setFirestoreCollectionFilter}
                  setDocumentFilter={setFirestoreDocumentFilter}
                  loadCollections={loadFirestoreCollections}
                  loadDocuments={loadFirestoreDocuments}
                  loadDocumentDetail={loadFirestoreDocumentDetail}
                  openContextMenu={openFirestoreContextMenu}
                />
              : sqlProfile.db_type==='redis'
                ? <RedisBrowserPanel
                    connected={sqlConnectionStatus?.connected}
                    profile={sqlProfile}
                    browser={redisBrowser}
                    browserBusy={redisBrowserBusy}
                    browserError={redisBrowserError}
                    keyFilter={redisKeyFilter}
                    typeFilter={redisTypeFilter}
                    selectedKey={redisSelectedKey}
                    keyDetail={redisKeyDetail}
                    keyDetailBusy={redisKeyDetailBusy}
                    keyExpanded={redisKeyExpanded}
                    setKeyFilter={setRedisKeyFilter}
                    setTypeFilter={setRedisTypeFilter}
                    toggleKeyGroup={toggleRedisKeyGroup}
                    loadKeys={loadRedisKeys}
                    loadKeyDetail={loadRedisKeyDetail}
                    openContextMenu={openRedisContextMenu}
                  />
                : <SqlObjectTreePanel
                    connected={sqlConnectionStatus?.connected}
                    profile={sqlProfile}
                    connectionStatus={sqlConnectionStatus}
                    dbObjects={sqlDbObjects}
                    busy={sqlDbObjectsBusy}
                    error={sqlDbObjectsError}
                    expanded={sqlDbObjectExpanded}
                    actionBusy={sqlObjectActionBusy}
                    toggleObject={toggleSqlDbObject}
                    openObject={openSqlDbObject}
                    openObjectContextMenu={openSqlObjectContextMenu}
                    openSchemaContextMenu={openSqlSchemaContextMenu}
                    openDatabaseContextMenu={openSqlDatabaseContextMenu}
                  />}

            {sqlDbObjects?.refreshed_at&&sqlProfile.db_type!=='firestore'&&sqlProfile.db_type!=='redis'&&
              <div className="sql-object-refreshed">최근 조회: {sqlDbObjects.refreshed_at.replace('T',' ')}</div>}

            <DatabaseBrowserContextMenus
              firestoreContextMenu={firestoreContextMenu}
              firestoreScriptBusy={firestoreScriptBusy}
              createFirestorePythonScript={createFirestorePythonScript}
              redisContextMenu={redisContextMenu}
              redisScriptBusy={redisScriptBusy}
              createRedisPythonScript={createRedisPythonScript}
              sqlObjectContextMenu={sqlObjectContextMenu}
              sqlSchemaContextMenu={sqlSchemaContextMenu}
              sqlObjectActionBusy={sqlObjectActionBusy}
              createSqlTableDiagram={createSqlTableDiagram}
              createSqlSchemaDiagram={createSqlSchemaDiagram}
              createSqlTableScript={createSqlTableScript}
              createSqlTableAlterScript={createSqlTableAlterScript}
              createSqlTableDmlScript={createSqlTableDmlScript}
              sqlDatabaseContextMenu={sqlDatabaseContextMenu}
              dbObjects={sqlDbObjects}
              profile={sqlProfile}
              createPostgresqlAdminScript={createPostgresqlAdminScript}
              openSqlAdminPrompt={openSqlAdminPrompt}
              sqlAdminPrompt={sqlAdminPrompt}
              setSqlAdminPrompt={setSqlAdminPrompt}
              submitSqlAdminPrompt={submitSqlAdminPrompt}
            />

          </div>

          {sqlConnectionStatus?.error&&<div className="sql-connection-error">{sqlConnectionStatus.error}</div>}
        </div>}

        {codeRightPanelTab==='PROPOSAL'&&
        <div className="info-card code-proposal-panel code-tab-panel">
          <div className="code-proposal-panel-head">
            <div>
              <strong>AI 변경 제안</strong>
              <small>AI 코드는 바로 원본에 반영되지 않습니다.</small>
            </div>
            {codeDiffReview&&<span className="diff-review-badge">Diff 검토 중</span>}
          </div>

          {codeEditProposal
            ? <>
                <div className="code-proposal-meta">
                  <span>대상 파일</span>
                  <code>{codeEditProposal.path}</code>
                </div>
                {codeEditProposal.instruction&&
                  <div className="code-proposal-instruction">
                    <span>요청</span>
                    <p>{codeEditProposal.instruction}</p>
                  </div>
                }
                {codeEditProposal.editScope==='notebook_cell'&&
                  <div className="code-proposal-context-budget">
                    <span>Notebook Cell {(Number(codeEditProposal.activeCellIndex)||0)+1}만 수정</span>
                    {codeEditProposal.contextBudget&&<small>
                      LLM Context {Number(codeEditProposal.contextBudget.llm_context_chars||0).toLocaleString('ko-KR')}자
                      {' / '}전체 파일 {Number(codeEditProposal.contextBudget.original_file_chars||0).toLocaleString('ko-KR')}자
                    </small>}
                  </div>
                }
                {codeEditProposal.explanation&&
                  <p className="code-proposal-explanation">{codeEditProposal.explanation}</p>
                }
                <div className="code-proposal-editor-wrap">
                  <Editor
                    key={codeEditProposal.createdAt||codeEditProposal.path}
                    height="100%"
                    value={codeEditProposal.displayCode||codeEditProposal.code}
                    language={codeEditProposal.editScope==='notebook_cell'?'python':getEditorLanguage(codeEditProposal.path)}
                    theme="vs-dark"
                    options={{
                      readOnly:true,
                      minimap:{enabled:false},
                      lineNumbers:'on',
                      fontSize:13,
                      lineHeight:20,
                      automaticLayout:true,
                      scrollBeyondLastLine:false,
                      folding:true,
                      wordWrap:'off',
                      mouseWheelScrollSensitivity:1,
                      scrollbar:{
                        vertical:'visible',
                        horizontal:'auto',
                        verticalScrollbarSize:12,
                        horizontalScrollbarSize:10,
                        alwaysConsumeMouseWheel:false,
                        useShadows:true
                      }
                    }}
                  />
                </div>
                <div className="code-proposal-panel-actions">
                  <button type="button" className="apply" onClick={openCodeEditDiffReview}>Apply · 비교</button>
                  <button type="button" onClick={discardCodeEditProposal}>취소</button>
                </div>
              </>
            : <div className="code-proposal-empty">
                <span>◇</span>
                <strong>AI 변경 제안이 없습니다.</strong>
                <p>하단 채팅에서 파일 단위로 코드 변경을 요청하면 이 탭에 제안 코드가 표시됩니다.</p>
              </div>
          }
        </div>}
      </div>}

    </aside>
  </div>
  }

  const pickExternalProjectFolder=async()=>{
    if(externalProjectPickerLoading) return

    setExternalProjectPickerLoading(true)
    setExternalProjectPickerMessage(
      'Windows 폴더 선택창을 여는 중입니다...'
    )

    try{
      const r=await api('/system/pick-folder',{
        method:'POST',
        body:JSON.stringify({
          title:'분석할 기존 프로젝트 폴더 선택',
          initial_path:externalProjectPath||''
        })
      })

      if(r?.ok && !r?.cancelled && r?.path){
        setExternalProjectPath(r.path)
        setExternalProjectPickerMessage(
          '선택한 경로: '+r.path
        )
        return
      }

      if(r?.cancelled){
        setExternalProjectPickerMessage(
          '폴더 선택을 취소했습니다.'
        )
        return
      }

      setExternalProjectPickerMessage(
        '경로 선택 실패: '
        +(r?.message||'폴더 선택창을 열지 못했습니다.')
      )
    }catch(e){
      const message='경로 선택 실패: '+String(e)

      setExternalProjectPickerMessage(message)
      setProjectLoadMessage(message)
    }finally{
      setExternalProjectPickerLoading(false)
    }
  }

  const pollExternalProjectJob=async(jobId)=>{
    let lastProgress=0

    for(let i=0;i<1800;i++){
      try{
        const j=await api(`/jobs/${jobId}`)

        const progress=Math.max(lastProgress,Number(j.progress||0))
        lastProgress=progress

        setExternalProjectProgress(progress)
        setExternalProjectStatus(j.status||'RUNNING')
        setExternalProjectStep(j.message||'분석 작업을 진행하고 있습니다.')

        if(j.status==='SUCCESS'){
          const r=j.result||{}

          setExternalProjectProgress(100)
          setExternalProjectStatus('SUCCESS')
          setExternalProjectStep('분석 및 DB 저장 완료. 작업공간으로 이동합니다.')

          setExternalProjectAnalysis(r)
          setExternalProjectMode(false)
          setSelectedProjectId(r.project_id||null)
          setRoot(r.project_root||externalProjectPath)
          setNewAgentProjectRoot(r.project_root||externalProjectPath)
          setNewAgentName(
            r.project_name
            || (r.project_root||externalProjectPath).split(/[\\/]/).filter(Boolean).pop()
            || 'External Project'
          )
          setNewAgentCachePath(r.cache_path||'')
          setNewAgentTempPath(r.temp_path||'')
          setNewAgentOutputPath(r.output_path||'')
          setNewAgentVenvPath(r.venv_path||'')
          setNewAgentModelsPath(r.models_path||'')
          setLoadedProjectAnalysis({
            summary:r.summary||'',
            tech_stack:r.tech_stack||[],
            entry_points:r.entry_points||[],
            major_files:r.major_files||[],
            mcp_tools:r.mcp_tools||[],
            structure:r.structure||{}
          })

          setProjectLoadMessage(`Project #${r.project_id} 분석 및 DB 저장 완료`)
          const dbProjects=await refreshProjectList()

          if(!dbProjects.some(p=>p.id===r.project_id)){
            setProjectListStatus(
              `DB 저장 응답은 성공했지만 Project #${r.project_id}가 GET /api/projects 결과에 없습니다.`
            )
          }

          await loadProject(r.project_id)

          // 완료 상태를 잠깐 보여준 후 자동으로 작업공간 이동
          await new Promise(resolve=>setTimeout(resolve,700))

          setProjectListOpen(false)
          setScreen('WORKSPACE')

          try{
            const externalRoot=String(r.project_root||externalProjectPath||'').trim()
            const fileResult=await api(
              `/files?root=${encodeURIComponent(externalRoot)}`
            )
            if(externalRoot){
              workspaceRootRef.current=externalRoot
              fileTreeRootRef.current=externalRoot
            }
            setFiles(
              Array.isArray(fileResult)
                ? fileResult
                : (fileResult.files||[])
            )
          }catch(e){
            try{ await loadFiles() }catch(_){}
          }

          setExternalProjectLoading(false)
          return
        }

        if(['FAILED','CANCELLED'].includes(j.status)){
          setExternalProjectStatus(j.status)
          setExternalProjectStep(
            j.result?.message
            || j.message
            || '프로젝트 분석 작업에 실패했습니다.'
          )
          setExternalProjectAnalysis({
            ok:false,
            message:j.result?.message||j.message||'',
            log_path:j.result?.log_path||'',
            traceback:j.result?.traceback||''
          })
          setProjectLoadMessage(
            '프로젝트 분석 실패: '
            + (j.result?.message||j.message||'상세 오류를 확인하세요.')
          )
          setExternalProjectLoading(false)
          return
        }
      }catch(e){
        setExternalProjectStep(
          '분석 상태 확인 중 오류: '+String(e)
        )
      }

      await new Promise(resolve=>setTimeout(resolve,800))
    }

    setExternalProjectStatus('FAILED')
    setExternalProjectStep('프로젝트 분석 상태 확인 시간이 초과되었습니다.')
    setExternalProjectLoading(false)
  }

  const analyzeExternalProject=async()=>{
    if(!externalProjectPath.trim()){
      setProjectLoadMessage('분석할 프로젝트 경로를 지정하세요.')
      return
    }

    setExternalProjectLoading(true)
    setExternalProjectProgress(0)
    setExternalProjectStatus('QUEUED')
    setExternalProjectStep('프로젝트 분석 작업을 준비하고 있습니다.')
    setProjectLoadMessage('')
    setExternalProjectAnalysis(null)

    try{
      const job=await api('/projects/analyze-external',{
        method:'POST',
        body:JSON.stringify({
          project_root:externalProjectPath,
          request:'프로젝트 소스 구조, 기술 스택, 주요 파일, 실행 진입점, MCP/Agent 관련 소스만 분석해주세요. 모델은 실행하지 말고 소스에 명시된 모델명만 참고해주세요.'
        })
      })

      if(!job.ok || !job.job_id){
        setExternalProjectStatus('FAILED')
        setExternalProjectStep(job.message||'분석 작업 시작에 실패했습니다.')
        setExternalProjectLoading(false)
        return
      }

      setExternalProjectStatus(job.status||'QUEUED')
      setExternalProjectProgress(job.progress||0)
      setExternalProjectStep(job.message||'분석 작업을 시작했습니다.')

      pollExternalProjectJob(job.job_id)

    }catch(e){
      setExternalProjectStatus('FAILED')
      setExternalProjectStep('프로젝트 분석 시작 실패: '+String(e))
      setExternalProjectLoading(false)
    }
  }

  const openExternalProjectWorkspace=async()=>{
    if(!externalProjectAnalysis?.project_root) return

    setRoot(externalProjectAnalysis.project_root)
    setScreen('WORKSPACE')
    setProjectListOpen(false)
    setExternalProjectMode(true)

    try{
      const externalRoot=String(externalProjectAnalysis.project_root||'').trim()
      const r=await api(`/files?root=${encodeURIComponent(externalRoot)}`)
      workspaceRootRef.current=externalRoot
      fileTreeRootRef.current=externalRoot
      setFiles(Array.isArray(r)?r:(r.files||[]))
    }catch(e){
      try{ await loadFiles() }catch(_){}
    }
  }

  const registerExternalProject=async()=>{
    if(!externalProjectAnalysis?.project_root) return

    const name = newAgentName.trim() || externalProjectAnalysis.project_root.split(/[\\/]/).filter(Boolean).pop() || 'Imported Project'

    try{
      const r=await api('/projects/create-agent',{
        method:'POST',
        body:JSON.stringify({
          name,
          project_root:externalProjectAnalysis.project_root,
          cache_path:'',
          temp_path:'',
          output_path:'',
          venv_path:'',
          models_path:''
        })
      })

      if(r.ok){
        setSelectedProjectId(r.project_id)
        setExternalProjectMode(false)
        setProjectLoadMessage(`프로젝트 #${r.project_id} DB 등록 완료`)
        setExternalProjectAnalysis(prev=>({...prev,registered:true,project_id:r.project_id}))
      }else{
        setProjectLoadMessage(r.message||'프로젝트 등록에 실패했습니다.')
      }
    }catch(e){
      setProjectLoadMessage('프로젝트 등록 실패: '+String(e))
    }
  }


  const runningBackgroundJobs=Object.values(jobs||{}).filter(job=>['QUEUED','PENDING','RUNNING','WAITING_USER'].includes(String(job?.status||'').toUpperCase()))
  const busyTerminalSessions=terminalSessions.filter(item=>item?.busy)
  const hasActiveExecution=Boolean(
    pythonExecutionState.busy
    ||sqlQueryBusy
    ||cmdExecution.busy
    ||agentBuildBusy
    ||activeWorkflowJobId
    ||busyTerminalSessions.length
    ||runningBackgroundJobs.length
  )

  const stopAllExecutions=async()=>{
    if(globalStopBusy||!hasActiveExecution) return
    setGlobalStopBusy(true)
    try{
      const actions=[]
      if(pythonExecutionState.busy){
        if(isNotebookFile(selectedEditorFileRef.current||selected||'')) actions.push(notebookEditorControllerRef.current?.stopExecution?.()||stopPythonExecution())
        else actions.push(stopPythonExecution())
      }
      if(sqlQueryBusy) actions.push(stopSqlExecution())
      if(cmdExecution.busy) actions.push(stopCurrentCmdFile())
      if(activeWorkflowJobId) actions.push(cancelAgentDevelopment())

      for(const terminalSession of busyTerminalSessions){
        try{ interruptTerminal(terminalSession.id) }catch{}
      }

      const distinctJobIds=new Set(runningBackgroundJobs.map(job=>String(job?.id||'')).filter(Boolean))
      if(activeWorkflowJobId) distinctJobIds.delete(String(activeWorkflowJobId))
      for(const jobId of distinctJobIds){
        actions.push(api(`/jobs/${encodeURIComponent(jobId)}/cancel`,{method:'POST'}).catch(()=>null))
      }
      await Promise.allSettled(actions)
    }finally{
      setGlobalStopBusy(false)
    }
  }


  const openWorkspaceCommand=(tabName)=>{
    setScreen('WORKSPACE')
    setWorkspaceTab(tabName)
  }

  const commandPaletteCommands=[
    {id:'new-agent',icon:'✦',category:'프로젝트',title:'신규 Agent 만들기',description:'새 Agent 설계 인터뷰를 시작합니다.',keywords:['새 프로젝트','에이전트 생성'],run:()=>startNewProject()},
    {id:'projects',icon:'⌘',category:'프로젝트',title:'프로젝트 열기',description:'등록된 프로젝트 목록을 엽니다.',keywords:['불러오기','프로젝트 전환'],run:()=>openProjectList()},
    {id:'design',icon:'AI',category:'워크스페이스',title:'에이전트 설계 열기',description:'현재 Agent의 요구사항 인터뷰 화면으로 이동합니다.',run:()=>openWorkspaceCommand('DESIGN')},
    {id:'workflow',icon:'◇',category:'워크스페이스',title:'워크플로우 열기',description:'현재 Agent/프로젝트 Workflow를 엽니다.',run:()=>openWorkspaceCommand('WORKFLOW')},
    {id:'code',icon:'</>',category:'워크스페이스',title:'코드 편집 열기',description:'프로젝트 코드 편집 Workspace로 이동합니다.',run:()=>openWorkspaceCommand('CODE')},
    {id:'run',icon:'▶',category:'워크스페이스',title:'실행 결과 열기',description:'Agent 개발/테스트 실행 결과를 확인합니다.',run:()=>openWorkspaceCommand('RUN')},
    {id:'report',icon:'▤',category:'워크스페이스',title:'분석 리포트 열기',description:'현재 Agent/프로젝트 분석 리포트를 확인합니다.',run:()=>openWorkspaceCommand('REPORT')},
    {id:'architecture',icon:'▱',category:'워크스페이스',title:'아키텍처 열기',description:'프로젝트 적응형 Architecture를 확인합니다.',run:()=>openWorkspaceCommand('ARCHITECTURE')},
    {id:'erd',icon:'DB',category:'데이터베이스',title:'DB ERD 열기',description:'현재 Agent/프로젝트 DB ERD를 확인합니다.',keywords:['erd','database'],run:()=>openWorkspaceCommand('DB_ERD')},
    {id:'llm',icon:'LLM',category:'워크스페이스',title:'LLM 리스트 열기',description:'LLM 사용/호출 목록 화면으로 이동합니다.',run:()=>openWorkspaceCommand('LLM')},
    {id:'browser',icon:'◎',category:'워크스페이스',title:'웹브라우저 열기',description:'AgentStudio 웹브라우저 Workspace를 엽니다.',run:()=>openWorkspaceCommand('BROWSER')},
    {id:'find-current',icon:'⌕',category:'찾기',title:'현재 파일에서 텍스트 찾기',description:'현재 편집 파일에서 문자열을 검색합니다.',keywords:['찾기','검색'],run:()=>{openWorkspaceCommand('CODE');openEditorTextSearch('CURRENT')}},
    {id:'find-project',icon:'⌕',category:'찾기',title:'프로젝트 전체 텍스트 찾기',description:'현재 프로젝트 전체 파일에서 문자열을 검색합니다.',keywords:['프로젝트 검색','전체 찾기'],run:()=>{openWorkspaceCommand('CODE');openEditorTextSearch('PROJECT')}},
    {id:'agent-ppt',icon:'PPT',category:'리포트',title:'Agent PPT 다운로드',description:'현재 Agent/로드 프로젝트 전체 PPT를 생성합니다.',disabled:!!pptExportBusy,run:()=>exportWorkspacePowerPoint('ALL','AGENT')},
    {id:'studio-ppt',icon:'PPT',category:'리포트',title:'Studio PPT 다운로드',description:'THEANOVA AgentStudio 전체 PPT를 생성합니다.',disabled:!!pptExportBusy,run:()=>exportWorkspacePowerPoint('ALL','STUDIO')},
    {id:'ui-layout',icon:'▦',category:'설계',title:'UI Layout 템플릿 선택',description:'신규 Agent의 웹/웹앱 화면 Layout Gallery를 엽니다.',run:()=>{openWorkspaceCommand('DESIGN');setUiLayoutGalleryOpen(true)}},
    {id:'redevelop',icon:'↻',category:'개발',title:'재개발 시작',description:redevelopmentInfo?.available?`실패 단계 ${redevelopmentInfo?.failure_stage||'-'} 직전부터 재개합니다.`:'재개 가능한 실패 Checkpoint가 없습니다.',disabled:!redevelopmentInfo?.available||agentBuildBusy,run:()=>startAgentDevelopment({redevelopment:true})},
    {id:'work-center',icon:'♢',category:'AgentStudio',title:'Agent 작업 센터',description:'현재/최근/실패 Agent 작업을 한 곳에서 확인합니다.',run:()=>setAgentWorkCenterOpen(true)},
    {id:'mcp',icon:'◉',category:'AgentStudio',title:'MCP 관리 열기',description:'등록된 MCP Server와 Tool을 관리합니다.',run:()=>{refreshMcp();setScreen('MCP')}},
    {id:'tools',icon:'◫',category:'AgentStudio',title:'Tool 관리 열기',description:'AgentStudio Tool 화면으로 이동합니다.',run:()=>setScreen('TOOLS')},
    {id:'help',icon:'?',category:'AgentStudio',title:'AgentStudio 사용 방법',description:'탭별 사용 방법, 단축키, 실패 복구 가이드를 엽니다.',run:()=>setUsageOpen(true)},
    {id:'system',icon:'⚙',category:'AgentStudio',title:'시스템 설정 열기',description:'AgentStudio 시스템 관리/설정 화면으로 이동합니다.',run:()=>{location.href='/system'}},
  ]


  return <div className="app studio-app ux-app">
    <header className="ux-topbar">
      <div className="brand-block" onClick={()=>setScreen('HOME')} title="THEANOVA AgentStudio 홈">
        <img
          className="brand-symbol-image"
          src="/branding/theanova-symbol.png"
          alt="THEANOVA"
          draggable="false"
        />
        <img
          className="brand-wordmark-image"
          src="/branding/theanova-wordmark.png"
          alt="THEANOVA"
          draggable="false"
        />
        <strong className="brand-product-name">AgentStudio</strong>
        <span
          className="brand-version-badge"
          title={`현재 THEANOVA AgentStudio 버전 v${AGENTSTUDIO_FRONTEND_VERSION}`}
        >
          v{AGENTSTUDIO_FRONTEND_VERSION}
        </span>
      </div>
      {hasActiveExecution&&<button
        type="button"
        className="global-execution-stop-button"
        onClick={stopAllExecutions}
        disabled={globalStopBusy}
        title="현재 AgentStudio에서 실행 중인 작업을 모두 중지"
      >■ {globalStopBusy?'정지 중…':'실행 정지'}</button>}
      <div className="project-switcher-control">
        <button
          type="button"
          className="project-switcher"
          onClick={async()=>{
            const next=!projectSwitcherOpen
            setProjectSwitcherOpen(next)
            if(next) await refreshProjectList()
          }}
          aria-expanded={projectSwitcherOpen}
        >
          <span>{currentProjectName}</span><b>⌄</b>
        </button>
        {projectSwitcherOpen&&
          <div className="project-switcher-menu">
            <div className="project-switcher-menu-head">
              <strong>프로젝트 전환</strong>
              <small>{projectList.length}개</small>
            </div>
            <button
              type="button"
              className="project-switcher-new"
              onClick={()=>{
                setProjectSwitcherOpen(false)
                startNewProject()
              }}
            >＋ 신규 Agent 만들기</button>
            <div className="project-switcher-list">
              {projectList.map(p=>
                <button
                  type="button"
                  key={p.id}
                  className={selectedProjectId===p.id?'project-switcher-item active':'project-switcher-item'}
                  onClick={async()=>{
                    setProjectSwitcherOpen(false)
                    await loadProject(p.id)
                  }}
                >
                  <span>
                    <strong>{p.name||`Project ${p.id}`}</strong>
                    <small>{p.project_root||''}</small>
                  </span>
                  {selectedProjectId===p.id&&<b>✓</b>}
                </button>
              )}
              {!projectList.length&&
                <div className="project-switcher-empty">등록된 프로젝트가 없습니다.</div>
              }
            </div>
            <button
              type="button"
              className="project-switcher-all"
              onClick={async()=>{
                setProjectSwitcherOpen(false)
                await openProjectList()
              }}
            >전체 프로젝트 보기</button>
          </div>
        }
      </div>
      <button
        type="button"
        className="global-search"
        onClick={()=>setCommandPaletteOpen(true)}
        title="전역 명령 팔레트 열기 (Ctrl + K)"
        aria-label="전역 명령 팔레트 열기"
      ><span>⌕ 명령어 검색...</span> <kbd>Ctrl + K</kbd></button>
      <div className="topbar-spacer"/>
      <div className="ai-mode-control">
        <button
          type="button"
          className="mode-pill ai-mode-button"
          onClick={async()=>{
            const next=!aiModeMenuOpen
            setAiModeMenuOpen(next)
            if(next) await refreshAiRuntimeStatus()
          }}
          aria-expanded={aiModeMenuOpen}
        >
          {aiModeHeaderLabel} <span className="ai-mode-caret">⌄</span>
        </button>

        {aiModeMenuOpen&&
          <div className="ai-mode-menu">
            <div className="ai-mode-menu-head">
              <strong>AI 실행 모드</strong>
              <button
                type="button"
                onClick={refreshAiRuntimeStatus}
                disabled={aiModeBusy}
              >↻</button>
            </div>

            <button
              type="button"
              className={aiRuntimeStatus?.mode==='auto'?'ai-mode-option active':'ai-mode-option'}
              onClick={()=>applyAiMode('auto')}
              disabled={aiModeBusy}
            >
              <span><strong>AUTO</strong><small>일반 작업 Ollama 우선 · 고난도 작업 Codex → OpenAI → Ollama</small></span>
              {aiRuntimeStatus?.mode==='auto'&&<b>✓</b>}
            </button>

            <button
              type="button"
              className={aiRuntimeStatus?.mode==='openai'?'ai-mode-option active':'ai-mode-option'}
              onClick={()=>applyAiMode('openai')}
              disabled={aiModeBusy||aiRuntimeStatus?.providers?.openai?.enabled===false||!aiRuntimeStatus?.providers?.openai?.configured}
            >
              <span>
                <strong>OpenAI · {aiRuntimeStatus?.providers?.openai?.model||'-'}</strong>
                <small>{aiRuntimeStatus?.providers?.openai?.enabled===false?'비사용 설정':aiRuntimeStatus?.providers?.openai?.configured?'API Key 설정됨':'API Key 미설정'}</small>
              </span>
              {aiRuntimeStatus?.mode==='openai'&&<b>✓</b>}
            </button>

            <button
              type="button"
              className={aiRuntimeStatus?.mode==='ollama'?'ai-mode-option active':'ai-mode-option'}
              onClick={()=>applyAiMode('ollama')}
              disabled={aiModeBusy||!aiRuntimeStatus?.providers?.ollama?.connected}
            >
              <span>
                <strong>Ollama · {aiRuntimeStatus?.providers?.ollama?.model||'-'}</strong>
                <small className={aiRuntimeStatus?.providers?.ollama?.connected?'provider-ok':'provider-bad'}>
                  {aiRuntimeStatus?.providers?.ollama?.connected?'연결됨':'연결 안됨'}
                </small>
              </span>
              {aiRuntimeStatus?.mode==='ollama'&&<b>✓</b>}
            </button>

            <button
              type="button"
              className={aiRuntimeStatus?.mode==='codex'?'ai-mode-option active':'ai-mode-option'}
              onClick={()=>applyAiMode('codex')}
              disabled={aiModeBusy||!aiRuntimeStatus?.providers?.codex?.enabled||!aiRuntimeStatus?.providers?.codex?.installed}
            >
              <span>
                <strong>Codex · ChatGPT</strong>
                <small className={aiRuntimeStatus?.providers?.codex?.connected?'provider-ok':'provider-bad'}>
                  {aiRuntimeStatus?.providers?.codex?.status||'설정 확인 필요'}
                </small>
              </span>
              {aiRuntimeStatus?.mode==='codex'&&<b>✓</b>}
            </button>

            {aiRuntimeStatus?.local_only&&<div className="hint-box ai-mode-local-only">외부 Provider 비사용 · LLM/Embedding 작업은 Ollama 로컬에서 처리됩니다.</div>}
            <div className="ai-mode-routing">
              <div><span>코딩/디버깅</span><b>{aiRuntimeStatus?.routing?.coding?.provider||'-'} · {aiRuntimeStatus?.routing?.coding?.model||'-'}</b></div>
              <div><span>요구사항</span><b>{aiRuntimeStatus?.routing?.requirements?.provider||'-'} · {aiRuntimeStatus?.routing?.requirements?.model||'-'}</b></div>
              <div><span>로컬 작업</span><b>{aiRuntimeStatus?.routing?.local?.provider||'-'} · {aiRuntimeStatus?.routing?.local?.model||'-'}</b></div>
            </div>

            {aiModeError&&<div className="ai-mode-error">{aiModeError}</div>}

            <button
              type="button"
              className="ai-mode-settings-link"
              onClick={()=>location.href='/system'}
            >AI 설정 열기
            </button>
          </div>
        }
      </div>
      <div className="external-notification-control">
        <button
          type="button"
          className={externalFileNotifications.length?'icon-btn notification-bell active':'icon-btn notification-bell'}
          onClick={()=>setExternalNotificationOpen(prev=>!prev)}
          title="외부 파일 변경 알림"
          aria-label="외부 파일 변경 알림"
        >
          🔔
          {externalFileNotifications.length>0&&
            <span className="notification-badge">
              {Math.min(externalFileNotifications.length,99)}
            </span>
          }
        </button>
        {externalNotificationOpen&&
          <div className="external-notification-menu">
            <div className="external-notification-head">
              <strong>외부 파일 변경</strong>
              <button
                type="button"
                onClick={()=>setExternalFileNotifications([])}
                disabled={!externalFileNotifications.length}
              >모두 지우기</button>
            </div>
            <div className="external-notification-list">
              {externalFileNotifications.map(item=><div
                key={item.id}
                className="external-notification-item"
              >
                <span>{item.status==='deleted'?'삭제':'수정'}</span>
                <div className="external-notification-body">
                  <strong>{item.path.split('/').pop()}</strong>
                  <small>{item.path}</small>
                  <em>
                    {item.status==='modified_conflict'
                      ? '미저장 내용과 외부 수정이 충돌했습니다.'
                      : item.status==='modified_reloaded'
                        ? '외부 수정 내용을 자동 반영했습니다.'
                        : '외부에서 파일이 삭제되었습니다.'}
                  </em>
                </div>
                <div className="external-notification-actions">
                  <button
                    type="button"
                    className="external-notification-review"
                    onClick={()=>handleExternalNotificationClick(item)}
                  >{item.status==='deleted'?'확인':'수정'}</button>
                  <button
                    type="button"
                    className="external-notification-ignore"
                    onClick={()=>handleExternalNotificationIgnore(item)}
                    title={item.status==='modified_conflict'
                      ? '외부 수정 내용을 지금은 무시하고 현재 AgentStudio 편집 내용을 유지합니다.'
                      : '이 알림을 무시합니다.'}
                  >무시</button>
                </div>
              </div>)}
              {!externalFileNotifications.length&&
                <div className="external-notification-empty">새 알림이 없습니다.</div>
              }
            </div>
          </div>
        }
      </div>
      <button className="icon-btn" onClick={()=>setUsageOpen(true)} title="AgentStudio 사용 방법" aria-label="AgentStudio 사용 방법 열기">?</button>
      <button className="icon-btn" onClick={()=>setAgentWorkCenterOpen(true)} title="Agent 작업 센터" aria-label="Agent 작업 센터 열기">♢</button>
      <button className="icon-btn" onClick={()=>location.href='/system'}>⚙</button>
      <div className="profile-block"><span className="avatar">A</span><div><strong>admin</strong><small>시스템 관리자</small></div></div>
    </header>

    <div className="ux-body">
      <aside className="ux-global-nav">
        <StudioIcon
          active={screen==='HOME'}
          onClick={()=>setScreen('HOME')}
        >⌂</StudioIcon>

        <StudioIcon
          active={screen==='WORKSPACE'&&workspaceTab==='DESIGN'}
          onClick={startNewProject}
          title="신규 Agent 설계"
        >✦</StudioIcon>

        <StudioIcon
          active={screen==='MCP'}
          onClick={()=>{
            refreshMcp()
            setScreen('MCP')
          }}
        >◉</StudioIcon>

        <StudioIcon
          active={screen==='PROJECTS'}
          onClick={async()=>{
            await refreshProjectList()
            setScreen('PROJECTS')
          }}
        >⌘</StudioIcon>

        <StudioIcon
          active={screen==='TOOLS'}
          onClick={()=>setScreen('TOOLS')}
        >◫</StudioIcon>

        <StudioIcon
          active={false}
          onClick={()=>location.href='/system'}
        >⚙</StudioIcon>

        <div className="nav-spacer"/>

        <StudioIcon
          active={false}
          onClick={()=>setUsageOpen(true)}
          title="AgentStudio 사용 방법"
        >?</StudioIcon>
      </aside>

      <div className="ux-content">
        {screen==='HOME'&&renderHomeScreen()}
        <div className={
          screen==='WORKSPACE'
            ? 'persistent-workspace-host active'
            : 'persistent-workspace-host hidden'
        }>
          {renderWorkspaceScreen()}
        </div>
        {screen==='MCP'&&renderMcpScreen()}
        {screen==='PROJECTS'&&renderProjectLibraryScreen()}
        {screen==='TOOLS'&&renderToolsScreen()}
      </div>
    </div>

    <div className="ux-statusbar">
      <span><b className="status-green">●</b> 시스템 상태 정상</span>
      <span><b className="status-green">●</b> Ollama</span>
      <span><b className="status-blue">●</b> MCP {mcpServers.length}</span>
      <span><b className="status-green">●</b> PostgreSQL</span>
      <div className="statusbar-spacer"/>
      <span>Project #{selectedProjectId||'-'}</span>
      <span>{new Date().toLocaleTimeString()}</span>
    </div>

    {mcpAddOpen&&
      <div className="mcp-add-overlay" onMouseDown={e=>{if(e.target===e.currentTarget)closeMcpAddDialog()}}>
        <div className="mcp-add-dialog" role="dialog" aria-modal="true" aria-labelledby="mcp-add-title">
          <div className="mcp-add-head">
            <div>
              <strong id="mcp-add-title">MCP 연결 추가</strong>
              <small>서버를 등록한 뒤 Tool 목록을 자동 동기화합니다.</small>
            </div>
            <button type="button" onClick={closeMcpAddDialog} disabled={mcpAddBusy}>×</button>
          </div>

          <label className="mcp-add-field">
            <span>서버 이름</span>
            <input
              value={mcpAddForm.name}
              onChange={e=>setMcpAddForm(p=>({...p,name:e.target.value}))}
              placeholder="예: GitHub MCP"
              autoFocus
            />
          </label>

          <label className="mcp-add-field">
            <span>Endpoint</span>
            <input
              value={mcpAddForm.endpoint}
              onChange={e=>setMcpAddForm(p=>({...p,endpoint:e.target.value}))}
              placeholder="예: http://127.0.0.1:8001/mcp"
            />
          </label>

          <label className="mcp-add-field">
            <span>신뢰 수준</span>
            <select
              value={mcpAddForm.trust_level}
              onChange={e=>setMcpAddForm(p=>({...p,trust_level:e.target.value}))}
            >
              <option value="UNTRUSTED">UNTRUSTED · 매 실행 확인 권장</option>
              <option value="TRUSTED">TRUSTED · 신뢰된 서버</option>
            </select>
          </label>

          <label className="mcp-add-check">
            <input
              type="checkbox"
              checked={mcpAddForm.allow_read_without_prompt}
              onChange={e=>setMcpAddForm(p=>({...p,allow_read_without_prompt:e.target.checked}))}
            />
            읽기 Tool은 별도 확인 없이 허용
          </label>

          <label className="mcp-add-check">
            <input
              type="checkbox"
              checked={mcpAddForm.allow_write_without_prompt}
              onChange={e=>setMcpAddForm(p=>({...p,allow_write_without_prompt:e.target.checked}))}
            />
            쓰기 Tool은 별도 확인 없이 허용
          </label>

          {mcpAddError&&<div className="mcp-add-error">{mcpAddError}</div>}

          <div className="mcp-add-actions">
            <button type="button" onClick={closeMcpAddDialog} disabled={mcpAddBusy}>취소</button>
            <button type="button" className="primary" onClick={submitMcpServer} disabled={mcpAddBusy}>
              {mcpAddBusy?'등록/동기화 중...':'등록하고 Tool 동기화'}
            </button>
          </div>
        </div>
      </div>
    }

    {editorCloseConfirm&&
      <div
        className="editor-unsaved-overlay"
        onMouseDown={e=>e.stopPropagation()}
      >
        <div
          className="editor-unsaved-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="editor-unsaved-title"
          onMouseDown={e=>e.stopPropagation()}
        >
          <div className="editor-unsaved-icon">!</div>
          <div className="editor-unsaved-copy">
            <h3 id="editor-unsaved-title">저장되지 않은 파일이 있습니다.</h3>
            <p>정말 닫겠습니까?</p>
            <small>저장되지 않은 파일 {editorCloseConfirm.dirtyPaths.length}개</small>
            {editorCloseConfirm.error&&
              <div className="editor-unsaved-error">
                {editorCloseConfirm.error}
              </div>
            }
          </div>
          <div className="editor-unsaved-actions">
            <button
              type="button"
              className="primary"
              disabled={editorCloseConfirm.saving}
              onClick={()=>handleEditorCloseDecision('save')}
            >
              {editorCloseConfirm.saving?'저장 중...':'저장하고 닫기'}
            </button>
            <button
              type="button"
              className="danger"
              disabled={editorCloseConfirm.saving}
              onClick={()=>handleEditorCloseDecision('discard')}
            >
              저장 안하고 닫기
            </button>
            <button
              type="button"
              disabled={editorCloseConfirm.saving}
              onClick={()=>handleEditorCloseDecision('cancel')}
            >
              취소
            </button>
          </div>
        </div>
      </div>
    }

    {fileDeleteConfirm&&
      <div className="editor-unsaved-overlay" onMouseDown={e=>e.stopPropagation()}>
        <div className="editor-unsaved-dialog" role="dialog" aria-modal="true" onMouseDown={e=>e.stopPropagation()}>
          <div className="editor-unsaved-icon danger">!</div>
          <div className="editor-unsaved-copy">
            <h3>정말 삭제하시겠습니까?</h3>
            <p>선택한 파일 {fileDeleteConfirm.paths.length}개를 실제 디스크에서 삭제합니다.</p>
            {fileDeleteConfirm.dirtyCount>0&&
              <small>저장되지 않은 파일 {fileDeleteConfirm.dirtyCount}개도 함께 삭제됩니다.</small>
            }
            {fileDeleteConfirm.error&&<div className="editor-unsaved-error">{fileDeleteConfirm.error}</div>}
          </div>
          <div className="editor-unsaved-actions">
            <button
              type="button"
              className="danger"
              disabled={fileDeleteConfirm.deleting}
              onClick={confirmProjectFilesDelete}
            >{fileDeleteConfirm.deleting?'삭제 중...':'OK'}</button>
            <button
              type="button"
              disabled={fileDeleteConfirm.deleting}
              onClick={()=>setFileDeleteConfirm(null)}
            >취소</button>
          </div>
        </div>
      </div>
    }

    {externalChangeConfirm&&
      <div className="editor-unsaved-overlay" onMouseDown={e=>e.stopPropagation()}>
        <div className="editor-unsaved-dialog" role="dialog" aria-modal="true" onMouseDown={e=>e.stopPropagation()}>
          <div className="editor-unsaved-icon">↻</div>
          <div className="editor-unsaved-copy">
            <h3>외부에서 수정이 되었습니다.</h3>
            {externalChangeConfirm.mode==='save_conflict'
              ? <p>외부 파일과 현재 AgentStudio의 내용이 다릅니다. 어떻게 처리하시겠습니까?</p>
              : <p>수정된 외부 파일 로드하시겠습니까?</p>
            }
            <small>{externalChangeConfirm.path}</small>
            <small className="external-change-warning">
              {externalChangeConfirm.mode==='save_conflict'
                ? '외부 파일 무시하고 저장을 선택하면 현재 AgentStudio 내용으로 디스크 파일을 덮어씁니다.'
                : '외부 파일 로드를 선택하면 현재 AgentStudio에서 저장하지 않은 수정 내용은 사라집니다.'
              }
            </small>
            {externalChangeConfirm.error&&<div className="editor-unsaved-error">{externalChangeConfirm.error}</div>}
          </div>
          <div className="editor-unsaved-actions">
            <button
              type="button"
              className="primary"
              disabled={externalChangeConfirm.loading}
              onClick={()=>handleExternalChangeDecision('load_external')}
            >{externalChangeConfirm.loading&&externalChangeConfirm.loadingAction==='load_external'?'로드 중...':'외부 파일 로드'}</button>
            {externalChangeConfirm.mode==='save_conflict'&&
              <button
                type="button"
                className="danger"
                disabled={externalChangeConfirm.loading}
                onClick={()=>handleExternalChangeDecision('force_save')}
              >{externalChangeConfirm.loading&&externalChangeConfirm.loadingAction==='force_save'?'저장 중...':'외부 파일 무시하고 저장'}</button>
            }
            <button
              type="button"
              disabled={externalChangeConfirm.loading}
              onClick={()=>handleExternalChangeDecision('cancel')}
            >취소</button>
          </div>
        </div>
      </div>
    }

    {projectListOpen&&<div className="project-list-overlay" onClick={()=>setProjectListOpen(false)}>
      <div className="project-list-dialog redesigned" onClick={e=>e.stopPropagation()}>
        <div className="project-list-head">
          <div><span className="eyebrow">PROJECT LIBRARY</span><h2>프로젝트 불러오기</h2>
        {projectLoadProgress.active&&<div className={projectLoadProgress.failed?'project-load-progress modal failed':'project-load-progress modal'}>
          <div className="project-load-progress-head">
            <strong>{projectLoadProgress.message}</strong>
            <span>{projectLoadProgress.percent}%</span>
          </div>
          <div className="project-load-progress-track">
            <div className="project-load-progress-fill" style={{width:`${projectLoadProgress.percent}%`}} />
          </div>
        </div>}<p>저장된 프로젝트를 선택하면 바로 작업공간으로 이동합니다.</p></div>
          <button onClick={()=>setProjectListOpen(false)}>✕</button>
        </div>
        
        <div className="external-project-import">
          <div className="external-import-head">
            <div>
              <strong>DB에 없는 기존 프로젝트 분석</strong>
              <small>저장되지 않은 프로젝트도 폴더를 지정하면 바로 분석하고 열 수 있습니다.</small>
            </div>
          </div>

          <div className="external-path-row">
            <input
              value={externalProjectPath}
              onChange={e=>setExternalProjectPath(e.target.value)}
              placeholder="분석할 기존 프로젝트 경로"
            />
            <button
              type="button"
              className={
                externalProjectPickerLoading
                  ? 'external-path-picker-button busy'
                  : 'external-path-picker-button'
              }
              disabled={externalProjectPickerLoading}
              onClick={pickExternalProjectFolder}
              title="Windows 폴더 선택창 열기"
            >
              {externalProjectPickerLoading?'선택창 여는 중...':'경로 찾기'}
            </button>
            <button
              className="primary-install"
              disabled={externalProjectLoading||!externalProjectPath.trim()}
              onClick={analyzeExternalProject}
            >
              {externalProjectLoading?`${Math.round(externalProjectProgress||0)}% 분석 중...`:'프로젝트 분석'}
            </button>
          </div>

          {externalProjectPickerMessage&&
            <div className={
              externalProjectPickerMessage.startsWith('경로 선택 실패')
                ? 'external-path-picker-message error'
                : 'external-path-picker-message'
            }>
              {externalProjectPickerMessage}
            </div>}

          {(externalProjectLoading||externalProjectStatus)&&<div className={
            externalProjectStatus==='SUCCESS'
              ?'external-progress-box success'
              :externalProjectStatus==='FAILED'
                ?'external-progress-box failed'
                :'external-progress-box running'
          }>
            <div className="external-progress-head">
              <strong>
                {externalProjectStatus==='SUCCESS'
                  ?'분석 완료'
                  :externalProjectStatus==='FAILED'
                    ?'분석 실패'
                    :'프로젝트 분석 중'}
              </strong>
              <b>{Math.round(externalProjectProgress||0)}%</b>
            </div>

            <progress
              max="100"
              value={externalProjectProgress||0}
            />

            <div className="external-progress-step">
              {externalProjectStep||'분석 준비 중...'}
            </div>

            <div className="external-progress-stages">
              <span className={(externalProjectProgress||0)>=5?'done':''}>경로 확인</span>
              <span className={(externalProjectProgress||0)>=15?'done':''}>파일 스캔</span>
              <span className={(externalProjectProgress||0)>=40?'done':''}>소스 분석</span>
              <span className={(externalProjectProgress||0)>=82?'done':''}>DB 저장</span>
              <span className={(externalProjectProgress||0)>=100?'done':''}>완료</span>
            </div>

            {externalProjectStatus==='SUCCESS'&&
              <div className="auto-move-note">
                DB 저장이 완료되었습니다. 작업공간으로 자동 이동합니다.
              </div>}
          </div>}

          {externalProjectStatus==='FAILED'&&externalProjectAnalysis?.ok===false&&
            <div className="external-failure-detail">
              <div className="failure-title">분석 실패 상세</div>
              <div className="failure-message">
                {externalProjectAnalysis.message||externalProjectStep}
              </div>

              <div className="failure-label">로그 파일 전체 경로</div>
              <code className="failure-log-path">
                {externalProjectAnalysis.log_path||'로그 파일 저장에 실패했습니다.'}
              </code>

              {externalProjectAnalysis.traceback&&<details>
                <summary>상세 Traceback 보기</summary>
                <pre>{externalProjectAnalysis.traceback}</pre>
              </details>}
            </div>}

          {externalProjectAnalysis&&externalProjectAnalysis.ok!==false&&<div className="external-analysis-result">
            <div className="external-analysis-title">
              <div>
                <strong>{newAgentName||'기존 프로젝트'}</strong>
                <code>{externalProjectAnalysis.project_root}</code>
              </div>
              <span className="unregistered-chip">
                {externalProjectAnalysis.registered?'DB 등록됨':'DB 미등록'}
              </span>
            </div>

            {externalProjectAnalysis.summary&&<div className="external-summary-box">
              <div><b>프로젝트 요약</b></div>
              <pre>{typeof externalProjectAnalysis.summary==='string'
                ? externalProjectAnalysis.summary
                : JSON.stringify(externalProjectAnalysis.summary,null,2)}</pre>
            </div>}

            <div className="external-analysis-actions">
              <button className="hero-primary" onClick={openExternalProjectWorkspace}>
                분석 결과로 프로젝트 열기
              </button>
              {!externalProjectAnalysis.registered&&
                <button onClick={registerExternalProject}>이 프로젝트를 DB에 등록</button>}
            </div>
          </div>}
        </div>

        {projectListLoading&&<div className="project-list-empty">프로젝트 목록을 불러오는 중...</div>}
        {!projectListLoading&&projectList.length===0&&<div className="project-list-empty">저장된 프로젝트가 없습니다.<br/><button onClick={()=>{setProjectListOpen(false);startNewProject()}}>첫 프로젝트 만들기</button></div>}
        {!projectListLoading&&projectList.length>0&&<div className="project-list-items">
          {projectList.map(p=><button key={p.id} className="project-list-item" onClick={()=>loadProject(p.id)}>
            <div className="project-list-title"><strong>{p.name}</strong><span>#{p.id}</span></div>
            <div className="project-list-path">{p.project_root}</div>
            <div className="project-list-meta">
              <span>Cache {p.cache_path?'✓':'-'}</span><span>Models {p.models_path?'✓':'-'}</span>
            </div>
          </button>)}
        </div>}
      </div>
    </div>}

    <GlobalCommandPalette
      open={commandPaletteOpen}
      onClose={()=>setCommandPaletteOpen(false)}
      commands={commandPaletteCommands}
    />

    <AgentWorkCenterPanel
      open={agentWorkCenterOpen}
      onClose={()=>setAgentWorkCenterOpen(false)}
      jobs={jobs}
      developmentProgress={developmentProgress}
      workflowProgress={workflowProgress}
      redevelopmentInfo={redevelopmentInfo}
      onOpenRun={()=>{setAgentWorkCenterOpen(false);openWorkspaceCommand('RUN')}}
      onRedevelop={()=>{setAgentWorkCenterOpen(false);startAgentDevelopment({redevelopment:true})}}
      onCancelJob={(jobId)=>api(`/jobs/${encodeURIComponent(jobId)}/cancel`,{method:'POST'}).catch(()=>null)}
    />

    <HelpCenterPanel
      open={usageOpen}
      onClose={()=>setUsageOpen(false)}
      onStartNewAgent={()=>{setUsageOpen(false);startNewProject()}}
      onOpenCommandPalette={()=>{setUsageOpen(false);setCommandPaletteOpen(true)}}
    />

  </div>
}
export default function App(){return location.pathname.startsWith('/system')?<SystemPage/>:<IDE/>}
