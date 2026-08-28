import { useEffect } from 'react'

const VIEWPORTS={
  desktop:{width:1440,height:900,label:'Desktop 1440×900'},
  tablet:{width:820,height:1180,label:'Tablet 820×1180'},
  mobile:{width:390,height:844,label:'Mobile 390×844'},
}

const visible=el=>{
  if(!el)return false
  const style=getComputedStyle(el)
  const rect=el.getBoundingClientRect()
  return style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0
}

const previewViewport=dialog=>{
  const buttons=[...dialog.querySelectorAll('button')].filter(visible)
  const active=buttons.find(btn=>btn.classList.contains('active')&&/desktop|tablet|mobile/i.test(btn.textContent||''))
  const text=String(active?.textContent||'').trim().toLowerCase()
  if(text.includes('mobile'))return 'mobile'
  if(text.includes('tablet'))return 'tablet'
  return 'desktop'
}

const findDialog=root=>{
  let node=root
  for(let i=0;i<8&&node;i+=1,node=node.parentElement){
    const rect=node.getBoundingClientRect?.()
    if(!rect)continue
    const text=String(node.textContent||'')
    if(rect.width>700&&rect.height>400&&(/LAYOUT\s*\+\s*THEME\s*PREVIEW/i.test(text)||/Desktop.*Tablet.*Mobile/is.test(text)))return node
  }
  return root.parentElement
}

const ensureButton=dialog=>{
  if(!dialog||dialog.querySelector('[data-agentstudio-large-preview-button]'))return
  const button=document.createElement('button')
  button.type='button'
  button.dataset.agentstudioLargePreviewButton='true'
  button.className='agentstudio-large-preview-button'
  button.textContent='⛶ 실제 크기 미리보기'
  button.addEventListener('click',()=>{
    const mode=previewViewport(dialog)
    dialog.dataset.agentstudioPreviewViewport=mode
    dialog.classList.add('agentstudio-large-layout-preview')
    document.body.classList.add('agentstudio-large-preview-open')
    requestAnimationFrame(()=>fitPreview(dialog))
  })
  const header=[...dialog.querySelectorAll('header,div')].find(el=>{
    const text=String(el.textContent||'')
    const rect=el.getBoundingClientRect?.()
    return rect&&rect.height<180&&/LAYOUT\s*\+\s*THEME\s*PREVIEW/i.test(text)
  })
  ;(header||dialog).appendChild(button)
}

const ensureExitButton=dialog=>{
  let button=dialog.querySelector('[data-agentstudio-large-preview-exit]')
  if(button)return button
  button=document.createElement('button')
  button.type='button'
  button.dataset.agentstudioLargePreviewExit='true'
  button.className='agentstudio-large-preview-exit'
  button.textContent='✕ 전체 미리보기 닫기'
  button.addEventListener('click',()=>closeLarge(dialog))
  dialog.appendChild(button)
  return button
}

const closeLarge=dialog=>{
  if(!dialog)return
  dialog.classList.remove('agentstudio-large-layout-preview')
  delete dialog.dataset.agentstudioPreviewViewport
  document.body.classList.remove('agentstudio-large-preview-open')
  const wire=dialog.querySelector('.ui-layout-wireframe')
  if(wire){wire.style.removeProperty('--agentstudio-preview-scale')}
}

const fitPreview=dialog=>{
  if(!dialog?.classList.contains('agentstudio-large-layout-preview'))return
  const mode=previewViewport(dialog)
  dialog.dataset.agentstudioPreviewViewport=mode
  const spec=VIEWPORTS[mode]||VIEWPORTS.desktop
  const wire=dialog.querySelector('.ui-layout-wireframe')
  if(!wire)return
  wire.dataset.agentstudioViewportLabel=spec.label
  const availableWidth=Math.max(320,window.innerWidth-110)
  const availableHeight=Math.max(320,window.innerHeight-170)
  const scale=Math.min(1,availableWidth/spec.width,availableHeight/spec.height)
  wire.style.setProperty('--agentstudio-preview-width',`${spec.width}px`)
  wire.style.setProperty('--agentstudio-preview-height',`${spec.height}px`)
  wire.style.setProperty('--agentstudio-preview-scale',String(scale))
  ensureExitButton(dialog)
}

export function LargeLayoutPreviewEnhancer(){
  useEffect(()=>{
    let stopped=false
    const scan=()=>{
      if(stopped)return
      document.querySelectorAll('.ui-layout-wireframe').forEach(root=>{
        if(!visible(root))return
        const dialog=findDialog(root)
        ensureButton(dialog)
        if(dialog?.classList.contains('agentstudio-large-layout-preview'))fitPreview(dialog)
      })
    }
    const observer=new MutationObserver(scan)
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class','style']})
    const timer=setInterval(scan,600)
    const onKey=event=>{
      if(event.key!=='Escape')return
      document.querySelectorAll('.agentstudio-large-layout-preview').forEach(closeLarge)
    }
    const onResize=()=>document.querySelectorAll('.agentstudio-large-layout-preview').forEach(fitPreview)
    window.addEventListener('keydown',onKey,true)
    window.addEventListener('resize',onResize)
    scan()
    return()=>{
      stopped=true
      clearInterval(timer)
      observer.disconnect()
      window.removeEventListener('keydown',onKey,true)
      window.removeEventListener('resize',onResize)
      document.body.classList.remove('agentstudio-large-preview-open')
    }
  },[])
  return null
}
