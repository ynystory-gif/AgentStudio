import React from 'react'
import { WorkspaceTabs } from './components/WorkspaceTabs'
import { workspaceTabDefinition, type WorkspaceTab } from './workspace.types'

interface Props{
  tab:WorkspaceTab
  leftCollapsed:boolean
  rightCollapsed:boolean
  bottomCollapsed:boolean
  bottomResizing:boolean
  binaryPreview:boolean
  pptExportBusy?:string
  children:React.ReactNode
  onTabChange:(tab:WorkspaceTab)=>void
  onToggleLeft:()=>void
  onToggleRight:()=>void
  onExportPowerPoint:(scope:string,target:'AGENT'|'STUDIO')=>void
}

export function WorkspaceShell(props:Props){
  const def=workspaceTabDefinition(props.tab)
  const compactResult=Boolean(def?.compactResult)
  const className=[
    'workspace-main',`workspace-tab-${props.tab.toLowerCase()}`,
    compactResult?'compact-workspace result-only-workspace':props.tab==='CODE'&&!props.binaryPreview?'workspace-with-bottom-tools code-tools-workspace':'workspace-clean-design',
    props.bottomCollapsed?'workspace-bottom-collapsed':'',
    props.bottomResizing?'workspace-bottom-resizing':''
  ].filter(Boolean).join(' ')
  return <main className={className}>
    <WorkspaceTabs tab={props.tab} leftCollapsed={props.leftCollapsed} rightCollapsed={props.rightCollapsed} pptExportBusy={props.pptExportBusy} onTabChange={props.onTabChange} onToggleLeft={props.onToggleLeft} onToggleRight={props.onToggleRight} onExportPowerPoint={props.onExportPowerPoint}/>
    {props.children}
  </main>
}
