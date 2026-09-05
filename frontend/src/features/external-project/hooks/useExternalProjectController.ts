import { useState } from 'react'
type LegacyValue=any

export function useExternalProjectController(){
  const [externalProjectPath,setExternalProjectPath]=useState('')
  const [externalProjectAnalysis,setExternalProjectAnalysis]=useState<LegacyValue|null>(null)
  const [externalProjectLoading,setExternalProjectLoading]=useState(false)
  const [externalProjectPickerLoading,setExternalProjectPickerLoading]=useState(false)
  const [externalProjectPickerMessage,setExternalProjectPickerMessage]=useState('')
  const [externalProjectProgress,setExternalProjectProgress]=useState(0)
  const [externalProjectStatus,setExternalProjectStatus]=useState('')
  const [externalProjectStep,setExternalProjectStep]=useState('')
  const [externalProjectMode,setExternalProjectMode]=useState(false)

  const beginExternalProjectAnalysis=()=>{
    setExternalProjectLoading(true)
    setExternalProjectProgress(0)
    setExternalProjectStatus('QUEUED')
    setExternalProjectStep('프로젝트 분석 작업을 준비하고 있습니다.')
    setExternalProjectAnalysis(null)
  }
  const failExternalProjectAnalysis=(message:string)=>{
    setExternalProjectStatus('FAILED')
    setExternalProjectStep(message)
    setExternalProjectLoading(false)
  }
  return {
    externalProjectPath,setExternalProjectPath,externalProjectAnalysis,setExternalProjectAnalysis,
    externalProjectLoading,setExternalProjectLoading,
    externalProjectPickerLoading,setExternalProjectPickerLoading,
    externalProjectPickerMessage,setExternalProjectPickerMessage,
    externalProjectProgress,setExternalProjectProgress,
    externalProjectStatus,setExternalProjectStatus,externalProjectStep,setExternalProjectStep,
    externalProjectMode,setExternalProjectMode,
    beginExternalProjectAnalysis,failExternalProjectAnalysis,
  }
}
