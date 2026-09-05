from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
builder=(ROOT/'frontend/src/features/agent-builder/hooks/useAgentBuilderController.ts').read_text(encoding='utf-8')
for token in ['agentDesignAutoSaveTabRef','latestDesignProjectSaveRef','userActionSaveTimerRef','saveRequirementDraft(','requirementCheckpointSignatureRef']:
    assert token not in app, token
    assert token not in builder, token
assert 'autoSaveEnabled={true}' not in app
assert app.count('autoSaveEnabled={false}')>=2
assert '기능 삭제 전 자동 Snapshot' not in app
assert "자동 저장은 사용하지 않습니다. 필요한 내용은 먼저 '지금 저장'으로 저장해 주세요." in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.566'" in app
print('v5.566 remove Agent Design autosave: PASS')
