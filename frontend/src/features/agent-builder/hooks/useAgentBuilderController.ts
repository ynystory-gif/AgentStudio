import { useRef, useState } from 'react'
type LegacyValue=any
type LegacyRecord=Record<string,any>

export function useAgentBuilderController(options:LegacyRecord={}){
  const [confirmedInterviewRequirements,setConfirmedInterviewRequirements]=useState<LegacyRecord>({})
  const [designProjectId,setDesignProjectId]=useState<LegacyValue|null>(null)
  const [designProjectSavedAt,setDesignProjectSavedAt]=useState('')
  const [designProjectVersion,setDesignProjectVersion]=useState(1)
  const [designFeatureRegistry,setDesignFeatureRegistry]=useState<LegacyValue[]>([])
  const [requirementRecommendations,setRequirementRecommendations]=useState<LegacyValue|null>(null)
  const [requirementRecommendationSettings,setRequirementRecommendationSettings]=useState(()=>options.initialRecommendationSettings||{})
  const [developmentStagePlan,setDevelopmentStagePlan]=useState<LegacyValue|null>(null)
  const [developmentStagePlanBusy,setDevelopmentStagePlanBusy]=useState(false)
  const [codeDocumentationEnabled,setCodeDocumentationEnabled]=useState(false)
  const [toolPromptSettings,setToolPromptSettings]=useState(()=>({...options.initialToolPromptSettings}))
  const [agentCodingStyle,setAgentCodingStyle]=useState(()=>options.initialCodingStyle||{})
  const [builderSummaryTab,setBuilderSummaryTab]=useState('REQUIREMENTS')
  const [designProjectSaving,setDesignProjectSaving]=useState(false)
  const [requirementDraftRestored,setRequirementDraftRestored]=useState(false)
  const [requirementDraftSavedAt,setRequirementDraftSavedAt]=useState('')
  const [requirementDraftCandidate,setRequirementDraftCandidate]=useState<LegacyValue|null>(null)
  const [requirementDraftDecisionPending,setRequirementDraftDecisionPending]=useState(false)
  const requirementDraftDecisionPendingRef=useRef(false)
  const projectAutoRestoreRootRef=useRef('')

  const resetRequirementDraftState=()=>{
    setRequirementDraftCandidate(null)
    setRequirementDraftDecisionPending(false)
    requirementDraftDecisionPendingRef.current=false
    setRequirementDraftRestored(false)
    setRequirementDraftSavedAt('')
  }

  return {
    confirmedInterviewRequirements,setConfirmedInterviewRequirements,
    designProjectId,setDesignProjectId,designProjectSavedAt,setDesignProjectSavedAt,
    designProjectVersion,setDesignProjectVersion,designFeatureRegistry,setDesignFeatureRegistry,
    requirementRecommendations,setRequirementRecommendations,
    requirementRecommendationSettings,setRequirementRecommendationSettings,
    developmentStagePlan,setDevelopmentStagePlan,developmentStagePlanBusy,setDevelopmentStagePlanBusy,
    codeDocumentationEnabled,setCodeDocumentationEnabled,
    toolPromptSettings,setToolPromptSettings,agentCodingStyle,setAgentCodingStyle,
    builderSummaryTab,setBuilderSummaryTab,designProjectSaving,setDesignProjectSaving,
    requirementDraftRestored,setRequirementDraftRestored,requirementDraftSavedAt,setRequirementDraftSavedAt,
    requirementDraftCandidate,setRequirementDraftCandidate,
    requirementDraftDecisionPending,setRequirementDraftDecisionPending,requirementDraftDecisionPendingRef,
    projectAutoRestoreRootRef,
    resetRequirementDraftState,
  }
}
