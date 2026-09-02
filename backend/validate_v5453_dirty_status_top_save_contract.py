from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX=(ROOT/'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')
checks={
 'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.453'" in APP,
 'backend version': 'version="5.453"' in MAIN and '"version": "5.453"' in ROUTES,
 'codex version': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.453"' in CODEX,
 'dirty beside save': 'className="file-save-status dirty editor-save-dirty-status"' in APP,
 'dirty lower header removed': '<span className="file-save-status dirty" title="저장되지 않은 변경">●</span>' not in APP,
 'top dirty styling': '.code-file-actions-fixed .editor-save-dirty-status{' in CSS,
}
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('v5.453 contract failed: '+', '.join(failed))
print(f"v5.453 contracts: {len(checks)}/{len(checks)} PASS")
