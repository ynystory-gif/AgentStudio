import { api } from '../api'

export const loadMediaWorkflowCatalog=async(phase='')=>{
  const suffix=phase?`?phase=${encodeURIComponent(phase)}`:''
  return api(`/media/workflow/catalog${suffix}`)
}

export const loadMediaWorkflowContracts=()=>api('/media/workflow/contracts')

export const validateMediaPortConnection=(outputType,inputType)=>api('/media/workflow/validate-port',{
  method:'POST',
  body:JSON.stringify({output_type:outputType,input_type:inputType})
})

export const normalizeMediaWorkflow=(workflow)=>api('/media/workflow/normalize',{
  method:'POST',
  body:JSON.stringify({workflow})
})

export const validateMediaWorkflow=(workflow)=>api('/media/workflow/validate',{
  method:'POST',
  body:JSON.stringify({workflow})
})
