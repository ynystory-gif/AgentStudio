from pathlib import Path

root = Path(__file__).resolve().parents[1]
app = (root / "frontend/src/App.jsx").read_text(encoding="utf-8")
editor = (root / "frontend/src/components/notebook/NotebookEditor.tsx").read_text(encoding="utf-8")
styles = (root / "frontend/src/styles.css").read_text(encoding="utf-8")
routes = (root / "backend/app/api/routes.py").read_text(encoding="utf-8")
service = (root / "backend/app/services/python_execution_service.py").read_text(encoding="utf-8")
checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.396'" in app,
    "backend version": '"version": "5.396"' in routes,
    "debug cell button": "🐞 디버그 셀" in editor,
    "breakpoint storage": "NOTEBOOK_BREAKPOINT_STORAGE_PREFIX" in editor,
    "debug current line": "notebook-debug-current-line" in editor and "notebook-debug-current-line" in styles,
    "continue step controls": all(token in editor for token in ["step_over", "step_into", "step_out", "continue"]),
    "variables panel": "notebook-debug-variable-list" in editor,
    "debug console": "notebook-debug-console" in editor and "evaluate" in editor,
    "start endpoint": '@router.post("/python/debug/start")' in routes,
    "command endpoint": '@router.post("/python/debug/command")' in routes,
    "status endpoint": '@router.get("/python/debug/status")' in routes,
    "bdb worker": "_AgentStudioCellDebugger(bdb.Bdb)" in service,
    "persistent debug manager": "def debug_start(" in service and "def debug_command(" in service,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit(f"v5.396 contract failed: {failed}")
print(f"v5.396 contract PASS {len(checks)}/{len(checks)}")
