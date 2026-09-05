import React from 'react'
import type { WorkspaceTab } from '../workspace.types'
export function LlmWorkspace({activeTab,children}:{activeTab:WorkspaceTab;children:React.ReactNode}){
  return activeTab==='LLM'?<>{children}</>:null
}
