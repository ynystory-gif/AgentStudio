from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")

checks = {
    "version": "AGENTSTUDIO_FRONTEND_VERSION='5.403'" in APP and 'version="5.403"' in MAIN and '"version": "5.403"' in ROUTES,
    "spacer_rendered": 'className="code-file-actions-spacer"' in APP,
    "right_margin": '.code-file-actions-fixed{\n  margin-left:auto;' in CSS,
    "spacer_flex": '.code-file-actions-fixed .code-file-actions-spacer{' in CSS and 'flex:1 1 auto;' in CSS,
    "spacer_order": 'order:-1;' in CSS,
    "execution_priority": '.code-file-actions-fixed .powershell-editor-actions{order:0}' in CSS,
    "find_priority": '.code-file-actions-fixed .editor-find-toolbar-button{order:1}' in CSS,
    "debug_priority": '.code-file-actions-fixed .source-debug-actions{order:2}' in CSS,
    "bookmark_priority": '.code-file-actions-fixed .editor-bookmark-toolbar{order:3}' in CSS,
}
failed=[name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit(f"v5.403 contract FAIL: {failed}")
print(f"v5.403 code toolbar right alignment contract PASS {len(checks)}/{len(checks)}")
