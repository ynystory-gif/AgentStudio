from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
blender=(ROOT/'frontend/src/features/agent-builder/components/BlenderAgentWorkflowCard.tsx').read_text(encoding='utf-8')
db_service=(ROOT/'frontend/src/features/database/services/databaseService.ts').read_text(encoding='utf-8')
assert 'BlenderAgentWorkflowCard' in app
assert '3D 제작 Agent · Blender MCP' in blender
assert 'finalizeDatabaseDesignPlan' in db_service
assert 'autoFinalizeDatabasePlanFromApprovedResource' in app
assert "approval_source:'APPROVED_DATABASE_RESOURCE_PLAN'" in app
assert '설계 검토 전에 승인한 DB Resource Plan을 재사용' in app
assert '사전 승인 반영' in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.557'" in app
print('v5.557 Blender separation + DB preapproval reuse: PASS')
