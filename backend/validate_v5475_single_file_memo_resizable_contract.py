from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
MEMO = (ROOT / 'frontend/src/components/memo/ProjectMemoPanel.tsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES_PATH = ROOT / 'backend/app/api/routes.py'
ROUTES = ROUTES_PATH.read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = []
def check(name, condition):
    checks.append((name, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")

check('frontend version 5.475', "AGENTSTUDIO_FRONTEND_VERSION='5.475'" in APP)
check('backend version 5.475', 'version="5.475"' in MAIN)
check('health version 5.475', '"version": "5.475"' in ROUTES)
check('codex client version 5.475', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.475"' in CODEX)
check('single memo helper exists', 'dedupeMemosByFile' in MEMO and 'memoFileKey' in MEMO)
check('frontend duplicate conflict guard', 'conflictingMemo' in MEMO and '파일별 메모는 1개만 저장할 수 있습니다.' in MEMO)
check('existing memo file locked', 'disabled={Boolean(selectedMemo)}' in MEMO)
check('active file memo auto load', 'memoForActiveFile' in MEMO and 'setSelectedId(existing.id)' in MEMO)
check('resizable memo workspace exists', 'project-memo-workspace' in MEMO and 'project-memo-splitter' in MEMO)
check('splitter pointer handlers exist', 'onSplitterPointerDown' in MEMO and 'onSplitterPointerMove' in MEMO and 'finishSplitterDrag' in MEMO)
check('split ratio persisted per project', 'agentstudio:project-memo-split:' in MEMO and 'localStorage.setItem' in MEMO)
check('memo editor gets larger default area', 'DEFAULT_LIST_PERCENT = 22' in MEMO and 'min-height:220px' in CSS)
check('splitter has row-resize cursor', '.project-memo-splitter' in CSS and 'cursor:row-resize' in CSS)
check('backend normalizer documents one memo rule', 'enforce exactly one memo per file path' in ROUTES)
check('backend dedupe uses casefold file key', 'key = file_path.casefold()' in ROUTES and 'by_file' in ROUTES)
check('build marker updated', 'SingleMemoPerFileResizableMemoSplit' in ROUTES)

# Execute only the backend normalizer function body in isolation and verify migration dedupe.
tree = ast.parse(ROUTES)
fn = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_normalize_project_memo_items'), None)
check('backend normalizer AST found', fn is not None)
if fn is not None:
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    scope = {}
    exec(compile(module, str(ROUTES_PATH), 'exec'), scope)
    normalize = scope['_normalize_project_memo_items']
    rows = normalize([
        {'id': 'old', 'filePath': 'Rag/Test.py', 'content': 'old', 'updatedAt': '2026-09-01T10:00:00Z'},
        {'id': 'new', 'filePath': 'rag\\test.py', 'content': 'new', 'updatedAt': '2026-09-01T11:00:00Z'},
        {'id': 'other', 'filePath': 'Rag/Other.py', 'content': 'other', 'updatedAt': '2026-09-01T09:00:00Z'},
    ])
    check('backend dedupe keeps one memo per file', len(rows) == 2)
    selected = next((row for row in rows if row['filePath'].casefold() == 'rag/test.py'), None)
    check('backend dedupe keeps newest duplicate', bool(selected and selected['id'] == 'new'))

failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.475 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.475 single-file memo/resizable split contract: ALL PASS ({len(checks)}/{len(checks)})')
