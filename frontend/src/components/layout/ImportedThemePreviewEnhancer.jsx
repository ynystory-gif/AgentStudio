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

function previewMode(root){
  const preview=root?.closest?.('.ui-theme-preview')
  if(preview?.classList.contains('mobile'))return 'mobile'
  if(preview?.classList.contains('tablet'))return 'tablet'
  return 'desktop'
}

function layoutContract(layout={}){
  const contract=layout.layoutContract||layout.layout_contract||{}
  const mobile=contract.mobile||{}
  const drawer=mobile.drawer||{}
  const navigation=contract.navigation||{}
  return {
    raw:contract,
    drawerSide:String(drawer.side||layout.mobileDrawerSide||'left').toLowerCase()==='right'?'right':'left',
    drawerWidth:drawer.width||layout.mobileDrawerWidth||'82%',
    overlay:drawer.overlay||{detected:false,color:'rgba(0,0,0,.42)'},
    drawerDetected:drawer.detected!==false,
    desktopSidebarPresent:contract.desktop?.sidebar_present??layout.desktopSidebarPresent,
    navigationItems:Array.isArray(navigation.items)?navigation.items:(Array.isArray(layout.sourceNavigationItems)?layout.sourceNavigationItems:[]),
    navigationItemDetails:Array.isArray(navigation.item_details)?navigation.item_details:(Array.isArray(layout.sourceNavigationItemDetails)?layout.sourceNavigationItemDetails:[]),
    navigationPresentation:navigation.presentation||layout.sourceNavigationPresentation||{},
    useSourceItems:navigation.use_source_items_in_preview!==false,
  }
}

function clearMobileStructure(root,sidebarRoot){
  if(!root)return
  root.querySelector('.agentstudio-imported-drawer-overlay')?.remove()
  root.removeAttribute('data-imported-drawer-side')
  if(!(sidebarRoot instanceof HTMLElement))return
  ;['position','top','bottom','left','right','zIndex','maxWidth','height','boxShadow','display'].forEach(key=>{sidebarRoot.style[key]=''})
}

const navGlyph=(label='',index=0)=>{
  const value=String(label||'').toLowerCase()
  if(/home|홈/.test(value))return '⌂'
  if(/issue|문제/.test(value))return '◉'
  if(/pull|request|요청/.test(value))return '⇄'
  if(/repo|저장소/.test(value))return '▣'
  if(/project|프로젝트/.test(value))return '▦'
  if(/discussion|대화|토론/.test(value))return '◌'
  if(/market|상품|catalog/.test(value))return '◇'
  return ['◆','○','□','◇','△','◎'][index%6]
}

function sourceNavigation(sidebarRoot,items,itemDetails,presentation,menuNormal,menuActive){
  if(!(sidebarRoot instanceof HTMLElement)||!items.length)return
  const slots=[...sidebarRoot.querySelectorAll('i')]
  const iconText=String(presentation?.mode||'').toLowerCase()==='icon_text'
  slots.forEach((item,index)=>{
    const label=items[index]
    if(label){
      item.textContent=''
      const detail=itemDetails?.[index]||{}
      const showIcon=iconText||Boolean(detail?.has_icon||detail?.icon?.detected)
      if(showIcon){
        const icon=document.createElement('span')
        icon.className='agentstudio-imported-nav-icon'
        icon.textContent=navGlyph(label,index)
        icon.setAttribute('aria-hidden','true')
        item.appendChild(icon)
      }
      const text=document.createElement('span')
      text.className='agentstudio-imported-nav-text'
      text.textContent=label
      item.appendChild(text)
      item.dataset.importedSourceNav='true'
      item.title=label
      item.style.fontStyle='normal'
      item.style.fontSize='11px'
      item.style.lineHeight='18px'
      item.style.whiteSpace='nowrap'
      item.style.overflow='hidden'
      item.style.textOverflow='ellipsis'
      item.style.padding='0 7px'
      item.style.display='flex'
      item.style.alignItems='center'
      item.style.gap=String(detail?.gap||presentation?.gap||'6px')
      item.style.color=String((index===0?menuActive:menuNormal).color||'')
    }else if(item.dataset.importedSourceNav==='true'){
      item.textContent=''
      delete item.dataset.importedSourceNav
      item.removeAttribute('title')
    }
  })
}

