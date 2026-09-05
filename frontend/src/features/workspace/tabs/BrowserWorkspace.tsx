import React from 'react'
import type { WorkspaceTab } from '../workspace.types'
export function BrowserWorkspace({activeTab,children}:{activeTab:WorkspaceTab;children:React.ReactNode}){
  return activeTab==='BROWSER'?<>{children}</>:null
}
