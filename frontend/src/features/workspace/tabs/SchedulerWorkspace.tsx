import React from 'react'
import type { WorkspaceTab } from '../workspace.types'
export function SchedulerWorkspace({activeTab,children}:{activeTab:WorkspaceTab;children:React.ReactNode}){
  return activeTab==='SCHEDULER'?<>{children}</>:null
}
