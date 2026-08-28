from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")

checks = {
    "version": "AGENTSTUDIO_FRONTEND_VERSION='5.399'" in APP and 'version="5.399"' in MAIN,
    "path_bar_removed": 'className="file-path-bar"' not in APP,
    "path_bar_css_removed": '.file-path-bar{' not in CSS,
    "single_editor_row": 'grid-template-rows:minmax(0,1fr)' in CSS,
    "editor_tabs_kept": 'code-file-tabs-shell' in APP,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL: '+', '.join(failed))
print(f'v5.399 code editor path bar removal contract PASS {len(checks)}/{len(checks)}')
