from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
MEMO = (ROOT/'frontend/src/components/memo/ProjectMemoPanel.tsx').read_text(encoding='utf-8')
CSS = (ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN = (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT/'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks=[]
def check(name, condition):
    checks.append((name, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")

check('frontend version 5.474', "AGENTSTUDIO_FRONTEND_VERSION='5.474'" in APP)
check('backend version 5.474', 'version="5.474"' in MAIN)
check('health version 5.474', '"version": "5.474"' in ROUTES)
check('codex client version 5.474', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.474"' in CODEX)
check('memo panel imported', "ProjectMemoPanel" in APP and "components/memo/ProjectMemoPanel" in APP)
check('memo tab to right of codex', ">Codex</button>\n          <button" in APP and ">메모</button>" in APP)
check('memo tab route', "codeRightPanelTab==='MEMO'" in APP)
check('memo panel receives project root', 'projectRoot={resolveWorkspaceRoot()}' in APP)
check('memo panel receives active file', "activeFile={selected||''}" in APP)
check('memo panel receives project files', 'projectFiles={files}' in APP)
check('project memo backend api load', '/project-memos?root=' in MEMO and 'loadMemos(projectRoot)' in MEMO)
check('project memo backend api save', "api('/project-memos'" in MEMO and 'persistMemos(projectRoot, next)' in MEMO)
check('project memo file store', '.agentstudio' in ROUTES and 'file_memos.json' in ROUTES)
check('project memo endpoints', '@router.get("/project-memos")' in ROUTES and '@router.post("/project-memos")' in ROUTES)
check('memo stores file path', 'filePath' in MEMO and 'draftFile' in MEMO)
check('memo list', 'project-memo-list' in MEMO and 'visibleMemos.map' in MEMO)
check('memo select loads content', 'loadMemo' in MEMO and 'setDraftContent(memo.content)' in MEMO)
check('memo save', 'saveMemo' in MEMO and 'persistMemos(projectRoot, next)' in MEMO)
check('memo delete', 'deleteMemo' in MEMO and 'window.confirm' in MEMO)
check('current-file filter', "filterMode === 'CURRENT'" in MEMO)
check('memo keyboard save', "event.key.toLowerCase() === 's'" in MEMO)
check('five right tabs layout', '.code-right-panel-tabs.code-five-tabs' in CSS)
check('memo UI styles', '.project-memo-panel' in CSS and '.project-memo-editor' in CSS)

failed=[name for name,ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.474 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.474 Project/file memo contract: ALL PASS ({len(checks)}/{len(checks)})')
