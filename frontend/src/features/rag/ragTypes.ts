export type RagScope='AGENT'|'PROJECT'|'GLOBAL'
export type RagSourceType='FILE'|'FOLDER'|'SOURCE_CODE'
export type RagSourceStatus='REGISTERED'|'ANALYZING'|'REVIEW_REQUIRED'|'REVIEWED'|'APPROVED'|'INDEXED'|string

export interface RagStudioSetting{
  id:number
  pc_name:string
  project_root:string
  rag_enabled:boolean
  db_provider:string
  connection_mode:string
  db_schema:string
  scope:RagScope|string
  created_at?:string|null
  updated_at?:string|null
}

export interface RagCollection{
  id:number
  pc_name:string
  project_root:string
  agent_design_project_id?:number|null
  name:string
  description:string
  scope:RagScope|string
  security_level:string
  is_active:boolean
  is_deleted:boolean
  created_at?:string|null
  updated_at?:string|null
}

export interface RagSourceAnalysis{
  suitability?:string
  risk_level?:string
  reason?:string
  recommended_chunking?:string
  exists?:boolean
  resolved_path?:string
  detected_type?:string
  file_count?:number
  size_bytes?:number
  warnings?:string[]
  engine?:string
  note?:string
}

export interface RagSource{
  id:number
  pc_name:string
  project_root:string
  source_type:RagSourceType|string
  source_uri:string
  display_name:string
  status:RagSourceStatus
  suitability:string
  risk_level:string
  recommendation_reason:string
  recommended_chunking:string
  analysis_engine:string
  analysis_result:RagSourceAnalysis
  collection_ids:number[]
  reviewed_at?:string|null
  approved_at?:string|null
  is_active:boolean
  created_at?:string|null
  updated_at?:string|null
}

export interface RagDatabaseTestResult{
  ok:boolean
  postgresql?:{ok?:boolean;message?:string;[key:string]:unknown}
  pgvector?:{ok?:boolean;message?:string;[key:string]:unknown}
  ready_for_phase2_indexing?:boolean
}

export interface RagIndexConfig{
  embedding_provider:string
  embedding_model:string
  storage_dimension:number
  chunk_chars:number
  chunk_overlap_chars:number
  hnsw_index_name:string
  hnsw_metric:string
  embedding_batch_size:number
}

export interface RagChunkPreviewItem{
  document_path:string
  document_type:string
  language:string
  chunk_index:number
  content:string
  char_count:number
  token_estimate:number
  start_line?:number|null
  end_line?:number|null
  heading?:string
  symbol_name?:string
  metadata?:Record<string,unknown>
}

export interface RagChunkPreviewDocument{
  path:string
  filename:string
  document_type:string
  language:string
  size_bytes:number
  checksum:string
  chunk_count:number
  safety_level:string
  safety_warnings:string[]
  redaction_count:number
  prompt_injection_count:number
  instruction_like_count?:number
  exfiltration_count?:number
  risk_score?:number
  risk_categories?:string[]
  quarantined?:boolean
  is_duplicate:boolean
  duplicate_of_document_id?:number|null
}

export interface RagChunkPreviewResult{
  source_id:number
  documents_total:number
  documents_previewed:number
  document_preview_truncated:boolean
  duplicate_count:number
  safety_warning_count:number
  total_chunk_count:number
  chunks:RagChunkPreviewItem[]
  documents:RagChunkPreviewDocument[]
  skipped_files:Array<{path:string;reason:string}>
  config:RagIndexConfig
}

export interface RagIndexJob{
  id:number
  pc_name:string
  project_root:string
  source_id:number
  status:'PENDING'|'RUNNING'|'COMPLETED'|'FAILED'|string
  stage:string
  progress:number
  documents_total:number
  documents_processed:number
  duplicates_skipped:number
  safety_warnings:number
  chunks_created:number
  embeddings_created:number
  embedding_provider:string
  embedding_model:string
  embedding_dimension:number
  index_name:string
  index_ready:boolean
  error_message:string
  result_json:Record<string,unknown>
  started_at?:string|null
  finished_at?:string|null
  created_at?:string|null
  updated_at?:string|null
}

export type RagSearchMode='VECTOR'|'KEYWORD'|'HYBRID'

export interface RagIntelligenceSetting{
  id:number
  pc_name:string
  project_root:string
  router_enabled:boolean
  reranking_enabled:boolean
  rerank_top_n:number
  created_at?:string|null
  updated_at?:string|null
}

export interface RagRetrievalMetadataFilter{
  collection_ids:number[]
  source_ids:number[]
  document_types:string[]
  languages:string[]
  path_contains:string
}

export interface RagRetrievalSetting{
  id:number
  pc_name:string
  project_root:string
  search_mode:RagSearchMode|string
  top_k:number
  similarity_threshold:number
  metadata_filter:RagRetrievalMetadataFilter
  created_at?:string|null
  updated_at?:string|null
}

