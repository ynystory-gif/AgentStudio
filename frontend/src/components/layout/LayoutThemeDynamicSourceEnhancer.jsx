import { useEffect } from 'react'
import { api } from '../../api'

const installed=new WeakSet()

function esc(value=''){
  return String(value||'').replace(/[&<>"']/g,ch=>{
    if(ch==='&')return '&amp;'
    if(ch==='<')return '&lt;'
    if(ch==='>')return '&gt;'
    if(ch==='"')return '&quot;'
    return '&#39;'
  })
}

function ensureStyle(){
  if(document.getElementById('agentstudio-dynamic-theme-source-style'))return
  const style=document.createElement('style')
  style.id='agentstudio-dynamic-theme-source-style'
  style.textContent=`
  .ui-layout-dynamic-source{border:1px solid #294258;border-radius:9px;padding:10px;margin:8px 0;background:#0d1822;display:grid;gap:10px}
  .ui-layout-dynamic-head{display:flex;align-items:center;justify-content:space-between;gap:10px}.ui-layout-dynamic-head b{font-size:12px}.ui-layout-dynamic-head span{font-size:10px;color:#7e9ab2}
  .ui-layout-dynamic-section{display:grid;gap:7px}.ui-layout-dynamic-title{display:flex;align-items:center;justify-content:space-between;gap:8px}.ui-layout-dynamic-title strong{font-size:11px;color:#b8d1e7}.ui-layout-dynamic-title button{padding:5px 9px}
  .ui-layout-dynamic-row{display:grid;grid-template-columns:1fr auto;gap:6px;align-items:center}.ui-layout-dynamic-row.image{grid-template-columns:minmax(0,1fr) 150px auto}.ui-layout-dynamic-row input[type=text],.ui-layout-dynamic-row select{width:100%;min-width:0}.ui-layout-dynamic-row input[type=file]{width:100%;font-size:11px;color:#9eb4c8}.ui-layout-dynamic-row button.remove{min-width:34px;color:#f0a0a0}
  .ui-layout-dynamic-status{font-size:10px;color:#91a8bc;min-height:16px}.ui-layout-dynamic-status.error{color:#ff9b9b}.ui-layout-dynamic-status.ok{color:#7ee2a8}
  .ui-layout-dynamic-progress{display:none;border:1px solid #294258;border-radius:8px;background:#09131c;padding:9px;gap:7px}.ui-layout-dynamic-progress.active{display:grid}.ui-layout-dynamic-progress-head{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:10px}.ui-layout-dynamic-progress-head strong{color:#c7def1;font-size:11px}.ui-layout-dynamic-progress-head span{color:#89a7bd;font-variant-numeric:tabular-nums}.ui-layout-dynamic-progress-track{height:10px;border-radius:999px;background:#172838;overflow:hidden;position:relative}.ui-layout-dynamic-progress-bar{height:100%;width:0%;min-width:0;border-radius:999px;background:linear-gradient(90deg,#2d8cff,#65b8ff,#2d8cff);background-size:200% 100%;transition:width .28s ease;animation:agentstudio-theme-progress-stripe 1.2s linear infinite}.ui-layout-dynamic-progress.done .ui-layout-dynamic-progress-bar{animation:none}.ui-layout-dynamic-progress-message{font-size:10px;color:#a8c0d4;white-space:normal;word-break:break-word;line-height:1.45}.ui-layout-dynamic-progress-stage{font-size:9px;color:#6f8ca2;text-transform:uppercase;letter-spacing:.04em}
  @keyframes agentstudio-theme-progress-stripe{0%{background-position:0 0}100%{background-position:200% 0}}
  .ui-layout-wireframe.agentstudio-phone-wireframe{width:118px!important;max-width:118px!important;height:226px!important;min-height:226px!important;aspect-ratio:9/18!important;margin:8px auto!important;border:6px solid #172331!important;border-radius:24px!important;box-shadow:0 8px 22px rgba(0,0,0,.36)!important;overflow:hidden!important;position:relative!important}
  .ui-layout-wireframe.agentstudio-phone-wireframe:before{content:'';position:absolute;z-index:10;top:4px;left:50%;transform:translateX(-50%);width:34px;height:5px;border-radius:999px;background:#172331;opacity:.95}
  .ui-layout-wireframe.agentstudio-phone-wireframe .ui-layout-wf-header{height:22px!important;padding:4px!important}
  .ui-layout-wireframe.agentstudio-phone-wireframe .ui-layout-wf-nav{display:none!important}
  .ui-layout-wireframe.agentstudio-phone-wireframe .ui-layout-wf-body{display:block!important;height:calc(100% - 22px)!important}
  .ui-layout-wireframe.agentstudio-phone-wireframe .ui-layout-wf-sidebar{display:none!important}
  .ui-layout-wireframe.agentstudio-phone-wireframe .ui-layout-wf-main{width:100%!important;height:100%!important;padding:6px!important;display:flex!important;flex-direction:column!important;gap:5px!important}
  .ui-layout-wireframe.agentstudio-phone-wireframe .ui-layout-wf-main>*{min-height:12px!important;border-radius:5px!important}
  .ui-layout-template-card:has(.agentstudio-phone-wireframe){min-height:285px!important}
  `
  document.head.appendChild(style)
}

