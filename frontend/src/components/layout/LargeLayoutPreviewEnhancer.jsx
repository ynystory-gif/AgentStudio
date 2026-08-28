import { useEffect } from 'react'

/*
 * The actual-size preview belongs to Theme 미리보기 -> 전체 미리보기.
 *
 * UILayoutThemePreview already owns the real React interactions (menu hover/click,
 * submenu, user menu, input focus, mobile menu, etc.).  This enhancer only gives
 * that existing interactive preview a device-sized stage.  It intentionally does
 * NOT add buttons to layout-template gallery cards.
 */
const VIEWPORTS={
  desktop:{width:1440,height:900,label:'Desktop 1440×900'},
  tablet:{width:820,height:1180,label:'Tablet 820×1180'},
  mobile:{width:390,height:844,label:'Mobile 390×844'},
}

const previewViewport=modal=>{
  const preview=modal?.querySelector('.ui-theme-preview')
  if(preview?.classList.contains('mobile'))return 'mobile'
  if(preview?.classList.contains('tablet'))return 'tablet'
  return 'desktop'
}

const clearLegacyCardButtons=()=>{
  document.querySelectorAll('[data-agentstudio-large-preview-button]').forEach(button=>button.remove())
  document.querySelectorAll('.agentstudio-large-layout-preview').forEach(node=>node.classList.remove('agentstudio-large-layout-preview'))
}

const fitThemePreview=modal=>{
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

const enhanceThemePreviewModal=modal=>{
  if(!(modal instanceof HTMLElement))return
  modal.classList.add('agentstudio-theme-actual-preview')
  document.body.classList.add('agentstudio-large-preview-open')
  requestAnimationFrame(()=>fitThemePreview(modal))
}

export function LargeLayoutPreviewEnhancer(){
  useEffect(()=>{
    let stopped=false

    const scan=()=>{
      if(stopped)return
      clearLegacyCardButtons()
      const modals=[...document.querySelectorAll('.ui-layout-theme-preview-modal')]
      modals.forEach(enhanceThemePreviewModal)
      if(!modals.length)document.body.classList.remove('agentstudio-large-preview-open')
    }

    const observer=new MutationObserver(scan)
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class']})
    const timer=window.setInterval(scan,500)
    const onResize=()=>document.querySelectorAll('.ui-layout-theme-preview-modal.agentstudio-theme-actual-preview').forEach(fitThemePreview)
    window.addEventListener('resize',onResize)
    scan()

    return()=>{
      stopped=true
      window.clearInterval(timer)
      observer.disconnect()
      window.removeEventListener('resize',onResize)
      document.body.classList.remove('agentstudio-large-preview-open')
      clearLegacyCardButtons()
    }
  },[])
  return null
}
