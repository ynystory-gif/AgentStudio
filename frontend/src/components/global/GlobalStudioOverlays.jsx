import React, { useEffect, useMemo, useRef, useState } from 'react'

const statusLabel=(value='')=>{
  const key=String(value||'').toUpperCase()
  if(['SUCCESS','COMPLETED','DONE'].includes(key)) return '성공'
  if(['FAILED','ERROR','REPAIR_PLAN_INCOMPLETE','TEST_FAILED','TEST_REPAIR_PLAN_INCOMPLETE'].includes(key)) return '실패'
  if(['CANCELLED','CANCELED'].includes(key)) return '중단'
  if(['QUEUED','PENDING'].includes(key)) return '대기'
  if(['RUNNING','WAITING_USER'].includes(key)) return '실행 중'
  return value||'대기'
}

export function GlobalCommandPalette({open,onClose,commands=[]}){
  const [query,setQuery]=useState('')
  const [selectedIndex,setSelectedIndex]=useState(0)
  const inputRef=useRef(null)
  const filtered=useMemo(()=>{
    const needle=query.trim().toLowerCase()
    const source=Array.isArray(commands)?commands:[]
    if(!needle) return source
    return source.filter(command=>[
      command.title,command.description,command.category,...(command.keywords||[])
    ].join(' ').toLowerCase().includes(needle))
  },[commands,query])

  useEffect(()=>{
    if(!open) return
    setQuery('')
    setSelectedIndex(0)
    const timer=window.setTimeout(()=>inputRef.current?.focus?.(),0)
    return()=>window.clearTimeout(timer)
  },[open])

  useEffect(()=>{
    if(selectedIndex<filtered.length) return
    setSelectedIndex(Math.max(0,filtered.length-1))
  },[filtered.length,selectedIndex])

  if(!open) return null
  const runCommand=(command)=>{
    if(!command||command.disabled) return
    onClose?.()
    window.setTimeout(()=>command.run?.(),0)
  }
  return <div className="studio-overlay command-palette-overlay" onMouseDown={event=>{if(event.target===event.currentTarget) onClose?.()}}>
    <div className="command-palette" role="dialog" aria-modal="true" aria-label="전역 명령 팔레트">
      <div className="command-palette-search">
        <span>⌕</span>
        <input
          ref={inputRef}
          value={query}
          onChange={event=>{setQuery(event.target.value);setSelectedIndex(0)}}
          onKeyDown={event=>{
            if(event.key==='ArrowDown'){event.preventDefault();setSelectedIndex(index=>Math.min(filtered.length-1,index+1))}
            if(event.key==='ArrowUp'){event.preventDefault();setSelectedIndex(index=>Math.max(0,index-1))}
            if(event.key==='Enter'){event.preventDefault();runCommand(filtered[selectedIndex])}
            if(event.key==='Escape'){event.preventDefault();onClose?.()}
          }}
          placeholder="AgentStudio 명령 검색..."
          spellCheck={false}
        />
        <kbd>Esc</kbd>
      </div>
      <div className="command-palette-caption">명령 이름이나 기능을 입력하세요. ↑↓ 이동 · Enter 실행</div>
      <div className="command-palette-list">
        {filtered.map((command,index)=><button
          type="button"
          key={command.id}
          className={`command-palette-item ${selectedIndex===index?'selected':''}`}
          onMouseEnter={()=>setSelectedIndex(index)}
          onClick={()=>runCommand(command)}
          disabled={command.disabled}
        >
          <span className="command-palette-icon">{command.icon||'›'}</span>
          <span className="command-palette-copy"><strong>{command.title}</strong><small>{command.description||''}</small></span>
          <span className="command-palette-category">{command.category||''}</span>
        </button>)}
        {!filtered.length&&<div className="command-palette-empty">일치하는 명령이 없습니다.</div>}
      </div>
    </div>
  </div>
}

