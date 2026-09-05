import React from 'react'
import type { WorkspaceTab } from '../workspace.types'
export function CodeWorkspace({activeTab,children}:{activeTab:WorkspaceTab;children:React.ReactNode}){
  return activeTab==='CODE'?<>{children}</>:null
}
