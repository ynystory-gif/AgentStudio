import { useEffect } from 'react'

const MAX_SECONDS=180

function parseElapsed(text=''){
  const match=String(text).match(/경과\s+(\d{1,3}):(\d{2})/)
  if(!match)return 0
  return Number(match[1]||0)*60+Number(match[2]||0)
}
function formatElapsed(seconds){
  const value=Math.max(0,Math.floor(seconds||0))
  return `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`
}

export function ThemeImportWatchdogEnhancer(){
  useEffect(()=>{
    let startAt=0
    let activeBox=null
    let timeoutHandled=false

    const reset=()=>{startAt=0;activeBox=null;timeoutHandled=false}
    const tick=()=>{
      const box=document.querySelector('[data-analysis-progress].active:not(.done)')
      if(!box){reset();return}
      if(activeBox!==box){
        activeBox=box
        const percent=box.querySelector('[data-analysis-progress-percent]')
        const already=parseElapsed(percent?.textContent||'')
        startAt=Date.now()-already*1000
        timeoutHandled=false
      }
      if(!startAt)startAt=Date.now()
      const elapsed=Math.max(0,Math.floor((Date.now()-startAt)/1000))
      const percent=box.querySelector('[data-analysis-progress-percent]')
      if(percent){
        const pct=(String(percent.textContent||'').match(/(\d{1,3})%/)||[])[1]||'0'
        percent.textContent=`${pct}% · 경과 ${formatElapsed(elapsed)}`
      }
      const heartbeat=box.querySelector('[data-analysis-heartbeat]')
      if(heartbeat&&elapsed>=60&&!String(heartbeat.textContent||'').includes('브라우저 Watchdog')){
        const current=String(heartbeat.textContent||'').trim()
        heartbeat.textContent=`${current}${current?' · ':''}브라우저 Watchdog 정상 동작 중`
      }
      if(elapsed<MAX_SECONDS||timeoutHandled)return
      timeoutHandled=true

      const warning=box.querySelector('[data-analysis-progress-warning]')
      if(warning){
        warning.textContent='전체 제한 3분을 초과했습니다. 서버 응답 여부와 관계없이 화면 작업을 시간 초과로 전환하고 취소를 요청합니다.'
        warning.style.display='block'
      }
      box.classList.add('warning')
      const message=box.querySelector('[data-analysis-progress-message]')
      if(message)message.textContent='전체 통합 분석 제한시간 3분을 초과했습니다. 작업 취소를 요청했습니다.'
      const stage=box.querySelector('[data-analysis-progress-stage]')
      if(stage)stage.textContent='CLIENT_TIMEOUT'
      const cancel=box.querySelector('[data-analysis-cancel]')
      if(cancel&&!cancel.disabled){
        try{cancel.click()}catch{}
      }
      window.setTimeout(()=>{
        if(!box.isConnected||box.classList.contains('done'))return
        box.classList.add('done')
        const bar=box.querySelector('[data-analysis-progress-bar]')
        if(bar)bar.style.animation='none'
        if(cancel){cancel.disabled=true;cancel.textContent='시간 초과'}
      },1500)
    }

    const timer=window.setInterval(tick,1000)
    tick()
    return()=>window.clearInterval(timer)
  },[])
  return null
}
