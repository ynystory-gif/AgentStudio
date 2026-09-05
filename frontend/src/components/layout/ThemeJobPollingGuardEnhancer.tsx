import { useEffect } from 'react'

const PATCH_KEY='__theanovaThemeJobPollingGuardPatched__'
const STATUS_PATH='/api/ui-themes/import-dynamic/jobs/'
const MIN_POLL_INTERVAL_MS=1000
const REQUEST_TIMEOUT_MS=3000

const sleep=(ms: LegacyValue)=>new Promise((resolve: LegacyValue)=>window.setTimeout(resolve,ms))
const isStatusGet=(input: LegacyValue,init: LegacyValue)=>{
  const method=String(init?.method||'GET').toUpperCase()
  const url=typeof input==='string'?input:input instanceof Request?input.url:input instanceof URL?input.toString():''
  if(method!=='GET'||!url.includes(STATUS_PATH))return false
  return !url.endsWith('/cancel')
}

export function ThemeJobPollingGuardEnhancer(){
  useEffect(()=>{
    const globalWindow=window as typeof window & LegacyRecord
    if(globalWindow[PATCH_KEY])return
    globalWindow[PATCH_KEY]=true

    const originalFetch=globalWindow.fetch.bind(globalWindow)
    const lastStartedAt=new Map<LegacyValue,LegacyValue>()
    const lastGoodBody=new Map<LegacyValue,LegacyValue>()

    globalWindow.fetch=async(input: LegacyValue,init:LegacyRecord={})=>{
      if(!isStatusGet(input,init))return originalFetch(input,init)

      const url=typeof input==='string'?input:input instanceof Request?input.url:input instanceof URL?input.toString():''
      const now=Date.now()
      const previous=Number(lastStartedAt.get(url)||0)
      const wait=Math.max(0,MIN_POLL_INTERVAL_MS-(now-previous))
      if(wait>0)await sleep(wait)
      lastStartedAt.set(url,Date.now())

      const controller=new AbortController()
      const upstream=init?.signal
      const onAbort=()=>controller.abort(upstream?.reason)
      if(upstream){
        if(upstream.aborted)controller.abort(upstream.reason)
        else upstream.addEventListener('abort',onAbort,{once:true})
      }
      const timer=window.setTimeout(()=>controller.abort(new DOMException('Theme job status request timeout','TimeoutError')),REQUEST_TIMEOUT_MS)

      try{
        const response=await originalFetch(input,{...init,signal:controller.signal})
        if(response.ok){
          try{
            const text=await response.clone().text()
            if(text)lastGoodBody.set(url,text)
          }catch{}
        }
        return response
      }catch(error){
        const cached=lastGoodBody.get(url)
        if(controller.signal.aborted&&cached){
          console.warn('[ThemeJobPollingGuard] 상태 조회 3초 초과 · 직전 정상 상태를 사용하고 polling을 계속합니다.',url)
          return new Response(cached,{
            status:200,
            headers:{'Content-Type':'application/json','X-AgentStudio-Theme-Poll-Fallback':'1'},
          })
        }
        throw error
      }finally{
        window.clearTimeout(timer)
        if(upstream&&!upstream.aborted)upstream.removeEventListener('abort',onAbort)
      }
    }

    // Intentionally keep the patch for the lifetime of this page. React StrictMode
    // mounts effects twice in development; restoring fetch during the probe unmount can
    // race with an already-running Theme import.
  },[])

  return null
}
