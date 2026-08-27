from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
PS1=(ROOT/'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8-sig')

checks={
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.372'" in APP,
    'backend version': 'version="5.372"' in MAIN,
    'health version': '"version": "5.372"' in ROUTES,
    'launcher version': '$FallbackAgentStudioVersion = "5.372"' in PS1,
    'editor content ref': 'const editorFileContentsRef=useRef({})' in APP,
    'immediate notebook mirror': 'Keep an immediate mirror for Ctrl+S' in APP and '[selected]:next' in APP,
    'shortcut uses selected ref': 'selectedEditorFileRef.current||selected' in APP,
    'shortcut no root gate': "&& root\n        && selected" not in APP,
    'save root uses editor root': 'editorFileRootRef.current?.[selectedPath]' in APP,
    'save root uses file tree': '||fileTreeRootRef.current' in APP,
    'save root uses workspace ref': '||workspaceRootRef.current' in APP,
    'ctrl s save log': '[저장 완료 · Ctrl+S]' in APP,
    'browser save prevented': 'e.preventDefault()' in APP and "String(e.key).toLowerCase()==='s'" in APP,
    'ctrl shift s no top root': "screen==='WORKSPACE'\n          && workspaceTab==='CODE'\n        ){\n          saveAllDirtyFiles()" in APP,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.372 Ctrl+S Notebook Save Root contract: '+', '.join(failed))
print('PASS v5.372 Ctrl+S Notebook Save Root contract')
