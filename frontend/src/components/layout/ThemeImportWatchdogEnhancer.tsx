import { useEffect } from 'react'

const MAX_SECONDS=300
const MISSING_BOX_GRACE_MS=5000

// Module-level runtime deliberately survives React StrictMode mount/unmount cycles and
// AuthGate/layout rerenders. The elapsed clock is UX state and must not be rebuilt from
// each backend polling response or from a newly-created progress DOM node.
const runtime={
  startedAt:0,
  lastSeenAt:0,
  active:false,
  timeoutHandled:false,
}

function parseElapsed(text: LegacyValue=''){
  const match=String(text).match(/경과\s+(\d{1,3}):(\d{2})/)
  if(!match)return 0
  return Number(match[1]||0)*60+Number(match[2]||0)
}
function formatElapsed(seconds: LegacyValue){
  const value=Math.max(0,Math.floor(seconds||0))
  return `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`
}
function resetRuntime(){
  runtime.startedAt=0
  runtime.lastSeenAt=0
  runtime.active=false
  runtime.timeoutHandled=false
}

export function ThemeImportWatchdogEnhancer(){
  useEffect(()=>{
    const tick=()=>{
      const now=Date.now()
      const box=document.querySelector('[data-analysis-progress].active:not(.done)')

      if(!box){
        // React can briefly replace the modal/progress subtree. Do not reset the clock
        // immediately; otherwise an ongoing job can repeatedly jump back or freeze.
        if(runtime.active && runtime.lastSeenAt && now-runtime.lastSeenAt>MISSING_BOX_GRACE_MS){
          resetRuntime()
        }
        return
      }

      if(!runtime.active){
        const percent=box.querySelector('[data-analysis-progress-percent]')
        const already=parseElapsed(percent?.textContent||'')
        runtime.startedAt=now-already*1000
        runtime.active=true
        runtime.timeoutHandled=false
      }
      if(!runtime.startedAt)runtime.startedAt=now
      runtime.lastSeenAt=now

      const elapsed=Math.max(0,Math.floor((now-runtime.startedAt)/1000))
      const percent=box.querySelector('[data-analysis-progress-percent]')
      if(percent){
        const pct=(String(percent.textContent||'').match(/(\d{1,3})%/)||[])[1]||'0'
        percent.textContent=`${pct}% · 경과 ${formatElapsed(elapsed)}`
      }

      const heartbeat=box.querySelector('[data-analysis-heartbeat]')
      if(heartbeat&&elapsed>=30){
        const backendText=String(heartbeat.textContent||'').replace(/\s*·\s*프론트 타이머[^·]*/g,'').trim()
        heartbeat.textContent=`${backendText}${backendText?' · ':''}프론트 타이머 ${formatElapsed(elapsed)} 정상 동작 중`
      }

      if(elapsed<MAX_SECONDS||runtime.timeoutHandled)return
      runtime.timeoutHandled=true

      const warning=box.querySelector<HTMLElement>('[data-analysis-progress-warning]')
      if(warning){
        warning.textContent='최대 분석시간 5분에 도달했습니다. Backend가 실패 처리하고 분석 Process를 종료하는 상태를 확인 중입니다.'
        warning.style.display='block'
      }
      box.classList.add('warning')
      const message=box.querySelector('[data-analysis-progress-message]')
      if(message)message.textContent='최대 분석시간 5분에 도달했습니다. Backend 실패 종료 상태를 확인하고 있습니다.'
      const stage=box.querySelector('[data-analysis-progress-stage]')
      if(stage)stage.textContent='BACKEND_TIMEOUT_PENDING'
      const cancel=box.querySelector<HTMLButtonElement>('[data-analysis-cancel]')
      // Automatic timeout is not a user cancellation. Backend is authoritative and
      // returns FAILED at 300 seconds; keep the UI active until that state is observed.
      if(cancel){cancel.disabled=true;cancel.textContent='Backend 종료 확인 중'}
    }

    // 250ms makes the visible seconds stable even when backend polling is delayed.
    // The displayed value still changes only once per second because it is floored.
    const timer=window.setInterval(tick,250)
    tick()
    return()=>window.clearInterval(timer)
  },[])
  return null
}
