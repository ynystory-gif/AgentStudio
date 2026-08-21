export type SystemSettingScalar = string | number | boolean | null | undefined

export interface SystemStatus {
  python?: boolean
  node?: boolean
  npm?: boolean
  git?: boolean
  postgres?: boolean
  fastapi?: boolean
  langgraph?: boolean
  langgraph_persistent?: boolean
  langgraph_persistent_message?: string
  ollama?: boolean
  openai_key?: boolean
  tavily_key?: boolean
  langsmith_key?: boolean
  [key: string]: unknown
}

export interface PortRecommendationSide {
  state?: string
  recommended?: number
  suggestions?: number[]
  [key: string]: unknown
}

export interface PortRecommendationInfo {
  backend?: PortRecommendationSide
  frontend?: PortRecommendationSide
  note?: string
  [key: string]: unknown
}

export type RuntimeDatabaseProvider = 'local' | 'supabase' | string

export interface DatabaseRuntimeInfo {
  active_provider?: RuntimeDatabaseProvider
  selected_provider?: RuntimeDatabaseProvider
  local_target?: string
  supabase_target?: string
  supabase_configured?: boolean
  supabase_schema?: string
  last_error?: string
  [key: string]: unknown
}

export interface LangGraphRuntimeVerification {
  ok?: boolean
  migration_count?: number
  message?: string
  [key: string]: unknown
}

export interface DatabaseSchemaVerification {
  ok?: boolean
  [key: string]: unknown
}

export interface DatabaseRuntimeSchemaResult {
  schema?: string
  agentstudio_table_count?: number
  verification?: DatabaseSchemaVerification
  vector?: 'already_installed' | 'installed' | 'verified' | string
  langgraph?: LangGraphRuntimeVerification
  rolled_back?: boolean
  [key: string]: unknown
}

export interface DatabaseRuntimeResult {
  ok?: boolean
  message?: string
  target?: string
  supabase_schema?: string
  local_settings_updated?: boolean
  verification?: DatabaseSchemaVerification
  vector?: 'already_installed' | 'installed' | 'verified' | string
  langgraph?: LangGraphRuntimeVerification
  langgraph_ok?: boolean
  langgraph_error?: string
  rolled_back?: boolean
  schema?: DatabaseRuntimeSchemaResult
  [key: string]: unknown
}

export interface OllamaRuntimeInfo {
  ok?: boolean
  message?: string
  installed?: boolean
  running?: boolean
  manageable?: boolean
  managed_by_agentstudio?: boolean
  managed_pid?: number | string | null
  local?: boolean
  version?: string
  base_url?: string
  models?: string[]
  ollama_exe?: string
  log_path?: string
  last_error?: string
  [key: string]: unknown
}

export interface SystemJobResult {
  ollama_exe?: string
  models_path?: string
  release?: {
    release_name?: string
    [key: string]: unknown
  }
  postgresql_root?: string
  traceback?: string
  [key: string]: unknown
}

export interface SystemJobState {
  job_id?: string
  status?: string
  progress?: number
  message?: string
  result?: SystemJobResult
  [key: string]: unknown
}
