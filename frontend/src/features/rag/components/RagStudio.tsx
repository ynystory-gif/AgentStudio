import React, { useEffect, useMemo, useState } from 'react'
import { OptionHelp } from '../../../components/common/OptionHelp'
import { RagOperationPanel } from './RagOperationPanel'
import { asLegacyError } from '../../../utils/errors'
import {
  analyzeRagSource,
  approveRagSource,
  applyRagAiRecommendation,
  bindRagWorkflow,
  createRagCollection,
  createRagSource,
  createRagAiRecommendation,
  generateRagAgentTool,
  deleteRagCollection,
  deleteRagSource,
  loadRagCollections,
  loadRagIndexConfig,
  loadRagIndexJobs,
  loadRagAgentTestLogs,
  loadRagIntelligenceSetting,
  loadRagAgentTools,
  loadRagRetrievalOptions,
  loadRagRetrievalSetting,
  loadRagSearchLogs,
  loadRagSources,
  loadRagState,
  loadAccountProjectSettings,
  saveAccountProjectSetting,
  previewRagChunks,
  pickRagSourceFile,
  pickRagSourceFolder,
  prepareRagAgentTest,
  retrieveRag,
  markRagPromptToolRegistered,
  reviewRagSource,
  evaluateRagSettings,
  saveRagRetrievalSetting,
  saveRagIntelligenceSetting,
  saveRagState,
  startRagIndex,
  testRagDatabase,
  testRagAgentTool,
  updateRagCollection,
  updateRagPromptContext,
} from '../ragApi'
import type {
  RagAgentTestLog,
  RagAgentTestPreparation,
  RagAgentTool,
  RagAiRecommendation,
  RagChunkPreviewResult,
  RagCollection,
  RagDatabaseTestResult,
  RagIndexConfig,
  RagIndexJob,
  RagIntelligenceSetting,
  RagRetrievalMetadataFilter,
  RagRetrievalOptions,
  RagRetrievalResult,
  RagRetrievalSetting,
  RagSearchLog,
  RagSearchMode,
  RagSecurityContext,
  RagSettingEvaluation,
  RagScope,
  RagSource,
  RagSourceType,
  RagStudioSetting,
  RagToolTestResult,
  RagWorkflowBindingResult,
} from '../ragTypes'
import type { AccountDatabaseProfile } from '../ragApi'
import '../ragStudio.css'

interface RagStudioProps{
  projectRoot:string
  agentDesignProjectId?:number|null
  onSyncPromptTool?:(tool:RagAgentTool)=>void
  onBindWorkflow?:(binding:RagWorkflowBindingResult)=>void
  onOpenPromptToolStudio?:(tool:RagAgentTool)=>void
  onOpenAgentTest?:(preparation:RagAgentTestPreparation)=>void
}

type RagTab='KNOWLEDGE'|'RETRIEVAL'|'TEST'|'OPERATION'

const DEFAULT_SETTING:Pick<RagStudioSetting,'rag_enabled'|'db_provider'|'connection_mode'|'db_schema'|'scope'>={
  rag_enabled:false,
  db_provider:'POSTGRESQL_PGVECTOR',
  connection_mode:'RUNTIME',
  db_schema:'',
  scope:'AGENT',
}

const DEFAULT_METADATA_FILTER:RagRetrievalMetadataFilter={collection_ids:[],source_ids:[],document_types:[],languages:[],path_contains:''}
const DEFAULT_RETRIEVAL:Pick<RagRetrievalSetting,'search_mode'|'top_k'|'similarity_threshold'|'metadata_filter'>={
  search_mode:'HYBRID',top_k:5,similarity_threshold:0.20,metadata_filter:DEFAULT_METADATA_FILTER,
}
const DEFAULT_INTELLIGENCE:Pick<RagIntelligenceSetting,'router_enabled'|'reranking_enabled'|'rerank_top_n'>={
  router_enabled:true,reranking_enabled:true,rerank_top_n:12,
}
const SEARCH_MODE_LABEL:Record<string,string>={VECTOR:'Vector Search',KEYWORD:'Keyword Search',HYBRID:'Hybrid Search'}

const STATUS_LABEL:Record<string,string>={
  REGISTERED:'등록 완료',ANALYZING:'분석 중',REVIEW_REQUIRED:'검토 필요',REVIEWED:'검토 완료',APPROVED:'승인 완료',INDEXED:'Indexed',
}
const JOB_STATUS_LABEL:Record<string,string>={PENDING:'대기',RUNNING:'진행 중',COMPLETED:'완료',FAILED:'실패'}
const JOB_STAGE_LABEL:Record<string,string>={
  QUEUED:'대기',DOCUMENT_SCAN:'문서 탐색',DUPLICATE_SAFETY_CHUNK:'중복·안전·Chunk',CHUNK_EMBEDDING:'Embedding',HNSW_INDEX:'HNSW Index',COMPLETED:'완료',FAILED:'실패',
}
const SUITABILITY_LABEL:Record<string,string>={SUITABLE:'✓ RAG 적합',PARTIAL_REVIEW:'⚠ 일부 제외 권장',NOT_RECOMMENDED:'✕ RAG 등록 비추천',UNKNOWN:'분석 전'}
const SOURCE_TYPE_LABEL:Record<string,string>={FILE:'File',FOLDER:'Folder',SOURCE_CODE:'Source Code'}

function humanBytes(value:number|undefined):string{
  const size=Number(value||0)
  if(size<1024)return `${size} B`
  if(size<1024*1024)return `${(size/1024).toFixed(1)} KB`
  return `${(size/1024/1024).toFixed(1)} MB`
}
function replaceSource(items:RagSource[],next:RagSource):RagSource[]{return items.map((item)=>item.id===next.id?next:item)}
function sortJobs(items:RagIndexJob[]):RagIndexJob[]{return [...items].sort((a,b)=>b.id-a.id)}
function pathLeaf(value:string):string{const cleaned=String(value||'').replace(/[\\/]+$/,'');const parts=cleaned.split(/[\\/]/);return parts[parts.length-1]||''}

