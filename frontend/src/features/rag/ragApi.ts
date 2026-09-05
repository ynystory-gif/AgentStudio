import { api } from '../../api'
import type { RagAccessRule, RagAgentTestLog, RagAgentTestPreparation, RagAgentTool, RagAiRecommendation, RagChangeDetection, RagChunkPreviewResult, RagCollection, RagDatabaseTestResult, RagDocumentVersion, RagEvaluationCase, RagEvaluationRun, RagIndexConfig, RagIndexJob, RagIntelligenceSetting, RagOperationDocument, RagRecommendationApplyResult, RagRetrievalMetadataFilter, RagRetrievalOptions, RagRetrievalResult, RagRetrievalSetting, RagSearchAuditLog, RagSearchLog, RagSearchMode, RagSecurityContext, RagSettingEvaluation, RagSource, RagSourceOperation, RagStudioSetting, RagSyncJob, RagToolTestResult, RagWorkflowBindingResult } from './ragTypes'

function qs(value:string):string{return encodeURIComponent(value||'')}

export interface RagNativePathPickResult{ok:boolean;cancelled?:boolean;path?:string;message?:string}
export async function pickRagSourceFile(initialPath=''):Promise<RagNativePathPickResult>{
  return api<RagNativePathPickResult>('/system/pick-file',{method:'POST',body:JSON.stringify({title:'RAG에 등록할 파일 선택',initial_path:initialPath||'',file_filter:'모든 파일 (*.*)|*.*'})})
}
export async function pickRagSourceFolder(initialPath=''):Promise<RagNativePathPickResult>{
  return api<RagNativePathPickResult>('/system/pick-folder',{method:'POST',body:JSON.stringify({title:'RAG에 등록할 폴더 선택',initial_path:initialPath||''})})
}

