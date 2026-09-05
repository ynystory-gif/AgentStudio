import React from 'react'

type LegacyValue=any
type Props={plan:LegacyValue;readiness:LegacyValue;readinessBusy:boolean;onRefresh:()=>void}

export function BlenderAgentWorkflowCard({plan,readiness,readinessBusy,onRefresh}:Props){
  if(!plan||plan?.type!=='BLENDER_3D') return null
  return <div className="workflow-3d-agent-card">
    <div className="workflow-3d-agent-head">
      <div><span>◈</span><div><strong>3D 제작 Agent · Blender MCP</strong><small>MCP Tool 호출만이 아니라 Scene 상태와 실제 화면 품질까지 검증하는 제작 Workflow입니다.</small></div></div>
      <em>BLENDER 3D</em>
    </div>
    <div className="workflow-3d-pipeline">
      {['SceneSpec','Validator','LangGraph State','Blender MCP','Viewport QA','Repair','Render / Export'].map((item,index)=><React.Fragment key={item}><span>{item}</span>{index<6&&<b>→</b>}</React.Fragment>)}
    </div>
    <div className="workflow-3d-grid">
      <div><small>SceneSpec</small><strong>{(plan.scene_schema_fields||[]).length} fields</strong><p>{(plan.scene_schema_fields||[]).slice(0,6).join(' · ')}</p></div>
      <div><small>Scene State</small><strong>{(plan.scene_state_fields||[]).length} fields</strong><p>{(plan.scene_state_fields||[]).slice(0,6).join(' · ')}</p></div>
      <div><small>검증 계층</small><strong>{(plan.validation_layers||[]).length} layers</strong><p>{(plan.validation_layers||[]).slice(0,6).join(' · ')}</p></div>
    </div>
    <div className="workflow-3d-editor-contract">
      <b>Agent Editor 증분 수정 계약</b>
      <span>{(plan.editor_contract?.pipeline||[]).join(' → ')}</span>
      <small>보존: {(plan.editor_contract?.preserve||[]).join(' · ')}</small>
    </div>
    <div className={`workflow-3d-readiness ${readiness?.ready?'ready':'pending'}`}>
      <div><b>{readiness?.ready?'✓ Blender MCP Registry 준비됨':'○ Blender MCP Registry 연결 필요'}</b><small>{readinessBusy?'상태 확인 중...':(readiness?.message||'설계는 계속할 수 있지만 실제 3D 실행 전 Blender MCP 연결이 필요합니다.')}</small></div>
      <button type="button" onClick={onRefresh} disabled={readinessBusy}>상태 확인</button>
    </div>
  </div>
}
