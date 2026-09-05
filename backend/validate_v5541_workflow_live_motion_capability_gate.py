from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')

for token in [
    'workflowProgressClock',
    'workflowElapsedLabel',
    'workflowLiveStages',
    'workflowActiveStageIndex',
    'hasExplicitBlenderCapability',
    'workflow-live-route',
    'workflow-live-current',
    'workflow-live-loop',
    'workflow-progress-spark',
    '3D / Blender 설계 제외',
]:
    assert token in app, token

assert "hasExplicitBlenderCapability&&targetWorkflowPreview?.three_d_agent_plan?.type==='BLENDER_3D'" in app
for token in [
    '@keyframes workflow-flow-line',
    '@keyframes workflow-node-breathe',
    '@keyframes workflow-bars',
    '@keyframes workflow-loop-spin',
    'prefers-reduced-motion',
]:
    assert token in css, token

assert "AGENTSTUDIO_FRONTEND_VERSION='5.541'" in app
assert 'version="5.541"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.541"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
print('v5.541 workflow live motion / capability gate: PASS')
