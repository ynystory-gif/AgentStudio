import { api } from '../../../api'
type LegacyRecord=Record<string,any>
export const fetchWorkflowDefinition=()=>api('/workflow/definition')
export const fetchWorkflowProviderStatus=()=>api('/llm/runtime-status')
export const previewWorkflow=(payload:LegacyRecord)=>api('/workflow/preview',{method:'POST',body:JSON.stringify(payload)})
