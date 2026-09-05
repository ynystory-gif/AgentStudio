import { api } from '../../../api'
type LegacyRecord=Record<string,any>
export const saveAgentDesignCheckpoint=(payload:LegacyRecord)=>
  api('/agent-design/checkpoint',{method:'POST',body:JSON.stringify(payload)})
export const loadAgentDesignCheckpoint=(projectRoot:string)=>
  api(`/agent-design/checkpoint?project_root=${encodeURIComponent(projectRoot)}`)
export const recommendAgentDevelopmentStages=(payload:LegacyRecord)=>
  api('/agent-development/stages/recommend',{method:'POST',body:JSON.stringify(payload)})