export interface RagRetrievalOptions{
  search_modes:string[]
  default_mode:RagSearchMode|string
  default_top_k:number
  default_similarity_threshold:number
  max_top_k:number
  rrf_k:number
  hnsw_index_name:string
  embedding_provider:string
  embedding_model:string
  indexed_source_count:number
  indexed_chunk_count:number
  embedding_count:number
  sources:Array<{id:number;display_name:string;source_type:string;source_uri:string}>
  document_types:string[]
  languages:string[]
}

export interface RagRetrievedChunk{
  rank:number
  chunk_id:number
  document_id:number
  source_id:number
  source_name:string
  source_type:string
  document_path:string
  filename:string
  document_type:string
  language:string
  chunk_index:number
  content:string
  start_line?:number|null
  end_line?:number|null
  heading?:string
  symbol_name?:string
  metadata:Record<string,unknown>
  collections:Array<{id:number;name:string}>
  score:number
  vector_similarity?:number|null
  keyword_score?:number|null
  fusion_score?:number|null
  vector_rank?:number|null
  keyword_rank?:number|null
  retrieval_score?:number|null
  rerank_score?:number|null
  rerank_lexical?:number|null
  rerank_structural?:number|null
}

export interface RagRetrievalRouterDecision{
  enabled:boolean
  configured_mode:string
  selected_mode:string
  reason:string
  confidence:number
  signals:Record<string,unknown>
}

export interface RagRetrievalRerankingInfo{
  enabled:boolean
  top_n:number
  engine:string
}

export interface RagSecurityContext{
  user_id:string
  role:string
  security_clearance:'PUBLIC'|'INTERNAL'|'CONFIDENTIAL'|'RESTRICTED'|string
}

export interface RagRetrievalSecurityScope extends RagSecurityContext{
  allowed_collection_ids:number[]
  denied_collection_ids:number[]
  allowed_document_security_levels:string[]
  reasons?:Record<string,string>
}

export interface RagRetrievalResult{
  search_log_id:number
  search_audit_log_id?:number
  security?:RagRetrievalSecurityScope
  query:string
  requested_search_mode?:RagSearchMode|string
  search_mode:RagSearchMode|string
  router?:RagRetrievalRouterDecision
  reranking?:RagRetrievalRerankingInfo
  top_k:number
  similarity_threshold:number
  metadata_filter:RagRetrievalMetadataFilter
  result_count:number
  vector_candidate_count:number
  keyword_candidate_count:number
  duration_ms:number
  embedding_provider:string
  embedding_model:string
  embedding_dimension:number
  hnsw_index_name:string
  rrf_k?:number|null
  warnings:string[]
  results:RagRetrievedChunk[]
}

export interface RagSearchLog{
  id:number
  pc_name:string
  project_root:string
  query_text:string
  search_mode:RagSearchMode|string
  top_k:number
  similarity_threshold:number
  metadata_filter:RagRetrievalMetadataFilter
  result_count:number
  vector_candidate_count:number
  keyword_candidate_count:number
  duration_ms:number
  embedding_provider:string
  embedding_model:string
  result_summary:{warnings?:string[];results?:Array<Record<string,unknown>>}
  error_message:string
  created_at?:string|null
}

export interface RagStudioToolDefinition{
  id:string
  name:string
  type:'API'|'Python'|'MCP'|'Database'|'Agent'
  description:string
  inputSchema:string
  outputSchema:string
  permissions:string[]
  timeout:number
  retry:number
  source:string
  usage:string[]
  version:number
  requiresConfirmation?:boolean
  riskLevel?:number
}

export interface RagStudioRouteDefinition{
  id:string
  intent:string
  condition:string
  targetType:'TOOL'|'WORKFLOW'|'LLM'|'NEXT_QUESTION'
  target:string
  enabled:boolean
}

export interface RagAgentTool{
  id:number
  pc_name:string
  project_root:string
  agent_design_project_id?:number|null
  collection_id?:number|null
  collection_name:string
  tool_name:string
  description:string
  search_mode:RagSearchMode|string
  top_k:number
  similarity_threshold:number
  metadata_filter:RagRetrievalMetadataFilter
  input_schema:Record<string,unknown>
  output_schema:Record<string,unknown>
  prompt_context_enabled:boolean
  prompt_context_mode:string
  prompt_tool_registered:boolean
  workflow_bound:boolean
  workflow_step_name:string
  status:string
  is_active:boolean
  prompt_context_rule:string
  studio_tool:RagStudioToolDefinition
  studio_route:RagStudioRouteDefinition
  created_at?:string|null
  updated_at?:string|null
}

export interface RagWorkflowBindingResult{
  id:number
  tool_id:number
  agent_design_project_id?:number|null
  node_name:string
  node_label:string
  trigger_condition:string
  is_active:boolean
  tool:RagAgentTool
  workflow_step:Record<string,unknown>
}

export interface RagToolTestResult{
  ok:boolean
  tool_id:number
  tool_name:string
  query:string
  search_mode:string
  search_log_id:number
  agent_test_log_id:number
  duration_ms:number
  chunks:RagRetrievedChunk[]
  sources:Array<Record<string,unknown>>
  scores:Array<number|null>
  prompt_context_enabled:boolean
  prompt_context_rule:string
  retrieval:RagRetrievalResult
}

