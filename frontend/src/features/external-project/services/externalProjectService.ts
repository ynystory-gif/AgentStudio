import { api } from '../../../api'
export const pickExternalProjectFolder=(initialPath:string)=>api('/system/pick-folder',{
  method:'POST',body:JSON.stringify({title:'분석할 기존 프로젝트 폴더 선택',initial_path:initialPath||''})
})
export const startExternalProjectAnalysis=(projectRoot:string)=>api('/projects/analyze-external',{
  method:'POST',
  body:JSON.stringify({
    project_root:projectRoot,
    request:'프로젝트 소스 구조, 기술 스택, 주요 파일, 실행 진입점, MCP/Agent 관련 소스만 분석해주세요. 모델은 실행하지 말고 소스에 명시된 모델명만 참고해주세요.'
  })
})
export const fetchExternalProjectJob=(jobId:string|number)=>api(`/jobs/${encodeURIComponent(String(jobId))}`)
export const registerExternalProjectAsAgent=(name:string,projectRoot:string)=>api('/projects/create-agent',{
  method:'POST',
  body:JSON.stringify({name,project_root:projectRoot,cache_path:'',temp_path:'',output_path:'',venv_path:'',models_path:''})
})
