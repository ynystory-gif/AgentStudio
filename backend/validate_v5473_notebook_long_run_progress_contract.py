from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
NOTEBOOK = (ROOT / "frontend/src/components/notebook/NotebookEditor.tsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

checks = []
def check(name, condition):
    checks.append((name, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")

check('frontend version 5.473', "AGENTSTUDIO_FRONTEND_VERSION='5.473'" in APP)
check('backend version 5.473', 'version="5.473"' in MAIN)
check('health version 5.473', '"version": "5.473"' in ROUTES)
check('codex client version 5.473', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.473"' in CODEX)
check('build marker', 'NotebookLongRunProgressHeartbeat' in ROUTES)
check('execution start time tracked', 'executionStartedAtRef' in NOTEBOOK)
check('long-run delay exists', '}, 650)' in NOTEBOOK)
check('progress visibility state', 'executionProgressVisible' in NOTEBOOK)
check('elapsed heartbeat exists', 'executionHeartbeatAt' in NOTEBOOK and 'setInterval' in NOTEBOOK)
check('elapsed time formatter', 'formatNotebookExecutionElapsed' in NOTEBOOK)
check('progress UI rendered only for code cell', "cellType === 'code' && progressVisible" in NOTEBOOK)
check('indeterminate progress role', 'role="progressbar"' in NOTEBOOK and 'aria-valuetext' in NOTEBOOK)
check('execution status copy', 'Python 실행 결과를 기다리고 있습니다.' in NOTEBOOK)
check('progress cleanup on completion', 'delete executionStartedAtRef.current[index]' in NOTEBOOK)
check('progress timer cleanup', 'window.clearTimeout(progressTimer)' in NOTEBOOK)
check('existing stop control preserved', '실행 정지' in NOTEBOOK)
check('indeterminate animation css', '@keyframes notebook-execution-indeterminate' in CSS)
check('reduced-motion css', '@media (prefers-reduced-motion:reduce)' in CSS)
check('no fake percentage label', 'aria-valuenow' not in NOTEBOOK)
check('readme current feature', 'Notebook 장시간 실행 상태 Progress 표시' in README)

failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.473 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.473 Notebook long-run progress contract: ALL PASS ({len(checks)}/{len(checks)})')
