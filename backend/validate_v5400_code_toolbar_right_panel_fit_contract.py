from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/"frontend/src/App.jsx").read_text(encoding="utf-8")
CSS=(ROOT/"frontend/src/styles.css").read_text(encoding="utf-8")
MAIN=(ROOT/"backend/app/main.py").read_text(encoding="utf-8")
ROUTES=(ROOT/"backend/app/api/routes.py").read_text(encoding="utf-8")

checks={
    "version": "AGENTSTUDIO_FRONTEND_VERSION='5.400'" in APP and 'version="5.400"' in MAIN and '"version": "5.400"' in ROUTES,
    "actions container scroll containment": '.code-file-actions-fixed::-webkit-scrollbar' in CSS and 'overflow-x:auto' in CSS,
    "execution priority": '.code-file-actions-fixed .powershell-editor-actions' in CSS and 'order:0' in CSS,
    "find lower priority": '.code-file-actions-fixed .editor-find-toolbar-button' in CSS and 'order:1' in CSS,
    "debug lower priority": '.code-file-actions-fixed .source-debug-actions' in CSS and 'order:2' in CSS,
    "bookmark lower priority": '.code-file-actions-fixed .editor-bookmark-toolbar' in CSS and 'order:3' in CSS,
    "right safe padding": 'padding-right:7px' in CSS,
    "workspace containment kept": '.workspace-main.workspace-tab-code' in CSS and 'overflow-x:hidden !important' in CSS,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL: '+', '.join(failed))
print(f'v5.400 code toolbar right panel fit contract PASS {len(checks)}/{len(checks)}')
