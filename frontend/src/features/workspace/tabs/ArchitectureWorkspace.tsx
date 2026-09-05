import React from 'react'
import type { WorkspaceTab } from '../workspace.types'
export function ArchitectureWorkspace({activeTab,children}:{activeTab:WorkspaceTab;children:React.ReactNode}){
  return activeTab==='ARCHITECTURE'?<>{children}</>:null
}
