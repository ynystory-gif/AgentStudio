import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../../api'

type CaseRow = Record<string, any>
type DatasetRow = Record<string, any>
type JobRow = Record<string, any>

const REOPEN_KEY='theanova.agentstudio.learning.reopen'

export function LlmLearningCenter() {
  const reopen=sessionStorage.getItem(REOPEN_KEY)==='1'
  if(reopen)sessionStorage.removeItem(REOPEN_KEY)
  const [open,setOpen]=useState(reopen)
  const [tab,setTab]=useState<'cases'|'datasets'|'training'>('cases')
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
    setSummary(s||{})
    setCases(c?.items||[])
    setDatasets(d?.items||[])
    return {summary:s,cases:c,datasets:d}
  }
  useEffect(()=>{if(open)refresh().catch(e=>setMessage(String(e)))},[open,provider])

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
          setMessage(next?.message||`문제 수집 완료 · Dataset ${generated.length}개 생성`)
          await refresh()
          if(generated.length){
            setSelectedDatasetId(String(generated[0]?.id||''))
            setTab('datasets')
          }
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
    setMessage(`문제 수집 준비 · 오판 주제 ${maxCases}개 × 주제당 ${targetPerCase}문제 = 최대 ${maxCases*targetPerCase}문제`)
    try{
      const job=await api<any>('/learning/problems/collect-job',{method:'POST',body:JSON.stringify({target_per_case:targetPerCase,max_cases:maxCases,provider:'ollama'})})
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

  const page=open?createPortal(<div className="nav-page-shell llm-learning-page" aria-label="LLM 학습 센터">
    <div className="nav-page-head"><div><div className="eyebrow">LEARNING</div><h2>LLM 학습 센터</h2><p>오판 수집 → 문제 수집 → 문제 확인/검증 → 현재 PC 학습 적용</p></div></div>
    <div className="llm-learning-shared-db-note"><b>공용 학습 데이터</b><span>유사 오판은 하나의 주제로 묶어 횟수와 최근 발생일을 관리합니다. 75% 이상은 자동 확정합니다. 현재 PC에 학습 적용된 과거 오판은 이 PC 목록에서 숨깁니다.</span><em>현재 PC: {summary.current_pc_name||'-'}</em></div>
    <div className="llm-learning-model-upgrade"><div><small>현재 Ollama</small><strong>{summary.current_ollama_model||'-'}</strong></div><div><small>권장 최신 로컬 모델</small><strong>{recommended.recommended_model||'qwen3.5:4b'}</strong></div><div className="llm-learning-model-path"><small>공통 모델 관리 경로</small><code>{recommended.common_models_root||'설정되지 않음'}</code></div><button disabled={downloadRunning||summary.current_ollama_model==='qwen3.5:4b'} onClick={startDownloadRecommended}>{summary.current_ollama_model==='qwen3.5:4b'?'qwen3.5:4b 적용됨':downloadRunning?'다운로드 중...':'qwen3.5:4b 다운로드 및 적용'}</button></div>
    {progressBlock(modelJob,'모델 다운로드/적용')}{progressBlock(problemJob,'문제 수집')}{progressBlock(applyJob,'학습 적용')}
    <div className="llm-learning-metrics"><div><b>{candidateCount}</b><span>75% 미만 검토 후보</span></div><div><b>{confirmedCount}</b><span>자동/확정 오판 주제</span></div><div><b>{datasets.length}</b><span>공용 Dataset</span></div><div><b>{summary.current_ollama_model||'-'}</b><span>현재 Ollama</span></div></div>
    <div className="llm-learning-toolbar"><button className={tab==='cases'?'active':''} onClick={()=>setTab('cases')}>1. 오판 수집</button><button className={tab==='datasets'?'active':''} onClick={()=>setTab('datasets')}>2. 수집 문제 / Dataset</button><button className={tab==='training'?'active':''} onClick={()=>setTab('training')}>3. PC별 학습 적용 관리</button><span/><button disabled={!!busy||problemRunning||applyRunning} onClick={()=>run('오판 수집',()=>api('/learning/misjudgments/sync',{method:'POST'}))}>↻ 오판 수집</button><button className="primary" disabled={!!busy||problemRunning||applyRunning} onClick={startProblemCollection}>＋ 문제 수집</button></div>
    <div className="llm-problem-help"><b>문제 수집:</b> 처리할 오판 주제 수를 1~20개에서 선택한 뒤, 주제 하나당 생성할 문제 수를 1~500개에서 정합니다. 예: 오판 주제 1개 × 1문제 = 최대 1문제.</div>
    {message&&<div className="llm-learning-message">{busy?`${busy} 중... `:''}{message}</div>}
    <div className="llm-learning-body">
      {tab==='cases'&&<><div className="llm-learning-filter"><label>모델 제공자 <select value={provider} onChange={e=>setProvider(e.target.value)}><option value="">전체</option>{providers.map(p=><option key={p}>{p}</option>)}</select></label><em>학습 데이터 유무는 공용 Dataset 기준이며, 현재 PC 적용 여부도 함께 표시합니다.</em></div><table className="llm-case-table"><thead><tr><th>상태</th><th>횟수</th><th>최근 발생</th><th>수집 PC</th><th>Provider / Model</th><th>감지 사유</th><th>학습 데이터</th><th>사용자 요청 / 잘못된 결과</th><th>작업</th></tr></thead><tbody>{cases.map(row=><tr key={row.id}><td><b>{row.status}</b><small>{Math.round((row.confidence||0)*100)}%</small></td><td><b className="occurrence-count">{row.occurrence_count||1}</b></td><td className="date-cell">{fmtDate(row.last_occurred_at||row.updated_at)}</td><td><b>{row.source_pc_name||'-'}</b></td><td><b>{row.provider}</b><small>{row.model}</small></td><td>{row.detection_reason}</td><td><b>{row.learning_data_exists?'있음':'없음'}</b><small>{row.learning_data_label||'학습 데이터 없음'}</small>{row.learning_data_current_pc_applied&&<small>현재 PC 적용됨</small>}</td><td><div className="case-text-scroll"><b>[사용자 요청]</b><pre>{row.user_request||'-'}</pre><b>[잘못된 결과]</b><pre>{row.wrong_output||'-'}</pre>{row.correction_evidence&&<><b>[수정 증거]</b><pre>{row.correction_evidence}</pre></>}</div></td><td><div className="llm-learning-actions"><button onClick={()=>rejectGroup(row)}>제외</button></div></td></tr>)}</tbody></table></>}
      {tab==='datasets'&&<><table className="llm-dataset-table"><thead><tr><th>상태</th><th>생성 PC</th><th>학습 주제</th><th>문제 수</th><th>검증</th><th>현재 PC</th><th>작업</th></tr></thead><tbody>{datasets.map(row=>{const app=pcState(row);return <tr key={row.id} className={selectedDatasetId===String(row.id)?'selected':''}><td>{row.status}</td><td>{row.source_pc_name||'-'}</td><td><b>{row.scope?.domain||'-'} / {row.scope?.topic||'-'}</b><small>{row.scope?.learning_objective||''}</small></td><td>{row.problem_count||0}</td><td>{row.validation?.approved||0} 승인 / {row.validation?.pending||0} 대기</td><td><b>{app?.enabled?'학습 적용됨':app?.installed?'설치됨':'미적용'}</b><small>{app?.model_name||''}</small></td><td><div className="llm-learning-actions"><button onClick={()=>setSelectedDatasetId(String(row.id))}>문제 보기</button>{row.status==='review'&&<button onClick={()=>validate(row)}>검증</button>}{!app?.enabled&&<button className="primary" disabled={applyRunning} onClick={()=>startLearningApply(row)}>학습 적용</button>}{app?.enabled&&<button disabled={!!busy} onClick={()=>setEnabled(row,false)}>사용 중지</button>}</div></td></tr>})}</tbody></table>{selectedDataset&&<div className="llm-problem-viewer"><div className="llm-problem-viewer-head"><div><strong>수집된 문제</strong><small>{selectedDataset.scope?.domain||'-'} / {selectedDataset.scope?.topic||'-'} · 총 {selectedDataset.problem_count||selectedDataset.problems?.length||0}개</small></div><button className="primary" disabled={applyRunning||pcState(selectedDataset)?.enabled} onClick={()=>startLearningApply(selectedDataset)}>{pcState(selectedDataset)?.enabled?'현재 PC 학습 적용됨':applyRunning?'학습 적용 중...':'학습 적용'}</button></div><div className="llm-problem-list"><table><thead><tr><th>#</th><th>유형/난이도</th><th>문제 / 지시</th><th>입력 / 상황</th><th>정답 / 권장 응답</th></tr></thead><tbody>{(selectedDataset.problems||[]).map((problem:any,index:number)=><tr key={problem.id||index}><td>{index+1}</td><td><b>{problem.problem_type||'-'}</b><small>{problem.difficulty||'-'}</small></td><td><div className="problem-text">{problem.instruction||'-'}</div></td><td><div className="problem-text">{problem.input||'-'}</div></td><td><div className="problem-text answer">{problem.output||'-'}</div></td></tr>)}</tbody></table></div><div className="llm-problem-apply-note">현재 <b>학습 적용</b>은 검증된 문제를 현재 PC의 Ollama 커리큘럼 모델에 적용합니다. 공용 Dataset은 그대로 유지되고 적용 여부만 PC별로 관리됩니다.</div></div>}</>}
      {tab==='training'&&<div className="llm-learning-training"><h3>PC별 학습 적용 현황</h3><p>Dataset은 모든 등록 PC가 공통 조회하고 실제 학습 적용은 PC별로 독립 관리합니다. 이 PC에 적용된 오판 주제의 기존 기록은 오판 목록에서 숨겨집니다.</p>{datasets.map(row=>{const app=pcState(row);return <article key={row.id}><b>{row.scope?.topic||row.id}</b><span>{row.problem_count||0}개 문제 · {row.status}</span><small>전체 PC: {allPcSummary(row)}</small><small>현재 PC: {app?`${app.status} · ${app.model_name||'-'}`:'미적용'}</small><div className="llm-learning-actions">{!app?.enabled&&<button className="primary" disabled={applyRunning} onClick={()=>startLearningApply(row)}>학습 적용</button>}{app?.installed&&app?.enabled&&<button disabled={!!busy} onClick={()=>setEnabled(row,false)}>현재 PC 사용 중지</button>}{app?.installed&&!app?.enabled&&<button disabled={!!busy} onClick={()=>setEnabled(row,true)}>현재 PC 다시 사용</button>}</div></article>})}</div>}
    </div>
  </div>,contentHost):null
  return <>{nav}{page}</>
}