function markMobilePreviews(){
  const modal=document.querySelector('.ui-layout-gallery-modal')
  if(!modal)return
  const active=[...modal.querySelectorAll('.ui-layout-gallery-toolbar button')].find(button=>button.classList.contains('active'))
  const mobileCategory=String(active?.textContent||'').trim()==='모바일'
  modal.querySelectorAll('.ui-layout-wireframe').forEach(wireframe=>{
    const card=wireframe.closest('.ui-layout-template-card')
    const namedMobile=String(card?.textContent||'').includes('Mobile Responsive')
    wireframe.classList.toggle('agentstudio-phone-wireframe',mobileCategory||namedMobile)
  })
}

async function imageReference(file,role){
  const bitmap=await createImageBitmap(file)
  const size=64
  const canvas=document.createElement('canvas')
  canvas.width=size;canvas.height=size
  const ctx=canvas.getContext('2d',{willReadFrequently:true})
  if(!ctx){bitmap.close?.();throw new Error('이미지 분석 Canvas를 만들 수 없습니다.')}
  ctx.drawImage(bitmap,0,0,size,size);bitmap.close?.()
  const data=ctx.getImageData(0,0,size,size).data
  const counts=new Map()
  for(let i=0;i<data.length;i+=16){
    if(data[i+3]<180)continue
    const r=Math.round(data[i]/32)*32,g=Math.round(data[i+1]/32)*32,b=Math.round(data[i+2]/32)*32
    const key=`#${Math.min(255,r).toString(16).padStart(2,'0')}${Math.min(255,g).toString(16).padStart(2,'0')}${Math.min(255,b).toString(16).padStart(2,'0')}`
    counts.set(key,(counts.get(key)||0)+1)
  }
  const palette=[...counts.entries()].sort((a,b)=>b[1]-a[1]).slice(0,8).map(x=>x[0])
  const background=palette[0]||'#ffffff',surface=palette[1]||background,primary=palette.find(x=>x!==background&&x!==surface)||'#2563eb'
  const rgb=hex=>[parseInt(hex.slice(1,3),16),parseInt(hex.slice(3,5),16),parseInt(hex.slice(5,7),16)]
  const [rr,gg,bb]=rgb(background);const lum=(.2126*rr+.7152*gg+.0722*bb)/255
  const textPrimary=lum>.55?'#111827':'#f3f4f6',textSecondary=lum>.55?'#475569':'#a8b3c2'
  const tokens={colors:{primary,secondary:palette[2]||primary,background,surface,textPrimary,textSecondary,border:palette[3]||surface,success:'#16a34a',danger:'#dc2626'},typography:{fontFamily:"system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",headingWeight:700,bodyWeight:400},radius:{button:8,card:12,input:8},shadow:{card:'0 8px 24px rgba(15,23,42,.08)'},spacing:{unit:4,density:'comfortable'}}
  return {file_name:file.name,reference_role:role||'default',tokens,component_rules:{},layout_rules:{},preview_colors:palette}
}

