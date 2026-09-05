import React from 'react'
import type { WorkspaceTab } from '../workspace.types'
export function WorkflowWorkspace({activeTab,children}:{activeTab:WorkspaceTab;children:React.ReactNode}){
  return activeTab==='WORKFLOW'?<>{children}</>:null
}
