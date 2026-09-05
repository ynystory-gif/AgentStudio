import { useEffect } from 'react'
import { api } from '../../api'

const fmtSeconds=(value: LegacyValue)=>{
  const sec=Math.max(0,Number(value||0))
  if(!Number.isFinite(sec))return '-'
  if(sec<60)return `${Math.round(sec)}초`
  const min=Math.floor(sec/60)
  const rest=Math.round(sec%60)
  return rest?`${min}분 ${rest}초`:`${min}분`
}

export function LearningProblemProgressEnhancer(){
  useEffect(()=>{
    let stopped=false
    let busy=false
    const findProblemBlock=()=>[...document.querySelectorAll('.llm-job-progress')].find((el: LegacyValue)=>String(el.textContent||'').includes('문제 수집'))
    const getJobId=(root: LegacyValue)=>{
      const text=String(root?.textContent||'')
      const match=text.match(/작업 ID:\s*([a-f0-9]{16,})/i)
      return match?.[1]||''
    }
    const render=(root: LegacyValue,job: LegacyValue)=>{
      const detail=job?.generation||{}
      if(!detail||!Object.keys(detail).length)return
      let panel=root.querySelector('.llm-problem-live-detail')
      if(!panel){
        panel=document.createElement('div')
        panel.className='llm-problem-live-detail'
        panel.style.cssText='display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:9px;padding:9px 10px;border:1px solid #303846;border-radius:7px;background:#111821;font-size:13px;'
        root.appendChild(panel)
      }
      const items=[
        ['Teacher',`${detail.provider||'-'}${detail.model?` · ${detail.model}`:''}`],
        ['문제',`${detail.generated_count||0} / ${detail.target_count||job.target_per_topic||'-'}`],
        ['Batch',`${detail.completed_batches||0} / ${detail.total_batches||'-'}`],
        ['LLM 호출',`${detail.llm_calls||0}회`],
        ['예상 남은 시간',detail.eta_seconds===null||detail.eta_seconds===undefined?'-':fmtSeconds(detail.eta_seconds)],
      ]
      panel.innerHTML=items.map(([label,value]: LegacyValue)=>`<div style="min-width:0"><span style="display:block;color:#8997aa;margin-bottom:3px">${label}</span><b style="display:block;color:#e7edf5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${String(value)}</b></div>`).join('')
      panel.dataset.stage=String(detail.stage||'')
    }
    const tick=async()=>{
      if(stopped||busy)return
      const root=findProblemBlock()
      if(!root)return
      const jobId=getJobId(root)
      if(!jobId)return
      busy=true
      try{
        const job=await api(`/learning/problems/collect-job/${jobId}`)
        if(!stopped)render(root,job)
      }catch{}finally{busy=false}
    }
    tick()
    const timer=window.setInterval(tick,1000)
    return()=>{stopped=true;window.clearInterval(timer)}
  },[])
  return null
}
