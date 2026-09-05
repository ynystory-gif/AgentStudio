import React, { useEffect, useMemo, useState } from 'react'
import { OptionHelp } from '../../../components/common/OptionHelp'
import { asLegacyError } from '../../../utils/errors'
import {
  createRagAccessRule,
  createRagEvaluationCase,
  deleteRagAccessRule,
  deleteRagEvaluationCase,
  detectRagSourceChanges,
  loadRagAccessRules,
  loadRagDocumentVersions,
  loadRagEvaluationCases,
  loadRagEvaluationRuns,
  loadRagOperationDocuments,
  loadRagOperationSources,
  loadRagSearchAudits,
  loadRagSyncJobs,
  rollbackRagDocumentVersion,
  saveRagDocumentSecurity,
  saveRagSourceSyncMode,
  setRagDocumentActive,
  setRagSourceActive,
  startRagEvaluation,
  startRagSourceSync,
} from '../ragApi'
import type {
  RagAccessRule,
  RagChangeDetection,
  RagCollection,
  RagDocumentVersion,
  RagEvaluationCase,
  RagEvaluationRun,
  RagOperationDocument,
  RagSearchAuditLog,
  RagSecurityContext,
  RagSourceOperation,
  RagSyncJob,
} from '../ragTypes'

interface RagOperationPanelProps{
  projectRoot:string
  collections:RagCollection[]
  securityContext:RagSecurityContext
  onSecurityContextChange:(next:RagSecurityContext)=>void
}

const SECURITY_LEVELS=['PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED'] as const
const SYNC_MODES=[
  {value:'MANUAL',label:'수동'},
  {value:'ON_PROJECT_OPEN',label:'프로젝트 열기 시'},
  {value:'DAILY',label:'하루 1회'},
  {value:'CHANGE_DETECT',label:'원본 변경 감지'},
]

function pct(value:number):string{return `${Math.round(Math.max(0,Math.min(1,Number(value||0)))*100)}%`}
function dateText(value?:string|null):string{return value?new Date(value).toLocaleString():'-'}

