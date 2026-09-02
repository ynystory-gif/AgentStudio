from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.450'" in APP,
    'backend version': 'version="5.450"' in MAIN and '"version": "5.450"' in ROUTES,
    'codex version': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.450"' in CODEX,
    'top save toolbar button': 'className="powershell-run-button editor-save-toolbar-button"' in APP and '>\n                저장\n              </button>' in APP,
    'save next to find': APP.find('editor-save-toolbar-button') < APP.find('editor-find-toolbar-button'),
    'lower fixed clear button': "onClick={clearCodeEditReferences}" in APP and "disabled={codeEditBusy||codeEditReferences.length===0}" in APP,
    'old lower code save removed': '>코드 저장</button>' not in APP,
    'reference head duplicate clear removed': '<span>{codeEditReferences.length}개</span>\n                  <button type="button" onClick={clearCodeEditReferences}' not in APP,
    'reference list vertical scroll': '.llm-code-chat-panel .code-edit-reference-list{' in CSS and 'overflow-y:scroll;' in CSS and 'scrollbar-gutter:stable;' in CSS,
    'reference panel can shrink': 'flex:0 1 240px;' in CSS and 'overflow:hidden;' in CSS,
    'composer order preserved': '>.ai-attachment-picker{\n  order:30;' in CSS and '>.code-llm-input{\n  order:40;' in CSS,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.450 contract failed: ' + ', '.join(failed))
print(f"v5.450 contracts: {len(checks)}/{len(checks)} PASS")
