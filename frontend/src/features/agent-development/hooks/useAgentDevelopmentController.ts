import { useRef, useState } from 'react'
type LegacyValue=any
type LegacyRecord=Record<string,any>

export function useAgentDevelopmentController(){
  const [restoredBuildResume,setRestoredBuildResume]=useState<LegacyValue|null>(null)
  const [redevelopmentInfo,setRedevelopmentInfo]=useState<LegacyValue|null>(null)
  const [developmentProgress,setDevelopmentProgress]=useState<LegacyRecord>({
    active:false,percent:0,stage:'대기',detail:'',startedAt:null,elapsedSeconds:0,events:[]
  })
  const [developmentFinalStatus,setDevelopmentFinalStatus]=useState<LegacyValue|null>(null)
  const builderMessagesEndRef=useRef<LegacyValue|null>(null)
  const [agentBuildStage,setAgentBuildStage]=useState('REQUIREMENTS')
  const [agentBuildBusy,setAgentBuildBusy]=useState(false)
  const [projectCreateFlowBusy,setProjectCreateFlowBusy]=useState(false)
  const [agentBuildMessage,setAgentBuildMessage]=useState('')

  const resetDevelopmentState=()=>{
    setDevelopmentProgress({active:false,percent:0,stage:'대기',detail:'',startedAt:null,elapsedSeconds:0,events:[]})
    setDevelopmentFinalStatus(null)
    setRestoredBuildResume(null)
    setRedevelopmentInfo(null)
    setAgentBuildBusy(false)
    setProjectCreateFlowBusy(false)
    setAgentBuildMessage('')
  }

  const beginDevelopment=(stage='개발 준비',detail='Agent 개발을 준비하고 있습니다.')=>{
    setDevelopmentFinalStatus(null)
    setDevelopmentProgress({active:true,percent:1,stage,detail,startedAt:Date.now(),elapsedSeconds:0,events:[]})
  }

  return {
    restoredBuildResume,setRestoredBuildResume,redevelopmentInfo,setRedevelopmentInfo,
    developmentProgress,setDevelopmentProgress,developmentFinalStatus,setDevelopmentFinalStatus,
    builderMessagesEndRef,agentBuildStage,setAgentBuildStage,agentBuildBusy,setAgentBuildBusy,
    projectCreateFlowBusy,setProjectCreateFlowBusy,agentBuildMessage,setAgentBuildMessage,
    resetDevelopmentState,beginDevelopment,
  }
}
