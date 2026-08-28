import { useEffect } from 'react'
import { api } from '../../api'

type DynamicState={urls:string[];files:(File|null)[];roles:string[];busy:boolean}

const installed=new WeakSet<HTMLElement>()

function esc(value:string){return String(value||'').replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]||ch))}

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
  `
  document.head.appendChild(style)
}

async function imageReference(file:File,role:string){
  const bitmap=await createImageBitmap(file)
  const size=64
  const canvas=document.createElement('canvas');canvas.width=size;canvas.height=size
  const ctx=canvas.getContext('2d',{willReadFrequently:true})!
  ctx.drawImage(bitmap,0,0,size,size);bitmap.close?.()
  const data=ctx.getImageData(0,0,size,size).data
  const counts=new Map<string,number>()
  for(let i=0;i<data.length;i+=16){
    if(data[i+3]<180)continue
    const r=Math.round(data[i]/32)*32,g=Math.round(data[i+1]/32)*32,b=Math.round(data[i+2]/32)*32
    const key=`#${Math.min(255,r).toString(16).padStart(2,'0')}${Math.min(255,g).toString(16).padStart(2,'0')}${Math.min(255,b).toString(16).padStart(2,'0')}`
    counts.set(key,(counts.get(key)||0)+1)
  }
  const palette=[...counts.entries()].sort((a,b)=>b[1]-a[1]).slice(0,8).map(x=>x[0])
  const background=palette[0]||'#ffffff',surface=palette[1]||background,primary=palette.find(x=>x!==background&&x!==surface)||'#2563eb'
  const rgb=(hex:string)=>[parseInt(hex.slice(1,3),16),parseInt(hex.slice(3,5),16),parseInt(hex.slice(5,7),16)]
  const [rr,gg,bb]=rgb(background);const lum=(.2126*rr+.7152*gg+.0722*bb)/255
  const textPrimary=lum>.55?'#111827':'#f3f4f6',textSecondary=lum>.55?'#475569':'#a8b3c2'
  const tokens={colors:{primary,secondary:palette[2]||primary,background,surface,textPrimary,textSecondary,border:palette[3]||surface,success:'#16a34a',danger:'#dc2626'},typography:{fontFamily:"system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",headingWeight:700,bodyWeight:400},radius:{button:8,card:12,input:8},shadow:{card:'0 8px 24px rgba(15,23,42,.08)'},spacing:{unit:4,density:'comfortable'}}
  return {file_name:file.name,reference_role:role||'default',tokens,component_rules:{},layout_rules:{},preview_colors:palette}
}

function render(host:HTMLElement,state:DynamicState,status:HTMLElement){
  const urlRows=host.querySelector<HTMLElement>('[data-dynamic-urls]')!
  const imageRows=host.querySelector<HTMLElement>('[data-dynamic-images]')!
  urlRows.innerHTML=state.urls.map((value,index)=>`<div class="ui-layout-dynamic-row"><input type="text" data-url-index="${index}" value="${esc(value)}" placeholder="https://example.com"/><button type="button" class="remove" data-remove-url="${index}" ${state.urls.length===1?'disabled':''}>×</button></div>`).join('')
  imageRows.innerHTML=state.files.map((file,index)=>`<div class="ui-layout-dynamic-row image"><input type="file" accept="image/*" data-image-index="${index}"/><select data-role-index="${index}"><option value="default" ${state.roles[index]==='default'?'selected':''}>기본 화면</option><option value="menu_hover" ${state.roles[index]==='menu_hover'?'selected':''}>메뉴 Hover</option><option value="user_menu_open" ${state.roles[index]==='user_menu_open'?'selected':''}>사용자 메뉴 Open</option><option value="active" ${state.roles[index]==='active'?'selected':''}>Active 상태</option><option value="other" ${state.roles[index]==='other'?'selected':''}>기타</option></select><button type="button" class="remove" data-remove-image="${index}" ${state.files.length===1?'disabled':''}>×</button>${file?`<small style="grid-column:1 / 3;color:#8fb0ca">선택: ${esc(file.name)}</small>`:''}</div>`).join('')
  status.textContent=`URL ${state.urls.filter(x=>x.trim()).length}개 · 이미지 ${state.files.filter(Boolean).length}개 추가됨`
  status.className='ui-layout-dynamic-status'
}

