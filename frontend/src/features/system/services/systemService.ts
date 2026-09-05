import { api, apiFetch, runtimeInfo, saveBlobToOutput } from '../../../api'
export { apiFetch, runtimeInfo, saveBlobToOutput }
export const systemApi=(path:string,init?:RequestInit)=>api(path,init)
export async function loadSystemOverview(){
  const [status,settings]=await Promise.all([api('/system/status'),api('/settings')])
  const optional=async(path:string)=>{try{return await api(path)}catch{return null}}
  const [ollamaRuntime,gpuRuntime,databaseRuntime]=await Promise.all([
    optional('/settings/ollama/runtime/status'),
    optional('/settings/gpu/runtime/status'),
    optional('/settings/database-runtime'),
  ])
  const backendPort=Number(settings?.AGENTSTUDIO_BACKEND_PORT||window.__AGENTSTUDIO_CONFIG__?.BACKEND_PORT||0)
  const frontendPort=Number(settings?.AGENTSTUDIO_FRONTEND_PORT||window.__AGENTSTUDIO_CONFIG__?.FRONTEND_PORT||0)
  const currentFrontendPort=Number(window.location.port||window.__AGENTSTUDIO_CONFIG__?.FRONTEND_PORT||0)
  const portInfo=await optional(`/system/ports/recommend?backend_port=${backendPort}&frontend_port=${frontendPort}&current_frontend_port=${currentFrontendPort}`)
  return {status,settings,ollamaRuntime,gpuRuntime,databaseRuntime,portInfo}
}