export function RagStudio({projectRoot,agentDesignProjectId,onSyncPromptTool,onBindWorkflow,onOpenPromptToolStudio,onOpenAgentTest}:RagStudioProps){
  const [tab,setTab]=useState<RagTab>('KNOWLEDGE')
  const [setting,setSetting]=useState<Pick<RagStudioSetting,'rag_enabled'|'db_provider'|'connection_mode'|'db_schema'|'scope'>>(DEFAULT_SETTING)
  const [collections,setCollections]=useState<RagCollection[]>([])
  const [sources,setSources]=useState<RagSource[]>([])
  const [jobs,setJobs]=useState<RagIndexJob[]>([])
  const [indexConfig,setIndexConfig]=useState<RagIndexConfig|null>(null)
  const [preview,setPreview]=useState<RagChunkPreviewResult|null>(null)
  const [previewSourceId,setPreviewSourceId]=useState<number|null>(null)
  const [busy,setBusy]=useState('')
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [dbUrl,setDbUrl]=useState('')
  const [dbResult,setDbResult]=useState<RagDatabaseTestResult|null>(null)
  const [collectionDraft,setCollectionDraft]=useState({name:'',description:'',scope:'AGENT' as RagScope,security_level:'INTERNAL'})
  const [editingCollectionId,setEditingCollectionId]=useState<number|null>(null)
  const [editCollection,setEditCollection]=useState({name:'',description:'',scope:'AGENT',security_level:'INTERNAL'})
  const [sourceDraft,setSourceDraft]=useState<{source_type:RagSourceType;source_uri:string;source_text:string;display_name:string;collection_ids:number[]}>({source_type:'FILE',source_uri:'',source_text:'',display_name:'',collection_ids:[]})
  const [expandedSourceId,setExpandedSourceId]=useState<number|null>(null)
  const [sourcePickerBusy,setSourcePickerBusy]=useState(false)
  const [retrieval,setRetrieval]=useState<Pick<RagRetrievalSetting,'search_mode'|'top_k'|'similarity_threshold'|'metadata_filter'>>(DEFAULT_RETRIEVAL)
  const [intelligence,setIntelligence]=useState<Pick<RagIntelligenceSetting,'router_enabled'|'reranking_enabled'|'rerank_top_n'>>(DEFAULT_INTELLIGENCE)
  const [evaluation,setEvaluation]=useState<RagSettingEvaluation|null>(null)
  const [recommendation,setRecommendation]=useState<RagAiRecommendation|null>(null)
  const [recommendationKeys,setRecommendationKeys]=useState<string[]>([])
  const [retrievalOptions,setRetrievalOptions]=useState<RagRetrievalOptions|null>(null)
  const [retrievalQuery,setRetrievalQuery]=useState('')
  const [retrievalResult,setRetrievalResult]=useState<RagRetrievalResult|null>(null)
  const [searchLogs,setSearchLogs]=useState<RagSearchLog[]>([])
  const [agentTools,setAgentTools]=useState<RagAgentTool[]>([])
  const [agentTestLogs,setAgentTestLogs]=useState<RagAgentTestLog[]>([])
  const [toolCollectionId,setToolCollectionId]=useState<number|null>(null)
  const [selectedAgentToolId,setSelectedAgentToolId]=useState<number|null>(null)
  const [toolTestResult,setToolTestResult]=useState<RagToolTestResult|null>(null)
  const [securityContext,setSecurityContext]=useState<RagSecurityContext>({user_id:'agentstudio-local',role:'DEVELOPER',security_clearance:'RESTRICTED'})
  const [accountDbProfiles,setAccountDbProfiles]=useState<AccountDatabaseProfile[]>([])
  const [projectDbProfileId,setProjectDbProfileId]=useState<number|null>(null)

  const projectReady=Boolean(String(projectRoot||'').trim())
  const approvedCount=useMemo(()=>sources.filter((item)=>['APPROVED','INDEXED'].includes(item.status)).length,[sources])
  const activeJobIds=useMemo(()=>jobs.filter((item)=>['PENDING','RUNNING'].includes(item.status)).map((item)=>item.id).join(','),[jobs])
  const selectedAgentTool=useMemo(()=>agentTools.find((item)=>item.id===selectedAgentToolId)||agentTools[0]||null,[agentTools,selectedAgentToolId])

  useEffect(()=>{
    let cancelled=false
    setError('')
    Promise.all([
      loadRagState(projectRoot),loadRagCollections(projectRoot),loadRagSources(projectRoot),loadRagIndexJobs(projectRoot),loadRagIndexConfig(),loadRagRetrievalSetting(projectRoot),loadRagIntelligenceSetting(projectRoot),loadRagRetrievalOptions(projectRoot),loadRagSearchLogs(projectRoot),loadRagAgentTools(projectRoot),loadRagAgentTestLogs(projectRoot),
    ]).then(([state,collectionItems,sourceItems,jobItems,config,retrievalState,intelligenceState,retrievalOptionState,logItems,toolItems,agentLogItems])=>{
      if(cancelled)return
      setSetting({rag_enabled:Boolean(state.rag_enabled),db_provider:state.db_provider||'POSTGRESQL_PGVECTOR',connection_mode:state.connection_mode||'RUNTIME',db_schema:state.db_schema||'',scope:state.scope||'AGENT'})
      setCollections(collectionItems)
      setSources(sourceItems)
      setJobs(jobItems)
      setIndexConfig(config)
      setRetrieval({search_mode:(retrievalState.search_mode||'HYBRID') as RagSearchMode,top_k:Number(retrievalState.top_k||5),similarity_threshold:Number(retrievalState.similarity_threshold??0.20),metadata_filter:{...DEFAULT_METADATA_FILTER,...(retrievalState.metadata_filter||{})}})
      setIntelligence({router_enabled:Boolean(intelligenceState.router_enabled),reranking_enabled:Boolean(intelligenceState.reranking_enabled),rerank_top_n:Number(intelligenceState.rerank_top_n||12)})
      setRetrievalOptions(retrievalOptionState)
      setSearchLogs(logItems)
      setAgentTools(toolItems)
      setAgentTestLogs(agentLogItems)
      toolItems.filter((item)=>item.prompt_tool_registered).forEach((item)=>onSyncPromptTool?.(item))
      const firstTool=toolItems[0]
      if(firstTool)setSelectedAgentToolId(firstTool.id)
      const firstCollection=collectionItems[0]
      if(firstCollection)setToolCollectionId(firstCollection.id)
    }).catch((exc)=>{if(!cancelled)setError(asLegacyError(exc).message||String(exc))})
    return ()=>{cancelled=true}
  },[projectRoot])

  useEffect(()=>{
    let cancelled=false
    if(!projectReady){setAccountDbProfiles([]);setProjectDbProfileId(null);return}
    loadAccountProjectSettings(projectRoot).then((result)=>{
      if(cancelled)return
      setAccountDbProfiles(Array.isArray(result.account_database_profiles)?result.account_database_profiles:[])
      const binding=(result.items||[]).find((item)=>item.setting_group==='RAG_DATABASE_PROFILE'&&item.setting_key==='default')
      const sourceId=Number(binding?.source_profile_id||binding?.value?.account_profile_id||0)
      setProjectDbProfileId(sourceId||null)
    }).catch(()=>{if(!cancelled){setAccountDbProfiles([]);setProjectDbProfileId(null)}})
    return()=>{cancelled=true}
  },[projectRoot,projectReady])

  useEffect(()=>{
    if(!activeJobIds)return
    let cancelled=false
    const poll=async()=>{
      try{
        const next=await loadRagIndexJobs(projectRoot)
        if(cancelled)return
        setJobs(next)
        const justFinished=next.some((job)=>['COMPLETED','FAILED'].includes(job.status) && activeJobIds.split(',').includes(String(job.id)))
        if(justFinished){
          const [nextSources,nextOptions]=await Promise.all([loadRagSources(projectRoot),loadRagRetrievalOptions(projectRoot)])
          if(!cancelled){setSources(nextSources);setRetrievalOptions(nextOptions)}
        }
      }catch{/* polling error is shown only when user triggers an action */}
    }
    const timer=window.setInterval(poll,1600)
    return ()=>{cancelled=true;window.clearInterval(timer)}
  },[activeJobIds,projectRoot])

  const run=async<T,>(key:string,work:()=>Promise<T>,success?:string):Promise<T|undefined>=>{
    setBusy(key);setError('');setNotice('')
    try{const result=await work();if(success)setNotice(success);return result}
    catch(exc){setError(asLegacyError(exc).message||String(exc));return undefined}
    finally{setBusy('')}
  }

  const changeTab=(next:RagTab)=>{setError('');setNotice('');setTab(next)}

  const persistSetting=async(patch:Partial<typeof setting>)=>{
    const next={...setting,...patch}
    setSetting(next)
    const saved=await run('setting',()=>saveRagState(projectRoot,patch),'RAG Studio 설정을 저장했습니다.')
    if(saved)setSetting({rag_enabled:Boolean(saved.rag_enabled),db_provider:saved.db_provider,connection_mode:saved.connection_mode,db_schema:saved.db_schema,scope:saved.scope})
  }

  const bindAccountDbProfile=async(profileId:number)=>{
    const profile=accountDbProfiles.find((item)=>Number(item.account_profile_id||item.account_database_profiles_id)===Number(profileId))
    if(!profile)return
    if(!['postgresql','supabase'].includes(String(profile.db_type||'').toLowerCase())){setError('RAG Vector Store는 현재 PostgreSQL / Supabase PostgreSQL 계정 설정만 연결할 수 있습니다.');return}
    const nextSchema=String(profile.schema_name||setting.db_schema||'').trim()
    const saved=await run('account-db-bind',()=>Promise.all([
      saveAccountProjectSetting({project_root:projectRoot,setting_group:'RAG_DATABASE_PROFILE',setting_key:'default',value:{account_profile_id:Number(profile.account_profile_id||profile.account_database_profiles_id),connection_id:profile.connection_id,name:profile.name,db_type:profile.db_type,host:profile.host||'',port:profile.port||0,database:profile.database||'',schema_name:profile.schema_name||'',username:profile.username||''},source_profile_id:Number(profile.account_profile_id||profile.account_database_profiles_id),title:'RAG 프로젝트 DB 설정 연결',summary:profile.name||profile.db_type}),
      nextSchema?saveRagState(projectRoot,{db_schema:nextSchema}):Promise.resolve(null),
    ]),'계정 DB 설정을 현재 RAG 프로젝트 설정에 연결했습니다.')
    if(saved){setProjectDbProfileId(Number(profile.account_profile_id||profile.account_database_profiles_id));if(nextSchema)setSetting((prev)=>({...prev,db_schema:nextSchema}))}
  }

  const addCollection=async()=>{
    const name=collectionDraft.name.trim()
    if(!name){setError('Knowledge Collection 이름을 입력하세요.');return}
    const created=await run('collection-create',()=>createRagCollection({project_root:projectRoot,agent_design_project_id:agentDesignProjectId||null,name,description:collectionDraft.description.trim(),scope:collectionDraft.scope,security_level:collectionDraft.security_level}),'Knowledge Collection을 생성했습니다.')
    if(created){setCollections((prev)=>[...prev,created].sort((a,b)=>a.name.localeCompare(b.name)));setCollectionDraft({name:'',description:'',scope:'AGENT',security_level:'INTERNAL'})}
  }

  const beginEditCollection=(item:RagCollection)=>{setEditingCollectionId(item.id);setEditCollection({name:item.name,description:item.description||'',scope:item.scope||'AGENT',security_level:item.security_level||'INTERNAL'})}
  const saveCollectionEdit=async()=>{
    if(editingCollectionId==null)return
    const updated=await run(`collection-${editingCollectionId}`,()=>updateRagCollection(editingCollectionId,editCollection),'Knowledge Collection을 수정했습니다.')
    if(updated){setCollections((prev)=>prev.map((item)=>item.id===updated.id?updated:item).sort((a,b)=>a.name.localeCompare(b.name)));setEditingCollectionId(null)}
  }
  const removeCollection=async(item:RagCollection)=>{
    if(!window.confirm(`'${item.name}' Knowledge Collection을 삭제할까요?\n연결 정보는 해제되며 Source 자체는 삭제되지 않습니다.`))return
    const result=await run(`collection-${item.id}`,()=>deleteRagCollection(item.id),'Knowledge Collection을 삭제했습니다.')
    if(result){setCollections((prev)=>prev.filter((value)=>value.id!==item.id));setSourceDraft((prev)=>({...prev,collection_ids:prev.collection_ids.filter((id)=>id!==item.id)}))}
  }

  const chooseSourcePath=async(kind:'FILE'|'FOLDER')=>{
    if(!projectReady){setError('파일/폴더를 선택하기 전에 Agent 프로젝트 경로를 먼저 설정하세요.');return}
    if(sourcePickerBusy)return
    setSourcePickerBusy(true);setError('');setNotice('')
    try{
      const initial=sourceDraft.source_uri.trim()||projectRoot
      const result=kind==='FILE'?await pickRagSourceFile(initial):await pickRagSourceFolder(initial)
      if(result?.cancelled){setNotice(`${kind==='FILE'?'파일':'폴더'} 선택을 취소했습니다.`);return}
      if(!result?.ok||!result?.path){setError(result?.message||`${kind==='FILE'?'파일':'폴더'} 선택에 실패했습니다.`);return}
      const picked=String(result.path)
      setSourceDraft((prev)=>({...prev,source_type:kind,source_uri:picked,display_name:prev.display_name||pathLeaf(picked)}))
      setNotice(`${kind==='FILE'?'파일':'폴더'} 경로를 선택했습니다.`)
    }catch(exc){setError(asLegacyError(exc).message||String(exc))}
    finally{setSourcePickerBusy(false)}
  }

  const addSource=async()=>{
    if(!projectReady){setError('File / Folder / Source Code 등록 전에 Agent 프로젝트 경로를 먼저 설정하세요.');return}
    if(sourceDraft.source_type==='SOURCE_CODE'){
      if(!sourceDraft.source_text.trim()){setError('붙여넣을 Source Code를 입력하세요.');return}
    }else if(!sourceDraft.source_uri.trim()){setError('파일/폴더 경로를 입력하거나 찾기 버튼으로 선택하세요.');return}
    const created=await run('source-create',()=>createRagSource({project_root:projectRoot,source_type:sourceDraft.source_type,source_uri:sourceDraft.source_uri.trim(),source_text:sourceDraft.source_type==='SOURCE_CODE'?sourceDraft.source_text:'',display_name:sourceDraft.display_name.trim(),collection_ids:sourceDraft.collection_ids}),'Source를 등록했습니다. 다음 단계에서 Analyse를 실행하세요.')
    if(created){setSources((prev)=>[created,...prev]);setSourceDraft((prev)=>({...prev,source_uri:'',source_text:'',display_name:''}));setExpandedSourceId(created.id)}
  }
  const sourceAction=async(item:RagSource,action:'ANALYZE'|'REVIEW'|'APPROVE')=>{
    const fn=action==='ANALYZE'?analyzeRagSource:action==='REVIEW'?reviewRagSource:approveRagSource
    const message=action==='ANALYZE'?'Source 분석이 완료되었습니다. 결과를 검토하세요.':action==='REVIEW'?'검토 완료 상태로 변경했습니다.':'RAG 등록 승인 상태로 변경했습니다.'
    const updated=await run(`source-${item.id}`,()=>fn(item.id),message)
    if(updated){setSources((prev)=>replaceSource(prev,updated));setExpandedSourceId(updated.id);if(action==='ANALYZE')setPreview(null)}
  }
  const removeSource=async(item:RagSource)=>{
    if(!window.confirm(`'${item.display_name||item.source_uri}' Source를 RAG Studio에서 제거할까요?`))return
    const result=await run(`source-${item.id}`,()=>deleteRagSource(item.id),'Source를 제거했습니다.')
    if(result){setSources((prev)=>prev.filter((value)=>value.id!==item.id));if(previewSourceId===item.id){setPreview(null);setPreviewSourceId(null)}}
  }
  const testDatabase=async()=>{
    const result=await run('db-test',()=>testRagDatabase(setting.connection_mode==='CUSTOM'?dbUrl.trim():''))
    if(result){setDbResult(result);setNotice(result.ok?'PostgreSQL + pgvector 연결을 확인했습니다.':'연결 테스트 결과를 확인하세요.')}
  }
  const openChunkPreview=async(item:RagSource)=>{
    const result=await run(`preview-${item.id}`,()=>previewRagChunks(item.id,16),'Chunk Preview를 생성했습니다.')
    if(result){setPreview(result);setPreviewSourceId(item.id);setExpandedSourceId(item.id)}
  }
  const startIndexing=async(item:RagSource)=>{
    const job=await run(`index-${item.id}`,()=>startRagIndex(item.id),'Index Job을 시작했습니다. Chunk → Embedding → HNSW 상태를 아래에서 확인하세요.')
    if(job)setJobs((prev)=>sortJobs([job,...prev.filter((value)=>value.id!==job.id)]))
  }
  const updateMetadataFilter=(patch:Partial<RagRetrievalMetadataFilter>)=>setRetrieval((prev)=>({...prev,metadata_filter:{...prev.metadata_filter,...patch}}))
  const setSearchEngine=(engine:'VECTOR'|'KEYWORD',checked:boolean)=>{
    const vectorEnabled=engine==='VECTOR'?checked:retrieval.search_mode!=='KEYWORD'
    const keywordEnabled=engine==='KEYWORD'?checked:retrieval.search_mode!=='VECTOR'
    if(!vectorEnabled&&!keywordEnabled){setError('Vector Search 또는 Keyword Search 중 최소 하나는 선택해야 합니다.');return}
    const search_mode:RagSearchMode=vectorEnabled&&keywordEnabled?'HYBRID':vectorEnabled?'VECTOR':'KEYWORD'
    setError('');setRetrieval((prev)=>({...prev,search_mode}))
  }
  const toggleFilterValue=(key:'collection_ids'|'source_ids',value:number,checked:boolean)=>{
    const current=retrieval.metadata_filter[key]||[]
    updateMetadataFilter({[key]:checked?[...current.filter((item)=>item!==value),value]:current.filter((item)=>item!==value)} as Partial<RagRetrievalMetadataFilter>)
  }
  const toggleTextFilterValue=(key:'document_types'|'languages',value:string,checked:boolean)=>{
    const current=retrieval.metadata_filter[key]||[]
    updateMetadataFilter({[key]:checked?[...current.filter((item)=>item!==value),value]:current.filter((item)=>item!==value)} as Partial<RagRetrievalMetadataFilter>)
  }
  const saveRetrieval=async()=>{
    const saved=await run('retrieval-save',()=>Promise.all([saveRagRetrievalSetting(projectRoot,retrieval),saveRagIntelligenceSetting(projectRoot,intelligence)]),'Retrieval / Intelligence 설정을 저장했습니다.')
    if(saved){
      const [retrievalSaved,intelligenceSaved]=saved
      setRetrieval({search_mode:retrievalSaved.search_mode as RagSearchMode,top_k:retrievalSaved.top_k,similarity_threshold:retrievalSaved.similarity_threshold,metadata_filter:{...DEFAULT_METADATA_FILTER,...retrievalSaved.metadata_filter}})
      setIntelligence({router_enabled:Boolean(intelligenceSaved.router_enabled),reranking_enabled:Boolean(intelligenceSaved.reranking_enabled),rerank_top_n:Number(intelligenceSaved.rerank_top_n||12)})
    }
  }
  const refreshSearchLogs=async()=>{
    const items=await run('search-logs',()=>loadRagSearchLogs(projectRoot,30))
    if(items)setSearchLogs(items)
  }
  const executeRetrievalTest=async(nextRetrieval= retrieval,nextIntelligence=intelligence)=>{
    if(!retrievalQuery.trim()){setError('Retrieval Test 질문을 입력하세요.');return}
    const result=await run('retrieval-test',()=>retrieveRag({project_root:projectRoot,query:retrievalQuery.trim(),search_mode:nextRetrieval.search_mode,top_k:nextRetrieval.top_k,similarity_threshold:nextRetrieval.similarity_threshold,metadata_filter:nextRetrieval.metadata_filter,router_enabled:nextIntelligence.router_enabled,reranking_enabled:nextIntelligence.reranking_enabled,rerank_top_n:nextIntelligence.rerank_top_n,security_context:securityContext}))
    if(result){
      setRetrievalResult(result)
      setNotice(`Retrieved Chunk ${result.result_count}개 · ${result.duration_ms}ms${result.router?.enabled?` · Router ${result.router.selected_mode}`:''}${result.reranking?.enabled?' · Reranking ON':''}`)
      const logs=await loadRagSearchLogs(projectRoot,30).catch(()=>[])
      if(logs.length)setSearchLogs(logs)
      const nextEvaluation=await evaluateRagSettings(projectRoot).catch(()=>null)
      if(nextEvaluation)setEvaluation(nextEvaluation)
    }
  }
  const runRetrievalTest=async()=>executeRetrievalTest()
  const runSettingEvaluation=async()=>{
    if(!projectReady){setError('설정 평가 전에 Agent 프로젝트 경로를 설정하세요.');return}
    const result=await run('rag-evaluation',()=>evaluateRagSettings(projectRoot),'현재 RAG 설정 평가를 완료했습니다.')
    if(result)setEvaluation(result)
  }
  const runAiRecommendation=async()=>{
    if(!projectReady){setError('AI 추천 전에 Agent 프로젝트 경로를 설정하세요.');return}
    const result=await run('rag-recommendation',()=>createRagAiRecommendation(projectRoot),'AI RAG 구성 추천을 생성했습니다. 변경 전/후를 확인한 뒤 적용할 항목을 선택하세요.')
    if(result){
      setRecommendation(result)
      setEvaluation(result.evaluation)
      setRecommendationKeys(result.diff.filter((item)=>item.changed).map((item)=>item.key))
    }
  }
  const toggleRecommendationKey=(key:string,checked:boolean)=>setRecommendationKeys((prev)=>checked?[...prev.filter((item)=>item!==key),key]:prev.filter((item)=>item!==key))
  const applyRecommendation=async(applyAll:boolean)=>{
    if(!recommendation)return
    const keys=applyAll?recommendation.diff.filter((item)=>item.changed).map((item)=>item.key):recommendationKeys
    if(!keys.length){setError('적용할 AI 추천 항목을 선택하세요.');return}
    const result=await run('rag-recommendation-apply',()=>applyRagAiRecommendation(recommendation.id,keys,applyAll),'AI 추천 설정을 적용했습니다.')
    if(!result)return
    const nextRetrieval={search_mode:result.retrieval_setting.search_mode as RagSearchMode,top_k:result.retrieval_setting.top_k,similarity_threshold:result.retrieval_setting.similarity_threshold,metadata_filter:{...DEFAULT_METADATA_FILTER,...result.retrieval_setting.metadata_filter}}
    const nextIntelligence={router_enabled:Boolean(result.intelligence_setting.router_enabled),reranking_enabled:Boolean(result.intelligence_setting.reranking_enabled),rerank_top_n:Number(result.intelligence_setting.rerank_top_n||12)}
    setRetrieval(nextRetrieval)
    setIntelligence(nextIntelligence)
    setRecommendation(result.recommendation)
    const refreshedTools=await loadRagAgentTools(projectRoot).catch(()=>[])
    if(refreshedTools.length){
      setAgentTools(refreshedTools)
      refreshedTools.filter((tool)=>tool.prompt_tool_registered).forEach((tool)=>onSyncPromptTool?.(tool))
    }
    setTab('TEST')
    if(retrievalQuery.trim())await executeRetrievalTest(nextRetrieval,nextIntelligence)
    else setNotice('AI 추천을 적용했습니다. Retrieval Test 질문을 입력하고 검색하면 적용 결과를 바로 확인할 수 있습니다.')
  }

  const generateAgentTool=async()=>{
    if(!projectReady){setError('RAG Tool 생성 전에 Agent 프로젝트 경로를 설정하세요.');return}
    if(!toolCollectionId){setError('RAG Tool이 사용할 Knowledge Collection을 선택하세요.');return}
    const created=await run('tool-generate',()=>generateRagAgentTool({project_root:projectRoot,agent_design_project_id:agentDesignProjectId||null,collection_id:toolCollectionId,search_mode:retrieval.search_mode,top_k:retrieval.top_k,similarity_threshold:retrieval.similarity_threshold,metadata_filter:retrieval.metadata_filter,prompt_context_enabled:false}),'RAG Tool을 생성했습니다. Prompt & Tool Studio에 자동 등록합니다.')
    if(!created)return
    onSyncPromptTool?.(created)
    const registered=await markRagPromptToolRegistered(created.id,true).catch(()=>created)
    setAgentTools((prev)=>[...prev.filter((item)=>item.id!==registered.id),registered].sort((a,b)=>a.id-b.id))
    setSelectedAgentToolId(registered.id)
  }
  const togglePromptContext=async(tool:RagAgentTool,enabled:boolean)=>{
    const updated=await run(`tool-context-${tool.id}`,()=>updateRagPromptContext(tool.id,enabled),enabled?'Prompt Context 연결을 활성화했습니다.':'Prompt Context 자동 연결을 해제했습니다.')
    if(updated){setAgentTools((prev)=>prev.map((item)=>item.id===updated.id?updated:item));onSyncPromptTool?.(updated)}
  }
  const connectWorkflow=async(tool:RagAgentTool)=>{
    const binding=await run(`workflow-bind-${tool.id}`,()=>bindRagWorkflow(tool.id,agentDesignProjectId||null),'RAG Tool을 Agent Workflow Node에 연결했습니다.')
    if(binding){setAgentTools((prev)=>prev.map((item)=>item.id===binding.tool.id?binding.tool:item));onBindWorkflow?.(binding)}
  }
  const runRagToolTest=async()=>{
    if(!selectedAgentTool){setError('RAG Tool을 먼저 생성하세요.');return}
    if(!retrievalQuery.trim()){setError('RAG Tool Test 질문을 입력하세요.');return}
    const result=await run(`tool-test-${selectedAgentTool.id}`,()=>testRagAgentTool(selectedAgentTool.id,{query:retrievalQuery.trim(),security_context:securityContext}),`RAG Tool ${selectedAgentTool.tool_name} 실행을 완료했습니다.`)
    if(result){setToolTestResult(result);const logs=await loadRagAgentTestLogs(projectRoot,30).catch(()=>[]);if(logs.length)setAgentTestLogs(logs)}
  }
  const openAgentTest=async()=>{
    if(!selectedAgentTool){setError('RAG Tool을 먼저 생성하세요.');return}
    if(!retrievalQuery.trim()){setError('Agent Test 질문을 입력하세요.');return}
    const prepared=await run(`agent-test-${selectedAgentTool.id}`,()=>prepareRagAgentTest(selectedAgentTool.id,retrievalQuery.trim()),'Prompt & Tool Studio Agent Test에 RAG Tool을 연결했습니다.')
    if(prepared){onSyncPromptTool?.(prepared.tool);onOpenAgentTest?.(prepared);const logs=await loadRagAgentTestLogs(projectRoot,30).catch(()=>[]);if(logs.length)setAgentTestLogs(logs)}
  }

  return <div className="rag-studio-root">
    <header className="rag-studio-head">
      <div><strong>RAG Studio</strong><small>Knowledge → Retrieval → RAG Tool → Prompt & Tool Studio → Workflow → Agent Test를 하나의 설계 흐름으로 연결합니다.</small></div>
      <div className="rag-head-actions">
        <label className="rag-switch"><input type="checkbox" checked={setting.rag_enabled} onChange={(event)=>persistSetting({rag_enabled:event.target.checked})}/><span>RAG 사용</span></label>
        <span className="rag-phase-badge">운영형 RAG · Security / Evaluation</span>
      </div>
    </header>

    <nav className="rag-main-tabs" role="tablist" aria-label="RAG Studio 작업 영역">
      <button type="button" className={tab==='KNOWLEDGE'?'active':''} onClick={()=>changeTab('KNOWLEDGE')}>Knowledge</button>
      <button type="button" className={tab==='RETRIEVAL'?'active':''} onClick={()=>changeTab('RETRIEVAL')}>Retrieval</button>
      <button type="button" className={tab==='TEST'?'active':''} onClick={()=>changeTab('TEST')}>Test</button>
      <button type="button" className={tab==='OPERATION'?'active':''} onClick={()=>changeTab('OPERATION')}>Operation</button>
    </nav>

    {(error||notice)&&<div className={`rag-message ${error?'error':'ok'}`}>{error||notice}</div>}

    {tab==='KNOWLEDGE'&&<div className="rag-knowledge-layout">
      <aside className="rag-collection-panel">
        <div className="rag-panel-title"><div><strong>Knowledge Collections</strong><small>Agent가 Knowledge를 목적별로 묶는 논리 그룹</small></div><OptionHelp title="Knowledge Collection" summary="여러 Source를 목적별 Knowledge 묶음으로 관리합니다." detail="예: 개발문서, Source Code, DB Schema, 운영 장애. Agent나 Router는 필요한 Collection만 선택해 검색할 수 있습니다." recommendedFor={["Agent별 Knowledge 분리","검색 범위 축소"]}/></div>
        <div className="rag-collection-list">
          {collections.map((item)=><article key={item.id} className={item.is_active?'':'disabled'}>
            {editingCollectionId===item.id?<div className="rag-collection-edit"><input value={editCollection.name} onChange={(event)=>setEditCollection((prev)=>({...prev,name:event.target.value}))}/><textarea value={editCollection.description} onChange={(event)=>setEditCollection((prev)=>({...prev,description:event.target.value}))}/><div className="rag-inline-fields"><select value={editCollection.scope} onChange={(event)=>setEditCollection((prev)=>({...prev,scope:event.target.value}))}><option value="AGENT">Agent 전용</option><option value="PROJECT">프로젝트 공용</option><option value="GLOBAL">전체 공용</option></select><select value={editCollection.security_level} onChange={(event)=>setEditCollection((prev)=>({...prev,security_level:event.target.value}))}><option value="INTERNAL">Internal</option><option value="PUBLIC">Public</option><option value="CONFIDENTIAL">Confidential</option></select></div><div className="rag-mini-actions"><button type="button" onClick={saveCollectionEdit}>저장</button><button type="button" onClick={()=>setEditingCollectionId(null)}>취소</button></div></div>:<><div className="rag-collection-name"><strong>{item.name}</strong><span>ID {item.id}</span></div><p>{item.description||'설명 없음'}</p><small>{item.scope} · {item.security_level}</small><div className="rag-mini-actions"><button type="button" onClick={()=>beginEditCollection(item)}>수정</button><button type="button" className="danger" onClick={()=>removeCollection(item)}>삭제</button></div></>}
          </article>)}
          {!collections.length&&<div className="rag-empty">아직 Knowledge Collection이 없습니다.</div>}
        </div>
        <div className="rag-add-collection"><strong>+ Knowledge Collection</strong><input placeholder="예: 개발문서" value={collectionDraft.name} onChange={(event)=>setCollectionDraft((prev)=>({...prev,name:event.target.value}))}/><textarea placeholder="이 Collection의 용도" value={collectionDraft.description} onChange={(event)=>setCollectionDraft((prev)=>({...prev,description:event.target.value}))}/><div className="rag-inline-fields"><select value={collectionDraft.scope} onChange={(event)=>setCollectionDraft((prev)=>({...prev,scope:event.target.value as RagScope}))}><option value="AGENT">Agent 전용</option><option value="PROJECT">프로젝트 공용</option><option value="GLOBAL">전체 공용</option></select><select value={collectionDraft.security_level} onChange={(event)=>setCollectionDraft((prev)=>({...prev,security_level:event.target.value}))}><option value="INTERNAL">Internal</option><option value="PUBLIC">Public</option><option value="CONFIDENTIAL">Confidential</option></select></div><button type="button" className="rag-primary" onClick={addCollection} disabled={Boolean(busy)}>Collection 생성</button></div>
      </aside>

      <main className="rag-knowledge-main">
        <section className="rag-section rag-db-section">
          <div className="rag-section-head"><div><strong>DB / Vector Store</strong><small>PostgreSQL + pgvector · 실제 Embedding과 HNSW Index를 저장합니다.</small></div><OptionHelp title="PostgreSQL + pgvector" summary="문서 Metadata와 Vector를 한 DB에서 관리하는 AgentStudio 기본 RAG 저장소입니다." detail="Index Job 완료 시 rag_chunks / rag_embeddings에 데이터가 저장되고 cosine HNSW Index 존재 여부까지 검증합니다."/></div>
          <div className="rag-account-db-profile">
            <div><strong>프로젝트 DB 설정</strong><small>{projectDbProfileId?'계정 DB 설정이 이 프로젝트의 RAG 설계에 연결되어 있습니다.':'프로젝트에 저장된 RAG DB 설정이 없습니다. 계정에 저장된 DB 설정 목록에서 선택할 수 있습니다.'}</small></div>
            <select value={projectDbProfileId||''} disabled={!projectReady||busy==='account-db-bind'} onChange={(event)=>{const id=Number(event.target.value||0);if(id)void bindAccountDbProfile(id)}}>
              <option value="">{accountDbProfiles.length?'계정 저장 DB 설정 선택':'계정 저장 DB 설정 없음'}</option>
              {accountDbProfiles.filter((item)=>['postgresql','supabase'].includes(String(item.db_type||'').toLowerCase())).map((item)=><option key={item.account_profile_id||item.account_database_profiles_id} value={item.account_profile_id||item.account_database_profiles_id}>{item.name} · {String(item.db_type||'').toUpperCase()} · {[item.host,item.database].filter(Boolean).join(' / ')}</option>)}
            </select>
            <small>계정 DB 목록에는 비밀번호 원문을 저장하지 않습니다. 자격증명은 기존 Windows DPAPI 보관 정책을 유지합니다.</small>
          </div>
          <div className="rag-db-grid"><label>DB 유형<select value={setting.db_provider} onChange={(event)=>persistSetting({db_provider:event.target.value})}><option value="POSTGRESQL_PGVECTOR">PostgreSQL + pgvector · AI 추천</option></select></label><label>연결 방식<select value={setting.connection_mode} onChange={(event)=>persistSetting({connection_mode:event.target.value})}><option value="RUNTIME">AgentStudio Runtime DB 설정 사용</option><option value="CUSTOM">이번 연결 테스트용 URL 입력</option></select></label><label>Schema<input value={setting.db_schema} placeholder="예: theanova_agentstudio" onChange={(event)=>setSetting((prev)=>({...prev,db_schema:event.target.value}))} onBlur={()=>persistSetting({db_schema:setting.db_schema.trim()})}/></label><label>Knowledge 범위<select value={setting.scope} onChange={(event)=>persistSetting({scope:event.target.value})}><option value="AGENT">현재 Agent 전용</option><option value="PROJECT">현재 프로젝트 공용</option><option value="GLOBAL">AgentStudio 전체 공용</option></select></label></div>
          {setting.connection_mode==='CUSTOM'&&<label className="rag-db-url">Database URL <span>비밀번호는 저장하지 않고 연결 테스트 요청에만 사용합니다.</span><input type="password" autoComplete="off" placeholder="postgresql+asyncpg://user:password@host:5432/database" value={dbUrl} onChange={(event)=>setDbUrl(event.target.value)}/></label>}
          <div className="rag-db-actions"><button type="button" onClick={testDatabase} disabled={busy==='db-test'}>{busy==='db-test'?'연결 확인 중...':'연결 테스트'}</button>{dbResult&&<div className={`rag-db-result ${dbResult.ok?'pass':'fail'}`}><b>{dbResult.ok?'✓ RAG DB 준비됨':'⚠ 연결 확인 필요'}</b><span>PostgreSQL {dbResult.postgresql?.ok?'PASS':'FAIL'} · pgvector {dbResult.pgvector?.ok?'PASS':'FAIL'}</span>{dbResult.postgresql?.message&&<small>{String(dbResult.postgresql.message)}</small>}{dbResult.pgvector?.message&&<small>{String(dbResult.pgvector.message)}</small>}</div>}</div>
        </section>

        <section className="rag-section rag-index-config-section">
          <div className="rag-section-head"><div><strong>Indexing 기본 설정</strong><small>자동 문서 판별 → Duplicate/Safety Scan → 자동 Chunking → Embedding → pgvector HNSW</small></div><OptionHelp title="Indexing Pipeline" summary="승인된 Source를 실제 검색 가능한 Vector Index로 변환합니다." detail="Embedding 모델은 현재 AgentStudio Embedding Provider 설정을 사용합니다. 기본 저장 규격은 1536차원이며 768차원 로컬 모델은 zero-padding해 cosine geometry를 유지합니다."/></div>
          <div className="rag-index-config-grid">
            <div><span>Embedding</span><strong>{indexConfig?`${indexConfig.embedding_provider} · ${indexConfig.embedding_model}`:'불러오는 중...'}</strong></div>
            <div><span>Vector 저장</span><strong>{indexConfig?`${indexConfig.storage_dimension} dim`:'-'}</strong></div>
            <div><span>자동 Chunk</span><strong>{indexConfig?`${indexConfig.chunk_chars} chars / overlap ${indexConfig.chunk_overlap_chars}`:'-'}</strong></div>
            <div><span>Index</span><strong>{indexConfig?`HNSW · ${indexConfig.hnsw_metric}`:'-'}</strong></div>
          </div>
        </section>

        <section className="rag-section">
          <div className="rag-section-head"><div><strong>Source 등록</strong><small>Upload → Analyse → Review → Approve → Chunk Preview → Index 순서로 처리합니다.</small></div><OptionHelp title="Source 등록" summary="원본을 등록해도 바로 Vector DB에 넣지 않고 먼저 분석·검토합니다." detail="승인 뒤 실제 문서 유형 판별, 중복 검사, Safety Scan, Chunk/Embedding/Index까지 실행합니다."/></div>
          {!projectReady&&<div className="rag-warning">현재 Agent 프로젝트 경로가 없습니다. 프로젝트 경로를 설정한 뒤 Source를 등록하세요.</div>}
          <div className="rag-source-form"><div className="rag-source-types" role="group" aria-label="RAG Source 유형">{(['FILE','FOLDER','SOURCE_CODE'] as RagSourceType[]).map((type)=><button type="button" key={type} className={sourceDraft.source_type===type?'active':''} onClick={()=>setSourceDraft((prev)=>({...prev,source_type:type,source_uri:type==='SOURCE_CODE'?'':prev.source_uri}))}>{SOURCE_TYPE_LABEL[type]}</button>)}</div>{sourceDraft.source_type!=='SOURCE_CODE'?<label>Source 경로<div className="rag-path-picker-row"><input value={sourceDraft.source_uri} disabled={!projectReady||sourcePickerBusy} placeholder={sourceDraft.source_type==='FOLDER'?'폴더 경로를 입력하거나 폴더 찾기로 선택':'파일 경로를 입력하거나 파일 찾기로 선택'} onChange={(event)=>setSourceDraft((prev)=>({...prev,source_uri:event.target.value}))}/><button type="button" disabled={!projectReady||sourcePickerBusy} onClick={()=>chooseSourcePath(sourceDraft.source_type as 'FILE'|'FOLDER')}>{sourcePickerBusy?'선택 중...':sourceDraft.source_type==='FOLDER'?'폴더 찾기':'파일 찾기'}</button></div><small>프로젝트 루트: {projectRoot||'미설정'}</small></label>:<label>Source Code<div className="rag-source-code-box"><textarea value={sourceDraft.source_text} disabled={!projectReady} spellCheck={false} placeholder="RAG Knowledge로 등록할 소스코드를 여기에 붙여넣으세요.\n예: Python / TypeScript / SQL / Java / C# 등" onChange={(event)=>setSourceDraft((prev)=>({...prev,source_text:event.target.value}))}/><small>{sourceDraft.source_text.length.toLocaleString()}자 · 등록 시 프로젝트 내부 RAG 보관 파일로 저장한 뒤 Safety Scan / Chunking / Embedding을 수행합니다.</small></div></label>}<label>표시 이름 <span>{sourceDraft.source_type==='SOURCE_CODE'?'파일명 권장':'선택'}</span><input value={sourceDraft.display_name} disabled={!projectReady} placeholder={sourceDraft.source_type==='SOURCE_CODE'?'예: auth_service.py':'비우면 파일/폴더 이름을 사용합니다.'} onChange={(event)=>setSourceDraft((prev)=>({...prev,display_name:event.target.value}))}/></label><fieldset><legend>연결할 Knowledge Collection</legend>{collections.length?collections.map((item)=><label key={item.id}><input type="checkbox" checked={sourceDraft.collection_ids.includes(item.id)} onChange={(event)=>setSourceDraft((prev)=>({...prev,collection_ids:event.target.checked?[...prev.collection_ids,item.id]:prev.collection_ids.filter((id)=>id!==item.id)}))}/><span>{item.name}</span></label>):<small>Collection 없이도 Source를 먼저 등록할 수 있습니다.</small>}</fieldset><button type="button" className="rag-primary" disabled={!projectReady||Boolean(busy)} onClick={addSource}>Source 등록</button></div>
        </section>

        <section className="rag-section rag-sources-section">
          <div className="rag-section-head"><div><strong>등록 Source</strong><small>{sources.length}개 · 승인/Indexed {approvedCount}개</small></div><div className="rag-flow-legend"><span>1 등록</span><i>→</i><span>2 Analyse</span><i>→</i><span>3 Review</span><i>→</i><span>4 Approve</span><i>→</i><span>5 Index</span></div></div>
          <div className="rag-source-list">{sources.map((item)=>{
            const expanded=expandedSourceId===item.id
            const analysis=item.analysis_result||{}
            const activeJob=jobs.find((job)=>job.source_id===item.id&&['PENDING','RUNNING'].includes(job.status))
            return <article key={item.id} className={`rag-source-card status-${String(item.status||'').toLowerCase()}`}>
              <header><button type="button" className="rag-source-expand" onClick={()=>setExpandedSourceId(expanded?null:item.id)} aria-expanded={expanded}>{expanded?'▾':'▸'}</button><div><strong>{item.display_name||item.source_uri}</strong><small>{SOURCE_TYPE_LABEL[item.source_type]||item.source_type} · ID {item.id} · {item.source_uri}</small></div><span className={`rag-status status-${String(item.status||'').toLowerCase()}`}>{STATUS_LABEL[item.status]||item.status}</span><span className={`rag-suitability suitability-${String(item.suitability||'unknown').toLowerCase()}`}>{SUITABILITY_LABEL[item.suitability]||item.suitability||'분석 전'}</span></header>
              <div className="rag-source-actions"><button type="button" onClick={()=>sourceAction(item,'ANALYZE')} disabled={Boolean(busy)||Boolean(activeJob)}>Analyse</button><button type="button" onClick={()=>sourceAction(item,'REVIEW')} disabled={Boolean(busy)||!['REVIEW_REQUIRED','REVIEWED','APPROVED'].includes(item.status)}>Review 완료</button><button type="button" className="rag-primary" onClick={()=>sourceAction(item,'APPROVE')} disabled={Boolean(busy)||!['REVIEWED','APPROVED'].includes(item.status)}>Approve</button><button type="button" onClick={()=>openChunkPreview(item)} disabled={Boolean(busy)||!['APPROVED','INDEXED'].includes(item.status)}>Chunk Preview</button><button type="button" className="rag-primary" onClick={()=>startIndexing(item)} disabled={Boolean(busy)||Boolean(activeJob)||!['APPROVED','INDEXED'].includes(item.status)}>{activeJob?`Index ${activeJob.progress}%`:'Index 생성'}</button><button type="button" className="danger" onClick={()=>removeSource(item)} disabled={Boolean(busy)||Boolean(activeJob)}>제거</button></div>
              {activeJob&&<div className="rag-inline-job"><div><span>{JOB_STAGE_LABEL[activeJob.stage]||activeJob.stage}</span><strong>{activeJob.progress}%</strong></div><progress max={100} value={activeJob.progress}/></div>}
              {expanded&&<div className="rag-source-detail"><div className="rag-analysis-summary"><div><span>적합성</span><strong>{SUITABILITY_LABEL[item.suitability]||item.suitability||'분석 전'}</strong></div><div><span>Risk</span><strong>{item.risk_level||'UNKNOWN'}</strong></div><div><span>추천 Chunk</span><strong>{item.recommended_chunking||'Analyse 후 표시'}</strong></div><div><span>파일</span><strong>{analysis.file_count??'-'}개 · {analysis.size_bytes!=null?humanBytes(analysis.size_bytes):'-'}</strong></div></div><div className="rag-analysis-reason"><strong>적합성 분석</strong><p>{item.recommendation_reason||'Analyse를 실행하면 등록 적합성, 위험도, 추천 Chunk 방식이 표시됩니다.'}</p>{Array.isArray(analysis.warnings)&&analysis.warnings.length>0&&<ul>{analysis.warnings.map((warning,index)=><li key={`${item.id}-${index}`}>{warning}</li>)}</ul>}{analysis.note&&<small>{analysis.note}</small>}</div><div className="rag-source-collections"><strong>Collection</strong><span>{item.collection_ids?.length?item.collection_ids.map((id)=>collections.find((collection)=>collection.id===id)?.name||`ID ${id}`).join(', '):'미연결'}</span></div></div>}
            </article>
          })}{!sources.length&&<div className="rag-empty large">등록된 Source가 없습니다. 위에서 File / Folder / Source Code를 등록하세요.</div>}</div>
        </section>

        {preview&&<section className="rag-section rag-preview-section">
          <div className="rag-section-head"><div><strong>Chunk Preview · Source ID {preview.source_id}</strong><small>실제 DB 저장 전 문서 판별 / Duplicate / Safety Scan / 자동 Chunking 결과</small></div><button type="button" className="rag-close-preview" onClick={()=>{setPreview(null);setPreviewSourceId(null)}}>닫기</button></div>
          <div className="rag-preview-summary"><div><span>문서</span><strong>{preview.documents_total}</strong></div><div><span>예상 Chunk</span><strong>{preview.total_chunk_count}</strong></div><div><span>Duplicate</span><strong>{preview.duplicate_count}</strong></div><div><span>Safety 경고</span><strong>{preview.safety_warning_count}</strong></div></div>
          <div className="rag-preview-documents">{preview.documents.map((doc)=><div key={doc.path} className={`rag-preview-doc safety-${doc.safety_level.toLowerCase()}`}><div><strong>{doc.path}</strong><span>{doc.document_type}{doc.language?` · ${doc.language}`:''}</span></div><small>{humanBytes(doc.size_bytes)} · Chunk {doc.chunk_count} · Safety {doc.safety_level}{doc.risk_score!=null?` · Risk ${doc.risk_score}`:''}{doc.quarantined?' · Quarantined':''}{doc.is_duplicate?` · Duplicate of Document ID ${doc.duplicate_of_document_id}`:''}</small>{doc.safety_warnings.length>0&&<ul>{doc.safety_warnings.map((warning,index)=><li key={`${doc.path}-${index}`}>{warning}</li>)}</ul>}</div>)}</div>
          <div className="rag-chunk-preview-list">{preview.chunks.map((chunk)=><article key={`${chunk.document_path}-${chunk.chunk_index}`}><header><strong>Chunk {String(chunk.chunk_index+1).padStart(3,'0')}</strong><span>{chunk.document_type} · {chunk.char_count} chars · ~{chunk.token_estimate} tokens</span></header><small>{chunk.document_path}{chunk.start_line?` · L${chunk.start_line}${chunk.end_line?`-${chunk.end_line}`:''}`:''}{chunk.symbol_name?` · ${chunk.symbol_name}`:''}{chunk.heading?` · ${chunk.heading}`:''}</small><pre>{chunk.content}</pre></article>)}</div>
          {preview.document_preview_truncated&&<div className="rag-warning">Preview는 앞 {preview.documents_previewed}개 문서까지만 분석했습니다. 실제 Index Job은 전체 지원 문서를 처리합니다.</div>}
        </section>}

        <section className="rag-section rag-jobs-section">
          <div className="rag-section-head"><div><strong>Index Job 상태</strong><small>Chunk 생성 · Embedding 저장 · HNSW Index 완료 여부를 지속적으로 확인합니다.</small></div><OptionHelp title="Index Job" summary="장시간 Indexing을 화면 로컬 상태가 아닌 DB Job으로 추적합니다." detail="Job 실패 시 이미 완료된 문서는 유지되고 실패 원인을 표시합니다. Operation에서 변경 감지와 증분 Re-index를 이어서 수행할 수 있습니다."/></div>
          <div className="rag-job-list">{jobs.map((job)=>{
            const source=sources.find((item)=>item.id===job.source_id)
            return <article key={job.id} className={`rag-job-card job-${job.status.toLowerCase()}`}><div className="rag-job-main"><div><strong>Job #{job.id} · {source?.display_name||source?.source_uri||`Source ${job.source_id}`}</strong><small>{JOB_STAGE_LABEL[job.stage]||job.stage} · {JOB_STATUS_LABEL[job.status]||job.status}</small></div><span>{job.progress}%</span></div><progress max={100} value={job.progress}/><div className="rag-job-metrics"><span>문서 {job.documents_processed}/{job.documents_total||'-'}</span><span>Duplicate {job.duplicates_skipped}</span><span>Safety {job.safety_warnings}</span><span>Chunk {job.chunks_created}</span><span>Embedding {job.embeddings_created}</span><span>HNSW {job.index_ready?'PASS':'-'}</span></div>{job.embedding_model&&<small className="rag-job-model">{job.embedding_provider} · {job.embedding_model}{job.embedding_dimension?` · source ${job.embedding_dimension} dim`:''}{job.index_ready?` · ${job.index_name}`:''}</small>}{job.error_message&&<div className="rag-job-error">{job.error_message}</div>}</article>
          })}{!jobs.length&&<div className="rag-empty large">아직 Index Job이 없습니다. 승인된 Source에서 Chunk Preview를 확인한 뒤 Index 생성을 실행하세요.</div>}</div>
        </section>
      </main>
    </div>}

    {tab==='RETRIEVAL'&&<div className="rag-retrieval-layout">
      <section className="rag-section rag-retrieval-config">
        <div className="rag-section-head"><div><strong>Retrieval 설정</strong><small>Vector / Keyword / Hybrid 검색 방식과 후보 범위를 설정합니다.</small></div><OptionHelp title="Retrieval" summary="Indexed Chunk에서 질문과 관련된 정보를 찾는 단계입니다." detail="Vector는 의미 유사도, Keyword는 정확한 문자열, Hybrid는 두 결과를 RRF로 결합합니다. Similarity Threshold는 Vector 후보에만 적용합니다."/></div>
        <div className="rag-retrieval-mode">
          <label className={retrieval.search_mode!=='KEYWORD'?'active':''}><input type="checkbox" checked={retrieval.search_mode!=='KEYWORD'} onChange={(event)=>setSearchEngine('VECTOR',event.target.checked)}/><span>Vector Search</span><small>의미 유사도 · pgvector cosine HNSW</small></label>
          <label className={retrieval.search_mode!=='VECTOR'?'active':''}><input type="checkbox" checked={retrieval.search_mode!=='VECTOR'} onChange={(event)=>setSearchEngine('KEYWORD',event.target.checked)}/><span>Keyword Search</span><small>정확 문자열 · Content / Path / Symbol</small></label>
          <div className={`rag-hybrid-mode ${retrieval.search_mode==='HYBRID'?'active':''}`}><span>Hybrid Search</span><small>{retrieval.search_mode==='HYBRID'?'Vector + Keyword 후보를 RRF로 자동 결합합니다.':'Vector와 Keyword를 모두 체크하면 자동 활성화됩니다.'}</small><b>{retrieval.search_mode==='HYBRID'?'ON · RRF':'OFF'}</b></div>
        </div>
        <div className="rag-retrieval-numbers"><label><span>Top K</span><input type="number" min={1} max={50} value={retrieval.top_k} onChange={(event)=>setRetrieval((prev)=>({...prev,top_k:Math.max(1,Math.min(50,Number(event.target.value)||1))}))}/><small>최종 Retrieved Chunk 수</small></label><label><span>Similarity Threshold</span><input type="number" min={0} max={1} step={0.05} value={retrieval.similarity_threshold} disabled={retrieval.search_mode==='KEYWORD'} onChange={(event)=>setRetrieval((prev)=>({...prev,similarity_threshold:Math.max(0,Math.min(1,Number(event.target.value)||0))}))}/><small>Vector similarity 최소값 · 0~1</small></label></div>
        <div className="rag-intelligence-settings">
          <div className="rag-subhead"><strong>Intelligence</strong><OptionHelp title="Retrieval Router / Reranking" summary="질문 성격에 따라 검색 방식을 자동 선택하고 검색 후보를 다시 정렬합니다." detail="Router는 오류코드·함수명·설명형 질문 신호를 분석해 Keyword/Vector/Hybrid를 선택합니다. Reranking은 1차 후보의 질문 단어·Heading·Symbol·Path 관련도를 다시 계산해 최종 Top K를 정렬합니다."/></div>
          <div className="rag-intelligence-grid">
            <label className={intelligence.router_enabled?'active':''}><input type="checkbox" checked={intelligence.router_enabled} onChange={(event)=>setIntelligence((prev)=>({...prev,router_enabled:event.target.checked}))}/><span>Retrieval Router</span><small>질문별 검색 방식 자동 선택</small></label>
            <label className={intelligence.reranking_enabled?'active':''}><input type="checkbox" checked={intelligence.reranking_enabled} onChange={(event)=>setIntelligence((prev)=>({...prev,reranking_enabled:event.target.checked}))}/><span>Reranking</span><small>1차 후보를 최종 Context 기준으로 재정렬</small></label>
            <label><span>Rerank 후보 수</span><input type="number" min={retrieval.top_k} max={50} value={intelligence.rerank_top_n} disabled={!intelligence.reranking_enabled} onChange={(event)=>setIntelligence((prev)=>({...prev,rerank_top_n:Math.max(retrieval.top_k,Math.min(50,Number(event.target.value)||retrieval.top_k))}))}/><small>최종 Top K 전에 다시 평가할 후보 수</small></label>
          </div>
        </div>
        <div className="rag-metadata-filter"><div className="rag-subhead"><strong>Metadata Filter · 기본형</strong><OptionHelp title="Metadata Filter" summary="검색 전에 Source/문서 Metadata로 후보 범위를 줄입니다." detail="Collection, Source, 문서 유형, 언어, 경로를 지원하며 Role/Access Rule과 문서 보안등급도 Retrieval 전에 Backend에서 강제합니다."/></div>
          <div className="rag-filter-group"><strong>Collection</strong><div>{collections.map((item)=><label key={item.id}><input type="checkbox" checked={retrieval.metadata_filter.collection_ids.includes(item.id)} onChange={(event)=>toggleFilterValue('collection_ids',item.id,event.target.checked)}/><span>{item.name}</span></label>)}{!collections.length&&<small>Collection 없음</small>}</div></div>
          <div className="rag-filter-group"><strong>Indexed Source</strong><div>{(retrievalOptions?.sources||[]).map((item)=><label key={item.id}><input type="checkbox" checked={retrieval.metadata_filter.source_ids.includes(item.id)} onChange={(event)=>toggleFilterValue('source_ids',item.id,event.target.checked)}/><span>{item.display_name||item.source_uri}</span></label>)}{!(retrievalOptions?.sources||[]).length&&<small>Indexed Source 없음</small>}</div></div>
          <div className="rag-filter-group"><strong>문서 유형</strong><div>{(retrievalOptions?.document_types||[]).map((value)=><label key={value}><input type="checkbox" checked={retrieval.metadata_filter.document_types.includes(value)} onChange={(event)=>toggleTextFilterValue('document_types',value,event.target.checked)}/><span>{value}</span></label>)}{!(retrievalOptions?.document_types||[]).length&&<small>Index 후 자동 표시</small>}</div></div>
          <div className="rag-filter-group"><strong>언어</strong><div>{(retrievalOptions?.languages||[]).map((value)=><label key={value}><input type="checkbox" checked={retrieval.metadata_filter.languages.includes(value)} onChange={(event)=>toggleTextFilterValue('languages',value,event.target.checked)}/><span>{value}</span></label>)}{!(retrievalOptions?.languages||[]).length&&<small>Metadata 없음</small>}</div></div>
          <label className="rag-path-filter"><span>Path 포함</span><input value={retrieval.metadata_filter.path_contains} placeholder="예: backend/auth" onChange={(event)=>updateMetadataFilter({path_contains:event.target.value})}/></label>
        </div>
        <div className="rag-retrieval-actions"><button type="button" className="rag-primary" onClick={saveRetrieval} disabled={Boolean(busy)}>Retrieval 설정 저장</button><button type="button" onClick={()=>changeTab('TEST')}>Retrieval Test 열기</button></div>
        <div className="rag-ai-intelligence-panel">
          <div className="rag-section-head"><div><strong>✨ AI RAG 추천 / 설정 평가</strong><small>현재 Index 상태와 Retrieval Test 로그를 분석해 변경 이유와 Diff를 보여줍니다.</small></div><div className="rag-ai-actions"><button type="button" onClick={runSettingEvaluation} disabled={Boolean(busy)}>현재 설정 평가</button><button type="button" className="rag-primary" onClick={runAiRecommendation} disabled={Boolean(busy)}>{busy==='rag-recommendation'?'AI 분석 중...':'✨ AI 추천'}</button></div></div>
          {evaluation&&<div className="rag-evaluation-grid"><div><span>종합 추정</span><strong>{evaluation.overall_score}</strong></div><div><span>검색 준비</span><strong>{evaluation.retrieval_readiness}</strong></div><div><span>검색 범위</span><strong>{evaluation.search_coverage}</strong></div><div><span>테스트 안정성</span><strong>{evaluation.test_stability}</strong></div><div><span>효율</span><strong>{evaluation.efficiency}</strong></div></div>}
          {evaluation&&<small className="rag-evaluation-basis">{evaluation.basis}</small>}
          {evaluation&&evaluation.improvements.length>0&&<div className="rag-improvement-list">{evaluation.improvements.map((item,index)=><div key={`${item.level}-${index}`}>• {item.text}</div>)}</div>}
          {recommendation&&<div className="rag-recommendation-card"><header><div><strong>추천 #{recommendation.id} · {recommendation.provider}</strong><small>{recommendation.summary}</small></div><span>{recommendation.diff.filter((item)=>item.changed).length}개 변경</span></header>{recommendation.test_insights.map((text,index)=><p key={`insight-${index}`}>▸ {text}</p>)}{recommendation.warnings.map((text,index)=><p key={`warn-${index}`} className="warning">⚠ {text}</p>)}<div className="rag-recommendation-diff">{recommendation.diff.map((item)=><label key={item.key} className={item.changed?'changed':'same'}><input type="checkbox" disabled={!item.changed} checked={item.changed&&recommendationKeys.includes(item.key)} onChange={(event)=>toggleRecommendationKey(item.key,event.target.checked)}/><span>{item.label}</span><code>{String(item.current)}</code><i>→</i><code>{String(item.recommended)}</code><small>{item.reason}</small></label>)}</div><div className="rag-recommendation-actions"><button type="button" onClick={()=>setRecommendation(null)}>취소</button><button type="button" onClick={()=>applyRecommendation(false)} disabled={!recommendationKeys.length||Boolean(busy)}>선택 적용</button><button type="button" className="rag-primary" onClick={()=>applyRecommendation(true)} disabled={Boolean(busy)}>전체 적용</button></div><small className="rag-apply-note">적용 후 현재 Retrieval Test 질문이 있으면 자동으로 Test 탭에서 재실행합니다.</small></div>}
        </div>
        <div className="rag-agent-link-section">
          <div className="rag-section-head"><div><strong>Agent 연결</strong><small>Knowledge Collection을 RAG Tool로 만들고 Prompt & Tool Studio / Workflow에 연결합니다.</small></div><OptionHelp title="RAG Agent 연결" summary="검색 설정을 실제 Agent가 호출할 수 있는 Tool 계약으로 고정합니다." detail="Tool 생성 시 Prompt & Tool Studio Registry에 자동 등록합니다. Prompt Context는 Tool Result를 LLM Context에 연결하는 정책이며 Workflow 연결은 target_agent_workflow에 Tool step을 추가합니다."/></div>
          <div className="rag-tool-generator"><label><span>Knowledge Collection</span><select value={toolCollectionId??''} onChange={(event)=>setToolCollectionId(Number(event.target.value)||null)}><option value="">선택</option>{collections.map((item)=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><div><span>현재 Retrieval</span><strong>{SEARCH_MODE_LABEL[retrieval.search_mode]||retrieval.search_mode} · Top K {retrieval.top_k}</strong></div><button type="button" className="rag-primary" onClick={generateAgentTool} disabled={Boolean(busy)||!toolCollectionId}>+ RAG Tool 생성</button></div>
          <div className="rag-agent-tool-list">{agentTools.map((tool)=><article key={tool.id} className={selectedAgentTool?.id===tool.id?'selected':''} onClick={()=>setSelectedAgentToolId(tool.id)}><header><div><strong>{tool.tool_name}</strong><small>{tool.collection_name||'프로젝트 Knowledge'} · {SEARCH_MODE_LABEL[tool.search_mode]||tool.search_mode} · Top K {tool.top_k}</small></div><span className="rag-status status-indexed">{tool.status}</span></header><div className="rag-tool-link-status"><span className={tool.prompt_tool_registered?'pass':''}>Prompt & Tool {tool.prompt_tool_registered?'✓':'-'}</span><span className={tool.workflow_bound?'pass':''}>Workflow {tool.workflow_bound?'✓':'-'}</span><span className={tool.prompt_context_enabled?'pass':''}>Prompt Context {tool.prompt_context_enabled?'ON':'OFF'}</span></div><div className="rag-tool-link-actions"><label><input type="checkbox" checked={tool.prompt_context_enabled} onChange={(event)=>{event.stopPropagation();togglePromptContext(tool,event.target.checked)}}/><span>Prompt Context 연결</span></label><button type="button" onClick={(event)=>{event.stopPropagation();onOpenPromptToolStudio?.(tool)}}>Prompt & Tool Studio 열기</button><button type="button" className="rag-primary" onClick={(event)=>{event.stopPropagation();connectWorkflow(tool)}}>{tool.workflow_bound?'Workflow 다시 연결':'Workflow 연결'}</button></div></article>)}{!agentTools.length&&<div className="rag-empty">아직 RAG Tool이 없습니다. Collection을 선택하고 Tool을 생성하세요.</div>}</div>
        </div>
      </section>
      <aside className="rag-retrieval-summary">
        <section className="rag-section"><div className="rag-section-head"><div><strong>검색 준비 상태</strong><small>Indexing 결과를 Retrieval이 사용합니다.</small></div></div><div className="rag-retrieval-stats"><div><span>Indexed Source</span><strong>{retrievalOptions?.indexed_source_count??0}</strong></div><div><span>Indexed Chunk</span><strong>{retrievalOptions?.indexed_chunk_count??0}</strong></div><div><span>Embedding</span><strong>{retrievalOptions?.embedding_count??0}</strong></div><div><span>HNSW</span><strong>{retrievalOptions?.hnsw_index_name||'-'}</strong></div></div></section>
        <section className="rag-section rag-search-guide"><div className="rag-section-head"><div><strong>검색 방식 용도</strong><small>질문 성격에 맞게 직접 비교할 수 있습니다.</small></div></div><article><strong>Vector Search</strong><p>자연어 의미가 비슷한 Chunk를 pgvector cosine HNSW로 검색합니다.</p></article><article><strong>Keyword Search</strong><p>오류코드, 함수명, 테이블명처럼 정확한 문자열을 Content/Path/Symbol에서 검색합니다.</p></article><article><strong>Hybrid Search</strong><p>Vector와 Keyword 후보를 각각 검색한 뒤 RRF로 결합합니다.</p></article></section>
      </aside>
    </div>}
    {tab==='TEST'&&<div className="rag-test-layout">
      <main className="rag-test-main">
        <section className="rag-section rag-retrieval-test">
          <div className="rag-section-head"><div><strong>Retrieval Test</strong><small>질문 입력 → 권한 Filter → 검색 → Retrieved Chunk를 직접 확인합니다.</small></div><div className="rag-test-setting-summary"><span>{SEARCH_MODE_LABEL[retrieval.search_mode]||retrieval.search_mode}</span><span>Top K {retrieval.top_k}</span><span>Threshold {retrieval.similarity_threshold.toFixed(2)}</span><span>Router {intelligence.router_enabled?'ON':'OFF'}</span><span>Rerank {intelligence.reranking_enabled?`ON · ${intelligence.rerank_top_n}`:'OFF'}</span><span>{securityContext.role} · {securityContext.security_clearance}</span></div></div>
          <div className="rag-test-security-context"><label><span>Role</span><input value={securityContext.role} onChange={(event)=>setSecurityContext((prev)=>({...prev,role:event.target.value.toUpperCase()}))}/></label><label><span>Clearance</span><select value={securityContext.security_clearance} onChange={(event)=>setSecurityContext((prev)=>({...prev,security_clearance:event.target.value}))}><option value="PUBLIC">PUBLIC</option><option value="INTERNAL">INTERNAL</option><option value="CONFIDENTIAL">CONFIDENTIAL</option><option value="RESTRICTED">RESTRICTED</option></select></label><small>권한이 없는 Collection/Document는 Vector Search 전에 제외됩니다.</small></div>
          <div className="rag-test-query"><textarea value={retrievalQuery} placeholder="예: 로그인 실패 원인을 처리하는 코드는 어디에 있나요?" onChange={(event)=>setRetrievalQuery(event.target.value)} onKeyDown={(event)=>{if((event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();runRetrievalTest()}}}/><div><button type="button" className="rag-primary" disabled={busy==='retrieval-test'||!projectReady} onClick={runRetrievalTest}>{busy==='retrieval-test'?'검색 중...':'검색'}</button><button type="button" onClick={()=>changeTab('RETRIEVAL')}>검색 설정</button><small>Ctrl+Enter 검색</small></div></div>
          {retrievalResult&&<><div className="rag-retrieval-result-summary"><div><span>Retrieved</span><strong>{retrievalResult.result_count}</strong></div><div><span>Vector 후보</span><strong>{retrievalResult.vector_candidate_count}</strong></div><div><span>Keyword 후보</span><strong>{retrievalResult.keyword_candidate_count}</strong></div><div><span>검색 시간</span><strong>{retrievalResult.duration_ms} ms</strong></div><div><span>Search Log</span><strong>#{retrievalResult.search_log_id}</strong></div></div>{retrievalResult.router&&<div className="rag-router-trace"><div><strong>Retrieval Router</strong><span>{retrievalResult.router.configured_mode} → {retrievalResult.router.selected_mode}</span><span>confidence {Math.round((retrievalResult.router.confidence||0)*100)}%</span>{retrievalResult.reranking?.enabled&&<span>Reranking {retrievalResult.reranking.engine} · top {retrievalResult.reranking.top_n}</span>}</div><small>{retrievalResult.router.reason}</small></div>}{retrievalResult.security&&<div className="rag-security-trace"><strong>Security Filter</strong><span>{retrievalResult.security.role} · {retrievalResult.security.security_clearance}</span><span>Collection allow {retrievalResult.security.allowed_collection_ids.length} / deny {retrievalResult.security.denied_collection_ids.length}</span>{retrievalResult.search_audit_log_id&&<span>Audit #{retrievalResult.search_audit_log_id}</span>}</div>}{retrievalResult.warnings?.length>0&&<div className="rag-retrieval-warnings">{retrievalResult.warnings.map((warning,index)=><div key={index}>⚠ {warning}</div>)}</div>}<div className="rag-retrieved-list">{retrievalResult.results.map((item)=><article key={item.chunk_id}><header><div><strong>#{item.rank} · Chunk ID {item.chunk_id}</strong><small>{item.document_path}{item.start_line?` · L${item.start_line}${item.end_line?`-${item.end_line}`:''}`:''}</small></div><div className="rag-score-stack"><b>{item.score.toFixed(4)}</b><small>{retrievalResult.search_mode==='HYBRID'?'RRF':retrievalResult.search_mode==='VECTOR'?'Similarity':'Keyword'}</small></div></header><div className="rag-retrieved-meta"><span>{item.document_type}</span>{item.language&&<span>{item.language}</span>}{item.symbol_name&&<span>{item.symbol_name}</span>}{item.collections?.map((collection)=><span key={collection.id}>{collection.name}</span>)}</div><div className="rag-score-detail">{item.vector_similarity!=null&&<span>Vector {item.vector_similarity.toFixed(4)}{item.vector_rank?` · rank ${item.vector_rank}`:''}</span>}{item.keyword_score!=null&&<span>Keyword {item.keyword_score.toFixed(4)}{item.keyword_rank?` · rank ${item.keyword_rank}`:''}</span>}{item.fusion_score!=null&&<span>RRF {item.fusion_score.toFixed(4)}</span>}{item.retrieval_score!=null&&<span>1차 {item.retrieval_score.toFixed(4)}</span>}{item.rerank_score!=null&&<span className="rerank">Rerank {item.rerank_score.toFixed(4)}</span>}</div><pre>{item.content}</pre></article>)}{retrievalResult.results.length===0&&<div className="rag-empty large">검색된 Chunk가 없습니다. Threshold를 낮추거나 Metadata Filter / 검색 방식을 조정해보세요.</div>}</div></>}
        </section>
        <section className="rag-section rag-tool-test-section">
          <div className="rag-section-head"><div><strong>RAG Tool Test</strong><small>생성된 Tool 계약으로 실제 Retrieval을 실행해 Tool 출력 chunks / sources / scores를 확인합니다.</small></div><OptionHelp title="RAG Tool Test" summary="Prompt & Tool Studio에 등록된 것과 동일한 Internal Tool Executor 경로를 검사합니다." detail="Tool은 AgentStudio Backend 내부에서 직접 Retrieval Service를 호출하므로 localhost 포트 하드코딩이나 외부 HTTP 왕복이 없습니다."/></div>
          <div className="rag-agent-test-controls"><label><span>RAG Tool</span><select value={selectedAgentTool?.id??''} onChange={(event)=>setSelectedAgentToolId(Number(event.target.value)||null)}><option value="">선택</option>{agentTools.map((tool)=><option key={tool.id} value={tool.id}>{tool.tool_name}</option>)}</select></label><button type="button" className="rag-primary" disabled={!selectedAgentTool||busy.startsWith('tool-test-')} onClick={runRagToolTest}>RAG Tool Test 실행</button><button type="button" disabled={!selectedAgentTool} onClick={()=>selectedAgentTool&&onOpenPromptToolStudio?.(selectedAgentTool)}>Tool Registry에서 보기</button></div>
          {toolTestResult&&<div className="rag-tool-test-result"><div className="rag-retrieval-result-summary"><div><span>Tool</span><strong>{toolTestResult.tool_name}</strong></div><div><span>Chunk</span><strong>{toolTestResult.chunks.length}</strong></div><div><span>Search Log</span><strong>#{toolTestResult.search_log_id}</strong></div><div><span>Agent Test Log</span><strong>#{toolTestResult.agent_test_log_id}</strong></div><div><span>시간</span><strong>{toolTestResult.duration_ms} ms</strong></div></div><div className="rag-retrieved-list">{toolTestResult.chunks.map((item)=><article key={item.chunk_id}><header><div><strong>#{item.rank} · {item.document_path}</strong><small>Chunk ID {item.chunk_id} · {item.source_name}</small></div><div className="rag-score-stack"><b>{item.score.toFixed(4)}</b><small>score</small></div></header><pre>{item.content}</pre></article>)}</div></div>}
        </section>
        <section className="rag-section rag-agent-test-link-section">
          <div className="rag-section-head"><div><strong>Agent Test 연결</strong><small>RAG Tool 결과를 Prompt Context로 전달하고 기존 Prompt & Tool Studio FULL_EXECUTE Runtime에서 LLM까지 테스트합니다.</small></div></div>
          <div className="rag-agent-flow"><span>Knowledge</span><i>→</i><span>RAG Tool</span><i>→</i><span>Prompt & Tool Studio</span><i>→</i><span>Workflow</span><i>→</i><span>Agent Test</span></div>
          <div className="rag-agent-test-actions"><div><strong>{selectedAgentTool?.tool_name||'RAG Tool 미선택'}</strong><small>{selectedAgentTool?.workflow_bound?'Workflow 연결됨':'Workflow 연결 필요'} · {selectedAgentTool?.prompt_context_enabled?'Prompt Context ON':'Tool Result Context 사용'}</small></div><button type="button" className="rag-primary" disabled={!selectedAgentTool||!selectedAgentTool.workflow_bound||!retrievalQuery.trim()||busy.startsWith('agent-test-')} onClick={openAgentTest}>Prompt & Tool Studio Agent Test 열기</button></div>
          <div className="rag-agent-test-log-list">{agentTestLogs.slice(0,5).map((log)=><div key={log.id}><strong>#{log.id} · {log.test_mode} · {log.status}</strong><span>{log.query_text}</span><small>{log.duration_ms} ms{log.error_message?` · ${log.error_message}`:''}</small></div>)}{!agentTestLogs.length&&<small>RAG Tool Test 또는 Agent Test 연결 이력이 없습니다.</small>}</div>
        </section>
      </main>
      <aside className="rag-search-log-panel"><section className="rag-section"><div className="rag-section-head"><div><strong>검색 로그</strong><small>최근 Retrieval 실행 이력 · DB 저장</small></div><button type="button" onClick={refreshSearchLogs} disabled={busy==='search-logs'}>새로고침</button></div><div className="rag-search-log-list">{searchLogs.map((log)=><article key={log.id} className={log.error_message?'failed':''}><header><strong>#{log.id} · {SEARCH_MODE_LABEL[log.search_mode]||log.search_mode}</strong><span>{log.duration_ms} ms</span></header><p>{log.query_text}</p><small>Top K {log.top_k} · 결과 {log.result_count} · Vector {log.vector_candidate_count} · Keyword {log.keyword_candidate_count}</small>{log.error_message&&<div>{log.error_message}</div>}</article>)}{!searchLogs.length&&<div className="rag-empty">검색 로그가 없습니다.</div>}</div></section></aside>
    </div>}
    {tab==='OPERATION'&&<RagOperationPanel projectRoot={projectRoot} collections={collections} securityContext={securityContext} onSecurityContextChange={setSecurityContext}/>}
  </div>
}
