import React from 'react'
import { WORKSPACE_TABS, type WorkspaceTab } from '../workspace.types'

interface Props{
  tab:WorkspaceTab
  leftCollapsed:boolean
  rightCollapsed:boolean
  pptExportBusy?:string
  onTabChange:(tab:WorkspaceTab)=>void
  onToggleLeft:()=>void
  onToggleRight:()=>void
  onExportPowerPoint:(scope:string,target:'AGENT'|'STUDIO')=>void
}

export function WorkspaceTabs({tab,leftCollapsed,rightCollapsed,pptExportBusy='',onTabChange,onToggleLeft,onToggleRight,onExportPowerPoint}:Props){
  const supportsPpt=WORKSPACE_TABS.find(item=>item.id===tab)?.supportsPptExport===true
  return <div className="workspace-tabs workspace-tabs-with-panel-controls">
    <button type="button" className={`workspace-panel-toggle workspace-panel-toggle-left ${leftCollapsed?'collapsed':''}`} onClick={onToggleLeft} title={leftCollapsed?'좌측 영역 열기':'좌측 영역 닫기'} aria-label={leftCollapsed?'좌측 영역 열기':'좌측 영역 닫기'} aria-pressed={!leftCollapsed}><span aria-hidden="true">{leftCollapsed?'▶':'◀'}</span></button>
    <div className="workspace-tab-list">
      {WORKSPACE_TABS.map(item=><button key={item.id} className={tab===item.id?'active':''} onClick={()=>onTabChange(item.id)}>{item.label}</button>)}
    </div>
    {supportsPpt&&<div className="workspace-ppt-export-group">
      <button type="button" className="workspace-ppt-export-button all" onClick={()=>onExportPowerPoint('ALL','AGENT')} disabled={!!pptExportBusy} title="현재 Agent 전체 PowerPoint 다운로드">{pptExportBusy==='AGENT:ALL'?'PPT 생성 중...':'▣ Agent PPT'}</button>
      <button type="button" className="workspace-ppt-export-button studio" onClick={()=>onExportPowerPoint('ALL','STUDIO')} disabled={!!pptExportBusy} title="AgentStudio 전체 PowerPoint 다운로드">{pptExportBusy==='STUDIO:ALL'?'PPT 생성 중...':'▣ Studio PPT'}</button>
    </div>}
    <button type="button" className={`workspace-panel-toggle workspace-panel-toggle-right ${rightCollapsed?'collapsed':''}`} onClick={onToggleRight} title={rightCollapsed?'우측 영역 열기':'우측 영역 닫기'} aria-label={rightCollapsed?'우측 영역 열기':'우측 영역 닫기'} aria-pressed={!rightCollapsed}><span aria-hidden="true">{rightCollapsed?'◀':'▶'}</span></button>
  </div>
}
