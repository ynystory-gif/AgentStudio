import { useEffect } from 'react'

/*
 * Actual-size preview belongs only to Theme 미리보기 -> 전체 미리보기.
 *
 * Important: do not observe every class/style mutation in AgentStudio. The main
 * workspace changes classes frequently (hover/active/menu/job state), and a
 * document-wide MutationObserver can create a hot rescan loop that makes normal
 * buttons feel unresponsive.  This enhancer therefore uses a very small polling
 * check and only touches the Theme preview modal while it actually exists.
 */
const VIEWPORTS={
  desktop:{width:1440,height:900,label:'Desktop 1440×900'},
  tablet:{width:820,height:1180,label:'Tablet 820×1180'},
  mobile:{width:390,height:844,label:'Mobile 390×844'},
}

const previewViewport=(modal: LegacyValue)=>{
  const preview=modal?.querySelector('.ui-theme-preview')
  if(preview?.classList.contains('mobile'))return 'mobile'
  if(preview?.classList.contains('tablet'))return 'tablet'
  return 'desktop'
}

const fitThemePreview=(modal: LegacyValue)=>{
  if(!(modal instanceof HTMLElement))return
  const body=modal.querySelector('.ui-layout-theme-preview-modal-body')
  const preview=modal.querySelector('.ui-theme-preview')
  const browser=preview?.querySelector('.ui-theme-preview-browser')
  if(!(body instanceof HTMLElement)||!(preview instanceof HTMLElement)||!(browser instanceof HTMLElement))return

  const mode=previewViewport(modal)
  const spec=VIEWPORTS[mode]||VIEWPORTS.desktop
  modal.dataset.agentstudioPreviewViewport=mode
  preview.dataset.agentstudioViewportLabel=spec.label
  preview.style.setProperty('--agentstudio-preview-width',`${spec.width}px`)
  preview.style.setProperty('--agentstudio-preview-height',`${spec.height}px`)

  const availableWidth=Math.max(280,body.clientWidth-44)
  const availableHeight=Math.max(280,body.clientHeight-44)
  const scale=Math.min(1,availableWidth/spec.width,availableHeight/spec.height)
  preview.style.setProperty('--agentstudio-preview-scale',String(scale))
}

export function LargeLayoutPreviewEnhancer(){
  useEffect(()=>{
    let stopped=false
    let activeModal:LegacyValue|null=null
    let lastMode=''
    let lastSize=''

    // Remove any DOM buttons left by an older hot-reloaded build once only.
    document.querySelectorAll('[data-agentstudio-large-preview-button]').forEach((button: LegacyValue)=>button.remove())
    document.querySelectorAll('.agentstudio-large-layout-preview').forEach((node: LegacyValue)=>node.classList.remove('agentstudio-large-layout-preview'))

    const sync=()=>{
      if(stopped)return
      const modal=document.querySelector('.ui-layout-theme-preview-modal')

      if(!(modal instanceof HTMLElement)){
        if(activeModal){
          activeModal.classList.remove('agentstudio-theme-actual-preview')
          delete activeModal.dataset.agentstudioPreviewViewport
          activeModal=null
          lastMode=''
          lastSize=''
        }
        document.body.classList.remove('agentstudio-large-preview-open')
        return
      }

      if(activeModal!==modal){
        activeModal=modal
        lastMode=''
        lastSize=''
        if(!modal.classList.contains('agentstudio-theme-actual-preview'))modal.classList.add('agentstudio-theme-actual-preview')
        if(!document.body.classList.contains('agentstudio-large-preview-open'))document.body.classList.add('agentstudio-large-preview-open')
      }

      const mode=previewViewport(modal)
      const body=modal.querySelector('.ui-layout-theme-preview-modal-body')
      const size=body instanceof HTMLElement?`${body.clientWidth}x${body.clientHeight}`:''
      if(mode!==lastMode||size!==lastSize){
        lastMode=mode
        lastSize=size
        requestAnimationFrame(()=>fitThemePreview(modal))
      }
    }

    // 250 ms is more than enough for opening/viewport switching and avoids any
    // global DOM mutation feedback loop.
    const timer=window.setInterval(sync,250)
    const onResize=()=>{
      lastSize=''
      if(activeModal)requestAnimationFrame(()=>fitThemePreview(activeModal))
    }
    window.addEventListener('resize',onResize)
    sync()

    return()=>{
      stopped=true
      window.clearInterval(timer)
      window.removeEventListener('resize',onResize)
      if(activeModal){
        activeModal.classList.remove('agentstudio-theme-actual-preview')
        delete activeModal.dataset.agentstudioPreviewViewport
      }
      document.body.classList.remove('agentstudio-large-preview-open')
    }
  },[])
  return null
}