const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms))
const elapsedText=start=>{
  const seconds=Math.max(0,Math.floor((Date.now()-start)/1000))
  const mm=String(Math.floor(seconds/60)).padStart(2,'0')
  const ss=String(seconds%60).padStart(2,'0')
  return `${mm}:${ss}`
}

function setProgress(host,pct,message,stage,start,{done=false,error=false}={}){
  const box=host.querySelector('[data-analysis-progress]')
  const bar=host.querySelector('[data-analysis-progress-bar]')
  const percent=host.querySelector('[data-analysis-progress-percent]')
  const msg=host.querySelector('[data-analysis-progress-message]')
  const stageEl=host.querySelector('[data-analysis-progress-stage]')
  if(!box||!bar||!percent||!msg||!stageEl)return
  const value=Math.max(0,Math.min(100,Math.round(Number(pct)||0)))
  box.classList.add('active')
  box.classList.toggle('done',done)
  box.style.borderColor=error?'#6f3030':''
  bar.style.width=`${value}%`
  percent.textContent=`${value}% · ${elapsedText(start)}`
  msg.textContent=message||'분석 중입니다.'
  stageEl.textContent=stage||'ANALYSIS'
}

async function waitForJob(host,job,start){
  let current=job
  let displayed=Math.max(12,12+Number(current?.progress||0)*.88)
  while(current&& !['completed','failed'].includes(String(current.status||''))){
    const actual=Math.max(12,12+Number(current.progress||0)*.88)
    displayed=Math.max(displayed,actual)
    // The striped bar is the activity indicator. A small bounded nudge makes a
    // long single-URL network pass visibly alive without pretending it completed.
    displayed=Math.min(96,Math.max(actual,displayed+0.35))
    setProgress(host,displayed,current.message||'통합 분석이 진행 중입니다.',current.stage||'analysis',start)
    await sleep(350)
    current=await api(`/ui-themes/import-dynamic/jobs/${encodeURIComponent(job.job_id)}`)
  }
  if(!current)throw new Error('Theme 통합 분석 작업 상태를 확인할 수 없습니다.')
  if(current.status==='failed'){
    setProgress(host,Math.max(1,displayed),current.error||current.message||'통합 분석 저장에 실패했습니다.','failed',start,{error:true})
    throw new Error(current.error||current.message||'통합 분석 저장에 실패했습니다.')
  }
  setProgress(host,100,current.message||'Theme 저장이 완료되었습니다.','completed',start,{done:true})
  return current.result||current
}

function render(host,state,status){
  const urlRows=host.querySelector('[data-dynamic-urls]')
  const imageRows=host.querySelector('[data-dynamic-images]')
  if(!urlRows||!imageRows)return
  urlRows.innerHTML=state.urls.map((value,index)=>`<div class="ui-layout-dynamic-row"><input type="text" data-url-index="${index}" value="${esc(value)}" placeholder="https://example.com"/><button type="button" class="remove" data-remove-url="${index}" ${state.urls.length===1?'disabled':''}>×</button></div>`).join('')
  imageRows.innerHTML=state.files.map((file,index)=>`<div class="ui-layout-dynamic-row image"><input type="file" accept="image/*" data-image-index="${index}"/><select data-role-index="${index}"><option value="default" ${state.roles[index]==='default'?'selected':''}>기본 화면</option><option value="menu_hover" ${state.roles[index]==='menu_hover'?'selected':''}>메뉴 Hover</option><option value="user_menu_open" ${state.roles[index]==='user_menu_open'?'selected':''}>사용자 메뉴 Open</option><option value="active" ${state.roles[index]==='active'?'selected':''}>Active 상태</option><option value="other" ${state.roles[index]==='other'?'selected':''}>기타</option></select><button type="button" class="remove" data-remove-image="${index}" ${state.files.length===1?'disabled':''}>×</button>${file?`<small style="grid-column:1 / 3;color:#8fb0ca">선택: ${esc(file.name)}</small>`:''}</div>`).join('')
  if(!state.busy){status.textContent=`URL ${state.urls.filter(x=>x.trim()).length}개 · 이미지 ${state.files.filter(Boolean).length}개 추가됨`;status.className='ui-layout-dynamic-status'}
}

