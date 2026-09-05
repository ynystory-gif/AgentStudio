import React from 'react'
import type { WorkspaceTab } from '../workspace.types'
export function DesignWorkspace({activeTab,children}:{activeTab:WorkspaceTab;children:React.ReactNode}){
  return activeTab==='DESIGN'?<>{children}</>:null
}