function install(panel:HTMLElement){
  if(installed.has(panel))return
  installed.add(panel);ensureStyle()
  const labels=[...panel.querySelectorAll('label')]
  const urlLabel=labels.find(label=>label.querySelector('span')?.textContent?.includes('웹사이트 URL')) as HTMLElement|undefined
  const originalFiles=panel.querySelector<HTMLElement>('.ui-layout-theme-file-slots')
  if(urlLabel)urlLabel.style.display='none'
  if(originalFiles)originalFiles.style.display='none'
  const sourceHead=panel.querySelector('.ui-layout-theme-import-source-head')
  const countBadge=sourceHead?.querySelector('span') as HTMLElement|null
  if(countBadge)countBadge.style.display='none'

  const state:DynamicState={urls:[''],files:[null],roles:['default'],busy:false}
  const host=document.createElement('div');host.className='ui-layout-dynamic-source'
  host.innerHTML=`<div class="ui-layout-dynamic-head"><b>동적 스타일 참고 자료</b><span>URL/이미지는 필요한 만큼 추가하여 통합 분석합니다.</span></div><div class="ui-layout-dynamic-section"><div class="ui-layout-dynamic-title"><strong>웹사이트 URL</strong><button type="button" data-add-url>＋ URL 추가</button></div><div data-dynamic-urls></div></div><div class="ui-layout-dynamic-section"><div class="ui-layout-dynamic-title"><strong>화면 캡처 이미지</strong><button type="button" data-add-image>＋ 이미지 추가</button></div><div data-dynamic-images></div></div><div class="ui-layout-dynamic-status"></div>`
  const themeNameLabel=labels.find(label=>label.querySelector('span')?.textContent?.includes('Theme 이름'))
  if(themeNameLabel?.parentElement===panel)themeNameLabel.insertAdjacentElement('afterend',host);else panel.insertBefore(host,panel.children[1]||null)
  const status=host.querySelector<HTMLElement>('.ui-layout-dynamic-status')!
  render(host,state,status)

  host.addEventListener('click',event=>{
    const target=event.target as HTMLElement
    if(target.closest('[data-add-url]')){state.urls.push('');render(host,state,status);return}
    if(target.closest('[data-add-image]')){state.files.push(null);state.roles.push('default');render(host,state,status);return}
    const ru=target.closest<HTMLElement>('[data-remove-url]');if(ru&&state.urls.length>1){state.urls.splice(Number(ru.dataset.removeUrl),1);render(host,state,status);return}
    const ri=target.closest<HTMLElement>('[data-remove-image]');if(ri&&state.files.length>1){const i=Number(ri.dataset.removeImage);state.files.splice(i,1);state.roles.splice(i,1);render(host,state,status)}
  })
  host.addEventListener('input',event=>{const t=event.target as HTMLInputElement;const idx=t.dataset.urlIndex;if(idx!==undefined)state.urls[Number(idx)]=t.value})
  host.addEventListener('change',event=>{const t=event.target as HTMLInputElement|HTMLSelectElement;if((t as HTMLInputElement).dataset.imageIndex!==undefined){const input=t as HTMLInputElement;state.files[Number(input.dataset.imageIndex)]=input.files?.[0]||null;render(host,state,status)}else if((t as HTMLSelectElement).dataset.roleIndex!==undefined){const select=t as HTMLSelectElement;state.roles[Number(select.dataset.roleIndex)]=select.value}})

  const action=panel.querySelector<HTMLButtonElement>('.ui-layout-theme-import-actions button.primary')
  action?.addEventListener('click',async event=>{
    event.preventDefault();event.stopPropagation();(event as any).stopImmediatePropagation?.()
    if(state.busy)return
    const nameInput=(labels.find(label=>label.querySelector('span')?.textContent?.includes('Theme 이름'))?.querySelector('input') as HTMLInputElement|null)
    const name=String(nameInput?.value||'').trim();const urls=state.urls.map(x=>x.trim()).filter(Boolean);const selected=state.files.map((file,index)=>({file,index})).filter(x=>x.file) as {file:File;index:number}[]
    if(!name){status.textContent='Theme 이름을 입력하세요.';status.className='ui-layout-dynamic-status error';return}
    if(!urls.length&&!selected.length){status.textContent='URL 또는 이미지를 하나 이상 추가하세요.';status.className='ui-layout-dynamic-status error';return}
    state.busy=true;if(action){action.disabled=true;action.textContent='통합 분석·저장 중...'}
    try{
      const images=[] as any[]
      for(let i=0;i<selected.length;i++){status.textContent=`이미지 분석 중 ${i+1}/${selected.length} · ${selected[i].file.name}`;images.push(await imageReference(selected[i].file,state.roles[selected[i].index]||'default'))}
      status.textContent=`URL ${urls.length}개 · 이미지 ${images.length}개 통합 분석 중...`
      const result=await api<any>('/ui-themes/import-dynamic',{method:'POST',body:JSON.stringify({name,urls,images,scope:'GLOBAL'})})
      status.textContent=result?.message||'Theme 저장이 완료되었습니다.';status.className='ui-layout-dynamic-status ok'
      window.setTimeout(()=>window.location.reload(),700)
    }catch(error:any){status.textContent=String(error?.message||error);status.className='ui-layout-dynamic-status error'}finally{state.busy=false;if(action){action.disabled=false;action.textContent='분석 후 Theme 저장'}}
  },true)
}

export function LayoutThemeDynamicSourceEnhancer(){
  useEffect(()=>{
    const scan=()=>document.querySelectorAll<HTMLElement>('.ui-layout-theme-import-panel.unified-source').forEach(install)
    scan();const observer=new MutationObserver(scan);observer.observe(document.body,{childList:true,subtree:true});return()=>observer.disconnect()
  },[])
  return null
}
