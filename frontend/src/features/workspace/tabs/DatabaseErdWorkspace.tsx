import React from 'react'
import type { WorkspaceTab } from '../workspace.types'
export function DatabaseErdWorkspace({activeTab,children}:{activeTab:WorkspaceTab;children:React.ReactNode}){
  return activeTab==='DB_ERD'?<>{children}</>:null
}
