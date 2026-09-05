import { api } from '../../../api'
type LegacyRecord=Record<string,any>
export const fetchDevelopmentJob=(jobId:string|number)=>api(`/jobs/${encodeURIComponent(String(jobId))}`)
export const cancelDevelopmentJob=(jobId:string|number)=>api(`/jobs/${encodeURIComponent(String(jobId))}/cancel`,{method:'POST'})
export const fetchDevelopmentDiagnostics=(projectRoot:string)=>api(`/agent-development/diagnostics?project_root=${encodeURIComponent(projectRoot)}`)
export const resumeAgentDevelopment=(payload:LegacyRecord)=>api('/agent-development/resume',{method:'POST',body:JSON.stringify(payload)})
