import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../../api'

const statusLabel=(value='')=>({
  DRAFT:'초안',
  INTERVIEWING:'설계 인터뷰',
  REQUIREMENTS_REVIEW:'요구사항 검토',
  DESIGNING:'설계 중',
  READY_TO_GENERATE:'생성 준비 완료',
  GENERATING:'생성 중',
  GENERATION_PAUSED:'생성 일시중지',
  GENERATED:'생성 완료',
  FAILED:'실패',
  ARCHIVED:'보관',
}[String(value||'').toUpperCase()]||value||'초안')

const formatDate=(value='')=>{
  if(!value) return '-'
  const date=new Date(value)
  return Number.isNaN(date.getTime())?String(value):date.toLocaleString()
}

const normalizeName=(value='')=>String(value||'').trim().toLowerCase().replace(/\s+/g,' ')

const featureImpact=(name='')=>{
  const text=normalizeName(name)
  const areas=new Set(['Agent Workflow','테스트 시나리오'])
  if(/회원|로그인|인증|권한|role|permission|rbac/.test(text)){
    ;['Auth/RBAC','사용자 UI','API','DB','권한별 테스트 계정'].forEach(v=>areas.add(v))
  }
  if(/상품|검색|추천|재고|catalog|product|search/.test(text)){
    ;['사용자 UI','관리자 UI','API','DB','검색/Vector/Cache','테스트 데이터'].forEach(v=>areas.add(v))
  }
  if(/주문|장바구니|결제|order|cart|payment/.test(text)){
    ;['사용자 UI','API','DB','주문 Workflow','테스트 주문 데이터'].forEach(v=>areas.add(v))
  }
  if(/rag|문서|파일|지식|embedding|벡터/.test(text)){
    ;['RAG/pgvector','Ingestion','API','DB','테스트 문서/Chunk'].forEach(v=>areas.add(v))
  }
  if(/관리자|admin/.test(text)){
    ;['관리자 UI','권한','API'].forEach(v=>areas.add(v))
  }
  if(areas.size<=2){
    ;['UI','API','관련 DB/설정'].forEach(v=>areas.add(v))
  }
  return Array.from(areas)
}

export function AgentDesignProjectToolbar({
  designProjectId=null,
  projectName='',
  savedAt='',
  status='INTERVIEWING',
  progress=0,
  onNew,
  onSave,
  onLoad,
}){
  const [listOpen,setListOpen]=useState(false)
  const [loading,setLoading]=useState(false)
  const [rows,setRows]=useState([])
  const [error,setError]=useState('')

  const loadList=async()=>{
    setLoading(true)
    setError('')
    try{
      const result=await api('/agent-design-projects')
      setRows(Array.isArray(result?.projects)?result.projects:[])
    }catch(e){
      setRows([])
      setError(String(e?.message||e))
    }finally{
      setLoading(false)
    }
  }

  useEffect(()=>{
    if(listOpen) void loadList()
  },[listOpen])

  return <>
    <div className="agent-design-project-toolbar">
      <div className="agent-design-project-identity">
        <span>설계 프로젝트</span>
        <strong>{projectName||'이름 미정'}</strong>
        <small>{designProjectId?`#${designProjectId} · ${statusLabel(status)} · ${Math.max(0,Math.min(100,Number(progress)||0))}%`:'아직 DB에 저장되지 않음'}</small>
      </div>
      <div className="agent-design-project-actions">
        <button type="button" className="agent-design-new-button" onClick={onNew}>＋ 새 프로젝트</button>
        <button type="button" className="primary agent-design-save-button" onClick={onSave}>💾 프로젝트 저장</button>
        <button type="button" className="agent-design-load-button" onClick={()=>setListOpen(true)}>📂 프로젝트 로드</button>
        <span className="agent-design-save-state">{savedAt?`✓ 저장됨 ${formatDate(savedAt)}`:'저장 대기'}</span>
      </div>
    </div>

    {listOpen&&<div className="agent-design-modal-backdrop" onMouseDown={()=>setListOpen(false)}>
      <div className="agent-design-project-modal" onMouseDown={e=>e.stopPropagation()}>
        <div className="agent-design-modal-head">
          <div><strong>Agent 설계 프로젝트 목록</strong><small>저장한 프로젝트를 선택하면 중단했던 설계 인터뷰와 Workflow 상태부터 이어서 진행합니다.</small></div>
          <button type="button" onClick={()=>setListOpen(false)}>✕</button>
        </div>
        <div className="agent-design-project-list-toolbar">
          <button type="button" onClick={loadList} disabled={loading}>↻ 새로고침</button>
          <span>{loading?'불러오는 중...':`${rows.length}개 프로젝트`}</span>
        </div>
        {error&&<div className="agent-design-project-error">{error}</div>}
        <div className="agent-design-project-list">
          {rows.map(row=><button
            key={row.id}
            type="button"
            className={`agent-design-project-row ${Number(designProjectId)===Number(row.id)?'current':''}`}
            onClick={async()=>{
              try{
                const result=await api(`/agent-design-projects/${row.id}`)
                if(result?.project){
                  await onLoad?.(result.project)
                  setListOpen(false)
                }
              }catch(e){ setError(String(e?.message||e)) }
            }}
          >
            <span className="agent-design-project-main"><strong>{row.name||`설계 프로젝트 #${row.id}`}</strong><small>{row.project_root||'생성 경로 미정'}</small></span>
            <span className="agent-design-project-meta"><b>{statusLabel(row.status)}</b><i>{Number(row.progress)||0}%</i><small>{formatDate(row.updated_at)}</small></span>
          </button>)}
          {!loading&&!rows.length&&<div className="agent-design-project-empty">저장된 Agent 설계 프로젝트가 없습니다.</div>}
        </div>
      </div>
    </div>}
  </>
}

