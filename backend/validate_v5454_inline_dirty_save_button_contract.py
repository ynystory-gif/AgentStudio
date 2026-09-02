from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.454'" in APP,
    "backend version": 'version="5.454"' in MAIN and '"version": "5.454"' in ROUTES,
    "codex version": 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.454"' in CODEX,
    "save button has inline dirty dot": 'className="file-save-status dirty editor-save-button-dot"' in APP,
    "old separate dirty badge removed": 'className="file-save-status dirty editor-save-dirty-status"' not in APP,
    "inline dot styles added": '.editor-save-toolbar-button .editor-save-button-dot{' in CSS,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.454 contract failed: ' + ', '.join(failed))
print(f"v5.454 contracts: {len(checks)}/{len(checks)} PASS")
