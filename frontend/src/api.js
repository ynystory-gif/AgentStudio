function getRuntimeConfig() {
  return window.__AGENTSTUDIO_CONFIG__ || {}
}

function getApiBase() {
  const envBase = import.meta.env.VITE_API_BASE_URL
  if (envBase) return envBase.replace(/\/$/, '')

  const cfg = getRuntimeConfig()
  const host = cfg.BACKEND_HOST || window.location.hostname || '127.0.0.1'
  const port = cfg.BACKEND_PORT || 8000
  return `${window.location.protocol}//${host}:${port}/api`
}

function getWsBase() {
  const cfg = getRuntimeConfig()
  const host = cfg.BACKEND_HOST || window.location.hostname || '127.0.0.1'
  const port = cfg.BACKEND_PORT || 8000
  return `ws://${host}:${port}/api/ws`
}

export async function api(path, options = {}) {
  const apiBase=getApiBase()
  const url=`${apiBase}${path}`

  let res

  try{
    res=await fetch(url,{
      headers:{'Content-Type':'application/json',...(options.headers||{})},
      ...options
    })
  }catch(cause){
    const error=new Error(
      `Backend 연결 실패: ${url}`
    )
    error.name='BackendFetchError'
    error.network=true
    error.apiBase=apiBase
    error.url=url
    error.path=path
    error.cause=cause
    throw error
  }

  if(!res.ok){
    const body=await res.text()
    const error=new Error(
      `Backend HTTP ${res.status}: ${body||res.statusText}`
    )
    error.name='BackendHttpError'
    error.network=false
    error.status=res.status
    error.apiBase=apiBase
    error.url=url
    error.path=path
    error.responseBody=body
    throw error
  }

  return res.json()
}

export function connectJobs(onEvent) {
  const ws = new WebSocket(getWsBase())
  ws.onmessage = e => onEvent(JSON.parse(e.data))
  ws.onopen = () => ws.send('connected')
  return ws
}

export function runtimeInfo() {
  return {
    apiBase: getApiBase(),
    wsBase: getWsBase(),
    config: getRuntimeConfig()
  }
}
