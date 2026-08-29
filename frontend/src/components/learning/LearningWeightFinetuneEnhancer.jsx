import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../../api'

const REOPEN_KEY='theanova.agentstudio.learning.reopen'

const stageLabel=stage=>({
  queued:'대기',capability:'학습 조건 확인',runtime:'전용 실행환경 준비',train:'QLoRA 가중치 학습',
  merge:'Base + Adapter Merge',ollama_import:'Ollama Q4_K_M 양자화',smoke_test:'실행 검증',
  promote:'theanova-learn:latest 교체',database:'DB 학습 매핑',done:'완료',failed:'실패',
}[stage]||stage||'-')

export function LearningWeightFinetuneEnhancer(){
  const [toolbar,setToolbar]=useState(null)
  const [panelHost,setPanelHost]=useState(null)
  const [capability,setCapability]=useState(null)
  const [job,setJob]=useState(null)
  const [error,setError]=useState('')

  useEffect(()=>{
    let disposed=false
    const locate=()=>{
      if(disposed)return
      const nextToolbar=document.querySelector('.llm-learning-toolbar')
      setToolbar(nextToolbar instanceof HTMLElement?nextToolbar:null)
      const modelBlock=document.querySelector('.llm-learning-model-upgrade')
      if(modelBlock instanceof HTMLElement){
        let host=document.querySelector('[data-weight-finetune-progress-host]')
        if(!(host instanceof HTMLElement)){
          host=document.createElement('div')
          host.dataset.weightFinetuneProgressHost='true'
          modelBlock.insertAdjacentElement('afterend',host)
        }
        setPanelHost(host)
      }else setPanelHost(null)
    }
    locate()
    const timer=window.setInterval(locate,500)
    return()=>{disposed=true;window.clearInterval(timer)}
  },[])

  useEffect(()=>{
    if(!toolbar)return
    let cancelled=false
    api('/learning/weight-finetune/capability')
      .then(value=>{if(!cancelled)setCapability(value)})
      .catch(e=>{if(!cancelled)setError(String(e))})
    return()=>{cancelled=true}
  },[toolbar])

  /*
   * Once a real merged weight model is active, the old curriculum/apply buttons must
   * not overwrite the same theanova-learn:latest alias. New validated data is folded
   * into the weights by running this QLoRA button again.
   */
  useEffect(()=>{
    const active=Boolean(capability?.weight_model_active)
    const guard=()=>{
      document.querySelectorAll('.llm-learning-page button').forEach(button=>{
        if(!(button instanceof HTMLButtonElement)||button.classList.contains('weight-finetune-button'))return
        const text=String(button.textContent||'').trim()
        const legacy=text.includes('모두 학습 적용')||text==='학습 적용'||text.includes('전체 재학습')
        if(!legacy)return
        if(active){
          button.dataset.weightModelProtected='true'
          button.disabled=true
          button.title='독립 가중치 모델이 사용 중입니다. 새 Dataset은 [가중치 파인튜닝]으로 다시 학습해야 합니다.'
        }else if(button.dataset.weightModelProtected==='true'){
          delete button.dataset.weightModelProtected
          button.disabled=false
          button.removeAttribute('title')
        }
      })
    }
    guard()
    const timer=window.setInterval(guard,600)
    return()=>window.clearInterval(timer)
  },[capability?.weight_model_active])

  useEffect(()=>{
    if(!job?.id||job.status!=='running')return
    const timer=window.setInterval(async()=>{
      try{
        const next=await api(`/learning/weight-finetune/jobs/${job.id}`)
        setJob(next)
        if(next?.status==='completed'){
          window.clearInterval(timer)
          try{setCapability(await api('/learning/weight-finetune/capability'))}catch{}
          sessionStorage.setItem(REOPEN_KEY,'1')
        }else if(next?.status==='failed'){
          window.clearInterval(timer)
          setError(next?.error||next?.message||'가중치 파인튜닝에 실패했습니다.')
        }
      }catch(e){
        window.clearInterval(timer)
        setError(String(e))
      }
    },1200)
    return()=>window.clearInterval(timer)
  },[job?.id,job?.status])

  const start=async()=>{
    if(!capability?.ready)return
    const datasets=Number(capability?.validated_dataset_count||0)
    const problems=Number(capability?.validated_problem_count||0)
    const rerun=Boolean(capability?.weight_model_active)
    const ok=window.confirm(
      `${rerun?'현재 독립 모델을 새 검증 데이터까지 포함해 다시 학습합니다.':'독립 가중치 모델을 생성합니다.'}\n\n`+
      `검증 완료 Dataset ${datasets}개 / 문제 ${problems}개로 Qwen3.5-4B의 실제 가중치를 QLoRA 학습합니다.\n`+
      `학습 후 Adapter를 Base에 Merge하고 Q4_K_M으로 양자화하여 theanova-learn:latest를 독립 모델로 교체합니다.\n\n`+
      `GPU를 장시간 사용할 수 있으며 최초 실행은 Hugging Face 모델/학습 패키지 다운로드가 필요합니다. 계속할까요?`
    )
    if(!ok)return
    setError('')
    try{setJob(await api('/learning/weight-finetune/jobs',{method:'POST'}))}
    catch(e){setError(String(e))}
  }

  if(!toolbar)return null
  const running=job?.status==='running'
  const completed=job?.status==='completed'
  const progress=Math.max(0,Math.min(100,Number(job?.progress||0)))
  const reasons=Array.isArray(capability?.reasons)?capability.reasons:[]
  const ready=Boolean(capability?.ready)
  const weightActive=Boolean(capability?.weight_model_active)
  const buttonTitle=running
    ? `${stageLabel(job?.stage)} ${progress}%`
    : ready
      ? '검증된 Dataset으로 Qwen3.5-4B QLoRA 가중치를 학습하고 독립 theanova-learn:latest를 만듭니다.'
      : reasons.join(' / ')||'파인튜닝 준비 상태 확인 중...'

  const button=createPortal(
    <button type="button" className="primary weight-finetune-button" disabled={running||!ready} onClick={start} title={buttonTitle}>
      {running?`🧠 파인튜닝 ${progress}%`:weightActive?'🧠 독립 모델 재학습':'🧠 독립 모델 파인튜닝'}
    </button>,toolbar)

  const panel=panelHost?createPortal(
    <div className={`weight-finetune-panel ${running?'running':''} ${(completed||weightActive)?'completed':''} ${error?'failed':''}`}>
      <div className="weight-finetune-head">
        <div><b>독립 가중치 모델</b><strong>qwen3.5:4b → QLoRA/Merge → theanova-learn:latest</strong></div>
        <span className={(ready||weightActive)?'ready':'not-ready'}>{weightActive?'독립 가중치 모델 사용 중':ready?'파인튜닝 준비됨':'준비 확인 필요'}</span>
      </div>
      <div className="weight-finetune-capability">
        <span>GPU <b>{capability?.gpu_name||'-'} {capability?.gpu_memory_gb?`${capability.gpu_memory_gb}GB`:''}</b></span>
        <span>검증 Dataset <b>{capability?.validated_dataset_count??'-'}개</b></span>
        <span>검증 문제 <b>{capability?.validated_problem_count??'-'}개</b></span>
        <span>디스크 여유 <b>{capability?.disk_free_gb??'-'}GB</b></span>
      </div>
      {weightActive&&<div className="weight-finetune-success">현재 <b>theanova-learn:latest</b>는 실제 QLoRA 가중치를 Merge한 독립 모델입니다. 새 Dataset을 반영할 때는 이 버튼으로 다시 파인튜닝합니다.</div>}
      {!ready&&reasons.length>0&&<div className="weight-finetune-warning">{reasons.join(' · ')}</div>}
      {(job||error)&&<>
        <div className="weight-finetune-progress-head"><b>{error||job?.message||'진행 중...'}</b><span>{progress}%</span></div>
        <div className="weight-finetune-track"><i style={{width:`${progress}%`}}/></div>
        <small>현재 단계: {stageLabel(job?.stage)}{job?.id?` · Job ID: ${job.id}`:''}</small>
        {Array.isArray(job?.logs)&&job.logs.length>0&&<details className="weight-finetune-logs" open={Boolean(error)}><summary>상세 학습 로그</summary><pre>{job.logs.slice(-12).join('\n')}</pre></details>}
      </>}
      {completed&&!weightActive&&<div className="weight-finetune-success">실제 가중치가 Merge된 독립 모델이 <b>theanova-learn:latest</b>로 적용되었습니다.</div>}
    </div>,panelHost):null

  return <>{button}{panel}</>
}