function install(panel){
  if(installed.has(panel))return
  installed.add(panel);ensureStyle()
  const labels=[...panel.querySelectorAll('label')]
  const urlLabel=labels.find(label=>label.querySelector('span')?.textContent?.includes('웹사이트 URL'))
  const originalFiles=panel.querySelector('.ui-layout-theme-file-slots')
  if(urlLabel)urlLabel.style.display='none'
  if(originalFiles)originalFiles.style.display='none'
  const sourceHead=panel.querySelector('.ui-layout-theme-import-source-head')
  const countBadge=sourceHead?.querySelector('span')
  if(countBadge)countBadge.style.display='none'

  const state={urls:[''],files:[null],roles:['default'],busy:false}
  const host=document.createElement('div');host.className='ui-layout-dynamic-source'
  host.innerHTML=`<div class="ui-layout-dynamic-head"><b>동적 스타일 참고 자료</b><span>URL/이미지는 필요한 만큼 추가하여 통합 분석합니다.</span></div><div class="ui-layout-dynamic-section"><div class="ui-layout-dynamic-title"><strong>웹사이트 URL</strong><button type="button" data-add-url>＋ URL 추가</button></div><div data-dynamic-urls></div></div><div class="ui-layout-dynamic-section"><div class="ui-layout-dynamic-title"><strong>화면 캡처 이미지</strong><button type="button" data-add-image>＋ 이미지 추가</button></div><div data-dynamic-images></div></div><div class="ui-layout-dynamic-progress" data-analysis-progress><div class="ui-layout-dynamic-progress-head"><strong>통합 분석 · 저장 진행률</strong><span data-analysis-progress-percent>0% · 00:00</span></div><div class="ui-layout-dynamic-progress-track"><div class="ui-layout-dynamic-progress-bar" data-analysis-progress-bar></div></div><div class="ui-layout-dynamic-progress-message" data-analysis-progress-message>대기 중</div><div class="ui-layout-dynamic-progress-stage" data-analysis-progress-stage>READY</div></div><div class="ui-layout-dynamic-status"></div>`
  const themeNameLabel=labels.find(label=>label.querySelector('span')?.textContent?.includes('Theme 이름'))
  if(themeNameLabel?.parentElement===panel)themeNameLabel.insertAdjacentElement('afterend',host);else panel.insertBefore(host,panel.children[1]||null)
  const status=host.querySelector('.ui-layout-dynamic-status')
  if(!status)return
  render(host,state,status)

  host.addEventListener('click',event=>{
    const target=event.target
    if(!(target instanceof HTMLElement)||state.busy)return
    if(target.closest('[data-add-url]')){state.urls.push('');render(host,state,status);return}
    if(target.closest('[data-add-image]')){state.files.push(null);state.roles.push('default');render(host,state,status);return}
    const ru=target.closest('[data-remove-url]');if(ru&&state.urls.length>1){state.urls.splice(Number(ru.dataset.removeUrl),1);render(host,state,status);return}
    const ri=target.closest('[data-remove-image]');if(ri&&state.files.length>1){const i=Number(ri.dataset.removeImage);state.files.splice(i,1);state.roles.splice(i,1);render(host,state,status)}
  })
  host.addEventListener('input',event=>{const t=event.target;if(!(t instanceof HTMLInputElement)||state.busy)return;const idx=t.dataset.urlIndex;if(idx!==undefined)state.urls[Number(idx)]=t.value})
  host.addEventListener('change',event=>{if(state.busy)return;const t=event.target;if(t instanceof HTMLInputElement&&t.dataset.imageIndex!==undefined){state.files[Number(t.dataset.imageIndex)]=t.files?.[0]||null;render(host,state,status)}else if(t instanceof HTMLSelectElement&&t.dataset.roleIndex!==undefined){state.roles[Number(t.dataset.roleIndex)]=t.value}})

  const action=panel.querySelector('.ui-layout-theme-import-actions button.primary')
  action?.addEventListener('click',async event=>{
    event.preventDefault();event.stopPropagation();event.stopImmediatePropagation?.()
    if(state.busy)return
    const nameInput=labels.find(label=>label.querySelector('span')?.textContent?.includes('Theme 이름'))?.querySelector('input')
    const name=String(nameInput?.value||'').trim();const urls=state.urls.map(x=>x.trim()).filter(Boolean);const selected=state.files.map((file,index)=>({file,index})).filter(x=>x.file)
    if(!name){status.textContent='Theme 이름을 입력하세요.';status.className='ui-layout-dynamic-status error';return}
    if(!urls.length&&!selected.length){status.textContent='URL 또는 이미지를 하나 이상 추가하세요.';status.className='ui-layout-dynamic-status error';return}
    state.busy=true
    const started=Date.now()
    if(action){action.disabled=true;action.textContent='통합 분석·저장 중...'}
    panel.querySelectorAll('[data-add-url],[data-add-image],[data-remove-url],[data-remove-image],input,select').forEach(el=>{if(el!==nameInput)el.disabled=true})
    try{
      const images=[]
      setProgress(host,2,'통합 분석 작업을 준비하고 있습니다.','prepare',started)
      for(let i=0;i<selected.length;i++){
        const pct=2+Math.round(((i+1)/Math.max(1,selected.length))*10)
        setProgress(host,pct,`화면 캡처 전처리 중 ${i+1}/${selected.length} · ${selected[i].file.name}`,'image_prepare',started)
        images.push(await imageReference(selected[i].file,state.roles[selected[i].index]||'default'))
      }
      setProgress(host,12,`URL ${urls.length}개 · 이미지 ${images.length}개 통합 분석 작업을 시작합니다.`,'queue',started)
      status.textContent='통합 분석·저장이 진행 중입니다. 아래 진행률에서 현재 단계를 확인할 수 있습니다.';status.className='ui-layout-dynamic-status'
      const job=await api('/ui-themes/import-dynamic/jobs',{method:'POST',body:JSON.stringify({name,urls,images,scope:'GLOBAL'})})
      const result=await waitForJob(host,job,started)
      status.textContent=result?.message||'Theme 저장이 완료되었습니다.';status.className='ui-layout-dynamic-status ok'
      window.setTimeout(()=>window.location.reload(),900)
    }catch(error){
      status.textContent=String(error?.message||error);status.className='ui-layout-dynamic-status error'
      const box=host.querySelector('[data-analysis-progress]');if(box)box.style.borderColor='#6f3030'
    }finally{
      state.busy=false
      if(action){action.disabled=false;action.textContent='분석 후 Theme 저장'}
      panel.querySelectorAll('[data-add-url],[data-add-image],[data-remove-url],[data-remove-image],input,select').forEach(el=>{el.disabled=false})
      render(host,state,status)
    }
  },true)
}

export function LayoutThemeDynamicSourceEnhancer(){
  useEffect(()=>{
    ensureStyle()
    const scan=()=>{
      document.querySelectorAll('.ui-layout-theme-import-panel.unified-source').forEach(panel=>install(panel))
      markMobilePreviews()
    }
    scan()
    const observer=new MutationObserver(scan)
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class']})
    return()=>observer.disconnect()
  },[])
  return null
}
