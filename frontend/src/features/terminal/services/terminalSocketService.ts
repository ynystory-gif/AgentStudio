export interface TerminalSocketTarget{
  sessionId:string
  projectRoot:string
  projectName?:string
}

export function terminalSocketUrl(target:TerminalSocketTarget){
  const cfg=window.__AGENTSTUDIO_CONFIG__||{}
  const host=cfg.BACKEND_HOST||window.location.hostname||'127.0.0.1'
  const port=cfg.BACKEND_PORT
  const protocol=window.location.protocol==='https:'?'wss':'ws'
  return `${protocol}://${host}:${port}/ws/terminal/${encodeURIComponent(target.sessionId)}`
    +`?root=${encodeURIComponent(target.projectRoot)}`
    +`&project_name=${encodeURIComponent(target.projectName||'')}`
}

export function createTerminalSocket(target:TerminalSocketTarget){
  return new WebSocket(terminalSocketUrl(target))
}