export function RagOperationPanel({projectRoot,collections,securityContext,onSecurityContextChange}:RagOperationPanelProps){
  const [sources,setSources]=useState<RagSourceOperation[]>([])
  const [documents,setDocuments]=useState<RagOperationDocument[]>([])
  const [syncJobs,setSyncJobs]=useState<RagSyncJob[]>([])
  const [changeResult,setChangeResult]=useState<RagChangeDetection|null>(null)
  const [selectedSourceId,setSelectedSourceId]=useState<number|null>(null)
  const [selectedDocumentId,setSelectedDocumentId]=useState<number|null>(null)
  const [versions,setVersions]=useState<RagDocumentVersion[]>([])
  const [accessRules,setAccessRules]=useState<RagAccessRule[]>([])
  const [audits,setAudits]=useState<RagSearchAuditLog[]>([])
  const [evaluationCases,setEvaluationCases]=useState<RagEvaluationCase[]>([])
  const [evaluationRuns,setEvaluationRuns]=useState<RagEvaluationRun[]>([])
  const [ruleDraft,setRuleDraft]=useState({collection_id:0,subject_type:'ROLE',subject_value:'DEVELOPER',effect:'ALLOW'})
  const [caseDraft,setCaseDraft]=useState({question:'',expected_document_path:'',expected_text:''})
  const [busy,setBusy]=useState('')
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')

  const selectedSource=useMemo(()=>sources.find((item)=>item.id===selectedSourceId)||null,[sources,selectedSourceId])
  const selectedDocument=useMemo(()=>documents.find((item)=>item.id===selectedDocumentId)||null,[documents,selectedDocumentId])
  const activeSync=useMemo(()=>syncJobs.some((item)=>['PENDING','RUNNING'].includes(item.status)),[syncJobs])
  const activeEvaluation=useMemo(()=>evaluationRuns.some((item)=>['PENDING','RUNNING'].includes(item.status)),[evaluationRuns])
  const collectionName=useMemo(()=>new Map(collections.map((item)=>[item.id,item.name] as const)),[collections])

  const run=async<T,>(key:string,work:()=>Promise<T>,success?:string):Promise<T|undefined>=>{
    setBusy(key);setError('');setNotice('')
    try{const result=await work();if(success)setNotice(success);return result}
    catch(exc){setError(asLegacyError(exc).message||String(exc));return undefined}
    finally{setBusy('')}
  }

  const refresh=async()=>{
    const result=await run('refresh-operation',()=>Promise.all([
      loadRagOperationSources(projectRoot),
      loadRagSyncJobs(projectRoot),
      loadRagAccessRules(projectRoot),
      loadRagSearchAudits(projectRoot,80),
      loadRagEvaluationCases(projectRoot),
      loadRagEvaluationRuns(projectRoot,20),
    ]))
    if(!result)return
    const [sourceItems,jobItems,ruleItems,auditItems,caseItems,runItems]=result
    setSources(sourceItems);setSyncJobs(jobItems);setAccessRules(ruleItems);setAudits(auditItems);setEvaluationCases(caseItems);setEvaluationRuns(runItems)
    if(selectedSourceId==null){const first=sourceItems[0];if(first)setSelectedSourceId(first.id)}
  }

  useEffect(()=>{refresh()},[projectRoot])

  useEffect(()=>{
    if(selectedSourceId==null){setDocuments([]);setSelectedDocumentId(null);return}
    let cancelled=false
    loadRagOperationDocuments(projectRoot,selectedSourceId).then((items)=>{
      if(cancelled)return
      setDocuments(items)
      const current=items.find((item)=>item.id===selectedDocumentId)
      if(!current){const first=items[0];setSelectedDocumentId(first?first.id:null)}
    }).catch((exc)=>{if(!cancelled)setError(asLegacyError(exc).message||String(exc))})
    return()=>{cancelled=true}
  },[projectRoot,selectedSourceId])

  useEffect(()=>{
    if(selectedDocumentId==null){setVersions([]);return}
    let cancelled=false
    loadRagDocumentVersions(selectedDocumentId).then((items)=>{if(!cancelled)setVersions(items)}).catch((exc)=>{if(!cancelled)setError(asLegacyError(exc).message||String(exc))})
    return()=>{cancelled=true}
  },[selectedDocumentId])

  useEffect(()=>{
    if(!activeSync&&!activeEvaluation)return
    const timer=window.setInterval(async()=>{
      try{
        const [jobs,runs,sourceItems,auditItems]=await Promise.all([loadRagSyncJobs(projectRoot),loadRagEvaluationRuns(projectRoot,20),loadRagOperationSources(projectRoot),loadRagSearchAudits(projectRoot,80)])
        setSyncJobs(jobs);setEvaluationRuns(runs);setSources(sourceItems);setAudits(auditItems)
        if(selectedSourceId!=null)setDocuments(await loadRagOperationDocuments(projectRoot,selectedSourceId))
      }catch{/* manual actions surface errors */}
    },1800)
    return()=>window.clearInterval(timer)
  },[activeSync,activeEvaluation,projectRoot,selectedSourceId])

  const detectChanges=async(source:RagSourceOperation)=>{
    const result=await run(`changes-${source.id}`,()=>detectRagSourceChanges(source.id),'원본 변경 검사를 완료했습니다.')
    if(result){setChangeResult(result);setSources(await loadRagOperationSources(projectRoot))}
  }
  const syncSource=async(source:RagSourceOperation)=>{
    const result=await run(`sync-${source.id}`,()=>startRagSourceSync(source.id),'증분 Re-index Job을 시작했습니다.')
    if(result){setSyncJobs((prev)=>[result,...prev.filter((item)=>item.id!==result.id)]);setSelectedSourceId(source.id)}
  }
  const toggleSource=async(source:RagSourceOperation)=>{
    const result=await run(`source-active-${source.id}`,()=>setRagSourceActive(source.id,!source.is_active),source.is_active?'Source를 검색 대상에서 비활성화했습니다.':'Source를 다시 활성화했습니다.')
    if(result)setSources((prev)=>prev.map((item)=>item.id===source.id?{...item,is_active:result.is_active}:item))
  }
  const toggleDocument=async(document:RagOperationDocument)=>{
    const result=await run(`document-active-${document.id}`,()=>setRagDocumentActive(document.id,!document.is_active),document.is_active?'문서를 검색 대상에서 비활성화했습니다.':'문서를 다시 활성화했습니다.')
    if(result)setDocuments((prev)=>prev.map((item)=>item.id===document.id?{...item,is_active:result.is_active,status:result.status}:item))
  }
  const changeDocumentSecurity=async(document:RagOperationDocument,level:string)=>{
    const result=await run(`document-security-${document.id}`,()=>saveRagDocumentSecurity(document.id,level,document.security_note),'문서 보안등급을 저장했습니다.')
    if(result)setDocuments((prev)=>prev.map((item)=>item.id===document.id?{...item,security_level:level}:item))
  }
  const rollback=async(version:RagDocumentVersion)=>{
    if(!window.confirm(`v${version.version_no}으로 Rollback할까요?\n현재 Index 상태는 자동으로 백업 Version을 만든 뒤 복원합니다.`))return
    const result=await run(`rollback-${version.id}`,()=>rollbackRagDocumentVersion(version.id),`v${version.version_no} Rollback을 완료했습니다.`)
    if(result&&selectedDocumentId!=null){setVersions(await loadRagDocumentVersions(selectedDocumentId));setDocuments(await loadRagOperationDocuments(projectRoot,selectedSourceId))}
  }
  const addRule=async()=>{
    if(!ruleDraft.collection_id){setError('Access Rule 대상 Knowledge Collection을 선택하세요.');return}
    const result=await run('rule-create',()=>createRagAccessRule({project_root:projectRoot,...ruleDraft}),'Access Rule을 추가했습니다.')
    if(result)setAccessRules(await loadRagAccessRules(projectRoot))
  }
  const removeRule=async(rule:RagAccessRule)=>{
    const result=await run(`rule-delete-${rule.id}`,()=>deleteRagAccessRule(rule.id),'Access Rule을 삭제했습니다.')
    if(result)setAccessRules((prev)=>prev.filter((item)=>item.id!==rule.id))
  }
  const addCase=async()=>{
    if(!caseDraft.question.trim()){setError('Evaluation 질문을 입력하세요.');return}
    const result=await run('eval-case-create',()=>createRagEvaluationCase({project_root:projectRoot,question:caseDraft.question.trim(),expected_document_path:caseDraft.expected_document_path.trim(),expected_text:caseDraft.expected_text.trim()}),'Evaluation Case를 추가했습니다.')
    if(result){setEvaluationCases((prev)=>[...prev,result]);setCaseDraft({question:'',expected_document_path:'',expected_text:''})}
  }
  const removeCase=async(item:RagEvaluationCase)=>{
    const result=await run(`eval-case-delete-${item.id}`,()=>deleteRagEvaluationCase(item.id),'Evaluation Case를 삭제했습니다.')
    if(result)setEvaluationCases((prev)=>prev.filter((value)=>value.id!==item.id))
  }
  const runEvaluation=async()=>{
    const result=await run('eval-run',()=>startRagEvaluation(projectRoot,securityContext),'현재 Test User / Role / Clearance 기준으로 반복 Evaluation을 시작했습니다.')
    if(result)setEvaluationRuns((prev)=>[result,...prev.filter((item)=>item.id!==result.id)])
  }

  const latestEvaluation=evaluationRuns[0]

  return <div className="rag-operation-layout">
    {(error||notice)&&<div className={`rag-message ${error?'error':'success'}`}>{error||notice}</div>}

    <section className="rag-section rag-operation-sync">
      <div className="rag-section-head"><div><strong>Sync / 변경 감지 / 증분 Re-index</strong><small>원본 전체를 매번 다시 Embedding하지 않고 Added / Changed / Removed 문서만 반영합니다.</small></div><button type="button" onClick={refresh} disabled={Boolean(busy)}>새로고침</button></div>
      <div className="rag-operation-source-list">{sources.map((source)=><article key={source.id} className={!source.is_active?'disabled':''}>
        <header><div><strong>{source.display_name||source.source_uri}</strong><small>{source.source_type} · 문서 {source.document_count} · {source.status}</small></div><span>{source.is_active?'Active':'Disabled'}</span></header>
        <div className="rag-operation-source-controls"><label><span>Sync Mode</span><select value={source.sync_mode} onChange={async(event)=>{const mode=event.target.value;await run(`sync-mode-${source.id}`,()=>saveRagSourceSyncMode(source.id,mode),'Sync Mode를 저장했습니다.');setSources((prev)=>prev.map((item)=>item.id===source.id?{...item,sync_mode:mode}:item))}}>{SYNC_MODES.map((mode)=><option key={mode.value} value={mode.value}>{mode.label}</option>)}</select></label><button type="button" onClick={()=>detectChanges(source)} disabled={Boolean(busy)}>변경 확인</button><button type="button" className="rag-primary" onClick={()=>syncSource(source)} disabled={Boolean(busy)||!source.is_active}>증분 Re-index</button><button type="button" onClick={()=>toggleSource(source)} disabled={Boolean(busy)}>{source.is_active?'Disable':'Enable'}</button></div>
        <small>마지막 확인 {dateText(source.last_checked_at)} · 마지막 Sync {dateText(source.last_synced_at)} · 마지막 변경 {source.last_change_count}</small>
      </article>)}{!sources.length&&<div className="rag-empty">운영할 RAG Source가 없습니다.</div>}</div>
      {changeResult&&<div className="rag-change-result"><strong>{changeResult.source_name} · 변경 {changeResult.change_count}</strong><span>Added {changeResult.added.length}</span><span>Changed {changeResult.changed.length}</span><span>Removed {changeResult.removed.length}</span><span>Unchanged {changeResult.unchanged.length}</span><div>{[...changeResult.added,...changeResult.changed,...changeResult.removed].slice(0,12).map((item,index)=><small key={`${item.path}-${index}`}>• {item.path}</small>)}</div></div>}
      <div className="rag-sync-jobs">{syncJobs.slice(0,6).map((job)=><div key={job.id}><strong>Sync #{job.id} · {job.status}</strong><span>{job.stage} · {job.progress}%</span><small>+{job.added_count} / Δ{job.changed_count} / -{job.removed_count} · Chunk {job.chunks_updated} · Embedding {job.embeddings_updated}{job.error_message?` · ${job.error_message}`:''}</small><div className="rag-progress"><i style={{width:`${job.progress}%`}}/></div></div>)}</div>
    </section>

    <section className="rag-section rag-version-security">
      <div className="rag-section-head"><div><strong>Version / Rollback / Disable / 문서 보안등급</strong><small>Sync 전에 현재 Chunk 구조를 Version으로 보관하고 필요하면 재-Embedding하여 Rollback합니다.</small></div><OptionHelp title="Document Security" summary="Safety Scan 위험도와 문서 보안등급은 별개입니다." detail="Safety Level은 Secret/Prompt Injection 탐지 결과이고, Security Level은 사용자 Role이 검색 가능한지 결정하는 업무 보안등급입니다."/></div>
      <div className="rag-operation-two-col"><div><label className="rag-inline-field"><span>Source</span><select value={selectedSourceId??''} onChange={(event)=>setSelectedSourceId(Number(event.target.value)||null)}><option value="">선택</option>{sources.map((source)=><option key={source.id} value={source.id}>{source.display_name||source.source_uri}</option>)}</select></label><div className="rag-operation-doc-list">{documents.map((document)=><button type="button" key={document.id} className={document.id===selectedDocumentId?'active':''} onClick={()=>setSelectedDocumentId(document.id)}><strong>{document.path}</strong><small>{document.status} · Chunk {document.chunk_count} · v{document.current_version_no??'-'} · {document.security_level}</small></button>)}{!documents.length&&<div className="rag-empty">Indexed Document가 없습니다.</div>}</div></div>
      <div>{selectedDocument?<><div className="rag-document-operation-card"><strong>{selectedDocument.path}</strong><div><span>Safety {selectedDocument.safety_level}</span><span>Version {selectedDocument.version_count}</span><span>{selectedDocument.is_active?'Active':'Disabled'}</span></div><label><span>문서 보안등급</span><select value={selectedDocument.security_level} onChange={(event)=>changeDocumentSecurity(selectedDocument,event.target.value)}>{SECURITY_LEVELS.map((level)=><option key={level} value={level}>{level}</option>)}</select></label><button type="button" onClick={()=>toggleDocument(selectedDocument)}>{selectedDocument.is_active?'검색에서 Disable':'검색에 Enable'}</button></div><div className="rag-version-list">{versions.map((version)=><article key={version.id} className={version.is_current?'current':''}><div><strong>v{version.version_no}{version.is_current?' · Current':''}</strong><small>{version.chunk_count} chunks · {version.created_by} · {dateText(version.created_at)}</small></div><button type="button" disabled={version.is_current||Boolean(busy)} onClick={()=>rollback(version)}>Rollback</button></article>)}{!versions.length&&<div className="rag-empty">Version이 없습니다. Indexed 문서를 선택하면 현재 상태를 v1로 보관합니다.</div>}</div></>:<div className="rag-empty large">문서를 선택하세요.</div>}</div></div>
    </section>

    <section className="rag-section rag-access-section">
      <div className="rag-section-head"><div><strong>Role / Access Rule</strong><small>Retrieval 전에 허용 Collection을 계산하고 문서 Security Level까지 적용합니다. DENY가 ALLOW보다 우선합니다.</small></div></div>
      <div className="rag-security-context"><label><span>Test User</span><input value={securityContext.user_id} onChange={(event)=>onSecurityContextChange({...securityContext,user_id:event.target.value})}/></label><label><span>Role</span><input value={securityContext.role} onChange={(event)=>onSecurityContextChange({...securityContext,role:event.target.value.toUpperCase()})}/></label><label><span>Clearance</span><select value={securityContext.security_clearance} onChange={(event)=>onSecurityContextChange({...securityContext,security_clearance:event.target.value})}>{SECURITY_LEVELS.map((level)=><option key={level} value={level}>{level}</option>)}</select></label><small>이 Context는 Retrieval Test의 권한 필터 검증에 사용됩니다. 실제 서비스에서는 로그인 사용자 Context를 주입해야 합니다.</small></div>
      <div className="rag-rule-create"><select value={ruleDraft.collection_id} onChange={(event)=>setRuleDraft((prev)=>({...prev,collection_id:Number(event.target.value)||0}))}><option value={0}>Collection 선택</option>{collections.map((item)=><option key={item.id} value={item.id}>{item.name} · {item.security_level}</option>)}</select><select value={ruleDraft.subject_type} onChange={(event)=>setRuleDraft((prev)=>({...prev,subject_type:event.target.value}))}><option value="ROLE">Role</option><option value="USER">User</option><option value="ALL">All</option></select><input value={ruleDraft.subject_value} disabled={ruleDraft.subject_type==='ALL'} placeholder="DEVELOPER 또는 user id" onChange={(event)=>setRuleDraft((prev)=>({...prev,subject_value:event.target.value}))}/><select value={ruleDraft.effect} onChange={(event)=>setRuleDraft((prev)=>({...prev,effect:event.target.value}))}><option value="ALLOW">ALLOW</option><option value="DENY">DENY</option></select><button type="button" className="rag-primary" onClick={addRule}>Rule 추가</button></div>
      <div className="rag-rule-list">{accessRules.map((rule)=><div key={rule.id}><strong>{rule.effect} · {collectionName.get(rule.collection_id)||`Collection #${rule.collection_id}`}</strong><span>{rule.subject_type}:{rule.subject_value}</span><button type="button" onClick={()=>removeRule(rule)}>삭제</button></div>)}{!accessRules.length&&<div className="rag-empty">명시적 Access Rule이 없습니다. Collection Security Level 기준으로 검색됩니다.</div>}</div>
    </section>

    <section className="rag-section rag-audit-section">
      <div className="rag-section-head"><div><strong>Search Audit Log</strong><small>누가 어떤 Role/Clearance로 어떤 Knowledge 범위를 검색했는지 별도 보안 로그로 남깁니다.</small></div></div>
      <div className="rag-audit-list">{audits.slice(0,20).map((audit)=><article key={audit.id} className={audit.decision!=='ALLOW'?'denied':''}><header><strong>#{audit.id} · {audit.decision} · {audit.role}</strong><span>{audit.security_clearance}</span></header><p>{audit.query_text}</p><small>User {audit.user_id||'-'} · Collection allow {audit.allowed_collection_ids.length} / deny {audit.denied_collection_ids.length} · Source {audit.allowed_source_count} · Result {audit.result_count}</small></article>)}{!audits.length&&<div className="rag-empty">Security-aware Retrieval을 실행하면 Audit Log가 기록됩니다.</div>}</div>
    </section>

    <section className="rag-section rag-evaluation-section">
      <div className="rag-section-head"><div><strong>반복 Evaluation / 품질 Metric</strong><small>같은 테스트 Case를 반복 실행하여 Hit Rate, MRR, Recall@K, 검색시간을 비교합니다.</small></div><button type="button" className="rag-primary" onClick={runEvaluation} disabled={Boolean(busy)||!evaluationCases.length}>{busy==='eval-run'?'시작 중...':'Evaluation 실행'}</button></div>
      {latestEvaluation&&<div className="rag-evaluation-metrics"><div><span>상태</span><strong>{latestEvaluation.status}</strong></div><div><span>Hit Rate</span><strong>{pct(latestEvaluation.hit_rate)}</strong></div><div><span>MRR</span><strong>{latestEvaluation.mrr.toFixed(3)}</strong></div><div><span>Recall@K</span><strong>{pct(latestEvaluation.recall_at_k)}</strong></div><div><span>Zero Result</span><strong>{pct(latestEvaluation.zero_result_rate)}</strong></div><div><span>평균 검색</span><strong>{latestEvaluation.avg_duration_ms} ms</strong></div><div><span>평가 권한</span><strong>{latestEvaluation.security_context?.role||'DEVELOPER'} / {latestEvaluation.security_context?.security_clearance||'RESTRICTED'}</strong></div></div>}
      <div className="rag-eval-case-create"><textarea value={caseDraft.question} placeholder="평가 질문" onChange={(event)=>setCaseDraft((prev)=>({...prev,question:event.target.value}))}/><input value={caseDraft.expected_document_path} placeholder="예상 문서 경로 (예: backend/auth.py)" onChange={(event)=>setCaseDraft((prev)=>({...prev,expected_document_path:event.target.value}))}/><input value={caseDraft.expected_text} placeholder="또는 반드시 포함될 근거 텍스트" onChange={(event)=>setCaseDraft((prev)=>({...prev,expected_text:event.target.value}))}/><button type="button" onClick={addCase}>Case 추가</button></div>
      <div className="rag-operation-two-col"><div className="rag-eval-case-list">{evaluationCases.map((item)=><article key={item.id}><div><strong>{item.question}</strong><small>{item.expected_document_path?`Path: ${item.expected_document_path}`:`Text: ${item.expected_text}`}</small></div><button type="button" onClick={()=>removeCase(item)}>삭제</button></article>)}{!evaluationCases.length&&<div className="rag-empty">평가 Case를 추가하세요.</div>}</div><div className="rag-eval-run-list">{evaluationRuns.slice(0,8).map((item)=><article key={item.id}><strong>Run #{item.id} · {item.status}</strong><span>{item.passed_cases}/{item.total_cases} · Hit {pct(item.hit_rate)} · MRR {item.mrr.toFixed(3)}</span><small>{item.avg_duration_ms} ms · {dateText(item.finished_at||item.created_at)}{item.error_message?` · ${item.error_message}`:''}</small></article>)}{!evaluationRuns.length&&<div className="rag-empty">Evaluation 실행 이력이 없습니다.</div>}</div></div>
    </section>
  </div>
}
