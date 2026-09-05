from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
nb=(ROOT/'frontend/src/features/notebook/components/NotebookEditor.tsx').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert 'requestIdleCallback' in nb
assert '}, 900)' in nb
assert 'sourceCommitIdleRef' in nb
for token in ['editorWorkspaceStorageKey','persistEditorWorkspace','restoreEditorWorkspace','await restoreEditorWorkspace(projectRoot)']:
    assert token in app, token
assert 'theanova.agentstudio.editor-workspace::' in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.564'" in app
print('v5.564 Notebook idle typing + editor workspace restore: PASS')
