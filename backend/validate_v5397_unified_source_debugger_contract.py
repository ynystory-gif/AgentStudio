from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NB=(ROOT/'frontend/src/components/notebook/NotebookEditor.tsx').read_text(encoding='utf-8')
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
SERVICE=(ROOT/'backend/app/services/source_debug_service.py').read_text(encoding='utf-8')
checks={
 'python3 kernel': 'isPythonNotebookKernel' in NB and "startsWith('python')" in NB,
 'notebook breakpoint toolbar': 'breakpoints.length > 0' in NB and '▶ 디버그 시작' in NB,
 'no wait hover': 'notebook-debug-cell-button:disabled{cursor:not-allowed' in CSS,
 'source breakpoint': 'TEXT_EDITOR_BREAKPOINT_STORAGE_PREFIX' in APP and 'editor-debug-breakpoint-glyph' in APP,
 'source debug toolbar': 'source-debug-actions' in APP and 'startSourceFileDebug' in APP,
 'source variables': 'source-debug-variable-list' in APP,
 'source console': 'sourceDebugExpression' in APP and "commandSourceFileDebug('evaluate'" in APP,
 'python source route': 'endswith((".py", ".pyw", ".ipynb"))' in ROUTES,
 'generic runner route': '/source/debug/run' in ROUTES and 'run_source_code' in ROUTES,
 'js ts adapters': '".js"' in SERVICE and '".jsx"' in SERVICE and '".ts"' in SERVICE and '".tsx"' in SERVICE,
 'shell adapters': '".ps1"' in SERVICE and '".cmd"' in SERVICE and '".sh"' in SERVICE,
 'compiled adapters': '".cpp"' in SERVICE and '".rs"' in SERVICE,
}
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('FAIL: '+', '.join(failed))
print(f'v5.397 unified source debugger contract PASS {len(checks)}/{len(checks)}')
