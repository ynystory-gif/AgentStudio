from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
for token in [
    'persistRequirementCheckpoint(',
    'latestDesignProjectSaveRef',
    'userActionSaveTimerRef',
    'agentDesignAutoSaveTabRef',
    'saveRequirementDraft(',
]:
    assert token not in app, token
assert "AGENTSTUDIO_FRONTEND_VERSION='5.567'" in app
assert 'Automatic project-folder checkpoint persistence was removed in v5.566.' in app
print('v5.567 autosave orphan reference cleanup: PASS')
