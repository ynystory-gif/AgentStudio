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

  return <>
    <button className="llm-learning-nav-button" type="button" onClick={()=>setOpen(true)} title="LLM 오판 학습">🧠<span>학습</span></button>
    {open&&<div className="llm-learning-overlay" role="dialog" aria-modal="true">
      <div className="llm-learning-window">
        <header><div><strong>🧠 LLM 학습 센터</strong><small>오판 수집 → 관련 문제 대량 생성 → 검증 → 학습/평가 → Ollama 적용</small></div><button onClick={()=>setOpen(false)}>✕</button></header>
        <div className="llm-learning-metrics">
          <div><b>{summary?.cases?.candidate||0}</b><span>검토 대기</span></div><div><b>{summary?.cases?.confirmed||0}</b><span>확정 오판</span></div><div><b>{datasets.length}</b><span>Dataset</span></div><div><b>{summary.current_ollama_model||'-'}</b><span>현재 Ollama</span></div>
        </div>
        <nav><button className={tab==='cases'?'active':''} onClick={()=>setTab('cases')}>1. 오판/문제 생성</button><button className={tab==='datasets'?'active':''} onClick={()=>setTab('datasets')}>2. Dataset 검증</button><button className={tab==='training'?'active':''} onClick={()=>setTab('training')}>3. 학습·평가·적용</button><span/><button disabled={!!busy} onClick={()=>run('동기화',()=>api('/learning/misjudgments/sync',{method:'POST'}))}>↻ 수집 동기화</button></nav>
        {message&&<div className="llm-learning-message">{busy?`${busy} 중... `:''}{message}</div>}
        <main>
          {tab==='cases'&&<><div className="llm-learning-filter"><label>모델 제공자 <select value={provider} onChange={e=>setProvider(e.target.value)}><option value="">전체</option>{providers.map(p=><option key={p}>{p}</option>)}</select></label><em>후보는 자동 학습되지 않습니다. 기대 결과를 확인하여 오판을 확정해야 문제 생성이 가능합니다.</em></div>
          <table><thead><tr><th>상태</th><th>Provider / Model</th><th>감지 사유</th><th>사용자 요청 / 잘못된 결과</th><th>작업</th></tr></thead><tbody>{cases.map(row=><tr key={row.id}><td>{row.status}</td><td><b>{row.provider}</b><small>{row.model}</small></td><td>{row.detection_reason}<small>{Math.round((row.confidence||0)*100)}%</small></td><td><b>{row.user_request||'-'}</b><small>{row.wrong_output||'-'}</small>{row.expected_output&&<em>정답: {row.expected_output}</em>}</td><td><div className="llm-learning-actions">{row.status==='candidate'&&<><button onClick={()=>confirmCase(row)}>오판 확정</button><button onClick={()=>rejectCase(row)}>제외</button></>}{row.status==='confirmed'&&<button onClick={()=>generate(row)}>관련 문제 대량 생성</button>}</div></td></tr>)}</tbody></table></>}
          {tab==='datasets'&&<table><thead><tr><th>상태</th><th>학습 범위</th><th>문제 수</th><th>검증</th><th>작업</th></tr></thead><tbody>{datasets.map(row=><tr key={row.id}><td>{row.status}</td><td><b>{row.scope?.domain||'-'} / {row.scope?.topic||'-'}</b><small>{row.scope?.learning_objective||''}</small></td><td>{row.problem_count||0}</td><td>{row.validation?.approved||0} 승인 / {row.validation?.pending||0} 대기</td><td>{row.status==='review'&&<button onClick={()=>validate(row)}>전체 검증 완료</button>}{row.status==='validated'&&<button onClick={()=>prepare(row)}>학습 준비</button>}</td></tr>)}</tbody></table>}
          {tab==='training'&&<div className="llm-learning-training"><h3>학습 적용 안전 Gate</h3><p>① 검증 완료 Dataset만 학습 → ② Train/Validation/Test 분리 → ③ LoRA/QLoRA 학습 → ④ 기존 모델과 Blind Test 비교 → ⑤ 최소 향상폭 통과 → ⑥ Ollama 등록 순서입니다.</p><p><b>현재 Base Model:</b> {summary.current_ollama_model||'-'} · <b>라우팅:</b> {summary.current_strategy||'-'}</p><div className="llm-learning-gate">자동 배포 금지: 평가를 통과하지 않은 Adapter는 Ollama 적용 API에서도 차단됩니다.</div>{datasets.filter(x=>x.status==='training'||x.status==='trained'||x.status==='deployed').map(row=><article key={row.id}><b>{row.scope?.topic||row.id}</b><span>{row.status} · Train {row.split?.train||0} / Validation {row.split?.validation||0} / Test {row.split?.test||0}</span><small>{row.training?.dataset_dir||''}</small></article>)}</div>}
        </main>
      </div>
    </div>}
  </>
}
