import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../../api'

type CaseRow = Record<string, any>
type DatasetRow = Record<string, any>
type ModelJob = Record<string, any>

export function LlmLearningCenter() {
  const [open,setOpen]=useState(false)
  const [tab,setTab]=useState<'cases'|'datasets'|'training'>('cases')
  const [summary,setSummary]=useState<any>({})
  const [cases,setCases]=useState<CaseRow[]>([])
  const [datasets,setDatasets]=useState<DatasetRow[]>([])
  const [provider,setProvider]=useState('')
  const [busy,setBusy]=useState('')
  const [message,setMessage]=useState('')
  const [modelJob,setModelJob]=useState<ModelJob|null>(null)
  const [navHost,setNavHost]=useState<HTMLElement|null>(null)
  const [contentHost,setContentHost]=useState<HTMLElement|null>(null)

  const onSystemPage=window.location.pathname.startsWith('/system')

  useEffect(()=>{
    if(onSystemPage)return
    let disposed=false
    const locate=()=>{
      if(disposed)return
      setNavHost(document.querySelector<HTMLElement>('.ux-global-nav'))
      setContentHost(document.querySelector<HTMLElement>('.ux-content'))
    }
    locate()
    const timer=window.setInterval(locate,500)
    return()=>{disposed=true;window.clearInterval(timer)}
  },[onSystemPage])

  useEffect(()=>{
    if(!contentHost)return
    contentHost.classList.toggle('llm-learning-active',open)
    return()=>contentHost.classList.remove('llm-learning-active')
  },[contentHost,open])

  useEffect(()=>{
    if(!navHost)return
    const closeOnOtherNavigation=(event:Event)=>{
      const target=event.target as HTMLElement
      if(target.closest('[data-agentstudio-learning-nav="true"]'))return
      if(target.closest('button'))setOpen(false)
    }
    navHost.addEventListener('click',closeOnOtherNavigation,true)
    return()=>navHost.removeEventListener('click',closeOnOtherNavigation,true)
  },[navHost])

  const refresh=async()=>{
    const [s,c,d]=await Promise.all([
      api<any>('/learning/summary'),
      api<any>(`/learning/misjudgments?limit=1000${provider?`&provider=${encodeURIComponent(provider)}`:''}`),
      api<any>('/learning/datasets'),
    ])
    setSummary(s||{});setCases(c?.items||[]);setDatasets(d?.items||[])
  }
  useEffect(()=>{if(open)refresh().catch(e=>setMessage(String(e)))},[open,provider])

  useEffect(()=>{
    if(!modelJob?.id||!['running'].includes(String(modelJob.status||'')))return
    const timer=window.setInterval(async()=>{
      try{
        const next=await api<any>(`/learning/recommended-ollama/download-job/${modelJob.id}`)
        setModelJob(next)
        if(next?.status==='completed'){
          setMessage(next?.message||'qwen3.5:4b 다운로드 및 적용이 완료되었습니다.')
          window.clearInterval(timer)
          await refresh()
        }else if(next?.status==='failed'){
          setMessage(next?.error||next?.message||'모델 다운로드에 실패했습니다.')
          window.clearInterval(timer)
        }
      }catch(e){
        setMessage(String(e));window.clearInterval(timer)
      }
    },1000)
    return()=>window.clearInterval(timer)
  },[modelJob?.id,modelJob?.status])

  const providers=useMemo(()=>Array.from(new Set(cases.map(x=>String(x.provider||'unknown')))),[cases])
  const candidateCount=useMemo(()=>cases.filter(x=>x.status==='candidate').length,[cases])
  const confirmedCount=useMemo(()=>cases.filter(x=>x.status==='confirmed').length,[cases])
  const run=async(label:string,fn:()=>Promise<any>)=>{setBusy(label);setMessage('');try{const result=await fn();setMessage(result?.message||'완료되었습니다.');await refresh();return result}catch(e){setMessage(String(e))}finally{setBusy('')}}

  const rejectGroup=(row:CaseRow)=>run('오판 제외',async()=>{
    const ids=Array.isArray(row.group_case_ids)&&row.group_case_ids.length?row.group_case_ids:[row.id]
    await Promise.all(ids.map((id:string)=>api(`/learning/misjudgments/${id}`,{method:'PATCH',body:JSON.stringify({status:'rejected'})})))
    return {message:`유사 오판 ${ids.length}건을 제외했습니다.`}
  })

  const collectProblems=()=>{
    const rawCount=window.prompt('확정 오판 범위 하나당 수집할 후보 문제 수를 입력하세요. (10~500)','100')
    if(!rawCount)return
    const rawCases=window.prompt('이번에 처리할 오판 범위 수를 입력하세요. (1~20)','5')
    if(!rawCases)return
    const targetPerCase=Math.max(10,Math.min(500,Number(rawCount)||100))
    const maxCases=Math.max(1,Math.min(20,Number(rawCases)||5))
    return run('문제 수집',()=>api('/learning/problems/collect',{method:'POST',body:JSON.stringify({target_per_case:targetPerCase,max_cases:maxCases,provider:'ollama'})}))
  }

  const validate=(row:DatasetRow)=>run('Dataset 검증',()=>api(`/learning/datasets/${row.id}/validate`,{method:'POST',body:JSON.stringify({approved_problem_ids:[]})}))
  const prepare=(row:DatasetRow)=>run('학습 준비',()=>api(`/learning/datasets/${row.id}/prepare-training`,{method:'POST',body:JSON.stringify({base_model:summary.current_ollama_model||''})}))
  const applyCurrentPc=(row:DatasetRow)=>{
    const defaultName=`theanova-${String(row.scope?.topic||'learned').toLowerCase().replace(/[^a-z0-9가-힣_-]+/g,'-')}`
    const modelName=window.prompt(`현재 PC(${summary.current_pc_name||'-'})에 등록할 Ollama 모델 이름`,defaultName)
    if(!modelName?.trim())return
    const defaultAdapter=row.training?.prepared_by_pc_name===summary.current_pc_name?(row.training?.adapter_dir||''):''
    const adapterPath=window.prompt('현재 PC의 학습 Adapter 경로를 입력하세요.',defaultAdapter)
    if(!adapterPath?.trim())return
    return run('현재 PC 적용',()=>api(`/learning/datasets/${row.id}/apply-ollama`,{method:'POST',body:JSON.stringify({model_name:modelName.trim(),adapter_path:adapterPath.trim()})}))
  }
  const setEnabled=(row:DatasetRow,enabled:boolean)=>run(enabled?'현재 PC 활성화':'현재 PC 비활성화',()=>api(`/learning/datasets/${row.id}/current-pc-application`,{method:'PATCH',body:JSON.stringify({enabled})}))

  const startDownloadRecommended=async()=>{
    setMessage('')
    try{
      const job=await api<any>('/learning/recommended-ollama/download-job',{method:'POST'})
      setModelJob(job)
    }catch(e){setMessage(String(e))}
  }

  const pcState=(row:DatasetRow)=>row.current_pc_application||null
  const allPcSummary=(row:DatasetRow)=>{
    const apps=Array.isArray(row.pc_applications)?row.pc_applications:[]
    if(!apps.length)return '적용 PC 없음'
    return apps.map((x:any)=>`${x.pc_name}: ${x.enabled?'사용 중':x.installed?'설치됨':'미적용'}${x.model_name?` (${x.model_name})`:''}`).join(' · ')
  }
  const fmtDate=(value:any)=>{
    if(!value)return '-'
    const date=new Date(String(value))
    return Number.isNaN(date.getTime())?String(value):date.toLocaleString()
  }

  if(onSystemPage||!navHost||!contentHost)return null

  const nav=createPortal(
    <button type="button" data-agentstudio-learning-nav="true" className={open?'studio-nav-icon active':'studio-nav-icon'} onClick={()=>setOpen(v=>!v)} title="LLM 학습" aria-label="LLM 학습">♧</button>,
    navHost
  )

  const recommended=summary?.recommended_ollama||{}
  const downloadRunning=modelJob?.status==='running'
  const downloadProgress=Math.max(0,Math.min(100,Number(modelJob?.progress||0)))
  const page=open?createPortal(
    <div className="nav-page-shell llm-learning-page" aria-label="LLM 학습 센터">
      <div className="nav-page-head">
        <div><div className="eyebrow">LEARNING</div><h2>LLM 학습 센터</h2><p>오판 수집 → 문제 수집 → Dataset 검증 → 학습/평가 → PC별 Ollama 적용</p></div>
      </div>

      <div className="llm-learning-shared-db-note"><b>공용 학습 데이터</b><span>유사 오판은 하나의 범위로 묶어 발생 횟수와 최근 발생일을 관리합니다. confidence 75% 이상은 자동 오판 확정합니다.</span><em>현재 PC: {summary.current_pc_name||'-'}</em></div>

      <div className="llm-learning-model-upgrade">
        <div><small>현재 Ollama</small><strong>{summary.current_ollama_model||'-'}</strong></div>
        <div><small>권장 최신 로컬 모델</small><strong>{recommended.recommended_model||'qwen3.5:4b'}</strong></div>
        <div className="llm-learning-model-path"><small>공통 모델 관리 경로</small><code>{recommended.common_models_root||'설정되지 않음'}</code></div>
        <button disabled={downloadRunning||summary.current_ollama_model==='qwen3.5:4b'} onClick={startDownloadRecommended}>{summary.current_ollama_model==='qwen3.5:4b'?'qwen3.5:4b 적용됨':downloadRunning?'다운로드 중...':'qwen3.5:4b 다운로드 및 적용'}</button>
      </div>
      {(downloadRunning||modelJob?.status==='failed'||modelJob?.status==='completed')&&<div className={`llm-model-progress ${modelJob?.status||''}`}>
        <div className="llm-model-progress-head"><b>{modelJob?.message||'모델 작업 진행 중...'}</b><span>{downloadProgress}%</span></div>
        <div className="llm-model-progress-track"><i style={{width:`${downloadProgress}%`}}/></div>
        <small>단계: {modelJob?.stage||'-'} · 작업 ID: {modelJob?.id||'-'}</small>
      </div>}

      <div className="llm-learning-metrics"><div><b>{candidateCount}</b><span>75% 미만 검토 후보</span></div><div><b>{confirmedCount}</b><span>자동/확정 오판 범위</span></div><div><b>{datasets.length}</b><span>공용 Dataset</span></div><div><b>{summary.current_ollama_model||'-'}</b><span>현재 Ollama</span></div></div>

      <div className="llm-learning-toolbar">
        <button className={tab==='cases'?'active':''} onClick={()=>setTab('cases')}>1. 오판 수집</button>
        <button className={tab==='datasets'?'active':''} onClick={()=>setTab('datasets')}>2. Dataset 검증</button>
        <button className={tab==='training'?'active':''} onClick={()=>setTab('training')}>3. 학습·평가·PC별 적용</button>
        <span/>
        <button disabled={!!busy} onClick={()=>run('오판 수집',()=>api('/learning/misjudgments/sync',{method:'POST'}))}>↻ 오판 수집</button>
        <button className="primary" disabled={!!busy} onClick={collectProblems}>＋ 문제 수집</button>
      </div>
      <div className="llm-problem-help">문제 수집은 confidence 75% 이상으로 확정된 오판 범위 중 아직 Dataset이 없는 범위를 선택해 관련 후보 문제를 대량 생성합니다. 생성 문제는 검증 전까지 학습에 사용되지 않습니다.</div>
      {message&&<div className="llm-learning-message">{busy?`${busy} 중... `:''}{message}</div>}

      <div className="llm-learning-body">
        {tab==='cases'&&<>
          <div className="llm-learning-filter"><label>모델 제공자 <select value={provider} onChange={e=>setProvider(e.target.value)}><option value="">전체</option>{providers.map(p=><option key={p}>{p}</option>)}</select></label><em>같거나 매우 유사한 오판은 한 행으로 묶으며 발생할 때마다 카운트와 최근 발생일이 갱신됩니다.</em></div>
          <table className="llm-case-table"><thead><tr><th>상태</th><th>횟수</th><th>최근 발생</th><th>수집 PC</th><th>Provider / Model</th><th>감지 사유</th><th>사용자 요청 / 잘못된 결과</th><th>작업</th></tr></thead><tbody>{cases.map(row=><tr key={row.id}>
            <td><b>{row.status}</b><small>{Math.round((row.confidence||0)*100)}%</small></td>
            <td><b className="occurrence-count">{row.occurrence_count||1}</b></td>
            <td className="date-cell">{fmtDate(row.last_occurred_at||row.updated_at)}</td>
            <td><b>{row.source_pc_name||'-'}</b></td>
            <td><b>{row.provider}</b><small>{row.model}</small></td>
            <td>{row.detection_reason}</td>
            <td><div className="case-text-scroll"><b>[사용자 요청]</b><pre>{row.user_request||'-'}</pre><b>[잘못된 결과]</b><pre>{row.wrong_output||'-'}</pre>{row.correction_evidence&&<><b>[수정 증거]</b><pre>{row.correction_evidence}</pre></>}</div></td>
            <td><div className="llm-learning-actions"><button onClick={()=>rejectGroup(row)}>제외</button></div></td>
          </tr>)}</tbody></table>
        </>}
        {tab==='datasets'&&<table><thead><tr><th>상태</th><th>생성 PC</th><th>학습 범위</th><th>문제 수</th><th>검증</th><th>PC별 적용 현황</th><th>작업</th></tr></thead><tbody>{datasets.map(row=><tr key={row.id}><td>{row.status}</td><td>{row.source_pc_name||'-'}</td><td><b>{row.scope?.domain||'-'} / {row.scope?.topic||'-'}</b><small>{row.scope?.learning_objective||''}</small></td><td>{row.problem_count||0}</td><td>{row.validation?.approved||0} 승인 / {row.validation?.pending||0} 대기</td><td><b>{pcState(row)?.enabled?'현재 PC 사용 중':pcState(row)?.installed?'현재 PC 설치됨':'현재 PC 미적용'}</b><small>{allPcSummary(row)}</small></td><td>{row.status==='review'&&<button onClick={()=>validate(row)}>전체 검증 완료</button>}{row.status==='validated'&&<button onClick={()=>prepare(row)}>이 PC에서 학습 준비</button>}</td></tr>)}</tbody></table>}
        {tab==='training'&&<div className="llm-learning-training"><h3>학습 적용 안전 Gate</h3><p>① 공용 DB 검증 Dataset → ② Train/Validation/Test 분리 → ③ LoRA/QLoRA 학습 → ④ 기존 모델과 Blind Test 비교 → ⑤ 최소 향상폭 통과 → ⑥ 각 PC 개별 적용 순서입니다.</p><p><b>현재 Base Model:</b> {summary.current_ollama_model||'-'} · <b>라우팅:</b> {summary.current_strategy||'-'}</p><div className="llm-learning-gate">Dataset과 평가 결과는 공통입니다. 집 PC 적용 여부와 학원 노트북 적용 여부는 서로 영향을 주지 않습니다.</div>{datasets.filter(x=>['training','trained','deployed'].includes(x.status)).map(row=>{const app=pcState(row);return <article key={row.id}><b>{row.scope?.topic||row.id}</b><span>{row.status} · Train {row.split?.train||0} / Validation {row.split?.validation||0} / Test {row.split?.test||0}</span><small>전체 PC: {allPcSummary(row)}</small><small>현재 PC: {app?`${app.status} · ${app.model_name||'-'}`:'미적용'}</small><div className="llm-learning-actions">{row.evaluation?.passed&&!app?.installed&&<button disabled={!!busy} onClick={()=>applyCurrentPc(row)}>현재 PC에 적용</button>}{app?.installed&&app?.enabled&&<button disabled={!!busy} onClick={()=>setEnabled(row,false)}>현재 PC 사용 중지</button>}{app?.installed&&!app?.enabled&&<button disabled={!!busy} onClick={()=>setEnabled(row,true)}>현재 PC 다시 사용</button>}</div></article>})}</div>}
      </div>
    </div>,
    contentHost
  ):null

  return <>{nav}{page}</>
}
