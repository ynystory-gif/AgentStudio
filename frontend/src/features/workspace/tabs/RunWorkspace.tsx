import React from 'react'
import type { WorkspaceTab } from '../workspace.types'
export function RunWorkspace({activeTab,children}:{activeTab:WorkspaceTab;children:React.ReactNode}){
  return activeTab==='RUN'?<>{children}</>:null
}