function applyMobileDrawer(root,sidebarRoot,contract,rules,layout){
  if(!(root instanceof HTMLElement)||!(sidebarRoot instanceof HTMLElement))return
  root.style.position='relative'
  root.style.overflow='hidden'
  root.dataset.importedDrawerSide=contract.drawerSide

  const requested=String(contract.drawerWidth||'82%')
  let width=requested
  if(/^\d+(?:\.\d+)?px$/i.test(requested)){
    const raw=Number.parseFloat(requested)
    width=`${Math.max(120,Math.min(330,raw*.72))}px`
  }
  sidebarRoot.style.position='absolute'
  sidebarRoot.style.top=layout.headerHeight?`${Math.max(22,Math.min(64,Number(layout.headerHeight)*.55))}px`:'28px'
  sidebarRoot.style.bottom='0'
  sidebarRoot.style.height='auto'
  sidebarRoot.style.zIndex='32'
  sidebarRoot.style.width=width
  sidebarRoot.style.maxWidth='86%'
  sidebarRoot.style.boxShadow='0 16px 48px rgba(0,0,0,.24)'
  sidebarRoot.style.left=contract.drawerSide==='left'?'0':'auto'
  sidebarRoot.style.right=contract.drawerSide==='right'?'0':'auto'
  apply(sidebarRoot,(rules.sidebar||{}).normal||rules.sidebar||{})

  if(contract.overlay?.detected){
    const overlay=document.createElement('div')
    overlay.className='agentstudio-imported-drawer-overlay'
    overlay.setAttribute('aria-hidden','true')
    Object.assign(overlay.style,{
      position:'absolute',inset:sidebarRoot.style.top+' 0 0 0',zIndex:'24',
      background:String(contract.overlay.color||'rgba(0,0,0,.42)'),pointerEvents:'none',
    })
    root.insertBefore(overlay,sidebarRoot)
  }
}

function styleWireframe(root,theme){
  if(!root||!theme)return
  const rules=theme.component_rules||{}
  const layout=theme.layout_rules||{}
  const mode=previewMode(root)
  const contract=layoutContract(layout)
  const signature=JSON.stringify([theme.id,theme.updated_at,rules,layout,mode])
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
  clearMobileStructure(root,sidebarRoot)
  apply(sidebarRoot,sidebar.normal||sidebar)
  if(sidebarRoot&&layout.sidebarWidth){
    const scaled=Math.max(38,Math.min(120,Number(layout.sidebarWidth)*0.28))
    sidebarRoot.style.width=`${scaled}px`
  }
  ;[...root.querySelectorAll('.ui-layout-wf-sidebar i')].forEach((item,index)=>{
    item.style.width='calc(100% - 10px)';item.style.height='18px';item.style.boxSizing='border-box'
    apply(item,index===0?(sidebar.active||menuActive):menuNormal)
  })

  if(contract.useSourceItems&&contract.navigationItems.length){
    sourceNavigation(sidebarRoot,contract.navigationItems,contract.navigationItemDetails,contract.navigationPresentation,menuNormal,menuActive)
  }

  if(mode==='mobile'&&contract.drawerDetected){
    applyMobileDrawer(root,sidebarRoot,contract,rules,layout)
  }else if(mode==='desktop'&&contract.desktopSidebarPresent===false&&sidebarRoot){
    // Do not invent a permanent desktop sidebar when the source site has none.
    sidebarRoot.style.display='none'
  }

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
    const timer=setInterval(scan,400)
    // Observe only structural/class changes; styling is idempotent and the signature includes viewport mode.
    const observer=new MutationObserver(scan);observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class','value']})
    return()=>{stopped=true;clearInterval(timer);observer.disconnect()}
  },[])
  return null
}