export async function loadRagState(projectRoot:string):Promise<RagStudioSetting>{
  return api<RagStudioSetting>(`/rag/state?project_root=${qs(projectRoot)}`)
}
export async function saveRagState(projectRoot:string,patch:Partial<RagStudioSetting>):Promise<RagStudioSetting>{
  return api<RagStudioSetting>('/rag/state',{method:'PUT',body:JSON.stringify({project_root:projectRoot,...patch})})
}
export async function loadRagCollections(projectRoot:string):Promise<RagCollection[]>{
  const result=await api<{items:RagCollection[]}>(`/rag/collections?project_root=${qs(projectRoot)}`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function createRagCollection(payload:{project_root:string;agent_design_project_id?:number|null;name:string;description:string;scope:string;security_level:string}):Promise<RagCollection>{
  return api<RagCollection>('/rag/collections',{method:'POST',body:JSON.stringify(payload)})
}
export async function updateRagCollection(id:number,patch:Partial<RagCollection>):Promise<RagCollection>{
  return api<RagCollection>(`/rag/collections/${id}`,{method:'PUT',body:JSON.stringify(patch)})
}
export async function deleteRagCollection(id:number):Promise<{ok:boolean;id:number}>{
  return api<{ok:boolean;id:number}>(`/rag/collections/${id}`,{method:'DELETE'})
}
export async function loadRagSources(projectRoot:string):Promise<RagSource[]>{
  const result=await api<{items:RagSource[]}>(`/rag/sources?project_root=${qs(projectRoot)}`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function createRagSource(payload:{project_root:string;source_type:string;source_uri:string;source_text?:string;display_name?:string;collection_ids:number[]}):Promise<RagSource>{
  return api<RagSource>('/rag/sources',{method:'POST',body:JSON.stringify(payload)})
}
export async function analyzeRagSource(sourceId:number):Promise<RagSource>{
  return api<RagSource>('/rag/sources/analyze',{method:'POST',body:JSON.stringify({source_id:sourceId})})
}
export async function reviewRagSource(sourceId:number):Promise<RagSource>{
  return api<RagSource>('/rag/sources/review',{method:'POST',body:JSON.stringify({source_id:sourceId})})
}
export async function approveRagSource(sourceId:number):Promise<RagSource>{
  return api<RagSource>('/rag/sources/approve',{method:'POST',body:JSON.stringify({source_id:sourceId})})
}
export async function deleteRagSource(sourceId:number):Promise<{ok:boolean;id:number}>{
  return api<{ok:boolean;id:number}>(`/rag/sources/${sourceId}`,{method:'DELETE'})
}
export async function testRagDatabase(databaseUrl=''):Promise<RagDatabaseTestResult>{
  return api<RagDatabaseTestResult>('/rag/database/test',{method:'POST',body:JSON.stringify({database_url:databaseUrl})})
}
export async function loadRagIndexConfig():Promise<RagIndexConfig>{
  return api<RagIndexConfig>('/rag/index/config')
}
export async function previewRagChunks(sourceId:number,limit=16):Promise<RagChunkPreviewResult>{
  return api<RagChunkPreviewResult>('/rag/chunk-preview',{method:'POST',body:JSON.stringify({source_id:sourceId,limit})})
}
export async function startRagIndex(sourceId:number):Promise<RagIndexJob>{
  return api<RagIndexJob>('/rag/index',{method:'POST',body:JSON.stringify({source_id:sourceId})})
}
export async function loadRagIndexJobs(projectRoot:string,limit=30):Promise<RagIndexJob[]>{
  const result=await api<{items:RagIndexJob[]}>(`/rag/index/jobs?project_root=${qs(projectRoot)}&limit=${limit}`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function loadRagIndexJob(jobId:number):Promise<RagIndexJob>{
  return api<RagIndexJob>(`/rag/index/jobs/${jobId}`)
}
export async function loadRagRetrievalSetting(projectRoot:string):Promise<RagRetrievalSetting>{
  return api<RagRetrievalSetting>(`/rag/retrieval/settings?project_root=${qs(projectRoot)}`)
}
export async function saveRagRetrievalSetting(projectRoot:string,patch:Partial<RagRetrievalSetting>):Promise<RagRetrievalSetting>{
  return api<RagRetrievalSetting>('/rag/retrieval/settings',{method:'PUT',body:JSON.stringify({project_root:projectRoot,...patch})})
}
export async function loadRagRetrievalOptions(projectRoot:string):Promise<RagRetrievalOptions>{
  return api<RagRetrievalOptions>(`/rag/retrieval/options?project_root=${qs(projectRoot)}`)
}
export async function retrieveRag(payload:{project_root:string;query:string;search_mode:RagSearchMode|string;top_k:number;similarity_threshold:number;metadata_filter:RagRetrievalMetadataFilter;router_enabled?:boolean;reranking_enabled?:boolean;rerank_top_n?:number;security_context?:RagSecurityContext}):Promise<RagRetrievalResult>{
  return api<RagRetrievalResult>('/rag/retrieve',{method:'POST',body:JSON.stringify(payload)})
}

export async function loadRagIntelligenceSetting(projectRoot:string):Promise<RagIntelligenceSetting>{
  return api<RagIntelligenceSetting>(`/rag/intelligence/settings?project_root=${qs(projectRoot)}`)
}
export async function saveRagIntelligenceSetting(projectRoot:string,patch:Partial<RagIntelligenceSetting>):Promise<RagIntelligenceSetting>{
  return api<RagIntelligenceSetting>('/rag/intelligence/settings',{method:'PUT',body:JSON.stringify({project_root:projectRoot,...patch})})
}
export async function evaluateRagSettings(projectRoot:string):Promise<RagSettingEvaluation>{
  return api<RagSettingEvaluation>(`/rag/evaluation?project_root=${qs(projectRoot)}`)
}
export async function createRagAiRecommendation(projectRoot:string):Promise<RagAiRecommendation>{
  return api<RagAiRecommendation>('/rag/recommendations',{method:'POST',body:JSON.stringify({project_root:projectRoot})})
}
export async function applyRagAiRecommendation(recommendationId:number,keys:string[],applyAll=false):Promise<RagRecommendationApplyResult>{
  return api<RagRecommendationApplyResult>(`/rag/recommendations/${recommendationId}/apply`,{method:'POST',body:JSON.stringify({keys,apply_all:applyAll})})
}
export async function loadRagSearchLogs(projectRoot:string,limit=30):Promise<RagSearchLog[]>{
  const result=await api<{items:RagSearchLog[]}>(`/rag/search-logs?project_root=${qs(projectRoot)}&limit=${limit}`)
  return Array.isArray(result?.items)?result.items:[]
}



export async function loadRagAgentTools(projectRoot:string):Promise<RagAgentTool[]>{
  const result=await api<{items:RagAgentTool[]}>(`/rag/tools?project_root=${qs(projectRoot)}`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function generateRagAgentTool(payload:{project_root:string;agent_design_project_id?:number|null;collection_id?:number|null;tool_name?:string;description?:string;search_mode?:string;top_k?:number;similarity_threshold?:number;metadata_filter?:RagRetrievalMetadataFilter;prompt_context_enabled?:boolean}):Promise<RagAgentTool>{
  return api<RagAgentTool>('/rag/tools/generate',{method:'POST',body:JSON.stringify(payload)})
}
export async function markRagPromptToolRegistered(toolId:number,registered=true):Promise<RagAgentTool>{
  return api<RagAgentTool>(`/rag/tools/${toolId}/register`,{method:'POST',body:JSON.stringify({registered})})
}
export async function updateRagPromptContext(toolId:number,enabled:boolean):Promise<RagAgentTool>{
  return api<RagAgentTool>(`/rag/tools/${toolId}/prompt-context`,{method:'PUT',body:JSON.stringify({enabled})})
}
export async function bindRagWorkflow(toolId:number,agentDesignProjectId?:number|null):Promise<RagWorkflowBindingResult>{
  return api<RagWorkflowBindingResult>(`/rag/tools/${toolId}/workflow-bind`,{method:'POST',body:JSON.stringify({agent_design_project_id:agentDesignProjectId||null})})
}
export async function testRagAgentTool(toolId:number,payload:{query:string;top_k?:number;similarity_threshold?:number;security_context?:RagSecurityContext}):Promise<RagToolTestResult>{
  return api<RagToolTestResult>(`/rag/tools/${toolId}/execute`,{method:'POST',body:JSON.stringify(payload)})
}
export async function prepareRagAgentTest(toolId:number,query:string):Promise<RagAgentTestPreparation>{
  return api<RagAgentTestPreparation>(`/rag/tools/${toolId}/agent-test/prepare`,{method:'POST',body:JSON.stringify({query})})
}
export async function loadRagAgentTestLogs(projectRoot:string,limit=30):Promise<RagAgentTestLog[]>{
  const result=await api<{items:RagAgentTestLog[]}>(`/rag/agent-test-logs?project_root=${qs(projectRoot)}&limit=${limit}`)
  return Array.isArray(result?.items)?result.items:[]
}

export async function loadRagOperationSources(projectRoot:string):Promise<RagSourceOperation[]>{
  const result=await api<{items:RagSourceOperation[]}>(`/rag/operation/sources?project_root=${qs(projectRoot)}`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function saveRagSourceSyncMode(sourceId:number,syncMode:string):Promise<Record<string,unknown>>{
  return api<Record<string,unknown>>(`/rag/operation/sources/${sourceId}/sync-mode`,{method:'PUT',body:JSON.stringify({sync_mode:syncMode})})
}
export async function detectRagSourceChanges(sourceId:number):Promise<RagChangeDetection>{
  return api<RagChangeDetection>(`/rag/operation/sources/${sourceId}/changes`,{method:'POST'})
}
export async function startRagSourceSync(sourceId:number):Promise<RagSyncJob>{
  return api<RagSyncJob>(`/rag/operation/sources/${sourceId}/sync`,{method:'POST'})
}
export async function loadRagSyncJobs(projectRoot:string,limit=30):Promise<RagSyncJob[]>{
  const result=await api<{items:RagSyncJob[]}>(`/rag/operation/sync-jobs?project_root=${qs(projectRoot)}&limit=${limit}`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function setRagSourceActive(sourceId:number,active:boolean):Promise<{ok:boolean;id:number;is_active:boolean}>{
  return api<{ok:boolean;id:number;is_active:boolean}>(`/rag/operation/sources/${sourceId}/active`,{method:'PUT',body:JSON.stringify({active})})
}
export async function loadRagOperationDocuments(projectRoot:string,sourceId?:number|null):Promise<RagOperationDocument[]>{
  const suffix=sourceId?`&source_id=${sourceId}`:''
  const result=await api<{items:RagOperationDocument[]}>(`/rag/operation/documents?project_root=${qs(projectRoot)}${suffix}`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function setRagDocumentActive(documentId:number,active:boolean):Promise<{ok:boolean;id:number;is_active:boolean;status:string}>{
  return api<{ok:boolean;id:number;is_active:boolean;status:string}>(`/rag/operation/documents/${documentId}/active`,{method:'PUT',body:JSON.stringify({active})})
}
export async function loadRagDocumentVersions(documentId:number):Promise<RagDocumentVersion[]>{
  const result=await api<{items:RagDocumentVersion[]}>(`/rag/operation/documents/${documentId}/versions`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function rollbackRagDocumentVersion(versionId:number):Promise<{ok:boolean;document_id:number;version_id:number;version_no:number;chunk_count:number;embedding_count:number}>{
  return api<{ok:boolean;document_id:number;version_id:number;version_no:number;chunk_count:number;embedding_count:number}>(`/rag/operation/versions/${versionId}/rollback`,{method:'POST'})
}
export async function saveRagDocumentSecurity(documentId:number,securityLevel:string,note=''):Promise<Record<string,unknown>>{
  return api<Record<string,unknown>>(`/rag/security/documents/${documentId}`,{method:'PUT',body:JSON.stringify({security_level:securityLevel,note})})
}
export async function loadRagAccessRules(projectRoot:string):Promise<RagAccessRule[]>{
  const result=await api<{items:RagAccessRule[]}>(`/rag/security/access-rules?project_root=${qs(projectRoot)}`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function createRagAccessRule(payload:{project_root:string;collection_id:number;subject_type:string;subject_value:string;effect:string}):Promise<RagAccessRule>{
  return api<RagAccessRule>('/rag/security/access-rules',{method:'POST',body:JSON.stringify(payload)})
}
export async function deleteRagAccessRule(ruleId:number):Promise<{ok:boolean;id:number}>{
  return api<{ok:boolean;id:number}>(`/rag/security/access-rules/${ruleId}`,{method:'DELETE'})
}
export async function loadRagSearchAudits(projectRoot:string,limit=100):Promise<RagSearchAuditLog[]>{
  const result=await api<{items:RagSearchAuditLog[]}>(`/rag/security/audit-logs?project_root=${qs(projectRoot)}&limit=${limit}`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function loadRagEvaluationCases(projectRoot:string):Promise<RagEvaluationCase[]>{
  const result=await api<{items:RagEvaluationCase[]}>(`/rag/evaluation/cases?project_root=${qs(projectRoot)}`)
  return Array.isArray(result?.items)?result.items:[]
}
export async function createRagEvaluationCase(payload:{project_root:string;question:string;expected_document_path:string;expected_text:string}):Promise<RagEvaluationCase>{
  return api<RagEvaluationCase>('/rag/evaluation/cases',{method:'POST',body:JSON.stringify(payload)})
}
export async function deleteRagEvaluationCase(caseId:number):Promise<{ok:boolean;id:number}>{
  return api<{ok:boolean;id:number}>(`/rag/evaluation/cases/${caseId}`,{method:'DELETE'})
}
export async function startRagEvaluation(projectRoot:string,securityContext?:RagSecurityContext):Promise<RagEvaluationRun>{
  return api<RagEvaluationRun>('/rag/evaluation/runs',{method:'POST',body:JSON.stringify({project_root:projectRoot,security_context:securityContext})})
}
export async function loadRagEvaluationRuns(projectRoot:string,limit=30):Promise<RagEvaluationRun[]>{
  const result=await api<{items:RagEvaluationRun[]}>(`/rag/evaluation/runs?project_root=${qs(projectRoot)}&limit=${limit}`)
  return Array.isArray(result?.items)?result.items:[]
}


export interface AccountDatabaseProfile{
  account_database_profiles_id:number
  account_profile_id:number
  connection_id:string
  name:string
  db_type:string
  host?:string
  port?:number
  database?:string
  schema_name?:string
  username?:string
  project_id?:string
  credential_saved?:boolean
}
export interface AccountProjectSettingItem{account_project_settings_id:number;setting_group:string;setting_key:string;value:Record<string,unknown>;source_profile_id?:number|null;updated_at?:string}
export interface AccountProjectSettingsResponse{ok:boolean;project_root:string;items:AccountProjectSettingItem[];has_project_settings:boolean;account_database_profiles:AccountDatabaseProfile[]}
export async function loadAccountProjectSettings(projectRoot:string):Promise<AccountProjectSettingsResponse>{
  return api<AccountProjectSettingsResponse>(`/account-settings/project?project_root=${qs(projectRoot)}`)
}
export async function saveAccountProjectSetting(payload:{project_root:string;setting_group:string;setting_key?:string;value:Record<string,unknown>;source_profile_id?:number|null;title?:string;summary?:string}):Promise<Record<string,unknown>>{
  return api<Record<string,unknown>>('/account-settings/project',{method:'PUT',body:JSON.stringify(payload)})
}
