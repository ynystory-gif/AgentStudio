import { useEffect, useMemo, useState } from 'react'
import { fetchWorkflowDefinition, fetchWorkflowProviderStatus } from '../services/workflowService'
type LegacyValue=any
type LegacyRecord=Record<string,any>
export function useWorkflowController(){
  const [workflowReq,setWorkflowReq]=useState('')
  const [workflow,setWorkflow]=useState<LegacyValue|null>(null)
  const [workflowDefinition,setWorkflowDefinition]=useState<LegacyValue|null>(null)
  const [workflowView,setWorkflowView]=useState('STUDIO')
  const [targetWorkflowPreview,setTargetWorkflowPreview]=useState<LegacyValue|null>(null)
  const [previousTargetWorkflowPreview,setPreviousTargetWorkflowPreview]=useState<LegacyValue|null>(null)
  const [targetWorkflowLoading,setTargetWorkflowLoading]=useState(false)
  const [workflowProgress,setWorkflowProgress]=useState<LegacyRecord>({active:false,percent:0,stage:'대기',detail:'',startedAt:null})
  const [workflowProgressClock,setWorkflowProgressClock]=useState(Date.now())
  const [targetWorkflowError,setTargetWorkflowError]=useState('')
  const [workflowRecoveryInfo,setWorkflowRecoveryInfo]=useState<LegacyValue|null>(null)
  const [workflowProviderDiagnostic,setWorkflowProviderDiagnostic]=useState<LegacyValue|null>(null)
  const [workflowRecoveryBusy,setWorkflowRecoveryBusy]=useState('')
  const [targetWorkflowQuality,setTargetWorkflowQuality]=useState<LegacyValue|null>(null)

  useEffect(()=>{
    if(!workflowProgress?.active)return
    setWorkflowProgressClock(Date.now())
    const timer=window.setInterval(()=>setWorkflowProgressClock(Date.now()),1000)
    return()=>window.clearInterval(timer)
  },[workflowProgress?.active,workflowProgress?.startedAt])

  const workflowElapsedSeconds=Math.max(0,Math.floor((workflowProgressClock-Number(workflowProgress?.startedAt||workflowProgressClock))/1000))
  const workflowElapsedLabel=`${String(Math.floor(workflowElapsedSeconds/60)).padStart(2,'0')}:${String(workflowElapsedSeconds%60).padStart(2,'0')}`
  const workflowLiveStages=useMemo(()=>[
    {id:'requirements',label:'요구사항 분석',threshold:5,icon:'✓'},
    {id:'design',label:'AI 설계 요청',threshold:18,icon:'◆'},
    {id:'waiting',label:'LLM 응답 대기',threshold:45,icon:'●'},
    {id:'validation',label:'Workflow 검증',threshold:90,icon:'◇'},
    {id:'complete',label:'완료',threshold:100,icon:'✓'},
  ],[])
  const workflowActiveStageIndex=(()=>{const p=Number(workflowProgress?.percent||0);if(p>=100)return 4;if(p>=90)return 3;if(p>=45)return 2;if(p>=18)return 1;return 0})()

  const loadWorkflowDefinition=async()=>{
    try{const result=await fetchWorkflowDefinition();setWorkflowDefinition(result);return result}
    catch(error){setWorkflowDefinition({ok:false,error:String(error)});return null}
  }
  const inspectWorkflowProviderStatus=async()=>{
    setWorkflowRecoveryBusy('PROVIDER')
    try{const result=await fetchWorkflowProviderStatus();setWorkflowProviderDiagnostic(result||{});return result}
    catch(error){setWorkflowProviderDiagnostic({ok:false,error:String(error)});return null}
    finally{setWorkflowRecoveryBusy('')}
  }
  const beginWorkflowProgress=(stage:string,detail:string,percent=5)=>setWorkflowProgress({active:true,percent,stage,detail,startedAt:Date.now()})
  const finishWorkflowProgress=(detail='대상 Agent Workflow와 요구사항 반영 검사가 완료되었습니다.')=>setWorkflowProgress(prev=>({...prev,active:true,percent:100,stage:'Workflow 설계 완료',detail}))
  const failWorkflowProgress=(error:unknown)=>setWorkflowProgress(prev=>({...prev,active:false,percent:0,stage:'Workflow 설계 실패',detail:String(error)}))

  return {workflowReq,setWorkflowReq,workflow,setWorkflow,workflowDefinition,setWorkflowDefinition,workflowView,setWorkflowView,targetWorkflowPreview,setTargetWorkflowPreview,previousTargetWorkflowPreview,setPreviousTargetWorkflowPreview,targetWorkflowLoading,setTargetWorkflowLoading,workflowProgress,setWorkflowProgress,workflowProgressClock,setWorkflowProgressClock,workflowElapsedSeconds,workflowElapsedLabel,workflowLiveStages,workflowActiveStageIndex,targetWorkflowError,setTargetWorkflowError,workflowRecoveryInfo,setWorkflowRecoveryInfo,workflowProviderDiagnostic,setWorkflowProviderDiagnostic,workflowRecoveryBusy,setWorkflowRecoveryBusy,targetWorkflowQuality,setTargetWorkflowQuality,loadWorkflowDefinition,inspectWorkflowProviderStatus,beginWorkflowProgress,finishWorkflowProgress,failWorkflowProgress}
}
