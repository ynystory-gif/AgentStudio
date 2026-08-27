from pathlib import Path
import ast
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / 'backend/app/services/agent_workflow.py'
WORKFLOW = WORKFLOW_PATH.read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
PS1 = (ROOT / 'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.369'" in APP,
    'backend version': 'version="5.369"' in MAIN or "version='5.369'" in MAIN,
    'health version': '"version": "5.369"' in ROUTES,
    'launcher version': '$FallbackAgentStudioVersion = "5.369"' in PS1,
    'cleanup helper': 'def _cleanup_react_typescript_legacy_sources' in WORKFLOW,
    'legacy App.jsx cleanup': '"frontend/src/App.jsx"' in WORKFLOW,
    'legacy main.jsx cleanup': '"frontend/src/main.jsx"' in WORKFLOW,
    'legacy api.js cleanup': '"frontend/src/services/api.js"' in WORKFLOW,
    'real deletion': 'target.unlink(missing_ok=True)' in WORKFLOW,
    'verified deletion patch row': '"deleted": True' in WORKFLOW and 'delete_legacy_react_javascript_entry' in WORKFLOW,
    'cleanup before validation': 'react_ts_cleanup = _cleanup_react_typescript_legacy_sources(state)' in WORKFLOW,
    'canonical App.tsx': 'return "frontend/src/App.tsx"' in WORKFLOW,
    'cleanup diagnostics': '"react_typescript_legacy_cleanup": react_ts_cleanup' in WORKFLOW,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.369: ' + ', '.join(failed))

# Functional test the cleanup helper without importing LangGraph/runtime dependencies.
tree = ast.parse(WORKFLOW)
helper_node = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == '_cleanup_react_typescript_legacy_sources'
)
module = ast.Module(body=[helper_node], type_ignores=[])
ast.fix_missing_locations(module)
ns = {
    'Path': Path,
    'AgentState': dict,
    '_requirement_contracts': lambda state: {'react_typescript': bool(state.get('typescript'))},
}
exec(compile(module, str(WORKFLOW_PATH), 'exec'), ns)
cleanup = ns['_cleanup_react_typescript_legacy_sources']

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    legacy = [
        root / 'frontend/src/App.jsx',
        root / 'frontend/src/main.jsx',
        root / 'frontend/src/services/api.js',
    ]
    for path in legacy:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('// legacy\n', encoding='utf-8')
    result = cleanup({'project_root': str(root), 'typescript': True})
    if not result.get('ok') or len(result.get('removed') or []) != 3:
        raise SystemExit(f'FAIL v5.369 functional cleanup result: {result!r}')
    if any(path.exists() for path in legacy):
        raise SystemExit('FAIL v5.369 functional cleanup: legacy file still exists')
    if not all(row.get('deleted') and row.get('verified') for row in result.get('patch_rows') or []):
        raise SystemExit('FAIL v5.369 functional cleanup: patch row not verified/deleted')

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    path = root / 'frontend/src/App.jsx'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('// javascript project\n', encoding='utf-8')
    result = cleanup({'project_root': str(root), 'typescript': False})
    if not path.exists() or result.get('removed'):
        raise SystemExit('FAIL v5.369 non-TypeScript project must preserve App.jsx')

print('PASS v5.369 React TypeScript Legacy Source Cleanup contract')
