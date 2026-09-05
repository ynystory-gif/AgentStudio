import { api } from '../../../api'

export const listProjects=()=>api('/projects')
export const projectDiagnostics=()=>api('/projects/diagnostics')
export const analyzeProject=(root:string)=>api(`/project/analyze?root=${encodeURIComponent(root)}`)
export const loadProjectFiles=(root:string)=>api(`/files?root=${encodeURIComponent(root)}`)
export const loadDesignCheckpoint=(root:string)=>
  api(`/workflow/design-checkpoint?project_root=${encodeURIComponent(root)}`)
