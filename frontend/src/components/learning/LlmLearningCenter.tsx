import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api'

type CaseRow = Record<string, any>
type DatasetRow = Record<string, any>

export function LlmLearningCenter() {
  const [open,setOpen]=useState(false)
  const [tab,setTab]=useState<'cases'|'datasets'|'training'>('cases')
  const [summary,setSummary]=useState<any>({})
  const [cases,setCases]=useState<CaseRow[]>([])
  const [datasets,setDatasets]=useState<DatasetRow[]>([])
  const [provider,setProvider]=useState('')
  const [busy,setBusy]=useState('')
  const [message,setMessage]=useState('')

  const refresh=async()=>{
    const [s,c,d]=await Promise.all([
      api<any>('/learning/summary'),
      api<any>(`/learning/misjudgments?limit=1000${provider?`&provider=${encodeURIComponent(provider)}`:''}`),
      api<any>('/learning/datasets'),
    ])
    setSummary(s||{});setCases(c?.items||[]);setDatasets(d?.items||[])
  }
  useEffect(()=>{if(open) refresh().catch(e=>setMessage(String(e)))},[open,provider])

  const providers=useMemo(()=>Array.from(new Set(cases.map(x=>String(x.provider||'unknown')))),[cases])
  const run=async(label:string,fn:()=>Promise<any>)=>{setBusy(label);setMessage('');try{const result=await fn();setMessage(result?.message||'완료되었습니다.');await refresh()}catch(e){setMessage(String(e))}finally{setBusy('')}}

  const confirmCase=async(row:CaseRow)=>{
    const expected=window.prompt('이 사례에서 모델이 했어야 하는 올바른 결과를 입력하세요.',row.expected_output||row.correction_evidence||'')
    if(!expected?.trim()) return
    const errorType=window.prompt('오판 유형을 입력하세요. 예: requirement_misunderstanding',row.error_type==='unclassified'?'':row.error_type)||'unclassified'
    await run('오판 확정',()=>api(`/learning/misjudgments/${row.id}`,{method:'PATCH',body:JSON.stringify({status:'confirmed',expected_output:expected,error_type:errorType,error_reason:row.detection_reason||'',domain:row.domain||'',topic:row.topic||''})}))
  }
  const rejectCase=(row:CaseRow)=>run('후보 제외',()=>api(`/learning/misjudgments/${row.id}`,{method:'PATCH',body:JSON.stringify({status:'rejected'})}))
  const generate=(row:CaseRow)=>{
    const raw=window.prompt('관련 범위로 생성할 문제 수를 입력하세요. (10~2000)','100')
    if(!raw) return
    const count=Math.max(10,Math.min(2000,Number(raw)||100))
    return run('관련 문제 생성',()=>api('/learning/datasets/generate',{method:'POST',body:JSON.stringify({case_id:row.id,target_count:count,provider:'ollama'})}))
  }
  const validate=(row:DatasetRow)=>run('Dataset 검증',()=>api(`/learning/datasets/${row.id}/validate`,{method:'POST',body:JSON.stringify({approved_problem_ids:[]})}))
  const prepare=(row:DatasetRow)=>run('학습 준비',()=>api(`/learning/datasets/${row.id}/prepare-training`,{method:'POST',body:JSON.stringify({base_model:summary.current_ollama_model||''})}))
  const applyCurrentPc=(row:DatasetRow)=>{
    const defaultName=`theanova-${String(row.scope?.topic||'learned').toLowerCase().replace(/[^a-z0-9가-힣_-]+/g,'-')}`
    const modelName=window.prompt(`현재 PC(${summary.current_pc_name||'-'})에 등록할 Ollama 모델 이름`,defaultName)
    if(!modelName?.trim()) return
    const defaultAdapter=row.training?.prepared_by_pc_name===summary.current_pc_name?(row.training?.adapter_dir||''):''
    const adapterPath=window.prompt('현재 PC의 학습 Adapter 경로를 입력하세요.',defaultAdapter)
    if(!adapterPath?.trim()) return
    return run('현재 PC 적용',()=>api(`/learning/datasets/${row.id}/apply-ollama`,{method:'POST',body:JSON.stringify({model_name:modelName.trim(),adapter_path:adapterPath.trim()})}))
  }
  const setEnabled=(row:DatasetRow,enabled:boolean)=>run(enabled?'현재 PC 활성화':'현재 PC 비활성화',()=>api(`/learning/datasets/${row.id}/current-pc-application`,{method:'PATCH',body:JSON.stringify({enabled})}))
  const pcState=(row:DatasetRow)=>row.current_pc_application||null
  const allPcSummary=(row:DatasetRow)=>{
    const apps=Array.isArray(row.pc_applications)?row.pc_applications:[]
    if(!apps.length) return '적용 PC 없음'
    return apps.map((x:any)=>`${x.pc_name}: ${x.enabled?'사용 중':x.installed?'설치됨':'미적용'}${x.model_name?` (${x.model_name})`:''}`).join(' · ')
  }

  return <>
    <button className="llm-learning-nav-button" type="button" onClick={()=>setOpen(true)} title="LLM 오판 학습">🧠<span>학습</span></button>
    {open&&<div className="llm-learning-overlay" role="dialog" aria-modal="true">
      <div className="llm-learning-window">
        <header><div><strong>🧠 LLM 학습 센터</strong><small>오판 수집 → 관련 문제 대량 생성 → 검증 → 학습/평가 → PC별 Ollama 적용</small></div><button onClick={()=>setOpen(false)}>✕</button></header>
        <div className="llm-learning-shared-db-note"><b>🌐 공용 학습 데이터</b><span>오판 사례·생성 문제·Dataset·검증·평가 결과는 A PC/B PC 모두 동일하게 조회합니다. 학습 모델 설치·사용 여부만 PC별로 따로 관리합니다.</span><em>현재 PC: {summary.current_pc_name||'-'}</em></div>
        <div className="llm-learning-metrics">
          <div><b>{summary?.cases?.candidate||0}</b><span>검토 대기</span></div><div><b>{summary?.cases?.confirmed||0}</b><span>확정 오판</span></div><div><b>{datasets.length}</b><span>공용 Dataset</span></div><div><b>{summary.current_ollama_model||'-'}</b><span>현재 Ollama</span></div>
        </div>
        <nav><button className={tab==='cases'?'active':''} onClick={()=>setTab('cases')}>1. 오판/문제 생성</button><button className={tab==='datasets'?'active':''} onClick={()=>setTab('datasets')}>2. Dataset 검증</button><button className={tab==='training'?'active':''} onClick={()=>setTab('training')}>3. 학습·평가·PC별 적용</button><span/><button disabled={!!busy} onClick={()=>run('동기화',()=>api('/learning/misjudgments/sync',{method:'POST'}))}>↻ 이 PC 수집 → 공용 DB</button></nav>
        {message&&<div className="llm-learning-message">{busy?`${busy} 중... `:''}{message}</div>}
        <main>
          {tab==='cases'&&<><div className="llm-learning-filter"><label>모델 제공자 <select value={provider} onChange={e=>setProvider(e.target.value)}><option value="">전체</option>{providers.map(p=><option key={p}>{p}</option>)}</select></label><em>후보는 자동 학습되지 않습니다. 어느 PC에서 수집됐든 공용 DB에서 검토 후 확정해야 문제 생성이 가능합니다.</em></div>
          <table><thead><tr><th>상태</th><th>수집 PC</th><th>Provider / Model</th><th>감지 사유</th><th>사용자 요청 / 잘못된 결과</th><th>작업</th></tr></thead><tbody>{cases.map(row=><tr key={row.id}><td>{row.status}</td><td><b>{row.source_pc_name||'-'}</b><small>{row.updated_by_pc_name&&row.updated_by_pc_name!==row.source_pc_name?`최근 수정: ${row.updated_by_pc_name}`:''}</small></td><td><b>{row.provider}</b><small>{row.model}</small></td><td>{row.detection_reason}<small>{Math.round((row.confidence||0)*100)}%</small></td><td><b>{row.user_request||'-'}</b><small>{row.wrong_output||'-'}</small>{row.expected_output&&<em>정답: {row.expected_output}</em>}</td><td><div className="llm-learning-actions">{row.status==='candidate'&&<><button onClick={()=>confirmCase(row)}>오판 확정</button><button onClick={()=>rejectCase(row)}>제외</button></>}{row.status==='confirmed'&&<button onClick={()=>generate(row)}>관련 문제 대량 생성</button>}</div></td></tr>)}</tbody></table></>}
          {tab==='datasets'&&<table><thead><tr><th>상태</th><th>생성 PC</th><th>학습 범위</th><th>문제 수</th><th>검증</th><th>PC별 적용 현황</th><th>작업</th></tr></thead><tbody>{datasets.map(row=><tr key={row.id}><td>{row.status}</td><td>{row.source_pc_name||'-'}<small>{row.updated_by_pc_name&&row.updated_by_pc_name!==row.source_pc_name?`최근 수정: ${row.updated_by_pc_name}`:''}</small></td><td><b>{row.scope?.domain||'-'} / {row.scope?.topic||'-'}</b><small>{row.scope?.learning_objective||''}</small></td><td>{row.problem_count||0}</td><td>{row.validation?.approved||0} 승인 / {row.validation?.pending||0} 대기</td><td><b>{pcState(row)?.enabled?'현재 PC 사용 중':pcState(row)?.installed?'현재 PC 설치됨':'현재 PC 미적용'}</b><small>{allPcSummary(row)}</small></td><td>{row.status==='review'&&<button onClick={()=>validate(row)}>전체 검증 완료</button>}{row.status==='validated'&&<button onClick={()=>prepare(row)}>이 PC에서 학습 준비</button>}</td></tr>)}</tbody></table>}
          {tab==='training'&&<div className="llm-learning-training"><h3>학습 적용 안전 Gate</h3><p>① 공용 DB 검증 Dataset → ② Train/Validation/Test 분리 → ③ LoRA/QLoRA 학습 → ④ 기존 모델과 Blind Test 비교 → ⑤ 최소 향상폭 통과 → ⑥ 각 PC가 필요할 때 개별 적용 순서입니다.</p><p><b>현재 Base Model:</b> {summary.current_ollama_model||'-'} · <b>라우팅:</b> {summary.current_strategy||'-'}</p><div className="llm-learning-gate">Dataset과 평가 결과는 공통입니다. A PC 적용 여부와 B PC 적용 여부는 서로 영향을 주지 않습니다.</div>{datasets.filter(x=>['training','trained','deployed'].includes(x.status)).map(row=>{const app=pcState(row);return <article key={row.id}><b>{row.scope?.topic||row.id}</b><span>{row.status} · Train {row.split?.train||0} / Validation {row.split?.validation||0} / Test {row.split?.test||0}</span><small>전체 PC: {allPcSummary(row)}</small><small>현재 PC: {app?`${app.status} · ${app.model_name||'-'}`:'미적용'}</small><div className="llm-learning-actions">{row.evaluation?.passed&&!app?.installed&&<button disabled={!!busy} onClick={()=>applyCurrentPc(row)}>현재 PC에 적용</button>}{app?.installed&&app?.enabled&&<button disabled={!!busy} onClick={()=>setEnabled(row,false)}>현재 PC 사용 중지</button>}{app?.installed&&!app?.enabled&&<button disabled={!!busy} onClick={()=>setEnabled(row,true)}>현재 PC 다시 사용</button>}</div></article>})}</div>}
        </main>
      </div>
    </div>}
  </>
}
