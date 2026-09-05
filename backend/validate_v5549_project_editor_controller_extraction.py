from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
project=(ROOT/'frontend/src/features/project/hooks/useProjectController.ts').read_text(encoding='utf-8')
editor=(ROOT/'frontend/src/features/editor/hooks/useEditorController.ts').read_text(encoding='utf-8')
service=(ROOT/'frontend/src/features/editor/services/editorFileService.ts').read_text(encoding='utf-8')
assert 'useProjectController()' in app
assert 'useEditorController()' in app
assert 'readEditorTextFile(workspaceRoot,requestedPath)' in app
assert 'writeEditorTextFile(fullPath' in app
for token in ['projectSearch','projectLoadProgress','beginProjectLoad','filterProjects']:
    assert token in project, token
for token in ['editorInstanceRef','editorFileRootRef','editorTextSearchQuery','editorTabsScrollRef','toggleBookmark','rememberSelection','rememberScroll']:
    assert token in editor, token
assert "AGENTSTUDIO_FRONTEND_VERSION='5.549'" in app
assert len(app.splitlines()) < 22076
print('v5.549 Project + Editor Controller extraction: PASS')
print('App.tsx:',len(app.splitlines()))
