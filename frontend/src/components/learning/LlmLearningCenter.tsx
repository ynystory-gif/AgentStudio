import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api, saveBlobToOutput } from '../../api'

type CaseRow = Record<string, any>
type DatasetRow = Record<string, any>
type JobRow = Record<string, any>
type LearningLoadPart='summary'|'cases'|'datasets'
type LearningLoadState={
  visible:boolean
  active:boolean
  progress:number
  completed:number
  total:number
  stage:string
  startedAt:number
  elapsedSeconds:number
  error:string
  parts:Record<LearningLoadPart,'waiting'|'done'|'error'>
}

const REOPEN_KEY='theanova.agentstudio.learning.reopen'
const TAB_KEY='theanova.agentstudio.learning.active-tab'
const SCROLL_KEY='theanova.agentstudio.learning.scroll-top'


type LearningSqlKind='cases'|'datasets'|'training'

export function LlmLearningCenter() {
  const reopen=sessionStorage.getItem(REOPEN_KEY)==='1'
  if(reopen)sessionStorage.removeItem(REOPEN_KEY)
  const [open,setOpen]=useState(reopen)
  const [tab,setTab]=useState<'cases'|'datasets'|'training'>(()=>{const saved=sessionStorage.getItem(TAB_KEY);return saved==='datasets'||saved==='training'?saved:'cases'})
  const [summary,setSummary]=useState<any>({})
  const [cases,setCases]=useState<CaseRow[]>([])
  const [datasets,setDatasets]=useState<DatasetRow[]>([])
  const [provider,setProvider]=useState('')
  const [busy,setBusy]=useState('')
  const [message,setMessage]=useState('')
  const [modelJob,setModelJob]=useState<JobRow|null>(null)
  const [problemJob,setProblemJob]=useState<JobRow|null>(null)
  const [applyJob,setApplyJob]=useState<JobRow|null>(null)
  const [selectedDatasetId,setSelectedDatasetId]=useState('')
  const [navHost,setNavHost]=useState<HTMLElement|null>(null)
  const [contentHost,setContentHost]=useState<HTMLElement|null>(null)
  const [loadState,setLoadState]=useState<LearningLoadState>({
    visible:false,active:false,progress:0,completed:0,total:3,stage:'대기',startedAt:0,elapsedSeconds:0,error:'',
    parts:{summary:'waiting',cases:'waiting',datasets:'waiting'},
  })
  const refreshSequence=useRef(0)

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
    if(open){
      const saved=Number(sessionStorage.getItem(SCROLL_KEY)||0)
      window.setTimeout(()=>{if(Number.isFinite(saved)&&saved>0)contentHost.scrollTop=saved},80)
    }
    const rememberScroll=()=>{if(open)sessionStorage.setItem(SCROLL_KEY,String(Math.max(0,contentHost.scrollTop||0)))}
    contentHost.addEventListener('scroll',rememberScroll,{passive:true})
    return()=>{contentHost.removeEventListener('scroll',rememberScroll);contentHost.classList.remove('llm-learning-active')}
  },[contentHost,open])

  useEffect(()=>{sessionStorage.setItem(TAB_KEY,tab)},[tab])

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

  const refresh=async(reason='학습 데이터 로드')=>{
    const requestId=++refreshSequence.current
    const startedAt=Date.now()
    const total=3
    setLoadState({
      visible:true,active:true,progress:6,completed:0,total,
      stage:`${reason} · Backend 조회 요청 3개 전송`,startedAt,elapsedSeconds:0,error:'',
      parts:{summary:'waiting',cases:'waiting',datasets:'waiting'},
    })

    const finishPart=(part:LearningLoadPart,label:string)=>{
      if(requestId!==refreshSequence.current)return
      setLoadState(prev=>{
        const parts={...prev.parts,[part]:'done' as const}
        const completed=Object.values(parts).filter(value=>value==='done').length
        const progress=completed>=total?100:Math.min(92,8+completed*28)
        return {...prev,parts,completed,progress,stage:completed>=total?'학습 데이터 로드 완료':`${label} 완료 · Backend 응답 ${completed}/${total}`}
      })
    }
    const failPart=(part:LearningLoadPart,label:string,error:unknown)=>{
      if(requestId!==refreshSequence.current)return
      const errorText=error instanceof Error?error.message:String(error)
      setLoadState(prev=>({...prev,visible:true,active:false,progress:100,error:errorText,stage:`${label} 로드 실패`,parts:{...prev.parts,[part]:'error'}}))
    }

    const summaryPromise=api<any>('/learning/summary').then(value=>{
      if(requestId===refreshSequence.current)setSummary(value||{})
      finishPart('summary','학습 요약/모델 상태')
      return value
    }).catch(error=>{failPart('summary','학습 요약/모델 상태',error);throw error})
    const casesPromise=api<any>(`/learning/misjudgments?limit=1000${provider?`&provider=${encodeURIComponent(provider)}`:''}`).then(value=>{
      if(requestId===refreshSequence.current)setCases(value?.items||[])
      finishPart('cases','오판 목록')
      return value
    }).catch(error=>{failPart('cases','오판 목록',error);throw error})
    const datasetsPromise=api<any>('/learning/datasets').then(value=>{
      if(requestId===refreshSequence.current)setDatasets(value?.items||[])
      finishPart('datasets','Dataset/문제 목록')
      return value
    }).catch(error=>{failPart('datasets','Dataset/문제 목록',error);throw error})

    try{
      const [s,c,d]=await Promise.all([summaryPromise,casesPromise,datasetsPromise])
      if(requestId===refreshSequence.current){
        setLoadState(prev=>({...prev,visible:true,active:false,progress:100,completed:total,stage:'학습 데이터 로드 완료',elapsedSeconds:Math.max(0,Math.round((Date.now()-startedAt)/1000))}))
        window.setTimeout(()=>{
          if(requestId===refreshSequence.current)setLoadState(prev=>prev.active||prev.error?prev:{...prev,visible:false})
        },900)
      }
      return {summary:s,cases:c,datasets:d}
    }catch(error){
      if(requestId===refreshSequence.current)setMessage(`학습 데이터 로드 실패: ${error instanceof Error?error.message:String(error)}`)
      throw error
    }
  }

  useEffect(()=>{
    if(!loadState.active||!loadState.startedAt)return
    const timer=window.setInterval(()=>{
      setLoadState(prev=>prev.active?{...prev,elapsedSeconds:Math.max(0,Math.floor((Date.now()-prev.startedAt)/1000))}:prev)
    },500)
    return()=>window.clearInterval(timer)
  },[loadState.active,loadState.startedAt])

  useEffect(()=>{if(open)refresh(provider?'모델 제공자 필터 적용':'LLM 학습 센터 초기 로드').catch(()=>{})},[open,provider])

  useEffect(()=>{
    if(!modelJob?.id||modelJob.status!=='running')return
    const timer=window.setInterval(async()=>{
      try{
        const next=await api<any>(`/learning/recommended-ollama/download-job/${modelJob.id}`)
        setModelJob(next)
        if(next?.status==='completed'){
          setMessage(next?.message||'qwen3.5:4b 다운로드 및 적용이 완료되었습니다.')
          window.clearInterval(timer)
          await refresh()
          sessionStorage.setItem(REOPEN_KEY,'1')
          window.setTimeout(()=>window.location.reload(),500)
        }else if(next?.status==='failed'){
          setMessage(next?.error||next?.message||'모델 다운로드에 실패했습니다.')
          window.clearInterval(timer)
        }
      }catch(e){setMessage(String(e));window.clearInterval(timer)}
    },1000)
    return()=>window.clearInterval(timer)
  },[modelJob?.id,modelJob?.status])

  useEffect(()=>{
    if(!problemJob?.id||problemJob.status!=='running')return
    const timer=window.setInterval(async()=>{
      try{
        const next=await api<any>(`/learning/problems/collect-job/${problemJob.id}`)
        setProblemJob(next)
        if(next?.status==='completed'){
          window.clearInterval(timer)
          const result=next?.result||{}
          const generated=Array.isArray(result?.datasets)?result.datasets:[]
          const generatedProblems=Number(result?.generated_problem_count||generated.reduce((sum:number,row:any)=>sum+Number(row?.problem_count||row?.problems?.length||0),0))
          const requestedSourceIds=(result?.requested_source_case_ids||next?.source_case_ids||[]).map((value:any)=>String(value||'')).filter(Boolean)
          const createdSourceIds=(result?.created_source_case_ids||generated.map((row:any)=>row?.source_case_id)).map((value:any)=>String(value||'')).filter(Boolean)
          if(requestedSourceIds.length&&requestedSourceIds.join('|')!==createdSourceIds.join('|')){
            setMessage(`오판 ID 매핑 검증 실패 · 요청 ${requestedSourceIds.join(', ')} · Dataset ${createdSourceIds.join(', ')}`)
            return
          }
          const refreshed=await refresh()
          if(generated.length){
            const generatedIds=new Set(generated.map((row:any)=>String(row?.id||'')).filter(Boolean))
            const persisted=(refreshed?.datasets?.items||refreshed?.datasets||[]).find((row:any)=>generatedIds.has(String(row?.id||''))) || generated[0]
            sessionStorage.setItem(TAB_KEY,'datasets')
            setSelectedDatasetId(String(persisted?.id||generated[0]?.id||''))
            setTab('datasets')
          }
          setMessage(next?.message||`문제 수집 완료 · Dataset ${generated.length}개 / 문제 ${generatedProblems}개 DB 저장 확인`)
        }else if(next?.status==='failed'){
          window.clearInterval(timer)
          setMessage(next?.error||next?.message||'문제 수집에 실패했습니다.')
        }
      }catch(e){window.clearInterval(timer);setMessage(String(e))}
    },1000)
    return()=>window.clearInterval(timer)
  },[problemJob?.id,problemJob?.status])

  useEffect(()=>{
    if(!applyJob?.id||applyJob.status!=='running')return
    const timer=window.setInterval(async()=>{
      try{
        const next=await api<any>(`/learning/learning-apply-job/${applyJob.id}`)
        setApplyJob(next)
        if(next?.status==='completed'){
          window.clearInterval(timer)
          setMessage(next?.message||'현재 PC 학습 적용이 완료되었습니다.')
          await refresh()
          sessionStorage.setItem(REOPEN_KEY,'1')
          window.setTimeout(()=>window.location.reload(),700)
        }else if(next?.status==='failed'){
          window.clearInterval(timer)
          setMessage(next?.error||next?.message||'학습 적용에 실패했습니다.')
        }
      }catch(e){window.clearInterval(timer);setMessage(String(e))}
    },1000)
    return()=>window.clearInterval(timer)
  },[applyJob?.id,applyJob?.status])

  const providers=useMemo(()=>Array.from(new Set(cases.map(x=>String(x.provider||'unknown')))),[cases])
  const candidateCount=useMemo(()=>cases.filter(x=>x.status==='candidate').length,[cases])
  const confirmedCount=useMemo(()=>cases.filter(x=>x.status==='confirmed').length,[cases])
  const selectedDataset=useMemo(()=>datasets.find(x=>String(x.id)===selectedDatasetId)||null,[datasets,selectedDatasetId])

  const run=async(label:string,fn:()=>Promise<any>)=>{
    setBusy(label);setMessage('')
    try{const result=await fn();setMessage(result?.message||'완료되었습니다.');await refresh();return result}
    catch(e){setMessage(String(e))}finally{setBusy('')}
  }

  const downloadSql=async(kind:LearningSqlKind)=>{
    try{
      const payload={
        kind,
        provider,
        case_ids:kind==='cases'?cases.map(row=>String(row?.id||'')).filter(Boolean):[],
        dataset_ids:kind==='cases'?[]:datasets.map(row=>String(row?.id||'')).filter(Boolean),
      }
      const item=await api<any>('/learning/sql-export',{method:'POST',body:JSON.stringify(payload)})
      const sql=String(item?.sql||'')
      if(!sql)throw new Error('다운로드할 SQL이 없습니다.')
      const blob=new Blob([sql],{type:'application/sql;charset=utf-8'})
      const fileName=String(item?.file_name||'LLM_학습_화면_조회.sql')
      const saved=await saveBlobToOutput(blob,fileName,'sql')
      setMessage(`${fileName} 저장 · ${saved.path} · 화면 ${Number(item?.expected_count||0)}건과 동일한 ID 스냅샷 SQL입니다.`)
    }catch(e){setMessage(`SQL 다운로드 실패: ${e instanceof Error?e.message:String(e)}`)}
  }

  const rejectGroup=(row:CaseRow)=>run('오판 제외',async()=>{
    const ids=Array.isArray(row.group_case_ids)&&row.group_case_ids.length?row.group_case_ids:[row.id]
    await Promise.all(ids.map((id:string)=>api(`/learning/misjudgments/${id}`,{method:'PATCH',body:JSON.stringify({status:'rejected'})})))
    return {message:`유사 오판 ${ids.length}건을 제외했습니다.`}
  })

  const startProblemCollection=async()=>{
    const rawTopics=window.prompt('처리할 오판 주제 수를 입력하세요. (1~20)','1')
    if(rawTopics===null)return
    const maxCases=Math.max(1,Math.min(20,Number(rawTopics)||1))
    const rawCount=window.prompt('오판 주제 하나당 생성할 후보 문제 수를 입력하세요. (1~500)','100')
    if(rawCount===null)return
    const targetPerCase=Math.max(1,Math.min(500,Number(rawCount)||100))
    // v5.443: collect from the exact visible misjudgment IDs shown to the user.
    // The backend must never re-select different raw rows only from a count, because
    // Dataset/source mapping and current-PC learned-state tracking depend on identity.
    const eligibleCases=cases.filter(row=>String(row?.status||'').toLowerCase()==='confirmed'&&!row?.learning_exact_source_dataset_exists)
    const sourceCaseIds=eligibleCases.slice(0,maxCases).map(row=>String(row?.id||'')).filter(Boolean)
    if(!sourceCaseIds.length){
      setMessage('현재 화면의 확정 오판 ID를 찾지 못했습니다. 오판 수집을 새로고침한 뒤 다시 시도해 주세요.')
      return
    }
    setMessage(`문제 수집 준비 · 실제 오판 ID ${sourceCaseIds.length}개 × 주제당 ${targetPerCase}문제 = 최대 ${sourceCaseIds.length*targetPerCase}문제`)
    try{
      const job=await api<any>('/learning/problems/collect-job',{method:'POST',body:JSON.stringify({target_per_case:targetPerCase,max_cases:sourceCaseIds.length,provider:'ollama',source_case_ids:sourceCaseIds})})
      setProblemJob(job)
    }catch(e){setMessage(String(e))}
  }

  const validate=(row:DatasetRow)=>run('Dataset 검증',()=>api(`/learning/datasets/${row.id}/validate`,{method:'POST',body:JSON.stringify({approved_problem_ids:[]})}))

  const startLearningApply=async(row:DatasetRow)=>{
    setSelectedDatasetId(String(row.id||''));setMessage('')
    try{setApplyJob(await api<any>(`/learning/datasets/${row.id}/learning-apply-job`,{method:'POST'}))}
    catch(e){setMessage(String(e))}
  }

  const setEnabled=(row:DatasetRow,enabled:boolean)=>run(enabled?'현재 PC 활성화':'현재 PC 비활성화',()=>api(`/learning/datasets/${row.id}/current-pc-application`,{method:'PATCH',body:JSON.stringify({enabled})}))
  const startDownloadRecommended=async()=>{setMessage('');try{setModelJob(await api<any>('/learning/recommended-ollama/download-job',{method:'POST'}))}catch(e){setMessage(String(e))}}

  const pcState=(row:DatasetRow)=>row.current_pc_application||null
  const allPcSummary=(row:DatasetRow)=>{
    const apps=Array.isArray(row.pc_applications)?row.pc_applications:[]
    if(!apps.length)return '적용 PC 없음'
    return apps.map((x:any)=>`${x.pc_name}: ${x.enabled?'사용 중':x.installed?'설치됨':'미적용'}${x.model_name?` (${x.model_name})`:''}`).join(' · ')
  }
  const fmtDate=(value:any)=>{if(!value)return '-';const date=new Date(String(value));return Number.isNaN(date.getTime())?String(value):date.toLocaleString()}
  const jobProgress=(job:JobRow|null)=>Math.max(0,Math.min(100,Number(job?.progress||0)))

  if(onSystemPage||!navHost||!contentHost)return null

  const nav=createPortal(<button type="button" data-agentstudio-learning-nav="true" className={open?'studio-nav-icon active':'studio-nav-icon'} onClick={()=>setOpen(v=>!v)} title="LLM 학습" aria-label="LLM 학습">♧</button>,navHost)
  const recommended=summary?.recommended_ollama||{}
  const downloadRunning=modelJob?.status==='running'
  const problemRunning=problemJob?.status==='running'
  const applyRunning=applyJob?.status==='running'
  const progressBlock=(job:JobRow|null,label:string)=>job&&['running','failed','completed'].includes(String(job.status||''))?<div className={`llm-job-progress ${job.status||''}`}><div className="llm-job-progress-head"><b>{label} · {job.message||'진행 중...'}</b><span>{jobProgress(job)}%</span></div><div className="llm-job-progress-track"><i style={{width:`${jobProgress(job)}%`}}/></div><small>단계: {job.stage||'-'}{job.current_topic&&job.total_topics?` · 오판 주제 ${job.current_topic}/${job.total_topics}`:''} · 작업 ID: {job.id||'-'}</small></div>:null
  const formatElapsed=(seconds:number)=>`${String(Math.floor(Math.max(0,seconds)/60)).padStart(2,'0')}:${String(Math.max(0,seconds)%60).padStart(2,'0')}`
  const loadPartLabel=(part:LearningLoadPart)=>part==='summary'?'요약/모델':part==='cases'?'오판 목록':'Dataset/문제'
  const loadProgressPanel=loadState.visible?<div className={`llm-data-load-progress ${loadState.error?'failed':loadState.active?'running':'completed'}`} role="status" aria-live="polite">
    <div className="llm-data-load-progress-head"><b>{loadState.error?'학습 데이터 로드 실패':loadState.active?'학습 데이터 로드 중':'학습 데이터 로드 완료'}</b><span>{loadState.progress}% · 경과 {formatElapsed(loadState.elapsedSeconds)}</span></div>
    <div className="llm-data-load-progress-track"><i style={{width:`${loadState.progress}%`}}/></div>
    <div className="llm-data-load-progress-foot"><span>{loadState.active&&loadState.elapsedSeconds>=10?`${loadState.stage} · 응답 대기 중 (화면은 동작 중입니다.)`:loadState.stage}</span><div>{(Object.keys(loadState.parts) as LearningLoadPart[]).map(part=><small key={part} className={loadState.parts[part]}>{loadState.parts[part]==='done'?'✓':loadState.parts[part]==='error'?'!':'…'} {loadPartLabel(part)}</small>)}</div></div>
    {loadState.error&&<small className="llm-data-load-error">{loadState.error}</small>}
  </div>:null

  const page=open?createPortal(<div className="nav-page-shell llm-learning-page" aria-label="LLM 학습 센터">
    <div className="nav-page-head"><div><div className="eyebrow">LEARNING</div><h2>LLM 학습 센터</h2><p>오판 수집 → 문제 수집 → 문제 확인/검증 → 현재 PC 학습 적용</p></div></div>
    {loadProgressPanel}
    <div className="llm-learning-shared-db-note"><b>공용 학습 데이터</b><span>유사 오판은 하나의 주제로 묶어 횟수와 최근 발생일을 관리합니다. 75% 이상은 자동 확정합니다. 현재 PC에 학습 적용된 과거 오판은 이 PC 목록에서 숨깁니다.</span><em>현재 PC: {summary.current_pc_name||'-'}</em></div>
    <div className="llm-learning-model-upgrade"><div><small>현재 Ollama</small><strong>{summary.current_ollama_model||'-'}</strong></div><div><small>권장 최신 로컬 모델</small><strong>{recommended.recommended_model||'qwen3.5:4b'}</strong></div><div className="llm-learning-model-path"><small>공통 모델 관리 경로</small><code>{recommended.common_models_root||'설정되지 않음'}</code></div><button disabled={downloadRunning||summary.current_ollama_model==='qwen3.5:4b'} onClick={startDownloadRecommended}>{summary.current_ollama_model==='qwen3.5:4b'?'qwen3.5:4b 적용됨':downloadRunning?'다운로드 중...':'qwen3.5:4b 다운로드 및 적용'}</button></div>
    {progressBlock(modelJob,'모델 다운로드/적용')}{progressBlock(problemJob,'문제 수집')}{progressBlock(applyJob,'학습 적용')}
    <div className="llm-learning-metrics"><div><b>{candidateCount}</b><span>75% 미만 검토 후보</span></div><div><b>{confirmedCount}</b><span>자동/확정 오판 주제</span></div><div><b>{datasets.length}</b><span>공용 Dataset</span></div><div><b>{summary.current_ollama_model||'-'}</b><span>현재 Ollama</span></div></div>
    <div className="llm-learning-toolbar"><button className={tab==='cases'?'active':''} onClick={()=>{setTab('cases');refresh('오판 수집 탭 로드').catch(()=>{})}}>1. 오판 수집</button><button className={tab==='datasets'?'active':''} onClick={()=>{sessionStorage.setItem(TAB_KEY,'datasets');setTab('datasets');refresh('수집 문제 / Dataset 탭 로드').catch(()=>{})}}>2. 수집 문제 / Dataset</button><button className={tab==='training'?'active':''} onClick={()=>{setTab('training');refresh('PC별 학습 적용 관리 탭 로드').catch(()=>{})}}>3. PC별 학습 적용 관리</button><span/><button disabled={!!busy||problemRunning||applyRunning} onClick={()=>run('오판 수집',()=>api('/learning/misjudgments/sync',{method:'POST'}))}>↻ 오판 수집</button><button className="primary" disabled={!!busy||problemRunning||applyRunning} onClick={startProblemCollection}>＋ 문제 수집</button></div>
    <div className="llm-problem-help"><b>문제 수집:</b> 처리할 오판 주제 수를 1~20개에서 선택한 뒤, 주제 하나당 생성할 문제 수를 1~500개에서 정합니다. 예: 오판 주제 1개 × 1문제 = 최대 1문제.</div>
    {message&&<div className="llm-learning-message">{busy?`${busy} 중... `:''}{message}</div>}
    <div className="llm-learning-body">
      {tab==='cases'&&<><div className="llm-learning-filter"><label>모델 제공자 <select value={provider} onChange={e=>setProvider(e.target.value)}><option value="">전체</option>{providers.map(p=><option key={p}>{p}</option>)}</select></label><em>학습 데이터는 공용이며 현재 PC 학습 적용 이력만 PC 조건으로 판단합니다. SQL은 현재 화면과 동일한 행 ID 스냅샷을 내려받습니다.</em><button type="button" onClick={()=>downloadSql('cases')}>SQL ({cases.length}건)</button></div><table className="llm-case-table"><thead><tr><th>상태</th><th>오판 ID</th><th>횟수</th><th>최근 발생</th><th>수집 PC</th><th>Provider / Model</th><th>감지 사유</th><th>학습 데이터</th><th>사용자 요청 / 잘못된 결과</th><th>작업</th></tr></thead><tbody>{cases.map(row=><tr key={row.id}><td><b>{row.status}</b><small>{Math.round((row.confidence||0)*100)}%</small></td><td><code title={String(row.id||'')}>{row.id||'-'}</code>{Array.isArray(row.group_case_ids)&&row.group_case_ids.length>1&&<small>그룹 {row.group_case_ids.length}건</small>}</td><td><b className="occurrence-count">{row.occurrence_count||1}</b></td><td className="date-cell">{fmtDate(row.last_occurred_at||row.updated_at)}</td><td><b>{row.source_pc_name||'-'}</b></td><td><b>{row.provider}</b><small>{row.model}</small></td><td>{row.detection_reason}</td><td><b>{row.learning_data_exists?'있음':'없음'}</b><small>{row.learning_data_label||'학습 데이터 없음'}</small>{row.learning_data_exists&&!row.learning_exact_source_dataset_exists&&<small className="learning-id-warning">동일 계열 Dataset은 있으나 현재 오판 ID 직접 연결 없음</small>}{row.learning_data_current_pc_applied&&<small>현재 PC 적용됨</small>}</td><td><div className="case-text-scroll"><b>[사용자 요청]</b><pre>{row.user_request||'-'}</pre><b>[잘못된 결과]</b><pre>{row.wrong_output||'-'}</pre>{row.correction_evidence&&<><b>[수정 증거]</b><pre>{row.correction_evidence}</pre></>}</div></td><td><div className="llm-learning-actions"><button onClick={()=>rejectGroup(row)}>제외</button></div></td></tr>)}</tbody></table></>}
      {tab==='datasets'&&<><div className="llm-learning-filter llm-learning-sql-row"><em>Dataset은 모든 PC 공용 전체 조회입니다. 현재 PC 적용 상태만 PC 이름 조건으로 판단하며 SQL 결과 건수도 현재 목록과 동일합니다.</em><button type="button" onClick={()=>downloadSql('datasets')}>SQL ({datasets.length}건)</button></div><div className="llm-dataset-table-scroll"><table className="llm-dataset-table"><thead><tr><th>상태</th><th data-learning-trace="1">오판 / Dataset ID</th><th>생성 PC</th><th>학습 주제</th><th>문제 수</th><th>검증</th><th>현재 PC</th><th>작업</th></tr></thead><tbody>{datasets.map(row=>{const app=pcState(row);return <tr key={row.id} className={selectedDatasetId===String(row.id)?'selected':''}><td>{row.status}</td><td className="learning-dataset-trace-cell"><div className="learning-dataset-trace-block"><small>오판 ID</small><code className="learning-trace-id" title={String(row.source_case_id||'')}>{row.source_case_id||'-'}</code></div><div className="learning-dataset-trace-block"><small>Dataset ID</small><code className="learning-trace-id" title={String(row.id||'')}>{row.id||'-'}</code></div></td><td>{row.source_pc_name||'-'}</td><td className="learning-topic-cell"><div className="learning-topic-scroll" title={`${row.scope?.domain||'-'} / ${row.scope?.topic||'-'}${row.scope?.learning_objective?`\n${row.scope.learning_objective}`:''}`}><b>{row.scope?.domain||'-'} / {row.scope?.topic||'-'}</b><small>{row.scope?.learning_objective||''}</small></div></td><td><b>{row.problem_count||row.problems?.length||0}</b><small>{(row.problems?.length||0)>0?'DB 확인됨':'문제 없음'}</small></td><td>{row.validation?.approved||0} 승인 / {row.validation?.pending||0} 대기</td><td><b>{app?.enabled?'학습 적용됨':app?.installed?'설치됨':'미적용'}</b><small>{app?.model_name||''}</small></td><td><div className="llm-learning-actions"><button onClick={()=>setSelectedDatasetId(String(row.id))}>문제 보기</button>{row.status==='review'&&<button onClick={()=>validate(row)}>검증</button>}{!app?.enabled&&<button className="primary" disabled={applyRunning} onClick={()=>startLearningApply(row)}>학습 적용</button>}{app?.enabled&&<button disabled={!!busy} onClick={()=>setEnabled(row,false)}>사용 중지</button>}</div></td></tr>})}</tbody></table></div>{datasets.length===0&&!loadState.active&&!loadState.error&&<div className="llm-learning-message">저장된 Dataset이 없습니다. 문제 수집 완료 메시지가 표시되었는데 이 화면이 비어 있다면 Backend 저장이 완료되지 않은 상태입니다.</div>}{selectedDataset&&<div className="llm-problem-viewer"><div className="llm-problem-viewer-head"><div><strong>수집된 문제</strong><small>{selectedDataset.scope?.domain||'-'} / {selectedDataset.scope?.topic||'-'} · 총 {selectedDataset.problem_count||selectedDataset.problems?.length||0}개</small><div className="learning-problem-trace"><code>오판 ID: {selectedDataset.source_case_id||'-'}</code><code>Dataset ID: {selectedDataset.id||'-'}</code></div></div><button className="primary" disabled={applyRunning||pcState(selectedDataset)?.enabled||!(selectedDataset.problems||[]).length} onClick={()=>startLearningApply(selectedDataset)}>{pcState(selectedDataset)?.enabled?'현재 PC 학습 적용됨':applyRunning?'학습 적용 중...':'학습 적용'}</button></div>{!(selectedDataset.problems||[]).length&&<div className="llm-learning-message">이 Dataset의 문제 본문이 비어 있습니다. 현재 버전은 정규화 문제 테이블과 Dataset JSON을 자동 재동기화합니다. 새로고침 후에도 비어 있으면 해당 Dataset은 저장 실패로 판정해야 합니다.</div>}<div className="llm-problem-list"><table><thead><tr><th>#</th><th data-learning-trace="1">Problem ID / 오판 ID</th><th>유형/난이도</th><th>문제 / 지시</th><th>입력 / 상황</th><th>정답 / 권장 응답</th></tr></thead><tbody>{(selectedDataset.problems||[]).map((problem:any,index:number)=><tr key={problem.id||problem.db_id||index}><td>{index+1}</td><td><div className="learning-problem-id-block"><small>Problem ID</small><code className="learning-trace-id" title={String(problem.db_id||problem.id||'')}>{problem.id||problem.db_id||'-'}</code><small>오판 ID</small><code className="learning-trace-id learning-source-case-id" title={String(problem.source_case_id||selectedDataset.source_case_id||'')}>{problem.source_case_id||selectedDataset.source_case_id||'-'}</code></div></td><td><b>{problem.problem_type||'-'}</b><small>{problem.difficulty||'-'}</small></td><td><div className="problem-text">{problem.instruction||'-'}</div></td><td><div className="problem-text">{problem.input||'-'}</div></td><td><div className="problem-text answer">{problem.output||'-'}</div></td></tr>)}</tbody></table></div><div className="llm-problem-apply-note">현재 <b>학습 적용</b>은 검증된 문제를 현재 PC의 Ollama 커리큘럼 모델에 적용합니다. 공용 Dataset은 그대로 유지되고 적용 여부만 PC별로 관리됩니다.</div></div>}</>}
      {tab==='training'&&<div className="llm-learning-training"><div className="llm-learning-training-head"><h3>PC별 학습 적용 현황</h3><button type="button" onClick={()=>downloadSql('training')}>SQL ({datasets.length}건)</button></div><p>Dataset은 모든 등록 PC가 공통 조회하고 실제 학습 적용은 PC별로 독립 관리합니다. 이 PC에 적용된 오판 주제의 기존 기록은 오판 목록에서 숨겨집니다.</p>{datasets.map(row=>{const app=pcState(row);return <article key={row.id}><b>{row.scope?.topic||row.id}</b><span>{row.problem_count||0}개 문제 · {row.status}</span><small>전체 PC: {allPcSummary(row)}</small><small>현재 PC: {app?`${app.status} · ${app.model_name||'-'}`:'미적용'}</small><div className="llm-learning-actions">{!app?.enabled&&<button className="primary" disabled={applyRunning} onClick={()=>startLearningApply(row)}>학습 적용</button>}{app?.installed&&app?.enabled&&<button disabled={!!busy} onClick={()=>setEnabled(row,false)}>현재 PC 사용 중지</button>}{app?.installed&&!app?.enabled&&<button disabled={!!busy} onClick={()=>setEnabled(row,true)}>현재 PC 다시 사용</button>}</div></article>})}</div>}
    </div>
  </div>,contentHost):null
  return <>{nav}{page}</>
}