export function AgentFeatureManager({detectedFeatures=[],features=[],onChange}){
  const [editing,setEditing]=useState(null)
  const [name,setName]=useState('')
  const [description,setDescription]=useState('')

  const merged=useMemo(()=>{
    const map=new Map()
    for(const raw of detectedFeatures||[]){
      const featureName=String(raw||'').trim()
      if(!featureName) continue
      map.set(normalizeName(featureName),{
        id:`detected:${normalizeName(featureName)}`,
        name:featureName,
        description:'설계 인터뷰에서 감지된 기존 기능',
        status:'ACTIVE',
        source:'DISCOVERED',
        change_type:'BASE',
      })
    }
    for(const item of features||[]){
      const featureName=String(item?.name||'').trim()
      if(!featureName) continue
      const originalName=String(item?.original_name||'').trim()
      if(originalName&&normalizeName(originalName)!==normalizeName(featureName)){
        map.delete(normalizeName(originalName))
      }
      map.set(normalizeName(featureName),{...item,name:featureName,source:item?.source||'MANUAL'})
    }
    return Array.from(map.values())
  },[detectedFeatures,features])

  const openAdd=()=>{
    setEditing({mode:'ADD'})
    setName('')
    setDescription('')
  }
  const openModify=(item)=>{
    setEditing({mode:'MODIFY',item})
    setName(item.name||'')
    setDescription(item.description||'')
  }
  const submit=async()=>{
    const clean=String(name||'').trim()
    if(!clean) return
    await onChange?.(editing?.mode==='MODIFY'?'MODIFY':'ADD',editing?.item||null,{name:clean,description:String(description||'').trim()})
    setEditing(null)
  }
  const changeStatus=async(item,action)=>{
    const impacts=featureImpact(item?.name)
    const label=action==='REMOVE'?'삭제':action==='DISABLE'?'비활성화':'복원'
    if(action==='REMOVE'){
      const accepted=window.confirm(
        `"${item?.name}" 기능을 삭제하시겠습니까?\n\n영향 가능 영역:\n- ${impacts.join('\n- ')}\n\n삭제 전 현재 설계 Snapshot을 저장하고, 관련 Workflow/DB/UI/테스트 영향도를 다시 분석합니다.`
      )
      if(!accepted) return
    }
    await onChange?.(action,item,{impact:impacts,label})
  }

  return <div className="agent-feature-manager">
    <div className="agent-feature-manager-head">
      <div><strong>기능 관리</strong><small>현재 설계가 진행된 뒤에도 기능을 추가·수정·비활성화·삭제할 수 있습니다.</small></div>
      <button type="button" className="primary" onClick={openAdd}>＋ 기능 추가</button>
    </div>
    <div className="agent-feature-list">
      {merged.map(item=><div key={item.id||normalizeName(item.name)} className={`agent-feature-row status-${String(item.status||'ACTIVE').toLowerCase()}`}>
        <div className="agent-feature-info">
          <strong>{item.name}</strong>
          <small>{item.description||'기능 설명 없음'}</small>
          <span>{item.source==='DISCOVERED'?'기존 설계':'사용자 변경'} · {item.status==='REMOVED'?'삭제됨':item.status==='DISABLED'?'사용 안 함':'사용 중'}</span>
        </div>
        <div className="agent-feature-actions">
          {item.status!=='REMOVED'&&<button type="button" onClick={()=>openModify(item)}>수정</button>}
          {item.status==='ACTIVE'&&<button type="button" onClick={()=>changeStatus(item,'DISABLE')}>사용 안 함</button>}
          {item.status==='DISABLED'&&<button type="button" onClick={()=>changeStatus(item,'RESTORE')}>다시 사용</button>}
          {item.status!=='REMOVED'&&<button type="button" className="danger" onClick={()=>changeStatus(item,'REMOVE')}>삭제</button>}
          {item.status==='REMOVED'&&<button type="button" onClick={()=>changeStatus(item,'RESTORE')}>복원</button>}
        </div>
      </div>)}
      {!merged.length&&<div className="agent-feature-empty">인터뷰에서 기능이 수집되면 여기에 표시됩니다. 필요한 기능은 직접 추가할 수 있습니다.</div>}
    </div>

    {editing&&<div className="agent-feature-editor">
      <strong>{editing.mode==='MODIFY'?'기능 수정 / 재정의':'새 기능 추가'}</strong>
      <label><span>기능명</span><input value={name} onChange={e=>setName(e.target.value)} placeholder="예: 쿠폰 / 회원등급 / 예약 변경"/></label>
      <label><span>설명</span><textarea value={description} onChange={e=>setDescription(e.target.value)} placeholder="어떤 동작이 필요한지 간단히 입력하세요. 저장 후 Agent 설계 인터뷰에서 필요한 추가 질문을 이어서 진행합니다."/></label>
      <div><button type="button" onClick={()=>setEditing(null)}>취소</button><button type="button" className="primary" onClick={submit} disabled={!name.trim()}>적용</button></div>
    </div>}
  </div>
}
