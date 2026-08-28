import { useEffect } from 'react'
import { api } from '../../api'

const styled=new WeakMap()

const px=value=>typeof value==='number'?`${value}px`:String(value||'')
const apply=(el,rule={})=>{
  if(!el||!rule||typeof rule!=='object')return
  const map={background:'background',color:'color',border:'borderColor',radius:'borderRadius',fontWeight:'fontWeight',fontSize:'fontSize',lineHeight:'lineHeight',padding:'padding',boxShadow:'boxShadow',textDecoration:'textDecoration',opacity:'opacity',transform:'transform'}
  for(const [key,css] of Object.entries(map)){
    if(rule[key]===undefined||rule[key]===null||rule[key]==='')continue
    let value=rule[key]
    if(['radius','fontSize'].includes(key)&&typeof value==='number')value=px(value)
    if(key==='border'){
      el.style.borderStyle='solid';el.style.borderWidth='1px'
    }
    el.style[css]=String(value)
  }
}

function visible(el){
  if(!el)return false
  const s=getComputedStyle(el)
  return s.display!=='none'&&s.visibility!=='hidden'&&el.getBoundingClientRect().width>0
}

function activeTheme(themes){
  const selects=[...document.querySelectorAll('select')].filter(visible)
  for(const select of selects){
    const opt=select.options?.[select.selectedIndex]
    const label=String(opt?.textContent||'').trim()
    const value=String(select.value||'').trim()
    const found=themes.find(t=>String(t.id)===value||String(t.name||'').trim()===label||label.includes(String(t.name||'').trim()))
    if(found)return found
  }
  return null
}

function styleWireframe(root,theme){
  if(!root||!theme)return
  const rules=theme.component_rules||{}
  const layout=theme.layout_rules||{}
  const signature=JSON.stringify([theme.id,theme.updated_at,rules,layout])
  if(styled.get(root)===signature)return
  styled.set(root,signature)

  root.dataset.importedThemeApplied='true'
  const header=root.querySelector('.ui-layout-wf-header')
  const menu=rules.menu||{}
  const menuNormal=menu.normal||{}
  const menuActive=menu.active||menuNormal
  const sidebar=rules.sidebar||{}
  const card=rules.card||{}
  const input=rules.input||{}
  const button=rules.button||{}

  apply(header,rules.header||{})
  if(header&&layout.headerHeight)header.style.minHeight=px(layout.headerHeight)

  const navItems=[...root.querySelectorAll('.ui-layout-wf-nav span')]
  navItems.forEach((item,index)=>{
    item.style.width='auto';item.style.minWidth='34px';item.style.height='18px';item.style.display='inline-block';item.style.boxSizing='border-box'
    apply(item,index===0?menuActive:menuNormal)
    if(!menuNormal.padding)item.style.padding='3px 10px'
  })

  const sidebarRoot=root.querySelector('.ui-layout-wf-sidebar')
  apply(sidebarRoot,sidebar.normal||sidebar)
  if(sidebarRoot&&layout.sidebarWidth){
    const scaled=Math.max(38,Math.min(120,Number(layout.sidebarWidth)*0.28))
    sidebarRoot.style.width=`${scaled}px`
  }
  ;[...root.querySelectorAll('.ui-layout-wf-sidebar i')].forEach((item,index)=>{
    item.style.width='calc(100% - 10px)';item.style.height='18px';item.style.boxSizing='border-box'
    apply(item,index===0?(sidebar.active||menuActive):menuNormal)
  })

  ;[...root.querySelectorAll('.ui-layout-wf-main > div:not(.ui-layout-wf-search), .ui-layout-wf-card')].forEach(el=>apply(el,card.normal||card))
  ;[...root.querySelectorAll('.ui-layout-wf-search')].forEach(el=>apply(el,input.normal||input))
  ;[...root.querySelectorAll('.ui-layout-wf-header b, .ui-layout-wf-main b')].forEach(el=>apply(el,button.normal||button))

  if(layout.contentGap){root.querySelector('.ui-layout-wf-main')?.style.setProperty('gap',px(layout.contentGap))}
}

export function ImportedThemePreviewEnhancer(){
  useEffect(()=>{
    let themes=[]
    let stopped=false
    const load=async()=>{
      try{
        const result=await api('/ui-themes')
        themes=Array.isArray(result?.themes)?result.themes:[]
      }catch{}
    }
    load()
    const scan=()=>{
      if(stopped||!themes.length)return
      const theme=activeTheme(themes)
      if(!theme)return
      document.querySelectorAll('.ui-layout-wireframe').forEach(root=>styleWireframe(root,theme))
    }
    const timer=setInterval(scan,500)
    const observer=new MutationObserver(scan);observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class','value']})
    return()=>{stopped=true;clearInterval(timer);observer.disconnect()}
  },[])
  return null
}
