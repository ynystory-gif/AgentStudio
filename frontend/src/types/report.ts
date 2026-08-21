import type { ReactNode } from 'react'

export interface KeyValueItem {
  label: ReactNode
  value?: ReactNode
}

export interface WorkflowStepObject {
  label?: string
  name?: string
  title?: string
}

export type WorkflowStep = string | WorkflowStepObject

export interface WorkflowSummary {
  steps?: WorkflowStep[]
}

export interface ArchitectureEntry {
  label?: string
  name?: string
  component?: string
  title?: string
  path?: string
  description?: string
  purpose?: string
  reason?: string
  type?: string
}

export type ArchitectureListItem = string | ArchitectureEntry

export interface AgentArchitecture {
  components?: ArchitectureListItem[]
  interfaces?: ArchitectureListItem[]
  persistence?: ArchitectureListItem[]
  security?: ArchitectureListItem[]
  state?: ArchitectureListItem[]
}

export interface GeneratedAgentArchitectureReport {
  architecture?: AgentArchitecture
  requirementSpec?: {
    goal?: string
  }
}

export interface LlmRouteRequest {
  method?: string
  endpoint?: string
  headers?: Record<string, unknown>
  body?: unknown
}

export interface LlmRouteItem {
  label?: string
  task?: string
  group?: string
  provider?: string
  model?: string
  request?: LlmRouteRequest
  notes?: string[]
}

export interface LlmUsageSummary {
  total_tokens?: number
  input_tokens?: number
  output_tokens?: number
  cost_usd?: number
}

export interface LlmHistoryItem {
  id?: string
  status?: string
  timestamp?: string | number | Date
  task?: string
  operation?: string
  provider?: string
  model?: string
  project_root?: string
  thread_id?: string
  elapsed_ms?: number
  usage?: LlmUsageSummary
  request?: unknown
  response?: unknown
  error?: unknown
}

export interface LlmCatalogDefaults {
  llm_provider?: string
  local_llm_provider?: string
  requirements_llm_provider?: string
  coding_llm_provider?: string
  openai_model?: string
  ollama_model?: string
  ollama_base_url?: string
}

export interface LlmCatalogData {
  items?: LlmRouteItem[]
  defaults?: LlmCatalogDefaults
}

export interface LlmHistoryData {
  items?: LlmHistoryItem[]
  total_count?: number
  retention_days?: number
  truncated?: boolean
  log_path?: string
}