export function AgentWorkCenterPanel({open,onClose,jobs={},developmentProgress,workflowProgress,redevelopmentInfo,onOpenRun,onRedevelop,onCancelJob}){
  const [tab,setTab]=useState('CURRENT')
  if(!open) return null
  const all=Object.values(jobs||{}).filter(Boolean).sort((a,b)=>String(b.updated_at||b.created_at||b.id||'').localeCompare(String(a.updated_at||a.created_at||a.id||''))).slice(0,20)
  const active=all.filter(job=>['QUEUED','PENDING','RUNNING','WAITING_USER'].includes(String(job.status||'').toUpperCase()))
  const failed=all.filter(job=>['FAILED','ERROR','REPAIR_PLAN_INCOMPLETE','TEST_FAILED','TEST_REPAIR_PLAN_INCOMPLETE'].includes(String(job.status||'').toUpperCase()))
  const visible=tab==='CURRENT'?active:tab==='FAILED'?failed:all
  return <div className="studio-side-overlay" onMouseDown={event=>{if(event.target===event.currentTarget) onClose?.()}}>
    <aside className="studio-side-panel agent-work-center" role="dialog" aria-modal="true" aria-label="Agent 작업 센터">
      <div className="studio-side-head">
        <div><span className="eyebrow">AGENT WORK CENTER</span><h2>Agent 작업 센터</h2><p>현재 실행, 최근 작업, 실패 복구를 한 곳에서 확인합니다.</p></div>
        <button type="button" onClick={onClose}>✕</button>
      </div>
      <div className="work-center-summary-grid">
        <div><span>Agent 개발</span><strong>{developmentProgress?.active?'실행 중':statusLabel(developmentProgress?.status||'대기')}</strong><small>{developmentProgress?.stage||'대기'} · {Math.round(Number(developmentProgress?.percent||0))}%</small></div>
        <div><span>Workflow</span><strong>{workflowProgress?.active?'실행 중':'대기'}</strong><small>{workflowProgress?.stage||'대기'} · {Math.round(Number(workflowProgress?.percent||0))}%</small></div>
        <div><span>Background</span><strong>{active.length}개</strong><small>최근 작업 {all.length}개 보관</small></div>
      </div>
      {redevelopmentInfo?.available&&<div className="work-center-recovery">
        <strong>재개 가능한 실패 기록</strong>
        <span>{redevelopmentInfo?.status||'FAILED'} · 실패 {redevelopmentInfo?.failure_stage||'-'} · 재개 {redevelopmentInfo?.resume_from_node||'-'}</span>
        <button type="button" onClick={onRedevelop}>↻ 재개발 시작</button>
      </div>}
      <div className="work-center-tabs">
        <button className={tab==='CURRENT'?'active':''} onClick={()=>setTab('CURRENT')}>현재 작업 {active.length}</button>
        <button className={tab==='RECENT'?'active':''} onClick={()=>setTab('RECENT')}>최근 작업 {all.length}</button>
        <button className={tab==='FAILED'?'active':''} onClick={()=>setTab('FAILED')}>실패/복구 {failed.length}</button>
      </div>
      <div className="work-center-list">
        {visible.map(job=><div className="work-center-job" key={job.id}>
          <div className="work-center-job-head"><strong>{job.message||job.name||job.type||'Agent 작업'}</strong><span className={`job-status ${String(job.status||'').toLowerCase()}`}>{statusLabel(job.status)}</span></div>
          <div className="work-center-progress"><i style={{width:`${Math.max(0,Math.min(100,Number(job.progress||0)))}%`}}/></div>
          <small>ID {job.id||'-'} · {Math.round(Number(job.progress||0))}%{job.last_node?` · ${job.last_node}`:''}</small>
          <div className="work-center-job-actions">
            <button type="button" onClick={onOpenRun}>실행 결과</button>
            {['QUEUED','PENDING','RUNNING','WAITING_USER'].includes(String(job.status||'').toUpperCase())&&<button type="button" onClick={()=>onCancelJob?.(job.id)}>중지</button>}
          </div>
        </div>)}
        {!visible.length&&<div className="work-center-empty">표시할 작업이 없습니다.</div>}
      </div>
    </aside>
  </div>
}

