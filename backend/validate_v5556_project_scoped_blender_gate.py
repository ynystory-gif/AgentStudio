from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert 'const hasExplicitBlenderRequirement=' in app
assert 'const resolveRestoredAgentSpecialization=' in app
assert "specializationSource==='USER'" in app
assert "source:'USER'" in app
assert "snapshot?.workflow_preview?.three_d_agent_plan?.type||'GENERAL'" not in app
assert "restoredPreview?.three_d_agent_plan?.type==='BLENDER_3D'||restoredRuntimeState?.three_d_agent_plan?.type==='BLENDER_3D'" not in app
assert "delete restoredPreview.three_d_agent_plan" in app
assert "{hasExplicitBlenderCapability&&targetWorkflowPreview?.three_d_agent_plan?.type==='BLENDER_3D'&&" in app
assert "3D / Blender 설계 제외" not in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.556'" in app
print('v5.556 project-scoped Blender gate: PASS')
