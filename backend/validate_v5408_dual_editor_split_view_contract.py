from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')

checks={
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.408'" in APP and 'version="5.408"' in MAIN and '"version": "5.408"' in ROUTES,
    'build badge': 'DualEditorSplitView' in ROUTES,
    'split state': 'const [editorSplit,setEditorSplit]=useState(null)' in APP,
    'right menu': '오른쪽으로 화면 열기' in APP and "openEditorInSplit(editorTabMenu.path,'RIGHT')" in APP,
    'left menu': '왼쪽으로 화면 열기' in APP and "openEditorInSplit(editorTabMenu.path,'LEFT')" in APP,
    'split renderer': 'renderSecondaryEditorContent' in APP,
    'notebook split': 'secondaryNotebookEditorControllerRef' in APP and 'controllerRef={secondaryNotebookEditorControllerRef}' in APP,
    'monaco split': 'secondaryEditorInstanceRef' in APP and 'split-monaco-editor' in APP,
    'active pane save': 'activeEditorPathRef.current||selectedEditorFileRef.current||selected' in APP and 'saveFile(shortcutPath)' in APP,
    'drag resize': 'beginEditorSplitResize' in APP and 'code-editor-vertical-splitter' in APP,
    'persist ratio': 'agentstudio.editorSplit.ratio' in APP,
    'direction swap': "side:prev.side==='LEFT'?'RIGHT':'LEFT'" in APP,
    'close split': 'closeEditorSplit' in APP and '분할 화면 닫기' in APP,
    'layout css': '.code-editor-document-layout' in CSS and '.code-editor-secondary-pane' in CSS,
    'left order css': '.code-editor-document-layout.split-left .code-editor-secondary-pane{order:1}' in CSS,
    'right order css': '.code-editor-document-layout.split-right .code-editor-secondary-pane{order:3}' in CSS,
    'resizer css': '.code-editor-vertical-splitter' in CSS and 'cursor:col-resize' in CSS,
    'no literal helper newlines': 'renderSecondaryEditorContent=(relativePath)=>{\\n' not in APP,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.408 contract FAIL: '+', '.join(failed))
print(f'v5.408 Dual Editor Split View contract PASS {len(checks)}/{len(checks)}')