const HELP_ARTICLES=[
  {id:'start',category:'시작하기',title:'AgentStudio 시작하기',keywords:'신규 agent 프로젝트',body:'신규 Agent 만들기에서 목적을 설명하면 요구사항을 한 번에 하나씩 수집합니다. 프로젝트 이름과 경로를 지정한 뒤 설계 검토 → 프로젝트 생성 → 개발 시작 순서로 진행합니다.'},
  {id:'tabs',category:'탭별 사용법',title:'워크스페이스 탭',keywords:'워크플로우 코드 실행 분석 아키텍처 erd 스케줄러 scheduler llm 브라우저',body:'에이전트 설계, 워크플로우, 코드 편집, 실행 결과, 분석 리포트, 아키텍처, DB ERD, 스케줄러, LLM 리스트, 웹브라우저 탭을 프로젝트 상태에 맞게 사용할 수 있습니다.'},
  {id:'attachment',category:'자주 쓰는 작업',title:'첨부 파일 분석',keywords:'참고 파일 ipynb pdf csv 요구사항',body:'첨부 파일은 안전한 Context로 분석합니다. AI가 추출한 요구사항은 첨부 파일 AI 정리에서 확인할 수 있고 원문/긴 코드는 대화창에 그대로 노출하지 않습니다.'},
  {id:'redevelop',category:'문제 해결',title:'개발 실패 후 재개발',keywords:'실패 복구 재개 checkpoint',body:'실패 Checkpoint가 있는 프로젝트를 선택하면 재개발 시작 버튼이 활성화됩니다. 요구사항부터 다시 시작하지 않고 실패 직전 검증 단계부터 수정된 소스를 재검증합니다.'},
  {id:'ppt',category:'리포트',title:'Agent PPT와 Studio PPT',keywords:'ppt powerpoint erd',body:'Agent PPT는 현재 Agent/로드 프로젝트만 포함합니다. Studio PPT는 THEANOVA AgentStudio 자체 자료만 포함하며 각각 DB ERD도 해당 범위에 맞게 포함됩니다.'},
  {id:'shortcuts',category:'단축키',title:'주요 단축키',keywords:'ctrl k esc 찾기',body:'Ctrl + K는 전역 명령 팔레트를 엽니다. Esc는 열린 전역 패널을 닫습니다. 코드 편집의 찾기 버튼에서는 현재 파일/프로젝트 전체 텍스트 검색을 전환할 수 있습니다.'},
  {id:'notebook',category:'문제 해결',title:'Notebook 실행',keywords:'jupyter 셀 실행 프로젝트 경로',body:'Notebook 셀은 열린 파일의 프로젝트 Root를 기준으로 실행됩니다. 프로젝트 선택이 비어 있어도 프로젝트 파일 트리에서 연 Notebook이면 파일 트리 Root를 자동 사용합니다.'},
]

export function HelpCenterPanel({open,onClose,onStartNewAgent,onOpenCommandPalette}){
  const [query,setQuery]=useState('')
  if(!open) return null
  const needle=query.trim().toLowerCase()
  const articles=HELP_ARTICLES.filter(article=>!needle||`${article.category} ${article.title} ${article.keywords} ${article.body}`.toLowerCase().includes(needle))
  return <div className="studio-side-overlay" onMouseDown={event=>{if(event.target===event.currentTarget) onClose?.()}}>
    <aside className="studio-side-panel help-center-panel" role="dialog" aria-modal="true" aria-label="AgentStudio 사용 방법">
      <div className="studio-side-head">
        <div><span className="eyebrow">HELP CENTER</span><h2>AgentStudio 사용 방법</h2><p>기능, 단축키, 실패 복구 방법을 검색할 수 있습니다.</p></div>
        <button type="button" onClick={onClose}>✕</button>
      </div>
      <div className="help-search"><span>⌕</span><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="예: 재개발, PPT, ERD, 첨부파일" autoFocus/></div>
      <div className="help-quick-actions">
        <button type="button" onClick={onOpenCommandPalette}>Ctrl + K 명령 팔레트</button>
        <button type="button" onClick={onStartNewAgent}>＋ 신규 Agent 시작</button>
      </div>
      <div className="help-article-list">
        {articles.map(article=><article key={article.id} className="help-article">
          <span>{article.category}</span><h3>{article.title}</h3><p>{article.body}</p>
        </article>)}
        {!articles.length&&<div className="work-center-empty">검색 결과가 없습니다.</div>}
      </div>
    </aside>
  </div>
}
