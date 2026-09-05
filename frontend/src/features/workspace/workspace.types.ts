export type WorkspaceTab =
  | 'DESIGN' | 'WORKFLOW' | 'CODE' | 'RUN' | 'REPORT'
  | 'ARCHITECTURE' | 'DB_ERD' | 'SCHEDULER' | 'LLM' | 'BROWSER'

export type WorkspacePanelSide = 'left' | 'right'

export interface WorkspaceTabDefinition {
  id: WorkspaceTab
  label: string
  compactResult?: boolean
  supportsPptExport?: boolean
}

export const WORKSPACE_TABS: WorkspaceTabDefinition[] = [
  {id:'DESIGN',label:'에이전트 설계'},
  {id:'WORKFLOW',label:'워크플로우',supportsPptExport:true},
  {id:'RUN',label:'실행 결과',compactResult:true,supportsPptExport:true},
  {id:'CODE',label:'코드 편집'},
  {id:'REPORT',label:'분석 리포트',compactResult:true,supportsPptExport:true},
  {id:'ARCHITECTURE',label:'아키텍처',compactResult:true,supportsPptExport:true},
  {id:'DB_ERD',label:'DB ERD',compactResult:true,supportsPptExport:true},
  {id:'SCHEDULER',label:'스케줄러',compactResult:true},
  {id:'LLM',label:'LLM 리스트',compactResult:true},
  {id:'BROWSER',label:'웹브라우저',compactResult:true},
]

export const workspaceTabDefinition=(tab:WorkspaceTab):WorkspaceTabDefinition=>{
  const match=WORKSPACE_TABS.find(item=>item.id===tab)
  if(match) return match
  return {
    id:'DESIGN',
    label:'에이전트 설계',
    compactResult:false,
    supportsPptExport:false,
  }
}
