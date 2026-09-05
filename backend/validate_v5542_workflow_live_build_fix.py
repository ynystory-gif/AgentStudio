from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')

manual=app.index("const [requirementManualOverrides,setRequirementManualOverrides]")
gate=app.index("const hasExplicitBlenderCapability")
assert manual < gate, (manual, gate)

assert "workflow-live-route" in app
assert "hasExplicitBlenderCapability&&targetWorkflowPreview?.three_d_agent_plan?.type==='BLENDER_3D'" in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.542'" in app
assert 'version="5.542"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.542"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
print('v5.542 Workflow Live build ordering: PASS')
