import React from 'react'
import type { WorkspaceTab } from '../workspace.types'
export function ReportWorkspace({activeTab,children}:{activeTab:WorkspaceTab;children:React.ReactNode}){
  return activeTab==='REPORT'?<>{children}</>:null
}