export interface RagAgentTestPreparation{
  ok:boolean
  agent_test_log_id:number
  tool:RagAgentTool
  prompt_tool_studio:{
    tab:string
    testMode:string
    testInput:string
    toolTestName:string
    toolTestArgs:string
    toolTestConfirmed:boolean
  }
  trace:string[]
}

export interface RagAgentTestLog{
  id:number
  tool_id:number
  test_mode:string
  query_text:string
  status:string
  result_json:Record<string,unknown>
  error_message:string
  duration_ms:number
  created_at?:string|null
}

export interface RagSettingEvaluation{
  overall_score:number
  retrieval_readiness:number
  search_coverage:number
  test_stability:number
  efficiency:number
  basis:string
  test_summary:{
    test_count:number
    zero_result_rate:number
    warning_rate:number
    avg_duration_ms:number
    avg_result_count:number
    exact_query_ratio:number
  }
  improvements:Array<{level:string;text:string}>
  current_config:Record<string,unknown>
}

export interface RagRecommendationDiffItem{
  key:string
  label:string
  current:unknown
  recommended:unknown
  changed:boolean
  reason:string
}

export interface RagAiRecommendation{
  id:number
  pc_name:string
  project_root:string
  provider:string
  status:string
  summary:string
  current_config:Record<string,unknown>
  recommended_config:Record<string,unknown>
  diff:RagRecommendationDiffItem[]
  evaluation:RagSettingEvaluation
  test_insights:string[]
  warnings:string[]
  applied_keys:string[]
  created_at?:string|null
  applied_at?:string|null
}

export interface RagRecommendationApplyResult{
  ok:boolean
  applied_keys:string[]
  retrieval_setting:RagRetrievalSetting
  intelligence_setting:RagIntelligenceSetting
  recommendation:RagAiRecommendation
  updated_tool_count?:number
}

export interface RagSourceOperation{
  id:number
  display_name:string
  source_uri:string
  source_type:string
  status:string
  is_active:boolean
  sync_mode:string
  last_checked_at?:string|null
  last_synced_at?:string|null
  last_change_count:number
  document_count:number
}

export interface RagChangeItem{
  path:string
  filename?:string
  document_type?:string
  checksum?:string
  document_id?:number
  previous_checksum?:string
  previous_status?:string
}

export interface RagChangeDetection{
  source_id:number
  source_name:string
  added:RagChangeItem[]
  changed:RagChangeItem[]
  removed:RagChangeItem[]
  unchanged:RagChangeItem[]
  change_count:number
  skipped_files:Array<{path:string;reason:string}>
  checked_at:string
}

export interface RagSyncJob{
  id:number
  pc_name:string
  project_root:string
  source_id:number
  status:string
  stage:string
  progress:number
  added_count:number
  changed_count:number
  removed_count:number
  unchanged_count:number
  chunks_updated:number
  embeddings_updated:number
  error_message:string
  result_json:Record<string,unknown>
  started_at?:string|null
  finished_at?:string|null
  created_at?:string|null
  updated_at?:string|null
}

export interface RagOperationDocument{
  id:number
  source_id:number
  path:string
  filename:string
  document_type:string
  language:string
  checksum:string
  status:string
  chunk_count:number
  safety_level:string
  security_level:string
  security_note:string
  is_active:boolean
  version_count:number
  current_version_id?:number|null
  current_version_no?:number|null
  updated_at?:string|null
}

export interface RagDocumentVersion{
  id:number
  document_id:number
  version_no:number
  checksum:string
  document_type:string
  language:string
  safety_level:string
  chunk_count:number
  source_revision:string
  is_current:boolean
  created_by:string
  created_at?:string|null
}

export interface RagAccessRule{
  id:number
  collection_id:number
  subject_type:string
  subject_value:string
  effect:string
  permission:string
  is_active:boolean
  created_at?:string|null
  updated_at?:string|null
}

export interface RagSearchAuditLog{
  id:number
  search_log_id?:number|null
  user_id:string
  role:string
  security_clearance:string
  query_text:string
  decision:string
  allowed_collection_ids:number[]
  denied_collection_ids:number[]
  allowed_source_count:number
  result_count:number
  reason:string
  created_at?:string|null
}

export interface RagEvaluationCase{
  id:number
  question:string
  expected_document_path:string
  expected_text:string
  is_active:boolean
  created_at?:string|null
  updated_at?:string|null
}

export interface RagEvaluationRun{
  id:number
  status:string
  total_cases:number
  passed_cases:number
  hit_rate:number
  mrr:number
  recall_at_k:number
  zero_result_rate:number
  avg_duration_ms:number
  security_context?:RagSecurityContext
  result_json:{top_k?:number;search_mode?:string;security_context?:RagSecurityContext;cases?:Array<Record<string,unknown>>;metric_note?:string;[key:string]:unknown}
  error_message:string
  started_at?:string|null
  finished_at?:string|null
  created_at?:string|null
}

