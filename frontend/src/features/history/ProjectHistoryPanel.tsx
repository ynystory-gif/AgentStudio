import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../../api'
import { asLegacyError } from '../../utils/errors'
import './projectHistory.css'

type HistoryItem={
  id:number
  project_setting_histories_id?:number
  category:string
  action:string
  title:string
  summary:string
  project_root:string
  created_at:string
  before?:Record<string,unknown>
  after?:Record<string,unknown>
}

interface ProjectHistoryPanelProps{projectRoot:string}

const CATEGORY_LABEL:Record<string,string>={
  AGENT_DESIGN:'Agent 설계',REQUIREMENTS:'요구사항',REQUIREMENTS_OVERRIDE:'요구사항 수정',RUNTIME:'실행 환경',DATABASE:'Database',DATABASE_RESOURCE_PLAN:'DB Resource Plan',
  CODE_EDITOR_DB:'코드 편집 DB',RAG:'RAG',RAG_KNOWLEDGE:'RAG Knowledge',RAG_RETRIEVAL:'RAG Retrieval',RAG_INTELLIGENCE:'RAG Intelligence',UI_LAYOUT:'UI / Layout',TOOL_PROMPT:'Tool / Prompt',PROMPT_TOOL_STUDIO:'Prompt & Tool Studio',DEVELOPMENT_STAGE:'개발 Stage',RECOMMENDATION:'AI 추천',CODING_STYLE:'코딩 스타일',CODE_DOCUMENTATION:'코드 문서화',GENERAL:'기타',
}

function fmt(value:string):string{
  if(!value)return '-'
  const date=new Date(value)
  return Number.isNaN(date.getTime())?value:date.toLocaleString()
}
function pretty(value:unknown):string{return JSON.stringify(value??{},null,2)}

export function ProjectHistoryPanel({projectRoot}:ProjectHistoryPanelProps){
  const [items,setItems]=useState<HistoryItem[]>([])
  const [selectedId,setSelectedId]=useState<number|null>(null)
  const [detail,setDetail]=useState<HistoryItem|null>(null)
  const [filter,setFilter]=useState('ALL')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const projectReady=Boolean(String(projectRoot||'').trim())

  const load=async()=>{
    if(!projectReady){setItems([]);setSelectedId(null);setDetail(null);return}
    setBusy(true);setError('')
    try{
      const result=await api<{items:HistoryItem[]}>(`/account-settings/history?project_root=${encodeURIComponent(projectRoot)}&limit=200`)
      const next=Array.isArray(result?.items)?result.items:[]
      setItems(next)
      const firstItem=next[0]
      if(firstItem&&!selectedId)setSelectedId(firstItem.id)
    }catch(exc){setError(asLegacyError(exc).message||String(exc))}
    finally{setBusy(false)}
  }

  useEffect(()=>{void load()},[projectRoot])
  useEffect(()=>{
    let cancelled=false
    if(!selectedId){setDetail(null);return}
    api<{item:HistoryItem}>(`/account-settings/history/${selectedId}`).then((result)=>{if(!cancelled)setDetail(result.item||null)}).catch((exc)=>{if(!cancelled)setError(asLegacyError(exc).message||String(exc))})
    return()=>{cancelled=true}
  },[selectedId])

  const categories=useMemo(()=>Array.from(new Set(items.map((item)=>item.category).filter(Boolean))),[items])
  const visible=useMemo(()=>filter==='ALL'?items:items.filter((item)=>item.category===filter),[items,filter])

  return <section className="project-history-panel">
    <header className="project-history-head">
      <div><strong>프로젝트 수정 이력</strong><small>요구사항 · Database · RAG · Runtime · UI · Tool/Prompt 등 프로젝트 설정 변경을 계정 기준으로 기록합니다.</small></div>
      <button type="button" onClick={()=>void load()} disabled={busy||!projectReady}>{busy?'새로고침 중...':'새로고침'}</button>
    </header>
    {!projectReady&&<div className="project-history-empty">프로젝트 경로를 먼저 설정하면 수정 이력이 프로젝트별로 저장됩니다.</div>}
    {error&&<div className="project-history-error">{error}</div>}
    {projectReady&&<div className="project-history-toolbar">
      <span>총 {items.length}건</span>
      <select value={filter} onChange={(e)=>setFilter(e.target.value)}>
        <option value="ALL">전체 분류</option>
        {categories.map((category)=><option key={category} value={category}>{CATEGORY_LABEL[category]||category}</option>)}
      </select>
    </div>}
    {projectReady&&<div className="project-history-layout">
      <div className="project-history-list">
        {visible.length===0?<div className="project-history-empty">아직 저장된 수정 이력이 없습니다.</div>:visible.map((item)=><button type="button" key={item.id} className={selectedId===item.id?'active':''} onClick={()=>setSelectedId(item.id)}>
          <div><span>{CATEGORY_LABEL[item.category]||item.category}</span><em>{item.action}</em></div>
          <strong>{item.title||'설정 변경'}</strong>
          {item.summary&&<small>{item.summary}</small>}
          <time>{fmt(item.created_at)}</time>
        </button>)}
      </div>
      <div className="project-history-detail">
        {!detail?<div className="project-history-empty">왼쪽 이력을 선택하면 상세 변경 내용을 확인할 수 있습니다.</div>:<>
          <header><div><span>{CATEGORY_LABEL[detail.category]||detail.category}</span><em>{detail.action}</em></div><strong>{detail.title}</strong><small>{fmt(detail.created_at)}</small></header>
          {detail.summary&&<p>{detail.summary}</p>}
          <div className="project-history-diff">
            <section><h4>변경 전</h4><pre>{pretty(detail.before)}</pre></section>
            <section><h4>변경 후</h4><pre>{pretty(detail.after)}</pre></section>
          </div>
        </>}
      </div>
    </div>}
  </section>
}
